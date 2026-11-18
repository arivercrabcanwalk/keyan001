"""Train pi_exec v3:  stage X (Expert Iteration with fair-twin rollout search) -> stage P (PPO + PID-Lagrangian).
Training plans = OUR plans on TRAIN maps (pi_route on the coverage-feasible siting); never TSALNS/ALNS plans.
Weather days: 6e6 + 1e5*seed (ExIt), 7e6 + 1e5*seed (PPO); dev = dev plans x dev days (checkpoint selection only).
Outputs <out>/exit_r{k}.pt, <out>/best.pt (dict P=numpy params, stage, dev metrics), curve.jsonl, DONE."""
import os, sys, json, time, argparse
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, seed_all, JsonlLog, progress, atomic_save, read_instance
from e2e.exec_policy import ExecNet
from e2e import exec_v3 as X
from e2e.dyn_eval import parse_days


def _sim_day(ins, sol, day, adapt):
    from wx2 import sim as S
    from e2e import rl_adapt as RA
    wx, reqs, meta = S.make_day(ins, day)
    asol, _, _ = RA.adapt(ins, sol, wx, adapt)
    return S, asol, wx, reqs


def exit_job(job):
    """One (plan, day) episode acting with the search-improved policy; returns (x, mask, Q) at searched decisions."""
    try:
        torch.set_num_threads(1)
        ins = read_instance(os.path.join(ROOT, job["path"]))
        S, asol, wx, reqs = _sim_day(ins, job["sol"], job["day"], job.get("adapt"))
        rng = np.random.default_rng(job["day"])
        if job["P"] is None:
            from wx2 import policies as PL
            base5 = PL.name_policy("N6_90_0.25"); base = X.make_rule_off(base5) if job.get("base_off") else base5
        else:
            base = X.make_policy(job["P"], greedy=True)
        XS, MS, QS, PB = [], [], [], []
        stats = dict(n_dec=0, n_search=0, n_full=0)

        def pol(sim, i, m5, cands, info):
            mask, off = X.legal6(sim, i, m5, info, True)
            legal = [a for a in range(X.NACT) if mask[a]]
            stats["n_dec"] += 1
            if job["P"] is None:
                a_base = None; p = np.full(X.NACT, np.nan)
            else:
                xx = X.features6(sim, i, m5, cands, info, off); p, _ = X.np_forward(job["P"], xx, mask); a_base = int(np.argmax(p))
            if len(legal) > 1 and rng.random() < job["p_search"]:
                Q, nf = X.q_values(sim, i, legal, off, base, job["M"], rng, None)
                stats["n_search"] += 1; stats["n_full"] += nf
                if Q is not None:
                    q = np.full(X.NACT, np.nan); q[legal] = Q
                    XS.append(X.features6(sim, i, m5, cands, info, off)); MS.append(mask); QS.append(q); PB.append(p)
                    return X.apply_action(sim, i, int(legal[int(np.argmin(Q))]), off)
            if a_base is None:
                return base(sim, i, m5, cands, info)
            return X.apply_action(sim, i, a_base, off)
        m = S.Sim(ins, asol, wx, reqs).run(pol)
        return dict(X=np.array(XS, np.float32).reshape(-1, X.NIN), M=np.array(MS, bool).reshape(-1, X.NACT), Q=np.array(QS).reshape(-1, X.NACT), PB=np.array(PB).reshape(-1, X.NACT),
                    J=m["J"], ot=m["ot_min"], complete=m["complete"], **stats)
    except Exception as e:
        import traceback
        return dict(error=repr(e), tb=traceback.format_exc()[-1500:])


def val_job(job):
    try:
        torch.set_num_threads(1)
        ins = read_instance(os.path.join(ROOT, job["path"]))
        S, asol, wx, reqs = _sim_day(ins, job["sol"], job["day"], job.get("adapt"))
        m = S.Sim(ins, asol, wx, reqs).run(X.make_policy(job["P"], greedy=True))
        from e2e import rl_adapt as RA
        cs = int(m["unfinished"] == 0 and m["unserved"] - RA.n_unservable_all(ins, reqs) <= 0)
        return dict(J=m["J"], ot=m["ot_min"], fails=m["fails"], complete_strict=cs)
    except Exception:
        import traceback; traceback.print_exc(); return None


def ppo_job(job):
    """PPO episode with the sampling policy; also the greedy reference policy (stage-X result) on the SAME day for
    the overtime constraint (common random numbers)."""
    try:
        torch.set_num_threads(1)
        from e2e.exec_policy import sim_j_running  # noqa: F401
        ins = read_instance(os.path.join(ROOT, job["path"]))
        S, asol, wx, reqs = _sim_day(ins, job["sol"], job["day"], job.get("adapt"))
        rec = []
        pol = X.make_policy(job["P"], greedy=False, rng=np.random.default_rng(job["day"]), record=rec)
        sim = S.Sim(ins, asol, wx, reqs); m = sim.run(pol)
        mr = S.Sim(ins, asol, wx, reqs).run(X.make_policy(job["Pref"], greedy=True))
        J_runs = [r[5] for r in rec] + [m["J"]]
        Xs = np.stack([r[0] for r in rec]) if rec else np.zeros((0, X.NIN), np.float32)
        Ms = np.stack([r[1] for r in rec]) if rec else np.zeros((0, X.NACT), bool)
        return dict(X=Xs, M=Ms, A=np.array([r[2] for r in rec], np.int64), LP=np.array([r[3] for r in rec]), V=np.array([r[4] for r in rec]),
                    R=-np.diff(np.array(J_runs)) / 100.0, J=m["J"], ot=m["ot_min"], J_ref=mr["J"], ot_ref=mr["ot_min"],
                    complete=m["complete"], noff=int(getattr(sim, "n_offload", 0)))
    except Exception as e:
        import traceback
        return dict(error=repr(e), tb=traceback.format_exc()[-1500:])


# ---------------- stage E: OpenAI-ES (antithetic, common random numbers), as v5 RL5 but on the 6-action net ----------
ES_KEYS = ("W1.weight", "W1.bias", "W2.weight", "W2.bias", "W3.weight", "W3.bias", "Wa.weight", "Wa.bias")
_EW = {}


def _es_theta(f):
    mt = os.path.getmtime(f)
    if _EW.get("mt") != (f, mt):
        z = np.load(f, allow_pickle=True); _EW["th"] = z["theta"]; _EW["sig"] = float(z["sigma"])
        _EW["P0"] = z["P0"].item(); _EW["mt"] = (f, mt)
    return _EW["th"], _EW["sig"], _EW["P0"]


def es_unflat(v, P0):
    P = dict(P0); o = 0
    for k in ES_KEYS:
        n = P0[k].size; P[k] = v[o:o + n].reshape(P0[k].shape); o += n
    return P


def es_job(job):
    """(theta_file, nseed, sign, path, sol, day, adapt) -> metrics of the perturbed (or centre: nseed<0) policy."""
    try:
        torch.set_num_threads(1)
        f, ns, sg, path, sol, day, adapt = job
        th, sig, P0 = _es_theta(f)
        v = th if ns < 0 else th + sg * sig * np.random.default_rng(int(ns)).standard_normal(th.size)
        ins = read_instance(os.path.join(ROOT, path))
        S, asol, wx, reqs = _sim_day(ins, sol, day, adapt)
        m = S.Sim(ins, asol, wx, reqs).run(X.make_policy(es_unflat(v, P0), greedy=True), record_time=False)
        return dict(J=m["J"], ot=m["ot_min"], viol=float(m["unfinished"] + max(0, m["unserved"] - m["n_unservable"])))
    except Exception as e:
        return dict(error=repr(e))


def ref_job(job):
    try:
        torch.set_num_threads(1)
        Pref, path, sol, day, adapt = job
        ins = read_instance(os.path.join(ROOT, path))
        S, asol, wx, reqs = _sim_day(ins, sol, day, adapt)
        m = S.Sim(ins, asol, wx, reqs).run(X.make_policy(Pref, greedy=True), record_time=False)
        return dict(J=m["J"], ot=m["ot_min"])
    except Exception as e:
        return dict(error=repr(e))


def stage_es(a, st, pool, plans, Pref, P_init, dev_eval, ref_dev, save, log, stf):
    """F = J5 + 1000*violations + lam_OT*(ot - ot_ref)   (ot_ref: reference = stage-X/init policy on the SAME day)."""
    P0 = {k: np.asarray(v, np.float64) for k, v in P_init.items()}
    thf = os.path.join(a.out, "es_theta.npz"); esf = os.path.join(a.out, "es_state.npz")
    if os.path.exists(esf):
        z = np.load(esf); th, m1, m2 = z["theta"], z["m1"], z["m2"]
    else:
        th = np.concatenate([P0[k].ravel() for k in ES_KEYS]); m1 = np.zeros_like(th); m2 = np.zeros_like(th)
    rng0 = np.random.default_rng(1000 + a.seed)
    pool_items = [(plans[int(rng0.integers(len(plans)))], 6_500_000 + 100_000 * a.seed + j) for j in range(a.es_pool)]
    refc = st.setdefault("es_ref", {})
    Kp, Ki, Kd = map(float, a.pid.split(","))
    te = time.time() - st.get("e_elapsed", 0.0)
    while st["es_it"] < a.es_iters and time.time() - te < a.es_hours * 3600:
        it = st["es_it"]; rng = np.random.default_rng(a.seed * 7_777_777 + it)
        np.savez(thf + ".tmp.npz", theta=th, sigma=a.es_sigma, P0=np.array(P0, dtype=object)); os.replace(thf + ".tmp.npz", thf)
        bidx = rng.choice(len(pool_items), a.es_batch, replace=False)
        need = [int(b) for b in bidx if str(int(b)) not in refc]
        if need:
            rr = pool.map(ref_job, [(Pref, pool_items[b][0]["path"], pool_items[b][0]["solution"], pool_items[b][1], a.adapt) for b in need], chunksize=1)
            for b, r in zip(need, rr):
                refc[str(b)] = r.get("ot", 0.0)
        seeds = rng.integers(1, 2 ** 31 - 1, a.es_pop)
        jobs = [(thf, int(sd), sg, pool_items[b][0]["path"], pool_items[b][0]["solution"], pool_items[b][1], a.adapt)
                for sd in seeds for sg in (1, -1) for b in bidx]
        res = pool.map(es_job, jobs, chunksize=2)
        F = np.zeros((a.es_pop, 2, a.es_batch)); otd = []
        for q, r in enumerate(res):
            i, rem = divmod(q, 2 * a.es_batch); sgi, bi = divmod(rem, a.es_batch)
            if "error" in r:
                F[i, sgi, bi] = 1e5; continue
            d = r["ot"] - refc[str(int(bidx[bi]))]; otd.append(d)
            F[i, sgi, bi] = r["J"] + 1000.0 * r["viol"] + st["lam"] * d
        diff = (F[:, 0] - F[:, 1]).mean(1)                            # CRN antithetic difference per direction
        rk = np.empty(len(diff)); rk[np.argsort(diff)] = np.arange(len(diff)); rk = rk / max(1, len(diff) - 1) - 0.5
        g = np.zeros_like(th)
        for sd, w in zip(seeds, rk):
            g += w * np.random.default_rng(int(sd)).standard_normal(th.size)
        g /= (a.es_pop * a.es_sigma)
        m1 = 0.9 * m1 + 0.1 * g; m2 = 0.999 * m2 + 0.001 * g * g
        th = th - a.es_lr * (m1 / (1 - 0.9 ** (it + 1))) / (np.sqrt(m2 / (1 - 0.999 ** (it + 1))) + 1e-8)
        e = float(np.mean(otd)) - a.ot_eps if otd else 0.0
        st["I"] = max(0.0, st["I"] + e); st["lam"] = max(0.0, Kp * e + Ki * st["I"] + Kd * (e - st["e_prev"])); st["e_prev"] = e
        st["es_it"] = it + 1; st["e_elapsed"] = time.time() - te
        rec = dict(stage="E", it=st["es_it"], F=float(F.mean()), ot_minus_ref=float(np.mean(otd)) if otd else None, lam=st["lam"])
        if st["es_it"] % a.val_every == 0 or st["es_it"] >= a.es_iters:
            P = es_unflat(th, P0); dv = dev_eval(P); rec["dev"] = dv
            feas = dv["strict"] >= 1.0 and dv["ot"] <= ref_dev["ot"] + a.ot_eps; rec["dev_feasible"] = feas
            if feas and (st["best"] is None or dv["J"] < st["best"]["J"]):
                st["best"] = dict(J=dv["J"], ot=dv["ot"], tag=f"es_{st['es_it']}"); save(P, "best.pt", stage="E", it=st["es_it"], dev=dv)
        np.savez(esf + ".tmp.npz", theta=th, m1=m1, m2=m2); os.replace(esf + ".tmp.npz", esf)
        json.dump(st, open(stf, "w")); log.write(**rec); print(json.dumps(rec), flush=True)


def gae(R, V, lam=0.95):
    T = len(R); adv = np.zeros(T); last = 0.0
    for t in range(T - 1, -1, -1):
        nv = V[t + 1] if t + 1 < T else 0.0
        delta = R[t] + nv - V[t]; last = delta + lam * last; adv[t] = last
    return adv, adv + V


def soft_targets(Q, M, tau):
    Qm = np.where(M, Q, np.inf); qmin = Qm.min(1, keepdims=True)
    z = np.where(M, -(Qm - qmin) / tau, -np.inf); z = z - z.max(1, keepdims=True)
    p = np.exp(z) * M; p = p / p.sum(1, keepdims=True)
    spread = np.where(M, Q, -np.inf).max(1) - qmin[:, 0]
    return p, spread


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--plans", required=True); ap.add_argument("--dev_plans", required=True)
    ap.add_argument("--dev_days", default="16000-16019"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--adapt", default=None)
    ap.add_argument("--init_rl5", default="", help="ablation: start from v5 RL5 weights (default: scratch, round-0 base = N6 rule)")
    # stage X
    ap.add_argument("--rounds", type=int, default=3); ap.add_argument("--days_per_round", type=int, default=800)
    ap.add_argument("--M", type=int, default=4); ap.add_argument("--p_search", type=float, default=0.25)
    ap.add_argument("--tau", type=float, default=20.0); ap.add_argument("--anchor", type=float, default=0.3); ap.add_argument("--x_epochs", type=int, default=30)
    ap.add_argument("--x_hours", type=float, default=6.0)
    # stage P
    ap.add_argument("--ppo_iters", type=int, default=150); ap.add_argument("--ppo_hours", type=float, default=1.5)
    ap.add_argument("--episodes", type=int, default=160); ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--clip", type=float, default=0.15); ap.add_argument("--kl_stop", type=float, default=0.02)
    ap.add_argument("--ent", type=float, default=0.002); ap.add_argument("--ot_eps", type=float, default=2.0)
    ap.add_argument("--pid", default="0.05,0.005,0.02", help="Kp,Ki,Kd of the PID Lagrangian (Stooke et al. 2020)")
    ap.add_argument("--val_every", type=int, default=10)
    ap.add_argument("--stageP", default="es", choices=["es", "ppo", "none"], help="fine-tune stage after ExIt")
    ap.add_argument("--es_iters", type=int, default=300); ap.add_argument("--es_hours", type=float, default=4.0)
    ap.add_argument("--es_pop", type=int, default=16); ap.add_argument("--es_batch", type=int, default=16)
    ap.add_argument("--es_sigma", type=float, default=0.02); ap.add_argument("--es_lr", type=float, default=0.01)
    ap.add_argument("--es_pool", type=int, default=2000)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dev = device(); seed_all(a.seed)
    net = ExecNet().to(dev)
    if a.init_rl5:
        net.load_rl5(a.init_rl5)
    plans = [json.loads(l) for l in open(a.plans)]
    devplans = [json.loads(l) for l in open(a.dev_plans)]
    log = JsonlLog(os.path.join(a.out, "curve.jsonl"))
    stf = os.path.join(a.out, "state.json")
    st = json.load(open(stf)) if os.path.exists(stf) else dict(round=0, best=None, stage="X", ppo_it=0, es_it=0, lam=0.0, I=0.0, e_prev=0.0)
    from multiprocessing import get_context
    pool = get_context("spawn").Pool(a.workers, maxtasksperchild=50)
    rng = np.random.default_rng(a.seed)
    dvdays = parse_days(a.dev_days)

    def dev_eval(P):
        vr = pool.map(val_job, [dict(path=pl["path"], sol=pl["solution"], day=d, P=P, adapt=a.adapt) for pl in devplans for d in dvdays], chunksize=1)
        vr = [r for r in vr if r]
        return dict(J=float(np.mean([r["J"] for r in vr])), ot=float(np.mean([r["ot"] for r in vr])), fails=float(np.mean([r["fails"] for r in vr])),
                    strict=float(np.mean([r["complete_strict"] for r in vr])), n=len(vr))

    def save(P, name, **kw):
        atomic_save(dict(P=P, **kw), os.path.join(a.out, name))

    # ---------------- stage X ----------------
    dataf = os.path.join(a.out, "exit_data.npz")
    D = dict(np.load(dataf)) if os.path.exists(dataf) else dict(X=np.zeros((0, X.NIN), np.float32), M=np.zeros((0, X.NACT), bool), Q=np.zeros((0, X.NACT)), PB=np.zeros((0, X.NACT)))
    lastck = os.path.join(a.out, "last_net.pt")
    if os.path.exists(lastck):
        net.load_state_dict(torch.load(lastck, map_location=dev, weights_only=False))
    if a.init_rl5 and "init_dev" not in st:
        Pi = net.numpy_params(); dv = dev_eval(Pi); st["init_dev"] = dv
        save(Pi, "init.pt", stage="init", dev=dv)
        if dv["strict"] >= 1.0:
            st["best"] = dict(J=dv["J"], ot=dv["ot"], tag="init"); save(Pi, "best.pt", stage="init", dev=dv); save(Pi, "best_exit.pt", stage="init", dev=dv)
        json.dump(st, open(stf, "w")); log.write(stage="init", dev=dv); print(json.dumps(dict(init_dev=dv)), flush=True)
    t0 = time.time() - st.get("x_elapsed", 0.0)
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    while st["stage"] == "X" and st["round"] < a.rounds and time.time() - t0 < a.x_hours * 3600:
        r = st["round"]
        P = None if (r == 0 and not a.init_rl5) else net.numpy_params()
        day0 = 6_000_000 + 100_000 * a.seed + 10_000 * r
        jobs = [dict(path=pl["path"], sol=pl["solution"], day=day0 + k, P=P, M=a.M, p_search=a.p_search, adapt=a.adapt)
                for k, pl in enumerate(plans[int(i)] for i in rng.integers(len(plans), size=a.days_per_round))]
        res = pool.map(exit_job, jobs, chunksize=1)
        err = [x for x in res if "error" in x]; res = [x for x in res if "error" not in x]
        if err:
            print("[exit] worker errors", len(err), err[0]["tb"], flush=True)
        if not res:
            raise RuntimeError("no ExIt episodes")
        for k in ("X", "M", "Q", "PB"):
            D[k] = np.concatenate([D[k]] + [x[k] for x in res])
        np.savez_compressed(dataf, **D)
        beh = dict(J=float(np.mean([x["J"] for x in res])), ot=float(np.mean([x["ot"] for x in res])), n_new=int(sum(len(x["X"]) for x in res)),
                   search_frac=float(np.sum([x["n_search"] for x in res]) / max(1, np.sum([x["n_dec"] for x in res]))))
        # distill on the aggregated data set (DAgger-style aggregation)
        tgt, spread = soft_targets(D["Q"], D["M"], a.tau)
        # anchor to the behaviour policy that generated the data (trust region; no anchor for the rule base)
        hasb = ~np.isnan(D["PB"]).any(1)
        tgt[hasb] = (1 - a.anchor) * tgt[hasb] + a.anchor * D["PB"][hasb]
        w = np.clip(spread / 100.0, 0.05, 2.0)
        Xt = torch.as_tensor(D["X"], device=dev); Mt = torch.as_tensor(D["M"], device=dev)
        Tt = torch.as_tensor(tgt, dtype=torch.float32, device=dev); Wt = torch.as_tensor(w, dtype=torch.float32, device=dev)
        n = len(Xt); idx = np.arange(n); rng.shuffle(idx); nv = max(1, n // 10)
        vi, ti = torch.as_tensor(idx[:nv], device=dev), torch.as_tensor(idx[nv:], device=dev)
        best_vl, best_sd, bad = None, None, 0
        for ep in range(a.x_epochs):
            perm = ti[torch.randperm(len(ti), device=dev)]
            for s0 in range(0, len(perm), 2048):
                b = perm[s0:s0 + 2048]
                lg, _ = net(Xt[b], Mt[b])
                loss = -(Wt[b] * (Tt[b] * torch.log_softmax(lg, -1).clamp(min=-30)).sum(-1)).mean()
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
            with torch.no_grad():
                lg, _ = net(Xt[vi], Mt[vi])
                vl = float(-(Wt[vi] * (Tt[vi] * torch.log_softmax(lg, -1).clamp(min=-30)).sum(-1)).mean())
                agree = float((lg.argmax(-1) == Tt[vi].argmax(-1)).float().mean())
            if best_vl is None or vl < best_vl - 1e-5:
                best_vl, best_sd, bad = vl, {k: v.clone() for k, v in net.state_dict().items()}, 0
            else:
                bad += 1
                if bad >= 4:
                    break
        net.load_state_dict(best_sd)
        Pn = net.numpy_params(); dv = dev_eval(Pn)
        st["round"] = r + 1; st["x_elapsed"] = time.time() - t0
        save(Pn, f"exit_r{r + 1}.pt", stage="X", round=r + 1, dev=dv)
        rec = dict(stage="X", round=r + 1, beh=beh, n_data=int(len(D["X"])), val_loss=best_vl, val_agree=agree, dev=dv)
        print(json.dumps(rec), flush=True); log.write(**rec)
        if dv["strict"] >= 1.0 and (st["best"] is None or dv["J"] < st["best"]["J"]):
            st["best"] = dict(J=dv["J"], ot=dv["ot"], tag=f"exit_r{r + 1}"); save(Pn, "best.pt", stage="X", round=r + 1, dev=dv)
            save(Pn, "best_exit.pt", stage="X", round=r + 1, dev=dv)
        torch.save(net.state_dict(), lastck); json.dump(st, open(stf, "w"))
    if st["stage"] == "X":
        st["stage"] = "P"; json.dump(st, open(stf, "w"))
    # ---------------- stage P ----------------
    bx = os.path.join(a.out, "best_exit.pt")
    if not os.path.exists(bx):        # no strictly-complete ExIt round on dev: keep the last round as reference
        save(net.numpy_params(), "best_exit.pt", stage="X", note="no strict-complete dev round"); save(net.numpy_params(), "best.pt", stage="X")
    Pref = torch.load(bx, map_location="cpu", weights_only=False)["P"]
    if not os.path.exists(os.path.join(a.out, "ppo_net.pt")):
        net.load_state_dict({k: torch.as_tensor(v, dtype=torch.float32) for k, v in Pref.items()})
    else:
        net.load_state_dict(torch.load(os.path.join(a.out, "ppo_net.pt"), map_location=dev, weights_only=False))
    ref_dev = st.get("ref_dev") or dev_eval(Pref); st["ref_dev"] = ref_dev
    if a.stageP == "es":
        stage_es(a, st, pool, plans, Pref, Pref, dev_eval, ref_dev, save, log, stf)
        a.ppo_iters = 0
    elif a.stageP == "none":
        a.ppo_iters = 0
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    Kp, Ki, Kd = map(float, a.pid.split(","))
    tp = time.time() - st.get("p_elapsed", 0.0)
    while st["ppo_it"] < a.ppo_iters and time.time() - tp < a.ppo_hours * 3600:
        P = net.numpy_params(); day0 = 7_000_000 + 100_000 * a.seed + a.episodes * st["ppo_it"]
        jobs = [dict(path=pl["path"], sol=pl["solution"], day=day0 + k, P=P, Pref=Pref, adapt=a.adapt)
                for k, pl in enumerate(plans[int(i)] for i in rng.integers(len(plans), size=a.episodes))]
        res = [x for x in pool.map(ppo_job, jobs, chunksize=1) if "error" not in x and len(x["A"])]
        if not res:
            raise RuntimeError("no PPO episodes")
        Xs, Ms, As, LPs, ADV, RET = [], [], [], [], [], []
        for x in res:
            R = x["R"].copy(); R[-1] -= st["lam"] * (x["ot"] - x["ot_ref"] - a.ot_eps) / 100.0
            adv, ret = gae(R, x["V"]); Xs.append(x["X"]); Ms.append(x["M"]); As.append(x["A"]); LPs.append(x["LP"]); ADV.append(adv); RET.append(ret)
        Xt = torch.as_tensor(np.concatenate(Xs), device=dev); Mt = torch.as_tensor(np.concatenate(Ms), device=dev)
        At = torch.as_tensor(np.concatenate(As), device=dev); LPt = torch.as_tensor(np.concatenate(LPs), dtype=torch.float32, device=dev)
        ADVt = torch.as_tensor(np.concatenate(ADV), dtype=torch.float32, device=dev); RETt = torch.as_tensor(np.concatenate(RET), dtype=torch.float32, device=dev)
        ADVt = (ADVt - ADVt.mean()) / ADVt.std().clamp(min=1e-6)
        warm = st["ppo_it"] < 3; kl = 0.0; stop = False
        for ep in range(4):
            perm = torch.randperm(len(At), device=dev)
            for s0 in range(0, len(perm), 4096):
                b = perm[s0:s0 + 4096]
                lg, v = net(Xt[b], Mt[b]); lpa = torch.log_softmax(lg, -1); lp = lpa.gather(1, At[b][:, None]).squeeze(1)
                ratio = torch.exp(lp - LPt[b])
                pg = -torch.min(ratio * ADVt[b], ratio.clamp(1 - a.clip, 1 + a.clip) * ADVt[b]).mean()
                ent = -(lpa.exp() * lpa.clamp(min=-1e4)).sum(-1).mean()
                vl = torch.nn.functional.smooth_l1_loss(v, RETt[b])
                loss = (0.0 if warm else 1.0) * (pg - a.ent * ent) + 0.5 * vl
                opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 0.5); opt.step()
                with torch.no_grad():
                    kl = float((LPt[b] - lp).mean())
                if not warm and kl > a.kl_stop:
                    stop = True; break
            if stop:
                break
        e = float(np.mean([x["ot"] - x["ot_ref"] for x in res])) - a.ot_eps
        st["I"] = max(0.0, st["I"] + e)
        st["lam"] = max(0.0, Kp * e + Ki * st["I"] + Kd * (e - st["e_prev"])); st["e_prev"] = e
        st["ppo_it"] += 1; st["p_elapsed"] = time.time() - tp
        rec = dict(stage="P", it=st["ppo_it"], J=float(np.mean([x["J"] for x in res])), J_ref=float(np.mean([x["J_ref"] for x in res])),
                   ot=float(np.mean([x["ot"] for x in res])), ot_ref=float(np.mean([x["ot_ref"] for x in res])), lam=st["lam"], kl=kl)
        if st["ppo_it"] % a.val_every == 0 or st["ppo_it"] >= a.ppo_iters:
            P = net.numpy_params(); dv = dev_eval(P); rec["dev"] = dv
            feas = dv["strict"] >= 1.0 and dv["ot"] <= ref_dev["ot"] + a.ot_eps
            rec["dev_feasible"] = feas
            if feas and (st["best"] is None or dv["J"] < st["best"]["J"]):
                st["best"] = dict(J=dv["J"], ot=dv["ot"], tag=f"ppo_{st['ppo_it']}"); save(P, "best.pt", stage="P", it=st["ppo_it"], dev=dv)
        print(json.dumps(rec), flush=True); log.write(**rec)
        torch.save(net.state_dict(), os.path.join(a.out, "ppo_net.pt")); json.dump(st, open(stf, "w"))
    pool.close()
    open(os.path.join(a.out, "DONE"), "w").write(json.dumps(st))
    progress(f"exec_train_v3 {a.out} done: best={st['best']} ref_dev={ref_dev}")


if __name__ == "__main__":
    main()
