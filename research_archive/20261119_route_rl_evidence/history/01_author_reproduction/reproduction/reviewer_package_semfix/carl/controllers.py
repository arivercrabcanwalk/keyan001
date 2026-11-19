"""Controllers for CA-RL-TSALNS.

All controllers choose one of 51 operator-level actions (17 explicit
neighborhood subtypes x supported intensities) under the same dynamic mask.
The candidate generator, kernel and validator are identical across controllers,
so performance differences are attributable to the controller only.

M1 FixedPolicy        uniform random over feasible macro actions (sanity baseline)
M1d ScheduledPolicy   tuned phase schedule; principal strong non-RL baseline
M2 AdaptiveWeights    ALNS-style recency weights over 51 operator-level actions
M3 RuleController     bottleneck rule using load/assignment/stagnation signals
M4 LinUCB             51-arm contextual bandit with Sherman-Morrison updates
M5 QLearning          tabular semi-Markov Q-learning over a discretised bottleneck state
M6 PPOController      MLP policy/value, trained offline on the train split
"""
import math
import random

import numpy as np

from .state import FEATURE_NAMES, N_FEATURES
from .actions import (N_ACTIONS, N_OPERATORS, OPERATOR_NAMES,
                      OPERATOR_FAMILY, OPERATOR_INTENSITIES)

IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}


class Controller:
    name = "base"

    def begin(self, ins, seed):
        self.rng = random.Random(seed * 7919 + 13)

    def act(self, feat, mask, step):
        raise NotImplementedError

    def observe(self, feat, action, reward, next_feat, done, mask, info):
        pass

    def end_episode(self):
        pass


class FixedPolicy(Controller):
    """Uniform random over feasible macro actions (no learning)."""

    name = "M1_fixed_joint"

    def act(self, feat, mask, step):
        allowed = np.flatnonzero(mask)
        return int(self.rng.choice(allowed.tolist()))


class CyclicPolicy(Controller):
    name = "M1b_cyclic_joint"

    def act(self, feat, mask, step):
        for k in range(N_ACTIONS):
            a = (step * 5 + k) % N_ACTIONS
            if mask[a]:
                return a
        return int(np.flatnonzero(mask)[0])


class DistributionPolicy(Controller):
    """Fixed hand-tuned distribution over explicit operators."""

    name = "M1c_dist_operator"
    FAMILY_W = (0.15, 0.20, 0.50, 0.15)
    INTENSITY_W = (0.45, 0.35, 0.20)
    OPERATOR_W = (
        0.20, 0.20, 0.20, 0.20, 0.20,   # location
        0.65, 0.35,                     # assignment
        0.22, 0.18, 0.15, 0.15, 0.30,  # routing
        0.20, 0.20, 0.20, 0.20, 0.20,  # joint
    )

    def act(self, feat, mask, step):
        weights = np.zeros(N_ACTIONS, dtype=np.float64)
        for op in range(N_OPERATORS):
            family = OPERATOR_FAMILY[op]
            for intensity in OPERATOR_INTENSITIES[op]:
                a = op * 3 + intensity
                if mask[a]:
                    weights[a] = (self.FAMILY_W[family] *
                                  self.OPERATOR_W[op] *
                                  self.INTENSITY_W[intensity])
        if weights.sum() <= 0:
            return int(np.flatnonzero(mask)[0])
        return int(self.rng.choices(range(N_ACTIONS),
                                    weights=weights.tolist(), k=1)[0])


class ScheduledPolicy(Controller):
    """Phase schedule over explicit location/assignment/routing/joint subtypes."""

    name = "M1d_scheduled_operator_joint"
    OPERATOR_W = DistributionPolicy.OPERATOR_W
    INTENSITY_EARLY = (0.30, 0.40, 0.30)
    INTENSITY_LATE = (0.55, 0.30, 0.15)

    def act(self, feat, mask, step):
        phase = float(feat[IDX["budget_used"]])
        if phase < 0.30:
            family_w = (0.35, 0.25, 0.15, 0.25)
            intensity_w = self.INTENSITY_EARLY
        else:
            family_w = (0.08, 0.12, 0.68, 0.12)
            intensity_w = self.INTENSITY_LATE
        weights = np.zeros(N_ACTIONS, dtype=np.float64)
        for op in range(N_OPERATORS):
            family = OPERATOR_FAMILY[op]
            for intensity in OPERATOR_INTENSITIES[op]:
                a = op * 3 + intensity
                if mask[a]:
                    weights[a] = (family_w[family] * self.OPERATOR_W[op] *
                                  intensity_w[intensity])
        if weights.sum() <= 0:
            return int(np.flatnonzero(mask)[0])
        return int(self.rng.choices(range(N_ACTIONS),
                                    weights=weights.tolist(), k=1)[0])


class AdaptiveWeights(Controller):
    """ALNS-style adaptive weights over explicit operator-level actions."""

    name = "M2_adaptive_joint"

    def begin(self, ins, seed):
        super().begin(ins, seed)
        self.w = np.ones(N_ACTIONS)
        self.score = np.zeros(N_ACTIONS)
        self.count = np.zeros(N_ACTIONS)
        self.last_action = None
        self.last_feasible = True

    def act(self, feat, mask, step):
        w = np.where(mask, self.w, 0.0)
        if w.sum() <= 0:
            w = mask.astype(float)
        a = int(self.rng.choices(range(N_ACTIONS), weights=w.tolist(), k=1)[0])
        self.last_action = a
        return a

    def observe(self, feat, action, reward, next_feat, done, mask, info):
        a = action
        # Classical ALNS credit assignment: best update > incumbent
        # improvement > accepted move > merely feasible candidate.
        # This avoids rewarding an operator simply because it was attempted.
        self.score[a] += (
            5.0 * int(bool(info.get("best_updated", False)))
            + 3.0 * int(bool(info.get("improved", False)))
            + 1.0 * int(bool(info.get("accepted", False)))
            + 0.1 * int(bool(info.get("feasible", False)))
        )
        self.count[a] += 1
        if (self.count.sum() % 50) == 0:
            for i in range(N_ACTIONS):
                if self.count[i]:
                    self.w[i] = max(0.1, min(5.0, 0.8 * self.w[i] + 0.2 * self.score[i] / self.count[i]))
            self.score[:] = 0.0
            self.count[:] = 0.0


class RuleController(Controller):
    """Bottleneck rule over explicit operator types, not just four families."""

    name = "M3_rule_operator_joint"

    def _pick(self, mask, operators, intensity):
        # Try the requested intensity, then progressively smaller repair sizes.
        for level in (intensity, 1, 0, 2):
            allowed = [op * 3 + level for op in operators
                       if 0 <= op < N_OPERATORS and mask[op * 3 + level]]
            if allowed:
                return int(self.rng.choice(allowed))
        return int(self.rng.choice(np.flatnonzero(mask).tolist()))

    def act(self, feat, mask, step):
        g = lambda n: float(feat[IDX[n]])
        phase = g("budget_used")
        stagnation = g("stagnation") * 100.0
        max_load = g("max_load")
        std_load = g("std_load")
        alt = g("alt_target_share")
        detour = g("detour_ratio")
        low_slack = g("low_energy_slack_share")

        if self.rng.random() < 0.04:
            return int(self.rng.choice(np.flatnonzero(mask).tolist()))
        if phase < 0.22:
            return self._pick(mask, list(range(0, 5)) + list(range(12, 17)), 1)
        if stagnation > 120:
            return self._pick(mask, list(range(12, 17)) + list(range(0, 5)), 2)
        if max_load > 0.90 or low_slack > 0.30:
            return self._pick(mask, [6, 5, 7, 15, 13], 1)
        if std_load > 0.22 or (alt > 0.30 and detour > 1.05):
            return self._pick(mask, [5, 13, 12, 14, 6], 1 if std_load < 0.35 else 2)
        return self._pick(mask, [7, 8, 9, 10, 11], 0 if phase > 0.55 else 1)


class LinUCB(Controller):
    """Contextual bandit on 11 interpretable state features and 51 masked actions."""

    name = "M4_bandit_joint"
    CTX = ["budget_used", "stagnation", "max_load", "std_load", "alt_target_share",
           "detour_ratio", "min_slack", "low_energy_slack_share", "accept_rate",
           "gap_to_best", "budget_left"]

    def begin(self, ins, seed):
        super().begin(ins, seed)
        self.idx = [IDX[n] for n in self.CTX]
        self.d = len(self.idx) + 1
        self.alpha = 0.35
        self.A_inv = np.array([np.eye(self.d) for _ in range(N_ACTIONS)])
        self.b = np.zeros((N_ACTIONS, self.d))
        self.theta = np.zeros((N_ACTIONS, self.d))
        self.last_x = None
        self.last_a = None

    def _x(self, feat, mask):
        x = np.empty(self.d, dtype=np.float64)
        for j, i in enumerate(self.idx):
            v = float(feat[i])
            x[j] = v
        x[-1] = 1.0
        # squash for numerical stability
        np.clip(x, -5.0, 5.0, out=x)
        return x

    def act(self, feat, mask, step):
        x = self._x(feat, mask)
        best, best_a = -1e18, None
        for a in range(N_ACTIONS):
            if not mask[a]:
                continue
            th = self.A_inv[a] @ self.b[a]
            self.theta[a] = th
            Ainv_x = self.A_inv[a] @ x
            p = float(th @ x + self.alpha * math.sqrt(max(x @ Ainv_x, 1e-12)))
            if p > best:
                best, best_a = p, a
        if best_a is None:
            best_a = int(np.flatnonzero(mask)[0])
        self.last_x, self.last_a = x, best_a
        return best_a

    def observe(self, feat, action, reward, next_feat, done, mask, info):
        if self.last_x is None or action != self.last_a:
            return
        x = self.last_x
        a = action
        Ainv = self.A_inv[a]
        Ainv_x = Ainv @ x
        den = 1.0 + float(x @ Ainv_x)
        Ainv -= np.outer(Ainv_x, Ainv_x) / den
        self.b[a] += reward * x
        self.last_x = None


class QLearning(Controller):
    """Tabular Q-learning over a 18-state bottleneck discretisation."""

    name = "M5_qlearning_joint"

    def begin(self, ins, seed):
        super().begin(ins, seed)
        self.Q = np.zeros((18, N_ACTIONS))
        self.alpha = 0.12
        self.gamma = 0.95
        self.reference_action_seconds = 0.01
        self.eps0 = 0.25
        self.last_state = None
        self.last_action = None

    def _state(self, feat):
        g = lambda n: float(feat[IDX[n]])
        load = g("max_load") - g("mean_load")
        stag = g("stagnation") * 100.0
        phase = g("budget_used")
        a = 0 if load < 0.15 else (1 if load < 0.35 else 2)
        b = 0 if stag < 40 else (1 if stag < 150 else 2)
        c = 0 if phase < 0.5 else 1
        return (a * 3 + b) * 2 + c

    def act(self, feat, mask, step):
        s = self._state(feat)
        self.last_state = s
        eps = max(0.02, self.eps0 * (1.0 - step / 6000.0))
        allowed = np.flatnonzero(mask).tolist()
        if self.rng.random() < eps:
            a = int(self.rng.choice(allowed))
        else:
            q = np.where(mask, self.Q[s], -1e18)
            a = int(np.argmax(q))
        self.last_action = a
        return a

    def observe(self, feat, action, reward, next_feat, done, mask, info):
        if self.last_state is None:
            return
        s = self.last_state
        a = self.last_action
        s2 = self._state(next_feat) if next_feat is not None else s
        duration = max(0.0, float(info.get("duration_seconds", self.reference_action_seconds)))
        discount = self.gamma ** (duration / self.reference_action_seconds)
        target = reward + (0.0 if done else discount * float(
            np.max(np.where(mask, self.Q[s2], -1e18))))
        self.Q[s, a] += self.alpha * (target - self.Q[s, a])
        self.last_state = None


class PPOController(Controller):
    """MLP actor-critic controller with low-overhead NumPy inference.

    The policy is immutable during an episode, so copying its small weights
    once avoids per-decision PyTorch tensor construction and distribution
    overhead. The NumPy forward pass is numerically checked against PolicyNet.
    """

    name = "M6_ppo_joint"

    def __init__(self, model=None, device="cpu", training=False, deterministic=None):
        self.model = model
        self.device = device
        self.training = training
        self.deterministic = (not training) if deterministic is None else deterministic
        self.buffer = []
        self.last = None
        self._np_weights = None
        self._refresh_numpy_weights()

    def _refresh_numpy_weights(self):
        if self.model is None:
            self._np_weights = None
            return
        self.model.eval()
        def pair(layer):
            return (layer.weight.detach().cpu().numpy().astype(np.float32, copy=True),
                    layer.bias.detach().cpu().numpy().astype(np.float32, copy=True))
        self._np_weights = {
            "fc1": pair(self.model.fc1),
            "fc2": pair(self.model.fc2),
            "pi": pair(self.model.pi),
            "v": pair(self.model.v),
        }

    def _numpy_forward(self, feat):
        if self._np_weights is None:
            raise RuntimeError("PPO model weights are unavailable")
        x = np.asarray(feat, dtype=np.float32)
        w1, b1 = self._np_weights["fc1"]
        w2, b2 = self._np_weights["fc2"]
        wp, bp = self._np_weights["pi"]
        wv, bv = self._np_weights["v"]
        h1 = np.tanh(w1 @ x + b1)
        h2 = np.tanh(w2 @ h1 + b2)
        logits = wp @ h2 + bp
        value = float((wv @ h2 + bv)[0])
        return logits, value

    def begin(self, ins, seed):
        super().begin(ins, seed)
        self._refresh_numpy_weights()
        self.buffer = []
        self.last = None

    def act(self, feat, mask, step):
        logits, value = self._numpy_forward(feat)
        valid = np.flatnonzero(mask)
        if len(valid) == 0:
            raise RuntimeError("PPO received an empty action mask")
        z = logits[valid].astype(np.float64)
        z -= float(np.max(z))
        probs = np.exp(z)
        probs /= float(np.sum(probs))
        if self.deterministic:
            chosen = int(np.argmax(z))
        else:
            chosen = int(self.rng.choices(range(len(valid)),
                                          weights=probs.tolist(), k=1)[0])
        a = int(valid[chosen])
        logp = math.log(max(float(probs[chosen]), 1e-30))
        self.last = (feat.copy(), a, logp, value, mask.copy())
        return a

    def observe(self, feat, action, reward, next_feat, done, mask, info):
        if self.last is None:
            return
        self.buffer.append({"feat": self.last[0], "action": self.last[1],
                            "logp": self.last[2], "value": self.last[3],
                            "mask": self.last[4], "reward": reward, "done": done,
                            "duration_seconds": float((info or {}).get("duration_seconds", 0.0))})
        self.last = None

    def end_episode(self):
        pass

    def save(self, path):
        import torch
        from .ppo import save_model
        save_model(self.model, path)

    def load(self, path):
        import torch
        from .ppo import load_model
        self.model = load_model(path, self.device)
        self._refresh_numpy_weights()


def make_controller(name, seed=0, ppo_model=None, deterministic=True):
    name = name.lower()
    if name in ("m0", "tsalns"):
        raise ValueError("M0 is the frozen V6 TSALNS baseline, not a CA-RL controller")
    if name in ("m1", "fixed", "random"):
        return FixedPolicy()
    if name in ("m1b", "cyclic"):
        return CyclicPolicy()
    if name in ("m1c", "dist"):
        return DistributionPolicy()
    if name in ("m1d", "scheduled"):
        return ScheduledPolicy()
    if name in ("m2", "adaptive"):
        return AdaptiveWeights()
    if name in ("m3", "rule"):
        return RuleController()
    if name in ("m4", "bandit", "linucb"):
        return LinUCB()
    if name in ("m5", "q", "qlearning"):
        return QLearning()
    if name in ("m6", "ppo"):
        if ppo_model is None:
            raise ValueError("PPO controller requires a model")
        return PPOController(ppo_model, training=False, deterministic=deterministic)
    raise ValueError("unknown controller %r" % name)
