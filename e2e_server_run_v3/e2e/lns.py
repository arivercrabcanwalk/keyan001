"""Fallback C: learned-repair LNS (NLNS-style). Destroy = pick one or two open stations (all their trips); repair =
pi_route sampling on the station sub-problem (targets of those stations, same types). Accept if cheaper.
The repair operator is the learned policy; no hand-written repair, no ALNS operator."""
import time, numpy as np
from .common import evaluate, to_solution, fixed_cost
from .route_infer import solve_routes


def improve(ins, sol, rpol, dev, budget=5.0, seed=0):
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter()
    types = list(sol["station_types"]); routes = [[list(map(list, d)) for d in s] for s in sol["routes"]]
    tidx = {t.id: k for k, t in enumerate(ins.targets)}
    TG = np.array([[t.x, t.y] for t in ins.targets]); ST = np.array([[s.x, s.y] for s in ins.stations])
    best = evaluate(ins, to_solution(ins, types, routes))["cost"]
    opened = [s for s, t in enumerate(types) if t]
    it = 0
    while time.perf_counter() - t0 < budget and opened:
        it += 1
        k = 1 if len(opened) < 2 or rng.random() < 0.5 else 2
        S = list(rng.choice(opened, k, replace=False))
        nids = [nid for s in S for d in routes[s] for tr in d for nid in tr]
        if len(nids) < 2:
            continue
        tg = TG[[tidx[n] for n in nids]]; st = ST[S]; ty = np.array([types[s] for s in S])
        c, acts = solve_routes(rpol, tg, st, ty, mode="sample:2", dev=dev, seed=int(rng.integers(1 << 30)))
        if not np.isfinite(c):
            continue
        from .route_env import decode_actions
        sub = decode_actions(acts, len(nids), len(S), ty)
        new = [[list(map(list, d)) for d in s] for s in routes]
        for j, s in enumerate(S):
            new[s] = [[[nids[q] for q in tr] for tr in sub[j][dr]] for dr in range(2)]
        ev = evaluate(ins, to_solution(ins, types, new))
        if ev["feasible"] and ev["cost"] < best - 1e-9:
            best, routes = ev["cost"], new
    return to_solution(ins, types, routes), best, it


# ---------------------------------------------------------------------------------------------------------------
# v3: learned-repair LNS for anytime budgets (NLNS, Hottung & Tierney 2020; RRC/"learning to reconstruct", Ye et
# al. 2024 / Luo et al. 2024 style).  The repair operator is pi_route itself (POMO aug8 x multi-start batch on the
# sub-problem = all targets of the selected stations, same opened types -> targets may MOVE between stations).
# Destroy neighbourhoods (no ALNS operator of the author is used): 1 station / station + k nearest open stations /
# target-region (stations owning the targets nearest to a random target). Operator weights adapt by success,
# acceptance = record-to-record travel (threshold decays linearly to 0 at the deadline).
# ---------------------------------------------------------------------------------------------------------------
def improve_v3(ins, sol, rpol, dev, budget=5.0, seed=0, rrt0=0.004, N=None):
    from .route_env import decode_actions
    rng = np.random.default_rng(seed)
    t0 = time.perf_counter(); T = max(1e-6, budget)
    types = list(sol["station_types"]); routes = [[list(map(list, d)) for d in s] for s in sol["routes"]]
    tidx = {t.id: k for k, t in enumerate(ins.targets)}
    TG = np.array([[t.x, t.y] for t in ins.targets]); ST = np.array([[s.x, s.y] for s in ins.stations])
    cur = evaluate(ins, to_solution(ins, types, routes))["cost"]
    best, best_routes = cur, routes
    opened = [s for s, t in enumerate(types) if t]
    if not opened:
        return to_solution(ins, types, routes), best, dict(iters=0)
    D = np.linalg.norm(ST[opened][:, None] - ST[opened][None], axis=-1)
    ops = ["one", "pair", "triple", "region"]; w = np.ones(len(ops)); stats = dict(iters=0, acc=0, imp=0)
    while time.perf_counter() - t0 < budget:
        stats["iters"] += 1
        k = int(rng.choice(len(ops), p=w / w.sum())); op = ops[k]
        a = int(rng.integers(len(opened)))
        if op == "one" or len(opened) == 1:
            S = [opened[a]]
        elif op in ("pair", "triple"):
            m = 2 if op == "pair" else 3
            S = [opened[q] for q in np.argsort(D[a])[:m]]
        else:
            owner = {nid: s for s in opened for d in routes[s] for tr in d for nid in tr}
            if not owner:
                continue
            ids = list(owner); c = TG[tidx[ids[int(rng.integers(len(ids)))]]]
            near = sorted(ids, key=lambda n: np.hypot(*(TG[tidx[n]] - c)))[:max(4, len(ids) // 4)]
            S = sorted({owner[n] for n in near})
        nids = [nid for s in S for d in routes[s] for tr in d for nid in tr]
        if len(nids) < 2:
            continue
        tg = TG[[tidx[n] for n in nids]]; st = ST[S]; ty = np.array([types[s] for s in S])
        c, acts = solve_routes(rpol, tg, st, ty, mode="pomo", dev=dev, N=N, seed=int(rng.integers(1 << 30)))
        if not np.isfinite(c):
            w[k] = max(0.2, 0.9 * w[k]); continue
        sub = decode_actions(acts, len(nids), len(S), ty)
        new = [[list(map(list, d)) for d in s] for s in routes]
        for j, s in enumerate(S):
            new[s] = [[[nids[q] for q in tr] for tr in sub[j][dr]] for dr in range(2)]
        ev = evaluate(ins, to_solution(ins, types, new))
        if not ev["feasible"]:
            w[k] = max(0.2, 0.9 * w[k]); continue
        frac = min(1.0, (time.perf_counter() - t0) / T)
        if ev["cost"] < best - 1e-9:
            best, best_routes = ev["cost"], new; w[k] += 1.0; stats["imp"] += 1
        if ev["cost"] <= cur + rrt0 * (1 - frac) * best + 1e-9:
            cur, routes = ev["cost"], new; stats["acc"] += 1
        w[k] = max(0.2, 0.98 * w[k])
    stats["w"] = dict(zip(ops, np.round(w / w.sum(), 3).tolist()))
    return to_solution(ins, types, best_routes), best, stats
