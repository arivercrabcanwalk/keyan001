"""Feasibility-aware deterministic initialization.

The historical official-code profile is retained as the first attempt. If it
cannot produce a feasible solution, a deterministic fallback promotes
overloaded SABS stations to DABS and assigns targets to drones by physical
energy eligibility and workload balancing. Both M0 and CA consume this same
builder.
"""
from .problem import empty_solution
from .evaluator import evaluate


def station_set(ins):
    remaining = set(ins.target_ids)
    types = [0] * len(ins.stations)
    while remaining:
        best = None
        covered = set()
        for si, station in enumerate(ins.stations):
            if types[si]:
                continue
            for kind in (1, 2):
                candidate = {
                    n for n in remaining
                    if ins.dist[station.id, n] <= ins.radius(kind)
                }
                # Strict > and iteration order reproduce public Java tie handling.
                if len(candidate) > len(covered):
                    best = (si, kind)
                    covered = candidate
        if best is None:
            raise ValueError("targets outside all coverage circles")
        types[best[0]] = best[1]
        remaining -= covered
    return types


def _legacy_build(ins, types):
    p = ins.params
    types = list(types)
    sol = empty_solution(ins, types)
    assignments = [[] for _ in types]
    for nid in ins.target_ids:
        choices = [
            si for si, station in enumerate(ins.stations)
            if types[si] and ins.dist[station.id, nid] <= ins.radius(types[si])
        ]
        if not choices:
            raise ValueError("uncovered target")
        si = min(choices, key=lambda j: ins.dist[ins.stations[j].id, nid])
        assignments[si].append(nid)

    for si, kind in enumerate(types):
        if not kind or not assignments[si]:
            continue
        station = ins.stations[si].id
        if kind == 2:
            ordered = sorted(assignments[si], key=lambda n: ins.dist[station, n])
            groups = [ordered[::2], ordered[1::2]]
            if not groups[1]:
                groups[1].append(groups[0].pop(0))
        else:
            groups = [[], assignments[si]]

        for di, pending0 in enumerate(groups):
            pending = list(pending0)
            while pending:
                trip = []
                last = station
                energy = 0.0
                elapsed = 0.0
                while True:
                    feasible = []
                    for nid in pending:
                        node = ins.nodes[nid]
                        fly = ins.dist[last, nid] / p.speed
                        back = ins.dist[nid, station] / p.speed
                        if (
                            energy + fly * p.flight_energy + node.energy + back * p.flight_energy
                            <= ins.capacity(di)
                            and elapsed + fly + node.service + back <= ins.duration(kind)
                        ):
                            feasible.append(nid)
                    if not feasible:
                        break
                    nid = min(feasible, key=lambda n: ins.dist[last, n])
                    node = ins.nodes[nid]
                    fly = ins.dist[last, nid] / p.speed
                    energy += fly * p.flight_energy + node.energy
                    elapsed += fly + node.service
                    trip.append(nid)
                    pending.remove(nid)
                    last = nid
                if not trip:
                    raise ValueError("unserviceable target: legacy nearest-feasible append")
                sol["routes"][si][di].append(trip)
    return sol


def _assign_targets(ins, types):
    assignments = [[] for _ in types]
    for nid in ins.target_ids:
        choices = [
            si for si, station in enumerate(ins.stations)
            if types[si] and ins.dist[station.id, nid] <= ins.radius(types[si]) + 1e-7
        ]
        if not choices:
            raise ValueError(f"uncovered target in fallback: {nid}")
        si = min(choices, key=lambda j: (ins.dist[ins.stations[j].id, nid], j))
        assignments[si].append(nid)
    return assignments


def _promote_overloaded_sabs(ins, types, assignments):
    """Promote only SABS stations whose one-sortie workload cannot fit."""
    p = ins.params
    promoted = []
    for si, kind in enumerate(types):
        if kind != 1 or not assignments[si]:
            continue
        station = ins.stations[si].id
        direct_work = 0.0
        requires_large = False
        for nid in assignments[si]:
            node = ins.nodes[nid]
            round_trip = 2.0 * ins.dist[station, nid] / p.speed
            direct_work += round_trip + node.service
            minimum_energy = round_trip * p.flight_energy + node.energy
            if minimum_energy > p.small_battery + 1e-7:
                requires_large = True
        if requires_large or direct_work > p.small_duration + 1e-7:
            types[si] = 2
            promoted.append(si)
    return promoted


def _drone_groups(ins, station_id, kind, target_ids):
    """LPT assignment with per-target energy eligibility (drone 0 is LD)."""
    p = ins.params
    groups = [[], []]
    loads = [0.0, 0.0]
    capacities = [p.large_battery, p.small_battery]
    ordered = sorted(
        target_ids,
        key=lambda n: (
            -(2.0 * ins.dist[station_id, n] / p.speed + ins.nodes[n].service),
            n,
        ),
    )
    for nid in ordered:
        node = ins.nodes[nid]
        round_trip = 2.0 * ins.dist[station_id, nid] / p.speed
        required_energy = round_trip * p.flight_energy + node.energy
        eligible = [
            di for di in (0, 1)
            if required_energy <= capacities[di] + 1e-7
        ]
        if kind == 1:
            eligible = [1] if 1 in eligible else []
        if not eligible:
            raise ValueError(
                f"target {nid} cannot be served by any eligible drone at station {station_id}"
            )
        di = min(eligible, key=lambda d: (loads[d], d))
        groups[di].append(nid)
        loads[di] += round_trip + node.service
    return groups, loads


def _pack_drone_trips(ins, station_id, kind, drone_id, target_ids):
    """Nearest-feasible trip packing with cumulative per-drone duty accounting."""
    p = ins.params
    pending = list(target_ids)
    trips = []
    cumulative_time = 0.0
    capacity = p.large_battery if drone_id == 0 else p.small_battery
    duration = p.small_duration if kind == 1 else p.large_duration

    while pending:
        trip = []
        last = station_id
        energy = 0.0
        elapsed = 0.0
        while True:
            feasible = []
            for nid in pending:
                node = ins.nodes[nid]
                fly = ins.dist[last, nid] / p.speed
                back = ins.dist[nid, station_id] / p.speed
                next_energy = energy + fly * p.flight_energy + node.energy
                next_elapsed = elapsed + fly + node.service + back
                if next_energy + back * p.flight_energy <= capacity + 1e-7:
                    if next_elapsed <= duration + 1e-7:
                        feasible.append(nid)
            if not feasible:
                break
            nid = min(feasible, key=lambda n: (ins.dist[last, n], n))
            node = ins.nodes[nid]
            fly = ins.dist[last, nid] / p.speed
            energy += fly * p.flight_energy + node.energy
            elapsed += fly + node.service
            trip.append(nid)
            pending.remove(nid)
            last = nid

        if not trip:
            raise ValueError(
                f"unserviceable target in fallback: station={station_id}, drone={drone_id}, "
                f"target={pending[0]}"
            )
        last_target = trip[-1]
        trip_time = elapsed + ins.dist[last_target, station_id] / p.speed
        if cumulative_time + trip_time > duration + 1e-7:
            raise ValueError(
                f"cumulative drone duty exceeds duration: station={station_id}, "
                f"drone={drone_id}, duty={cumulative_time + trip_time:.6f}, "
                f"limit={duration:.6f}"
            )
        cumulative_time += trip_time
        trips.append(trip)
    return trips, cumulative_time


def _robust_build(ins, types):
    p = ins.params
    types = list(types)
    assignments = _assign_targets(ins, types)
    promoted = _promote_overloaded_sabs(ins, types, assignments)
    if promoted:
        # Promoting SABS to DABS only expands coverage, so nearest-station
        # assignment remains valid but is recomputed for deterministic ties.
        assignments = _assign_targets(ins, types)

    sol = empty_solution(ins, types)
    diagnostics = {
        "initializer": "feasibility_aware_lpt_fallback_v1",
        "promoted_sabs_station_indices": promoted,
        "station_workloads": {},
    }
    for si, kind in enumerate(types):
        target_ids = assignments[si]
        if not kind or not target_ids:
            continue
        station_id = ins.stations[si].id
        groups, estimated_loads = _drone_groups(ins, station_id, kind, target_ids)
        actual_loads = []
        for di in (0, 1):
            trips, duty = _pack_drone_trips(ins, station_id, kind, di, groups[di])
            sol["routes"][si][di] = trips
            actual_loads.append(duty)
        diagnostics["station_workloads"][str(si)] = {
            "station_type": kind,
            "target_count": len(target_ids),
            "drone_target_counts": [len(groups[0]), len(groups[1])],
            "estimated_drone_minutes": estimated_loads,
            "actual_cumulative_drone_minutes": actual_loads,
        }

    audit = evaluate(ins, sol)
    if not audit["feasible"]:
        raise ValueError(
            "feasibility-aware greedy fallback failed independent evaluator: "
            + repr(audit["issues"][:20])
        )
    sol["initializer_diagnostics"] = diagnostics
    return sol


def build(ins, types=None):
    types = list(types if types is not None else station_set(ins))
    # Preserve the original initializer exactly whenever it produces a
    # feasible solution; the fallback is only invoked for failure cases.
    try:
        legacy = _legacy_build(ins, types)
        legacy_audit = evaluate(ins, legacy)
        if legacy_audit["feasible"]:
            return legacy
    except (ValueError, IndexError, KeyError):
        pass
    return _robust_build(ins, types)
