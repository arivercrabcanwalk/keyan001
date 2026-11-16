"""pi_route: heterogeneous transformer encoder + LEHD-style HEAVY local decoder (INViT/ICAM-style local view).
Encoder (light-ish, run once): target tokens + drone tokens (station x drone kind), FiLM on the energy reserve r.
Decoder (heavy, every step): a context token + the k nearest FEASIBLE targets of the current position + all drone
tokens are re-embedded with step-dependent features (distances, energy/duty slack) and passed through L_dec
self-attention layers; logits = scaled dot-product(context, candidates) + learned distance bias.
Training memory: rollouts are sampled without grad; the gradient pass replays recorded actions in step chunks
against a detached encoder output (manual activation checkpointing), so cost is O(chunk) memory."""
import math, torch, torch.nn as nn, torch.nn.functional as Fn
from .common import SPEED, FE, E_T, S_T
from .route_env import Batch, State


def _layer(d, h, ff, drop=0.0):
    return nn.TransformerEncoderLayer(d, h, ff, drop, batch_first=True, norm_first=True, activation="gelu")


class RoutePolicy(nn.Module):
    def __init__(self, d=128, h=8, enc_layers=6, dec_layers=2, kc=24, ff_mult=4):
        super().__init__()
        self.cfg = dict(d=d, h=h, enc_layers=enc_layers, dec_layers=dec_layers, kc=kc, ff_mult=ff_mult)
        self.d = d; self.kc = kc
        self.emb_t = nn.Linear(6, d); self.emb_k = nn.Linear(11, d)
        self.film = nn.Sequential(nn.Linear(1, d), nn.GELU(), nn.Linear(d, 2 * d))
        self.enc = nn.ModuleList([_layer(d, h, ff_mult * d) for _ in range(enc_layers)])
        self.enc_norm = nn.LayerNorm(d)
        self.dyn_t = nn.Linear(6, d); self.dyn_k = nn.Linear(6, d)
        self.ctx = nn.Linear(3 * d + 8, d)
        self.none = nn.Parameter(torch.zeros(d))
        self.dec = nn.ModuleList([_layer(d, h, ff_mult * d) for _ in range(dec_layers)])
        self.dec_norm = nn.LayerNorm(d)
        self.Wq = nn.Linear(d, d, bias=False); self.Wk = nn.Linear(d, d, bias=False)
        self.wb = nn.Parameter(torch.tensor([-2.0, -1.0, -1.0]))      # distance bias: d(last,j), d(stn,j), d(last,token stn)

    # ---------------- encoder ----------------
    def encode(self, bt):
        n = bt.n; B = bt.B
        xy = bt.xy
        lo = xy.min(1, keepdim=True).values; span = (xy.max(1, keepdim=True).values - lo).amax(-1, keepdim=True).clamp(min=1.0)
        nxy = (xy - lo) / span
        dk = bt.dk.masked_fill(~bt.tok_open[..., None], 1e9)
        dmin = dk.min(1).values.clamp(max=2e4) / 5000.0
        ncov = bt.single_ok.float().sum(1) / 6.0
        ft = torch.cat([nxy[:, :n], dmin[..., None], ncov[..., None], torch.full((B, n, 1), n / 100.0, device=bt.dev),
                        (span.view(B, 1, 1) / 15000.0).expand(B, n, 1)], -1)
        st_xy = nxy[:, n:][:, bt.tok_st]
        oh = Fn.one_hot(bt.tok_ty, 3).float()[None].expand(B, -1, -1)
        fk = torch.cat([st_xy, oh, (bt.tok_rad / 5000)[None, :, None].expand(B, -1, 1), bt.capr[..., None],
                        (bt.tok_lim / 600)[None, :, None].expand(B, -1, 1), bt.tok_open[..., None].float(),
                        (bt.tdone0 / bt.tok_lim[None])[..., None], bt.single_ok.float().sum(-1, keepdim=True) / max(n, 1)], -1)
        hx = torch.cat([self.emb_t(ft), self.emb_k(fk)], 1)
        g, b = self.film(bt.reserve[:, None] * 5.0).chunk(2, -1)
        hx = hx * (1 + g[:, None]) + b[:, None]
        pad = torch.cat([torch.zeros(B, n, dtype=torch.bool, device=bt.dev), ~bt.tok_open], 1)
        for l in self.enc:
            hx = l(hx, src_key_padding_mask=pad)
        return self.enc_norm(hx)

    # ---------------- heavy decoder ----------------
    def step_logits(self, h, bt, s, mask):
        n = bt.n; K = bt.K; I = s.inst; R = s.R; ar = s.ar; d = self.d
        a = s.active.clamp(min=0); has = s.active >= 0
        stn = n + bt.tok_st[a]
        tok_h = torch.where(has[:, None], h[I, n + a], self.none[None].expand(R, -1))
        last_h = torch.where((s.last < n)[:, None], h[I, s.last.clamp(max=n - 1)], tok_h)
        Dl = bt.D[I, s.last]                                            # (R,V)
        Ds = bt.D[I, stn, :n]
        mt = mask[:, :n]; mk = mask[:, n:]
        kc = min(self.kc, n)
        score = Dl[:, :n].masked_fill(~mt, float("inf"))
        idx = score.topk(kc, dim=1, largest=False).indices               # (R,kc)
        feas_c = mt.gather(1, idx)
        capr = bt.capr[I, a]; lim = bt.tok_lim[a]
        dl_c = Dl[:, :n].gather(1, idx); ds_c = Ds.gather(1, idx)
        L_after = s.Lopen[:, None] + dl_c + ds_c
        e_slack = (capr[:, None] - (L_after / SPEED * FE + E_T * (s.m[:, None] + 1))) / capr[:, None].clamp(min=1e-6)
        t_slack = (lim[:, None] - (s.Tdone[ar, a][:, None] + L_after / SPEED + S_T * (s.m[:, None] + 1))) / 600.0
        ft = torch.stack([dl_c / 5000, ds_c / 5000, e_slack, t_slack, feas_c.float(), has[:, None].expand(-1, kc).float()], -1)
        ht = h[I[:, None], idx] + self.dyn_t(ft)
        Dk = Dl[:, n + bt.tok_st]
        unv = (~s.visited).float()
        covfrac = (bt.single_ok[I].float() * unv[:, None, :]).sum(-1) / unv.sum(1, keepdim=True).clamp(min=1)
        fk = torch.stack([s.Tdone / bt.tok_lim[None], (s.active[:, None] == torch.arange(K, device=bt.dev)[None]).float(),
                          Dk / 5000, mk.float(), covfrac, bt.tok_open[I].float()], -1)
        hk = h[I, n:] + self.dyn_k(fk)
        glob = torch.stack([s.Lopen / 10000, s.m / 4, s.Tdone[ar, a] / lim, capr, s.visited.float().mean(1),
                            has.float(), s.need_t.float(), bt.reserve[I] * 5], 1)
        q = self.ctx(torch.cat([self._gm[I], tok_h, last_h, glob], 1))
        seq = torch.cat([q[:, None], ht, hk], 1)
        pad = torch.cat([torch.zeros(R, 1, dtype=torch.bool, device=bt.dev), ~feas_c, ~mk], 1)
        for l in self.dec:
            seq = l(seq, src_key_padding_mask=pad)
        seq = self.dec_norm(seq)
        qo = self.Wq(seq[:, 0]); ko = self.Wk(seq[:, 1:])
        lg = (ko * qo[:, None]).sum(-1) / math.sqrt(d)
        lg = 10 * torch.tanh(lg)
        bias_t = self.wb[0] * dl_c / 5000 + self.wb[1] * ds_c / 5000
        bias_k = self.wb[2] * Dk / 5000
        lt = (lg[:, :kc] + bias_t).masked_fill(~feas_c, -1e9)
        lk = (lg[:, kc:] + bias_k).masked_fill(~mk, -1e9)
        full = torch.full((R, n), -1e9, device=bt.dev, dtype=lt.dtype)
        full = full.scatter(1, idx, lt)
        out = torch.cat([full, lk], 1)
        return out.float().masked_fill(~mask, -1e9)

    def prep(self, h):
        self._gm = h.mean(1)


def rollout(pol, bt, greedy=False, force=None, h=None, temp=1.0, record=True):
    """Sample/greedy rollouts without grad. Returns dict(F, cost, mk, acts (R,T), fail, state)."""
    with torch.no_grad():
        if h is None:
            h = pol.encode(bt)
        pol.prep(h)
        s = State(bt, force=force)
        acts = []
        for t in range(4 * bt.n + 10):
            if bool(s.done.all()):
                break
            m = s.mask()
            stuck = ~s.done & ~m.any(1)
            if bool(stuck.any()):
                s.finish_fail(stuck); m = s.mask()
            lg = pol.step_logits(h, bt, s, m)
            if greedy:
                a = lg.argmax(-1)
            else:
                a = torch.multinomial(torch.softmax(lg / temp, -1), 1).squeeze(1)
            a = torch.where(s.done, torch.zeros_like(a), a)
            acts.append(torch.where(s.done, torch.full_like(a, -1), a))
            s.step(a)
        F, cost, mk = s.objective()
    A = torch.stack(acts, 1) if acts else torch.zeros(s.R, 0, dtype=torch.long, device=bt.dev)
    return dict(F=F, cost=cost, mk=mk, acts=A, fail=s.fail.clone(), state=s)


def replay_grad(pol, bt, acts, weight, force=None, h=None, hd=None, ent_coef=0.0, chunk=16, extra_logp_weight=None):
    """Gradient pass: replay recorded actions; loss = sum_t [ weight * (-logp_t) - ent_coef * H_t ] / R.
    weight (R,) already contains the advantage sign (REINFORCE: weight = advantage). Backprops in chunks into the
    decoder params and into hd (detached encoder output); caller then does h.backward(hd.grad).
    Returns (mean logp, mean entropy)."""
    s = State(bt, force=force)
    pol.prep(hd)
    R = s.R; T = acts.shape[1]
    tot_lp = 0.0; tot_ent = 0.0; nlive = 0
    loss = 0.0; k = 0
    for t in range(T):
        if bool(s.done.all()):
            break
        m = s.mask()
        stuck = ~s.done & ~m.any(1)
        if bool(stuck.any()):
            s.finish_fail(stuck); m = s.mask()
        live = (~s.done).float()
        a = acts[:, t].clamp(min=0)
        lg = pol.step_logits(hd, bt, s, m)
        lp = torch.log_softmax(lg, -1)
        lpa = lp.gather(1, a[:, None]).squeeze(1) * live
        p = lp.exp()
        ent = -(p * lp.clamp(min=-1e4)).sum(-1) * live
        loss = loss + (weight * (-lpa)).sum() / R - ent_coef * ent.sum() / R
        tot_lp += float(lpa.detach().sum()); tot_ent += float(ent.detach().sum()); nlive += float(live.sum())
        k += 1
        if k == chunk:
            loss.backward(retain_graph=False); loss = 0.0; k = 0; pol.prep(hd)
        s.step(a)
    if k:
        loss.backward()
    return tot_lp / max(R, 1), tot_ent / max(nlive, 1)


def save_route(pol, path, **extra):
    from .common import atomic_save
    atomic_save(dict(cfg=pol.cfg, sd=pol.state_dict(), **extra), path)


def load_route(path, dev="cpu"):
    ck = torch.load(path, map_location=dev)
    pol = RoutePolicy(**ck["cfg"]).to(dev)
    pol.load_state_dict(ck["sd"]); pol.eval()
    return pol, ck
