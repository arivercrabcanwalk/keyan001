"""MLP actor-critic trained with PPO for the macro-action controller."""
import math

import numpy as np
import torch
import torch.nn as nn

from .state import N_FEATURES, STATE_SCHEMA, ACTION_SCHEMA, REWARD_SCHEMA
from .actions import N_ACTIONS

MODEL_SCHEMA = "policy-mlp-tanh-75x64x64x51-v2"


class PolicyNet(nn.Module):
    def __init__(self, n_in=N_FEATURES, hidden=64, n_out=N_ACTIONS):
        super().__init__()
        self.fc1 = nn.Linear(n_in, hidden)
        self.fc2 = nn.Linear(hidden, hidden)
        self.pi = nn.Linear(hidden, n_out)
        self.v = nn.Linear(hidden, 1)
        for layer in (self.fc1, self.fc2):
            nn.init.orthogonal_(layer.weight, gain=math.sqrt(2))
            nn.init.zeros_(layer.bias)
        nn.init.orthogonal_(self.pi.weight, gain=0.01)
        nn.init.zeros_(self.pi.bias)
        nn.init.orthogonal_(self.v.weight, gain=1.0)
        nn.init.zeros_(self.v.bias)

    def forward(self, x):
        h = torch.tanh(self.fc1(x))
        h = torch.tanh(self.fc2(h))
        return self.pi(h), self.v(h).squeeze(-1)


def save_model(model, path):
    torch.save({"state_dict": model.state_dict(), "model_schema": MODEL_SCHEMA,
                "state_schema": STATE_SCHEMA, "action_schema": ACTION_SCHEMA,
                "reward_schema": REWARD_SCHEMA}, path)


def load_model(path, device="cpu"):
    model = PolicyNet()
    state = torch.load(path, map_location=device)
    expected = (MODEL_SCHEMA, STATE_SCHEMA, ACTION_SCHEMA, REWARD_SCHEMA)
    actual = (state.get("model_schema"), state.get("state_schema"),
              state.get("action_schema"), state.get("reward_schema")) if isinstance(state, dict) else None
    if actual != expected:
        raise ValueError(f"checkpoint schema mismatch: expected {expected}, got {actual}; retrain in the versioned environment")
    model.load_state_dict(state["state_dict"])
    model.eval()
    return model


def compute_gae(rewards, values, dones, durations=None, budget_seconds=None,
                gamma=0.99, lam=0.95):
    """GAE with elapsed-time discounts for semi-Markov macro actions.

    gamma and lambda are defined over one complete episode budget. For a
    transition lasting dt in an episode with budget B, the local factors are
    gamma ** (dt/B) and lambda ** (dt/B), so the total discount over B seconds
    remains gamma/lambda regardless of how many decisions fit in the budget.
    """
    n = len(rewards)
    adv = np.zeros(n, dtype=np.float32)
    last = 0.0
    use_time = durations is not None and budget_seconds is not None and budget_seconds > 0
    for t in reversed(range(n)):
        if use_time:
            frac = max(float(durations[t]), 0.0) / float(budget_seconds)
            gamma_t = gamma ** frac
            lambda_t = lam ** frac
        else:
            gamma_t = gamma
            lambda_t = lam
        next_value = 0.0 if (t == n - 1 or dones[t]) else values[t + 1]
        nonterminal = 0.0 if dones[t] else 1.0
        delta = rewards[t] + gamma_t * next_value * nonterminal - values[t]
        last = delta + gamma_t * lambda_t * nonterminal * last
        adv[t] = last
    returns = adv + np.asarray(values, dtype=np.float32)
    return adv, returns


def flatten_episodes(episodes, gamma=0.99, lam=0.95):
    feats, actions, logps, values, rewards, dones, masks, durations, advs, rets = (
        [], [], [], [], [], [], [], [], [], [])
    for ep in episodes:
        tr = ep["transitions"]
        if not ep.get("feasible", True):
            raise ValueError("infeasible training episode")
        if not tr:
            raise ValueError("empty training episode")
        if not tr[-1]["done"]:
            raise ValueError("truncated rollout requires explicit bootstrap")
        r = np.asarray([t["reward"] for t in tr], dtype=np.float32)
        v = np.asarray([t["value"] for t in tr], dtype=np.float32)
        d = np.asarray([1.0 if t["done"] else 0.0 for t in tr], dtype=np.float32)
        dt = np.asarray([t.get("duration_seconds", 0.0) for t in tr], dtype=np.float32)
        budget = ep.get("budget_seconds")
        adv, ret = compute_gae(r, v, d, dt if budget else None, budget, gamma, lam)
        feats.extend([t["feat"] for t in tr])
        actions.extend([t["action"] for t in tr])
        logps.extend([t["logp"] for t in tr])
        values.extend([t["value"] for t in tr])
        rewards.extend(r.tolist())
        dones.extend(d.tolist())
        masks.extend([t["mask"] for t in tr])
        durations.extend(dt.tolist())
        advs.extend(adv.tolist())
        rets.extend(ret.tolist())
    return {
        "feat": np.asarray(feats, dtype=np.float32),
        "action": np.asarray(actions, dtype=np.int64),
        "logp": np.asarray(logps, dtype=np.float32),
        "value": np.asarray(values, dtype=np.float32),
        "reward": np.asarray(rewards, dtype=np.float32),
        "done": np.asarray(dones, dtype=np.float32),
        "mask": np.asarray(masks, dtype=bool),
        "duration": np.asarray(durations, dtype=np.float32),
        "adv": np.asarray(advs, dtype=np.float32),
        "ret": np.asarray(rets, dtype=np.float32),
    }


def ppo_update(model, optimizer, batch, epochs=6, minibatch=4096, clip=0.2,
               value_coef=0.5, entropy_coef=0.04, max_grad=0.5):
    n = len(batch["feat"])
    if n == 0:
        raise ValueError("empty PPO rollout")
    if not np.isfinite(batch["feat"]).all() or not np.isfinite(batch["ret"]).all():
        raise ValueError("nonfinite PPO rollout")
    if not np.asarray(batch["mask"])[np.arange(n), batch["action"]].all():
        raise ValueError("masked action in PPO rollout")
    adv = batch["adv"]
    adv = (adv - adv.mean()) / (adv.std() + 1e-8)
    idx = np.arange(n)
    stats = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "updates": 0}
    for _ in range(epochs):
        np.random.shuffle(idx)
        for start in range(0, n, minibatch):
            mb = idx[start:start + minibatch]
            feat = torch.as_tensor(batch["feat"][mb])
            mask = torch.as_tensor(batch["mask"][mb])
            act = torch.as_tensor(batch["action"][mb])
            old_logp = torch.as_tensor(batch["logp"][mb])
            ret = torch.as_tensor(batch["ret"][mb])
            adv_mb = torch.as_tensor(adv[mb])
            logits, value = model(feat)
            logits = logits.masked_fill(~mask, -1e9)
            dist = torch.distributions.Categorical(logits=logits)
            logp = dist.log_prob(act)
            ratio = torch.exp(logp - old_logp)
            surr1 = ratio * adv_mb
            surr2 = torch.clamp(ratio, 1 - clip, 1 + clip) * adv_mb
            policy_loss = -torch.min(surr1, surr2).mean()
            value_loss = torch.nn.functional.mse_loss(value, ret)
            entropy = dist.entropy().mean()
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_grad)
            optimizer.step()
            stats["policy_loss"] += float(policy_loss.item())
            stats["value_loss"] += float(value_loss.item())
            stats["entropy"] += float(entropy.item())
            stats["updates"] += 1
    for k in ("policy_loss", "value_loss", "entropy"):
        stats[k] /= max(stats["updates"], 1)
    return stats


def collect_episode(task):
    """Worker entry point: run one search episode with the current policy."""
    torch.set_num_threads(1)
    from lrphsd.problem import read_instance
    from .controllers import PPOController
    from .search import solve
    ins = read_instance(task["instance_path"])
    model = load_model(task["model_path"])
    ctrl = PPOController(model, training=True, deterministic=False)
    res = solve(ins, ctrl, seed=task["seed"], seconds=task["seconds"],
                max_steps=task.get("max_steps", 20000), collect=True,
                intensities=tuple(task.get("intensities", (0, 1, 2))))
    if not res["feasible"]:
        raise ValueError("infeasible PPO episode")
    if res["steps"] >= task.get("max_steps", 20000) and res["solver_seconds"] < task["seconds"]:
        raise ValueError("step limit truncated budget episode; increase max_steps")
    return {"transitions": ctrl.buffer, "cost": res["cost"],
            "initial_cost": res["initial_cost"], "steps": res["steps"],
            "feasible": res["feasible"], "instance": task["instance"],
            "seed": task["seed"], "budget_seconds": float(task["seconds"]),
            "counters": res.get("counters", {})}
