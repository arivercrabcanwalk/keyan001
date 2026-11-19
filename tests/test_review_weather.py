"""Hand-written physics/weather counterexamples; no stored maps or scientific runs."""
import importlib
import math

import numpy as np
import pytest


@pytest.fixture(params=("rlv3_weather", "rlv3_emergency"))
def modules(request):
    base = request.param + ".rlcore."
    return importlib.import_module(base + "phys"), importlib.import_module(base + "weather")


def _cell(w, **updates):
    cell = dict(tb=0.0, L=60.0, cx0=1000.0, cy0=0.0, vx=0.0, vy=0.0,
                a=10.0, b=10.0, ang=0.0, uo=0.0, ou=np.zeros((w.NT, 2)))
    cell.update(updates)
    w._build_cells([cell])
    return cell


def test_nowcast_detects_crossing_between_all_nine_old_samples(modules):
    _, weather = modules
    nc = [dict(cx=62.5, cy=0.0, vx=0.0, vy=0.0, a=1.0, b=1.0, ang=0.0, t0=0.0)]
    assert weather.nowcast_hits(nc, 0, 0, 1000, 0, 0, 1, buf=0)
    assert not weather.nowcast_hits(nc, 0, 5, 1000, 5, 0, 1, buf=0)


def test_nowcast_detects_moving_cell_crossing_stationary_hover(modules):
    _, weather = modules
    nc = [dict(cx=-62.5, cy=0.0, vx=1000.0, vy=0.0, a=1.0, b=1.0, ang=0.0, t0=0.0)]
    assert weather.nowcast_hits(nc, 0, 0, 0, 0, 0, 1, buf=0)


def test_future_cell_is_not_visible_before_its_birth(modules):
    _, weather = modules
    w = weather.WeatherDay(11, (0, 1000, 0, 1000), "wind")
    _cell(w, tb=4.0, L=10.0)
    assert not w.in_cell(1000, 0, 3.0)
    assert w.nowcast(3.0) == []


def test_zero_scale_future_has_finite_wind(modules):
    _, weather = modules
    w = weather.WeatherDay(12, (0, 1000, 0, 1000), "wind", scale=0)
    future = w.resample_future(12.5, 4)
    assert future.truth_wind(0, 0, 40) == (0.0, 0.0)


def test_born_cell_future_is_resampled_and_current_is_preserved(modules):
    _, weather = modules
    w = weather.WeatherDay(13, (0, 1000, 0, 1000), "wind")
    _cell(w, a=100.0, b=50.0)
    a, b = w.resample_future(12.5, 31), w.resample_future(12.5, 32)
    assert a._cell_state(0, 12.5) == w._cell_state(0, 12.5)
    assert a._cell_state(0, 35) != b._cell_state(0, 35)
    assert a.truth_wind(17, 23, 12.5) == w.truth_wind(17, 23, 12.5)
    assert a.truth_wind(17, 23, 11.0) == w.truth_wind(17, 23, 11.0)


def test_truth_detects_cell_between_leg_endpoints(modules):
    _, weather = modules
    w = weather.WeatherDay(14, (0, 1000, 0, 1000), "wind")
    _cell(w, cx0=225.0, a=1.0, b=1.0)
    assert not w.in_cell(0, 0, 20)
    assert not w.in_cell(450, 0, 20.5)
    assert w.truth_segment_hits(0, 0, 450, 0, 20, 0.5)


def test_wind_triangle_and_energy_units_have_independent_values(modules):
    phys, _ = modules
    # 9 m/s crosswind leaves 12 m/s forward airspeed; 3 m/s tailwind gives 15 m/s ground speed.
    assert phys.ground_speed(3, 9, 1, 0) == pytest.approx(15)
    e, t, ok = phys.leg_cost(0, 0, 900, 0, 3, 9)
    assert ok and t == pytest.approx(1) and e == pytest.approx(0.018)
    e0, t0, ok0 = phys.leg_cost(0, 0, 900, 0, 0, 0)
    assert ok0 and t0 == 1 and e0 == 0.018
    assert phys.p_hover(0) * 10 == 0.2


def test_nonphysical_airspeeds_and_nonunit_heading_are_rejected(modules):
    phys, _ = modules
    with pytest.raises(ValueError):
        phys.power(-1)
    with pytest.raises(ValueError):
        phys.ground_speed(0, 0, 1, 0, va=0)
    with pytest.raises(ValueError):
        phys.ground_speed(0, 0, 2, 0)
    with pytest.raises(ValueError):
        phys.leg_cost(0, 0, 1, 0, float("nan"), 0)


def test_infeasible_leg_does_not_invent_crawl_motion(modules):
    phys, _ = modules
    e, t, ok = phys.leg_cost(0, 0, 900, 0, -15, 0)
    assert not ok and math.isinf(e) and math.isinf(t)


def test_no_feasible_range_speed_is_reported(modules):
    phys, _ = modules
    with pytest.raises(ValueError, match="feasible"):
        phys.maxrange_airspeed(-40, 0)


def test_forecast_uses_only_already_issued_error_and_no_future_truth(modules):
    _, weather = modules
    import copy
    w = weather.WeatherDay(15, (0, 1000, 0, 1000), "wind")
    other = copy.deepcopy(w)
    other.coef[3:] += 1000
    other.gx[3:] += 1000
    other.fc_err[1:] += 1000
    assert other.forecast_wind(12.5, 100) == w.forecast_wind(12.5, 100)


def test_fixed_weather_is_known_deterministic_and_uses_truth_path(modules):
    _, weather = modules
    w = weather.FixedWeather(4, 0)
    assert w.calm is False and w.ncell == 0
    assert w.forecast_wind(12, 50) == w.truth_wind(99, 100, 50) == (4.0, 0.0)
    assert w.nowcast(12) == [] and w.resample_future(12, 123) is w
    assert not w.truth_segment_hits(0, 0, 100, 100, 12, 5)


def test_synthetic_weather_horizon_is_explicit(modules):
    _, weather = modules
    w = weather.WeatherDay(16, (0, 1000, 0, 1000), "wind")
    assert w.horizon == weather.T_MAX
    with pytest.raises(ValueError, match="horizon"):
        w.forecast_wind(0, weather.T_MAX + 1)


def test_wind_triangle_air_vector_has_prescribed_magnitude(modules):
    phys, _ = modules
    # Independent vector closure across cardinal and oblique hand-written tracks.
    for wind in ((0, 0), (4, 0), (0, 8), (-7, 2), (3, -5)):
        for ang in (0, math.pi / 4, math.pi / 2, math.pi):
            ux, uy = math.cos(ang), math.sin(ang)
            vg = phys.ground_speed(*wind, ux, uy)
            assert math.hypot(vg * ux - wind[0], vg * uy - wind[1]) == pytest.approx(15)
    # A pure lateral limiting air vector is possible with positive along-track wind.
    assert phys.ground_speed(6, 15, 1, 0) == pytest.approx(6)
    assert phys.ground_speed(0, 16, 1, 0) == 0


def test_continuous_ellipse_tangency_rotation_and_growing_axes(modules):
    _, weather = modules
    # A rotated 2x1 ellipse has vertical support sqrt(2.5); boundary contact counts.
    radius = math.sqrt(2.5)
    nc = [dict(cx=0.0, cy=0.0, vx=0.0, vy=0.0, a=2.0, b=1.0, ang=math.pi / 4, t0=0.0)]
    assert weather.nowcast_hits(nc, -100, radius, 100, radius, 0, 0, buf=0) is False
    assert weather.nowcast_hits(nc, -100, radius, 100, radius, 0, 1e-9, buf=0)
    assert not weather.nowcast_hits(nc, -100, radius + .01, 100, radius + .01, 0, 1e-9, buf=0)
    # Stationary point becomes covered because forecast semi-axes grow 1 -> 2.
    circle = [dict(cx=0.0, cy=0.0, vx=0.0, vy=0.0, a=1.0, b=1.0, ang=0.0, t0=0.0)]
    assert weather.nowcast_hits(circle, 1.5, 0, 1.5, 0, 0, 100, buf=0)
    assert not weather.nowcast_hits(circle, 2.1, 0, 2.1, 0, 0, 100, buf=0)


def test_truth_active_threshold_crossing_is_detected(modules):
    _, weather = modules
    w = weather.WeatherDay(20, (0, 1000, 0, 1000), "wind")
    _cell(w, tb=4.0, L=10.0, cx0=0.0)
    assert not w.in_cell(0, 0, 4.0)
    assert w.in_cell(0, 0, 5.0)
    assert w.truth_segment_hits(0, 0, 0, 0, 3.5, 1.5)
    assert not w.truth_segment_hits(0, 0, 0, 0, 2, 1.9)


def test_resampling_maps_born_cells_to_original_unsorted_indices(modules):
    _, weather = modules
    w = weather.WeatherDay(21, (0, 1000, 0, 1000), "wind")
    first = _cell(w, tb=50.0, L=100.0, cx0=-1000.0)
    second = dict(first, tb=0.0, cx0=1000.0)
    w._build_cells([first, second])
    f = w.resample_future(12.5, 33)
    assert f._cell_state(0, 12.5) == w._cell_state(1, 12.5)
    assert f.in_cell(1000, 0, 12.5) == w.in_cell(1000, 0, 12.5)
    assert f.truth_segment_hits(0, 0, 2000, 0, 10, 2) == w.truth_segment_hits(0, 0, 2000, 0, 10, 2)


def test_invalid_weather_and_collision_inputs_fail_explicitly(modules):
    _, weather = modules
    with pytest.raises(ValueError):
        weather.WeatherDay(22, (0, 1000, 0, 1000), "unknown")
    with pytest.raises(ValueError):
        weather.WeatherDay(22, (0, 1000, 0, 1000), "wind", scale=-1)
    with pytest.raises(ValueError):
        weather.nowcast_hits([], 0, 0, 1, 1, 0, -1)
    with pytest.raises(ValueError):
        weather.nowcast_hits([dict(cx=0, cy=0, vx=0, vy=0, a=-1, b=1, ang=0, t0=0)], 0, 0, 1, 1, 0, 1)
