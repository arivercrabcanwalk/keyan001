"""Bounded exhaustive numerical reference for a fixed station target pool."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Optional


EPS = 1e-7
MAX_TARGETS = 12
MAX_TRANSITION_CHECKS = 2_000_000
MAX_STATE_CELLS = 180_000


class BoundExceeded(RuntimeError):
    pass


@dataclass
class WorkBudget:
    deadline: float
    max_transitions: int = MAX_TRANSITION_CHECKS
    transitions: int = 0

    def check(self, transitions: int = 1):
        self.transitions += transitions
        if self.transitions > self.max_transitions:
            raise BoundExceeded("transition_bound")
        if (self.transitions <= 1 or self.transitions % 1024 == 0) and time.perf_counter() >= self.deadline:
            raise BoundExceeded("map_wallclock_cap")


@dataclass
class StationResult:
    status: str
    station_idx: int
    station_type: int
    target_ids: tuple[int, ...]
    routes: Optional[list]
    operating_minutes_dp: Optional[float]
    slot_target_ids: Optional[dict]
    slot_dp_minutes: Optional[dict]
    slot_energy_slack_min: Optional[dict]
    slot_duty_slack: Optional[dict]
    trip_metrics: Optional[dict]
    state_cells: int
    transition_checks: int
    elapsed_seconds: float
    detail: Optional[str] = None

    def as_dict(self):
        return {
            "status": self.status,
            "station_idx": self.station_idx,
            "station_type": self.station_type,
            "target_ids": list(self.target_ids),
            "target_count": len(self.target_ids),
            "routes": self.routes,
            "operating_minutes_dp": self.operating_minutes_dp,
            "slot_target_ids": self.slot_target_ids,
            "slot_dp_minutes": self.slot_dp_minutes,
            "slot_energy_slack_min": self.slot_energy_slack_min,
            "slot_duty_slack": self.slot_duty_slack,
            "trip_metrics": self.trip_metrics,
            "state_cells": self.state_cells,
            "transition_checks": self.transition_checks,
            "elapsed_seconds": self.elapsed_seconds,
            "detail": self.detail,
        }


def _distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _trip_partition(slot: int, n: int, trip_cost, trip_energy, battery: float,
                    budget: WorkBudget):
    size = 1 << n
    dp = [math.inf] * size
    parent_trip = [0] * size
    dp[0] = 0.0
    feasible_trip = [False] * size
    feasible_trip[0] = True
    min_energy_slack = math.inf
    for mask in range(1, size):
        slack = battery - trip_energy[mask]
        if trip_energy[mask] <= battery + EPS:
            feasible_trip[mask] = True
            min_energy_slack = min(min_energy_slack, slack)

    for mask in range(1, size):
        pivot = mask & -mask
        sub = mask
        best = math.inf
        best_trip = 0
        while sub:
            budget.check()
            if sub & pivot and feasible_trip[sub]:
                previous = mask ^ sub
                value = trip_cost[sub] + dp[previous]
                if value < best:
                    best = value
                    best_trip = sub
            sub = (sub - 1) & mask
        dp[mask] = best
        parent_trip[mask] = best_trip
    return dp, parent_trip, min_energy_slack


def _reconstruct_partition(mask: int, parent_trip, trip_sequence, target_ids):
    trips = []
    trip_masks = []
    while mask:
        trip = parent_trip[mask]
        if not trip:
            raise RuntimeError("finite partition is missing a parent trip")
        trips.append([target_ids[i] for i in trip_sequence[trip]])
        trip_masks.append(trip)
        mask ^= trip
    return trips, trip_masks


def solve_station(instance, station_idx: int, station_type: int, target_ids,
                  budget: WorkBudget, max_targets: int = MAX_TARGETS,
                  fixed_slot_target_ids=None) -> StationResult:
    """Return a full route witness for one fixed-station target pool, if bounded."""
    started = time.perf_counter()
    ids = tuple(sorted(int(x) for x in target_ids))

    def result(status, **kwargs):
        return StationResult(
            status=status,
            station_idx=int(station_idx),
            station_type=int(station_type),
            target_ids=ids,
            routes=kwargs.get("routes"),
            operating_minutes_dp=kwargs.get("operating_minutes_dp"),
            slot_target_ids=kwargs.get("slot_target_ids"),
            slot_dp_minutes=kwargs.get("slot_dp_minutes"),
            slot_energy_slack_min=kwargs.get("slot_energy_slack_min"),
            slot_duty_slack=kwargs.get("slot_duty_slack"),
            trip_metrics=kwargs.get("trip_metrics"),
            state_cells=kwargs.get("state_cells", 0),
            transition_checks=budget.transitions,
            elapsed_seconds=time.perf_counter() - started,
            detail=kwargs.get("detail"),
        )

    complete_status = ("COMPLETE_FIXED_OWNER_REFERENCE" if fixed_slot_target_ids is not None
                       else "COMPLETE_JOINT_REFERENCE")
    if not (0 <= station_idx < len(instance.stations)):
        return result("INPUT_INVALID", detail="station index outside instance")
    if len(ids) != len(set(ids)):
        return result("INPUT_INVALID", detail="duplicate target IDs")
    missing = set(ids) - set(instance.target_ids)
    if missing:
        return result("INPUT_INVALID", detail=f"non-target IDs: {sorted(missing)}")
    if station_type not in (0, 1, 2):
        return result("INPUT_INVALID", detail=f"invalid station type {station_type}")
    if station_type == 0:
        if ids:
            return result("INPUT_INVALID", detail="closed station has nonempty target pool")
        return result(
            complete_status, routes=[[], []], operating_minutes_dp=0.0,
            slot_target_ids={"0": [], "1": []}, slot_dp_minutes={"0": 0.0, "1": 0.0},
            slot_energy_slack_min={"0": None, "1": None},
            slot_duty_slack={"0": None, "1": None},
        )
    if not ids:
        return result(
            complete_status, routes=[[], []], operating_minutes_dp=0.0,
            slot_target_ids={"0": [], "1": []}, slot_dp_minutes={"0": 0.0, "1": 0.0},
            slot_energy_slack_min={"0": None, "1": None},
            slot_duty_slack={"0": None, "1": None},
        )
    if len(ids) > max_targets:
        return result("UNRESOLVED_SIZE_LIMIT", detail=f"{len(ids)}>{max_targets}")

    p = instance.params
    station = instance.stations[station_idx]
    targets = [instance.nodes[nid] for nid in ids]
    radius = p.small_radius if station_type == 1 else p.large_radius
    coverage_slack = [radius - _distance(station, node) for node in targets]
    if any(math.hypot(station.x - node.x, station.y - node.y) > radius + EPS for node in targets):
        return result("INPUT_INVALID", detail="station pool violates fixed-type coverage")

    slots = (1,) if station_type == 1 else (0, 1)
    capacities = {0: p.large_battery, 1: p.small_battery}
    duty_limit = p.small_duration if station_type == 1 else p.large_duration
    speed = p.speed
    n = len(ids)
    size = 1 << n
    # Conservative dense table, parent and reconstructed sequence cell count.
    state_cells = (5 * n * size) // 2 + 11 * size + n * n + 4 * n + 128
    if state_cells > MAX_STATE_CELLS:
        return result("UNRESOLVED_STATE_BOUND", detail=f"{state_cells}>{MAX_STATE_CELLS}", state_cells=state_cells)

    forced_masks = None
    if fixed_slot_target_ids is not None:
        forced = {int(slot): tuple(int(nid) for nid in values)
                  for slot, values in fixed_slot_target_ids.items()}
        if any(slot not in slots for slot in forced):
            return result("INPUT_INVALID", detail="fixed owner uses an ineligible physical slot", state_cells=state_cells)
        owner_ids = [nid for values in forced.values() for nid in values]
        if len(owner_ids) != len(set(owner_ids)) or set(owner_ids) != set(ids):
            return result("INPUT_INVALID", detail="fixed slot owners are not a disjoint exact partition", state_cells=state_cells)
        forced_masks = {slot: 0 for slot in slots}
        id_to_idx = {nid: idx for idx, nid in enumerate(ids)}
        for slot, values in forced.items():
            for nid in values:
                forced_masks[slot] |= 1 << id_to_idx[nid]

    try:
        budget.check(0)
        origin = [_distance(station, node) for node in targets]
        between = [[_distance(a, b) for b in targets] for a in targets]
        service_sum = [0.0] * size
        target_energy_sum = [0.0] * size
        for mask in range(1, size):
            bit = mask & -mask
            idx = bit.bit_length() - 1
            rest = mask ^ bit
            service_sum[mask] = service_sum[rest] + targets[idx].service
            target_energy_sum[mask] = target_energy_sum[rest] + targets[idx].energy
    
        # Held-Karp open paths are accumulated in visit order; closing edge is added last.
        path = [[math.inf] * n for _ in range(size)]
        predecessor = [[-1] * n for _ in range(size)]
        tour_length = [math.inf] * size
        trip_sequence = [None] * size
        for j in range(n):
            path[1 << j][j] = origin[j]
    
        for mask in range(1, size):
            for j in range(n):
                if not (mask & (1 << j)):
                    continue
                previous = mask ^ (1 << j)
                if not previous:
                    continue
                best = math.inf
                best_k = -1
                for k in range(n):
                    if previous & (1 << k):
                        budget.check()
                        value = path[previous][k] + between[k][j]
                        if value < best:
                            best = value
                            best_k = k
                path[mask][j] = best
                predecessor[mask][j] = best_k
    
            best_closed = math.inf
            best_last = -1
            for j in range(n):
                if mask & (1 << j):
                    budget.check()
                    value = path[mask][j] + origin[j]
                    if value < best_closed:
                        best_closed = value
                        best_last = j
            tour_length[mask] = best_closed
            order = []
            cursor_mask = mask
            cursor = best_last
            while cursor_mask:
                order.append(cursor)
                prev = predecessor[cursor_mask][cursor]
                cursor_mask ^= 1 << cursor
                cursor = prev
            trip_sequence[mask] = tuple(reversed(order))
    
        trip_cost = [0.0] * size
        trip_energy = [0.0] * size
        for mask in range(1, size):
            trip_time = tour_length[mask] / speed
            trip_cost[mask] = trip_time + service_sum[mask]
            trip_energy[mask] = trip_time * p.flight_energy + target_energy_sum[mask]
    
        per_slot = {}
        for slot in slots:
            dp, parent_trip, min_energy_slack = _trip_partition(
                slot, n, trip_cost, trip_energy, capacities[slot], budget
            )
            per_slot[slot] = (dp, parent_trip, min_energy_slack)

        if forced_masks is not None:
            assigned = forced_masks
            for slot in slots:
                slot_dp = per_slot[slot][0]
                owned_mask = assigned[slot]
                if (not math.isfinite(slot_dp[owned_mask])
                        or slot_dp[owned_mask] > duty_limit + EPS):
                    return result(
                        "UNRESOLVED_FIXED_OWNER_INFEASIBLE",
                        detail=f"fixed slot {slot} has no duty-feasible trip partition",
                        state_cells=state_cells,
                    )
            operating = sum(per_slot[slot][0][assigned[slot]] for slot in slots)
        elif station_type == 1:
            small_dp, _, _ = per_slot[1]
            best_mask = (1 << n) - 1
            if not math.isfinite(small_dp[best_mask]) or small_dp[best_mask] > duty_limit + EPS:
                return result("UNRESOLVED_NO_FEASIBLE_PARTITION", detail="SABS pool has no feasible route partition", state_cells=state_cells)
            assigned = {1: best_mask}
            operating = small_dp[best_mask]
        else:
            large_dp, _, _ = per_slot[0]
            small_dp, _, _ = per_slot[1]
            full = (1 << n) - 1
            operating = math.inf
            best_large = None
            best_small = None
            for large_mask in range(size):
                budget.check()
                small_mask = full ^ large_mask
                large_cost = large_dp[large_mask]
                small_cost = small_dp[small_mask]
                if (math.isfinite(large_cost) and math.isfinite(small_cost)
                        and large_cost <= duty_limit + EPS
                        and small_cost <= duty_limit + EPS):
                    value = large_cost + small_cost
                    if value < operating:
                        operating = value
                        best_large = large_mask
                        best_small = small_mask
            if best_large is None:
                return result("UNRESOLVED_NO_FEASIBLE_PARTITION", detail="DABS pool has no feasible split partition", state_cells=state_cells)
            assigned = {0: best_large, 1: best_small}

        routes = [[], []]
        slot_target_ids = {"0": [], "1": []}
        slot_dp_minutes = {"0": 0.0, "1": 0.0}
        slot_energy_slack = {"0": None, "1": None}
        slot_duty_slack = {"0": None, "1": None}
        trip_metrics = {"0": [], "1": []}
        for slot in slots:
            mask = assigned[slot]
            dp, parent_trip, min_energy_slack = per_slot[slot]
            routes[slot], selected_trip_masks = _reconstruct_partition(mask, parent_trip, trip_sequence, ids)
            slot_target_ids[str(slot)] = [ids[i] for i in range(n) if mask & (1 << i)]
            slot_dp_minutes[str(slot)] = dp[mask]
            slot_energy_slack[str(slot)] = None if mask == 0 else min(
                capacities[slot] - trip_energy[trip_mask] for trip_mask in selected_trip_masks
            )
            slot_duty_slack[str(slot)] = duty_limit - dp[mask]
            for trip_mask, sequence in zip(selected_trip_masks, routes[slot]):
                trip_metrics[str(slot)].append({
                    "target_ids": list(sequence),
                    "tour_length_m_dp": tour_length[trip_mask],
                    "operating_minutes_dp": trip_cost[trip_mask],
                    "energy_dp": trip_energy[trip_mask],
                    "battery_slack_dp": capacities[slot] - trip_energy[trip_mask],
                })

        visited = [nid for slot_routes in routes for trip in slot_routes for nid in trip]
        if sorted(visited) != list(ids) or len(visited) != len(ids):
            return result("INTERNAL_WITNESS_ERROR", detail="witness is not exact-once station coverage", state_cells=state_cells)
        if time.perf_counter() >= budget.deadline:
            raise BoundExceeded("map_wallclock_cap")
        return result(
            "COMPLETE_FIXED_OWNER_REFERENCE" if forced_masks is not None else "COMPLETE_JOINT_REFERENCE",
            routes=routes, operating_minutes_dp=operating,
            slot_target_ids=slot_target_ids, slot_dp_minutes=slot_dp_minutes,
            slot_energy_slack_min=slot_energy_slack,
            slot_duty_slack=slot_duty_slack,
            trip_metrics=trip_metrics, state_cells=state_cells,
        )
    except BoundExceeded as exc:
        return result("UNRESOLVED_BOUND", detail=str(exc), state_cells=state_cells)
