#!/usr/bin/env python3
"""Post-hoc G-b/G-c finalize for a seed whose run_stage2 crashed at the G-c pairing step
(pickling bug of local pair_job, fixed 2026-11-13). Uses saved checkpoints only; no retraining.
Identical logic to the tail of run_stage2.main()."""

import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.dirname(_os_paths.path.abspath(__file__)))
WX_ROOT = _wx_root()
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)

import os, sys, json, time, argparse
from multiprocessing import get_context
import numpy as np
sys.path.insert(0, WX_ROOT)
import run_stage2 as R
from wx2 import const as C, inst as I

ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--workers", type=int, default=2); ap.add_argument("--iters", type=int, default=-1)
args = ap.parse_args()
freeze = json.load(open(os.path.join(R.OUT, "GA_FREEZE.json"))); rule = freeze["best_n"]
dev_plans = I.load_plans("dev_ours"); dev_days = list(C.DEV_DAYS)
bc_path = os.path.join(R.MOD, f"bc_s{args.seed}.npz")
best_path = os.path.join(R.MOD, f"rl_s{args.seed}_best.npz")
if not os.path.exists(best_path): best_path = os.path.join(R.MOD, f"dagger_s{args.seed}_r1.npz")
pool = get_context("fork").Pool(args.workers, maxtasksperchild=25)
R.log("FINALIZE-ONLY seed", args.seed, "best", best_path, time.strftime("%Y-%m-%d %H:%M:%S %z"))
ev = R.dev_eval(pool, best_path, dev_plans, dev_days, rule)
J = R.mean(ev, "J"); ot = R.mean(ev, "ontime_h")
gap = (J - freeze["J_n"]) / freeze["J_n"] * 100; dot = (ot - freeze["ot_n"]) * 100
gb_j = gap <= -0.5; gb_ot = dot >= 1.5; gb = gb_j or gb_ot
pair_jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm",
                  ckpt_a=bc_path, ckpt_b=best_path, rule=rule) for r in dev_plans for d in dev_days]
pairs = pool.map(R._pair_job, pair_jobs, chunksize=1)
n = sum(p["n"] for p in pairs) + 1e-9
frac_diff = sum(p["n_diff"] for p in pairs) / n; kl = sum(p["kl"] for p in pairs) / n
gc_kl = kl > 0.01; gc_diff = frac_diff >= 0.05; gc = gc_kl and gc_diff
out = dict(seed=args.seed, rule=rule, dev_J=J, dev_ot=ot, dev_cvar=R.mean(ev, "cvar_h"),
           dev_fails=R.mean(ev, "fails"), gap_vs_bestN=gap, d_ot_pp=dot,
           G_b=gb, G_b_J=gb_j, G_b_ot=gb_ot, G_c=gc, KL=kl, frac_diff=frac_diff,
           gc_kl=gc_kl, gc_diff=gc_diff, best_ckpt=best_path, hours=2.0, iters=args.iters,
           J_n=freeze["J_n"], ot_n=freeze["ot_n"], finalized_posthoc=True)
R.log("SEED RESULT (posthoc)", json.dumps(out, indent=2))
json.dump(out, open(os.path.join(R.OUT, f"GB_s{args.seed}.json"), "w"), indent=2)
pool.close(); pool.join()
