"""Independent deterministic wind/NFZ route evaluator.

This module deliberately does not import the environment or `weather_oracle`'s
route planner.  It owns a second visibility-graph enumeration, wind-knot
integrator, and strict-interior overlap test.  The immutable scenario value
classes are shared solely to keep the serialized input schema identical.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import hypot, isfinite, sqrt
from typing import Optional

from weather_oracle import FlightParams, NoFlyZone, Point, WindField


EPS = 1e-9
# Match the primary oracle's geometric boundary without weakening the route
# search's looser time/tie comparison tolerance.
GEOM_EPS = 1e-10
DIST_EPS = 1e-10


@dataclass(frozen=True)
class ReplaySegment:
    start: Point
    end: Point
    departure_s: float
    arrival_s: float
    distance_m: float
    energy: float


@dataclass(frozen=True)
class ReplayRoute:
    legal: bool
    arrival_s: Optional[float]
    distance_m: float
    energy: float
    path: tuple[Point, ...]
    segments: tuple[ReplaySegment, ...]
    failure: Optional[str] = None


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _area2(vertices: tuple[Point, ...]) -> float:
    return sum(a.x_m * b.y_m - b.x_m * a.y_m
               for a, b in zip(vertices, vertices[1:] + vertices[:1]))


def _track_ground_speed(dx: float, dy: float, wind_x: float, wind_y: float,
                        airspeed: float) -> Optional[float]:
    length = hypot(dx, dy)
    if not isfinite(length):
        return None
    # Keep the independent replay's zero-leg contract identical to the primary
    # oracle: only an exactly coincident endpoint is zero length. A positive,
    # sub-EPS leg still has physical time and energy and must not disappear.
    if length == 0.0:
        return 0.0
    ux, uy = dx / length, dy / length
    along = wind_x * ux + wind_y * uy
    crosswind = -wind_x * uy + wind_y * ux
    # Match the primary oracle's physical boundary exactly.  Numerical
    # independence must never loosen a feasibility certificate.
    if abs(crosswind) > airspeed:
        return None
    speed = along + sqrt(max(0.0, airspeed * airspeed - crosswind * crosswind))
    return speed if isfinite(speed) and speed > 0.0 else None


def _wind_failure(dx: float, dy: float, wind_x: float, wind_y: float, airspeed: float) -> str:
    length = hypot(dx, dy)
    if length == 0.0:
        return "nonpositive_progress"
    crosswind = -wind_x * (dy / length) + wind_y * (dx / length)
    return "crosswind_infeasible" if abs(crosswind) > airspeed else "nonpositive_progress"


def _integrate(start: Point, end: Point, departure_s: float, wind: WindField,
               flight: FlightParams) -> tuple[ReplaySegment, tuple[tuple[float, float], ...]]:
    """Own exact piecewise wind integration; profile maps path distance to time."""
    if not isfinite(departure_s) or departure_s < 0.0:
        raise ValueError("departure must be finite and nonnegative")
    distance = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
    if not isfinite(distance):
        raise ValueError("nonfinite leg distance")
    if distance == 0.0:
        segment = ReplaySegment(start, end, departure_s, departure_s, 0.0, 0.0)
        return segment, ((0.0, departure_s),)
    now, travelled, remaining = departure_s, 0.0, distance
    profile = [(0.0, now)]
    times = tuple(k.time_s for k in wind.knots)
    while remaining > 0.0:
        index = bisect_right(times, now) - 1
        if index < 0:
            raise ValueError("wind does not cover departure time")
        knot = wind.knots[index]
        speed = _track_ground_speed(end.x_m - start.x_m, end.y_m - start.y_m,
                                    knot.east_mps, knot.north_mps, flight.airspeed_mps)
        if speed is None:
            raise ValueError(_wind_failure(end.x_m - start.x_m, end.y_m - start.y_m,
                                           knot.east_mps, knot.north_mps, flight.airspeed_mps))
        next_time = times[index + 1] if index + 1 < len(times) else None
        if next_time is None:
            duration = remaining / speed
            now += duration
            travelled += remaining
            remaining = 0.0
            profile.append((distance, now))
            break
        available = max(0.0, next_time - now) * speed
        if remaining <= available:
            duration = remaining / speed
            now += duration
            travelled += remaining
            remaining = 0.0
            profile.append((distance, now))
        else:
            now = next_time
            travelled += available
            remaining -= available
            profile.append((min(distance, travelled), now))
        if not all(isfinite(v) for v in (now, travelled, remaining)):
            raise ValueError("nonfinite leg timing")
    if not all(isfinite(v) for v in (now, travelled, remaining)):
        raise ValueError("nonfinite leg timing")
    elapsed = now - departure_s
    if not isfinite(elapsed):
        raise ValueError("nonfinite leg elapsed time")
    segment = ReplaySegment(start, end, departure_s, now, distance,
                            flight.flight_energy * elapsed / 60.0)
    return segment, tuple(profile)


def _time_for_distance(profile: tuple[tuple[float, float], ...], value: float) -> float:
    if value <= 0.0:
        return profile[0][1]
    for (d0, t0), (d1, t1) in zip(profile, profile[1:]):
        if value <= d1 + DIST_EPS:
            if d1 <= d0 + DIST_EPS:
                return t1
            return t0 + (t1 - t0) * (value - d0) / (d1 - d0)
    return profile[-1][1]


def _strict_interior_distances(start: Point, end: Point,
                               zone: NoFlyZone) -> Optional[tuple[float, float]]:
    """Independent convex clipping, returning strict-interior path distances."""
    dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
    length = hypot(dx, dy)
    if length <= DIST_EPS:
        return None
    sign = 1.0 if _area2(zone.vertices) > 0.0 else -1.0
    lower, upper = 0.0, 1.0
    for a, b in zip(zone.vertices, zone.vertices[1:] + zone.vertices[:1]):
        c0 = sign * _cross(b.x_m - a.x_m, b.y_m - a.y_m,
                           start.x_m - a.x_m, start.y_m - a.y_m)
        cd = sign * _cross(b.x_m - a.x_m, b.y_m - a.y_m, dx, dy)
        if abs(cd) <= GEOM_EPS:
            if c0 < -GEOM_EPS:
                return None
            continue
        boundary = -c0 / cd
        if cd > 0.0:
            lower = max(lower, boundary)
        else:
            upper = min(upper, boundary)
        if lower >= upper - GEOM_EPS:
            return None
    lower, upper = max(0.0, lower), min(1.0, upper)
    if upper <= lower + GEOM_EPS:
        return None
    midpoint = (lower + upper) / 2.0
    point = Point(start.x_m + midpoint * dx, start.y_m + midpoint * dy)
    for a, b in zip(zone.vertices, zone.vertices[1:] + zone.vertices[:1]):
        if sign * _cross(b.x_m - a.x_m, b.y_m - a.y_m,
                         point.x_m - a.x_m, point.y_m - a.y_m) <= GEOM_EPS:
            return None
    return lower * length, upper * length


def _edge_allowed(start: Point, end: Point, departure_s: float, wind: WindField,
                  flight: FlightParams, zone: Optional[NoFlyZone]):
    try:
        segment, profile = _integrate(start, end, departure_s, wind, flight)
    except ValueError as exc:
        return None, str(exc)
    if zone is not None:
        inside = _strict_interior_distances(start, end, zone)
        if inside is not None:
            enters = _time_for_distance(profile, inside[0])
            exits = _time_for_distance(profile, inside[1])
            if max(enters, zone.on_s) < min(exits, zone.off_s):
                return None, "active_nfz_intersection"
    return segment, None


def replay_route(start: Point, end: Point, departure_s: float, wind: WindField,
                 flight: FlightParams, zone: Optional[NoFlyZone] = None) -> ReplayRoute:
    """Independently select the canonical earliest simple visibility route."""
    if not isfinite(departure_s) or departure_s < 0.0:
        raise ValueError("departure must be finite and nonnegative")
    if start == end:
        return ReplayRoute(True, departure_s, 0.0, 0.0, (start,), ())
    nodes: list[Point] = []
    for point in (start, end) + (() if zone is None else zone.vertices):
        if point not in nodes:
            nodes.append(point)
    start_idx, goal_idx = nodes.index(start), nodes.index(end)
    chosen = None
    failures: set[str] = set()

    def search(index: int, seen: tuple[int, ...], now: float,
               segments: tuple[ReplaySegment, ...], distance: float, energy: float) -> None:
        nonlocal chosen
        if chosen is not None and now > chosen[0] + EPS:
            return
        if index == goal_idx:
            candidate = (now, distance, seen, segments, energy)
            if chosen is None or (round(now, 11), round(distance, 11), seen) < (
                    round(chosen[0], 11), round(chosen[1], 11), chosen[2]):
                chosen = candidate
            return
        for next_idx, target in enumerate(nodes):
            if next_idx in seen:
                continue
            segment, failure = _edge_allowed(nodes[index], target, now, wind, flight, zone)
            if failure is not None:
                failures.add(failure)
                continue
            search(next_idx, seen + (next_idx,), segment.arrival_s,
                   segments + (segment,), distance + segment.distance_m,
                   energy + segment.energy)

    search(start_idx, (start_idx,), departure_s, (), 0.0, 0.0)
    if chosen is None:
        return ReplayRoute(False, None, 0.0, 0.0, (), (),
                           "+".join(sorted(failures)) or "no_legal_path")
    arrival, distance, path_indices, segments, energy = chosen
    return ReplayRoute(True, arrival, distance, energy,
                       tuple(nodes[index] for index in path_indices), segments)
