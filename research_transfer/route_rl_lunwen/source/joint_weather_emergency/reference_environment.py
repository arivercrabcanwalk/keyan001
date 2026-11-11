"""Independent reference for <EXPERIMENT_SERVER> verification, not a calibrated aircraft model.
No solver matrices/caches are read. Uniform piecewise-constant wind, minutes/metres.
This module is an audit oracle and does not replace any historical source.
"""
import math
from collections import Counter

TOL = 1e-7


def ground_speed(dx, dy, wx, wy, va=900.0):
    distance = math.hypot(dx, dy)
    if distance == 0:
        return va
    along = (wx * dx + wy * dy) / distance
    cross = (wx * dy - wy * dx) / distance
    disc = va * va - cross * cross
    if disc <= 0:
        raise ValueError('NO_FLY')
    speed = along + math.sqrt(disc)
    if speed <= .05 * va:
        raise ValueError('NO_FLY')
    return speed


def integrate_leg(u, v, start, intervals, va=900.0):
    """Intervals are (exclusive_end_min, wx_m_per_min, wy_m_per_min).
    Last end may be infinity. Event-exact crossing; no silent horizon extension.
    """
    dx, dy = v.x - u.x, v.y - u.y
    remain, t = math.hypot(dx, dy), start
    if remain == 0:
        return 0.0
    for end, wx, wy in intervals:
        if end <= t:
            continue
        speed = ground_speed(dx, dy, wx, wy, va)
        available = end - t
        duration = remain / speed
        if duration <= available:
            return t + duration - start
        remain -= available * speed
        t = end
    raise ValueError('HORIZON_EXCEEDED')


def directed_delta(distance, depot, trip, a, b):
    seq = [depot] + list(trip) + [depot]
    new = list(trip)
    new[a:b+1] = reversed(new[a:b+1])
    seq2 = [depot] + new + [depot]
    return (sum(distance[x, y] for x, y in zip(seq2, seq2[1:]))
            - sum(distance[x, y] for x, y in zip(seq, seq[1:])))


def evaluate_constant(ins, sol, wind=(0., 0.)):
    """Independent full-solution planning audit under uniform constant forecast.
    Geometric coverage, fixed cost, battery per trip, duty never reset at return.
    """
    issues, seen, details = [], Counter(), []
    fixed = operating = makespan = 0.
    if len(sol['station_types']) != len(ins.stations) or len(sol['routes']) != len(ins.stations):
        return dict(feasible=False, issues=['station_dimension'])
    for si, (st, kind, routes) in enumerate(zip(ins.stations, sol['station_types'], sol['routes'])):
        if type(kind) is not int or kind not in (0, 1, 2) or len(routes) != 2:
            issues.append('station_or_drone_dimension')
            continue
        fixed += ins.fixed(kind)
        for di, trips in enumerate(routes):
            duty = 0.
            for ti, trip in enumerate(trips):
                if not trip:
                    continue
                if kind == 0 or (kind == 1 and di == 0):
                    issues.append('drone_qualification')
                valid = []
                for nid in trip:
                    if type(nid) is not int or nid not in ins.target_ids:
                        issues.append('non_target')
                        continue
                    n = ins.nodes[nid]
                    seen[nid] += 1
                    valid.append(n)
                    if math.hypot(n.x - st.x, n.y - st.y) > ins.radius(kind) + TOL:
                        issues.append('coverage')
                seq, flight = [st] + valid + [st], 0.
                try:
                    for u, v in zip(seq, seq[1:]):
                        flight += integrate_leg(u, v, 0., [(math.inf, *wind)], ins.params.speed)
                except ValueError as exc:
                    issues.append(str(exc))
                    flight = math.inf
                duration = flight + sum(n.service for n in valid)
                energy = flight * ins.params.flight_energy + sum(n.energy for n in valid)
                if energy > ins.capacity(di) + TOL:
                    issues.append('energy')
                duty += duration
                details.append(dict(station=si, drone=di, trip=ti, time=duration, energy=energy))
            if kind and duty > ins.duration(kind) + TOL:
                issues.append('cumulative_duty')
            operating += duty
            makespan = max(makespan, duty)
    if any(seen[n] != 1 for n in ins.target_ids):
        issues.append('exactly_once')
    return dict(feasible=not issues, issues=issues, cost=fixed + operating * ins.params.time_cost,
                operating_minutes=operating, makespan=makespan, details=details)
