"""Round-5 throughput engine.

Search semantics are those of ``tsalns_v4`` (same RNG streams, same operation
order, same acceptance rule, same complete physical guard).  The engine differs
only in representation: immutable per-instance tables, allocation-free route
statistics and a guard that reuses one evaluator skeleton instead of rebuilding
it per station.
"""
import copy, math, time
from collections import Counter

from . import fidelity_ops_v5 as ops, greedy
from .round4_runtime import Streams, Runtime, AbsoluteBudget  # noqa: F401
from .java_random import JavaRandom  # noqa: F401
from .evaluator import evaluate
from .guard_v5 import Guard

DEFAULT = {'outer_iterations': 500, 'local_iterations': 100, 'alns_iterations': 5000,
           'initial_temperature': 1000., 'cooling_rate': .95, 'final_temperature': .001,
           'weight_upper': 5.}


def solve(ins, seed=0, seconds=None, config=None, events=None, removed_tape=None,
          physical_guard=True, rng_mode="split", cache=False, guard_cache=False,
          detail_rng=False, removed_order="input"):
    wall_start = time.perf_counter()
    ops.prepare(ins)
    runtime = Runtime(ins, cache)
    ops.RUNTIME = runtime
    guard = Guard(ins, guard_cache)
    factory = Streams(seed, rng_mode, detail_rng)
    config = {**DEFAULT, **(config or {})}
    rng = factory.create("Main.java:113")
    start = wall_start
    evaluations = 0
    counters = runtime.counts
    timings = runtime.timings
    trace = []
    timings["precompute"] = time.perf_counter() - wall_start
    targets = ins.target_ids
    target_set = set(targets)

    def alive():
        return seconds is None or time.perf_counter() - start < seconds

    def cost(sol, fixed=True):
        nonlocal evaluations
        objective_start = time.perf_counter()
        evaluations += 1
        counters["full_solution_objectives" if fixed else "route_set_objectives"] += 1
        value = 0.0
        p = ins.params
        path_time = ops.path_time
        for si, s in enumerate(sol['routes']):
            if fixed:
                kind = sol['station_types'][si]
                if kind == 2:
                    value = value + p.large_station_cost + p.large_drone_cost + p.small_drone_cost
                elif kind == 1:
                    value += p.small_station_cost + p.small_drone_cost
            for d in s:
                if fixed:
                    total = 0.0
                    for t in d:
                        total += path_time(ins, si, t)
                    value += total * p.time_cost
                else:
                    for t in d:
                        value += path_time(ins, si, t) * p.time_cost
        timings["objective"] += time.perf_counter() - objective_start
        return value

    def emit(stage, step, op, sol, **extra):
        if events is not None:
            events.append({'stage': stage, 'step': step, 'op': op, 'random_calls': factory.calls,
                           'state': {'station_types': sol['station_types'].copy(),
                                     'routes': copy.deepcopy(sol['routes'])},
                           'evaluations': evaluations, **extra})

    def measured(name, fn, *args):
        t = time.perf_counter()
        value = fn(*args)
        timings[name] += time.perf_counter() - t
        counters[name] += 1
        return value

    def physically_valid(sol, partial=False):
        if not physical_guard:
            return True
        t = time.perf_counter()
        result = guard.valid(ops.physical(sol))
        timings['physical_guard'] += time.perf_counter() - t
        counters['complete_physical_checks'] += 1
        if not result:
            counters['guard_rejections'] += 1
        return result

    current = measured('greedy', greedy.build, ins)
    initial = cost(current)
    current_cost = initial
    best = ops.clone(current)
    best_cost = initial
    if not physically_valid(current):
        raise ValueError('initializer invalid under complete physical contract')
    emit('initial', 0, -1, current)
    temperature = config['initial_temperature']
    outer_done = 0
    trace.append({'elapsed': time.perf_counter() - start, 'cost': best_cost,
                  'evaluations': evaluations, 'solution': ops.physical(best)})

    def alns(sol):
        nonlocal evaluations
        cur = ops.clone(sol)
        cur_cost = cost(cur, False)
        local_best = ops.clone(cur)
        local_cost = cur_cost
        temp = config['initial_temperature']
        weights = [[1.] * 4 for _ in range(2)]
        scores = [[0.] * 4 for _ in range(2)]
        counts = [[0] * 4 for _ in range(2)]
        for k in range(config['alns_iterations']):
            if not alive() or temp <= config['final_temperature']:
                break
            mathrng = factory.math()
            d, r = [mathrng.choices(range(4), w, k=1)[0] for w in weights]
            destroy_rng = factory.create({1: 'RoutingOperator.java:632', 2: 'RoutingOperator.java:431',
                                          3: 'RoutingOperator.java:710'}[d]) if d else rng
            destroyed = measured('destroy', ops.destroy_candidate, ins, cur, d, destroy_rng)
            oldset = ops.target_set(cur)
            newset = ops.target_set(destroyed)
            removed = [n for n in targets if n in oldset - newset]
            if removed_order == "sorted_id":
                removed.sort()
            if removed_tape is not None:
                assert removed_tape, ('removal_tape_exhausted', k)
                ordered = removed_tape.pop(0)
                assert set(ordered) == set(removed), ('removed_set', ordered, removed)
                removed = ordered
            emit('destroy', k, d, destroyed, repair_op=r, removed=removed)
            candidate = measured('repair', ops.repair_candidate, ins, destroyed, removed, r)
            counters['repair_rollback'] += candidate is destroyed
            cand = [n for station in candidate['routes'] for drone in station for trip in drone for n in trip]
            complete = len(cand) == len(targets) and set(cand) == target_set
            counters['repair_success' if complete else 'repair_failure'] += 1
            counters['candidate_generated_alns'] += 1
            value = cost(candidate, False)
            improvement = local_cost - value
            accepted = value < cur_cost or mathrng.random() < math.exp((cur_cost - value) / temp)
            if not physically_valid(candidate):
                accepted = False
                counters['candidate_guard_rejections'] += 1
            emit('repair', k, r, candidate, accepted=accepted, temperature=temp,
                 weights_d=weights[0].copy(), weights_r=weights[1].copy(), scores_d=scores[0].copy())
            counters['alns_candidates'] += 1
            counters['alns_accepted'] += accepted
            counters['candidate_accepted'] += accepted
            if accepted:
                cur = candidate
                cur_cost = value
                if value < local_cost:
                    local_best = ops.clone(candidate)
                    local_cost = value
                    counters['alns_best_improved'] += 1
                    counters['best_improvements_alns'] += 1
            reward = (1. + (2. * improvement / (improvement + 1) if improvement > 0 else 0)) if accepted else -.2
            for group, index in enumerate((d, r)):
                scores[group][index] = .9 * scores[group][index] + reward
                counts[group][index] += 1
            if k % 50 == 0:
                for group in range(2):
                    for j in range(4):
                        if counts[group][j]:
                            weights[group][j] = max(.1, min(config['weight_upper'],
                                                            weights[group][j] * .8 + (scores[group][j] / counts[group][j]) * .2))
                    scores[group] = [0.] * 4
                    counts[group] = [0] * 4
            temp *= config['cooling_rate']
        return local_best, local_cost

    for outer in range(config['outer_iterations']):
        if not alive():
            break
        outer_done = outer + 1
        selector = factory.create('LocationOperator.java:112')
        which = selector.randrange(4)
        site_rng = factory.create(['LocationOperator.java:15', 'LocationOperator.java:37',
                                   'LocationOperator.java:61', 'LocationOperator.java:85'][which])
        types = measured('location', ops.location, current['station_types'], site_rng, which)
        counters['candidate_generated_location'] += 1
        emit('location', outer, -1, {'station_types': types, 'routes': current['routes']})
        try:
            candidate = measured('greedy', greedy.build, ins, types)
        except ValueError:
            counters['location_rejected'] += 1
            continue
        counters['source_feasibility_checkpoints'] += 1
        if not ops.raw_valid(ins, candidate, time_check=False):
            counters['location_rejected'] += 1
            continue
        for j in range(config['local_iterations']):
            if not alive():
                break
            op = rng.randrange(5)
            localrng = factory.create(['RoutingOperator.java:12', 'RoutingOperator.java:93',
                                       'RoutingOperator.java:152', 'RoutingOperator.java:221'][op]) if op < 4 else rng
            candidate = measured('local', ops.local_candidate, ins, candidate, op, localrng)
            counters['candidate_generated_local'] += 1
            emit('local', j, op, candidate)
        emit('local_end', outer, -1, candidate)
        candidate, _ = alns(candidate)
        counters['candidate_generated_outer'] += 1
        value = cost(candidate)
        probability = 1. if value < current_cost else math.exp((current_cost - value) / temperature)
        accepted = probability > rng.random()
        if not physically_valid(candidate):
            accepted = False
            counters['outer_guard_rejections'] += 1
        if accepted:
            current = candidate
            current_cost = value
            if value < best_cost:
                best = ops.clone(candidate)
                best_cost = value
                counters['best_improvements_outer'] += 1
                trace.append({'elapsed': time.perf_counter() - start, 'cost': best_cost,
                              'evaluations': evaluations, 'solution': ops.physical(best)})
        counters['outer_accepted'] += accepted
        counters['candidate_accepted'] += accepted
        emit('outer_end', outer, -1, current, current_cost=current_cost, best_cost=best_cost,
             temperature=temperature)
        temperature *= config['cooling_rate']
    final = ops.physical(best)
    emit('final', config['outer_iterations'], -1, best, best_cost=best_cost, budget_alive=alive())
    elapsed = time.perf_counter() - start
    counters['route_time_computations'] = ops.NTIME
    counters['route_energy_computations'] = ops.NENERGY
    return final, {'algorithm': 'independent_tsalns_v5', 'seed': seed, 'initial_objective': initial,
                   'objective': best_cost, 'evaluations': evaluations, 'elapsed_seconds': elapsed,
                   'outer_iterations_attempted': outer_done, 'config': config,
                   'physical_guard': physical_guard,
                   'removed_order': 'recorded_reference_tape' if removed_tape is not None else 'input_target_order; differs from unspecified Java identity-HashSet',
                   'trace': trace, 'timings': dict(timings), 'counters': dict(counters),
                   'termination': 'time_budget' if not alive() else 'configured_iterations',
                   'random_draws': factory.calls, 'rng_mode': rng_mode,
                   'rng_created': dict(factory.counts), 'rng_streams': factory.created,
                   'rng_details': factory.draws, 'route_cache': False, 'guard_cache': guard_cache,
                   'guard_cache_hits': guard.hits, 'engine': 'round5'}
