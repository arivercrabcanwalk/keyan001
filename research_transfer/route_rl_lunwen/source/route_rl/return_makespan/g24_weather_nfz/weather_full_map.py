"""Fixed-outer, multi-station weather/NFZ route construction.

The policy's only decisions are physical `(station, slot, target)` and
`(station, slot, RETURN)` actions.  Stations, station types, and target-to-
station ownership are fixed by the common anchor.  Every slot starts at zero;
the Python decode order is therefore never a launch-time decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isfinite
from pathlib import Path
import sys
from typing import Optional

import numpy as np

PACKAGE_ROOT = Path(__file__).resolve().parent
PARENT_ROOT = PACKAGE_ROOT.parent
if str(PARENT_ROOT) not in sys.path:
    sys.path.insert(0, str(PARENT_ROOT))

from scorer import CostAnchor, COST_TOLERANCE, score_solution, validate_candidate  # noqa: E402
from weather_oracle import FlightParams, NoFlyZone, Point, RouteResult, WindField, plan_route  # noqa: E402
from weather_replay import replay_route  # noqa: E402


EPS = 1e-7
MAX_WIND_KNOTS = 4
MAX_NFZ_VERTICES = 4
# The frozen Liu-family envelope reaches ten stations and 110 targets
# (`10_110`); a DABS at every station gives twenty physical route slots.
MAX_POLICY_SLOTS = 20
MAX_POLICY_TARGETS = 128


@dataclass(frozen=True, order=True)
class WeatherMapAction:
    station_idx: int
    slot: int
    target_id: Optional[int] = None

    @property
    def is_return(self) -> bool:
        return self.target_id is None


@dataclass(frozen=True)
class WeatherMapScenario:
    """Known forecast and scheduled closure for a fixed-outer route problem."""

    wind: WindField
    no_fly_zone: Optional[NoFlyZone] = None
    flight: Optional[FlightParams] = None
    name: str = "synthetic_deterministic_forecast_nfz_v1"

    def __post_init__(self):
        if not self.name:
            raise ValueError("scenario needs a nonempty name")
        if len(self.wind.knots) > MAX_WIND_KNOTS:
            raise ValueError(f"v1 schema supports at most {MAX_WIND_KNOTS} wind knots")
        if self.no_fly_zone is not None and len(self.no_fly_zone.vertices) > MAX_NFZ_VERTICES:
            raise ValueError(f"v1 schema supports at most {MAX_NFZ_VERTICES} NFZ vertices")


@dataclass
class _Slot:
    station_idx: int
    slot: int
    station_id: int
    current_id: int
    clock_s: float = 0.0
    static_operating_min: float = 0.0
    trip_energy: float = 0.0
    current_trip: list[int] = field(default_factory=list)
    closed_trips: list[list[int]] = field(default_factory=list)


def _point(node) -> Point:
    return Point(float(node.x), float(node.y))


def _minutes(route: RouteResult) -> float:
    if not route.legal or route.arrival_time_s is None:
        raise ValueError(route.failure or "no_legal_path")
    if not route.segments:
        return 0.0
    return (route.arrival_time_s - route.segments[0].departure_time_s) / 60.0


def _scenario_flight(instance, scenario: WeatherMapScenario) -> FlightParams:
    return scenario.flight or FlightParams(instance.params.speed, instance.params.flight_energy)


def _station_slots(station_type: int) -> tuple[int, ...]:
    if station_type == 1:
        return (1,)
    if station_type == 2:
        return (0, 1)
    return ()


def _slot_capacity(instance, slot: int) -> float:
    return instance.params.large_battery if slot == 0 else instance.params.small_battery


def _duty_limit(instance, station_type: int) -> float:
    return instance.params.large_duration if station_type == 2 else instance.params.small_duration


def _fixed_cost(instance, station_types) -> float:
    return sum(instance.fixed(kind) for kind in station_types)


def _route_with_primary_oracle(start: Point, end: Point, departure_s: float, scenario, flight):
    return plan_route(start, end, departure_s, scenario.wind, flight, scenario.no_fly_zone)


def replay_weather_solution(instance, anchor, scenario: WeatherMapScenario, solution: dict,
                            *, weather_cost_cap: Optional[float] = None,
                            tolerance: float = COST_TOLERANCE,
                            strict_weather_cap: bool = True) -> dict:
    """Full-map weather replay using the independent `weather_replay` oracle.

    This function never reads environment state, masks, leg records, or the
    primary route-planning function.  It also calls the original scorer for
    unchanged LRPHSD feasibility diagnostics.
    """
    anchor = anchor if isinstance(anchor, CostAnchor) else CostAnchor.from_solution(instance, anchor)
    original = score_solution(instance, solution)
    original_admission = validate_candidate(instance, solution, anchor, epsilon=0.0,
                                            cost_tolerance=tolerance)
    issues = []
    if solution.get("station_types") != list(anchor.station_types):
        issues.append("station_types_changed")
    expected_owner = dict(anchor.target_station)
    routes = solution.get("routes") if isinstance(solution, dict) else None
    if not isinstance(routes, list) or len(routes) != len(instance.stations):
        return {"admissible": False, "issues": issues + ["route_dimensions"],
                "original_score": original}
    flight = _scenario_flight(instance, scenario)
    target_seen = []
    completion = {}
    slot_rows = []
    total_operating = 0.0
    max_clock = 0.0
    for si, station in enumerate(instance.stations):
        station_type = anchor.station_types[si]
        station_routes = routes[si]
        if not isinstance(station_routes, list) or len(station_routes) != 2:
            issues.append(f"slot_dimensions:{si}")
            continue
        for slot in (0, 1):
            trips = station_routes[slot]
            if slot not in _station_slots(station_type) and trips:
                issues.append(f"unavailable_slot:{si}:{slot}")
            if not isinstance(trips, list):
                issues.append(f"trip_list:{si}:{slot}")
                continue
            clock_s = 0.0
            leg_rows = []
            for ti, trip in enumerate(trips):
                if not trip:
                    issues.append(f"empty_trip:{si}:{slot}:{ti}")
                    continue
                current = _point(station)
                energy = 0.0
                for nid in trip:
                    if type(nid) is not int or nid not in instance.nodes or nid not in instance.target_ids:
                        issues.append(f"unknown_target:{si}:{slot}:{nid}")
                        continue
                    if expected_owner.get(nid) != si:
                        issues.append(f"target_station_changed:{nid}")
                    target = instance.nodes[nid]
                    departure_s = clock_s
                    route = replay_route(current, _point(target), departure_s, scenario.wind, flight,
                                         scenario.no_fly_zone)
                    if not route.legal or route.arrival_s is None:
                        issues.append(f"outbound:{si}:{slot}:{nid}:{route.failure}")
                        continue
                    energy += route.energy + target.energy
                    clock_s = route.arrival_s + target.service * 60.0
                    completion[nid] = clock_s / 60.0
                    target_seen.append(nid)
                    leg_rows.append({"trip": ti, "target": nid, "departure_s": departure_s,
                                     "arrival_s": route.arrival_s, "distance_m": route.distance_m,
                                     "energy": route.energy, "polyline": [[p.x_m, p.y_m] for p in route.path]})
                    current = _point(target)
                departure_s = clock_s
                route = replay_route(current, _point(station), departure_s, scenario.wind, flight,
                                     scenario.no_fly_zone)
                if not route.legal or route.arrival_s is None:
                    issues.append(f"return:{si}:{slot}:{ti}:{route.failure}")
                    continue
                energy += route.energy
                clock_s = route.arrival_s
                if energy > _slot_capacity(instance, slot) + EPS:
                    issues.append(f"battery:{si}:{slot}:{ti}")
                leg_rows.append({"trip": ti, "target": "RETURN", "departure_s": departure_s,
                                 "arrival_s": route.arrival_s, "distance_m": route.distance_m,
                                 "energy": route.energy, "polyline": [[p.x_m, p.y_m] for p in route.path]})
            clock_min = clock_s / 60.0
            if clock_min > _duty_limit(instance, station_type) + EPS:
                issues.append(f"duty:{si}:{slot}")
            total_operating += clock_min
            max_clock = max(max_clock, clock_min)
            slot_rows.append({"station_idx": si, "slot": slot, "clock_min": clock_min,
                              "trips": trips, "legs": leg_rows})
    if sorted(target_seen) != sorted(instance.target_ids):
        issues.append("target_exact_once")
    if not original_admission.get("admissible"):
        issues.append("original_cost_or_domain_cap")
    weather_cost = _fixed_cost(instance, anchor.station_types) + instance.params.time_cost * total_operating
    cap_ok = weather_cost_cap is not None and weather_cost - weather_cost_cap <= tolerance
    if weather_cost_cap is None:
        if strict_weather_cap:
            issues.append("weather_cost_cap_missing")
            issues.append("weather_cost_cap")
    elif not cap_ok:
        issues.append("weather_cost_cap")
    return {"schema": "weather_full_map_replay_v1", "admissible": not issues,
            "issues": issues, "original_score": original, "original_admission": original_admission,
            "weather_cost": weather_cost,
            "weather_cost_cap": weather_cost_cap, "weather_cost_cap_satisfied": cap_ok,
            "strict_weather_cap": strict_weather_cap,
            "M_return": max_clock,
            "MTC": (sum(completion.values()) / len(instance.target_ids)
                    if len(completion) == len(instance.target_ids) else None),
            "completion_min": completion, "slot_rows": slot_rows,
            "forecast_name": scenario.name}


class WeatherFullMapEnv:
    """Weather-aware multi-station route constructor with physical actions only."""

    # The 42 fixed features comprise generic state, forecast/NFZ, and the
    # original-LRPHSD cost cap/lower bound.  Both budget fields affect future
    # physical-action legality and therefore must be model inputs.
    global_dim = 42 + 9 * MAX_POLICY_SLOTS + 7 * MAX_POLICY_TARGETS
    candidate_dim = 20

    def __init__(self, instance, anchor, scenario: WeatherMapScenario, *,
                 weather_cost_cap: Optional[float] = None,
                 cost_tolerance: float = COST_TOLERANCE):
        self.instance = instance
        if any(not isfinite(n.service) or n.service < 0 or not isfinite(n.energy) or n.energy < 0
               for n in instance.targets):
            raise ValueError("target service and energy must be finite and nonnegative")
        self.anchor = anchor if isinstance(anchor, CostAnchor) else CostAnchor.from_solution(instance, anchor)
        self.anchor.verify(instance)
        self.scenario = scenario
        self.flight = _scenario_flight(instance, scenario)
        if weather_cost_cap is not None and (not isfinite(weather_cost_cap) or weather_cost_cap < 0):
            raise ValueError("weather_cost_cap must be finite and nonnegative")
        if not isfinite(cost_tolerance) or cost_tolerance < 0:
            raise ValueError("cost_tolerance must be finite and nonnegative")
        self.weather_cost_cap = weather_cost_cap
        self.cost_tolerance = cost_tolerance
        self.target_pools = {si: set() for si in range(len(instance.stations))}
        for nid, si in self.anchor.target_station:
            self.target_pools[si].add(nid)
        self.active_stations = tuple(si for si, pool in self.target_pools.items() if pool)
        physical_slots = sum(len(_station_slots(self.anchor.station_types[si])) for si in self.active_stations)
        if physical_slots > MAX_POLICY_SLOTS or len(instance.target_ids) > MAX_POLICY_TARGETS:
            raise ValueError("v1 policy-state table capacity exceeded")
        self.fixed_cost = _fixed_cost(instance, self.anchor.station_types)
        self.reset()

    def reset(self):
        self.remaining = {si: set(pool) for si, pool in self.target_pools.items()}
        self.slots = {}
        for si in self.active_stations:
            station = self.instance.stations[si]
            for slot in _station_slots(self.anchor.station_types[si]):
                self.slots[(si, slot)] = _Slot(si, slot, station.id, station.id)
        self.total_reward = 0.0
        self.action_count = 0
        self._terminal_replay = None
        self.failure = None
        if self.dead_end:
            self.failure = "dead_end"
        return self.observation()

    @property
    def done(self) -> bool:
        return (all(not pool for pool in self.remaining.values())
                and all(not state.current_trip for state in self.slots.values()))

    @property
    def potential(self) -> float:
        return max((state.clock_s / 60.0 for state in self.slots.values()), default=0.0)

    @property
    def weather_cost(self) -> float:
        return self.fixed_cost + self.instance.params.time_cost * sum(
            state.clock_s / 60.0 for state in self.slots.values())

    def _original_lower_bound(self, action: Optional[WeatherMapAction] = None) -> float:
        """Necessary original-model cost bound from direct legs and open returns.

        It preserves the parent strict `C <= C_ref` contract during decoding;
        the exact original scorer remains the terminal authority.
        """
        spent = sum(state.static_operating_min for state in self.slots.values())
        current = {key: (state.current_id, bool(state.current_trip)) for key, state in self.slots.items()}
        service_left = sum(self.instance.nodes[nid].service for pool in self.remaining.values() for nid in pool)
        if action is not None:
            state = self.slots[(action.station_idx, action.slot)]
            key = (action.station_idx, action.slot)
            if action.is_return:
                if not state.current_trip:
                    return float("inf")
                spent += self.instance.dist[state.current_id, state.station_id] / self.instance.params.speed
                current[key] = (state.station_id, False)
            else:
                target = self.instance.nodes[action.target_id]
                spent += self.instance.dist[state.current_id, target.id] / self.instance.params.speed + target.service
                service_left -= target.service
                current[key] = (target.id, True)
        returns = sum(self.instance.dist[current_id, self.slots[key].station_id] / self.instance.params.speed
                      for key, (current_id, open_trip) in current.items() if open_trip)
        return self.fixed_cost + self.instance.params.time_cost * (spent + returns + service_left)

    def _weather_route(self, start_id: int, end_id: int, departure_s: float) -> RouteResult:
        return _route_with_primary_oracle(_point(self.instance.nodes[start_id]),
                                          _point(self.instance.nodes[end_id]), departure_s,
                                          self.scenario, self.flight)

    def _project_target(self, action: WeatherMapAction):
        state = self.slots[(action.station_idx, action.slot)]
        target = self.instance.nodes[action.target_id]
        outbound = self._weather_route(state.current_id, target.id, state.clock_s)
        out_min = _minutes(outbound)
        inbound = self._weather_route(target.id, state.station_id,
                                      outbound.arrival_time_s + target.service * 60.0)
        # A direct return can be temporarily infeasible while a later target
        # changes the departure time (for example, a scheduled NFZ closes).
        # The target mask therefore uses the return only as a candidate feature;
        # exact trip energy/duty and eventual return remain terminal replay
        # obligations.  This is a necessary-bound mask, not a completion proof.
        back_min = _minutes(inbound) if inbound.legal else 0.0
        return {"target": target, "outbound": outbound, "inbound": inbound,
                "out_min": out_min, "back_min": back_min,
                "energy": state.trip_energy + outbound.energy + target.energy,
                "duty_min": state.clock_s / 60.0 + out_min + target.service + back_min}

    def _project_return(self, action: WeatherMapAction):
        state = self.slots[(action.station_idx, action.slot)]
        if not state.current_trip:
            return None
        inbound = self._weather_route(state.current_id, state.station_id, state.clock_s)
        back_min = _minutes(inbound)
        return {"inbound": inbound, "back_min": back_min,
                "energy": state.trip_energy + inbound.energy,
                "duty_min": state.clock_s / 60.0 + back_min}

    def _weather_lower_bound(self, action: Optional[WeatherMapAction] = None) -> float:
        """Weather cost lower bound: elapsed slot time plus remaining service.

        Future flight time is omitted: immediate-return times are not lower
        bounds when forecasts and temporary closures vary with time.
        """
        spent = sum(state.clock_s / 60.0 for state in self.slots.values())
        service_left = sum(self.instance.nodes[nid].service for pool in self.remaining.values() for nid in pool)
        if action is not None:
            if action.is_return:
                projected = self._project_return(action)
                if projected is None:
                    return float("inf")
                spent += projected["back_min"]
            else:
                projected = self._project_target(action)
                spent += projected["out_min"] + projected["target"].service
                service_left -= projected["target"].service
        return self.fixed_cost + self.instance.params.time_cost * (spent + service_left)

    def _legal(self, action: WeatherMapAction) -> bool:
        if not isinstance(action, WeatherMapAction) or (action.station_idx, action.slot) not in self.slots:
            return False
        state = self.slots[(action.station_idx, action.slot)]
        station_type = self.anchor.station_types[action.station_idx]
        try:
            if action.is_return:
                projected = self._project_return(action)
                if projected is None:
                    return False
            else:
                if action.target_id not in self.remaining[action.station_idx]:
                    return False
                target = self.instance.nodes[action.target_id]
                station = self.instance.stations[action.station_idx]
                if hypot(target.x - station.x, target.y - station.y) > self.instance.radius(station_type) + EPS:
                    return False
                projected = self._project_target(action)
            if projected["energy"] > _slot_capacity(self.instance, state.slot) + EPS:
                return False
            if projected["duty_min"] > _duty_limit(self.instance, station_type) + EPS:
                return False
            lower = self._weather_lower_bound(action)
            weather_ok = (self.weather_cost_cap is None
                          or lower - self.weather_cost_cap <= self.cost_tolerance)
            original_ok = self._original_lower_bound(action) - self.anchor.cost <= self.cost_tolerance
            return weather_ok and original_ok
        except (ValueError, KeyError):
            return False

    def _actions(self):
        actions = []
        for si, slot in sorted(self.slots):
            actions.extend(WeatherMapAction(si, slot, nid) for nid in sorted(self.remaining[si]))
            actions.append(WeatherMapAction(si, slot))
        mask = tuple(self._legal(action) for action in actions)
        return tuple(actions), mask

    @property
    def dead_end(self) -> bool:
        return not self.done and not any(self._actions()[1])

    @property
    def terminated(self) -> bool:
        return self.done or self.dead_end

    def _forecast_features(self):
        wind = []
        wind_mask = []
        for knot in self.scenario.wind.knots:
            wind.extend([knot.time_s / 3600.0 / 24.0, knot.east_mps / 20.0, knot.north_mps / 20.0])
            wind_mask.append(1.0)
        wind.extend([0.0] * (3 * (MAX_WIND_KNOTS - len(self.scenario.wind.knots))))
        wind_mask.extend([0.0] * (MAX_WIND_KNOTS - len(self.scenario.wind.knots)))
        vertices = []
        vertex_mask = []
        zone = self.scenario.no_fly_zone
        if zone is not None:
            # Every geometric component exposed to the policy uses this same
            # declared coordinate frame.  Do not normalize an NFZ from hidden
            # instance extrema: that can alias distinct physical closures.
            scale = max(1.0, self.instance.params.large_radius)
            for point in zone.vertices:
                vertices.extend([point.x_m / scale, point.y_m / scale])
                vertex_mask.append(1.0)
            vertices.extend([0.0] * (2 * (MAX_NFZ_VERTICES - len(zone.vertices))))
            vertex_mask.extend([0.0] * (MAX_NFZ_VERTICES - len(zone.vertices)))
            zone_features = [1.0, zone.on_s / 3600.0 / 24.0, zone.off_s / 3600.0 / 24.0]
        else:
            vertices = [0.0] * (2 * MAX_NFZ_VERTICES)
            vertex_mask = [0.0] * MAX_NFZ_VERTICES
            zone_features = [0.0, 0.0, 0.0]
        return wind + wind_mask + vertices + vertex_mask + zone_features

    def _policy_state_features(self):
        """Fixed-size Markov state table consumed directly by the policy.

        Receipt dictionaries below remain human-auditable, but this table makes
        every slot's current physical state and every target's immutable/served
        state part of the actual tensor supplied to PPO, A2C, and controls.
        """
        scale = max(1.0, self.instance.params.large_radius)
        max_duty = max(1.0, self.instance.params.large_duration)
        max_capacity = max(1.0, self.instance.params.large_battery, self.instance.params.small_battery)
        slots = []
        for (si, slot), state in sorted(self.slots.items()):
            current = self.instance.nodes[state.current_id]
            station = self.instance.stations[si]
            duty = max(1.0, _duty_limit(self.instance, self.anchor.station_types[si]))
            capacity = max(1.0, _slot_capacity(self.instance, slot))
            slots.extend([1.0, si / max(1, len(self.instance.stations)), float(slot),
                          (current.x - station.x) / scale, (current.y - station.y) / scale,
                          state.clock_s / 60.0 / duty, state.trip_energy / capacity,
                          float(bool(state.current_trip)), state.static_operating_min / max_duty])
        slots.extend([0.0] * (9 * (MAX_POLICY_SLOTS - len(self.slots))))
        owners = dict(self.anchor.target_station)
        targets = []
        for nid in sorted(self.instance.target_ids):
            target = self.instance.nodes[nid]
            owner = owners[nid]
            targets.extend([1.0, target.x / scale, target.y / scale, target.service / max_duty,
                            target.energy / max_capacity, float(nid in self.remaining[owner]),
                            owner / max(1, len(self.instance.stations))])
        targets.extend([0.0] * (7 * (MAX_POLICY_TARGETS - len(self.instance.target_ids))))
        return slots + targets

    def _candidate_features(self, action: WeatherMapAction):
        state = self.slots[(action.station_idx, action.slot)]
        scale_m = max(1.0, self.instance.params.large_radius)
        duty = max(1.0, _duty_limit(self.instance, self.anchor.station_types[action.station_idx]))
        cap = max(1.0, _slot_capacity(self.instance, state.slot))
        original_scale = max(1.0, self.anchor.cost)
        try:
            cost_slack = 0.0 if self.weather_cost_cap is None else (
                (self.weather_cost_cap - self._weather_lower_bound(action))
                / max(self.weather_cost_cap, 1.0)
            )
            current = self.instance.nodes[state.current_id]
            current_x = (current.x - self.instance.stations[action.station_idx].x) / scale_m
            current_y = (current.y - self.instance.stations[action.station_idx].y) / scale_m
            clock = state.clock_s / 60.0 / duty
            trip_size = len(state.current_trip) / max(1, len(self.target_pools[action.station_idx]))
            if action.is_return:
                p = self._project_return(action)
                if p is None:
                    raise ValueError("empty")
                return [1.0, self.anchor.station_types[action.station_idx] / 2.0, action.slot,
                        0.0, 0.0, p["back_min"] / duty, p["back_min"] / duty,
                        max(0.0, 1.0 - p["energy"] / cap), max(0.0, 1.0 - p["duty_min"] / duty),
                        cost_slack,
                        p["inbound"].distance_m / scale_m, float(len(p["inbound"].segments) > 1),
                        current_x, current_y, 0.0, 0.0, clock, trip_size,
                        (self.anchor.cost - self._original_lower_bound(action)) / original_scale, 1.0]
            p = self._project_target(action)
            target = p["target"]
            return [0.0, self.anchor.station_types[action.station_idx] / 2.0, action.slot,
                    (target.x - self.instance.stations[action.station_idx].x) / scale_m,
                    (target.y - self.instance.stations[action.station_idx].y) / scale_m,
                    p["out_min"] / duty, p["back_min"] / duty,
                    max(0.0, 1.0 - p["energy"] / cap), max(0.0, 1.0 - p["duty_min"] / duty),
                    cost_slack,
                    p["outbound"].distance_m / scale_m, float(len(p["outbound"].segments) > 1),
                    current_x, current_y, target.service / duty, target.energy / cap, clock, trip_size,
                    (self.anchor.cost - self._original_lower_bound(action)) / original_scale,
                    float(p["inbound"].legal)]
        except (ValueError, KeyError):
            return [0.0] * self.candidate_dim

    def observation(self):
        actions, mask = self._actions()
        total_targets = max(1, len(self.instance.target_ids))
        remaining = sum(len(pool) for pool in self.remaining.values())
        max_duty = max(1.0, self.instance.params.large_duration)
        cap = max(self.weather_cost_cap or self.weather_cost or 1.0, 1.0)
        original_scale = max(1.0, self.anchor.cost)
        original_lower_bound = self._original_lower_bound()
        base = [remaining / total_targets, self.potential / max_duty,
                self.weather_cost / cap, self._weather_lower_bound() / cap,
                len(self.slots) / 3.0,
                sum(bool(s.current_trip) for s in self.slots.values()) / max(1, len(self.slots)),
                self.fixed_cost / cap, float(self.done), float(self.dead_end),
                self.anchor.cost / original_scale, original_lower_bound / original_scale]
        global_features = np.asarray(base + self._forecast_features() + self._policy_state_features(), dtype=np.float32)
        candidates = np.asarray([self._candidate_features(action) for action in actions], dtype=np.float32)
        if global_features.size != self.global_dim:
            raise AssertionError("forecast encoding dimension changed")
        state_receipt = {
            "slots": tuple({"station_idx": state.station_idx, "slot": state.slot,
                             "current_id": state.current_id, "clock_s": state.clock_s,
                             "static_operating_min": state.static_operating_min,
                             "trip_energy": state.trip_energy,
                             "current_trip": tuple(state.current_trip),
                             "closed_trips": tuple(tuple(t) for t in state.closed_trips)}
                           for _, state in sorted(self.slots.items())),
            "remaining_by_station": tuple((si, tuple(sorted(pool))) for si, pool in sorted(self.remaining.items())),
            "target_attributes": tuple((nid, self.instance.nodes[nid].x, self.instance.nodes[nid].y,
                                         self.instance.nodes[nid].service, self.instance.nodes[nid].energy)
                                       for nid in sorted(self.instance.target_ids)),
        }
        return {"global": global_features, "candidates": candidates,
                "mask": np.asarray(mask, dtype=np.bool_), "actions": actions,
                "done": self.done, "dead_end": self.dead_end, "terminated": self.terminated,
                "weather_cost": self.weather_cost, "weather_cost_lower_bound": self._weather_lower_bound(),
                "weather_cost_cap": self.weather_cost_cap, "M_return_potential": self.potential,
                "original_cost_lower_bound": original_lower_bound,
                "original_cost_cap": self.anchor.cost,
                "forecast": {"wind_knots": tuple(self.scenario.wind.knots), "no_fly_zone": self.scenario.no_fly_zone},
                "forecast_masks": {"wind_knots": np.asarray(
                    [index < len(self.scenario.wind.knots) for index in range(MAX_WIND_KNOTS)], dtype=np.bool_),
                    "nfz_vertices": np.asarray([self.scenario.no_fly_zone is not None and index < len(self.scenario.no_fly_zone.vertices)
                                                  for index in range(MAX_NFZ_VERTICES)], dtype=np.bool_)},
                "state_receipt": state_receipt,
                "forecast_is_fully_known": True}

    def step(self, action: WeatherMapAction):
        if self.terminated:
            raise RuntimeError("step called after completion or dead-end")
        if not self._legal(action):
            raise ValueError(f"illegal physical weather action: {action}")
        before = self.potential
        state = self.slots[(action.station_idx, action.slot)]
        info = {"action": action, "weather_cost_before": self.weather_cost}
        if action.is_return:
            p = self._project_return(action)
            state.clock_s = p["inbound"].arrival_time_s
            state.static_operating_min += self.instance.dist[state.current_id, state.station_id] / self.instance.params.speed
            state.closed_trips.append(list(state.current_trip))
            state.current_trip = []
            state.trip_energy = 0.0
            state.current_id = state.station_id
        else:
            p = self._project_target(action)
            target = p["target"]
            state.clock_s = p["outbound"].arrival_time_s + target.service * 60.0
            state.static_operating_min += self.instance.dist[state.current_id, target.id] / self.instance.params.speed + target.service
            state.trip_energy += p["outbound"].energy + target.energy
            state.current_id = target.id
            state.current_trip.append(target.id)
            self.remaining[action.station_idx].remove(target.id)
            info["completion_min"] = state.clock_s / 60.0
        self.action_count += 1
        reward = before - self.potential
        self.total_reward += reward
        if self.done:
            self._terminal_replay = replay_weather_solution(
                self.instance, self.anchor, self.scenario, self.candidate(),
                weather_cost_cap=self.weather_cost_cap, tolerance=self.cost_tolerance)
            if not self._terminal_replay["admissible"]:
                self.failure = "terminal_replay_rejected"
        elif self.dead_end:
            self.failure = "dead_end"
        info.update({"reward": reward, "weather_cost_after": self.weather_cost,
                     "M_return_potential": self.potential, "done": self.done,
                     "dead_end": self.dead_end, "failure": self.failure,
                     "terminal_replay": self._terminal_replay})
        return self.observation(), reward, self.terminated, info

    def candidate(self):
        if not self.done:
            raise RuntimeError("partial routes cannot be materialized as a complete solution")
        solution = self.anchor.solution()
        solution["routes"] = [[[], []] for _ in self.instance.stations]
        for (si, slot), state in self.slots.items():
            solution["routes"][si][slot] = [list(trip) for trip in state.closed_trips]
        return solution

    def result(self):
        if not self.done or self._terminal_replay is None or not self._terminal_replay["admissible"]:
            raise RuntimeError("no complete weather-admissible route result")
        return {"solution": self.candidate(), "replay": self._terminal_replay,
                "reward": self.total_reward, "action_count": self.action_count}
