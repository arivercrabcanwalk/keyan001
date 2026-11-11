"""Independent full-map clock, original feasibility, and frozen cost-anchor checks.

This module intentionally uses neither optimizer caches nor the old evaluator.
Physical vehicles start together at zero; a vehicle's trips run sequentially.
There is no added charging, turnaround, launch-pad, or synchronization time.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any


COST_TOLERANCE = 1e-7  # Absolute original cost units, not relative slack.
PHYSICS_TOLERANCE = 1e-7


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parameter_identity(instance) -> str:
    return identity(asdict(instance.params))


def _distance(a, b) -> float:
    # Deliberately do not read instance.dist.
    return math.hypot(a.x - b.x, a.y - b.y)


def _finite_nonnegative(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except (OverflowError, ValueError):
        return False


def cost_within_cap(cost: float, budget: float, tolerance: float = COST_TOLERANCE) -> bool:
    if not all(_finite_nonnegative(x) for x in (cost, budget, tolerance)):
        return False
    return cost - budget <= tolerance


def score_solution(instance, solution: Any) -> dict:
    """Score complete original-model solutions; malformed input fails closed.

    Infeasible solutions retain their raw diagnostics. Their time values never
    imply scientific admissibility. Empty trips are ignored, as in the original.
    """
    result = {
        "schema": "return_makespan_score_v1",
        "instance_sha256": instance.sha256,
        "parameter_sha256": parameter_identity(instance),
        "original_feasible": False,
        "issues": [],
        "cost": None,
        "M_return": None,
        "M_service": None,
        "mean_target_completion": None,
        "p90_target_completion_nearest_rank": None,
        "target_completion": {},
        "target_station": {},
        "slot_duty": [],
        "station_makespan": [],
        "trips": [],
    }
    issues = result["issues"]
    if not isinstance(solution, dict):
        issues.append("solution_format")
        return result
    try:
        result["solution_sha256"] = identity(solution)
    except (TypeError, ValueError, OverflowError):
        issues.append("solution_nonfinite_or_nonjson")
        return result
    if solution.get("instance_sha256") != instance.sha256:
        issues.append("instance_hash_missing_or_mismatch")
    types, routes = solution.get("station_types"), solution.get("routes")
    if (not isinstance(types, list) or not isinstance(routes, list)
            or len(types) != len(instance.stations) or len(routes) != len(instance.stations)):
        issues.append("station_dimension")
        return result
    if (len(instance.nodes) != len(instance.targets) + len(instance.stations)
            or len(set(instance.target_ids)) != len(instance.targets)):
        issues.append("instance_duplicate_node_id")
        return result
    for node in tuple(instance.targets) + tuple(instance.stations):
        if (type(node.id) is not int
                or not all(type(x) in (int, float) and math.isfinite(x)
                           for x in (node.x, node.y, node.energy, node.service))
                or min(node.energy, node.service) < 0):
            issues.append("instance_nonfinite_or_invalid_node")
            return result
    p = instance.params
    counts = Counter()
    targets = {node.id: node for node in instance.targets}
    fixed = operating = 0.0
    distances = total_energy = 0.0
    completion_values = []
    empty_trips = 0
    structural_error = False
    for si, station in enumerate(instance.stations):
        kind = types[si]
        if type(kind) is not int or kind not in (0, 1, 2):
            issues.append(f"station_type:{si}")
            structural_error = True
            continue
        if kind == 1:
            fixed += p.small_station_cost + p.small_drone_cost
        elif kind == 2:
            fixed += p.large_station_cost + p.small_drone_cost + p.large_drone_cost
        if not isinstance(routes[si], list) or len(routes[si]) != 2:
            issues.append(f"slot_dimension:{si}")
            structural_error = True
            continue
        station_loads = []
        for slot, trips in enumerate(routes[si]):
            if not isinstance(trips, list):
                issues.append(f"trip_dimension:{si}:{slot}")
                structural_error = True
                continue
            duty = 0.0
            for ti, trip in enumerate(trips):
                if not isinstance(trip, list):
                    issues.append(f"trip_format:{si}:{slot}:{ti}")
                    structural_error = True
                    continue
                if not trip:
                    empty_trips += 1
                    continue
                if kind == 0:
                    issues.append(f"closed_station:{si}")
                if kind == 1 and slot == 0:
                    issues.append(f"large_drone_at_small_station:{si}")
                if any(type(nid) is not int or nid not in targets for nid in trip):
                    issues.append(f"non_target:{si}:{slot}:{ti}")
                    structural_error = True
                    continue
                nodes = [targets[nid] for nid in trip]
                prefix = 0.0
                previous = station
                for node in nodes:
                    counts[node.id] += 1
                    radius = p.small_radius if kind == 1 else p.large_radius
                    if _distance(station, node) > radius + PHYSICS_TOLERANCE:
                        issues.append(f"coverage:{node.id}")
                    prefix += _distance(previous, node) / p.speed + node.service
                    completion = duty + prefix
                    result["target_completion"][node.id] = completion
                    result["target_station"][node.id] = si
                    completion_values.append(completion)
                    previous = node
                sequence = [station] + nodes + [station]
                length = sum(_distance(a, b) for a, b in zip(sequence, sequence[1:]))
                service = sum(node.service for node in nodes)
                travel = length / p.speed
                duration = travel + service
                energy = travel * p.flight_energy + sum(node.energy for node in nodes)
                capacity = p.large_battery if slot == 0 else p.small_battery
                if not all(math.isfinite(x) for x in (length, duration, energy, prefix)):
                    issues.append(f"nonfinite_geometry:{si}:{slot}:{ti}")
                    structural_error = True
                    continue
                if energy > capacity + PHYSICS_TOLERANCE:
                    issues.append(f"energy:{si}:{slot}:{ti}")
                duty += duration
                distances += length
                total_energy += energy
                result["trips"].append({
                    "station": si, "slot": slot, "trip": ti,
                    "targets": list(trip), "length_m": length,
                    "duration_min": duration, "energy": energy,
                    "energy_slack": capacity - energy,
                })
            limit = p.small_duration if kind == 1 else p.large_duration
            if duty > limit + PHYSICS_TOLERANCE:
                issues.append(f"cumulative_duty:{si}:{slot}")
            operating += duty
            station_loads.append(duty)
            result["slot_duty"].append({"station": si, "slot": slot, "duty_min": duty})
        result["station_makespan"].append(max(station_loads, default=0.0))
    for nid in targets:
        if counts[nid] == 0:
            issues.append(f"missing:{nid}")
        elif counts[nid] != 1:
            issues.append(f"duplicate:{nid}")
    result["fixed_cost"] = fixed
    result["operating_minutes"] = operating
    result["operating_cost"] = operating * p.time_cost
    result["total_distance_m"] = distances
    result["total_energy"] = total_energy
    result["nonempty_trip_count"] = len(result["trips"])
    result["ignored_empty_trip_count"] = empty_trips
    result["visited_count"] = sum(counts.values())
    if not structural_error:
        cost = fixed + operating * p.time_cost
        if not math.isfinite(cost):
            issues.append("nonfinite_total_cost")
        else:
            result["cost"] = cost
            result["M_return"] = max(result["station_makespan"], default=0.0)
            result["M_service"] = max(completion_values, default=0.0)
            if completion_values:
                ordered = sorted(completion_values)
                result["mean_target_completion"] = sum(ordered) / len(ordered)
                result["p90_target_completion_nearest_rank"] = ordered[math.ceil(.9 * len(ordered)) - 1]
    result["original_feasible"] = not issues
    return result


@dataclass(frozen=True)
class CostAnchor:
    """Immutable full feasible witness, including problem and parameter identity."""

    instance_sha256: str
    parameter_sha256: str
    station_types: tuple[int, ...]
    target_station: tuple[tuple[int, int], ...]
    cost: float
    makespan: float
    solution_sha256: str
    solution_json: str

    @classmethod
    def from_solution(cls, instance, solution) -> "CostAnchor":
        score = score_solution(instance, solution)
        if not score["original_feasible"]:
            raise ValueError(f"anchor is not a complete original-feasible witness: {score['issues']}")
        return cls(instance.sha256, parameter_identity(instance),
                   tuple(solution["station_types"]), tuple(sorted(score["target_station"].items())),
                   score["cost"], score["M_return"], score["solution_sha256"], canonical_json(solution))

    def solution(self) -> dict:
        # Never expose the stored witness as mutable shared state.
        return json.loads(self.solution_json)

    def verify(self, instance) -> None:
        if self.instance_sha256 != instance.sha256 or self.parameter_sha256 != parameter_identity(instance):
            raise ValueError("anchor instance/parameter identity mismatch")
        try:
            solution = self.solution()
            saved = score_solution(instance, solution)
            expected = (saved.get("solution_sha256"), saved["cost"], saved["M_return"],
                        tuple(solution["station_types"]), tuple(sorted(saved["target_station"].items())))
        except (TypeError, KeyError, ValueError, OverflowError) as exc:
            raise ValueError("malformed anchor witness") from exc
        actual = (self.solution_sha256, self.cost, self.makespan, self.station_types, self.target_station)
        if not saved["original_feasible"] or expected != actual:
            raise ValueError("anchor witness or cached fields mismatch")


def validate_candidate(instance, solution, anchor: CostAnchor, *, epsilon: float = 0.0,
                       cost_tolerance: float = COST_TOLERANCE) -> dict:
    """Original feasibility AND fixed domain AND full-map (not per-station) cap."""
    if not _finite_nonnegative(epsilon) or not _finite_nonnegative(cost_tolerance):
        raise ValueError("epsilon and absolute cost tolerance must be finite and nonnegative")
    anchor.verify(instance)
    result = score_solution(instance, solution)
    domain_issues = []
    if not isinstance(solution, dict) or solution.get("station_types") != list(anchor.station_types):
        domain_issues.append("fixed_station_types_changed")
    if tuple(sorted(result["target_station"].items())) != anchor.target_station:
        domain_issues.append("fixed_target_station_changed")
    budget = (1.0 + epsilon) * anchor.cost
    if not math.isfinite(budget):
        raise ValueError("nonfinite cost budget")
    delta = None if result["cost"] is None else result["cost"] - budget
    cap_ok = result["cost"] is not None and cost_within_cap(result["cost"], budget, cost_tolerance)
    result.update({
        "domain_issues": domain_issues,
        "domain_valid": not domain_issues,
        "cost_cap_satisfied": cap_ok,
        "cost_budget": budget,
        "epsilon": epsilon,
        "absolute_cost_tolerance": cost_tolerance,
        "raw_cost_minus_cap": delta,
        "raw_cost_minus_anchor": None if result["cost"] is None else result["cost"] - anchor.cost,
        "anchor_solution_sha256": anchor.solution_sha256,
        "admissible": result["original_feasible"] and not domain_issues and cap_ok,
    })
    return result
