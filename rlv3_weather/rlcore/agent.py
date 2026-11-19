"""RL policy wrapper usable by the simulator workers (CPU, single thread)."""
import numpy as np
import torch
from .feat import featurize
from .model import Policy, collate

PHYS_COLS = list(range(13, 19))          # eta / xi / eta(+30) / eta(measured)
PHYS_CTX = list(range(8, 16))


def ablate(tok, ctx, kind):
    if kind == "nophys":
        tok[:, PHYS_COLS] = 0.0; ctx[PHYS_CTX] = 0.0
    return tok, ctx


_CACHE = {}


def load_policy(path):
    """returns (model, feat_ablate, base_spec)"""
    if path not in _CACHE:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        m = Policy(**ck.get("arch", {})); m.load_state_dict(ck["model"]); m.eval()
        _CACHE[path] = (m, ck.get("feat_ablate", "none"), ck.get("base", "none"))
    return _CACHE[path]


class RLPolicy:
    """base: spec of a non-RL policy run in shadow mode whose current choice is shown to the network as a token flag
    ('learning to improve a heuristic'); 'none' = pure end-to-end policy (ablation ABL_nobase)."""

    def __init__(self, model, feat_ablate="none", greedy=True, temp=1.0, rng=None, collect=False, name="RL", base="none"):
        self.m = model; self.fa = feat_ablate; self.greedy = greedy; self.temp = temp
        self.rng = rng or np.random.default_rng(0); self.collect = collect; self.name = name
        self.base_spec = base
        torch.set_num_threads(1)

    def reset(self, env):
        self.buf = []
        self.base = None
        if self.base_spec and self.base_spec != "none":
            from . import policies as PO
            self.base = PO.make(self.base_spec); self.base.reset(env)

    @torch.no_grad()
    def act(self, env, cur):
        sug = self.base.act(env, cur) if self.base is not None else None
        tok, ctx, mask, acts = featurize(env, cur, sug)
        tok, ctx = ablate(tok, ctx, self.fa)
        t, c, m = collate([(tok, ctx, mask)])
        lg = self.m(t, c, m)[0].numpy().astype(np.float64)
        if self.greedy:
            k = int(np.argmax(lg))
        else:
            z = lg / self.temp; z = z - z.max(); p = np.exp(z) * mask; p /= p.sum()
            k = int(self.rng.choice(len(p), p=p))
        if self.collect:
            d = cur[0]
            self.buf.append((tok, ctx, mask, k, d["st"], float(tok[k, 13]) if k < len(acts) - 2 else 0.0))
        return acts[k]
