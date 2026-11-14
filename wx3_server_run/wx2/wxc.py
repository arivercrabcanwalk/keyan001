"""WX-C: in-flight contingency under moving cells and gusts.

Actions at target completion and on a 1-min threat tick:
  0 CONTINUE, 1 SKIP_NEXT, 2 RETURN_HOME, 3 DIVERT to nearest other open station.
All methods share these four physical actions (public extension of Liu's
return-to-home-station rule).

Headroom diagnostic (dev, 20 maps × 50 days 6100-6149) must pass BEFORE any RL.
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

import math, time, heapq
import numpy as np
from . import const as C
from . import inst as I
from . import weather as W
from . import fly as F
from . import planadapt as PA
from . import sim as S

CONTINUE, SKIP, RETURN, DIVERT = 0, 1, 2, 3
U_UNFINISHED = 20.0


def _origin(st):
    return (st["x"], st["y"])


def nearest_other_station(st_list, sid, x, y, R_extra=1e18):
    best = None
    for k, s in enumerate(st_list):
        if k == sid:
            continue
        d = math.hypot(s["x"] - x, s["y"] - y)
        if d <= R_extra and (best is None or d < best[0]):
            best = (d, k)
    return best


class InFlight:
    """Execute planned trips with mid-trip decisions."""

    def __init__(self, ins, sol, wx, P=C.P_MAIN):
        self.ins = ins
        self.wx = wx
        self.P = P
        self.p = ins.params
        self.nodes = I.node_by_id(ins)
        if wx.mode == "nowind":
            self.sol = sol
        else:
            self.sol, self.unpacked = PA.repack(ins, sol, wx, margin=0.08, relocate=2)
        self.fixed, self.st, drones0 = I.open_drones(ins, self.sol)
        self.drones = []
        for d0 in drones0:
            d = dict(d0)
            d["trips"] = [list(tr) for tr in d0["trips"]]
            d["cur"] = None          # current trip node list (remaining)
            d["state"] = "idle"
            d["t"] = 0.0
            d["busy"] = 0.0
            d["energy"] = 0.0        # used on current battery
            d["planned_end"] = 0.0
            d["x"], d["y"] = self.st[d["sid"]]["x"], self.st[d["sid"]]["y"]
            d["fails"] = 0
            d["down_until"] = -1.0
            self.drones.append(d)
        self.unfinished = list(getattr(self, "unpacked", []) or [])
        self.fail_log = []
        self.ndec = 0
        self.dec_ms = []
        self.act_counts = np.zeros(4, dtype=int)

    def _pred_rest(self, d, remaining_nodes, include_return=True, t=None, use_truth=False):
        t = (d["t"] if t is None else t)
        st = self.st[d["sid"]]
        origin = (d["x"], d["y"])
        home = (st["x"], st["y"])
        stops = []
        nodes = remaining_nodes
        for nid in nodes:
            n = self.nodes[nid]
            stops.append((n.x, n.y, n.service, n.energy))
        # path: current pos -> stops -> home
        seq_pts = [origin] + [(s[0], s[1]) for s in stops] + ([home] if include_return else [])
        fc = self.wx.forecast_wind(t, t) if not use_truth else None
        nc = self.wx.nowcast_cells(t) if not use_truth else self.wx.nowcast_cells(t)
        # build wps
        wps = [(origin[0], origin[1], 0.0, 0.0)]
        clear = True
        tt = t
        for i in range(len(seq_pts) - 1):
            # service already at stops: attach at destination if it's a stop
            svc = een = 0.0
            if 0 < i + 1 <= len(stops):
                svc, een = stops[i][2], stops[i][3]
            wind = fc if fc is not None else self.wx.forecast_wind(t, tt)
            leg, cl, dur, dist = F.plan_leg(seq_pts[i], seq_pts[i + 1], tt, nc if not use_truth else [], wind)
            clear = clear and cl
            for p in leg[1:-1]:
                wps.append((p[0], p[1], 0.0, 0.0))
            wps.append((seq_pts[i + 1][0], seq_pts[i + 1][1], svc, een))
            tt += dur + svc
        if use_truth:
            res = F.integrate(wps, t, d["energy"], d["cap"], self.wx, self.p.flight_energy, truth=True)
            return res
        e, ttot, fl = F.pred_energy_time(wps, t, self.wx, self.p.flight_energy, t)
        return dict(ok=(e <= d["cap"] + 1e-9) and clear, energy=e, ttot=ttot, clear=clear, wps=wps)

    def _exec(self, d, wps, leftover_if_fail):
        res = F.integrate(wps, d["t"], d["energy"], d["cap"],
                          self.wx, self.p.flight_energy, truth=True)
        if res["ok"]:
            dur = res["t"] - d["t"]
            d["busy"] += dur
            d["t"] = res["t"]
            d["energy"] = 0.0  # swap at home assumed when trip completes at home
            d["x"], d["y"] = wps[-1][0], wps[-1][1]
            d["planned_end"] = max(d["planned_end"], d["t"])
            return True, res
        self.fail_log.append((d["t"], res.get("fail"), res.get("fail_t")))
        d["fails"] += 1
        used = max(0.0, (res.get("fail_t") or d["t"]) - d["t"])
        d["busy"] += used
        d["t"] = d["t"] + used + C.FAIL_GROUND
        d["energy"] = 0.0
        st = self.st[d["sid"]]
        d["x"], d["y"] = st["x"], st["y"]
        d["down_until"] = d["t"]
        d["cur"] = None
        self.unfinished.extend(leftover_if_fail)
        return False, res

    def _threat(self, d, remaining):
        """Threat if nowcast cell is close to current corridor or energy tight."""
        info = self._pred_rest(d, remaining)
        tight = info["energy"] > 0.85 * d["cap"]
        return (not info["clear"]) or tight, info

    def run(self, policy, record=True):
        """policy(state)->action. We process drones mostly independently
        (no urgents), in time order of their next event."""
        # launch all first trips at t=0, stepping drone-by-drone in a loop
        # Each drone executes trip-by-trip; at the start of each remaining
        # suffix (and when a threat is flagged) we query the policy.
        for d in self.drones:
            d["t"] = 0.0
            while d["trips"] or d["cur"]:
                if d["t"] > C.H + 180:
                    # dump remaining
                    if d["cur"]:
                        self.unfinished.extend(d["cur"])
                        d["cur"] = None
                    for tr in d["trips"]:
                        self.unfinished.extend(tr)
                    d["trips"] = []
                    break
                if d["cur"] is None:
                    if not d["trips"]:
                        break
                    d["cur"] = d["trips"].pop(0)
                    d["energy"] = 0.0  # fresh battery after swap at station
                    st = self.st[d["sid"]]
                    d["x"], d["y"] = st["x"], st["y"]
                remaining = list(d["cur"])
                # decision at start of (remaining) trip and conceptually mid-threat
                threat, info = self._threat(d, remaining)
                act = CONTINUE
                if policy is not None:
                    t1 = time.perf_counter() if record else 0
                    act = policy(self, d, remaining, info, threat)
                    if record:
                        self.dec_ms.append((time.perf_counter() - t1) * 1000.0)
                    self.ndec += 1
                    if 0 <= act < 4:
                        self.act_counts[act] += 1
                act = self._apply(d, remaining, info, act)
                if act == "stop":
                    break
        return self.metrics()

    def _apply(self, d, remaining, info, act):
        st = self.st[d["sid"]]
        if act == SKIP and remaining:
            self.unfinished.append(remaining.pop(0))
            d["cur"] = remaining
            if not remaining:
                # just go home empty
                act = RETURN
            else:
                return "continue"  # re-loop to decide on the reduced remaining
        if act == RETURN or (act == SKIP and not remaining):
            wps, _, _, _ = F.plan_trip((d["x"], d["y"]), [], d["t"],
                                       self.wx.nowcast_cells(d["t"]),
                                       self.wx.forecast_wind(d["t"], d["t"]))
            # plan_trip with no stops is origin-origin. Need current to home.
            fc = self.wx.forecast_wind(d["t"], d["t"])
            nc = self.wx.nowcast_cells(d["t"])
            leg, cl, dur, dist = F.plan_leg((d["x"], d["y"]), (st["x"], st["y"]), d["t"], nc, fc)
            wps = [(p[0], p[1], 0.0, 0.0) for p in leg]
            ok, res = self._exec(d, wps, remaining)
            d["cur"] = None
            self.unfinished.extend(remaining)
            d["energy"] = 0.0
            return "continue"
        if act == DIVERT:
            nxt = nearest_other_station(self.st, d["sid"], d["x"], d["y"])
            if nxt is None:
                act = RETURN
                return self._apply(d, remaining, info, RETURN)
            _, ks = nxt
            s2 = self.st[ks]
            fc = self.wx.forecast_wind(d["t"], d["t"])
            nc = self.wx.nowcast_cells(d["t"])
            # fly to s2, swap, then empty to home
            leg1, _, _, _ = F.plan_leg((d["x"], d["y"]), (s2["x"], s2["y"]), d["t"], nc, fc)
            wps = [(p[0], p[1], 0.0, 0.0) for p in leg1]
            ok, res = self._exec(d, wps, remaining)
            self.unfinished.extend(remaining)
            d["cur"] = None
            if not ok:
                return "continue"
            # deadhead home (fresh battery)
            d["energy"] = 0.0
            d["x"], d["y"] = s2["x"], s2["y"]
            leg2, _, _, _ = F.plan_leg((s2["x"], s2["y"]), (st["x"], st["y"]), d["t"],
                                       self.wx.nowcast_cells(d["t"]),
                                       self.wx.forecast_wind(d["t"], d["t"]))
            wps2 = [(p[0], p[1], 0.0, 0.0) for p in leg2]
            self._exec(d, wps2, [])
            d["energy"] = 0.0
            return "continue"
        # CONTINUE: fly the remaining trip (truth)
        stops = [(self.nodes[n].x, self.nodes[n].y, self.nodes[n].service, self.nodes[n].energy)
                 for n in remaining]
        # from current position: if at home, plan_trip; else first leg from current xy
        fc = self.wx.forecast_wind(d["t"], d["t"])
        nc = self.wx.nowcast_cells(d["t"])
        home = (st["x"], st["y"])
        # if already at home:
        if math.hypot(d["x"] - st["x"], d["y"] - st["y"]) < 5.0:
            wps, _, _, _ = F.plan_trip(home, stops, d["t"], nc, fc)
        else:
            # path from current to first stop then rest then home
            first = [(d["x"], d["y"], 0.0, 0.0)]
            wps, _, _, _ = F.plan_trip(home, stops, d["t"], nc, fc)
            # replace start
            if wps:
                wps[0] = (d["x"], d["y"], 0.0, 0.0)
        ok, res = self._exec(d, wps, remaining)
        d["cur"] = None
        return "continue"

    def metrics(self, P=None):
        P = self.P if P is None else P
        busy = sum(d["busy"] for d in self.drones)
        mk = max([d["planned_end"] for d in self.drones] + [0.0])
        cost = self.fixed + C.C_BUSY * busy
        nfail = len(self.fail_log)
        # unique unfinished target ids
        unf = len(set(self.unfinished))
        J = cost + P * nfail + U_UNFINISHED * unf
        ms = np.array(self.dec_ms, dtype=float) if self.dec_ms else np.array([0.0])
        return dict(J=float(J), cost=float(cost), mk=float(mk), busy=float(busy),
                    fails=int(nfail), p_fail=int(nfail > 0), unfinished=int(unf),
                    ndec=int(self.ndec),
                    ms_p50=float(np.percentile(ms, 50)), ms_p99=float(np.percentile(ms, 99)),
                    ms_mean=float(ms.mean()),
                    n_cont=int(self.act_counts[0]), n_skip=int(self.act_counts[1]),
                    n_ret=int(self.act_counts[2]), n_div=int(self.act_counts[3]),
                    storm=int(self.wx.storm), ncell=int(self.wx.ncell), P=float(P),
                    fixed=float(self.fixed))


# ---------- policies ----------
def make_margin(m=0.06, b_km=1.0):
    def pol(env, d, remaining, info, threat):
        cap = d["cap"] * (1.0 - m)
        # re-check corridor with buffer (plan_leg already uses 1km; b_km extra via clear flag)
        if info.get("ok") and info.get("energy", 9) <= cap and info.get("clear", False):
            return CONTINUE
        # RETURN vs DIVERT: pick predicted faster
        st = env.st[d["sid"]]
        fc = env.wx.forecast_wind(d["t"], d["t"])
        # time home
        vg = 700.0
        t_home = math.hypot(d["x"] - st["x"], d["y"] - st["y"]) / vg
        nxt = nearest_other_station(env.st, d["sid"], d["x"], d["y"])
        if nxt and nxt[0] / vg < t_home:
            return DIVERT
        return RETURN
    return pol


def make_always_continue():
    def pol(env, d, remaining, info, threat):
        return CONTINUE
    return pol


def make_oracle():
    """Clairvoyant: simulate CONTINUE vs RETURN vs DIVERT vs SKIP under truth,
    pick the lowest remaining-day J contribution (fails + unfinished + time)."""
    def pol(env, d, remaining, info, threat):
        # cheap one-step: truth-integrate each action's immediate segment +
        # assume CONTINUE for the rest (myopic clairvoyant on this trip)
        best, ba = None, CONTINUE
        for act in (CONTINUE, SKIP, RETURN, DIVERT):
            # fork drone state
            # Use truth integrate of the chosen immediate plan
            res = env._pred_rest(d, remaining if act == CONTINUE else
                                 remaining[1:] if act == SKIP and len(remaining) > 1 else [],
                                 include_return=True, t=d["t"], use_truth=True)
            # score: fail is terrible, then time, leftover
            leftover = 0
            if act == RETURN:
                leftover = len(remaining)
            elif act == SKIP:
                leftover = 1
            elif act == DIVERT:
                leftover = len(remaining)
            fail = 0 if res.get("ok") else 1
            ttot = res.get("t", d["t"] + 60) - d["t"] if "t" in res else res.get("ttot", 60)
            score = 1000 * fail + 20 * leftover + 0.5 * ttot
            if best is None or score < best:
                best, ba = score, act
        return ba
    return pol


class _SampleWx:
    """One model-consistent realization around the issued forecast / nowcast.

    Does NOT touch hidden truth gusts or unobserved cells (that would be
    clairvoyant). Wind residual ~ N(0, σ0) at issue, grows with lead via κ.
    Visible cells get a velocity jitter of σ_v.
    """
    def __init__(self, wx, t_now, rng):
        self._wx = wx
        self.t_now = t_now
        self.r0x = float(rng.normal(0.0, C.SIGMA0))
        self.r0y = float(rng.normal(0.0, C.SIGMA0))
        self.nc = list(wx.nowcast_cells(t_now) or [])
        self.dv = [(float(rng.normal(0.0, C.SIG_V)), float(rng.normal(0.0, C.SIG_V)))
                   for _ in self.nc]

    def forecast_wind(self, t_now, t_future=None):
        return self._wx.forecast_wind(t_now, t_future)

    def truth_wind(self, x, y, t):
        fx, fy = self._wx.forecast_wind(self.t_now, t)
        lead_h = max(0.0, (t - self.t_now) / 60.0)
        s = 1.0 + (C.KAPPA * lead_h) / max(C.SIGMA0, 0.2)
        return fx + self.r0x * s, fy + self.r0y * s

    def in_any_cell(self, x, y, t, buf=0.0):
        for c, (dvx, dvy) in zip(self.nc, self.dv):
            cx, cy = F.pred_cell_at(c, self.t_now, t)
            dtsec = (t - self.t_now) * 60.0
            cx = cx + dvx * dtsec
            cy = cy + dvy * dtsec
            rad = max(c.get("a", 0.0), c.get("b", 0.0)) + buf
            if math.hypot(x - cx, y - cy) <= rad:
                return True
        return False


def make_mc(M=64, eps=0.15, deadline_ms=None):
    """Generative-model Monte-Carlo lookahead: sample forecast residuals and
    nowcast velocity jitter, integrate each physical action, pick the lowest
    expected score (fail >> leftover >> time). `eps` is unused (kept for API).
    """
    def pol(env, d, remaining, info, threat):
        t0 = time.perf_counter()
        rng = np.random.default_rng(int(d["t"] * 9973 + d["sid"] * 13 + len(remaining) * 7) % (2 ** 31))
        nxt = nearest_other_station(env.st, d["sid"], d["x"], d["y"])
        plans = {}
        act_rem = [(CONTINUE, remaining)]
        if remaining and len(remaining) > 1:
            act_rem.append((SKIP, remaining[1:]))
        act_rem.append((RETURN, []))
        for act, rem in act_rem:
            plans[act] = env._pred_rest(d, rem, include_return=True, use_truth=False)
        acts = [a for a, _ in act_rem]
        if nxt is not None:
            acts.append(DIVERT)

        def leftover(act):
            if act == CONTINUE:
                return 0
            if act == SKIP:
                return 1
            return len(remaining)

        acc = {a: 0.0 for a in acts}
        n = 0
        for _m in range(M):
            if deadline_ms is not None and (time.perf_counter() - t0) * 1000.0 >= deadline_ms:
                break
            sw = _SampleWx(env.wx, d["t"], rng)
            for act in acts:
                if act == DIVERT:
                    k = nxt[1]
                    st2 = env.st[k]
                    wps = [(d["x"], d["y"], 0.0, 0.0), (st2["x"], st2["y"], 0.0, 0.0)]
                    res = F.integrate(wps, d["t"], d["energy"], d["cap"], sw,
                                      env.p.flight_energy, truth=True)
                else:
                    wps = plans[act].get("wps")
                    if not wps or len(wps) < 2:
                        # already at home / empty plan
                        res = dict(ok=True, t=d["t"] + plans[act].get("ttot", 0.0))
                    else:
                        res = F.integrate(wps, d["t"], d["energy"], d["cap"], sw,
                                          env.p.flight_energy, truth=True)
                fail = 0 if res.get("ok") else 1
                ttot = (res["t"] - d["t"]) if res.get("t") is not None else 60.0
                acc[act] += 1000.0 * fail + 20.0 * leftover(act) + 0.5 * ttot
            n += 1
        if n == 0:
            if info.get("ok", True):
                return CONTINUE
            if nxt and nxt[0] < math.hypot(d["x"] - env.st[d["sid"]]["x"], d["y"] - env.st[d["sid"]]["y"]):
                return DIVERT
            return RETURN
        return min(acts, key=lambda a: acc[a])
    return pol
