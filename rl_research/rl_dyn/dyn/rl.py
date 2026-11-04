"""RL hold/launch policy: MLP on state features; numpy forward for rollouts, torch for updates."""
import dyn, numpy as np
from dyn.feat import features, NF
class NPPolicy:
    def __init__(self, params, greedy=True, rng=None, record=None):
        self.W = [np.asarray(p, dtype=np.float32) for p in params]; self.greedy = greedy
        self.rng = rng or np.random.default_rng(0); self.record = record
    def prob(self, x):
        W1, b1, W2, b2, W3, b3 = self.W
        h = np.tanh(x @ W1 + b1); h = np.tanh(h @ W2 + b2); z = float(h @ W3 + b3)
        return 1.0 / (1.0 + np.exp(-z))
    def __call__(self, sim, i):
        x = features(sim, i); p = self.prob(x)
        a = (p > 0.5) if self.greedy else (self.rng.random() < p)
        if self.record is not None: self.record.append((x, int(a)))
        return bool(a)
def init_params(H=64, seed=0, bias=-1.0):
    rng = np.random.default_rng(seed)
    g = lambda a, b: (rng.normal(0, 1 / np.sqrt(a), (a, b))).astype(np.float32)
    return [g(NF, H), np.zeros(H, np.float32), g(H, H), np.zeros(H, np.float32), g(H, 1)[:, 0] * 0.1, np.float32(bias)]
