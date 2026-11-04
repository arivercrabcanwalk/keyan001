"""Target-level residual policy (v2).

Hooks carl.neighborhood._sample: whenever an operator samples k targets from a pool,
targets are drawn by Plackett-Luce (Gumbel top-k) with weights exp(score_i), where
score_i = f_theta(target features_i, global/op/lambda features). The output layer is
initialised to zero, so the untrained policy is exactly uniform sampling = the heuristic
generator (residual policy). Station-level choices stay heuristic.
"""
import math, numpy as np
import carl.neighborhood as NB
from carl.actions import N_OPERATORS

_orig_sample = NB._sample
ACTIVE = None
def _hook(rng, items, k):
    if ACTIVE is None or k <= 0 or k >= len(items):
        return _orig_sample(rng, items, k)
    return ACTIVE.sample(rng, items, k)
NB._sample = _hook

FT = 12
FG = N_OPERATORS + 3 + 10
HID = 64; HID2 = 32

def init_params(seed=0):
    r = np.random.default_rng(seed)
    p = {'W1t': r.normal(0, 1/np.sqrt(FT), (FT, HID)), 'W1g': r.normal(0, 1/np.sqrt(FG), (FG, HID)), 'b1': np.zeros(HID),
         'Wc': np.zeros((3, HID)),  # FiLM gate from (lambda, reserve, risk)
         'W2': r.normal(0, 1/np.sqrt(HID), (HID, HID2)), 'b2': np.zeros(HID2),
         'w3': np.zeros(HID2), 'b3': np.zeros(1)}
    return p

class TargetPolicy:
    name = 'tpol'; needs_feats = False
    def __init__(self, params, lam=0.0, reserve=0.0, risk=0.0, log=False, nocond=False, greedy_temp=1.0):
        self.p = {k: np.asarray(v, dtype=np.float64) for k, v in params.items()}
        self.lam, self.reserve, self.risk = lam, reserve, risk
        self.nocond = nocond
        self.log = log; self.temp = greedy_temp
        self.ctx = None; self.D = None
        self.states = []; self.calls = []; self.cand = -1; self.step_calls = []
        self.groups = []
    # ---------------- per-instance / per-state
    def _dist_matrix(self, ins):
        ids = [t.id for t in ins.targets] + [s.id for s in ins.stations]
        n = max(ids) + 1
        D = np.zeros((n, n))
        for a in ids:
            for b in ids:
                D[a, b] = ins.dist[a, b]
        self.D = D; self.st_ids = np.array([s.id for s in ins.stations])
    def _state(self, ctx):
        if ctx is self.ctx:
            return
        self.ctx = ctx
        if self.D is None:
            self._dist_matrix(ctx.ins)
        D = self.D; mir = ctx.mirror
        nids = []; prv = []; nxt = []; tl = []; tsz = []; own = []; st = []; dr = []
        for si, station in enumerate(mir.routes):
            dep = self.st_ids[si]
            for di, trips in enumerate(station):
                for trip in trips:
                    if not trip: continue
                    L = D[dep, trip[0]] + D[trip[-1], dep]
                    for a, b in zip(trip, trip[1:]): L += D[a, b]
                    for pi, n in enumerate(trip):
                        nids.append(n); prv.append(trip[pi-1] if pi else dep); nxt.append(trip[pi+1] if pi+1 < len(trip) else dep)
                        tl.append(L); tsz.append(len(trip)); st.append(si); dr.append(di)
        nids = np.array(nids); prv = np.array(prv); nxt = np.array(nxt); st = np.array(st); dr = np.array(dr)
        sav = D[prv, nids] + D[nids, nxt] - D[prv, nxt]
        ownd = D[self.st_ids[st], nids]
        open_st = np.array(ctx.open_stations)
        dd = D[self.st_ids[open_st][:, None], nids[None, :]]  # (n_open, n)
        dd = np.where(open_st[:, None] == st[None, :], np.inf, dd)
        oth = dd.min(0) if len(open_st) > 1 else np.full(len(nids), 15000.0)
        oth = np.where(np.isfinite(oth), oth, 15000.0)
        btl = ctx.btl
        load = np.array(ctx.load); slack = np.array(ctx.slack)
        dw = np.stack([np.array(ctx.dw0), np.array(ctx.dw1)], 1)
        mk = max(dw.max(), 1e-9)
        T = np.zeros((len(nids), FT))
        T[:, 0] = sav / 1000; T[:, 1] = np.array(tl) / 10000; T[:, 2] = np.array(tsz) / 10
        T[:, 3] = ownd / 15000 * 4; T[:, 4] = oth / 15000 * 4; T[:, 5] = (ownd - oth) / 15000 * 4
        if btl:
            T[:, 6] = (st == btl[0]) & (dr == btl[1]); T[:, 7] = (st == btl[0])
        T[:, 8] = load[st]; T[:, 9] = slack[st]; T[:, 10] = dw[st, dr] / mk
        T[:, 11] = sav / np.maximum(np.array(tl), 1e-9)
        self.T = T; self.row = {int(n): i for i, n in enumerate(nids)}
        self.H1t = T @ self.p['W1t']
        self.sid = len(self.states)
        if self.log:
            self.states.append(T.astype(np.float32))
        tot = dw.sum(); self.btl_share = dw.max() / tot if tot > 0 else 0.0
    # ---------------- per-step
    def step_begin(self, ctx, op, it, frac, T, init_obj, stagnation, cur_obj, best_obj):
        self._ctx_pending = ctx
        self._gargs = (op, it, frac, T, init_obj, stagnation, cur_obj, best_obj)
        self.s = None; self.g = None
        self.step_calls = []
    def _make_g(self):
        ctx = self._ctx_pending
        op, it, frac, T, init_obj, stagnation, cur_obj, best_obj = self._gargs
        self._state(ctx)
        g = np.zeros(FG)
        g[op] = 1; g[N_OPERATORS + it] = 1
        o = N_OPERATORS + 3
        lam, rsv, risk = (0.0, 0.0, 0.0) if self.nocond else (self.lam, self.reserve, self.risk)
        g[o:o+10] = [lam, rsv, risk, frac, T / init_obj * 100, math.log1p(stagnation) / 8,
                     (cur_obj / best_obj - 1) * 100, self.btl_share, ctx.nst / 10, len(ctx.ins.targets) / 100]
        self.g = g
    def cand_begin(self, j):
        self.cand = j
    def scores(self):
        if self.s is None:
            if self.g is None: self._make_g()
            p = self.p; g = self.g
            c = g[N_OPERATORS + 3:N_OPERATORS + 6]
            h = self.H1t + g @ p['W1g'] + p['b1']
            h = h * (1 + c @ p['Wc'])
            h = np.maximum(h, 0)
            h2 = np.maximum(h @ p['W2'] + p['b2'], 0)
            self.s = (h2 @ p['w3'] + p['b3'][0]) / self.temp
        return self.s
    def sample(self, rng, items, k):
        items = list(items)
        s = self.scores()
        keys = [it if isinstance(it, int) else it[1] for it in items]
        rows = [self.row.get(int(x), -1) for x in keys]
        sc = np.array([s[r] if r >= 0 else 0.0 for r in rows])
        u = np.array([rng.random() for _ in items])
        gum = -np.log(-np.log(np.clip(u, 1e-12, 1 - 1e-12)))
        order = np.argsort(-(sc + gum))[:k]
        if self.log:
            self.step_calls.append((self.cand, self.sid, np.array(rows), order.copy()))
        return [items[i] for i in order]
    def step_end(self, picked, vals, cur_obj):
        if self.log and self.step_calls and self.g is not None:
            self.groups.append((self.g.astype(np.float32), self.step_calls, list(picked), np.array(vals, dtype=np.float64), cur_obj))


class FastTargetPolicy(TargetPolicy):
    """Inference-only variant: per-target features computed lazily (only for targets in the
    sampled pool) and cached per accepted solution. Numerically the same features as TargetPolicy."""
    def __init__(self, params, **kw):
        kw['log'] = False
        super().__init__(params, **kw)
        self.Dl = None
    def _state(self, ctx):
        if ctx is self.ctx:
            return
        self.ctx = ctx
        if self.Dl is None:
            if self.D is None: self._dist_matrix(ctx.ins)
            self.Dl = self.D.tolist(); self.sid_l = [int(x) for x in self.st_ids]
        self.fc = {}; self.tc = {}
        self.load = ctx.load; self.slack = ctx.slack; self.dw = (ctx.dw0, ctx.dw1)
        self.mk = max(max(ctx.dw0), max(ctx.dw1), 1e-9)
        self.open_st = ctx.open_stations; self.btl = ctx.btl
        tot = sum(ctx.dw0) + sum(ctx.dw1); self.btl_share = self.mk / tot if tot > 0 else 0.0
    def _row(self, n):
        f = self.fc.get(n)
        if f is not None:
            return f
        pos = self.ctx.mirror.pos.get(n)
        if pos is None:
            f = [0.0] * FT; self.fc[n] = f; return f
        si, di, ti, pi = pos; D = self.Dl; dep = self.sid_l[si]
        trip = self.ctx.mirror.routes[si][di][ti]
        key = (si, di, ti); L = self.tc.get(key)
        if L is None:
            L = D[dep][trip[0]] + D[trip[-1]][dep]
            for a, b in zip(trip, trip[1:]): L += D[a][b]
            self.tc[key] = L
        a = trip[pi-1] if pi else dep; b = trip[pi+1] if pi + 1 < len(trip) else dep
        sav = D[a][n] + D[n][b] - D[a][b]
        own = D[dep][n]; oth = 15000.0
        for s in self.open_st:
            if s != si:
                d = D[self.sid_l[s]][n]
                if d < oth: oth = d
        btl = self.btl
        onb = 1.0 if (btl and si == btl[0] and di == btl[1]) else 0.0
        ons = 1.0 if (btl and si == btl[0]) else 0.0
        f = [sav / 1000, L / 10000, len(trip) / 10, own / 3750, oth / 3750, (own - oth) / 3750, onb, ons,
             self.load[si], self.slack[si], self.dw[di][si] / self.mk, sav / max(L, 1e-9)]
        self.fc[n] = f
        return f
    def scores(self):
        raise RuntimeError('lazy policy scores per pool')
    def sample(self, rng, items, k):
        if self.g is None: self._make_g()
        items = list(items)
        keys = [int(it if isinstance(it, int) else it[1]) for it in items]
        sc = self.sc
        miss = [n for n in keys if n not in sc]
        if miss:
            p = self.p
            if self.gh is None:
                g = self.g; c = g[N_OPERATORS + 3:N_OPERATORS + 6]
                self.gh = (g @ p['W1g'] + p['b1'], 1 + c @ p['Wc'])
            gb, gm = self.gh
            F = np.array([self._row(n) for n in miss])
            h = np.maximum((F @ p['W1t'] + gb) * gm, 0)
            v = (np.maximum(h @ p['W2'] + p['b2'], 0) @ p['w3'] + p['b3'][0]) / self.temp
            for n, x in zip(miss, v.tolist()): sc[n] = x
        log = math.log; rnd = rng.random
        keyed = []
        for i, n in enumerate(keys):
            u = rnd()
            if u <= 0.0: u = 1e-12
            keyed.append((sc[n] - log(-log(u)), i))
        keyed.sort(reverse=True)
        return [items[i] for _, i in keyed[:k]]
    def step_begin(self, *a):
        super().step_begin(*a); self.gh = None; self.sc = {}
