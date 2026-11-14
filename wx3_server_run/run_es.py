#!/usr/bin/env python3
"""WX3 main learner: trajectory-level Evolution Strategies (OpenAI-ES, antithetic, CRN) fine-tuning
of the RL policy network on the constrained scalarised objective

    F(theta) = mean_{(plan,day) in batch} [ J + lam_h * late_min_h + lam_c * cvar_h ]

* initial theta = pomo_v2 policy (or fresh / any PolicyNet ckpt)
* every candidate theta +/- sigma*eps_i is evaluated on the SAME batch of training (plan, day) pairs
  (common random numbers): the antithetic difference F(+)-F(-) is low variance
* fitness shaping: centred ranks of per-pair differences; Adam on the ES gradient; weight decay
* noise is regenerated from integer seeds in workers (no big arrays shipped)
* every --val-every iterations the centre theta is evaluated on a fixed VALIDATION pool of
  training-distribution days (NOT dev); best-val ckpt kept; dev is touched only by the final
  pre-registered selection (one dev evaluation per (seed, lam) candidate)
* checkpoint/resume: es_state_{tag}_s{seed}.npz written atomically each iteration
Greedy deterministic policy -> evaluation is a deterministic function of (theta, plan, day).
"""
from __future__ import annotations
import argparse, json, os, sys, time
from multiprocessing import Pool
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("WX_ROOT", ROOT)
sys.path.insert(0, ROOT)
from wx2 import evaljob as E, sim as S, const as C, inst as I, learn as L
from wx2.feat import features

KEYS = ("W1", "b1", "W2", "b2", "W3", "b3", "Wa", "ba")
ES_DAY0 = C.TRAIN_WX_MIN + 5_000_000      # disjoint from dev 6000s / tests 7000s, 8000s, 8100s
VAL_DAY0 = C.TRAIN_WX_MIN + 6_000_000


def flat(p):
    return np.concatenate([np.asarray(p[k], np.float64).ravel() for k in KEYS])


def unflat(v, shapes):
    out, o = {}, 0
    for k in KEYS:
        n = int(np.prod(shapes[k]))
        out[k] = v[o:o + n].reshape(shapes[k]); o += n
    return out


_W = {}


def _winit(theta_file):
    _W["theta_file"] = theta_file
    _W["mtime"] = None


def _theta():
    f = _W["theta_file"]
    mt = os.path.getmtime(f)
    if _W.get("mtime") != mt:
        z = np.load(f)
        _W["theta"] = z["theta"]; _W["shapes"] = {k: tuple(z["shape_" + k]) for k in KEYS}
        _W["sigma"] = float(z["sigma"]); _W["mtime"] = mt
    return _W["theta"], _W["shapes"], _W["sigma"]


def _noise(seed, n):
    return np.random.default_rng(int(seed)).standard_normal(n)


def run_day(params, path, sol, day):
    rec = E.materialize(path, sol, day, "storm")
    ins = E._ins(path)
    net = L.PolicyNet(np.random.default_rng(0)); net.load(params)
    pol = L.make_policy(net, greedy=True)
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"], P=C.P_MAIN)
    m = sim.run(pol, record_time=False)
    return {k: float(m[k]) for k in ("J", "cost", "mk", "ontime", "ontime_h", "fails", "cvar_h",
                                       "late_min_h", "late_min_n")}


def wjob(job):
    """job: (nseed, sign, path, sol, day). nseed<0 -> centre."""
    nseed, sign, path, sol, day = job
    th, shapes, sig = _theta()
    v = th if nseed < 0 else th + sign * sig * _noise(nseed, th.size)
    try:
        return run_day(unflat(v, shapes), path, sol, day)
    except Exception as e:  # pragma: no cover
        return {"error": repr(e)}


LAM_M = [0.0]


def obj(m, lh, lc):
    return m["J"] + lh * m["late_min_h"] + lc * m["cvar_h"] + LAM_M[0] * m["mk"]


def centred_ranks(x):
    r = np.empty(len(x)); r[np.argsort(x)] = np.arange(len(x))
    return r / (len(x) - 1) - 0.5


def atomic_savez(path, **kw):
    tmp = path + ".tmp.npz"
    np.savez(tmp, **kw); os.replace(tmp, path)


def log(msg, f=None):
    s = time.strftime("%H:%M:%S") + " " + msg
    print(s, flush=True)
    if f:
        with open(f, "a") as fh:
            fh.write(s + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--init", default=os.path.join(ROOT, "models", "rl_s0_best_pomo_v2.npz"))
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--pop", type=int, default=16, help="antithetic pairs per iteration")
    ap.add_argument("--batch", type=int, default=16, help="(plan,day) pairs per iteration (CRN)")
    ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--wd", type=float, default=0.0)
    ap.add_argument("--lam_h", type=float, default=0.0)
    ap.add_argument("--lam_c", type=float, default=0.0)
    ap.add_argument("--lam_m", type=float, default=0.0, help="extra weight on makespan (min)")
    ap.add_argument("--pool-days", type=int, default=2000, help="training (plan,day) pool size")
    ap.add_argument("--val-n", type=int, default=64)
    ap.add_argument("--val-every", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tag", default="es")
    ap.add_argument("--models", default=os.path.join(ROOT, "models3"))
    ap.add_argument("--log", default=None)
    ap.add_argument("--max-minutes", type=float, default=0, help="stop cleanly after this wall time")
    a = ap.parse_args()
    os.makedirs(a.models, exist_ok=True)
    LAM_M[0] = a.lam_m
    name = f"{a.tag}_s{a.seed}_lh{a.lam_h:g}_lc{a.lam_c:g}" + (f"_lm{a.lam_m:g}" if a.lam_m else "")
    state_f = os.path.join(a.models, f"es_state_{name}.npz")
    theta_f = os.path.join(a.models, f"es_theta_{name}.npz")
    best_f = os.path.join(a.models, f"es_best_{name}.npz")
    hist_f = os.path.join(a.models, f"es_hist_{name}.jsonl")
    logf = a.log
    train = I.load_plans("train_ours")
    rng0 = np.random.default_rng(1000 + a.seed)
    # fixed pools (seed-dependent pool; validation pool shared across seeds for comparability)
    pool = [(train[int(rng0.integers(len(train)))], ES_DAY0 + a.seed * 100_000 + j) for j in range(a.pool_days)]
    rv = np.random.default_rng(777)
    val = [(train[int(rv.integers(len(train)))], VAL_DAY0 + j) for j in range(a.val_n)]

    net0 = L.load_net(a.init)
    p0 = net0.params(); shapes = {k: p0[k].shape for k in KEYS}
    if os.path.exists(state_f):
        z = np.load(state_f)
        theta, m1, m2, it0 = z["theta"], z["m1"], z["m2"], int(z["it"])
        best_val = float(z["best_val"])
        log(f"[{name}] resume at it={it0} best_val={best_val:.2f}", logf)
    else:
        theta = flat(p0); m1 = np.zeros_like(theta); m2 = np.zeros_like(theta); it0 = 0; best_val = np.inf
    n = theta.size

    def write_theta(th):
        atomic_savez(theta_f, theta=th, sigma=a.sigma, **{"shape_" + k: np.array(shapes[k]) for k in KEYS})

    def save_ckpt(th, path):
        net = L.PolicyNet(np.random.default_rng(0)); net.load(unflat(th, shapes)); L.save_net(net, path + ".tmp.npz")
        os.replace(path + ".tmp.npz", path)

    write_theta(theta)
    t_start = time.time()
    with Pool(a.workers, initializer=_winit, initargs=(theta_f,), maxtasksperchild=400) as pool_p:
        def eval_centre(pairs):
            rows = pool_p.map(wjob, [(-1, 0, r["path"], r["solution"], d) for r, d in pairs], chunksize=1)
            rows = [r for r in rows if "error" not in r]
            return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} | {
                "F": float(np.mean([obj(r, a.lam_h, a.lam_c) for r in rows]))}
        if it0 == 0 and not np.isfinite(best_val):
            v = eval_centre(val); best_val = v["F"]; save_ckpt(theta, best_f)
            with open(hist_f, "a") as fh:
                fh.write(json.dumps(dict(it=0, val=v, best=True)) + "\n")
            log(f"[{name}] it0 val F={v['F']:.2f} J={v['J']:.2f} onh={v['ontime_h']:.4f} cvh={v['cvar_h']:.2f}", logf)
        for it in range(it0, a.iters):
            if a.max_minutes and (time.time() - t_start) / 60 > a.max_minutes:
                log(f"[{name}] max-minutes reached at it={it}; state saved", logf); break
            t0 = time.time()
            rit = np.random.default_rng([a.seed, it, 99])
            bidx = rit.choice(len(pool), size=a.batch, replace=False)
            seeds = rit.integers(1, 2 ** 31 - 1, size=a.pop)
            jobs = []
            for s in seeds:
                for sg in (1, -1):
                    for b in bidx:
                        r, d = pool[b]; jobs.append((int(s), sg, r["path"], r["solution"], d))
            rows = pool_p.map(wjob, jobs, chunksize=2)
            Fv = np.array([obj(r, a.lam_h, a.lam_c) if "error" not in r else np.nan for r in rows]).reshape(a.pop, 2, a.batch)
            Fv = np.where(np.isnan(Fv), np.nanmean(Fv), Fv)
            # per-day normalisation (days differ by orders of magnitude): divide by mean |F| of the day
            scale = np.abs(Fv).mean(axis=(0, 1)) + 1.0
            Fn = (Fv / scale).mean(axis=2)      # (pop, 2)
            diff = Fn[:, 0] - Fn[:, 1]          # + minus -   (we MINIMISE)
            w = centred_ranks(np.concatenate([Fn[:, 0], Fn[:, 1]]))
            wp, wm = w[:a.pop], w[a.pop:]
            g = np.zeros(n)
            for s, c in zip(seeds, wp - wm):
                g += c * _noise(int(s), n)
            g /= (a.pop * a.sigma)
            g += a.wd * theta
            # Adam (descent)
            t = it + 1
            m1 = 0.9 * m1 + 0.1 * g; m2 = 0.999 * m2 + 0.001 * g * g
            theta = theta - a.lr * (m1 / (1 - 0.9 ** t)) / (np.sqrt(m2 / (1 - 0.999 ** t)) + 1e-8)
            write_theta(theta)
            rec = dict(it=t, F_mean=float(np.mean(Fv)), dmean=float(np.mean(np.abs(diff))),
                       sec=round(time.time() - t0, 1))
            if t % a.val_every == 0 or t == a.iters:
                v = eval_centre(val); rec["val"] = v
                if v["F"] < best_val:
                    best_val = v["F"]; save_ckpt(theta, best_f); rec["best"] = True
                log(f"[{name}] it{t} val F={v['F']:.2f} J={v['J']:.2f} cost={v['cost']:.1f} mk={v['mk']:.1f} "
                    f"onh={v['ontime_h']:.4f} fails={v['fails']:.3f} cvh={v['cvar_h']:.2f} best={best_val:.2f} ({rec['sec']}s)", logf)
            with open(hist_f, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            atomic_savez(state_f, theta=theta, m1=m1, m2=m2, it=t, best_val=best_val)
    log(f"[{name}] done; best ckpt {best_f}", logf)


if __name__ == "__main__":
    main()
