"""Regression tests for bounded failure ordering in PPO/A2C smoke rollouts."""
from pathlib import Path
import unittest
import sys

import numpy as np
import torch

PACKAGE_ROOT = Path(__file__).resolve().parent
LUNWEN_ROOT = PACKAGE_ROOT.parents[3]
for import_root in (PACKAGE_ROOT, PACKAGE_ROOT.parent,
                    LUNWEN_ROOT / "reproduction/reviewer_package_semfix"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import run_full_map_smoke as runner
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from scorer import CostAnchor
from weather_full_map import WeatherFullMapEnv, WeatherMapAction, WeatherMapScenario
from weather_oracle import WindField, WindKnot


def dead_end_fixture():
    params = Parameters(speed=900, flight_energy=.018, small_battery=99, large_battery=99,
                        small_radius=10000, large_radius=10000, small_duration=999,
                        large_duration=999, time_cost=1)
    instance = Instance("dead_end", (Node(1, 900, 0, 0, 0), Node(2, 800, 0, 0, 60)),
                        (Node(100, 0, 0, 0, 0),), "dead_end", params)
    solution = empty_solution(instance, [1])
    solution["routes"] = [[[], [[2, 1]]]]
    anchor = CostAnchor.from_solution(instance, solution)
    scenario = WeatherMapScenario(WindField((WindKnot(0, 0, 0), WindKnot(60, 20, 0),
                                             WindKnot(200, 0, 0))), name="timed-headwind")
    return instance, anchor, scenario


class FirstAction(torch.nn.Module):
    def forward(self, global_features, candidates, mask):
        logits = torch.zeros(mask.numel(), device=mask.device)
        logits[int(torch.nonzero(mask, as_tuple=False)[0])] = 1000.0
        return logits, torch.zeros((), device=mask.device)


class OneStepFailureEnv:
    def __init__(self, instance, failure):
        self.instance, self.failure, self.want_failure = instance, None, failure
        self.done = False
        self.terminated = False

    def observation(self):
        return {"global": np.zeros(2, np.float32), "candidates": np.zeros((1, 20), np.float32),
                "mask": np.ones(1, np.bool_), "actions": (WeatherMapAction(0, 1),)}

    def step(self, action):
        self.failure = self.want_failure
        self.done = self.want_failure != "dead_end"
        self.terminated = True
        return self.observation(), -4.0, True, {"failure": self.failure}


class EmptyDeadEndEnv:
    global_dim = WeatherFullMapEnv.global_dim
    candidate_dim = WeatherFullMapEnv.candidate_dim

    def __init__(self, instance, *args, **kwargs):
        self.instance, self.failure, self.done, self.terminated = instance, "dead_end", False, True


class FailureRewardTests(unittest.TestCase):
    def test_bounded_penalty_dominates_feasible_makespan_and_real_dead_end(self):
        instance, anchor, scenario = dead_end_fixture()
        feasible_return = -62.0
        bound = runner.feasible_makespan_upper_bound(instance)
        penalty = runner.failure_reward_penalty(instance)
        self.assertAlmostEqual(bound, 999.0 + 1e-7)
        self.assertGreater(penalty, bound)
        self.assertLess(-penalty, feasible_return)
        self.assertGreater(-26.0, feasible_return)
        env = WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap=1e9)
        episode = runner.rollout(env, FirstAction(), stochastic=False)
        self.assertEqual(episode["failure"], "dead_end")
        self.assertTrue(episode["failure_penalty_applied"])
        self.assertLess(sum(item["reward"] for item in episode["transitions"]), feasible_return)

    def test_terminal_replay_rejection_is_penalized(self):
        instance, _, _ = dead_end_fixture()
        episode = runner.rollout(OneStepFailureEnv(instance, "terminal_replay_rejected"),
                                 FirstAction(), stochastic=False)
        self.assertEqual(episode["failure"], "terminal_replay_rejected")
        self.assertTrue(episode["failure_penalty_applied"])
        self.assertLess(sum(item["reward"] for item in episode["transitions"]),
                        -runner.feasible_makespan_upper_bound(instance))

    def test_lambda_one_preserves_terminal_failure_order(self):
        from rl_algorithms import add_gae
        instance, _, _ = dead_end_fixture()
        penalty = runner.failure_reward_penalty(instance)
        success = {"transitions": [{"reward": -62.0, "value": 0.0, "done": True}]}
        failure = {"transitions": [{"reward": 0.0, "value": 0.0, "done": False} for _ in range(99)] +
                                   [{"reward": -penalty, "value": 0.0, "done": True}]}
        exact = add_gae([failure], gamma=1.0, lam=1.0)[0]["return"]
        truncated = add_gae([failure], gamma=1.0, lam=.95)[0]["return"]
        valid = add_gae([success], gamma=1.0, lam=1.0)[0]["return"]
        self.assertLess(exact, valid)
        self.assertGreater(truncated, valid)

    def test_zero_transition_failures_are_counted_and_updates_skipped(self):
        instance, anchor, scenario = dead_end_fixture()
        original_env, original_rollout = runner.WeatherFullMapEnv, runner.rollout
        try:
            runner.WeatherFullMapEnv = EmptyDeadEndEnv
            runner.rollout = lambda env, model, **kwargs: {
                "transitions": [], "complete": False, "failure": "dead_end",
                "failure_reward_penalty_min": 0.0, "failure_penalty_applied": False,
                "zero_transition_failure": True, "result": None}
            _, result, history = runner.train(instance, anchor, scenario, 1e9, "PPO", 103,
                                              updates=1, episodes=2)
        finally:
            runner.WeatherFullMapEnv, runner.rollout = original_env, original_rollout
        self.assertIsNone(result)
        self.assertEqual(history[0]["failures"], ["dead_end", "dead_end"])
        self.assertEqual(history[0]["zero_transition_failures"], 2)
        self.assertTrue(history[0]["skipped_update_no_transitions"])

    def test_ppo_and_a2c_pin_gamma_and_lambda_to_one(self):
        instance, anchor, scenario = dead_end_fixture()
        original_env, original_rollout = runner.WeatherFullMapEnv, runner.rollout
        original_ppo, original_a2c = runner.ppo_update, runner.a2c_update
        seen = []
        def update(*args, **kwargs):
            seen.append((kwargs["gamma"], kwargs["lam"]))
            return {"updates": 1, "transitions": 1}
        try:
            runner.WeatherFullMapEnv = EmptyDeadEndEnv
            runner.rollout = lambda env, model, **kwargs: {
                "transitions": [{"reward": -1}], "complete": False,
                "failure": "dead_end", "failure_reward_penalty_min": runner.failure_reward_penalty(instance),
                "failure_penalty_applied": True, "zero_transition_failure": False, "result": None}
            runner.ppo_update = update
            runner.a2c_update = update
            for algorithm in ("PPO", "A2C"):
                runner.train(instance, anchor, scenario, 1e9, algorithm, 103, updates=1, episodes=1)
        finally:
            runner.WeatherFullMapEnv, runner.rollout = original_env, original_rollout
            runner.ppo_update, runner.a2c_update = original_ppo, original_a2c
        self.assertEqual(seen, [(1.0, 1.0), (1.0, 1.0)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
