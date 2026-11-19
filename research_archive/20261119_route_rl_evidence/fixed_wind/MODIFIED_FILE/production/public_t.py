"""Bounded typed intact-trip T; original heading scorer has final authority.

Only complete schedules, never an executed/open physical prefix. Exactness is
not claimed when the existing ALNS enumerator has >15 trips or hits deadline.
"""
from copy import deepcopy
from time import perf_counter
from types import SimpleNamespace
import json
import math

from baselines import minmax_alns as alns
from baselines import wind_scorer


def rebalance_complete(instance, anchor, ctx, si, raw, deadline):
    if not math.isfinite(deadline):
        raise ValueError('FINITE_ABSOLUTE_T_DEADLINE_REQUIRED')
    template = anchor.solution()
    template['routes'][si] = deepcopy(raw)
    source = wind_scorer.score_solution(instance, template, wind=anchor.wind)
    if source['cost'] is None:
        raise AssertionError('STRUCTURALLY_INVALID_T_INPUT')
    ids = sorted(a for slot in raw for tr in slot for a in tr)
    if ids != sorted(a for a,s in anchor.target_station if s==si):
        raise AssertionError('T_TARGET_STATION_COVERAGE_CHANGED')
    best = None
    def consider(routes):
        nonlocal best
        proposal = anchor.solution()
        proposal['routes'][si] = deepcopy(routes)
        score = wind_scorer.score_solution(instance, proposal, wind=anchor.wind)
        if not score['original_feasible'] or not wind_scorer.cost_within_cap(score['cost'], source['cost']):
            return
        key = (score['station_makespan'][si], score['cost'], json.dumps(routes,separators=(',',':')))
        if best is None or key < best[0]:
            best = key, deepcopy(routes)
    consider(raw)
    budget = alns.Budget(perf_counter(), max(0.0,deadline-perf_counter()), perf_counter)
    if not budget.over():
        view = SimpleNamespace(station_types=anchor.station_types, solution=lambda:deepcopy(template))
        lpt = alns.lpt_plan(ctx, view)
        consider(lpt.to_solution(template)['routes'][si])
    count = sum(len(slot) for slot in raw)
    enumerated = False
    if not budget.over():
        plan = alns.plan_from_solution(ctx, template)
        for label, slots in alns.gen_rebalance(ctx, plan, si, budget):
            consider([[list(tr.seq) for tr in slot] for slot in slots])
            enumerated = True
    status = ('APPROXIMATE_OR_TIMEOUT' if count>15 or budget.hit else
              'BOUNDED_EXISTING_ENUMERATOR_COMPLETED' if enumerated else 'LPT_OR_ORIGINAL')
    if best is None:
        raise AssertionError('NO_TYPED_PHYSICALLY_VALID_T_ASSIGNMENT')
    return best[1], {'trip_count':count,'status':status,'budget_hit':budget.hit,
                     'cost_cap_reference':'input full schedule, not author local cap'}
