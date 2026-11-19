#!/usr/bin/env python3
"""Synthetic multi-station PPO/A2C integration run under wind and a timed NFZ.

This is an executable engineering test, not a registered-map experiment.  It
replays the static anchor under the same weather oracle, then gives the common
weather cost cap to a deterministic physical greedy control, PPO, and A2C.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
import time

import numpy as np
import torch

PACKAGE_ROOT = Path(__file__).resolve().parent
LUNWEN_ROOT = PACKAGE_ROOT.parents[3]
for import_root in (PACKAGE_ROOT, PACKAGE_ROOT.parent,
                    LUNWEN_ROOT / "reproduction/reviewer_package_semfix"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from lrphsd.problem import Instance, Node, Parameters, empty_solution
from rl_algorithms import a2c_update, masked_policy_distribution, ppo_update
from scorer import CostAnchor
from weather_full_map import (MAX_POLICY_SLOTS, MAX_POLICY_TARGETS,
                              WeatherFullMapEnv, WeatherMapAction, WeatherMapScenario,
                              replay_weather_solution)
from weather_oracle import NoFlyZone, Point, WindField, WindKnot
from weather_policy import WeatherPointerActorCritic, greedy_action


SEEDS = (103, 211, 307)
FAILURE_REWARD_MARGIN_MIN = 1.0
FEASIBILITY_TOLERANCE_MIN = 1e-7


def feasible_makespan_upper_bound(instance) -> float:
    """Maximum replay-admissible M_return in minutes under the duty contract."""
    return max(instance.params.small_duration, instance.params.large_duration) + FEASIBILITY_TOLERANCE_MIN


def failure_reward_penalty(instance) -> float:
    """Terminal penalty, in minutes, strictly exceeds every feasible M_return."""
    return feasible_makespan_upper_bound(instance) + FAILURE_REWARD_MARGIN_MIN


def fixture():
    params = Parameters(speed=900.0, flight_energy=0.018, small_battery=0.62,
                        large_battery=0.9, small_radius=4000.0, large_radius=5000.0,
                        small_duration=60.0, large_duration=70.0)
    stations = (Node(100, 0.0, 0.0, 0.0, 0.0), Node(200, 6000.0, 0.0, 0.0, 0.0))
    targets = (Node(1, 900.0, 0.0, 0.10, 0.5), Node(2, 6900.0, 0.0, 0.10, 0.5),
               Node(3, 1250.0, 750.0, 0.10, 0.5), Node(4, 1700.0, -500.0, 0.10, 0.5),
               Node(5, 6250.0, 900.0, 0.10, 0.5))
    instance = Instance("synthetic_weather_full_map", targets, stations,
                        "synthetic-weather-full-map-v1", params)
    solution = empty_solution(instance, [2, 1])
    solution["routes"] = [[[[1, 4]], [[3]]], [[], [[2, 5]]]]
    anchor = CostAnchor.from_solution(instance, solution)
    scenario = WeatherMapScenario(
        WindField((WindKnot(0.0, 2.0, 0.0), WindKnot(150.0, -2.0, 3.0),
                   WindKnot(450.0, 1.0, -1.0))),
        NoFlyZone((Point(300.0, -220.0), Point(760.0, -220.0),
                   Point(760.0, 220.0), Point(300.0, 220.0)), 0.0, 600.0),
        name="synthetic_full_map_wind_nfz_v1")
    return instance, solution, anchor, scenario


def _seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_receipt():
    import lrphsd.problem
    import scorer
    sources = (PACKAGE_ROOT / "weather_oracle.py", PACKAGE_ROOT / "weather_replay.py",
               PACKAGE_ROOT / "weather_full_map.py", PACKAGE_ROOT / "weather_policy.py",
               PACKAGE_ROOT / "rl_algorithms.py", PACKAGE_ROOT / "run_full_map_smoke.py",
               Path(scorer.__file__), Path(lrphsd.problem.__file__),
               Path(lrphsd.problem.__file__).with_name("__init__.py"))
    return {
        "python": sys.version, "platform": platform.platform(), "cwd": str(Path.cwd().resolve()),
        "numpy": str(np.__version__), "torch": str(torch.__version__), "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(), "torch_threads": torch.get_num_threads(),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch_config": torch.__config__.show(),
        "source_manifest": {str(path.resolve()): _sha256(path) for path in sources},
    }


def greedy_physical(env: WeatherFullMapEnv):
    """Common-oracle deterministic rule: earliest projected target, then return."""
    while not env.terminated:
        obs = env.observation()
        legal = [(i, action) for i, action in enumerate(obs["actions"]) if obs["mask"][i]]
        targets = [(i, action) for i, action in legal if not action.is_return]
        if targets:
            index, action = min(targets, key=lambda pair: (
                float(obs["candidates"][pair[0], 5]), pair[1].station_idx,
                pair[1].slot, pair[1].target_id))
        else:
            returns = [(i, action) for i, action in legal if action.is_return]
            if not returns:
                break
            index, action = returns[0]
        env.step(action)
    return env.result() if env.done and env.failure is None else None


def rollout(env: WeatherFullMapEnv, model, *, stochastic=True):
    transitions = []
    penalty = failure_reward_penalty(env.instance)
    penalty_applied = False
    while not env.terminated:
        observation = env.observation()
        with torch.no_grad():
            distribution, value = masked_policy_distribution(model, observation)
            action_index = int(distribution.sample().item()) if stochastic else int(torch.argmax(distribution.logits))
            old_logp = float(distribution.log_prob(torch.tensor(action_index)).item())
        _, reward, terminated, info = env.step(observation["actions"][action_index])
        if info["failure"] is not None:
            reward -= penalty
            penalty_applied = True
        transitions.append({"global": observation["global"], "candidates": observation["candidates"],
                            "mask": observation["mask"], "action": action_index, "reward": reward,
                            "done": terminated, "value": float(value), "old_logp": old_logp})
    return {"transitions": transitions, "complete": env.done and env.failure is None,
            "failure": env.failure, "failure_reward_penalty_min": penalty if penalty_applied else 0.0,
            "failure_penalty_applied": penalty_applied,
            "zero_transition_failure": bool(not transitions and env.failure is not None),
            "result": env.result() if env.done and env.failure is None else None}


def train(instance, anchor, scenario, cost_cap, algorithm, seed, *, updates, episodes):
    _seed(seed)
    model = WeatherPointerActorCritic(global_dim=WeatherFullMapEnv.global_dim,
                                      candidate_dim=WeatherFullMapEnv.candidate_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    history = []
    for update in range(updates):
        batch = [rollout(WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=cost_cap), model)
                 for _ in range(episodes)]
        valid = [episode for episode in batch if episode["transitions"]]
        stats = ({"skipped_update_no_transitions": True, "loss": None}
                 if not valid else
                 (ppo_update(model, optimizer, valid, epochs=2, minibatch=32, gamma=1.0, lam=1.0,
                             rng=random.Random(seed * 1000 + update))
                  if algorithm == "PPO" else a2c_update(model, optimizer, valid, gamma=1.0, lam=1.0)))
        history.append({"update": update, "complete": sum(row["complete"] for row in batch),
                        "failures": [row["failure"] for row in batch if row["failure"]],
                        "zero_transition_failures": sum(row["zero_transition_failure"] for row in batch),
                        "failure_penalty_episodes": sum(row["failure_penalty_applied"] for row in batch),
                        **stats})
    decoded = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=cost_cap)
    while not decoded.terminated:
        observation = decoded.observation()
        action_index, _, _ = greedy_action(model, observation)
        decoded.step(observation["actions"][action_index])
    return model, (decoded.result() if decoded.done and decoded.failure is None else None), history


def run(output_dir: Path, *, updates=4, episodes=8):
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    instance, solution, anchor, scenario = fixture()
    raw_reference = replay_weather_solution(instance, anchor, scenario, solution,
                                            strict_weather_cap=False)
    cap = raw_reference["weather_cost"]
    static_route_reference = replay_weather_solution(instance, anchor, scenario, solution,
                                                      weather_cost_cap=cap)
    if not static_route_reference["admissible"]:
        raise RuntimeError(f"synthetic static-route reference is weather-infeasible: {static_route_reference['issues']}")
    started = time.perf_counter()
    greedy = greedy_physical(WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=cap))
    rows = {"PPO": [], "A2C": []}
    for algorithm in rows:
        for seed in SEEDS:
            model, result, history = train(instance, anchor, scenario, cap, algorithm, seed,
                                           updates=updates, episodes=episodes)
            checkpoint = output_dir / f"{algorithm.lower()}_seed{seed}.pt"
            torch.save({"state_dict": model.state_dict(), "algorithm": algorithm, "seed": seed,
                        "global_dim": WeatherFullMapEnv.global_dim,
                        "candidate_dim": WeatherFullMapEnv.candidate_dim,
                        "hidden_dim": model.hidden_dim, "schema": "weather_full_map_checkpoint_v1",
                        "runtime": _runtime_receipt()}, checkpoint)
            loaded = torch.load(checkpoint, map_location="cpu", weights_only=True)
            restored = WeatherPointerActorCritic(global_dim=loaded["global_dim"],
                                                 candidate_dim=loaded["candidate_dim"],
                                                 hidden_dim=loaded["hidden_dim"])
            restored.load_state_dict(loaded["state_dict"], strict=True)
            reload_observation = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=cap).observation()
            with torch.no_grad():
                source_logits, source_value = model(reload_observation["global"],
                                                     reload_observation["candidates"], reload_observation["mask"])
                restored_logits, restored_value = restored(reload_observation["global"],
                                                            reload_observation["candidates"], reload_observation["mask"])
            if not (torch.equal(source_logits, restored_logits) and torch.equal(source_value, restored_value)):
                raise RuntimeError("checkpoint reload inference round trip diverged")
            rows[algorithm].append({"seed": seed, "complete": result is not None,
                                    "result": result, "history": history,
                                    "checkpoint": str(checkpoint.resolve()),
                                    "checkpoint_sha256": _sha256(checkpoint),
                                    "checkpoint_bytes": checkpoint.stat().st_size,
                                    "checkpoint_reload_verified": True,
                                    "checkpoint_inference_round_trip_verified": True})
    report = {
        "schema": "weather_full_map_synthetic_smoke_v1",
        "scope": "synthetic engineering fixture only; not an author-map, registered, or formal result",
        "command": f"{sys.executable} {Path(__file__).name} --smoke --output-dir {output_dir}",
        "scenario": {"name": scenario.name, "wind_knots": [k.__dict__ for k in scenario.wind.knots],
                     "nfz": {"vertices": [[p.x_m, p.y_m] for p in scenario.no_fly_zone.vertices],
                             "on_s": scenario.no_fly_zone.on_s, "off_s": scenario.no_fly_zone.off_s}},
        "anchor": {"kind": "synthetic static-route reference replayed through common weather oracle",
                   "weather_score": static_route_reference, "weather_cost_cap": cap},
        "greedy_common_oracle": None if greedy is None else greedy["replay"],
        "runtime": _runtime_receipt(),
        "observation_schema": {"global_dim": WeatherFullMapEnv.global_dim,
                               "candidate_dim": WeatherFullMapEnv.candidate_dim,
                               "max_policy_slots": MAX_POLICY_SLOTS,
                               "max_policy_targets": MAX_POLICY_TARGETS},
        "training": {"algorithms": rows, "seeds": list(SEEDS), "updates": updates,
                     "episodes_per_update": episodes, "elapsed_seconds": time.perf_counter() - started},
    }
    (output_dir / "full_map_smoke_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("full_map_smoke_output"))
    parser.add_argument("--updates", type=int, default=4)
    parser.add_argument("--episodes", type=int, default=8)
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("only the explicit synthetic --smoke fixture is available")
    report = run(args.output_dir, updates=args.updates, episodes=args.episodes)
    print(json.dumps({"report": str((args.output_dir / "full_map_smoke_report.json").resolve()),
                      "weather_cost_cap": report["anchor"]["weather_cost_cap"]}, sort_keys=True))


if __name__ == "__main__":
    main()
