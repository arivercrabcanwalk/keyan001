"""Source/launcher preflight, no old scientific or successful fixture reruns."""
from pathlib import Path
import ast,hashlib,importlib.util,json,os,re,shutil,socket,subprocess,sys
assert socket.gethostname()=='EXECUTION_HOST'
ROOT=Path(__file__).resolve().parent.parent;os.chdir(ROOT)
sys.path.insert(0,str(ROOT/'MODIFIED_FILE'))
from source_closure import freeze,verify,AUTHOR
manifest=json.loads((ROOT/'LOCAL_SOURCE_MANIFEST.json').read_text())
for r in manifest:assert hashlib.sha256((ROOT/'MODIFIED_FILE'/r['path']).read_bytes()).hexdigest()==r['sha256'],r['path']
for file in (ROOT/'MODIFIED_FILE').rglob('*.py'):ast.parse(file.read_text(),filename=str(file))
receipts=[]
def run(phase,argv,expected=0):
 p=subprocess.run(argv,text=True,capture_output=True,timeout=30)
 receipts.append({'phase':phase,'command':argv,'input':'frozen source closure and launch timing only; scientific canary remains a registered author row','stdout_literal':p.stdout,'stderr_literal':p.stderr,'exit_status':p.returncode})
 (ROOT/'PREFLIGHT_COMMANDS.json').write_text(json.dumps(receipts,indent=2)+'\n')
 assert p.returncode==expected,receipts[-1]
run('BASELINE',[sys.executable,'-c',"from pathlib import Path; assert not Path('ORIGINALS/production/scientific_driver.py').exists(); print('SCIENTIFIC_DRIVER_ABSENT')"])
assert re.search(r'MAX_ITERATIONS\s*=\s*500\s*;', (AUTHOR/'frozen/wind_adapted_fixed/Main.java').read_text())
assert re.search(r'maxIterations\s*=\s*5000\s*;', (AUTHOR/'frozen/wind_adapted_fixed/ALNSSolver.java').read_text())
sp=importlib.util.spec_from_file_location('full_author_verified',AUTHOR/'validation/fullsolve_driver.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old);man=old.verify_build('wind_adapted_fixed')
assert man['identity']=='J1b_constant_wind_final_record_v1'
# Entire controller entry start is tested by a late child, including its startup.
argv=[sys.executable,'MODIFIED_FILE/ticket_guard.py','--ledger','PREFLIGHT_ROW_LEDGER.jsonl','--out','preflight_late','--row-id','external_clock_late_negative','--reserved-cpu-seconds','150','--wall-cap-seconds','9','--method-deadline-seconds','6','--',sys.executable,'-c',"import os,time,pathlib; assert float(os.environ['CONTROL_PROCESS_STARTED'])<=time.perf_counter(); pathlib.Path('EARLY_RAW_NEGATIVE.txt').write_text('SAVED_BEFORE_FULL_EXIT'); time.sleep(7)"]
run('MODIFIED_FULL_EXIT_NEGATIVE',argv,4)
t=json.loads((ROOT/'preflight_late/TERMINAL.json').read_text());assert t['stop_reason']=='CONTROL_PROCESS_DEADLINE' and not t['complete_process_ontime'] and t['exit_status']==-9 and not t['remaining_descendants']
proof=ROOT/'ROLLBACK_COPY';proof.mkdir();(proof/'.ROLLBACK_PROOF_ONLY').touch();shutil.copytree(ROOT/'MODIFIED_FILE',proof/'MODIFIED_FILE')
run('ROLLBACK',['/bin/sh','ROLLBACK.sh',str(proof)])
run('ROLLBACK_BEHAVIOR',[sys.executable,'-c',"from pathlib import Path; import hashlib; a=Path('ORIGINALS/production');b=Path('ROLLBACK_COPY/MODIFIED_FILE'); assert not (b/'scientific_driver.py').exists(); assert {str(p.relative_to(a)):hashlib.sha256(p.read_bytes()).hexdigest() for p in a.rglob('*') if p.is_file()}=={str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest() for p in b.rglob('*') if p.is_file()}; print('ORIGINAL_PRODUCTION_HASHES_AND_ABSENT_DRIVER_RESTORED')"])
closure=freeze(ROOT);verify(ROOT)
result={'status':'SOURCE_CLOSURE_OUTER_TIMING_AND_ROLLBACK_PREFLIGHT_PASS','source_files':len(closure['source_files']),'author_build_verified':True,'author_full_iterations_verified':True,'actual_full_author_entry_acceptance':'first registered qualified author row; no extra attempt','negative_late_child':'REJECTED_WITH_EARLY_RAW_RETAINED','independent_rollback':True,'main_modified_retained':(ROOT/'MODIFIED_FILE/scientific_driver.py').exists()}
(ROOT/'PREFLIGHT_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
