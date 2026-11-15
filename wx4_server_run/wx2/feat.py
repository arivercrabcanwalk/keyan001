"""State and per-action features for the WX-E policy network.

All features are functions of information also available to the non-RL
baselines (forecast, nowcast, station wind, alarmed requests).
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

import math
import numpy as np
from . import const as C
from .sim import LAUNCH, HOLD, SERVE0, N_ACT, N_SERVE
from . import fly as F
from . import policies as P

NG = 40   # global
NA = 10   # per action
NIN = NG + N_ACT * NA


def _clip(x, lo=-3.0, hi=3.0):
    return lo if x < lo else hi if x > hi else x


def features(sim, i, mask, cands, info):
    """Return a float32 vector of length NIN."""
    d = sim.drones[i]
    st = sim.st[d["sid"]]
    t = sim.t
    fc = sim._fc()
    nc = sim._nowcast()
    mx, my = sim.wx.truth_wind(st["x"], st["y"], t)  # station-measured wind
    g = np.zeros(NG, dtype=np.float32)
    g[0] = t / C.H
    g[1] = float(len(nc) > 0)
    g[2] = min(len(nc), 8) / 8.0
    # nearest predicted cell to this station
    ndist, neta, napp = 3.0, 2.0, 0.0
    sweep15 = sweep30 = 0.0
    for c in nc:
        dist = math.hypot(c["cx"] - st["x"], c["cy"] - st["y"]) / 10000.0
        spd = math.hypot(c["vx"], c["vy"]) + 1e-6
        # closing speed toward station
        cl = -((c["cx"] - st["x"]) * c["vx"] + (c["cy"] - st["y"]) * c["vy"]) / spd
        eta = dist * 10000.0 / (max(cl, 0.1) * 60.0) / 60.0  # hours-ish -> /60 min scale
        if dist < ndist:
            ndist, neta, napp = dist, max(-1.0, min(2.0, eta)), max(-1.0, min(1.0, cl / 15.0))
        if P._station_in_sweep(sim, d["sid"], 15.0):
            sweep15 = 1.0
        if P._station_in_sweep(sim, d["sid"], 30.0):
            sweep30 = 1.0
    g[3] = ndist
    g[4] = neta
    g[5] = napp
    g[6] = sweep15
    g[7] = sweep30
    g[8] = math.hypot(*fc) / 15.0
    g[9] = math.hypot(mx, my) / 15.0
    g[10] = (math.hypot(mx, my) - math.hypot(*fc)) / 10.0
    # requests
    pend = [sim.reqs[j] for j in sim.pending if not sim._done_flags[j]]
    nh = sum(1 for r in pend if r[3] == 1)
    nn_ = len(pend) - nh
    g[11] = min(nh, 6) / 6.0
    g[12] = min(nn_, 6) / 6.0
    if pend:
        dls = [r[0] + C.DL[r[3]] - t for r in pend]
        g[13] = _clip(min(dls) / 30.0, -2, 2)
        g[14] = _clip(np.mean(dls) / 45.0, -2, 2)
    # in-coverage pending
    cov = [r for r in pend if math.hypot(r[1] - st["x"], r[2] - st["y"]) <= d["R"]]
    g[15] = min(len(cov), 5) / 5.0
    g[16] = min(sum(1 for r in cov if r[3] == 1), 4) / 4.0
    # fleet
    g[17] = min(P._ready_others(sim, i), 4) / 4.0
    g[18] = float(d["large"])
    g[19] = float(st["kind"] == 2)
    g[20] = d["duty"] / max(d["duty_max"], 1.0)
    g[21] = d["holds"] / 10.0
    ntrips = len(d["trips"])
    g[22] = min(ntrips, 6) / 6.0
    rem_t = sum(d["q"] for d in [])  # placeholder
    if info is not None:
        g[23] = min(info["ttot"], 90) / 60.0
        g[24] = float(info["clear"])
        g[25] = min(info["energy"] / max(d["cap"], 1e-6), 1.5)
    # projected makespan slack
    ends = []
    for j, e in enumerate(sim.drones):
        extra = 0.0
        if e["state"] == "busy":
            extra = max(0.0, e["free"] - t)
        # remaining trips nominal 40 min each (rough)
        extra += 30.0 * len(e["trips"])
        ends.append(extra)
    mk_o = max([ends[j] for j in range(len(ends)) if j != i] + [0.0])
    self_e = ends[i] if i < len(ends) else 0.0
    g[26] = _clip((mk_o - self_e) / 60.0, -2, 2)
    g[27] = min(len(sim.fail_log), 8) / 8.0
    g[28] = min(len(sim.seen), 12) / 12.0
    # recent alarms in radius
    rec = 0
    for (tt, x, y, pri, j) in sim.seen:
        if t - tt <= 30.0 and math.hypot(x - st["x"], y - st["y"]) <= d["R"] + 1000:
            rec += 1 + pri
    g[29] = min(rec, 6) / 6.0
    g[30] = float(sim.wx.storm)  # NOT observable! -- do NOT use. leave 0
    g[30] = 0.0
    # fraction of targets in predicted 30-min sweep (nowcast, observable)
    if len(sim.Txy) and nc:
        hit = 0
        for xy in sim.Txy:
            for c in nc:
                for step in (0.0, 15.0, 30.0):
                    cx, cy = F.pred_cell_at(c, t, t + step)
                    if math.hypot(xy[0] - cx, xy[1] - cy) <= max(c["a"], c["b"]):
                        hit += 1
                        break
        g[31] = hit / max(len(sim.Txy), 1)
    g[32] = min(sum(1 for e in sim.drones if e["state"] == "busy"), 8) / 8.0
    g[33] = min(sum(1 for e in sim.drones if e["state"] == "hold"), 4) / 4.0
    g[34] = min(sum(len(e["trips"]) for e in sim.drones), 20) / 20.0
    # measured wind direction vs next-leg heading
    if info is not None and info.get("wps") and len(info["wps"]) >= 2:
        p0, p1 = info["wps"][0], info["wps"][1]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        nrm = math.hypot(dx, dy) + 1e-6
        vg = max(1.0, __import__("wx2.weather", fromlist=["ground_speed_mpm"]).ground_speed_mpm(mx, my, dx / nrm, dy / nrm))
        g[35] = _clip(vg / C.VA, 0, 2)
    g[36] = float(mask[LAUNCH])
    g[37] = float(mask[HOLD])
    g[38] = float(mask[SERVE0:].any())
    g[39] = min(len(cands), 3) / 3.0

    af = np.zeros((N_ACT, NA), dtype=np.float32)
    # LAUNCH
    if info is not None:
        af[LAUNCH, 0] = 1.0
        af[LAUNCH, 1] = min(info["ttot"], 90) / 60.0
        af[LAUNCH, 2] = float(info["clear"])
        af[LAUNCH, 3] = min(info["energy"] / max(d["cap"], 1e-6), 1.5)
        af[LAUNCH, 4] = g[26]
        af[LAUNCH, 5] = sweep30
    # HOLD
    af[HOLD, 0] = 1.0
    af[HOLD, 1] = g[17]  # ready others
    af[HOLD, 2] = sweep15
    af[HOLD, 3] = sweep30
    af[HOLD, 4] = g[16]  # high-pri in coverage
    af[HOLD, 5] = g[26]
    af[HOLD, 6] = g[13] if pend else 1.0
    # SERVE k
    for k, c in enumerate(cands[:N_SERVE]):
        dl, j, wps, ttot, e, clear = c[0], c[1], c[2], c[3], c[4], c[5]
        r = sim.reqs[j]
        af[SERVE0 + k, 0] = 1.0
        af[SERVE0 + k, 1] = min(ttot, 60) / 40.0
        af[SERVE0 + k, 2] = float(clear)
        af[SERVE0 + k, 3] = float(r[3])  # pri
        af[SERVE0 + k, 4] = _clip((dl - t) / 30.0, -2, 2)
        af[SERVE0 + k, 5] = min(e / max(d["cap"], 1e-6), 1.5)
        af[SERVE0 + k, 6] = float(r[4] in ("storm", "uniform"))  # kind is observable? storm vs bg is not labelled to the agent. Don't use truth kind.
        af[SERVE0 + k, 6] = 0.0
        dist = math.hypot(r[1] - st["x"], r[2] - st["y"])
        af[SERVE0 + k, 7] = min(dist / 5000.0, 2.0)
    vec = np.concatenate([g, af.reshape(-1)]).astype(np.float32)
    return vec
