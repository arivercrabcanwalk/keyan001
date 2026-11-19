"""REOPT baseline: rolling-horizon re-optimisation (strongest non-RL baseline; 'author adaptation: re-optimise on event').

At each trip start (and on new emergency requests) the remaining tasks of a station are re-planned as a multi-trip,
energy-constrained routing problem with the CURRENT forecast physics costs (asymmetric, wind-dependent) and soft
deadlines for emergency requests:  cheapest-insertion construction + relocate / 2-opt / exchange local search
(an ALNS-style repair/improve loop under a small time budget).  Only forecast information is used.
"""
import math, time
import numpy as np
from . import phys
from .common import P1, P2, VA_MS, TIME_COST


def cost_matrix(pts, wind, calm):
    """pts: (n,2) metres. Returns energy E[i,j], minutes T[i,j], feasible F[i,j] under constant forecast wind."""
    pts = np.asarray(pts, float)
    dx = pts[None, :, 0] - pts[:, None, 0]; dy = pts[None, :, 1] - pts[:, None, 1]
    d = np.hypot(dx, dy)
    if calm:
        T = d / (VA_MS * 60.0)
        return P1 * T, T, np.ones_like(d, bool)
    wx, wy = wind
    with np.errstate(invalid="ignore", divide="ignore"):
        ux = np.where(d > 1e-6, dx / np.maximum(d, 1e-9), 0.0); uy = np.where(d > 1e-6, dy / np.maximum(d, 1e-9), 0.0)
    eta = (wx * ux + wy * uy) / VA_MS; xi = (wx * uy - wy * ux) / VA_MS
    disc = 1 - xi ** 2
    vg = VA_MS * (eta + np.sqrt(np.maximum(disc, 0)))
    F = (disc > 0) & (vg >= phys.VG_MIN) | (d < 1e-6)
    vg = np.maximum(vg, 0.5)
    T = np.where(d > 1e-6, d / (vg * 60.0), 0.0)
    return phys.P_CRUISE * T, T, F


class Prob:
    """node 0 = station, nodes 1..n tasks.  start: dict per drone (pos node index or None, e_used, t_ready, cap)."""

    def __init__(self, E, T, F, svc, hen, rel, dl, w, caps, t_ready, margin, t_now, t_day=600.0, c_ot=1.0):
        self.E, self.T, self.F = E, T, F
        self.svc, self.hen, self.rel, self.dl, self.w = svc, hen, rel, dl, w
        self.caps, self.t_ready = caps, t_ready
        self.m = margin; self.t_now = t_now; self.t_day = t_day; self.c_ot = c_ot
        self.n = len(svc) - 1

    def trip_energy(self, trip):
        E = self.E; e = 0.0; p = 0
        for j in trip:
            e += E[p, j] + self.hen[j]; p = j
        return e + E[p, 0]

    def trip_ok(self, trip, cap):
        p = 0
        for j in trip:
            if not self.F[p, j]:
                return False
            p = j
        if not self.F[p, 0]:
            return False
        return self.trip_energy(trip) * (1 + self.m) <= cap + 1e-9

    def sched_cost(self, routes):
        """routes[d] = list of trips.  cost = 0.5*minutes + lateness penalties + overtime."""
        c = 0.0
        for dI, trips in enumerate(routes):
            t = self.t_ready[dI]
            for tr in trips:
                p = 0
                for j in tr:
                    t += self.T[p, j]; t = max(t, self.rel[j]); t += self.svc[j]
                    c += TIME_COST * (self.T[p, j] + self.svc[j])
                    if self.w[j] > 0:
                        c += self.w[j] * max(0.0, t - self.dl[j])
                    p = j
                t += self.T[p, 0]; c += TIME_COST * self.T[p, 0]
            c += self.c_ot * max(0.0, t - self.t_day)
        return c


def insert_all(P, routes, todo, deadline):
    for j in sorted(todo, key=lambda j: (P.dl[j] if P.w[j] > 0 else 1e9, -P.T[0, j])):
        best = None
        base = P.sched_cost(routes)
        for dI, trips in enumerate(routes):
            cap = P.caps[dI]
            for ti in range(len(trips) + 1):
                if ti == len(trips):
                    cand = [j]
                    if not P.trip_ok(cand, cap):
                        continue
                    new = trips + [cand]
                    nr = routes[:dI] + [new] + routes[dI + 1:]
                    c = P.sched_cost(nr) - base
                    if best is None or c < best[0]:
                        best = (c, nr)
                    continue
                tr = trips[ti]
                for pos in range(len(tr) + 1):
                    cand = tr[:pos] + [j] + tr[pos:]
                    if not P.trip_ok(cand, cap):
                        continue
                    nr_trips = trips[:ti] + [cand] + trips[ti + 1:]
                    nr = routes[:dI] + [nr_trips] + routes[dI + 1:]
                    c = P.sched_cost(nr) - base
                    if best is None or c < best[0]:
                        best = (c, nr)
        if best is None:
            # infeasible now (forecast): park as a singleton trip on drone 0 (will be re-planned later)
            routes = [routes[0] + [[j]]] + routes[1:]
        else:
            routes = best[1]
        if time.time() > deadline:
            pass
    return routes


def local_search(P, routes, deadline, max_pass=4):
    cur = P.sched_cost(routes)
    for _ in range(max_pass):
        improved = False
        # relocate: remove one task and re-insert best
        flat = [(dI, ti, pos) for dI, trips in enumerate(routes) for ti, tr in enumerate(trips) for pos in range(len(tr))]
        for dI, ti, pos in flat:
            if time.time() > deadline:
                return routes
            if ti >= len(routes[dI]) or pos >= len(routes[dI][ti]):
                continue
            j = routes[dI][ti][pos]
            tr = routes[dI][ti][:pos] + routes[dI][ti][pos + 1:]
            trips = routes[dI][:ti] + ([tr] if tr else []) + routes[dI][ti + 1:]
            rem = routes[:dI] + [trips] + routes[dI + 1:]
            nr = insert_all(P, rem, [j], deadline)
            c = P.sched_cost(nr)
            if c < cur - 1e-6:
                routes, cur, improved = nr, c, True
        # 2-opt inside each trip
        for dI, trips in enumerate(routes):
            for ti, tr in enumerate(trips):
                if len(tr) < 3:
                    continue
                for a in range(len(tr) - 1):
                    for b in range(a + 1, len(tr)):
                        cand = tr[:a] + tr[a:b + 1][::-1] + tr[b + 1:]
                        if not P.trip_ok(cand, P.caps[dI]):
                            continue
                        nt = trips[:ti] + [cand] + trips[ti + 1:]
                        nr = routes[:dI] + [nt] + routes[dI + 1:]
                        c = P.sched_cost(nr)
                        if c < cur - 1e-6:
                            routes, cur, improved, trips, tr = nr, c, True, nt, cand
        # merge two trips of the same drone if feasible
        for dI, trips in enumerate(routes):
            k = 0
            while k < len(trips) - 1:
                cand = trips[k] + trips[k + 1]
                if P.trip_ok(cand, P.caps[dI]):
                    nt = trips[:k] + [cand] + trips[k + 2:]
                    nr = routes[:dI] + [nt] + routes[dI + 1:]
                    c = P.sched_cost(nr)
                    if c < cur - 1e-6:
                        routes, cur, improved, trips = nr, c, True, nt
                        continue
                k += 1
        if not improved:
            break
    return routes


def solve(P, init_routes=None, budget_s=0.03):
    deadline = time.time() + budget_s
    routes = [[] for _ in P.caps] if init_routes is None else [list(map(list, r)) for r in init_routes]
    placed = {j for r in routes for tr in r for j in tr}
    todo = [j for j in range(1, P.n + 1) if j not in placed]
    routes = insert_all(P, routes, todo, deadline)
    routes = local_search(P, routes, deadline)
    return routes
