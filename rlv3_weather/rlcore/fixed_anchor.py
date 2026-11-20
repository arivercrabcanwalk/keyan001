"""Independent closed-route audit for the bounded, known fixed-wind A domain.

No optimizer, environment, physics cache or old map is executed here. A feasible
re-score of a calm/10-second route is engineering evidence, not a same-wind full
author solve. Provenance is a bound execution record, not proof of optimality.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math
import re

WINDS = {"W00": (0.0, 0.0), "W04E": (4.0, 0.0), "W08N": (0.0, 8.0)}
SCENARIO_WINDS = {"nowind": "W00", "fixed_e4": "W04E", "fixed_n8": "W08N"}
SCHEMA = "rlv3-fixed-author-anchor-audit-v1"
ENERGY_EPS = 1e-12  # battery units, independent of the monetary cost tolerance
FULL_AUTHOR_BUDGET_S = 1800.0


def digest(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _nonnegative(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def _wind(wind):
    if isinstance(wind, str):
        key = SCENARIO_WINDS.get(wind, wind)
        if key in WINDS:
            return key, WINDS[key]
    elif isinstance(wind, (list, tuple)) and len(wind) == 2:
        for key, vector in WINDS.items():
            if tuple(wind) == vector:
                return key, vector
    raise ValueError("fixed anchor supports only W00, W04E and W08N")


def _leg(a, b, wind, speed_m_min):
    """Independent wind triangle; returns metres and minutes, never a crawl."""
    dx, dy = b.x - a.x, b.y - a.y
    distance = math.hypot(dx, dy)
    if distance == 0:
        return 0.0, 0.0
    ux, uy = dx / distance, dy / distance
    va = speed_m_min / 60.0
    along, cross = wind[0] * ux + wind[1] * uy, wind[0] * uy - wind[1] * ux
    discriminant = va * va - cross * cross
    if discriminant < 0:
        return distance, None
    vg = along + math.sqrt(discriminant)
    if vg < 4.0:
        return distance, None
    return distance, distance / (60.0 * vg)


def audit_fixed_anchor(instance, solution, provenance=None, *, wind, map_path=None):
    """Return a strict-JSON receipt; validate both resources and anchor identity.

    Full provenance requires an external completed author-execution JSON receipt
    at ``run_receipt_path``, bound by ``run_receipt_sha256``. Required receipt keys
    are documented by ``_provenance`` below. Missing/short/calm provenance leaves
    the route ENGINEERING_ONLY even when its resource audit passes.
    """
    wind_id, vector = _wind(wind)
    provenance = {} if provenance is None else provenance
    issues, details, counts = [], [], Counter()
    p = instance.params
    map_sha = instance.sha256
    file_hash = None
    if map_path is not None:
        file_hash = _sha(map_path)
        if file_hash != map_sha:
            issues.append("map_file_hash")
        # A caller cannot mutate coordinates/energy while retaining a valid SHA.
        try:
            rows = Path(map_path).read_text(encoding="utf-8-sig").splitlines()
            if not rows or "CUST_NO" not in rows[0]:
                raise ValueError("header")
            parsed = [tuple(map(float, line.split())) for line in rows[1:] if line.strip()]
            expected_targets = [tuple((n.id,n.x,n.y,n.energy,n.service)) for n in instance.targets]
            expected_stations = [tuple((n.id,n.x,n.y,n.energy,n.service)) for n in instance.stations]
            if (any(len(row) != 5 or not all(math.isfinite(v) for v in row)
                    or not row[0].is_integer() or min(row[3:]) < 0
                    or (row[3] == 0 and row[4] != 0) for row in parsed)
                    or len({row[0] for row in parsed}) != len(parsed)
                    or [row for row in parsed if row[3] > 0] != expected_targets
                    or [row for row in parsed if row[3] == 0] != expected_stations
                    or instance.name != Path(map_path).stem):
                raise ValueError("content")
        except (OSError, ValueError, IndexError):
            issues.append("instance_map_content")
    if solution.get("instance_sha256") != map_sha:
        issues.append("solution_map_hash")
    if solution.get("instance") != instance.name:
        issues.append("solution_instance_name")
    types, routes = solution.get("station_types"), solution.get("routes")
    dimension_ok = (isinstance(types, list) and isinstance(routes, list)
                    and len(types) == len(instance.stations) and len(routes) == len(instance.stations))
    fixed, operating, makespan, total_distance = 0.0, 0.0, 0.0, 0.0
    targets = {n.id: n for n in instance.targets}
    if not dimension_ok:
        issues.append("station_dimension")
    else:
        for si, station in enumerate(instance.stations):
            kind = types[si]
            if type(kind) is not int or kind not in (0, 1, 2):
                issues.append(f"station_type:{si}")
                continue
            if kind == 1:
                fixed += p.small_station_cost + p.small_drone_cost
            elif kind == 2:
                fixed += p.large_station_cost + p.large_drone_cost + p.small_drone_cost
            drones = routes[si]
            if not isinstance(drones, list) or len(drones) != 2:
                issues.append(f"drone_dimension:{si}")
                continue
            for di, trips in enumerate(drones):
                if not isinstance(trips, list):
                    issues.append(f"trip_dimension:{si}:{di}")
                    continue
                duty = 0.0
                for ti, trip in enumerate(trips):
                    prefix = f"{si}:{di}:{ti}"
                    if not isinstance(trip, list):
                        issues.append("trip_format:" + prefix)
                        continue
                    if not trip:
                        continue
                    if kind == 0:
                        issues.append("closed_station:" + prefix)
                    if kind == 1 and di == 0:
                        issues.append("large_drone_at_small_station:" + prefix)
                    nodes = []
                    for nid in trip:
                        if type(nid) is not int or nid not in targets:
                            issues.append("unknown_target:" + prefix)
                            continue
                        node = targets[nid]
                        counts[nid] += 1
                        nodes.append(node)
                        radius = p.small_radius if kind == 1 else p.large_radius
                        if math.hypot(node.x - station.x, node.y - station.y) > radius + 1e-7:
                            issues.append(f"station_radius:{si}:{nid}")
                    sequence = [station] + nodes + [station]
                    distance, travel, leg_ok = 0.0, 0.0, True
                    for a, b in zip(sequence[:-1], sequence[1:]):
                        d, tm = _leg(a, b, vector, p.speed)
                        distance += d
                        if tm is None:
                            issues.append("wind_leg:" + prefix)
                            leg_ok = False
                        else:
                            travel += tm
                    service = sum(n.service for n in nodes)
                    node_energy = sum(n.energy for n in nodes)
                    energy = travel * p.flight_energy + node_energy
                    capacity = p.large_battery if di == 0 else p.small_battery
                    if energy > capacity + ENERGY_EPS:
                        issues.append("battery:" + prefix)
                    duty += travel + service
                    total_distance += distance
                    details.append(dict(station=si, station_id=station.id, drone=di, trip=ti,
                        distance_m=distance, flight_minutes=travel if leg_ok else None,
                        service_minutes=service, node_energy=node_energy,
                        energy=energy if leg_ok else None, battery_capacity=capacity,
                        energy_slack=capacity-energy if leg_ok else None))
                # The vendor author contract assigns cumulative duration by station type.
                limit = p.small_duration if kind == 1 else p.large_duration
                if duty > limit + 1e-7:
                    issues.append(f"cumulative_duty:{si}:{di}")
                operating += duty
                makespan = max(makespan, duty)
        for tid in targets:
            if counts[tid] == 0:
                issues.append(f"missing:{tid}")
            elif counts[tid] > 1:
                issues.append(f"duplicate:{tid}")
    solution_sha = digest(solution)
    params_sha = digest(asdict(p))
    prov_issues = _provenance(provenance, map_sha, solution_sha, params_sha, wind_id, vector, file_hash)
    feasible = not issues
    full = feasible and not prov_issues
    metrics = dict(fixed_cost=fixed, operating_minutes=operating,
                   cost=fixed + p.time_cost * operating, M_return=makespan,
                   flight_distance_m=total_distance, targets=len(targets),
                   visited=sum(counts.values()))
    # Invalid legs must not leave partial travel presented as a valid aggregate.
    if any(v.startswith("wind_leg:") for v in issues):
        metrics.update(operating_minutes=None, cost=None, M_return=None)
    receipt = dict(schema=SCHEMA, status="FULL_SAME_WIND_AUTHOR_RECORDED" if full else
                   ("ENGINEERING_ONLY" if feasible else "RESOURCE_AUDIT_FAILED"),
                   physical_feasible=feasible, full_same_wind_author=full,
                   scientific_eligible=full, formal=False, map_sha256=map_sha,
                   parameters_sha256=params_sha, solution_sha256=solution_sha,
                   provenance_sha256=digest(provenance), wind_id=wind_id, wind_m_s=list(vector),
                   energy_model="author_node_energy_plus_flight_rate",
                   issues=issues, provenance_issues=prov_issues, metrics=metrics, trips=details)
    receipt["audit_sha256"] = digest(receipt)
    return receipt


def _provenance(prov, map_sha, solution_sha, params_sha, wind_id, vector, file_hash):
    issues = []
    if not isinstance(prov, dict):
        return ["provenance_not_object"]
    expected = dict(schema="liu-full-same-wind-author-run-v1", map_sha256=map_sha,
                    solution_sha256=solution_sha, parameters_sha256=params_sha,
                    wind_id=wind_id, wind_m_s=list(vector),
                    energy_model="author_node_energy_plus_flight_rate", solver="TSALNS",
                    complete_author_run=True, solve_included_wind=True, exit_status=0,
                    outer_iterations=500, inner_iterations=5000, full_strength=True,
                    downgraded=False)
    for key, value in expected.items():
        if key not in prov or prov[key] != value or (type(value) in (bool, int) and type(prov[key]) is not type(value)):
            issues.append("provenance:" + key)
    if file_hash != map_sha:
        issues.append("provenance:map_bytes_unverified")
    if not _nonnegative(prov.get("budget_s")) or prov["budget_s"] < FULL_AUTHOR_BUDGET_S:
        issues.append("provenance:full_budget_1800s_required")
    if not _nonnegative(prov.get("wall_s")) or not _nonnegative(prov.get("budget_s")) or prov.get("wall_s", 0) > prov.get("budget_s", 0) + 1e-7:
        issues.append("provenance:wall_s")
    for key in ("author_repository", "command", "run_id"):
        if not isinstance(prov.get(key), str) or not prov[key].strip():
            issues.append("provenance:" + key)
    if not isinstance(prov.get("author_commit"), str) or re.fullmatch(r"[0-9a-f]{40}", prov["author_commit"]) is None:
        issues.append("provenance:author_commit")
    for key in ("author_source_sha256", "run_receipt_sha256"):
        if not _hash(prov.get(key)):
            issues.append("provenance:" + key)
    # Bind an external execution record to all of the asserted solver metadata.
    try:
        path = Path(prov["run_receipt_path"])
        if _sha(path) != prov.get("run_receipt_sha256"):
            issues.append("provenance:run_receipt_hash")
        record = json.loads(path.read_text(encoding="utf-8"))
        for key in (*expected, "budget_s", "wall_s", "author_repository", "author_commit", "author_source_sha256", "command", "run_id"):
            if key not in prov or record.get(key) != prov[key]:
                issues.append("provenance:run_receipt_binding:" + key)
    except (KeyError, TypeError, OSError, ValueError):
        issues.append("provenance:missing_or_invalid_run_receipt")
    return sorted(set(issues))


def audit_anchor_file(anchor_path, map_path, wind):
    """Read an external solution+provenance artifact for strict-pilot registration."""
    from .common import load_ins
    path = Path(anchor_path)
    record = json.loads(path.read_text(encoding="utf-8"))
    provenance = record.get("provenance")
    if isinstance(provenance, dict) and isinstance(provenance.get("run_receipt_path"), str):
        provenance = dict(provenance)
        run_path = Path(provenance["run_receipt_path"])
        if not run_path.is_absolute():
            provenance["run_receipt_path"] = str((path.parent / run_path).resolve())
    result = audit_fixed_anchor(load_ins(str(map_path)), record["solution"],
                               provenance, wind=wind, map_path=map_path)
    result["anchor_file_sha256"] = _sha(path)
    result["audit_sha256"] = digest({k:v for k,v in result.items() if k != "audit_sha256"})
    return result


def bind_split_anchors(rows, manifest, wind):
    """Train/validation must start from the same kind of author solve as the pilot.

    The split file maps each registered map path directly to its original anchor
    JSON. These are different maps, never copies of pilot maps or budgets.
    """
    from .common import rel
    manifest = Path(manifest)
    links = json.loads(manifest.read_text())
    if not isinstance(links, dict) or set(links) != {row["path"] for row in rows}:
        raise ValueError("same-wind split manifest must cover every registered training/validation map")
    bound = {}
    for row in rows:
        key = row["path"]
        link = Path(links[key])
        if not link.is_absolute():
            link = manifest.parent / link
        scored = audit_anchor_file(link, rel(key), wind)
        if not scored["full_same_wind_author"] or scored["solution_sha256"] != digest(row["solution"]):
            raise ValueError("missing full same-wind anchor or changed training/validation deployment: " + key)
        bound[key] = {"solution":scored["solution_sha256"], "author_receipt":scored["audit_sha256"],
                      "anchor_file":scored["anchor_file_sha256"], "cost":scored["metrics"]["cost"]}
    return bound


def main(argv=None):
    """Write a receipt; exit 0=full recorded, 2=engineering, 1=resource failure."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", required=True, help="external JSON with solution and provenance")
    parser.add_argument("--map", required=True, dest="map_path", help="original Liu instance bytes")
    parser.add_argument("--wind", required=True, choices=tuple(WINDS) + tuple(SCENARIO_WINDS))
    parser.add_argument("--output", required=True, help="new audit receipt JSON")
    args = parser.parse_args(argv)
    result = audit_anchor_file(args.anchor, args.map_path, args.wind)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"] + " " + str(out.resolve()))
    return 0 if result["scientific_eligible"] else (2 if result["physical_feasible"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
