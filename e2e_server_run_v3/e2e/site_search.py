"""RL-owned station-set local search: neighbours of a siting (drop / add-SABS / add-DABS / flip type / swap) are
scored in ONE batched pi_route rollout (greedy, or greedy multi-start) and the best improving move is applied until
no improvement or the deadline. The evaluator is the learned router itself (no OR heuristic, no ALNS)."""
import time, numpy as np, torch
from .route_env import Batch
from .route_model import rollout
from .sitings import cov_mats, feasible


def neighbours(t, c_s, c_d, swap=True):
    ns = len(t); out = []
    for s in range(ns):
        for v in (0, 1, 2):
            if v != t[s]:
                t2 = t.copy(); t2[s] = v; out.append(t2)
    if swap:
        op = [s for s in range(ns) if t[s]]; cl = [s for s in range(ns) if not t[s]]
        for s in op:
            for a in cl:
                for v in (1, 2):
                    t2 = t.copy(); t2[s] = 0; t2[a] = v; out.append(t2)
    return [x for x in out if feasible(x, c_s, c_d)]


def eval_sitings(pol, tg, st, T, dev, N=1, chunk=512):
    """cost (fixed + route) for each siting in T (list of arrays) via batched greedy rollouts."""
    costs = []
    for i in range(0, len(T), chunk):
        S = np.stack(T[i:i + chunk]); b = len(S)
        n = len(tg)
        bt = Batch(np.repeat(tg[None], b, 0), np.repeat(st[None], b, 0), S, N=N, dev=dev)
        force = None
        if N > 1:
            force = torch.as_tensor(np.tile(np.random.default_rng(0).permutation(n)[:N], b), device=dev)
        o = rollout(pol, bt, greedy=True, force=force)
        c = torch.where(o["fail"], torch.full_like(o["cost"], float("inf")), o["cost"]).view(b, N).min(1).values
        costs += c.tolist()
    return costs


def search(pol, tg, st, t0, dev, deadline=None, N=1, swap=True, max_rounds=50):
    _, c_s, c_d = cov_mats(tg, st)
    t = np.asarray(t0).copy()
    best = eval_sitings(pol, tg, st, [t], dev, N=N)[0]
    nev = 1; rounds = 0
    while rounds < max_rounds and (deadline is None or time.perf_counter() < deadline):
        rounds += 1
        nb = neighbours(t, c_s, c_d, swap=swap)
        if not nb:
            break
        cs = eval_sitings(pol, tg, st, nb, dev, N=N); nev += len(nb)
        k = int(np.argmin(cs))
        if cs[k] < best - 1e-6:
            best, t = cs[k], nb[k]
        else:
            break
    return t, best, dict(nev=nev, rounds=rounds)
