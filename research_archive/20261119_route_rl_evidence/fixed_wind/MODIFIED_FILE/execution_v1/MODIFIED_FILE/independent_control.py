"""Standard independent station search with shared H and literal full-map cap.

Reuse existing minmax generators/acceptance, public T and bank combination.
No model, learning, new RL mechanism or scientific superiority claim.
"""
from copy import deepcopy
import hashlib
import json
import math
import random
from time import perf_counter

from baselines import minmax_alns as alns
from baselines.constant_wind_adapter import ConstantWindCtx
from baselines.wind_scorer import score_solution, cost_within_cap
from public_t import rebalance_complete
from schedule_credit import Context

MODE = 'independent_h_cost'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def local_row(instance, anchor, si, routes, row_id, *, anchor_row=False):
    solution = anchor.solution()
    solution['routes'][si] = deepcopy(routes)
    score = score_solution(instance, solution, wind=anchor.wind)
    if not score['original_feasible']:
        raise ValueError(('PHYSICAL_SCHEDULE_INVALID', row_id, score['issues']))
    if tuple(sorted(score['target_station'].items())) != anchor.target_station:
        raise ValueError('TARGET_STATION_CHANGED')
    duties = [r['duty_min'] for r in score['slot_duty'] if r['station'] == si]
    # Cost is deliberately NOT gated with all other stations frozen at anchor.
    return {'id': row_id, 'station': si, 'duties': duties, 'm': max(duties),
            'anchor': anchor_row, 'routes': deepcopy(routes),
            'single_replacement_cost': score['cost'],
            'single_replacement_over_cap': not cost_within_cap(score['cost'], anchor.cost)}


def station_plan(ctx, template, si, station_routes):
    plan = alns.Plan(ctx, template['station_types'])
    for slot, trips in enumerate(station_routes):
        for trip in trips:
            plan.add(si, slot, trip)
    return plan


def plan_routes(plan, si):
    return [[list(t.seq) for t in plan.slots[si][slot]] for slot in (0, 1)]


def projected_slots(instance, anchor, ctx, si, new_slots, deadline, stats):
    raw = [[list(t.seq) for t in new_slots[slot]] for slot in (0, 1)]
    routes, receipt = rebalance_complete(instance, anchor, ctx, si, raw, deadline)
    stats['public_T_statuses'][receipt['status']] = stats['public_T_statuses'].get(receipt['status'],0)+1
    return [[ctx.make_trip(si, slot, trip) for trip in routes[slot]] for slot in (0, 1)]


def search_station(instance, anchor, si, H, config, *, mode=None, deadline=None):
    mode = MODE if mode is None else mode
    if mode not in ('independent_minmax', 'independent_h_cost'):
        raise ValueError(mode)
    if not math.isfinite(H) or H < 0:
        raise ValueError('FINITE_NONNEGATIVE_COMMON_H_REQUIRED')
    if deadline is not None and not math.isfinite(deadline):
        raise ValueError('FINITE_ABSOLUTE_DEADLINE_REQUIRED')
    template = anchor.solution()
    bank = [local_row(instance, anchor, si, template['routes'][si],
                      'S%d:anchor' % si, anchor_row=True)]
    if anchor.station_types[si] == 0:
        return bank, {'station': si, 'evaluated': 0, 'accepted': 0, 'trace': [],
                      'candidate_identity_count': 0, 'search_status': 'CLOSED_STATION'}
    if deadline is not None and perf_counter() >= deadline:
        return bank, {'station': si, 'evaluated': 0, 'accepted': 0, 'trace': [],
                      'candidate_identity_count': 0, 'search_status': 'DEADLINE_EXHAUSTED',
                      'budget_hit': True, 'deadline': deadline}
    ctx = ConstantWindCtx(instance, anchor.station_types, dict(anchor.target_station), wind=anchor.wind)
    absolute_deadline = perf_counter()+600.0 if deadline is None else deadline
    start_routes, initial_T = rebalance_complete(instance, anchor, ctx, si, template['routes'][si], absolute_deadline)
    plan = station_plan(ctx, template, si, start_routes)
    seen = {canonical(template['routes'][si])}
    stats = {'initial_public_T':initial_T,'public_T_statuses':{},'evaluated': 0, 'accepted': 0, 'candidate_identity_count': 0,
             'invalid_projections': [], 'trace': [], 'station': si,
             'initial_M': plan.station_mk(si), 'initial_operating': plan.stot[si],
             'common_H': H, 'mode': mode, 'global_cap_gate_during_search': False,
             'proposal_support': 'existing finite minmax generators, not exhaustive physical domain'}
    search_started = perf_counter()
    budget = alns.Budget(search_started,
                         600.0 if deadline is None else max(0.0, deadline - search_started),
                         perf_counter)
    rng = random.Random(config['base_seed'] + si)
    limit = config['max_evaluations_per_station']

    def register(slots, label):
        try:
            candidate = projected_slots(instance, anchor, ctx, si, slots, absolute_deadline, stats)
        except AssertionError as exc:
            stats['invalid_projections'].append({'label': label, 'reason': str(exc)})
            return None
        probe = alns._probe(plan, si, candidate, math.inf)
        if probe is None:
            stats['invalid_projections'].append({'label': label, 'reason': 'ORIGINAL_PHYSICAL_PROBE'})
            return None
        routes = [[list(t.seq) for t in candidate[slot]] for slot in (0, 1)]
        identity = canonical(routes)
        if identity not in seen:
            seen.add(identity)
            stats['candidate_identity_count'] += 1
            row = local_row(instance, anchor, si, routes,
                            'S%d:option%d' % (si, stats['candidate_identity_count']))
            # Keep full physically legal candidates. Shared H/cap combination
            # decides what is useful, including temporary single-station cost rises.
            if budget.over():
                return None
            bank.append(row)
        return candidate

    if not budget.over():
        register(plan.slots[si], 'initial_public_T')
    for round_index in range(config['rounds']):
        if stats['evaluated'] >= limit or budget.over():
            break
        moved = False
        makers = alns._makers(plan, si, budget, tuple(config['operator_order']))
        for make in makers:
            if stats['evaluated'] >= limit:
                break
            for label, slots in make():
                if stats['evaluated'] >= limit or budget.over():
                    break
                candidate = register(slots, label)
                if candidate is None:
                    stats['evaluated'] += 1
                    continue
                # Reuse the existing epsilon-constraint objective. Until an H-
                # feasible start is found, normal minmax is a feasibility search.
                ceiling = H if mode == 'independent_h_cost' and plan.station_mk(si) <= H else None
                if alns.attempt(plan, si, candidate, 0.0, math.inf, stats, stats['trace'],
                                'independent', label, m_cap=ceiling):
                    stats['accepted'] += 1
                    moved = True
                    break
            if moved:
                break
        if moved:
            continue
        loaded = 0 if plan.duty[si][0] >= plan.duty[si][1] else 1
        for label, slots in alns.gen_ruin(plan, si, loaded, rng):
            if stats['evaluated'] >= limit or budget.over():
                break
            candidate = register(slots, label)
            if candidate is None:
                stats['evaluated'] += 1
                continue
            ceiling = H if mode == 'independent_h_cost' and plan.station_mk(si) <= H else None
            if alns.attempt(plan, si, candidate, 0.0, math.inf, stats, stats['trace'],
                            'independent_ruin', label, m_cap=ceiling):
                stats['accepted'] += 1
                moved = True
                break
        if not moved:
            break
    stats.update(final_M=plan.station_mk(si), final_operating=plan.stot[si],
                 search_status='CANDIDATES_GENERATED', budget_hit=budget.hit)
    return bank, stats


def combine_at_H(instance, anchor, banks, H):
    fixed = sum(instance.fixed(k) for k in anchor.station_types)
    ctx = Context(banks, fixed, instance.params.time_cost, anchor.cost)
    result = ctx.minimum(H)
    if result is None:
        return {'status': 'NO_BANK_WITNESS_AT_H_NOT_PHYSICAL_UNSAT',
                'solution': anchor.solution(), 'fallback': True, 'selected_ids': [],
                'score': score_solution(instance, anchor.solution(), wind=anchor.wind)}
    selected, cost = result
    if not cost_within_cap(cost, anchor.cost):
        return {'status': 'BANK_COST_OVER_CAP_NOT_PHYSICAL_UNSAT',
                'solution': anchor.solution(), 'fallback': True, 'selected_ids': [],
                'score': score_solution(instance, anchor.solution(), wind=anchor.wind)}
    solution = anchor.solution()
    for si, row in enumerate(selected):
        solution['routes'][si] = deepcopy(row['routes'])
    score = score_solution(instance, solution, wind=anchor.wind)
    assert score['original_feasible'] and cost_within_cap(score['cost'], anchor.cost)
    assert score['M_return'] <= H and score['cost'] == cost
    return {'status': 'FULL_WITNESS_AT_H', 'solution': solution, 'fallback': False,
            'selected_ids': [r['id'] for r in selected], 'score': score}


def generate(instance, anchor, H, config, *, mode=None, deadline=None, delivery_reserve_s=0.0):
    if deadline is not None and not math.isfinite(deadline):
        raise ValueError('FINITE_ABSOLUTE_DEADLINE_REQUIRED')
    if not math.isfinite(delivery_reserve_s) or delivery_reserve_s < 0:
        raise ValueError('FINITE_NONNEGATIVE_DELIVERY_RESERVE_REQUIRED')
    if deadline is None and delivery_reserve_s:
        raise ValueError('RESERVE_REQUIRES_DEADLINE')
    anchor.verify(instance)
    banks, records = [], []
    for si in range(len(instance.stations)):
        if deadline is None:
            bank, record = search_station(instance, anchor, si, H, config, mode=mode)
        else:
            # One absolute full-map budget. Divide the remaining search time
            # among unopened active stations; do not restart the clock per station.
            now = perf_counter()
            active_left = sum(kind != 0 for kind in anchor.station_types[si:])
            search_end = deadline - delivery_reserve_s
            station_deadline = min(search_end, now + max(0.0, search_end - now) / max(1, active_left))
            bank, record = search_station(instance, anchor, si, H, config, mode=mode,
                                          deadline=station_deadline)
            record['allocated_deadline'] = station_deadline
            record['full_map_deadline'] = deadline
            record['delivery_reserve_s'] = delivery_reserve_s
        banks.append(bank)
        records.append(record)
    result = combine_at_H(instance, anchor, banks, H)
    return {'mode': MODE if mode is None else mode, 'H': H, 'banks': banks,
            'station_searches': records, 'delivery': result}
