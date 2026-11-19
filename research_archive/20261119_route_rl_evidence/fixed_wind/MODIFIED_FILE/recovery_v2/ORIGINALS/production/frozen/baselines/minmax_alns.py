#!/usr/bin/env python3
"""STRONG NON-RL: bottleneck-targeted min-max ALNS for the S contract.

Contract
--------
Objective : minimise M_return = max_station max_slot(cumulative duty).
Constraint: complete original-feasible solution; station_types and
            target_station frozen to the anchor; full-map cost
            C(candidate) <= C(anchor) + 1e-7 (epsilon = 0), where
            C = fixed + time_cost * operating_minutes.  Because "fixed" is
            a constant of the frozen station types, the cost cap is exactly a
            *global operating-minute budget*; every move is therefore gated by
            an incremental duration delta, never by a full rescore.

Search structure (all moves are physical route decisions, no operator choice)
----------------------------------------------------------------------------
1. init      : anchor routes intact, or the same trips repacked by LPT.
2. harvest   : per-station travelling-distance descent (merge / relocate /
               swap / exact trip re-sequencing).  Monotone: never increases
               M_return and never increases the global operating minutes, so it
               can only create *credit* (cap slack) for later balance moves.
3. rebalance : exact slot partition of the intact trips of one station
               (subset DP, cost-neutral) - the strongest possible free move.
4. min-max   : targeted destroy/repair on the bottleneck (station, slot):
               borrow targets/trips from the loaded slot, pay for the extra
               round trip out of the global credit bank.
5. certify   : the finished solution is rescored by the independent
               scorer.validate_candidate(epsilon=0); if it is late or
               inadmissible the run falls back to the anchor and says so.

Determinism: fixed seed, fixed candidate order, no wall-clock branch except
the single deadline check at loop boundaries, and every random draw comes from
random.Random(seed) in a fixed call order.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import pathlib
import random
import sys
from time import perf_counter

EPS = 1e-7            # scorer PHYSICS_TOLERANCE
COST_TOL = 1e-7       # scorer absolute cost tolerance
ENERGY_EPS = 1e-12   # constant-wind engine energy units
SEARCH_MARGIN = 1e-7  # operating-minute safety margin kept inside the cap


# --------------------------------------------------------------------------
# plan representation
# --------------------------------------------------------------------------
class Trip:
    """One non-empty trip: ordered target sequence plus cached metrics."""

    __slots__ = ("slot", "seq", "dur", "en", "length")

    def __init__(self, slot, seq, dur, en, length):
        self.slot = slot
        self.seq = seq          # tuple of target ids, visiting order
        self.dur = dur          # travel minutes + service minutes
        self.en = en            # flight energy + target energy
        self.length = length    # metres

    @property
    def size(self):
        return len(self.seq)


class Ctx:
    """Per-instance immutable geometry cache (standard library only)."""

    __slots__ = ("inst", "p", "speed", "fe", "X", "Y", "S", "E", "stx", "sty",
                 "kind", "cap", "dlim", "rad", "slots_of", "tg", "time_cost")

    def __init__(self, instance, types, target_station):
        self.inst = instance
        p = instance.params
        self.p = p
        self.speed = p.speed
        self.fe = p.flight_energy
        self.time_cost = p.time_cost
        self.X = {n.id: n.x for n in instance.targets}
        self.Y = {n.id: n.y for n in instance.targets}
        self.S = {n.id: n.service for n in instance.targets}
        self.E = {n.id: n.energy for n in instance.targets}
        self.stx = [n.x for n in instance.stations]
        self.sty = [n.y for n in instance.stations]
        self.kind = list(types)
        self.cap = (p.large_battery, p.small_battery)
        # scorer.py:175-186 -> the cumulative-duty limit depends on station kind
        # only (both slots of an open large station use large_duration).
        self.dlim = [p.small_duration if k == 1 else
                     (p.large_duration if k == 2 else 0.0) for k in types]
        # scorer.py:154 -> coverage radius depends on station kind only.
        self.rad = [p.large_radius if k == 2 else p.small_radius for k in types]
        self.slots_of = [(1,) if k == 1 else ((0, 1) if k == 2 else ()) for k in types]
        self.tg = [[] for _ in types]
        for nid, si in target_station.items():
            self.tg[si].append(nid)

    # -- geometry ---------------------------------------------------------
    def tour(self, si, seq):
        X = self.X
        Y = self.Y
        sx = self.stx[si]
        sy = self.sty[si]
        px = sx
        py = sy
        length = 0.0
        for nid in seq:
            nx = X[nid]
            ny = Y[nid]
            length += math.hypot(px - nx, py - ny)
            px = nx
            py = ny
        length += math.hypot(px - sx, py - sy)
        return length

    def metrics(self, si, seq):
        X = self.X
        Y = self.Y
        S = self.S
        E = self.E
        sx = self.stx[si]
        sy = self.sty[si]
        px = sx
        py = sy
        length = 0.0
        svc = 0.0
        en = 0.0
        for nid in seq:
            nx = X[nid]
            ny = Y[nid]
            length += math.hypot(px - nx, py - ny)
            px = nx
            py = ny
            svc += S[nid]
            en += E[nid]
        length += math.hypot(px - sx, py - sy)
        # scorer.py:167 -> energy = travel_MINUTES * flight_energy + target energy
        travel = length / self.speed
        return travel + svc, travel * self.fe + en, length

    def make_trip(self, si, slot, seq):
        seq = tuple(seq)
        dur, en, length = self.metrics(si, seq)
        return Trip(slot, seq, dur, en, length)

    def best_order(self, si, seq):
        """Exact re-sequencing for small trips, 2-opt otherwise."""
        seq = list(seq)
        k = len(seq)
        if k <= 1:
            return tuple(seq)
        if k <= 5:
            best = None
            best_len = None
            for perm in itertools.permutations(seq):
                ln = self.tour(si, perm)
                if best_len is None or ln < best_len - 1e-12:
                    best_len = ln
                    best = perm
            return tuple(best)
        return self._two_opt(si, seq)

    def _two_opt(self, si, seq):
        seq = list(seq)
        improved = True
        while improved:
            improved = False
            base = self.tour(si, seq)
            for i in range(0, len(seq) - 1):
                for j in range(i + 1, len(seq)):
                    cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                    if self.tour(si, cand) < base - 1e-9:
                        seq = cand
                        base = self.tour(si, cand)
                        improved = True
        return tuple(seq)


class Plan:
    """Mutable station-joint route plan with O(1) duty/total bookkeeping."""

    __slots__ = ("ctx", "types", "slots", "duty", "stot", "total")

    def __init__(self, ctx, types):
        self.ctx = ctx
        self.types = tuple(types)
        n = len(types)
        self.slots = [[[], []] for _ in range(n)]
        self.duty = [[0.0, 0.0] for _ in range(n)]
        self.stot = [0.0] * n
        self.total = 0.0

    def add(self, si, slot, seq):
        trip = self.ctx.make_trip(si, slot, seq)
        if not trip.seq:
            return None
        self.slots[si][slot].append(trip)
        self.duty[si][slot] += trip.dur
        self.stot[si] += trip.dur
        self.total += trip.dur
        return trip

    def M(self):
        m = 0.0
        for d in self.duty:
            if d[0] > m:
                m = d[0]
            if d[1] > m:
                m = d[1]
        return m

    def bottleneck(self):
        best_d = -1.0
        best = (0.0, 0, 0)
        for si, d in enumerate(self.duty):
            for slot in (0, 1):
                if d[slot] > best_d + 1e-15:
                    best_d = d[slot]
                    best = (d[slot], si, slot)
        return best

    def m_other(self, si):
        m = 0.0
        for sj, d in enumerate(self.duty):
            if sj == si:
                continue
            if d[0] > m:
                m = d[0]
            if d[1] > m:
                m = d[1]
        return m

    def station_mk(self, si):
        d = self.duty[si]
        return d[0] if d[0] >= d[1] else d[1]

    def clone(self):
        other = Plan.__new__(Plan)
        other.ctx = self.ctx
        other.types = self.types
        other.slots = [[list(self.slots[si][0]), list(self.slots[si][1])]
                       for si in range(len(self.types))]
        other.duty = [list(d) for d in self.duty]
        other.stot = list(self.stot)
        other.total = self.total
        return other

    def restore(self, other):
        self.slots = [[list(a), list(b)] for a, b in other.slots]
        self.duty = [list(d) for d in other.duty]
        self.stot = list(other.stot)
        self.total = other.total

    def to_solution(self, template):
        routes = []
        for si in range(len(self.types)):
            station = []
            for slot in (0, 1):
                station.append([[int(n) for n in t.seq] for t in self.slots[si][slot]
                                if t.seq])
            routes.append(station)
        out = dict(template)
        out["station_types"] = [int(k) for k in self.types]
        out["routes"] = routes
        return out


def plan_from_solution(ctx, solution):
    plan = Plan(ctx, solution["station_types"])
    for si, station in enumerate(solution["routes"]):
        for slot, trips in enumerate(station):
            for seq in trips:
                if seq:
                    plan.add(si, slot, list(seq))
    return plan


# --------------------------------------------------------------------------
# initial solutions
# --------------------------------------------------------------------------
def lpt_plan(ctx, anchor):
    """Longest-processing-time repack of intact anchor trips (cost-neutral)."""
    base = plan_from_solution(ctx, anchor.solution())
    plan = Plan(ctx, anchor.station_types)
    for si, kind in enumerate(anchor.station_types):
        if kind == 0:
            continue
        slots = ctx.slots_of[si]
        trips = [t for slot in (0, 1) for t in base.slots[si][slot]]
        if not trips:
            continue
        order = sorted(range(len(trips)),
                       key=lambda i: (-trips[i].dur, trips[i].seq))
        loads = [0.0, 0.0]
        placed = [[], []]
        failed = False
        for idx in order:
            trip = trips[idx]
            cands = []
            for slot in slots:
                if trip.en > ctx.cap[slot] + ENERGY_EPS:
                    continue
                if loads[slot] + trip.dur > ctx.dlim[si] + EPS:
                    continue
                cands.append(slot)
            if not cands:
                failed = True
                break
            slot = min(cands, key=lambda s: (loads[s], s))
            placed[slot].append(trip.seq)
            loads[slot] += trip.dur
        if failed:
            for slot in slots:
                for t in base.slots[si][slot]:
                    plan.add(si, slot, t.seq)
            continue
        for slot in slots:
            for seq in placed[slot]:
                plan.add(si, slot, seq)
    return plan


# --------------------------------------------------------------------------
# atomic commit with incremental cost/feasibility accounting
# --------------------------------------------------------------------------
def _probe(plan, si, new_slots, cap_total):
    """(station_total, station_makespan, new_global_total) or None."""
    ctx = plan.ctx
    kind = ctx.kind[si]
    slots = ctx.slots_of[si]
    dlim = ctx.dlim[si] + EPS
    cap = ctx.cap
    total = 0.0
    mk = 0.0
    for slot in (0, 1):
        trips = new_slots[slot]
        if trips:
            if slot not in slots:
                return None
            c = cap[slot] + ENERGY_EPS
            d = 0.0
            for trip in trips:
                if trip.en > c:
                    return None
                d += trip.dur
            if d > dlim:
                return None
            total += d
            if d > mk:
                mk = d
    new_total = plan.total - plan.stot[si] + total
    if new_total > cap_total:
        return None
    return total, mk, new_total


def _install(plan, si, new_slots, total):
    plan.slots[si][0] = new_slots[0]
    plan.slots[si][1] = new_slots[1]
    d0 = 0.0
    for t in new_slots[0]:
        d0 += t.dur
    d1 = 0.0
    for t in new_slots[1]:
        d1 += t.dur
    plan.duty[si][0] = d0
    plan.duty[si][1] = d1
    plan.total = plan.total - plan.stot[si] + total
    plan.stot[si] = total


def attempt(plan, si, new_slots, m_other, cap_total, stats, trace, stage, label,
            m_cap=None):
    """Acceptance rule for the min-max objective.

    1. any move that lowers the global M_return inside the cost cap is taken;
    2. otherwise a move that lowers this station's makespan for free
       (no extra operating minutes) is taken - it is progress towards
       untying a shared bottleneck at zero cost;
    3. otherwise a move that lowers this station's makespan while spending
       credit is taken only when the station actually sits at the bottleneck
       level, i.e. credit is only ever spent on the binding slot;
    4. otherwise a cost-reducing move is taken when global makespan is
       unchanged, including a rise in a non-bottleneck station's makespan.
    """
    res = _probe(plan, si, new_slots, cap_total)
    stats["evaluated"] += 1
    if res is None:
        return False
    total, mk, _new_total = res
    cur_mk = plan.station_mk(si)
    cur_tot = plan.stot[si]
    cur_M = m_other if m_other > cur_mk else cur_mk
    new_M = m_other if m_other > mk else mk
    if m_cap is not None:
        # makespan-ceiling mode: minimise operating minutes subject to M <= m_cap
        ok = new_M <= m_cap + 1e-12 and total < cur_tot - 1e-12
    elif new_M < cur_M - 1e-12:
        ok = True
    elif new_M > cur_M + 1e-12:
        ok = False
    elif mk < cur_mk - 1e-12:
        ok = (total <= cur_tot + 1e-12) or (cur_mk >= cur_M - 1e-12)
    elif mk > cur_mk + 1e-12:
        # Global M is already known to be unchanged. A non-bottleneck station
        # may trade its unused time margin for strictly lower global cost.
        # This lexicographic (global M, total) move funds later splits.
        ok = total < cur_tot - 1e-12
    else:
        ok = total < cur_tot - 1e-12
    if not ok:
        return False
    _install(plan, si, new_slots, total)
    if trace is not None:
        trace.append({"stage": stage, "move": label, "station": si,
                      "M": max(m_other, mk), "station_total": total,
                      "global_total": plan.total, "accepted": True})
    return True

# --------------------------------------------------------------------------
# deadline accounting
# --------------------------------------------------------------------------
class Budget:
    __slots__ = ("t0", "deadline", "clock", "checks", "hit")

    def __init__(self, t0, deadline, clock):
        self.t0 = t0
        self.deadline = deadline
        self.clock = clock
        self.checks = 0
        self.hit = False

    def over(self):
        self.checks += 1
        if self.clock() - self.t0 > self.deadline:
            self.hit = True
            return True
        return False


# --------------------------------------------------------------------------
# candidate generators (deterministic order, lazy)
# --------------------------------------------------------------------------
def _order(ctx, si, seq):
    return ctx.best_order(si, seq)


def _trip_lists(plan, si):
    return plan.slots[si][0], plan.slots[si][1]


def gen_rebalance(ctx, plan, si, budget=None):
    """Every feasible two-slot partition of the intact trips (cost-neutral)."""
    slots = ctx.slots_of[si]
    if len(slots) < 2:
        return
    l0, l1 = _trip_lists(plan, si)
    trips = l0 + l1
    k = len(trips)
    if k < 2 or k > 15:
        return
    dlim = ctx.dlim[si]
    cap0 = ctx.cap[0] + ENERGY_EPS
    cap1 = ctx.cap[1] + ENERGY_EPS
    ok1 = [t.en <= cap1 for t in trips]
    # forced to slot 0 when the small battery cannot carry the intact trip
    forced = [not o for o in ok1]
    best = None
    best_mk = None
    total = 0.0
    for t in trips:
        total += t.dur
    for mask in range(1 << k):
        if not mask & 63 and budget is not None and budget.over():
            return
        d0 = 0.0
        bad = False
        for i in range(k):
            # A set bit goes to LD (slot0); heavy trips must set that bit.
            if forced[i] and not (mask >> i & 1):
                bad = True
                break
            if mask >> i & 1:
                d0 += trips[i].dur
        if bad or d0 > dlim + EPS:
            continue
        d1 = total - d0
        if d1 > dlim + EPS:
            continue
        mk = d0 if d0 >= d1 else d1
        if best_mk is None or mk < best_mk - 1e-12:
            best_mk = mk
            best = mask
    if best is None:
        return
    n0 = [trips[i] for i in range(k) if best >> i & 1]
    n1 = [trips[i] for i in range(k) if not best >> i & 1]
    yield ("rebalance_exact", [n0, n1])


def gen_relocate(ctx, plan, si):
    """Move one target into another trip of the same station (best insertion)."""
    for sa in ctx.slots_of[si]:
        for ia, A in enumerate(plan.slots[si][sa]):
            if A.size < 2:
                continue
            for target in A.seq:
                rest = tuple(x for x in A.seq if x != target)
                newA = ctx.make_trip(si, sa, _order(ctx, si, rest))
                for sb in ctx.slots_of[si]:
                    for ib, B in enumerate(plan.slots[si][sb]):
                        if sa == sb and ia == ib:
                            continue
                        for pos in range(B.size + 1):
                            seq = B.seq[:pos] + (target,) + B.seq[pos:]
                            newB = ctx.make_trip(si, sb, seq)
                            n0 = list(plan.slots[si][0])
                            n1 = list(plan.slots[si][1])
                            if sa == 0:
                                n0[ia] = newA
                            else:
                                n1[ia] = newA
                            if sb == 0:
                                n0[ib] = newB
                            else:
                                n1[ib] = newB
                            yield ("relocate", [n0, n1])
                    # a first-class route decision: the target gets its own trip
                    if len(ctx.slots_of[si]) == 2 or sb == 1:
                        newB = ctx.make_trip(si, sb, (target,))
                        n0 = list(plan.slots[si][0])
                        n1 = list(plan.slots[si][1])
                        if sa == 0:
                            n0[ia] = newA
                        else:
                            n1[ia] = newA
                        if sb == 0:
                            n0.append(newB)
                        else:
                            n1.append(newB)
                        yield ("relocate_new_trip", [n0, n1])


def gen_swap(ctx, plan, si):
    """Swap two targets between two different trips of the same station."""
    locs = []
    for slot in ctx.slots_of[si]:
        for idx, trip in enumerate(plan.slots[si][slot]):
            for pos in range(trip.size):
                locs.append((slot, idx, pos, trip.seq[pos]))
    for a in range(len(locs)):
        sa, ia, pa, ta = locs[a]
        for b in range(a + 1, len(locs)):
            sb, ib, pb, tb = locs[b]
            if sa == sb and ia == ib:
                continue
            A = plan.slots[si][sa][ia]
            B = plan.slots[si][sb][ib]
            seqA = tuple(tb if i == pa else x for i, x in enumerate(A.seq))
            seqB = tuple(ta if i == pb else x for i, x in enumerate(B.seq))
            newA = ctx.make_trip(si, sa, _order(ctx, si, seqA))
            newB = ctx.make_trip(si, sb, _order(ctx, si, seqB))
            n0 = list(plan.slots[si][0])
            n1 = list(plan.slots[si][1])
            if sa == 0:
                n0[ia] = newA
            else:
                n1[ia] = newA
            if sb == 0:
                n0[ib] = newB
            else:
                n1[ib] = newB
            yield ("swap", [n0, n1])


def gen_merge(ctx, plan, si):
    """Merge two trips of the same station into one (saves a round trip)."""
    refs = []
    for slot in ctx.slots_of[si]:
        for idx in range(len(plan.slots[si][slot])):
            refs.append((slot, idx))
    for a in range(len(refs)):
        sa, ia = refs[a]
        for b in range(a + 1, len(refs)):
            sb, ib = refs[b]
            A = plan.slots[si][sa][ia]
            B = plan.slots[si][sb][ib]
            if A.size + B.size > 6:
                continue
            seq = _order(ctx, si, A.seq + B.seq)
            for slot in ctx.slots_of[si]:
                merged = ctx.make_trip(si, slot, seq)
                n0 = list(plan.slots[si][0])
                n1 = list(plan.slots[si][1])
                if slot == 0:
                    n0.append(merged)
                else:
                    n1.append(merged)
                drop = {(sa, ia), (sb, ib)}
                keep0 = [t for i, t in enumerate(plan.slots[si][0]) if (0, i) not in drop]
                keep1 = [t for i, t in enumerate(plan.slots[si][1]) if (1, i) not in drop]
                if slot == 0:
                    keep0.append(merged)
                else:
                    keep1.append(merged)
                yield ("merge", [keep0, keep1])


def gen_split(ctx, plan, si):
    """Split one trip into two, keeping or changing slot (spends credit)."""
    if len(ctx.slots_of[si]) == 1:
        targets_slots = (ctx.slots_of[si][0],)
    else:
        targets_slots = ctx.slots_of[si]
    for sa in ctx.slots_of[si]:
        for ia, A in enumerate(plan.slots[si][sa]):
            if A.size < 2:
                continue
            for cut in range(1, A.size):
                left = A.seq[:cut]
                right = A.seq[cut:]
                for sb in targets_slots:
                    t1 = ctx.make_trip(si, sa, _order(ctx, si, left))
                    t2 = ctx.make_trip(si, sb, _order(ctx, si, right))
                    n0 = list(plan.slots[si][0])
                    n1 = list(plan.slots[si][1])
                    if sa == 0:
                        n0[ia] = t1
                        if sb == 0:
                            n0.append(t2)
                        else:
                            n1.append(t2)
                    else:
                        n1[ia] = t1
                        if sb == 0:
                            n0.append(t2)
                        else:
                            n1.append(t2)
                    yield ("split", [n0, n1])


def gen_move_trip(ctx, plan, si):
    """Move a whole intact trip to the other slot (cost-neutral)."""
    if len(ctx.slots_of[si]) < 2:
        return
    for sa in (0, 1):
        sb = 1 - sa
        for ia, A in enumerate(plan.slots[si][sa]):
            moved = ctx.make_trip(si, sb, A.seq)
            n0 = list(plan.slots[si][0])
            n1 = list(plan.slots[si][1])
            if sa == 0:
                n0.pop(ia)
            else:
                n1.pop(ia)
            if sb == 0:
                n0.append(moved)
            else:
                n1.append(moved)
            yield ("move_trip_slot", [n0, n1])


# --------------------------------------------------------------------------
# descent kernels
# --------------------------------------------------------------------------
def _first_improve(plan, si, gen, m_other, cap_total, stats, trace, budget, stage,
                   m_cap=None):
    for label, new_slots in gen:
        if budget.over():
            return False
        if attempt(plan, si, new_slots, m_other, cap_total, stats, trace, stage, label,
                   m_cap=m_cap):
            return True
    return False


ORDERS = {
    "balance": ("rebalance", "move_trip", "split", "relocate", "swap", "merge"),
    "travel": ("rebalance", "merge", "relocate", "swap", "move_trip", "split"),
}


def _makers(plan, si, budget, order):
    ctx = plan.ctx
    table = {
        "rebalance": lambda: gen_rebalance(ctx, plan, si, budget),
        "move_trip": lambda: gen_move_trip(ctx, plan, si),
        "split": lambda: gen_split(ctx, plan, si),
        "relocate": lambda: gen_relocate(ctx, plan, si),
        "swap": lambda: gen_swap(ctx, plan, si),
        "merge": lambda: gen_merge(ctx, plan, si),
    }
    return [table[name] for name in order]


def station_descent(plan, si, m_other, cap_total, stats, trace, budget, stage,
                    max_rounds=60, order=None, m_cap=None):
    """VND at one station under the (M_return, station_total) lexicographic key."""
    improved_any = False
    for _ in range(max_rounds):
        if budget.over():
            break
        moved = False
        makers = _makers(plan, si, budget, order or ORDERS["balance"])
        for make in makers:
            if _first_improve(plan, si, make(), m_other, cap_total,
                              stats, trace, budget, stage, m_cap=m_cap):
                moved = True
                improved_any = True
                break
        if not moved:
            break
    return improved_any

# --------------------------------------------------------------------------
# destroy / repair (min-max ALNS)
# --------------------------------------------------------------------------
def _repair(ctx, si, n0, n1, removed, dlim):
    """Greedy reinsertion of removed targets minimising (station makespan, total)."""
    duty = [0.0, 0.0]
    for t in n0:
        duty[0] += t.dur
    for t in n1:
        duty[1] += t.dur
    slots = ctx.slots_of[si]
    for target in removed:
        best = None
        for slot in slots:
            arr = n0 if slot == 0 else n1
            cap = ctx.cap[slot] + ENERGY_EPS
            other = duty[1 - slot]
            for i in range(len(arr)):
                T = arr[i]
                base_d = duty[slot] - T.dur
                for pos in range(T.size + 1):
                    seq = T.seq[:pos] + (target,) + T.seq[pos:]
                    nt = ctx.make_trip(si, slot, seq)
                    if nt.en > cap:
                        continue
                    nd = base_d + nt.dur
                    if nd > dlim + EPS:
                        continue
                    mk = nd if nd >= other else other
                    tot = duty[0] + duty[1] - T.dur + nt.dur
                    key = (mk, tot)
                    if best is None or key < best[0]:
                        best = (key, slot, i, nt)
            nt = ctx.make_trip(si, slot, (target,))
            if nt.en <= cap:
                nd = duty[slot] + nt.dur
                if nd <= dlim + EPS:
                    mk = nd if nd >= other else other
                    tot = duty[0] + duty[1] + nt.dur
                    key = (mk, tot)
                    if best is None or key < best[0]:
                        best = (key, slot, -1, nt)
        if best is None:
            return None
        _, slot, idx, nt = best
        arr = n0 if slot == 0 else n1
        if idx < 0:
            arr.append(nt)
            duty[slot] += nt.dur
        else:
            duty[slot] += nt.dur - arr[idx].dur
            arr[idx] = nt
    return n0, n1


def _strip(n0, n1, drop, si, ctx):
    """Remove the given (slot, trip_index, target) entries and re-sequence."""
    work = [[], []]
    for slot in (0, 1):
        src = n0 if slot == 0 else n1
        for i, T in enumerate(src):
            keep = [x for x in T.seq if (slot, i, x) not in drop]
            if keep:
                if len(keep) == T.size:
                    work[slot].append(T)
                else:
                    work[slot].append(ctx.make_trip(si, slot, keep))
    return work


def _ruin_trials(plan, si, slot, rng, stats):
    """Deterministic + seeded destroy sets for one station."""
    src = plan.slots[si][slot]
    if not src:
        return []
    entries = [(slot, i, p, src[i].seq[p]) for i in range(len(src))
               for p in range(src[i].size)]
    if not entries:
        return []
    order = sorted(entries, key=lambda e: (-src[e[1]].dur, e[1], e[2]))
    trials = []
    for r in (2, 3, 4, 5, 6):
        if r > len(order):
            break
        trials.append(("near", order[:r]))
        trials.append(("rand", sorted(rng.sample(order, r), key=lambda e: (e[1], e[2]))))
    whole = [e for e in entries if src[e[1]].size <= 3]
    if 1 <= len(whole) <= 8:
        trials.append(("whole_small", whole))
    return trials


def gen_ruin(plan, si, slot, rng):
    """Destroy a subset of the loaded slot and repair it greedily."""
    ctx = plan.ctx
    dlim = ctx.dlim[si]
    src = plan.slots[si][slot]
    out = []
    seen = set()
    for name, chosen in _ruin_trials(plan, si, slot, rng, None):
        key = tuple(sorted((e[0], e[1], e[3]) for e in chosen))
        if key in seen:
            continue
        seen.add(key)
        drop = set(key)
        work = _strip(list(plan.slots[si][0]), list(plan.slots[si][1]), drop, si, ctx)
        targets = [e[2] for e in key]
        targets.sort(key=lambda t: (-math.hypot(ctx.X[t] - ctx.stx[si],
                                                ctx.Y[t] - ctx.sty[si]), t))
        res = _repair(ctx, si, work[0], work[1], targets, dlim)
        if res is None:
            continue
        out.append(("ruin_%s_r%d" % (name, len(chosen)), [res[0], res[1]]))
    return out


def ruin_step(plan, si, cap_total, stats, rng, m_limit):
    """One atomic destroy/repair perturbation; caller decides to keep it."""
    loaded = 0 if plan.duty[si][0] >= plan.duty[si][1] else 1
    if not plan.slots[si][loaded] and plan.slots[si][1 - loaded]:
        loaded = 1 - loaded
    trials = _ruin_trials(plan, si, loaded, rng, stats)
    rng.shuffle(trials)
    ctx = plan.ctx
    dlim = ctx.dlim[si]
    for name, chosen in trials:
        stats["evaluated"] += 1
        key = set((e[0], e[1], e[3]) for e in chosen)
        work = _strip(list(plan.slots[si][0]), list(plan.slots[si][1]), key, si, ctx)
        targets = [e[3] for e in chosen]
        rng.shuffle(targets)
        res = _repair(ctx, si, work[0], work[1], targets, dlim)
        if res is None:
            continue
        probe = _probe(plan, si, [res[0], res[1]], cap_total)
        if probe is None:
            continue
        total, mk, _ = probe
        if max(plan.m_other(si), mk) > m_limit + 1e-9:
            continue
        _install(plan, si, [res[0], res[1]], total)
        return name
    return None


# --------------------------------------------------------------------------
# solve
# --------------------------------------------------------------------------
def _scorer():
    """Late import of the frozen scoring stack (independent referee)."""
    mod = sys.modules.get("scorer")
    if mod is not None:
        return mod
    root = pathlib.Path(os.environ.get(
        "TAKEOVER_ROOT", "/root/lunwen_engineering/20261112_takeover_completion"))
    code = root / "code"
    for extra in (str(code / "route_rl_research/20261103/return_makespan"),
                  str(code / "reproduction/reviewer_package_semfix/lrphsd")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import scorer
    return scorer


def fixed_cost(params, types):
    total = 0.0
    for k in types:
        if k == 1:
            total += params.small_station_cost + params.small_drone_cost
        elif k == 2:
            total += (params.large_station_cost + params.small_drone_cost
                      + params.large_drone_cost)
    return total


def vnd_all(plan, cap_total, stats, trace, budget, stage="vnd", max_passes=6,
            order=None):
    """VND over every station, loaded stations first."""
    moved_any = False
    for _ in range(max_passes):
        if budget.over():
            break
        station_order = sorted(range(len(plan.types)), key=lambda s: -plan.station_mk(s))
        moved = False
        for si in station_order:
            if plan.types[si] == 0:
                continue
            if budget.over():
                return moved_any
            if station_descent(plan, si, plan.m_other(si), cap_total, stats, trace,
                               budget, stage, order=order):
                moved = True
                moved_any = True
        if not moved:
            break
    return moved_any


def cost_descent(plan, m_cap, cap_probe, stats, trace, budget, max_passes=6):
    """Minimise operating minutes subject to M_return <= m_cap (epsilon-constraint)."""
    for _ in range(max_passes):
        if budget.over():
            break
        station_order = sorted(range(len(plan.types)), key=lambda s: -plan.stot[s])
        moved = False
        for si in station_order:
            if plan.types[si] == 0:
                continue
            if budget.over():
                return moved
            if station_descent(plan, si, plan.m_other(si), cap_probe, stats, trace,
                               budget, "cost", max_rounds=30,
                               order=("merge", "relocate", "swap", "rebalance"),
                               m_cap=m_cap):
                moved = True
        if not moved:
            break
    return moved


def recover_cost(plan, cap_probe, cap_hard, stats, trace, budget, max_passes=4):
    """Travel-only descent used to fund a balance move that overspent credit."""
    for _ in range(max_passes):
        if budget.over() or plan.total <= cap_hard:
            break
        moved = False
        station_order = sorted(range(len(plan.types)),
                               key=lambda s: -plan.station_mk(s))
        for si in station_order:
            if plan.types[si] == 0:
                continue
            if budget.over():
                return plan.total <= cap_hard
            if station_descent(plan, si, plan.m_other(si), cap_probe, stats, trace,
                               budget, "recover", max_rounds=30,
                               order=("merge", "relocate", "swap", "rebalance")):
                moved = True
        if not moved:
            break
    return plan.total <= cap_hard


def perturb(plan, stations, cap_total, stats, rng, m_limit):
    """Apply atomic destroy/repair steps at the given stations."""
    moved = 0
    order = list(stations)
    rng.shuffle(order)
    for si in order:
        if ruin_step(plan, si, cap_total, stats, rng, m_limit) is not None:
            moved += 1
    return moved


def alns(plan, best, best_any, cap_search, cap_hard, stats, trace, budget, rng,
         stagnation_limit=220, max_iters=40000):
    """Iterated ruin-and-recreate with record-to-record acceptance.

    The cost cap is a hard wall; M_return may drift up by a decaying threshold
    so that the search can leave a local optimum, and the best incumbent is
    always kept separately.
    """
    stagnation = 0
    iters = 0
    active = [si for si in range(len(plan.types)) if plan.types[si] != 0
              and (plan.slots[si][0] or plan.slots[si][1])]
    if not active:
        return best, best_any
    while iters < max_iters and stagnation < stagnation_limit:
        if budget.over():
            break
        iters += 1
        M_now, si_peak, _slot = plan.bottleneck()
        thr = 0.02 * best.M() * max(0.0, 1.0 - stagnation / float(stagnation_limit))
        snap = plan.clone()
        stations = [si_peak] if rng.random() < 0.6 else [active[rng.randrange(len(active))]]
        if stagnation > 30:
            stations.append(active[rng.randrange(len(active))])
        stats["ruin_steps"] += 1
        if not perturb(plan, stations, cap_search, stats, rng, best.M() + thr):
            plan.restore(snap)
            stagnation += 1
            continue
        station_descent(plan, si_peak, plan.m_other(si_peak), cap_search, stats, trace,
                        budget, "alns")
        for si in stations:
            station_descent(plan, si, plan.m_other(si), cap_search, stats, trace,
                            budget, "alns")
        if stagnation and stagnation % 64 == 0:
            vnd_all(plan, cap_search, stats, trace, budget, "alns_vnd", max_passes=2)
        key = (plan.M(), plan.total)
        bkey = (best.M(), best.total)
        if plan.M() > bkey[0] + thr + 1e-9 or plan.total > cap_search + 1e-12:
            plan.restore(snap)
            stagnation += 1
            continue
        if best_any is None or key < (best_any.M(), best_any.total):
            best_any = plan.clone()
        if key < bkey and plan.total <= cap_hard + 1e-12:
            best = plan.clone()
            stagnation = 0
            trace.append({"stage": "alns_improve", "move": "ruin_repair",
                          "station": si_peak, "M": best.M(),
                          "station_total": best.total, "global_total": best.total,
                          "accepted": True})
        elif plan.M() < bkey[0] - 1e-9 and plan.total > cap_hard:
            rec = plan.clone()
            stats["recover_calls"] += 1
            if recover_cost(rec, cap_search, cap_hard, stats, trace, budget):
                if (rec.M(), rec.total) < (best.M(), best.total):
                    best = rec.clone()
                    plan.restore(rec)
                    stagnation = 0
                    trace.append({"stage": "alns_improve", "move": "funded_split",
                                  "station": si_peak, "M": best.M(),
                                  "station_total": best.total,
                                  "global_total": best.total, "accepted": True})
                else:
                    stagnation += 1
            else:
                stagnation += 1
        else:
            stagnation += 1
        if stagnation and stagnation % 80 == 79:
            plan = best_any.clone()
        if stagnation and stagnation % 48 == 47 and best_any is not None \
                and best_any.total > cap_hard:
            rec = best_any.clone()
            stats["recover_calls"] += 1
            if recover_cost(rec, cap_search, cap_hard, stats, trace, budget):
                if (rec.M(), rec.total) < (best.M(), best.total):
                    best = rec.clone()
                    trace.append({"stage": "alns_improve", "move": "funded_recover",
                                  "station": -1, "M": best.M(),
                                  "station_total": best.total,
                                  "global_total": best.total, "accepted": True})
    stats["iters"] = iters
    return best, best_any


def solve(instance, anchor, budget_s, *, started_at=None, clock=perf_counter,
          seed=20261112, reserve_frac=0.14, context_factory=None, candidate_validator=None):
    """Run the bottleneck-targeted min-max search and certify the incumbent."""
    if type(budget_s) not in (int, float) or not math.isfinite(budget_s) or budget_s <= 0:
        raise ValueError("budget_s must be finite and positive")
    t0 = clock() if started_at is None else started_at
    anchor.verify(instance)

    types = tuple(int(k) for k in anchor.station_types)
    ctx = (context_factory or Ctx)(instance, types, dict(anchor.target_station))
    p = instance.params
    anchor_op = (anchor.cost - fixed_cost(p, types)) / p.time_cost
    cap_total = anchor_op + SEARCH_MARGIN
    base = anchor.solution()

    stats = {"evaluated": 0, "ruin_steps": 0, "iters": 0,
             "recover_calls": 0}
    trace = []
    hist = []
    stage_M = []

    plan = plan_from_solution(ctx, base)
    stage_M.append(["anchor", plan.M(), plan.total, round(clock() - t0, 3)])
    try:
        lpt = lpt_plan(ctx, anchor)
        if (lpt.M(), lpt.total) < (plan.M(), plan.total):
            plan = lpt
        stage_M.append(["init_best", plan.M(), plan.total, round(clock() - t0, 3)])
    except Exception as exc:                      # noqa: BLE001 - recorded, not hidden
        stage_M.append(["lpt_failed", plan.M(), plan.total, round(clock() - t0, 3)])
        stats["lpt_error"] = repr(exc)

    reserve = max(0.30, reserve_frac * budget_s)
    deadline = budget_s - reserve   # relative elapsed seconds
    budget = Budget(t0, deadline, clock)
    rng = random.Random(seed)

    start = plan.clone()
    best = plan.clone()
    slack = min(8.0, max(0.5, 0.005 * anchor_op))
    cap_work = cap_total + slack
    stats["elastic_slack_minutes"] = slack
    for variant in ("balance", "travel"):
        if budget.over():
            break
        cand = start.clone()
        vnd_all(cand, cap_total, stats, trace, budget, "vnd_" + variant,
                max_passes=6, order=ORDERS[variant])
        stage_M.append(["vnd_" + variant, cand.M(), cand.total,
                        round(clock() - t0, 3)])
        if (cand.M(), cand.total) < (best.M(), best.total):
            best = cand.clone()
    plan = best.clone()
    best_any = best.clone()
    # budget-annealed elastic starts: a temporary overspend lets the search cross
    # the region where a balance move must be paid for before it is funded.
    for level in (0.34, 0.67, 1.0):
        if budget.over():
            break
        cap_level = cap_total + level * slack
        for variant in ("balance", "travel"):
            if budget.over():
                break
            cand = start.clone()
            vnd_all(cand, cap_level, stats, trace, budget,
                    "elastic%d_%s" % (int(level * 100), variant),
                    max_passes=6, order=ORDERS[variant])
            stage_M.append(["elastic%d_%s" % (int(level * 100), variant),
                            cand.M(), cand.total, round(clock() - t0, 3)])
            if (cand.M(), cand.total) < (best_any.M(), best_any.total):
                best_any = cand.clone()
            rec = cand.clone()
            if cand.total > cap_total and recover_cost(rec, cap_level, cap_total,
                                                       stats, trace, budget):
                if (rec.M(), rec.total) < (best.M(), best.total):
                    best = rec.clone()
                    stage_M.append(["funded%d_%s" % (int(level * 100), variant),
                                    best.M(), best.total, round(clock() - t0, 3)])
    if best_any.M() < best.M() - 1e-9:
        lo = best_any.M()
        hi = best.M()
        for frac in (0.0, 0.25, 0.5, 0.75):
            if budget.over() or lo >= hi:
                break
            m_cap = lo + frac * (hi - lo)
            rec = best_any.clone()
            cost_descent(rec, m_cap, cap_work, stats, trace, budget)
            stage_M.append(["cost_at_%.2f" % m_cap, rec.M(), rec.total,
                            round(clock() - t0, 3)])
            if rec.total <= cap_total + 1e-12 and (rec.M(), rec.total) < (best.M(), best.total):
                best = rec.clone()
                break
    hist.append({"t": round(clock() - t0, 3), "M": best.M(), "total": best.total,
                 "stage": "post_vnd", "evals": stats["evaluated"]})

    if not budget.over():
        plan = best_any.clone()
        best, best_any = alns(plan, best, best_any, cap_work, cap_total, stats,
                              trace, budget, rng)
        stage_M.append(["alns", best.M(), best.total, round(clock() - t0, 3)])

    if not budget.over():
        plan = best.clone()
        vnd_all(plan, cap_total, stats, trace, budget, "final", max_passes=8)
        if (plan.M(), plan.total) < (best.M(), best.total):
            best = plan.clone()
        stage_M.append(["final", best.M(), best.total, round(clock() - t0, 3)])

    plan = best.clone()
    hist.append({"t": round(clock() - t0, 3), "M": best.M(), "total": best.total,
                 "stage": "final", "evals": stats["evaluated"]})

    accepted = len(trace)
    sol = plan.to_solution(base)
    validate_candidate = candidate_validator or _scorer().validate_candidate
    score = validate_candidate(instance, sol, anchor, epsilon=0.0,
                               cost_tolerance=COST_TOL)
    elapsed = clock() - t0
    fallback_reason = None
    if not score["admissible"]:
        fallback_reason = "raw_inadmissible"
    elif score["M_return"] is None or score["M_return"] > anchor.makespan:
        fallback_reason = "raw_worse_than_anchor"
    elif elapsed > budget_s:
        fallback_reason = "raw_validation_late"

    chosen = sol
    chosen_score = score
    if fallback_reason is not None:
        chosen = base
        chosen_score = validate_candidate(instance, chosen, anchor, epsilon=0.0,
                                          cost_tolerance=COST_TOL)
        status = ("ONTIME_VALID" if chosen_score["admissible"]
                  and clock() - t0 <= budget_s else "NO_ONTIME_VALID_OUTPUT")
    else:
        status = "ONTIME_VALID"

    wall = clock() - t0
    return {
        "schema": "strong_nonrl_minmax_alns_v1",
        "status": status,
        "method": "minmax_alns",
        "M_return": chosen_score["M_return"],
        "cost": chosen_score["cost"],
        "admissible": bool(chosen_score["admissible"]),
        "wall_s": round(wall, 4),
        "output_ready_elapsed_s": round(wall, 4),
        "budget_s": budget_s,
        "over_budget": wall > budget_s,
        "fallback_used": fallback_reason is not None,
        "fallback_reason": fallback_reason,
        "search_timed_out": bool(budget.hit),
        "accepted_moves": accepted,
        "evaluated_candidates": stats["evaluated"],
        "ruin_steps": stats["ruin_steps"],
        "recover_calls": stats["recover_calls"],
        "alns_iterations": stats["iters"],
        "deadline_checks": budget.checks,
        "bottleneck_history": hist,
        "accepted_move_trace": trace,
        "stage_M": stage_M,
        "final_station_duty": [[round(d[0], 6), round(d[1], 6)] for d in plan.duty],
        "final_station_kind": list(plan.types),
        "final_slot_trip_counts": [[len(plan.slots[si][0]), len(plan.slots[si][1])]
                                   for si in range(len(plan.types))],
        "final_operating_minutes": plan.total,
        "anchor_M_return": anchor.makespan,
        "anchor_cost": anchor.cost,
        "delta_M_return_pct": (None if chosen_score["M_return"] is None
                               or not anchor.makespan
                               else 100.0 * (chosen_score["M_return"] - anchor.makespan)
                               / anchor.makespan),
        "cost_delta_vs_anchor": (None if chosen_score["cost"] is None
                                 else chosen_score["cost"] - anchor.cost),
        "solution": chosen,
        "solution_sha256": chosen_score.get("solution_sha256"),
        "seed": seed,
        "bounds": {"anchor_operating_minutes": anchor_op,
                   "operating_cap_minutes": cap_total,
                   "operating_minutes_used": chosen_score.get("operating_minutes")},
        "issues": list(chosen_score.get("issues", [])) + list(chosen_score.get("domain_issues", [])),
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _stack(root):
    """Import the frozen scoring stack exactly as the other harness drivers do."""
    code = root / "code"
    rm = code / "route_rl_research/20261103/return_makespan"
    for extra in (str(rm), str(code / "reproduction/reviewer_package_semfix/lrphsd"),
                  str(rm / "g23/nonrl_baseline")):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import problem            # noqa: E402
    import scorer             # noqa: E402
    return problem, scorer


def _load_maps(root, names):
    index = json.loads((root / "g3_pop/population_index.json").read_text())
    maps = [m for m in index["maps"] if m["status"] == "generated"]
    if names and names != "all":
        keep = {x.strip() for x in names.split(",") if x.strip()}
        maps = [m for m in maps if m["name"] in keep]
    return maps


def _ref_rows(root):
    path = root / "g3_pop/NONRL_RESULTS.json"
    refs = {}
    if path.exists():
        for row in json.loads(path.read_text())["rows"]:
            refs[(row.get("map"), row.get("method"), row.get("budget_s"))] = row
    return refs


def cmd_run(args, problem, scorer):
    root = pathlib.Path(args.root)
    out = pathlib.Path(args.out)
    maps = _load_maps(root, args.maps)
    refs = _ref_rows(root)
    rows = []
    if out.exists() and not args.force:
        rows = json.loads(out.read_text()).get("rows", [])
    done = {(r.get("map"), r.get("budget_s")) for r in rows}
    log = open(args.log, "a") if args.log else None

    def emit(row):
        rows.append(row)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": "takeover_g3_strong_nonrl_results_v1",
                   "generated_at_utc": None, "rows": rows,
                   "reference": "g3_pop/NONRL_RESULTS.json (lpt, joint_minmax)",
                   "seed": args.seed}
        out.write_text(json.dumps(payload, indent=2, sort_keys=True,
                                  allow_nan=False) + chr(10))

    for m in maps:
        name = m["name"]
        adir = root / "g3_pop/author" / name
        run_json = adir / "RUN.json"
        if not run_json.exists():
            continue
        run = json.loads(run_json.read_text())
        if not run.get("anchor_eligible"):
            continue
        inst = problem.read_instance(pathlib.Path(m["path"]))
        anchor = scorer.CostAnchor.from_solution(inst, json.loads((adir / "solution.json").read_text()))
        anchor.verify(inst)
        for budget in [float(x) for x in args.budgets.split(",")]:
            if (name, budget) in done:
                continue
            t0 = perf_counter()
            try:
                res = solve(inst, anchor, budget, started_at=t0, seed=args.seed)
                err = None
            except Exception as exc:              # noqa: BLE001 - failures are data
                res, err = None, repr(exc)
            wall = perf_counter() - t0
            lpt = refs.get((name, "lpt", 6.0))
            joint = refs.get((name, "joint_minmax", budget))
            row = {
                "map": name, "sites": m["sites"], "targets": m["targets"],
                "instance_sha256": inst.sha256,
                "budget_s": budget,
                "wall_s": round(wall, 4),
                "seed": args.seed,
                "anchor_M_return": anchor.makespan,
                "anchor_cost": anchor.cost,
                "lpt_M_return": None if not lpt else lpt.get("chosen_M_return"),
                "lpt_cost": None if not lpt else lpt.get("chosen_cost"),
                "joint_minmax_M_return": None if not joint else joint.get("chosen_M_return"),
                "joint_minmax_cost": None if not joint else joint.get("chosen_cost"),
                "joint_minmax_status": None if not joint else joint.get("status"),
            }
            if err:
                row.update({"status": "ERROR", "error": err, "M_return": None,
                            "cost": None, "admissible": False})
            else:
                for key in ("status", "M_return", "cost", "admissible",
                            "accepted_moves", "evaluated_candidates",
                            "fallback_used", "fallback_reason", "over_budget",
                            "search_timed_out", "delta_M_return_pct",
                            "cost_delta_vs_anchor", "output_ready_elapsed_s",
                            "solution_sha256", "stage_M", "bounds",
                            "deadline_checks", "issues"):
                    row[key] = res[key]
                row["bottleneck_history"] = res["bottleneck_history"][:40]
                row["accepted_move_trace"] = res["accepted_move_trace"][:80]
                row["solution"] = res["solution"]
                if row.get("M_return") is not None and anchor.makespan:
                    row["delta_vs_lpt_pct"] = (
                        None if not row.get("lpt_M_return")
                        else 100.0 * (row["M_return"] - row["lpt_M_return"]) / row["lpt_M_return"])
            emit(row)
            def _f(value, spec="%.6f"):
                return "na" if value is None else spec % value
            line = ("%s b=%.0f %s M=%s cost=%s wall=%.3f evals=%s acc=%s "
                    "dM_anchor=%s dM_lpt=%s" % (
                        name, budget, row.get("status"),
                        _f(row.get("M_return")), _f(row.get("cost")), wall,
                        row.get("evaluated_candidates"), row.get("accepted_moves"),
                        _f(row.get("delta_M_return_pct"), "%.3f%%"),
                        _f(row.get("delta_vs_lpt_pct"), "%.3f%%")))
            print(line, flush=True)
            if log:
                log.write(line + chr(10))
                log.flush()
    if log:
        log.close()
    return 0


def cmd_analyze(args, problem, scorer):
    root = pathlib.Path(args.root)
    for m in _load_maps(root, args.maps):
        adir = root / "g3_pop/author" / m["name"]
        run_json = adir / "RUN.json"
        if not run_json.exists():
            continue
        if not json.loads(run_json.read_text()).get("anchor_eligible"):
            print(m["name"], "ANCHOR_NOT_ELIGIBLE")
            continue
        inst = problem.read_instance(pathlib.Path(m["path"]))
        anchor = scorer.CostAnchor.from_solution(inst, json.loads((adir / "solution.json").read_text()))
        for budget in [float(x) for x in args.budgets.split(",")]:
            t0 = perf_counter()
            res = solve(inst, anchor, budget, started_at=t0, seed=args.seed)
            print("%-10s b=%2.0f %s M=%9.5f dM=%7.3f%% wall=%5.3f evals=%6d acc=%3d "
                  "stages=%s" % (
                      m["name"], budget, res["status"], res["M_return"],
                      res["delta_M_return_pct"], res["wall_s"],
                      res["evaluated_candidates"], res["accepted_moves"],
                      [(s[0], round(s[1], 3)) for s in res["stage_M"]]), flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("run", "analyze"))
    ap.add_argument("--root", default="/root/lunwen_engineering/20261112_takeover_completion")
    ap.add_argument("--out", default="")
    ap.add_argument("--log", default="")
    ap.add_argument("--maps", default="all")
    ap.add_argument("--budgets", default="6,12")
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    if not args.out:        args.out = str(pathlib.Path(args.root) / "g3_pop/STRONG_NONRL_RESULTS.json")
    problem, scorer = _stack(pathlib.Path(args.root))
    if args.command == "run":
        return cmd_run(args, problem, scorer)
    return cmd_analyze(args, problem, scorer)


if __name__ == "__main__":
    raise SystemExit(main())
