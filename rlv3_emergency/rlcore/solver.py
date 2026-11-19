"""Budgeted insertion/relocate/2-opt/merge heuristic.

This is a custom forecast heuristic, not TSALNS or ALNS and not a certified
strongest baseline. The monotonic deadline includes construction and search;
unplaced nodes are returned in P.last_solve, never fabricated as feasible trips.
"""
import math
import time
import numpy as np
from . import phys
from .common import P1, VA_MS, TIME_COST


def cost_matrix(pts, wind, calm):
    pts = np.asarray(pts, float)
    n = len(pts)
    E, T = np.zeros((n, n)), np.zeros((n, n))
    F = np.ones((n, n), bool)
    for i, (x1, y1) in enumerate(pts):
        for j, (x2, y2) in enumerate(pts):
            if calm:
                tm = math.hypot(x2-x1, y2-y1)/(VA_MS*60)
                E[i, j], T[i, j] = P1*tm, tm
            else:
                E[i, j], T[i, j], F[i, j] = phys.leg_cost(x1, y1, x2, y2, *wind)
    return E, T, F


class Prob:
    def __init__(self, E, T, F, svc, hen, rel, dl, w, caps, t_ready, margin,
                 t_now, t_day=600.0, c_ot=1.0, duty_left=None):
        self.E, self.T, self.F = E, T, F
        self.svc, self.hen, self.rel, self.dl, self.w = svc, hen, rel, dl, w
        self.caps, self.t_ready = caps, t_ready
        self.m, self.t_now, self.t_day, self.c_ot = margin, t_now, t_day, c_ot
        self.duty_left = list(duty_left) if duty_left is not None else [t_day]*len(caps)
        self.n = len(svc)-1
        self.last_solve = {}

    def trip_energy(self, trip):
        p, e = 0, 0.0
        for j in trip:
            e += self.E[p, j]+self.hen[j]
            p = j
        return e+self.E[p, 0]

    def trip_ok(self, trip, cap):
        p = 0
        for j in trip:
            if not self.F[p, j]:
                return False
            p = j
        return bool(self.F[p, 0] and self.trip_energy(trip)*(1+self.m) <= cap+1e-9)

    def sched_cost(self, routes):
        c, seen = 0.0, set()
        for di, trips in enumerate(routes):
            t, duty = self.t_ready[di], 0.0
            for tr in trips:
                if not self.trip_ok(tr, self.caps[di]):
                    return float("inf")
                p = 0
                for j in tr:
                    if j in seen or not 1 <= j <= self.n:
                        return float("inf")
                    seen.add(j)
                    arrival = max(t+self.T[p, j], self.rel[j])
                    dt = self.T[p, j]+self.svc[j]
                    duty += dt
                    t = arrival+self.svc[j]
                    c += TIME_COST*dt+self.w[j]*max(0.0, arrival-self.dl[j])
                    p = j
                t += self.T[p, 0]
                duty += self.T[p, 0]
                c += TIME_COST*self.T[p, 0]
            if duty > self.duty_left[di]+1e-9 or t > self.t_day+1e-9:
                return float("inf")
        return c


def _alive(deadline):
    return time.perf_counter() < deadline


def insert_all(P, routes, todo, deadline):
    for j in sorted(todo, key=lambda j: (P.dl[j] if P.w[j] else float("inf"), j)):
        if not _alive(deadline):
            return routes
        best = None
        for di, trips in enumerate(routes):
            for ti in range(len(trips)+1):
                positions = range(len(trips[ti])+1) if ti < len(trips) else (0,)
                for pos in positions:
                    if not _alive(deadline):
                        return routes
                    tr = trips[ti] if ti < len(trips) else []
                    cand = tr[:pos]+[j]+tr[pos:]
                    if not P.trip_ok(cand, P.caps[di]):
                        continue
                    nt = trips[:ti]+[cand]+trips[ti+1:]
                    nr = routes[:di]+[nt]+routes[di+1:]
                    cost = P.sched_cost(nr)
                    if math.isfinite(cost) and (best is None or cost < best[0]):
                        best = cost, nr
        if best is not None:
            routes = best[1]
    return routes

def local_search(P, routes, deadline, max_pass=4):
    cur = P.sched_cost(routes)
    for _ in range(max_pass):
        if not _alive(deadline):
            return routes
        improved = False
        flat = [(di, ti, pos) for di, trips in enumerate(routes)
                for ti, tr in enumerate(trips) for pos in range(len(tr))]
        for di, ti, pos in flat:
            if not _alive(deadline):
                return routes
            if ti >= len(routes[di]) or pos >= len(routes[di][ti]):
                continue
            j = routes[di][ti][pos]
            tr = routes[di][ti][:pos]+routes[di][ti][pos+1:]
            nt = routes[di][:ti]+([tr] if tr else [])+routes[di][ti+1:]
            rem = routes[:di]+[nt]+routes[di+1:]
            nr = insert_all(P, rem, [j], deadline)
            if {x for r in nr for tr in r for x in tr} != {x for r in routes for tr in r for x in tr}:
                continue
            cost = P.sched_cost(nr)
            if cost < cur-1e-9:
                routes, cur, improved = nr, cost, True
        for di in range(len(routes)):
            for ti in range(len(routes[di])):
                tr = routes[di][ti]
                for a in range(len(tr)-1):
                    for b in range(a+1, len(tr)):
                        if not _alive(deadline):
                            return routes
                        cand = tr[:a]+tr[a:b+1][::-1]+tr[b+1:]
                        nt = routes[di][:ti]+[cand]+routes[di][ti+1:]
                        nr = routes[:di]+[nt]+routes[di+1:]
                        cost = P.sched_cost(nr)
                        if cost < cur-1e-9:
                            routes, cur, improved, tr = nr, cost, True, cand
            k = 0
            while k < len(routes[di])-1:
                if not _alive(deadline):
                    return routes
                trips = routes[di]
                nt = trips[:k]+[trips[k]+trips[k+1]]+trips[k+2:]
                nr = routes[:di]+[nt]+routes[di+1:]
                cost = P.sched_cost(nr)
                if cost < cur-1e-9:
                    routes, cur, improved = nr, cost, True
                else:
                    k += 1
        if not improved:
            break
    return routes


def solve(P, init_routes=None, budget_s=0.03):
    if not math.isfinite(budget_s) or budget_s < 0:
        raise ValueError("finite nonnegative solver budget required")
    start = time.perf_counter()
    deadline = start+budget_s
    routes = [[] for _ in P.caps]
    # Validate warm starts node by node, and count the work in the same budget.
    if init_routes is not None:
        for di, trips in enumerate(init_routes):
            for tr in trips:
                if not _alive(deadline):
                    break
                nr = [list(map(list, r)) for r in routes]
                nr[di].append(list(tr))
                if math.isfinite(P.sched_cost(nr)):
                    routes = nr
    placed = {j for r in routes for tr in r for j in tr}
    routes = insert_all(P, routes, [j for j in range(1, P.n+1) if j not in placed], deadline)
    routes = local_search(P, routes, deadline)
    placed = {j for r in routes for tr in r for j in tr}
    elapsed = time.perf_counter()-start
    P.last_solve = dict(algorithm="insertion_relocate_2opt_merge", budget_s=budget_s,
        elapsed_s=elapsed, deadline_reached=not _alive(deadline),
        unassigned=[j for j in range(1, P.n+1) if j not in placed],
        feasible=math.isfinite(P.sched_cost(routes)))
    return routes
