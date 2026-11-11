"""Direct physical route-construction environment for one fixed station."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


EPS = 1e-7


@dataclass(frozen=True, order=True)
class RouteAction:
    slot: int
    target_id: Optional[int] = None

    @property
    def is_return(self) -> bool:
        return self.target_id is None


class IllegalAction(ValueError):
    pass


class StationRouteEnv:
    """Construct all physical routes for one fixed-mode station target pool.

    Slot 0 is LD and slot 1 is SD. SABS exposes only slot 1. RETURN closes
    one nonempty trip, resets trip-local state, and preserves cumulative duty.
    """

    def __init__(self, instance, station_idx: int, station_type: int, target_ids):
        if station_type not in (1, 2):
            raise ValueError("a nonempty route pool requires SABS(1) or DABS(2)")
        self.instance = instance
        self.params = instance.params
        self.station_idx = int(station_idx)
        self.station_type = int(station_type)
        self.station = instance.stations[self.station_idx]
        self.target_ids = tuple(sorted(int(n) for n in target_ids))
        if len(set(self.target_ids)) != len(self.target_ids):
            raise ValueError("target_ids must be unique")
        missing = set(self.target_ids) - set(instance.target_ids)
        if missing:
            raise ValueError(f"non-target IDs in station pool: {sorted(missing)}")
        self.targets = {n: instance.nodes[n] for n in self.target_ids}
        self.slots = (1,) if self.station_type == 1 else (0, 1)
        self.capacity = {
            0: self.params.large_battery,
            1: self.params.small_battery,
        }
        self.duty_limit = (
            self.params.small_duration if self.station_type == 1
            else self.params.large_duration
        )
        self.radius = (
            self.params.small_radius if self.station_type == 1
            else self.params.large_radius
        )
        self.reset()

    def reset(self):
        self.remaining = set(self.target_ids)
        self.routes = {slot: [] for slot in self.slots}
        self.current_pos = {slot: self.station.id for slot in self.slots}
        self.current_trip = {slot: [] for slot in self.slots}
        self.trip_energy = {slot: 0.0 for slot in self.slots}
        self.trip_elapsed = {slot: 0.0 for slot in self.slots}
        self.cumulative_duty = {slot: 0.0 for slot in self.slots}
        self.operating_minutes = 0.0
        self.total_reward = 0.0
        return self.observation()

    @property
    def done(self):
        return not self.remaining and all(not self.current_trip[d] for d in self.slots)

    def _target_legal(self, slot: int, target_id: int) -> bool:
        if slot not in self.slots or target_id not in self.remaining:
            return False
        target = self.targets[target_id]
        station_distance = self.instance.dist[self.station.id, target_id]
        if station_distance > self.radius + EPS:
            return False
        travel = self.instance.dist[self.current_pos[slot], target_id] / self.params.speed
        back = station_distance / self.params.speed
        energy = (
            self.trip_energy[slot]
            + travel * self.params.flight_energy
            + target.energy
            + back * self.params.flight_energy
        )
        duty = (
            self.cumulative_duty[slot]
            + self.trip_elapsed[slot]
            + travel + target.service + back
        )
        return energy <= self.capacity[slot] + EPS and duty <= self.duty_limit + EPS

    def _return_legal(self, slot: int) -> bool:
        if slot not in self.slots or not self.current_trip[slot]:
            return False
        back = self.instance.dist[self.current_pos[slot], self.station.id] / self.params.speed
        energy = self.trip_energy[slot] + back * self.params.flight_energy
        duty = self.cumulative_duty[slot] + self.trip_elapsed[slot] + back
        return energy <= self.capacity[slot] + EPS and duty <= self.duty_limit + EPS

    def legal(self, action: RouteAction) -> bool:
        if action.is_return:
            return self._return_legal(action.slot)
        return self._target_legal(action.slot, action.target_id)

    def observation(self):
        actions = tuple(
            [RouteAction(slot, nid) for nid in sorted(self.remaining) for slot in self.slots]
            + [RouteAction(slot) for slot in self.slots]
        )
        mask = tuple(self.legal(a) for a in actions)
        return {
            "station_idx": self.station_idx,
            "station_type": self.station_type,
            "station_id": self.station.id,
            "remaining_target_ids": tuple(sorted(self.remaining)),
            "slots": {
                slot: {
                    "current_pos": self.current_pos[slot],
                    "current_trip": tuple(self.current_trip[slot]),
                    "closed_trips": tuple(tuple(t) for t in self.routes[slot]),
                    "trip_energy": self.trip_energy[slot],
                    "trip_elapsed": self.trip_elapsed[slot],
                    "cumulative_duty": self.cumulative_duty[slot],
                    "battery_capacity": self.capacity[slot],
                    "duty_limit": self.duty_limit,
                }
                for slot in self.slots
            },
            "actions": actions,
            "mask": mask,
            "done": self.done,
            "dead_end": not self.done and not any(mask),
        }

    def step(self, action: RouteAction):
        if self.done:
            raise RuntimeError("step called after route construction completed")
        if not self.legal(action):
            raise IllegalAction(f"illegal physical route action: {action}")

        slot = action.slot
        cost_delta = 0.0
        info = {}
        if action.is_return:
            back = self.instance.dist[self.current_pos[slot], self.station.id] / self.params.speed
            cost_delta = back
            self.routes[slot].append(list(self.current_trip[slot]))
            self.cumulative_duty[slot] += self.trip_elapsed[slot] + back
            self.current_pos[slot] = self.station.id
            self.current_trip[slot] = []
            self.trip_energy[slot] = 0.0
            self.trip_elapsed[slot] = 0.0
            info["returned_slot"] = slot
        else:
            nid = action.target_id
            travel = self.instance.dist[self.current_pos[slot], nid] / self.params.speed
            target = self.targets[nid]
            self.trip_energy[slot] += travel * self.params.flight_energy + target.energy
            self.trip_elapsed[slot] += travel + target.service
            self.current_pos[slot] = nid
            self.current_trip[slot].append(nid)
            self.remaining.remove(nid)
            cost_delta = travel + target.service
            info["visited_target"] = nid

        self.operating_minutes += cost_delta
        reward = -cost_delta * self.params.time_cost
        self.total_reward += reward
        info.update({
            "cost_delta_minutes": cost_delta,
            "operating_minutes": self.operating_minutes,
            "cumulative_duty": dict(self.cumulative_duty),
            "done": self.done,
        })
        return self.observation(), reward, self.done, info

    def result(self):
        if not self.done:
            raise RuntimeError("cannot return an incomplete station route set")
        return {
            "routes": [
                [list(trip) for trip in self.routes.get(slot, [])]
                for slot in (0, 1)
            ],
            "operating_minutes": float(self.operating_minutes),
            "route_variable_cost": float(self.operating_minutes * self.params.time_cost),
            "reward": float(self.total_reward),
            "visited_target_ids": tuple(self.target_ids),
        }
