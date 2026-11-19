#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'


def main():
    parser = argparse.ArgumentParser()
    for key in ('project-root', 'binding-dir', 'cache-dir', 'run-root', 'out'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    root, run, out = map(lambda x: Path(x).resolve(), (args.project_root, args.run_root, args.out))
    out.mkdir(parents=True, exist_ok=False)
    g24 = root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz'
    for path in (g24, g24.parent, root / 'reproduction/reviewer_package_semfix',
                 Path(args.binding_dir), Path(args.cache_dir), g24 / 'comparison'):
        sys.path.insert(0, str(path))
    import torch
    import development_runner as runner
    from context_bound_env import make_model, OBSERVATION_SCHEMA
    from route_cache import CachedContextBoundEnv
    from rl_algorithms import behavior_clone_update, masked_policy_distribution
    from run_full_map_smoke import _seed
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    runner.WeatherFullMapEnv = CachedContextBoundEnv
    started = time.perf_counter()
    report = {'status': 'running', 'scope': 'training-only engineering gate; not RL effect or novelty',
              'config': {'seeds': [103, 211, 307], 'epochs': 400, 'lr': 0.001, 'minibatch': 64,
                         'max_grad': 0.5, 'train_wall_s_per_seed': 300, 'rollout_budget_s': 12},
              'heldout_calls': 0, 'rl_updates': 0, 'records': [], 'observation_schema': OBSERVATION_SCHEMA}
    def persist():
        temp = out / 'RESULTS.partial.tmp'
        temp.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
        os.replace(temp, out / 'RESULTS.partial.json')
    def check():
        if time.perf_counter() - started > 1000:
            raise TimeoutError('total1000s_cap')
    def fidelity(model, demos):
        rows = []
        for map_id, demo in demos:
            correct = 0; loss = 0.0
            for item in demo['transitions']:
                with torch.no_grad():
                    dist, _ = masked_policy_distribution(model, item)
                correct += int(torch.argmax(dist.logits)) == item['action']
                loss -= float(dist.log_prob(torch.tensor(item['action'])))
            count = len(demo['transitions'])
            rows.append({'map': map_id, 'matches': correct, 'actions': count, 'nll': loss / count})
        return rows
    try:
        ids = ('opportunity_2', 'opportunity_4')
        cases = {name: runner.load_case(run / 'output' / name) for name in ids}
        demonstrations = runner.read(run / 'output/experiment/DEMONSTRATIONS.json')
        assert tuple(row['map'] for row in demonstrations['records']) == ids
        demos = []
        for row in demonstrations['records']:
            path = run / 'output' / row['map'] / 'author/solution.json'
            assert runner.sha(path) == row['solution_sha256']
            demo = runner.author_demonstration(cases[row['map']], runner.read(path), max_steps=128, deadline=60)
            assert json.loads(json.dumps(demo['result']['replay'])) == row['replay']
            assert len(demo['transitions']) == row['action_count']
            demos.append((row['map'], demo))
        demo_elapsed = time.perf_counter() - started
        report['demonstration_actions'] = sum(len(demo['transitions']) for _, demo in demos)
        report['demonstration_preparation_s'] = demo_elapsed
        report['source_hashes'] = {str(p): runner.sha(p) for p in [Path(__file__),
            Path(args.binding_dir) / 'context_bound_env.py', Path(args.cache_dir) / 'route_cache.py',
            run / 'output/experiment/DEMONSTRATIONS.json']}
        persist()
        for seed in (103, 211, 307):
            check()
            seed_started = time.perf_counter()
            record = {'seed': seed, 'status': 'running', 'teacher_history': [], 'rollouts': [],
                      'demonstration_preparation_s_charged': demo_elapsed}
            report['records'].append(record)
            try:
                _seed(seed)
                model = make_model(hidden_dim=64)
                optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
                record['teacher_history'].append({'epoch': 0, 'maps': fidelity(model, demos)})
                for chunk, epochs in ((100, 100), (200, 100), (400, 200)):
                    remaining = 300 - demo_elapsed - (time.perf_counter() - seed_started)
                    if remaining <= 0:
                        raise TimeoutError('seed300s_cap')
                    record['last_bc_stats'] = behavior_clone_update(model, optimizer, [d for _, d in demos],
                        epochs=epochs, minibatch=64, max_grad=0.5,
                        rng=random.Random(seed * 1000003 + chunk), deadline=remaining)
                    record['teacher_history'].append({'epoch': chunk, 'maps': fidelity(model, demos)})
                    persist()
                checkpoint = out / f'bc_context44_seed{seed}_last.pt'
                torch.save({'state_dict': model.state_dict(), 'global_dim': CachedContextBoundEnv.global_dim,
                            'candidate_dim': CachedContextBoundEnv.candidate_dim, 'hidden_dim': 64,
                            'observation_schema': OBSERVATION_SCHEMA, 'seed': seed,
                            'epochs': 400, 'regime': 'BC-only'}, checkpoint)
                record['checkpoint_sha256'] = runner.sha(checkpoint)
                record['checkpoint'] = checkpoint.name
                for map_id in ids:
                    episode = runner.run_episode(cases[map_id], model, deadline=12, max_steps=128)
                    episode.pop('transitions')
                    teacher = next(d for name, d in demos if name == map_id)['events']
                    divergent = None
                    for index, (actual, expected) in enumerate(zip(episode['events'], teacher)):
                        if any(actual[k] != expected[k] for k in ('station_idx', 'slot', 'target')):
                            divergent = index; break
                    record['rollouts'].append({'map': map_id, 'first_serialized_teacher_deviation': divergent,
                                               'episode': episode})
                if time.perf_counter() - seed_started + demo_elapsed > 300:
                    raise TimeoutError('seed300s_cap')
                record['status'] = 'completed'
            except Exception as error:
                record.update(status='failed', error=f'{type(error).__name__}: {error}')
            record['elapsed_s'] = time.perf_counter() - seed_started
            persist()
        report['gate_pass'] = len(report['records']) == 3 and all(
            r['status'] == 'completed' and len(r['rollouts']) == 2 and all(
                row['episode']['complete'] and row['episode']['result']['replay']['admissible']
                for row in r['rollouts']) for r in report['records'])
        report['status'] = 'completed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}', gate_pass=False)
    report['elapsed_s'] = time.perf_counter() - started
    (out / 'RESULTS.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'status': report['status'], 'gate_pass': report['gate_pass'], 'records': len(report['records']),
                      'elapsed_s': report['elapsed_s'], 'rl_updates': 0, 'heldout_calls': 0}, sort_keys=True))
    if report['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
