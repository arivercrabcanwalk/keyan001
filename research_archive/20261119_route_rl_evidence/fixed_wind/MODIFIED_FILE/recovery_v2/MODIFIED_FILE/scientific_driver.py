"""Root serial one-ticket G3 execution, full ITT, immutable registered rows."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import fcntl,hashlib,json,os,socket,subprocess,sys,time
assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
ROOT=Path(__file__).resolve().parent.parent;SRC=ROOT/'MODIFIED_FILE';PRIOR=ROOT.parent/'execution_v1'
os.chdir(ROOT);sys.path[:0]=[str(SRC/'frozen'),str(SRC)]
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from baselines import problem,wind_scorer
import allocation,generator_v2 as generator
from source_closure import verify,loaded_modules,AUTHOR,sha
import ticket_guard


def save(path,x):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def event(row):
 with Path('EVENTS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**row),sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())

def progress(state,**kw):
 save('PROGRESS.json',dict(state=state,**counts,**kw,updated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),pid=os.getpid()))

def guarded(rowid,command,out,*,cpu,wall,D=None):
 verify(ROOT)
 argv=[sys.executable,str(SRC/'ticket_guard.py'),'--ledger',str(ROOT/'ROW_RESOURCE_LEDGER.jsonl'),'--out',str(out),'--row-id',rowid,'--reserved-cpu-seconds',str(cpu),'--wall-cap-seconds',str(wall),'--ticket-cap-seconds','171900','--termination-reserve-seconds','120']
 if D is not None:argv+=['--method-deadline-seconds',str(D)]
 argv+=['--',*command]
 event({'row_id':rowid,'event':'INTENT','command':argv,'source_closure_sha256':sha(ROOT/'SOURCE_CLOSURE.json')})
 p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 save(out.parent/(out.name+'_SUPERVISOR.json'),{'argv':argv,'exit_status':p.returncode,'stdout_literal':p.stdout,'stderr_literal':p.stderr})
 if (out/'NOT_STARTED.json').exists():return {'budget_not_started':True},p.returncode
 terminal=json.loads((out/'TERMINAL.json').read_text()) if (out/'TERMINAL.json').exists() else {'budget_and_cleanup_pass':False,'exit_status':p.returncode,'stop_reason':'NO_TERMINAL_RECEIPT'}
 assert terminal.get('budget_and_cleanup_pass',False),'RESOURCE_OR_CLEANUP_VIOLATION'
 return terminal,p.returncode


def main():
 global counts
 lock=Path('SCIENTIFIC_DRIVER.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 verify(ROOT)
 assert not Path('PROGRESS.json').exists(), 'RECOVERY_INVOCATION_ALREADY_ATTEMPTED'
 # Preserve the original registration, population and A000. No generator call.
 provenance=json.loads((ROOT/'PRIOR_EVIDENCE_MANIFEST.json').read_text())
 for row in provenance['files']:assert sha(row['path'])==row['sha256'],row['path']
 oldterm=json.loads((PRIOR/'scientific_batch_guard/TERMINAL.json').read_text())
 assert oldterm['state']=='TERMINAL' and oldterm['budget_and_cleanup_pass'] and not oldterm['remaining_descendants']
 previous=json.loads((PRIOR/'PROGRESS.json').read_text())
 assert previous['maps_generated']==24 and previous['authors_started']==1 and previous['authors_qualified']==1 and previous['controls_started']==0
 registration=json.loads((PRIOR/'REGISTRATION.json').read_text())
 maps=registration['maps'];authors=registration['authors'];controls=registration['controls']
 population={r['map_id']:r for r in json.loads((PRIOR/'POPULATION_MANIFEST.json').read_text())['records']}
 assert len(maps)==24 and len(authors)==72 and len(controls)==2880
 assert len({a['row_id'] for a in authors})==72 and len({c['row_id'] for c in controls})==2880
 counts={'registered_maps':24,'registered_authors':72,'registered_controls':2880,'maps_attempted':24,'maps_generated':24,'map_failures':0,'authors_started':0,'authors_qualified':0,'authors_failed':0,'authors_reused_without_rerun':0,'controls_started':0,'controls_ontime_valid':0,'controls_failed':0,'controls_skipped_anchor_or_map':0,'training':0,'Formal':0}
 save('RECOVERY_PLAN.json',{'status':'REUSE_ORIGINAL_24_MAPS_AND_A000_NO_RERUN','original_registration_sha256':sha(PRIOR/'REGISTRATION.json'),'original_population_sha256':sha(PRIOR/'POPULATION_MANIFEST.json'),'previous_failure_retained':str(PRIOR/'scientific_batch_guard/STDERR.txt'),'only_numeric_representation_change':'tuple(float(v) for v in registered wind); routes, parameters, scorer and registered rows unchanged','no_new_maps':True,'no_extra_author_attempts':True})
 loaded_modules('DRIVER_LOADED_MODULES.json')
 progress('RECOVERY_REGISTERED_OLD_POPULATION_REUSED')
 author_manifest_sha=sha(AUTHOR/'builds/wind_adapted_fixed/BUILD_MANIFEST.json')
 canary_done=False
 for author in authors:
  cell=population[author['map_id']];subset=[r for r in controls if r['map_id']==author['map_id'] and r['wind_id']==author['wind_id']]
  if cell['status']!='generated':
   event({'row_id':author['row_id'],'event':'AUTHOR_TERMINAL','status':'SKIPPED_GENERATION_FAILED'})
   for r in subset:event({'row_id':r['row_id'],'event':'CONTROL_TERMINAL','status':'SKIPPED_GENERATION_FAILED'})
   counts['controls_skipped_anchor_or_map']+=40;continue
  path=PRIOR/'population'/cell['short_id']/'instance.txt'
  # Normalization mirrors argparse(type=float) in the full author CLI.
  # Never rewrite the solution's physics SHA or change the registration.
  wind=tuple(float(v) for v in author['wind_m_per_min'])
  if author['row_id']=='A000':
   out=PRIOR/'authors'/cell['short_id']/author['wind_id']
   term=json.loads((PRIOR/'guards/authors/A000/TERMINAL.json').read_text())
   assert term['exit_status']==0 and term['budget_and_cleanup_pass'] and not term['remaining_descendants']
   code=0;counts['authors_reused_without_rerun']+=1
   event({'row_id':'A000','event':'AUTHOR_REUSED_NOT_RERUN','source':str(out),'source_terminal':str(PRIOR/'guards/authors/A000/TERMINAL.json')})
  else:
   out=ROOT/'authors'/cell['short_id']/author['wind_id']
   assert not (PRIOR/'guards/authors'/author['row_id']).exists(), 'PRIOR_ATTEMPT_REQUIRES_EXPLICIT_RECONCILIATION'
   assert not out.exists(), 'AUTHOR_ALREADY_ATTEMPTED'
   argv=[sys.executable,str(SRC/'full_author_cli.py'),'--instance',str(path),'--source-root',str(AUTHOR),'--build',str(AUTHOR/'builds/wind_adapted_fixed'),'--wind',*[str(x) for x in wind],'--seed',author['author_seed_i63_decimal'],'--out',str(out),'--timeout','1800','--expected-input-sha256',cell['raw_sha256'],'--expected-source-manifest-sha256',author_manifest_sha]
   progress('FULL_AUTHOR_RUNNING',current_author=author['row_id'],current_map=cell['short_id'],current_wind=author['wind_id'])
   term,code=guarded(author['row_id'],argv,ROOT/'guards/authors'/author['row_id'],cpu=2000,wall=1830)
  if term.get('budget_not_started'):progress('BUDGET_NOT_STARTED');return
  counts['authors_started']+=1
  run=json.loads((out/'RUN.json').read_text()) if (out/'RUN.json').exists() else {}
  qualified=code==0 and run.get('wind_witness_qualified') is True
  event({'row_id':author['row_id'],'event':'AUTHOR_TERMINAL','status':run.get('status','NO_RUN_RECORD'),'qualified':qualified,'guard_exit':code,'run_file':str(out/'RUN.json')})
  if not qualified:
   counts['authors_failed']+=1
   for r in subset:event({'row_id':r['row_id'],'event':'CONTROL_TERMINAL','status':'SKIPPED_ANCHOR_INELIGIBLE'})
   counts['controls_skipped_anchor_or_map']+=40
   # An actual source/CLI execution failure is not a bad problem instance.
   if not run or run.get('audit_exception'):raise RuntimeError('FULL_AUTHOR_INTERFACE_FAILURE; preserve attempt, no automatic rerun')
   continue
  counts['authors_qualified']+=1
  ins=problem.read_instance(path)
  solution=json.loads((out/'QUALIFIED_WIND_SOLUTION.json').read_text())
  anchor=wind_scorer.CostAnchor.from_solution(ins,solution,wind=wind)
  q=json.loads((out/'QUALIFICATION.json').read_text())
  assert q['source_record_qualified'] and q['wind_witness_qualified']
  assert json.loads(json.dumps(wind_scorer.score_solution(ins,solution,wind=wind)))==q['wind_score'], 'AUTHOR_SCORE_DIVERGENCE'
  if not canary_done:
   # First registered successful author is the real entry acceptance; no extra
   # map/attempt is bought or rerun, and failed population slots stay failed.
   save('FULL_AUTHOR_ENTRY_ACCEPTANCE.json',{'status':'PASS_FULL_SAME_WIND_MAIN_AND_TWO_INDEPENDENT_SCORERS','author_row_id':author['row_id'],'registered_attempt_counted':True,'repro_seconds':0,'outer_iterations':500,'alns_iterations':5000,'external_main_timeout_s':1800,'main_returned':run['main_returned'],'source_manifest_sha256':author_manifest_sha,'wind':list(wind),'input_sha256':cell['raw_sha256'],'qualification_file':str(out/'QUALIFICATION.json'),'source_score_file':str(out/'SOURCE_SCORE.json'),'final_main_file':str(out/'FINAL_MAIN.json'),'original_registration_sha256':sha(PRIOR/'REGISTRATION.json'),'source_closure_sha256':sha(ROOT/'SOURCE_CLOSURE.json'),'reused_not_rerun':author['row_id']=='A000','solution_bytes_unchanged_sha256':sha(out/'QUALIFIED_WIND_SOLUTION.json')});canary_done=True
  bundle=ROOT/'bundles'/cell['short_id']/(author['wind_id']+'.json')
  save(bundle,{'schema':'physical_route_delivery_input_v1','instance_file':str(path),'parameters':asdict(ins.params),'anchor':anchor.solution(),'wind':list(wind),'run_role':'AUTHORIZED_F3_G3_NEW_POPULATION','author_row_id':author['row_id']})
  for r in subset:
   progress('CONTROL_RUNNING',current_control=r['row_id'],current_map=cell['short_id'],current_wind=author['wind_id'],method=r['method'],deadline_s=r['deadline_s'])
   method='strong' if r['method']=='native_strong_minmax_ALNS' else 'common_h';D=r['deadline_s']
   target=ROOT/'controls'/cell['short_id']/author['wind_id']/method/('seed_'+str(r['run_seed']))/('budget_'+str(D))
   argv=[sys.executable,str(SRC/'control_cli.py'),'--bundle',str(bundle),'--out',str(target),'--budget',str(D),'--method',method,'--seed',str(r['run_seed'])]
   guardout=ROOT/'guards/controls'/r['row_id']
   assert not (PRIOR/'guards/controls'/r['row_id']).exists() and not target.exists(), 'CONTROL_ALREADY_ATTEMPTED'
   term,code=guarded(r['row_id'],argv,guardout,cpu=160,wall=D+3,D=D)
   if term.get('budget_not_started'):progress('BUDGET_NOT_STARTED');return
   counts['controls_started']+=1
   dec=json.loads((target/'DECISION.json').read_text()) if (target/'DECISION.json').exists() else {}
   valid=code==0 and term.get('complete_process_ontime',False) and dec.get('accepted',False)
   counts['controls_ontime_valid' if valid else 'controls_failed']+=1
   final={'row_id':r['row_id'],'registration':r,'status':'ONTIME_VALID' if valid else 'NO_ONTIME_VALID_OUTPUT','outer_exit_status':term.get('exit_status'),'guard_exit_status':code,'outer_process_observed_elapsed_s':term.get('process_exit_observed_elapsed_s'),'controller_decision_file':str(target/'DECISION.json'),'raw_output_exists':(target/'RAW_RESULT.json').exists(),'itt_is_virtual_no_improvement':not valid,'itt_M_return':dec['itt_M_return'] if valid else anchor.makespan,'itt_cost':dec['itt_cost'] if valid else anchor.cost,'anchor_M_return':anchor.makespan,'anchor_cost':anchor.cost}
   save(guardout/'FINAL_DELIVERY.json',final);event({'row_id':r['row_id'],'event':'CONTROL_TERMINAL','status':final['status'],'final_delivery_file':str(guardout/'FINAL_DELIVERY.json')})
   if not dec and term.get('exit_status') not in (-9,-24):raise RuntimeError('CONTROL_LAUNCH_INTERFACE_FAILURE; preserve row')
  progress('CELL_COMPLETED',current_map=cell['short_id'],current_wind=author['wind_id'])
 verify(ROOT)
 save('FINAL_SUMMARY.json',dict(status='REGISTERED_BATCH_TERMINAL',**counts))
 progress('REGISTERED_BATCH_TERMINAL')

if __name__=='__main__':
 try:main()
 except BaseException as exc:
  event({'event':'DRIVER_ABORT','type':type(exc).__name__,'message':str(exc)})
  if 'counts' in globals():progress('STOPPED_PRESERVED_FAILURE',failure=type(exc).__name__+':'+str(exc))
  raise
