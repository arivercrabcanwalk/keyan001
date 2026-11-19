"""Synthetic physics and accounting checks; no historical scientific-map runs."""
import math
import pathlib
import sys
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rlcore.common import P1, P2
from rlcore import phys
from rlcore.env import Env
from rlcore import policies as PO
from rlcore.weather import FixedWeather


def sample():
    return dict(stations=[dict(k=0, x=0.0, y=0.0, R=5000.0, drones=[0], kind=1)],
        drones=[dict(i=0, st=0, di=1, cap=0.81, limit=480.0, trips=[[1]])],
        targets={1: (900.0, 0.0, 10.0, 0.2)}, assign={1: 0},
        fixed=27.8, n_open=1, n_dabs=0)


def test_power_calibration_and_calm_leg():
    assert phys.power(15.0) == pytest.approx(P1)
    assert phys.power(0.0) == pytest.approx(P2)
    for dist in (100.0, 1234.5, 9000.0):
        e, tm, ok = phys.leg_cost(0, 0, dist, 0, 0, 0)
        assert ok and tm == pytest.approx(dist/900)
        assert e == pytest.approx(P1*dist/900)


def test_headwind_and_crosswind_ground_time():
    eh, th, _ = phys.leg_cost(0, 0, 3000, 0, -8, 0)
    et, tt, _ = phys.leg_cost(0, 0, 3000, 0, 8, 0)
    e0, t0, _ = phys.leg_cost(0, 0, 3000, 0, 0, 0)
    ec, tc, _ = phys.leg_cost(0, 0, 3000, 0, 0, 8)
    assert eh > e0 > et and th > t0 > tt
    assert ec > e0 and tc > t0
    assert phys.leg_cost(0, 0, 3000, 0, -12, 0)[2] is False


@pytest.mark.parametrize("policy", [PO.A1, PO.Greedy, PO.Reopt])
def test_synthetic_calm_cost_and_actual_return(policy):
    env = Env(sample())
    res = PO.run_episode(env, policy())
    assert res["routine_done"] == res["routine_total"] == 1
    assert res["all_returned"] == res["physically_feasible"] == res["complete_strict"] == 1
    assert res["M_return"] == pytest.approx(12.0)
    assert res["cost"] == pytest.approx(27.8+0.5*12)
    assert res["fixed"] == 27.8 and res["n_drones"] == 1


@pytest.mark.parametrize("wind", [(0.0, 0.0), (4.0, 0.0), (0.0, 8.0)])
def test_fixed_wind_service_uses_original_node_energy(wind):
    env = Env(sample(), wx=FixedWeather(*wind))
    cur = env.next_decision()
    assert cur[3][0]["h"] == pytest.approx(0.2)
    env.step(cur[1][0]["j"])
    pol = PO.Greedy()
    # Existing node decision has been consumed; run the remaining event stream.
    res = PO.run_episode(env, pol)
    assert res["complete_strict"] == 1
    assert env.tasks[0]["done"]
    # Independent wind triangle for east/west return.
    wx, wy = wind
    east = wx+math.sqrt(15.0**2-wy**2)
    west = -wx+math.sqrt(15.0**2-wy**2)
    expected = 900/(east*60)+10+900/(west*60)
    assert res["M_return"] == pytest.approx(expected)
    assert env.dr[0]["busy"] == pytest.approx(expected)


def test_reproducible_physical_outputs_exclude_measured_compute_time():
    a = PO.run_episode(Env(sample()), PO.Greedy())
    b = PO.run_episode(Env(sample()), PO.Greedy())
    for key in ("J", "cost", "complete_strict", "M_return", "routine_done"):
        assert a[key] == b[key]
