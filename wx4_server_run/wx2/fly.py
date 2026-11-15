"""Path planning around predicted cells, and truth-wind flight integration."""
from __future__ import annotations

from __future__ import annotations as _ann_paths
import os as _os_paths, sys as _sys_paths
def _wx_root():
    e = _os_paths.environ.get("WX_ROOT")
    if e:
        return _os_paths.path.abspath(e)
    return _os_paths.path.abspath(_os_paths.path.join(_os_paths.path.dirname(_os_paths.path.abspath(__file__)), ".."))
WX_ROOT = _wx_root()
_VENDOR = _os_paths.path.join(WX_ROOT, "vendor")
if WX_ROOT not in _sys_paths.path:
    _sys_paths.path.insert(0, WX_ROOT)
if _VENDOR not in _sys_paths.path:
    _sys_paths.path.insert(0, _VENDOR)

import math
import numpy as np
from . import const as C
from .weather import ground_speed_mpm, ellipse_contains, segment_hits_ellipse, _around_points


def _lerp(p1, p2, s):
    return (p1[0] * (1 - s) + p2[0] * s, p1[1] * (1 - s) + p2[1] * s)


def _dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def pred_cell_at(nc, t_now, t):
    dtsec = (t - t_now) * 60.0
    return nc["cx"] + nc["vx"] * dtsec, nc["cy"] + nc["vy"] * dtsec


def corridor_hits(p1, p2, t0, dur, nowcast, buf=C.BUFFER, n=10):
    if not nowcast or dur <= 0:
        # still check static if dur==0
        dur = max(dur, _dist(p1, p2) / C.VA)
    for nc in nowcast:
        for k in range(n + 1):
            s = k / n
            t = t0 + s * dur
            x, y = _lerp(p1, p2, s)
            cx, cy = pred_cell_at(nc, t0, t)
            if ellipse_contains(x, y, cx, cy, nc["a"], nc["b"], nc["ang"], buf):
                return True
    return False


def plan_leg(p1, p2, t0, nowcast, wx_fc, buf=C.BUFFER):
    """Return (waypoints including both ends, predicted_clear, pred_time_min, pred_dist).

    wx_fc is (wx,wy) in m/s used to estimate duration (constant along the leg).
    """
    d0 = _dist(p1, p2)
    if d0 < 1e-6:
        return [p1, p2], True, 0.0, 0.0
    ux, uy = (p2[0] - p1[0]) / d0, (p2[1] - p1[1]) / d0
    vg = ground_speed_mpm(wx_fc[0], wx_fc[1], ux, uy)
    spd = vg if vg > 30.0 else C.VA * 0.3
    dur = d0 / spd
    if not nowcast or not corridor_hits(p1, p2, t0, dur, nowcast, buf):
        return [p1, p2], True, dur, d0

    # try one-waypoint detours around each threatening cell
    best = None
    for nc in nowcast:
        pts = _around_points(nc["cx"], nc["cy"], nc["a"], nc["b"], nc["ang"], buf + 400.0, n=8)
        for q in pts:
            d1 = _dist(p1, q) + _dist(q, p2)
            dur1 = d1 / spd
            if corridor_hits(p1, q, t0, _dist(p1, q) / spd, nowcast, buf):
                continue
            tq = t0 + _dist(p1, q) / spd
            if corridor_hits(q, p2, tq, _dist(q, p2) / spd, nowcast, buf):
                continue
            if best is None or d1 < best[0]:
                best = (d1, [p1, q, p2], dur1)
    if best is None:
        # no safe detour found: return straight, flagged unsafe
        return [p1, p2], False, dur, d0
    return best[1], True, best[2], best[0]


def plan_trip(origin, stops, t0, nowcast, wx_fc, buf=C.BUFFER):
    """stops: list of (x,y,service,energy) then back to origin is added.
    Returns waypoints-with-service, pred_clear, pred_time (incl service), pred_flight_dist.
    Each wp: (x,y,service,energy) ; service only at stops, 0 at detour wps and origin ends.
    """
    seq = [origin] + [(s[0], s[1]) for s in stops] + [origin]
    svc = [0.0] + [s[2] for s in stops] + [0.0]
    en = [0.0] + [s[3] for s in stops] + [0.0]
    wps = []
    t = t0
    clear = True
    flight_d = 0.0
    for i in range(len(seq) - 1):
        leg, cl, dur, dist = plan_leg(seq[i], seq[i + 1], t, nowcast, wx_fc, buf)
        clear = clear and cl
        # all but last of this leg are intermediate (no service); last coincides with next origin
        for k, p in enumerate(leg[:-1]):
            if i == 0 and k == 0:
                wps.append((p[0], p[1], 0.0, 0.0))
            elif k == 0:
                pass  # already added as previous stop
            else:
                wps.append((p[0], p[1], 0.0, 0.0))
        # add destination of this leg with its service
        dest = leg[-1]
        wps.append((dest[0], dest[1], svc[i + 1], en[i + 1]))
        t += dur + svc[i + 1]
        flight_d += dist
    pred_time = t - t0
    return wps, clear, pred_time, flight_d


def integrate(wps, t0, energy0, cap, wx, flight_energy, truth=True, t_now_for_fc=None,
              nowcast=None):
    """Integrate along waypoints under TRUTH (default) or forecast wind.

    wps: (x,y,service,energy)* . Starts at first wp at t0 (already there).
    energy0 is energy already used on this battery (0 after a swap).
    Returns dict(ok, t, energy, flight_min, fail, fail_t, x, y).
    """
    t = t0
    e = energy0
    flight_min = 0.0
    x, y = wps[0][0], wps[0][1]
    tref = t0 if t_now_for_fc is None else t_now_for_fc
    for k in range(1, len(wps)):
        x2, y2, svc, een = wps[k]
        # fly to (x2,y2)
        while True:
            dx, dy = x2 - x, y2 - y
            d = math.hypot(dx, dy)
            if d < 1.0:
                x, y = x2, y2
                break
            ux, uy = dx / d, dy / d
            if truth:
                wxv, wyv = wx.truth_wind(x, y, t)
                if wx.in_any_cell(x, y, t, buf=0.0):
                    return dict(ok=False, t=t, energy=e, flight_min=flight_min,
                                fail="cell", fail_t=t, x=x, y=y, k=k)
            else:
                wxv, wyv = wx.forecast_wind(tref, t)
            vg = ground_speed_mpm(wxv, wyv, ux, uy)
            if vg < 40.0:
                # unsustainable / very slow: crawl at 40 m/min (~0.67 m/s) and drain energy
                vg = 40.0
            step = C.DT_FLY
            reach = d / vg
            dt = min(step, reach)
            # cell check at mid-step under truth
            xm, ym = x + ux * vg * dt * 0.5, y + uy * vg * dt * 0.5
            if truth and wx.in_any_cell(xm, ym, t + dt * 0.5, buf=0.0):
                return dict(ok=False, t=t + dt * 0.5, energy=e, flight_min=flight_min + dt * 0.5,
                            fail="cell", fail_t=t + dt * 0.5, x=xm, y=ym, k=k)
            e += flight_energy * dt
            if e > cap + 1e-9:
                return dict(ok=False, t=t + dt, energy=e, flight_min=flight_min + dt,
                            fail="energy", fail_t=t + dt, x=x + ux * vg * dt, y=y + uy * vg * dt, k=k)
            x += ux * vg * dt
            y += uy * vg * dt
            t += dt
            flight_min += dt
            # hard cap on a single leg (should not happen with 40 m/min crawl + energy fail)
            if flight_min > 180.0:
                return dict(ok=False, t=t, energy=e, flight_min=flight_min,
                            fail="timeout", fail_t=t, x=x, y=y, k=k)
        # service at this wp (hover). Cell arriving during service = fail.
        if svc > 0:
            remaining = svc
            while remaining > 1e-9:
                dt = min(C.DT_FLY, remaining)
                if truth and wx.in_any_cell(x, y, t + dt * 0.5, buf=0.0):
                    return dict(ok=False, t=t + dt * 0.5, energy=e + een * (1 - remaining / svc),
                                flight_min=flight_min, fail="cell", fail_t=t + dt * 0.5, x=x, y=y, k=k)
                t += dt
                remaining -= dt
            e += een
            if e > cap + 1e-9:
                return dict(ok=False, t=t, energy=e, flight_min=flight_min,
                            fail="energy", fail_t=t, x=x, y=y, k=k)
    return dict(ok=True, t=t, energy=e, flight_min=flight_min, fail=None, fail_t=None, x=x, y=y, k=len(wps))


def pred_energy_time(wps, t0, wx, flight_energy, t_now=None):
    """Forecast-only energy and time (no failure from true cells). Used for masks / N2."""
    # approximate: use forecast wind, ignore spatial, sum dist/vg + service
    tref = t0 if t_now is None else t_now
    t = t0
    e = 0.0
    flight = 0.0
    x, y = wps[0][0], wps[0][1]
    for k in range(1, len(wps)):
        x2, y2, svc, een = wps[k]
        d = math.hypot(x2 - x, y2 - y)
        if d > 1.0:
            ux, uy = (x2 - x) / d, (y2 - y) / d
            wxv, wyv = wx.forecast_wind(tref, t)
            vg = ground_speed_mpm(wxv, wyv, ux, uy)
            if vg < 30.0:
                vg = 30.0
            dt = d / vg
            e += flight_energy * dt
            t += dt
            flight += dt
        t += svc
        e += een
        x, y = x2, y2
    return e, t - t0, flight
