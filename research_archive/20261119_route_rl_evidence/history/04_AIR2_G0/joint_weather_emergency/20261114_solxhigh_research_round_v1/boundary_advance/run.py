"""Frozen once-only finite boundary validation and independent-copy rollback."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import resource
import shutil
import socket
import subprocess
import sys
import time

assert socket.gethostname() == '<COMPUTE_HOST>', '<REMOVED_ENDPOINT>_ONLY'
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
intent = json.loads(Path('RUN_INTENT.json').read_text())
assert intent['status'] == 'FROZEN'
for row in json.loads(Path('FROZEN_MANIFEST.json').read_text()):
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256'], row
Path('runs').mkdir(exist_ok=False)
receipts = []


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (8, 9))
    resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))


def execute(phase, command, inputs):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    result = subprocess.run(command, text=True, capture_output=True, timeout=15,
                            preexec_fn=limits,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = {'phase': phase, 'command': command, 'input': inputs,
              'stdout_literal': result.stdout, 'stderr_literal': result.stderr,
              'exit_status': result.returncode, 'wall_s': time.perf_counter() - started,
              'child_cpu_s': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
              'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    receipts.append(record)
    Path('runs/COMMAND_RECEIPTS.json').write_text(json.dumps(receipts, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    assert result.returncode == 0, record
    assert sum(row['child_cpu_s'] for row in receipts) <= intent['cpu_seconds_total']
    assert sum(row['wall_s'] for row in receipts) <= intent['wall_seconds_total']


execute('BASELINE', [sys.executable, 'validate.py', 'ORIGINALS/air2_before.py',
                    'BASELINE', 'runs/BASELINE.json'], 'INPUT.json; arbitrary-action force used as boundary adapter')
execute('MODIFIED', [sys.executable, 'validate.py', 'MODIFIED_FILE.py',
                    'MODIFIED', 'runs/MODIFIED.json'], 'same INPUT.json; dedicated next-token boundary adapter')
Path('ROLLBACK_COPY').mkdir(exist_ok=False)
shutil.copy2('MODIFIED_FILE.py', 'ROLLBACK_COPY/MODIFIED_FILE.py')
execute('ROLLBACK_APPLY', ['/bin/sh', 'ROLLBACK.sh', str(ROOT / 'ROLLBACK_COPY')],
        'independent modified copy; original bytes restored')
execute('ROLLBACK', [sys.executable, 'validate.py', 'ROLLBACK_COPY/MODIFIED_FILE.py',
                    'ROLLBACK', 'runs/ROLLBACK.json'], 'same INPUT.json; restored original behavior')
baseline = json.loads(Path('runs/BASELINE.json').read_text())
rollback = json.loads(Path('runs/ROLLBACK.json').read_text())
for key in ('source_sha256', 'preserved', 'cases_total', 'invalid_next_rejected', 'rows', 'rejects', 'status'):
    assert baseline[key] == rollback[key], key
manifest = {row['path']: row['sha256'] for row in json.loads(Path('FROZEN_MANIFEST.json').read_text())}
assert hashlib.sha256(Path('MODIFIED_FILE.py').read_bytes()).hexdigest() == manifest['MODIFIED_FILE.py']
summary = {'status': 'FINITE_BOUNDARY_ADAPTER_PASS_NOT_AIR2_OR_G3',
           'baseline_preserved': baseline['preserved'],
           'modified_preserved': json.loads(Path('runs/MODIFIED.json').read_text())['preserved'],
           'cases_total': baseline['cases_total'], 'rollback_matches_baseline': True,
           'main_modified_retained': True, 'source_repairs': 0,
           'total_child_cpu_s': sum(row['child_cpu_s'] for row in receipts),
           'total_phase_wall_s': sum(row['wall_s'] for row in receipts),
           'physical_solver_runs': 0, 'new_scientific_maps': 0, 'training': 0, 'Formal': 0}
Path('runs/SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, sort_keys=True))
