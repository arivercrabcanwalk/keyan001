#!/usr/bin/env python3
"""Exact min-max reassignment of the anchor's intact trips (cost-neutral class).

Reassigning intact trips to the station's legal slots changes no trip duration,
so total operating minutes -- hence the full cost -- is bit-identical to the
anchor.  The cost cap is therefore satisfied by construction and the only
question is the makespan.  This script computes the exact minimum M_return in
that class by exhaustive assignment per station, which makes the LPT control's
optimality gap a theorem rather than a guess.
"""
from __future__ import annotations
import argparse, itertools, json, math, pathlib, sys

R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
RM = C / "route_rl_research/20261103/return_makespan"
sys.path.insert(0, str(RM))
sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix/lrphsd"))
import problem  # noqa: E402
import scorer  # noqa: E402


def trip_metrics(inst, station_idx, trip):
    st = inst.stations[station_idx]
    seq = [st] + [inst.nodes[n] for n in trip] + [st]
    length = sum(math.hypot(a.x - b.x, a.y - b.y) for a, b in zip(seq, seq[1:]))
    travel = length / inst.params.speed
    service = sum(inst.nodes[n].service for n in trip)
    energy = travel * inst.params.flight_energy + sum(inst.nodes[n].energy for n in trip)
    return travel + service, energy


def exact_reassign(inst, solution):
    types = solution["station_types"]
    total = 0.0
    per_station = []
    for si, kind in enumerate(types):
        trips = []
        for slot, slot_trips in enumerate(solution["routes"][si]):
            for trip in slot_trips:
                if not trip:
                    continue
                dur, energy = trip_metrics(inst, si, trip)
                trips.append({"targets": list(trip), "duration": dur, "energy": energy,
                              "slot": slot})
        if not trips:
            per_station.append({"station": si, "kind": kind, "slots": 0,
                                "min_makespan": 0.0, "assignment": []})
            continue
        slots = (1,) if kind == 1 else ((0, 1) if kind == 2 else ())
        if not slots:
            raise SystemExit(f"station {si} closed but has trips")
        limit = inst.params.small_duration if kind == 1 else inst.params.large_duration
        cap = {s: (inst.params.large_battery if s == 0 else inst.params.small_battery)
               for s in slots}
        feasible = []
        for t in trips:
            ok = [s for s in slots if t["energy"] <= cap[s] + 1e-9]
            if not ok:
                raise SystemExit(f"station {si} trip {t['targets']} exceeds every slot battery")
            feasible.append(ok)
        best = None
        best_assign = None
        # exhaustive: at most 2^len(trips) combinations for two-slot stations
        for combo in itertools.product(*feasible):
            loads = {s: 0.0 for s in slots}
            for t, s in zip(trips, combo):
                loads[s] += t["duration"]
            if any(loads[s] > limit + 1e-9 for s in slots):
                continue
            mk = max(loads.values())
            if best is None or mk < best - 1e-12:
                best, best_assign = mk, combo
        if best is None:
            raise SystemExit(f"station {si}: no feasible reassignment")
        per_station.append({"station": si, "kind": kind, "slots": len(slots),
                            "trips": len(trips), "min_makespan": best,
                            "assignment": [{"targets": t["targets"], "slot": s}
                                           for t, s in zip(trips, best_assign)],
                            })
        total = max(total, best)
    return total, per_station


def rebuild(inst, solution, per_station):
    out = dict(solution)
    out["station_types"] = list(solution["station_types"])
    out["routes"] = [[[], []] for _ in inst.stations]
    for st in per_station:
        if not st["assignment"]:
            continue
        for row in st["assignment"]:
            out["routes"][st["station"]][row["slot"]].append(list(row["targets"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    pop = pathlib.Path(args.out)
    index = json.loads((pop / "population_index.json").read_text())
    (pop / "EXACT_REASSIGN_INTENT.json").write_text(json.dumps({
        "schema": "takeover_g3_exact_reassign_intent_v1",
        "maps": [m["name"] for m in index["maps"]],
        "method": "exhaustive_min_max_reassignment_of_intact_trips",
        "contract": {"epsilon": 0.0, "cost_tolerance": 1e-7},
        "note": "cost-neutral by construction; only slot assignment changes",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = []
    for m in index["maps"]:
        if m["status"] != "generated":
            continue
        adir = pop / "author" / m["name"]
        run_json = adir / "RUN.json"
        if not run_json.exists():
            continue
        if not json.loads(run_json.read_text()).get("anchor_eligible"):
            rows.append({"map": m["name"], "status": "ANCHOR_NOT_ELIGIBLE"})
            continue
        inst = problem.read_instance(pathlib.Path(m["path"]))
        sol = json.loads((adir / "solution.json").read_text())
        anchor = scorer.CostAnchor.from_solution(inst, sol)
        mk, per_station = exact_reassign(inst, sol)
        cand = rebuild(inst, sol, per_station)
        val = scorer.validate_candidate(inst, cand, anchor, epsilon=0.0)
        rows.append({
            "map": m["name"], "status": "OK",
            "anchor_M_return": anchor.makespan, "anchor_cost": anchor.cost,
            "exact_reassign_M_return": mk,
            "validated_M_return": val.get("M_return"), "validated_cost": val.get("cost"),
            "admissible": val.get("admissible"), "issues": val.get("issues"),
            "cost_delta_vs_anchor": (None if val.get("cost") is None
                                     else val["cost"] - anchor.cost),
            "improvement_pct": 100.0 * (mk - anchor.makespan) / anchor.makespan,
            "per_station": per_station,
        })
        print(json.dumps({k: rows[-1][k] for k in
                          ("map", "anchor_M_return", "exact_reassign_M_return",
                           "improvement_pct", "admissible", "cost_delta_vs_anchor")}), flush=True)
    (pop / "EXACT_REASSIGN_RESULTS.json").write_text(json.dumps(
        {"schema": "takeover_g3_exact_cost_neutral_reassign_v1", "rows": rows},
        indent=2, sort_keys=True, allow_nan=False) + "\n")
    ok = sum(1 for r in rows if r.get("status") == "OK")
    bad = [r for r in rows if r.get("status") == "OK" and not r.get("admissible")]
    print(json.dumps({"rows": len(rows), "ok": ok, "inadmissible": len(bad)}))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())