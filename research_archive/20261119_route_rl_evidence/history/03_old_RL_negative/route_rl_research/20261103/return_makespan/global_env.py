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


# The station-local API above is an unchanged, hash-preserved copy.  The new
# wrapper is generic engineering, not the proposed scientific contribution.
import math

from scorer import CostAnchor, COST_TOLERANCE, validate_candidate


class FullMapRouteEnv:
    """Physical route construction with a global clock and necessary cost mask.

    Station order is a fixed program input, never a policy action.  This is a
    conditional (cross-station autoregressive) environment.  Its dynamic cost
    mask MUST NOT be used with a product-independent station-gradient formula.
    A passed necessary mask does not certify that the remaining map completes.
    """

    def __init__(self, instance, anchor, *, epsilon=0.0,
                 cost_tolerance=COST_TOLERANCE, station_order=None,
                 use_necessary_cost_mask=True):
        if type(epsilon) not in (int, float) or not math.isfinite(epsilon) or epsilon < 0:
            raise ValueError("epsilon must be finite and nonnegative")
        if (type(cost_tolerance) not in (int, float)
                or not math.isfinite(cost_tolerance) or cost_tolerance < 0):
            raise ValueError("absolute cost tolerance must be finite and nonnegative")
        if type(use_necessary_cost_mask) is not bool:
            raise ValueError("use_necessary_cost_mask must be bool")
        self.instance = instance
        self.anchor = anchor if isinstance(anchor, CostAnchor) else CostAnchor.from_solution(instance, anchor)
        self.anchor.verify(instance)
        self.epsilon = epsilon
        self.cost_tolerance = cost_tolerance
        self.cost_budget = self.anchor.cost * (1.0 + epsilon)
        if not math.isfinite(self.cost_budget):
            raise ValueError("nonfinite global cost budget")
        self.use_necessary_cost_mask = use_necessary_cost_mask
        self.target_pools = {si: [] for si in range(len(instance.stations))}
        for nid, si in self.anchor.target_station:
            self.target_pools[si].append(nid)
        active = tuple(si for si, pool in self.target_pools.items() if pool)
        order = active if station_order is None else tuple(station_order)
        if (any(type(si) is not int for si in order)
                or len(order) != len(active) or set(order) != set(active)):
            raise ValueError("station_order must be a permutation of nonempty stations")
        self.station_order = order
        self.fixed_cost = sum(instance.fixed(kind) for kind in self.anchor.station_types)
        self.reset()

    def reset(self):
        self.station_envs = {
            si: StationRouteEnv(self.instance, si, self.anchor.station_types[si], self.target_pools[si])
            for si in self.station_order
        }
        self.total_reward = 0.0
        self.action_count = 0
        self._terminal_score = None
        return self.observation()

    @property
    def active_station(self):
        return next((si for si in self.station_order if not self.station_envs[si].done), None)

    @property
    def done(self):
        return self.active_station is None

    @property
    def potential(self):
        # Accrued physical clocks, not a sum of station maxima or decode time.
        return max((env.cumulative_duty[d] + env.trip_elapsed[d]
                    for env in self.station_envs.values() for d in env.slots), default=0.0)

    @property
    def operating_minutes(self):
        return sum(env.operating_minutes for env in self.station_envs.values())

    def necessary_cost_lower_bound(self, action=None):
        """Immediate returns + mandatory service, without a completion claim."""
        p = self.instance.params
        spent = self.operating_minutes
        service_left = sum(env.targets[nid].service
                           for env in self.station_envs.values() for nid in env.remaining)
        returns = sum(self.instance.dist[env.current_pos[d], env.station.id] / p.speed
                      for env in self.station_envs.values() for d in env.slots
                      if env.current_trip[d])
        if action is not None:
            si = self.active_station
            if si is None:
                raise ValueError("no active physical station")
            env = self.station_envs[si]
            if not self._typed_action(action) or not env.legal(action):
                raise IllegalAction("cannot project an illegal physical action")
            d = action.slot
            old_return = (self.instance.dist[env.current_pos[d], env.station.id] / p.speed
                          if env.current_trip[d] else 0.0)
            if action.is_return:
                spent += old_return
                returns -= old_return
            else:
                node = env.targets[action.target_id]
                travel = self.instance.dist[env.current_pos[d], node.id] / p.speed
                spent += travel + node.service
                service_left -= node.service
                returns += self.instance.dist[node.id, env.station.id] / p.speed - old_return
        return self.fixed_cost + p.time_cost * (spent + service_left + returns)

    @staticmethod
    def _typed_action(action):
        return (isinstance(action, RouteAction) and type(action.slot) is int
                and (action.target_id is None or type(action.target_id) is int))

    def _actions_and_masks(self):
        si = self.active_station
        if si is None:
            return (), (), (), ()
        local = self.station_envs[si].observation()
        actions, physics = local["actions"], local["mask"]
        cost = tuple(bool(ok) and self.necessary_cost_lower_bound(a) - self.cost_budget <= self.cost_tolerance
                     for a, ok in zip(actions, physics))
        mask = tuple(bool(ok) and (cost_ok or not self.use_necessary_cost_mask)
                     for ok, cost_ok in zip(physics, cost))
        return actions, physics, cost, mask

    @property
    def dead_end(self):
        return not self.done and not any(self._actions_and_masks()[3])

    @property
    def terminated(self):
        return self.done or self.dead_end

    def legal(self, action):
        if not self._typed_action(action):
            return False
        actions, _, _, mask = self._actions_and_masks()
        return any(action == a and ok for a, ok in zip(actions, mask))

    def observation(self):
        actions, physics, cost, mask = self._actions_and_masks()
        si = self.active_station
        dead_end = si is not None and not any(mask)
        status = ("COMPLETE_ADMISSIBLE" if self.done and self._terminal_score
                  and self._terminal_score["admissible"] else
                  "COMPLETE_INVALID" if self.done else "DEAD_END" if dead_end else "RUNNING")
        return {
            "active_station": si,
            "station_order": self.station_order,
            "station": None if si is None else self.station_envs[si].observation(),
            "all_station_states": {j: env.observation() for j, env in self.station_envs.items()},
            "actions": actions, "physics_mask": physics, "necessary_cost_mask": cost, "mask": mask,
            "global_cost_budget": self.cost_budget,
            "necessary_cost_lower_bound": self.necessary_cost_lower_bound(),
            "necessary_mask_is_completion_certificate": False,
            "elapsed_makespan_potential": self.potential,
            "done": self.done, "dead_end": dead_end,
            "terminated": self.done or dead_end, "status": status,
            "anchor_solution_sha256": self.anchor.solution_sha256,
        }

    def step(self, action):
        if self.terminated:
            raise RuntimeError("step called after complete construction or explicit dead-end")
        if not self.legal(action):
            raise IllegalAction(f"illegal physical route action or necessary-cost exclusion: {action}")
        si, before = self.active_station, self.potential
        self.station_envs[si].step(action)  # Ignore old local operating-cost reward.
        self.action_count += 1
        reward = before - self.potential
        self.total_reward += reward
        if self.done:
            self._terminal_score = validate_candidate(
                self.instance, self.candidate(), self.anchor,
                epsilon=self.epsilon, cost_tolerance=self.cost_tolerance)
        obs = self.observation()
        complete_valid = bool(self._terminal_score and self._terminal_score["admissible"])
        info = {
            "physical_station": si, "physical_slot": action.slot,
            "visited_target": action.target_id, "is_return": action.is_return,
            "episode_reward": self.total_reward,
            "reward_is_complete_objective": complete_valid,
            "failure": ("dead_end" if obs["dead_end"] else
                        "terminal_invalid" if self.done and not complete_valid else None),
            "terminal_score": self._terminal_score,
        }
        return obs, reward, obs["terminated"], info

    def candidate(self):
        if not self.done:
            raise RuntimeError("partial construction is not a complete candidate")
        solution = self.anchor.solution()
        solution["routes"] = [[[], []] for _ in self.instance.stations]
        for si, env in self.station_envs.items():
            solution["routes"][si] = env.result()["routes"]
        return solution

    def result(self):
        if not self.done or not self._terminal_score or not self._terminal_score["admissible"]:
            raise RuntimeError("no complete admissible map; raw failure is retained without hidden fallback")
        return {"solution": self.candidate(), "score": dict(self._terminal_score),
                "reward": self.total_reward, "action_count": self.action_count}
