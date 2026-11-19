#!/usr/bin/env python3
"""Executable synthetic PPO/A2C smoke study for wind/NFZ route construction.

This command is deliberately a training-system integration test. It uses one
hand-built, explicitly synthetic fixture and must not be reported as a result
on the registered map partitions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

import numpy as np
import torch

from rl_algorithms import a2c_update, masked_policy_distribution, ppo_update
from weather_env import (NoFlyZone, Point, Target, WeatherInstance, WeatherRouteEnv,
                         WindField, WindKnot, FlightParams, replay_trips)
from weather_policy import WeatherPointerActorCritic, greedy_action


SMOKE_SEEDS = (103, 211, 307)


def synthetic_fixture() -> WeatherInstance:
    """Non-calibrated five-target map with an active temporary convex NFZ."""
    return WeatherInstance(
        station=Point(0.0, 0.0),
        targets=(Target(0, Point(1400.0, 300.0)), Target(1, Point(2200.0, 900.0)),
                 Target(2, Point(1650.0, -1000.0)), Target(3, Point(300.0, 1900.0)),
                 Target(4, Point(-950.0, 1250.0))),
        wind=WindField((WindKnot(0.0, 2.0, 0.0), WindKnot(180.0, -3.0, 4.0),
                        WindKnot(420.0, 1.0, -2.0))),
        no_fly_zone=NoFlyZone((Point(650.0, -300.0), Point(1350.0, -300.0),
                               Point(1350.0, 650.0), Point(650.0, 650.0)), 45.0, 390.0),
        flight=FlightParams(speed=900.0, flight_energy=0.018),
        coverage_radius_m=5000.0, energy_capacity=0.42, duty_limit_min=35.0,
        fixed_cost=2.0, time_cost=1.0,
    )


def nearest_route(instance: WeatherInstance) -> list[list[int]]:
    """Deterministic constructive control: next legal target minimizing leg arrival."""
    env = WeatherRouteEnv(instance, cost_cap=None)
    while not env.done:
        obs = env.observation()
        legal = [(i, action) for i, action in enumerate(obs["actions"]) if obs["mask"][i]]
        targets = [(i, action) for i, action in legal if not action.is_return]
        if targets:
            choice = min(targets, key=lambda pair: (
                float(obs["candidates"][pair[0], 1]), pair[1].target_id))
        else:
            choice = next((item for item in legal if item[1].is_return), None)
            if choice is None:
                raise RuntimeError("nearest controller hit physical/cost dead-end")
        env.step(choice[1])
    return env.result()["trips"]


def _run_greedy_env(env: WeatherRouteEnv, model=None):
    while not env.done:
        obs = env.observation()
        if not bool(obs["mask"].any()):
            return None
        if model is None:
            candidates = [(i, action) for i, action in enumerate(obs["actions"])
                          if obs["mask"][i] and not action.is_return]
            idx = (min(candidates, key=lambda pair: (float(obs["candidates"][pair[0], 1]),
                                                      pair[1].target_id))[0]
                   if candidates else int(np.flatnonzero(obs["mask"])[0]))
        else:
            idx, _, _ = greedy_action(model, obs)
        env.step(obs["actions"][idx])
    return env.result()


def rollout(env: WeatherRouteEnv, model: WeatherPointerActorCritic, *, stochastic: bool):
    transitions = []
    while not env.done:
        obs = env.observation()
        if not bool(obs["mask"].any()):
            return {"transitions": transitions, "complete": False, "reason": "dead_end"}
        with torch.no_grad():
            dist, value = masked_policy_distribution(model, obs)
            action = int(dist.sample().item()) if stochastic else int(torch.argmax(dist.logits).item())
            logp = float(dist.log_prob(torch.tensor(action)).item())
        next_obs, reward, done, _ = env.step(obs["actions"][action])
        # Keep an exposed future-infeasible prefix as a terminal failure
        # trajectory. It is never silently discarded or resampled.
        if bool(next_obs["dead_end"]):
            reward -= 25.0
            done = True
        transitions.append({"global": obs["global"], "candidates": obs["candidates"],
                            "mask": obs["mask"], "action": action, "reward": reward,
                            "done": done, "value": float(value.item()), "old_logp": logp})
    return {"transitions": transitions, "complete": env.done,
            "reason": None if env.done else "dead_end",
            "result": env.result() if env.done else None}


def _set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)


def train_one(instance, cap, algorithm: str, seed: int, *, updates=4, episodes_per_update=8):
    _set_seed(seed)
    model = WeatherPointerActorCritic()
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    log = []
    for update in range(updates):
        episodes = [rollout(WeatherRouteEnv(instance, cost_cap=cap), model, stochastic=True)
                    for _ in range(episodes_per_update)]
        sampled = [episode for episode in episodes if episode["transitions"]]
        if not sampled:
            raise RuntimeError("rollout batch contains no route decisions")
        stats = (ppo_update(model, optimizer, sampled, epochs=2, minibatch=32,
                            rng=random.Random(seed * 1000 + update))
                 if algorithm == "PPO" else a2c_update(model, optimizer, sampled))
        log.append({"update": update,
                    "complete_episodes": sum(ep["complete"] for ep in sampled), **stats})
    result = _run_greedy_env(WeatherRouteEnv(instance, cost_cap=cap), model)
    return model, result, log


def run_smoke(output_dir: Path, *, updates=4, episodes_per_update=8):
    output_dir.mkdir(parents=True, exist_ok=True)
    instance = synthetic_fixture()
    baseline_trips = nearest_route(instance)
    reference = replay_trips(instance, baseline_trips)
    if not reference["feasible"]:
        raise RuntimeError(f"reference route is infeasible: {reference['issues']}")
    # Smoke cap has a predeclared 25% synthetic allowance for policy exploration.
    cap = reference["cost"] * 1.25
    baseline_under_cap = replay_trips(instance, baseline_trips, cost_cap=cap)
    algorithms = {}
    for algorithm in ("PPO", "A2C"):
        rows = []
        for seed in SMOKE_SEEDS:
            _, selected, training = train_one(instance, cap, algorithm, seed,
                                               updates=updates, episodes_per_update=episodes_per_update)
            rows.append({"seed": seed, "selected": selected, "training": training,
                         "selected_complete": selected is not None,
                         "selected_cost_cap_satisfied": (selected is not None and
                                                         selected["cost_cap_satisfied"])})
        algorithms[algorithm] = rows
    report = {
        "schema": "weather_nfz_rl_synthetic_smoke_v1",
        "scope": "synthetic engineering fixture only; not a registered-map or scientific quality result",
        "command": f"{sys.executable} {Path(__file__).name} --smoke --output-dir {output_dir}",
        "fixture": {"target_count": len(instance.targets), "wind_knots": [k.__dict__ for k in instance.wind.knots],
                    "nfz_interval_s": [instance.no_fly_zone.on_s, instance.no_fly_zone.off_s],
                    "energy_capacity": instance.energy_capacity, "duty_limit_min": instance.duty_limit_min},
        "reference_controller": "deterministic nearest legal target with RETURN only when no target action is legal",
        "reference": {**reference, "trips": baseline_trips},
        "cost_cap": cap, "cost_cap_rule": "1.25 * synthetic nearest-route reference cost",
        "reference_under_cap": baseline_under_cap,
        "training": {"seeds": list(SMOKE_SEEDS), "updates": updates,
                     "episodes_per_update": episodes_per_update,
                     "algorithms": algorithms},
    }
    (output_dir / "smoke_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = ["# Synthetic Wind/NFZ RL Smoke Run", "",
             "This is an engineering integration fixture, not a registered-map result.", "",
             f"Reference MTC: {reference['MTC']:.6f} min", f"Reference cost: {reference['cost']:.6f}",
             f"Synthetic cap: {cap:.6f}", f"Reference trips: {baseline_trips}", ""]
    for algorithm, rows in algorithms.items():
        lines.extend([f"## {algorithm}", "", "| seed | complete | cap OK | MTC | cost |", "|---:|:---:|:---:|---:|---:|"])
        for row in rows:
            score = row["selected"]
            lines.append(f"| {row['seed']} | {bool(score)} | {row['selected_cost_cap_satisfied']} | "
                         f"{score['MTC'] if score else 'NA'} | {score['cost'] if score else 'NA'} |")
        lines.append("")
    (output_dir / "SMOKE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run the synthetic engineering fixture")
    parser.add_argument("--output-dir", type=Path, default=Path("smoke_output"))
    parser.add_argument("--updates", type=int, default=4)
    parser.add_argument("--episodes-per-update", type=int, default=8)
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("only --smoke is provided; it is not the registered-map study runner")
    report = run_smoke(args.output_dir, updates=args.updates, episodes_per_update=args.episodes_per_update)
    print(json.dumps({"report": str((args.output_dir / "smoke_report.json").resolve()),
                      "reference_MTC": report["reference"]["MTC"]}, sort_keys=True))


if __name__ == "__main__":
    main()
