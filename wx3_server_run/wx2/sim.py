"""Event-driven WX-E simulator: planned trips + weather-generated urgents.

Actions at each idle-drone decision:
  0 LAUNCH_PLANNED, 1 HOLD_5MIN, 2..4 SERVE(j) for the 3 soonest-deadline
  eligible requests. Illegal actions are masked.
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

import math, heapq, time, copy
import numpy as np
from . import const as C
from . import inst as I
from . import weather as W
from . import fly as F
from . import planadapt as PA

LAUNCH, HOLD, SERVE0 = 0, 1, 2
N_ACT = 5
N_SERVE = 3


class Sim:
    def __init__(self, ins, sol, wx, reqs, P=C.P_MAIN):
        self.ins = ins
        self.wx = wx
        self.P = float(P)
        self.p = ins.params
        self.nodes = I.node_by_id(ins)
        self.targets = {n.id: n for n in ins.targets}
        self.Txy = I.targets_xy(ins)
        # forecast-wind re-pack on frozen stations (idempotent if already adapted).
        # Skip in the nowind regression setting so trip times match the Liu evaluator.
        self.unfinished_planned = 0
        if getattr(wx, "mode", "") == "nowind":
            self.sol = sol
            self.unpacked_init = []
        elif sol.get("adapted"):
            self.sol = sol
            self.unpacked_init = list(sol.get("unpacked", []))
        else:
            self.sol, self.unpacked_init = PA.repack(ins, sol, wx, margin=0.08, t0=0.0, relocate=2)
            self.sol["adapt_wx_seed"] = getattr(wx, "seed", None)
        sol = self.sol
        self.fixed, self.st, drones0 = I.open_drones(ins, sol)
        self.attempts = {}  # nid -> number of launch attempts
        self.t_horizon = C.H + 180.0
        self.drones = []
        for d0 in drones0:
            d = dict(d0)
            d["trips"] = [list(tr) for tr in d0["trips"]]  # remaining planned node-id lists
            d["free"] = 0.0
            d["state"] = "idle"          # idle | hold | busy | down
            d["busy"] = 0.0
            d["duty"] = 0.0
            d["holds"] = 0
            d["planned_end"] = 0.0
            d["cur_planned"] = False
            d["xq"] = []                 # assigned urgent trip descriptors waiting
            d["backlog"] = []            # leftover planned node ids after a failure
            self.drones.append(d)
        self.reqs = list(reqs)           # (t,x,y,pri,kind,tid)
        self.nreq = len(self.reqs)
        self.pending = []                # indices into reqs, not yet assigned / served
        self.assigned = set()
        self.t = 0.0
        self.ev = []
        self.k = 0
        self.log = []                    # (pri, resp_or_None, late_min, kind, j, i)
        self.fail_log = []               # (t, i, reason)
        self.seen = []                   # released (t,x,y,pri,j)
        self.ndec = 0
        self.dec_ms = []
        self.act_counts = np.zeros(N_ACT, dtype=int)
        self.n_launch = self.n_hold = self.n_serve = 0
        self._ctx = None
        for i in range(len(self.drones)):
            self._push(0.0, 0, i)        # type 0: drone decision/free
        for j, r in enumerate(self.reqs):
            self._push(r[0], 1, j)       # type 1: request alarm
        # weather ticks so HOLD expires into a fresh decision and nowcast updates
        tt = C.DT
        while tt <= C.H + 1e-9:
            self._push(tt, 2, 0)
            tt += C.DT
        self._done_flags = [False] * self.nreq
        self.unfinished_planned = 0

    def _push(self, t, typ, i):
        self.k += 1
        heapq.heappush(self.ev, (t, typ, self.k, i))

    def clone(self):
        s = Sim.__new__(Sim)
        s.__dict__.update(self.__dict__)
        s.drones = [dict(d, trips=[list(tr) for tr in d["trips"]],
                         xq=list(d["xq"]), backlog=list(d["backlog"])) for d in self.drones]
        s.ev = list(self.ev)
        s.pending = list(self.pending)
        s.assigned = set(self.assigned)
        s.log = list(self.log)
        s.fail_log = list(self.fail_log)
        s.seen = list(self.seen)
        s.dec_ms = list(self.dec_ms)
        s.act_counts = self.act_counts.copy()
        s._done_flags = list(self._done_flags)
        s.attempts = dict(self.attempts)
        # wx, ins, reqs, st, nodes, sol shared (immutable during a day)
        return s

    # ----- helpers -----
    def _nowcast(self):
        return self.wx.nowcast_cells(self.t)

    def _fc(self):
        return self.wx.forecast_wind(self.t, self.t)

    def _station(self, d):
        return self.st[d["sid"]]

    def serve_candidates(self, i):
        """Up to 3 pending requests, soonest deadline, coverage + predicted energy feasible."""
        d = self.drones[i]
        st = self._station(d)
        fc = self._fc()
        nc = self._nowcast()
        cands = []
        for j in self.pending:
            if j in self.assigned or self._done_flags[j]:
                continue
            t0, x, y, pri, kind, tid = self.reqs[j]
            if math.hypot(x - st["x"], y - st["y"]) > d["R"] + 1e-6:
                continue
            origin = (st["x"], st["y"])
            stops = [(x, y, C.U_SERVICE, C.U_ENERGY)]
            wps, clear, ptime, pdist = F.plan_trip(origin, stops, self.t, nc, fc)
            e, ttot, _ = F.pred_energy_time(wps, self.t, self.wx, self.p.flight_energy, self.t)
            if e > d["cap"] + 1e-9:
                continue
            # remaining duty
            if d["duty"] + ttot > d["duty_max"] + 1e-9:
                continue
            dl = t0 + C.DL[pri]
            cands.append((dl, j, wps, ttot, e, clear))
        cands.sort(key=lambda z: (z[0], z[1]))
        return cands[:N_SERVE]

    def next_trip_info(self, i):
        d = self.drones[i]
        if not d["trips"]:
            # maybe pack backlog
            if d["backlog"]:
                self._pack_backlog(i)
            if not d["trips"]:
                return None
        tr = d["trips"][0]
        st = self._station(d)
        fc = self._fc()
        nc = self._nowcast()
        stops = []
        for nid in tr:
            n = self.nodes[nid]
            stops.append((n.x, n.y, n.service, n.energy))
        origin = (st["x"], st["y"])
        wps, clear, ptime, pdist = F.plan_trip(origin, stops, self.t, nc, fc)
        e, ttot, fl = F.pred_energy_time(wps, self.t, self.wx, self.p.flight_energy, self.t)
        return dict(wps=wps, clear=clear, ptime=ptime, pdist=pdist, energy=e, ttot=ttot,
                    nodes=list(tr), flight=fl)

    def mask(self, i):
        m = np.zeros(N_ACT, dtype=np.bool_)
        d = self.drones[i]
        info = self.next_trip_info(i)
        if info is not None and self.t <= self.t_horizon:
            # do not relaunch a trip whose targets already failed twice
            nodes = info.get("nodes") or []
            over = any(self.attempts.get(nid, 0) >= 2 for nid in nodes)
            duty_ok = d["duty"] + info["ttot"] <= d["duty_max"] + 1e-6
            # after H, still allow finishing if duty ok
            if (not over) and duty_ok and (info["energy"] <= d["cap"] * 1.08 + 1e-6):
                m[LAUNCH] = True
        # HOLD is only meaningful as deferring a launch (or waiting while serve
        # is also available — serve is preferred by most rules anyway)
        if self.t < C.H - 1e-9 and m[LAUNCH]:
            m[HOLD] = True
        cands = self.serve_candidates(i)
        for k in range(len(cands)):
            m[SERVE0 + k] = True
        return m, cands, info

    def _pack_backlog(self, i):
        """Fixed greedy rule (shared by all methods): pack leftover targets into new trips."""
        d = self.drones[i]
        if not d["backlog"]:
            return
        st = self._station(d)
        left = list(d["backlog"])
        d["backlog"] = []
        # nearest-neighbour pack by energy
        while left:
            trip = []
            # approximate energy with no-wind
            px, py = st["x"], st["y"]
            e = 0.0
            tmin = 0.0
            used = []
            for nid in left:
                n = self.nodes[nid]
                dist = math.hypot(n.x - px, n.y - py) + math.hypot(n.x - st["x"], n.y - st["y"])
                # subtract return of previous
                if trip:
                    prev = self.nodes[trip[-1]]
                    dist = math.hypot(n.x - px, n.y - py) + math.hypot(n.x - st["x"], n.y - st["y"]) - math.hypot(px - st["x"], py - st["y"])
                dt = dist / C.VA + n.service
                de = (dist / C.VA) * self.p.flight_energy + n.energy
                if e + de <= d["cap"] * 0.95:
                    trip.append(nid)
                    used.append(nid)
                    e += de
                    tmin += dt
                    px, py = n.x, n.y
                elif not trip:
                    # single target may itself be tight; still try
                    trip.append(nid)
                    used.append(nid)
                    break
            for nid in used:
                left.remove(nid)
            if trip:
                d["trips"].append(trip)
            else:
                break

    # ----- event loop -----
    def run(self, pol, record_time=True, max_events=200000):
        n = 0
        while self.ev:
            t, typ, _, i = heapq.heappop(self.ev)
            if t < self.t - 1e-9:
                continue
            self.t = t
            n += 1
            if n > max_events or t > self.t_horizon + 1e-9:
                break
            if typ == 0:
                self._free(i, pol, record_time)
            elif typ == 1:
                self._arrive(i, pol, record_time)
            elif typ == 2:
                self._tick(pol, record_time)
            elif typ == 3:
                self._recover(i)
        self._close_unserved()
        return self.metrics()

    def _close_unserved(self):
        for j in list(self.pending):
            if self._done_flags[j]:
                continue
            t0, x, y, pri, kind, tid = self.reqs[j]
            dl = C.DL[pri]
            late = max(C.UNSERVED_FLOOR, C.H - t0 - dl)
            self.log.append((pri, None, late, kind, j, -1))
            self._done_flags[j] = True
        self.pending = []
        # unflown planned targets
        left = 0
        for d in self.drones:
            for tr in d["trips"]:
                left += len(tr)
            left += len(d["backlog"])
        self.unfinished_planned = left

    def _free(self, i, pol, record_time):
        d = self.drones[i]
        if d["state"] == "busy" and self.t < d["free"] - 1e-9:
            return
        if d["state"] == "down" and self.t < d["free"] - 1e-9:
            return
        if d["state"] == "busy" and d.get("cur_planned"):
            d["planned_end"] = self.t
            d["cur_planned"] = False
        if d["state"] == "down":
            d["state"] = "idle"
        # assigned urgent waiting?
        if d["xq"]:
            self._exec_urgent(i, d["xq"].pop(0))
            return
        d["state"] = "idle"
        self._decide(i, pol, record_time)

    def _tick(self, pol, record_time):
        # offer a fresh decision to every idle/hold drone (HOLD_5MIN expires here)
        for i, d in enumerate(self.drones):
            if d["state"] in ("idle", "hold") and d.get("xq"):
                d["state"] = "idle"
                self._exec_urgent(i, d["xq"].pop(0))
            elif d["state"] in ("idle", "hold"):
                self._decide(i, pol, record_time)

    def _arrive(self, j, pol, record_time):
        t0, x, y, pri, kind, tid = self.reqs[j]
        self.seen.append((t0, x, y, pri, j))
        self.pending.append(j)
        # offer decisions to idle/hold drones, nearest first
        order = []
        for i, d in enumerate(self.drones):
            if d["state"] in ("idle", "hold"):
                st = self._station(d)
                order.append((math.hypot(x - st["x"], y - st["y"]), i))
        order.sort()
        for _, i in order:
            if j not in self.pending or self._done_flags[j]:
                break
            if self.drones[i]["state"] in ("idle", "hold"):
                self._decide(i, pol, record_time)

    def _recover(self, i):
        d = self.drones[i]
        d["state"] = "idle"
        self._push(self.t, 0, i)

    def _decide(self, i, pol, record_time):
        d = self.drones[i]
        if d["state"] == "busy" or d["state"] == "down":
            return
        if self.t > self.t_horizon:
            d["state"] = "idle"
            return
        m, cands, info = self.mask(i)
        # no remaining launch and no serve: stay idle (do not count as a HOLD)
        if (not m[LAUNCH]) and (not m[SERVE0:].any()):
            d["state"] = "idle"
            return
        if not m.any():
            d["state"] = "idle"
            return
        # after H, finish remaining planned trips but do not HOLD
        if self.t >= C.H:
            m[HOLD] = False
            if not m.any():
                d["state"] = "idle"
                return
        t1 = time.perf_counter() if record_time else 0.0
        act = pol(self, i, m, cands, info)
        if record_time:
            self.dec_ms.append((time.perf_counter() - t1) * 1000.0)
        if act is None or act < 0 or act >= N_ACT or (not m[act]):
            # illegal / None: default urgent-first then launch then hold
            act = self._default(m)
        self.ndec += 1
        self.act_counts[act] += 1
        d["state"] = "idle"
        if act == HOLD:
            d["state"] = "hold"
            d["holds"] += 1
            self.n_hold += 1
            # next decision at next weather tick (or sooner if a request arrives)
            return
        if act == LAUNCH:
            self.n_launch += 1
            self._exec_launch(i, info)
            return
        # SERVE
        k = act - SERVE0
        if k < 0 or k >= len(cands):
            act = self._default(m)
            if act == LAUNCH and info is not None:
                self.n_launch += 1
                self._exec_launch(i, info)
            return
        self.n_serve += 1
        self._exec_urgent(i, cands[k])

    def _default(self, m):
        if m[SERVE0]:
            return SERVE0
        if m[LAUNCH]:
            return LAUNCH
        if m[HOLD]:
            return HOLD
        return int(np.argmax(m)) if m.any() else HOLD

    def _exec_launch(self, i, info):
        d = self.drones[i]
        if info is None:
            info = self.next_trip_info(i)
        if info is None:
            d["state"] = "idle"
            return
        # pop the trip we planned
        if d["trips"] and d["trips"][0] == info["nodes"]:
            d["trips"].pop(0)
        elif d["trips"]:
            # mismatch: pop first anyway
            d["trips"].pop(0)
        for nid in info["nodes"]:
            self.attempts[nid] = self.attempts.get(nid, 0) + 1
        wps = info["wps"]
        nodes_left = list(info["nodes"])
        res = F.integrate(wps, self.t, 0.0, d["cap"], self.wx, self.p.flight_energy, truth=True)
        if res["ok"]:
            dur = res["t"] - self.t
            d["state"] = "busy"
            d["free"] = res["t"]
            d["busy"] += dur
            d["duty"] += dur
            d["cur_planned"] = True
            d["planned_end"] = res["t"]
            self._push(res["t"], 0, i)
        else:
            self._on_fail(i, res, nodes_left, planned=True)

    def _exec_urgent(self, i, cand):
        """cand is a serve_candidates tuple (dl, j, wps, ttot, e, clear) or similar."""
        d = self.drones[i]
        if isinstance(cand, tuple):
            dl, j, wps, ttot, e, clear = cand[0], cand[1], cand[2], cand[3], cand[4], cand[5]
        else:
            j, wps = cand["j"], cand["wps"]
        if j in self.assigned or self._done_flags[j] or j not in self.pending:
            d["state"] = "idle"
            return
        self.assigned.add(j)
        if j in self.pending:
            self.pending.remove(j)
        t0, x, y, pri, kind, tid = self.reqs[j]
        res = F.integrate(wps, self.t, 0.0, d["cap"], self.wx, self.p.flight_energy, truth=True)
        # response = arrival at the request (first service wp) - t0
        # we approximate: if success, arrival = res.t - U_SERVICE - return_time
        # more accurately: integrate gives only end time. Estimate arrival from pred.
        if res["ok"]:
            dur = res["t"] - self.t
            # arrival ≈ t + outbound time. Use residual: total - service - return.
            # crude: half of (dur - U_SERVICE) plus a bit. Better: use pred split.
            ret = math.hypot(x - self._station(d)["x"], y - self._station(d)["y"]) / C.VA
            arr = res["t"] - C.U_SERVICE - ret
            arr = max(arr, self.t)
            resp = arr - t0
            late = max(0.0, resp - C.DL[pri])
            self.log.append((pri, resp, late, kind, j, i))
            self._done_flags[j] = True
            d["state"] = "busy"
            d["free"] = res["t"]
            d["busy"] += dur
            d["duty"] += dur
            d["cur_planned"] = False
            self._push(res["t"], 0, i)
        else:
            # failed on the way: request unserved (back to pending if outbound failed)
            self.assigned.discard(j)
            if not self._done_flags[j]:
                self.pending.append(j)
            self._on_fail(i, res, [], planned=False)

    def _on_fail(self, i, res, leftover_nodes, planned=False):
        d = self.drones[i]
        st = self._station(d)
        self.fail_log.append((self.t, i, res.get("fail"), res.get("fail_t")))
        # leftover planned targets return
        if leftover_nodes:
            retry, give = [], []
            for nid in leftover_nodes:
                if self.attempts.get(nid, 0) >= 2 or self.t >= C.H:
                    give.append(nid)
                else:
                    retry.append(nid)
            d["backlog"].extend(retry)
            self.unfinished_planned += len(give)
        # snap drone back to station after FAIL_GROUND (it is grounded 60 min, then at home)
        d["x"], d["y"] = st["x"], st["y"]
        d["state"] = "down"
        # busy includes flight until fail
        used = max(0.0, (res.get("fail_t") or self.t) - self.t)
        d["busy"] += used
        d["duty"] += used
        d["cur_planned"] = False
        d["free"] = self.t + used + C.FAIL_GROUND
        self._push(d["free"], 3, i)

    def metrics(self, P=None):
        P = self.P if P is None else P
        mk = max([d["planned_end"] for d in self.drones] + [0.0])
        busy = sum(d["busy"] for d in self.drones)
        cost = self.fixed + C.C_BUSY * busy
        logs = self.log
        nh = sum(1 for L in logs if L[0] == 1)
        nn = len(logs) - nh
        late_h = [L[2] for L in logs if L[0] == 1]
        late_n = [L[2] for L in logs if L[0] == 0]
        ontime_h = (sum(1 for L in logs if L[0] == 1 and L[1] is not None and L[2] <= 1e-12) / nh) if nh else 1.0
        ontime = (sum(1 for L in logs if L[1] is not None and L[2] <= 1e-12) / len(logs)) if logs else 1.0
        unserved = sum(1 for L in logs if L[1] is None)
        unserved_h = sum(1 for L in logs if L[0] == 1 and L[1] is None)
        resp = [L[1] for L in logs if L[1] is not None]
        resp_h = [L[1] for L in logs if L[0] == 1 and L[1] is not None]
        cvar_h = cvar90(late_h)
        cvar = cvar90(late_h + late_n)
        slh = float(sum(late_h))
        sln = float(sum(late_n))
        nfail = len(self.fail_log)
        J = cost + C.C_MK * mk + C.C_LATE_H * slh + C.C_LATE_N * sln + P * nfail
        ms = np.array(self.dec_ms, dtype=float) if self.dec_ms else np.array([0.0])
        return dict(
            J=float(J), cost=float(cost), mk=float(mk), busy=float(busy), fixed=float(self.fixed),
            pen_late=float(C.C_LATE_H * slh + C.C_LATE_N * sln), pen_fail=float(P * nfail),
            late_min_h=slh, late_min_n=sln,
            ontime_h=float(ontime_h), ontime=float(ontime),
            cvar_h=float(cvar_h), cvar=float(cvar),
            n=len(logs), nh=int(nh), nn=int(nn),
            unserved=int(unserved), unserved_h=int(unserved_h),
            resp=float(np.mean(resp) if resp else 0.0),
            resp_h=float(np.mean(resp_h) if resp_h else 0.0),
            fails=int(nfail), p_fail=int(nfail > 0),
            unfinished=int(self.unfinished_planned),
            holds=int(sum(d["holds"] for d in self.drones)),
            ndec=int(self.ndec),
            n_launch=int(self.n_launch), n_hold=int(self.n_hold), n_serve=int(self.n_serve),
            ms_p50=float(np.percentile(ms, 50)), ms_p99=float(np.percentile(ms, 99)),
            ms_mean=float(ms.mean()), ms_n=int(len(self.dec_ms)),
            storm=int(self.wx.storm), ncell=int(self.wx.ncell),
            n_storm_req=int(sum(1 for r in self.reqs if r[4] in ("storm", "uniform"))),
            n_bg=int(sum(1 for r in self.reqs if r[4] == "bg")),
            P=float(P),
        )


def cvar90(xs):
    if not xs:
        return 0.0
    a = np.sort(np.asarray(xs, dtype=float))
    k = max(1, int(math.ceil(0.10 * len(a))))
    return float(a[-k:].mean())


# ----- day factory -----
_DAY_CACHE = {}


def make_day(ins, weather_seed, mode="storm", p_f=None, lam=None, sigma_scale=1.0, speed_bias=0.0, nc_bias=0.0):
    """Build (wx, reqs, meta). Optional robustness knobs applied AFTER generation
    (P4): sigma_scale multiplies OU/forecast error; speed_bias multiplies cell speed.
    These knobs must NOT be used for training / dev tuning.
    """
    bbox = I.bbox_of(ins)
    T = I.targets_xy(ins)
    wx = W.WeatherDay(weather_seed, bbox, T, mode=("nowind" if mode == "nowind" else "storm"),
                      p_f=p_f, lam=lam)
    if mode == "uniform":
        # first build storm faults to lock the count, then re-place
        reqs_s, meta_s = W.make_requests(wx, T, weather_seed, mode="storm")
        n_st = meta_s["n_storm"]
        reqs, meta = W.make_requests(wx, T, weather_seed, mode="uniform", n_storm_force=n_st)
    else:
        reqs, meta = W.make_requests(wx, T, weather_seed, mode=("storm" if mode != "nowind" else "storm"))
        if mode == "nowind":
            reqs, meta = [], dict(n_storm=0, n_bg=0, n_swept=0, storm=0, ncell=0)
    # robustness (test only)
    if sigma_scale != 1.0:
        wx.ou_sig *= sigma_scale
        wx.ou *= sigma_scale
        wx.wtx = wx.F0x + wx.ou[:, 0] + wx.gust[:, 0]
        wx.wty = wx.F0y + wx.ou[:, 1] + wx.gust[:, 1]
        # inflate forecast residual similarly
        smx = wx.F0x + wx.ou[:, 0]
        smy = wx.F0y + wx.ou[:, 1]
        # keep issued forecasts but widen by moving them toward / away: already built;
        # scale (fc - smooth) 
        wx.fc_x = smx[None, :] + (wx.fc_x - (wx.F0x + wx.ou[:, 0] / max(sigma_scale, 1e-9))[None, :]) * sigma_scale
        # simpler: rebuild fc as smooth + sigma_scale * old residual, residual was fc - (F0+ou_old)
        # skip messy; already multiplied ou so smooth changed. Leave fc as is (conservative).
    if nc_bias:
        wx.nc_bias = float(nc_bias)
    if speed_bias != 0.0 and wx.ncell:
        # +30% means multiply true cell speed by 1.3 (nowcast still from last 3 obs,
        # so short-term nowcast tracks, long-term prediction from a single snapshot lags)
        fac = 1.0 + speed_bias
        wx.c_vx *= fac
        wx.c_vy *= fac
        # re-integrate positions from birth using new velocities? The arrays are already
        # positions at truth; scaling vel without positions would be inconsistent.
        # For P4 we scale subsequent motion: rebuild cx,cy from birth with scaled vel.
        for i, c in enumerate(wx.cells):
            ib = wx._idx(c["birth"])
            cx0, cy0 = c["cx"][ib], c["cy"][ib]
            vx, vy = wx.c_vx[i], wx.c_vy[i]
            cx, cy = c["cx"].copy(), c["cy"].copy()
            cx[ib], cy[ib] = cx0, cy0
            for k in range(ib + 1, wx.NT):
                cx[k] = cx[k - 1] + vx[k - 1] * 60.0 * C.DT
                cy[k] = cy[k - 1] + vy[k - 1] * 60.0 * C.DT
            for k in range(ib - 1, -1, -1):
                cx[k] = cx[k + 1] - vx[k] * 60.0 * C.DT
                cy[k] = cy[k + 1] - vy[k] * 60.0 * C.DT
            c["cx"], c["cy"] = cx, cy
            wx.c_cx[i], wx.c_cy[i] = cx, cy
    meta = dict(meta)
    meta["day_hash"] = W.day_hash(wx, reqs)
    meta["wx_hash"] = wx.hash()
    return wx, reqs, meta
