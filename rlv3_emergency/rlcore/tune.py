"""Dev-set tuning of every non-RL baseline (fairness: baselines get the same dev budget for hyper-parameters as RL gets
for checkpoint selection).  Writes results/tuned_<scen>.json with the best spec per family + the overall best (teacher)."""
import os, sys, json, argparse
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from rlcore.common import load_plans, rel
from rlcore.scen import DEV_DAYS, SCENARIOS
from rlcore.evaluate import one, _winit

MARGINS = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]
THETAS = [8.0, 10.0]


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
    rows = load_plans(a.plans)[:a.maps]; days = DEV_DAYS[:a.days]
    G = grid(a.scen)
    specs = [s for v in G.values() for s in v]
    jobs = [(r, d, a.scen, s, s) for s in specs for r in rows for d in days]
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(a.workers, initializer=_winit) as pool:
        res = pool.map(one, jobs, chunksize=4)
    errs = [r for r in res if "error" in r]
    if errs:
        print("[tune] errors:", errs[:3]); sys.exit(1)
    agg = {}
    for s in specs:
        rr = [r for r in res if r["method"] == s]
        agg[s] = dict(J=float(np.mean([r["J"] for r in rr])), cost=float(np.mean([r["cost"] for r in rr])),
                      strict=float(np.mean([r["complete_strict"] for r in rr])),
                      inc=float(np.mean([r["inc_cell"] + r["inc_land"] for r in rr])))
    best = {}
    for fam, ss in G.items():
        ok = [s for s in ss if agg[s]["strict"] == 1.0] or ss
        best[fam + "-T"] = min(ok, key=lambda s: agg[s]["J"])     # "-T" = dev-tuned variant
    overall = min(best.values(), key=lambda s: agg[s]["J"])
    out = dict(scen=a.scen, best=best, overall=overall, grid=agg, dev_days=days, n_maps=len(rows))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"[tune] {a.scen} best={best} overall={overall}")
    for s in specs:
        print(f"   {s:16s} J={agg[s]['J']:.2f} cost={agg[s]['cost']:.2f} strict={agg[s]['strict']:.3f} inc={agg[s]['inc']:.3f}")


if __name__ == "__main__":
    main()
