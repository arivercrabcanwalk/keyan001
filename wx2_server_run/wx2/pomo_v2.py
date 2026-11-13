"""pomo_v2: signed, clipped, KL-regularized POMO (see wx_e/PREREG.md addendum).

Does not overwrite pomo_v1 artifacts. All hparams are the frozen addendum values.
"""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import json, os, time
import numpy as np
from . import const as C, evaljob as E, sim as S, feat as F, learn as L

# Frozen hparams (PREREG addendum 2026-11-13)
HP = dict(
    lr=1e-4,
    clip_eps=0.2,
    kl_coef=0.05,
    kl_step_max=0.03,
    kl_ref_max=0.15,
    grad_clip=1.0,
    sd_min=1.0,
    K=8,
    B=24,
    ppo_epochs=2,
    ent0=0.02,
    ent1=0.005,
    ent_horizon=200,
    lr_decay_trigger=1.05,  # restore + lr*=0.5 if dev J exceeds init * this
    eval_every=10,
    eval_every_sanity=5,
)


def _collect_job(job):
    """K stochastic rollouts; record features, actions, masks, and collection logp."""
    rec = E.materialize(job["path"], job["sol"], job["day"], job.get("mode", "storm"), 0.08)
    ins = E._ins(job["path"])
    net = L.load_net(job["ckpt"])
    K = job["K"]
    outs = []
    for k in range(K):
        rng = np.random.default_rng(job.get("seed", 0) * 10007 + k * 17 + job["day"] + 13 * job.get("it", 0))
        buf = []

        def wrap(ss, i, mask, cands, info, _net=net, _rng=rng, _buf=buf):
            x = F.features(ss, i, mask, cands, info)
            a, p = _net.act(x, mask.astype(np.float64), greedy=False, rng=_rng)
            lp = float(np.log(p[int(a)] + L.EPS))
            _buf.append((x, int(a), mask.copy(), lp))
            return a

        sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=job.get("P", C.P_MAIN))
        m = sim.run(wrap, record_time=False)
        if buf:
            X = np.stack([b[0] for b in buf])
            A = np.array([b[1] for b in buf], np.int32)
            M = np.stack([b[2] for b in buf])
            LP = np.array([b[3] for b in buf], np.float64)
        else:
            X = np.zeros((0, F.NIN), np.float32)
            A = np.zeros((0,), np.int32)
            M = np.zeros((0, 5), np.bool_)
            LP = np.zeros((0,), np.float64)
        outs.append(dict(X=X, A=A, M=M, LP=LP, J=m["J"], ontime_h=m["ontime_h"],
                         cvar_h=m["cvar_h"], fails=m["fails"],
                         n_hold=m["n_hold"], n_serve=m["n_serve"], n_launch=m.get("n_launch", 0)))
    return outs


def advantages_loo(Js, sd_min=HP["sd_min"]):
    """Leave-one-out POMO baseline, correct sign: low J → positive A."""
    Js = np.asarray(Js, dtype=np.float64)
    K = len(Js)
    if K <= 1:
        return np.zeros_like(Js)
    total = Js.sum()
    mu_lo = (total - Js) / (K - 1)
    sd = max(float(Js.std()), float(sd_min))
    return (mu_lo - Js) / sd


def pack_batch(batch, sd_min=HP["sd_min"]):
    """Concatenate K-rollout groups with per-trajectory equal weight.

    w_{k,t} = A_k * (N / n_traj) / T_k   so  mean_decisions(w * f) = mean_traj(A * mean_t f).
    """
    traj = []
    for outs in batch:
        Js = np.array([o["J"] for o in outs], np.float64)
        A = advantages_loo(Js, sd_min=sd_min)
        for o, a in zip(outs, A):
            T = len(o["A"])
            if T == 0:
                continue
            traj.append((o, float(a), T, float(o["J"]), float(o["n_hold"])))
    if not traj:
        return None
    n_traj = len(traj)
    N = sum(t[2] for t in traj)
    Xs, As, Ms, LPs, Ws = [], [], [], [], []
    Js, Hs, Ts, Advs = [], [], [], []
    for o, a, T, j, h in traj:
        w = np.full(T, a * (N / n_traj) / T)
        Xs.append(o["X"]); As.append(o["A"]); Ms.append(o["M"]); LPs.append(o["LP"]); Ws.append(w)
        Js.append(j); Hs.append(h); Ts.append(T); Advs.append(a)
    return dict(
        X=np.concatenate(Xs), A=np.concatenate(As),
        M=np.concatenate(Ms).astype(np.float64),
        LP=np.concatenate(LPs), W=np.concatenate(Ws),
        J=np.array(Js), H=np.array(Hs), T=np.array(Ts), adv=np.array(Advs),
        n_traj=n_traj, n_dec=N,
        batchJ=float(np.mean([o["J"] for outs in batch for o in outs])),
        batchH=float(np.mean([o["n_hold"] for outs in batch for o in outs])),
        batch_ot=float(np.mean([o["ontime_h"] for outs in batch for o in outs])),
    )


def ppo_update(net, ref, pk, *, lr, ent, hp=HP):
    """2 PPO epochs on a packed batch. Rejects the update if KL exceeds caps.
    Returns (accepted, diag).
    """
    snap = net.snapshot()
    X, M, A, W, LP = pk["X"], pk["M"], pk["A"], pk["W"], pk["LP"]
    ref_p = ref.probs(X, M) if ref is not None else None
    last = None
    gn0 = 0.0
    for _ep in range(hp["ppo_epochs"]):
        grads, diag = net.backward_ppo(
            X, M, A, W, LP,
            ent_coef=ent, clip_eps=hp["clip_eps"],
            ref_probs=ref_p, kl_coef=hp["kl_coef"],
        )
        gn, grads = L.clip_grads(grads, hp["grad_clip"])
        if _ep == 0:
            gn0 = gn
        net.step(grads, lr=lr)
        last = diag
    kl_step = L.kl_div(net, _net_from_snap(snap), X, M)
    kl_ref = L.kl_div(net, ref, X, M) if ref is not None else 0.0
    accepted = True
    reason = "ok"
    if kl_step > hp["kl_step_max"] or kl_ref > hp["kl_ref_max"]:
        net.restore(snap)
        accepted = False
        reason = "kl_step" if kl_step > hp["kl_step_max"] else "kl_ref"
    last = dict(last or {})
    last.update(gnorm=gn0, kl_step=kl_step, kl_ref_post=kl_ref,
                accepted=accepted, reject_reason=reason, lr=lr, ent_coef=ent)
    return accepted, last


def _net_from_snap(snap):
    n = L.PolicyNet(np.random.default_rng(0))
    n.restore(snap)
    return n


def select_init(candidates, pool, dev_eval, dev_plans, dev_days, rule, mode, log_fn, mean_fn):
    """candidates: list of (name, path). Eval on full dev, return best (lowest J)."""
    scored = []
    for name, path in candidates:
        if not os.path.exists(path):
            log_fn(f"init skip missing {name} {path}")
            continue
        ev = dev_eval(pool, path, dev_plans, dev_days, rule, mode=mode)
        J = mean_fn(ev, "J"); ot = mean_fn(ev, "ontime_h")
        h = mean_fn(ev, "n_hold") if ev and "n_hold" in ev[0] else float("nan")
        scored.append(dict(name=name, path=path, J=J, ot=ot, holds=h, ev=ev))
        log_fn(f"init cand {name} J={J:.4f} ot={ot:.4f} holds={h:.2f} {path}")
    if not scored:
        raise FileNotFoundError("no init checkpoints")
    scored.sort(key=lambda r: (r["J"], -r["ot"]))
    best = scored[0]
    log_fn(f"init SELECT {best['name']} J={best['J']:.4f}")
    return best, scored


def train(net, *, pool, train_plans, dev_plans, dev_days, rule, mode, seed,
          hours, B, K, eval_every, tag, freeze, log_fn, mean_fn, dev_eval,
          MOD, OUT, init_name, init_J, init_path, ref_net,
          logp_path, best_path, live_path, max_iters=None):
    """POMO v2 loop. Returns (best_path, last_full_eval_rows, history)."""
    t_rl = time.time()
    budget = hours * 3600
    rng = np.random.default_rng(seed + 17011)
    net.reset_adam()
    it = 0
    best = 1e18
    best_ot = -1e18
    hist = []
    n_reject = 0
    n_lr_decay = 0
    lr = HP["lr"]
    # initial eval (it=0) is the selected DAgger/BC — record as current best
    ev0 = dev_eval(pool, init_path, dev_plans, dev_days, rule, mode=mode)
    J0 = mean_fn(ev0, "J"); ot0 = mean_fn(ev0, "ontime_h")
    best = J0; best_ot = ot0
    L.save_net(net, best_path)
    rec0 = dict(it=0, dev_J=J0, dev_ot=ot0, dev_cvar=mean_fn(ev0, "cvar_h"),
                dev_fails=mean_fn(ev0, "fails"), dev_holds=mean_fn(ev0, "n_hold"),
                gap_vs_bestN=(J0 - freeze["J_n"]) / freeze["J_n"] * 100,
                sec=0.0, phase="rl_pomo_v2", init=init_name, accepted=True)
    log_fn(json.dumps(rec0))
    with open(logp_path, "a") as f:
        f.write(json.dumps(rec0) + "\n")
    log_fn("NEW BEST (init)", J0, "ot", ot0, init_name)

    while time.time() - t_rl < budget:
        if max_iters is not None and it >= max_iters:
            log_fn(f"max_iters={max_iters} reached, stopping POMO")
            break
        L.save_net(net, live_path)
        jobs = []
        for _ in range(B):
            r = train_plans[int(rng.integers(len(train_plans)))]
            day = int(C.TRAIN_WX_MIN + 800000 + rng.integers(0, 500000))
            jobs.append(dict(path=r["path"], sol=r["solution"], day=day, mode=mode,
                             ckpt=live_path, K=K, seed=seed, P=C.P_MAIN, it=it))
        batch = pool.map(_collect_job, jobs, chunksize=1)
        pk = pack_batch(batch, sd_min=HP["sd_min"])
        if pk is None:
            it += 1
            continue
        frac = it / max(1, HP["ent_horizon"])
        ent = HP["ent0"] + (HP["ent1"] - HP["ent0"]) * min(1.0, frac)
        ok, diag = ppo_update(net, ref_net, pk, lr=lr, ent=ent, hp=HP)
        if not ok:
            n_reject += 1
        rec = {k: (float(diag[k]) if isinstance(diag[k], (int, float, np.floating, np.integer)) else diag[k])
               for k in diag}
        rec.update(it=it + 1, phase="rl_pomo_v2_step",
                   batchJ=pk["batchJ"], batchH=pk["batchH"], batch_ot=pk["batch_ot"],
                   n_reject=n_reject, lr=float(lr))
        if it % 5 == 0 or not ok:
            log_fn(f"rlv2 it{it+1} batchJ={pk['batchJ']:.1f} H={pk['batchH']:.1f} "
                   f"gn={diag['gnorm']:.4f} ent={diag['ent']:.3f} kl_s={diag['kl_step']:.4f} "
                   f"kl_r={diag['kl_ref_post']:.4f} accpt={ok} rej={n_reject} "
                   f"frac_clip={diag.get('frac_clip', 0):.3f} sec={time.time()-t_rl:.0f}")
        with open(logp_path, "a") as f:
            f.write(json.dumps(rec, default=float) + "\n")
        hist.append(rec)
        it += 1
        if it % eval_every == 0 or time.time() - t_rl >= budget:
            ck = os.path.join(MOD, f"rl_s{seed}_it{it}{tag}.npz")
            L.save_net(net, ck)
            ev = dev_eval(pool, ck, dev_plans, dev_days, rule, mode=mode)
            J = mean_fn(ev, "J"); ot = mean_fn(ev, "ontime_h")
            gap = (J - freeze["J_n"]) / freeze["J_n"] * 100
            erec = dict(it=it, dev_J=J, dev_ot=ot, dev_cvar=mean_fn(ev, "cvar_h"),
                        dev_fails=mean_fn(ev, "fails"), dev_holds=mean_fn(ev, "n_hold"),
                        gap_vs_bestN=gap, sec=time.time() - t_rl, phase="rl_pomo_v2",
                        n_reject=n_reject, lr=lr)
            log_fn(json.dumps(erec))
            with open(logp_path, "a") as f:
                f.write(json.dumps(erec, default=float) + "\n")
            hist.append(erec)
            improved = (J < best - 1e-9) or (abs(J - best) <= 1e-9 and ot > best_ot)
            if improved:
                best, best_ot = J, ot
                L.save_net(net, best_path)
                log_fn("NEW BEST", J, "gap", gap, "ot", ot)
            # diverge guard: restore + lr decay once
            if J > init_J * HP["lr_decay_trigger"]:
                log_fn(f"DEV J {J:.2f} exceeds {HP['lr_decay_trigger']}x init {init_J:.2f}; restore best")
                net = L.load_net(best_path)
                net.reset_adam()
                if n_lr_decay == 0:
                    lr *= 0.5
                    n_lr_decay += 1
                    log_fn("lr decayed to", lr)
            if time.time() - t_rl >= budget:
                break
    return best_path, hist
