#!/usr/bin/env python3
"""Pre-registered selection (PREREG_v5 §5). For one (variant, seed) run: candidates = {best-val ckpt, final ckpt}.
REFUSES to select unless the run reached the pre-registered iteration count (DONE marker, equal compute).
Each candidate is evaluated ONCE on dev (dev_ours x dev days). Choose min dev J5 subject to
  dev complete == 100%  AND  dev mean ot_min <= dev mean ot_min of the frozen N6_best (+budget, =0) (constrained variants);
else min J5 among complete candidates (FLAGGED feasible=False).
Writes {models}/final_{name}.npz + select_{name}.json; dev evals cached (resume-safe)."""
import argparse, json, os, shutil, sys
from multiprocessing import Pool
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
os.environ.setdefault("WX_ROOT", ROOT)
from wx2 import evaljob as E, const as C, inst as I
from run_jobs3 import parse_days
KEYS = ("J", "J_v4", "cost", "mk", "ot_min", "ontime", "ontime_h", "fails", "cvar_h", "complete", "unfinished")


def dev_eval(pool, method, extra, plans, days):
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", method=method, P=C.P_MAIN,
                 extra=extra, record_time=False) for r in plans for d in days]
    rows = pool.map(E.eval_one, jobs, chunksize=1)
    rows = [r for r in rows if "error" not in r]
    return {k: float(np.mean([r[k] for r in rows])) for k in KEYS} | dict(n=len(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="run name, e.g. es5_s0 or es5_s0_noforecast")
    ap.add_argument("--iters", type=int, required=True)
    ap.add_argument("--models", default=os.path.join(ROOT, "models5"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dev-days", default="6000-6009")
    ap.add_argument("--dev-limit", type=int, default=0)
    ap.add_argument("--ot-budget", type=float, default=-1.0, help="<0: unconstrained; else dev ot <= ot(ref) + budget")
    ap.add_argument("--ot-ref", default="", help="frozen reference rule, e.g. N6_90_0.25")
    a = ap.parse_args()
    done = os.path.join(a.models, f"DONE_{a.name}")
    if not os.path.exists(done) or json.load(open(done))["iters"] < a.iters:
        print(f"REFUSE: {a.name} has not completed {a.iters} iterations (equal-compute rule)"); sys.exit(3)
    dev = I.load_plans("dev_ours")
    if a.dev_limit:
        k = max(1, len(dev) // a.dev_limit); dev = dev[::k][:a.dev_limit]
    days = parse_days(a.dev_days)
    cache_f = os.path.join(a.models, f"dev_cache_{a.name}.json")
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    cands = []
    ref_ot = 0.0
    with Pool(a.workers) as pool:
        if a.ot_ref:
            rk = f"REF|{a.ot_ref}|{len(dev)}|{a.dev_days}"
            if rk not in cache:
                cache[rk] = dev_eval(pool, a.ot_ref, None, dev, days); json.dump(cache, open(cache_f, "w"), indent=1)
            ref_ot = cache[rk]["ot_min"]
        for kind in ("best", "final"):
            f = os.path.join(a.models, f"es_{kind}_{a.name}.npz")
            if not os.path.exists(f):
                continue
            key = f"{kind}|{os.path.getmtime(f)}|{len(dev)}|{a.dev_days}"
            if key not in cache:
                cache[key] = dev_eval(pool, "RL5_x", {"ckpt": f}, dev, days); json.dump(cache, open(cache_f, "w"), indent=1)
            cands.append(dict(kind=kind, ckpt=f, dev=cache[key]))
    if not cands:
        print("no candidates"); sys.exit(2)
    comp = [c for c in cands if c["dev"]["complete"] >= 1.0 - 1e-12]
    feas = [c for c in comp if a.ot_budget < 0 or c["dev"]["ot_min"] <= ref_ot + a.ot_budget]
    pick = min(feas or comp or cands, key=lambda c: c["dev"]["J"])
    out = os.path.join(a.models, f"final_{a.name}.npz")
    shutil.copyfile(pick["ckpt"], out + ".tmp"); os.replace(out + ".tmp", out)
    sel = dict(name=a.name, candidates=cands, picked=pick, feasible=bool(feas), ot_budget=a.ot_budget, ot_ref=a.ot_ref, ref_dev_ot=ref_ot,
               rule="min dev J5 s.t. complete==1 and dev ot_min<=ot_min(frozen N6_best)+budget (constrained variants); else min J5 among complete (flagged)")
    json.dump(sel, open(os.path.join(a.models, f"select_{a.name}.json"), "w"), indent=1)
    print(json.dumps(dict(picked=pick["kind"], feasible=bool(feas), dev=pick["dev"])))


if __name__ == "__main__":
    main()
