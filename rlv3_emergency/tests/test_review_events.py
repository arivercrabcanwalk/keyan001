"""Handwritten engineering counterexamples only; no data plans, training, or quality experiments."""
import copy
import math
import pathlib
import sys
import pytest
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rlcore.env import Env, ACT_RETURN, ACT_WAIT
from rlcore import policies as PO
from rlcore import solver as S
from rlcore.urgent import make_requests
from rlcore.scen import SCENARIOS


def layout(coords=((900.0, 0.0),), ndr=1, limit=600.0, cap=1.0):
    targets = {i+1: (x, y, 10.0, 0.2) for i, (x, y) in enumerate(coords)}
    return dict(stations=[dict(k=0, x=0.0, y=0.0, R=10000.0, kind=2, drones=list(range(ndr)))],
        drones=[dict(i=i, st=0, di=i % 2, cap=cap, limit=limit,
                     trips=[list(targets)] if i == 0 else []) for i in range(ndr)],
        assign={i: 0 for i in targets}, targets=targets, fixed=43.4, n_open=1, n_dabs=1)


def request(rid=0, t=0.0, x=900.0, prio=1, deadline=20.0):
    return dict(rid=rid, tid=1, x=x, y=0.0, t=t, prio=prio,
                dl=t+deadline, svc=10.0, energy=0.2)


def drain(env, policy=None):
    return PO.run_episode(env, policy or PO.Greedy())


def test_launch_does_not_commit_future_service_or_position():
    env = Env(layout(ndr=2))
    cur = env.next_decision()
    env.step(0)
    assert env.t == 0 and env.dr[0]["x"] == 0
    assert not env.tasks[0]["done"] and env.tasks[0]["t_done"] is None
    assert env.dr[0]["e"] == 0


def test_release_during_transit_wakes_idle_drone_at_exact_time():
    env = Env(layout(coords=((1800.0, 0.0),), ndr=2), requests=[request(t=0.25)], record=True)
    env.step(env.next_decision()[1][0]["j"])
    cur = env.next_decision()
    assert math.isclose(env.t, 0.25)
    assert cur[0]["i"] == 1
    assert math.isclose(env.dr[0]["x"], 225.0)
    assert not env.tasks[0]["done"]
    assert [x["j"] for x in cur[1] if x["urgent"]] == [1]


def test_simultaneous_requests_claimed_once_and_routine_retained():
    env = Env(layout(ndr=2), requests=[request(0), request(1)], record=True)
    res = drain(env)
    assert res["n_urgent"] == 2 and res["urgent_done"] == 2
    assert res["routine_total"] == res["routine_done"] == 1
    assert res["complete_strict"] == 1
    assert len([e for e in env.event_trace if e[1] == "release"]) == 2


def test_uncovered_and_unfinished_requests_remain_in_denominator():
    env = Env(layout(coords=()), requests=[request(x=20000.0)])
    res = drain(env)
    assert res["n_unserviceable"] == 1
    assert res["n_urgent"] == res["high_total"] == 1
    assert res["urgent_done"] == res["high_on_time"] == 0
    assert res["completion"] == 0 and res["complete_strict"] == 0
    assert res["failure_penalty"] >= 1000
    assert res["response_missing"] == 1


def test_deadline_is_arrival_plus_successful_service_not_service_end():
    env = Env(layout(coords=()), requests=[request(deadline=5.0)])
    res = drain(env)
    assert res["high_on_time"] == 1
    assert env.tasks[0]["t_arrival"] == pytest.approx(1.0)
    assert env.tasks[0]["t_done"] == pytest.approx(11.0)
    assert res["resp_mean"] == pytest.approx(1.0)
    assert res["completion_response_mean"] == pytest.approx(11.0)


def test_arrival_without_service_success_is_not_on_time():
    env = Env(layout(coords=(), cap=0.3), requests=[request()])
    # A valid forecast dispatch is followed by an unforecast service drain.
    cur = env.next_decision()
    env.step(cur[1][0]["j"])
    env.dr[0]["cap"] = 0.05
    res = drain(env)
    assert res["high_on_time"] == 0 and res["high_total"] == 1
    assert res["urgent_done"] == 0 and res["failed"] == 1


def test_hard_mask_reserves_return_and_cumulative_duty():
    env = Env(layout(limit=11.5))
    ok, inf = env.task_check(env.dr[0], env.tasks[0])
    assert inf["t1"]+env.tasks[0]["svc"]+inf["t2"] == pytest.approx(12.0)
    assert not ok


def test_battery_swap_does_not_reset_daily_operating_duty():
    env = Env(layout(coords=((900.0, 0.0), (1800.0, 0.0)), limit=20.0, cap=0.25))
    res = drain(env)
    assert res["routine_done"] == 1 and res["routine_total"] == 2
    assert res["complete_strict"] == 0
    assert env.dr[0]["busy"] <= 20.0+1e-8
    assert env.dr[0]["e"] == 0


def test_last_physical_return_sets_m_return():
    env = Env(layout())
    res = drain(env)
    assert res["M_return"] == pytest.approx(12.0)
    assert res["all_returned"] == res["physically_feasible"] == res["complete_strict"] == 1
    assert res["service_min"] == pytest.approx(10.0)
    assert res["flight_min"] == pytest.approx(2.0)


def test_no_free_recovery_after_resource_failure():
    env = Env(layout(coords=((900.0, 0.0),), cap=0.3))
    cur = env.next_decision()
    env.step(cur[1][0]["j"])
    env.dr[0]["cap"] = 0.01
    res = drain(env)
    d = env.dr[0]
    assert res["failed"] == 1 and not d["at_st"]
    assert d["x"] > 0 and d["x"] < 900
    assert d["e"] == pytest.approx(d["cap"])
    assert res["M_return"] is None and res["all_returned"] == res["physically_feasible"] == 0
    assert res["complete_strict"] == 0 and res["fallback"] == 0


def test_late_no_skip_does_not_guarantee_completion():
    env = Env(layout(), requests=[request(t=599.0)])
    res = drain(env)
    assert res["routine_done"] == 1
    assert res["urgent_done"] == 0 and res["complete_strict"] == 0
    assert res["fallback"] == 0


def test_wait_policy_terminates_at_horizon_with_failure():
    class Wait:
        def reset(self, env): pass
        def act(self, env, cur): return ACT_WAIT if cur[-1] else ACT_RETURN
    env = Env(layout())
    res = drain(env, Wait())
    assert res["timeout"] and res["complete_strict"] == 0
    assert res["routine_done"] == 0 and env.t <= 600.0


class HiddenCell:
    calm = False
    ncell = 1
    horizon = 900.0
    def forecast_wind(self, t_now, t): return 0.0, 0.0
    def truth_wind(self, x, y, t): return 0.0, 0.0
    def nowcast(self, t): return []
    def truth_segment_hits(self, x1, y1, x2, y2, t0, dur):
        return t0 < 2.25 <= t0+dur
    def resample_future(self, t, seed): return self


def test_truth_collision_applies_even_when_forecast_cell_shield_disabled():
    env = Env(layout(), wx=HiddenCell(), use_cells=False)
    res = drain(env)
    assert res["inc_cell"] == 1
    assert res["physically_feasible"] == 0 and res["complete_strict"] == 0


def test_truth_collision_is_checked_on_actual_return_leg():
    class ReturnCell(HiddenCell):
        def truth_segment_hits(self, x1, y1, x2, y2, t0, dur):
            return t0 < 11.25 <= t0+dur
    env = Env(layout(), wx=ReturnCell())
    res = drain(env)
    assert res["routine_done"] == 1 and res["complete_strict"] == 0
    assert res["inc_cell"] == 1 and res["all_returned"] == 0
    assert res["M_return"] is None


def test_cross_station_request_capability_is_equal_and_assets_unchanged():
    source = layout(ndr=2)
    source["stations"].append(dict(k=1, x=1000.0, y=0.0, R=10000.0, kind=1, drones=[1]))
    source["stations"][0]["drones"] = [0]
    source["drones"][1]["st"] = 1
    source["n_open"] = 2
    original = copy.deepcopy(source)
    for factory in (PO.A1, PO.Greedy, PO.Reopt):
        env = Env(copy.deepcopy(source), requests=[request()])
        assert env.tasks[0]["elig"] == (0,)
        assert env.tasks[1]["elig"] == (0, 1)
        for d in env.dr:
            assert any(x["urgent"] for x in env.avail_tasks(d))
        res = drain(env, factory())
        assert res["n_open"] == 2 and res["n_drones"] == 2
        assert env.L == original


def test_claim_is_not_available_before_actual_failure_or_completion():
    env = Env(layout(ndr=2), requests=[request(t=0.25)])
    env.step(env.next_decision()[1][0]["j"])
    cur = env.next_decision()
    assert env.t == pytest.approx(0.25)
    assert all(x["j"] != 0 for x in cur[1])
    assert env.tasks[0]["claim"] == 0


def test_future_request_redraw_keeps_released_and_committed_task():
    env = Env(layout(ndr=2), requests=[request(0, 0.0), request(1, 100.0)])
    cur = env.next_decision()
    env.step(cur[1][0]["j"])
    env.req_gen = ([(1, 900.0, 0.0)], "mid", "random")
    old = copy.deepcopy(env.tasks[1])
    env.resample_future(12)
    assert env.tasks[1] == old and env.tasks[1]["rel"] == 0
    assert all(x["rel"] <= env.t or x["claim"] < 0 for x in env.tasks)


def test_invalid_request_is_explicitly_rejected():
    for req in (request(t=-1), request(t=601), dict(request(), svc=0), dict(request(), prio=2)):
        with pytest.raises(ValueError):
            Env(layout(), requests=[req])


def test_nonfinite_or_negative_margin_is_rejected():
    for margin in (float("nan"), -0.1):
        with pytest.raises(ValueError):
            Env(layout(), margin=margin)


def test_scenario_registry_has_fixed_weather_and_two_patterns():
    assert {"nowind", "fixed_e4", "fixed_n8"} <= SCENARIOS.keys()
    assert {f"emerg_{p}_{l}" for p in ("random", "clustered") for l in ("low", "mid", "high")} <= SCENARIOS.keys()


def test_all_49_visible_candidates_remain_selectable():
    env = Env(layout(coords=()), requests=[request(i) for i in range(49)])
    cur = env.next_decision()
    assert len(cur[1]) == 49
    assert all(cur[2])


def test_request_generation_is_route_independent_and_distinct_by_pattern():
    targets = [(i, i*100.0, 0.0) for i in range(50)]
    a = make_requests(21, targets, "high", pattern="random")
    b = make_requests(21, targets, "high", pattern="clustered")
    assert a == make_requests(21, targets, "high", pattern="random")
    assert a != b
    assert all(0 <= x["t"] < 450 for x in a+b)


def problem(cap=1.0, duty=600.0):
    E, T, F = S.cost_matrix([(0.0, 0.0), (900.0, 0.0)], (0.0, 0.0), True)
    return S.Prob(E, T, F, np.array([0.,10.]), np.array([0.,.2]),
        np.array([0.,0.]), np.array([0.,20.]), np.array([0.,10.]),
        [cap], [0.0], 0., 0., duty_left=[duty])


def test_solver_never_parks_infeasible_singleton():
    p = problem(cap=0.01)
    routes = S.solve(p, budget_s=0.01)
    assert routes == [[]]
    assert p.last_solve["unassigned"] == [1]


def test_solver_duty_and_return_are_hard_not_soft_overtime():
    p = problem(duty=11.0)
    assert S.solve(p, budget_s=0.01) == [[]]
    assert not math.isfinite(p.sched_cost([[[1]]]))


def test_solver_zero_budget_keeps_tasks_explicitly_unassigned():
    p = problem()
    assert S.solve(p, budget_s=0.0) == [[]]
    assert p.last_solve["deadline_reached"] and p.last_solve["unassigned"] == [1]
    assert p.last_solve["algorithm"] == "insertion_relocate_2opt_merge"
