"""Serial, prospective resource envelope; EXECUTION_HOST only."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time

assert socket.gethostname() == 'EXECUTION_HOST', 'HN01_ONLY'
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
JOBS = {
    'BUILD': (15, 25, ['validation/fullsolve_driver.py', 'build']),
    'BASELINE': (5, 10, ['validation/stages.py', 'baseline', 'runs/BASELINE/results']),
    'MODIFIED': (40, 50, ['validation/stages.py', 'modified', 'runs/MODIFIED/results']),
    'ROLLBACK': (15, 25, ['validation/stages.py', 'rollback', 'runs/ROLLBACK/results']),
    'AUDIT': (5, 10, ['validation/stages.py', 'audit', 'runs/AUDIT/results']),
}

phase = sys.argv[1]
assert phase in JOBS
cpu, wall, command = JOBS[phase]
manifest = json.loads((ROOT / 'FROZEN_MANIFEST.json').read_text())
for rel, h in manifest.items():
    assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h, ('FROZEN_HASH_CHANGED', rel)
lock = (ROOT / '.phase.lock').open('w')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
starts = list((ROOT / 'runs').glob('*/START.json'))
terms = list((ROOT / 'runs').glob('*/TERMINAL.json'))
assert {p.parent for p in starts} == {p.parent for p in terms}, 'PREVIOUS_PHASE_NOT_TERMINAL'
assert len(starts) < 5
spent_cpu = sum(json.loads(p.read_text())['cpu_s'] for p in terms)
spent_wall = sum(json.loads(p.read_text())['wall_s'] for p in terms)
assert spent_cpu + cpu <= 80 and spent_wall + wall <= 120, 'AGGREGATE_RESOURCE_LIMIT'
loc = ROOT / 'runs' / phase
loc.mkdir(parents=True, exist_ok=False)
argv = [sys.executable, *command]
record = dict(phase=phase, hostname=socket.gethostname(), command=argv, cwd=str(ROOT),
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              cpu_limit_s=cpu, wall_limit_s=wall, address_limit_bytes=2 * 1024**3)
(loc / 'START.json').write_text(json.dumps(record, indent=2) + '\n')


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))


t0 = time.monotonic()
before = resource.getrusage(resource.RUSAGE_CHILDREN)
env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0',
       'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}
child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True, preexec_fn=limits, env=env)
timeout = False
try:
    out, err = child.communicate(timeout=wall)
    code = child.returncode
except subprocess.TimeoutExpired:
    timeout = True
    os.killpg(child.pid, signal.SIGKILL)
    out, err = child.communicate()
    code = 124
after = resource.getrusage(resource.RUSAGE_CHILDREN)
(loc / 'stdout.txt').write_bytes(out)
(loc / 'stderr.txt').write_bytes(err)
record.update(exit_status=code, phase_timed_out=timeout, wall_s=time.monotonic() - t0,
              cpu_s=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
              child_maxrss_kib=after.ru_maxrss,
              stdout=out.decode(errors='replace'), stderr=err.decode(errors='replace'),
              finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(loc / 'TERMINAL.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, sort_keys=True))
raise SystemExit(code)
