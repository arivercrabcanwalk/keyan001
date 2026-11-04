"""Heterogeneous attention encoder-decoder (DPTARL/AM-style) for LRPHSD construction.
Nodes: targets and drone tokens (station x drone type: SABS-small, DABS-large, DABS-small).
Conditioning (kappa = makespan price, reserve r = energy-risk level) by FiLM on node embeddings
and in the decoder context."""
import math, torch, torch.nn as nn
from .inst import SCALE, SPEED, S_T

D_MODEL = 64
class Layer(nn.Module):
    def __init__(self, d, h=4, ff=128):
        super().__init__()
        self.att = nn.MultiheadAttention(d, h, batch_first=True)
        self.n1 = nn.LayerNorm(d); self.n2 = nn.LayerNorm(d)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.ReLU(), nn.Linear(ff, d))
    def forward(self, x):
        x = self.n1(x + self.att(x, x, x, need_weights=False)[0])
        return self.n2(x + self.ff(x))

class Policy(nn.Module):
    def __init__(self, d=D_MODEL, layers=3, cond=True):
        super().__init__()
        self.d = d; self.cond = cond
        self.emb_t = nn.Linear(4, d); self.emb_k = nn.Linear(8, d)
        self.film = nn.Linear(2, 2 * d)
        self.enc = nn.ModuleList([Layer(d) for _ in range(layers)])
        self.k_dyn = nn.Linear(4, d)
        self.none = nn.Parameter(torch.zeros(d))
        self.q = nn.Linear(3 * d + 7, d)
        self.Wk = nn.Linear(d, d, bias=False); self.Wv = nn.Linear(d, d, bias=False); self.Wl = nn.Linear(d, d, bias=False)
        self.Wo = nn.Linear(d, d)
        # distance-aware bias (cf. DAR, distance-aware attention reshaping): features d(last,target), d(active station,target)
        # for targets and d(last, token station) for tokens, all /5000 m; separate weights for glimpse and final logits
        self.wa = nn.Parameter(torch.tensor([-3.0, -1.0, -1.0])); self.wl = nn.Parameter(torch.tensor([-3.0, -1.0, -1.0]))
        self.value = nn.Sequential(nn.Linear(d + 2, 64), nn.ReLU(), nn.Linear(64, 1))  # A2C ablation critic
    def cond_vec(self, bt):
        c = torch.stack([bt.kappa / 5.0, bt.reserve * 5.0], 1)
        if not self.cond: c = torch.zeros_like(c)
        return c
    def encode(self, bt):
        n = bt.n; B = bt.B
        xy = bt.xy / SCALE
        dmin = bt.dk.min(1).values / 5000.0              # (B,n) nearest station-token distance
        ft = torch.cat([xy[:, :n], dmin[..., None], torch.ones(B, n, 1) * n / 100], -1)
        st_xy = xy[:, n:][:, bt.tok_st]                  # (B,K,2)
        oh = torch.nn.functional.one_hot(bt.tok_ty, 3).float()[None].expand(B, -1, -1)
        fk = torch.cat([st_xy, oh, (bt.tok_rad / 5000)[None, :, None].expand(B, -1, 1),
                        bt.capr[..., None], (bt.tok_lim / 600)[None, :, None].expand(B, -1, 1)], -1)
        h = torch.cat([self.emb_t(ft), self.emb_k(fk)], 1)
        c = self.cond_vec(bt)
        g, b = self.film(c).chunk(2, -1)
        h = h * (1 + g[:, None]) + b[:, None]
        for l in self.enc: h = l(h)
        self.h = h; self.c = c
        self.hk = self.Wk(h); self.hv = self.Wv(h); self.hl = self.Wl(h); self.gm = h.mean(1)
        return h
    def logits(self, bt, s, mask):
        n = bt.n; I = s.inst; R = s.R; ar = s.ar; B = bt.B; N = bt.N
        a = s.active.clamp(min=0); has = (s.active >= 0)
        tok_h = self.h[I, n + a]; tok_h = torch.where(has[:, None], tok_h, self.none[None].expand(R, -1))
        last_is_t = s.last < n
        last_h = torch.where(last_is_t[:, None], self.h[I, s.last.clamp(max=n - 1)], tok_h)
        lim = bt.tok_lim[a]; capr = bt.capr[I, a]
        dyn = torch.stack([s.Lopen / 10000, s.m / 4, s.Tdone[ar, a] / lim, capr,
                           s.visited.float().mean(1), has.float(), s.need_t.float()], 1)
        q = self.q(torch.cat([self.gm[I], tok_h, last_h, dyn], 1))   # (R,d)
        st = s.stype[:, bt.tok_st]
        kind = self.kind_t(bt)
        kd = torch.stack([s.Tdone / bt.tok_lim[None], (st == 0).float(), (st == kind).float(),
                          (s.active[:, None] == self.kar(bt)).float()], -1)  # (R,K,4)
        dk = self.k_dyn(kd)                                   # (R,K,d)
        Dl = bt.D[I, s.last] / 5000.0                          # (R, n+ns)
        Ds = bt.D[I, n + bt.tok_st[a], :n] / 5000.0            # (R, n)
        Dk = Dl[:, n + bt.tok_st]                              # (R, K)
        def bias(w): return torch.cat([w[0] * Dl[:, :n] + w[1] * Ds, w[2] * Dk], 1)
        qb = q.view(B, N, -1)
        att = torch.bmm(qb, self.hk.transpose(1, 2)).view(R, -1)    # (R,V')
        att = torch.cat([att[:, :n], att[:, n:] + (dk * q[:, None]).sum(-1)], 1) / math.sqrt(self.d) + bias(self.wa)
        att = att.masked_fill(~mask, -1e9)
        glimpse = torch.bmm(torch.softmax(att, -1).view(B, N, -1), self.hv).view(R, -1)
        q2 = self.Wo(glimpse)
        lg = torch.bmm(q2.view(B, N, -1), self.hl.transpose(1, 2)).view(R, -1)
        lg = torch.cat([lg[:, :n], lg[:, n:] + (dk * q2[:, None]).sum(-1)], 1)
        lg = 10 * torch.tanh(lg / math.sqrt(self.d)) + bias(self.wl)
        return lg.masked_fill(~mask, -1e9)
    def kind_t(self, bt):
        from .inst import TOK_KIND
        return torch.tensor(TOK_KIND)[bt.tok_ty][None]
    def kar(self, bt):
        return torch.arange(bt.K)[None]

def load_policy(path, **kw):
    """Loads new and pre-distance-bias checkpoints (old ones get wa = wl = 0, i.e. exactly their original behaviour)."""
    sd = torch.load(path); pol = Policy(**kw)
    if 'wa' not in sd: sd['wa'] = torch.zeros(3); sd['wl'] = torch.zeros(3)
    pol.load_state_dict(sd); return pol

def rollout(pol, bt, greedy=False, record=False):
    from .env import State
    s = State(bt); pol.encode(bt)
    logp = torch.zeros(s.R); acts = []
    for t in range(4 * bt.n + 10):
        if s.done.all(): break
        m = s.mask()
        stuck = ~s.done & ~m.any(1)
        if stuck.any():
            s.finish_fail(stuck); m = s.mask()
        lg = pol.logits(bt, s, m)
        lp = torch.log_softmax(lg, -1)
        a = lp.argmax(-1) if greedy else torch.multinomial(lp.exp(), 1).squeeze(1)
        logp = logp + lp.gather(1, a[:, None]).squeeze(1) * (~s.done).float()
        if record: acts.append(torch.where(s.done, torch.full_like(a, -1), a))
        s.step(a)
    F, cost, mk = s.objective()
    return F, cost, mk, logp, s, (torch.stack(acts, 1) if record else None)
