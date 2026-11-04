import torch, torch.nn as nn
from .feats import N_FEAT, N_LOCAL, N_GLOBAL
from carl.actions import N_OPERATORS
LOC0 = N_OPERATORS + 3
LOC1 = LOC0 + N_LOCAL
G0 = LOC1
class Scorer(nn.Module):
    """Per-candidate scorer; input = raw features + group-centred local features.
    FiLM conditioning on (lambda, reserve, risk) when film=True."""
    def __init__(self, hid=64, film=True, cond=True):
        super().__init__()
        self.film = film; self.cond = cond
        din = N_FEAT + N_LOCAL
        self.l1 = nn.Linear(din, hid); self.l2 = nn.Linear(hid, hid); self.out = nn.Linear(hid, 1)
        if film:
            self.f = nn.Sequential(nn.Linear(3, 32), nn.ReLU(), nn.Linear(32, 4 * hid))
        self.act = nn.ReLU()
    def forward(self, X, valid):
        # X: (B,G,F) valid: (B,G) bool
        X = X.clone()
        if not self.cond:
            X[..., G0:G0 + 3] = 0.0
        loc = X[..., LOC0:LOC1]
        w = valid.float().unsqueeze(-1)
        mean = (loc * w).sum(1, keepdim=True) / w.sum(1, keepdim=True).clamp(min=1)
        h = torch.cat([X, loc - mean], -1)
        h1 = self.l1(h); 
        if self.film:
            c = X[:, 0, G0:G0 + 3]
            g1, b1, g2, b2 = self.f(c).chunk(4, -1)
            h1 = h1 * (1 + g1.unsqueeze(1)) + b1.unsqueeze(1)
        h1 = self.act(h1)
        h2 = self.l2(h1)
        if self.film:
            h2 = h2 * (1 + g2.unsqueeze(1)) + b2.unsqueeze(1)
        h2 = self.act(h2)
        s = self.out(h2).squeeze(-1)
        return s.masked_fill(~valid, -1e9)
