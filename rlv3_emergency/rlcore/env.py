"""Finite-day node-decision simulator: no skip, rescue, or completion guarantee.

Requests release independently of routes. Flight and service are non-preemptive;
all aircraft advance on one public clock. Energy and cumulative operating duty
are hard constraints. Failed missions retain their original denominators.
"""
import math
import heapq
import numpy as np
from . import phys
from .common import P1, P2, TIME_COST, VA_MS
from .weather import nowcast_hits

DT_FLY = 0.5
RTH_RES = 0.0
WAIT_STEP = 10.0
T_DAY = 600.0
T_HARD = T_DAY
T_ABORT = T_DAY
C_OT = 1.0
C_INC = 200.0
C_UNSERVED = 1000.0
C_FAIL = 1000.0
K_MAX = None                   # dynamic attention/collation; no candidate truncation
ACT_RETURN, ACT_WAIT = -1, -2


class Env:
    def __init__(self, layout, wx=None, requests=None, margin=None, use_cells=True,
                 wind_limit=True, urgent_w=None, record=False):
        self.L, self.wx = layout, wx
        self.calm = wx is None or getattr(wx, "calm", False)
        self.author_simple = self.calm or getattr(wx, "energy_model", None) == "author_simple"
        self.margin = 0.0 if margin is None else float(margin)
        if not math.isfinite(self.margin) or self.margin < 0:
            raise ValueError("invalid nonnegative energy margin")
        self.use_cells = bool(use_cells and wx is not None and getattr(wx, "ncell", 0))
        self.wind_limit = bool(wind_limit and not self.calm)
        self.record, self.trace, self.event_trace = record, [], []
        self.st = layout["stations"]
        if [s["k"] for s in self.st] != list(range(len(self.st))):
            raise ValueError("station indices must be contiguous")
        if [d["i"] for d in layout["drones"]] != list(range(len(layout["drones"]))):
            raise ValueError("drone indices must be contiguous")
        if set(layout["assign"]) != set(layout["targets"]):
            raise ValueError("every routine target must have exactly one fixed assignment")
        self.tasks = []
        for tid, k in sorted(layout["assign"].items()):
            x, y, svc, en = layout["targets"][tid]
            self.tasks.append(dict(j=len(self.tasks), tid=tid, x=x, y=y, svc=svc,
                en=en, urgent=0, st=k, elig=(k,), rel=0.0, dl=None, prio=0,
                w=0.0, done=False, claim=-1, t_arrival=None, t_done=None))
        self.n_planned = len(self.tasks)
        from .urgent import W_LATE
        self.W_LATE = W_LATE if urgent_w is None else urgent_w
        self.requests = sorted(requests or [], key=lambda r: (r["t"], r["rid"]))
        if len({r["rid"] for r in self.requests}) != len(self.requests):
            raise ValueError("request ids must be unique")
        for r in self.requests:
            if (not all(math.isfinite(float(r[z])) for z in ("x", "y", "t", "dl", "svc", "energy"))
                    or not 0 <= r["t"] <= T_DAY or r["dl"] < r["t"]
                    or r["svc"] <= 0 or r["energy"] < 0 or r["prio"] not in (0, 1)):
                raise ValueError("unsupported request: finite day/time/service/priority required")
            self.tasks.append(self._req_task(r))
        self.n_unserviceable = sum(x["urgent"] and not x["elig"] for x in self.tasks)
        self.req_gen = None
        self.rank = {}
        for d in layout["drones"]:
            seq = [tid for tr in d["trips"] for tid in tr]
            for r, tid in enumerate(seq):
                self.rank[tid] = (d["i"], r, len(seq))
        self.tid2j = {x["tid"]: x["j"] for x in self.tasks if not x["urgent"]}
        self.dr = []
        for d in layout["drones"]:
            s = self.st[d["st"]]
            self.dr.append(dict(i=d["i"], st=d["st"], di=d["di"], cap=d["cap"],
                limit=d["limit"], x=s["x"], y=s["y"], at_st=True, node=-1,
                e=0.0, t=0.0, busy=0.0, flight=0.0, hover=0.0, dist=0.0,
                launches=0, aborts=0, inc_cell=0, inc_land=0, retired=False,
                t_last=0.0, ntrip=0, mode="idle", failed=False, last_return=0.0,
                target=None, service_left=0.0, slp=False, failure_reason=None))
        self.heap = [(0.0, d["i"]) for d in self.dr]
        heapq.heapify(self.heap)
        self.t, self.cur, self.done, self.n_dec = 0.0, None, False, 0
        self.fallback, self.timeout = False, False
        self.termination_reason = None
        self._release_seen = set()

    def _req_task(self, r):
        elig = tuple(s["k"] for s in self.st if math.hypot(s["x"]-r["x"], s["y"]-r["y"]) <= s["R"]+1e-7)
        return dict(j=len(self.tasks), tid=r["tid"], x=r["x"], y=r["y"],
            svc=r["svc"], en=r["energy"], urgent=1, st=-1, elig=elig,
            rel=r["t"], dl=r["dl"], prio=r["prio"], w=self.W_LATE[r["prio"]],
            done=False, claim=-1, t_arrival=None, t_done=None, rid=r["rid"])

    def resample_future(self, seed):
        """Simulator-state conditional redraw; not a public-history belief sampler."""
        if self.wx is not None and not self.calm:
            self.wx = self.wx.resample_future(self.t, seed)
        if self.req_gen is None:
            return
        from .urgent import make_requests
        targets, level, pattern = self.req_gen
        self.tasks = [x for x in self.tasks if not x["urgent"] or x["rel"] <= self.t+1e-9]
        next_rid = max((x["rid"] for x in self.tasks if x["urgent"]), default=-1)+1
        for r in make_requests(10**9+int(seed), targets, level, pattern=pattern):
            if r["t"] > self.t+1e-9:
                r = dict(r, rid=next_rid)
                next_rid += 1
                self.tasks.append(self._req_task(r))
        self.n_unserviceable = sum(x["urgent"] and not x["elig"] for x in self.tasks)

    def _released(self, t):
        return [x for x in self.tasks if x["urgent"] and x["rel"] <= t+1e-9]

    def _fc(self, t):
        return (0.0, 0.0) if self.calm else self.wx.forecast_wind(self.t, t)

    def leg_pred(self, x1, y1, x2, y2, t0):
        if self.calm:
            tm = math.hypot(x2-x1, y2-y1)/(VA_MS*60)
            return P1*tm, tm, True
        return phys.leg_cost(x1, y1, x2, y2, *self._fc(t0))

    def hover_pred(self, t0, svc):
        return P2*svc if self.calm else phys.p_hover(math.hypot(*self._fc(t0)))*svc

    def unfinished(self):
        return [x for x in self.tasks if not x["done"]]

    def avail_tasks(self, d):
        return [x for x in self.tasks if not x["done"] and x["claim"] < 0
            and x.get("free_at", 0.0) <= self.t+1e-9 and x["rel"] <= self.t+1e-9
            and d["st"] in x["elig"]]

    def task_check(self, d, x):
        s = self.st[d["st"]]
        e1, t1, ok1 = self.leg_pred(d["x"], d["y"], x["x"], x["y"], self.t)
        inf = dict(e1=e1, t1=t1, h=float("inf"), e2=float("inf"),
                   t2=float("inf"), need=float("inf"), cell=False, duty=float("inf"))
        if not ok1 or not math.isfinite(t1) or self.t+t1+x["svc"] > T_DAY+1e-9:
            return False, inf
        h = x["en"] if self.author_simple else self.hover_pred(self.t+t1, x["svc"])
        e2, t2, ok2 = self.leg_pred(x["x"], x["y"], s["x"], s["y"], self.t+t1+x["svc"])
        need, duty = e1+h+e2, t1+x["svc"]+t2
        feas = (ok2 and math.isfinite(duty) and not d["failed"]
            and need*(1+self.margin) <= d["cap"]-d["e"]+1e-9
            and d["busy"]+duty <= d["limit"]+1e-9 and self.t+duty <= T_DAY+1e-9)
        cell = False
        if feas and self.use_cells:
            nc = self._nc()
            cell = (nowcast_hits(nc, d["x"], d["y"], x["x"], x["y"], self.t, t1)
                or nowcast_hits(nc, x["x"], x["y"], x["x"], x["y"], self.t+t1, x["svc"])
                or nowcast_hits(nc, x["x"], x["y"], s["x"], s["y"], self.t+t1+x["svc"], t2))
            feas = not cell
        if feas and self.wind_limit:
            feas = all(math.hypot(*self._fc(tt)) <= phys.W_LIMIT for tt in
                       (self.t, self.t+t1, self.t+t1+x["svc"], self.t+duty))
        inf.update(h=h, e2=e2, t2=t2, need=need, cell=cell, duty=duty)
        return bool(feas), inf

    def _nc(self):
        if getattr(self, "_nc_key", None) != self.t:
            self._nc_key, self._nc_val = self.t, self.wx.nowcast(self.t) if self.use_cells else []
        return self._nc_val

    def _return_check(self, d):
        if d["at_st"] or d["failed"]:
            return False
        s = self.st[d["st"]]
        e, tm, ok = self.leg_pred(d["x"], d["y"], s["x"], s["y"], self.t)
        if (not ok or not math.isfinite(tm) or e > d["cap"]-d["e"]+1e-9
                or d["busy"]+tm > d["limit"]+1e-9 or self.t+tm > T_DAY+1e-9):
            return False
        if self.wind_limit and any(math.hypot(*self._fc(tt)) > phys.W_LIMIT
                                   for tt in (self.t, self.t+tm)):
            return False
        return not (self.use_cells and nowcast_hits(self._nc(), d["x"], d["y"],
                            s["x"], s["y"], self.t, tm))

    def _queue(self, d, t):
        d["retired"] = False
        heapq.heappush(self.heap, (t, d["i"]))

    def _fail(self, d, reason):
        d.update(failed=True, failure_reason=reason, mode="failed", retired=True)
        if d["target"] is not None:
            x = self.tasks[d["target"]]
            if not x["done"]:
                x["claim"], x["free_at"] = -1, d["t"]
                d["aborts"] += 1
        if reason == "energy":
            d["inc_land"] += 1
        if self.record:
            self.event_trace.append((d["t"], "failure", d["i"], reason))

    def _motion(self, d):
        s = self.st[d["st"]]
        x2, y2 = (s["x"], s["y"]) if d["mode"] == "return" else (self.tasks[d["target"]]["x"], self.tasks[d["target"]]["y"])
        dist = math.hypot(x2-d["x"], y2-d["y"])
        if self.calm or dist <= 1e-9:
            vg = VA_MS*60
        else:
            wx, wy = self.wx.truth_wind(d["x"], d["y"], d["t"])
            vg = phys.ground_speed(wx, wy, (x2-d["x"])/dist, (y2-d["y"])/dist)*60
        return x2, y2, dist, vg

    def _next_active_event(self, d):
        if d["mode"] == "service":
            return d["t"]+min(DT_FLY, d["service_left"])
        if d["mode"] in ("fly", "return"):
            _, _, dist, vg = self._motion(d)
            return d["t"]+min(DT_FLY, dist/vg) if vg > 0 else d["t"]
        return float("inf")

    def _advance_active(self, t):
        for d in self.dr:
            if d["mode"] not in ("fly", "return", "service"):
                continue
            dt, mode = t-d["t"], d["mode"]
            if dt < -1e-9:
                raise RuntimeError("event clock moved backwards")
            x0, y0, t0 = d["x"], d["y"], d["t"]
            wx, wy = (0.0, 0.0) if self.calm else self.wx.truth_wind(x0, y0, t0)
            if not self.calm and math.hypot(wx, wy) > phys.W_LIMIT+1e-9:
                self._fail(d, "truth_wind_limit"); continue
            if mode == "service":
                x = self.tasks[d["target"]]
                power = x["en"]/x["svc"] if self.author_simple else phys.p_hover(math.hypot(wx, wy))
                x2, y2, dist, vg = x0, y0, 0.0, 0.0
            else:
                x2, y2, dist, vg = self._motion(d)
                power = P1 if self.calm else phys.P_CRUISE
                if dist > 1e-9 and vg < phys.VG_MIN*60-1e-9:
                    self._fail(d, "truth_heading_limit"); continue
            permitted = min(dt, max(0.0, d["limit"]-d["busy"]),
                            max(0.0, (d["cap"]-d["e"])/power) if power > 0 else dt)
            frac = 0.0 if dist <= 1e-9 else min(1.0, vg*permitted/dist)
            xn, yn = x0+(x2-x0)*frac, y0+(y2-y0)*frac
            if mode == "service":
                xn, yn = x0, y0
            d["e"] += power*permitted
            d["t"] += permitted
            d["busy"] += permitted
            d["x"], d["y"] = xn, yn
            if mode == "service":
                d["hover"] += permitted; d["service_left"] -= permitted
            else:
                d["flight"] += permitted; d["dist"] += dist*frac
            if self.wx is not None and getattr(self.wx, "ncell", 0) and self.wx.truth_segment_hits(x0, y0, xn, yn, t0, permitted):
                d["inc_cell"] += 1; self._fail(d, "storm_intersection"); continue
            if permitted < dt-1e-9:
                self._fail(d, "energy" if d["cap"]-d["e"] <= 1e-8 else "duty"); continue
            if mode == "service" and d["service_left"] <= 1e-9:
                x = self.tasks[d["target"]]
                x["done"], x["t_done"] = True, t
                d["node"], d["mode"] = x["j"], "idle"
                self._queue(d, t)
                if self.record: self.event_trace.append((t, "service_done", d["i"], x["j"]))
            elif mode in ("fly", "return") and math.hypot(x2-d["x"], y2-d["y"]) <= 1e-7:
                d["x"], d["y"] = x2, y2
                if mode == "return":
                    d.update(mode="idle", at_st=True, node=-1, e=0.0, target=None, last_return=t)
                    self._queue(d, t)
                    if self.record: self.event_trace.append((t, "returned", d["i"], None))
                else:
                    x = self.tasks[d["target"]]
                    x["t_arrival"] = t
                    d.update(mode="service", service_left=x["svc"])
                    if self.record: self.event_trace.append((t, "arrival", d["i"], x["j"]))

    def _publish(self):
        fresh = [x for x in self._released(self.t) if x["rid"] not in self._release_seen]
        for x in fresh:
            self._release_seen.add(x["rid"])
            if self.record: self.event_trace.append((self.t, "release", None, x["rid"]))
        if fresh:
            active_ids = {i for t, i in self.heap if t <= self.t+1e-9}
            for d in self.dr:
                if d["mode"] == "idle" and d["at_st"] and d["i"] not in active_ids:
                    self.heap = [(tt, i) for tt, i in self.heap if i != d["i"]]
                    self._queue(d, self.t)
            heapq.heapify(self.heap)

    def next_decision(self):
        """Return a decision at a node; committed transit/service exposes no future state."""
        if self.cur is not None:
            raise RuntimeError("step the current decision first")
        while not self.done:
            self._publish()
            if self.heap and self.heap[0][0] <= self.t+1e-9:
                _, i = heapq.heappop(self.heap)
                d = self.dr[i]
                if d["mode"] != "idle" or d["failed"]:
                    continue
                d["t"] = self.t
                av = self.avail_tasks(d)
                av.sort(key=lambda x: (not x["urgent"], x["dl"] or float("inf"),
                    (x["x"]-d["x"])**2+(x["y"]-d["y"])**2, x["j"]))
                checked = [self.task_check(d, x) for x in av]
                feas = [a for a, b in checked]; infos = [b for a, b in checked]
                can_return = self._return_check(d)
                if not any(feas):
                    if not d["at_st"]:
                        if can_return:
                            self._apply(d, ACT_RETURN, None)
                        else:
                            self._fail(d, "no_feasible_return")
                    else:
                        d["retired"] = True
                        if (not self.calm and av) or any(o["mode"] in ("fly", "return", "service") for o in self.dr):
                            if self.t < T_DAY-1e-9:
                                self._queue(d, min(self.t+WAIT_STEP, T_DAY))
                    continue
                self.cur = (d, av, feas, infos, can_return, d["at_st"])
                return self.cur
            future = [x["rel"] for x in self.tasks if x["urgent"] and x["rel"] > self.t+1e-9]
            times = [self._next_active_event(d) for d in self.dr]
            if self.heap: times.append(self.heap[0][0])
            if future: times.append(min(future))
            nxt = min(times, default=float("inf"))
            horizon = min(T_DAY, getattr(self.wx, "horizon", T_DAY))
            if not math.isfinite(nxt) or self.t >= horizon-1e-9:
                self.done = True
                self.timeout = bool(self.unfinished() or any(not d["at_st"] for d in self.dr))
                self.termination_reason = "day_horizon" if self.t >= horizon-1e-9 else ("no_feasible_continuation" if self.unfinished() else "completed")
                return None
            nxt = min(nxt, horizon)
            if nxt < self.t-1e-9:
                raise RuntimeError("invalid event ordering")
            self._advance_active(nxt)
            self.t = nxt
        return None

    def step(self, action):
        if self.cur is None:
            raise RuntimeError("no current decision")
        d, av, feas, infos, can_ret, can_wait = self.cur
        if action == ACT_RETURN:
            if not can_ret: raise ValueError("return is masked")
            inf = None
        elif action == ACT_WAIT:
            if not can_wait: raise ValueError("wait is masked")
            inf = None
        else:
            ids = [x["j"] for x in av]
            if action not in ids or not feas[ids.index(action)]:
                raise ValueError("task action is masked")
            inf = infos[ids.index(action)]
        self.n_dec += 1
        self.cur = None
        self._apply(d, action, inf)

    def _apply(self, d, a, info):
        if self.record: self.trace.append((self.t, d["i"], a))
        if a == ACT_WAIT:
            self._queue(d, min(self.t+WAIT_STEP, T_DAY)); d["slp"] = True
            return
        d["slp"] = False
        if a == ACT_RETURN:
            d.update(mode="return", target=None)
            return
        x = self.tasks[a]
        if d["at_st"]:
            d["launches"] += 1; d["ntrip"] += 1
        d.update(mode="fly", at_st=False, target=a)
        x["claim"] = d["i"]

    def result(self):
        fl = sum(d["flight"] for d in self.dr); hv = sum(d["hover"] for d in self.dr)
        routine = self.tasks[:self.n_planned]; urgent = self.tasks[self.n_planned:]
        n_pl_done = sum(x["done"] for x in routine); n_u_done = sum(x["done"] for x in urgent)
        ot = {p: [sum(x["done"] and x["t_arrival"] is not None and x["t_arrival"] <= x["dl"]+1e-9 for x in urgent if x["prio"] == p),
                  sum(x["prio"] == p for x in urgent)] for p in (0, 1)}
        arrivals = [x["t_arrival"]-x["rel"] for x in urgent if x["t_arrival"] is not None]
        completions = [x["t_done"]-x["rel"] for x in urgent if x["done"]]
        late = sum(max(0.0, x["t_arrival"]-x["dl"]) for x in urgent if x["t_arrival"] is not None)
        late_pen = sum(x["w"]*max(0.0, x["t_arrival"]-x["dl"]) for x in urgent if x["t_arrival"] is not None)
        failed = sum(d["failed"] for d in self.dr)
        unserved = len(self.tasks)-n_pl_done-n_u_done
        all_returned = all(d["at_st"] and not d["failed"] for d in self.dr)
        feasible = (not failed and all_returned and all(d["busy"] <= d["limit"]+1e-8 and d["e"] <= d["cap"]+1e-8 for d in self.dr))
        strict = int(unserved == 0 and feasible and not self.timeout)
        busy_ot = sum(max(0.0, d["busy"]-d["limit"]) for d in self.dr)
        author = self.L["fixed"]+TIME_COST*(fl+hv)
        failure_pen = C_UNSERVED*unserved+C_FAIL*failed
        inc = sum(d["inc_cell"]+d["inc_land"] for d in self.dr)
        per_st_J = {s["k"]: sum(TIME_COST*(d["flight"]+d["hover"])+C_FAIL*d["failed"]+
            C_INC*(d["inc_cell"]+d["inc_land"]) for d in self.dr if d["st"] == s["k"])
            + C_UNSERVED*sum(not x["done"] for x in routine if x["st"] == s["k"]) for s in self.st}
        m_return = max((d["last_return"] for d in self.dr), default=0.0) if all_returned else None
        return dict(J=author+C_INC*inc+late_pen+failure_pen, cost=author,
            fixed=self.L["fixed"], n_open=self.L["n_open"], n_dabs=self.L["n_dabs"],
            n_drones=len(self.dr), flight_min=fl, service_min=hv, op_min=fl+hv,
            dist_km=sum(d["dist"] for d in self.dr)/1000, launches=sum(d["launches"] for d in self.dr),
            aborts=sum(d["aborts"] for d in self.dr), inc_cell=sum(d["inc_cell"] for d in self.dr),
            inc_land=sum(d["inc_land"] for d in self.dr), busy_ot=busy_ot, clock_ot=0.0,
            makespan=self.t, M_return=m_return, all_returned=int(all_returned), physically_feasible=int(feasible),
            n_planned=self.n_planned, planned_done=n_pl_done, routine_total=self.n_planned, routine_done=n_pl_done,
            completion=(n_pl_done+n_u_done)/len(self.tasks) if self.tasks else 1.0, complete_strict=strict,
            n_urgent=len(urgent), urgent_done=n_u_done, n_unserviceable=self.n_unserviceable,
            high_on_time=ot[1][0], high_total=ot[1][1], norm_on_time=ot[0][0], norm_total=ot[0][1],
            ontime_high=ot[1][0]/ot[1][1] if ot[1][1] else None,
            ontime_norm=ot[0][0]/ot[0][1] if ot[0][1] else None,
            late_min=late, late_pen=late_pen,
            resp_mean=float(np.mean(arrivals)) if arrivals else None,
            resp_p95=float(np.percentile(arrivals, 95)) if arrivals else None,
            response_observed=len(arrivals), response_missing=len(urgent)-len(arrivals),
            completion_response_mean=float(np.mean(completions)) if completions else None,
            failure_penalty=failure_pen, unserved=unserved, failed=failed,
            fallback=0, timeout=int(self.timeout), termination_reason=self.termination_reason,
            n_dec=self.n_dec, per_st_J=per_st_J)
