"""Small deterministic route oracle for synthetic, time-varying wind fixtures.

Coordinates are planar metres (x=east, y=north), and times are seconds. Wind is
piecewise-constant and uniform over space. The default ``speed`` and
``flight_energy`` retain the project parameter convention (m/min and abstract
energy units per flight minute); they are not aircraft-calibrated quantities.
No-fly vertices are supplied already buffered by the caller.

The visibility graph is finite. Since wind can make edge arrival functions
non-FIFO, the oracle enumerates simple graph paths instead of using Dijkstra's
FIFO-only label-setting rule. It never inserts a wait action or a cycle.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import hypot, isfinite, sqrt
from typing import Optional


_GEOM_EPS = 1e-10
_DIST_EPS = 1e-10


class WindInfeasibleError(ValueError):
    """A leg cannot make positive, track-aligned progress under the wind."""


@dataclass(frozen=True)
class Point:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        if not (isfinite(self.x_m) and isfinite(self.y_m)):
            raise ValueError("point coordinates must be finite")


@dataclass(frozen=True)
class WindKnot:
    time_s: float
    east_mps: float
    north_mps: float

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.time_s, self.east_mps, self.north_mps)):
            raise ValueError("wind knots must contain finite values")


@dataclass(frozen=True)
class WindField:
    """Uniform vector wind; each knot holds until the next knot."""

    knots: tuple[WindKnot, ...]

    def __post_init__(self) -> None:
        if not self.knots:
            raise ValueError("at least one wind knot is required")
        if any(not isinstance(knot, WindKnot) for knot in self.knots):
            raise TypeError("knots must be WindKnot values")
        if any(a.time_s >= b.time_s for a, b in zip(self.knots, self.knots[1:])):
            raise ValueError("wind knot times must be strictly increasing")
        if self.knots[0].time_s > 0.0:
            raise ValueError("the first wind knot must cover time zero")

    @property
    def times(self) -> tuple[float, ...]:
        return tuple(knot.time_s for knot in self.knots)

    def at(self, time_s: float) -> WindKnot:
        if not isfinite(time_s):
            raise ValueError("time must be finite")
        index = bisect_right(self.times, time_s) - 1
        if index < 0:
            raise ValueError("departure precedes the first wind knot")
        return self.knots[index]


@dataclass(frozen=True)
class FlightParams:
    # The project convention is m/min, converted to m/s for wind kinematics.
    speed: float = 900.0
    # Abstract energy units per flight minute; intentionally not calibrated.
    flight_energy: float = 0.018

    def __post_init__(self) -> None:
        if not isfinite(self.speed) or self.speed <= 0:
            raise ValueError("speed must be finite and positive")
        if not isfinite(self.flight_energy) or self.flight_energy < 0:
            raise ValueError("flight_energy must be finite and nonnegative")

    @property
    def airspeed_mps(self) -> float:
        return self.speed / 60.0


@dataclass(frozen=True)
class NoFlyZone:
    """Convex polygon active on the half-open interval [on_s, off_s)."""

    vertices: tuple[Point, ...]
    on_s: float
    off_s: float

    def __post_init__(self) -> None:
        if len(self.vertices) < 3 or any(not isinstance(p, Point) for p in self.vertices):
            raise ValueError("a no-fly zone needs at least three Point vertices")
        if not (isfinite(self.on_s) and isfinite(self.off_s) and self.on_s < self.off_s):
            raise ValueError("no-fly interval must be finite with on_s < off_s")
        area2 = _polygon_area2(self.vertices)
        if abs(area2) <= _GEOM_EPS:
            raise ValueError("no-fly polygon must have nonzero area")
        sign = 1.0 if area2 > 0 else -1.0
        count = len(self.vertices)
        for i, a in enumerate(self.vertices):
            b = self.vertices[(i + 1) % count]
            for j, point in enumerate(self.vertices):
                if j in (i, (i + 1) % count):
                    continue
                if sign * _cross(b.x_m - a.x_m, b.y_m - a.y_m,
                                 point.x_m - a.x_m, point.y_m - a.y_m) <= _GEOM_EPS:
                    raise ValueError("vertices must define a strictly convex polygon")


@dataclass(frozen=True)
class SegmentTiming:
    start: Point
    end: Point
    departure_time_s: float
    arrival_time_s: float
    distance_m: float
    energy: float


@dataclass(frozen=True)
class RouteResult:
    polyline: tuple[Point, ...]
    segments: tuple[SegmentTiming, ...]
    distance_m: float
    energy: float
    arrival_time_s: Optional[float]
    legal: bool
    failure: Optional[str] = None
    rejection_reasons: tuple[str, ...] = ()


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _polygon_area2(vertices: tuple[Point, ...]) -> float:
    return sum(
        a.x_m * b.y_m - b.x_m * a.y_m
        for a, b in zip(vertices, vertices[1:] + vertices[:1])
    )


def _inside_distance_interval(start: Point, end: Point, zone: NoFlyZone) -> Optional[tuple[float, float]]:
    """Return the positive-length open-interior interval along a segment."""
    dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
    length = hypot(dx, dy)
    if length <= _DIST_EPS:
        return None

    area2 = _polygon_area2(zone.vertices)
    sign = 1.0 if area2 > 0 else -1.0
    low, high = 0.0, 1.0
    for a, b in zip(zone.vertices, zone.vertices[1:] + zone.vertices[:1]):
        ex, ey = b.x_m - a.x_m, b.y_m - a.y_m
        f0 = sign * _cross(ex, ey, start.x_m - a.x_m, start.y_m - a.y_m)
        fd = sign * _cross(ex, ey, dx, dy)
        if abs(fd) <= _GEOM_EPS:
            if f0 < -_GEOM_EPS:
                return None
            continue
        boundary = -f0 / fd
        if fd > 0:
            low = max(low, boundary)
        else:
            high = min(high, boundary)
        if low >= high - _GEOM_EPS:
            return None

    low, high = max(0.0, low), min(1.0, high)
    if high <= low + _GEOM_EPS:
        return None

    # A tangent or a segment following the polygon boundary has no interior.
    middle = (low + high) / 2.0
    mx, my = start.x_m + middle * dx, start.y_m + middle * dy
    for a, b in zip(zone.vertices, zone.vertices[1:] + zone.vertices[:1]):
        if sign * _cross(b.x_m - a.x_m, b.y_m - a.y_m,
                         mx - a.x_m, my - a.y_m) <= _GEOM_EPS:
            return None
    return low * length, high * length


def _track_speed(direction_x: float, direction_y: float, wind: WindKnot,
                 airspeed_mps: float) -> float:
    if not all(isfinite(v) for v in (direction_x, direction_y, airspeed_mps)):
        raise ValueError("nonfinite leg geometry")
    along = wind.east_mps * direction_x + wind.north_mps * direction_y
    cross = -wind.east_mps * direction_y + wind.north_mps * direction_x
    if abs(cross) > airspeed_mps:
        raise WindInfeasibleError("crosswind_infeasible")
    ground_speed = along + sqrt(max(0.0, airspeed_mps * airspeed_mps - cross * cross))
    if not isfinite(ground_speed) or ground_speed <= 0.0:
        raise WindInfeasibleError("nonpositive_progress")
    return ground_speed


def _integrate_leg(start: Point, end: Point, departure_time_s: float,
                   wind: WindField, params: FlightParams
                   ) -> tuple[SegmentTiming, tuple[tuple[float, float], ...]]:
    if not isfinite(departure_time_s) or departure_time_s < 0.0:
        raise ValueError("departure time must be finite and nonnegative")
    dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
    distance = hypot(dx, dy)
    if not isfinite(distance):
        raise ValueError("leg distance must be finite")
    if distance == 0.0:
        segment = SegmentTiming(start, end, departure_time_s, departure_time_s,
                                0.0, 0.0)
        return segment, ((0.0, departure_time_s),)

    ux, uy = dx / distance, dy / distance
    remaining, covered, now = distance, 0.0, departure_time_s
    profile: list[tuple[float, float]] = [(0.0, now)]
    times = wind.times
    while remaining > 0.0:
        knot_index = bisect_right(times, now) - 1
        if knot_index < 0:
            raise ValueError("departure precedes the first wind knot")
        knot = wind.knots[knot_index]
        speed = _track_speed(ux, uy, knot, params.airspeed_mps)
        next_knot = times[knot_index + 1] if knot_index + 1 < len(times) else None
        if next_knot is None:
            duration = remaining / speed
            covered += remaining
            now += duration
            profile.append((distance, now))
            remaining = 0.0
            break

        available_duration = next_knot - now
        available_distance = speed * available_duration
        if remaining <= available_distance:
            duration = remaining / speed
            covered += remaining
            now += duration
            profile.append((distance, now))
            remaining = 0.0
        else:
            covered += available_distance
            remaining -= available_distance
            now = next_knot
            profile.append((covered, now))

        if not all(isfinite(v) for v in (now, covered, remaining)):
            raise ValueError("nonfinite leg timing")

    if not all(isfinite(v) for v in (now, covered, remaining)):
        raise ValueError("nonfinite leg timing")
    energy = params.flight_energy * ((now - departure_time_s) / 60.0)
    if not isfinite(energy):
        raise ValueError("nonfinite leg energy")
    segment = SegmentTiming(start, end, departure_time_s, now, distance, energy)
    return segment, tuple(profile)


def integrate_leg(start: Point, end: Point, departure_time_s: float,
                  wind: WindField, params: FlightParams = FlightParams()) -> SegmentTiming:
    """Integrate one straight leg exactly across wind knots; infeasible legs raise."""
    return _integrate_leg(start, end, departure_time_s, wind, params)[0]


def _time_at_distance(profile: tuple[tuple[float, float], ...], distance_m: float) -> float:
    if distance_m <= 0:
        return profile[0][1]
    for (d0, t0), (d1, t1) in zip(profile, profile[1:]):
        if distance_m <= d1 + _DIST_EPS:
            if d1 <= d0:
                return t1
            ratio = min(1.0, max(0.0, (distance_m - d0) / (d1 - d0)))
            return t0 + ratio * (t1 - t0)
    return profile[-1][1]


def plan_route(start: Point, end: Point, departure_time_s: float, wind: WindField,
               params: FlightParams = FlightParams(),
               no_fly_zone: Optional[NoFlyZone] = None) -> RouteResult:
    """Find the earliest-arrival simple path in the endpoint/vertex visibility graph.

    Every edge departs immediately after the previous edge arrives. The active
    zone rejects an edge only when its positive-length polygon-interior portion
    overlaps ``[on_s, off_s)`` at the integrated entry/exit times.
    """
    if not isfinite(departure_time_s) or departure_time_s < 0.0:
        raise ValueError("departure time must be finite and nonnegative")
    if start == end:
        return RouteResult((start,), (), 0.0, 0.0, departure_time_s, True)

    nodes: list[Point] = []
    for point in (start, end) + (() if no_fly_zone is None else no_fly_zone.vertices):
        if point not in nodes:
            nodes.append(point)
    start_index, goal_index = nodes.index(start), nodes.index(end)
    best_key: Optional[tuple[float, float, tuple[int, ...]]] = None
    best: Optional[RouteResult] = None
    rejected: set[str] = set()

    def visit(index: int, path: tuple[int, ...], now: float,
              segments: tuple[SegmentTiming, ...], distance: float, energy: float) -> None:
        nonlocal best_key, best
        if best is not None and now > best.arrival_time_s:
            return
        if index == goal_index:
            key = (round(now, 12), round(distance, 12), path)
            if best_key is None or key < best_key:
                best_key = key
                best = RouteResult(tuple(nodes[i] for i in path), segments,
                                   distance, energy, now, True)
            return

        for next_index in range(len(nodes)):
            if next_index in path:
                continue
            a, b = nodes[index], nodes[next_index]
            try:
                segment, profile = _integrate_leg(a, b, now, wind, params)
            except WindInfeasibleError as exc:
                rejected.add(str(exc))
                continue

            if no_fly_zone is not None:
                inside = _inside_distance_interval(a, b, no_fly_zone)
                if inside is not None:
                    entry = _time_at_distance(profile, inside[0])
                    exit_ = _time_at_distance(profile, inside[1])
                    if max(entry, no_fly_zone.on_s) < min(exit_, no_fly_zone.off_s):
                        rejected.add("active_nfz_intersection")
                        continue

            visit(next_index, path + (next_index,), segment.arrival_time_s,
                  segments + (segment,), distance + segment.distance_m,
                  energy + segment.energy)

    visit(start_index, (start_index,), departure_time_s, (), 0.0, 0.0)
    if best is not None:
        return best
    reasons = tuple(sorted(rejected))
    failure = "+".join(reasons) if reasons else "no_legal_path"
    return RouteResult((), (), 0.0, 0.0, None, False, failure, reasons)
