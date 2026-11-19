"""Exogenous stream: background Poisson releases and moving elliptical NFZ.

Contract sections 5.6 and 6.2.  Everything here is PUBLIC: releases define when
a task becomes visible, and the no-fly geometry is published with the forecast.
No private truth is read.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .core import AlarmJob, PublicRolloutError, _f


@dataclass(frozen=True)
class MovingNFZ:
    """An ellipse that translates at constant velocity."""

    cx0: float
    cy0: float
    vx: float
    vy: float
    a: float               # semi-major axis, m
    b: float               # semi-minor axis, m
    angle: float = 0.0     # radians
    active_from: float = 0.0
    active_to: float = 1e18

    def center(self, t: float) -> tuple[float, float]:
        return (_f(self.cx0 + self.vx * t), _f(self.cy0 + self.vy * t))

    def contains(self, x: float, y: float, t: float) -> bool:
        if not (self.active_from <= t <= self.active_to):
            return False
        cx, cy = self.center(t)
        dx, dy = x - cx, y - cy
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        u = dx * c - dy * s
        v = dx * s + dy * c
        if self.a <= 0 or self.b <= 0:
            raise PublicRolloutError("degenerate NFZ axes")
        return (u / self.a) ** 2 + (v / self.b) ** 2 <= 1.0

    def blocks_leg(self, a_xy, b_xy, t0: float,
                   t1: float | None = None) -> bool:
        """Exact segment/linear-time intersection for this translating ellipse."""
        if self.a <= 0 or self.b <= 0:
            raise PublicRolloutError("degenerate NFZ axes")
        t1 = t0 if t1 is None else t1
        if t1 < t0:
            raise PublicRolloutError("leg ends before it starts")
        dt = t1 - t0
        if dt == 0:
            if not self.active_from <= t0 <= self.active_to:
                return False
            lo, hi = 0.0, 1.0
        else:
            lo = max(0.0, (self.active_from - t0) / dt)
            hi = min(1.0, (self.active_to - t0) / dt)
            if lo > hi:
                return False
        c, s = math.cos(-self.angle), math.sin(-self.angle)
        cx, cy = self.center(t0)
        x0, y0 = a_xy[0] - cx, a_xy[1] - cy
        dx = b_xy[0] - a_xy[0] - self.vx * dt
        dy = b_xy[1] - a_xy[1] - self.vy * dt
        u0, v0 = c * x0 - s * y0, s * x0 + c * y0
        du, dv = c * dx - s * dy, s * dx + c * dy
        a = (du / self.a) ** 2 + (dv / self.b) ** 2
        b = (u0 * du / self.a ** 2 + v0 * dv / self.b ** 2)
        f_star = lo if a == 0 else min(hi, max(lo, -b / a))
        q_min = ((u0 + du * f_star) / self.a) ** 2 + ((v0 + dv * f_star) / self.b) ** 2
        return q_min <= 1.0 + 1e-12

    def payload(self) -> list:
        return [_f(self.cx0), _f(self.cy0), _f(self.vx), _f(self.vy),
                _f(self.a), _f(self.b), _f(self.angle),
                _f(self.active_from), _f(self.active_to)]


def nfz_from_payload(rows) -> tuple[MovingNFZ, ...]:
    return tuple(MovingNFZ(*row) for row in rows)


def poisson_releases(rate_per_min: float, horizon: float, rng: random.Random,
                     pool) -> tuple[tuple[float, int], ...]:
    """Background requests: independent exponential inter-arrival times."""
    if rate_per_min <= 0:
        return ()
    pool = list(pool)
    out: list[tuple[float, int]] = []
    t = 0.0
    while True:
        t += rng.expovariate(rate_per_min)
        if t > horizon or not pool:
            break
        out.append((_f(t), pool.pop(0)))
    return tuple(out)


def blocked_by_nfz(zones, point, t: float) -> bool:
    return any(z.contains(point[0], point[1], t) for z in zones)


def leg_crosses_nfz(zones, a_xy, b_xy, t0: float,
                    t1: float | None = None) -> bool:
    return any(z.blocks_leg(a_xy, b_xy, t0, t1) for z in zones)


def storm_exit_time(zone: MovingNFZ, point) -> float | None:
    """First end of a target/ellipse crossing, independent of drone actions."""
    if zone.a <= 0 or zone.b <= 0:
        raise PublicRolloutError("degenerate NFZ axes")
    c, s = math.cos(-zone.angle), math.sin(-zone.angle)
    x0, y0 = point[0] - zone.cx0, point[1] - zone.cy0
    u0, v0 = c * x0 - s * y0, s * x0 + c * y0
    du, dv = -c * zone.vx + s * zone.vy, -s * zone.vx - c * zone.vy
    a = (du / zone.a) ** 2 + (dv / zone.b) ** 2
    b = 2 * (u0 * du / zone.a ** 2 + v0 * dv / zone.b ** 2)
    c0 = (u0 / zone.a) ** 2 + (v0 / zone.b) ** 2 - 1.0
    if a < 1e-24:
        return _f(zone.active_to) if c0 <= 0 else None
    disc = b * b - 4 * a * c0
    if disc < 0:
        return None
    root = math.sqrt(max(0.0, disc))
    enter, leave = sorted(((-b - root) / (2 * a), (-b + root) / (2 * a)))
    if max(enter, zone.active_from) > min(leave, zone.active_to):
        return None
    return _f(min(leave, zone.active_to))

@dataclass(frozen=True)
class AlarmLaw:
    """Pre-drawn fault and delay law for a storm crossing.

    For every target we draw, BEFORE the episode, whether a fault will occur
    and how long after the storm exits it appears.  The draw is independent
    of the policy and never waits for a drone service completion.

    Parameters are ENGINEERING DEFAULTS with stated provenance, not fitted
    values.  See DOCS_IMPLEMENTATION.md section 6.
    """

    prob: float = 0.2
    delay_lo: float = 0.0
    delay_hi: float = 20.0
    high_prob: float = 0.4
    high_due: float = 20.0
    routine_due: float = 45.0
    law_id: str = "alarm-uniform-delay-v1"

    def draw(self, targets, rng: random.Random) -> tuple[tuple[int, float], ...]:
        out = []
        for tid in targets:
            if rng.random() < self.prob:
                d = rng.uniform(self.delay_lo, self.delay_hi)
            else:
                # -1 is the explicit 'no alarm' sentinel; JSON stays finite
                d = -1.0
            out.append((tid, _f(d)))
        return tuple(out)

    def payload(self) -> dict:
        return {"law_id": self.law_id, "prob": _f(self.prob),
                "delay_lo": _f(self.delay_lo), "delay_hi": _f(self.delay_hi),
                "high_prob": _f(self.high_prob), "high_due": _f(self.high_due),
                "routine_due": _f(self.routine_due)}


def storm_alarm_jobs(zones, targets, law: AlarmLaw, rng: random.Random,
                     horizon: float) -> tuple[AlarmJob, ...]:
    """Freeze first-crossing alarm jobs before any policy acts."""
    targets = sorted(targets, key=lambda node: node.node_id)
    delays = dict(law.draw((node.node_id for node in targets), rng))
    priorities = {node.node_id: rng.random() for node in targets}
    out = []
    for node in targets:
        exits = [t for z in zones
                 if (t := storm_exit_time(z, (node.x, node.y))) is not None]
        if not exits or delays[node.node_id] < 0:
            continue
        release = min(exits) + delays[node.node_id]
        if release > horizon:
            continue
        priority = "high" if priorities[node.node_id] < law.high_prob else "routine"
        due = law.high_due if priority == "high" else law.routine_due
        out.append(AlarmJob(f"storm:{node.node_id}", node.node_id,
                            _f(release), _f(release + due), priority))
    return tuple(out)
