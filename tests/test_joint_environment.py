"""Handwritten synthetic engineering checks; no scientific map or solver runs."""
import copy
import math

import pytest

from rlv3_weather.rlcore.joint_route import JointRoute, RETURN, FEAT_DIM, FEATURE_NAMES
from rlv3_weather.vendor.lrphsd.problem import read_instance, empty_solution


def row_for(tmp_path, lines, types, routes):
    path = tmp_path / "joint_manual.txt"
    path.write_text("CUST_NO X Y ENERGY SERVICE\n" + lines)
    ins = read_instance(path)
    sol = empty_solution(ins, types)
    sol["routes"] = routes
    return dict(path=str(path), solution=sol)


def replay(env, choose):
    while not env.done:
        action = choose()
        assert action is not None
        env.step(action)
    return env.result()


def test_teacher_independent_same_wind_audit_and_explicit_return(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n",
                  [2], [[[[1]], [[2]]]])
    env = JointRoute(row, "fixed_e4", 100)
    assert FEAT_DIM == len(FEATURE_NAMES) == 30
    assert {a for a, _ in env.options()} == {(0, 0, 1), (0, 0, 2), (0, 1, 1), (0, 1, 2)}
    for _, feature in env.options():
        assert len(feature) == FEAT_DIM and all(math.isfinite(v) for v in feature)
    env.step(env.teacher_action())
    assert not env.done and (0, 0, RETURN) in dict(env.options())
    incomplete = env.result()
    assert not incomplete["all_returned"] and not incomplete["eligible"]
    assert incomplete["M_return"] is None and incomplete["open_trips"]
    result = replay(env, env.teacher_action)
    assert result["eligible"] and result["complete_strict"] and not result["fallback"]
    assert result["solution"] == row["solution"]
    assert result["cost"] == pytest.approx(result["audit"]["metrics"]["cost"])
    assert result["M_return"] == pytest.approx(10 + 900/(19*60) + 900/(11*60))
    assert result["J"] == result["cost"]
    assert not result["scientific_eligible"] and not result["formal"]


def test_return_resets_battery_but_preserves_cumulative_duty(tmp_path):
    row = row_for(tmp_path, "1 900 0 .5 200\n2 0 900 .5 200\n100 0 0 0 0\n",
                  [1], [[[], [[1], [2]]]])
    env = JointRoute(row, "nowind", 1000)
    env.step((0, 1, 1))
    assert (0, 1, 2) not in dict(env.options())
    env.step((0, 1, RETURN))
    slot = env.slots[0, 1]
    assert slot["energy"] == 0 and slot["duty"] == pytest.approx(202)
    env.step((0, 1, 2))
    assert not env.done and not env.result()["all_returned"]
    env.step((0, 1, RETURN))
    result = env.result()
    assert result["M_return"] == pytest.approx(404)
    assert len(result["audit"]["trips"]) == 2 and result["eligible"]
    with pytest.raises(ValueError, match="ended"):
        env.step((0, 1, RETURN))


def test_heterogeneous_opportunity_mask_preserves_large_only_job(tmp_path):
    row = row_for(tmp_path, "1 900 0 .1 300\n2 0 900 .9 300\n100 0 0 0 0\n",
                  [2], [[[[2]], [[1]]]])
    env = JointRoute(row, "nowind", 1000)
    choices = dict(env.options())
    # LD can physically do target 1 now, but then cannot do LD-only 2 in its
    # remaining cumulative duty. SD cannot rescue target 2 on a new battery.
    assert (0, 0, 1) not in choices
    assert (0, 1, 2) not in choices
    assert choices[0, 0, 2][27] == 1.0
    assert choices[0, 1, 1][27] == 0.0
    before = copy.deepcopy(env.slots)
    with pytest.raises(ValueError, match="masked"):
        env.step((0, 0, 1))
    assert before == env.slots and not env.trace
    assert replay(env, env.teacher_action)["eligible"]


def test_fixed_station_assignment_and_inactive_slots_are_not_decisions(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 10900 0 .2 10\n100 0 0 0 0\n101 10000 0 0 0\n102 20000 0 0 0\n",
                  [1, 2, 0], [[[], [[1]]], [[[2]], []], [[], []]])
    env = JointRoute(row, "fixed_n8", 200)
    actions = {a for a, _ in env.options()}
    assert actions == {(0, 1, 1), (1, 0, 2), (1, 1, 2)}
    for invalid in ((0, 0, 1), (1, 0, 1), (2, 1, 1), (0, 1, RETURN), (0, 1, 999)):
        with pytest.raises(ValueError, match="masked"):
            env.step(invalid)
    assert replay(env, env.teacher_action)["eligible"]


def test_original_cost_cap_dead_end_has_no_implicit_completion(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n100 0 0 0 0\n", [1], [[[], [[1]]]])
    env = JointRoute(row, "nowind", 28)
    assert env.done and env.termination_reason == "dead_end" and env.options() == []
    result = env.result()
    assert result["routine_done"] == 0 and result["unserved"] == 1
    assert result["J"] == pytest.approx(27.8+1000)
    assert not result["complete_strict"] and not result["eligible"] and not result["fallback"]
    assert result["solution"]["routes"] == [[[], []]]
    assert "missing:1" in result["audit"]["issues"]


def test_greedy_reproducible_shared_options_and_no_teacher_feature_leak(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n",
                  [2], [[[[1]], [[2]]]])
    swapped = copy.deepcopy(row)
    swapped["solution"]["routes"] = [[[[2]], [[1]]]]
    first, second = JointRoute(row, "fixed_e4", 100), JointRoute(swapped, "fixed_e4", 100)
    assert first.options() == second.options()
    assert first.greedy_action() == second.greedy_action()
    assert first.teacher_action() != second.teacher_action()
    result1, result2 = replay(first, first.greedy_action), replay(second, second.greedy_action)
    assert first.trace == second.trace and result1["eligible"] and result2["eligible"]
    assert len(first.trace) <= first.max_steps


def test_source_slot_reference_and_teacher_deviation_are_explicit(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n",
                  [2], [[[[1]], [[2]]]])
    env = JointRoute(row, "nowind", 100)
    while not env.done:
        action = env.source_slot_action()
        assert action in dict(env.options())
        if action[2] != RETURN:
            assert action[:2] == env.source_slot[action[2]]
        env.step(action)
    assert env.result()["eligible"]
    env = JointRoute(row, "nowind", 100)
    env.step((0, 1, 1))
    with pytest.raises(ValueError, match="non-teacher"):
        env.teacher_action()


def test_serial_subsets_replay_the_same_teacher_trips_in_another_order(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n",
                  [2], [[[[1]], [[2]]]])
    env = JointRoute(row, "fixed_e4", 100)
    # A scheduler can begin with SD while preserving exactly the same per-slot
    # physical trip and teacher label. Both policies score the shared features.
    for key in ((0, 1), (0, 0)):
        while any(a[:2] == key for a, _ in env.options()):
            subset = [(a, f) for a, f in env.options() if a[:2] == key]
            action = env.teacher_action(subset)
            assert action in dict(subset)
            assert env.greedy_action(subset) in dict(subset)
            env.step(action)
            if action[2] == RETURN:
                break
    assert env.done and env.result()["solution"] == row["solution"]
    assert env.greedy_action([]) is None


def test_feature_units_and_exact_original_cap_are_bound(tmp_path):
    row = row_for(tmp_path, "1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n",
                  [2], [[[[1]], [[2]]]])
    env = JointRoute(row, "fixed_e4", 100)
    feature = dict(env.options())[0, 0, 1]
    outbound, inbound = 900/(19*60), 900/(11*60)
    duty = 10+outbound+inbound
    by_name = dict(zip(FEATURE_NAMES, feature))
    assert by_name["leg_minutes_over_duty_limit"] == pytest.approx(outbound/600)
    assert by_name["return_minutes_over_duty_limit"] == pytest.approx(inbound/600)
    assert by_name["closed_energy_over_battery"] == pytest.approx(.2+.018*(outbound+inbound))
    assert by_name["projected_team_makespan_over_600"] == pytest.approx(duty/600)
    assert by_name["remaining_service_cost_bound_over_cap"] == pytest.approx((43.4+.5*(duty+10))/100)
    assert by_name["other_slot_opportunity_fraction"] == 1.0
    cap = env.anchor_audit["metrics"]["cost"]
    exact = JointRoute(row, "fixed_e4", cap)
    assert replay(exact, exact.teacher_action)["cost"] == pytest.approx(cap)


def test_calm_anchor_cannot_substitute_for_infeasible_same_wind_anchor(tmp_path):
    row = row_for(tmp_path, "1 0 900 .77 10\n100 0 0 0 0\n", [1], [[[], [[1]]]])
    calm = JointRoute(row, "nowind", 100)
    assert replay(calm, calm.teacher_action)["eligible"]
    with pytest.raises(ValueError, match="infeasible same-wind"):
        JointRoute(row, "fixed_n8", 100)
    for cap in (0, -1, math.inf, float("nan"), True):
        with pytest.raises(ValueError, match="cap"):
            JointRoute(row, "nowind", cap)


def test_energy_tolerance_is_not_cost_tolerance(tmp_path):
    # Co-located service isolates battery energy from flight and clock rounding.
    routes = [[[], [[1]]]]
    exact = row_for(tmp_path, "1 0 0 .81 1\n100 0 0 0 0\n", [1], routes)
    env = JointRoute(exact, "nowind", 100)
    assert replay(env, env.teacher_action)["eligible"]
    (tmp_path / "excess").mkdir()
    excess = row_for(tmp_path / "excess", "1 0 0 .81000001 1\n100 0 0 0 0\n", [1], routes)
    with pytest.raises(ValueError, match="battery:0:1:0"):
        JointRoute(excess, "nowind", 100)
