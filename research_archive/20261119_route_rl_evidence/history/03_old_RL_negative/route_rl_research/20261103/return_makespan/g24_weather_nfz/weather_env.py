"""Single-station physical route-construction environment for wind/NFZ studies.

Mission state and reported times use minutes, matching the route project. The
weather oracle receives seconds. This module is a small synthetic research
fixture; its parameters are not a calibrated aircraft model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, hypot, isfinite
from typing import Optional

import numpy as np

from weather_oracle import (
    FlightParams,
    NoFlyZone,
    Point,
    RouteResult,
    WindField,
    WindInfeasibleError,
    WindKnot,
    plan_route,
)


@dataclass(frozen=True)
class Target:
    target_id: int
    point: Point
    energy: float = 0.015
    service_min: float = 0.5

    def __post_init__(self):
        if type(self.target_id) is not int or self.target_id < 0:
            raise ValueError("target_id must be a nonnegative integer")
        if not isfinite(self.energy) or self.energy < 0:
            raise ValueError("target energy must be finite and nonnegative")
        if not isfinite(self.service_min) or self.service_min < 0:
            raise ValueError("service_min must be finite and nonnegative")


@dataclass(frozen=True)
class WeatherInstance:
    station: Point
    targets: tuple[Target, ...]
    wind: WindField
    no_fly_zone: Optional[NoFlyZone] = None
    flight: FlightParams = FlightParams()
    coverage_radius_m: float = 5000.0
    energy_capacity: float = 1.8
    duty_limit_min: float = 60.0
    fixed_cost: float = 0.0
    time_cost: float = 1.0

    def __post_init__(self):
        if not self.targets or len({t.target_id for t in self.targets}) != len(self.targets):
            raise ValueError("instance needs uniquely identified targets")
        if any(not isinstance(t, Target) for t in self.targets):
            raise TypeError("targets must be Target values")
        for name, value in (("coverage_radius_m", self.coverage_radius_m),
                            ("energy_capacity", self.energy_capacity),
                            ("duty_limit_min", self.duty_limit_min),
                            ("fixed_cost", self.fixed_cost), ("time_cost", self.time_cost)):
            if not isfinite(value) or value < 0 or (name in ("coverage_radius_m", "duty_limit_min") and value == 0):
                raise ValueError(f"{name} must be finite and nonnegative (positive where required)")
        if self.time_cost == 0:
            raise ValueError("time_cost must be positive")
        if any(hypot(t.point.x_m - self.station.x_m,
                     t.point.y_m - self.station.y_m) > self.coverage_radius_m + 1e-7
               for t in self.targets):
            raise ValueError("every target must be within station coverage radius")


@dataclass(frozen=True)
class RouteAction:
    target_id: Optional[int] = None

    @property
    def is_return(self) -> bool:
        return self.target_id is None


class WeatherRouteEnv:
    """Construct one aircraft's trips with exact wind and NFZ-aware legs.

    RETURN is the only non-target action. Trips are sequential with zero ground
    turnaround, and the active policy chooses no operator or search action.
    """

    def __init__(self, instance: WeatherInstance, *, cost_cap: Optional[float] = None,
                 cost_tolerance: float = 1e-7, overcap_penalty: float = 100.0):
        self.instance = instance
        self.cost_cap = cost_cap
        self.cost_tolerance = cost_tolerance
        self.overcap_penalty = overcap_penalty
        if cost_cap is not None and (not isfinite(cost_cap) or cost_cap < 0):
            raise ValueError("cost_cap must be finite and nonnegative")
        if not isfinite(cost_tolerance) or cost_tolerance < 0:
            raise ValueError("cost_tolerance must be finite and nonnegative")
        if not isfinite(overcap_penalty) or overcap_penalty < 0:
            raise ValueError("overcap_penalty must be finite and nonnegative")
        self.targets = {t.target_id: t for t in instance.targets}
        self.reset()

    def reset(self):
        self.remaining = set(self.targets)
        self.current_pos = self.instance.station
        self.cumulative_duty_min = 0.0
        self.trip_elapsed_min = 0.0
        self.trip_energy = 0.0
        self.operating_min = 0.0
        self.trip: list[int] = []
        self.trips: list[list[int]] = []
        self.completion_min: dict[int, float] = {}
        self.leg_records: list[dict] = []
        self.failure: Optional[str] = None
        self.done = False
        return self.observation()

    @property
    def clock_min(self) -> float:
        return self.cumulative_duty_min + self.trip_elapsed_min

    @property
    def variable_cost(self) -> float:
        return self.operating_min * self.instance.time_cost

    @property
    def total_cost(self) -> float:
        return self.instance.fixed_cost + self.variable_cost

    @property
    def dead_end(self) -> bool:
        return not self.done and not any(self.observation()["mask"])

    def _route(self, start: Point, end: Point, depart_min: float) -> RouteResult:
        return plan_route(start, end, depart_min * 60.0, self.instance.wind,
                          self.instance.flight, self.instance.no_fly_zone)

    @staticmethod
    def _minutes(route: RouteResult) -> float:
        if not route.legal or route.arrival_time_s is None:
            raise WindInfeasibleError(route.failure or "no_legal_path")
        return (route.arrival_time_s - route.segments[0].departure_time_s) / 60.0

    def _target_projection(self, target_id: int):
        target = self.targets[target_id]
        outbound = self._route(self.current_pos, target.point, self.clock_min)
        out_min = self._minutes(outbound)
        return_depart_min = self.clock_min + out_min + target.service_min
        inbound = self._route(target.point, self.instance.station, return_depart_min)
        back_min = self._minutes(inbound)
        energy = self.trip_energy + outbound.energy + target.energy + inbound.energy
        duty = (self.cumulative_duty_min + self.trip_elapsed_min + out_min
                + target.service_min + back_min)
        return target, outbound, inbound, out_min, back_min, energy, duty

    def _return_projection(self):
        if not self.trip:
            return None
        inbound = self._route(self.current_pos, self.instance.station, self.clock_min)
        back_min = self._minutes(inbound)
        energy = self.trip_energy + inbound.energy
        duty = self.cumulative_duty_min + self.trip_elapsed_min + back_min
        return inbound, back_min, energy, duty

    def _within_cap_lower_bound(self, add_flight_min: float = 0.0,
                                remaining_service_min: float = 0.0,
                                return_min: float = 0.0) -> bool:
        if self.cost_cap is None:
            return True
        variable_budget = (self.cost_cap - self.instance.fixed_cost) / self.instance.time_cost
        lower_bound = self.operating_min + add_flight_min + remaining_service_min + return_min
        return lower_bound <= variable_budget + self.cost_tolerance / self.instance.time_cost

    def _legal_target(self, target_id: int) -> bool:
        try:
            target, _, _, out_min, back_min, energy, duty = self._target_projection(target_id)
        except (ValueError, WindInfeasibleError):
            return False
        if energy > self.instance.energy_capacity + 1e-7:
            return False
        if duty > self.instance.duty_limit_min + 1e-7:
            return False
        mandatory_service = sum(self.targets[n].service_min
                                for n in self.remaining if n != target_id)
        return self._within_cap_lower_bound(out_min + target.service_min,
                                            mandatory_service, back_min)

    def _legal_return(self) -> bool:
        try:
            _, back_min, energy, duty = self._return_projection()
        except (ValueError, WindInfeasibleError, TypeError):
            return False
        if energy > self.instance.energy_capacity + 1e-7:
            return False
        if duty > self.instance.duty_limit_min + 1e-7:
            return False
        mandatory_service = sum(self.targets[n].service_min for n in self.remaining)
        return self._within_cap_lower_bound(return_min=back_min,
                                            remaining_service_min=mandatory_service)

    def _candidate_feature(self, target_id: Optional[int]) -> list[float]:
        scale_m = max(self.instance.coverage_radius_m, 1.0)
        scale_min = max(self.instance.duty_limit_min, 1.0)
        scale_energy = max(self.instance.energy_capacity, 1.0)
        if target_id is None:
            try:
                inbound, back_min, energy, duty = self._return_projection()
                distance = inbound.distance_m
                feasible = 1.0
            except (ValueError, WindInfeasibleError, TypeError):
                distance, back_min, energy, duty, feasible = 0.0, 0.0, 0.0, 0.0, 0.0
            return [distance / scale_m, back_min / scale_min,
                    max(0.0, 1.0 - energy / scale_energy),
                    max(0.0, 1.0 - duty / scale_min), 0.0, 0.0, 0.0, 1.0,
                    feasible]
        target = self.targets[target_id]
        try:
            _, outbound, inbound, out_min, back_min, energy, duty = self._target_projection(target_id)
            distance = outbound.distance_m
            reachable = 1.0
        except (ValueError, WindInfeasibleError):
            distance = hypot(target.point.x_m - self.current_pos.x_m,
                             target.point.y_m - self.current_pos.y_m)
            out_min = back_min = 0.0
            energy, duty, reachable = 0.0, 0.0, 0.0
        return [distance / scale_m, out_min / scale_min, back_min / scale_min,
                target.service_min / scale_min, target.energy / scale_energy,
                (target.point.x_m - self.instance.station.x_m) / scale_m,
                (target.point.y_m - self.instance.station.y_m) / scale_m,
                max(0.0, 1.0 - energy / scale_energy), reachable]

    def observation(self):
        legal_ids = sorted(self.remaining)
        actions = [RouteAction(n) for n in legal_ids] + [RouteAction()]
        mask = [self._legal_target(n) for n in legal_ids] + [self._legal_return()]
        now_s = self.clock_min * 60.0
        wind = self.instance.wind.at(now_s)
        next_knot_s = next((k.time_s for k in self.instance.wind.knots if k.time_s > now_s), None)
        until_knot = 0.0 if next_knot_s is None else (next_knot_s - now_s) / 3600.0
        nfz = self.instance.no_fly_zone
        if nfz is None:
            nfz_state, nfz_until_on, nfz_until_off = 0.0, 0.0, 0.0
        else:
            nfz_state = float(nfz.on_s <= now_s < nfz.off_s)
            nfz_until_on = max(0.0, nfz.on_s - now_s) / 3600.0
            nfz_until_off = max(0.0, nfz.off_s - now_s) / 3600.0
        scale_m = max(self.instance.coverage_radius_m, 1.0)
        scale_min = max(self.instance.duty_limit_min, 1.0)
        global_features = np.asarray([
            len(self.remaining) / max(len(self.targets), 1),
            self.clock_min / scale_min,
            self.cumulative_duty_min / scale_min,
            self.trip_elapsed_min / scale_min,
            self.trip_energy / max(self.instance.energy_capacity, 1.0),
            len(self.trip) / max(len(self.targets), 1),
            (self.current_pos.x_m - self.instance.station.x_m) / scale_m,
            (self.current_pos.y_m - self.instance.station.y_m) / scale_m,
            self.instance.station.x_m / scale_m,
            self.instance.station.y_m / scale_m,
            wind.east_mps / 20.0,
            wind.north_mps / 20.0,
            until_knot,
            nfz_state,
            nfz_until_on,
            nfz_until_off,
            self.variable_cost / max(self.cost_cap or 1.0, 1.0),
        ], dtype=np.float32)
        candidates = np.asarray([self._candidate_feature(a.target_id) for a in actions],
                                dtype=np.float32)
        return {
            "global": global_features,
            "candidates": candidates,
            "mask": np.asarray(mask, dtype=np.bool_),
            "actions": tuple(actions),
            "target_ids": tuple(legal_ids),
            "done": self.done,
            "dead_end": (not self.done and not any(mask)),
        }

    def step(self, action: RouteAction):
        if self.done:
            raise RuntimeError("step after completion")
        if not isinstance(action, RouteAction) or action not in self.observation()["actions"]:
            raise ValueError("action is not in the physical action list")
        obs = self.observation()
        action_index = obs["actions"].index(action)
        if not bool(obs["mask"][action_index]):
            raise ValueError("action violates route, battery, duty, or necessary cost constraints")
        reward = 0.0
        info = {"action": action, "cost_before": self.total_cost}
        if action.is_return:
            inbound, back_min, energy, duty = self._return_projection()
            depart_s = self.clock_min * 60.0
            self._record_route(inbound, "return", depart_s)
            self.trip_elapsed_min += back_min
            self.operating_min += back_min
            self.trip_energy += inbound.energy
            self.cumulative_duty_min += self.trip_elapsed_min
            self.trips.append(self.trip.copy())
            self.trip = []
            self.trip_elapsed_min = 0.0
            self.trip_energy = 0.0
            self.current_pos = self.instance.station
            if not self.remaining:
                self.done = True
        else:
            target, outbound, _, out_min, _, _, _ = self._target_projection(action.target_id)
            depart_s = self.clock_min * 60.0
            self._record_route(outbound, str(target.target_id), depart_s)
            self.trip_elapsed_min += out_min + target.service_min
            self.operating_min += out_min + target.service_min
            self.trip_energy += outbound.energy + target.energy
            self.current_pos = target.point
            self.trip.append(target.target_id)
            self.remaining.remove(target.target_id)
            completion = self.clock_min
            self.completion_min[target.target_id] = completion
            reward = -completion / len(self.targets)
        if self.done:
            over = max(0.0, self.total_cost - (self.cost_cap or self.total_cost))
            if over > self.cost_tolerance:
                reward -= self.overcap_penalty * (1.0 + over)
                self.failure = "cost_cap_exceeded"
        info.update({"reward": reward, "cost_after": self.total_cost,
                     "completion_min": dict(self.completion_min),
                     "done": self.done, "failure": self.failure})
        return self.observation(), reward, self.done, info

    def _record_route(self, route: RouteResult, label: str, departure_s: float):
        if not route.legal or route.arrival_time_s is None:
            raise WindInfeasibleError(route.failure or "no_legal_path")
        self.leg_records.append({
            "label": label,
            "departure_time_s": departure_s,
            "arrival_time_s": route.arrival_time_s,
            "distance_m": route.distance_m,
            "energy": route.energy,
            "polyline": [[p.x_m, p.y_m] for p in route.polyline],
        })

    def result(self):
        if not self.done:
            raise RuntimeError("incomplete routes have no result")
        if self.remaining or self.trip:
            raise RuntimeError("a complete result must visit all targets and return")
        return {"trips": [trip.copy() for trip in self.trips],
                "completion_min": dict(self.completion_min),
                "MTC": sum(self.completion_min.values()) / len(self.targets),
                "M_return": self.cumulative_duty_min,
                "operating_min": self.operating_min,
                "cost": self.total_cost,
                "cost_cap": self.cost_cap,
                "cost_cap_satisfied": (self.cost_cap is None or
                    self.total_cost - self.cost_cap <= self.cost_tolerance),
                "failure": self.failure,
                "leg_records": list(self.leg_records)}


def replay_trips(instance: WeatherInstance, trips: list[list[int]], *, cost_cap=None,
                 cost_tolerance=1e-7) -> dict:
    """Independent physical replay and score for a route witness."""
    target_map = {target.target_id: target for target in instance.targets}
    seen = [nid for trip in trips for nid in trip]
    issues = []
    if sorted(seen) != sorted(target_map):
        issues.append("target_coverage")
    completion = {}
    legs = []
    total_min = total_energy = total_distance = cumulative = 0.0
    for ti, trip in enumerate(trips):
        if not trip:
            issues.append("empty_trip")
            continue
        pos = instance.station
        trip_start_min = cumulative
        trip_minutes = trip_energy = trip_distance = 0.0
        for nid in trip:
            if nid not in target_map:
                issues.append(f"unknown_target:{nid}")
                continue
            target = target_map[nid]
            try:
                route = plan_route(pos, target.point, (trip_start_min + trip_minutes) * 60,
                                   instance.wind, instance.flight, instance.no_fly_zone)
            except ValueError as exc:
                issues.append(f"route:{ti}:{nid}:{exc}")
                continue
            if not route.legal:
                issues.append(f"route:{ti}:{nid}:{route.failure}")
                continue
            flight_min = (route.arrival_time_s - (trip_start_min + trip_minutes) * 60) / 60
            trip_minutes += flight_min + target.service_min
            trip_energy += route.energy + target.energy
            trip_distance += route.distance_m
            total_distance += route.distance_m
            pos = target.point
            completion[nid] = trip_start_min + trip_minutes
            legs.append({"trip": ti, "target": nid, "departure_s": route.segments[0].departure_time_s,
                         "arrival_s": route.arrival_time_s, "distance_m": route.distance_m,
                         "energy": route.energy, "polyline": [[p.x_m, p.y_m] for p in route.polyline]})
        try:
            route = plan_route(pos, instance.station, (trip_start_min + trip_minutes) * 60,
                               instance.wind, instance.flight, instance.no_fly_zone)
        except ValueError as exc:
            issues.append(f"return:{ti}:{exc}")
            continue
        if not route.legal:
            issues.append(f"return:{ti}:{route.failure}")
            continue
        back_min = (route.arrival_time_s - (trip_start_min + trip_minutes) * 60) / 60
        trip_minutes += back_min
        trip_energy += route.energy
        trip_distance += route.distance_m
        total_distance += route.distance_m
        if trip_energy > instance.energy_capacity + 1e-7:
            issues.append(f"energy:{ti}")
        total_energy += trip_energy
        cumulative += trip_minutes
        total_min += trip_minutes
        if cumulative > instance.duty_limit_min + 1e-7:
            issues.append("cumulative_duty")
        legs.append({"trip": ti, "target": "RETURN", "departure_s": route.segments[0].departure_time_s,
                     "arrival_s": route.arrival_time_s, "distance_m": route.distance_m,
                     "energy": route.energy, "polyline": [[p.x_m, p.y_m] for p in route.polyline]})
    mtc = sum(completion.values()) / len(target_map) if len(completion) == len(target_map) else None
    cost = instance.fixed_cost + total_min * instance.time_cost
    cap_ok = cost_cap is None or cost - cost_cap <= cost_tolerance
    if not cap_ok:
        issues.append("cost_cap")
    return {"feasible": not issues, "issues": issues,
            "MTC": mtc, "M_return": cumulative, "p90_completion_min": (
                sorted(completion.values())[ceil(0.9 * len(completion)) - 1]
                if completion else None),
            "completion_min": completion, "operating_min": total_min,
            "energy": total_energy, "distance_m": total_distance,
            "cost": cost, "cost_cap": cost_cap,
            "cost_cap_satisfied": cap_ok, "legs": legs}
