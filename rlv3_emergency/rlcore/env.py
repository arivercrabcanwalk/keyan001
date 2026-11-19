"""Event-driven arc-level simulator shared by both rlv3 papers.

World = Liu et al. (2026) LRPHSD: the AUTHOR's stations / drones / target-to-station assignment (TSALNS plan) are fixed,
so #stations and fixed cost are identical for every method by construction.
Every drone, whenever it is at a node, chooses its next node: a task of its own station's pool
(paper A) / own pool or an eligible emergency request (paper B), RETURN to swap battery, or WAIT (at station only).

Shared feasibility layer ("shield", identical for all methods):
  * energy conservation mask (design 8.3): forecast c_ij + h_j + c_jD  <= (cap - e_used) / (1 + margin), margin = 0
    by default; heuristics add their own dev-tuned risk buffer, the RL policy learns its own buffer
  * thunderstorm mask: the legs i->j and j->D must clear the extrapolated nowcast cells (+buffer)
  * wind limit: no launch / continuation while forecast wind > W_LIMIT (manufacturer limit)
  * completion: no 'skip' action exists; the episode ends only when every planned target and every released request
    has been served -> strict 100 % completion is structural.  After T_HARD a late fallback relaxes margin / wind limit
    (flag `fallback` in the result; gate requires 0 for all reported methods' averages to be comparable).
Truth execution (paper A): leg integrated in 0.5-min steps with the TRUE spatio-temporal wind + gusts + outflow,
  physics energy P(v_a)*dt while flying and P(|w|)*dt while hovering; smart return-to-home (RTH) when remaining energy
  drops to the truth return need (+reserve) -> task not served, re-queued (abort); entering a true storm core
  = safety incident + RTH; battery depleted on the way home = forced landing incident (+60 min recovery).
"""
import math, heapq
import numpy as np
from . import phys
from .common import P1, P2, TIME_COST, VA_MS
from .weather import nowcast_hits

DT_FLY = 0.5
RTH_RES = 0.0           # author capacity Q is read as USABLE energy above the manufacturer critical-battery reserve
FAIL_GROUND = 60.0
WAIT_STEP = 10.0
T_DAY = 600.0           # 10-h working day (DABS endurance as clock limit)
T_HARD = 660.0
T_ABORT = 1400.0        # absolute safety stop (never reached in tests; result flagged)
C_OT = 1.0              # RMB per drone-minute beyond the author's per-drone operating limit and per station-minute after T_DAY
C_INC = 200.0           # RMB per safety incident (cell incursion / forced landing) - J only
K_MAX = 48              # max task candidates shown to a policy (nearest first)

ACT_RETURN, ACT_WAIT = -1, -2


class Env:
    def __init__(self, layout, wx=None, requests=None, margin=None, use_cells=True, wind_limit=True,
                 urgent_w=None, record=False):
        self.L = layout
        self.wx = wx
        self.calm = (wx is None) or getattr(wx, "calm", False)
        # shield margin: 0 = exactly design 8.3 (forecast energy conservation); methods may add their own buffer
        self.margin = 0.0 if margin is None else float(margin)
        self.use_cells = use_cells and (wx is not None) and getattr(wx, "ncell", 0) > 0
        self.wind_limit = wind_limit and not self.calm
        self.record = record
        self.trace = []
        st = layout["stations"]
        self.st = st
        # tasks: planned targets first
        self.tasks = []
        for tid, k in sorted(layout["assign"].items()):
            x, y, svc, en = layout["targets"][tid]
            self.tasks.append(dict(j=len(self.tasks), tid=tid, x=x, y=y, svc=svc, en=en, urgent=0, st=k,
                                   elig=(k,), rel=0.0, dl=None, prio=0, w=0.0, done=False, claim=-1, t_done=None))
        self.n_planned = len(self.tasks)
        self.requests = sorted(requests or [], key=lambda r: r["t"])
        from .urgent import W_LATE
        self.W_LATE = urgent_w or W_LATE
        self.req_gen = None          # (targets, level) set by scen.make_env; used only by resample_future
        for r in self.requests:
            self.tasks.append(self._req_task(r))
        self.n_unserviceable = sum(1 for t in self.tasks if t["urgent"] and not t["elig"])
        # planned order rank per station (author's sequence) and per-drone planned queues (for A1 + features)
        self.rank = {}
        for d in layout["drones"]:
            seq = [tid for tr in d["trips"] for tid in tr]
            for r_, tid in enumerate(seq):
                self.rank[tid] = (d["i"], r_, len(seq))
        self.tid2j = {t["tid"]: t["j"] for t in self.tasks if not t["urgent"]}
        self.dr = []
        for d in layout["drones"]:
            s = st[d["st"]]
            self.dr.append(dict(i=d["i"], st=d["st"], di=d["di"], cap=d["cap"], limit=d["limit"], x=s["x"], y=s["y"],
                                at_st=True, node=-1, e=0.0, t=0.0, busy=0.0, flight=0.0, hover=0.0, dist=0.0,
                                launches=0, aborts=0, inc_cell=0, inc_land=0, retired=False, t_last=0.0, ntrip=0))
        self.heap = [(0.0, d["i"]) for d in self.dr]
        heapq.heapify(self.heap)
        self.t = 0.0
        self.next_rel = 0
        self.fallback = False
        self.cur = None
        self.done = False
        self.n_dec = 0
        self.timeout = False

    def _req_task(self, r):
        elig = tuple(s["k"] for s in self.st if math.hypot(s["x"] - r["x"], s["y"] - r["y"]) <= s["R"] + 1e-7)
        return dict(j=len(self.tasks), tid=r["tid"], x=r["x"], y=r["y"], svc=r["svc"], en=r["energy"],
                    urgent=1, st=-1, elig=elig, rel=r["t"], dl=r["dl"], prio=r["prio"],
                    w=self.W_LATE[r["prio"]], done=False, claim=-1, t_done=None, rid=r["rid"])

    def resample_future(self, seed):
        """Redraw everything not yet observable at self.t (weather after t / requests released after t) from the
        generative model.  Call on a COPY of the env (rollout-improvement labels without hindsight bias)."""
        if self.wx is not None and not self.calm:
            self.wx = self.wx.resample_future(self.t, seed)
        if self.req_gen is None:
            return
        from .urgent import make_requests
        targets, level = self.req_gen
        keep = [x for x in self.tasks[self.n_planned:] if x["rel"] <= self.t + 1e-9]
        self.tasks = self.tasks[:self.n_planned] + keep
        assert all(x["j"] == k for k, x in enumerate(self.tasks))
        new = []
        for r in make_requests(10 ** 9 + int(seed), targets, level):
            if r["t"] > self.t + 1e-9:
                r = dict(r, rid=10 ** 6 + r["rid"]); x = self._req_task(r); self.tasks.append(x); new.append(x)
        ent = {i: t for t, i in self.heap}
        for d in self.dr:
            rels = [x["rel"] for x in new if d["st"] in x["elig"]]
            if not rels:
                continue
            r0 = min(rels)
            if d["retired"]:
                d["retired"] = False; d["slp"] = False; d["t"] = max(r0, d["t"]); ent[d["i"]] = d["t"]
            elif d.get("slp") and d["i"] in ent and ent[d["i"]] > r0:
                d["t"] = r0; ent[d["i"]] = r0
        self.heap = [(t, i) for i, t in ent.items()]
        heapq.heapify(self.heap)

    # ---------------------------------------------------------------- helpers
    def _released(self, t):
        return [x for x in self.tasks if x["urgent"] and x["rel"] <= t + 1e-9]

    def _fc(self, t):
        if self.calm:
            return 0.0, 0.0
        return self.wx.forecast_wind(self.t, t)

    def leg_pred(self, x1, y1, x2, y2, t0):
        """forecast physics energy / minutes / feasible of a leg (design 8.1 revised)."""
        if self.calm:
            d = math.hypot(x2 - x1, y2 - y1); tm = d / (VA_MS * 60.0)
            return P1 * tm, tm, True
        wx, wy = self._fc(t0)
        return phys.leg_cost(x1, y1, x2, y2, wx, wy)

    def hover_pred(self, t0, svc):
        if self.calm:
            return P2 * svc
        wx, wy = self._fc(t0)
        return phys.p_hover(math.hypot(wx, wy)) * svc

    def unfinished(self):
        return [x for x in self.tasks if not x["done"]]

    def avail_tasks(self, d):
        """tasks the drone may pick now (released, unserved, unclaimed, eligible)."""
        out = []
        for x in self.tasks:
            if x["done"] or x["claim"] >= 0 or x.get("free_at", 0.0) > self.t + 1e-9:
                continue
            if x["urgent"]:
                if x["rel"] > self.t + 1e-9 or d["st"] not in x["elig"]:
                    continue
            elif x["st"] != d["st"]:
                continue
            out.append(x)
        return out

    def task_check(self, d, x):
        """shield for one candidate task -> (feasible, info dict)."""
        s = self.st[d["st"]]
        relax = self.t >= T_HARD
        e1, t1, ok1 = self.leg_pred(d["x"], d["y"], x["x"], x["y"], self.t)
        h = self.hover_pred(self.t + t1, x["svc"]) if not self.calm else x["en"]
        e2, t2, ok2 = self.leg_pred(x["x"], x["y"], s["x"], s["y"], self.t + t1 + x["svc"])
        need = e1 + h + e2
        m = 0.0 if relax else self.margin
        feas = ok1 and ok2 and (need * (1 + m) <= d["cap"] - d["e"] + 1e-9)
        cell = False
        if feas and self.use_cells and not relax:
            nc = self._nc()
            cell = nowcast_hits(nc, d["x"], d["y"], x["x"], x["y"], self.t, t1) or \
                nowcast_hits(nc, x["x"], x["y"], s["x"], s["y"], self.t + t1 + x["svc"], t2)
            feas = not cell
        if feas and self.wind_limit and not relax:
            wx, wy = self._fc(self.t)
            if math.hypot(wx, wy) > phys.W_LIMIT:
                feas = False
        return feas, dict(e1=e1, t1=t1, h=h, e2=e2, t2=t2, need=need, cell=cell)

    def _nc(self):
        key = round(self.t, 3)
        if getattr(self, "_nc_key", None) != key:
            self._nc_key = key
            self._nc_val = self.wx.nowcast(self.t) if self.use_cells else []
        return self._nc_val

    # ---------------------------------------------------------------- decision interface
    def next_decision(self):
        """Advance to the next drone decision with >1 legal action.  Returns (drone, cand, info) or None when done.
        Decisions with exactly one legal action are applied automatically."""
        while True:
            if not self.heap:
                self.done = True
                return None
            t, i = heapq.heappop(self.heap)
            d = self.dr[i]
            self.t = max(self.t, t)
            if self.t > T_ABORT:
                self.timeout = True; self.done = True
                return None
            if self.t >= T_HARD and not self.fallback and self.unfinished():
                self.fallback = True
            av = self.avail_tasks(d)
            if not av:
                if not d["at_st"]:
                    self._apply(d, ACT_RETURN, None); continue
                # idle at station: sleep until next release that could concern anyone, or retire
                fut = [x["rel"] for x in self.tasks if x["urgent"] and not x["done"] and x["rel"] > self.t + 1e-9
                       and d["st"] in x["elig"]]
                pend = [x for x in self.tasks if not x["done"] and
                        ((x["urgent"] and d["st"] in x["elig"]) or (not x["urgent"] and x["st"] == d["st"]))]
                if fut:
                    d["t"] = min(fut); d["slp"] = True; heapq.heappush(self.heap, (d["t"], i)); continue
                if pend:
                    # tasks of my pool are claimed by my sibling (may be released after abort) -> check again later
                    d["t"] = self.t + WAIT_STEP; heapq.heappush(self.heap, (d["t"], i)); continue
                d["retired"] = True
                continue
            av.sort(key=lambda x: (x["x"] - d["x"]) ** 2 + (x["y"] - d["y"]) ** 2)
            av = av[:K_MAX]
            feas, infos = [], []
            for x in av:
                f, inf = self.task_check(d, x)
                feas.append(f); infos.append(inf)
            nfeas = sum(feas)
            can_ret = not d["at_st"]
            can_wait = d["at_st"] and not (self.t >= T_HARD and nfeas > 0)   # completion guarantee: no idling late
            if nfeas == 0:
                if can_ret:
                    self._apply(d, ACT_RETURN, None); continue
                self._apply(d, ACT_WAIT, None); continue
            if nfeas == 1 and not can_ret and not can_wait:
                k = feas.index(True); self._apply(d, av[k]["j"], infos[k]); continue
            self.cur = (d, av, feas, infos, can_ret, can_wait)
            return self.cur

    def step(self, action):
        """action: task index j (must be feasible in the current candidate list), ACT_RETURN or ACT_WAIT."""
        d, av, feas, infos, can_ret, can_wait = self.cur
        self.n_dec += 1
        if action == ACT_RETURN:
            assert can_ret
            self._apply(d, ACT_RETURN, None)
        elif action == ACT_WAIT:
            assert can_wait
            self._apply(d, ACT_WAIT, None)
        else:
            k = [x["j"] for x in av].index(action)
            assert feas[k], "policy chose a masked task"
            self._apply(d, action, infos[k])
        self.cur = None

    # ---------------------------------------------------------------- truth execution
    def _fly(self, d, x2, y2, allow_rth=True):
        """integrate a straight leg under truth; returns 'ok' | 'rth' | 'cell' | 'land'."""
        if self.calm:
            dd = math.hypot(x2 - d["x"], y2 - d["y"]); tm = dd / (VA_MS * 60.0)
            d["e"] += P1 * tm; d["t"] += tm; d["flight"] += tm; d["dist"] += dd
            d["x"], d["y"] = x2, y2
            return "ok"
        s = self.st[d["st"]]
        while True:
            dx, dy = x2 - d["x"], y2 - d["y"]; dd = math.hypot(dx, dy)
            if dd < 1.0:
                d["x"], d["y"] = x2, y2
                return "ok"
            ux, uy = dx / dd, dy / dd
            wx, wy = self.wx.truth_wind(d["x"], d["y"], d["t"])
            vg = phys.ground_speed(wx, wy, ux, uy) * 60.0
            if vg < 30.0:
                vg = 30.0          # crawl (unsustainable heading); energy keeps draining
            dt = min(DT_FLY, dd / vg)
            d["e"] += phys.P_CRUISE * dt
            d["x"] += ux * vg * dt; d["y"] += uy * vg * dt; d["t"] += dt; d["flight"] += dt; d["dist"] += vg * dt
            if self.wx.ncell and self.wx.in_cell(d["x"], d["y"], d["t"]):
                d["inc_cell"] += 1
                return "cell"
            if d["e"] > d["cap"] + 1e-9:
                return "land"
            if allow_rth:
                er = self._ret_need_truth(d, s)
                if d["cap"] - d["e"] < er + RTH_RES:
                    return "rth"

    def _ret_need_truth(self, d, s):
        """flight-controller return-energy estimate with a wind-proportional safety factor (1 + |w|/v_a);
        factor = 1 at zero wind, so author-feasible trips never trigger RTH in calm air."""
        dd = math.hypot(s["x"] - d["x"], s["y"] - d["y"])
        if dd < 1.0:
            return 0.0
        wx, wy = self.wx.truth_wind(d["x"], d["y"], d["t"])
        vg = max(phys.ground_speed(wx, wy, (s["x"] - d["x"]) / dd, (s["y"] - d["y"]) / dd), 0.5)
        return phys.P_CRUISE * dd / (vg * 60.0) * (1.0 + math.hypot(wx, wy) / VA_MS)

    def _hover(self, d, x):
        """service hover under truth; returns 'ok' | 'rth' | 'cell'."""
        if self.calm:
            d["e"] += x["en"]; d["t"] += x["svc"]; d["hover"] += x["svc"]
            return "ok"
        s = self.st[d["st"]]
        rem = x["svc"]
        while rem > 1e-9:
            dt = min(DT_FLY, rem)
            wx, wy = self.wx.truth_wind(d["x"], d["y"], d["t"])
            d["e"] += phys.p_hover(math.hypot(wx, wy)) * dt
            d["t"] += dt; d["hover"] += dt; rem -= dt
            if self.wx.ncell and self.wx.in_cell(d["x"], d["y"], d["t"]):
                d["inc_cell"] += 1
                return "cell"
            if d["cap"] - d["e"] < self._ret_need_truth(d, s) + RTH_RES:
                return "rth"
        return "ok"

    def _go_home(self, d):
        s = self.st[d["st"]]
        t0, f0, h0 = d["t"], d["flight"], d["hover"]
        r = self._fly(d, s["x"], s["y"], allow_rth=False)
        while r == "cell":           # keep flying home through the core (incident already counted)
            r = self._fly(d, s["x"], s["y"], allow_rth=False)
        if r == "land":
            d["inc_land"] += 1
            # forced landing: drone recovered by crew, counted as flight to station distance
            dd = math.hypot(s["x"] - d["x"], s["y"] - d["y"])
            d["x"], d["y"] = s["x"], s["y"]
            d["t"] += FAIL_GROUND
        d["busy"] += (d["flight"] - f0) + (d["hover"] - h0)
        d["e"] = 0.0; d["at_st"] = True; d["node"] = -1

    def _apply(self, d, a, info):
        i = d["i"]
        if self.record:
            self.trace.append((round(self.t, 3), i, a))
        if a == ACT_WAIT:
            fut = [x["rel"] for x in self.tasks if x["urgent"] and x["rel"] > self.t + 1e-9]
            d["t"] = min([self.t + WAIT_STEP] + fut); d["slp"] = True
            heapq.heappush(self.heap, (d["t"], i)); return
        d["slp"] = False
        if a == ACT_RETURN:
            self._go_home(d)
            heapq.heappush(self.heap, (d["t"], i)); return
        x = self.tasks[a]
        if d["at_st"]:
            d["launches"] += 1; d["ntrip"] += 1
        d["at_st"] = False
        x["claim"] = i
        f0, h0 = d["flight"], d["hover"]
        r = self._fly(d, x["x"], x["y"])
        if r == "ok":
            r = self._hover(d, x)
        d["busy"] += (d["flight"] - f0) + (d["hover"] - h0)
        if r == "ok":
            x["done"] = True; x["t_done"] = d["t"]; d["node"] = a
            heapq.heappush(self.heap, (d["t"], i)); return
        # abort: task released again (visible to others only from the abort time on), drone returns home
        x["claim"] = -1; x["free_at"] = d["t"]
        d["aborts"] += 1
        self._go_home(d)
        heapq.heappush(self.heap, (d["t"], i))

    # ---------------------------------------------------------------- results
    def result(self):
        L = self.L
        fl = sum(d["flight"] for d in self.dr); hv = sum(d["hover"] for d in self.dr)
        busy_ot = sum(max(0.0, d["busy"] - d["limit"]) for d in self.dr)
        st_end = {}
        for d in self.dr:
            st_end[d["st"]] = max(st_end.get(d["st"], 0.0), d["t"])
        clock_ot = sum(max(0.0, v - T_DAY) for v in st_end.values())
        late = 0.0; late_pen = 0.0; n_u = 0; ontime = {0: [0, 0], 1: [0, 0]}; resp = []
        for x in self.tasks:
            if not x["urgent"] or not x["elig"]:
                continue
            n_u += 1
            if x["done"]:
                lt = max(0.0, x["t_done"] - x["dl"]); late += lt; late_pen += x["w"] * lt
                ontime[x["prio"]][0] += int(lt <= 1e-9); ontime[x["prio"]][1] += 1
                resp.append(x["t_done"] - x["rel"])
        n_pl_done = sum(1 for x in self.tasks[:self.n_planned] if x["done"])
        n_u_done = sum(1 for x in self.tasks[self.n_planned:] if x["done"])
        inc = sum(d["inc_cell"] + d["inc_land"] for d in self.dr)
        author = L["fixed"] + TIME_COST * (fl + hv)
        J = author + C_OT * (busy_ot + clock_ot) + C_INC * inc + late_pen
        per_st = {}
        for d in self.dr:
            p = per_st.setdefault(d["st"], dict(op=0.0, busy_ot=0.0, inc=0))
            p["op"] += d["flight"] + d["hover"]; p["busy_ot"] += max(0.0, d["busy"] - d["limit"])
            p["inc"] += d["inc_cell"] + d["inc_land"]
        per_st_J = {k: TIME_COST * v["op"] + C_OT * (v["busy_ot"] + max(0.0, st_end[k] - T_DAY)) + C_INC * v["inc"]
                    for k, v in per_st.items()}
        return dict(
            J=J, cost=author, fixed=L["fixed"], n_open=L["n_open"], n_dabs=L["n_dabs"],
            n_drones=len(self.dr), flight_min=fl, service_min=hv, op_min=fl + hv,
            dist_km=sum(d["dist"] for d in self.dr) / 1000.0,
            launches=sum(d["launches"] for d in self.dr), aborts=sum(d["aborts"] for d in self.dr),
            inc_cell=sum(d["inc_cell"] for d in self.dr), inc_land=sum(d["inc_land"] for d in self.dr),
            busy_ot=busy_ot, clock_ot=clock_ot, makespan=max(st_end.values()) if st_end else 0.0,
            n_planned=self.n_planned, planned_done=n_pl_done,
            completion=(n_pl_done + n_u_done) / max(1, self.n_planned + n_u),
            complete_strict=int(n_pl_done == self.n_planned and n_u_done == n_u),
            n_urgent=n_u, urgent_done=n_u_done, n_unserviceable=self.n_unserviceable,
            late_min=late, late_pen=late_pen,
            ontime_high=(ontime[1][0] / ontime[1][1]) if ontime[1][1] else None,
            ontime_norm=(ontime[0][0] / ontime[0][1]) if ontime[0][1] else None,
            resp_mean=float(np.mean(resp)) if resp else None, resp_p95=float(np.percentile(resp, 95)) if resp else None,
            fallback=int(self.fallback), timeout=int(self.timeout), n_dec=self.n_dec, per_st_J=per_st_J)
