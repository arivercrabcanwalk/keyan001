"""pi_site: learned station siting & typing (set decision), DRLHQ-style heterogeneous encoder.
Encoder: target tokens + station tokens (coverage statistics), L layers. Decoder: autoregressive over stations in a
(randomly permuted during training = POMO-style diverse starts) order; at every step a 1-layer "decision
transformer" re-reads all stations with their current decision embeddings (closed/SABS/DABS/undecided) and emits
3 logits {close, SABS, DABS} for the current station. A coverage mask guarantees every target stays coverable."""
import math, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
from .common import SR, LR, SPEED, FE, E_T, SB, LB, SABS_FIX, DABS_FIX


def _layer(d, h, ff):
    return nn.TransformerEncoderLayer(d, h, ff, 0.0, batch_first=True, norm_first=True, activation="gelu")


def cover_tensors(tg, st):
    """tg (B,n,2), st (B,ns,2) tensors -> c_s, c_d (B,ns,n) bool, dist (B,ns,n)."""
    d = torch.cdist(st, tg)
    c_s = (d <= SR + 1e-6) & (2 * d / SPEED * FE + E_T <= SB + 1e-9)
    c_d = (d <= LR + 1e-6) & (2 * d / SPEED * FE + E_T <= LB + 1e-9)
    return c_s, c_d, d


class SitePolicy(nn.Module):
    def __init__(self, d=128, h=8, layers=4):
        super().__init__()
        self.cfg = dict(d=d, h=h, layers=layers)
        self.d = d
        self.emb_t = nn.Linear(5, d); self.emb_s = nn.Linear(8, d)
        self.enc = nn.ModuleList([_layer(d, h, 4 * d) for _ in range(layers)])
        self.norm = nn.LayerNorm(d)
        self.dec_emb = nn.Embedding(5, d)          # 0 closed, 1 SABS, 2 DABS, 3 undecided, 4 current
        self.dec = _layer(d, h, 4 * d)
        self.head = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, 3))

    def encode(self, tg, st):
        B, n, _ = tg.shape; ns = st.shape[1]
        xy = torch.cat([tg, st], 1)
        lo = xy.min(1, keepdim=True).values; span = (xy.max(1, keepdim=True).values - lo).amax(-1, keepdim=True).clamp(min=1.0)
        ntg = (tg - lo) / span; nst = (st - lo) / span
        c_s, c_d, dist = cover_tensors(tg, st)
        ncs = c_s.float().sum(1); ncd = c_d.float().sum(1)                      # (B,n) how many stations cover j
        ft = torch.cat([ntg, ncs[..., None] / 4, ncd[..., None] / 4, (ncd[..., None] <= 1).float()], -1)
        uniq_d = (c_d & (ncd[:, None] <= 1)).float().sum(-1) / max(n, 1)
        uniq_s = (c_s & (ncd[:, None] <= 1)).float().sum(-1) / max(n, 1)
        md = (dist * c_d).sum(-1) / c_d.float().sum(-1).clamp(min=1) / 5000
        fs = torch.cat([nst, (c_s.float().sum(-1) / max(n, 1))[..., None], (c_d.float().sum(-1) / max(n, 1))[..., None],
                        uniq_d[..., None], uniq_s[..., None], md[..., None],
                        torch.full((B, ns, 1), n / 100.0, device=tg.device)], -1)
        hx = torch.cat([self.emb_t(ft), self.emb_s(fs)], 1)
        for l in self.enc:
            hx = l(hx)
        hx = self.norm(hx)
        return hx[:, n:], hx[:, :n].mean(1), (c_s, c_d)

    def run(self, tg, st, M=1, greedy=False, order=None, forced=None, temp=1.0):
        """Construct sitings for each of B instances x M samples. Returns types (B*M, ns), logp (B*M,), ent (B*M,).
        forced (B*M, ns): teacher-forced decisions (imitation / evaluation of given sitings)."""
        hs, gm, (c_s, c_d) = self.encode(tg, st)
        B, ns, d = hs.shape; R = B * M; dev = tg.device
        I = torch.arange(B, device=dev).repeat_interleave(M)
        hs = hs[I]; gm = gm[I]; c_s = c_s[I]; c_d = c_d[I]
        if order is None:
            order = torch.stack([torch.randperm(ns, device=dev) if (not greedy or m > 0) else torch.arange(ns, device=dev)
                                 for _ in range(B) for m in range(M)])
        dec = torch.full((R, ns), 3, dtype=torch.long, device=dev)
        logp = torch.zeros(R, device=dev); ent = torch.zeros(R, device=dev)
        ar = torch.arange(R, device=dev)
        for k in range(ns):
            s = order[:, k]
            cur = dec.clone(); cur[ar, s] = 4
            x = self.dec(hs + self.dec_emb(cur))
            lg = self.head(torch.cat([x[ar, s], gm], -1))                     # (R,3)
            # coverage mask: potential cover after each option
            und = (dec == 3); und[ar, s] = False
            base = ((dec == 1)[..., None] & c_s) | ((dec == 2)[..., None] & c_d) | (und[..., None] & c_d)
            pot = base.any(1)                                                   # without s
            ok_close = pot.all(1)
            ok_sabs = (pot | c_s[ar, s]).all(1)
            m = torch.stack([ok_close, ok_sabs, torch.ones_like(ok_close)], 1)
            lg = lg.float().masked_fill(~m, -1e9)
            lp = torch.log_softmax(lg / temp, -1)
            if forced is not None:
                a = forced[ar, s]
            elif greedy:
                a = lp.argmax(-1)
                if M > 1:
                    smp = torch.multinomial(lp.exp(), 1).squeeze(1)
                    a = torch.where(torch.arange(R, device=dev) % M == 0, a, smp)
            else:
                a = torch.multinomial(lp.exp(), 1).squeeze(1)
            logp = logp + lp.gather(1, a[:, None]).squeeze(1)
            ent = ent - (lp.exp() * lp.clamp(min=-1e4)).sum(-1)
            dec[ar, s] = a
        return dec, logp, ent


def save_site(pol, path, **extra):
    from .common import atomic_save
    atomic_save(dict(cfg=pol.cfg, sd=pol.state_dict(), **extra), path)


def load_site(path, dev="cpu"):
    ck = torch.load(path, map_location=dev, weights_only=False)
    pol = SitePolicy(**ck["cfg"]).to(dev); pol.load_state_dict(ck["sd"]); pol.eval()
    return pol, ck
