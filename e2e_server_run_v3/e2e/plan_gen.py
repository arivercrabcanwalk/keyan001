"""Generate OUR static plans (no ALNS anywhere): pi_site -> [RL-owned station-set search] -> pi_route [-> EAS].
modes:
  pure     : pi_site greedy + pi_route greedy                               (pure policy, no search at all)
  sample   : pi_site M samples + pi_route aug8 x multi-start                (policy sampling only)
  full     : sample + station-set search (router-scored) + final aug8xMS + EAS until --budget seconds
  j5       : full, then the top-k sitings are re-ranked by simulated J5 (pi_exec, K training-weather days) = A4
Writes plan jsonl rows {path, method, mode, sec, solution, cost, feasible, n_open, wall}."""
import os, sys, json, time, argparse, glob
import numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from e2e.common import ROOT, device, read_instance, from_instance, evaluate, progress
from e2e.site_model import load_site
from e2e.route_model import load_route
from e2e.route_infer import solve_routes, to_official
from e2e.site_search import search, eval_sitings
from e2e.sitings import cov_mats, feasible


def plan_one(ins, spol, rpol, dev, mode="full", M=32, budget=10.0, eas=True, exec_spec=None, K=4, topk=3, seed=0, lns_budget=0.0, adapt=None):
    t0 = time.perf_counter(); deadline = t0 + budget
    tg, st, tid, sid = from_instance(ins)
    tgt = torch.as_tensor(tg[None], dtype=torch.float32, device=dev); stt = torch.as_tensor(st[None], dtype=torch.float32, device=dev)
    info = {}
    with torch.no_grad():
        if mode == "pure":
            types, _, _ = spol.run(tgt, stt, M=1, greedy=True)
            T = [types[0].cpu().numpy()]
        else:
            types, _, _ = spol.run(tgt, stt, M=M, greedy=True)
            T = list({tuple(x) for x in types.cpu().numpy().tolist()})
            T = [np.array(x) for x in T]
    if mode == "pure":
        c, acts = solve_routes(rpol, tg, st, T[0], mode="greedy", dev=dev)
        t_best = T[0]
    else:
        cs = eval_sitings(rpol, tg, st, T, dev)
        order = np.argsort(cs)
        t_best = T[order[0]]
        cands = [T[k] for k in order[:topk]]
        if mode in ("full", "j5"):
            t_s, c_s, si = search(rpol, tg, st, t_best, dev, deadline=t0 + 0.5 * budget)
            info.update(search_nev=si["nev"], search_rounds=si["rounds"])
            t_best = t_s
            cands = [t_s] + [x for x in cands if tuple(x) != tuple(t_s)][:topk - 1]
        if mode == "j5" and exec_spec:
            from e2e import dyn_eval as D
            best = None; t_j5 = time.perf_counter()
            for tt in cands:
                c1, a1 = solve_routes(rpol, tg, st, tt, mode="pomo", dev=dev)
                if not np.isfinite(c1):
                    continue
                sol = to_official(ins, tid, tt, a1, len(st))
                J = np.mean([D.run_day(ins, sol, 5_000_000 + k, exec_spec, adapt=adapt)["J"] for k in range(K)])  # training-weather days
                if best is None or J < best[0]:
                    best = (J, tt)
            info["j5_rerank_s"] = time.perf_counter() - t_j5      # REVIEW: reported; counts against the budget
            if best is not None:
                t_best = best[1]; info["j5_rank"] = float(best[0])
        rmode = "pomo"
        c, acts = solve_routes(rpol, tg, st, t_best, mode=rmode, dev=dev, seed=seed)
        if mode in ("full", "j5") and eas and time.perf_counter() < deadline:
            c2, a2 = solve_routes(rpol, tg, st, t_best, mode="eas:1000000", dev=dev, deadline=deadline, seed=seed)
            if c2 < c:
                c, acts = c2, a2
    if not np.isfinite(c):
        return None
    sol = to_official(ins, tid, t_best, acts, len(st))
    if lns_budget > 0:   # fallback C: learned-repair LNS polish
        from e2e.lns import improve
        sol, _, info["lns_iters"] = improve(ins, sol, rpol, dev, budget=lns_budget, seed=seed)
    ev = evaluate(ins, sol)
    wall = time.perf_counter() - t0
    return dict(solution=sol, cost=ev["cost"], feasible=ev["feasible"], n_open=int(sum(1 for x in t_best if x)), wall=wall, **info)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--inst", required=True, help="glob relative to ROOT, e.g. data/instances/test/*.txt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="full")
    ap.add_argument("--budget", type=float, default=10.0)
    ap.add_argument("--M", type=int, default=32)
    ap.add_argument("--exec", default="")
    ap.add_argument("--no_eas", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--lns_budget", type=float, default=0.0)
    ap.add_argument("--adapt", default=None)
    a = ap.parse_args()
    dev = device()
    spol, _ = load_site(a.site, dev); rpol, _ = load_route(a.route, dev)
    files = sorted(glob.glob(os.path.join(ROOT, a.inst)))
    if not files: sys.exit(f"no instances match {a.inst}")
    si, sn = map(int, a.shard.split("/")); files = files[si::sn]
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["path"] for l in open(a.out)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "a") as f:
        for p in files:
            rel = os.path.relpath(p, ROOT)
            if rel in done:
                continue
            ins = read_instance(p)
            r = plan_one(ins, spol, rpol, dev, mode=a.mode, M=a.M, budget=a.budget, eas=not a.no_eas, exec_spec=a.exec or None, seed=a.seed, lns_budget=a.lns_budget, adapt=a.adapt)
            if r is None:
                print("[plan_gen] FAILED", rel, flush=True); continue
            row = dict(path=rel, method=f"e2e_{a.mode}" + ("_lns" if a.lns_budget > 0 else ""), mode=a.mode, sec=a.budget, **r)
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"[plan_gen] {rel} cost={r['cost']:.2f} feas={r['feasible']} open={r['n_open']} wall={r['wall']:.2f}s", flush=True)


if __name__ == "__main__":
    main()
