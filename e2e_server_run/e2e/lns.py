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
