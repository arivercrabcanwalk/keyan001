#!/usr/bin/env python3
"""Read-only teacher-forced diagnostics over saved training maps/checkpoints."""
import argparse
import cProfile
import hashlib
import json
import math
import os
from pathlib import Path
import pstats
import sys
import time

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--run-root', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root, run, out = map(lambda p: Path(p).resolve(), (args.project_root, args.run_root, args.out))
    out.mkdir(parents=True, exist_ok=False)
    g24 = root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz'
    sys.path.insert(0, str(g24 / 'comparison'))
    import development_runner as runner
    import numpy as np
    import torch
    from weather_policy import WeatherPointerActorCritic
    from rl_algorithms import masked_policy_distribution
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    started = time.perf_counter()
    report = {'scope': 'retrospective training-only teacher-forced diagnostic', 'status': 'running',
              'script_sha256': sha(__file__), 'results_sha256': sha(run / 'output/experiment/RESULTS.json'),
              'training_updates': 0, 'heldout_calls': 0, 'online_rollouts': 0, 'rows': []}
    def check():
        if time.perf_counter() - started > 180:
            raise TimeoutError('diagnostic_180s_cap')
    try:
        results = runner.read(run / 'output/experiment/RESULTS.json')
        expected = runner.read(run / 'output/experiment/DEMONSTRATIONS.json')
        assert [x['map'] for x in expected['records']] == ['opportunity_2', 'opportunity_4']
        demos = []
        profiler = cProfile.Profile()
        profiler.enable()
        for row in expected['records']:
            check()
            solution_path = run / 'output' / row['map'] / 'author/solution.json'
            assert sha(solution_path) == row['solution_sha256']
            demo = runner.author_demonstration(runner.load_case(solution_path.parent.parent), runner.read(solution_path),
                                              max_steps=128, deadline=max(0, 180 - (time.perf_counter() - started)))
            assert len(demo['transitions']) == row['action_count']
            assert json.loads(json.dumps(demo['result']['replay'], allow_nan=False)) == row['replay']
            demos.append((row['map'], demo))
        profiler.disable()
        profiler.dump_stats(str(out / 'demonstration_reconstruction.prof'))
        stats = pstats.Stats(profiler)
        profile_rows = []
        for (filename, line, name), (cc, nc, tt, ct, callers) in stats.stats.items():
            if ('weather_' in filename and name in ('_weather_route', '_route_with_primary_oracle', 'plan_route',
                                                     '_project_target', '_project_return', '_legal', 'observation')):
                profile_rows.append({'file': Path(filename).name, 'line': line, 'function': name,
                                     'primitive_calls': cc, 'total_calls': nc, 'self_s': tt, 'cumulative_s': ct})
        report['reconstruction_elapsed_s'] = time.perf_counter() - started
        report['profile'] = sorted(profile_rows, key=lambda r: -r['cumulative_s'])
        report['demonstration_actions'] = sum(len(x['transitions']) for _, x in demos)
        for record in results['controls'] + results['training']:
            check()
            path = run / 'output/experiment' / record['checkpoint']
            assert sha(path) == record['checkpoint_sha256']
            ckpt = torch.load(path, map_location='cpu', weights_only=True)
            model = WeatherPointerActorCritic(global_dim=ckpt['global_dim'], candidate_dim=ckpt['candidate_dim'],
                                              hidden_dim=ckpt['hidden_dim'])
            model.load_state_dict(ckpt['state_dict'], strict=True)
            model.eval()
            for map_id, demo in demos:
                correct = collision_labels = ties = 0
                nll = 0.0
                probabilities = []
                for item in demo['transitions']:
                    check()
                    with torch.no_grad():
                        dist, _ = masked_policy_distribution(model, item)
                    action = item['action']
                    logits = dist.logits.detach().cpu().numpy()
                    prediction = int(np.argmax(logits))
                    correct += prediction == action
                    ties += int(np.count_nonzero(logits == logits[prediction]) > 1)
                    legal = np.flatnonzero(item['mask'])
                    collision_labels += int(any(int(i) != action and
                        np.array_equal(item['candidates'][i], item['candidates'][action]) for i in legal))
                    probability = float(dist.probs[action])
                    probabilities.append(probability)
                    nll -= float(dist.log_prob(torch.tensor(action)))
                count = len(demo['transitions'])
                report['rows'].append({'regime': record['training_regime'], 'seed': record['seed'], 'map': map_id,
                                       'checkpoint_sha256': sha(path), 'actions': count, 'top1_matches': int(correct),
                                       'top1_accuracy': correct / count, 'mean_teacher_nll': nll / count,
                                       'minimum_teacher_probability': min(probabilities), 'top1_tied_states': ties,
                                       'label_candidate_collision_states': collision_labels})
        report['status'] = 'completed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    report['elapsed_s'] = time.perf_counter() - started
    (out / 'RESULTS.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'status': report['status'], 'rows': len(report['rows']), 'elapsed_s': report['elapsed_s'],
                      'training_updates': 0, 'heldout_calls': 0, 'error': report.get('error')}, sort_keys=True))
    if report['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
