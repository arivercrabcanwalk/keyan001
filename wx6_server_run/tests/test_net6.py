"""Finite-difference check of Net6.loss_grad + flatten round trip."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from v6.net6 import Net6, KEYS


def main():
    r = np.random.default_rng(1)
    net = Net6(3, d1=12, d2=8)
    B, A, Fd = 6, 5, net.meta["nin"]
    X = r.normal(size=(B, A, Fd)); mask = r.random((B, A)) < 0.7; mask[:, 0] = True
    T = r.random((B, A)) * mask; T /= T.sum(1, keepdims=True)
    w = r.random(B) + 0.5
    L, g = net.loss_grad(X, mask, T, w)
    worst = 0.0
    for k in KEYS:
        P = net.p[k]
        for _ in range(5):
            idx = tuple(r.integers(s) for s in P.shape)
            old = P[idx]; h = 1e-6
            P[idx] = old + h; Lp, _ = net.loss_grad(X, mask, T, w)
            P[idx] = old - h; Lm, _ = net.loss_grad(X, mask, T, w)
            P[idx] = old
            num = (Lp - Lm) / (2 * h)
            worst = max(worst, abs(num - g[k][idx]) / max(1e-6, abs(num) + abs(g[k][idx])))
    v = net.flat(); net2 = Net6(9, d1=12, d2=8); net2.set_flat(v)
    assert np.allclose(net2.logits(X), net.logits(X))
    print(f"[test_net6] max relative gradient error {worst:.2e}")
    assert worst < 1e-4, worst
    print("[test_net6] OK")


if __name__ == "__main__":
    main()
