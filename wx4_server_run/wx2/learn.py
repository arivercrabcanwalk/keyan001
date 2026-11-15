"""Numpy MLP policy: BC, DAgger (rollout expert), REINFORCE-POMO (K shared baseline).

Network: 2x128 ReLU, global + per-action features, masked softmax.
No residual-around-a-rule, no operator selection. Direct logits.
"""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import math, json, os, time
import numpy as np
from .feat import features, NIN, NG, NA
from .sim import N_ACT, LAUNCH, HOLD, SERVE0, Sim
from . import const as C

EPS = 1e-8


def _relu(x):
    return np.maximum(x, 0.0)


def _softmax_masked(logits, mask):
    z = np.where(mask, logits, -1e9)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z) * mask
    s = e.sum(axis=-1, keepdims=True) + EPS
    return e / s


class PolicyNet:
    def __init__(self, rng, d=128, n_in=NIN):
        self.d = d
        self.n_in = n_in
        # two hidden layers on the GLOBAL part, then late fusion with action feats
        self.W1 = rng.normal(0, math.sqrt(2 / NG), (NG, d)).astype(np.float64)
        self.b1 = np.zeros(d)
        self.W2 = rng.normal(0, math.sqrt(2 / d), (d, d)).astype(np.float64)
        self.b2 = np.zeros(d)
        self.W3 = rng.normal(0, math.sqrt(2 / d), (d, N_ACT)).astype(np.float64)
        self.b3 = np.zeros(N_ACT)
        self.Wa = rng.normal(0, math.sqrt(2 / NA), (NA, 1)).astype(np.float64)
        self.ba = np.zeros(1)
        self._adam = {}
        self._t = 0

    def params(self):
        return dict(W1=self.W1.copy(), b1=self.b1.copy(), W2=self.W2.copy(), b2=self.b2.copy(),
                    W3=self.W3.copy(), b3=self.b3.copy(), Wa=self.Wa.copy(), ba=self.ba.copy())

    def load(self, p):
        for k, v in p.items():
            setattr(self, k, np.asarray(v, dtype=np.float64))

    def _fwd(self, X):
        """X: (B, NIN). Returns logits (B, 5) and cache."""
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None]
        g = X[:, :NG]
        af = X[:, NG:].reshape(-1, N_ACT, NA)
        h1 = _relu(g @ self.W1 + self.b1)
        h2 = _relu(h1 @ self.W2 + self.b2)
        logits = h2 @ self.W3 + self.b3  # (B, 5)
        logits = logits + (af @ self.Wa)[..., 0] + self.ba  # (B, 5)
        return logits, (g, af, h1, h2)

    def logits(self, X):
        return self._fwd(X)[0]

    def probs(self, X, mask):
        lg, _ = self._fwd(X)
        return _softmax_masked(lg, np.asarray(mask, dtype=np.float64))

    def act(self, x, mask, greedy=False, rng=None, temperature=1.0):
        if temperature != 1.0:
            lg, _ = self._fwd(x[None])
            p = _softmax_masked(lg / max(float(temperature), 1e-6), np.asarray(mask[None], dtype=np.float64))[0]
        else:
            p = self.probs(x[None], mask[None])[0]
        p = p * mask
        s = p.sum()
        if s <= 0:
            legal = np.flatnonzero(mask)
            return int(legal[0]) if len(legal) else 0, p
        p = p / s
        if greedy:
            return int(np.argmax(p)), p
        if rng is None:
            rng = np.random.default_rng()
        return int(rng.choice(N_ACT, p=p)), p

    def kl_from(self, other, X, mask):
        p = self.probs(X, mask)
        q = other.probs(X, mask)
        return float(np.sum(p * (np.log(p + EPS) - np.log(q + EPS)), axis=-1).mean())

    # ----- Adam -----
    def _slot(self, name, arr):
        if name not in self._adam:
            self._adam[name] = (np.zeros_like(arr), np.zeros_like(arr))
        return self._adam[name]

    def _upd(self, name, arr, g, lr, b1=0.9, b2=0.999, wd=1e-5):
        self._t += 0  # step is incremented once per step()
        m, v = self._slot(name, arr)
        m[:] = b1 * m + (1 - b1) * g
        v[:] = b2 * v + (1 - b2) * (g * g)
        t = max(self._t, 1)
        mh = m / (1 - b1 ** t)
        vh = v / (1 - b2 ** t)
        arr -= lr * (mh / (np.sqrt(vh) + 1e-8) + wd * arr)

    def step(self, grads, lr=3e-4):
        self._t += 1
        for name in ("W1", "b1", "W2", "b2", "W3", "b3", "Wa", "ba"):
            self._upd(name, getattr(self, name), grads[name], lr)

    def backward(self, X, mask, actions, weights, ent_coef=0.0):
        """REINFORCE / BC gradient. weights = advantages (or 1 for BC).
        loss = mean(w * (-log pi(a)) ) - ent_coef * entropy.
        Returns grads dict and diagnostics.
        """
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None]
        mask = np.asarray(mask, dtype=np.float64)
        actions = np.asarray(actions, dtype=int)
        w = np.asarray(weights, dtype=np.float64)
        B = len(X)
        logits, (g, af, h1, h2) = self._fwd(X)
        p = _softmax_masked(logits, mask)
        logp = np.log(p[np.arange(B), actions] + EPS)
        ent = -(p * np.log(p + EPS) * mask).sum(-1)
        # dL/dlogits
        # d(-log p_a)/dlogits = p - onehot(a)
        one = np.zeros_like(p)
        one[np.arange(B), actions] = 1.0
        dlog = (p - one)  # for -logp
        # entropy grad: d(-H)/dlogits ... we want to MAXIMIZE ent, so loss has -ent_coef*H
        # H = -sum p log p, dH/dlogits_i = -p_i * (log p_i + H-related); use
        # dH/dz = -p * (log p - sum p log p)  (for unmasked softmax)
        logp_all = np.log(p + EPS)
        dH = -p * (logp_all - (p * logp_all * mask).sum(-1, keepdims=True))
        dH *= mask
        dlogits = (w[:, None] * dlog) / max(B, 1) - (ent_coef * dH) / max(B, 1)
        dlogits *= mask
        # backprop
        # logits = h2 @ W3 + b3 + (af @ Wa)[...,0] + ba
        dW3 = h2.T @ dlogits
        db3 = dlogits.sum(0)
        dh2 = dlogits @ self.W3.T
        dWa = np.zeros_like(self.Wa)
        for k in range(N_ACT):
            dWa += af[:, k, :].T @ dlogits[:, k][:, None]
        dba = dlogits.sum() * np.ones(1)  # ba is scalar added to all, actually ba is (1,)
        dba = np.array([dlogits.sum()])
        # relu h2
        dh2 *= (h2 > 0)
        dW2 = h1.T @ dh2
        db2 = dh2.sum(0)
        dh1 = dh2 @ self.W2.T
        dh1 *= (h1 > 0)
        dW1 = g.T @ dh1
        db1 = dh1.sum(0)
        grads = dict(W1=dW1, b1=db1, W2=dW2, b2=db2, W3=dW3, b3=db3, Wa=dWa, ba=dba)
        diag = dict(loss=float((-w * logp).mean() - ent_coef * ent.mean()),
                    ent=float(ent.mean()), logp=float(logp.mean()),
                    acc=float((np.argmax(p, 1) == actions).mean()))
        return grads, diag

    def backward_ppo(self, X, mask, actions, advantages, old_logp,
                     ent_coef=0.0, clip_eps=0.2, ref_probs=None, kl_coef=0.0):
        """PPO-clip objective for cost-minimization (advantages already signed:
        positive A = better than baseline = lower J).

        L = -mean(min(r*A, clip(r,1-ε,1+ε)*A)) - ent_coef*H + kl_coef*KL(π||π_ref)
        r = exp(logπ(a) - logπ_old(a))
        """
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None]
        mask = np.asarray(mask, dtype=np.float64)
        actions = np.asarray(actions, dtype=int)
        adv = np.asarray(advantages, dtype=np.float64)
        old_logp = np.asarray(old_logp, dtype=np.float64)
        B = len(X)
        logits, (g, af, h1, h2) = self._fwd(X)
        p = _softmax_masked(logits, mask)
        logp = np.log(p[np.arange(B), actions] + EPS)
        ratio = np.exp(np.clip(logp - old_logp, -20.0, 20.0))
        r_clip = np.clip(ratio, 1.0 - clip_eps, 1.0 + clip_eps)
        obj1 = ratio * adv
        obj2 = r_clip * adv
        use_unclipped = obj1 <= obj2  # pessimistic min; False => clip active, grad 0 wrt r
        obj = np.where(use_unclipped, obj1, obj2)
        ent = -(p * np.log(p + EPS) * mask).sum(-1)
        # d(-obj)/d logp  = -A*r  if unclipped else 0
        dL_dlogp = np.where(use_unclipped, -adv * ratio, 0.0) / max(B, 1)
        one = np.zeros_like(p)
        one[np.arange(B), actions] = 1.0
        # d logp / d logits = one - p
        dlogits = dL_dlogp[:, None] * (one - p)
        # entropy: loss has -ent_coef * H, same as backward()
        logp_all = np.log(p + EPS)
        dH = -p * (logp_all - (p * logp_all * mask).sum(-1, keepdims=True))
        dH *= mask
        dlogits -= (ent_coef * dH) / max(B, 1)
        kl = 0.0
        if ref_probs is not None and kl_coef:
            ref = np.asarray(ref_probs, dtype=np.float64) + EPS
            ref = ref / ref.sum(-1, keepdims=True)
            # KL(π||ref) = sum π (log π - log ref)
            kl_ia = p * (logp_all - np.log(ref)) * mask
            kl_i = kl_ia.sum(-1)
            kl = float(kl_i.mean())
            # dKL/dz_j = p_j * (log(p_j/ref_j) - KL_i)
            log_ratio = (logp_all - np.log(ref)) * mask
            dKL = p * (log_ratio - kl_i[:, None])
            dKL *= mask
            dlogits += (kl_coef * dKL) / max(B, 1)
        dlogits *= mask
        # same backprop as backward()
        dW3 = h2.T @ dlogits
        db3 = dlogits.sum(0)
        dh2 = dlogits @ self.W3.T
        dWa = np.zeros_like(self.Wa)
        for k in range(N_ACT):
            dWa += af[:, k, :].T @ dlogits[:, k][:, None]
        dba = np.array([dlogits.sum()])
        dh2 *= (h2 > 0)
        dW2 = h1.T @ dh2
        db2 = dh2.sum(0)
        dh1 = dh2 @ self.W2.T
        dh1 *= (h1 > 0)
        dW1 = g.T @ dh1
        db1 = dh1.sum(0)
        grads = dict(W1=dW1, b1=db1, W2=dW2, b2=db2, W3=dW3, b3=db3, Wa=dWa, ba=dba)
        frac_clip = float((~use_unclipped).mean())
        diag = dict(loss=float(-obj.mean() - ent_coef * ent.mean() + kl_coef * kl),
                    ent=float(ent.mean()), logp=float(logp.mean()),
                    acc=float((np.argmax(p, 1) == actions).mean()),
                    ratio=float(ratio.mean()), frac_clip=frac_clip,
                    kl_ref=kl, adv_mean=float(adv.mean()), adv_std=float(adv.std()),
                    adv_min=float(adv.min()), adv_max=float(adv.max()))
        return grads, diag

    def reset_adam(self):
        self._t = 0
        self._adam = {}

    def snapshot(self):
        return self.params(), self._t, {k: (m.copy(), v.copy()) for k, (m, v) in self._adam.items()}

    def restore(self, snap):
        params, t, adam = snap
        self.load(params)
        self._t = t
        self._adam = {k: (m.copy(), v.copy()) for k, (m, v) in adam.items()}


def grad_norm(grads):
    return float(np.sqrt(sum(np.sum(g * g) for g in grads.values())))


def clip_grads(grads, max_norm=1.0):
    n = grad_norm(grads)
    if n > max_norm and n > 0:
        s = max_norm / n
        grads = {k: g * s for k, g in grads.items()}
    return n, grads


def kl_div(net, other, X, mask):
    """mean KL(net || other) on a batch."""
    p = net.probs(X, mask)
    q = other.probs(X, mask)
    return float(np.sum(p * (np.log(p + EPS) - np.log(q + EPS)), axis=-1).mean())


def make_policy(net, greedy=True, rng=None, record_kl_vs=None):
    """Return a sim-compatible policy closure. Optionally logs (x, a, mask)."""
    buf = []

    def pol(sim, i, mask, cands, info):
        x = features(sim, i, mask, cands, info)
        a, p = net.act(x, mask.astype(np.float64), greedy=greedy, rng=rng)
        buf.append((x, a, mask.copy(), p.copy()))
        return a
    pol.buf = buf
    pol.net = net
    return pol


def save_net(net, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    np.savez(path, **net.params(), t=net._t)


def load_net(path, rng=None):
    z = np.load(path, allow_pickle=False)
    rng = rng or np.random.default_rng(0)
    net = PolicyNet(rng)
    net.load({k: z[k] for k in ("W1", "b1", "W2", "b2", "W3", "b3", "Wa", "ba")})
    if "t" in z:
        net._t = int(z["t"])
    return net



class ValueNet:
    """Scalar complete-day J predictor from decision features. 2x128 ReLU, MSE."""

    def __init__(self, rng, d=128, n_in=NIN):
        self.d = d
        self.n_in = n_in
        self.W1 = rng.normal(0, math.sqrt(2 / n_in), (n_in, d)).astype(np.float64)
        self.b1 = np.zeros(d)
        self.W2 = rng.normal(0, math.sqrt(2 / d), (d, d)).astype(np.float64)
        self.b2 = np.zeros(d)
        self.W3 = rng.normal(0, math.sqrt(2 / d), (d, 1)).astype(np.float64)
        self.b3 = np.zeros(1)
        self._adam = {}
        self._t = 0

    def params(self):
        return dict(W1=self.W1.copy(), b1=self.b1.copy(), W2=self.W2.copy(), b2=self.b2.copy(),
                    W3=self.W3.copy(), b3=self.b3.copy())

    def load(self, p):
        for k, v in p.items():
            if hasattr(self, k):
                setattr(self, k, np.asarray(v, dtype=np.float64))

    def _fwd(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None]
        h1 = _relu(X @ self.W1 + self.b1)
        h2 = _relu(h1 @ self.W2 + self.b2)
        y = (h2 @ self.W3 + self.b3)[:, 0]
        return y, (X, h1, h2)

    def predict(self, X):
        return self._fwd(X)[0]

    def _slot(self, name, arr):
        if name not in self._adam:
            self._adam[name] = (np.zeros_like(arr), np.zeros_like(arr))
        return self._adam[name]

    def _upd(self, name, arr, g, lr, b1=0.9, b2=0.999, wd=1e-5):
        m, v = self._slot(name, arr)
        m[:] = b1 * m + (1 - b1) * g
        v[:] = b2 * v + (1 - b2) * (g * g)
        t = max(self._t, 1)
        mh = m / (1 - b1 ** t)
        vh = v / (1 - b2 ** t)
        arr -= lr * (mh / (np.sqrt(vh) + 1e-8) + wd * arr)

    def step(self, grads, lr=1e-3):
        self._t += 1
        for name in ("W1", "b1", "W2", "b2", "W3", "b3"):
            self._upd(name, getattr(self, name), grads[name], lr)

    def backward(self, X, y):
        y = np.asarray(y, dtype=np.float64).reshape(-1)
        pred, (X, h1, h2) = self._fwd(X)
        B = max(len(y), 1)
        err = pred - y
        loss = float((err * err).mean())
        dy = (2.0 / B) * err  # (B,)
        dW3 = h2.T @ dy[:, None]
        db3 = dy.sum(0, keepdims=True) if False else np.array([dy.sum()])
        dh2 = dy[:, None] @ self.W3.T
        dh2 *= (h2 > 0)
        dW2 = h1.T @ dh2
        db2 = dh2.sum(0)
        dh1 = dh2 @ self.W2.T
        dh1 *= (h1 > 0)
        dW1 = X.T @ dh1
        db1 = dh1.sum(0)
        grads = dict(W1=dW1, b1=db1, W2=dW2, b2=db2, W3=dW3, b3=db3)
        return grads, dict(loss=loss, mae=float(np.abs(err).mean()))

    def fit(self, X, y, epochs=8, lr=1e-3, batch=256, rng=None):
        rng = rng or np.random.default_rng(0)
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64).reshape(-1)
        n = len(y)
        hist = []
        for ep in range(epochs):
            idx = rng.permutation(n)
            last = {}
            for s in range(0, n, batch):
                sl = idx[s:s + batch]
                grads, diag = self.backward(X[sl], y[sl])
                self.step(grads, lr=lr)
                last = diag
            hist.append(last)
        return hist


def save_value(net, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    np.savez(path, **net.params(), t=net._t)


def load_value(path, rng=None):
    z = np.load(path, allow_pickle=False)
    rng = rng or np.random.default_rng(0)
    net = ValueNet(rng)
    net.load({k: z[k] for k in ("W1", "b1", "W2", "b2", "W3", "b3")})
    if "t" in z:
        net._t = int(z["t"])
    return net
