"""Rollback evidence only after the frozen AIR2 batch stopped at baseline."""
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
root = Path(__file__).resolve().parent
os.chdir(root)
prior = json.loads(Path('runs/COMMAND_RECEIPTS.json').read_text())
assert len(prior) == 1 and prior[0]['phase'] == 'BASELINE' and prior[0]['exit_status'] == 1
assert not Path('runs/ROLLBACK_RECOVERY.json').exists()
Path('ROLLBACK_COPY').mkdir(exist_ok=False)
before_hash = hashlib.sha256(Path('MODIFIED_FILE.py').read_bytes()).hexdigest()
shutil.copy2('MODIFIED_FILE.py', 'ROLLBACK_COPY/MODIFIED_FILE.py')
commands = [['/bin/sh', 'ROLLBACK.sh', str(root/'ROLLBACK_COPY')],
            [sys.executable, 'validate.py', 'ROLLBACK']]
records = []
for command in commands:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    r = subprocess.run(command, text=True, capture_output=True, timeout=20,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    records.append({'command':command, 'input':'independent copy; same INPUT.json; rollback recovery only',
                    'stdout_literal':r.stdout,'stderr_literal':r.stderr,'exit_status':r.returncode,
                    'wall_s':time.perf_counter()-start,
                    'child_cpu_s':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime})
assert records[0]['exit_status'] == 0
assert records[1]['exit_status'] == 1 and records[1]['stderr_literal'] == prior[0]['stderr_literal']
assert hashlib.sha256(Path('ROLLBACK_COPY/MODIFIED_FILE.py').read_bytes()).hexdigest() == hashlib.sha256(Path('ORIGINALS/compiler.py').read_bytes()).hexdigest()
assert hashlib.sha256(Path('MODIFIED_FILE.py').read_bytes()).hexdigest() == before_hash
result = {'status':'CLOSED_FAILED_BASELINE_ADAPTER_ASSUMPTION_NOT_REOPENED',
          'modified_phase_executed':False,'audit_phase_executed':False,'repairs':0,
          'rollback_reproduces_original_failure':True,'main_modified_copy_retained':True,
          'records':records}
Path('runs/ROLLBACK_RECOVERY.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
