"""RL6 policy network: shared action-token scorer (permutation-equivariant over the SERVE slots).

  logit_a = w3 . relu(W2 relu(W1 x_a + b1) + b2) + b3,   x_a = [g, A_a, onehot(type_a)]   (v6/feat6.tokens)
  pi(a|s) = masked softmax over the legal actions (sim mask after the shift shield).
Pure numpy forward (about 0.05 ms per decision) so the dispatcher runs on one CPU core in real time; manual backprop
for the distillation loss (soft-target cross-entropy) - verified by a finite-difference test (tests/test_net6.py).
Parameters are flattened for the constrained ES fine-tuning (run_es6.py).
"""
import numpy as np
from . import feat6 as F6, shield as SH
from wx2.sim import HOLD, LAUNCH, SERVE0, N_ACT

KEYS = ("W1", "b1", "W2", "b2", "w3", "b3")


class Net6:
    def __init__(self, seed=0, d1=96, d2=64, nin=F6.NTOK):
        r = np.random.default_rng(seed)
        self.p = dict(W1=r.normal(0, np.sqrt(2.0 / nin), (nin, d1)), b1=np.zeros(d1),
                      W2=r.normal(0, np.sqrt(2.0 / d1), (d1, d2)), b2=np.zeros(d2),
                      w3=r.normal(0, 0.01, d2), b3=np.zeros(1))
        self.fmask = None      # optional [N_ACT, NTOK] ablation mask
        self.meta = dict(d1=d1, d2=d2, nin=nin, version="net6.1")

    # ---------- forward ----------
    def logits(self, X):
        """X: [..., N_ACT, NTOK] -> logits [..., N_ACT]."""
        if self.fmask is not None:
            X = X * self.fmask
        p = self.p
        h1 = np.maximum(X @ p["W1"] + p["b1"], 0.0)
        h2 = np.maximum(h1 @ p["W2"] + p["b2"], 0.0)
        return h2 @ p["w3"] + p["b3"][0]

    @staticmethod
    def masked_softmax(z, mask):
        z = np.where(mask, z, -1e9)
        z = z - z.max(-1, keepdims=True)
        e = np.exp(z) * mask
        return e / np.maximum(e.sum(-1, keepdims=True), 1e-12)

    # ---------- loss / backprop (soft-target CE, per-sample weights) ----------
    def loss_grad(self, X, mask, target, w=None, l2=1e-5):
        """X [B,A,F], mask [B,A] bool, target [B,A] (prob over legal), w [B]. Returns (loss, grads)."""
        p = self.p
        Xm = X * self.fmask if self.fmask is not None else X
        a1 = Xm @ p["W1"] + p["b1"]; h1 = np.maximum(a1, 0.0)
        a2 = h1 @ p["W2"] + p["b2"]; h2 = np.maximum(a2, 0.0)
        z = h2 @ p["w3"] + p["b3"][0]
        pr = self.masked_softmax(z, mask)
        B = X.shape[0]
        w = np.ones(B) if w is None else w
        logp = np.log(np.maximum(pr, 1e-12))
        loss = float(-(w[:, None] * target * np.where(mask, logp, 0.0)).sum() / B)
        dz = (pr - target) * mask * w[:, None] / B                 # [B,A]
        g = {}
        g["w3"] = np.einsum("ba,bad->d", dz, h2)
        g["b3"] = np.array([dz.sum()])
        dh2 = dz[..., None] * p["w3"][None, None, :]
        da2 = dh2 * (a2 > 0)
        g["W2"] = np.einsum("bai,baj->ij", h1, da2)
        g["b2"] = da2.sum((0, 1))
        dh1 = da2 @ p["W2"].T
        da1 = dh1 * (a1 > 0)
        g["W1"] = np.einsum("bai,baj->ij", Xm, da1)
        g["b1"] = da1.sum((0, 1))
        for k in ("W1", "W2"):
            loss += 0.5 * l2 * float((p[k] ** 2).sum()); g[k] = g[k] + l2 * p[k]
        return loss, g

    # ---------- flatten (ES) ----------
    def flat(self):
        return np.concatenate([self.p[k].ravel() for k in KEYS])

    def shapes(self):
        return [(k, self.p[k].shape) for k in KEYS]

    def set_flat(self, v):
        o = 0
        for k, sh in self.shapes():
            n = int(np.prod(sh)); self.p[k] = v[o:o + n].reshape(sh).copy(); o += n


def save(net, path, **meta):
    m = dict(net.meta); m.update(meta)
    import json, os
    tmp = path + ".tmp.npz"
    np.savez(tmp, meta=json.dumps(m), fmask=(net.fmask if net.fmask is not None else np.zeros(0)), **net.p)
    os.replace(tmp, path)


_LOADED = {}


def load(path):
    if path in _LOADED:
        return _LOADED[path]
    import json
    z = np.load(path, allow_pickle=False)
    m = json.loads(str(z["meta"]))
    net = Net6(0, m["d1"], m["d2"], m["nin"])
    for k in KEYS:
        net.p[k] = z[k].astype(np.float64)
    fm = z["fmask"]
    net.fmask = fm if fm.size else None
    net.meta = m
    _LOADED[path] = net
    return net


def make_policy(net, shield=True, greedy=True, rng=None, fmask=None, record=None):
    """Policy callable for wx2.sim. record: optional list collecting (X, mask, action) for analysis."""
    if fmask is not None:
        net.fmask = F6.ablation_mask(fmask) if isinstance(fmask, str) else fmask

    def pol(sim, i, mask, cands, info):
        on = False
        if shield and mask[HOLD] and SH.violates(sim, i, info):
            mask = mask.copy(); mask[HOLD] = False; on = True
            sim.n_shield = getattr(sim, "n_shield", 0) + 1
        legal = np.flatnonzero(mask)
        if len(legal) == 1:
            return int(legal[0])
        g, A = F6.features(sim, i, mask, cands, info, shield_on=on)
        X = F6.tokens(g, A)
        z = net.logits(X)
        if greedy:
            zz = np.where(mask, z, -np.inf)
            a = int(np.argmax(zz))
        else:
            pr = Net6.masked_softmax(z, mask)
            a = int((rng or np.random.default_rng()).choice(len(pr), p=pr))
        if record is not None:
            record.append((X, mask.copy(), a))
        return a
    return pol
