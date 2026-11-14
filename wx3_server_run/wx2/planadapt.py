"""Re-pack a frozen-station fleet under the morning forecast wind.

Keeps the original ALNS/TSALNS trip structure when it remains energy-feasible
under the forecast; drops tail targets from infeasible trips and re-inserts
them by earliest-finish (load-balancing) cheapest insertion.
"""
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

import math, hashlib
from . import inst as I
from . import fly as F

_CACHE = {}


def _energy(ins, st, d, trip, wx, t0, fc):
    if not trip:
        return 0.0, 0.0
    nodes = I.node_by_id(ins)
    stops = [(nodes[n].x, nodes[n].y, nodes[n].service, nodes[n].energy) for n in trip]
    wps, _, _, _ = F.plan_trip((st["x"], st["y"]), stops, t0, [], fc)
    e, ttot, fl = F.pred_energy_time(wps, t0, wx, ins.params.flight_energy, t0)
    return e, ttot


def _can(ins, st, d, trip, wx, t0, fc, margin):
    e, ttot = _energy(ins, st, d, trip, wx, t0, fc)
    return e <= d["cap"] * (1.0 - margin) + 1e-9, e, ttot


def _drone_time(ins, stations, d, wx, t0, fc):
    st = stations[d["sid"]]
    tot = 0.0
    for tr in d["trips"]:
        _, ttot = _energy(ins, st, d, tr, wx, t0, fc)
        tot += ttot
    return tot


def _assigned(drones):
    s = []
    for d in drones:
        for tr in d["trips"]:
            s.extend(tr)
    return s


def _try_insert(ins, stations, drones, tid, wx, t0, fc, margin, nodes):
    """Earliest-finish insertion: pick the feasible slot that minimizes the
    receiving drone's new total time (balances load; empty drones compete)."""
    n = nodes[tid]
    best = None
    times = [_drone_time(ins, stations, d, wx, t0, fc) for d in drones]
    for di, d in enumerate(drones):
        st = stations[d["sid"]]
        if math.hypot(n.x - st["x"], n.y - st["y"]) > d["R"] + 1e-6:
            continue
        # new trip
        ok, e, ttot = _can(ins, st, d, [tid], wx, t0, fc, margin)
        if ok:
            finish = times[di] + ttot
            # slight preference for a tighter insertion if finishes equal
            if best is None or finish < best[0] - 1e-9 or (abs(finish - best[0]) <= 1e-9 and ttot < best[1]):
                best = (finish, ttot, di, len(d["trips"]), 0, "new")
        for ti, tr in enumerate(d["trips"]):
            e0, t00 = _energy(ins, st, d, tr, wx, t0, fc)
            for pos in range(len(tr) + 1):
                nt = tr[:pos] + [tid] + tr[pos:]
                ok, e, ttot = _can(ins, st, d, nt, wx, t0, fc, margin)
                if not ok:
                    continue
                finish = times[di] - t00 + ttot
                detour = ttot - t00
                if best is None or finish < best[0] - 1e-9 or (abs(finish - best[0]) <= 1e-9 and detour < best[1]):
                    best = (finish, detour, di, ti, pos, "ins")
    if best is None:
        return False
    _, _, di, ti, pos, kind = best
    d = drones[di]
    if kind == "new":
        d["trips"].append([tid])
    else:
        d["trips"][ti].insert(pos, tid)
    return True


def _to_sol(sol, drones, leftover, margin):
    types = list(sol["station_types"])
    routes = [[[], []] for _ in types]
    for d in drones:
        routes[d["si"]][d["di"]] = [list(tr) for tr in d["trips"]]
    new = {k: sol[k] for k in sol}
    new["routes"] = routes
    new["station_types"] = types
    new["adapted"] = True
    new["adapt_margin"] = margin
    new["unpacked"] = list(leftover)
    return new


def _strip_dups(ins, drones):
    seen = set()
    for d in drones:
        nt = []
        for tr in d["trips"]:
            tr2 = [t for t in tr if t not in seen and not seen.add(t)]
            if tr2:
                nt.append(tr2)
        d["trips"] = nt
    leftover = [n.id for n in ins.targets if n.id not in seen]
    return leftover


def _sol_fp(sol):
    """Fingerprint station types + routes so ALNS vs TSALNS plans do not collide."""
    types = tuple((sol or {}).get("station_types") or [])
    rh = hashlib.sha1(repr((sol or {}).get("routes")).encode("utf-8", "replace")).hexdigest()[:16]
    return types, rh


def repack(ins, sol, wx, margin=0.08, t0=0.0, relocate=2):
    types, rh = _sol_fp(sol)
    key = (ins.sha256, wx.seed, margin, t0, relocate, getattr(wx, "mode", "storm"), types, rh)
    if key in _CACHE:
        new, left = _CACHE[key]
        return new, list(left)
    nodes = I.node_by_id(ins)
    fixed, stations, drones = I.open_drones(ins, sol)
    # keep original trip lists (already copied by open_drones)
    fc = wx.forecast_wind(t0, t0)

    # 1. trim infeasible original trips from the tail
    leftover = []
    for d in drones:
        st = stations[d["sid"]]
        new_trips = []
        for tr in d["trips"]:
            tr = list(tr)
            while tr:
                ok, e, ttot = _can(ins, st, d, tr, wx, t0, fc, margin)
                if ok:
                    new_trips.append(tr)
                    break
                leftover.append(tr.pop())
        d["trips"] = new_trips

    # 2. re-insert leftovers, furthest-from-station first
    def nearest(tid):
        n = nodes[tid]
        return min(math.hypot(n.x - s["x"], n.y - s["y"]) for s in stations) if stations else 0.0
    leftover = [t for t in leftover if t not in _assigned(drones)]
    leftover = list(dict.fromkeys(leftover))
    leftover.sort(key=nearest, reverse=True)
    still = []
    for tid in leftover:
        if not _try_insert(ins, stations, drones, tid, wx, t0, fc, margin, nodes):
            still.append(tid)

    # also catch any original-plan misses (shouldn't happen)
    missing = [n.id for n in ins.targets if n.id not in set(_assigned(drones)) and n.id not in still]
    for tid in missing:
        if not _try_insert(ins, stations, drones, tid, wx, t0, fc, margin, nodes):
            still.append(tid)

    # 3. a couple of earliest-finish relocates
    for _pass in range(relocate):
        snapshot = list(_assigned(drones))
        moved = False
        for tid in snapshot:
            # remove
            loc = None
            for di, d in enumerate(drones):
                for ti, tr in enumerate(d["trips"]):
                    if tid in tr:
                        tr.remove(tid)
                        loc = (di, d)
                        if not tr:
                            d["trips"].pop(ti)
                        break
                if loc:
                    break
            if loc is None:
                continue
            if not _try_insert(ins, stations, drones, tid, wx, t0, fc, margin, nodes):
                # put back as own trip
                d = loc[1]
                st = stations[d["sid"]]
                ok, _, _ = _can(ins, st, d, [tid], wx, t0, fc, margin)
                if ok:
                    d["trips"].append([tid])
                else:
                    still.append(tid)
            else:
                moved = True
        still = [t for t in still if t not in _assigned(drones)]
        if not moved:
            break

    still = _strip_dups(ins, drones)
    # last chance
    still2 = []
    for tid in still:
        if not _try_insert(ins, stations, drones, tid, wx, t0, fc, margin, nodes):
            still2.append(tid)
    new = _to_sol(sol, drones, still2, margin)
    _CACHE[key] = (new, list(still2))
    return new, list(still2)
