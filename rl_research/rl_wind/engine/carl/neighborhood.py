"""Coupling-aware joint neighborhoods (shared candidate generators).

All controllers choose *which macro family and intensity* to apply; the
micro-level target/station selection below is shared and deterministic given
the action and the RNG stream.  This keeps the controller comparison fair:
M1 (fixed policy) and M6 (PPO) see exactly the same candidate space.

Families
--------
0 Location   open / close / upgrade / downgrade / swap station type
1 Assignment cross-station target transfer (forced destination)
2 Routing    intra-station relocate, 2-opt, classic destroy-repair
3 Joint      type change + target transfer + affected-subproblem repair

A move is applied to kernel slot 1 (a clone of the current slot 0) with
explicit target removal, staged scoped repair and the complete physical guard.
A move that cannot be repaired or fails the guard is discarded; the current
solution is never mutated.
"""
import random
from dataclasses import dataclass, field

from lrphsd import fidelity_ops_v5 as ops
from .actions import OPERATOR_NAMES, OPERATOR_FAMILY, N_OPERATORS


FAMILIES = ("Location", "Assignment", "Routing", "Joint")
INTENSITY = ("small", "medium", "large")
INTENSITY_K = (2, 4, 8)
N_ACTIONS = 3 * N_OPERATORS


@dataclass
class Move:
    family: int
    intensity: int
    ids: list = field(default_factory=list)
    kinds: list = field(default_factory=list)
    station_mask: int = 0
    drone_mask: int = 0
    op: int = 0
    allow_empty: int = 1
    strict_kind: int = 1
    two_opt: tuple | None = None
    classic: tuple | None = None
    swap_pairs: list = field(default_factory=list)
    swap_mode: int = 0
    stages: list = field(default_factory=list)
    polish: int = -1
    alns_iters: int = 1
    full_rebuild: bool = False
    order: list = field(default_factory=list)
    tag: str = ""
    seed: int = 0


def _wchoice(rng, items, weights):
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    x = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if x <= acc:
            return it
    return items[-1]


def _sample(rng, items, k):
    if k >= len(items):
        return list(items)
    return rng.sample(list(items), k)


class Context:
    """Per-step view of the current solution used by the generators."""

    def __init__(self, ins, eng, mirror, coverage, rng, cross_exchange=True):
        self.ins = ins
        self.eng = eng
        self.mirror = mirror
        self.coverage = coverage
        self.rng = rng
        self.cross_exchange = bool(cross_exchange)
        self.nst = len(ins.stations)
        self.refresh()

    def refresh(self):
        self._operator_available_cache = None
        nst = self.nst
        self.work = [0.0] * nst
        self.slack = [0.0] * nst
        self.count = [0] * nst
        self.trips = [0] * nst
        self.fixed = [0.0] * nst
        self.load = [0.0] * nst
        self.dw0 = [0.0] * nst
        self.dw1 = [0.0] * nst
        self.dslack = [0.0] * nst
        self.dslack0 = [0.0] * nst
        self.dslack1 = [0.0] * nst
        total = 0.0
        for si in range(nst):
            if self.mirror.types[si] == 0:
                continue
            st = self.eng.station_stats(0, si)
            self.work[si] = st[0]
            self.fixed[si] = self.ins.fixed(self.mirror.types[si])
            self.slack[si] = max(0.0, 1.0 - max(st[2], st[3]) / self.ins.duration(self.mirror.types[si]))
            self.dw0[si] = st[2]
            self.dw1[si] = st[3]
            self.dslack[si] = st[4]
            self.dslack0[si] = st[7]
            self.dslack1[si] = st[8]
            self.count[si] = int(st[5])
            self.trips[si] = int(st[6])
            lim = self.ins.duration(self.mirror.types[si])
            self.load[si] = max(st[2], st[3]) / lim if lim > 0 else 0.0
            total += st[0]
        self.total_work = total
        self.open_stations = [si for si in range(nst) if self.mirror.types[si]]
        self.closed_stations = [si for si in range(nst) if not self.mirror.types[si]]
        self.total_targets = sum(self.count)
        # bottleneck drone (station, drone slot, working time); SABS uses slot 1
        btl = None
        for si in self.open_stations:
            for di, w in ((0, self.dw0[si]), (1, self.dw1[si])):
                if self.mirror.types[si] == 1 and di == 0:
                    continue
                if btl is None or w > btl[2]:
                    btl = (si, di, w)
        self.btl = btl

    def station_of(self, nid):
        return self.mirror.pos[nid][0]

    def dist_to(self, si, nid):
        return self.ins.dist[self.ins.stations[si].id, nid]


def _has_routes(ctx, mask):
    if mask == 0:
        return True
    for si in range(ctx.nst):
        if (mask >> si) & 1 and ctx.trips[si] > 0:
            return True
    return False


def _op_for(ctx, mask):
    return 0 if _has_routes(ctx, mask) else 2


def _sorted_by(ctx, ids, si):
    return sorted(ids, key=lambda n: ctx.dist_to(si, n))


def _order_far(ctx, ids, mask):
    """Far-first insertion order over the masked stations (coverage-aware)."""
    stations = [si for si in range(ctx.nst) if (mask >> si) & 1 and ctx.mirror.types[si]]
    if not stations:
        return list(ids)
    out = []
    for nid in ids:
        best = min((ctx.dist_to(si, nid) for si in stations
                    if ctx.coverage.covers(si, nid, ctx.mirror.types[si])), default=0.0)
        out.append((best, nid))
    out.sort(reverse=True)
    return [nid for _, nid in out]


def _move(family, intensity, ids=(), kinds=(), station_mask=0, drone_mask=0,
          op=None, allow_empty=1, strict_kind=1, stages=(), tag="",
          polish=-1, alns_iters=1, full_rebuild=False, order=(),
          swap_pairs=(), swap_mode=0):
    return Move(family=family, intensity=intensity, ids=list(ids), kinds=list(kinds),
                station_mask=station_mask, drone_mask=drone_mask,
                op=0 if op is None else op, allow_empty=allow_empty,
                strict_kind=strict_kind,
                stages=[[list(s[0]), int(s[1]), int(s[2])] for s in stages],
                tag=tag, polish=polish, alns_iters=alns_iters,
                full_rebuild=full_rebuild, order=list(order),
                swap_pairs=[tuple(x) for x in swap_pairs], swap_mode=int(swap_mode))


# ---------------------------------------------------------------- Location
def _loc_open(ctx, intensity):
    rng = ctx.rng
    best, best_saving = None, 0.0
    for si in ctx.closed_stations:
        pool = [nid for nid in ctx.coverage.by2[si]
                if ctx.mirror.pos[nid][0] != si
                and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 50.0]
        saving = sum(ctx.dist_to(ctx.station_of(nid), nid) - ctx.dist_to(si, nid)
                     for nid in pool)
        if saving > best_saving:
            best, best_saving = (si, pool), saving
    if best is None:
        return None
    si, pool = best
    kind = 2 if rng.random() < 0.7 else 1
    if kind == 1:
        pool = [n for n in pool if ctx.coverage.covers(si, n, 1)]
        if not pool:
            kind = 2
    if not pool:
        return None
    k = min(len(pool), INTENSITY_K[intensity])
    chosen = _order_far(ctx, _sample(rng, pool, k), 1 << si)
    return _move(0, intensity, [], [(si, kind)], 1 << si, tag="open",
                 full_rebuild=True, alns_iters=(0, 8, 20)[intensity],
                 order=ctx.coverage.order_all)


def _loc_close(ctx, intensity):
    rng = ctx.rng
    cand, weights = [], []
    for si in ctx.open_stations:
        ids = list(ctx.mirror.station_targets[si])
        if not ids:
            continue
        others = [t for t in ctx.open_stations if t != si]
        if not others:
            continue
        if not all(any(ctx.coverage.covers(t, nid, ctx.mirror.types[t]) for t in others)
                   for nid in ids):
            continue
        cand.append((si, ids))
        weights.append((1.4 - min(ctx.load[si], 1.2)) + ctx.fixed[si] / 100.0)
    if not cand:
        return None
    si, ids = _wchoice(rng, cand, weights)
    others_mask = 0
    for t in ctx.open_stations:
        if t != si:
            others_mask |= (1 << t)
    return _move(0, intensity, [], [(si, 0)], others_mask, tag="close",
                 full_rebuild=True, alns_iters=(0, 8, 20)[intensity],
                 order=ctx.coverage.order_all)


def _loc_up(ctx, intensity):
    rng = ctx.rng
    cand = [si for si in ctx.open_stations if ctx.mirror.types[si] == 1]
    if not cand:
        return None
    si = _wchoice(rng, cand, [ctx.load[s] + 1e-6 for s in cand])
    ids = _order_far(ctx, list(ctx.mirror.station_targets[si]), 1 << si)
    return _move(0, intensity, [], [(si, 2)], 1 << si, tag="upgrade",
                 full_rebuild=True, alns_iters=(0, 8, 20)[intensity],
                 order=ctx.coverage.order_all)


def _loc_down(ctx, intensity):
    rng = ctx.rng
    cand, weights = [], []
    for si in ctx.open_stations:
        if ctx.mirror.types[si] != 2:
            continue
        ids = list(ctx.mirror.station_targets[si])
        if not ids or not all(ctx.coverage.covers(si, nid, 1) for nid in ids):
            continue
        cand.append((si, ids))
        weights.append((1.4 - min(ctx.load[si], 1.2)) + 0.05)
    if not cand:
        return None
    si, ids = _wchoice(rng, cand, weights)
    return _move(0, intensity, [], [(si, 1)], 1 << si, tag="downgrade",
                 full_rebuild=True, alns_iters=(0, 8, 20)[intensity],
                 order=ctx.coverage.order_all)


def _loc_swap(ctx, intensity):
    rng = ctx.rng
    pairs, weights = [], []
    for a in ctx.open_stations:
        for b in ctx.open_stations:
            if a >= b or ctx.mirror.types[a] == ctx.mirror.types[b]:
                continue
            ta, tb = ctx.mirror.types[a], ctx.mirror.types[b]
            ia = list(ctx.mirror.station_targets[a])
            ib = list(ctx.mirror.station_targets[b])
            new_types = list(ctx.mirror.types)
            new_types[a], new_types[b] = tb, ta
            affected = ia + ib
            if not all(any(ctx.coverage.covers(t, n, new_types[t]) for t in ctx.open_stations) for n in affected):
                continue
            pairs.append((a, b, ta, tb))
            weights.append(1.0 + len(affected))
    if not pairs:
        return None
    a, b, ta, tb = _wchoice(rng, pairs, weights)
    return _move(0, intensity, [], [(a, tb), (b, ta)], (1 << a) | (1 << b),
                 tag="swap", full_rebuild=True, alns_iters=(0, 8, 20)[intensity],
                 order=ctx.coverage.order_all)

def gen_location(ctx, intensity):
    rng = ctx.rng
    options, weights = [], []
    if ctx.closed_stations:
        options.append("open")
        weights.append(0.8)
    if len(ctx.open_stations) > 1:
        options.append("close")
        weights.append(0.9)
    if any(ctx.mirror.types[s] == 1 for s in ctx.open_stations):
        options.append("up")
        weights.append(1.0)
    if any(ctx.mirror.types[s] == 2 for s in ctx.open_stations):
        options.append("down")
        weights.append(0.9)
    if len({ctx.mirror.types[s] for s in ctx.open_stations}) == 2:
        options.append("swap")
        weights.append(0.7)
    if not options:
        return None
    which = _wchoice(rng, options, weights)
    fn = {"open": _loc_open, "close": _loc_close, "up": _loc_up,
          "down": _loc_down, "swap": _loc_swap}[which]
    return fn(ctx, intensity)


# -------------------------------------------------------------- Assignment
def _transfer_ids(ctx, source, dest):
    ids = []
    for nid in ctx.mirror.station_targets[source]:
        if not ctx.coverage.covers(dest, nid, ctx.mirror.types[dest]):
            continue
        saving = ctx.dist_to(source, nid) - ctx.dist_to(dest, nid)
        ids.append((saving, nid))
    ids.sort(reverse=True)
    return [nid for _, nid in ids]


def gen_assignment(ctx, intensity):
    rng = ctx.rng
    if len(ctx.open_stations) < 2:
        return None
    sources, weights = [], []
    for si in ctx.open_stations:
        if not ctx.mirror.station_targets[si]:
            continue
        alt_counts = ctx.coverage.alt_counts(ctx.mirror.types)
        alt = sum(1 for nid in ctx.mirror.station_targets[si]
                  if alt_counts[ctx.coverage.tidx[nid]] >= 2)
        if alt:
            sources.append((si, alt))
            weights.append(alt * (0.4 + min(ctx.load[si], 2.0)))
    if not sources:
        return None
    src, _ = _wchoice(rng, sources, weights)
    pairs, pair_w = [], []
    for dst in ctx.open_stations:
        if dst == src:
            continue
        ids = _transfer_ids(ctx, src, dst)
        if ids:
            gain = sum(max(0.0, ctx.dist_to(src, n) - ctx.dist_to(dst, n)) for n in ids[:6])
            pairs.append((dst, ids))
            pair_w.append((1.3 - min(ctx.load[dst], 1.0)) + gain / 5000.0 + 0.05)
    if not pairs:
        return None
    dst, ids = _wchoice(rng, pairs, pair_w)
    k = min(len(ids), INTENSITY_K[intensity])
    chosen = _sample(rng, ids[: max(k, min(len(ids), 6))], k)
    chosen = _order_far(ctx, chosen, 1 << dst)
    return _move(1, intensity, chosen, [], 1 << dst,
                 op=0, tag="transfer", polish=1 << dst)


def _assignment_drone_reassign(ctx, intensity):
    """Move a small set of targets between the LD and SD of one DABS.

    The source is preferentially the more heavily loaded drone. Targets that
    cannot be flown as a depot-target-depot trip by the receiving drone are
    excluded before repair. The native repair is forced to the receiving
    drone; the full route/time/energy guard remains authoritative.
    """
    rng = ctx.rng
    candidates = []
    for si in ctx.open_stations:
        if ctx.mirror.types[si] != 2:
            continue
        for src, dst in ((0, 1), (1, 0)):
            ids = [nid for nid, pos in ctx.mirror.pos.items()
                   if pos[0] == si and pos[1] == src]
            if not ids:
                continue
            cap = ctx.ins.capacity(dst)
            feasible = [nid for nid in ids
                        if ops.path_energy(ctx.ins, si, [nid]) <= cap + 1e-9]
            if not feasible:
                continue
            src_work = ctx.dw0[si] if src == 0 else ctx.dw1[si]
            dst_work = ctx.dw0[si] if dst == 0 else ctx.dw1[si]
            imbalance = max(0.0, src_work - dst_work)
            candidates.append((si, src, dst, feasible, 0.05 + imbalance))
    if not candidates:
        return None
    si, src, dst, ids, _ = _wchoice(
        rng, candidates, [row[4] for row in candidates])
    # Prioritize far targets when moving work to the higher-capacity drone;
    # for LD->SD moves, the energy prefilter above is the safety condition.
    ids = sorted(ids, key=lambda nid: ctx.dist_to(si, nid), reverse=True)
    k = min(len(ids), INTENSITY_K[intensity])
    chosen = _sample(rng, ids, k)
    return _move(1, intensity, chosen, [], 1 << si, 1 << dst,
                 op=0, tag="drone_reassign", polish=1 << si)


def _station_closeable(ctx, si):
    ids = ctx.mirror.station_targets[si]
    others = [t for t in ctx.open_stations if t != si]
    return bool(ids and others) and all(
        any(ctx.coverage.covers(t, nid, ctx.mirror.types[t]) for t in others)
        for nid in ids
    )


def operator_available(ctx, operator):
    """Cached structural precondition test for the 17 operator-level actions.

    This is a cheap necessary-condition mask, not a feasibility certificate.
    Candidate repair and the complete physical guard still decide feasibility.
    """
    if type(operator) is not int or operator not in range(N_OPERATORS):
        raise ValueError("invalid operator ID")
    cache = getattr(ctx, "_operator_available_cache", None)
    if cache is None:
        cache = [None] * N_OPERATORS
        ctx._operator_available_cache = cache
    if cache[operator] is not None:
        return cache[operator]

    opened = ctx.open_stations
    closed = ctx.closed_stations
    types = ctx.mirror.types
    targets = ctx.mirror.station_targets
    value = False

    if operator == 0:  # location: open
        for si in closed:
            pool = [nid for nid in ctx.coverage.by2[si]
                    if ctx.mirror.pos[nid][0] != si
                    and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 50.0]
            if pool:
                value = True
                break
    elif operator == 1:  # location: close
        value = len(opened) > 1 and any(_station_closeable(ctx, si) for si in opened)
    elif operator == 2:
        value = any(types[si] == 1 for si in opened)
    elif operator == 3:
        value = any(types[si] == 2 and targets[si]
                    and all(ctx.coverage.covers(si, nid, 1) for nid in targets[si])
                    for si in opened)
    elif operator == 4:  # station-type exchange; generator checks target reassignability
        value = len({types[si] for si in opened}) == 2
    elif operator == 5:  # cross-station target transfer
        if len(opened) > 1:
            for src in opened:
                if not targets[src]:
                    continue
                for dst in opened:
                    if src != dst and _transfer_ids(ctx, src, dst):
                        value = True
                        break
                if value:
                    break
    elif operator == 6:  # within-DABS drone reassignment
        value = any(types[si] == 2 and
                    (any(pos[0] == si and pos[1] == 0 for pos in ctx.mirror.pos.values())
                     or any(pos[0] == si and pos[1] == 1 for pos in ctx.mirror.pos.values()))
                    for si in opened)
        if value:
            # At least one direction must have a receiver-feasible target.
            value = any(
                types[si] == 2 and any(
                    pos[0] == si and pos[1] == src
                    and ops.path_energy(ctx.ins, si, [nid]) <= ctx.ins.capacity(dst) + 1e-9
                    for nid, pos in ctx.mirror.pos.items()
                )
                for si in opened for src, dst in ((0, 1), (1, 0))
            )
    elif operator == 7:  # route relocate/reinsert within a station
        value = any(targets[si] for si in opened)
    elif operator == 8:  # 2-opt
        value = any(len(trip) >= 3 for si in opened
                    for drone in ctx.mirror.routes[si] for trip in drone)
    elif operator == 9:  # cross-drone positional exchange
        value = ctx.cross_exchange and any(
            types[si] == 2
            and any(nid for trip in ctx.mirror.routes[si][0] for nid in trip)
            and any(nid for trip in ctx.mirror.routes[si][1] for nid in trip)
            for si in opened
        )
    elif operator == 10:  # cross-trip positional exchange
        value = ctx.cross_exchange and any(
            sum(1 for trip in drone if trip) >= 2
            for si in opened for drone in ctx.mirror.routes[si]
        )
    elif operator == 11:  # classic ALNS destroy/repair
        value = any(targets[si] for si in opened)
    elif operator == 12:  # joint open + steal
        for si in closed:
            pool = [nid for nid in ctx.coverage.by2[si]
                    if ctx.mirror.pos[nid][0] != si
                    and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 100.0]
            if pool:
                value = True
                break
    elif operator == 13:  # joint close + shift
        value = len(opened) > 1 and any(_station_closeable(ctx, si) for si in opened)
    elif operator == 14:  # joint upgrade + absorb
        value = any(
            types[si] == 1 and any(
                ctx.mirror.pos[nid][0] != si
                and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 50.0
                for nid in ctx.coverage.by2[si]
            )
            for si in opened
        )
    elif operator == 15:  # joint downgrade + reallocate
        for si in opened:
            if types[si] != 2 or not targets[si]:
                continue
            outside = [nid for nid in targets[si]
                       if not ctx.coverage.covers(si, nid, 1)]
            if not outside or all(
                any(ctx.coverage.covers(t, nid, types[t]) for t in opened if t != si)
                for nid in outside
            ):
                value = True
                break
    elif operator == 16:  # joint station-type exchange with affected-target repair
        value = len({types[si] for si in opened}) == 2

    elif operator in (17, 18, 19):
        btl = ctx.btl
        if btl is not None and targets[btl[0]]:
            si = btl[0]
            if operator == 17:
                value = types[si] == 2 or any(
                    ctx.coverage.covers(t, nid, types[t])
                    for nid in targets[si] for t in opened if t != si)
            elif operator == 18:
                value = any(ctx.coverage.covers(c, nid, 2)
                            for c in closed for nid in targets[si])
            else:
                value = types[si] == 1

    cache[operator] = bool(value)
    return cache[operator]


# ----------------------------------------------------------------- Routing
def _route_relocate(ctx, intensity):
    rng = ctx.rng
    cand = [si for si in ctx.open_stations if ctx.count[si] > 0]
    if not cand:
        return None
    si = _wchoice(rng, cand, [0.2 + ctx.load[s] for s in cand])
    ids = list(ctx.mirror.station_targets[si])
    station = ctx.mirror.routes[si]
    if len(station) == 2 and ids:
        t0 = sum(len(tr) for tr in station[0])
        t1 = sum(len(tr) for tr in station[1])
        preferred = 0 if t0 >= t1 else 1
        pref = [n for n in ids if ctx.mirror.pos[n][1] == preferred]
        if pref and rng.random() < 0.7:
            ids = pref
    k = min(len(ids), INTENSITY_K[intensity])
    chosen = _order_far(ctx, _sample(rng, ids, k), 1 << si)
    return _move(2, intensity, chosen, [], 1 << si,
                 op=0, tag="relocate", polish=1 << si)


def _route_two_opt(ctx, intensity):
    rng = ctx.rng
    choices = [(si, di, ti) for si in ctx.open_stations
               for di, trips in enumerate(ctx.mirror.routes[si])
               for ti, trip in enumerate(trips) if len(trip) >= 3]
    if not choices:
        return None
    mv = _move(2, intensity, tag="two_opt")
    mv.two_opt = rng.choice(choices)
    return mv



def _route_cross_exchange(ctx, intensity, required_mode=None):
    """Swap target positions across two drones or two trips at one station.

    mode=1 is a DABS LD<->SD exchange; mode=2 is an exchange between two
    distinct trips of the same drone (also covers multi-trip SABS stations).
    The native kernel performs the positional swap; complete/physical guards
    decide feasibility. Intensities request 1/2/4 disjoint swaps.
    """
    rng = ctx.rng
    choices = []
    for si in ctx.open_stations:
        routes = ctx.mirror.routes[si]
        if ctx.mirror.types[si] == 2 and required_mode in (None, 1):
            left = [nid for trip in routes[0] for nid in trip]
            right = [nid for trip in routes[1] for nid in trip]
            if left and right:
                choices.append((si, 1, left, right))
        if required_mode in (None, 2):
            for di, trips in enumerate(routes):
                nonempty = [list(trip) for trip in trips if trip]
                for i in range(len(nonempty)):
                    for j in range(i + 1, len(nonempty)):
                        choices.append((si, 2, nonempty[i], nonempty[j]))
    if not choices:
        return None
    si, mode, left, right = rng.choice(choices)
    used_left, used_right, pairs = set(), set(), []
    for _ in range((1, 2, 4)[intensity]):
        a_pool = [nid for nid in left if nid not in used_left]
        b_pool = [nid for nid in right if nid not in used_right]
        if not a_pool or not b_pool:
            break
        a, b = rng.choice(a_pool), rng.choice(b_pool)
        pairs.append((a, b))
        used_left.add(a); used_right.add(b)
    if not pairs:
        return None
    tag = "cross_drone_exchange" if mode == 1 else "cross_trip_exchange"
    return _move(2, intensity, ids=[n for pair in pairs for n in pair],
                 tag=tag, swap_pairs=pairs, swap_mode=mode)


def _route_classic(ctx, intensity):
    rng = ctx.rng
    mv = _move(2, intensity, tag="classic")
    mv.classic = (0, 0)
    mv.seed = rng.getrandbits(48)
    mv.alns_iters = (4, 15, 40)[intensity]
    return mv


def gen_routing(ctx, intensity):
    roll = ctx.rng.random()
    if ctx.cross_exchange and roll < 0.25:
        mv = _route_cross_exchange(ctx, intensity)
        if mv is not None:
            return mv
    if roll < (0.45 if ctx.cross_exchange else 0.45):
        mv = _route_relocate(ctx, intensity)
        if mv is not None:
            return mv
    if roll < 0.72:
        mv = _route_two_opt(ctx, intensity)
        if mv is not None:
            return mv
    return _route_classic(ctx, intensity)


# ------------------------------------------------------- Bottleneck (makespan)
def _btl_ids(ctx):
    si, di, _ = ctx.btl
    return si, di, [nid for nid, pos in ctx.mirror.pos.items()
                    if pos[0] == si and pos[1] == di]


def _btl_offload(ctx, intensity):
    """Move targets off the busiest drone: to the sibling drone of a DABS
    (intensity 0) or to other open stations that cover them."""
    if ctx.btl is None:
        return None
    rng = ctx.rng
    si, di, ids = _btl_ids(ctx)
    if not ids:
        return None
    types = ctx.mirror.types
    if intensity == 0 and types[si] == 2:
        dst = 1 - di
        cap = ctx.ins.capacity(dst)
        feas = [n for n in ids if ops.path_energy(ctx.ins, si, [n]) <= cap + 1e-9]
        if feas:
            chosen = _sample(rng, feas, min(len(feas), 2))
            return _move(1, intensity, chosen, [], 1 << si, 1 << dst,
                         op=0, tag="btl_offload_drone", polish=1 << si)
    others = [t for t in ctx.open_stations if t != si]
    cand = []
    for n in ids:
        alt = [t for t in others if ctx.coverage.covers(t, n, types[t])]
        if alt:
            cand.append((min(ctx.dist_to(t, n) for t in alt), n, alt))
    if not cand:
        return None
    cand.sort()
    k = min(len(cand), INTENSITY_K[intensity])
    pick = _sample(rng, cand[: max(k, min(len(cand), 2 * k))], k)
    mask = 0
    for _, _, alt in pick:
        for t in alt:
            mask |= 1 << t
    chosen = _order_far(ctx, [n for _, n, _ in pick], mask)
    return _move(1, intensity, chosen, [], mask, 0, op=0,
                 tag="btl_offload_station", polish=mask)


def _btl_open_near(ctx, intensity):
    """Open a closed DABS that covers most targets of the bottleneck station
    and move bottleneck-drone targets to it."""
    if ctx.btl is None:
        return None
    rng = ctx.rng
    si, di, ids = _btl_ids(ctx)
    pool_all = list(ctx.mirror.station_targets[si])
    best = None
    for c in ctx.closed_stations:
        pool = [n for n in ids if ctx.coverage.covers(c, n, 2)]
        if not pool:
            pool = [n for n in pool_all if ctx.coverage.covers(c, n, 2)]
        if pool and (best is None or len(pool) > len(best[1])):
            best = (c, pool)
    if best is None:
        return None
    c, pool = best
    k = min(len(pool), INTENSITY_K[intensity] + 2)
    chosen = _order_far(ctx, _sample(rng, pool, k), 1 << c)
    return _move(3, intensity, chosen, [(c, 2)], 1 << c, op=0,
                 tag="btl_open", polish=1 << c)


def _btl_upgrade(ctx, intensity):
    """Upgrade a bottleneck SABS to DABS and split its targets onto the new
    large drone (farthest targets first: the large drone has more battery)."""
    if ctx.btl is None:
        return None
    si = ctx.btl[0]
    if ctx.mirror.types[si] != 1:
        return None
    ids = sorted(ctx.mirror.station_targets[si], key=lambda n: ctx.dist_to(si, n), reverse=True)
    if not ids:
        return None
    k = max(1, int(round(len(ids) * (0.3, 0.45, 0.6)[intensity])))
    chosen = ids[:k]
    return _move(3, intensity, chosen, [(si, 2)], 1 << si, 1 << 0, op=0,
                 tag="btl_upgrade", polish=1 << si)


# ------------------------------------------------------------------- Joint
def _joint_open_steal(ctx, intensity):
    rng = ctx.rng
    best, best_saving = None, 0.0
    for si in ctx.closed_stations:
        pool = [nid for nid in ctx.coverage.by2[si]
                if ctx.mirror.pos[nid][0] != si
                and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 100.0]
        saving = sum(ctx.dist_to(ctx.station_of(nid), nid) - ctx.dist_to(si, nid) for nid in pool)
        if saving > best_saving:
            best, best_saving = (si, pool), saving
    if best is None:
        return None
    si, pool = best
    k = min(len(pool), INTENSITY_K[intensity] + 2)
    chosen = _order_far(ctx, _sample(rng, pool, k), 1 << si)
    return _move(3, intensity, chosen, [(si, 2)], 1 << si, op=0,
                 tag="joint_open", polish=1 << si)


def _joint_downgrade(ctx, intensity):
    rng = ctx.rng
    cand, weights = [], []
    for si in ctx.open_stations:
        if ctx.mirror.types[si] != 2 or not ctx.mirror.station_targets[si]:
            continue
        cand.append(si)
        weights.append(1.5 - min(ctx.load[si], 1.3))
    if not cand:
        return None
    si = _wchoice(rng, cand, weights)
    ids = list(ctx.mirror.station_targets[si])
    inside = [n for n in ids if ctx.coverage.covers(si, n, 1)]
    outside = [n for n in ids if n not in inside]
    if not outside:
        return _move(3, intensity, ids, [(si, 1)], 1 << si,
                     op=0, tag="joint_downgrade_local", polish=1 << si)
    partners = []
    for t in ctx.open_stations:
        if t == si:
            continue
        cover = sum(1 for n in outside if ctx.coverage.covers(t, n, ctx.mirror.types[t]))
        if cover:
            partners.append((t, cover))
    if not partners:
        return None
    if not all(any(ctx.coverage.covers(t, nid, ctx.mirror.types[t])
                   for t, _ in partners) for nid in outside):
        return None
    mask = (1 << si)
    for t, _ in partners:
        mask |= 1 << t
    return _move(3, intensity, _order_far(ctx, ids, mask), [(si, 1)], mask,
                 op=0, tag="joint_downgrade", polish=mask)


def _joint_upgrade_absorb(ctx, intensity):
    rng = ctx.rng
    candidates = []
    weights = []
    for si in ctx.open_stations:
        if ctx.mirror.types[si] != 1:
            continue
        pool = [nid for nid in ctx.coverage.by2[si]
                if ctx.mirror.pos[nid][0] != si
                and ctx.dist_to(si, nid) < ctx.dist_to(ctx.station_of(nid), nid) - 50.0]
        if pool:
            candidates.append((si, pool))
            weights.append(0.3 + ctx.load[si] + 0.01 * len(pool))
    if not candidates:
        return None
    si, pool = _wchoice(rng, candidates, weights)
    k = min(len(pool), INTENSITY_K[intensity])
    chosen = _order_far(ctx, _sample(rng, pool, k), 1 << si)
    return _move(3, intensity, chosen, [(si, 2)], 1 << si, op=0,
                 tag="joint_upgrade", polish=1 << si)


def _joint_close_shift(ctx, intensity):
    rng = ctx.rng
    cand, weights = [], []
    for si in ctx.open_stations:
        ids = ctx.mirror.station_targets[si]
        if not ids or len(ctx.open_stations) < 2:
            continue
        others = [t for t in ctx.open_stations if t != si]
        if not all(any(ctx.coverage.covers(t, nid, ctx.mirror.types[t]) for t in others)
                   for nid in ids):
            continue
        cand.append(si)
        weights.append(1.3 - min(ctx.load[si], 1.1) + ctx.fixed[si] / 120.0)
    if not cand:
        return None
    si = _wchoice(rng, cand, weights)
    ids = list(ctx.mirror.station_targets[si])
    receivers = [t for t in ctx.open_stations if t != si
                 and any(ctx.coverage.covers(t, nid, ctx.mirror.types[t]) for nid in ids)]
    mask = sum(1 << t for t in receivers)
    if not mask:
        return None
    return _move(3, intensity, _order_far(ctx, ids, mask), [(si, 0)], mask,
                 op=0, tag="joint_close", polish=mask)


def _joint_swap_absorb(ctx, intensity):
    rng = ctx.rng
    pairs, weights = [], []
    for a in ctx.open_stations:
        for b in ctx.open_stations:
            if a >= b or ctx.mirror.types[a] == ctx.mirror.types[b]:
                continue
            ta, tb = ctx.mirror.types[a], ctx.mirror.types[b]
            ia = list(ctx.mirror.station_targets[a])
            ib = list(ctx.mirror.station_targets[b])
            new_types = list(ctx.mirror.types)
            new_types[a], new_types[b] = tb, ta
            affected = sorted(ia + ib)
            if not all(any(ctx.coverage.covers(t, n, new_types[t]) for t in ctx.open_stations) for n in affected):
                continue
            pairs.append((a, b, ta, tb, affected))
            weights.append(1.0 + len(affected))
    if not pairs:
        return None
    a, b, ta, tb, affected = _wchoice(rng, pairs, weights)
    new_types = list(ctx.mirror.types)
    new_types[a], new_types[b] = tb, ta
    receiver_mask = sum(1 << t for t in ctx.open_stations if new_types[t])
    return _move(3, intensity, affected, [(a, tb), (b, ta)], receiver_mask,
                 op=0, stages=[(affected, receiver_mask, 0)], tag="joint_swap",
                 polish=receiver_mask)

def gen_joint(ctx, intensity):
    rng = ctx.rng
    options = []
    if ctx.closed_stations:
        options.append(_joint_open_steal)
    if any(ctx.mirror.types[s] == 2 and ctx.mirror.station_targets[s] for s in ctx.open_stations):
        options.append(_joint_downgrade)
    if any(ctx.mirror.types[s] == 1 for s in ctx.open_stations):
        options.append(_joint_upgrade_absorb)
    if len(ctx.open_stations) > 1:
        options.append(_joint_close_shift)
    if len(ctx.open_stations) > 1 and len({ctx.mirror.types[s] for s in ctx.open_stations}) == 2:
        options.append(_joint_swap_absorb)
    if not options:
        return None
    rng.shuffle(options)
    for fn in options:
        mv = fn(ctx, intensity)
        if mv is not None and (mv.ids or mv.kinds or mv.stages):
            return mv
    return None


GEN = (gen_location, gen_assignment, gen_routing, gen_joint)


def generate(ctx, operator, intensity):
    """Generate one explicitly selected operator and intensity.

    The controller now chooses the concrete macro-neighborhood subtype. It no
    longer chooses only a family and delegates subtype choice to random code.
    """
    if operator not in range(N_OPERATORS):
        raise ValueError("invalid operator ID")
    if intensity not in (0, 1, 2):
        raise ValueError("invalid intensity")
    family = OPERATOR_FAMILY[operator]
    if operator == 0:
        return _loc_open(ctx, intensity)
    if operator == 1:
        return _loc_close(ctx, intensity)
    if operator == 2:
        return _loc_up(ctx, intensity)
    if operator == 3:
        return _loc_down(ctx, intensity)
    if operator == 4:
        return _loc_swap(ctx, intensity)
    if operator == 5:
        return gen_assignment(ctx, intensity)
    if operator == 6:
        return _assignment_drone_reassign(ctx, intensity)
    if operator == 7:
        return _route_relocate(ctx, intensity)
    if operator == 8:
        return _route_two_opt(ctx, 0) if intensity == 0 else None
    if operator == 9:
        return _route_cross_exchange(ctx, intensity, required_mode=1)
    if operator == 10:
        return _route_cross_exchange(ctx, intensity, required_mode=2)
    if operator == 11:
        return _route_classic(ctx, intensity)
    if operator == 12:
        return _joint_open_steal(ctx, intensity)
    if operator == 13:
        return _joint_close_shift(ctx, intensity)
    if operator == 14:
        return _joint_upgrade_absorb(ctx, intensity)
    if operator == 15:
        return _joint_downgrade(ctx, intensity)
    if operator == 16:
        return _joint_swap_absorb(ctx, intensity)
    if operator == 17:
        return _btl_offload(ctx, intensity)
    if operator == 18:
        return _btl_open_near(ctx, intensity)
    if operator == 19:
        return _btl_upgrade(ctx, intensity)
    raise AssertionError("unreachable operator")


def apply_move(eng, move, current_types, ins=None, repair_scope_mode="local"):
    """Apply a move to slot 1; repair_scope_mode can broaden Assignment and/or Joint receivers."""
    if repair_scope_mode not in (
            "local", "global_assignment", "global_joint", "global_assignment_joint"):
        raise ValueError(f"unknown repair_scope_mode: {repair_scope_mode}")
    eng.clone(0, 1)
    if move.swap_pairs:
        for nid_a, nid_b in move.swap_pairs:
            if eng.swap_targets(1, nid_a, nid_b, move.swap_mode) != 1:
                return None
        types = list(current_types)
        if not eng.complete(1) or not eng.guard(1):
            return None
        return types
    if move.full_rebuild:
        types = list(current_types)
        for si, kind in move.kinds:
            types[si] = kind
            if eng.lib.r6_set_kind(1, si, kind) != 1:
                return None
        # Exact C port of official Init.java GreedyRouting, differentially
        # verified against Python greedy.py on all 120 official instances.
        if eng.rebuild_official_greedy(1) != 1:
            return None
        if move.alns_iters > 1:
            local = random.Random(int(move.seed) or 12345)
            best_cost = eng.cost(1)
            for _ in range(move.alns_iters):
                eng.clone(1, 3)
                d = local.randrange(4)
                r = local.randrange(4)
                removed, _s, _d = eng.destroy(3, 1, d, local.getrandbits(48))
                ok = bool(removed) and bool(eng.repair_scoped(1, r, removed, 0, 0, 0, 1))
                if ok and eng.complete(1) and eng.valid(1, True):
                    c = eng.cost(1)
                    if c <= best_cost:
                        best_cost = c
                    else:
                        eng.clone(3, 1)
                else:
                    eng.clone(3, 1)
        if not eng.complete(1) or not eng.guard(1):
            return None
        return types
    if move.classic is not None:
        local = random.Random(int(move.seed))
        best_cost = eng.cost(1)
        iters = max(1, int(move.alns_iters))
        for i in range(iters):
            eng.clone(1, 3)
            d = local.randrange(4)
            r = local.randrange(4)
            seed = local.getrandbits(48)
            removed, _seed_after, _draws = eng.destroy(3, 1, d, seed)
            ok = bool(removed) and bool(eng.repair_scoped(1, r, removed, 0, 0, 0, 1))
            if ok and eng.complete(1) and eng.valid(1, True):
                c = eng.cost(1)
                if c <= best_cost:
                    best_cost = c
                else:
                    eng.clone(3, 1)
            else:
                eng.clone(3, 1)
    elif move.two_opt is not None:
        if eng.two_opt(1, *move.two_opt) <= 0:
            return None
    else:
        if move.ids:
            if eng.remove_ids(1, move.ids) != len(move.ids):
                return None
        for si, kind in move.kinds:
            if eng.lib.r6_set_kind(1, si, kind) != 1:
                return None
        if move.stages:
            repair_types = list(current_types)
            for si, kind in move.kinds:
                repair_types[si] = kind
            global_receiver_mask = sum(
                1 << si for si, kind in enumerate(repair_types) if kind)
            broaden_receiver_scope = (
                (repair_scope_mode in ("global_assignment", "global_assignment_joint")
                 and move.family == 1)
                or (repair_scope_mode in ("global_joint", "global_assignment_joint")
                    and move.family == 3)
            )
            for ids, mask, op in move.stages:
                if not ids:
                    continue
                if broaden_receiver_scope:
                    mask = global_receiver_mask
                if eng.repair_scoped(1, op, ids, mask, 0, 1, 1) != 1:
                    return None
        elif move.ids:
            repair_mask = move.station_mask
            repair_drone_mask = move.drone_mask
            broaden_receiver_scope = (
                (repair_scope_mode in ("global_assignment", "global_assignment_joint")
                 and move.family == 1)
                or (repair_scope_mode in ("global_joint", "global_assignment_joint")
                    and move.family == 3)
            )
            if broaden_receiver_scope:
                # Joint receiver scope must use post-move station types:
                # newly opened stations may receive targets; stations scheduled
                # to close must not remain in the receiver mask.
                repair_types = list(current_types)
                for si, kind in move.kinds:
                    repair_types[si] = kind
                repair_mask = sum(
                    1 << si for si, kind in enumerate(repair_types) if kind)
                repair_drone_mask = 0
            if eng.repair_scoped(1, move.op, move.ids, repair_mask,
                                 repair_drone_mask, move.allow_empty,
                                 move.strict_kind) != 1:
                return None
    types = list(current_types)
    for si, kind in move.kinds:
        types[si] = kind
    if move.polish >= 0:
        if move.polish == 0:
            stations = range(len(types))
        else:
            stations = [si for si in range(len(types)) if (move.polish >> si) & 1]
        for si in stations:
            if types[si]:
                eng.two_opt_station(1, si)
    if not eng.complete(1):
        return None
    if not eng.guard(1):
        return None
    return types
