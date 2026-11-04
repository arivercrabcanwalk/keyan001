"""Instances for the constructive RL (Liu LRPHSD). Parameters = Liu's (lrphsd.problem.Parameters)."""
import numpy as np, sys
sys.path.insert(0, '/workspace/rl_v3/engine')
SPEED = 900.0; FE = 0.018; E_T = 0.2; S_T = 10.0
SB, LB = 0.81, 1.0; SR, LR = 4000.0, 5000.0; SD, LD = 480.0, 600.0
SABS_FIX = 22.8 + 5.0; DABS_FIX = 30.4 + 8.0 + 5.0; TIME_COST = 0.5
SCALE = 15000.0
# token types: 0 = SABS small drone, 1 = DABS large drone, 2 = DABS small drone
TOK_KIND = np.array([1, 2, 2]); TOK_DI = np.array([1, 0, 1])
TOK_CAP = np.array([SB, LB, SB]); TOK_RAD = np.array([SR, LR, LR]); TOK_LIM = np.array([SD, LD, LD])

def gen(n, ns, rng):
    """Liu-style: stations uniform in [0,15000]^2, targets uniform but within 4750 m of some station."""
    st = rng.uniform(0, SCALE, (ns, 2))
    tg = np.zeros((0, 2))
    while len(tg) < n:
        c = rng.uniform(0, SCALE, (4 * n, 2))
        d = np.sqrt(((c[:, None, :] - st[None]) ** 2).sum(-1)).min(1)
        tg = np.concatenate([tg, c[d <= 4750]])
    return tg[:n], st

def from_lrphsd(ins):
    tg = np.array([[t.x, t.y] for t in ins.targets]); st = np.array([[s.x, s.y] for s in ins.stations])
    return tg, st, [t.id for t in ins.targets], [s.id for s in ins.stations]
