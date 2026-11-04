"""Learned per-trip recourse policy (design a). Conditioned on the failure price P.
At each launch: candidates k = 1..n (keep the first k targets, re-queue the rest). Features per candidate are computed from
observable information only: nowcast wind (no gust), forecast, context (sigma, gust prob, W), trip geometry, drone time slack,
plan reserve, P. Policy = shared MLP scoring each candidate, softmax over candidates.
Training: POMO-style multi-sample REINFORCE with a shared baseline: N rollouts on the SAME realized-wind scenario
(common random numbers), advantage = R_i - mean_j R_j, R = -(cost + P * failed_trips)."""
import wind, math, numpy as np
from wind.model import VA, MS, ground_speed
NF = 20
def leg_times(st, nodes, w):
    """times (min) of out-legs st->n1->..->nk and of return legs ni->st, under constant wind w (m/min)."""
    xs = np.array([st.x] + [n.x for n in nodes]); ys = np.array([st.y] + [n.y for n in nodes])
    dx = np.diff(xs); dy = np.diff(ys); d = np.hypot(dx, dy)
    vg = ground_speed(dx, dy, w[0], w[1]); out = np.where(np.isnan(vg), 1e3, d / np.where(np.isnan(vg), 1, vg))
    rx = st.x - xs[1:]; ry = st.y - ys[1:]; rd = np.hypot(rx, ry)
    vr = ground_speed(rx, ry, w[0], w[1]); ret = np.where(np.isnan(vr), 1e3, rd / np.where(np.isnan(vr), 1, vr))
    return out, ret
def prefix_stats(ins, st, nodes, w):
    """energy and duration of each prefix k=1..n under constant wind w"""
    p = ins.params; out, ret = leg_times(st, nodes, w)
    cum = np.cumsum(out); n = len(nodes); k = np.arange(1, n + 1)
    fly = cum + ret
    E = fly * p.flight_energy + 0.2 * k
    T = fly + 10.0 * k
    return E, T
def features(obs, P, reserve):
    ins, st, nodes, cap, ctx = obs['ins'], obs['st'], obs['nodes'], obs['cap'], obs['ctx']
    n = len(nodes); now = obs['now']; w0 = obs['w0']
    En, Tn = prefix_stats(ins, st, nodes, now); Ef, Tf = prefix_stats(ins, st, nodes, w0); Ec, Tc = prefix_stats(ins, st, nodes, np.zeros(2))
    # remainder trips (k+1..n flown separately) under nowcast
    extra = np.zeros(n)
    for k in range(1, n):
        Er, Tr = prefix_stats(ins, st, nodes[k:], now); extra[k - 1] = Tn[k - 1] + Tr[-1] - Tn[-1]
    # headwind on the return leg of each prefix
    hw = np.array([-(now[0] * (st.x - v.x) + now[1] * (st.y - v.y)) / max(math.hypot(st.x - v.x, st.y - v.y), 1.0) / VA for v in nodes])
    qt = sum(prefix_stats(ins, st, [ins.nodes[x] for x in q], w0)[1][-1] for q in obs['queue']) if obs['queue'] else 0.0
    slack = (obs['lim'] - obs['t'] - Tn[-1] - qt) / obs['lim']
    dev = np.linalg.norm(now - w0) / (ctx['sigma'] * MS + 1.0)
    k = np.arange(1, n + 1)
    F = np.stack([En / cap, Ef / cap, Ec / cap, (En - Ef) / cap, Tn / 60, k / n, (n - k) / 5, extra / 60, hw,
                  np.full(n, ctx['sigma'] / 2.5), np.full(n, ctx['gust'] * 5), np.full(n, ctx['W'] / 6), np.full(n, dev),
                  np.full(n, slack), np.full(n, math.log10(P) - 2), (En > cap).astype(float), np.full(n, reserve * 10),
                  (k == n).astype(float),
                  # model-informed risk features (same information the rules have): OU drift + gust exposure over the prefix duration
                  (cap - En) / np.maximum(En * (ctx['sigma'] * MS * np.sqrt(1 - np.exp(-Tn / ctx['tau']))) / VA + 1e-3, 1e-3) / 10,
                  ctx['gust'] * Tn / 5.0], 1)
    return F.astype(np.float32)
class NpMLP:
    def __init__(self, params): self.p = [np.asarray(x, dtype=np.float32) for x in params]
    def __call__(self, F):
        W1, b1, W2, b2, W3, b3, Ws, bs = self.p
        h = np.maximum(F @ W1.T + b1, 0); h = np.maximum(h @ W2.T + b2, 0); return (h @ W3.T + b3)[:, 0] + (F @ Ws.T + bs)[:, 0]
def make_rl(params, P, reserve, greedy=True, rng=None, record=None):
    mlp = NpMLP(params)
    def pol(obs):
        F = features(obs, P, reserve); s = mlp(F)
        if greedy: a = int(np.argmax(s))
        else:
            z = np.exp(s - s.max()); z /= z.sum(); a = int(rng.choice(len(s), p=z))
        if record is not None: record.append((F, a))
        return a + 1
    return pol
