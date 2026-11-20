"""Focused engineering tests; execute only on the authorized server.

The numerical PG test mocks all physical rollouts and checks a nonzero update
on a finite two-action policy. It is not a map-quality or training experiment.
"""
import copy
import importlib
import itertools
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rlcore.env import Env
from rlcore.event_learning import (Episode, collect_bc, input_sha, loo_advantages,
                                  parameter_sha, rollout, train_pg)
from rlcore.explore_emergency import METHODS, summarize
from rlcore.explore_emergency_inputs import build_inputs, canonical_sha, make_env, make_layout
from rlcore.feat import featurize
from rlcore.policies import Greedy


def _request(t=100.0, x=900.0):
    return dict(rid=0, tid=1, x=x, y=0.0, t=t, prio=1, dl=t+20,
                svc=10.0, energy=.2)


def test_corpus_repeatability_and_train_evaluation_isolation():
    first = build_inputs(20261120, "quick")
    second = build_inputs(20261120, "quick")
    assert canonical_sha(first) == canonical_sha(second)
    train = first["train_bc"]+first["train_pg"]
    evaluation = first["evaluation"]
    assert not ({row["map_sha256"] for row in train} & {row["map_sha256"] for row in evaluation})
    assert not ({row["event_seed"] for row in train} & {row["event_seed"] for row in evaluation})
    assert len(evaluation) == 24
    assert first["provenance"].startswith("generated_synthetic_non_author")


def test_fresh_same_case_environments_share_inputs_but_not_mutable_state():
    case = build_inputs(20261120, "quick")["evaluation"][0]
    first, second = make_env(case), make_env(case)
    assert input_sha(first) == input_sha(second)
    first.tasks[0]["done"] = True
    first.L["drones"][0]["trips"].clear()
    assert not second.tasks[0]["done"]
    assert case["layout"]["drones"][0]["trips"]


def test_changing_unreleased_request_changes_no_initial_public_feature():
    layout = make_layout(20261120, "train", 0, 2)
    first = Env(copy.deepcopy(layout), requests=[_request(t=100, x=900)])
    second = Env(copy.deepcopy(layout), requests=[_request(t=200, x=999999)])
    one, two = first.next_decision(), second.next_decision()
    assert first.t == second.t == 0
    assert all(not task["urgent"] for task in one[1]+two[1])
    for a, b in zip(featurize(first, one)[:3], featurize(second, two)[:3]):
        np.testing.assert_array_equal(a, b)


def test_missing_request_is_counted_and_censored_without_zero_response():
    layout = make_layout(20261120, "train", 0, 1)
    episode = rollout(Env(layout, requests=[_request(t=10, x=999999)]), Greedy())
    result = episode.metrics
    assert result["n_urgent"] == result["response_missing"] == 1
    assert result["urgent_done"] == result["high_on_time"] == 0
    assert result["resp_mean"] is None
    assert result["response_censored_mean"] == pytest.approx(590)
    assert result["emergency_records"][0]["done"] is False


def test_wait_with_no_future_request_keeps_routine_failure_denominator():
    from rlcore.env import ACT_WAIT
    class AlwaysWait:
        def reset(self, env):
            pass
        def act(self, env, cur):
            return ACT_WAIT
    layout = make_layout(20261120, "train", 0, 1)
    result = rollout(Env(layout), AlwaysWait()).metrics
    assert result["routine_total"] == 2 and result["routine_done"] == 0
    assert result["unserved"] == 2 and result["timeout"] == 1
    assert result["complete_strict"] == 0


def test_loo_expected_score_matches_analytic_bernoulli_reward_gradient():
    p = .37
    total = 0.0
    for first, second in itertools.product((0, 1), repeat=2):
        probability = (p if first else 1-p)*(p if second else 1-p)
        costs = [2.0 if action else 9.0 for action in (first, second)]
        advantages = loo_advantages(costs, 7.0)
        total += probability*(advantages[0]*(first-p)+advantages[1]*(second-p))/2
    assert total == pytest.approx(p*(1-p), abs=1e-14)
    with pytest.raises(ValueError):
        loo_advantages([1.0], 7.0)


def test_actual_pg_step_uses_episode_denominator_and_frozen_copy(monkeypatch):
    learning = importlib.import_module("rlcore.event_learning")
    class TwoAction(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.theta = torch.nn.Parameter(torch.tensor(.1))
        def forward(self, tok, ctx, mask):
            return torch.stack([self.theta.expand(len(tok)), torch.zeros(len(tok))], -1)
    model = TwoAction()
    frozen = copy.deepcopy(model)
    before = parameter_sha(model)
    decision = (np.zeros((2, 34), np.float32), np.zeros(24, np.float32), np.ones(2, bool), 0)
    # One no-action episode still participates in the two-episode denominator.
    episodes = iter([Episode(dict(J=1.0, input_sha256="same"), []),
                     Episode(dict(J=3.0, input_sha256="same"), [decision]*3)])
    monkeypatch.setattr(learning, "rollout", lambda *args, **kwargs: next(episodes))
    records = train_pg(model, lambda index: object(), iterations=1, rollouts=2,
                       reward_scale=1, learning_rate=.01)
    assert records[0]["rollouts"] == 2 and records[0]["physical_decisions"] == 3
    assert records[0]["gradient_norm"] == pytest.approx(3*(1-torch.sigmoid(torch.tensor(.1)).item()), rel=1e-6)
    assert records[0]["parameters_changed"]
    assert parameter_sha(model) != before and parameter_sha(frozen) == before
    assert len(records[0]["episode_metrics"]) == 2


def test_summary_errors_preserve_all_requested_task_denominators():
    rows = []
    for method in METHODS:
        rows.append(dict(case_id="one-day", input_sha256="same", method=method, status="error",
            metrics=dict(routine_total=3, routine_done=0, n_urgent=2, urgent_done=0,
                         high_total=1, high_on_time=0, norm_total=1, norm_on_time=0,
                         response_observed=0, response_missing=2, return_failure=1,
                         return_failures=2, emergency_records=[dict(release=100, arrival=None),
                                                               dict(release=200, arrival=None)])))
    result = summarize(rows)
    for method in METHODS:
        row = result["methods"][method]
        assert row["routine_total"] == 3 and row["n_urgent"] == 2
        assert row["error_episodes"] == 1 and row["strict_rate"] == 0
        assert row["return_failure_rate"] == 1 and row["response_censored_mean"] == 450
        assert row["mean_J_completed"] is None
    assert all(not row["paired_complete"] for row in result["paired_pg_minus_reference"])
