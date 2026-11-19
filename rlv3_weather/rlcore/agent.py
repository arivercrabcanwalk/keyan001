"""RL policy wrapper usable by the simulator workers (CPU, single thread)."""
import os
import numpy as np
import torch
from .feat import featurize
from .model import Policy, collate

PHYS_COLS = list(range(13, 19))          # eta / xi / eta(+30) / eta(measured)
PHYS_CTX = list(range(8, 16))
LEARNING_SCHEMA = "physical_route_reinforce_v2"
ABLATIONS = {"none", "nophys", "noplan", "nophys_noplan"}


def ablate(tok, ctx, kind):
    if kind not in ABLATIONS:
        raise ValueError(f"unknown feature ablation: {kind}")
    tok, ctx = tok.copy(), ctx.copy()
    if kind in ("nophys", "nophys_noplan"):
        tok[:, PHYS_COLS] = 0.0; ctx[PHYS_CTX] = 0.0
    if kind in ("noplan", "nophys_noplan"):
        tok[:, 21:24] = 0.0
    return tok, ctx


_CACHE = {}


def load_policy(path):
    """returns (model, feat_ablate, base_spec)"""
    path = os.path.abspath(path)
    st = os.stat(path)
    identity = (path, st.st_mtime_ns, st.st_size)
    if identity not in _CACHE:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        if ck.get("learning_schema") != LEARNING_SCHEMA:
            raise ValueError("checkpoint learning schema is unverified; use an audited v2 checkpoint")
        m = Policy(**ck.get("arch", {})); m.load_state_dict(ck["model"]); m.eval()
        _CACHE.clear()
        _CACHE[identity] = (m, ck["feat_ablate"], ck["base"])
    return _CACHE[identity]


def action_log_probs(logits, mask, temperature=1.0):
    """The identical float64 distribution is used for sampling and score replay."""
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    if not mask.any(dim=-1).all():
        raise ValueError("state has no legal physical action")
    return torch.log_softmax((logits.double() / temperature).masked_fill(~mask, -torch.inf), dim=-1)


class RLPolicy:
    """base: spec of a non-RL policy run in shadow mode whose current choice is shown to the network as a token flag
    ('learning with a heuristic hint'); 'none' removes that online suggestion.
    Author-plan features remain unless feat_ablate='noplan'."""

    def __init__(self, model, feat_ablate="none", greedy=True, temp=1.0, rng=None, collect=False, name="RL", base="none"):
        self.m = model; self.fa = feat_ablate; self.greedy = greedy; self.temp = temp
        self.rng = rng or np.random.default_rng(0); self.collect = collect; self.name = name
        self.base_spec = base
        if not np.isfinite(temp) or temp <= 0:
            raise ValueError("temperature must be finite and positive")
        if feat_ablate not in ABLATIONS:
            raise ValueError(f"unknown feature ablation: {feat_ablate}")
        self.m.eval()
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
        lg = self.m(t, c, m)
        logp = action_log_probs(lg, m, self.temp)[0].numpy()
        if self.greedy:
            k = int(np.argmax(logp))
        else:
            p = np.exp(logp)
            k = int(self.rng.choice(len(p), p=p))
        if self.collect:
            d = cur[0]
            self.buf.append((tok, ctx, mask, k, d["st"], float(tok[k, 13]) if k < len(acts) - 2 else 0.0))
        return acts[k]
