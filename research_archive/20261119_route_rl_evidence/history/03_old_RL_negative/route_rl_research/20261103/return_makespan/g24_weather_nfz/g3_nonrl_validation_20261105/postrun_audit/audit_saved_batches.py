#!/usr/bin/env python3
"""Root saved-output audit: replay only, no optimization, generation or training."""
import argparse, collections, hashlib, importlib.util, json, math, sys, time
from pathlib import Path
BATCHES=[('<EXECUTION_PATH>','g3_nonrl_calibration_20261105','4812c6bcc1a56c3191b4b54b80f8a61b1f07542b517af2909e8bb2b175c9b5fa'),('<EXECUTION_PATH>','g3_nonrl_validation_20261105','58fb17732e919e471037dc9fcfea4a4faa9c35be581d44309744ff6a7bdb4201')]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b):
 for k in ('M_return','MTC','weather_cost'):assert math.isclose(a[k],b[k],rel_tol=0,abs_tol=1e-7),(k,a[k],b[k])
 assert a['admissible']==b['admissible']
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',required=True);args=ap.parse_args();start=time.perf_counter();reports=[];raws=[];geometries=[]
 for location,package,expected in BATCHES:
  base=Path(location);out=base/'output';regpath=base/'REGISTRATION.json';assert sha(regpath)==expected;reg=read(regpath)
  f=Path(reg['project_root'])/'route_rl_research/20261103/return_makespan/g24_weather_nfz'/package/'phase_driver.py'
  sp=importlib.util.spec_from_file_location('driver_'+package,f);d=importlib.util.module_from_spec(sp);sp.loader.exec_module(d);d.validate_registration(regpath);r,g=d.setup(reg['project_root'])
  r.author_runner.verify_build(r.REPRO,'J1b',Path(reg['java_home']),Path(reg['build_dir']))
  rows=read(out/'COMPARISONS.json');anchors=read(out/'ANCHORS.json')['slots'];result=read(out/'RESULTS.json')
  assert len(anchors)==4 and len(rows)==40 and result['terminal_error'] is None and result['registration_sha256']==expected
  assert {(x['map'],x['method'],x['budget_s']) for x in rows}=={(s,m,b) for s in reg['slots'] for m in reg['methods'] for b in reg['budgets_s']}
  cases={};details=[];replays=0
  for a in anchors:
   directory=out/a['id'];raw=d.verify_generated_identity(directory,out,a['id'],r,reg);raws.append(raw);geometries.append(a['geometry_sha256']);run=read(directory/'author/RUN.json');sol=read(directory/'author/solution.json')
   assert run['status']=='ok' and run['anchor_eligible'] is True and run['input_sha256']==raw and run['process']['exit_code']==0 and not run['process']['timed_out']
   for relative,digest in run['artifacts'].items():assert sha(directory/'author'/relative)==digest
   inst=r.read_instance(directory/'instance.txt');anchor=r.CostAnchor.from_solution(inst,sol);weather,_=r.load_weather_scenario(directory/'scenario.json',expected_instance_sha256=raw)
   score=r.author_runner.audit_raw(inst,read(directory/'author/reference.json'),r.REPRO,g.parent/'scorer.py',run['witness_audit']['source_reported_latest_time']);assert score['witness_passed']
   replay=r.replay_weather_solution(inst,anchor,weather,sol,weather_cost_cap=None);replays+=1
   if a['status']=='eligible':
    d.verify_case(directory,a['artifact_hashes']);cap=read(directory/'weather_anchor.json')['weather_cost_cap'];replay=r.replay_weather_solution(inst,anchor,weather,sol,weather_cost_cap=cap);replays+=1;assert replay['admissible'];eq(replay,read(directory/'weather_anchor.json')['author_weather_replay']);cases[a['id']]=(inst,anchor,weather,cap,replay)
   else:assert replay['admissible'] is False and any(x.startswith('battery:') for x in replay['issues'])
   details.append({'map':a['id'],'raw_sha256':raw,'geometry_sha256':a['geometry_sha256'],'original_author_valid':True,'weather_admissible':replay['admissible'],'weather_issues':replay['issues'],'author_M_return':replay.get('M_return')})
  discarded=[];complete=0;improved=0
  for row in rows:
   c=row.get('raw_child') or {};complete+=int(c.get('candidate_complete') is True)
   if row['delivery_status']=='delivered':
    assert row['exit_code']==0 and not row['hard_killed'] and row['parent_elapsed_s']<=row['budget_s'];inst,anchor,weather,cap,author=cases[row['map']];selected=row['selected'];check=r.replay_weather_solution(inst,anchor,weather,selected['solution'],weather_cost_cap=cap);replays+=1;assert check['admissible'];eq(check,selected['replay']);eq(author,c['fallback']);assert check['M_return']<=author['M_return']+1e-7;improved+=int(check['M_return']<author['M_return']-1e-9)
   else:assert row['selected'] is None
   s=c.get('raw_search') or {}
   if s.get('solution') and s.get('replay') and c.get('candidate_complete') is False:
    inst,anchor,weather,cap,author=cases[row['map']];check=r.replay_weather_solution(inst,anchor,weather,s['solution'],weather_cost_cap=cap);replays+=1;eq(check,s['replay'])
    if check['admissible'] and check['M_return']<author['M_return']-1e-9:discarded.append({'map':row['map'],'method':row['method'],'budget_s':row['budget_s'],'author_M_return':author['M_return'],'raw_best_M_return':check['M_return'],'result':'saved feasible incumbent discarded after inner timeout; no quality credit'})
  methods=[]
  for m in reg['methods']:
   for b in reg['budgets_s']:
    rs=[x for x in rows if x['method']==m and x['budget_s']==b];values=[]
    for row in rs:
     if row['map'] not in cases:continue
     author=cases[row['map']][4]['M_return'];value=row['selected']['replay']['M_return'] if row.get('selected') else author;values.append({'map':row['map'],'M_return':value,'improvement_pct':100*(author-value)/author})
    methods.append({'method':m,'budget_s':b,'intents':4,'attempted':sum('exit_code' in x for x in rs),'delivered':sum(x['delivery_status']=='delivered' for x in rs),'map_values':values,'all_four_mean_pct':sum(x['improvement_pct'] for x in values)/4 if len(values)==4 else None})
  reports.append({'server_root':location,'registration_sha256':expected,'phase_elapsed_s':result['elapsed_s'],'author_attempts':4,'original_authors_pass':4,'eligible_weather_anchors':len(cases),'intent_rows':40,'attempted_rows':sum('exit_code' in x for x in rows),'raw_candidate_complete_rows':complete,'delivered_rows':sum(x['delivery_status']=='delivered' for x in rows),'delivered_improvement_rows':improved,'status_counts':dict(collections.Counter(x['delivery_status'] for x in rows)),'replay_calls':replays,'discarded_saved_raw_incumbents':discarded,'maps':details,'methods':methods})
 assert len(raws)==len(set(raws))==8 and len(geometries)==len(set(geometries))==8
 receipt={'schema':'root_saved_batch_integrity_audit_v1','source_sha256':sha(__file__),'executor':'root same model; independent evaluator replay, NOT independent-agent signoff','new_solver_calls':0,'new_maps':0,'training_calls':0,'formal_maps':0,'audited_author_attempts':8,'audited_intent_rows':80,'audited_actual_comparison_launches':sum(x['attempted_rows'] for x in reports),'audited_delivered_rows':sum(x['delivered_rows'] for x in reports),'replay_calls':sum(x['replay_calls'] for x in reports),'elapsed_s':time.perf_counter()-start,'batches':reports,'status':'PASS_SAVED_INTEGRITY; G3_NOT_PASSED; DO_NOT_NAME_STRONGEST_NONRL'}
 Path(args.report).write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+chr(10));print(json.dumps({k:v for k,v in receipt.items() if k!='batches'},sort_keys=True))
if __name__=='__main__':main()
