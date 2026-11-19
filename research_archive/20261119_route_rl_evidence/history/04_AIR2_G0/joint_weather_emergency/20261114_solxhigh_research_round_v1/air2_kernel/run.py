"""Once-only bounded <COMPUTE_HOST> AIR2 component transaction; no model/author solves."""
from pathlib import Path
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
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['sha256']
Path('runs').mkdir(exist_ok=False)
receipts = []


def execute(phase, command, cpu_cap, wall_cap, inputs):
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_cap, cpu_cap+1))
        resource.setrlimit(resource.RLIMIT_AS, (1073741824, 1073741824))
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    p = subprocess.run(command, text=True, capture_output=True, timeout=wall_cap, preexec_fn=limits,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'phase': phase, 'command': command, 'input': inputs,
               'stdout_literal': p.stdout, 'stderr_literal': p.stderr, 'exit_status': p.returncode,
               'wall_s': time.perf_counter()-start,
               'child_cpu_s': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime}
    receipts.append(receipt)
    Path('runs/COMMAND_RECEIPTS.json').write_text(json.dumps(receipts, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
    assert p.returncode == 0
    assert sum(r['child_cpu_s'] for r in receipts) <= intent['cpu_seconds_total']
    assert sum(r['wall_s'] for r in receipts) <= intent['wall_seconds_total']


execute('BASELINE', [sys.executable, 'validate.py', 'BASELINE'], 20, 30, 'INPUT.json; OLD_1RELOC')
execute('MODIFIED', [sys.executable, 'validate.py', 'MODIFIED'], 60, 70, 'same INPUT.json; AIR2')
execute('AUDIT', [sys.executable, 'audit.py'], 70, 80, 'runs/MODIFIED_DETAILS.json; original scorer')
Path('ROLLBACK_COPY').mkdir(exist_ok=False)
shutil.copy2('MODIFIED_FILE.py', 'ROLLBACK_COPY/MODIFIED_FILE.py')
execute('ROLLBACK_APPLY', ['/bin/sh', 'ROLLBACK.sh', str(ROOT/'ROLLBACK_COPY')], 5, 10,
        'independent modified copy; restore original compiler bytes')
execute('ROLLBACK', [sys.executable, 'validate.py', 'ROLLBACK'], 20, 30, 'same INPUT.json; restored OLD_1RELOC')
baseline = json.loads(Path('runs/BASELINE.json').read_text())
rollback = json.loads(Path('runs/ROLLBACK.json').read_text())
assert {k:v for k,v in baseline.items() if k!='phase'} == {k:v for k,v in rollback.items() if k!='phase'}
def untimed(value):
    if isinstance(value, list): return [untimed(v) for v in value]
    if isinstance(value, dict): return {k:untimed(v) for k,v in value.items() if k!='compile_wall_s'}
    return value
assert untimed(json.loads(Path('runs/BASELINE_DETAILS.json').read_text())) == untimed(json.loads(Path('runs/ROLLBACK_DETAILS.json').read_text()))
manifest = {r['path']:r['sha256'] for r in json.loads(Path('FROZEN_MANIFEST.json').read_text())}
assert hashlib.sha256(Path('MODIFIED_FILE.py').read_bytes()).hexdigest() == manifest['MODIFIED_FILE.py']
summary = {'status':'FINITE_AIR2_COMPONENT_VERIFIED_NOT_RL_OR_G3', 'rollback_matches_baseline':True,
           'main_modified_retained':True, 'source_repairs':0,
           'child_cpu_s':sum(r['child_cpu_s'] for r in receipts),
           'wall_s':sum(r['wall_s'] for r in receipts),
           'training':0, 'new_scientific_maps':0, 'Formal':0}
Path('runs/SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,sort_keys=True))
