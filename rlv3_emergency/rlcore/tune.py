"""Development tuning of named heuristic families; failures never qualify.

Evaluation counts and wall cost are recorded; equal dev data alone is not equal
compute or equal model-selection budget, nor evidence of the strongest control.
"""
import os, sys, json, argparse, time
from numbers import Real
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rlcore.common import load_plans, rel
from rlcore.scen import DEV_DAYS, SCENARIOS, make_env
from rlcore import policies as PO
from rlcore.train import eligible_result, development_score

MARGINS = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
THETAS = [8.0, 10.0]
FIXED_CONDITIONS = {"nowind", "fixed_e4", "fixed_n8"}


def _winit():
    import torch
    torch.set_num_threads(1)


def one(args):
    """Unregistered development probe; formal evaluation has a separate launcher."""
    row, day, scen, name, spec = args
    started = time.monotonic()
    try:
        env = make_env(row, day, scen)
        result = PO.run_episode(env, PO.make(spec))
        return dict(result, author_cost=env.L["author_cost"], author_cost_cap=env.L["author_cost"],
                    method=name, spec=spec, path=row["path"], day=day, wall=time.monotonic() - started)
    except Exception as error:
        return dict(method=name, spec=spec, path=row["path"], day=day, wall=time.monotonic() - started, error=repr(error))


def _qualified(summary):
    return bool(isinstance(summary, dict) and summary.get("qualified") == 1.0 and
                all(isinstance(summary.get(field), Real) and not isinstance(summary[field], bool)
                    and np.isfinite(summary[field]) for field in ("score", "J")))


def select_qualified(G, agg, kind="wx"):
    """Both tracks use their shared per-episode gates and minimized endpoint."""
    if kind not in ("wx", "urg"):
        raise ValueError("unknown tuning track")
    best, failed = {}, []
    for fam, specs in G.items():
        eligible = [s for s in specs if _qualified(agg[s])]
        if eligible:
            best[fam + "-T"] = min(eligible, key=lambda s: (agg[s]["score"], agg[s]["J"]))
        else:
            failed.append(fam)
    overall = min(best.values(), key=lambda s: (agg[s]["score"], agg[s]["J"])) if best else None
    return best, overall, failed


def require_tuned_reference(tuned, scenario, primary_reference):
    """Resolve tuning-only teacher and actual primary arm before any training."""
    if tuned.get("scen") != scenario:
        raise ValueError("tuning scenario differs from the registered training scenario")
    agg, best, teacher = tuned.get("grid", {}), tuned.get("best", {}), tuned.get("overall")
    if not isinstance(agg, dict) or not isinstance(best, dict):
        raise ValueError("invalid tuning aggregates or selected families")
    if not isinstance(teacher, str) or teacher not in best.values() or not _qualified(agg.get(teacher, {})):
        raise ValueError("tuning produced no eligible teacher with finite score")
    if any(not isinstance(spec, str) or not _qualified(agg.get(spec, {})) for spec in best.values()):
        raise ValueError("selected tuning family is not qualified with finite score")
    if primary_reference == "TUNED_OVERALL":
        reference = teacher
    elif primary_reference == "REOPT-T":
        reference = best.get("REOPT-T")
    elif primary_reference == "REOPT":
        # PO.make('REOPT') and PO.make('REOPT@0') have the same zero-margin
        # constructor. Check that actual probe, never a different tuned margin.
        reference = "REOPT" if "REOPT" in agg else "REOPT@0"
    else:
        raise ValueError("unsupported registered primary reference")
    if not isinstance(reference, str) or not _qualified(agg.get(reference, {})):
        raise ValueError("registered primary reference is missing or not qualified with finite score")
    return teacher


def grid(scen):
    if SCENARIOS[scen]["kind"] == "urg":       # deterministic energy: no risk buffer needed
        return {"A1": ["A1"], "GREEDY": ["GREEDY"], "REOPT": ["REOPT"]}
    g = {"A1": [f"A1@{m:g}" for m in MARGINS], "GREEDY": [f"GREEDY@{m:g}" for m in MARGINS],
         "REOPT": [f"REOPT@{m:g}" for m in MARGINS]}
    g["REOPT-W"] = [f"REOPT-W{t:g}@{m:g}" for t in THETAS for m in (0.1, 0.2, 0.3)]
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", required=True); ap.add_argument("--scen", required=True)
    ap.add_argument("--days", type=int, default=20); ap.add_argument("--maps", type=int, default=20)
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if not 1 <= a.days <= len(DEV_DAYS) or min(a.maps, a.workers) < 1:
        ap.error("days/maps/workers outside registered positive bounds")
    rows = load_plans(a.plans)[:a.maps]
    # These environments contain one deterministic condition per map. Relabeling
    # it as several development days adds cost without adding observations.
    days = DEV_DAYS[:1 if a.scen in FIXED_CONDITIONS else a.days]
    if not rows:
        ap.error("empty development plans")
    started = time.monotonic()
    G = grid(a.scen)
    specs = [s for v in G.values() for s in v]
    jobs = [(r, d, a.scen, s, s) for s in specs for r in rows for d in days]
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(a.workers, initializer=_winit) as pool:
        res = pool.map(one, jobs, chunksize=4)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out + ".attempts.jsonl", "w") as stream:
        for result in res:
            stream.write(json.dumps(result) + "\n")
    errs = [r for r in res if "error" in r]
    if errs:
        print("[tune] errors:", errs[:3]); sys.exit(1)
    agg = {}
    for s in specs:
        rr = [r for r in res if r["method"] == s]
        agg[s] = dict(J=float(np.mean([r["J"] for r in rr])), cost=float(np.mean([r["cost"] for r in rr])),
                      strict=float(np.mean([r["complete_strict"] for r in rr])),
                      qualified=float(np.mean([eligible_result(r, a.scen) for r in rr])),
                      score=development_score(rr, a.scen),
                      physical=float(np.mean([bool(r.get("physically_feasible") and r.get("all_returned")
                                                   and not r.get("timeout") and not r.get("failed")) for r in rr])),
                      inc=float(np.mean([r["inc_cell"] + r["inc_land"] for r in rr])))
    best, overall, failed = select_qualified(G, agg, SCENARIOS[a.scen]["kind"])
    out = dict(scen=a.scen, best=best, overall=overall, ineligible_families=failed, grid=agg, dev_days=days,
               n_maps=len(rows), n_specs=len(specs), evaluated_episodes=len(jobs), elapsed_wall=time.monotonic() - started,
               selection_objective=("negative_pooled_high_on_time_rate" if SCENARIOS[a.scen]["kind"] == "urg" else
                                    "M_return_with_per_map_author_cost_cap" if a.scen in FIXED_CONDITIONS else "failure_penalized_J_proxy"),
               qualification=("development_only_per_map_author_cost_cap_not_strongest_control" if a.scen in FIXED_CONDITIONS else
                              "development_only_not_strongest_control_cost_gate_pending"))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"[tune] {a.scen} best={best} overall={overall}")
    for s in specs:
        print(f"   {s:16s} J={agg[s]['J']:.2f} cost={agg[s]['cost']:.2f} strict={agg[s]['strict']:.3f} inc={agg[s]['inc']:.3f}")
    if overall is None:
        sys.exit(3)


if __name__ == "__main__":
    main()
