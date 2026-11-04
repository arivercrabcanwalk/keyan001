"""State features for the hold/launch decision (scenario E)."""
import dyn, math, numpy as np
from dyn import sim as S, pol as P
NF = 22
class Ctx:
    """per-(instance, plan) static info cached on the Sim object"""
    def __init__(self, sim):
        ins = sim.ins; self.post = P.Posterior(ins); T = self.post.T; self.T = T
        st = np.array([[s[0], s[1]] for s in sim.st]); R = np.array([s[2] for s in sim.st])
        D = np.sqrt(((T[:, None] - st[None]) ** 2).sum(-1)); cov = D <= R[None]
        self.excl = np.array([(cov[:, k] & (cov.sum(1) == 1)).sum() / max(1, cov[:, k].sum()) for k in range(len(st))])
        self.share = cov.sum(0) / len(T)
        self.dT = D   # target-to-station distances
        self.R = R; self.st = st
        self.rate = len(T) / 3.0 / S.H
        self.static = P.make_static(120); self.slack = P.make_slack(240, 0)
def features(sim, i):
    c = sim.__dict__.get('_ctx')
    if c is None: c = sim._ctx = Ctx(sim)
    d = sim.drones[i]; t = sim.t; k = d['sid']
    w = c.post.post(sim.seen) if sim.seen or not hasattr(c, 'w0') else c.w0
    if not sim.seen: c.w0 = w
    inR = c.dT[:, k] <= c.R[k] + 500
    p_hot_here = float(w[:-1][inR].sum())
    # expected urgent rate in station area per 15 min under posterior (0.4 base share + 0.6 hot if hot here)
    base_here = c.share[k]
    exp15 = c.rate * 15 * (0.4 * base_here + 0.6 * p_hot_here) if (1 - w[-1]) > 0 else c.rate * 15 * base_here
    exp15 = c.rate * 15 * ((1 - w[-1]) * (0.4 * base_here) + w[-1] * base_here + 0.6 * p_hot_here)
    lc30 = P.local_count(sim, i, 30.0); lc60 = P.local_count(sim, i, 60.0); lcall = P.local_count(sim, i, 1e9)
    g60 = sum(1 for (tt, _, _, _) in sim.seen if t - tt <= 60) / max(1e-9, c.rate * 60)
    ro_st = P.ready_others(sim, i); ro_5 = P.ready_others(sim, i, 5000.0)
    pe = [P.proj_end(sim, j) for j in range(len(sim.drones))]
    mk_o = max([pe[j] for j in range(len(pe)) if j != i] + [0.0])
    slack = (mk_o - pe[i]) / 60.0
    nxt = 1e9
    for j, e in enumerate(sim.drones):
        if j != i and e['state'] == 'busy' and math.hypot(e['x'] - d['x'], e['y'] - d['y']) <= 5000: nxt = min(nxt, e['free'] - t)
    nxt = min(nxt, 60.0) / 30.0
    f = [t / S.H, sum(d['q']) / 100.0, d['q'][0] / 60.0 if d['q'] else 0.0, len(d['q']) / 5.0,
         float(ro_st > 0), ro_5 / 3.0, max(-2.0, min(2.0, slack)), float(slack * 60 >= S.HOLD),
         lc30 / 3.0, lc60 / 3.0, lcall / 6.0, g60, p_hot_here, float(w[-1]), exp15,
         nxt, float(d['large']), float(sim.st[k][3] == 2), c.excl[k], c.share[k] * len(sim.st) / 4,
         float(c.static(sim, i)), d['holds'] / 10.0]
    return np.array(f, dtype=np.float32)
