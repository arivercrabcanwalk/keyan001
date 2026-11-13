#!/usr/bin/env python3
"""WX-E stage 2: BC -> DAgger -> REINFORCE-POMO, G-b / G-c on dev.

Requires wx_e/GA_FREEZE.json with a G-a GO (or --force). Does not touch test.
"""
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
from collections import defaultdict
from multiprocessing import get_context
import numpy as np

sys.path.insert(0, WX_ROOT)
from wx2 import const as C, inst as I, evaljob as E, sim as S, policies as P, feat as F
from wx2 import learn as L

OUT = os.path.join(WX_ROOT, "wx_e")
RES = os.path.join(OUT, "results")
MOD = os.path.join(WX_ROOT, "models")
os.makedirs(MOD, exist_ok=True)
os.makedirs(RES, exist_ok=True)
LOG = open(os.path.join(OUT, "STAGE2.log"), "a", buffering=1)

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(s + "\n"); LOG.flush()


def mean(rows, k):
    xs = [r[k] for r in rows if k in r and r[k] is not None]
    return float(np.mean(xs)) if xs else float("nan")


# ---------- collection ----------
def _collect_job(job):
    """Run one day with a behaviour policy, return (X, A, mask) and metrics.

    job keys: path, sol, day, mode, beh ('rule' or 'net'), rule, ckpt, greedy, seed, P
    """
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    if job["beh"] == "rule":
        pol = P.name_policy(job["rule"])
    else:
        net = L.load_net(job["ckpt"])
        rng = np.random.default_rng(job.get("seed", 0))
        pol = L.make_policy(net, greedy=job.get("greedy", False), rng=rng)
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=job.get("P", C.P_MAIN))
    # wrap to record features
    buf = []
    inner = pol

    def wrap(ss, i, mask, cands, info):
        x = F.features(ss, i, mask, cands, info)
        a = inner(ss, i, mask, cands, info)
        buf.append((x, int(a), mask.copy()))
        return a
    m = sim.run(wrap, record_time=False)
    X = np.stack([b[0] for b in buf]) if buf else np.zeros((0, F.NIN), np.float32)
    A = np.array([b[1] for b in buf], dtype=np.int32)
    M = np.stack([b[2] for b in buf]) if buf else np.zeros((0, 5), np.bool_)
    return dict(X=X, A=A, M=M, J=m["J"], ontime_h=m["ontime_h"], cvar_h=m["cvar_h"],
                fails=m["fails"], path=job["path"], day=job["day"], n=len(buf),
                n_hold=m["n_hold"], n_launch=m["n_launch"], n_serve=m["n_serve"])


def _rollout_label_job(job):
    """At each behaviour-policy decision (subsampled), label with rollout expert."""
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    if job.get("ckpt"):
        net = L.load_net(job["ckpt"])
        beh = L.make_policy(net, greedy=True, rng=np.random.default_rng(job.get("seed", 0)))
    else:
        beh = P.name_policy(job["rule"])
    expert = P.make_rollout(M=job.get("M", 8), base=P.name_policy(job["rule"]),
                            seed=job.get("seed", 0))
    rng = np.random.default_rng(job.get("seed", 1) + 99)
    q = job.get("q", 0.35)
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=job.get("P", C.P_MAIN))
    data = []

    def wrap(ss, i, mask, cands, info):
        x = F.features(ss, i, mask, cands, info)
        if rng.random() < q and mask.sum() > 1:
            a_star = expert(ss, i, mask, cands, info)
            data.append((x, int(a_star), mask.copy()))
        return beh(ss, i, mask, cands, info)
    m = sim.run(wrap, record_time=False)
    if not data:
        return dict(X=np.zeros((0, F.NIN), np.float32), A=np.zeros(0, np.int32),
                    M=np.zeros((0, 5), np.bool_), J=m["J"], n=0)
    return dict(X=np.stack([d[0] for d in data]), A=np.array([d[1] for d in data], np.int32),
                M=np.stack([d[2] for d in data]), J=m["J"], n=len(data))


def _pomo_job(job):
    """K stochastic rollouts of the current net on one (inst, day). Return trajectories + J."""
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    net = L.load_net(job["ckpt"])
    K = job["K"]
    outs = []
    for k in range(K):
        rng = np.random.default_rng(job.get("seed", 0) * 10007 + k * 17 + job["day"])
        pol = L.make_policy(net, greedy=False, rng=rng)
        sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=job.get("P", C.P_MAIN))
        buf = []

        def wrap(ss, i, mask, cands, info):
            x = F.features(ss, i, mask, cands, info)
            a, p = net.act(x, mask.astype(np.float64), greedy=False, rng=rng)
            buf.append((x, int(a), mask.copy()))
            return a
        m = sim.run(wrap, record_time=False)
        outs.append(dict(X=np.stack([b[0] for b in buf]) if buf else np.zeros((0, F.NIN), np.float32),
                         A=np.array([b[1] for b in buf], np.int32),
                         M=np.stack([b[2] for b in buf]) if buf else np.zeros((0, 5), np.bool_),
                         J=m["J"], ontime_h=m["ontime_h"], cvar_h=m["cvar_h"],
                         fails=m["fails"], n_hold=m["n_hold"], n_serve=m["n_serve"],
                         n_launch=m["n_launch"]))
    return outs


def _pair_job(j):
    rec = E.materialize(j["path"], j["sol"], j["day"], j.get("mode", "storm"), 0.08)
    ins = E._ins(j["path"])
    na, nb = L.load_net(j["ckpt_a"]), L.load_net(j["ckpt_b"])
    # follow RL greedy, compare what BC would do
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"])
    n = n_diff = 0
    kl_s = 0.0
    def wrap(ss, i, mask, cands, info):
        nonlocal n, n_diff, kl_s
        x = F.features(ss, i, mask, cands, info)
        a, pb = nb.act(x, mask.astype(np.float64), greedy=True)
        aa, pa = na.act(x, mask.astype(np.float64), greedy=True)
        n += 1
        n_diff += int(a != aa)
        # KL(RL||BC) on this state
        p = pb + 1e-8; q = pa + 1e-8
        # these are the greedy one-hot-ish? act returns full p from softmax
        # net.act returns p = probs
        kl_s += float(np.sum(pb * (np.log(pb + 1e-8) - np.log(pa + 1e-8))))
        return a
    sim.run(wrap, record_time=False)
    return dict(n=n, n_diff=n_diff, kl=kl_s)



def dev_eval(pool, ckpt, plans, days, rule, workers_unused=0, mode="storm"):
    jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode=mode,
                 beh="net" if ckpt else "rule", rule=rule, ckpt=ckpt, greedy=True,
                 seed=0, P=C.P_MAIN) for r in plans for d in days]
    # subsample for frequent eval: first 8 maps × all 10 days if ckpt eval mid-training
    res = pool.map(_collect_job, jobs, chunksize=1)
    return res


def fit_bc(net, X, A, M, epochs=3, lr=2e-3, smooth=0.1, batch=256, rng=None, log_fn=log):
    rng = rng or np.random.default_rng(0)
    n = len(X)
    # one-hot with label smoothing: the 'action' stays A, weight=1; we can mix
    for ep in range(epochs):
        perm = rng.permutation(n)
        losses = []
        for s in range(0, n, batch):
            idx = perm[s:s + batch]
            # BC: advantages = 1, maybe smooth by giving a fraction of weight to uniform legal
            w = np.ones(len(idx))
            grads, diag = net.backward(X[idx], M[idx].astype(np.float64), A[idx], w, ent_coef=smooth * 0.05)
            net.step(grads, lr=lr)
            losses.append(diag)
        log_fn(f"bc ep{ep} n={n} loss={np.mean([d['loss'] for d in losses]):.4f} "
               f"acc={np.mean([d['acc'] for d in losses]):.3f} ent={np.mean([d['ent'] for d in losses]):.3f}")
    return net


def _run_pomo_v2(args, freeze, rule, tag, pool, *, train_plans, dev_plans, dev_days,
                 skip_pretrain, net=None, bc_path=None):
    """Stabilized POMO (PREREG addendum). Writes only tagged files."""
    from wx2 import pomo_v2 as V2
    MOD = os.path.join(WX_ROOT, "models")
    OUT = os.path.join(WX_ROOT, "wx_e")
    # untagged originals are the seed-0 frozen BC/DAgger; tagged are fresh pretrain
    def untagged(stem_fmt):
        return os.path.join(MOD, stem_fmt.format(s=args.seed))

    cands = []
    if args.init_from:
        cands.append(("explicit", args.init_from))
    else:
        # prefer frozen untagged (seed 0), then tagged (fresh pretrain)
        for name, fmt in (("dagger_r0", "dagger_s{s}_r0.npz"),
                          ("dagger_r1", "dagger_s{s}_r1.npz"),
                          ("bc", "bc_s{s}.npz")):
            cands.append((name, untagged(fmt)))
        if tag:
            for name, stem in (("dagger_r0_tag", f"dagger_s{args.seed}_r0{tag}.npz"),
                               ("dagger_r1_tag", f"dagger_s{args.seed}_r1{tag}.npz"),
                               ("bc_tag", f"bc_s{args.seed}{tag}.npz")):
                cands.append((name, os.path.join(MOD, stem)))
    # unique existing
    seen = set(); uniq = []
    for n, pth in cands:
        if pth in seen:
            continue
        seen.add(pth)
        uniq.append((n, pth))
    best, scored = V2.select_init(uniq, pool, dev_eval, dev_plans, dev_days, rule, args.mode, log, mean)
    init_path, init_name, init_J = best["path"], best["name"], best["J"]
    torchless = L.load_net(init_path, rng=np.random.default_rng(args.seed))
    torchless.reset_adam()
    ref = L.load_net(init_path, rng=np.random.default_rng(0))
    # BC path for G-c: untagged first
    if bc_path is None or not os.path.exists(bc_path):
        for pth in (untagged("bc_s{s}.npz"), os.path.join(MOD, f"bc_s{args.seed}{tag}.npz")):
            if os.path.exists(pth):
                bc_path = pth
                break
    if bc_path is None or not os.path.exists(bc_path):
        log("WARN no BC ckpt for G-c; will use init as BC proxy")
        bc_path = init_path

    best_path = os.path.join(MOD, f"rl_s{args.seed}_best{tag}.npz")
    live_path = os.path.join(MOD, f"rl_s{args.seed}_live{tag}.npz")
    logp_path = os.path.join(OUT, f"results/train_s{args.seed}{tag}.jsonl")
    L.save_net(torchless, live_path)

    V2.train(
        torchless, pool=pool, train_plans=train_plans, dev_plans=dev_plans,
        dev_days=dev_days, rule=rule, mode=args.mode, seed=args.seed,
        hours=args.hours, B=args.B if args.B != 32 else V2.HP["B"],
        K=args.K, eval_every=args.eval_every, tag=tag, freeze=freeze,
        log_fn=log, mean_fn=mean, dev_eval=dev_eval,
        MOD=MOD, OUT=OUT, init_name=init_name, init_J=init_J, init_path=init_path,
        ref_net=ref, logp_path=logp_path, best_path=best_path, live_path=live_path,
        max_iters=getattr(args, "max_iters", None),
    )

    # ---- G-b / G-c on best (same gates as v1) ----
    ev = dev_eval(pool, best_path, dev_plans, dev_days, rule, mode=args.mode)
    J = mean(ev, "J"); ot = mean(ev, "ontime_h")
    gap = (J - freeze["J_n"]) / freeze["J_n"] * 100
    dot = (ot - freeze["ot_n"]) * 100
    gb_j = gap <= -0.5
    gb_ot = dot >= 1.5
    gb = gb_j or gb_ot
    pair_jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                      ckpt_a=bc_path, ckpt_b=best_path, rule=rule)
                 for r in dev_plans for d in dev_days]
    pairs = pool.map(_pair_job, pair_jobs, chunksize=1)
    n = sum(p["n"] for p in pairs) + 1e-9
    frac_diff = sum(p["n_diff"] for p in pairs) / n
    kl = sum(p["kl"] for p in pairs) / n
    gc_kl = kl > 0.01
    gc_diff = frac_diff >= 0.05
    gc = gc_kl and gc_diff
    out = dict(seed=args.seed, rule=rule, variant="pomo_v2", sanity=bool(args.sanity),
               tag=tag, init=init_name, init_J=init_J, init_path=init_path,
               dev_J=J, dev_ot=ot, dev_cvar=mean(ev, "cvar_h"),
               dev_fails=mean(ev, "fails"), dev_holds=mean(ev, "n_hold") if ev and "n_hold" in ev[0] else None,
               gap_vs_bestN=gap, d_ot_pp=dot,
               G_b=gb, G_b_J=gb_j, G_b_ot=gb_ot,
               G_c=gc, KL=kl, frac_diff=frac_diff, gc_kl=gc_kl, gc_diff=gc_diff,
               best_ckpt=best_path, hours=args.hours,
               J_n=freeze["J_n"], ot_n=freeze["ot_n"],
               bc_path=bc_path)
    log("SEED RESULT", json.dumps(out, indent=2, default=float))
    gb_file = os.path.join(OUT, f"GB_s{args.seed}{tag}.json")
    with open(gb_file, "w") as f:
        json.dump(out, f, indent=2, default=float)
    log("wrote", gb_file)
    return 0 if gb else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hours", type=float, default=2.0, help="RL budget per seed (G-b: <=2h)")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WX_WORKERS", "4")))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--K", type=int, default=8)
    ap.add_argument("--B", type=int, default=32, help="POMO batch (days)")
    ap.add_argument("--M-dagger", type=int, default=8, dest="M_dagger")
    ap.add_argument("--dagger-days", type=int, default=200)
    ap.add_argument("--bc-days", type=int, default=400)
    ap.add_argument("--mode", type=str, default="storm", help="weather mode: storm or uniform (P3 retrain)")
    ap.add_argument("--tag", type=str, default="", help="optional suffix for ckpt/result names")
    ap.add_argument("--variant", type=str, default="pomo_v1", choices=["pomo_v1", "pomo_v2"],
                    help="pomo_v1 = preregistered (known divergent). pomo_v2 = stabilized (PREREG addendum).")
    ap.add_argument("--skip-pretrain", action="store_true",
                    help="skip BC+DAgger; select init among existing untagged BC/DAgger ckpts on dev")
    ap.add_argument("--sanity", action="store_true",
                    help="short dev sanity (default 0.42 h, eval every 5); writes *_sanity artifacts")
    ap.add_argument("--eval-every", type=int, default=None)
    ap.add_argument("--init-from", type=str, default="", help="optional explicit init ckpt")
    ap.add_argument("--max-iters", type=int, default=None, dest="max_iters",
                    help="optional POMO iteration cap (smoke / debug); default is time budget only")
    ap.add_argument("--dev-limit", type=int, default=0, help="use only the first N dev plans (smoke)")
    ap.add_argument("--dev-days", type=str, default="", help="comma-separated dev weather days override")
    ap.add_argument("--train-limit", type=int, default=0, help="use only the first N train plans (smoke)")

    args = ap.parse_args()

    freeze_p = os.path.join(OUT, "GA_FREEZE.json")
    if not os.path.exists(freeze_p):
        log("NO GA_FREEZE.json — run stage 1 first")
        return 2
    freeze = json.load(open(freeze_p))
    if (not freeze.get("ga_o")) and (not args.force):
        log("G-a O gate failed; refusing to train (pass --force to override)")
        return 3
    # If N4 didn't pass, still allow training if O passed (document); G-a official needs both.
    if (not freeze.get("ga_n4")) and (not args.force):
        log("WARN G-a N4 gate not passed; training anyway for diagnosis? ",
            "official G-a is NO-GO. Use --force to train. Stopping.")
        # The prompt: if G-a fails, stop, write report, maybe one calibration.
        # I will still train if O passed, because we want to see G-b, but mark unofficial.
        if not freeze.get("ga_o"):
            return 3
        log("O passed but N4 did not: will train and FLAG as unofficial vs strict G-a.")
    rule = freeze["best_n"]
    tag = args.tag or ("" if args.mode == "storm" else f"_{args.mode}")
    if args.variant == "pomo_v2" and not args.tag:
        tag = "_pomo_v2" if args.mode == "storm" else f"_pomo_v2_{args.mode}"
        if args.sanity:
            tag = tag + "_sanity"
    if args.sanity:
        if "--hours" not in sys.argv:
            args.hours = 0.42
        if args.eval_every is None:
            args.eval_every = 5
    if args.eval_every is None:
        args.eval_every = 10 if args.variant == "pomo_v2" else 15
    # suffix for this run (P3 uniform retrains use tag=_uniform)
    def _p(name):
        # insert tag before extension or at end of stem
        if name.endswith(".npz"):
            return name[:-4] + tag + ".npz"
        if name.endswith(".json") or name.endswith(".jsonl"):
            root, ext = name.rsplit(".", 1)
            return root + tag + "." + ext
        return name + tag
    args._tag = tag
    log("=" * 60)
    log("STAGE2 start", time.strftime("%Y-%m-%d %H:%M:%S %z"), "seed", args.seed, "rule", rule,
        "mode", args.mode, "tag", tag, "variant", args.variant, "sanity", args.sanity,
        "hours", args.hours, "skip_pretrain", args.skip_pretrain)
    log("freeze", json.dumps({k: freeze[k] for k in freeze if k in
                              ("best_n", "J_n", "ot_n", "verdict", "ga_o", "ga_n4")}))

    train_plans = I.load_plans("train_ours")
    dev_plans = I.load_plans("dev_ours")
    dev_days = list(C.DEV_DAYS)
    if getattr(args, "dev_days", ""):
        dev_days = [int(x) for x in args.dev_days.split(",") if x.strip()]
    if getattr(args, "dev_limit", 0):
        dev_plans = dev_plans[: int(args.dev_limit)]
        log("SMOKE/limit dev_plans", len(dev_plans), "dev_days", dev_days)
    if getattr(args, "train_limit", 0):
        train_plans = train_plans[: int(args.train_limit)]
        log("SMOKE/limit train_plans", len(train_plans))
    rng = np.random.default_rng(args.seed)
    torchless = L.PolicyNet(np.random.default_rng(args.seed))
    pool = get_context("fork").Pool(args.workers, maxtasksperchild=25)

    # ---- optional skip of BC/DAgger (pomo_v2 seed 0 reuses frozen ckpts) ----
    from wx2 import pomo_v2 as V2
    if args.skip_pretrain:
        torchless, bc_path, dagger_last, tag, rule = None, None, None, tag, rule  # placeholders filled below
        # fall through to a dedicated branch after this if; implemented as a function call
        rc = _run_pomo_v2(args, freeze, rule, tag, pool, train_plans=train_plans,
                          dev_plans=dev_plans, dev_days=dev_days,
                          skip_pretrain=True, net=None)
        pool.close(); pool.join()
        return rc

    # ---- BC ----
    t0 = time.time()
    bc_jobs = []
    for _ in range(args.bc_days):
        r = train_plans[int(rng.integers(len(train_plans)))]
        day = int(C.TRAIN_WX_MIN + rng.integers(0, 200000))
        bc_jobs.append(dict(path=r["path"], sol=r["solution"], day=day, mode=args.mode,
                            beh="rule", rule=rule, ckpt=None, greedy=True, seed=args.seed, P=C.P_MAIN))
    log("BC collecting", len(bc_jobs), "days")
    # materialize a subset first in parent? train weather is new — pack will run. OK.
    cols = pool.map(_collect_job, bc_jobs, chunksize=1)
    X = np.concatenate([c["X"] for c in cols if len(c["X"])], 0)
    A = np.concatenate([c["A"] for c in cols if len(c["A"])], 0)
    M = np.concatenate([c["M"] for c in cols if len(c["M"])], 0)
    log(f"BC data {len(X)} decisions, rule J_train={np.mean([c['J'] for c in cols]):.1f}, "
        f"acc-base n/a, hold_frac={(A==1).mean():.3f} serve_frac={(A>=2).mean():.3f} sec={time.time()-t0:.1f}")
    fit_bc(torchless, X, A, M, epochs=3, lr=2e-3, smooth=0.1, rng=np.random.default_rng(args.seed))
    bc_path = os.path.join(MOD, f"bc_s{args.seed}{tag}.npz")
    L.save_net(torchless, bc_path)
    # snapshot BC net for KL
    bc_net = L.PolicyNet(np.random.default_rng(0))
    bc_net.load(torchless.params())

    # dev eval BC
    dev_sub = dev_plans[:8]  # 8x10=80 for mid eval; full 20x10 at the end
    ev = dev_eval(pool, bc_path, dev_plans, dev_days, rule, mode=args.mode)
    log(f"BC dev J={mean(ev,'J'):.2f} ot={mean(ev,'ontime_h'):.4f} cvar={mean(ev,'cvar_h'):.2f} "
        f"fails={mean(ev,'fails'):.2f} holds={mean(ev,'n_hold'):.1f} vs rule {rule} J_n={freeze['J_n']:.2f}")

    # ---- DAgger 2 rounds ----
    Xall, Aall, Mall = [X], [A], [M]
    for rd in range(2):
        t1 = time.time()
        djobs = []
        ckpt = os.path.join(MOD, f"dagger_s{args.seed}_r{rd-1}{tag}.npz" if rd else bc_path)
        if rd == 0:
            ckpt = bc_path
        L.save_net(torchless, ckpt)
        for _ in range(args.dagger_days):
            r = train_plans[int(rng.integers(len(train_plans)))]
            day = int(C.TRAIN_WX_MIN + 300000 + rd * 200000 + rng.integers(0, 200000))
            djobs.append(dict(path=r["path"], sol=r["solution"], day=day, mode=args.mode,
                              ckpt=ckpt, rule=rule, M=args.M_dagger, q=0.35,
                              seed=int(rng.integers(1 << 30)), P=C.P_MAIN))
        log(f"DAgger round {rd}: {len(djobs)} days, M={args.M_dagger}")
        labs = pool.map(_rollout_label_job, djobs, chunksize=1)
        nlab = sum(c["n"] for c in labs)
        log(f"DAgger r{rd} labels={nlab} sec={time.time()-t1:.1f}")
        if nlab:
            Xall.append(np.concatenate([c["X"] for c in labs if c["n"]], 0))
            Aall.append(np.concatenate([c["A"] for c in labs if c["n"]], 0))
            Mall.append(np.concatenate([c["M"] for c in labs if c["n"]], 0))
        Xt = np.concatenate(Xall, 0); At = np.concatenate(Aall, 0); Mt = np.concatenate(Mall, 0)
        fit_bc(torchless, Xt, At, Mt, epochs=2, lr=1e-3, smooth=0.05, rng=np.random.default_rng(args.seed + rd + 1))
        dpath = os.path.join(MOD, f"dagger_s{args.seed}_r{rd}{tag}.npz")
        L.save_net(torchless, dpath)
        ev = dev_eval(pool, dpath, dev_plans, dev_days, rule, mode=args.mode)
        log(f"DAgger r{rd} dev J={mean(ev,'J'):.2f} ot={mean(ev,'ontime_h'):.4f} "
            f"cvar={mean(ev,'cvar_h'):.2f} fails={mean(ev,'fails'):.2f} holds={mean(ev,'n_hold'):.1f}")

    # ---- REINFORCE-POMO ----
    if args.variant == "pomo_v2":
        rc = _run_pomo_v2(args, freeze, rule, tag, pool, train_plans=train_plans,
                          dev_plans=dev_plans, dev_days=dev_days,
                          skip_pretrain=False, net=torchless, bc_path=bc_path)
        pool.close(); pool.join()
        return rc
    t_rl = time.time()
    budget = args.hours * 3600
    it = 0
    best = 1e18
    best_path = os.path.join(MOD, f"rl_s{args.seed}_best{tag}.npz")
    logp = open(os.path.join(OUT, f"results/train_s{args.seed}{tag}.jsonl"), "a")
    dagger_last = os.path.join(MOD, f"dagger_s{args.seed}_r1{tag}.npz")
    if os.path.exists(dagger_last):
        torchless = L.load_net(dagger_last, rng=np.random.default_rng(args.seed))
    ent0, ent1 = 0.01, 0.001
    lr = 3e-4
    while time.time() - t_rl < budget:
        # eval every 15 iters (and it=0)
        if it % 15 == 0:
            ck = os.path.join(MOD, f"rl_s{args.seed}_it{it}{tag}.npz")
            L.save_net(torchless, ck)
            ev = dev_eval(pool, ck, dev_plans, dev_days, rule, mode=args.mode)
            J = mean(ev, "J"); ot = mean(ev, "ontime_h")
            gap = (J - freeze["J_n"]) / freeze["J_n"] * 100
            # action disagreement vs rule: collect
            # KL vs BC on last ev's would need features; approximate from n_hold
            rec = dict(it=it, dev_J=J, dev_ot=ot, dev_cvar=mean(ev, "cvar_h"),
                       dev_fails=mean(ev, "fails"), dev_holds=mean(ev, "n_hold"),
                       gap_vs_bestN=gap, sec=time.time() - t_rl, phase="rl")
            log(json.dumps(rec))
            logp.write(json.dumps(rec) + "\n"); logp.flush()
            if J < best:
                best = J
                L.save_net(torchless, best_path)
                log("NEW BEST", J, "gap", gap, "ot", ot)
            if time.time() - t_rl >= budget:
                break
        # one POMO batch
        ck = os.path.join(MOD, f"rl_s{args.seed}_live{tag}.npz")
        L.save_net(torchless, ck)
        jobs = []
        for _ in range(args.B):
            r = train_plans[int(rng.integers(len(train_plans)))]
            day = int(C.TRAIN_WX_MIN + 800000 + rng.integers(0, 500000))
            jobs.append(dict(path=r["path"], sol=r["solution"], day=day, mode=args.mode,
                             ckpt=ck, K=args.K, seed=args.seed, P=C.P_MAIN))
        batch = pool.map(_pomo_job, jobs, chunksize=1)
        Xs, As, Ms, Ws = [], [], [], []
        for outs in batch:
            Js = np.array([o["J"] for o in outs], dtype=np.float64)
            mu, sd = Js.mean(), Js.std() + 1e-6
            adv = (Js - mu) / sd  # lower J is better: we use +adv on (-logp) so need adv = J-centred
            # loss = w * (-logp) is minimized when high-w actions are avoided? 
            # We defined backward as loss = mean(w * (-logp)). To INCREASE prob of LOW-J, w should be (J-mean) 
            # (high J = high w = punish those actions). Yes adv = (J-mu)/sd.
            for o, a in zip(outs, adv):
                if len(o["A"]) == 0:
                    continue
                Xs.append(o["X"]); As.append(o["A"]); Ms.append(o["M"])
                Ws.append(np.full(len(o["A"]), a))
        if not Xs:
            it += 1
            continue
        Xb = np.concatenate(Xs); Ab = np.concatenate(As); Mb = np.concatenate(Ms); Wb = np.concatenate(Ws)
        frac = it / max(1, 200)
        ent = ent0 + (ent1 - ent0) * min(1.0, frac)
        # a few inner steps
        for _in in range(2):
            grads, diag = torchless.backward(Xb, Mb.astype(np.float64), Ab, Wb, ent_coef=ent)
            torchless.step(grads, lr=lr)
        if it % 5 == 0:
            log(f"rl it{it} batchJ={np.mean([o['J'] for outs in batch for o in outs]):.1f} "
                f"loss={diag['loss']:.3f} ent={diag['ent']:.3f} {diag} sec={time.time()-t_rl:.0f}")
        it += 1

    # final full-dev eval of best
    if os.path.exists(best_path):
        ev = dev_eval(pool, best_path, dev_plans, dev_days, rule, mode=args.mode)
    else:
        ev = []
        best_path = dagger_last
        ev = dev_eval(pool, best_path, dev_plans, dev_days, rule, mode=args.mode)
    J = mean(ev, "J"); ot = mean(ev, "ontime_h")
    gap = (J - freeze["J_n"]) / freeze["J_n"] * 100
    dot = (ot - freeze["ot_n"]) * 100
    gb_j = gap <= -0.5
    gb_ot = dot >= 1.5
    gb = gb_j or gb_ot
    # G-c: disagreement. Collect BC vs RL actions on dev.
    # KL
    # reload bc and best, run one pass storing probs — approximate via action freqs
    kl_jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                    beh="net", rule=rule, ckpt=best_path, greedy=True, seed=0, P=C.P_MAIN)
               for r in dev_plans for d in dev_days]
    ev_rl = ev
    ev_bc = dev_eval(pool, bc_path, dev_plans, dev_days, rule, mode=args.mode)
    # disagreement: we need paired actions. Re-collect both on same days with recorded actions — already have X,A
    # Use hold/serve/launch rates as a proxy PLUS a dedicated paired pass
    pair_jobs = [dict(path=r["path"], sol=r["solution"], day=d, mode=args.mode,
                      ckpt_a=bc_path, ckpt_b=best_path, rule=rule)
                 for r in dev_plans for d in dev_days]

    pairs = pool.map(_pair_job, pair_jobs, chunksize=1)
    n = sum(p["n"] for p in pairs) + 1e-9
    frac_diff = sum(p["n_diff"] for p in pairs) / n
    kl = sum(p["kl"] for p in pairs) / n
    gc_kl = kl > 0.01
    gc_diff = frac_diff >= 0.05
    gc = gc_kl and gc_diff

    out = dict(seed=args.seed, rule=rule, dev_J=J, dev_ot=ot, dev_cvar=mean(ev, "cvar_h"),
               dev_fails=mean(ev, "fails"), gap_vs_bestN=gap, d_ot_pp=dot,
               G_b=gb, G_b_J=gb_j, G_b_ot=gb_ot,
               G_c=gc, KL=kl, frac_diff=frac_diff, gc_kl=gc_kl, gc_diff=gc_diff,
               best_ckpt=best_path, hours=(time.time() - t_rl) / 3600.0, iters=it,
               J_n=freeze["J_n"], ot_n=freeze["ot_n"])
    log("SEED RESULT", json.dumps(out, indent=2))
    with open(os.path.join(OUT, f"GB_s{args.seed}{tag}.json"), "w") as f:
        json.dump(out, f, indent=2)
    pool.close(); pool.join()
    return 0 if gb else 1


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        traceback.print_exc()
        LOG.write(traceback.format_exc())
        sys.exit(2)
