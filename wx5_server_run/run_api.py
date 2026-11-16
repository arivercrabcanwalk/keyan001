#!/usr/bin/env python3
"""WX3 main method: rollout-based Approximate Policy Iteration (API / Expert Iteration)
with fair (non-clairvoyant) rollouts and centred multi-objective Q-regression.

  it0: behaviour = N1_240 (+eps), expert = fair rollout with base N1_240  -> D0 (shared by all seeds)
  fit  pi_1 = argmax QNet trained on D0
  itk: behaviour = pi_k (+eps), expert = fair rollout with base pi_k      -> Dk
  fit  pi_{k+1} on D0..Dk (aggregation), warm start from pi_k
Label = per-action vector of rollout means (J, cost, mk, fails, late_h, ..., cvar_h);
target scalarisation Q_lam = J + lam_h * n_late_h + lam_c * cvar_h (Lagrangian weights).
Everything is resumable: label shards are per (plan, day) npz; fits are deterministic per seed.
"""
import argparse, glob, json, os, sys, time, hashlib
from multiprocessing import Pool
import numpy as np
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from wx2 import evaljob as E, sim as S, const as C, policies as P, inst as I
from wx2 import feat as F, twin as TW, qnet as QN

LK = TW.LABEL_KEYS


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _label_job(job):
    out = job["out"]
    if os.path.exists(out):
        return out, -1, 0.0
    t0 = time.time()
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    if job["beh"] == "rule":
        beh = P.name_policy(job["rule"]); base = P.name_policy(job["rule"])
    else:
        net = QN.load_any(job["beh"])
        beh = QN.make_policy_any(net, greedy=True)
        base = QN.make_policy_any(net, greedy=True)
        if job.get("base_rule"):
            base = P.name_policy(job["rule"])
    rngd = np.random.default_rng(job["seed"])
    record = []
    expert = TW.make_rollout_v3(M=job["M"], base=base, seed=job["seed"], fair=job.get("fair", True), record=record)
    X, MS, Q, NF = [], [], [], []

    def wrap(ss, i, mask, cands, info):
        if mask.sum() > 1 and rngd.random() < job["q"]:
            x = F.features(ss, i, mask, cands, info)
            n0 = len(record)
            expert(ss, i, mask, cands, info)
            if len(record) > n0:
                legal, Qm, nf = record[-1]
                q = np.full((S.N_ACT, len(LK)), np.nan)
                q[legal] = Qm
                X.append(x); MS.append(mask.astype(np.bool_)); Q.append(q); NF.append(nf)
        if mask.sum() > 1 and rngd.random() < job.get("eps", 0.05):
            legal = np.flatnonzero(mask)
            return int(legal[rngd.integers(len(legal))])
        return beh(ss, i, mask, cands, info)
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=C.P_MAIN)
    m = sim.run(wrap, record_time=False)
    tmp = out + ".tmp.npz"
    np.savez_compressed(tmp, X=np.array(X, np.float32).reshape(-1, F.NIN),
                        M=np.array(MS, np.bool_).reshape(-1, S.N_ACT),
                        Q=np.array(Q, np.float64).reshape(-1, S.N_ACT, len(LK)),
                        NF=np.array(NF, np.int32), J=np.array(m["J"]))
    os.replace(tmp, out)
    return out, len(X), time.time() - t0


def label_jobs(plans, n_days, day_base, out_dir, beh, M, q, seed, rule="N1_240", base_rule=False, fair=True):
    rng = np.random.default_rng(seed)
    jobs = []
    os.makedirs(out_dir, exist_ok=True)
    for k in range(n_days):
        r = plans[int(rng.integers(len(plans)))]
        day = int(day_base + rng.integers(0, 100000))
        stem = os.path.basename(r["path"]).replace(".txt", "")
        jobs.append(dict(path=r["path"], sol=r["solution"], day=day, beh=beh, rule=rule, M=M, q=q,
                         seed=int(rng.integers(1 << 30)), base_rule=base_rule, fair=fair,
                         out=os.path.join(out_dir, f"{k:05d}_{stem}_{day}.npz")))
    return jobs


def load_labels(dirs):
    X, M, Q = [], [], []
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.npz"))):
            if f.endswith(".tmp.npz"):
                continue
            z = np.load(f)
            if len(z["X"]):
                X.append(z["X"]); M.append(z["M"]); Q.append(z["Q"])
    if not X:
        return None
    return np.concatenate(X), np.concatenate(M), np.concatenate(Q)


def targets(M, Q, lam_h, lam_c, scale):
    """centred, negated, scaled scalarised Q (higher = better)."""
    i = {k: n for n, k in enumerate(LK)}
    sc = Q[..., i["J"]] + lam_h * Q[..., i["n_late_h"]] + lam_c * Q[..., i["cvar_h"]]
    sc = np.where(M, sc, 0.0)
    mean = sc.sum(1, keepdims=True) / M.sum(1, keepdims=True).clip(1)
    T = -(sc - mean) / scale
    return np.where(M, T, 0.0)


def fit(net, X, M, T, epochs, lr, seed, batch=256, log_fn=log):
    rng = np.random.default_rng(seed)
    n = len(X)
    Mf = M.astype(np.float64)
    for ep in range(epochs):
        idx = rng.permutation(n)
        L = A = 0.0; nb = 0
        for s in range(0, n, batch):
            b = idx[s:s + batch]
            g, d = net.loss_grad(X[b], Mf[b], T[b], delta=1.0)
            net.step(g, lr=lr * (0.5 ** (ep / max(1, epochs - 1) * 2)))
            L += d["loss"]; A += d["acc"]; nb += 1
        log_fn(f"  fit ep{ep} loss={L/nb:.4f} acc={A/nb:.3f} n={n}")
    return net


def dev_eval(pool, ckpt, plans, days, tag):
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", method="RL", P=C.P_MAIN,
                 extra=dict(ckpt=ckpt)) for r in plans for d in days]
    rows = pool.map(E.eval_one, jobs, chunksize=1)
    keys = ("J", "cost", "mk", "ontime", "ontime_h", "fails", "cvar_h")
    return {k: float(np.mean([r[k] for r in rows])) for k in keys} | dict(n=len(rows), tag=tag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--days", default="300,200,200", help="label days per iteration")
    ap.add_argument("--M", type=int, default=16)
    ap.add_argument("--q", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--lam", default="0:0", help="lam_h:lam_c pairs, comma-separated; selection on dev")
    ap.add_argument("--scale", type=float, default=100.0)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--dev-limit", type=int, default=0)
    ap.add_argument("--dev-days", default="6000-6009")
    ap.add_argument("--train-limit", type=int, default=0)
    ap.add_argument("--base-rule", action="store_true", help="keep N1_240 as rollout base in all iterations")
    ap.add_argument("--unfair", action="store_true", help="ablation: privileged (true-weather) rollouts")
    ap.add_argument("--labels", default=os.path.join(ROOT, "labels"))
    ap.add_argument("--models", default=os.path.join(ROOT, "models3"))
    ap.add_argument("--tag", default="api")
    ap.add_argument("--log-jsonl", default=None)
    a = ap.parse_args()
    from run_jobs3 import parse_days
    days_per = [int(x) for x in a.days.split(",")]
    while len(days_per) < a.iters:
        days_per.append(days_per[-1])
    train = I.load_plans("train_ours")
    if a.train_limit:
        train = train[:a.train_limit]
    dev = I.load_plans("dev_ours")
    if a.dev_limit:
        k = max(1, len(dev) // a.dev_limit); dev = dev[::k][:a.dev_limit]
    dev_days = parse_days(a.dev_days)
    lams = [tuple(float(v) for v in p.split(":")) for p in a.lam.split(",")]
    fair = not a.unfair
    ftag = "" if fair else "_unfair"
    os.makedirs(a.models, exist_ok=True)
    jl = a.log_jsonl or os.path.join(ROOT, "wx_e", "results", f"api_{a.tag}_s{a.seed}.jsonl")
    os.makedirs(os.path.dirname(jl), exist_ok=True)

    def jlog(d):
        with open(jl, "a") as f:
            f.write(json.dumps(d) + "\n")
    label_dirs = []
    beh = "rule"
    prev = None
    with Pool(a.workers, maxtasksperchild=20) as pool:
        for it in range(a.iters):
            if it == 0:
                ldir = os.path.join(a.labels, f"it0_M{a.M}_q{a.q}{ftag}")   # shared across seeds
                jseed = 12345
            else:
                ldir = os.path.join(a.labels, f"{a.tag}_s{a.seed}_it{it}_M{a.M}{ftag}" + ("_br" if a.base_rule else ""))
                jseed = 1000 * a.seed + it
            jobs = label_jobs(train, days_per[it], C.TRAIN_WX_MIN + 2_000_000 + it * 100_000, ldir,
                              beh, a.M, a.q, jseed, base_rule=a.base_rule, fair=fair)
            todo = [j for j in jobs if not os.path.exists(j["out"])]
            log(f"[s{a.seed} it{it}] label {len(todo)}/{len(jobs)} days -> {ldir}")
            t0 = time.time(); n = 0
            for out, nl, sec in pool.imap_unordered(_label_job, todo, chunksize=1):
                n += 1
                if n % 10 == 0 or n == len(todo):
                    log(f"[s{a.seed} it{it}] labelled {n}/{len(todo)} ({time.time()-t0:.0f}s)")
            label_dirs.append(ldir)
            data = load_labels(label_dirs)
            X, Mk, Q = data
            log(f"[s{a.seed} it{it}] dataset n={len(X)}")
            best = None
            for (lh, lc) in lams:
                ck = os.path.join(a.models, f"{a.tag}_s{a.seed}_it{it}_lh{lh:g}_lc{lc:g}{ftag}.npz")
                if not os.path.exists(ck):
                    if prev is not None:
                        net = QN.load_any(prev[1])
                    else:
                        net = QN.QNet(np.random.default_rng(a.seed))
                    T = targets(Mk, Q, lh, lc, a.scale)
                    fit(net, X, Mk, T, a.epochs, a.lr, seed=a.seed * 100 + it)
                    QN.save_qnet(net, ck)
                prevrows = [json.loads(l) for l in open(jl)] if os.path.exists(jl) else []
                hit = [r for r in prevrows if r.get("ckpt") == ck and not r.get("selected") and r.get("n") == len(dev) * len(dev_days)]
                if hit:
                    ev = hit[-1]
                    if (best is None or ev["J"] < best[0]):
                        best = (ev["J"], ck, lh, lc)
                    log(f"[s{a.seed} it{it}] lam=({lh:g},{lc:g}) dev (cached) J={ev['J']:.2f}")
                    continue
                ev = dev_eval(pool, ck, dev, dev_days, f"it{it}_lh{lh:g}_lc{lc:g}")
                ev.update(seed=a.seed, it=it, lam_h=lh, lam_c=lc, ckpt=ck, n_labels=int(len(X)), fair=fair)
                jlog(ev)
                log(f"[s{a.seed} it{it}] lam=({lh:g},{lc:g}) dev " + " ".join(f"{k}={ev[k]:.4f}" for k in ("J", "cost", "mk", "ontime_h", "fails", "cvar_h")))
                if best is None or ev["J"] < best[0]:
                    best = (ev["J"], ck, lh, lc)
            prev = best
            beh = best[1]
        # ---- pre-registered final selection (PREREG_v3 §4) ----
        ref_path = os.path.join(a.models, f"dev_ref_N1_{len(dev)}x{len(dev_days)}.json")
        if os.path.exists(ref_path):
            ref = json.load(open(ref_path))
        else:
            jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode="storm", method="N1_240", P=C.P_MAIN, extra={})
                    for r in dev for d in dev_days]
            rows = pool.map(E.eval_one, jobs, chunksize=1)
            ref = {k: float(np.mean([r[k] for r in rows])) for k in ("J", "ontime_h", "cvar_h", "fails", "cost", "mk")}
            json.dump(ref, open(ref_path, "w"))
    cands = [json.loads(l) for l in open(jl)] if os.path.exists(jl) else []
    cands = [c for c in cands if c.get("seed") == a.seed and not c.get("selected") and c.get("fair") == fair]
    feas = [c for c in cands if c["ontime_h"] >= ref["ontime_h"] - 1e-12 and c["cvar_h"] <= ref["cvar_h"] + 1e-12]
    pick = min(feas or cands, key=lambda c: c["J"])
    final = os.path.join(a.models, f"final_{a.tag}_s{a.seed}{ftag}.npz")
    import shutil
    shutil.copyfile(pick["ckpt"], final)
    pick = dict(pick, selected=True, feasible=bool(feas), final=final, ref_N1=ref)
    jlog(pick)
    log(f"[s{a.seed}] SELECTED it{pick['it']} lam=({pick['lam_h']:g},{pick['lam_c']:g}) feasible={bool(feas)} "
        f"J={pick['J']:.2f} (N1 {ref['J']:.2f}) ot_h={pick['ontime_h']:.4f} (N1 {ref['ontime_h']:.4f}) "
        f"cvar_h={pick['cvar_h']:.3f} (N1 {ref['cvar_h']:.3f}) -> {final}")


if __name__ == "__main__":
    main()
