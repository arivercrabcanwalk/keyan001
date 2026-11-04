"""Design c': wind front passage within the horizon; online trip sequencing per drone.
Scenario per case (forecast known at dispatch): pre-front wind w1 = case forecast (ctx W, theta); front at time T
(forecast That ~ U(30,150) min, error sd sT ~ U(20,45) min); post-front wind w2 (forecast w2fc: 4-10 m/s, direction
turned 90-180 deg; realized w2 = w2fc + N(0, 1 m/s) per component). Before T the front is not observed; once a drone
is ready at t >= T the realized w2 is known. Legs use the wind at leg start. Trip fails if energy > battery or a leg
is unflyable (ground speed <= 5% airspeed). Decision: which remaining trip each drone flies next (plan fixes the
trips; drones are independent given the common front). J = time_cost * flight time + fixed + P * failed trips."""
import wind, math, json, zlib, itertools, numpy as np
from wind.model import ground_speed, MS, VA
from scipy.stats import norm
P_FAIL = 100.0
def front_ctx(case, ctx, rng=None):
    rng = rng or np.random.default_rng(zlib.crc32(('front' + case).encode()))
    W2 = rng.uniform(4, 10); th2 = ctx['theta'] + rng.choice([-1, 1]) * rng.uniform(math.pi / 2, math.pi)
    return dict(w1=(ctx['W'] * MS * math.cos(ctx['theta']), ctx['W'] * MS * math.sin(ctx['theta'])),
                w2fc=(W2 * MS * math.cos(th2), W2 * MS * math.sin(th2)), That=float(rng.uniform(30, 150)), sT=float(rng.uniform(20, 45)), s2=1.0 * MS)
def sample_scen(fc, rng, n):
    T = np.maximum(5.0, fc['That'] + rng.normal(0, fc['sT'], n))
    w2 = np.array(fc['w2fc'])[None] + rng.normal(0, fc['s2'], (n, 2))
    return T, w2
class Trip:
    def __init__(s, ins, st, trip):
        seq = [st] + [ins.nodes[n] for n in trip] + [st]; p = ins.params
        s.dx = np.array([v.x - u.x for u, v in zip(seq, seq[1:])]); s.dy = np.array([v.y - u.y for u, v in zip(seq, seq[1:])])
        s.d = np.hypot(s.dx, s.dy); s.svc = np.array([v.service for v in seq[1:-1]] + [0.0]); s.en = np.array([v.energy for v in seq[1:-1]] + [0.0])
        s.fe = p.flight_energy
    def legdur(s, w):
        vg = ground_speed(s.dx, s.dy, w[0], w[1]); bad = np.isnan(vg)
        return np.where(s.d > 0, s.d / np.where(bad, 0.3 * VA, vg), 0.0), bad
    def summary(s, w, cap):
        key = (round(float(w[0]), 6), round(float(w[1]), 6))
        c = s.__dict__.setdefault('_c', {})
        if key in c: return c[key]
        c[key] = s._summary(w, cap); return c[key]
    def _summary(s, w, cap):
        dur, bad = s.legdur(w); e = (dur * s.fe + s.en).sum()
        return dur.sum() + s.svc.sum(), dur.sum(), e / cap, bool(bad.any() or e > cap + 1e-9)
def fly(tr, t, T, L1, L2, cap):
    """fly trip from time t; L1/L2 = (legdur, bad) under w1 / w2. returns t_end, flight minutes, ok"""
    e = 0.0; ok = True; fm = 0.0
    for k in range(len(tr.d)):
        dur, bad = (L1[0][k], L1[1][k]) if t < T else (L2[0][k], L2[1][k])
        t += dur + tr.svc[k]; fm += dur; e += dur * tr.fe + tr.en[k]; ok = ok and not bad
    return t, fm, ok and e <= cap + 1e-9
class Drone:
    def __init__(s, ins, st, trips, cap):
        s.trips = [Trip(ins, st, t) for t in trips if t]; s.cap = cap; s.tc = ins.params.time_cost
def run_order(dr, order, T, w1, w2):
    t = 0.0; fm = 0.0; fail = 0
    L1 = [tr.legdur(w1) for tr in dr.trips]; L2 = [tr.legdur(w2) for tr in dr.trips]
    for i in order:
        t, f, ok = fly(dr.trips[i], t, T, L1[i], L2[i], dr.cap); fm += f; fail += (not ok)
    return dict(cost=t * dr.tc, fail=fail, end=t)
def run_policy(dr, pol, T, w1, w2, fc, ctx=None):
    """online: pol(dr, rem, t, passed, w2known, fc) -> index into rem"""
    t = 0.0; fm = 0.0; fail = 0; rem = list(range(len(dr.trips))); order = []
    L1 = [tr.legdur(w1) for tr in dr.trips]; L2 = [tr.legdur(w2) for tr in dr.trips]
    while rem:
        passed = t >= T
        k = pol(dr, rem, t, passed, (w2 if passed else None), fc) if len(rem) > 1 else 0
        i = rem.pop(k); order.append(i)
        t, f, ok = fly(dr.trips[i], t, T, L1[i], L2[i], dr.cap); fm += f; fail += (not ok)
    return dict(cost=t * dr.tc, fail=fail, end=t, order=order)
def J(r, P=P_FAIL): return r['cost'] + P * r['fail']
# ---------------- order search (static) ----------------
def best_order(dr, scen, w1, P=P_FAIL, start=None):
    """order minimising mean J over scenarios list[(T,w2)]: exhaustive for <=6 trips, else swap+insert local search"""
    n = len(dr.trips)
    f = lambda o: np.mean([J(run_order(dr, o, T, w1, w2), P) for T, w2 in scen])
    if n <= 1: return list(range(n))
    if n <= 5: return list(min(itertools.permutations(range(n)), key=f))
    cur = list(start) if start is not None else list(range(n)); bv = f(cur); imp = True
    while imp:
        imp = False
        for i in range(n):
            for j in range(n):
                if i == j: continue
                c2 = cur[:]; x = c2.pop(i); c2.insert(j, x); v = f(c2)
                if v < bv - 1e-9: cur, bv, imp = c2, v, True
    return cur
# ---------------- online rules ----------------
def trip_feats(dr, i, t, passed, w2k, fc):
    tr = dr.trips[i]
    D1, F1, E1, I1 = tr.summary(fc['w1'], dr.cap)
    D2, F2, E2, I2 = tr.summary(w2k if passed else fc['w2fc'], dr.cap)
    return D1, F1, E1, I1, D2, F2, E2, I2
def make_ratio(beta=1.0, P=P_FAIL):
    """fly first the trip with the largest benefit of flying it before the front, per pre-front minute^beta"""
    def pol(dr, rem, t, passed, w2k, fc):
        if passed: return 0
        best, bk = -1e18, 0
        for k, i in enumerate(rem):
            D1, F1, E1, I1, D2, F2, E2, I2 = trip_feats(dr, i, t, passed, w2k, fc)
            g = (F2 - F1) * dr.tc + P * (I2 - I1)
            sc = g / max(D1, 1e-6) ** beta
            if sc > best: best, bk = sc, k
        return bk
    return pol
def make_rollout(K=16, beta=1.0, seed=0, P=P_FAIL):
    """model-based online look-ahead: for each candidate next trip, mean J over K posterior front scenarios of
    [candidate, then ratio rule]"""
    rule = make_ratio(beta, P)
    def pol(dr, rem, t, passed, w2k, fc):
        if passed: return 0
        rng = np.random.default_rng(seed + int(t * 7) + len(rem))
        # posterior of T given T > t (rejection from forecast)
        Ts = []
        while len(Ts) < K:
            x = fc['That'] + rng.normal(0, fc['sT'], 4 * K); Ts += list(x[x > t])
        Ts = np.maximum(5.0, np.array(Ts[:K])); W2 = np.array(fc['w2fc'])[None] + rng.normal(0, fc['s2'], (K, 2))
        best, bk = 1e18, 0
        for k, i in enumerate(rem):
            v = 0.0
            for T, w2 in zip(Ts, W2):
                r = run_sub(dr, rem, k, t, T, fc['w1'], w2, rule, fc); v += J(r, P)
            if v < best: best, bk = v, k
        return bk
    return pol
def run_sub(dr, rem, k, t, T, w1, w2, rule, fc):
    rem = list(rem); fm = 0.0; fail = 0; first = True; t0 = t
    while rem:
        if first: kk = k; first = False
        else: kk = rule(dr, rem, t, t >= T, (w2 if t >= T else None), fc) if len(rem) > 1 else 0
        i = rem.pop(kk)
        t, f, ok = fly(dr.trips[i], t, T, dr.trips[i].legdur(w1), dr.trips[i].legdur(w2), dr.cap); fm += f; fail += (not ok)
    return dict(cost=(t - t0) * dr.tc, fail=fail, end=t)
def posterior(fc, t, rng, K):
    Ts = []
    while len(Ts) < K:
        x = fc['That'] + rng.normal(0, fc['sT'], 4 * K); Ts += list(x[x > t])
    return np.maximum(5.0, np.array(Ts[:K])), np.array(fc['w2fc'])[None] + rng.normal(0, fc['s2'], (K, 2))
def make_rsaa(K=16, seed=0, P=P_FAIL):
    """rolling-horizon SAA (model-based NoRL): at each decision before the front is observed, re-optimise the order of
    the remaining trips on K posterior scenarios (T > t) starting at time t, fly the first."""
    def pol(dr, rem, t, passed, w2k, fc):
        if passed: return 0
        rng = np.random.default_rng(seed + len(rem) * 1000 + int(t))
        Ts, W2 = posterior(fc, t, rng, K)
        sub = Drone.__new__(Drone); sub.trips = [dr.trips[i] for i in rem]; sub.cap = dr.cap; sub.tc = dr.tc
        o = best_order(sub, [(T - t, w2) for T, w2 in zip(Ts, W2)], fc['w1'], P)
        return o[0]
    return pol
# ---------------- case loading ----------------
def load_case(row):
    from lrphsd.problem import read_instance
    from wind.cases import LIU, DEVDIR
    b = row['case'].split('#')[0]
    path = row.get('path') or (f'{DEVDIR}/{b}.txt' if b.startswith('d') else f'{LIU}/{b}.txt')
    ins = read_instance(path); p = ins.params; sol = row['solution']; fixed = 0.0; drones = []
    for si, kind in enumerate(sol['station_types']):
        if not kind: continue
        fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
        for di, trips in enumerate(sol['routes'][si]):
            trips = [t for t in trips if t]
            if trips: drones.append(Drone(ins, ins.stations[si], trips, p.large_battery if di == 0 else p.small_battery))
    return ins, fixed, drones
