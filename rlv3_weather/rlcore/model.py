"""Attention pointer policy over the candidate set (Kool et al. 2019 / POMO-style encoder-decoder, re-encoded at every
decision because all features are dynamic).  Invalid actions are removed by masking logits (Huang & Ontanon 2022) -
the mask is the physics shield, so the policy can never select an energy-infeasible or storm-blocked node."""
import torch, torch.nn as nn
from .feat import F_T, F_C


class Policy(nn.Module):
    def __init__(self, d=128, heads=8, layers=3, clip=10.0):
        super().__init__()
        self.tok = nn.Sequential(nn.Linear(F_T, d), nn.ReLU(), nn.Linear(d, d))
        self.ctx = nn.Sequential(nn.Linear(F_C, d), nn.ReLU(), nn.Linear(d, d))
        enc = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.0, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(enc, layers, enable_nested_tensor=False)
        self.q = nn.Linear(2 * d, d); self.k = nn.Linear(d, d)
        self.clip = clip; self.d = d

    def forward(self, tok, ctx, mask):
        """tok (B,N,F_T) ctx (B,F_C) mask (B,N) bool (True = legal; padded = False). returns logits (B,N)."""
        h = self.tok(tok)
        c = self.ctx(ctx).unsqueeze(1)
        x = torch.cat([c, h], 1)
        pad = torch.cat([torch.zeros_like(mask[:, :1]), ~mask], 1)   # attend only to legal tokens (+ context)
        x = self.enc(x, src_key_padding_mask=pad)
        g = torch.cat([x[:, 0], x[:, 1:].masked_fill(pad[:, 1:, None], 0).sum(1) / mask.sum(1, keepdim=True).clamp(min=1)], -1)
        q = self.q(g).unsqueeze(1)
        k = self.k(x[:, 1:])
        lg = (q * k).sum(-1) / self.d ** 0.5
        lg = self.clip * torch.tanh(lg)
        return lg.masked_fill(~mask, -1e9)


def collate(samples, device=None):
    """samples: list of (tok, ctx, mask) numpy -> padded tensors."""
    import numpy as np
    B = len(samples); N = max(s[0].shape[0] for s in samples)
    tok = np.zeros((B, N, F_T), np.float32); ctx = np.zeros((B, F_C), np.float32); m = np.zeros((B, N), bool)
    for b, (t, c, mk) in enumerate(samples):
        tok[b, :t.shape[0]] = t; ctx[b] = c; m[b, :mk.shape[0]] = mk
    tt = lambda a: torch.from_numpy(a).to(device) if device is not None else torch.from_numpy(a)
    return tt(tok), tt(ctx), tt(m)
