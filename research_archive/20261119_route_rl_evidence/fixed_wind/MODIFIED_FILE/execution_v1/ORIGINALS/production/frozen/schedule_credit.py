"""All sample-copy deletion values for finite physical station schedules.

Both engines retain the frozen scorer's literal nonnegative binary64 accounting.
MODE is the reversible fixture branch. No policy/model/training is imported.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from fractions import Fraction as Q
import heapq
import math
import struct
import sys

from baselines.wind_scorer import cost_within_cap

MODE = 'guarded_sweep'


def total(selected, fixed, time_cost):
    operating = 0.0
    for r in selected:
        for d in r['duties']:
            operating += d
    return fixed + operating * time_cost


class Context:
    def __init__(self, banks, fixed, time_cost, cap, failures=()):
        self.banks, self.fixed, self.time_cost, self.cap = banks, fixed, time_cost, cap
        self.work = defaultdict(int)
        self.cache = {}
        self.station = {}
        self.samples = list(failures)
        for si, bank in enumerate(banks):
            if not bank or not any(r['anchor'] for r in bank):
                raise ValueError('PERMANENT_ANCHOR_REQUIRED')
            for r in bank:
                sid = r['id']
                if sid in self.station or sid in self.samples:
                    raise ValueError('COPY_ID_MUST_BE_UNIQUE')
                self.station[sid] = si
                if len(r['duties']) != 2 or any(not math.isfinite(d) or d < 0 for d in r['duties']):
                    raise ValueError('FINITE_NONNEGATIVE_TWO_SLOT_DUTIES_REQUIRED')
                if r['m'] != max(r['duties']):
                    raise ValueError('FULL_RETURN_MISMATCH')
                if not r['anchor']:
                    self.samples.append(sid)
        if len(self.samples) != len(set(self.samples)):
            raise ValueError('COPY_ID_MUST_BE_UNIQUE')
        if not banks or any(not math.isfinite(v) or v < 0 for v in (fixed, time_cost, cap)):
            raise ValueError('FINITE_NONNEGATIVE_COST_DOMAIN_REQUIRED')
        anchors = [next(r for r in b if r['anchor']) for b in banks]
        if not cost_within_cap(total(anchors, fixed, time_cost), cap):
            raise ValueError('ANCHOR_MUST_BE_ADMISSIBLE')
        self.thresholds = sorted({r['m'] for b in banks for r in b})

    def minimum(self, h, removed=None):
        # Cache literal optimal original prefixes at each threshold. Deleting an
        # unselected ID retains the original witness; otherwise only its suffix
        # must be recomputed. Ties preserve source-bank order.
        if h not in self.cache:
            selected, prefix, operating = [], [0.0], 0.0
            for bank in self.banks:
                allowed = [r for r in bank if r['m'] <= h]
                self.work['duty_option_evaluations'] += len(allowed)
                if not allowed:
                    self.cache[h] = None
                    break
                r = min(allowed, key=lambda r: (operating + r['duties'][0]) + r['duties'][1])
                operating = (operating + r['duties'][0]) + r['duties'][1]
                selected.append(r)
                prefix.append(operating)
            else:
                self.cache[h] = (selected, prefix)
        else:
            self.work['original_threshold_cache_hits'] += 1
        base = self.cache[h]
        if base is None:
            return None
        selected, prefix = base
        if removed is None or removed not in self.station:
            return selected, self.fixed + prefix[-1] * self.time_cost
        si = self.station[removed]
        if selected[si]['id'] != removed:
            self.work['unselected_at_threshold_reuse'] += 1
            return selected, self.fixed + prefix[-1] * self.time_cost
        selected, operating = list(selected[:si]), prefix[si]
        for bank in self.banks[si:]:
            allowed = [r for r in bank if r['m'] <= h and r['id'] != removed]
            self.work['duty_option_evaluations'] += len(allowed)
            if not allowed:
                return None
            r = min(allowed, key=lambda r: (operating + r['duties'][0]) + r['duties'][1])
            operating = (operating + r['duties'][0]) + r['duties'][1]
            selected.append(r)
        return selected, self.fixed + operating * self.time_cost

    def solve(self, removed=None, floor=None):
        self.work['literal_binary_queries'] += 1
        lo = 0 if floor is None else bisect_left(self.thresholds, floor)
        hi = len(self.thresholds) - 1
        if floor is not None:
            result = self.minimum(floor, removed)
            if result is not None and cost_within_cap(result[1], self.cap):
                return floor, result[0], result[1]
            lo += 1
        while lo < hi:
            mid = (lo + hi) // 2
            result = self.minimum(self.thresholds[mid], removed)
            if result is not None and cost_within_cap(result[1], self.cap):
                hi = mid
            else:
                lo = mid + 1
        if lo > hi:
            raise AssertionError('ANCHOR_LOST_AFTER_DELETION')
        h = self.thresholds[lo]
        result = self.minimum(h, removed)
        if result is None or not cost_within_cap(result[1], self.cap):
            raise AssertionError('ANCHOR_LOST_AFTER_DELETION')
        return h, result[0], result[1]


def screen(ctx, h, selected):
    pending, zeros, prefix = {}, set(), [0.0]
    for r in selected:
        p = prefix[-1]
        prefix.append((p + r['duties'][0]) + r['duties'][1])
    for si, r in enumerate(selected):
        if r['anchor']:
            continue
        sid = r['id']
        alternatives = [v for v in ctx.banks[si] if v['id'] != sid and v['m'] <= h]
        ctx.work['screen_option_evaluations'] += len(alternatives)
        if alternatives:
            p = prefix[si]
            replacement = min(alternatives, key=lambda v: (p + v['duties'][0]) + v['duties'][1])
            witness = list(selected)
            witness[si] = replacement
            ctx.work['screen_complete_witnesses'] += 1
            if cost_within_cap(total(witness, ctx.fixed, ctx.time_cost), ctx.cap):
                zeros.add(sid)
                continue
        pending[si] = sid
    return pending, zeros


def maximum_accepted_cost(cap):
    def value(bits):
        return struct.unpack('>d', struct.pack('>Q', bits))[0]
    lo, hi = 0, 0x7fefffffffffffff
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if cost_within_cap(value(mid), cap):
            lo = mid
        else:
            hi = mid - 1
    return Q(value(lo))


def dyadic_ceiling(x):
    if x == 0:
        return Q(0)
    e = x.numerator.bit_length() - x.denominator.bit_length()
    p = Q(2**e) if e >= 0 else Q(1, 2**(-e))
    return p if p >= x else 2*p


def guarded_integer_resources(ctx):
    f = sys.float_info
    if (f.radix, f.mant_dig, f.rounds) != (2, 53, 1):
        return None, 'NON_BINARY64_ROUND_TO_NEAREST'
    u, eta, upper, error = Q(1, 2**53), Q(1, 2**1074), Q(0), Q(0)
    for bank in ctx.banks:
        for slot in (0, 1):
            z = upper + max(Q(r['duties'][slot]) for r in bank)
            e = u*z + eta
            upper, error = z + e, error + e
    z = upper * Q(ctx.time_cost)
    emul = u*z + eta
    zadd = Q(ctx.fixed) + z + emul
    eadd = u*zadd + eta
    if max(upper, z + emul, zadd + eadd) >= Q(f.max)/2:
        return None, 'POSSIBLE_OVERFLOW_BOUND'
    error = dyadic_ceiling(error*Q(ctx.time_cost) + emul + eadd)
    maximum = maximum_accepted_cost(ctx.cap)
    optimistic = maximum - Q(ctx.fixed) + error
    conservative = maximum - Q(ctx.fixed) - error
    weights = {r['id']: (Q(r['duties'][0])+Q(r['duties'][1]))*Q(ctx.time_cost)
               for b in ctx.banks for r in b}
    denominator = max(v.denominator for v in [optimistic, conservative, *weights.values()])
    assert denominator & (denominator - 1) == 0
    def integer(v):
        assert denominator % v.denominator == 0
        return v.numerator * (denominator // v.denominator)
    return {'weights': {k: integer(v) for k, v in weights.items()},
            'optimistic': integer(optimistic), 'conservative': integer(conservative),
            'error_bound': str(error), 'denominator_bits': denominator.bit_length()}, None


def deletion_sweep(ctx, floor, pending, resources, budget):
    if not pending:
        return {}
    weights = resources['weights']
    events = sorted((r['m'], si, order, r['id']) for si, bank in enumerate(ctx.banks)
                    for order, r in enumerate(bank))
    top = [[] for _ in ctx.banks]
    active, versions, heap, result = set(pending), defaultdict(int), [], {}
    operating, missing, initialized = 0, len(top), False
    cursor = 0

    def push(si):
        versions[si] += 1
        pair = top[si]
        sid = pending[si]
        penalty = 0 if pair[0][2] != sid else (pair[1][0]-pair[0][0] if len(pair)>1 else None)
        if penalty is not None:
            heapq.heappush(heap, (penalty, si, versions[si]))
            ctx.work['sweep_heap_pushes'] += 1

    while cursor < len(events) and active:
        h = events[cursor][0]
        changed = set()
        while cursor < len(events) and events[cursor][0] == h:
            _, si, order, sid = events[cursor]
            pair = top[si]
            old = pair[0][0] if pair else None
            new = sorted([*pair, (weights[sid], order, sid)])[:2]
            if new != pair:
                top[si] = new
                changed.add(si)
            if old is None:
                missing -= 1
                operating += new[0][0]
            else:
                operating += new[0][0] - old
            cursor += 1
            ctx.work['sweep_events'] += 1
        if h < floor:
            continue
        if missing:
            raise AssertionError('ORIGINAL_FEASIBLE_THRESHOLD_MISSING_STATION')
        if not initialized:
            for si in active:
                push(si)
            initialized = True
        else:
            for si in changed & active:
                push(si)
        slack = budget - operating
        while heap:
            penalty, si, version = heap[0]
            if si not in active or version != versions[si]:
                heapq.heappop(heap)
                ctx.work['sweep_stale_pops'] += 1
                continue
            if penalty > slack:
                break
            heapq.heappop(heap)
            result[pending[si]] = h
            active.remove(si)
    for si in active:
        result[pending[si]] = None
    return result


def all_deletions(banks, fixed, time_cost, cap, failures=(), mode=None):
    ctx = Context(banks, fixed, time_cost, cap, failures)
    h, selected, cost = ctx.solve()
    pending, zeros = screen(ctx, h, selected)
    values = {sid: h for sid in ctx.samples}
    mode = MODE if mode is None else mode
    certificate, fallback_ids, certified_ids = None, [], []
    if mode == 'pivotal_binary':
        for sid in pending.values():
            values[sid] = ctx.solve(sid, h)[0]
    elif mode == 'guarded_sweep':
        if pending:
            resources, reason = guarded_integer_resources(ctx)
            if resources is None:
                certificate = {'guard_fallback_reason': reason}
                fallback_ids = list(pending.values())
            else:
                low = deletion_sweep(ctx, h, pending, resources, resources['optimistic'])
                high = deletion_sweep(ctx, h, pending, resources, resources['conservative'])
                certificate = {k: v for k, v in resources.items() if k != 'weights'}
                certificate.update(optimistic_values=low, conservative_values=high)
                for sid in pending.values():
                    if low[sid] is not None and low[sid] == high[sid]:
                        values[sid] = low[sid]
                        certified_ids.append(sid)
                    else:
                        fallback_ids.append(sid)
            for sid in fallback_ids:
                values[sid] = ctx.solve(sid, h)[0]
    else:
        raise ValueError('UNKNOWN_MODE')
    assert all(v >= h for v in values.values())
    return {'F': h, 'cost': cost, 'selected_ids': [r['id'] for r in selected],
            'deletions': values, 'advantages': {sid: v-h for sid, v in values.items()},
            'screened_zero_ids': sorted(zeros), 'pending_ids': sorted(pending.values()),
            'certified_ids': sorted(certified_ids), 'fallback_ids': sorted(fallback_ids),
            'certificate': certificate, 'work': dict(ctx.work), 'mode': mode}
