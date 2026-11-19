#!/usr/bin/env python3
"""Run same-objective non-RL controls on new-population author anchors.

Methods: lpt (intact-trip longest-processing-time repack) and joint_minmax
(deterministic station-joint min-max route descent).  Every candidate is scored
by the independent full-map scorer under C <= C_anchor + 1e-7, epsilon=0.
"""
from __future__ import annotations
import argparse, importlib.util, json, pathlib, sys, time
from time import perf_counter

R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
RM = C / "route_rl_research/20261103/return_makespan"
sys.path.insert(0, str(RM))
sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix"))


# Import the scoring stack under its real module names.  Loading it twice
# under aliases would create distinct CostAnchor classes and break isinstance.
sys.path.insert(0, str(RM))
sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix/lrphsd"))
sys.path.insert(0, str(RM / "g23/nonrl_baseline"))
import problem  # noqa: E402
import scorer  # noqa: E402
import baseline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--budgets", default="6,12")
    ap.add_argument("--families", default="all")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    budgets = [float(x) for x in args.budgets.split(",")]
    index = json.loads((out / "population_index.json").read_text())
    maps = [m for m in index["maps"] if m["status"] == "generated"]
    if args.families != "all":
        keep = {x.strip() for x in args.families.split(",")}
        maps = [m for m in maps if f"{m['sites']}x{m['targets']}" in keep]


    # Register the batch intent before any solver call (compliance with the
    # project's "intent before execution" rule).  Earlier runs of this script
    # predate this block and are recorded as INTENT_MISSING in RUN_LOG.md.
    (out / "NONRL_INTENT.json").write_text(json.dumps({
        "schema": "takeover_g3_nonrl_intent_v1",
        "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "maps": [m["name"] for m in maps], "budgets_s": budgets,
        "methods": ["lpt", "joint_minmax"],
        "max_evaluations": 12000,
        "scorer_sha256": __import__("hashlib").sha256(
            (RM / "scorer.py").read_bytes()).hexdigest(),
        "baseline_sha256": __import__("hashlib").sha256(
            (RM / "g23/nonrl_baseline/baseline.py").read_bytes()).hexdigest(),
        "contract": {"epsilon": 0.0, "cost_tolerance": 1e-7,
                     "deadline_is_wall_clock": True},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sol_dir = out / "solutions"
    sol_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in maps:
        name = m["name"]
        adir = out / "author" / name
        run_json = adir / "RUN.json"
        if not run_json.exists():
            rows.append({"map": name, "status": "NO_AUTHOR_RUN"}); continue
        run = json.loads(run_json.read_text())
        if not run.get("anchor_eligible"):
            rows.append({"map": name, "status": "ANCHOR_NOT_ELIGIBLE"}); continue
        inst = problem.read_instance(pathlib.Path(m["path"]))
        sol = json.loads((adir / "solution.json").read_text())
        anchor = scorer.CostAnchor.from_solution(inst, sol)
        anchor.verify(inst)
        base = {"map": name, "sites": m["sites"], "targets": m["targets"],
                "instance_sha256": inst.sha256,
                "anchor_cost": anchor.cost, "anchor_M_return": anchor.makespan,
                "anchor_solution_sha256": anchor.solution_sha256}
        # structural reference points (descriptive, not certificates)
        a_score = scorer.score_solution(inst, anchor.solution())
        duties = [d["duty_min"] for d in a_score["slot_duty"]]
        open_slots = sum(1 for d in a_score["slot_duty"]
                         if any(t["station"] == d["station"] and t["slot"] == d["slot"]
                                for t in a_score["trips"])) or 0
        base["anchor_operating_minutes"] = a_score["operating_minutes"]
        base["anchor_open_slots"] = open_slots
        base["balance_ratio"] = (a_score["operating_minutes"] / open_slots / anchor.makespan
                                 if open_slots and anchor.makespan else None)
        for method in ("lpt", "joint_minmax"):
            for budget in (budgets if method == "joint_minmax" else [budgets[0]]):
                t0 = perf_counter()
                try:
                    res = baseline.solve(inst, anchor, method=method, budget_s=budget,
                                         started_at=None)
                    err = None
                except Exception as exc:  # noqa: BLE001 - failures are data
                    res, err = None, repr(exc)
                wall = perf_counter() - t0
                row = dict(base, method=method, budget_s=budget, wall_s=round(wall, 3))
                if res is not None:
                    # Persist the delivered complete solution so the row can be
                    # reproduced from artifacts, not by re-running the search.
                    sol_path = sol_dir / f"{name}__{method}__{int(budget)}s.json"
                    sol_path.write_text(json.dumps({
                        "schema": "takeover_g3_nonrl_solution_v1",
                        "map": name, "method": method, "budget_s": budget,
                        "status": res["status"],
                        "chosen_solution": res.get("chosen_solution"),
                        "raw_solution": res.get("raw_solution"),
                        "chosen_solution_sha256": (
                            None if res.get("chosen_score") is None
                            else res["chosen_score"].get("solution_sha256")),
                        "raw_solution_sha256": (
                            None if res.get("raw_score") is None
                            else res["raw_score"].get("solution_sha256")),
                        "candidate_certificates": res.get("candidate_certificates"),
                        "accepted_moves": res.get("accepted_moves"),
                    }, indent=1, sort_keys=True) + "\n", encoding="utf-8")
                    row["solution_path"] = str(sol_path)
                    row["chosen_solution_sha256"] = (
                        None if res.get("chosen_score") is None
                        else res["chosen_score"].get("solution_sha256"))
                if err:
                    row.update({"status": "ERROR", "error": err}); rows.append(row); continue
                row.update({
                    "status": res["status"],
                    "ontime_valid_output": res["ontime_valid_output"],
                    "fallback_used": res["fallback_used"],
                    "fallback_reason": res["fallback_reason"],
                    "chosen_M_return": (res["chosen_score"] or {}).get("M_return"),
                    "chosen_cost": (res["chosen_score"] or {}).get("cost"),
                    "raw_M_return": (res["raw_score"] or {}).get("M_return"),
                    "raw_cost": (res["raw_score"] or {}).get("cost"),
                    "raw_admissible": (res["raw_score"] or {}).get("admissible"),
                    "candidate_validation_calls": res["candidate_validation_calls"],
                    "rejected_inadmissible_candidates": res["rejected_inadmissible_candidates"],
                    "accepted_moves": len(res["accepted_moves"]),
                    "search_timed_out": res["search_timed_out"],
                    "output_ready_elapsed_s": res["output_ready_elapsed_s"],
                })
                ch = row["chosen_M_return"]
                row["delta_M_return_pct"] = (None if ch is None or not anchor.makespan
                                             else 100.0 * (ch - anchor.makespan) / anchor.makespan)
                rows.append(row)
                print(json.dumps({k: row[k] for k in
                                  ("map", "method", "budget_s", "status",
                                   "anchor_M_return", "chosen_M_return",
                                   "delta_M_return_pct", "wall_s")}), flush=True)
        (out / "NONRL_RESULTS.json").write_text(json.dumps(
            {"schema": "takeover_g3_nonrl_results_v1", "rows": rows,
             "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            indent=2, sort_keys=True, allow_nan=False) + "\n")
    ok = sum(1 for r in rows if r.get("status") == "ONTIME_VALID")
    print(json.dumps({"rows": len(rows), "ontime_valid": ok}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())