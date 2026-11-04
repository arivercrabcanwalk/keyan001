"""Round-6 throughput engine: identical search semantics, native hot path.

The ALNS inner loop keeps the round-5 control flow.  Solution state, route
statistics, destroy, repair, raw feasibility, the complete physical guard and
the destroy RNG live in the native kernel; Python only chooses operators,
applies the acceptance rule, updates the adaptive weights and tracks the budget.
"""
import copy
import math
import time

from . import fidelity_ops_v5 as ops
from . import greedy
from .round4_runtime import Streams, Runtime
from .java_random import JavaRandom  # noqa: F401
from .evaluator import evaluate  # noqa: F401
from .guard_v5 import Guard
from . import native_kernel

DEFAULT = {'outer_iterations': 500, 'local_iterations': 100, 'alns_iterations': 5000,
           'initial_temperature': 1000., 'cooling_rate': .95, 'final_temperature': .001,
           'weight_lower': .1, 'weight_upper': 5.}

_ENGINE = None
_ENGINE_KEY = None


def get_engine(ins, lib_path=None):
    global _ENGINE, _ENGINE_KEY
    key = (ins.sha256, ins.params, lib_path)
    if _ENGINE is not None and _ENGINE_KEY == key:
        return _ENGINE
    if _ENGINE is not None:
        try:
            _ENGINE.lib.r6_free()
        except Exception:
            pass
        _ENGINE = None
    _ENGINE = native_kernel.NativeEngine(ins, lib_path)
    _ENGINE_KEY = key
    return _ENGINE


def reset_engine():
    global _ENGINE, _ENGINE_KEY
    if _ENGINE is not None:
        try:
            _ENGINE.lib.r6_free()
        except Exception:
            pass
    _ENGINE = None
    _ENGINE_KEY = None


def solve(ins, seed=0, seconds=None, config=None, events=None, removed_tape=None,
          physical_guard=True, rng_mode="split", cache=False, guard_cache=False,
          detail_rng=False, removed_order="input", lib_path=None):
    if detail_rng:
        raise ValueError('round-6 native engine does not record per-draw diagnostics')
    wall_start = time.perf_counter()
    ops.prepare(ins)
    prepare_done = time.perf_counter()
    eng = get_engine(ins, lib_path)
    engine_ready = time.perf_counter()
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
    anytime = {}
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

    def snap(slot):
        return eng.export(slot) if events is not None else None

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
    initialization_done = time.perf_counter()
    initialization_seconds = initialization_done - wall_start

    def tick_anytime(now, best_value):
        if seconds is None:
            return
        elapsed_now = now - wall_start
        for checkpoint in (.25, .5, .75, 1.0):
            key = str(checkpoint)
            deadline = checkpoint * seconds
            if key not in anytime and elapsed_now >= deadline:
                # A solution initialized after a checkpoint did not exist at
                # that checkpoint; do not retroactively report it.
                anytime[key] = (best_value if initialization_done - wall_start <= deadline
                                else None)

    tick_anytime(initialization_done, best_cost)
    temperature = config['initial_temperature']
    outer_done = 0
    trace.append({'elapsed': time.perf_counter() - start, 'cost': best_cost,
                  'evaluations': evaluations, 'solution': ops.physical(best)})

    def alns(sol):
        nonlocal evaluations
        eng.load(0, sol)
        t0 = time.perf_counter()
        cur_cost = eng.cost(0)
        timings['objective'] += time.perf_counter() - t0
        counters['route_set_objectives'] += 1
        evaluations += 1
        eng.clone(0, 2)
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
            t0 = time.perf_counter()
            removed, seed_after, draws = eng.destroy(0, 1, d, destroy_rng.seed)
            timings['destroy'] += time.perf_counter() - t0
            counters['destroy'] += 1
            destroy_rng.seed = seed_after
            destroy_rng.draws.count += draws
            factory.calls += draws
            if removed_tape is not None:
                assert removed_tape, ('removal_tape_exhausted', k)
                ordered = removed_tape.pop(0)
                assert set(ordered) == set(removed), ('removed_set', ordered, removed)
                removed = ordered
            if removed_order == "sorted_id":
                removed = sorted(removed)
            if events is not None:
                emit('destroy', k, d, snap(1), repair_op=r, removed=removed)
            eng.clone(1, 3)
            t0 = time.perf_counter()
            ok = eng.repair(1, r, removed)
            timings['repair'] += time.perf_counter() - t0
            counters['repair'] += 1
            rollback = False
            if not ok:
                rollback = True
            elif not eng.valid(1, True):
                rollback = True
            if rollback:
                eng.clone(3, 1)
                counters['repair_rollback'] += 1
            counters['repair_success' if eng.complete(1) else 'repair_failure'] += 1
            counters['candidate_generated_alns'] += 1
            t0 = time.perf_counter()
            value = eng.cost(1)
            timings['objective'] += time.perf_counter() - t0
            counters['route_set_objectives'] += 1
            evaluations += 1
            improvement = local_cost - value
            accepted = value < cur_cost or mathrng.random() < math.exp((cur_cost - value) / temp)
            if physical_guard:
                t0 = time.perf_counter()
                gok = eng.guard(1)
                timings['physical_guard'] += time.perf_counter() - t0
                counters['complete_physical_checks'] += 1
                if not gok:
                    accepted = False
                    counters['guard_rejections'] += 1
                    counters['candidate_guard_rejections'] += 1
            if events is not None:
                emit('repair', k, r, snap(1), accepted=accepted, temperature=temp,
                     weights_d=weights[0].copy(), weights_r=weights[1].copy(), scores_d=scores[0].copy())
            counters['alns_candidates'] += 1
            if config.get('strict_deadline', False) and not alive():
                accepted = False
                counters['deadline_rejected'] = counters.get('deadline_rejected', 0) + 1
            tick_anytime(time.perf_counter(), best_cost)
            counters['alns_accepted'] += int(accepted)
            counters['candidate_accepted'] += int(accepted)
            if accepted:
                eng.clone(1, 0)
                cur_cost = value
                if value < local_cost:
                    eng.clone(1, 2)
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
                            weights[group][j] = max(config['weight_lower'], min(config['weight_upper'],
                                                            weights[group][j] * .8 + (scores[group][j] / counts[group][j]) * .2))
                    scores[group] = [0.] * 4
                    counts[group] = [0] * 4
            temp *= config['cooling_rate']
        return eng.export(2), local_cost

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
        if config.get('strict_deadline', False) and not alive():
            accepted = False
            counters['deadline_rejected'] = counters.get('deadline_rejected', 0) + 1
        tick_anytime(time.perf_counter(), best_cost)
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
        tick_anytime(time.perf_counter(), best_cost)
    search_end = time.perf_counter()
    tick_anytime(search_end, best_cost)
    finalization_start = time.perf_counter()
    final = ops.physical(best)
    emit('final', config['outer_iterations'], -1, best, best_cost=best_cost, budget_alive=alive())
    finalization_end = time.perf_counter()
    finalization_seconds = finalization_end - finalization_start
    elapsed = finalization_end - wall_start
    search_seconds = search_end - initialization_done
    tick_anytime(finalization_end, best_cost)
    return final, {'algorithm': 'independent_tsalns_v6_native', 'seed': seed,
                   'initial_objective': initial, 'objective': best_cost,
                   'evaluations': evaluations, 'elapsed_seconds': elapsed,
                   'initialization_seconds': initialization_seconds,
                   'search_seconds': search_seconds,
                   'finalization_seconds': finalization_seconds,
                   'precompute_seconds': timings.get('precompute', 0.0),
                   'budget_overrun_seconds': max(0.0, elapsed - seconds) if seconds is not None else 0.0,
                   'termination_reason': ('outer_limit' if outer_done >= config['outer_iterations']
                                          else 'time_budget' if seconds is not None and elapsed >= seconds
                                          else 'completed'),
                   'anytime': anytime,
                   'outer_iterations_attempted': outer_done, 'config': config,
                   'engine_initialization_seconds': engine_ready - prepare_done,
                   'physical_guard': physical_guard,
                   'removed_order': 'recorded_reference_tape' if removed_tape is not None else 'input_target_order; differs from unspecified Java identity-HashSet',
                   'trace': trace, 'timings': dict(timings), 'counters': dict(counters),
                   'termination': 'time_budget' if not alive() else 'configured_iterations',
                   'random_draws': factory.calls, 'rng_mode': rng_mode,
                   'rng_created': dict(factory.counts), 'rng_streams': factory.created,
                   'rng_details': factory.draws, 'route_cache': False, 'guard_cache': guard_cache,
                   'guard_cache_hits': guard.hits, 'engine': 'round6_native'}
