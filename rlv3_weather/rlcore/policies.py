"""Non-RL policies on the shared simulator (identical shield / completion layer for all).
  A1      author TSALNS plan executed as planned (per-drone trip order); shield-blocked target -> return / wait;
          emergency requests (paper B): first-come-first-served by the first drone idle at a covering station.
  GREEDY  physics-aware myopic: EDF for emergencies, otherwise the task with least predicted energy (wind-aware NN).
  REOPT   rolling-horizon re-optimisation of the station's remaining work at every trip start / new request with
          forecast physics costs (solver.py) - the strongest non-RL baseline ("author method adapted: re-optimise on event").
          theta: optional wind-wait threshold (m/s), tuned on dev (REOPT-W).
"""
import math
import numpy as np
from .env import ACT_RETURN, ACT_WAIT, T_DAY, T_HARD
from . import solver as S


def _buf(cur, m):
    """method-specific risk buffer on top of the shared shield: need*(1+m) <= cap - e."""
    d, av, feas, infos, can_ret, can_wait = cur
    if m <= 0 or not can_wait and d["at_st"]:
        return cur
    f2 = [f and inf["need"] * (1 + m) <= d["cap"] - d["e"] + 1e-9 for f, inf in zip(feas, infos)]
    return (d, av, f2, infos, can_ret, can_wait)


def _idle(cur):
    """default 'do nothing' action that is legal in the current state."""
    d, av, feas, infos, can_ret, can_wait = cur
    if can_wait:
        return ACT_WAIT
    if can_ret:
        return ACT_RETURN
    fe = [x for x, f in zip(av, feas) if f]
    return min(fe, key=lambda x: (x["x"] - d["x"]) ** 2 + (x["y"] - d["y"]) ** 2)["j"]


def _pick(cur, j):
    d, av, feas, infos, can_ret, can_wait = cur
    ids = [x["j"] for x in av]
    if j in ids and feas[ids.index(j)]:
        return j
    return None


class A1:
    def __init__(self, margin=0.0):
        self.m = margin; self.name = "A1" if margin == 0 else f"A1@{margin:g}"

    def reset(self, env):
        self.q = {}
        for d in env.L["drones"]:
            self.q[d["i"]] = [[env.tid2j[t] for t in tr] for tr in d["trips"]]
        self.cur_trip = {}

    def act(self, env, cur):
        cur = _buf(cur, self.m)
        d, av, feas, infos, can_ret, can_wait = cur
        i = d["i"]
        q = [[j for j in tr if not env.tasks[j]["done"]] for tr in self.q[i]]
        self.q[i] = [tr for tr in q if tr]
        if not d["at_st"]:
            tr = self.cur_trip.get(i, [])
            tr = [j for j in tr if not env.tasks[j]["done"]]
            self.cur_trip[i] = tr
            if tr and _pick(cur, tr[0]) is not None:
                return tr[0]
            return ACT_RETURN
        # at station: emergencies first (FCFS by release time)
        urg = [x for x, f in zip(av, feas) if f and x["urgent"]]
        if urg:
            u = min(urg, key=lambda x: x["rel"])
            self.cur_trip[i] = []
            return u["j"]
        for ti, tr in enumerate(self.q[i]):
            for j in tr:
                if _pick(cur, j) is not None:
                    rest = [k for k in tr if k != j]
                    self.cur_trip[i] = rest
                    return j
        return _idle(cur)


class Greedy:
    def __init__(self, margin=0.0):
        self.m = margin; self.name = "GREEDY" if margin == 0 else f"GREEDY@{margin:g}"

    def reset(self, env):
        pass

    def act(self, env, cur):
        cur = _buf(cur, self.m)
        d, av, feas, infos, can_ret, can_wait = cur
        fe = [(x, inf) for x, f, inf in zip(av, feas, infos) if f]
        if not fe:
            return _idle(cur)
        urg = [(x, inf) for x, inf in fe if x["urgent"]]
        if urg:
            return min(urg, key=lambda p: p[0]["dl"])[0]["j"]
        return min(fe, key=lambda p: p[1]["e1"])[0]["j"]


class Reopt:
    def __init__(self, budget_s=0.03, theta=None, margin=0.0):
        self.budget = budget_s
        self.theta = theta
        self.m = margin
        self.name = ("REOPT" if theta is None else f"REOPT-W{theta:g}") + ("" if margin == 0 else f"@{margin:g}")

    def reset(self, env):
        self.trip = {d["i"]: [] for d in env.dr}
        self.seen_rel = {d["i"]: 0 for d in env.dr}

    def _reserved(self, env, i):
        r = set()
        for k, tr in self.trip.items():
            if k != i and not env.dr[k]["at_st"]:
                r.update(tr)
        return r

    def _plan_station(self, env, d, av):
        s = env.st[d["st"]]
        res = self._reserved(env, d["i"])
        tasks = [x for x in av if x["j"] not in res]
        if not tasks:
            return []
        sibs = [env.dr[k] for k in s["drones"]]
        pts = [(s["x"], s["y"])] + [(x["x"], x["y"]) for x in tasks]
        wind = (0.0, 0.0) if env.calm else env.wx.forecast_wind(env.t, env.t + 30.0)
        E, T, F = S.cost_matrix(pts, wind, env.calm)
        n = len(tasks)
        hen = np.zeros(n + 1); svc = np.zeros(n + 1); rel = np.zeros(n + 1); dl = np.zeros(n + 1); w = np.zeros(n + 1)
        for k, x in enumerate(tasks, 1):
            svc[k] = x["svc"]; hen[k] = env.hover_pred(env.t, x["svc"]) if not env.calm else x["en"]
            rel[k] = x["rel"]; dl[k] = x["dl"] if x["dl"] is not None else 1e9; w[k] = x["w"]
        order = [d] + [o for o in sibs if o["i"] != d["i"]]
        caps = [o["cap"] for o in order]
        t_ready = [env.t] + [max(env.t, o["t"]) + (0.0 if o["at_st"] else 15.0) for o in order[1:]]
        P = S.Prob(E, T, F, svc, hen, rel, dl, w, caps, t_ready, max(env.margin, self.m), env.t, T_DAY)
        # warm start = the author's remaining plan (per drone, planned order), repacked into forecast-feasible trips
        loc = {x["j"]: k for k, x in enumerate(tasks, 1)}
        init = []
        for o in order:
            trips = []
            for tr in env.L["drones"][o["i"]]["trips"]:
                cur_t = []
                for tid in tr:
                    j = env.tid2j[tid]
                    if j not in loc:
                        continue
                    if P.trip_ok(cur_t + [loc[j]], o["cap"]):
                        cur_t.append(loc[j])
                    else:
                        if cur_t:
                            trips.append(cur_t)
                        cur_t = [loc[j]] if P.trip_ok([loc[j]], o["cap"]) else []
                if cur_t:
                    trips.append(cur_t)
            init.append(trips)
        routes = S.solve(P, init_routes=init, budget_s=self.budget)
        if not routes[0] and len(routes) > 1 and len(routes[1]) >= 2:
            routes[0] = [routes[1][-1]]          # keep both drones busy (parallelism) instead of idling
        first = routes[0][0] if routes[0] else []
        return [tasks[k - 1]["j"] for k in first]

    def act(self, env, cur):
        cur = _buf(cur, self.m)
        d, av, feas, infos, can_ret, can_wait = cur
        i = d["i"]
        if not d["at_st"]:
            tr = [j for j in self.trip[i] if not env.tasks[j]["done"]]
            # new emergency released since trip start -> try cheapest insertion at the head of the remaining trip
            urg = [(x, inf) for x, f, inf in zip(av, feas, infos) if f and x["urgent"] and x["j"] not in tr
                   and x["j"] not in self._reserved(env, i)]
            if urg:
                x, inf = min(urg, key=lambda p: p[0]["dl"])
                tr = [x["j"]] + tr
            self.trip[i] = tr
            if tr and _pick(cur, tr[0]) is not None:
                self.trip[i] = tr[1:]
                return tr[0]
            self.trip[i] = []
            return ACT_RETURN
        if self.theta is not None and not env.calm:
            wx, wy = env.wx.forecast_wind(env.t, env.t)
            if math.hypot(wx, wy) > self.theta and env.t < 0.6 * T_DAY and can_wait:
                return ACT_WAIT
        tr = self._plan_station(env, d, av)
        for k, j in enumerate(tr):
            if _pick(cur, j) is not None:
                self.trip[i] = tr[k + 1:]
                return j
        fe = [x for x, f in zip(av, feas) if f and x["j"] not in self._reserved(env, i)]
        sib_busy = any(env.dr[k]["i"] != i for k in env.st[d["st"]]["drones"])
        if fe and not tr and not sib_busy:
            x = min(fe, key=lambda x: (x["x"] - d["x"]) ** 2 + (x["y"] - d["y"]) ** 2)
            self.trip[i] = []
            return x["j"]
        return _idle(cur)


def make(name):
    """'A1', 'A1@0.1', 'GREEDY@0.05', 'REOPT', 'REOPT@0.1', 'REOPT-W9@0.1' (theta = wind-wait threshold m/s)."""
    base, _, m = name.partition("@")
    m = float(m) if m else 0.0
    if base == "A1":
        return A1(margin=m)
    if base == "GREEDY":
        return Greedy(margin=m)
    if base == "REOPT":
        return Reopt(margin=m)
    if base.startswith("REOPT-W"):
        return Reopt(theta=float(base[7:]), margin=m)
    raise ValueError(name)


def run_episode(env, pol):
    pol.reset(env)
    while True:
        cur = env.next_decision()
        if cur is None:
            break
        env.step(pol.act(env, cur))
    return env.result()
