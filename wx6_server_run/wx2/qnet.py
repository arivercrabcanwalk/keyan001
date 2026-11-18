"""WX3 QNet: state trunk + per-action MLP (state x action interaction), numpy + Adam.

z_k = v . relu([h2(g), af_k, onehot_k] @ Wq + bq) + c          (higher z = better action)
Trained by centred advantage regression (approximate policy iteration):
  target t_k = -(Q_k - mean_legal Q) / S  ;  pred_k = z_k - mean_legal z ;  Huber(pred - t)
Greedy policy = argmax z = argmin predicted cost-to-go.  Same act/probs interface as PolicyNet.
"""
from __future__ import annotations
import math, os
import numpy as np
from .feat import NG, NA, NIN, features
from .sim import N_ACT

EPS = 1e-8


def _relu(x):
    return np.maximum(x, 0.0)


def _softmax_masked(z, mask):
    z = np.where(mask > 0, z, -1e9)
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z) * (mask > 0)
    return e / (e.sum(-1, keepdims=True) + EPS)


class QNet:
    kind = "qnet"
    NAMES = ("W1", "b1", "W2", "b2", "Wq", "bq", "v", "c")

    def __init__(self, rng, d=128, dq=64, tau=1.0):
        self.d, self.dq, self.tau = d, dq, tau
        din = d + NA + N_ACT
        self.W1 = rng.normal(0, math.sqrt(2 / NG), (NG, d)); self.b1 = np.zeros(d)
        self.W2 = rng.normal(0, math.sqrt(2 / d), (d, d)); self.b2 = np.zeros(d)
        self.Wq = rng.normal(0, math.sqrt(2 / din), (din, dq)); self.bq = np.zeros(dq)
        self.v = rng.normal(0, math.sqrt(1 / dq), dq) * 0.1; self.c = np.zeros(1)
        self._adam = {}; self._t = 0

    def params(self):
        return {k: getattr(self, k).copy() for k in self.NAMES}

    def load(self, p):
        for k in self.NAMES:
            setattr(self, k, np.asarray(p[k], dtype=np.float64))
        self.d = self.W1.shape[1]; self.dq = self.Wq.shape[1]

    def _fwd(self, X):
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None]
        B = len(X)
        g = X[:, :NG]
        af = X[:, NG:].reshape(B, N_ACT, NA)
        h1 = _relu(g @ self.W1 + self.b1)
        h2 = _relu(h1 @ self.W2 + self.b2)
        oh = np.broadcast_to(np.eye(N_ACT), (B, N_ACT, N_ACT))
        u = np.concatenate([np.broadcast_to(h2[:, None, :], (B, N_ACT, self.d)), af, oh], -1)
        r = _relu(u @ self.Wq + self.bq)              # (B, A, dq)
        z = r @ self.v + self.c[0]                    # (B, A)
        return z, (g, h1, h2, u, r)

    def logits(self, X):
        return self._fwd(X)[0] / self.tau

    def probs(self, X, mask):
        return _softmax_masked(self.logits(X), np.asarray(mask, dtype=np.float64))

    def act(self, x, mask, greedy=False, rng=None, temperature=1.0):
        p = self.probs(x[None], mask[None])[0]
        if greedy:
            z = np.where(mask > 0, self._fwd(x[None])[0][0], -1e18)
            return int(np.argmax(z)), p
        rng = rng or np.random.default_rng()
        if temperature != 1.0:
            p = _softmax_masked(self.logits(x[None]) / temperature, mask[None].astype(float))[0]
        return int(rng.choice(N_ACT, p=p / p.sum())), p

    def _back(self, cache, dz):
        g, h1, h2, u, r = cache
        B = len(g)
        dv = np.einsum("bad,ba->d", r, dz)
        dc = np.array([dz.sum()])
        dr = dz[..., None] * self.v[None, None, :]
        dr *= (r > 0)
        dWq = np.einsum("bai,baj->ij", u, dr)
        dbq = dr.sum((0, 1))
        du = dr @ self.Wq.T
        dh2 = du[..., :self.d].sum(1)
        dh2 *= (h2 > 0)
        dW2 = h1.T @ dh2; db2 = dh2.sum(0)
        dh1 = dh2 @ self.W2.T; dh1 *= (h1 > 0)
        dW1 = g.T @ dh1; db1 = dh1.sum(0)
        return dict(W1=dW1, b1=db1, W2=dW2, b2=db2, Wq=dWq, bq=dbq, v=dv, c=dc)

    def loss_grad(self, X, mask, T, w=None, delta=1.0):
        """Centred advantage regression. T: (B,A) targets (already centred, NaN-free on legal)."""
        z, cache = self._fwd(X)
        m = np.asarray(mask, dtype=np.float64)
        n = m.sum(1, keepdims=True).clip(1)
        zc = z - (z * m).sum(1, keepdims=True) / n
        e = (zc - T) * m
        h = np.clip(e, -delta, delta)                    # Huber derivative
        lossv = np.where(np.abs(e) <= delta, 0.5 * e * e, delta * (np.abs(e) - 0.5 * delta)) * m
        wv = np.ones(len(X)) if w is None else np.asarray(w, float)
        B = len(X)
        hn = h / n
        dzc = hn * wv[:, None] / B
        dz = (dzc - (dzc * m).sum(1, keepdims=True) / n) * m
        grads = self._back(cache, dz)
        # ranking accuracy: does argmax z hit argmax target?
        zz = np.where(m > 0, z, -1e18); tt = np.where(m > 0, T, -1e18)
        acc = float((zz.argmax(1) == tt.argmax(1)).mean())
        return grads, dict(loss=float((lossv.sum(1) / n[:, 0] * wv).mean()), acc=acc)

    def _upd(self, name, arr, g, lr, b1=0.9, b2=0.999, wd=1e-5):
        if name not in self._adam:
            self._adam[name] = (np.zeros_like(arr), np.zeros_like(arr))
        mm, vv = self._adam[name]
        mm[:] = b1 * mm + (1 - b1) * g; vv[:] = b2 * vv + (1 - b2) * g * g
        t = max(self._t, 1)
        arr -= lr * ((mm / (1 - b1 ** t)) / (np.sqrt(vv / (1 - b2 ** t)) + 1e-8) + wd * arr)

    def step(self, grads, lr=1e-3, clip=5.0):
        nrm = math.sqrt(sum(float((g * g).sum()) for g in grads.values()))
        if nrm > clip:
            grads = {k: g * (clip / nrm) for k, g in grads.items()}
        self._t += 1
        for k in self.NAMES:
            self._upd(k, getattr(self, k), grads[k], lr)
        return nrm


def save_qnet(net, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp.npz"
    np.savez(tmp, kind=np.array("qnet"), tau=np.array(net.tau), **net.params())
    os.replace(tmp, path)


def load_any(path, rng=None):
    z = np.load(path, allow_pickle=False)
    if "kind" in z.files and str(z["kind"]) == "qnet":
        net = QNet(np.random.default_rng(0))
        net.load({k: z[k] for k in QNet.NAMES})
        net.tau = float(z["tau"])
        return net
    from . import learn as L
    return L.load_net(path, rng=rng)


def make_policy_any(net, greedy=True, rng=None):
    def pol(sim, i, mask, cands, info):
        x = features(sim, i, mask, cands, info)
        a, _ = net.act(x, mask.astype(np.float64), greedy=greedy, rng=rng)
        return a
    pol.net = net
    return pol
