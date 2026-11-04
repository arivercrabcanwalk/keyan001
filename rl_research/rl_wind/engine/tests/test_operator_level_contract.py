import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd import fidelity_ops_v5 as ops
from lrphsd.evaluator import evaluate
from carl.actions import N_OPERATORS, N_ACTIONS, OPERATOR_NAMES, action_universe_mask
from carl.controllers import (FixedPolicy, DistributionPolicy, ScheduledPolicy,
                              AdaptiveWeights, RuleController, LinUCB, QLearning)
from carl.core import Coverage, Mirror
from carl.kernel import CAEngine
from carl.neighborhood import Context, operator_available, generate, apply_move
from carl.state import History, action_mask, encode, N_FEATURES
from carl.search import transition_reward

INST = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


def make_context(name="5_35_1"):
    ins = read_instance(INST / f"{name}.txt")
    ops.prepare(ins)
    eng = CAEngine(ins)
    sol = build(ins)
    eng.load(0, sol)
    ctx = Context(ins, eng, Mirror(ins, sol), Coverage(ins), random.Random(41))
    return ins, eng, sol, ctx


def test_adaptive_weights_credit_only_actual_outcomes():
    ins, eng, sol, ctx = make_context()
    try:
        from carl.controllers import AdaptiveWeights, QLearning
        ctrl = AdaptiveWeights()
        ctrl.begin(ins, 3)
        before = ctrl.w.copy()
        ctrl.observe(None, 7, -1.0, None, False, np.ones(N_ACTIONS, bool),
                     {"feasible": False, "accepted": False, "improved": False,
                      "best_updated": False})
        assert ctrl.score[7] == 0.0
        ctrl.observe(None, 8, 0.0, None, False, np.ones(N_ACTIONS, bool),
                     {"feasible": True, "accepted": True, "improved": True,
                      "best_updated": True})
        assert ctrl.score[8] == 9.1
        q = QLearning()
        q.begin(ins, 5)
        q.last_state, q.last_action = 0, 0
        q.observe(None, 0, 1.0, np.zeros(N_FEATURES), False,
                  np.ones(N_ACTIONS, bool), {"duration_seconds": 0.02})
        assert q.Q[0, 0] > 0.0
    finally:
        eng.free()


def test_reward_separates_incumbent_delta_time_and_global_best():
    base = transition_reward(100.0, 99.0, 100.0, 0.1, 10.0, False)
    best = transition_reward(100.0, 99.0, 100.0, 0.1, 10.0, True)
    no_change = transition_reward(100.0, 100.0, 100.0, 0.1, 10.0, False)
    assert abs(base - (1.0 - 0.0025)) < 1e-12
    assert abs((best - base) - 0.02) < 1e-12
    assert no_change < 0.0


def test_operator_mask_cache_is_invalidated_after_refresh():
    ins, eng, sol, ctx = make_context()
    try:
        action_mask(ctx)
        assert ctx._operator_available_cache is not None
        ctx.refresh()
        assert ctx._operator_available_cache is None
    finally:
        eng.free()


def test_mixed_type_location_and_joint_swap_are_reachable():
    ins = read_instance(INST / "10_110_1.txt")
    ops.prepare(ins)
    eng = CAEngine(ins)
    try:
        sol = build(ins)
        eng.load(0, sol)
        cov = Coverage(ins)
        mirror = Mirror(ins, sol)
        ctx = Context(ins, eng, mirror, cov, random.Random(91))
        assert operator_available(ctx, 2)
        upgrade = generate(ctx, 2, 1)
        assert upgrade is not None
        types = apply_move(eng, upgrade, list(mirror.types), ins)
        assert types is not None
        assert evaluate(ins, eng.export(1))["feasible"]
        eng.clone(1, 0)
        mixed = eng.export(0)
        ctx2 = Context(ins, eng, Mirror(ins, mixed), cov, random.Random(92))
        mask = action_mask(ctx2)
        assert mask[4 * 3] and mask[16 * 3]
        for op in (4, 16):
            move = generate(ctx2, op, 1)
            assert move is not None, op
            new_types = apply_move(eng, move, list(ctx2.mirror.types), ins)
            assert new_types is not None, op
            assert evaluate(ins, eng.export(1))["feasible"], op
    finally:
        eng.free()


def test_operator_universe_and_state_dimensions():
    assert N_OPERATORS == 17
    assert N_ACTIONS == 51
    assert len(OPERATOR_NAMES) == N_OPERATORS
    ins, eng, sol, ctx = make_context()
    try:
        feat = encode(ctx, History(), evaluate(ins, sol)["cost"], 0.0, 6.0,
                      100.0, 0, 0.0, 0.0, 0)
        assert len(feat) == N_FEATURES == 75
        assert np.isfinite(feat).all()
        assert action_universe_mask().shape == (51,)
    finally:
        eng.free()


def test_structural_mask_only_enables_available_operator():
    ins, eng, sol, ctx = make_context()
    try:
        mask = action_mask(ctx)
        assert mask.shape == (51,)
        assert mask.any()
        for op in range(N_OPERATORS):
            assert bool(mask[op * 3:op * 3 + 3].any()) == operator_available(ctx, op)
        assert not mask[8 * 3 + 1] and not mask[8 * 3 + 2]
    finally:
        eng.free()


def test_controllers_respect_51_action_mask():
    ins, eng, sol, ctx = make_context()
    try:
        feat = encode(ctx, History(), evaluate(ins, sol)["cost"], 0.0, 6.0,
                      100.0, 0, 0.0, 0.0, 0)
        mask = action_mask(ctx)
        for cls in (FixedPolicy, DistributionPolicy, ScheduledPolicy,
                    AdaptiveWeights, RuleController, LinUCB, QLearning):
            ctrl = cls()
            ctrl.begin(ins, 17)
            a = ctrl.act(feat, mask, 0)
            assert 0 <= a < N_ACTIONS and mask[a], (cls.__name__, a)
    finally:
        eng.free()


def test_explicit_operators_generate_only_the_selected_subtype():
    ins, eng, sol, ctx = make_context()
    try:
        # Direct generator calls are checked for family identity. A failed
        # candidate is allowed when random target selection has no repair,
        # but it must never silently dispatch to a different operator.
        for op in range(N_OPERATORS):
            if not operator_available(ctx, op):
                continue
            intensity = 0 if op == 8 else 1
            move = generate(ctx, op, intensity)
            if move is not None:
                assert move.family in (0, 1, 2, 3)
                assert move.family == __import__(
                    "carl.actions", fromlist=["OPERATOR_FAMILY"]
                ).OPERATOR_FAMILY[op]
    finally:
        eng.free()


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name, flush=True)
            except Exception as exc:
                failures += 1
                print("FAIL", name, repr(exc), flush=True)
    print("RESULT", 8 - failures, "/8", flush=True)
    raise SystemExit(bool(failures))
