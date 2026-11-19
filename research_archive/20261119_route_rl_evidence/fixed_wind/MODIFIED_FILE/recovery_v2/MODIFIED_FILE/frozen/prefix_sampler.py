"""Counterfactual certificates for real TARGET/RETURN trajectory generation.

The public postprocessor exactly reassigns complete trips to the two typed
vehicles (preserving each trip and its order). This is an engineering fixture,
not a Liu source change, actor, training run, or scientific performance claim.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
import hashlib
import math
import random
import sys

from baselines.wind_scorer import score_solution, cost_within_cap
from env.constant_audit import heading_leg
from global_env import StationRouteEnv
from schedule_credit import all_deletions

MODE = 'deletion_envelope'
DELETION_ENGINE = 'pivotal_binary'


def trip_resources(instance, station, trip, wind, closed=True):
    nodes = [instance.nodes[t] for t in trip]
    chain = [station] + nodes + ([station] if closed and nodes else [])
    travel = sum(heading_leg((a.x, a.y), (b.x, b.y), wind, instance.params.speed)
                 for a, b in zip(chain, chain[1:]))
    service = sum(n.service for n in nodes)
    energy = travel * instance.params.flight_energy + sum(n.energy for n in nodes)
    return travel + service, energy


def _down_to_float(value):
    if value <= 0:
        return 0.0
    result = float(value)
    if Q(result) > value:
        result = math.nextafter(result, -math.inf)
    return result


def prefix_bound(env):
    """Lower bound that also survives arbitrary complete-trip reassignment.

    CPython 3.10 uses ordered nonnegative float sums, as the frozen scorer.
    Trip extensions append nonnegative travel and service terms. A future
    slot's rounded duty is >=(1-N*u)*sum(trip durations)-N*eta. Taking the
    average across slots and rounding down yields a conservative bound.
    The maximum of any known (possibly open) trip duration is another bound.
    """
    assert sys.version_info[:2] == (3, 10), 'ORDERED_CPYTHON_310_SUM_REQUIRED'
    durations = []
    for slot in env.slots:
        for trip in env.routes[slot]:
            durations.append(trip_resources(env.instance, env.station, trip, env.wind)[0])
        if env.current_trip[slot]:
            durations.append(trip_resources(env.instance, env.station,
                                             env.current_trip[slot], env.wind, False)[0])
    if not durations:
        return 0.0
    n, slots = len(env.target_ids), len(env.slots)
    assert n < 2**52 and all(math.isfinite(d) and d >= 0 for d in durations)
    exact_sum = sum((Q(d) for d in durations), Q(0))
    averaged = (1-Q(n, 2**53))*exact_sum/slots-Q(n, 2**1074)
    return max(max(durations), _down_to_float(averaged))


def rebalance(instance, si, kind, routes, wind):
    """Public exhaustive typed two-slot reassignment; no route arc is changed."""
    if kind == 0:
        assert routes == [[], []]
        return deepcopy(routes)
    trips = [list(t) for slot in routes for t in slot if t]
    assert len(trips) <= 14, 'FROZEN_ENGINEERING_TRIP_LIMIT'
    resources = [trip_resources(instance, instance.stations[si], t, wind) for t in trips]
    slots = (1,) if kind == 1 else (0, 1)
    best, output = None, None
    for assignment in product(slots, repeat=len(trips)):
        duties = [0.0, 0.0]
        good = True
        for slot, (duration, energy) in zip(assignment, resources):
            capacity = instance.params.large_battery if slot == 0 else instance.params.small_battery
            if energy > capacity + 1e-12:
                good = False
                break
            duties[slot] += duration
        limit = instance.params.small_duration if kind == 1 else instance.params.large_duration
        if not good or any(d > limit+1e-7 for d in duties):
            continue
        key = (max(duties), sum(duties), assignment)
        if best is None or key < best:
            best = key
            output = [[t for t, s in zip(trips, assignment) if s == slot] for slot in (0, 1)]
    if output is None:
        raise AssertionError('COMPLETED_LEGAL_TRAJECTORY_LOST_TYPED_REASSIGNMENT')
    return output


def row(case, si, routes, sid, anchor=False):
    solution = case['anchor'].solution()
    solution['routes'][si] = deepcopy(routes)
    score = score_solution(case['instance'], solution, wind=case['wind'])
    if not score['original_feasible']:
        raise AssertionError(('COMPLETE_PHYSICAL_SCHEDULE_FAILED', sid, score['issues']))
    assert tuple(sorted(score['target_station'].items())) == case['anchor'].target_station
    duties = [v['duty_min'] for v in score['slot_duty'] if v['station'] == si]
    return {'id': sid, 'duties': duties, 'm': max(duties), 'anchor': anchor,
            'station': si, 'routes': deepcopy(routes)}


def evaluate(case, banks, failures=()):
    return all_deletions(banks, case['fixed'], case['time_cost'], case['cap'],
                         failures=failures, mode=DELETION_ENGINE)


def ranked_actions(env, obs):
    actions = [a for a, legal in zip(obs['actions'], obs['mask']) if legal]
    def key(a):
        # Geometry-only public proposal policy. All legal TARGET/RETURN actions
        # remain physical; a Bernoulli selects the first or last ranked action.
        target = env.station.id if a.is_return else a.target_id
        return (a.is_return, env.cumulative_duty[a.slot]+env.trip_elapsed[a.slot]
                + env._leg(env.current_pos[a.slot], target), a.slot, target)
    return sorted(actions, key=key)


def seed_for(case_name, batch, sid):
    text = 'counterfactual-prefix-20261113-v1|%s|%s|%s' % (case_name, batch, sid)
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:16], 'big')


def draw(case, si, sid, batch, threshold=math.inf, *, mode='full',
         probability=Q(7, 20), coins=None, finite=False):
    """Generate directly, never instantiate an unknown suffix after pruning."""
    f = case['fixture']
    env = StationRouteEnv(case['instance'], si, f['station_types'][si],
                          f['assignments'][si], wind=case['wind'])
    rng = random.Random(seed_for(case['name'], batch, sid))
    p = Q(probability)
    obs = env.observation()
    actions, bounds, score, used_coins = [], [], Q(0), []
    while not obs['done']:
        legal = ranked_actions(env, obs)
        if not legal:
            return {'id': sid, 'station': si, 'status': 'FAILED_PHYSICAL_DEAD_END',
                    'actions': actions, 'bounds': bounds, 'score': str(score),
                    'coins': used_coins, 'threshold': None if math.isinf(threshold) else threshold}
        stochastic = len(legal)>1 and (not finite or len(actions) in (0, 2))
        if stochastic:
            bit = (int(rng.random()<float(p)) if coins is None
                   else int(coins[len(used_coins)]))
            used_coins.append(bit)
            score += bit-p  # derivative with respect to the Bernoulli logit
            action = legal[-1] if bit else legal[0]
        else:
            action = legal[0]
        actions.append([action.slot, action.target_id])
        obs, _, _, _ = env.step(action)
        if mode != 'full' and not obs['done']:
            lower = prefix_bound(env)
            bounds.append({'steps': len(actions), 'LB': lower})
            if lower >= threshold:
                return {'id': sid, 'station': si, 'status': 'PRUNED_CERTIFIED_NONIMPROVING',
                        'actions': actions, 'bounds': bounds, 'score': str(score),
                        'coins': used_coins, 'threshold': threshold}
    original = env.result()['routes']
    routes = rebalance(case['instance'], si, f['station_types'][si], original, case['wind'])
    option = row(case, si, routes, sid)
    return {'id': sid, 'station': si, 'status': 'COMPLETED', 'actions': actions,
            'bounds': bounds, 'score': str(score), 'coins': used_coins,
            'threshold': None if math.isinf(threshold) else threshold,
            'original_routes': original, 'row': option}


def run_batch(case, k, batch, *, mode=None, probability=Q(7,20), finite=False, scripts=None):
    mode = MODE if mode is None else mode
    assert mode in ('full', 'anchor_certificate', 'deletion_envelope', 'primal_mutation')
    banks = [[dict(r)] for r in case['anchors']]
    initial = evaluate(case, banks)
    envelope = anchor_h = initial['F']
    failures, draws, envelope_events = [], [], []
    solver_calls = 1
    schedule = [(si, j) for j in range(k) for si, ids in enumerate(case['fixture']['assignments']) if ids]
    for index, (si, j) in enumerate(schedule):
        sid = 'S%d:%d' % (si, j)
        threshold = math.inf if mode=='full' else (anchor_h if mode=='anchor_certificate' else envelope)
        record = draw(case, si, sid, batch, threshold, mode=mode, probability=probability,
                      coins=None if scripts is None else scripts[index], finite=finite)
        if record['status']=='COMPLETED':
            banks[si].append(record['row'])
            if mode in ('deletion_envelope', 'primal_mutation') and record['row']['m'] < envelope:
                current = evaluate(case, banks, failures)
                solver_calls += 1
                previous = envelope
                envelope = (current['F'] if mode=='primal_mutation'
                            else max([current['F'], *current['deletions'].values()]))
                assert envelope <= previous
                envelope_events.append({'after': sid, 'H': current['F'], 'E': envelope,
                                        'D': current['deletions']})
        else:
            # Fixed identity remains in the denominator. It is never replaced.
            failures.append(sid)
        draws.append(record)
    final = evaluate(case, banks, failures)
    solver_calls += 1
    gradient = Q(0)
    for rec in draws:
        advantage = Q(final['deletions'][rec['id']])-Q(final['F'])
        if rec['status']=='PRUNED_CERTIFIED_NONIMPROVING':
            assert advantage==0
        gradient += advantage*Q(rec['score'])
    lookup = {r['id']: r for b in banks for r in b}
    solution = case['anchor'].solution()
    for si, sid in enumerate(final['selected_ids']):
        solution['routes'][si] = deepcopy(lookup[sid]['routes'])
    report = score_solution(case['instance'], solution, wind=case['wind'])
    assert report['original_feasible'] and cost_within_cap(report['cost'], case['cap'])
    assert report['M_return']==final['F'] and report['cost']==final['cost']
    return {'case': case['name'], 'batch': batch, 'mode': mode, 'anchor_H': anchor_h,
            'F': final['F'], 'D': final['deletions'], 'advantages': final['advantages'],
            'gradient': str(gradient), 'solution': solution, 'score': report,
            'draws': draws, 'envelope_events': envelope_events, 'solver_calls': solver_calls,
            'generated_actions': sum(len(r['actions']) for r in draws),
            'prefix_checks': sum(len(r['bounds']) for r in draws),
            'pruned': sum(r['status']=='PRUNED_CERTIFIED_NONIMPROVING' for r in draws),
            'failed': sum(r['status']=='FAILED_PHYSICAL_DEAD_END' for r in draws)}
