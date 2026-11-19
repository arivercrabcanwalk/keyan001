"""Only new identity repair and independent-copy rollback; no solve reruns."""
from pathlib import Path
import ast, hashlib, json, os, shutil, socket, subprocess, sys
assert socket.gethostname()=='EXECUTION_HOST', 'HN01_ONLY'
ROOT=Path(__file__).resolve().parent.parent
PRIOR=ROOT.parent/'execution_v1'
os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'MODIFIED_FILE'))
from source_closure import freeze,verify,sha
commands=[]
def run(phase,argv,probe_source=None):
    env=dict(os.environ)
    if probe_source is not None:env['RECOVERY_IDENTITY_SOURCE']=str(probe_source)
    p=subprocess.run(argv,text=True,capture_output=True,timeout=30,env=env)
    rec={'phase':phase,'command':argv,'input':'existing registered A000 final witness only; zero draws or solves',
         'stdout_literal':p.stdout,'stderr_literal':p.stderr,'exit_status':p.returncode,
         'probe_source':str(probe_source) if probe_source else None}
    commands.append(rec)
    (ROOT/'VERIFICATION_COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n')
    assert p.returncode==0,rec
    return p
for row in json.loads((ROOT/'LOCAL_SOURCE_MANIFEST.json').read_text()):
    assert sha(ROOT/'MODIFIED_FILE'/row['path'])==row['sha256'],row
for p in (ROOT/'MODIFIED_FILE').rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
run('BASELINE',[sys.executable,'MODIFIED_FILE/recovery_identity_check.py','--mode','BASELINE'])
run('MODIFIED',[sys.executable,'MODIFIED_FILE/recovery_identity_check.py','--mode','MODIFIED'])
proof=ROOT/'ROLLBACK_COPY';proof.mkdir();(proof/'.ROLLBACK_PROOF_ONLY').touch()
shutil.copytree(ROOT/'MODIFIED_FILE',proof/'MODIFIED_FILE')
run('ROLLBACK_SOURCE',['/bin/sh','ROLLBACK.sh',str(proof)])
old={str(p.relative_to(ROOT/'ORIGINALS/production')):sha(p) for p in (ROOT/'ORIGINALS/production').rglob('*') if p.is_file()}
back={str(p.relative_to(proof/'MODIFIED_FILE')):sha(p) for p in (proof/'MODIFIED_FILE').rglob('*') if p.is_file()}
assert old==back
assert "wind=tuple(author['wind_m_per_min'])" in (proof/'MODIFIED_FILE/scientific_driver.py').read_text()
assert "wind=tuple(float(v) for v in author['wind_m_per_min'])" in (ROOT/'MODIFIED_FILE/scientific_driver.py').read_text()
run('ROLLBACK_BEHAVIOR',[sys.executable,'MODIFIED_FILE/recovery_identity_check.py','--mode','BASELINE'],probe_source=proof/'MODIFIED_FILE')
files=[]
for name in ['SOURCE_CLOSURE.json','REGISTRATION.json','POPULATION_MANIFEST.json','POPULATION_READBACK_AUDIT.json','PROGRESS.json','ROW_RESOURCE_LEDGER.jsonl','PREFLIGHT_RESULT.json','scientific_batch_guard/TERMINAL.json','scientific_batch_guard/STDERR.txt']:
    files.append(PRIOR/name)
files += [p for p in (PRIOR/'population').rglob('*') if p.is_file()]
files += [p for p in (PRIOR/'authors/3x10_o1/W00').rglob('*') if p.is_file()]
files += [p for p in (PRIOR/'guards/authors/A000').rglob('*') if p.is_file()]
files += [p for p in (PRIOR/'MODIFIED_FILE').rglob('*') if p.is_file()]
evidence={'schema':'immutable_recovery_input_v1','previous_failure_preserved':True,
          'new_draws':0,'new_solves':0,'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files))]}
(ROOT/'PRIOR_EVIDENCE_MANIFEST.json').write_text(json.dumps(evidence,indent=2)+'\n')
closure=freeze(ROOT);verify(ROOT)
result={'status':'RECOVERY_IDENTITY_SOURCE_AND_ROLLBACK_PASS','source_closure_files':len(closure['source_files']),
        'prior_evidence_files':len(evidence['files']),'old_population_and_A000_reused':True,
        'modified_solution_bytes':False,'new_draws':0,'new_solves':0,
        'original_driver_sha256':sha(proof/'MODIFIED_FILE/scientific_driver.py'),
        'modified_driver_sha256':sha(ROOT/'MODIFIED_FILE/scientific_driver.py'),
        'rollback_source_and_original_identity_failure_restored':True}
(ROOT/'PREFLIGHT_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,sort_keys=True),flush=True)
