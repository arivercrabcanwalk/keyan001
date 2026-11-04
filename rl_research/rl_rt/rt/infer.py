"""Inference modes for the constructive policy (single instance, wall-clock measured by caller).
greedy | sample:N | aug8 (greedy on 8 symmetric copies) | aug8s:N (8 copies x N samples)."""
import numpy as np, torch
from .env import Batch
from .model import rollout
from .inst import SCALE
def _aug(tg, st):
    out = []
    for sw in (0, 1):
        for fx in (0, 1):
            for fy in (0, 1):
                def f(p):
                    p = p[:, ::-1] if sw else p.copy()
                    p = p.copy()
                    if fx: p[:, 0] = SCALE - p[:, 0]
                    if fy: p[:, 1] = SCALE - p[:, 1]
                    return p
                out.append((f(tg), f(st)))
    return out
@torch.no_grad()
def solve(pol, tg, st, kappa, rsv, mode='greedy', seed=0):
    torch.manual_seed(seed)
    if mode == 'greedy': copies, N, greedy = [(tg, st)], 1, True
    elif mode.startswith('sample:'): copies, N, greedy = [(tg, st)], int(mode[7:]), False
    elif mode == 'aug8': copies, N, greedy = _aug(tg, st), 1, True
    elif mode.startswith('aug8s:'): copies, N, greedy = _aug(tg, st), int(mode[6:]), False
    else: raise ValueError(mode)
    B = len(copies)
    bt = Batch([a for a, b in copies], [b for a, b in copies], np.full(B, kappa), np.full(B, rsv), N=N)
    F, c, mk, lp, s, acts = rollout(pol, bt, greedy=greedy, record=True)
    if greedy and mode == 'aug8':
        pass
    j = int(torch.argmin(F))
    return float(F[j]), float(c[j]), float(mk[j]), acts[j].tolist(), bool(s.fail[j])
