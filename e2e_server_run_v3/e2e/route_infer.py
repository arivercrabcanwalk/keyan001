"""pi_route inference: greedy | pomo (aug8 x multi-start, greedy) | sample:N | eas:T (EAS-Emb test-time adaptation).
All search here is RL-owned (the policy's own samples / its own embedding adaptation); no OR heuristic involved.
Returns official-format solutions validated by the independent evaluator."""
import time, math, numpy as np, torch
from .common import to_solution, evaluate, TOK_KIND
from .route_env import Batch, decode_actions
from .route_model import rollout, replay_grad


def dihedral(xy, k):
    x, y = xy[..., 0], xy[..., 1]
    c = [(x, y), (y, x), (-x, y), (y, -x), (x, -y), (-y, x), (-x, -y), (-y, -x)][k]
    return np.stack(c, -1)


def _routes_ids(routes, tid):
    return [[[[tid[j] for j in trip] for trip in dr] for dr in st_] for st_ in routes]


def _best(o, bt):
    c = torch.where(o["fail"], torch.full_like(o["cost"], float("inf")), o["cost"])
    k = int(torch.argmin(c)); return float(c[k]), o["acts"][k].tolist()


def solve_routes(pol, tg, st, types, mode="pomo", dev="cpu", N=None, reserve=0.0, tdone0=None, deadline=None, seed=0,
                 eas_lr=0.0041, eas_il=0.01):
    """Return (cost incl. fixed, acts list) for the best route found. types: (ns,) array."""
    n = len(tg); ns = len(st)
    g = torch.Generator(device="cpu").manual_seed(seed)
    if mode == "greedy":
        bt = Batch(tg[None], st[None], np.asarray(types)[None], reserve=[reserve], tdone0=None if tdone0 is None else tdone0[None], N=1, dev=dev)
        return _best(rollout(pol, bt, greedy=True), bt)
    A = 8
    N = N or min(n, 16)
    tga = np.stack([dihedral(tg, k) for k in range(A)]); sta = np.stack([dihedral(st, k) for k in range(A)])
    td = None if tdone0 is None else np.tile(tdone0, (A, 1))
    bt = Batch(tga, sta, np.tile(np.asarray(types), (A, 1)), reserve=[reserve] * A, tdone0=td, N=N, dev=dev)
    starts = torch.randperm(n, generator=g)[:N]
    force = starts.repeat(A).to(dev)
    best = _best(rollout(pol, bt, greedy=True, force=force), bt)
    if mode == "pomo":
        return best
    if mode.startswith("sample"):
        T = int(mode.split(":")[1]) if ":" in mode else 10 ** 9
        for _ in range(T):
            if deadline is not None and time.perf_counter() > deadline:
                break
            c = _best(rollout(pol, bt, greedy=False, force=force), bt)
            if c[0] < best[0]:
                best = c
        return best
    if mode.startswith("eas"):
        # EAS-Emb (Hottung et al., ICLR 2022): adapt the encoder output of THIS instance by gradient steps on
        # REINFORCE (shared baseline over the sampled rollouts) + imitation of the incumbent.
        T = int(mode.split(":")[1]) if ":" in mode else 10 ** 9
        with torch.no_grad():
            h0 = pol.encode(bt)
        emb = h0.detach().clone().requires_grad_(True)
        opt = torch.optim.Adam([emb], lr=eas_lr)
        for p in pol.parameters():
            p.requires_grad_(False)
        try:
            for it in range(T):
                if deadline is not None and time.perf_counter() > deadline:
                    break
                o = rollout(pol, bt, greedy=False, force=force, h=emb.detach())
                c = _best(o, bt)
                if c[0] < best[0]:
                    best = c
                F = o["F"].view(A, N); adv = (-(F - F.mean(1, keepdim=True)) / F.std(1, keepdim=True).clamp(min=1e-3)).view(-1)
                opt.zero_grad()
                hd = emb
                replay_grad(pol, bt, o["acts"], adv, force=force, hd=hd, ent_coef=0.0, chunk=64)
                # imitation of incumbent (single rollout, unforced) - reuse replay on a 1-instance batch view
                if eas_il > 0:
                    bt1 = Batch(tga[:1], sta[:1], np.asarray(types)[None], reserve=[reserve], tdone0=None if tdone0 is None else tdone0[None], N=1, dev=dev)
                    a1 = torch.as_tensor(best[1], device=dev)[None]
                    replay_grad(pol, bt1, a1, torch.full((1,), eas_il * N * A, device=dev), hd=emb[:1], chunk=64)
                opt.step()
        finally:
            for p in pol.parameters():
                p.requires_grad_(True)
        return best
    raise ValueError(mode)


def to_official(ins, tid, types, acts, ns):
    n = len(tid)
    routes = decode_actions(acts, n, ns, types)
    sol = to_solution(ins, list(types), _routes_ids(routes, tid))
    return sol


def plan_solution(pol, ins, tg, st, tid, types, mode="pomo", dev="cpu", **kw):
    c, acts = solve_routes(pol, tg, st, types, mode=mode, dev=dev, **kw)
    if not math.isfinite(c):
        return None, None
    sol = to_official(ins, tid, types, acts, len(st))
    ev = evaluate(ins, sol)
    return sol, ev
