"""Reusable public-observation BC and on-policy physical-route REINFORCE.

An ``env_factory(index)`` must return a fresh Env; equal indices must reproduce
the same exogenous map/weather/request stream. The policy sees only featurize's
released tasks and current/issued weather information. No future resampling,
operator selection, search, teacher hint, or test-time optimization is used.
"""
from dataclasses import dataclass
import hashlib
import math
import pickle
import time

import numpy as np
import torch

from .agent import action_log_probs
from .env import T_DAY
from .feat import featurize
from .model import collate


@dataclass
class Episode:
    metrics: dict
    decisions: list


def parameter_sha(model):
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def input_sha(env):
    return hashlib.sha256(pickle.dumps((env.L, env.wx, env.requests), protocol=4)).hexdigest()


def derived_seed(seed, *parts):
    text = "|".join(map(str, ("event-learning-v1", seed, *parts)))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little") % (2**63-1)


class TensorRoutePolicy:
    """Greedy/stochastic physical pointer on CPU or CUDA, with no online hint."""
    def __init__(self, model, device="cpu", greedy=True, seed=0, temperature=1.0):
        self.model = model
        self.device = torch.device(device)
        self.greedy = bool(greedy)
        self.rng = np.random.default_rng(seed)
        self.temperature = temperature

    def reset(self, env):
        self.model.eval()

    @torch.no_grad()
    def act(self, env, cur):
        tok, ctx, mask, actions = featurize(env, cur)
        tensors = collate([(tok, ctx, mask)], self.device)
        logits = self.model(*tensors)
        logp = action_log_probs(logits, tensors[2], self.temperature)[0].cpu().numpy()
        if self.greedy:
            chosen = int(np.argmax(logp))
        else:
            probability = np.exp(logp)
            probability /= probability.sum()
            chosen = int(self.rng.choice(len(probability), p=probability))
        return actions[chosen]


def rollout(env, policy, collect=False):
    """Return Episode(metrics, decisions); decisions are (tok, ctx, mask, label).

    The final denominator includes all frozen requests, including unreached
    requests. Missing arrivals are censored at the end of the finite day for
    the explicitly named response_censored_mean; observed-only response is
    reported separately. A censored mean is descriptive, not a survival estimate.
    """
    original_input_sha = input_sha(env)
    decisions = []
    policy.reset(env)
    started = time.perf_counter()
    while True:
        cur = env.next_decision()
        if cur is None:
            break
        if any(task["rel"] > env.t + 1e-9 for task in cur[1]):
            raise AssertionError("unreleased request exposed to policy")
        observation = featurize(env, cur) if collect else None
        action = policy.act(env, cur)
        if collect:
            tok, ctx, mask, actions = observation
            if action not in actions or not mask[actions.index(action)]:
                raise ValueError("policy returned a masked physical action")
            decisions.append((tok, ctx, mask, actions.index(action)))
        env.step(action)
    metrics = env.result()
    requests = env.tasks[env.n_planned:]
    response = [max(0.0, (task["t_arrival"] if task["t_arrival"] is not None else T_DAY)-task["rel"])
                for task in requests]
    metrics.update(input_sha256=original_input_sha,
                   rollout_wall_s=time.perf_counter()-started,
                   routine_completion=metrics["routine_done"]/metrics["routine_total"] if metrics["routine_total"] else 1.0,
                   urgent_completion=metrics["urgent_done"]/metrics["n_urgent"] if metrics["n_urgent"] else None,
                   response_censored_mean=float(np.mean(response)) if response else None,
                   return_failure=int(not metrics["all_returned"]),
                   return_failures=sum(not drone["at_st"] or drone["failed"] for drone in env.dr),
                   emergency_records=[dict(rid=task["rid"], release=task["rel"], deadline=task["dl"],
                       priority=task["prio"], arrival=task["t_arrival"], completion=task["t_done"],
                       done=bool(task["done"]), on_time=bool(task["done"] and task["t_arrival"] is not None
                                                              and task["t_arrival"] <= task["dl"]+1e-9))
                                      for task in requests])
    return Episode(metrics, decisions)


def collect_bc(env_factory, teacher, count):
    """teacher is a reset(env)/act(env, cur) object; reuse resets each episode."""
    if count <= 0:
        raise ValueError("BC requires positive episode count")
    dataset, episodes = [], []
    for index in range(count):
        episode = rollout(env_factory(index), teacher, collect=True)
        dataset.extend(episode.decisions)
        episodes.append(episode.metrics)
    if not dataset:
        raise ValueError("BC teacher produced no physical decisions")
    return dataset, episodes


def fit_bc(model, dataset, epochs, device="cpu", seed=0, learning_rate=1e-3, batch_size=128):
    if not dataset or epochs <= 0 or batch_size <= 0:
        raise ValueError("positive BC dataset/epochs/batch size required")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    rng = np.random.default_rng(seed)
    records = []
    for epoch in range(epochs):
        model.train()
        total_loss, total_correct, steps = 0.0, 0, 0
        for start in range(0, len(dataset), batch_size):
            # A single permutation per epoch keeps sampling deterministic.
            if start == 0:
                order = rng.permutation(len(dataset))
            batch = [dataset[index] for index in order[start:start+batch_size]]
            inputs = collate([item[:3] for item in batch], device)
            labels = torch.tensor([item[3] for item in batch], device=device)
            logits = model(*inputs)
            loss = torch.nn.functional.cross_entropy(logits, labels)
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite BC loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            total_loss += float(loss.detach()) * len(batch)
            total_correct += int((logits.argmax(-1) == labels).sum())
            steps += 1
        records.append(dict(stage="bc", epoch=epoch+1, samples=len(dataset), optimizer_steps=steps,
                            loss=total_loss/len(dataset), accuracy=total_correct/len(dataset),
                            gradient_norm_last=float(norm), parameter_sha256=parameter_sha(model)))
    model.eval()
    return records


def loo_advantages(costs, reward_scale):
    values = np.asarray(costs, dtype=np.float64)
    if len(values) < 2 or not np.isfinite(values).all() or not math.isfinite(reward_scale) or reward_scale <= 0:
        raise ValueError("LOO requires >=2 finite costs and positive scale")
    return ((values.sum()-values)/(len(values)-1)-values)/reward_scale


def train_pg(model, env_factory, iterations, rollouts=4, device="cpu", seed=0,
             reward_scale=100.0, learning_rate=1e-4, batch_size=128, on_record=None):
    """True REINFORCE on failure-penalized Env.J, initialized by caller.

    Every iteration draws IID action trajectories on one identical fresh world.
    An episode's leave-one-out reward baseline is independent of its own actions.
    Scores sum all physical decisions and divide by episodes, including episodes
    with no decisions. No minibatch/trajectory length normalization, imitation
    relabeling, or post-evaluation checkpoint selection is used.
    """
    if iterations <= 0 or rollouts < 2 or batch_size <= 0:
        raise ValueError("positive PG iterations and at least two rollouts required")
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    records = []
    for iteration in range(iterations):
        episodes = []
        for replica in range(rollouts):
            policy = TensorRoutePolicy(model, device, greedy=False,
                                       seed=derived_seed(seed, "pg-action", iteration, replica))
            episodes.append(rollout(env_factory(iteration), policy, collect=True))
        hashes = {episode.metrics["input_sha256"] for episode in episodes}
        if len(hashes) != 1:
            raise ValueError("PG replicas did not receive the same exogenous input")
        costs = [episode.metrics["J"] for episode in episodes]
        advantages = loo_advantages(costs, reward_scale)
        samples, weights = [], []
        for episode, advantage in zip(episodes, advantages):
            samples.extend(episode.decisions)
            weights.extend([advantage]*len(episode.decisions))
        if not samples:
            raise ValueError("PG iteration has no physical decisions")
        before = parameter_sha(model)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        total_loss = 0.0
        for start in range(0, len(samples), batch_size):
            batch = samples[start:start+batch_size]
            inputs = collate([item[:3] for item in batch], device)
            labels = torch.tensor([item[3] for item in batch], device=device)
            advantage = torch.as_tensor(weights[start:start+batch_size], dtype=torch.float64, device=device)
            logp = action_log_probs(model(*inputs), inputs[2], 1.0)
            loss = -(advantage*logp.gather(1, labels[:, None]).squeeze(1)).sum()/rollouts
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite REINFORCE loss")
            loss.backward()
            total_loss += float(loss.detach())
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
        optimizer.step()
        if str(device).startswith("cuda"):
            torch.cuda.synchronize(device)
        after = parameter_sha(model)
        record = dict(stage="pg", iteration=iteration+1, optimizer_steps=1, rollouts=rollouts,
                      physical_decisions=len(samples), loss=total_loss, cost_mean=float(np.mean(costs)),
                      cost_min=float(np.min(costs)), cost_max=float(np.max(costs)),
                      gradient_norm=float(norm), parameters_changed=(before != after),
                      before_sha256=before, parameter_sha256=after,
                      input_sha256=next(iter(hashes)), episode_metrics=[episode.metrics for episode in episodes])
        records.append(record)
        if on_record is not None:
            on_record(record)
        model.eval()
    return records
