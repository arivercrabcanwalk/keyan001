"""Synthetic, hand-built fixtures.  No map data, no official instance."""
from __future__ import annotations

from env.core import Node, Params, StaticContext, validate_static

P = Params(speed=100.0, flight_energy=0.01, small_battery=0.81,
           large_battery=1.0, small_radius=4000.0, large_radius=5000.0,
           small_duration=480.0, large_duration=600.0, time_cost=0.5)


def _ctx(name, stations, targets, types, assign, params=P, horizon=240.0):
    ctx = StaticContext(
        instance_sha256="fixture:" + name, params=params,
        stations=tuple(stations), targets=tuple(targets),
        station_types=tuple(types), target_station=tuple(assign),
        mode="W", day_id=name, horizon_min=horizon)
    validate_static(ctx)
    return ctx


def f01_1s_2t():
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 1000.0, 0.0, 0.2, 10.0), Node(2, 0.0, 1000.0, 0.2, 10.0)]
    return _ctx("f01", st, tg, [2], [(1, 0), (2, 0)], horizon=200.0)


def f02_3s_6t():
    st = [Node(101, 0.0, 0.0, 0.0, 0.0),
          Node(102, 2000.0, 0.0, 0.0, 0.0),
          Node(103, 4000.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 800.0, 0.0, 0.2, 10.0),
          Node(2, 0.0, 900.0, 0.2, 10.0),
          Node(3, -700.0, 0.0, 0.2, 10.0),
          Node(4, 2000.0, 1000.0, 0.2, 10.0),
          Node(5, 2600.0, 0.0, 0.2, 10.0),
          Node(6, 500.0, 500.0, 0.2, 10.0)]
    return _ctx("f02", st, tg, [2, 1, 0],
                [(1, 0), (2, 0), (3, 0), (4, 1), (5, 1), (6, 0)], horizon=240.0)


def f03_alias():
    """The analytic alias witness (CAUSAL_ROLLOUT_APPENDIX section 2)."""
    p = Params(speed=2.0, flight_energy=0.125, small_battery=4.0,
               large_battery=4.0, small_radius=5000.0, large_radius=5000.0,
               small_duration=20.0, large_duration=20.0, time_cost=0.5)
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 6.0, 0.0, 0.5, 4.0),      # drone A target
          Node(2, 0.0, 0.0, 0.75, 6.0)]     # drone B target (at the station)
    return _ctx("f03", st, tg, [2], [(1, 0), (2, 0)], params=p, horizon=20.0)


def f04_publication():
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 1000.0, 0.0, 0.2, 10.0), Node(2, 0.0, 1000.0, 0.2, 10.0)]
    return _ctx("f04", st, tg, [2], [(1, 0), (2, 0)], horizon=240.0)


def f05_storm_day():
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(i, 500.0 * i, 300.0 * (i % 3), 0.2, 10.0) for i in range(1, 7)]
    return _ctx("f05", st, tg, [2], [(i, 0) for i in range(1, 7)], horizon=200.0)

def f06_wday():
    """W-mode fixture: one background request released at t=60 and one target
    inside a no-fly ellipse that is active on [0, 40)."""
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 1000.0, 0.0, 0.2, 10.0),
          Node(2, 0.0, 1000.0, 0.2, 10.0),
          Node(3, -1000.0, 0.0, 0.2, 10.0),
          Node(4, 1000.0, 1000.0, 0.2, 10.0)]
    return _ctx("f06", st, tg, [2], [(i, 0) for i in (1, 2, 3, 4)], horizon=200.0)


def f06_nfz_row():
    """Ellipse centred on target 4, active on [0, 40)."""
    return (1000.0, 1000.0, 0.0, 0.0, 800.0, 800.0, 0.0, 0.0, 40.0)


def f06_leg_nfz_row():
    """Small ellipse on the station->target-1 leg, always active."""
    return (500.0, 0.0, 0.0, 0.0, 150.0, 150.0, 0.0, 0.0, 1e18)

def f07_alarm(limit=None):
    """Alarm fixture: two targets; an exogenous fault can re-open target 1."""
    p = P if limit is None else Params(
        speed=100.0, flight_energy=0.01, small_battery=0.81, large_battery=1.0,
        small_radius=4000.0, large_radius=5000.0, small_duration=limit,
        large_duration=limit, time_cost=0.5)
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 1000.0, 0.0, 0.2, 10.0), Node(2, 0.0, 1000.0, 0.2, 10.0)]
    return _ctx("f07", st, tg, [2], [(1, 0), (2, 0)], params=p, horizon=200.0)

def f08_deadlines():
    """W priorities: targets 1 and 2 are high priority with deadlines."""
    st = [Node(101, 0.0, 0.0, 0.0, 0.0)]
    tg = [Node(1, 1000.0, 0.0, 0.2, 10.0),
          Node(2, 0.0, 1000.0, 0.2, 10.0),
          Node(3, -1000.0, 0.0, 0.2, 10.0)]
    ctx = StaticContext(
        instance_sha256="fixture:f08", params=P,
        stations=tuple(st), targets=tuple(tg), station_types=(2,),
        target_station=tuple((i, 0) for i in (1, 2, 3)),
        mode="W", day_id="f08", horizon_min=200.0,
        deadlines=((1, 15.0, "high"), (2, 15.0, "high"), (3, 1e9, "routine")))
    validate_static(ctx)
    return ctx
