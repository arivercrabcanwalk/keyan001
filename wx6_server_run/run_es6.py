"""Stage E (RL6): constrained OpenAI-ES fine-tuning of the distilled token-scoring policy (PREREG_v6 sec. 5).

  minimise  E[J5]          s.t.  E[V] = 0  (strict completion violations; lambda_V dual ascent, floor 1000)
                                 E[OT_RL6] <= (1 - delta) * E[OT_REF]  on the SAME (plan, day) pairs
  F = J5 + lambda_V * V + lambda_OT * OT ;  lambda_OT by PID-Lagrangian (Stooke et al. 2020) on the RELATIVE
  residual e = (OT - (1-delta) OT_REF) / OT_REF  (scale-free, fixes the v5/e2e duals that never converged).
Antithetic sampling, common random numbers (all candidates on the same batch of days), centred ranks, Adam, fixed
iteration count (equal compute across seeds/variants; a run is DONE only at --iters). Checkpoint every iteration.
Greedy deterministic policy => evaluation is a deterministic function of (theta, plan, day).
Validation pool (training distribution, never dev/test) every --val-every iterations; candidates kept for the
preregistered dev selection: es_best (val score) and es_final.
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("WX_ROOT", ROOT)
sys.path.insert(0, ROOT)
from wx2 import evaljob as E, sim as S
from v6 import net6 as N6, feat6 as F6, registry as RG
from v6.common import load_plans

ES_DAY0 = 3_500_000
VAL_DAY0 = 3_900_000
_W = {}


def _winit(theta_file, ablate, shield):
    _W["theta_file"] = theta_file; _W["ablate"] = ablate; _W["shield"] = shield; _W["mtime"] = None


def _theta():
    mt = os.path.getmtime(_W["theta_file"])
    if _W.get("mtime") != mt:
        z = np.load(_W["theta_file"]); _W["theta"] = z["theta"]; _W["sigma"] = float(z["sigma"]); _W["mtime"] = mt
        _W["net"] = N6.Net6(0); _W["net"].fmask = F6.ablation_mask(_W["ablate"])
    return _W["theta"], _W["sigma"], _W["net"]


def _noise(seed, n):
    return np.random.default_rng(seed).standard_normal(n)


def run_day(theta, path, sol, day):
    rec = E.materialize(path, sol, day, "storm")
    ins = E._ins(path)
    _, _, net = _theta(); net.set_flat(theta)
    pol = N6.make_policy(net, shield=_W["shield"], greedy=True)
    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"])
    m = sim.run(pol, record_time=False)
    return dict(J=m["J"], ot=m["ot_min"], cost=m["cost"], fails=m["fails"], late_h=m["late_min_h"], late_n=m["late_min_n"],
                complete=m["complete_strict"], viol=float(m["unfinished"] + max(0, m["unserved"] - m["n_unservable_all"])))


def run_ref(spec, extra, path, sol, day):
    rec = E.materialize(path, sol, day, "storm")
    sim = S.Sim(E._ins(path), rec["sol"], rec["wx"], rec["reqs"])
    m = sim.run(RG.get_policy(spec, extra), record_time=False)
    return dict(ot=m["ot_min"], J=m["J"])


def wjob(job):
    kind, s, sg, path, sol, day = job
    try:
        if kind == "ref":
            return run_ref(s, sg, path, sol, day)
        th, sig, _ = _theta()
        v = th if s < 0 else th + sg * sig * _noise(s, th.size)
        return run_day(v, path, sol, day)
    except Exception as e:  # pragma: no cover
        import traceback
        return {"error": repr(e), "tb": traceback.format_exc()[-500:]}


def centred_ranks(x):
    r = np.empty(len(x)); r[np.argsort(x)] = np.arange(len(x))
    return r / (len(x) - 1) - 0.5


def atomic_savez(path, **kw):
    tmp = path + ".tmp.npz"; np.savez(tmp, **kw); os.replace(tmp, path)


def log(msg, f=None):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    if f:
        with open(f, "a") as fh:
            fh.write(line + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--init", required=True)
    ap.add_argument("--plans", required=True, help="training plan jsonl")
    ap.add_argument("--name", required=True); ap.add_argument("--models", default=os.path.join(ROOT, "models6"))
    ap.add_argument("--iters", type=int, default=250); ap.add_argument("--pop", type=int, default=20)
    ap.add_argument("--batch", type=int, default=16); ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--lr", type=float, default=0.005); ap.add_argument("--wd", type=float, default=0.0)
    ap.add_argument("--pool-days", type=int, default=3000); ap.add_argument("--val-n", type=int, default=96)
    ap.add_argument("--val-every", type=int, default=10); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ablate", default="none"); ap.add_argument("--shield", type=int, default=1)
    ap.add_argument("--ot-ref", default="", help="reference policy name for the relative OT constraint ('' = none)")
    ap.add_argument("--ot-ref-extra", default="{}")
    ap.add_argument("--delta", type=float, default=0.10, help="required relative OT reduction vs the reference")
    ap.add_argument("--pid", default="2.0:0.2", help="kp:ki of the PID-Lagrangian on the relative residual")
    ap.add_argument("--lam-v0", type=float, default=1000.0); ap.add_argument("--dual-lr-v", type=float, default=200.0)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    os.makedirs(a.models, exist_ok=True)
    name = a.name
    state_f = os.path.join(a.models, f"es_state_{name}.npz"); theta_f = os.path.join(a.models, f"es_theta_{name}.npz")
    best_f = os.path.join(a.models, f"es_best_{name}.npz"); hist_f = os.path.join(a.models, f"es_hist_{name}.jsonl")
    train = load_plans(a.plans)
    rng0 = np.random.default_rng(1000 + a.seed)
    pool = [(train[int(rng0.integers(len(train)))], ES_DAY0 + a.seed * 100_000 + j) for j in range(a.pool_days)]
    rv = np.random.default_rng(777)
    val = [(train[int(rv.integers(len(train)))], VAL_DAY0 + j) for j in range(a.val_n)]
    net0 = N6.load(a.init)
    tmpl = N6.Net6(0); tmpl.p = {k: v.copy() for k, v in net0.p.items()}; tmpl.fmask = F6.ablation_mask(a.ablate)
    ref_extra = json.loads(a.ot_ref_extra)
    lam = dict(v=a.lam_v0, ot=0.0, I=0.0, ema=0.0)
    if os.path.exists(state_f):
        z = np.load(state_f)
        theta, m1, m2, it0, best_val = z["theta"], z["m1"], z["m2"], int(z["it"]), float(z["best_val"])
        lam = json.loads(str(z["lam"]))
        log(f"[{name}] resume at it={it0} best_val={best_val:.2f}", a.log)
    else:
        theta = tmpl.flat(); m1 = np.zeros_like(theta); m2 = np.zeros_like(theta); it0 = 0; best_val = np.inf
    n = theta.size
    kp, ki = (float(x) for x in a.pid.split(":"))
    REF = {}
    ref_f = os.path.join(a.models, f"es_ref_{name}.json")
    if os.path.exists(ref_f):
        REF.update({int(k): v for k, v in json.load(open(ref_f)).items()})

    def save_ckpt(th, path, **meta):
        net = N6.Net6(0); net.set_flat(th); net.fmask = F6.ablation_mask(a.ablate)
        N6.save(net, path, stage="es", name=name, seed=a.seed, ablate=a.ablate, shield=a.shield, **meta)

    atomic_savez(theta_f, theta=theta, sigma=a.sigma)
    t_start = time.time()
    with Pool(a.workers, initializer=_winit, initargs=(theta_f, a.ablate, bool(a.shield)), maxtasksperchild=300) as P:
        VREF = {}

        def ref_of(pairs, keys):
            need = [k for k in keys if k not in REF]
            if need and a.ot_ref:
                rr = P.map(wjob, [("ref", a.ot_ref, ref_extra, pairs[k][0]["path"], pairs[k][0]["solution"], pairs[k][1]) for k in need], chunksize=1)
                for k, r in zip(need, rr):
                    REF[k] = float(r.get("ot", 0.0))
                json.dump(REF, open(ref_f, "w"))
            return float(np.mean([REF.get(k, 0.0) for k in keys])) if a.ot_ref else 0.0

        def eval_centre(pairs):
            rows = [r for r in P.map(wjob, [("pol", -1, 0, r["path"], r["solution"], d) for r, d in pairs], chunksize=1) if "error" not in r]
            return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}

        def val_ref():
            if a.ot_ref and "ot" not in VREF:
                rr = P.map(wjob, [("ref", a.ot_ref, ref_extra, r["path"], r["solution"], d) for r, d in val], chunksize=1)
                VREF["ot"] = float(np.mean([x.get("ot", 0.0) for x in rr])); VREF["J"] = float(np.mean([x.get("J", 0.0) for x in rr]))
            return VREF.get("ot", 0.0)

        def vscore(v):
            return v["J"] + (5.0 * max(0.0, v["ot"] - (1 - a.delta) * v["ot_ref"]) if a.ot_ref else 0.0)

        if it0 == 0 and not np.isfinite(best_val):
            v = eval_centre(val); v["ot_ref"] = val_ref(); v["score"] = vscore(v)
            best_val = v["score"] if v["complete"] >= 1 - 1e-9 else np.inf; save_ckpt(theta, best_f, it=0)
            with open(hist_f, "a") as fh:
                fh.write(json.dumps(dict(it=0, val=v, best=True, ref_J=VREF.get("J"))) + "\n")
            log(f"[{name}] it0 val J5={v['J']:.1f} ot={v['ot']:.1f} ref_ot={v['ot_ref']:.1f} ref_J={VREF.get('J', 0):.1f} compl={v['complete']:.3f}", a.log)
        for it in range(it0, a.iters):
            t0 = time.time()
            rit = np.random.default_rng([a.seed, it, 99])
            bidx = [int(b) for b in rit.choice(len(pool), size=a.batch, replace=False)]
            seeds = rit.integers(1, 2 ** 31 - 1, size=a.pop)
            jobs = [("pol", int(s), sg, pool[b][0]["path"], pool[b][0]["solution"], pool[b][1]) for s in seeds for sg in (1, -1) for b in bidx]
            ref_mean = ref_of(pool, bidx)
            rows = P.map(wjob, jobs, chunksize=2)
            def f(r):
                return r["J"] + lam["v"] * r["viol"] + lam["ot"] * r["ot"]
            Fv = np.array([f(r) if "error" not in r else np.nan for r in rows]).reshape(a.pop, 2, a.batch)
            ok = [r for r in rows if "error" not in r]
            viol = float(np.mean([r["viol"] for r in ok])); otm = float(np.mean([r["ot"] for r in ok]))
            lam["v"] = max(a.lam_v0, lam["v"] + a.dual_lr_v * viol)
            if a.ot_ref:
                e = float(np.clip((otm - (1 - a.delta) * ref_mean) / max(ref_mean, 5.0), -1.0, 2.0))
                lam["ema"] = 0.7 * lam["ema"] + 0.3 * e
                lam["I"] = float(np.clip(lam["I"] + e, 0.0, 50.0))
                lam["ot"] = max(0.0, kp * lam["ema"] + ki * lam["I"])
            Fv = np.where(np.isnan(Fv), np.nanmean(Fv), Fv)
            scale = np.abs(Fv).mean(axis=(0, 1)) + 1.0
            Fn = (Fv / scale).mean(axis=2)
            w = centred_ranks(np.concatenate([Fn[:, 0], Fn[:, 1]]))
            g = np.zeros(n)
            for s, c in zip(seeds, w[:a.pop] - w[a.pop:]):
                g += c * _noise(int(s), n)
            g = g / (a.pop * a.sigma) + a.wd * theta
            t = it + 1
            m1 = 0.9 * m1 + 0.1 * g; m2 = 0.999 * m2 + 0.001 * g * g
            theta = theta - a.lr * (m1 / (1 - 0.9 ** t)) / (np.sqrt(m2 / (1 - 0.999 ** t)) + 1e-8)
            atomic_savez(theta_f, theta=theta, sigma=a.sigma)
            rec = dict(it=t, sec=round(time.time() - t0, 1), J5=float(np.mean([r["J"] for r in ok])), ot=otm, ot_ref=ref_mean,
                       viol=viol, lam_v=lam["v"], lam_ot=lam["ot"], nerr=len(rows) - len(ok))
            if t % a.val_every == 0 or t == a.iters:
                v = eval_centre(val); v["ot_ref"] = val_ref(); v["score"] = vscore(v); rec["val"] = v
                if v["score"] < best_val and v["complete"] >= 1 - 1e-9:
                    best_val = v["score"]; save_ckpt(theta, best_f, it=t); rec["best"] = True
                log(f"[{name}] it{t} val J5={v['J']:.1f} ot={v['ot']:.1f} ref_ot={v['ot_ref']:.1f} lamOT={lam['ot']:.3f} fails={v['fails']:.3f} "
                    f"compl={v['complete']:.3f} best={best_val:.1f} ({rec['sec']}s/it)", a.log)
            with open(hist_f, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            atomic_savez(state_f, theta=theta, m1=m1, m2=m2, it=t, best_val=best_val, lam=json.dumps(lam))
    z = np.load(state_f)
    if int(z["it"]) >= a.iters:
        save_ckpt(theta, os.path.join(a.models, f"es_final_{name}.npz"), it=int(z["it"]))
        with open(os.path.join(a.models, f"DONE_{name}"), "w") as fh:
            fh.write(json.dumps(dict(iters=int(z["it"]), best_val=best_val, wall_s=time.time() - t_start)) + "\n")
    log(f"[{name}] done it={int(z['it'])}/{a.iters}", a.log)


if __name__ == "__main__":
    main()
