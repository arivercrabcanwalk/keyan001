"""Exogenous stream: background Poisson releases and moving elliptical NFZ.

Contract sections 5.6 and 6.2.  Everything here is PUBLIC: releases define when
a task becomes visible, and the no-fly geometry is published with the forecast.
No private truth is read.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .core import PublicRolloutError, _f


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

    def blocks_leg(self, a_xy, b_xy, t0: float, n: int = 12) -> bool:
        """Conservative check: sample the leg and its time window."""
        for i in range(n + 1):
            f = i / n
            x = a_xy[0] + (b_xy[0] - a_xy[0]) * f
            y = a_xy[1] + (b_xy[1] - a_xy[1]) * f
            if self.contains(x, y, t0):
                return True
        return False

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


def leg_crosses_nfz(zones, a_xy, b_xy, t: float) -> bool:
    return any(z.blocks_leg(a_xy, b_xy, t) for z in zones)

@dataclass(frozen=True)
class AlarmLaw:
    """Fault alarms that follow a sweep.

    For every target we draw, BEFORE the episode, whether a fault will occur
    and how long after the sweep it appears.  The draw is independent of the
    policy, so an alarm can never be conditioned on what the policy did; it is
    realised only when the target is actually swept.

    Parameters are ENGINEERING DEFAULTS with stated provenance, not fitted
    values.  See DOCS_IMPLEMENTATION.md section 6.
    """

    prob: float = 0.2
    delay_lo: float = 0.0
    delay_hi: float = 20.0
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
                "delay_lo": _f(self.delay_lo), "delay_hi": _f(self.delay_hi)}