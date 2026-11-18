"""Siting helpers (no learning): coverage structure, randomized feasible sitings used as a training distribution
for pi_route before pi_site exists, and type-feasibility checks shared by pi_site's action mask."""
import numpy as np
from .common import SR, LR, FE, E_T, SPEED, SB, LB


def cov_mats(tg, st):
    d = np.sqrt(((st[:, None, :] - tg[None]) ** 2).sum(-1))         # (ns,n)
    c_s = (d <= SR + 1e-6) & (2 * d / SPEED * FE + E_T <= SB + 1e-9)  # SABS small drone can serve single trip
    c_d = (d <= LR + 1e-6) & (2 * d / SPEED * FE + E_T <= LB + 1e-9)  # DABS (large drone)
    return d, c_s, c_d


def feasible(types, c_s, c_d):
    t = np.asarray(types)
    cov = ((t == 1)[:, None] & c_s) | ((t == 2)[:, None] & c_d)
    return bool(cov.any(0).all())


def random_siting(tg, st, rng, p_open=None, p_dabs=None):
    """Randomized cover: open each station w.p. p_open (type DABS w.p. p_dabs), then repair coverage greedily
    (open the station covering most uncovered targets as DABS), then try SABS downgrades that keep coverage."""
    ns = len(st)
    d, c_s, c_d = cov_mats(tg, st)
    p_open = rng.uniform(0.2, 0.8) if p_open is None else p_open
    p_dabs = rng.uniform(0.2, 0.9) if p_dabs is None else p_dabs
    t = np.where(rng.random(ns) < p_open, np.where(rng.random(ns) < p_dabs, 2, 1), 0)
    for _ in range(ns + 1):
        cov = ((t == 1)[:, None] & c_s) | ((t == 2)[:, None] & c_d)
        unc = ~cov.any(0)
        if not unc.any():
            break
        gain = (c_d & unc[None]).sum(1) * (t != 2)
        s = int(np.argmax(gain + rng.random(ns) * 0.1))
        t[s] = 2
    if rng.random() < 0.5:
        for s in rng.permutation(ns):
            if t[s] == 2:
                t2 = t.copy(); t2[s] = 1
                if feasible(t2, c_s, c_d) and rng.random() < 0.5:
                    t = t2
    return t


# ---------------- v3: coverage-feasibility layer (CFL) sitings ----------------
def cfl_mats(tg, st, step=None):
    """(cS, cD) of the v3 emergency-support set Q_rho (e2e/coverage.py). step: coarser grid for training-time sampling."""
    from . import coverage as CV
    _, cS, cD = CV.support(tg, st, step=step or CV.STEP)
    return cS, cD


def random_cfl_siting(tg, st, rng, cS=None, cD=None):
    """Random COVERAGE-FEASIBLE siting for training-distribution purposes: random open/type draw, greedy repair to
    Q_rho coverage (open/upgrade the station covering most uncovered support points as DABS), then random
    feasibility-preserving downgrades/closures. Returns int array (ns,)."""
    from . import coverage as CV
    if cS is None:
        cS, cD = cfl_mats(tg, st, step=750.0)
    ns = len(st)
    p_open = rng.uniform(0.5, 1.0); p_dabs = rng.uniform(0.5, 1.0)
    t = np.where(rng.random(ns) < p_open, np.where(rng.random(ns) < p_dabs, 2, 1), 0)
    for _ in range(2 * ns + 2):
        cov = ((t == 1)[:, None] & cS).any(0) | ((t == 2)[:, None] & cD).any(0)
        unc = ~cov
        if not unc.any():
            break
        gain = (cD & unc[None]).sum(1) * (t != 2)
        s = int(np.argmax(gain + rng.random(ns) * 0.1))
        t[s] = 2
    for s in rng.permutation(ns):
        if rng.random() < 0.5:
            continue
        for v in ((0, 1) if t[s] == 2 else (0,) if t[s] == 1 else ()):
            t2 = t.copy(); t2[s] = v
            if CV.feasible(t2, cS, cD):
                t = t2; break
    return t
