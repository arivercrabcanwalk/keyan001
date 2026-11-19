"""Synthetic probability / frozen-weight evidence only; no map, solve or training.

Run each package in an independent import namespace via the fixture. No optimizer
is constructed and no model parameter is updated in this file.
"""
import importlib
import itertools
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

TEST_BASE = Path(__file__).resolve().parents[1]
PACKAGES = [TEST_BASE.name] if TEST_BASE.name in ("rlv3_weather", "rlv3_emergency") else ["rlv3_weather", "rlv3_emergency"]

@pytest.fixture(params=PACKAGES)
def modules(request, monkeypatch):
    root = TEST_BASE if TEST_BASE.name == request.param else TEST_BASE / request.param
    monkeypatch.setenv("RLV3_ROOT", str(root))
    monkeypatch.syspath_prepend(str(root))
    # This suite runs in a single package process. Replacing live module classes
    # here breaks pickle identity in subsequent weather and spawn tests.
    return SimpleNamespace(**{name: importlib.import_module("rlcore." + name)
                              for name in ("train", "agent", "model", "feat", "tune")})


def test_loo_matches_exact_expected_reward_gradient(modules):
    """Enumerate the complete two-rollout sample space, including shared worlds."""
    p, scale = 0.37, 7.0
    estimate = 0.0
    for world, world_prob in [(0.0, .4), (3.0, .6)]:
        for actions in itertools.product((0, 1), repeat=2):
            probability = math.prod(p if a else 1 - p for a in actions)
            costs = [world + (2.0 if a else 9.0) for a in actions]
            advantages = modules.train.loo_advantages(costs, scale)
            score = [a - p for a in actions]
            estimate += world_prob * probability * np.dot(advantages, score) / 2
    expected = (9.0 - 2.0) * p * (1 - p) / scale
    assert estimate == pytest.approx(expected, abs=1e-14)


def test_episode_denominator_includes_no_action_failure(modules):
    tk, cx, mk = np.zeros((2, 34), np.float32), np.zeros(24, np.float32), np.ones(2, bool)
    dec = (tk, cx, mk, 1, 0)
    groups = [[dict(Jsh=1000.0, dec=[]), dict(Jsh=10.0, dec=[dec, dec, dec])]]
    samples, advantages, episodes = modules.train.pg_samples(groups, 100.0)
    assert episodes == 2 and len(samples) == 3
    assert advantages == pytest.approx([9.9] * 3)
    assert samples[0][0].dtype == np.float32


def test_variable_length_trajectory_gradient_is_episode_weighted(modules):
    theta, h = -.2, 1e-6
    def law(x):
        p = 1 / (1 + math.exp(-x))
        # Stop after action 0; action 1 causes another stochastic decision.
        return [(1-p, 9.0, -p), (p*(1-p), 3.0, 1-2*p), (p*p, 1.0, 2*(1-p))]
    estimate = 0.0
    for (p1, c1, s1), (p2, c2, s2) in itertools.product(law(theta), repeat=2):
        A = modules.train.loo_advantages([c1, c2], 1.0)
        estimate += p1*p2*(A[0]*s1+A[1]*s2)/2
    expected = lambda x: -sum(p*c for p, c, _ in law(x))
    assert estimate == pytest.approx((expected(theta+h)-expected(theta-h))/(2*h), rel=1e-8)


def test_temperature_score_matches_finite_difference(modules):
    theta, temp, step = .43, .37, 1e-6
    mask = torch.tensor([[True, True, False]])
    logits = torch.tensor([[theta, -.21, 9.0]], dtype=torch.float64, requires_grad=True)
    lp = modules.agent.action_log_probs(logits, mask, temp)[0, 0]
    derivative, = torch.autograd.grad(lp, logits)
    def value(x):
        z = np.array([x, -.21]) / temp
        return z[0] - np.logaddexp.reduce(z)
    finite_difference = (value(theta + step) - value(theta - step)) / (2 * step)
    assert derivative[0, 0].item() == pytest.approx(finite_difference, rel=1e-8)
    assert derivative[0, 2].item() == 0.0
    assert torch.isneginf(modules.agent.action_log_probs(logits, mask, temp)[0, 2])


def test_invalid_action_set_and_temperature_fail_explicitly(modules):
    tok = np.zeros((2, 34), np.float32); ctx = np.zeros(24, np.float32)
    with pytest.raises(ValueError, match="no legal"):
        modules.model.collate([(tok, ctx, np.zeros(2, bool))])
    with pytest.raises(ValueError, match="temperature"):
        modules.agent.action_log_probs(torch.zeros((1, 2)), torch.ones((1, 2), dtype=torch.bool), 0)
    model = modules.model.Policy(d=8, heads=2, layers=1)
    with pytest.raises(ValueError, match="legal physical"):
        model(torch.zeros((1, 2, 34)), torch.zeros((1, 24)), torch.zeros((1, 2), dtype=torch.bool))


def test_hidden_latent_future_sampler_never_qualifies(modules):
    for R in (0, 1, 3):
        with pytest.raises(ValueError):
            modules.train.require_public_sampler(SimpleNamespace(), R)
    modules.train.require_public_sampler(SimpleNamespace(public_future_sampler_verified=True), 2)


def test_tuning_never_silently_downgrades_failed_family(modules):
    grid = {"weak": ["x"], "complete": ["y", "z"]}
    agg = {"x": dict(J=0.0, strict=0.0, physical=1.0, qualified=0.0, score=0.0),
           "y": dict(J=100.0, strict=1.0, physical=1.0, qualified=1.0, score=100.0),
           "z": dict(J=1.0, strict=1.0, physical=0.0, qualified=0.0, score=1.0)}
    best, overall, failed = modules.tune.select_qualified(grid, agg)
    assert best == {"complete-T": "y"} and overall == "y" and failed == ["weak"]
    assert modules.tune.select_qualified({"weak": ["x"]}, agg) == ({}, None, ["weak"])


def test_ablation_is_explicit_and_does_not_mutate_observation(modules):
    tok = np.ones((3, 34), np.float32); ctx = np.ones(24, np.float32)
    new, cnew = modules.agent.ablate(tok, ctx, "nophys_noplan")
    assert np.all(new[:, 13:19] == 0) and np.all(new[:, 21:24] == 0)
    assert np.all(cnew[8:16] == 0) and np.all(tok == 1) and np.all(ctx == 1)
    with pytest.raises(ValueError, match="unknown"):
        modules.agent.ablate(tok, ctx, "typo")


def test_v2_checkpoint_and_changed_file_identity(modules, tmp_path):
    model = modules.model.Policy(d=8, heads=2, layers=1)
    ck = dict(model=model.state_dict(), arch=dict(d=8, heads=2, layers=1), feat_ablate="none", base="none",
              learning_schema=modules.agent.LEARNING_SCHEMA)
    path = tmp_path / "frozen.pt"
    torch.save(ck, path)
    assert modules.agent.load_policy(path)[2] == "none"
    ck["base"] = "GREEDY"
    torch.save(ck, path)
    assert modules.agent.load_policy(path)[2] == "GREEDY"
    ck.pop("learning_schema"); torch.save(ck, path)
    with pytest.raises(ValueError, match="schema"):
        modules.agent.load_policy(path)


def test_rng_roundtrip_and_group_seed_identity(modules):
    import random
    random.seed(7); np.random.seed(8); torch.manual_seed(9)
    driver = random.Random(10)
    state = modules.train.capture_rng(driver)
    first = (driver.random(), random.random(), np.random.random(), torch.rand(2))
    modules.train.restore_rng(state, driver)
    second = (driver.random(), random.random(), np.random.random(), torch.rand(2))
    assert first[:3] == second[:3] and torch.equal(first[3], second[3])
    seeds = {modules.train.rollout_seed(0, i, g) for i in range(3) for g in range(110)}
    assert len(seeds) == 330


def test_checkpoint_completion_requires_physics_and_return(modules):
    good = dict(J=1.0, complete_strict=1, physically_feasible=1, all_returned=1, timeout=0, failed=0)
    assert modules.train.eligible_result(good)
    for field, value in [("J", float("nan")), ("physically_feasible", 0), ("all_returned", 0), ("timeout", 1), ("failed", 1)]:
        assert not modules.train.eligible_result(dict(good, **{field: value}))


def test_B_qualification_keeps_failed_urgent_releases_in_primary(modules):
    result = dict(J=1001., routine_total=2, routine_done=2, physically_feasible=1, all_returned=1,
                  failed=0, complete_strict=0, timeout=1, high_on_time=0, high_total=3)
    assert modules.train.eligible_result(result, "emerg_clustered_high")
    assert not modules.train.eligible_result(dict(result, routine_done=1), "emerg_clustered_high")
    assert modules.train.development_score([result], "emerg_clustered_high") == 0.
    extra = dict(result, high_on_time=2, high_total=2)
    assert modules.train.development_score([result, extra], "emerg_clustered_high") == -.4
    assert modules.train.development_score([dict(result, high_total=0)], "emerg_low") is None
    agg = {"x": dict(J=1., qualified=1., score=-.1), "y": dict(J=100., qualified=1., score=-.8),
           "z": dict(J=0., qualified=0., score=-1.)}
    assert modules.tune.select_qualified({"F": ["x", "y", "z"]}, agg, "urg") == ({"F-T": "y"}, "y", [])


def test_frozen_policy_replays_exact_sampling_distribution(modules, monkeypatch):
    tok = np.arange(3 * 34, dtype=np.float32).reshape(3, 34) / 100
    ctx = np.arange(24, dtype=np.float32) / 100
    mask = np.array([True, False, True]); actions = [17, 18, -2]
    monkeypatch.setattr(modules.agent, "featurize", lambda *args: (tok, ctx, mask, actions))
    class Fixed(torch.nn.Module):
        def forward(self, token, context, legal):
            return torch.tensor([[.4, 200.0, -.9]])
    class CaptureRng:
        def choice(self, n, p):
            self.p = p.copy()
            return int(np.argmax(p))
    rng = CaptureRng()
    policy = modules.agent.RLPolicy(Fixed(), greedy=False, temp=.4, rng=rng, collect=True)
    policy.reset(None)
    assert policy.act(None, ({"st": 0},)) == 17
    stored = policy.buf[0]
    t, c, m = modules.model.collate([(stored[0], stored[1], stored[2])])
    score_distribution = modules.agent.action_log_probs(policy.m(t, c, m), m, .4).exp()[0].numpy()
    np.testing.assert_array_equal(rng.p, score_distribution)
    assert stored[0].dtype == np.float32 and rng.p[1] == 0.0


def test_teacher_recorder_binds_physical_action_label(modules, monkeypatch):
    tok = np.zeros((3, 34), np.float32); ctx = np.zeros(24, np.float32)
    mask = np.array([False, True, True]); actions = [7, 9, -1]
    class Teacher:
        name = "HAND"
        def reset(self, env):
            pass
        def act(self, env, cur):
            return 9
    seen = []
    def features(env, cur, suggest):
        seen.append(suggest)
        return tok, ctx, mask, actions
    monkeypatch.setattr(modules.train, "featurize", features)
    recorder = modules.train.Recorder(Teacher(), "none", True)
    recorder.reset(None)
    assert recorder.act(None, None) == 9 and recorder.buf[0][3] == 1 and seen == [9]
    mask[1] = False
    with pytest.raises(ValueError, match="illegal"):
        recorder.act(None, None)


def test_infinite_masked_physics_does_not_enter_attention(modules):
    env = SimpleNamespace(calm=True, t=0., st=[dict(x=0., y=0., drones=[0])],
                          L={"drones": [dict(trips=[[7]])]}, tid2j={7: 0}, margin=0., rank={7: (0, 0, 1)})
    d = dict(i=0, st=0, cap=1., e=0., x=0., y=0., at_st=True, busy=0., limit=600., ntrip=0)
    task = dict(j=0, tid=7, x=1., y=1., urgent=0, prio=0, st=0, done=False, svc=10.)
    env.tasks = [task]; env.dr = [d]
    inf = dict(e1=float("inf"), h=.2, e2=float("inf"), need=float("inf"), t1=float("inf"), t2=float("inf"))
    tok, ctx, mask, actions = modules.feat.featurize(env, (d, [task], [False], [inf], False, True))
    assert np.isfinite(tok).all() and np.isfinite(ctx).all() and not mask[0]
    assert np.all(tok[0] == 0.) and actions == [0, -1, -2]
