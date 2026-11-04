"""Online execution with per-trip recourse under realized wind (rl_wind, design (a)).
Realized wind is a deterministic function of time per scenario: w(t) = w0 + OU(t) + gust(t) (5-min bins, shared by drones).
Before launching each trip a policy observes the state and chooses how many targets to keep (trim the tail; trimmed targets
are re-queued as a new trip of the same drone, flown later). A trip fails if realized energy exceeds the battery."""
import wind, math, numpy as np
from wind.model import VA, MS, ground_speed
DT = 5.0
class Scenario:
    def __init__(self, ctx, seed, horizon=900):
        rng = np.random.default_rng(seed); K = int(horizon / DT) + 2
        a = math.exp(-DT / ctx['tau']); sd = ctx['sigma'] * MS * math.sqrt(1 - a * a)
        E = np.zeros((K, 2)); E[0] = rng.normal(0, ctx['sigma'] * MS, 2)
        for k in range(1, K): E[k] = a * E[k - 1] + rng.normal(0, sd, 2)
        g = (rng.random(K) < ctx['gust']) * rng.uniform(0.5, 1.0, K) * ctx['gmax'] * MS
        ang = ctx['theta'] + rng.normal(0, 0.5, K)
        w0 = np.array([math.cos(ctx['theta']), math.sin(ctx['theta'])]) * ctx['W'] * MS
        self.base = w0 + E                                    # without gusts (what a nowcast sees, smoothed)
        self.w = self.base + np.stack([g * np.cos(ang), g * np.sin(ang)], 1)
        self.K = K
    def at(self, t, gust=True):
        k = min(int(t / DT), self.K - 1); return (self.w if gust else self.base)[k]
def leg(u, v, w):
    vg = ground_speed(np.array(v.x - u.x), np.array(v.y - u.y), w[0], w[1])
    d = math.hypot(v.x - u.x, v.y - u.y)
    if np.isnan(vg): return d / VA, True
    return d / float(vg), False
def fly(ins, st, nodes, t0, wfun, cap):
    """returns (duration, energy, failed, n_served) flying station->nodes->station starting t0 under wind wfun(t)"""
    p = ins.params; seq = [st] + nodes + [st]; t = t0; e = 0.0; served = 0
    for i, (u, v) in enumerate(zip(seq, seq[1:])):
        tt, nofly = leg(u, v, wfun(t)); t += tt; e += tt * p.flight_energy
        if nofly or e > cap + 1e-9: return t - t0, e, True, served
        if i < len(seq) - 2: e += v.energy; t += v.service; served += 1
        if e > cap + 1e-9: return t - t0, e, True, served
    return t - t0, e, False, served
def predict(ins, st, nodes, t0, w, cap):
    """energy predicted with a constant wind vector w"""
    return fly(ins, st, nodes, t0, lambda t: w, 1e9)[1]
def run(ins, sol, ctx, sc, policy):
    """policy(obs) -> number of targets to keep (>=1). obs: dict. Returns metrics for one scenario."""
    p = ins.params; fixed = 0.0; operating = 0.0; mk = 0.0; failed = 0; undeliv = 0; trims = 0; over = 0.0
    w0 = np.array([math.cos(ctx['theta']), math.sin(ctx['theta'])]) * ctx['W'] * MS
    for si, kind in enumerate(sol['station_types']):
        if not kind: continue
        fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
        st = ins.stations[si]
        for di, trips in enumerate(sol['routes'][si]):
            cap = p.large_battery if di == 0 else p.small_battery
            lim = p.small_duration if kind == 1 else p.large_duration
            queue = [list(tr) for tr in trips if tr]; t = 0.0
            while queue:
                trip = queue.pop(0); nodes = [ins.nodes[n] for n in trip]
                now = sc.at(t, gust=False)
                obs = dict(ins=ins, st=st, nodes=nodes, t=t, cap=cap, lim=lim, now=now, w0=w0, ctx=ctx, queue=queue, sc=sc)
                k = max(1, min(len(nodes), int(policy(obs))))
                if k < len(nodes):
                    trims += 1; queue.insert(0, trip[k:]); nodes = nodes[:k]
                dur, e, fail, served = fly(ins, st, nodes, t, sc.at, cap)
                t += dur
                if fail: failed += 1; undeliv += len(nodes) - served
            operating += t; mk = max(mk, t); over += max(0.0, t - lim)
    return dict(cost=fixed + operating * p.time_cost, makespan=mk, failed=failed, undelivered=undeliv, trims=trims, overtime=over)
# ---------------- policies ----------------
def pol_none(obs): return len(obs['nodes'])
def make_margin(m):
    """NoRL rule: keep the longest prefix whose energy predicted with the current (nowcast) wind <= (1-m)*cap"""
    def pol(obs):
        n = len(obs['nodes'])
        for k in range(n, 0, -1):
            if predict(obs['ins'], obs['st'], obs['nodes'][:k], obs['t'], obs['now'], obs['cap']) <= (1 - m) * obs['cap']: return k
        return 1
    return pol
def pol_oracle(obs):
    """knows the realized wind: longest prefix that does not fail"""
    n = len(obs['nodes'])
    for k in range(n, 0, -1):
        if not fly(obs['ins'], obs['st'], obs['nodes'][:k], obs['t'], obs['sc'].at, obs['cap'])[2]: return k
    return 1
# ---------------- model-based look-ahead rule (strong NoRL) ----------------
def fail_prob(obs, nodes, M=32, rng=None):
    """P(trip fails) by Monte Carlo continuation of the OU forecast-error process from the current nowcast."""
    ins, st, ctx, cap = obs['ins'], obs['st'], obs['ctx'], obs['cap']; p = ins.params
    rng = rng or np.random.default_rng(0)
    a = math.exp(-DT / ctx['tau']); sd = ctx['sigma'] * MS * math.sqrt(1 - a * a)
    w0 = obs['w0']; e0 = obs['now'] - w0
    K = 40; E = np.zeros((M, K, 2)); E[:, 0] = e0
    for k in range(1, K): E[:, k] = a * E[:, k - 1] + rng.normal(0, sd, (M, 2))
    g = (rng.random((M, K)) < ctx['gust']) * rng.uniform(0.5, 1.0, (M, K)) * ctx['gmax'] * MS
    ang = ctx['theta'] + rng.normal(0, 0.5, (M, K))
    Wx = w0[0] + E[:, :, 0] + g * np.cos(ang); Wy = w0[1] + E[:, :, 1] + g * np.sin(ang)
    seq = [st] + nodes + [st]; t = np.zeros(M); e = np.zeros(M); dead = np.zeros(M, bool); ar = np.arange(M)
    t0 = obs['t']; off = int(t0 / DT)
    for i, (u, v) in enumerate(zip(seq, seq[1:])):
        k = np.minimum(((t0 + t) / DT).astype(int) - off, K - 1)
        vg = ground_speed(np.full(M, v.x - u.x), np.full(M, v.y - u.y), Wx[ar, k], Wy[ar, k])
        d = math.hypot(v.x - u.x, v.y - u.y); nofly = np.isnan(vg)
        tt = np.where(nofly, d / VA, d / np.where(nofly, 1.0, vg)); t += tt; e += tt * p.flight_energy
        dead |= nofly | (e > cap + 1e-9)
        if i < len(seq) - 2: e += v.energy; t += v.service; dead |= e > cap + 1e-9
    return dead.mean()
def make_lookahead(eps, M=32):
    def pol(obs):
        rng = np.random.default_rng(int(obs['t'] * 1000) % (2**31))
        n = len(obs['nodes'])
        for k in range(n, 0, -1):
            if fail_prob(obs, obs['nodes'][:k], M, rng) <= eps: return k
        return 1
    return pol
# ======================= v2: hidden gust regime, event-driven execution =======================
REGIMES = [(0.0, 0.4), (0.05, 0.4), (0.25, 0.2)]   # (true per-bin gust probability, prior prob); forecast only knows the mixture
class Scenario2(Scenario):
    """Like Scenario but the day's gust probability is a hidden regime (not in the forecast); gusts up to gmax2."""
    def __init__(self, ctx, seed, horizon=900, gmax2=4.0):
        rng = np.random.default_rng(seed)
        pr = np.array([p for _, p in REGIMES]); self.regime = int(rng.choice(len(REGIMES), p=pr / pr.sum()))
        pg = REGIMES[self.regime][0]
        c2 = dict(ctx); c2['gust'] = pg; c2['gmax'] = gmax2
        super().__init__(c2, int(rng.integers(1 << 30)), horizon)
def run2(ins, sol, ctx, sc, policy):
    """Event-driven: drones launch in time order; obs['hist'] holds (end_time, realized/predicted energy ratio,
    gust_seen) for trips COMPLETED before the current launch time (across all drones)."""
    import heapq
    p = ins.params; fixed = 0.0; failed = 0; undeliv = 0; trims = 0
    w0 = np.array([math.cos(ctx['theta']), math.sin(ctx['theta'])]) * ctx['W'] * MS
    heap = []; drones = []
    for si, kind in enumerate(sol['station_types']):
        if not kind: continue
        fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
        for di, trips in enumerate(sol['routes'][si]):
            q = [list(tr) for tr in trips if tr]
            if q:
                drones.append(dict(st=ins.stations[si], cap=p.large_battery if di == 0 else p.small_battery,
                                   lim=p.small_duration if kind == 1 else p.large_duration, queue=q, t=0.0))
                heapq.heappush(heap, (0.0, len(drones) - 1))
    done_trips = []   # (end_time, ratio, gust_seen)
    while heap:
        t, i = heapq.heappop(heap); dr = drones[i]
        trip = dr['queue'].pop(0); nodes = [ins.nodes[n] for n in trip]
        now = sc.at(t, gust=False)
        hist = [h for h in done_trips if h[0] <= t]
        obs = dict(ins=ins, st=dr['st'], nodes=nodes, t=t, cap=dr['cap'], lim=dr['lim'], now=now, w0=w0, ctx=ctx,
                   queue=dr['queue'], sc=sc, hist=hist)
        k = max(1, min(len(nodes), int(policy(obs))))
        if k < len(nodes): trims += 1; dr['queue'].insert(0, trip[k:]); nodes = nodes[:k]
        dur, e, fail, served = fly(ins, dr['st'], nodes, t, sc.at, dr['cap'])
        epred = predict(ins, dr['st'], nodes, t, now, dr['cap'])
        k0, k1 = int(t / DT), min(int((t + dur) / DT), sc.K - 1)
        gust_seen = float(np.max(np.linalg.norm(sc.w[k0:k1 + 1] - sc.base[k0:k1 + 1], axis=1)) > 1.0)
        done_trips.append((t + dur, e / max(epred, 1e-9), gust_seen))
        if fail: failed += 1; undeliv += len(nodes) - served
        dr['t'] = t + dur
        if dr['queue']: heapq.heappush(heap, (dr['t'], i))
    operating = sum(d['t'] for d in drones); mk = max([d['t'] for d in drones] + [0.0])
    over = sum(max(0.0, d['t'] - d['lim']) for d in drones)
    return dict(cost=fixed + operating * p.time_cost, makespan=mk, failed=failed, undelivered=undeliv, trims=trims,
                overtime=over, regime=sc.regime)
