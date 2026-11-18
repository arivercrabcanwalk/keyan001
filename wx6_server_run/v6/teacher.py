"""Stage T (RL6): rollout-teacher data for approximate policy iteration (API) / DAgger-style distillation.

For a (plan, training day) the day is simulated with a ROLL-IN policy. At each decision with >= 2 legal actions
(after the optional shift shield) and with probability p_label, the teacher estimates the action values
     Q(s,a) = E_future[ J5(day | a now, base policy afterwards) + lam_ot * OT ]
with M fair twin-weather futures (wx2/twin.sample_future_fair: only information observable at time t; common random
numbers across actions). The sample (tokens, mask, Q) is stored. The executed action is the teacher's argmin with
probability 1 - beta, else the roll-in policy's action (beta = 0 in round 0, 0.5 in round 1 = DAgger mixing).
Rollout-based policy improvement (Bertsekas 2019/2022: "rollout + approximation in policy space"; Silver et al.
expert iteration) guarantees, for exact Q, a policy no worse than the base; the student net distils it to 1 ms.
Output: one compressed npz shard per job in --outdir (resumable)."""
import os, sys, json, time, argparse, hashlib, traceback
import numpy as np
from multiprocessing import Pool
ROOT = os.environ.get("WX_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from wx2 import sim as S, evaljob as EJ, twin as TW, policies as PP
from wx2.sim import HOLD, N_ACT
from v6 import feat6 as F6, shield as SH, registry as RG
from v6.common import parse_days, load_plans


def rollout_q(sim, i, legal, base, M, rng, lam_ot):
    Q = np.zeros((M, len(legal))); OT = np.zeros_like(Q)
    for m in range(M):
        tw, fut = TW.sample_future_fair(sim, rng)
        for k, a in enumerate(legal):
            s = sim.clone(); s.wx = tw
            PP.inject_future_safe(s, fut)
            s = PP._apply_and_run(s, i, a, base)
            mm = s.metrics()
            Q[m, k] = mm["J"] + lam_ot * mm["ot_min"]; OT[m, k] = mm["ot_min"]
    return Q.mean(0), Q.std(0) / np.sqrt(M), OT.mean(0)


def run_job(job):
    rec = EJ.materialize(job["path"], job["sol"], job["day"], "storm")
    ins = EJ._ins(job["path"])
    shield = job["shield"]
    base = RG.get_policy(job["base"], job.get("base_extra"))
    if shield:
        base = SH.shielded(base)
    rollin = RG.get_policy(job["rollin"], job.get("rollin_extra")) if job.get("rollin") else base
    rng = np.random.default_rng(int(hashlib.sha1(f"{job['path']}|{job['day']}|{job['round']}|{job['seed']}".encode()).hexdigest()[:12], 16))
    out = dict(X=[], mask=[], Q=[], Qse=[], OT=[], t=[])

    def pol(sim, i, mask, cands, info):
        on = False
        if shield and mask[HOLD] and SH.violates(sim, i, info):
            mask = mask.copy(); mask[HOLD] = False; on = True
        legal = [a for a in range(N_ACT) if mask[a]]
        if len(legal) >= 2 and rng.random() < job["p_label"]:
            g, A = F6.features(sim, i, mask, cands, info, shield_on=on)
            q, se, ot = rollout_q(sim, i, legal, base, job["M"], rng, job["lam_ot"])
            Qf = np.full(N_ACT, np.nan); Qf[legal] = q
            Sf = np.full(N_ACT, np.nan); Sf[legal] = se
            Of = np.full(N_ACT, np.nan); Of[legal] = ot
            out["X"].append(F6.tokens(g, A).astype(np.float16)); out["mask"].append(mask.copy())
            out["Q"].append(Qf.astype(np.float32)); out["Qse"].append(Sf.astype(np.float32)); out["OT"].append(Of.astype(np.float32))
            out["t"].append(sim.t)
            if rng.random() >= job["beta"]:
                return legal[int(np.argmin(q))]
        a = rollin(sim, i, mask, cands, info)
        if a is None or a < 0 or a >= N_ACT or not mask[a]:
            a = legal[0] if legal else HOLD
        return a

    sim = S.Sim(ins, rec["sol"], rec["wx"], rec["reqs"])
    m = sim.run(pol, record_time=False)
    return out, dict(J=m["J"], ot=m["ot_min"], fails=m["fails"], complete_strict=m["complete_strict"], n=len(out["Q"]))


def _w(job):
    t0 = time.time()
    try:
        out, info = run_job(job)
        n = len(out["Q"])
        tmp = job["file"] + ".tmp.npz"
        np.savez_compressed(tmp, X=np.array(out["X"]).reshape(n, N_ACT, F6.NTOK) if n else np.zeros((0, N_ACT, F6.NTOK), np.float16),
                            mask=np.array(out["mask"]).reshape(n, N_ACT) if n else np.zeros((0, N_ACT), bool),
                            Q=np.array(out["Q"]).reshape(n, N_ACT) if n else np.zeros((0, N_ACT), np.float32),
                            Qse=np.array(out["Qse"]).reshape(n, N_ACT) if n else np.zeros((0, N_ACT), np.float32),
                            OT=np.array(out["OT"]).reshape(n, N_ACT) if n else np.zeros((0, N_ACT), np.float32),
                            t=np.array(out["t"], dtype=np.float32),
                            info=json.dumps(dict(info, path=job["path"], day=job["day"], round=job["round"])))
        os.replace(tmp, job["file"])
        return dict(ok=1, sec=time.time() - t0, **info)
    except Exception as e:
        return dict(ok=0, err=repr(e), tb=traceback.format_exc()[-600:], path=job["path"], day=job["day"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plans", required=True, help="plan jsonl (training maps, covering plans)")
    ap.add_argument("--days", required=True); ap.add_argument("--outdir", required=True)
    ap.add_argument("--round", type=int, default=0); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--base", required=True, help="policy name for the rollout continuation (e.g. RL5 / RL6:<npz>)")
    ap.add_argument("--base-extra", default="{}")
    ap.add_argument("--rollin", default="", help="roll-in policy (default = base)")
    ap.add_argument("--rollin-extra", default="{}")
    ap.add_argument("--M", type=int, default=8); ap.add_argument("--p-label", type=float, default=0.5)
    ap.add_argument("--beta", type=float, default=0.0); ap.add_argument("--lam-ot", type=float, default=1.0)
    ap.add_argument("--shield", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--max-jobs", type=int, default=0)
    ap.add_argument("--budget-h", type=float, default=0.0, help="stop submitting new jobs after this many hours")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    plans = load_plans(a.plans); days = parse_days(a.days)
    rng = np.random.default_rng(1000 + a.round)
    pairs = [(p, d) for d in days for p in plans]
    order = rng.permutation(len(pairs))
    jobs = []
    for k in order:
        p, d = pairs[k]
        f = os.path.join(a.outdir, f"r{a.round}_{os.path.basename(p['path'])[:-4]}_{d}.npz")
        if os.path.exists(f):
            continue
        jobs.append(dict(path=p["path"], sol=p["solution"], day=d, round=a.round, seed=a.seed, base=a.base,
                         base_extra=json.loads(a.base_extra), rollin=a.rollin, rollin_extra=json.loads(a.rollin_extra),
                         M=a.M, p_label=a.p_label, beta=a.beta, lam_ot=a.lam_ot, shield=a.shield, file=f))
    if a.max_jobs:
        jobs = jobs[:a.max_jobs]
    print(f"[teacher] round {a.round}: {len(jobs)} jobs todo -> {a.outdir}", flush=True)
    t0 = time.time(); n = 0; nl = 0; nerr = 0
    with Pool(a.workers, maxtasksperchild=20) as pool:
        it = pool.imap_unordered(_w, jobs, chunksize=1)
        for r in it:
            n += 1
            if r["ok"]:
                nl += r["n"]
            else:
                nerr += 1; print("[teacher] ERR", r, flush=True)
            if n % 10 == 0 or n == len(jobs):
                print(f"[teacher] {n}/{len(jobs)} labels={nl} err={nerr} {time.time()-t0:.0f}s", flush=True)
            if a.budget_h and time.time() - t0 > a.budget_h * 3600:
                print("[teacher] budget reached: terminating remaining jobs (shards written so far are kept)", flush=True)
                pool.terminate(); break
    return 0 if nerr <= max(2, 0.02 * max(n, 1)) else 2


if __name__ == "__main__":
    sys.exit(main())
