from pathlib import Path
from collections import Counter
import hashlib,json,os,shutil,time
ROOT=Path('/root/rivermind-data/liu_f3_g3_authorized_20261114_v1');P=ROOT/'execution_v1';R=ROOT/'recovery_v2'
now=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());D=ROOT/'snapshots'/now;D.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(p):
 p=Path(p)
 if not p.is_file():return
 dest=D/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
def tree(p):
 for f in Path(p).rglob('*'):
  if f.is_file():copy(f)
events_bytes=(R/'EVENTS.jsonl').read_bytes();assert events_bytes.endswith(b'\n')
events=[json.loads(x) for x in events_bytes.splitlines()]
progress=json.loads((R/'PROGRESS.json').read_text())
terminal_controls={x['row_id']:x for x in events if x['event']=='CONTROL_TERMINAL'}
terminal_authors={x['row_id']:x for x in events if x['event']=='AUTHOR_TERMINAL'}
intents={x['row_id']:x for x in events if x['event']=='INTENT'}
for n in ['REGISTRATION.json','POPULATION_MANIFEST.json','POPULATION_READBACK_AUDIT.json','PREFLIGHT_RESULT.json','PREFLIGHT_COMMANDS.json','SOURCE_CLOSURE.json','PROGRESS.json','SCIENTIFIC_LAUNCH_COMMAND.txt','SCIENTIFIC_BATCH_PID','ROW_RESOURCE_LEDGER.jsonl','POPULATION_AUDIT_STDOUT.txt','POPULATION_AUDIT_STDERR.txt','audit_execution_receipts.py']:
 copy(P/n)
for n in ['population','exclusions','scientific_batch_guard','preflight_guard','preflight_late','guards/authors/A000','authors/3x10_o1/W00']:tree(P/n)
for n in ['SOURCE_CLOSURE.json','PRIOR_EVIDENCE_MANIFEST.json','FULL_AUTHOR_ENTRY_ACCEPTANCE.json','RECOVERY_PLAN.json','PREFLIGHT_RESULT.json','VERIFICATION_COMMANDS.json','SCIENTIFIC_LAUNCH_COMMAND.txt','SCIENTIFIC_BATCH_PID','DRIVER_LOADED_MODULES.json','PROGRESS.json','ROW_RESOURCE_LEDGER.jsonl','AUTHORIZATION.json','EXPERIMENT_FREEZE.json','LOCAL_SOURCE_MANIFEST.json','DIFF_FILE.patch','ROLLBACK.sh']:
 copy(R/n)
for n in ['recovery_preflight_guard','identity_diagnosis_guard']:tree(R/n)
copy(R/'scientific_batch_guard/INTENT.json')
if (R/'scientific_batch_guard/TERMINAL.json').exists():tree(R/'scientific_batch_guard')
else:
 for n in ['STDERR.txt','STDOUT.txt']:copy(R/'scientific_batch_guard'/n)
for a in terminal_authors.values():
 tree(Path(a['run_file']).parent)
 row=a['row_id']
 if (R/'guards/authors'/row/'TERMINAL.json').exists():tree(R/'guards/authors'/row)
finals=[]
for e in terminal_controls.values():
 f=Path(e['final_delivery_file']);record=json.loads(f.read_text());finals.append(record)
 tree(f.parent);tree(Path(record['controller_decision_file']).parent)
copy(ROOT/'RESOURCE_LEDGER.jsonl')
ledger=[json.loads(x) for x in (D/'RESOURCE_LEDGER.jsonl').read_text().splitlines()]
latest={};fixed=0
for x in ledger:
 if x.get('schema')=='ticket_guard_v1':latest[x['row_id']]=x
 else:fixed+=x.get('total_debit_seconds',0)
active=[x for x in latest.values() if x['state']=='RUNNING'];assert len(active)<=1
snapshot_debit=fixed+sum(x.get('total_debit_seconds',x['reserved_cpu_seconds']) for x in latest.values())
observed=fixed+sum(x['total_debit_seconds'] for x in latest.values() if x['state']=='TERMINAL')
for x in active:
 usage=int(dict(v.split() for v in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())['usage_usec'])/1e6
 observed+=usage-x['container_cpu_start']
summary={'schema':'as_of_completed_receipt_snapshot_v1','as_of_utc':now,'snapshot_root':str(D),
 'driver_progress_observed':progress,'registered_maps':24,'generated_unique_maps':24,
 'registered_authors':72,'author_intents_unique_including_A000':1+sum(k.startswith('A') for k in intents),
 'author_terminal_count':len(terminal_authors),'authors_qualified':sum(x.get('qualified',False) for x in terminal_authors.values()),
 'registered_controls':2880,'controls_intents':sum(k.startswith('C') for k in intents),
 'controls_terminal_count':len(finals),'controls_statuses':dict(Counter(x['status'] for x in finals)),
 'by_method_deadline':dict(Counter(x['registration']['method']+':'+str(x['registration']['deadline_s'])+':'+x['status'] for x in finals)),
 'completed_author_row_ids':sorted(terminal_authors),'no_new_draws_or_solves_in_snapshot':True,
 'global_reserved_or_terminal_debit_seconds':snapshot_debit,
 'observed_global_terminal_plus_running_container_cpu_seconds':observed,
 'active_global_guard_rows':[x['row_id'] for x in active],
 'live_guard_pid':int((R/'SCIENTIFIC_BATCH_PID').read_text()),'training':0,'Formal':0,
 'first_four_completed_controls':[x for x in sorted(finals,key=lambda r:r['row_id'])[:4]],
 'source_closure_sha256':sha(R/'SOURCE_CLOSURE.json'),
 'original_A000_solution_sha256':sha(P/'authors/3x10_o1/W00/QUALIFIED_WIND_SOLUTION.json')}
proc=Path('/proc')/str(summary['live_guard_pid'])/'stat'
summary['guard_proc_state']=proc.read_text().rsplit(')',1)[1].split()[0] if proc.exists() else 'MISSING'
(D/'recovery_v2/EVENTS.jsonl').write_bytes(events_bytes)
(D/'SNAPSHOT_SUMMARY.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
files=[{'path':str(p.relative_to(D)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(D.rglob('*')) if p.is_file()]
(D/'SNAPSHOT_FILE_MANIFEST.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['first_four_completed_controls','driver_progress_observed']},sort_keys=True))
print('SNAPSHOT_PATH='+str(D))
