#!/usr/bin/env python3
"""exact_minmax.py -- exact minimum-M_return certificates on the frozen S contract.

Model (verbatim from scorer.py:111-217 and problem.py:6-71; every constant is
read from the instance parameters, nothing is hard-coded):

  station s with kind k owns a FIXED target set T_s (anchor.target_station);
  a trip is a closed tour station -> perm(B) -> station with
      travel = tour_length / speed
      energy(B) = travel * flight_energy + sum_{n in B} n.energy  <= capacity(slot) + 1e-7
  slot duty   = sum over its trips of (travel + sum service)    <= limit(kind) + 1e-7
  capacity(0) = large_battery, capacity(1) = small_battery
  kind 1 owns only slot 1; kind 2 owns slots {0,1}; kind 0 owns nothing.

  station makespan = max over its slots of slot duty
  station operating = sum over its trips of duration
  M_return = max over stations of makespan
  cost     = fixed + time_cost * sum_s operating_s
  admissible <=> original feasible AND station_types + target_station unchanged
                 AND cost <= anchor.cost + 1e-7   (epsilon = 0)

Exact reduction (proof in EXACT_MINMAX_REFERENCE.md sec.2):
  (i)   for a target subset B the tour that minimises both duration and energy is
        the TSP tour of B, so one Held-Karp table suffices for every slot;
  (ii)  for a fixed assignment of target SETS to slots the best partition of a
        slot's set is the min-total-duration partition d_j(U): both station
        objectives (makespan = max of slot loads, operating = sum of slot loads)
        are monotone nondecreasing in every slot load, so a longer partition is
        dominated;
  (iii) station frontier = { (max(d0(U), d1(T minus U)), d0(U)+d1(T minus U)) : U subset T }.
  d_j is a set-partition DP over 3^n transitions; TSP is Held-Karp over 2^n*n^2.
  Global optimum: min T such that sum_s min{op : M_s <= T} <= cap_op, scanned over
  the (finite) candidate set of station makespan values -- exact, not heuristic.

Anything with a station above --max-n-exact is reported as UNKNOWN with a proven
lower bound (never as an optimum).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import pathlib
import random
import sys
import time

R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
RM = C / "route_rl_research/20261103/return_makespan"
sys.path.insert(0, str(RM))
sys.path.insert(0, str(C / "reproduction/reviewer_package_semfix/lrphsd"))
import problem  # noqa: E402
import scorer  # noqa: E402

INF = float("inf")
RNG = random.Random(20261112)   # deterministic sampling seed for the dominance guard
PHYS = 1e-7            # scorer.PHYSICS_TOLERANCE: energy / duty / coverage gate
COST_TOL = 1e-7        # scorer.COST_TOLERANCE: absolute, on cost
CMP = 1e-9             # required agreement between our arithmetic and the scorer


def sha256_file(path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(scorer.canonical_json(obj).encode()).hexdigest()


# ----------------------------------------------------------------------------- TSP
def held_karp(n, d0, dd):
    """Shortest closed tour through a subset. d0[i] = dist(station, i)."""
    size = 1 << n
    dp = [[INF] * n for _ in range(size)]
    par = [[-1] * n for _ in range(size)]
    for j in range(n):
        dp[1 << j][j] = d0[j]
    for mask in range(1, size):
        row = dp[mask]
        for j in range(n):
            base = row[j]
            if base == INF:
                continue
            dj = dd[j]
            for k in range(n):
                if mask & (1 << k):
                    continue
                nm = mask | (1 << k)
                val = base + dj[k]
                if val < dp[nm][k]:
                    dp[nm][k] = val
                    par[nm][k] = j
    tsp = [0.0] * size
    last = [-1] * size
    for mask in range(1, size):
        bv, bl = INF, -1
        for j in range(n):
            if mask & (1 << j):
                v = dp[mask][j] + d0[j]
                if v < bv:
                    bv, bl = v, j
        tsp[mask] = bv
        last[mask] = bl
    return tsp, par, last


def tour_order(mask, par, last):
    j, m, seq = last[mask], mask, []
    while j != -1:
        seq.append(j)
        pj = par[m][j]
        m ^= (1 << j)
        j = pj
    seq.reverse()
    return seq


# ------------------------------------------------------------------ partition DP
def partition_dp(n, dur, energy, cap, limit):
    """best[mask] = min total duration of partitioning mask into trips that are
    energy-feasible on this slot; choice[] stores a block for reconstruction."""
    size = 1 << n
    best = [INF] * size
    choice = [-1] * size
    best[0] = 0.0
    cap_gate = cap + PHYS
    lim = limit + PHYS
    transitions = 0
    for mask in range(1, size):
        low = mask & (-mask)
        rest = mask ^ low
        s = rest
        bv, bc = INF, -1
        while True:
            block = s | low
            if energy[block] <= cap_gate:
                transitions += 1
                prev = best[mask ^ block]
                if prev < INF:
                    v = dur[block] + prev
                    if v < bv:
                        bv, bc = v, block
            if s == 0:
                break
            s = (s - 1) & rest
        if bv <= lim:
            best[mask] = bv
            choice[mask] = bc
    return best, choice, transitions


def split_blocks(mask, best, choice):
    blocks = []
    while mask:
        b = choice[mask]
        if b <= 0:
            raise RuntimeError("partition reconstruction failed")
        blocks.append(b)
        mask ^= b
    return blocks


# ------------------------------------------------------------- independent checks
def independent_eval(inst, solution):
    """Recompute the contract with raw hypot arithmetic, without scorer.py."""
    p = inst.params
    targets = {n.id: n for n in inst.targets}
    fixed = op = 0.0
    per_station = []
    issues = []
    seen = {}
    for si, st in enumerate(inst.stations):
        kind = solution["station_types"][si]
        if kind == 1:
            fixed += p.small_station_cost + p.small_drone_cost
        elif kind == 2:
            fixed += p.large_station_cost + p.small_drone_cost + p.large_drone_cost
        limit = p.small_duration if kind == 1 else p.large_duration
        loads = []
        for slot in (0, 1):
            if kind == 1 and slot == 0 and solution["routes"][si][slot]:
                issues.append("large_drone_at_small_station:%d" % si)
            duty = 0.0
            for trip in solution["routes"][si][slot]:
                if not trip:
                    continue
                seq = [st] + [targets[t] for t in trip] + [st]
                length = 0.0
                for a, b in zip(seq, seq[1:]):
                    length += math.hypot(a.x - b.x, a.y - b.y)
                travel = length / p.speed
                svc = sum(targets[t].service for t in trip)
                dur = travel + svc
                energy = travel * p.flight_energy + sum(targets[t].energy for t in trip)
                cap = p.large_battery if slot == 0 else p.small_battery
                if energy > cap + PHYS:
                    issues.append("energy:%d:%d" % (si, slot))
                for t in trip:
                    if math.hypot(st.x - targets[t].x, st.y - targets[t].y) > (
                            p.small_radius if kind == 1 else p.large_radius) + PHYS:
                        issues.append("coverage:%d" % t)
                    seen[t] = seen.get(t, 0) + 1
                duty += dur
            if duty > limit + PHYS:
                issues.append("cumulative_duty:%d:%d" % (si, slot))
            loads.append(duty)
            op += duty
        per_station.append(max(loads))
    for t in targets:
        if seen.get(t, 0) != 1:
            issues.append("coverage_count:%d" % t)
    return {"cost": fixed + p.time_cost * op, "operating_minutes": op,
            "M_return": max(per_station, default=0.0),
            "station_makespan": per_station, "issues": issues}


def tsp_lower_bound(coords):
    """Valid lower bound on the TSP tour through coords[0] (station) + the rest.

    LB = max(MST(spanning tree <= tour - one edge), 2 * max distance to station).
    """
    n = len(coords)
    if n <= 1:
        return 0.0
    d = [[math.hypot(coords[i][0] - coords[j][0], coords[i][1] - coords[j][1])
          for j in range(n)] for i in range(n)]
    # Prim MST on all nodes
    in_tree = [False] * n
    best = [INF] * n
    best[0] = 0.0
    mst = 0.0
    for _ in range(n):
        u, bu = -1, INF
        for i in range(n):
            if not in_tree[i] and best[i] < bu:
                bu, u = best[i], i
        in_tree[u] = True
        mst += bu
        for v in range(n):
            if not in_tree[v] and d[u][v] < best[v]:
                best[v] = d[u][v]
    far = max(d[0][1:]) if n > 1 else 0.0
    return max(mst, 2.0 * far)


def brute_force_frontier(coords, svc, en, p, kind, allowed_slots):
    """Independent exponential reference: all set partitions (RGS) x all slot
    assignments, with each block's tour solved by permutation enumeration."""
    n = len(svc)
    d0 = [math.hypot(coords[0][0] - coords[i + 1][0], coords[0][1] - coords[i + 1][1])
          for i in range(n)]
    dd = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            dd[i][j] = math.hypot(coords[i + 1][0] - coords[j + 1][0],
                                  coords[i + 1][1] - coords[j + 1][1])

    def block_dur_energy(block):
        if len(block) == 1:
            length = 2.0 * d0[block[0]]
        else:
            length = INF
            for perm in itertools.permutations(block):
                tot = d0[perm[0]]
                for a, b in zip(perm, perm[1:]):
                    tot += dd[a][b]
                tot += d0[perm[-1]]
                if tot < length:
                    length = tot
        travel = length / p.speed
        return travel + sum(svc[i] for i in block), travel * p.flight_energy + sum(en[i] for i in block)

    lim = p.small_duration if kind == 1 else p.large_duration
    caps = {0: p.large_battery, 1: p.small_battery}
    points = set()
    nparts = 0
    blocks = []

    def rec(i):
        nonlocal nparts
        if i == n:
            nparts += 1
            de = [block_dur_energy(b) for b in blocks]
            k = len(blocks)
            # pick the cheapest (makespan, operating) over slot assignments
            for assign in itertools.product(allowed_slots, repeat=k):
                loads = {0: 0.0, 1: 0.0}
                ok = True
                for bi, slot in enumerate(assign):
                    dur_b, en_b = de[bi]
                    if en_b > caps[slot] + PHYS:
                        ok = False
                        break
                    loads[slot] += dur_b
                if not ok:
                    continue
                if any(loads[s] > lim + PHYS for s in allowed_slots):
                    continue
                m = max(loads[s] for s in allowed_slots)
                op = sum(loads[s] for s in allowed_slots)
                points.add((round(m, 9), round(op, 9)))
            return
        for b in range(len(blocks)):
            blocks[b].append(i)
            rec(i + 1)
            blocks[b].pop()
        blocks.append([i])
        rec(i + 1)
        blocks.pop()

    rec(0)
    # Pareto filter
    pts = sorted(points)
    front, best_op = [], INF
    for m, op in pts:
        if op < best_op - 1e-12:
            front.append((m, op))
            best_op = op
    return front, nparts


def station_raw_loads(inst, si, kind, routes_slot):
    """(makespan, operating) of one station's reconstructed trips, raw hypot."""
    p = inst.params
    st = inst.stations[si]
    targets = {n.id: n for n in inst.targets}
    loads, op = [], 0.0
    for slot in (0, 1):
        duty = 0.0
        for trip in routes_slot[slot]:
            seq = [st] + [targets[t] for t in trip] + [st]
            length = 0.0
            for a, b in zip(seq, seq[1:]):
                length += math.hypot(a.x - b.x, a.y - b.y)
            travel = length / p.speed
            cap = p.large_battery if slot == 0 else p.small_battery
            energy = travel * p.flight_energy + sum(targets[t].energy for t in trip)
            assert energy <= cap + PHYS, "reconstructed trip violates energy"
            duty += travel + sum(targets[t].service for t in trip)
        loads.append(duty)
        op += duty
    return max(loads), op


def check_frontier_achievable(inst, si, kind, row):
    """Every Pareto point must be realised by the reconstructed trips."""
    worst = 0.0
    for pt in row["frontier"]:
        routes_slot, _m, _o = build_solution(inst, si, kind, row, tuple(pt))
        m, op = station_raw_loads(inst, si, kind, routes_slot)
        worst = max(worst, abs(m - pt[0]), abs(op - pt[1]))
    return worst


def sample_dominance(inst, si, kind, row, rng, samples=2000):
    """Random feasible configurations must all be dominated by the frontier:
    an independent (one-sided) guard against an over-optimistic frontier."""
    p = inst.params
    n = len(row["_tids"])
    tsp = row["_tsp"]
    dur = row["_dur"]
    allowed = [1] if kind == 1 else [0, 1]
    lim = p.small_duration if kind == 1 else p.large_duration
    caps = {0: p.large_battery, 1: p.small_battery}
    front = row["frontier"]
    bad = 0
    tested = 0
    for _ in range(samples):
        bits = [rng.random() < 0.5 for _ in range(n)]
        U = 0
        for i, b in enumerate(bits):
            if b:
                U |= 1 << i
        loads = {0: 0.0, 1: 0.0}
        ok = True
        for slot, mask in ((0, U), (1, ((1 << n) - 1) ^ U)):
            if slot not in allowed:
                if mask:
                    ok = False
                continue
            remaining = [i for i in range(n) if mask >> i & 1]
            rng.shuffle(remaining)
            while remaining:
                cut = rng.randint(1, len(remaining))
                block = 0
                for i in remaining[:cut]:
                    block |= 1 << i
                if row["_energy"][block] > caps[slot] + PHYS:
                    ok = False
                    break
                loads[slot] += dur[block]
                remaining = remaining[cut:]
            if not ok:
                break
        if not ok or any(loads[s] > lim + PHYS for s in allowed):
            continue
        if kind == 1:
            loads[0] = 0.0
        m = max(loads[s] for s in allowed)
        op = sum(loads[s] for s in allowed)
        tested += 1
        if not any(fm <= m + 1e-9 and fop <= op + 1e-9 for fm, fop in front):
            bad += 1
    return {"samples_tested": tested, "violations": bad, "ok": bad == 0}


# ------------------------------------------------------------------ station solve
def solve_station(inst, si, kind, tids, max_n_exact, do_bruteforce):
    p = inst.params
    st = inst.stations[si]
    n = len(tids)
    out = {"station": si, "kind": kind, "n_targets": n, "exact": False,
           "frontier": [], "lower_bound": None, "bruteforce": None,
           "_tids": tids}
    if kind == 0 or n == 0:
        out.update({"exact": True, "frontier": [[0.0, 0.0]], "dp_transitions": 0,
                    "splits": 1, "note": "empty station"})
        return out
    allowed = [1] if kind == 1 else [0, 1]
    limit = p.small_duration if kind == 1 else p.large_duration  # kind-based, both slots
    caps = {0: p.large_battery, 1: p.small_battery}
    coords = [(st.x, st.y)] + [(inst.nodes[t].x, inst.nodes[t].y) for t in tids]
    svc = [inst.nodes[t].service for t in tids]
    en = [inst.nodes[t].energy for t in tids]
    d0 = [math.hypot(coords[0][0] - coords[i + 1][0], coords[0][1] - coords[i + 1][1])
          for i in range(n)]
    assert all(x <= (p.small_radius if kind == 1 else p.large_radius) + PHYS for x in d0)
    out["tsp_lb_m"] = tsp_lower_bound(coords)
    out["makespan_lb"] = ((out["tsp_lb_m"] / p.speed + sum(svc)) / len(allowed))
    if n > max_n_exact:
        out["lower_bound"] = {
            "tsp_lb_m": out["tsp_lb_m"], "tsp_lb_min": out["tsp_lb_m"] / p.speed,
            "sum_service_min": sum(svc), "slots": len(allowed),
            "makespan_lb": out["makespan_lb"],
            "formula": "(tsp_lb_m/speed + sum_service)/n_slots  <=  makespan_s",
            "note": "not exact: station target count above the exact cap"}
        return out
    dd = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            dd[i][j] = math.hypot(coords[i + 1][0] - coords[j + 1][0],
                                  coords[i + 1][1] - coords[j + 1][1])

    tsp, par, last = held_karp(n, d0, dd)
    size = 1 << n
    dur = [0.0] * size
    energy = [0.0] * size
    for mask in range(1, size):
        travel = tsp[mask] / p.speed
        s = sum(svc[i] for i in range(n) if mask >> i & 1)
        dur[mask] = travel + s
        energy[mask] = travel * p.flight_energy + sum(en[i] for i in range(n) if mask >> i & 1)
    out["held_karp_states"] = size * n
    out["solve_note"] = "exact reduction: TSP per subset + set-partition DP per slot + subset split"

    tables = {}
    transitions = 0
    for slot in allowed:
        best, choice, tr = partition_dp(n, dur, energy, caps[slot], limit)
        tables[slot] = (best, choice)
        transitions += tr
    out["dp_transitions"] = transitions

    full = size - 1
    points = []
    splits = 0
    if kind == 1:
        b, _ = tables[1]
        if b[full] < INF:
            points.append((b[full], b[full], 0))
        splits = 1
    else:
        b0, _ = tables[0]
        b1, _ = tables[1]
        for U in range(size):
            a = b0[U]
            if a == INF:
                continue
            c = b1[full ^ U]
            if c == INF:
                continue
            splits += 1
            points.append((max(a, c), a + c, U))
    points.sort()
    front, best_op, chosen = [], INF, []
    for m, op, U in points:
        if op < best_op - 1e-12:
            front.append([m, op])
            chosen.append(U)
            best_op = op
    out.update({"exact": True, "frontier": front, "splits": splits,
                "frontier_size": len(front), "raw_point_count": len(points),
                "slot_capacity": {str(s): caps[s] for s in allowed},
                "slot_duty_limit": limit,
                "enumeration": "held_karp states 2^n*n=%d; partition DP transitions=%d; "
                               "subset splits=%d" % (size * n, transitions, splits)})
    out["_chosen_split"] = chosen
    out["_tables"] = tables
    out["_dur"] = dur
    out["_energy"] = energy
    out["_tsp"] = tsp
    out["_par"] = par
    out["_last"] = last
    out["_svc_sum"] = sum(svc)
    out["_tsp_lb"] = tsp_lower_bound(coords)
    out["_ms_lb"] = ((out["_tsp_lb"] / p.speed + sum(svc)) / len(allowed))
    out["frontier_achievable_max_abs_diff"] = check_frontier_achievable(
        inst, si, kind, out)
    out["sample_dominance"] = sample_dominance(inst, si, kind, out, RNG)

    if do_bruteforce:
        bf, nparts = brute_force_frontier(coords, svc, en, p, kind, allowed)
        ours = [(round(m, 9), round(op, 9)) for m, op in front]
        match = ours == bf
        out["bruteforce"] = {"partitions": nparts, "frontier_size": len(bf),
                             "match": bool(match),
                             "max_abs_M_diff": max([abs(a[0] - b[0]) for a, b in zip(ours, bf)] or [0.0])
                             if len(ours) == len(bf) else None,
                             "ours_head": ours[:4], "bf_head": bf[:4]}
    return out


# ------------------------------------------------------------------- global solve
def solve_global(station_rows, cap_op):
    fronts = [[tuple(x) for x in row["frontier"]] for row in station_rows]
    cands = sorted({m for f in fronts for (m, _op) in f})
    for T in cands:
        total = 0.0
        pick = []
        ok = True
        for f in fronts:
            bv, bp = INF, None
            for (m, op) in f:
                if m <= T + 1e-12 and op < bv:
                    bv, bp = op, (m, op)
            if bv == INF:
                ok = False
                break
            total += bv
            pick.append(bp)
        if ok and total <= cap_op:
            return T, total, pick
    return None, None, None


def build_solution(inst, si, kind, row, pick_point):
    """Reconstruct the concrete trips for one station at a Pareto point."""
    tids = row["_tids"]
    n = len(tids)
    size = 1 << n
    full = size - 1
    allowed = [1] if kind == 1 else [0, 1]
    tables = row["_tables"]
    # pick the split that realises this exact (M, op) point
    target_M = pick_point[0]
    target_op = pick_point[1]
    best_U = None
    for U, (m, op) in zip(row["_chosen_split"], row["frontier"]):
        if abs(m - target_M) <= CMP and abs(op - target_op) <= CMP:
            b0 = tables[0][0][U] if kind == 2 else 0.0
            b1 = tables[1][0][full ^ U] if kind == 2 else tables[1][0][full]
            if kind == 2 and (b0 == INF or b1 == INF):
                continue
            best_U = U
            break
    if best_U is None:
        raise RuntimeError("cannot reconstruct station %d" % si)
    if kind == 2:
        parts = {0: split_blocks(best_U, *tables[0]), 1: split_blocks(full ^ best_U, *tables[1])}
    else:
        parts = {0: [], 1: split_blocks(full, *tables[1])}
    routes = [[], []]
    loads = []
    for slot in (0, 1):
        if slot not in allowed:
            loads.append(0.0)
            continue
        duty = 0.0
        for block in parts[slot]:
            order = tour_order(block, row["_par"], row["_last"])
            routes[slot].append([tids[i] for i in order])
            duty += row["_dur"][block]
        loads.append(duty)
    return routes, max(loads), sum(loads)


# ------------------------------------------------------------------------- driver
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(R / "g3_pop"))
    ap.add_argument("--maps", default="3x10_o1,3x15_o1,3x20_o1,4x20_o1,4x25_o1,4x30_o1")
    ap.add_argument("--max-n-exact", type=int, default=12)
    ap.add_argument("--time-limit", type=float, default=600.0)
    ap.add_argument("--selfcheck-max-n", type=int, default=8)
    ap.add_argument("--intent-only", action="store_true")
    ap.add_argument("--intent-name", default="EXACT_INTENT.json")
    ap.add_argument("--results-name", default="EXACT_RESULTS.json")
    ap.add_argument("--exclude-from-summary", default="4x20_o1")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    maps = [x.strip() for x in args.maps.split(",") if x.strip()]
    index = json.loads((out / "population_index.json").read_text())
    by_name = {m["name"]: m for m in index["maps"]}

    # ---- INTENT first, before any solve -------------------------------------
    intent = {
        "schema": "takeover_exact_minmax_intent_v1",
        "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "registered_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "objective": "min M_return  s.t.  cost <= anchor.cost + 1e-7, epsilon=0, "
                     "station_types and target_station fixed to the anchor",
        "method": {
            "per_station": "exact: Held-Karp TSP per target subset; set-partition DP "
                           "d_j(U) (3^n transitions) per slot; station frontier over all "
                           "subset splits U of the station's target set",
            "global": "exact step-function scan: min T with sum_s min{op: M_s<=T} <= cap_op",
            "non_exact_rule": "any station with n_targets > max_n_exact is reported "
                              "not_exact with a proven makespan lower bound; the map "
                              "then reports UNKNOWN, never an optimum",
            "selfcheck": "independent exponential reference (all set partitions x all slot "
                         "assignments, tours by permutation enumeration) for stations with "
                         "n <= selfcheck_max_n",
        },
        "budget": {"per_map_wall_limit_s": args.time_limit,
                   "max_n_exact": args.max_n_exact,
                   "selfcheck_max_n": args.selfcheck_max_n,
                   "declared_cpu": "1 core, single process, no subprocesses"},
        "source_sha256": {
            "scorer.py": sha256_file(RM / "scorer.py"),
            "problem.py": sha256_file(C / "reproduction/reviewer_package_semfix/lrphsd/problem.py"),
            "global_env.py": sha256_file(RM / "global_env.py"),
            "exact_minmax.py": sha256_file(pathlib.Path(__file__)),
        },
        "maps": [{"name": nm, "path": by_name[nm]["path"],
                  "raw_sha256": by_name[nm]["raw_sha256"],
                  "author_solution_sha256": (
                      sha256_file(out / "author" / nm / "solution.json")
                      if (out / "author" / nm / "solution.json").exists() else None)}
                 for nm in maps],
        "excluded_from_summary": [x.strip() for x in args.exclude_from_summary.split(",") if x.strip()],
    }
    (out / args.intent_name).write_text(json.dumps(intent, indent=2, sort_keys=True) + "\n")
    print("[intent] wrote", out / args.intent_name, flush=True)
    print("[intent] source_sha256", json.dumps(intent["source_sha256"]), flush=True)
    if args.intent_only:
        return 0

    nonrl = {}
    np_path = out / "NONRL_RESULTS.json"
    if np_path.exists():
        for row in json.loads(np_path.read_text())["rows"]:
            if row.get("status") == "ONTIME_VALID":
                nonrl.setdefault(row["map"], {})[(row["method"], row.get("budget_s"))] = row

    rows = []
    for nm in maps:
        t0 = time.perf_counter()
        m = by_name[nm]
        inst = problem.read_instance(pathlib.Path(m["path"]))
        sol = json.loads((out / "author" / nm / "solution.json").read_text())
        run = json.loads((out / "author" / nm / "RUN.json").read_text())
        eligible = bool(run.get("anchor_eligible"))
        anchor = scorer.CostAnchor.from_solution(inst, sol)
        anchor.verify(inst)
        types = list(anchor.station_types)

        ts = dict(anchor.target_station)
        per_station = []
        timed_out = False
        for si in range(len(inst.stations)):
            tids = sorted([nid for nid, s in ts.items() if s == si])
            row = solve_station(inst, si, types[si], tids, args.max_n_exact,
                                len(tids) <= args.selfcheck_max_n)
            row["_tids"] = tids
            per_station.append(row)
            if time.perf_counter() - t0 > args.time_limit:
                timed_out = True
                break

        a_score = scorer.score_solution(inst, sol)
        cap_op = a_score["operating_minutes"] + 2.0 * COST_TOL
        all_exact = ((not timed_out) and len(per_station) == len(inst.stations)
                     and all(r.get("exact") for r in per_station))
        status = "EXACT" if all_exact else "UNKNOWN_NONEXACT_STATION"
        if timed_out:
            status = "TIMEOUT_OVER_BUDGET"
        if not eligible:
            status = "ANCHOR_NOT_ELIGIBLE_REFERENCE_ONLY"
        M_exact, op_exact, picks = (solve_global(per_station, cap_op) if all_exact
                                    else (None, None, None))

        rec = {
            "map": nm, "sites": m["sites"], "targets": m["targets"],
            "instance_sha256": inst.sha256, "anchor_eligible": eligible,
            "status": status,
            "anchor": {"cost": a_score["cost"], "M_return": a_score["M_return"],
                       "operating_minutes": a_score["operating_minutes"],
                       "solution_sha256": anchor.solution_sha256},
            "cap": {"epsilon": 0.0, "cost_tolerance": COST_TOL,
                    "cost_budget": anchor.cost + COST_TOL,
                    "operating_cap_min": cap_op,
                    "operating_cap_rule": "cap_op = anchor_operating + 2 * cost_tolerance"},
            "station_frontiers": [],
        }

        # strip private payload from the JSON record but keep it for reconstruction
        for row in per_station:
            pub = {k: v for k, v in row.items() if not k.startswith("_")}
            rec["station_frontiers"].append(pub)

        if all_exact:
            if M_exact is None:
                raise RuntimeError("exact search found no feasible combination")
            routes = [[[], []] for _ in inst.stations]
            per_M, per_op = [], []
            for si, row in enumerate(per_station):
                if row["kind"] == 0 or not row["_tids"]:
                    routes_si = [[], []]
                    per_M.append(0.0)
                    per_op.append(0.0)
                else:
                    routes_si, M_s, op_s = build_solution(inst, si, row["kind"], row, picks[si])
                    per_M.append(M_s)
                    per_op.append(op_s)
                routes[si] = routes_si
            solution = {"schema_version": 1, "instance": inst.name,
                        "instance_sha256": inst.sha256,
                        "station_types": types, "routes": routes}
            val = scorer.validate_candidate(inst, solution, anchor, epsilon=0.0)
            indep = independent_eval(inst, solution)
            d = pathlib.Path(out) / "exact" / nm
            d.mkdir(parents=True, exist_ok=True)
            (d / "solution.json").write_text(json.dumps(solution, sort_keys=True, indent=1) + "\n")
            (d / "validation.json").write_text(json.dumps(
                {k: val[k] for k in ("admissible", "original_feasible", "domain_valid",
                                     "cost_cap_satisfied", "cost_budget", "epsilon",
                                     "raw_cost_minus_cap", "raw_cost_minus_anchor",
                                     "cost", "M_return", "operating_minutes", "issues")},
                indent=2, sort_keys=True) + "\n")
            rec["solution_path"] = str(d / "solution.json")
            rec["solution_sha256"] = sha256_json(solution)
            rec["exact"] = {
                "M_return": M_exact, "operating_minutes": op_exact,
                "cost": a_score["fixed_cost"] + inst.params.time_cost * op_exact,
                "per_station_makespan": per_M, "per_station_operating": per_op,
                "cap_slack_operating": cap_op - op_exact,
                "headroom_vs_anchor_min": a_score["M_return"] - M_exact,
                "headroom_vs_anchor_pct": 100.0 * (a_score["M_return"] - M_exact) / a_score["M_return"],
            }
            rec["scorer_recheck"] = {
                "admissible": val["admissible"], "cost": val["cost"],
                "M_return": val["M_return"], "operating_minutes": val["operating_minutes"],
                "issues": val["issues"], "domain_valid": val["domain_valid"],
                "cost_cap_satisfied": val["cost_cap_satisfied"],
            }
            rec["consistency"] = {
                "abs_diff_M_return_vs_prediction": abs(val["M_return"] - M_exact),
                "abs_diff_operating_vs_prediction": abs(val["operating_minutes"] - op_exact),
                "abs_diff_cost_vs_prediction": abs(val["cost"] - rec["exact"]["cost"]),
                "abs_diff_M_return_vs_independent_eval": abs(val["M_return"] - indep["M_return"]),
                "abs_diff_cost_vs_independent_eval": abs(val["cost"] - indep["cost"]),
                "independent_eval_issues": indep["issues"],
                "required_agreement": CMP,
                "match_1e-9": bool(
                    abs(val["M_return"] - M_exact) <= CMP
                    and abs(val["operating_minutes"] - op_exact) <= CMP
                    and abs(val["M_return"] - indep["M_return"]) <= CMP
                    and abs(val["cost"] - indep["cost"]) <= CMP
                    and not indep["issues"]),
            }
        else:
            lvl = [r.get("lower_bound") for r in per_station if r.get("lower_bound")]
            exact_ms = [max(p[0] for p in r["frontier"]) for r in per_station
                        if r.get("exact") and r.get("frontier")]
            lb_candidates = [r["lower_bound"]["makespan_lb"] for r in per_station
                             if r.get("lower_bound")]
            lb_candidates += [max(p[0] for p in r["frontier"]) for r in per_station
                              if r.get("exact") and r.get("frontier")]
            ub = [a_score["M_return"]]
            for row in nonrl.get(nm, {}).values():
                if row.get("chosen_M_return") is not None:
                    ub.append(row["chosen_M_return"])
            rec["unknown"] = {
                "reason": "at least one station has more targets than max_n_exact=%d" %
                          args.max_n_exact,
                "nonexact_stations": [r["station"] for r in per_station if not r.get("exact")],
                "global_M_lower_bound": max(lb_candidates) if lb_candidates else None,
                "global_M_upper_bound_from_feasible": min(ub) if ub else None,
            }
            rec["unknown"]["bracket_width"] = (
                rec["unknown"]["global_M_upper_bound_from_feasible"]
                - rec["unknown"]["global_M_lower_bound"]
                if lb_candidates and ub else None)
            if (rec["unknown"]["bracket_width"] is not None
                    and rec["unknown"]["bracket_width"] < -1e-9):
                status = rec["status"] = "INCONSISTENT_BRACKET"
                print("[ERROR] lower bound exceeds feasible upper bound on", nm, flush=True)

        # comparison block
        cmp = {"anchor_M": a_score["M_return"]}
        for (meth, budget), row in sorted(nonrl.get(nm, {}).items(), key=lambda kv: str(kv[0])):
            key = "lpt" if meth == "lpt" else ("joint6" if budget == 6.0 else "joint12")
            cmp[key + "_M"] = row.get("chosen_M_return")
            cmp[key + "_status"] = row.get("status")
        if all_exact:
            cmp["exact_M"] = M_exact
            cmp["exact_vs_anchor_pct"] = 100.0 * (M_exact - a_score["M_return"]) / a_score["M_return"]
            for key in ("lpt", "joint6", "joint12"):
                v = cmp.get(key + "_M")
                if v is not None:
                    head = a_score["M_return"] - M_exact
                    cmp[key + "_remaining_gap_vs_exact_pct"] = 100.0 * (v - M_exact) / M_exact
                    cmp[key + "_headroom_captured_pct"] = (
                        100.0 * (a_score["M_return"] - v) / head if head > 1e-12 else None)
        rec["comparison"] = cmp
        rec["wall_s"] = round(time.perf_counter() - t0, 3)
        if rec["wall_s"] > args.time_limit:
            rec["status"] = "TIMEOUT_OVER_BUDGET"
        rows.append(rec)
        print(json.dumps({"map": nm, "status": rec["status"],
                          "anchor_M": round(a_score["M_return"], 6),
                          "exact_M": (round(M_exact, 6) if all_exact else None),
                          "exact_pct": (round(rec["exact"]["headroom_vs_anchor_pct"], 3)
                                        if all_exact else None),
                          "wall_s": rec["wall_s"]}), flush=True)
        (out / args.results_name).write_text(json.dumps(
            {"schema": "takeover_exact_minmax_v1",
             "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "intent": args.intent_name, "rows": rows},
            indent=2, sort_keys=True, allow_nan=False) + "\n")

    excluded = set(intent["excluded_from_summary"])
    summary = {
        "rows": len(rows),
        "exact_maps": [r["map"] for r in rows
                       if r["status"] == "EXACT" and r["map"] not in excluded],
        "exact_maps_reference_only": [r["map"] for r in rows
                                      if r["status"] == "ANCHOR_NOT_ELIGIBLE_REFERENCE_ONLY"],
        "unknown_maps": [r["map"] for r in rows if r["status"].startswith("UNKNOWN")],
        "all_consistency_ok": all(r.get("consistency", {}).get("match_1e-9", True) for r in rows),
        "all_bruteforce_ok": all(
            (s.get("bruteforce") or {}).get("match", True)
            for r in rows for s in r["station_frontiers"]),
        "all_exact_not_worse_than_heuristics": all(
            (r.get("exact", {}).get("M_return") is None
             or all(r["exact"]["M_return"] <= v + 1e-9
                    for k, v in r.get("comparison", {}).items()
                    if k.endswith("_M") and v is not None))
            for r in rows),
    }
    (out / args.results_name).write_text(json.dumps(
        {"schema": "takeover_exact_minmax_v1",
         "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "intent": args.intent_name, "rows": rows, "summary": summary},
        indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
