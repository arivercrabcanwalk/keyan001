"""Wind model for LRPHSD (rl_wind).
Physics (multirotor, constant commanded airspeed va = Liu's speed 900 m/min = 15 m/s):
  ground speed along leg direction u with wind vector w:  vg = w.u + sqrt(va^2 - (w x u)^2)   (crab angle compensates crosswind)
  flight time = d / vg ; flight energy = time * flight_energy  (power ~ constant at fixed airspeed, Dorling et al. 2017:
  hover and cruise power approximately equal), service energy/time unchanged.
  => headwind/tailwind asymmetry: t(A->B) != t(B->A); a round trip in any wind takes longer than in calm air.
Planning uses the FORECAST wind (constant vector) through 'effective distances' d_eff = d * va / vg (so all of Liu's
formulas, the kernel and the evaluator stay unchanged). Execution uses REALIZED wind: forecast + 2-D Ornstein-Uhlenbeck
deviation shared by all drones (time-varying, correlation time tau) + independent per-leg gusts."""
import math, numpy as np
VA = 900.0           # m/min (15 m/s)
MS = 60.0            # m/s -> m/min
def ground_speed(dx, dy, wx, wy, va=VA):
    """vectorised; dx,dy leg vector (m), wx,wy wind (m/min). returns vg (m/min), nan if not flyable"""
    d = np.hypot(dx, dy); d = np.where(d == 0, 1.0, d)
    ux, uy = dx / d, dy / d
    along = wx * ux + wy * uy; cross = wx * uy - wy * ux
    disc = va * va - cross * cross
    vg = along + np.sqrt(np.maximum(disc, 0.0))
    return np.where((disc <= 0) | (vg <= 0.05 * va), np.nan, vg)
def effective_dist(ins, wx, wy):
    """dict (a,b) -> effective distance d*va/vg for the constant wind (wx, wy) in m/min."""
    nodes = list(ins.nodes.values()); out = {}
    X = np.array([n.x for n in nodes]); Y = np.array([n.y for n in nodes])
    DX = X[None, :] - X[:, None]; DY = Y[None, :] - Y[:, None]
    D = np.hypot(DX, DY)
    vg = ground_speed(DX, DY, wx, wy)
    E = np.where(D > 0, D * VA / np.where(np.isnan(vg), 1e-9, vg), 0.0)
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            out[a.id, b.id] = float(E[i, j])
    return out
def make_planning_instance(ins, ctx, reserve=0.0, use_wind=True):
    """Instance used by planners: forecast-wind effective distances, batteries derated by (1+reserve)."""
    from dataclasses import replace
    from lrphsd.problem import Instance
    p = ins.params
    rs, rl = (reserve, reserve) if not isinstance(reserve, (list, tuple)) else reserve   # per drone type reserve
    q = Instance(ins.name, ins.targets, ins.stations, ins.sha256,
                 replace(p, small_battery=p.small_battery / (1 + rs), large_battery=p.large_battery / (1 + rl)))
    if use_wind:
        wx, wy = ctx['W'] * MS * math.cos(ctx['theta']), ctx['W'] * MS * math.sin(ctx['theta'])
        q.edist = effective_dist(q, wx, wy); q.dist = q.edist
    return q
# ---------------- context sampling ----------------
STRONG = False
def sample_context(rng):
    if STRONG:   # strong-wind regime: fresh/strong breeze, larger forecast error, gusty
        return dict(W=float(rng.uniform(6, 10)), theta=float(rng.uniform(0, 2 * math.pi)), sigma=float(rng.uniform(1.0, 3.0)),
                    gust=float(rng.choice([0.05, 0.15, 0.3])), gmax=4.0, tau=60.0)
    """Wind context known at planning time (forecast + its uncertainty)."""
    return dict(W=float(rng.uniform(0, 6)),                       # forecast mean wind speed m/s (calm .. moderate breeze)
                theta=float(rng.uniform(0, 2 * math.pi)),         # direction the wind blows TO
                sigma=float(rng.uniform(0.3, 2.5)),               # forecast error std per component, m/s
                gust=float(rng.choice([0.0, 0.05, 0.15])),        # per-leg gust probability
                gmax=3.0, tau=60.0)                               # gust peak m/s, OU correlation time (min)
# ---------------- Monte Carlo execution ----------------
def simulate(ins, sol, ctx, S=200, seed=0, horizon=720, dt=5.0):
    """Execute plan `sol` (official format) under S realized-wind scenarios.
    Each drone flies its trips in order from t=0. A trip FAILS if its realized energy exceeds the true battery
    (the drone must abort/emergency-land; its remaining targets are not delivered).
    Returns dict of arrays over scenarios: cost, makespan, failed_trips, undelivered, overtime (min over the drone limit)."""
    rng = np.random.default_rng(seed)
    p = ins.params
    K = int(horizon / dt) + 2
    a = math.exp(-dt / ctx['tau']); sd = ctx['sigma'] * MS * math.sqrt(1 - a * a)
    E = np.zeros((S, K, 2)); E[:, 0] = rng.normal(0, ctx['sigma'] * MS, (S, 2))
    for k in range(1, K): E[:, k] = a * E[:, k - 1] + rng.normal(0, sd, (S, 2))
    w0x, w0y = ctx['W'] * MS * math.cos(ctx['theta']), ctx['W'] * MS * math.sin(ctx['theta'])
    fixed = 0.0; operating = np.zeros(S); mk = np.zeros(S); failed = np.zeros(S); undeliv = np.zeros(S); over = np.zeros(S)
    for si, kind in enumerate(sol['station_types']):
        if not kind: continue
        fixed += (p.small_station_cost + p.small_drone_cost) if kind == 1 else (p.large_station_cost + p.small_drone_cost + p.large_drone_cost)
        st = ins.stations[si]
        for di, trips in enumerate(sol['routes'][si]):
            cap = p.large_battery if di == 0 else p.small_battery
            lim = p.small_duration if kind == 1 else p.large_duration
            t = np.zeros(S)
            for trip in trips:
                if not trip: continue
                seq = [st] + [ins.nodes[n] for n in trip] + [st]
                eng = np.zeros(S); alive = np.ones(S, bool); served = np.zeros(S)
                for li, (u, v) in enumerate(zip(seq, seq[1:])):
                    k = np.minimum((t / dt).astype(int), K - 1)
                    wx = w0x + E[np.arange(S), k, 0]; wy = w0y + E[np.arange(S), k, 1]
                    if ctx['gust'] > 0:
                        g = rng.random(S) < ctx['gust']
                        mag = rng.uniform(0.5, 1.0, S) * ctx['gmax'] * MS
                        ang = ctx['theta'] + rng.normal(0, 0.5, S)
                        wx = wx + g * mag * np.cos(ang); wy = wy + g * mag * np.sin(ang)
                    vg = ground_speed(v.x - u.x, v.y - u.y, wx, wy)
                    d = math.hypot(v.x - u.x, v.y - u.y)
                    nofly = np.isnan(vg)          # wind >= airspeed component: leg cannot be flown -> abort
                    tt = np.where(nofly, d / VA, d / np.where(nofly, 1.0, vg))
                    t = t + np.where(alive, tt, 0.0)
                    eng = eng + np.where(alive, tt * p.flight_energy, 0.0) + np.where(alive & nofly, 1e3, 0.0)
                    if li < len(seq) - 2:   # arriving at a target: service
                        eng = eng + np.where(alive, v.energy, 0.0); t = t + np.where(alive, v.service, 0.0)
                    # abort as soon as the battery is exhausted (remaining targets not served)
                    dead = alive & (eng > cap + 1e-9)
                    if li < len(seq) - 2: served = served + (alive & ~dead)
                    alive = alive & ~dead
                failed += ~alive; undeliv += len(trip) - served
            operating += t; mk = np.maximum(mk, t); over += np.maximum(0.0, t - lim)
    cost = fixed + operating * p.time_cost
    return dict(cost=cost, makespan=mk, failed=failed, undelivered=undeliv, overtime=over)
