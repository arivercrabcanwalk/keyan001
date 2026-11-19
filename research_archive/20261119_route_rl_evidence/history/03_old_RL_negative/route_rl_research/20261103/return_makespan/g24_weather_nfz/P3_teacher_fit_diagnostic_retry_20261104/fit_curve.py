#!/usr/bin/env python3
"""TRAIN-state-only supervised fit diagnostic for the closed P3 BC checkpoint."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import signal
import time

P3_ROOT = Path('<EXECUTION_PATH>')
AUDIT_ROOT = Path('<EXECUTION_PATH>')
OUT_NAME = 'RESULT.json'
RUN_ID = 'p3_teacher_fit_diagnostic_retry_v1'
REG_SHA = '4f7f72b10c581d72fd2889f323904b9bc8181d11713960928e1b4964f6e7a574'
STATES_SHA = 'b6b3de8bc1aca783d76b80fa5f4e937638e6512c63aac1d15debb5a4cd3b5eeb'
AUDIT_RESULT_SHA = '9dbc6b111446ca5104e92dbc9d2506d45d699c49879a5925ab3bbcd43a29c79f'
CKPT_SHA = 'cf7450136da5855fd521a11d498e918d3f4e8c3edc1d6f33e2a58f4cbfa93b58'
PROGRESS_SHA = '51027cea920ab9fda1e0d621e870e106331a4ca0ec21c60eaf08778bcf8c3c22'
TRAINER_SHA = '4046f35c5e2d11cdd291c2c7ff080870b6b0a4a705e840753b4817f5e3bda4e0'
CONTEXT_SHA = '5aecc7eab9dbde9d8c4aabd0c406ec619e558c0afc8f643fbc1f9a6462a8f024'
POLICY_SHA = '6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826'
RL_SHA = 'a9679133e93b3d2edf613102667827ad02427d49cfcea657d930b1004eb029fd'
PRIOR_RESULT_SHA = '7a9e59e221605c40bfa93099df2a9ec8018448cfc02d6643a70f0776bca0ca50'
EXPECTED_MODEL = 'b10e1bebae97a9a9c3fcb6b00ad4e56076fe00ff992464c137bd3ec3cbc4afbc'
EXPECTED_OPTIMIZER = 'cb72bb56d03d180eddb9b26828e47dabdd3e208c5f565c6c905032020db0f8bf'
SEED = 103
EPOCHS = 2000
BATCH_SIZE = 64
EVALUATION_EPOCHS = frozenset((0, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000))
WALL_SECONDS = 900


class FitDeadline(BaseException):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    os.replace(tmp, path)


def check(path, expected):
    observed = sha(path)
    if observed != expected:
        raise ValueError(f'hash mismatch: {path}')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data_items(states):
    if len(states) != 138:
        raise ValueError('expected exactly 138 audited teacher states')
    expected = {'TRAIN_1': 26, 'TRAIN_3': 28, 'TRAIN_4': 28, 'TRAIN_5': 28, 'TRAIN_6': 28}
    counts = {key: 0 for key in expected}
    items = []
    for row in states:
        name = row['map']
        if name not in counts:
            raise ValueError('unexpected non-TRAIN audit state')
        counts[name] += 1
        action = int(row['label_index'])
        mask = row['mask']
        candidates = row['candidate_features']
        global_features = row['global_features']
        if not (0 <= action < len(mask) == len(candidates)) or not bool(mask[action]):
            raise ValueError('audited teacher label is not legal')
        if not global_features or not candidates or any(not isinstance(x, bool) for x in mask):
            raise ValueError('invalid audited observation encoding')
        items.append({'global': global_features, 'candidates': candidates, 'mask': mask, 'action': action})
    if counts != expected:
        raise ValueError(f'map-state denominator mismatch: {counts}')
    return items


def evaluate(model, items, distribution):
    import torch
    model.eval()
    correct = 0
    nll_sum = 0.0
    with torch.no_grad():
        for item in items:
            dist, _ = distribution(model, item)
            top = int(torch.argmax(dist.logits))
            correct += int(top == item['action'])
            nll_sum -= float(dist.log_prob(torch.tensor(item['action'])))
    return {'teacher_correct': correct, 'teacher_states': len(items),
            'teacher_accuracy': correct / len(items), 'mean_teacher_NLL': nll_sum / len(items)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    out = Path(args.out).resolve()
    if out.is_relative_to(P3_ROOT) or out.is_relative_to(AUDIT_ROOT):
        raise ValueError('diagnostic output must be separate from every frozen input')
    out.mkdir(parents=True, exist_ok=False)
    deadline = started + WALL_SECONDS
    result = {
        'schema': 'p3_teacher_fit_diagnostic_v1',
        'run_id': RUN_ID,
        'attempt': 2,
        'prior_attempt': {
            'result_sha256': PRIOR_RESULT_SHA,
            'terminal_status': 'failed',
            'terminal_error': 'FitDeadline: 120s_fit_guard',
            'interpretation': 'No 400-epoch reproduction point was reached; its output remains preserved separately.',
        },
        'status': 'started',
        'diagnostic_only': True,
        'seed': SEED,
        'max_wall_s': WALL_SECONDS,
        'max_epochs': EPOCHS,
        'batch_size': BATCH_SIZE,
        'learning_rate': 0.001,
        'gradient_clip_norm': 0.5,
        'free_policy_rollouts': 0,
        'VAL_reads': 0,
        'solver_calls': 0,
        'new_maps': 0,
        'models_saved': 0,
        'evaluations': [],
        'error': None,
    }
    original_handler = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(FitDeadline('900s_fit_guard')))
    signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - time.perf_counter()))
    checkpoint = P3_ROOT / 'output/training/common_103/common_last.pt'
    try:
        root = P3_ROOT / 'lunwen'
        package = root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz/next_stage_protocol_sol_20261104/ordinary_rl_attribution_pilot/P3_fixed_population/implementation'
        checks = (
            (P3_ROOT / 'REGISTRATION.json', REG_SHA),
            (AUDIT_ROOT / 'output/STATES.json', STATES_SHA),
            (AUDIT_ROOT / 'output/RESULT.json', AUDIT_RESULT_SHA),
            (checkpoint, CKPT_SHA),
            (P3_ROOT / 'output/training/common_103/PROGRESS.json', PROGRESS_SHA),
            (package / 'trainer.py', TRAINER_SHA),
            (root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz/engineering_v4_context_binding/context_bound_env.py', CONTEXT_SHA),
            (root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_policy.py', POLICY_SHA),
            (root / 'route_rl_research/20261103/return_makespan/g24_weather_nfz/rl_algorithms.py', RL_SHA),
        )
        for path, expected in checks:
            check(path, expected)
        progress = read(P3_ROOT / 'output/training/common_103/PROGRESS.json')
        if (progress['tensor_sha256'], progress['optimizer_sha256'], progress['checkpoint_sha256'],
                progress['completed_epochs'], progress['gradient_steps']) != (EXPECTED_MODEL, EXPECTED_OPTIMIZER, CKPT_SHA, 400, 1200):
            raise ValueError('P3 completed-BC identity mismatch')
        states = read(AUDIT_ROOT / 'output/STATES.json')
        items = data_items(states)
        trainer = load('p3_fit_trainer', package / 'trainer.py')
        trainer.setup(root)
        import random
        import torch
        from context_bound_env import make_model
        from rl_algorithms import masked_policy_distribution
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        reference_model, reference_optimizer, reference_payload = trainer.load_clone(checkpoint, CKPT_SHA)
        if (trainer.state_digest(reference_model.state_dict()) != EXPECTED_MODEL
                or trainer.state_digest(reference_optimizer.state_dict()) != EXPECTED_OPTIMIZER
                or reference_payload['seed'] != SEED or reference_payload['regime'] != 'common_bc'):
            raise ValueError('reference checkpoint payload/state mismatch')
        del reference_model, reference_optimizer, reference_payload
        torch.manual_seed(SEED)
        rng = random.Random(SEED)
        model = make_model(hidden_dim=64)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        result['evaluations'].append({'epoch': 0, 'gradient_steps': 0, 'model_digest': trainer.state_digest(model.state_dict()),
                                      'optimizer_digest': trainer.state_digest(optimizer.state_dict()),
                                      **evaluate(model, items, masked_policy_distribution)})
        for epoch in range(1, EPOCHS + 1):
            if time.perf_counter() >= deadline:
                raise FitDeadline('900s_fit_guard')
            model.train()
            order = list(range(len(items)))
            rng.shuffle(order)
            for start in range(0, len(order), BATCH_SIZE):
                if time.perf_counter() >= deadline:
                    raise FitDeadline('900s_fit_guard')
                trainer.supervised_batch(model, optimizer, [items[index] for index in order[start:start + BATCH_SIZE]])
            result['last_completed_epoch'] = epoch
            result['last_completed_gradient_steps'] = epoch * math.ceil(len(items) / BATCH_SIZE)
            if epoch in EVALUATION_EPOCHS:
                point = {'epoch': epoch, 'gradient_steps': epoch * math.ceil(len(items) / BATCH_SIZE),
                         'model_digest': trainer.state_digest(model.state_dict()),
                         'optimizer_digest': trainer.state_digest(optimizer.state_dict()),
                         **evaluate(model, items, masked_policy_distribution)}
                result['evaluations'].append(point)
                if epoch == 400:
                    result['checkpoint_reproduced_at_epoch_400'] = (
                        point['model_digest'] == EXPECTED_MODEL and point['optimizer_digest'] == EXPECTED_OPTIMIZER
                    )
                    if not result['checkpoint_reproduced_at_epoch_400']:
                        raise ValueError('400-epoch checkpoint reproduction failed')
                if point['teacher_correct'] == len(items):
                    result['first_observed_exact_fit_epoch'] = epoch
                    break
        final = result['evaluations'][-1]
        result.update(status='completed', epochs_completed=final['epoch'], gradient_steps_completed=final['gradient_steps'],
                      final_teacher_correct=final['teacher_correct'], final_teacher_accuracy=final['teacher_accuracy'],
                      final_mean_teacher_NLL=final['mean_teacher_NLL'],
                      exact_fit_observed='first_observed_exact_fit_epoch' in result)
    except BaseException as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        result.update(elapsed_s=time.perf_counter() - started, deadline_met=time.perf_counter() <= deadline,
                      source_checkpoint_sha256_after=sha(checkpoint) if checkpoint.exists() else None,
                      source_checkpoint_unchanged=checkpoint.exists() and sha(checkpoint) == CKPT_SHA,
                      audit_states_sha256_after=sha(AUDIT_ROOT / 'output/STATES.json') if (AUDIT_ROOT / 'output/STATES.json').exists() else None,
                      audit_states_unchanged=(AUDIT_ROOT / 'output/STATES.json').exists() and sha(AUDIT_ROOT / 'output/STATES.json') == STATES_SHA)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, original_handler)
        write(out / OUT_NAME, result)
    print(json.dumps({key: result.get(key) for key in ('status', 'error', 'elapsed_s', 'checkpoint_reproduced_at_epoch_400',
                                                        'epochs_completed', 'final_teacher_accuracy', 'exact_fit_observed',
                                                        'source_checkpoint_unchanged', 'audit_states_unchanged')}, sort_keys=True), flush=True)
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
