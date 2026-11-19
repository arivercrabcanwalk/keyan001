"""Finite boundary algebra tests only; no map, scorer, solver or neural model."""
from pathlib import Path
import hashlib
import importlib.util
import json
import socket
import sys

assert socket.gethostname() == '<COMPUTE_HOST>', '<REMOVED_ENDPOINT>_ONLY'
root = Path(__file__).resolve().parent
source, phase, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
spec = importlib.util.spec_from_file_location('boundary_subject', source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
advance = getattr(mod, 'advance_next_token', mod.force)
inp = json.loads((root/'INPUT.json').read_text())
rows = []
for case in inp['cases']:
    station = mod.freeze(case['station'])
    slot, target = case['action']
    result = advance(station, slot, target)
    preserves = [mod.routes(sl) for sl in result] == [mod.routes(sl) for sl in station]
    locked = mod.force(station, slot, target)
    same_lock = all(result[k][:2] == locked[k][:2] for k in (0, 1))
    rows.append({'id':case['id'], 'before':station, 'after':result,
                 'complete_routes_preserved':preserves, 'same_executed_lock':same_lock})
rejects = []
for case in inp['reject_cases']:
    try:
        advance(mod.freeze(case['station']), *case['action'])
    except ValueError:
        rejected = True
    else:
        rejected = False
    rejects.append({'id':case['id'], 'rejected':rejected})
passed = sum(r['complete_routes_preserved'] and r['same_executed_lock'] for r in rows)
if phase == 'MODIFIED':
    assert passed == len(rows) and all(r['rejected'] for r in rejects)
else:
    assert passed < len(rows) and not any(r['rejected'] for r in rejects)
result = {'phase':phase, 'status':'BOUNDARY_ADAPTER_PASS' if phase=='MODIFIED' else 'OLD_FORCE_NOT_A_BOUNDARY_ADAPTER',
          'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'preserved':passed,
          'cases_total':len(rows), 'invalid_next_rejected':sum(r['rejected'] for r in rejects),
          'rows':rows, 'rejects':rejects, 'AIR2_enumeration_executed':False,
          'training':0, 'scientific_maps':0}
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('phase','status','preserved','cases_total','invalid_next_rejected')},sort_keys=True))
