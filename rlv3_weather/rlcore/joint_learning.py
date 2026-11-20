"""Paired terminal-policy-gradient controls over shared physical route options.

This module does not import, resume, tune, or overwrite the legacy Grok trainer.
``run_round`` has a fixed BC endpoint and two fixed PG endpoints; validation is
never a checkpoint selector. ``serial`` is a matched representation ablation,
not a claim to reproduce the original sequential Grok controller.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time
from collections.abc import Mapping

import torch
from torch import nn

from .joint_route import FEAT_DIM, JointRoute


SCHEMA = "joint-terminal-pg-v1"
HIDDEN_DIM = 64
REWARD_SCALE = 1000.0
ARMS = ("greedy", "frozen_bc", "pg_j", "pg_m")


class DeadlineReached(RuntimeError):
    """An absolute, continuous round deadline was reached."""


def json_safe(value):
    """Convert receipts to strict JSON, preserving non-finite values as null."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    if isinstance(value, torch.Tensor):
        return json_safe(value.detach().cpu().tolist())
    if hasattr(value, "tolist"):
        return json_safe(value.tolist())
    if hasattr(value, "item"):
        return json_safe(value.item())
    raise TypeError(f"unsupported receipt value: {type(value).__name__}")


def _canonical(value):
    return json.dumps(json_safe(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _seed(seed, *parts):
    return int.from_bytes(hashlib.sha256(_canonical([seed, *parts])).digest()[:8],
                          "big") % (2**63 - 1)


def _check(deadline):
    if time.monotonic() >= deadline:
        raise DeadlineReached("absolute round deadline reached")


def _sync(device):
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_canonical(value) + b"\n")
    temporary.replace(path)
    # Reopen every persisted JSON artifact and reject non-JSON receipts.
    return json.loads(path.read_text(encoding="utf-8"))


def weight_hash(model):
    """Hash named tensor values rather than nondeterministic pickle bytes."""
    result = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        result.update(_canonical([name, list(value.shape), str(value.dtype)]))
        result.update(value.numpy().tobytes())
    return result.hexdigest()


def collate_options(samples, device=None):
    """Pad variable option sets. Every real row is legal; padding is masked."""
    if not samples:
        raise ValueError("empty option batch")
    tensors = []
    for sample in samples:
        tensor = torch.as_tensor(sample, dtype=torch.float32, device=device)
        if tensor.ndim != 2 or tensor.shape[1] != FEAT_DIM or not len(tensor):
            raise ValueError("each state needs at least one FEAT_DIM physical option")
        if not torch.isfinite(tensor).all():
            raise ValueError("non-finite physical option feature")
        tensors.append(tensor)
    features = torch.zeros((len(tensors), max(map(len, tensors)), FEAT_DIM),
                           dtype=torch.float32, device=device)
    mask = torch.zeros(features.shape[:2], dtype=torch.bool, device=device)
    for index, tensor in enumerate(tensors):
        features[index, :len(tensor)] = tensor
        mask[index, :len(tensor)] = True
    return features, mask


class JointActor(nn.Module):
    """Permutation-equivariant actor conditioned on the whole legal action set."""

    def __init__(self, hidden_dim=HIDDEN_DIM):
        super().__init__()
        self.option = nn.Sequential(nn.Linear(FEAT_DIM, hidden_dim), nn.Tanh(),
                                    nn.Linear(hidden_dim, hidden_dim), nn.Tanh())
        self.score = nn.Sequential(nn.Linear(3 * hidden_dim, hidden_dim), nn.Tanh(),
                                   nn.Linear(hidden_dim, 1))

    def forward(self, features, mask):
        if features.ndim != 3 or features.shape[-1] != FEAT_DIM:
            raise ValueError("invalid actor feature dimensions")
        if mask.dtype != torch.bool or mask.shape != features.shape[:2] or not mask.any(-1).all():
            raise ValueError("actor requires legal physical options")
        if not torch.isfinite(features).all():
            raise ValueError("non-finite actor input")
        embedded = self.option(features)
        mean = embedded.masked_fill(~mask[..., None], 0).sum(1) / mask.sum(1, keepdim=True)
        maximum = embedded.masked_fill(~mask[..., None], -torch.inf).max(1).values
        context = torch.cat((mean, maximum), -1)[:, None, :].expand(-1, features.shape[1], -1)
        logits = self.score(torch.cat((embedded, context), -1)).squeeze(-1)
        return logits.masked_fill(~mask, -torch.inf)


class _SlotOrder:
    """A fixed cyclic station/slot order; slot choice has no learned scores."""

    def __init__(self, mode):
        self.mode, self.current, self.after_return = mode, None, False

    def options(self, options):
        if self.mode == "joint":
            return options
        slots = sorted({tuple(action[:2]) for action, _ in options})
        if not slots:
            return []
        if self.current not in slots or self.after_return:
            later = [slot for slot in slots if self.current is None or slot > self.current]
            self.current = later[0] if later else slots[0]
        self.after_return = False
        return [(action, features) for action, features in options
                if tuple(action[:2]) == self.current]

    def step(self, action):
        self.after_return = action[-1] == -1


def _options(env, order):
    options = list(env.options())
    for action, features in options:
        if not isinstance(action, tuple) or len(action) != 3:
            raise ValueError("joint action must be (station, slot, target_or_RETURN)")
        if len(features) != FEAT_DIM or not all(math.isfinite(float(x)) for x in features):
            raise ValueError("invalid physical option features")
    actions = [action for action, _ in options]
    if len(actions) != len(set(actions)):
        raise ValueError("duplicate physical actions")
    return order.options(options)


def _failure(reason, error=None):
    return dict(cost=None, J=None, M_return=None, complete_strict=False,
                all_returned=False, physically_feasible=False, eligible=False,
                fallback=False, solution=None, termination_reason=reason,
                error=error, learning_score_valid=False)


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"non-finite or missing terminal {name}")
    return float(value)


def result_eligible(result, cap):
    """Recheck all gates; an environment's positive eligible bit is insufficient."""
    flags = ("complete_strict", "all_returned", "physically_feasible", "eligible")
    if not all(result.get(key) is True or result.get(key) == 1 for key in flags):
        return False
    if result.get("fallback", True):
        return False
    try:
        return _number(result.get("cost"), "cost") <= cap + 1e-7
    except ValueError:
        return False


def terminal_score(result, objective, cap):
    """Minimization objectives, without shaping or validation-driven scaling.

    J uses the fixed-wind legacy cost+1000*unserved+1000*failed proxy.
    M uses the previously frozen three-tier L contract. M>600 does not satisfy
    that contract and raises rather than crossing its compliance tiers silently.
    """
    if objective == "j":
        cost = _number(result.get("cost"), "cost")
        unserved = _number(result.get("unserved"), "unserved")
        failed = _number(result.get("failed"), "failed")
        if min(unserved, failed) < 0:
            raise ValueError("negative terminal failure count")
        score = cost + 1000.0 * unserved + 1000.0 * failed
        if "J" in result and not math.isclose(_number(result["J"], "J"), score,
                                               rel_tol=1e-12, abs_tol=1e-7):
            raise ValueError("terminal J differs from fixed-wind legacy formula")
        return score
    if objective != "m":
        raise ValueError("unknown terminal objective")
    if result_eligible(result, cap):
        makespan = _number(result.get("M_return"), "M_return")
        if not 0 <= makespan <= 600:
            raise ValueError("eligible M_return is outside frozen L range [0,600]")
        return makespan
    completed_physical = (bool(result.get("complete_strict")) and
                          bool(result.get("all_returned")) and
                          bool(result.get("physically_feasible")) and
                          not bool(result.get("fallback", True)))
    if completed_physical:
        if cap <= 0:
            raise ValueError("positive cap required by frozen relative violation")
        violation = max(0.0, (_number(result.get("cost"), "cost") - cap) / cap)
        return 601.0 + 600.0 * violation / (1.0 + violation)
    unserved = _number(result.get("unserved"), "unserved")
    total = _number(result.get("routine_total", result.get("n_targets")), "routine_total")
    if total <= 0 or not 0 <= unserved <= total:
        raise ValueError("invalid terminal service counts")
    return 1202.0 + 600.0 * unserved / total


def loo_advantages(scores, scale=REWARD_SCALE):
    """Reward advantages for independent trajectories, including failed ones."""
    scores = [float(score) for score in scores]
    if not scores or not all(math.isfinite(score) for score in scores) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("invalid terminal score group")
    if len(scores) == 1:
        return [-scores[0] / scale]  # Explicit zero reward baseline for R=1.
    total = sum(scores)
    return [((total - score) / (len(scores) - 1) - score) / scale for score in scores]


def _episode(case, model, *, mode, kind, seed, device, deadline):
    """Return every attempt, including exceptions; no fallback route is inserted."""
    row, scenario, cap = case
    trace, logps, demonstrations = [], [], []
    env = None
    try:
        _check(deadline)
        env = JointRoute(copy.deepcopy(row), copy.deepcopy(scenario), float(cap))
        order = _SlotOrder(mode)
        generator = torch.Generator(device="cpu").manual_seed(seed)
        while not env.done:
            _check(deadline)
            options = _options(env, order)
            if not options:
                raise ValueError("unfinished environment exposed no physical options")
            actions = [action for action, _ in options]
            features = [feature for _, feature in options]
            if kind in ("teacher", "greedy"):
                method = env.teacher_action if kind == "teacher" else env.greedy_action
                action = method(options) if mode == "serial" else method()
                if action not in actions:
                    raise ValueError("teacher/greedy chose outside shared legal options")
                index = actions.index(action)
                if kind == "teacher":
                    demonstrations.append((features, index))
            else:
                tensors, mask = collate_options([features], device)
                logits = model(tensors, mask)[0]
                logprob = logits.log_softmax(-1)
                if kind == "sample":
                    index = int(torch.multinomial(logprob.detach().exp().cpu(), 1,
                                                  generator=generator).item())
                    logps.append(logprob[index])
                elif kind == "argmax":
                    index = int(logits.argmax().item())
                else:
                    raise ValueError("unknown route rollout kind")
                action = actions[index]
            _check(deadline)
            env.step(action)
            order.step(action)
            trace.append(action)
        _check(deadline)
        result = json_safe(env.result())
        _check(deadline)
        result["eligible"] = result_eligible(result, float(cap))
        result["learning_score_valid"] = True
        return dict(result=result, actions=trace, logps=logps,
                    demonstrations=demonstrations, interrupted=False)
    except DeadlineReached as exc:
        result = _failure("deadline", str(exc))
        interrupted = True
    except Exception as exc:
        result = _failure("exception", f"{type(exc).__name__}: {exc}")
        interrupted = False
    # Partial state is evidence only, never a successful terminal replacement.
    if env is not None:
        try:
            result["partial_result"] = json_safe(env.result())
        except Exception as exc:
            result["partial_result_error"] = f"{type(exc).__name__}: {exc}"
    return dict(result=result, actions=trace, logps=[], demonstrations=[],
                interrupted=interrupted)


def _commit_step(model, optimizer, device, deadline):
    """A late optimizer mutation restores both weights and Adam moments."""
    _check(deadline)
    before_model, before_optimizer = copy.deepcopy(model.state_dict()), copy.deepcopy(optimizer.state_dict())
    try:
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        _check(deadline)
        optimizer.step()
        _sync(device)
        _check(deadline)
    except BaseException:
        model.load_state_dict(before_model)
        optimizer.load_state_dict(before_optimizer)
        optimizer.zero_grad(set_to_none=True)
        _sync(device)
        raise


def _checkpoint(path, model, metadata):
    state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    torch.save(dict(schema=SCHEMA, model=state, feat_dim=FEAT_DIM,
                    hidden_dim=HIDDEN_DIM, **metadata), path)
    saved = torch.load(path, map_location="cpu", weights_only=True)
    clone = JointActor()
    clone.load_state_dict(saved["model"])
    if weight_hash(model) != weight_hash(clone):
        raise RuntimeError("checkpoint reopened with changed weights")
    return dict(path=str(path.resolve()), weight_sha256=weight_hash(model),
                file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **metadata)


def _validate_cases(train_cases, val_cases):
    if not train_cases or not val_cases:
        raise ValueError("independent nonempty train and validation cases are required")
    for case in [*train_cases, *val_cases]:
        if not isinstance(case, (tuple, list)) or len(case) != 3:
            raise ValueError("cases must be (row, scenario, cap)")
        cap = _number(case[2], "cap")
        if cap <= 0:
            raise ValueError("positive cap required")
    def row_id(case):
        row = case[0]
        if isinstance(row, Mapping) and row.get("path"):
            return _digest(str(Path(row["path"]).resolve()))
        return _digest(row)
    if {row_id(case) for case in train_cases} & {row_id(case) for case in val_cases}:
        raise ValueError("train/validation row identities overlap")


def run_round(train_cases, val_cases, *, out, seed, bc_epochs, pg_steps, rollouts,
              lr, device, deadline, mode="joint"):
    """Execute one paired, fixed-endpoint round and return a strict-JSON summary.

    Per mode: one BC optimizer step per full epoch; each J/M PG update uses one
    seeded training case and ``rollouts`` independent trajectories. The two PG
    arms clone exactly the same BC weights with fresh Adam optimizers. Validation
    uses argmax at the fixed endpoints, once per case and arm, without selection.
    ``deadline`` is an absolute time.monotonic() deadline covering this entire
    round, including demonstrations, checkpoints, and terminal validation.
    """
    train_cases, val_cases = list(train_cases), list(val_cases)
    _validate_cases(train_cases, val_cases)
    if mode not in ("joint", "serial"):
        raise ValueError("mode must be joint or serial")
    for name, value, minimum in (("seed", seed, 0), ("bc_epochs", bc_epochs, 0),
                                  ("pg_steps", pg_steps, 0), ("rollouts", rollouts, 1)):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"invalid {name}")
    if not math.isfinite(float(lr)) or lr <= 0 or not math.isfinite(float(deadline)):
        raise ValueError("finite positive lr and absolute deadline are required")
    device = torch.device(device)
    if device.type not in ("cpu", "cuda") or (device.type == "cuda" and not torch.cuda.is_available()):
        raise ValueError("device must be available cpu or cuda")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    names = ("contract.json", "receipts.jsonl", "summary.json", "validation.jsonl",
             "initial.pt", "bc.pt", "frozen_bc.pt", "pg_j.pt", "pg_m.pt")
    if any((out / name).exists() for name in names):
        raise FileExistsError("round artifacts already exist; use a fresh output directory")
    input_digest = _digest([train_cases, val_cases])
    legacy_paths = [Path(__file__).with_name(name) for name in ("train.py", "model.py", "env.py", "agent.py")]
    legacy = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in legacy_paths}
    started = time.monotonic()
    contract = dict(schema=SCHEMA, mode=mode, seed=seed, bc_epochs=bc_epochs,
                    pg_steps=pg_steps, rollouts=rollouts, lr=lr, device=str(device),
                    feat_dim=FEAT_DIM, hidden_dim=HIDDEN_DIM,
                    train_case_ids=[_digest(case) for case in train_cases],
                    validation_case_ids=[_digest(case) for case in val_cases],
                    split="independent rows; validation never used for training or selection",
                    input_sha256=input_digest,
                    objectives=dict(pg_j="cost+1000*unserved+1000*failed (fixed wind)",
                                    pg_m="L: eligible M<=600; complete excess 601+600*v/(1+v), v=(cost-cap)/cap; incomplete 1202+600*unserved/N"),
                    endpoints="exact registered update counts; no best-validation selection",
                    pg_baseline="leave-one-out across independent rollouts; zero if R=1",
                    reward_scale=REWARD_SCALE,
                    pg_reduction="sum all trajectory log-probabilities / rollout count",
                    representation="joint station*slot*target/RETURN" if mode == "joint" else
                        "fixed cyclic lexicographic station/slot; actor chooses target/RETURN",
                    budget=dict(max_bc_updates=bc_epochs, max_pg_updates=2*pg_steps,
                                max_pg_episodes=2*pg_steps*rollouts,
                                max_teacher_episodes=len(train_cases),
                                validation_episodes=4*len(val_cases)),
                    legacy_reference=dict(status="read_only_unexecuted_not_matched_comparison", sha256=legacy),
                    deadline_clock="continuous absolute time.monotonic including validation/checkpoints",
                    scientific_qualification="engineering implementation only; no scientific claim")
    _write_json(out / "contract.json", contract)
    receipts = (out / "receipts.jsonl").open("x", encoding="utf-8")
    counts = dict(bc_updates=0, pg_j_updates=0, pg_m_updates=0,
                  teacher_episodes=0, pg_episodes=0, validation_episodes=0)
    interrupted = False
    failures = []
    checkpoints = {}
    validation = []
    changed_updates = dict(bc=0, pg_j=0, pg_m=0)

    def record(tag, **values):
        row = json_safe(dict(tag=tag, mode=mode, **values))
        receipts.write(json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        receipts.flush()
        return row

    def save(name, model, **metadata):
        checkpoints[name] = _checkpoint(out / f"{name}.pt", model, metadata)
        record("checkpoint", name=name, **checkpoints[name])

    def attempt(case, model, *, stage, kind, episode_seed, **labels):
        record("episode_started", stage=stage, case_id=_digest(case), seed=episode_seed, **labels)
        episode = _episode(case, model, mode=mode, kind=kind, seed=episode_seed,
                           device=device, deadline=deadline)
        record("episode_finished", stage=stage, case_id=_digest(case), seed=episode_seed,
               actions=episode["actions"], result=episode["result"], **labels)
        if not episode["result"].get("eligible"):
            failures.append(dict(stage=stage, case_id=_digest(case),
                                 termination_reason=episode["result"].get("termination_reason"), **labels))
        return episode

    # fork_rng restores caller RNG state. Explicit CPU sampling generators make
    # rollout seeds independent of checkpoint serialization and validation order.
    cuda_devices = [device.index if device.index is not None else torch.cuda.current_device()] if device.type == "cuda" else []
    deterministic_before = torch.are_deterministic_algorithms_enabled()
    with torch.random.fork_rng(devices=cuda_devices):
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        try:
            model = JointActor().to(device)
            save("initial", model, optimizer_steps=0, endpoint_complete=True)
            demonstrations = []
            for case in train_cases:
                if bc_epochs == 0:
                    break
                episode = attempt(case, model, stage="bc_teacher", kind="teacher",
                                  episode_seed=_seed(seed, "teacher", _digest(case)))
                counts["teacher_episodes"] += 1
                # Completed but ineligible teacher routes remain supervised data;
                # exceptions/partial trajectories supply no fabricated labels.
                demonstrations.extend(episode["demonstrations"])
                if episode["interrupted"]:
                    interrupted = True
                    break
            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            for epoch in range(bc_epochs):
                if interrupted:
                    break
                try:
                    _check(deadline)
                    if not demonstrations:
                        record("bc_update_skipped", epoch=epoch, reason="no teacher decisions")
                        break
                    optimizer.zero_grad(set_to_none=True)
                    loss_value = 0.0
                    for features, label in demonstrations:
                        _check(deadline)
                        tensors, mask = collate_options([features], device)
                        loss = -model(tensors, mask)[0].log_softmax(-1)[label] / len(demonstrations)
                        loss.backward()
                        loss_value += float(loss.detach().cpu())
                    before = weight_hash(model)
                    _commit_step(model, optimizer, device, deadline)
                    counts["bc_updates"] += 1
                    after = weight_hash(model)
                    changed_updates["bc"] += int(before != after)
                    record("bc_update", epoch=epoch, optimizer_steps=counts["bc_updates"],
                           decisions=len(demonstrations), loss=loss_value,
                           before_weight_sha256=before, after_weight_sha256=after,
                           parameter_changed=before != after)
                except DeadlineReached:
                    optimizer.zero_grad(set_to_none=True)
                    interrupted = True
                    record("bc_interrupted", epoch=epoch, retained_updates=counts["bc_updates"])
                    break
            bc_complete = counts["bc_updates"] == bc_epochs
            save("bc", model, optimizer_steps=counts["bc_updates"], endpoint_complete=bc_complete)
            frozen = copy.deepcopy(model).eval()
            for parameter in frozen.parameters():
                parameter.requires_grad_(False)
            save("frozen_bc", frozen, optimizer_steps=0, endpoint_complete=bc_complete,
                 source_weight_sha256=checkpoints["bc"]["weight_sha256"])
            models = {"frozen_bc": frozen}
            for arm, objective in (("pg_j", "j"), ("pg_m", "m")):
                policy = copy.deepcopy(model)
                policy.train()
                optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
                record("pg_start", arm=arm, source_weight_sha256=weight_hash(policy),
                       fresh_optimizer=True)
                for step in range(pg_steps):
                    if interrupted or not bc_complete:
                        break
                    case_index = _seed(seed, "case", step) % len(train_cases)
                    case = train_cases[case_index]
                    episodes = []
                    for rollout in range(rollouts):
                        episode = attempt(case, policy, stage=arm, kind="sample",
                                          episode_seed=_seed(seed, "rollout", step, rollout),
                                          step=step, rollout=rollout)
                        counts["pg_episodes"] += 1
                        episodes.append(episode)
                        if episode["interrupted"]:
                            interrupted = True
                            break
                    if interrupted:
                        record("pg_update_interrupted", arm=arm, step=step,
                               retained_updates=counts[arm+"_updates"])
                        break
                    try:
                        _check(deadline)
                        scores = [terminal_score(episode["result"], objective, float(case[2]))
                                  for episode in episodes]
                        advantages = loo_advantages(scores)
                        if not any(episode["logps"] for episode in episodes):
                            record("pg_update_skipped", arm=arm, step=step,
                                   reason="no policy decisions", scores=scores)
                            continue
                        optimizer.zero_grad(set_to_none=True)
                        terms = [-advantage * torch.stack(episode["logps"]).sum()
                                 for episode, advantage in zip(episodes, advantages) if episode["logps"]]
                        loss = torch.stack(terms).sum() / rollouts
                        loss.backward()
                        before = weight_hash(policy)
                        _commit_step(policy, optimizer, device, deadline)
                        counts[arm+"_updates"] += 1
                        after = weight_hash(policy)
                        changed_updates[arm] += int(before != after)
                        record("pg_update", arm=arm, step=step, scores=scores,
                               advantages=advantages, episodes=rollouts,
                               decisions=sum(len(episode["logps"]) for episode in episodes),
                               loss=float(loss.detach().cpu()), before_weight_sha256=before,
                               after_weight_sha256=after, parameter_changed=before != after)
                    except DeadlineReached:
                        optimizer.zero_grad(set_to_none=True)
                        interrupted = True
                        record("pg_update_interrupted", arm=arm, step=step,
                               retained_updates=counts[arm+"_updates"])
                        break
                    except ValueError as exc:
                        record("pg_update_skipped", arm=arm, step=step,
                               reason="invalid terminal score; failures retained", error=str(exc))
                policy.eval()
                models[arm] = policy
                save(arm, policy, optimizer_steps=counts[arm+"_updates"],
                     source_weight_sha256=checkpoints["bc"]["weight_sha256"],
                     endpoint_complete=bc_complete and counts[arm+"_updates"] == pg_steps)
            frozen_before_validation = weight_hash(frozen)
            for arm in ARMS:
                endpoint_complete = arm == "greedy" or checkpoints[arm]["endpoint_complete"]
                for case_index, case in enumerate(val_cases):
                    if endpoint_complete:
                        with torch.no_grad():
                            episode = attempt(case, models.get(arm), stage="validation", kind="greedy" if arm == "greedy" else "argmax",
                                              episode_seed=_seed(seed, "validation", case_index), arm=arm)
                        counts["validation_episodes"] += 1
                        interrupted = interrupted or episode["interrupted"]
                    else:
                        episode = dict(result=_failure("registered_endpoint_not_reached"), actions=[])
                        record("validation_missing_endpoint", arm=arm, case_id=_digest(case),
                               result=episode["result"])
                        failures.append(dict(stage="validation", arm=arm,
                                             case_id=_digest(case), termination_reason="registered_endpoint_not_reached"))
                    value = dict(arm=arm, case_id=_digest(case), cap=float(case[2]),
                                 endpoint_complete=endpoint_complete, result=episode["result"],
                                 actions=episode["actions"])
                    for objective in ("j", "m"):
                        try:
                            value["score_"+objective] = terminal_score(episode["result"], objective, float(case[2]))
                        except ValueError:
                            value["score_"+objective] = None
                    validation.append(value)
            if weight_hash(frozen) != frozen_before_validation or weight_hash(frozen) != checkpoints["bc"]["weight_sha256"]:
                raise RuntimeError("frozen BC weights changed")
        finally:
            torch.use_deterministic_algorithms(deterministic_before)
            receipts.close()
    if input_digest != _digest([train_cases, val_cases]):
        raise RuntimeError("run mutated input cases")
    legacy_unchanged = all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
                           for path, digest in legacy.items())
    if not legacy_unchanged:
        raise RuntimeError("legacy reference source changed during run")
    with (out / "validation.jsonl").open("x", encoding="utf-8") as stream:
        for row in validation:
            stream.write(json.dumps(json_safe(row), sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n")
    # No failure is dropped from denominators or replaced by a heuristic route.
    aggregates = {}
    for arm in ARMS:
        rows = [row for row in validation if row["arm"] == arm]
        eligible = [row for row in rows if row["result"].get("eligible")]
        def mean_score(name):
            values = [row[name] for row in rows]
            return sum(values)/len(values) if all(value is not None for value in values) else None
        aggregates[arm] = dict(cases=len(rows), eligible_count=len(eligible),
                               failure_count=len(rows)-len(eligible),
                               eligible_all=len(eligible)==len(rows),
                               mean_J_all=mean_score("score_j"), mean_L_all=mean_score("score_m"),
                               mean_eligible_M=(sum(row["result"]["M_return"] for row in eligible)/len(eligible)
                                                if eligible else None))
    endpoints_complete = (counts["bc_updates"] == bc_epochs and
                          counts["pg_j_updates"] == pg_steps and counts["pg_m_updates"] == pg_steps)
    interrupted = interrupted or time.monotonic() >= deadline
    status = "completed_fixed_endpoints" if endpoints_complete and not interrupted else (
        "deadline_interrupted" if interrupted else "incomplete_registered_endpoints")
    summary = dict(schema=SCHEMA, mode=mode, status=status, counts=counts,
                   requested=dict(bc_epochs=bc_epochs, pg_steps=pg_steps, rollouts=rollouts),
                   checkpoints=checkpoints, arms=aggregates, failures=failures,
                   failure_attempts=len(failures), validation=validation,
                   fixed_endpoints_complete=endpoints_complete,
                   frozen_bc_unchanged=True, legacy_unchanged=legacy_unchanged,
                   learning_evidence={arm:dict(optimizer_steps=counts[arm+"_updates"],
                       changed_updates=changed_updates[arm],
                       zero_parameter_change_updates=counts[arm+"_updates"]-changed_updates[arm],
                       parameter_changed_from_source=(checkpoints[arm]["weight_sha256"] !=
                           checkpoints["initial" if arm == "bc" else "bc"]["weight_sha256"]),
                       qualification="optimizer/weight evidence only; no quality or learning-success claim")
                       for arm in ("bc", "pg_j", "pg_m")},
                   input_unchanged=True, input_sha256=input_digest,
                   deterministic_weight_hashes={key:value["weight_sha256"] for key,value in checkpoints.items()},
                   elapsed_wall_seconds=time.monotonic()-started,
                   deadline_overrun_seconds=max(0.0, time.monotonic()-deadline),
                   qualification="engineering-only; original Grok reference not run; no scientific claim")
    _write_json(out / "summary.json", summary)
    for name in ("receipts.jsonl", "validation.jsonl"):
        with (out / name).open(encoding="utf-8") as stream:
            for line in stream:
                json.loads(line)
    return json_safe(summary)
