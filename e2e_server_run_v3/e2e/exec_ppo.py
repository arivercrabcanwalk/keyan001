"""Train pi_exec with PPO (clipped, GAE(gamma=1, lambda=0.95), value clipping, entropy schedule, KL early stop),
large parallel rollout collection on CPU workers (one sim day per episode, policy in numpy), learner on GPU/CPU.
Reward = telescoped -J5 increments between consecutive fleet decisions (sum over the day = -J5 exactly; /100).
Constraint (Lagrangian, as v5): E[ot_ours - ot_N6] <= 0 per (plan, day); dual ascent lr_dual on the multiplier;
terminal reward additionally -lambda*(ot - ot_N6)/100. Warm start: RL5 (v5 ES) weights; REROUTE starts rare.
Plans for training = OUR plans on train maps (pi_site + pi_route), never TSALNS/ALNS plans."""
import os, sys, json, time, argparse
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, seed_all, JsonlLog, progress, atomic_save, read_instance
from e2e.exec_policy import ExecNet, NACT, NIN, make_exec_policy, sim_j_running
from e2e import dyn_eval as D


def collect(job):
    """Run one (plan, day) episode with sampling policy; return transitions + episode metrics + N6 reference ot."""
    try:
        torch.set_num_threads(1)
        ins = read_instance(os.path.join(ROOT, job["path"]))
        sol = job["sol"]
        from wx2 import sim as S, planadapt as PA
        wx, reqs, meta = S.make_day(ins, job["day"])
        from e2e import rl_adapt as RA
        asol, _, _ = RA.adapt(ins, sol, wx, job.get("adapt"))
        rec = []
        pol = make_exec_policy(job["P"], router_path=job["router"], greedy=False,
                               rng=np.random.default_rng(job["day"]), record=rec, allow_reroute=job["reroute"])
        sim = S.Sim(ins, asol, wx, reqs)
        m = sim.run(pol)
        ref = job.get("ot_ref")
        if ref is None:
            simb = S.Sim(ins, asol, wx, reqs)
            ref = simb.run(D.get_policy("N6_90_0.25"))["ot_min"]
        J_runs = [r[5] for r in rec] + [m["J"]]
        X = np.stack([r[0] for r in rec]) if rec else np.zeros((0, NIN), np.float32)
        Mk = np.stack([r[1] for r in rec]) if rec else np.zeros((0, NACT), bool)
        A = np.array([r[2] for r in rec], dtype=np.int64); LP = np.array([r[3] for r in rec]); V = np.array([r[4] for r in rec])
        Rw = -np.diff(np.array(J_runs)) / 100.0
        return dict(X=X, M=Mk, A=A, LP=LP, V=V, R=Rw, J=m["J"], ot=m["ot_min"], ot_ref=ref, fails=m["fails"],
                    complete=m["complete"], nrr=int(getattr(sim, "n_reroute", 0)), cost=m["cost"])
    except Exception as e:
        import traceback
        return dict(error=repr(e), tb=traceback.format_exc()[-1200:])


def gae(R, V, lam=0.95):
    T = len(R); adv = np.zeros(T); last = 0.0
    for t in range(T - 1, -1, -1):
        nv = V[t + 1] if t + 1 < T else 0.0
        delta = R[t] + nv - V[t]
        last = delta + lam * last; adv[t] = last
    return adv, adv + V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--plans", required=True, help="plan jsonl (our plans on train maps)")
    ap.add_argument("--router", required=True)
    ap.add_argument("--init_rl5", default=os.path.join(ROOT, "models_init", "es_best_p5r_s0.npz"))
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--hours", type=float, default=8.0)
    ap.add_argument("--episodes", type=int, default=160)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--mb", type=int, default=4096)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent0", type=float, default=0.01)
    ap.add_argument("--ent1", type=float, default=0.001)
    ap.add_argument("--kl_stop", type=float, default=0.03)
    ap.add_argument("--lr_dual", type=float, default=0.005)
    ap.add_argument("--vf_warm", type=int, default=5, help="first iterations: value-only (critic warm-up)")
    ap.add_argument("--reroute", type=int, default=1)
    ap.add_argument("--dev_plans", default="")
    ap.add_argument("--dev_days", default="16000-16009")
    ap.add_argument("--val_every", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--adapt", default=None, help="morning plan adaptation used in training/validation (must match test)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = device(); seed_all(a.seed)
    net = ExecNet().to(dev)
    if a.init_rl5 and os.path.exists(a.init_rl5):
        net.load_rl5(a.init_rl5)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    st = dict(it=0, lam=0.0, elapsed=0.0, best=None, day=4_000_000 + 100_000 * a.seed)
    last = os.path.join(a.out, "last.pt")
    if os.path.exists(last):
        ck = torch.load(last, map_location=dev, weights_only=False)
        net.load_state_dict(ck["sd"]); opt.load_state_dict(ck["opt"]); st = ck["state"]
        print(f"[exec_ppo] resumed it={st['it']}", flush=True)
    plans = [json.loads(l) for l in open(a.plans)]
    if not plans: sys.exit(f"empty plan file {a.plans}")
    devplans = [json.loads(l) for l in open(a.dev_plans)] if a.dev_plans else []
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    rng = np.random.default_rng(a.seed + st["it"])
    from multiprocessing import get_context
    pool = get_context("spawn").Pool(a.workers, maxtasksperchild=100)
    t_start = time.time() - st["elapsed"]
    rpath = os.path.relpath(a.router, ROOT) if os.path.isabs(a.router) else a.router
    while st["it"] < a.iters and st["elapsed"] < a.hours * 3600:
        P = net.numpy_params()
        jobs = []
        for k in range(a.episodes):
            pl = plans[rng.integers(len(plans))]
            jobs.append(dict(path=pl["path"], sol=pl["solution"], day=st["day"] + k, P=P, router=os.path.join(ROOT, rpath), reroute=bool(a.reroute), adapt=a.adapt))
        st["day"] += a.episodes
        res = [r for r in pool.map(collect, jobs, chunksize=1)]
        err = [r for r in res if "error" in r]; res = [r for r in res if "error" not in r and len(r["A"])]
        if err:
            print("[exec_ppo] worker errors:", len(err), err[0]["tb"], flush=True)
        if not res:
            raise RuntimeError("no episodes collected")
        # terminal Lagrangian term
        Xs, Ms, As, LPs, ADV, RET, Vs = [], [], [], [], [], [], []
        for r in res:
            R = r["R"].copy(); R[-1] -= st["lam"] * (r["ot"] - r["ot_ref"]) / 100.0
            adv, ret = gae(R, r["V"])
            Xs.append(r["X"]); Ms.append(r["M"]); As.append(r["A"]); LPs.append(r["LP"]); ADV.append(adv); RET.append(ret); Vs.append(r["V"])
        X = torch.as_tensor(np.concatenate(Xs), dtype=torch.float32, device=dev)
        Mk = torch.as_tensor(np.concatenate(Ms), device=dev); A = torch.as_tensor(np.concatenate(As), device=dev)
        LP = torch.as_tensor(np.concatenate(LPs), dtype=torch.float32, device=dev)
        ADVt = torch.as_tensor(np.concatenate(ADV), dtype=torch.float32, device=dev)
        RETt = torch.as_tensor(np.concatenate(RET), dtype=torch.float32, device=dev)
        V0 = torch.as_tensor(np.concatenate(Vs), dtype=torch.float32, device=dev)
        ADVt = (ADVt - ADVt.mean()) / ADVt.std().clamp(min=1e-6)
        frac = min(1.0, st["it"] / max(1, a.iters)); ent_c = a.ent0 + (a.ent1 - a.ent0) * frac
        Nn = len(A); kl_v = 0.0; stop = False
        for ep in range(a.epochs):
            perm = torch.randperm(Nn, device=dev)
            for s0 in range(0, Nn, a.mb):
                idx = perm[s0:s0 + a.mb]
                lg, v = net(X[idx], Mk[idx])
                lp_all = torch.log_softmax(lg, -1); lp = lp_all.gather(1, A[idx][:, None]).squeeze(1)
                ratio = torch.exp(lp - LP[idx])
                pg = -torch.min(ratio * ADVt[idx], ratio.clamp(1 - a.clip, 1 + a.clip) * ADVt[idx]).mean()
                vl = torch.nn.functional.smooth_l1_loss(v, RETt[idx])
                ent = -(lp_all.exp() * lp_all.clamp(min=-1e4)).sum(-1).mean()
                warm = st["it"] < a.vf_warm
                loss = (0.0 if warm else 1.0) * (pg - ent_c * ent) + 0.5 * vl
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
                with torch.no_grad():
                    kl_v = float((LP[idx] - lp).mean())
                if not warm and kl_v > a.kl_stop:
                    stop = True; break
            if stop:
                break
        gap_ot = float(np.mean([r["ot"] - r["ot_ref"] for r in res]))
        st["lam"] = max(0.0, st["lam"] + a.lr_dual * gap_ot)
        st["it"] += 1; st["elapsed"] = time.time() - t_start
        rec = dict(it=st["it"], h=st["elapsed"] / 3600, J=float(np.mean([r["J"] for r in res])), fails=float(np.mean([r["fails"] for r in res])),
                   ot_gap=gap_ot, lam=st["lam"], complete=float(np.mean([r["complete"] for r in res])),
                   reroute=float(np.mean([r["nrr"] for r in res])), kl=kl_v, ent=float(ent), n_steps=Nn, errors=len(err))
        print(json.dumps(rec), flush=True); log.write(**rec)
        ck = dict(sd=net.state_dict(), opt=opt.state_dict(), state=st)
        atomic_save(ck, last)
        atomic_save(dict(P=net.numpy_params(), router=rpath, it=st["it"]), os.path.join(a.out, "last_policy.pt"))
        if devplans and (st["it"] % a.val_every == 0 or st["it"] >= a.iters):
            P = net.numpy_params()
            vj = []
            for pl in devplans:
                for d in D.parse_days(a.dev_days):
                    vj.append(dict(path=pl["path"], sol=pl["solution"], day=d, P=P, router=os.path.join(ROOT, rpath), reroute=bool(a.reroute), greedy=True, adapt=a.adapt))
            vr = pool.map(_val_job, vj, chunksize=1)
            vr = [r for r in vr if r]
            J = float(np.mean([r["J"] for r in vr])); ot = float(np.mean([r["ot_min"] for r in vr])); otr = float(np.mean([r["ot_ref"] for r in vr]))
            feas = ot <= otr + 1.0 and all(r["complete"] for r in vr)
            log.write(it=st["it"], val_J=J, val_ot=ot, val_ot_ref=otr, val_fails=float(np.mean([r["fails"] for r in vr])), val_feasible=feas)
            print(f"[val] it={st['it']} J={J:.1f} ot={ot:.1f} (N6 {otr:.1f}) feasible={feas}", flush=True)
            soft = J + 100.0 * max(0.0, ot - otr - 1.0) + (1e6 if not all(r["complete"] for r in vr) else 0.0)
            if st.get("best_soft") is None or soft < st["best_soft"]:
                st["best_soft"] = soft
                atomic_save(dict(P=P, router=rpath, it=st["it"], val_J=J, soft=soft), os.path.join(a.out, "best_soft.pt"))
            if feas and (st["best"] is None or J < st["best"]):
                st["best"] = J
                atomic_save(dict(P=P, router=rpath, it=st["it"], val_J=J, adapt=a.adapt), os.path.join(a.out, "best.pt"))
            atomic_save(dict(sd=net.state_dict(), opt=opt.state_dict(), state=st), last)
    if not os.path.exists(os.path.join(a.out, "best.pt")) and os.path.exists(os.path.join(a.out, "best_soft.pt")):
        import shutil; shutil.copyfile(os.path.join(a.out, "best_soft.pt"), os.path.join(a.out, "best.pt"))
        progress(f"exec_ppo {a.out}: WARNING no validation checkpoint met ot<=N6+1; best.pt = min penalised-J checkpoint")
    if not os.path.exists(os.path.join(a.out, "best.pt")):
        atomic_save(dict(P=net.numpy_params(), router=rpath, it=st["it"]), os.path.join(a.out, "best.pt"))
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(st))
    pool.close()
    progress(f"exec_ppo {a.out} done it={st['it']} best_val_J={st['best']}")


def _val_job(job):
    try:
        torch.set_num_threads(1)
        from wx2 import sim as S, planadapt as PA
        ins = read_instance(os.path.join(ROOT, job["path"]))
        wx, reqs, meta = S.make_day(ins, job["day"])
        from e2e import rl_adapt as RA
        asol, _, _ = RA.adapt(ins, job["sol"], wx, job.get("adapt"))
        pol = make_exec_policy(job["P"], router_path=job["router"], greedy=True, allow_reroute=job["reroute"])
        m = S.Sim(ins, asol, wx, reqs).run(pol)
        m["ot_ref"] = S.Sim(ins, asol, wx, reqs).run(D.get_policy("N6_90_0.25"))["ot_min"]
        return {k: v for k, v in m.items() if not isinstance(v, (list, dict))}
    except Exception:
        import traceback; traceback.print_exc(); return None


if __name__ == "__main__":
    main()
