#!/usr/bin/env python3
"""Fit a complete-day J value net on greedy-RL (or rule) trajectories. For WX-H."""
from __future__ import annotations

import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.dirname(_os_paths.path.abspath(__file__)))
WX_ROOT = _wx_root()
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)

import os, sys, json, time, argparse, traceback
from multiprocessing import get_context
import numpy as np
sys.path.insert(0, WX_ROOT)
from wx2 import const as C, inst as I, evaljob as E, sim as S, feat as F, learn as L, policies as P

MOD = os.path.join(WX_ROOT, "models")
os.makedirs(MOD, exist_ok=True)

def log(*a):
    print(*a, flush=True)

def collect(job):
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    if job.get("ckpt"):
        net = L.load_net(job["ckpt"])
        pol = L.make_policy(net, greedy=True, rng=np.random.default_rng(0))
    else:
        pol = P.name_policy(job.get("rule", "N1_240"))
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=100)
    buf = []
    def wrap(ss, i, mask, cands, info):
        x = F.features(ss, i, mask, cands, info)
        a = pol(ss, i, mask, cands, info)
        buf.append(x)
        return a
    m = sim.run(wrap, record_time=False)
    if not buf:
        return dict(X=np.zeros((0, F.NIN), np.float32), y=np.zeros(0), J=m["J"])
    X = np.stack(buf)
    y = np.full(len(buf), m["J"], dtype=np.float64)
    return dict(X=X, y=y, J=m["J"], n=len(buf))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=str, default="")
    ap.add_argument("--out", type=str, default=os.path.join(MOD, "value_s0.npz"))
    ap.add_argument("--plans", type=str, default="dev_ours")
    ap.add_argument("--n-train", type=int, default=80, help="extra random train days")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WX_WORKERS", "3")))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit-plans", type=int, default=0)
    ap.add_argument("--days", type=str, default="")
    ap.add_argument("--epochs", type=int, default=12)

    args = ap.parse_args()
    if not args.ckpt:
        for s in (0, 1, 2):
            p = os.path.join(WX_ROOT, "models", f"rl_s{s}_best_pomo_v2.npz")
            if os.path.exists(p):
                args.ckpt = p
                break
    if not args.ckpt:
        log("no ckpt, will collect from N1_240")
    plans = I.load_plans(args.plans)
    train = I.load_plans("train_ours")
    rng = np.random.default_rng(args.seed)
    if getattr(args, "limit_plans", 0):
        plans = plans[: int(args.limit_plans)]
    dev_days = list(C.DEV_DAYS)
    if getattr(args, "days", ""):
        dev_days = [int(x) for x in args.days.split(",") if x.strip()]
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", ckpt=args.ckpt or None)
            for r in plans for d in dev_days]
    for _ in range(args.n_train):
        r = train[int(rng.integers(len(train)))]
        day = int(C.TRAIN_WX_MIN + 900000 + rng.integers(0, 100000))
        jobs.append(dict(path=r["path"], sol=r["solution"], day=day, mode="storm", ckpt=args.ckpt or None))
    log(f"value collect {len(jobs)} days ckpt={args.ckpt} W={args.workers}")
    t0 = time.time()
    with get_context("fork").Pool(args.workers, maxtasksperchild=20) as pool:
        cols = pool.map(collect, jobs, chunksize=1)
    Xs = [c["X"] for c in cols if len(c["X"])]
    ys = [c["y"] for c in cols if len(c["y"])]
    X = np.concatenate(Xs, 0)
    y = np.concatenate(ys, 0)
    log(f"data {len(y)} states, J mean={y.mean():.1f} std={y.std():.1f} sec={time.time()-t0:.1f}")
    net = L.ValueNet(np.random.default_rng(args.seed))
    # standardize targets for stability, store mu/sd in a sidecar
    mu, sd = float(y.mean()), float(y.std() + 1e-6)
    yn = (y - mu) / sd
    hist = net.fit(X, yn, epochs=getattr(args, "epochs", 12), lr=1e-3, batch=256, rng=np.random.default_rng(args.seed))
    pred = net.predict(X) * sd + mu
    mae = float(np.abs(pred - y).mean())
    corr = float(np.corrcoef(pred, y)[0, 1]) if len(y) > 2 else 0.0
    log(f"fit mae={mae:.1f} corr={corr:.3f} last={hist[-1] if hist else None}")
    L.save_value(net, args.out)
    json.dump(dict(mu=mu, sd=sd, mae=mae, corr=corr, n=int(len(y)), ckpt=args.ckpt,
                   hist=hist), open(args.out + ".meta.json", "w"), indent=2, default=float)
    # also save a random untrained net for ablation, same architecture
    rnd = L.ValueNet(np.random.default_rng(999))
    L.save_value(rnd, os.path.join(os.path.dirname(args.out), "value_random.npz"))
    json.dump(dict(mu=mu, sd=sd, random=True),
              open(os.path.join(os.path.dirname(args.out), "value_random.npz.meta.json"), "w"), indent=2)
    log("wrote", args.out)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        traceback.print_exc(); sys.exit(2)
