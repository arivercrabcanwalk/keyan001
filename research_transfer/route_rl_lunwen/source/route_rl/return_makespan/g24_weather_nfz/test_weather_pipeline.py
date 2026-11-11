"""Tests for the synthetic weather/NFZ physical-action training pipeline."""
from __future__ import annotations

from math import isclose
from pathlib import Path
import tempfile
import unittest

import torch

from run_experiment import (SMOKE_SEEDS, nearest_route, rollout, run_smoke,
                            synthetic_fixture)
from weather_env import RouteAction, WeatherRouteEnv, replay_trips
from weather_oracle import _inside_distance_interval, _integrate_leg, _time_at_distance
from weather_policy import WeatherPointerActorCritic


def assert_oracle_nfz_clear(testcase, instance, legs):
    """Independently replay each returned oracle segment against its active NFZ."""
    zone = instance.no_fly_zone
    for leg in legs:
        polyline = leg["polyline"]
        now = leg["departure_s"]
        for left, right in zip(polyline, polyline[1:]):
            from weather_oracle import Point
            segment, profile = _integrate_leg(Point(*left), Point(*right), now,
                                              instance.wind, instance.flight)
            inside = _inside_distance_interval(segment.start, segment.end, zone)
            if inside is not None:
                entry = _time_at_distance(profile, inside[0])
                exit_ = _time_at_distance(profile, inside[1])
                testcase.assertFalse(max(entry, zone.on_s) < min(exit_, zone.off_s),
                                     f"active NFZ overlap on {leg}")
            now = segment.arrival_time_s
        testcase.assertAlmostEqual(now, leg["arrival_s"], places=7)


class WeatherPipelineTests(unittest.TestCase):
    def setUp(self):
        self.instance = synthetic_fixture()
        self.trips = nearest_route(self.instance)
        self.reference = replay_trips(self.instance, self.trips)
        self.cap = self.reference["cost"] * 1.25

    def test_reference_physics_nfz_cost_and_mtc(self):
        score = replay_trips(self.instance, self.trips, cost_cap=self.cap)
        self.assertTrue(score["feasible"], score["issues"])
        self.assertTrue(score["cost_cap_satisfied"])
        self.assertLessEqual(score["M_return"], self.instance.duty_limit_min + 1e-7)
        self.assertLessEqual(score["cost"], self.cap + 1e-7)
        # Independently recompute MTC from immutable per-target completion times.
        expected_mtc = sum(score["completion_min"].values()) / len(self.instance.targets)
        self.assertAlmostEqual(score["MTC"], expected_mtc)
        assert_oracle_nfz_clear(self, self.instance, score["legs"])

    def test_exact_physical_mask_and_environment_result(self):
        env = WeatherRouteEnv(self.instance, cost_cap=self.cap)
        first = env.observation()
        self.assertFalse(first["mask"][-1], "RETURN is forbidden before a trip starts")
        self.assertEqual(first["actions"][-1], RouteAction())
        self.assertTrue(first["mask"].any())
        # An explicit illegal nonmember and the empty RETURN action cannot mutate the state.
        before = env.observation()
        with self.assertRaises(ValueError):
            env.step(RouteAction(999))
        self.assertEqual(before["target_ids"], env.observation()["target_ids"])
        # Replay the deterministic physical witness only through reported legal actions.
        for trip in self.trips:
            for target_id in trip:
                obs = env.observation()
                action = RouteAction(target_id)
                index = obs["actions"].index(action)
                self.assertTrue(obs["mask"][index], action)
                env.step(action)
            obs = env.observation()
            index = obs["actions"].index(RouteAction())
            self.assertTrue(obs["mask"][index])
            env.step(RouteAction())
        result = env.result()
        self.assertTrue(result["cost_cap_satisfied"])
        self.assertAlmostEqual(result["MTC"], self.reference["MTC"])
        self.assertEqual(result["trips"], self.trips)
        # The reward is the negative sum of individual completion / N, not M_return.
        env2 = WeatherRouteEnv(self.instance, cost_cap=self.cap)
        rewards = []
        for trip in self.trips:
            for target_id in trip:
                _, reward, _, _ = env2.step(RouteAction(target_id)); rewards.append(reward)
            _, reward, _, _ = env2.step(RouteAction()); rewards.append(reward)
        self.assertAlmostEqual(sum(rewards), -self.reference["MTC"])

    def test_rollout_and_both_updates_use_masked_variable_actions(self):
        torch.manual_seed(17)
        model = WeatherPointerActorCritic()
        episode = rollout(WeatherRouteEnv(self.instance, cost_cap=self.cap), model, stochastic=True)
        self.assertTrue(episode["transitions"])
        for transition in episode["transitions"]:
            self.assertTrue(bool(transition["mask"][transition["action"]]))
            self.assertTrue(transition["done"] or transition["reward"] <= 0.0)
        # The smoke command invokes the real PPO and A2C update paths for every fixed seed.
        with tempfile.TemporaryDirectory() as directory:
            report = run_smoke(Path(directory), updates=1, episodes_per_update=2)
            self.assertEqual(report["training"]["seeds"], list(SMOKE_SEEDS))
            for algorithm in ("PPO", "A2C"):
                rows = report["training"]["algorithms"][algorithm]
                self.assertEqual([row["seed"] for row in rows], list(SMOKE_SEEDS))
                self.assertTrue(all(row["training"] for row in rows))
                self.assertTrue((Path(directory) / "smoke_report.json").is_file())


if __name__ == "__main__":
    unittest.main()
