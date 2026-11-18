"""OUR v3 static plans (pure RL; no ALNS anywhere): siting -> pi_route -> RL-owned test-time search.
  --siting mincov            : S* = exact minimum-fixed-cost coverage-feasible siting (CFL).  SAME S* is given to the
                               author arm TS-FIX(S*) -> site/fixed-cost parity by construction (main comparison)
           plan:<jsonl>      : the siting of another plan set (e.g. TS-CC's) -> routing-only comparison at THEIR siting
           site:<ckpt>       : pi_site v3 (site_v3.py) choice among the exact feasible covers under the budget
  --mode greedy              : pi_route greedy (pure policy, ~ms)
         pomo                : aug8 x multi-start greedy (one batch)
         anytime             : pomo -> EAS-Emb (30 % of the budget) -> learned-repair LNS improve_v3 (rest)
         j5rr                : pomo candidates of the policy (aug8 x multi-start), top-k distinct by static cost,
                               re-ranked by simulated J5 with --exec on K TRAINING-weather days (5.9e6+; never test days)
Budget = wall seconds per instance (on the device used; recorded). Rows: {path, method, mode, sec, solution, cost,
feasible, cov_feasible, n_dabs, fixed_cost, wall, ...}."""
import os, sys, json, time, argparse, glob
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, read_instance, from_instance, evaluate
from e2e.route_model import load_route
from e2e.route_infer import solve_routes, to_official
from e2e import coverage as CV


def get_siting(ins, how, cache):
    P, cS, cD = CV.for_instance(ins, ROOT)
    if how == "mincov":
        return np.asarray(CV.min_cover(cS, cD)), {}
    if how.startswith("site:"):
        from e2e.site_v3 import choose
        return choose(ins, how[5:], cache)
    raise ValueError(how)


def j5_rerank(ins, rpol, dev, tg, st, tid, types, exec_spec, K=4, topk=8, seed=0, adapt=None):
    from e2e.route_infer import dihedral
    from e2e.route_model import rollout
    from e2e.route_env import Batch
    from e2e import dyn_eval as DE
    n = len(tg); N = min(n, 16); A = 8
    bt = Batch(np.stack([dihedral(tg, k) for k in range(A)]), np.stack([dihedral(st, k) for k in range(A)]), np.tile(types, (A, 1)), N=N, dev=dev)
    g = torch.Generator().manual_seed(seed); force = torch.randperm(n, generator=g)[:N].repeat(A).to(dev)
    o = rollout(rpol, bt, greedy=True, force=force)
    c = torch.where(o["fail"], torch.full_like(o["cost"], float("inf")), o["cost"]).cpu().numpy(); acts = o["acts"].cpu().numpy()
    cand, seen = [], set()
    for k in np.argsort(c):
        if not np.isfinite(c[k]) or len(cand) >= topk:
            break
        sol = to_official(ins, tid, types, acts[k].tolist(), len(st)); key = json.dumps(sol["routes"])
        if key in seen:
            continue
        seen.add(key); cand.append((float(c[k]), sol))
    best = None
    for ck, sol in cand:
        J = float(np.mean([DE.run_day(ins, sol, 5_900_000 + d, exec_spec, adapt=adapt)["J"] for d in range(K)]))
        if best is None or J < best[0]:
            best = (J, ck, sol)
    return best, len(cand)


def plan_one(ins, rel, rpol, dev, siting="mincov", mode="anytime", budget=10.0, seed=0, cache=None, eas_frac=0.3,
             exec_spec=None, K=4, topk=8, adapt=None):
    cache = {} if cache is None else cache
    t0 = time.perf_counter(); deadline = t0 + budget
    tg, st, tid, sid = from_instance(ins)
    info = {}
    if siting.startswith("plan:"):
        f = siting[5:]
        if f not in cache:
            cache[f] = {json.loads(l)["path"]: json.loads(l)["solution"]["station_types"] for l in open(f)}
        types = np.asarray(cache[f][rel])
    else:
        types, info = get_siting(ins, siting, cache)
    info["t_site"] = time.perf_counter() - t0
    if mode == "j5rr":
        best, nc = j5_rerank(ins, rpol, dev, tg, st, tid, types, exec_spec, K=K, topk=topk, seed=seed, adapt=adapt)
        if best is None:
            return None
        sol = best[2]; info.update(j5rr_train_J=best[0], j5rr_ncand=nc)
        ev = evaluate(ins, sol); P, cS, cD = CV.for_instance(ins, ROOT); t = sol["station_types"]
        return dict(solution=sol, cost=ev["cost"], feasible=ev["feasible"], cov_feasible=CV.feasible(t, cS, cD),
                    n_dabs=int(sum(1 for x in t if x == 2)), fixed_cost=CV.fixed_cost(t), wall=time.perf_counter() - t0, **info)
    if mode == "greedy":
        c, acts = solve_routes(rpol, tg, st, types, mode="greedy", dev=dev)
    else:
        c, acts = solve_routes(rpol, tg, st, types, mode="pomo", dev=dev, seed=seed)
        if mode == "anytime" and time.perf_counter() < deadline:
            d_eas = time.perf_counter() + eas_frac * max(0.0, deadline - time.perf_counter())
            c2, a2 = solve_routes(rpol, tg, st, types, mode="eas:1000000", dev=dev, deadline=d_eas, seed=seed)
            if c2 < c:
                c, acts = c2, a2
    if not np.isfinite(c):
        return None
    sol = to_official(ins, tid, types, acts, len(st))
    if mode == "anytime" and time.perf_counter() < deadline:
        from e2e.lns import improve_v3
        sol, _, st_l = improve_v3(ins, sol, rpol, dev, budget=deadline - time.perf_counter(), seed=seed)
        info.update(lns_iters=st_l["iters"], lns_imp=st_l["imp"], lns_w=st_l.get("w"))
    ev = evaluate(ins, sol)
    P, cS, cD = CV.for_instance(ins, ROOT)
    t = sol["station_types"]
    return dict(solution=sol, cost=ev["cost"], feasible=ev["feasible"], cov_feasible=CV.feasible(t, cS, cD),
                n_dabs=int(sum(1 for x in t if x == 2)), fixed_cost=CV.fixed_cost(t), wall=time.perf_counter() - t0, **info)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True); ap.add_argument("--inst", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--siting", default="mincov"); ap.add_argument("--mode", default="anytime")
    ap.add_argument("--budget", type=float, default=10.0); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--shard", default="0/1"); ap.add_argument("--tag", default="")
    ap.add_argument("--threads", type=int, default=int(os.environ.get("PLAN_THREADS", "2")))
    ap.add_argument("--exec", default="", help="j5rr: execution spec used for the re-ranking"); ap.add_argument("--K", type=int, default=4)
    ap.add_argument("--topk", type=int, default=8); ap.add_argument("--adapt", default=None)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    dev = device(); rpol, _ = load_route(a.route, dev); rpol.eval()
    files = sorted(glob.glob(os.path.join(ROOT, a.inst)))
    if not files:
        sys.exit(f"no instances match {a.inst}")
    si, sn = map(int, a.shard.split("/")); files = files[si::sn]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["path"] for l in open(a.out)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    cache = {}; nfail = 0
    with open(a.out, "a") as f:
        for p in files:
            rel = os.path.relpath(p, ROOT)
            if rel in done:
                continue
            ins = read_instance(p)
            r = plan_one(ins, rel, rpol, dev, siting=a.siting, mode=a.mode, budget=a.budget, seed=a.seed, cache=cache,
                         exec_spec=a.exec or None, K=a.K, topk=a.topk, adapt=a.adapt)
            if r is None or not r["feasible"] or not r["cov_feasible"]:
                nfail += 1; print("[plan_v3] FAILED", rel, None if r is None else (r["feasible"], r["cov_feasible"]), flush=True)
                if r is None:
                    continue
            row = dict(path=rel, method=a.tag or f"v3_{a.mode}", mode=a.mode, sec=a.budget, seed=a.seed, siting=a.siting, **r)
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"[plan_v3] {rel} cost={r['cost']:.2f} feas={r['feasible']} cov={r['cov_feasible']} dabs={r['n_dabs']} wall={r['wall']:.2f}s", flush=True)
    sys.exit(0 if nfail == 0 else 3)


if __name__ == "__main__":
    main()
