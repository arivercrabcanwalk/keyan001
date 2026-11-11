import copy
import math
import random
import unittest

import torch
from torch import nn

from rl_algorithms import (a2c_update, behavior_clone_update, masked_policy_distribution,
                           ppo_update, reinforce_update)


class TinyPointerPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(0.37))
        self.value_bias = nn.Parameter(torch.tensor(0.12))

    def forward(self, global_features, candidate_features, action_mask=None):
        target_logits = candidate_features[:, 0] * self.scale
        return_logit = global_features[0] * 0.2 - self.scale * 0.1
        logits = torch.cat([target_logits, return_logit.reshape(1)])
        value = self.value_bias + global_features[0] * 0.15
        return logits, value


def observation(global_value, candidate_values, mask):
    return {
        "global": torch.tensor([global_value, 0.0], dtype=torch.float32),
        "candidates": torch.tensor([[x, 0.0] for x in candidate_values], dtype=torch.float32),
        "mask": torch.tensor(mask, dtype=torch.bool),
    }


def make_rollouts(model):
    definitions = [
        [
            (observation(0.1, [0.4, 0.9], [True, False, True]), 0, 0.7, False),
            (observation(0.3, [0.2], [True, True]), 1, -0.1, True),
        ],
        [
            (observation(-0.2, [0.7, -0.1, 0.5], [False, True, True, True]), 2, 0.4, True),
        ],
    ]
    episodes = []
    for rows in definitions:
        transitions = []
        for obs, action, reward, done in rows:
            dist, value = masked_policy_distribution(model, obs)
            transitions.append({
                **obs,
                "action": action,
                "old_logp": float(dist.log_prob(torch.tensor(action)).detach()),
                "value": float(value.detach()),
                "reward": reward,
                "done": done,
            })
        episodes.append({"transitions": transitions})
    return episodes


class RLAlgorithmsTests(unittest.TestCase):
    def test_masked_distribution_assigns_exact_zero_to_excluded_actions(self):
        model = TinyPointerPolicy()
        obs = observation(0.5, [0.3, 0.8], [True, False, True])
        dist, _ = masked_policy_distribution(model, obs)
        probs = dist.probs
        self.assertEqual(float(probs[1].detach()), 0.0)
        self.assertAlmostEqual(float(probs.sum().detach()), 1.0, places=7)

    def test_ppo_and_a2c_updates_are_finite(self):
        torch.manual_seed(19)
        model = TinyPointerPolicy()
        episodes = make_rollouts(model)
        ppo_stats = ppo_update(
            model, torch.optim.Adam(model.parameters(), lr=1e-2), episodes,
            epochs=2, minibatch=2,
        )
        self.assertEqual(ppo_stats["algorithm"], "PPO")
        self.assertEqual(ppo_stats["transitions"], 3)
        self.assertTrue(all(math.isfinite(ppo_stats[k]) for k in (
            "policy_loss", "value_loss", "entropy", "clip_fraction"
        )))
        self.assertEqual(ppo_stats["updates"], 4)

        torch.manual_seed(19)
        model = TinyPointerPolicy()
        episodes = make_rollouts(model)
        a2c_stats = a2c_update(
            model, torch.optim.Adam(model.parameters(), lr=1e-2), episodes,
        )
        self.assertEqual(a2c_stats["algorithm"], "A2C")
        self.assertEqual(a2c_stats["updates"], 1)
        self.assertEqual(a2c_stats["transitions"], 3)
        self.assertTrue(all(math.isfinite(a2c_stats[k]) for k in (
            "policy_loss", "value_loss", "entropy"
        )))

    def test_ppo_clipping_path_is_reported(self):
        torch.manual_seed(7)
        model = TinyPointerPolicy()
        episodes = make_rollouts(model)
        for episode in episodes:
            for item in episode["transitions"]:
                item["old_logp"] -= 0.8
        stats = ppo_update(
            model, torch.optim.SGD(model.parameters(), lr=0.0), episodes,
            epochs=1, minibatch=8, clip=0.2,
        )
        self.assertGreater(stats["clip_fraction"], 0.0)

    def test_reinforce_update_is_finite_and_masked(self):
        torch.manual_seed(29)
        model = TinyPointerPolicy()
        episodes = make_rollouts(model)
        stats = reinforce_update(model, torch.optim.Adam(model.parameters(), lr=1e-2), episodes, gamma=0.95)
        self.assertEqual(stats["algorithm"], "REINFORCE")
        self.assertEqual(stats["updates"], 1)
        self.assertEqual(stats["transitions"], 3)
        self.assertTrue(all(math.isfinite(stats[k]) for k in ("policy_loss", "entropy")))

    def test_behavior_cloning_uses_only_legal_masked_actions(self):
        torch.manual_seed(43)
        model = TinyPointerPolicy()
        demonstrations = make_rollouts(model)
        stats = behavior_clone_update(model, torch.optim.Adam(model.parameters(), lr=1e-2),
                                      demonstrations, epochs=2, minibatch=2,
                                      rng=random.Random(43))
        self.assertEqual(stats["algorithm"], "behavior_cloning")
        self.assertEqual(stats["demonstration_transitions"], 3)
        self.assertEqual(stats["updates"], 4)
        self.assertTrue(math.isfinite(stats["negative_log_likelihood"]))

    def test_behavior_cloning_improves_probability_and_leaves_independent_value_bias(self):
        model = TinyPointerPolicy()
        obs = observation(0.0, [1.0, -1.0], [True, True, False])
        before = float(masked_policy_distribution(model, obs)[0].probs[0].detach())
        critic_before = model.value_bias.detach().clone()
        behavior_clone_update(model, torch.optim.SGD(model.parameters(), lr=0.1),
                              [{"transitions": [{**obs, "action": 0}]}], epochs=8)
        after = float(masked_policy_distribution(model, obs)[0].probs[0].detach())
        self.assertGreater(after, before)
        torch.testing.assert_close(model.value_bias.detach(), critic_before, atol=0, rtol=0)
        with self.assertRaises(ValueError):
            behavior_clone_update(model, torch.optim.SGD(model.parameters(), lr=0.1),
                                  [{"transitions": [{**obs, "action": 2}]}], epochs=1)

    def test_real_shared_encoder_bc_keeps_value_head_parameters_without_freezing_features(self):
        from weather_policy import WeatherPointerActorCritic
        torch.manual_seed(47)
        model = WeatherPointerActorCritic(global_dim=2, candidate_dim=2, hidden_dim=8)
        obs = {"global": torch.tensor([0.8, -0.3]),
               "candidates": torch.tensor([[1.0, 0.2], [-0.5, 0.7]]),
               "mask": torch.tensor([True, True])}
        head_before = {name: value.detach().clone() for name, value in model.value_head.named_parameters()}
        encoder_before = {name: value.detach().clone() for name, value in model.global_encoder.named_parameters()}
        before_value = float(model(obs["global"], obs["candidates"], obs["mask"])[1].detach())
        behavior_clone_update(model, torch.optim.Adam(model.parameters(), lr=0.03),
                              [{"transitions": [{**obs, "action": 0}]}], epochs=3)
        for name, value in model.value_head.named_parameters():
            torch.testing.assert_close(value.detach(), head_before[name], atol=0, rtol=0)
        self.assertTrue(any(not torch.equal(value.detach(), encoder_before[name])
                            for name, value in model.global_encoder.named_parameters()))
        self.assertNotEqual(float(model(obs["global"], obs["candidates"], obs["mask"])[1].detach()), before_value)

    def test_behavior_cloning_honors_expired_deadline(self):
        model = TinyPointerPolicy()
        with self.assertRaises(TimeoutError):
            behavior_clone_update(model, torch.optim.SGD(model.parameters(), lr=0.1),
                                  make_rollouts(model), deadline=0.0)

    def test_a2c_does_not_depend_on_old_logp_or_apply_ppo_clipping(self):
        torch.manual_seed(23)
        base = TinyPointerPolicy()
        episodes_a = make_rollouts(base)
        episodes_b = copy.deepcopy(episodes_a)
        for episode in episodes_b:
            for item in episode["transitions"]:
                item["old_logp"] += 50.0
        model_a, model_b = copy.deepcopy(base), copy.deepcopy(base)
        stats_a = a2c_update(model_a, torch.optim.SGD(model_a.parameters(), lr=0.03), episodes_a)
        stats_b = a2c_update(model_b, torch.optim.SGD(model_b.parameters(), lr=0.03), episodes_b)
        self.assertNotIn("clip_fraction", stats_a)
        for param_a, param_b in zip(model_a.parameters(), model_b.parameters()):
            torch.testing.assert_close(param_a, param_b, rtol=0, atol=0)
        self.assertEqual(stats_a["policy_loss"], stats_b["policy_loss"])

    def test_updates_are_reproducible_with_fixed_seed_and_shuffle_rng(self):
        torch.manual_seed(31)
        base = TinyPointerPolicy()
        episodes = make_rollouts(base)
        model_a, model_b = copy.deepcopy(base), copy.deepcopy(base)
        stats_a = ppo_update(
            model_a, torch.optim.Adam(model_a.parameters(), lr=1e-3), episodes,
            epochs=3, minibatch=2, rng=random.Random(31),
        )
        stats_b = ppo_update(
            model_b, torch.optim.Adam(model_b.parameters(), lr=1e-3), episodes,
            epochs=3, minibatch=2, rng=random.Random(31),
        )
        for param_a, param_b in zip(model_a.parameters(), model_b.parameters()):
            torch.testing.assert_close(param_a, param_b, rtol=0, atol=0)
        self.assertEqual(stats_a, stats_b)


if __name__ == "__main__":
    unittest.main()
