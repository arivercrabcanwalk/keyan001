"""Unit tests required before any server run (run: python -m pytest -q tests)."""
import os, sys, math, random
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from rlcore.common import load_plans, load_ins, plan_layout, evaluate, bbox, P1, P2, fixed_cost
from rlcore import phys
from rlcore.env import Env, ACT_RETURN, ACT_WAIT
from rlcore.weather import WeatherDay
from rlcore.scen import make_env
from rlcore import policies as PO

ROWS = load_plans(os.path.join(HERE, "data/plans/test_ts.jsonl")) + load_plans(os.path.join(HERE, "data/plans/dev_ts.jsonl"))
SUB = ROWS[::7]


class RandomPolicy:
    name = "RANDOM"

    def __init__(self, seed=0, check=None):
        self.r = random.Random(seed); self.check = check

    def reset(self, env):
        pass

    def act(self, env, cur):
        d, av, feas, infos, can_ret, can_wait = cur
        if self.check:
            self.check(env, cur)
        acts = [x["j"] for x, f in zip(av, feas) if f] + ([ACT_RETURN] if can_ret else []) + ([ACT_WAIT] if can_wait else [])
        return self.r.choice(acts)


def test_power_calibration_exact():
    assert abs(phys.power(15.0) - P1) < 1e-12 and abs(phys.power(0.0) - P2) < 1e-12
    assert phys.p_cruise() == P1 and phys.p_hover(0.0) == P2
    # 15 m/s is (close to) the max-range speed in calm air, consistent with the author's 'optimal 15 m/s'
    assert 14.0 <= phys.maxrange_airspeed(0.0, 0.0) <= 18.0


def test_leg_zero_wind_equals_author():
    for d in (100.0, 1234.5, 9000.0):
        e, t, ok = phys.leg_cost(0, 0, d, 0, 0.0, 0.0)
        assert ok and abs(t - d / 900.0) < 1e-12 and abs(e - P1 * d / 900.0) < 1e-12


def test_headwind_costs_more_and_sketch_sign_error():
    eh, _, _ = phys.leg_cost(0, 0, 3000, 0, -8.0, 0.0)    # headwind
    et, _, _ = phys.leg_cost(0, 0, 3000, 0, 8.0, 0.0)     # tailwind
    e0, _, _ = phys.leg_cost(0, 0, 3000, 0, 0.0, 0.0)
    assert eh > e0 > et
    # cross wind also costs (crab angle): 8 m/s pure crosswind
    ec, _, _ = phys.leg_cost(0, 0, 3000, 0, 0.0, 8.0)
    assert ec > e0
    # singular / infeasible: headwind >= airspeed - VG_MIN
    _, _, ok = phys.leg_cost(0, 0, 3000, 0, -12.0, 0.0)
    assert not ok
    # the sketch formula makes a tailwind MORE expensive (documented flaw)
    assert phys.sketch_cost(3000, 8.0, 0.0, 0.0) > phys.sketch_cost(3000, 8.0, 0.0, math.pi)


def test_a1_calm_equals_official_evaluator():
    for r in ROWS:
        ins = load_ins(r["path"]); L = plan_layout(ins, r["solution"]); ev = evaluate(ins, r["solution"])
        res = PO.run_episode(Env(L), PO.A1())
        assert res["complete_strict"] == 1
        assert abs(res["cost"] - ev["cost"]) < 1e-6, (r["path"], res["cost"], ev["cost"])


def test_physics_integrator_zero_wind_reduces_to_author():
    """non-calm code path (truth integration, physics power) with all winds scaled to 0 == author model."""
    for r in SUB:
        ins = load_ins(r["path"]); L = plan_layout(ins, r["solution"]); ev = evaluate(ins, r["solution"])
        wx = WeatherDay(123, bbox(ins), "wind", scale=0.0)
        assert not wx.calm
        res = PO.run_episode(Env(L, wx=wx), PO.A1())
        assert res["aborts"] == 0 and res["complete_strict"] == 1
        assert abs(res["cost"] - ev["cost"]) < 1e-3, (r["path"], res["cost"], ev["cost"])


def _check_mask(env, cur):
    d, av, feas, infos, can_ret, can_wait = cur
    s = env.st[d["st"]]
    for x, f, inf in zip(av, feas, infos):
        if not f:
            continue
        if env.calm:
            d1 = math.hypot(x["x"] - d["x"], x["y"] - d["y"]); d2 = math.hypot(s["x"] - x["x"], s["y"] - x["y"])
            need = P1 * (d1 + d2) / 900.0 + x["en"]
        else:
            wx, wy = env.wx.forecast_wind(env.t, env.t)
            e1, t1, ok1 = phys.leg_cost(d["x"], d["y"], x["x"], x["y"], wx, wy)
            assert ok1
            need = inf["need"]
            assert abs(inf["e1"] - e1) < 1e-12
        assert need <= d["cap"] - d["e"] + 1e-9, "shield admitted an energy-infeasible task"


def test_mask_never_permits_infeasible_trip_calm():
    for r in SUB:
        for seed in range(3):
            env = make_env(r, 0, "nowind")
            res = PO.run_episode(env, RandomPolicy(seed, _check_mask))
            assert res["aborts"] == 0 and res["inc_land"] == 0 and res["complete_strict"] == 1


def test_mask_forecast_conservation_weather_and_completion():
    for r in SUB[:5]:
        for day in (50000, 50001):
            env = make_env(r, day, "weather")
            res = PO.run_episode(env, RandomPolicy(day, _check_mask))
            assert res["complete_strict"] == 1 and res["timeout"] == 0


def test_completion_all_methods_weather_storm():
    for r in SUB[:4]:
        for m in ("A1", "A1@0.1", "GREEDY", "REOPT@0.1", "REOPT-W9@0.2"):
            res = PO.run_episode(make_env(r, 50003, "weather_storm"), PO.make(m))
            assert res["complete_strict"] == 1 and res["timeout"] == 0, (r["path"], m)


def test_completion_emergency_and_coverage():
    for r in SUB[:5]:
        for sc in ("emerg_mid", "emerg_high"):
            env = make_env(r, 50002, sc)
            assert env.n_unserviceable == 0               # every request is at a covered tower
            res = PO.run_episode(env, RandomPolicy(1, _check_mask))
            assert res["complete_strict"] == 1 and res["urgent_done"] == res["n_urgent"]
            for m in ("A1", "GREEDY", "REOPT"):
                rr = PO.run_episode(make_env(r, 50002, sc), PO.make(m))
                assert rr["complete_strict"] == 1


def test_no_extra_stations():
    for r in SUB:
        ins = load_ins(r["path"]); L = plan_layout(ins, r["solution"])
        assert abs(L["fixed"] - fixed_cost(r["solution"]["station_types"])) < 1e-9
        assert abs(L["fixed"] - evaluate(ins, r["solution"])["fixed_cost"]) < 1e-9
        for sc in ("weather", "emerg_high"):
            for m in ("A1", "REOPT"):
                res = PO.run_episode(make_env(r, 50001, sc), PO.make(m))
                assert res["n_open"] == L["n_open"] and abs(res["fixed"] - L["fixed"]) < 1e-9
                assert res["n_drones"] == len(L["drones"])


def test_reproducible():
    r = SUB[1]
    a = PO.run_episode(make_env(r, 50005, "weather"), PO.make("A1"))
    b = PO.run_episode(make_env(r, 50005, "weather"), PO.make("A1"))
    assert a["J"] == b["J"]


def test_rl_policy_runs_and_respects_mask():
    import torch
    from rlcore.model import Policy
    from rlcore.agent import RLPolicy
    m = Policy(d=32, layers=1); m.eval()
    for sc in ("weather", "emerg_mid"):
        res = PO.run_episode(make_env(SUB[2], 50000, sc), RLPolicy(m, greedy=False, rng=np.random.default_rng(0)))
        assert res["complete_strict"] == 1


def test_resample_future_keeps_past_and_completes():
    """rollout-improvement futures: observable past unchanged, episodes still complete 100 % after resampling."""
    import copy
    from rlcore.common import load_plans
    from rlcore.scen import make_env
    from rlcore import policies as PO
    rows = load_plans(os.path.join(HERE, "data/plans/dev_ts.jsonl"))[:4]
    for scen in ["weather_storm", "emerg_high"]:
        for r in rows:
            env = make_env(r, 50001, scen)
            pol = PO.make("REOPT"); pol.reset(env)
            for _ in range(25):
                cur = env.next_decision()
                if cur is None:
                    break
                env.step(pol.act(env, cur))
            e2, p2 = copy.deepcopy((env, pol))
            e2.resample_future(123)
            t = env.t
            if env.wx is not None:
                for tt in [0.0, t * 0.5, max(0.0, t - 2.0)]:
                    assert env.wx.truth_wind(1000.0, 2000.0, tt) == e2.wx.truth_wind(1000.0, 2000.0, tt)
                    assert env.wx.forecast_wind(tt, tt) == e2.wx.forecast_wind(tt, tt)
            rel0 = [(x["rid"], x["rel"]) for x in env.tasks if x["urgent"] and x["rel"] <= t + 1e-9]
            rel2 = [(x["rid"], x["rel"]) for x in e2.tasks if x["urgent"] and x["rel"] <= t + 1e-9]
            assert rel0 == rel2
            while True:
                cur = e2.next_decision()
                if cur is None:
                    break
                e2.step(p2.act(e2, cur))
            res = e2.result()
            assert res["complete_strict"], (scen, r["path"])
