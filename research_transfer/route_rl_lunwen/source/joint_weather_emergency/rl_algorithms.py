"""Matched PPO and synchronous A2C updates for variable-action actor-critics."""
from __future__ import annotations

import math
import random
import time
from typing import Iterable

import torch
from torch.distributions import Categorical


def masked_policy_distribution(model, observation, *, device=None):
    """Evaluate one pointer observation using the exact Boolean action mask."""
    if device is None:
        try:
            device = next(model.parameters()).device
        except StopIteration:
            device = torch.device("cpu")
    global_features = torch.as_tensor(
        observation["global"], dtype=torch.float32, device=device
    )
    candidates = torch.as_tensor(
        observation["candidates"], dtype=torch.float32, device=device
    )
    mask = torch.as_tensor(observation["mask"], dtype=torch.bool, device=device).reshape(-1)
    if mask.numel() == 0 or not bool(mask.any()):
        raise ValueError("an observation must have at least one legal action")
    logits, value = model(global_features, candidates, mask)
    logits = logits.reshape(-1)
    if logits.numel() != mask.numel():
        raise ValueError(f"mask/action mismatch: {mask.numel()} vs {logits.numel()}")
    if not bool(torch.isfinite(logits[mask]).all()):
        raise ValueError("legal actions must have finite logits")
    logits = logits.masked_fill(~mask, -torch.inf)
    return Categorical(logits=logits), value.reshape(())


def add_gae(episodes: Iterable[dict], gamma=1.0, lam=0.95):
    """Flatten complete episodes and attach normalized GAE and value targets."""
    if not (math.isfinite(gamma) and math.isfinite(lam) and 0.0 <= gamma <= 1.0 and 0.0 <= lam <= 1.0):
        raise ValueError("gamma and lambda must be finite values in [0, 1]")
    flat = []
    for episode in episodes:
        transitions = episode["transitions"]
        if not transitions:
            continue
        gae = 0.0
        next_value = 0.0
        for item in reversed(transitions):
            reward = float(item["reward"])
            value = float(item["value"])
            if not math.isfinite(reward) or not math.isfinite(value):
                raise ValueError("rollout rewards and values must be finite")
            nonterminal = 0.0 if item["done"] else 1.0
            delta = reward + gamma * next_value * nonterminal - value
            gae = delta + gamma * lam * nonterminal * gae
            prepared = dict(item)
            prepared["advantage"] = gae
            prepared["return"] = gae + value
            next_value = value
            flat.append(prepared)
    flat.reverse()
    if not flat:
        raise ValueError("rollout must contain at least one transition")
    advantages = torch.as_tensor([item["advantage"] for item in flat], dtype=torch.float32)
    mean = float(advantages.mean())
    std = float(advantages.std(unbiased=False))
    for item in flat:
        item["advantage"] = (item["advantage"] - mean) / (std + 1e-8)
    return flat


def _batch_loss_terms(model, items):
    log_probs, values, entropies = [], [], []
    for item in items:
        dist, value = masked_policy_distribution(model, item)
        action = int(item["action"])
        if action < 0 or action >= dist.logits.numel() or not bool(torch.isfinite(dist.logits[action])):
            raise ValueError("rollout action is outside the legal masked action set")
        log_probs.append(dist.log_prob(torch.as_tensor(action, device=dist.logits.device)))
        values.append(value)
        entropies.append(dist.entropy())
    return torch.stack(log_probs), torch.stack(values), torch.stack(entropies)


def _device_of(model):
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cpu")


def _targets(items, device):
    advantages = torch.as_tensor([x["advantage"] for x in items], dtype=torch.float32, device=device)
    returns = torch.as_tensor([x["return"] for x in items], dtype=torch.float32, device=device)
    return advantages, returns


def behavior_clone_update(model, optimizer, demonstrations, *, epochs=8, minibatch=64,
                          max_grad=0.5, rng=None, deadline=None):
    """Warm-start a policy from replayable physical-action demonstrations.

    ``demonstrations`` contains the same masked observations and integer action
    indices consumed by the online controls.  The helper does not create an
    action vocabulary or alter a mask. It applies no value loss and does not
    update value-head parameters; shared encoder features (and hence critic
    outputs) may change. This is ordinary maximum-likelihood training over
    actions that the environment already certified as legal.
    """
    if type(epochs) is not int or epochs <= 0 or type(minibatch) is not int or minibatch <= 0:
        raise ValueError("epochs and minibatch must be positive integers")
    if not (math.isfinite(max_grad) and max_grad > 0):
        raise ValueError("max_grad must be positive and finite")
    items = [item for episode in demonstrations for item in episode["transitions"]]
    if not items:
        raise ValueError("demonstrations must contain at least one physical action")
    rng = rng or random.Random(0)
    started = time.perf_counter()
    model.train()
    loss_sum = updates = 0
    for _ in range(epochs):
        order = list(range(len(items)))
        rng.shuffle(order)
        for start in range(0, len(order), minibatch):
            if deadline is not None and time.perf_counter() - started >= deadline:
                raise TimeoutError("behavior_clone_deadline")
            batch = [items[index] for index in order[start:start + minibatch]]
            logp, _values, _entropy = _batch_loss_terms(model, batch)
            loss = -logp.mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad)
            optimizer.step()
            loss_sum += float(loss.detach())
            updates += 1
    if deadline is not None and time.perf_counter() - started > deadline:
        raise TimeoutError("behavior_clone_deadline")
    return {"algorithm": "behavior_cloning", "demonstration_transitions": len(items),
            "epochs": epochs, "updates": updates, "negative_log_likelihood": loss_sum / max(1, updates)}


def ppo_update(
    model,
    optimizer,
    episodes,
    *,
    epochs=4,
    minibatch=48,
    clip=0.2,
    gamma=1.0,
    lam=0.95,
    value_coef=0.5,
    entropy_coef=0.02,
    max_grad=0.5,
    rng=None,
):
    """Apply clipped PPO updates to complete episode rollouts."""
    if type(epochs) is not int or epochs <= 0 or type(minibatch) is not int or minibatch <= 0:
        raise ValueError("epochs and minibatch must be positive integers")
    if not (math.isfinite(clip) and clip > 0 and math.isfinite(max_grad) and max_grad > 0):
        raise ValueError("clip and max_grad must be positive and finite")
    flat = add_gae(episodes, gamma=gamma, lam=lam)
    rng = rng or random.Random(0)
    device = _device_of(model)
    stats = {
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
        "clip_fraction": 0.0,
        "updates": 0,
        "transitions": len(flat),
        "algorithm": "PPO",
    }
    model.train()
    clipped = observed = 0
    for _ in range(epochs):
        order = list(range(len(flat)))
        rng.shuffle(order)
        for start in range(0, len(order), minibatch):
            items = [flat[i] for i in order[start:start + minibatch]]
            logp, values, entropy = _batch_loss_terms(model, items)
            old_logp = torch.as_tensor([x["old_logp"] for x in items], dtype=torch.float32, device=device)
            advantages, returns = _targets(items, device)
            ratios = torch.exp(logp - old_logp)
            clipped += int(((ratios < 1.0 - clip) | (ratios > 1.0 + clip)).sum().item())
            observed += ratios.numel()
            unclipped = ratios * advantages
            clipped_objective = torch.clamp(ratios, 1.0 - clip, 1.0 + clip) * advantages
            policy_loss = -torch.minimum(unclipped, clipped_objective).mean()
            value_loss = torch.square(values - returns).mean()
            entropy_mean = entropy.mean()
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy_mean
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad)
            optimizer.step()
            stats["policy_loss"] += float(policy_loss.detach())
            stats["value_loss"] += float(value_loss.detach())
            stats["entropy"] += float(entropy_mean.detach())
            stats["updates"] += 1
    count = max(stats["updates"], 1)
    for key in ("policy_loss", "value_loss", "entropy"):
        stats[key] /= count
    stats["clip_fraction"] = clipped / max(observed, 1)
    return stats


def a2c_update(
    model,
    optimizer,
    episodes,
    *,
    gamma=1.0,
    lam=0.95,
    value_coef=0.5,
    entropy_coef=0.02,
    max_grad=0.5,
):
    """Apply one synchronous, unclipped actor-critic update to a rollout batch."""
    if not (math.isfinite(max_grad) and max_grad > 0):
        raise ValueError("max_grad must be positive and finite")
    flat = add_gae(episodes, gamma=gamma, lam=lam)
    device = _device_of(model)
    model.train()
    logp, values, entropy = _batch_loss_terms(model, flat)
    advantages, returns = _targets(flat, device)
    policy_loss = -(logp * advantages).mean()
    value_loss = torch.square(values - returns).mean()
    entropy_mean = entropy.mean()
    loss = policy_loss + value_coef * value_loss - entropy_coef * entropy_mean
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad)
    optimizer.step()
    return {
        "policy_loss": float(policy_loss.detach()),
        "value_loss": float(value_loss.detach()),
        "entropy": float(entropy_mean.detach()),
        "updates": 1,
        "transitions": len(flat),
        "algorithm": "A2C",
    }


def reinforce_objective(model, episodes, *, gamma=1.0, entropy_coef=0.02):
    """Ordinary episodic score objective; no current-batch reward centering.

    For J=E[sum_t gamma**t r_t], the loss is the episode mean of
    -sum_t gamma**t log(pi(a_t|h_t)) G_t. No critic baseline is used.
    Histories may be partially observed; no Markov-state proof is implied.
    Entropy is a separate episode-mean sum regularizer with the same discounts.
    This helper is pure forward construction: no backward or optimizer step.
    """
    if not (math.isfinite(gamma) and 0.0 <= gamma <= 1.0
            and math.isfinite(entropy_coef)):
        raise ValueError("invalid REINFORCE hyperparameters")
    episodes = list(episodes)
    if not episodes:
        raise ValueError("rollout must contain at least one complete episode")
    episode_losses, episode_entropies, returns_all = [], [], []
    count = 0
    for episode in episodes:
        items = episode["transitions"]
        if not items:
            raise ValueError("empty actor episode is not update eligible")
        if (any(type(item.get("done")) is not bool for item in items)
                or not items[-1]["done"] or any(item["done"] for item in items[:-1])):
            raise ValueError("complete single-terminal episodes required")
        future = 0.0
        prepared = []
        for item in reversed(items):
            reward = float(item["reward"])
            if not math.isfinite(reward):
                raise ValueError("rollout rewards must be finite")
            future = reward + gamma * future
            if not math.isfinite(future):
                raise ValueError("rollout returns must be finite")
            prepared.append(future)
        returns = list(reversed(prepared))
        logp, _values, entropy = _batch_loss_terms(model, items)
        weights = torch.as_tensor([gamma ** t for t in range(len(items))],
                                  dtype=logp.dtype, device=logp.device)
        targets = torch.as_tensor(returns, dtype=logp.dtype, device=logp.device)
        episode_losses.append(-(weights * logp * targets).sum())
        episode_entropies.append((weights * entropy).sum())
        returns_all.extend(returns)
        count += len(items)
    policy_loss = torch.stack(episode_losses).mean()
    entropy = torch.stack(episode_entropies).mean()
    return policy_loss - entropy_coef * entropy, {
        "policy_loss": policy_loss, "entropy": entropy, "transitions": count,
        "episodes": len(episodes), "return_min": min(returns_all),
        "return_max": max(returns_all), "target_normalization": "none",
        "reduction": "mean_episode_score_sums", "gamma": gamma,
    }


def reinforce_update(model, optimizer, episodes, *, gamma=1.0, entropy_coef=0.02, max_grad=0.5):
    """Apply the ordinary complete-episode estimator, without reward erasure."""
    if not (math.isfinite(max_grad) and max_grad > 0):
        raise ValueError("invalid REINFORCE max_grad")
    model.train()
    loss, stats = reinforce_objective(model, episodes, gamma=gamma,
                                      entropy_coef=entropy_coef)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad)
    optimizer.step()
    return {**{key: (float(value.detach()) if torch.is_tensor(value) else value)
               for key, value in stats.items()}, "updates": 1,
            "algorithm": "REINFORCE"}
