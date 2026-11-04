"""NoRL policies for scenario E (hold/launch decision); dispatch = earliest arrival unless stated."""
import dyn, math, heapq, numpy as np
from dyn import sim as S
def myopic(sim, i): return False
def ready_others(sim, i, rad=None):
    """number of OTHER drones idle/holding whose station is within rad of drone i's station (default: same station)"""
    d = sim.drones[i]; n = 0
    for j, e in enumerate(sim.drones):
        if j == i or e['state'] == 'busy': continue
        if rad is None:
            if e['sid'] == d['sid']: n += 1
        elif math.hypot(e['x'] - d['x'], e['y'] - d['y']) <= rad: n += 1
    return n
def make_static(T_h, rad=None, dabs_only=True):
    """CFA-style reserve (Beraldi et al. 2024 keep-drones-ready idea): until T_h keep >=1 ready drone near each station."""
    def pol(sim, i):
        d = sim.drones[i]
        if sim.t >= T_h: return False
        if dabs_only and sim.st[d['sid']][3] != 2: return False
        return ready_others(sim, i, rad) == 0
    return pol
def local_count(sim, i, W):
    d = sim.drones[i]; c = 0
    for (t, x, y, p) in sim.seen:
        if sim.t - t <= W and math.hypot(x - d['x'], y - d['y']) <= d['R']: c += 1 + p
    return c
def make_adaptive(theta, W=60.0, rad=None, T_h=S.H):
    """hold if recent priority-weighted urgent demand in the station's radius >= theta and no other ready drone nearby"""
    def pol(sim, i):
        if sim.t >= T_h: return False
        if ready_others(sim, i, rad) > 0: return False
        return local_count(sim, i, W) >= theta
    return pol
# ------------- rollout (clairvoyant or sampled) -------------
def _continue(s, base):
    while s.ev:
        t, typ, _, i = heapq.heappop(s.ev); s.t = t
        if typ == 0: s._free(i, base)
        else: s._arrive(i, None)
    return s.metrics()['J']
def _forced(sim, i, act, base, day=None):
    s = sim.clone()
    if day is not None:
        s.day = day; s.ev = [e for e in s.ev if e[1] == 0]
        for j, r in enumerate(day.req):
            if r[0] > s.t: s._push(r[0], 1, j)
        heapq.heapify(s.ev)
    first = {'v': True}
    def pol(ss, k):
        if first['v'] and k == i:
            first['v'] = False; return act
        return base(ss, k)
    s._free(i, pol)
    return _continue(s, base)
def make_clairvoyant(base=myopic):
    """one-step rollout with the TRUE future (upper reference, not implementable)"""
    def pol(sim, i):
        return _forced(sim, i, True, base) < _forced(sim, i, False, base) - 1e-9
    return pol
class Posterior:
    """exact Bayesian posterior over the hidden hotspot (none, or centred near one of the targets) given seen requests"""
    def __init__(self, ins):
        self.T = np.array([[n.x, n.y] for n in ins.targets]); self.nt = len(self.T)
    def post(self, seen):
        T = self.T
        if not seen: lw = np.zeros(self.nt + 1)
        else:
            X = np.array([[x, y] for (_, x, y, _) in seen])
            d2 = ((X[:, None, :] - T[None]) ** 2).sum(-1)
            base = np.exp(-d2 / (2 * 500 ** 2)).mean(1) / (2 * math.pi * 500 ** 2) + 1e-300
            s2 = 700 ** 2 + 300 ** 2
            hot = np.exp(-d2 / (2 * s2)) / (2 * math.pi * s2)
            lw = np.concatenate([np.log(0.4 * base[:, None] + 0.6 * hot).sum(0), [np.log(base).sum()]])
        prior = np.concatenate([np.full(self.nt, 0.7 / self.nt), [0.3]])
        lw = lw + np.log(prior); w = np.exp(lw - lw.max()); return w / w.sum()
class FutureDay:
    def __init__(self, req): self.req = req
def sample_future(sim, post, rng, horizon=None, w=None):
    T = post.T; nt = post.nt
    w = post.post(sim.seen) if w is None else w; h = rng.choice(nt + 1, p=w)
    lam = nt / 3.0 / S.H; t0 = sim.t; t1 = S.H if horizon is None else min(S.H, t0 + horizon)
    n = rng.poisson(lam * max(0.0, t1 - t0)); t = np.sort(rng.uniform(t0, t1, n))
    if h < nt: c = T[h] + rng.normal(0, 300, 2); ish = rng.random(n) < 0.6
    else: c = T[0]; ish = np.zeros(n, bool)
    base = T[rng.integers(nt, size=n)] + rng.normal(0, 500, (n, 2)); hp = c + rng.normal(0, 700, (n, 2))
    xy = np.where(ish[:, None], hp, base); pri = (rng.random(n) < 0.4).astype(int)
    past = [r for r in sim.day.req if r[0] <= t0]
    return FutureDay(past + [(float(t[k]), float(xy[k, 0]), float(xy[k, 1]), int(pri[k])) for k in range(n)])
def make_rollout(M, base=myopic, seed=0, horizon=None):
    """sample-based rollout / SAA (MSA-style scenarios, known generative model, exact posterior)"""
    cache = {}
    def pol(sim, i):
        key = id(sim.ins)
        if key not in cache: cache.clear(); cache[key] = Posterior(sim.ins)
        post = cache[key]; rng = np.random.default_rng(int(sim.t * 7919 + i * 31 + seed))
        diff = 0.0; w = post.post(sim.seen)
        for m in range(M):
            day = sample_future(sim, post, rng, horizon, w)
            diff += _forced(sim, i, True, base, day) - _forced(sim, i, False, base, day)
        return diff < 0
    return pol
def proj_end(sim, j):
    e = sim.drones[j]
    a = max(sim.t, e['free']) if e['state'] == 'busy' else sim.t
    return a + sum(dd for dd, _ in e['uq']) + sum(e['q'])
def make_slack(T_h, margin, need_station=True, rad=None):
    """makespan-aware reserve: hold only drones whose projected end + HOLD stays below the projected makespan - margin"""
    def pol(sim, i):
        if sim.t >= T_h: return False
        if need_station and ready_others(sim, i, rad) > 0: return False
        mk = max(proj_end(sim, j) for j in range(len(sim.drones)) if j != i) if len(sim.drones) > 1 else 0.0
        return proj_end(sim, i) + S.HOLD <= mk - margin
    return pol
