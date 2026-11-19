"""Root serial one-ticket G3 execution, full ITT, immutable registered rows."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import fcntl,hashlib,json,os,socket,subprocess,sys,time
assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
ROOT=Path(__file__).resolve().parent.parent;SRC=ROOT/'MODIFIED_FILE'
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
 assert not Path('REGISTRATION.json').exists(),'REGISTERED_BATCH_NEVER_RESTART_BLINDLY'
 maps=sorted(allocation.allocation(),key=lambda r:(r['ordinal'],allocation.FAMILIES.index(tuple(r['family']))))
 controls=allocation.planned_control_rows()
 for i,r in enumerate(controls):r['row_id']='C%04d'%i
 authors=[]
 for mi,m in enumerate(maps):
  winds=allocation.WINDS[mi%3:]+allocation.WINDS[:mi%3]
  for wid,wind in winds:authors.append({'row_id':'A%03d'%len(authors),'map_id':m['map_id'],'short_id':m['short_id'],'wind_id':wid,'wind_m_per_min':list(wind),'author_seed_i63_decimal':m['author_seed_i63_decimal']})
 assert len(maps)==24 and len(authors)==72 and len(controls)==2880
 registration={'schema':'f3_g3_immutable_registration_v1','namespace':allocation.NAMESPACE,'maps':maps,'authors':authors,'controls':controls,'source_closure_sha256':sha(ROOT/'SOURCE_CLOSURE.json'),'exclusion_union_sha256':sha(ROOT/'exclusions/LATEST_EXPOSED_UNION.json'),'no_quality_replacements':True,'training_or_Formal_authorized':False}
 save('REGISTRATION.json',registration)
 counts={'registered_maps':24,'registered_authors':72,'registered_controls':2880,'maps_attempted':0,'maps_generated':0,'map_failures':0,'authors_started':0,'authors_qualified':0,'authors_failed':0,'controls_started':0,'controls_ontime_valid':0,'controls_failed':0,'controls_skipped_anchor_or_map':0,'training':0,'Formal':0}
 progress('REGISTERED_BEFORE_GENERATION')
 exp=ROOT/'exclusions';req=['PERMANENT_EXCLUSION_MANIFEST.json','SYNTHETIC_SMOKE_EXCLUSION.json','SYNTHETIC_EXCLUSION_MANIFEST.json','WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json']
 base=generator.ExclusionIndex.from_paths([exp/n for n in req]);base.require_research_ready()
 prior=json.loads((exp/'LATEST_EXPOSED_UNION.json').read_text())
 records=list(base.records)+list(prior['records']);fresh=[];population={}
 for m in maps:
  progress('GENERATING_POPULATION',current_map=m['short_id'])
  out=ROOT/'population'/m['short_id'];out.mkdir(parents=True,exist_ok=False)
  index=generator.ExclusionIndex(records+fresh,base.sources)
  result=generator.generate_allocated_instance(*m['family'],namespace=allocation.NAMESPACE,partition='opportunity',ordinal=m['ordinal'],exclusions=index)
  save(out/'GENERATION.json',result)
  (out/'RETAINED_COMPLETE_OR_PARTIAL.txt').write_text(result['retained_complete_or_partial_text'])
  counts['maps_attempted']+=1
  if result['status']=='generated':
   (out/'instance.txt').write_text(result['solver_input_text'])
   assert sha(out/'instance.txt')==result['raw_sha256']
   nodes=generator.parse_instance_text(result['solver_input_text'])
   assert generator.canonical_geometry_identity(nodes)==result['canonical_geometry_sha256']
   fresh.append({'raw_sha256':result['raw_sha256'],'canonical_geometry_sha256':result['canonical_geometry_sha256'],'map_id':m['map_id']})
   counts['maps_generated']+=1
  else:counts['map_failures']+=1
  population[m['map_id']]={**m,'status':result['status'],'failure_reason':result['failure_reason'],'raw_sha256':result['raw_sha256'],'canonical_geometry_sha256':result['canonical_geometry_sha256']}
  event({'event':'GENERATION_TERMINAL','map_id':m['map_id'],'status':result['status'],'raw_sha256':result['raw_sha256'],'canonical_geometry_sha256':result['canonical_geometry_sha256']})
 save('POPULATION_MANIFEST.json',{'namespace':allocation.NAMESPACE,'records':list(population.values()),'raw_unique_generated':len({r['raw_sha256'] for r in fresh}),'canonical_unique_generated':len({r['canonical_geometry_sha256'] for r in fresh})})
 loaded_modules('DRIVER_LOADED_MODULES.json')
 progress('POPULATION_GENERATED')
 author_manifest_sha=sha(AUTHOR/'builds/wind_adapted_fixed/BUILD_MANIFEST.json')
 canary_done=False
 for author in authors:
  cell=population[author['map_id']];subset=[r for r in controls if r['map_id']==author['map_id'] and r['wind_id']==author['wind_id']]
  if cell['status']!='generated':
   event({'row_id':author['row_id'],'event':'AUTHOR_TERMINAL','status':'SKIPPED_GENERATION_FAILED'})
   for r in subset:event({'row_id':r['row_id'],'event':'CONTROL_TERMINAL','status':'SKIPPED_GENERATION_FAILED'})
   counts['controls_skipped_anchor_or_map']+=40;continue
  path=ROOT/'population'/cell['short_id']/'instance.txt'
  out=ROOT/'authors'/cell['short_id']/author['wind_id']
  argv=[sys.executable,str(SRC/'full_author_cli.py'),'--instance',str(path),'--source-root',str(AUTHOR),'--build',str(AUTHOR/'builds/wind_adapted_fixed'),'--wind',*[str(x) for x in author['wind_m_per_min']],'--seed',author['author_seed_i63_decimal'],'--out',str(out),'--timeout','1800','--expected-input-sha256',cell['raw_sha256'],'--expected-source-manifest-sha256',author_manifest_sha]
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
  anchor=wind_scorer.CostAnchor.from_solution(ins,solution,wind=tuple(author['wind_m_per_min']))
  q=json.loads((out/'QUALIFICATION.json').read_text())
  assert q['source_record_qualified'] and q['wind_witness_qualified']
  if not canary_done:
   # First registered successful author is the real entry acceptance; no extra
   # map/attempt is bought or rerun, and failed population slots stay failed.
   save('FULL_AUTHOR_ENTRY_ACCEPTANCE.json',{'status':'PASS_FULL_SAME_WIND_MAIN_AND_TWO_INDEPENDENT_SCORERS','author_row_id':author['row_id'],'registered_attempt_counted':True,'repro_seconds':0,'outer_iterations':500,'alns_iterations':5000,'external_main_timeout_s':1800,'main_returned':run['main_returned'],'source_manifest_sha256':author_manifest_sha,'wind':author['wind_m_per_min'],'input_sha256':cell['raw_sha256'],'qualification_file':str(out/'QUALIFICATION.json'),'source_score_file':str(out/'SOURCE_SCORE.json'),'final_main_file':str(out/'FINAL_MAIN.json')});canary_done=True
  bundle=ROOT/'bundles'/cell['short_id']/(author['wind_id']+'.json')
  save(bundle,{'schema':'physical_route_delivery_input_v1','instance_file':str(path),'parameters':asdict(ins.params),'anchor':anchor.solution(),'wind':author['wind_m_per_min'],'run_role':'AUTHORIZED_F3_G3_NEW_POPULATION','author_row_id':author['row_id']})
  for r in subset:
   progress('CONTROL_RUNNING',current_control=r['row_id'],current_map=cell['short_id'],current_wind=author['wind_id'],method=r['method'],deadline_s=r['deadline_s'])
   method='strong' if r['method']=='native_strong_minmax_ALNS' else 'common_h';D=r['deadline_s']
   target=ROOT/'controls'/cell['short_id']/author['wind_id']/method/('seed_'+str(r['run_seed']))/('budget_'+str(D))
   argv=[sys.executable,str(SRC/'control_cli.py'),'--bundle',str(bundle),'--out',str(target),'--budget',str(D),'--method',method,'--seed',str(r['run_seed'])]
   guardout=ROOT/'guards/controls'/r['row_id']
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
