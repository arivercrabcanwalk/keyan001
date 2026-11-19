"""New finite AIR2 component checks; all numerical execution is <COMPUTE_HOST>-only."""
from copy import deepcopy
from pathlib import Path
import hashlib
import importlib.util
import json
import socket
import sys
import time

assert socket.gethostname() == '<COMPUTE_HOST>', '<REMOVED_ENDPOINT>_ONLY'
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'frozen'))
from baselines import problem, wind_scorer
from global_env import StationRouteEnv, RouteAction

phase = sys.argv[1]
source = ROOT / {'BASELINE': 'ORIGINALS/compiler.py', 'MODIFIED': 'MODIFIED_FILE.py',
                 'ROLLBACK': 'ROLLBACK_COPY/MODIFIED_FILE.py'}[phase]
spec = importlib.util.spec_from_file_location('air2_subject', source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
inputs = json.loads((ROOT / 'INPUT.json').read_text())
started = time.perf_counter()


def check():
    if time.perf_counter() - started > 55:
        raise TimeoutError('FROZEN_COMPONENT_WALL_BUDGET')


def solution_routes(station):
    return [[list(trip) for trip in mod.routes(sl)] for sl in station]


def action_tokens(station, enabled):
    actions = []
    for k in enabled:
        done, prefix, suffix, future = station[k]
        full = mod.routes(station[k])
        pending = full[len(done):]
        if not pending:
            continue
        next_trip = pending[0]
        assert next_trip[:len(prefix)] == prefix
        actions.append((k, next_trip[len(prefix)] if len(next_trip) > len(prefix) else None))
    return tuple(actions)


def group_order_id(station):
    # Remove slot labels but retain target group and its directed internal order.
    return tuple(sorted(trip for sl in station for trip in mod.routes(sl)))


records = []
total_scoring = 0
total_commits = 0
for fixture in inputs['cases']:
    targets = tuple(problem.Node(j, *row) for j, row in enumerate(fixture['targets'], 1))
    stations = tuple(problem.Node(10001 + j, *xy, 0, 0) for j, xy in enumerate(fixture['stations']))
    identity = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
    instance = problem.Instance(fixture['id'], targets, stations, identity, problem.Parameters())
    anchor_solution = problem.empty_solution(instance, fixture['types'])
    anchor_solution['routes'] = fixture['routes']
    anchor_solution['physics_sha256'] = wind_scorer.physics_identity(instance, tuple(inputs['wind']))
    anchor = wind_scorer.CostAnchor.from_solution(instance, anchor_solution, wind=tuple(inputs['wind']))
    for prefix_on in (False, True):
        compiled = []
        for si, raw_station in enumerate(fixture['routes']):
            enabled = (1,) if fixture['types'][si] == 1 else (0, 1)
            station = []
            for k, trips in enumerate(raw_station):
                trips = tuple(tuple(trip) for trip in trips)
                first, future = (trips[0], trips[1:]) if trips else ((), ())
                prefix = first[:1] if prefix_on and si == 0 and k == enabled[0] else ()
                station.append(((), prefix, first[len(prefix):], future))
            station = tuple(station)
            count = [0]

            def scorer(candidate):
                global total_scoring
                check()
                count[0] += 1
                total_scoring += 1
                solution = anchor.solution()
                solution['routes'][si] = solution_routes(candidate)
                sc = wind_scorer.score_solution(instance, solution, wind=anchor.wind)
                if not sc['original_feasible']:
                    return None
                assert tuple(sorted(sc['target_station'].items())) == anchor.target_station
                duties = [r['duty_min'] for r in sc['slot_duty'] if r['station'] == si]
                return {'full_single_replacement_cost': sc['cost'], 'local_M': max(duties),
                        'duties': duties, 'full_single_replacement_over_cap':
                        not wind_scorer.cost_within_cap(sc['cost'], anchor.cost)}

            old_rows = []
            for candidate in mod.neighborhood(station, inputs['row_limit'], check):
                receipt = scorer(candidate)
                if receipt is not None:
                    old_rows.append({'station': candidate, 'actions': action_tokens(candidate, enabled),
                                     'score': receipt})
            old_groups = {group_order_id(row['station']) for row in old_rows}
            before_compile = count[0]
            compile_started = time.perf_counter()
            if phase == 'MODIFIED':
                table = mod.compile_pair_rows(station, enabled, scorer,
                                              row_limit=inputs['row_limit'], check=check)
                rows = table['rows']
                for row in rows:
                    assert row['actions'] == action_tokens(row['station'], enabled)
                expected = {}
                for ri, row in enumerate(rows):
                    for action in action_tokens(row['station'], enabled):
                        expected.setdefault(mod.canonical(action), []).append(ri)
                assert expected == table['buckets'], 'ACTION_BUCKET_MISMATCH'
            else:
                table = {'status': 'OLD_SINGLE_RELOCATION_COMPONENT', 'rows': old_rows}
                rows = old_rows
            compile_wall = time.perf_counter() - compile_started
            novel = [row for row in rows if group_order_id(row['station']) not in old_groups]
            for row in rows:
                candidate = row['station']
                assert all(candidate[k][:2] == station[k][:2] for k in (0, 1))
                for k, a in row['actions']:
                    post = mod.force(candidate, k, a)
                    lock = mod.force(station, k, a)
                    assert solution_routes(post) == solution_routes(candidate)
                    assert all(post[j][:2] == lock[j][:2] for j in (0, 1))
                    total_commits += 1
            # Replay one complete new witness through the unmodified environment.
            chosen = (novel or rows)[0]
            env = StationRouteEnv(instance, si, fixture['types'][si],
                                  [a for k in enabled for tr in raw_station[k] for a in tr],
                                  wind=anchor.wind)
            for k in enabled:
                for trip in mod.routes(chosen['station'][k]):
                    for a in trip:
                        assert env.legal(RouteAction(k, a))
                        env.step(RouteAction(k, a))
                    assert env.legal(RouteAction(k, None))
                    env.step(RouteAction(k, None))
            assert env.done
            for k in enabled:
                assert abs(env.cumulative_duty[k] - chosen['score']['duties'][k]) <= 1e-7
            sharing = None
            if phase == 'MODIFIED' and fixture['id'] == 'E3' and not prefix_on:
                recompute_start = count[0]
                same = True
                for action_key, ids in table['buckets'].items():
                    again = mod.compile_pair_rows(station, enabled, scorer,
                                                  row_limit=inputs['row_limit'], check=check)
                    selected = [again['rows'][j]['station'] for j in again['buckets'].get(action_key, [])]
                    same &= selected == [rows[j]['station'] for j in ids]
                extra_calls = count[0] - recompute_start
                shared_calls = table['distinct_structural_candidates_scored']
                sharing = {'identical_buckets': same, 'shared_scorer_calls': shared_calls,
                           'per_action_recompile_scorer_calls': extra_calls}
                assert same and extra_calls > shared_calls
            compiled.append({'station': si, 'input_station': station, 'rows': rows,
                             'old_valid_rows': len(old_rows), 'novel_group_order_rows': len(novel),
                             'compile_scorer_calls': count[0] - before_compile,
                             'compile_wall_s': compile_wall, 'sharing': sharing})
        finance = None
        if phase == 'MODIFIED' and fixture['id'] == 'E2' and not prefix_on:
            H = anchor.makespan
            donors = [row for row in compiled[1]['rows'] if row['score']['local_M'] <= H]
            donor = min(donors, key=lambda row: row['score']['full_single_replacement_cost'])
            for row in compiled[0]['rows']:
                if not row['score']['full_single_replacement_over_cap'] or row['score']['local_M'] > H:
                    continue
                combined = anchor.solution()
                combined['routes'][0] = solution_routes(row['station'])
                combined['routes'][1] = solution_routes(donor['station'])
                sc = wind_scorer.validate_candidate(instance, combined, anchor)
                if sc['admissible'] and sc['M_return'] <= H:
                    finance = {'status': 'COMPLETE_CAP_COMPENSATION_FOUND', 'solution': combined,
                               'score': sc, 'recipient_single_cost': row['score']['full_single_replacement_cost'],
                               'anchor_cost': anchor.cost}
                    break
            if finance is None:
                finance = {'status': 'NO_COMPENSATION_IN_FROZEN_E2_AT_ANCHOR_H',
                           'consequence': 'close this fixture financing prediction; do not adjust input'}
        records.append({'fixture': fixture['id'], 'prefix_on': prefix_on,
                        'anchor_cost': anchor.cost, 'anchor_M': anchor.makespan,
                        'stations': compiled, 'financing': finance})
        (ROOT / 'runs' / (phase + '_DETAILS.json')).write_text(json.dumps(records) + '\n')
novel_count = sum(st['novel_group_order_rows'] for r in records for st in r['stations'])
if phase == 'MODIFIED':
    assert novel_count > 0, 'P1_NO_NEW_LEGAL_GROUP_OR_ORDER'
result = {'phase': phase, 'status': 'FINITE_COMPONENT_PASS' if phase == 'MODIFIED' else 'OLD_COMPONENT_RECORDED',
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'configurations': len(records), 'station_tables': sum(len(r['stations']) for r in records),
          'novel_group_order_rows': novel_count, 'physical_scorer_calls_including_repeats': total_scoring,
          'post_force_action_checks': total_commits,
          'financing_status': [r['financing']['status'] for r in records if r['financing']],
          'training': 0, 'new_scientific_maps': 0, 'scientific_qualification': False}
(ROOT / 'runs' / (phase + '.json')).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, sort_keys=True))
