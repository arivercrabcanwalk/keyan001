#!/usr/bin/env python3
"""Pre-registered selection (PREREG_v3 §4). For one seed: candidates = ES best-val ckpts for each lambda.
Each candidate is evaluated ONCE on the full dev set (dev_ours x 6000-6009). Choose min dev J subject to
dev ontime_h >= N1_240 dev ontime_h AND dev cvar_h <= N1_240 dev cvar_h; if none feasible -> min J, flagged.
Writes models3/final_es_s{seed}.npz and models3/select_es_s{seed}.json. Resume-safe (dev evals cached)."""
import argparse, json, os, shutil, sys
from multiprocessing import Pool
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
os.environ.setdefault("WX_ROOT", ROOT)
from wx2 import evaljob as E, const as C, inst as I
from run_jobs3 import parse_days
KEYS = ("J", "cost", "mk", "ontime", "ontime_h", "fails", "cvar_h")


def dev_eval(pool, method, extra, plans, days):
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", method=method, P=C.P_MAIN,
                 extra=extra, record_time=False) for r in plans for d in days]
    rows = pool.map(E.eval_one, jobs, chunksize=1)
    return {k: float(np.mean([r[k] for r in rows])) for k in KEYS} | dict(n=len(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--lams", required=True, help="e.g. 0:0,1:10,3:30")
    ap.add_argument("--tag", default="es")
    ap.add_argument("--models", default=os.path.join(ROOT, "models3"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dev-days", default="6000-6009")
    ap.add_argument("--dev-limit", type=int, default=0)
    a = ap.parse_args()
    dev = I.load_plans("dev_ours")
    if a.dev_limit:
        k = max(1, len(dev) // a.dev_limit); dev = dev[::k][:a.dev_limit]
    days = parse_days(a.dev_days)
    cache_f = os.path.join(a.models, f"dev_cache_{a.tag}.json")
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    ck = f"N1_240|{len(dev)}|{a.dev_days}"
    with Pool(a.workers) as pool:
        if ck not in cache:
            cache[ck] = dev_eval(pool, "N1_240", None, dev, days); json.dump(cache, open(cache_f, "w"), indent=1)
        ref = cache[ck]
        cands = []
        for lam in a.lams.split(","):
            v = [float(x) for x in lam.split(":")] + [0.0]
            lh, lc, lm = v[0], v[1], v[2]
            f = os.path.join(a.models, f"es_best_{a.tag}_s{a.seed}_lh{lh:g}_lc{lc:g}" + (f"_lm{lm:g}" if lm else "") + ".npz")
            if not os.path.exists(f):
                print("missing", f); continue
            key = f"{f}|{os.path.getmtime(f)}|{len(dev)}|{a.dev_days}"
            if key not in cache:
                cache[key] = dev_eval(pool, "RL", {"ckpt": f}, dev, days); json.dump(cache, open(cache_f, "w"), indent=1)
            cands.append(dict(lam=lam, ckpt=f, dev=cache[key]))
    if not cands:
        print("no candidates"); sys.exit(2)
    feas = [c for c in cands if c["dev"]["ontime_h"] >= ref["ontime_h"] and c["dev"]["cvar_h"] <= ref["cvar_h"]]
    pick = min(feas or cands, key=lambda c: c["dev"]["J"])
    out = os.path.join(a.models, f"final_{a.tag}_s{a.seed}.npz")
    shutil.copyfile(pick["ckpt"], out + ".tmp"); os.replace(out + ".tmp", out)
    sel = dict(seed=a.seed, N1_dev=ref, candidates=cands, picked=pick, feasible=bool(feas),
               rule="min dev J s.t. ontime_h>=N1 and cvar_h<=N1; else min J (flagged)")
    json.dump(sel, open(os.path.join(a.models, f"select_{a.tag}_s{a.seed}.json"), "w"), indent=1)
    print(json.dumps(dict(picked=pick["lam"], feasible=bool(feas), dev=pick["dev"], N1=ref)))


if __name__ == "__main__":
    main()
