#!/usr/bin/env python3
"""Saved evidence audit only: no search, data generation, model decode or training.

Author/model/route replays execute only after an explicit invocation on <COMPUTE_HOST>.
The model/timing extension must be supplied before an overall PASS is possible.
"""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal
import argparse
import hashlib
import json
import math
import socket
import sys
from model_timing_audit import audit_models_and_timing

NAMESPACE='<COMPUTE_HOST>-ordinary-route-ppo-attribution-20261104-v1'
SEEDS=(103,211,307)
REGIMES=('frozen_bc','ppo','continued_bc')
TOL=1e-7
def read(p):
    return json.loads(Path(p).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON '+x)))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def close(a,b):
    return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=TOL

def geometry(text):
    nodes=[]
    for line in text.splitlines()[1:]:
        if not line.strip():continue
        fields=line.split()
        if len(fields)!=5:raise ValueError('instance column mismatch')
        int(fields[0]);x,y,e,s=map(Decimal,fields[1:])
        if any(not v.is_finite() for v in (x,y,e,s)):raise ValueError('nonfinite instance')
        nodes.append((x,y,e,s))
    if not nodes:raise ValueError('no geometry')
    mx,my=min(Fraction(n[0]) for n in nodes),min(Fraction(n[1]) for n in nodes)
    def rat(x):return str(x.numerator) if x.denominator==1 else f'{x.numerator}/{x.denominator}'
    rows=[{'kind':'site' if e==s==0 else 'target','x':rat(Fraction(x)-mx),'y':rat(Fraction(y)-my),'energy':rat(Fraction(e)),'service':rat(Fraction(s))} for x,y,e,s in nodes]
    rows.sort(key=lambda x:tuple(x[k] for k in ('kind','x','y','energy','service')))
    return hashlib.sha256(canonical({'schema':'translation_row_order_invariant_geometry_v1','nodes':rows}).encode('ascii')).hexdigest()

def fixed_scenario(raw):
    return {'schema':'weather_map_scenario_v1','name':'fixed-global-square-and-wind-v1','instance_sha256':raw,
            'wind_knots':[{'time_s':0,'east_mps':1,'north_mps':0},{'time_s':900,'east_mps':-1,'north_mps':1},{'time_s':1800,'east_mps':0,'north_mps':-1}],
            'no_fly_zone':{'vertices_m':[[6750,6750],[7250,6750],[7250,7250],[6750,7250]],'on_s':300,'off_s':1200},
            'flight':{'speed_m_per_min':900,'flight_energy_per_min':0.018}}

def allocations():
    return [{'id':f'{split}_{i}','split':split,'namespace':NAMESPACE+f':{split}_{i}',
             'partition':'opportunity' if split=='TRAIN' else 'validation','ordinal':1}
            for split,count in (('TRAIN',6),('VAL',2)) for i in range(1,count+1)]

def expected_keys():
    methods=['author','strict','annealed']+[f'{r}_{s}' for r in REGIMES for s in SEEDS]
    return {(f'VAL_{i}',m,b) for i in (1,2) for m in methods for b in (6,12)}

def audit(args):
    # Explicit identity proof supports <COMPUTE_HOST> containers with an opaque hostname.
    host=socket.gethostname().split('.')[0]
    if not host.startswith('<COMPUTE_HOST>'):
        proof=read(args.host_proof) if args.host_proof else {}
        if proof.get('execution_host')!='<COMPUTE_HOST>' or proof.get('observed_hostname')!=socket.gethostname():
            raise RuntimeError('<COMPUTE_HOST> execution or matching frozen <COMPUTE_HOST> host proof required')
    root=Path(args.project_root).resolve();out=Path(args.results).resolve();regpath=Path(args.registration).resolve()
    errors=[];replays=[];maps=[];counts={};cases={};calls=0
    def check(ok,label):
        if not ok:errors.append(label)
    check(sha(regpath)==args.registration_sha256,'registration hash')
    reg=read(regpath);check(reg.get('schema')=='ordinary_route_pilot_p2','registration schema')
    check(reg.get('namespace')==NAMESPACE and reg.get('allocations')==allocations(),'fixed eight allocations')
    check(reg.get('seeds')==list(SEEDS) and reg.get('regimes')==list(REGIMES),'planned seeds/regimes')
    check(reg.get('phase_wall_cap_s')==7200 and reg.get('common_wall_cap_s')==300 and reg.get('continuation_wall_cap_s')==600,'time ceilings')
    check(reg.get('no_replacement') is True and reg.get('family')==[3,20] and reg.get('author_profile')=='J1b','domain and author identity')
    check(reg.get('author_seed_namespace')==NAMESPACE+':J1b' and reg.get('author_timeout_s')==180,'author seed/budget')
    check(Path(reg['project_root']).resolve()==root,'registered root')
    for name,digest in reg['dependencies'].items():
        path=Path(name) if Path(name).is_absolute() else root/name
        check(path.is_file() and sha(path)==digest,'dependency '+name)
    sidecar=Path(reg['sidecar'])
    check(sidecar.is_file() and sha(sidecar)==reg.get('sidecar_sha256')=='a8d43c449dff1533442cc5a6cfbf8337cb105529aaf474560c4bbc56f0613264','four-map sidecar')
    excludedraw=set();excludedgeo=set()
    for name in reg['exclusion_paths']:
        doc=read(name)
        for record in doc.get('records',[]):
            if record.get('raw_sha256'):excludedraw.add(record['raw_sha256'])
            if record.get('canonical_geometry_sha256'):excludedgeo.add(record['canonical_geometry_sha256'])
    check(len(excludedraw)>=12120 and len(excludedgeo)>=12120 and len(reg['exclusion_paths'])==5 and str(sidecar) in reg['exclusion_paths'],'operative historical and new-four exclusion coverage')
    mat=read(out/'MATERIALIZATION.json')['records'];anchors=read(out/'ANCHORS.json')['records']
    expectedids=[a['id'] for a in allocations()]
    check([r['id'] for r in mat]==expectedids,'all eight materialization slots')
    check([r['id'] for r in anchors]==expectedids,'all eight anchor slots')
    check(not [p.name for p in out.iterdir() if p.is_dir() and (p.name.startswith('TRAIN_') or p.name.startswith('VAL_')) and p.name not in expectedids],'unallocated replacement directory')
    g=root/'route_rl_research/20261103/return_makespan/g24_weather_nfz'
    for path in (g,g.parent,root/'reproduction/reviewer_package_semfix',g.parent/'g23/author_baseline'):sys.path.insert(0,str(path))
    from lrphsd.problem import read_instance
    from scorer import CostAnchor
    from weather_scenario_io import load_weather_scenario
    from weather_full_map import replay_weather_solution
    import author_runner
    seenraw=set();seengeo=set()
    for allocated in allocations():
        name=allocated['id'];directory=out/name
        mr=next((r for r in mat if r['id']==name),{})
        ar=next((r for r in anchors if r['id']==name),{})
        state={**allocated,'generation_status':mr.get('status'),'anchor_status':ar.get('status'),
               'raw_sha256':mr.get('raw_sha256'),'canonical_geometry_sha256':mr.get('geometry_sha256')};maps.append(state)
        try:
            generation=read(directory/'generation.json') if (directory/'generation.json').exists() else None
            if generation:
                identity=generation['metadata']['allocation_identity']
                check(all(identity.get(k)==v for k,v in {'namespace':allocated['namespace'],'family':[3,20],'partition':allocated['partition'],'ordinal':1}.items()),name+' generator allocation')
                for stream,key in (('coordinates','coordinate_seed_u64'),('target_ids','target_id_seed_u64')):
                    payload={'schema':'route_rl_sequential_v2_seed_v1','namespace':allocated['namespace'],'family':[3,20],'partition':allocated['partition'],'ordinal':1,'stream':stream}
                    seed=int.from_bytes(hashlib.sha256(canonical(payload).encode('ascii')).digest()[:8],'big')
                    check(identity.get(key)==seed,name+' '+stream+' RNG')
                check(generation['metadata'].get('replacement_on_failure') is False and generation['metadata'].get('retained_slot') is True,name+' retained no-replacement')
                state.update(raw_sha256=generation.get('raw_sha256'),canonical_geometry_sha256=generation.get('canonical_geometry_sha256'))
                retained=generation.get('retained_complete_or_partial_text')
                if retained:
                    check(hashlib.sha256(retained.encode()).hexdigest()==state['raw_sha256'],name+' retained proposal bytes')
                    if state['canonical_geometry_sha256']:check(geometry(retained)==state['canonical_geometry_sha256'],name+' retained geometry')
            if mr.get('status')=='generated':
                check(generation is not None and generation.get('status')=='generated',name+' missing generated receipt')
                raw=sha(directory/'instance.txt');geo=geometry((directory/'instance.txt').read_text())
                check(raw==mr.get('raw_sha256')==generation.get('raw_sha256') and geo==mr.get('geometry_sha256')==generation.get('canonical_geometry_sha256'),name+' generated identities')
                check(raw not in excludedraw and geo not in excludedgeo,name+' exclusion collision')
                check(raw not in seenraw and geo not in seengeo,name+' within-batch duplicate')
                seenraw.add(raw);seengeo.add(geo)
                check(read(directory/'scenario.json')==fixed_scenario(raw),name+' scenario')
            for relative,digest in ar.get('artifact_hashes',{}).items():
                path=directory/relative;check(path.is_file() and sha(path)==digest,name+' artifact '+relative)
            runpath=directory/'author/RUN.json'
            if runpath.exists():
                calls+=1;run=read(runpath);raw=sha(directory/'instance.txt')
                seed=int.from_bytes(hashlib.sha256((NAMESPACE+':J1b:'+raw).encode()).digest()[:8],'big')&((1<<63)-1)
                check(run.get('profile')=='J1b' and run.get('seed')==seed and run.get('input_sha256')==raw,name+' author invocation identity')
                check(run.get('timeout_seconds')==180,name+' author timeout')
                buildpath=Path(reg['build_dir'])/'J1b/BUILD_MANIFEST.json';build=read(buildpath)
                check(run.get('build_manifest_sha256')==sha(buildpath) and run.get('class_hashes')==build.get('class_hashes'),name+' author build')
                check(run.get('java')==build.get('jdk',{}).get('java'),name+' author JDK identity')
                check(run.get('source_identity')==author_runner.profile_identity(root/'reproduction/reviewer_package_semfix','J1b'),name+' author source')
                for relative,digest in run.get('artifacts',{}).items():check(sha(directory/'author'/relative)==digest,name+' author artifact '+relative)
            elif ar.get('status')=='eligible':check(False,name+' eligible missing RUN')
            if not (directory/'author/solution.json').exists():
                check(ar.get('status')!='eligible',name+' eligible missing author solution');continue
            instance=read_instance(directory/'instance.txt');solution=read(directory/'author/solution.json')
            anchor=CostAnchor.from_solution(instance,solution);weather,_=load_weather_scenario(directory/'scenario.json',expected_instance_sha256=instance.sha256)
            uncapped=replay_weather_solution(instance,anchor,weather,solution,strict_weather_cap=False);cap=uncapped['weather_cost']
            rep=replay_weather_solution(instance,anchor,weather,solution,weather_cost_cap=cap)
            replays.append({'map':name,'kind':'author','result':rep})
            state.update(author_original_cost=anchor.cost,author_weather_cost=cap,author_M_return=rep['M_return'],author_MTC=rep['MTC'],author_admissible=rep['admissible'])
            if ar.get('status')=='eligible':
                check(rep['admissible'],name+' eligible author inadmissible')
                saved=read(directory/'weather_anchor.json')
                check(close(saved.get('weather_cost_cap'),cap) and close(saved.get('fixed_outer_anchor_cost'),anchor.cost),name+' author caps')
                process=ar.get('author_process',{})
                check(process.get('status')=='completed' and process.get('stage_wall_s',1e9)<=185,name+' eligible author process late/failed')
                cases[name]=(instance,anchor,weather,cap,rep,solution)
        except Exception as exc:check(False,name+' identity/author audit exception '+repr(exc))
    train=read(out/'TRAIN_MANIFEST.json') if (out/'TRAIN_MANIFEST.json').exists() else None
    if train:
        check(train.get('split')=='TRAIN' and train.get('registration_sha256')==sha(regpath),'TRAIN manifest binding')
        check([x['id'] for x in train.get('allocation_records',[])]==[f'TRAIN_{i}' for i in range(1,7)],'six TRAIN denominator')
        expectedeligible={x['id'] for x in anchors if x['id'].startswith('TRAIN_') and x['status']=='eligible'}
        check({x['id'] for x in train.get('cases',[])}==expectedeligible,'eligible TRAIN exact manifest')
        for record in train.get('cases',[]):check(record.get('split')=='TRAIN' and 'VAL' not in record['id'] and 'VAL' not in record['directory'].upper(),'VAL leakage into TRAIN')
        check({r.get('raw_sha256') for r in train.get('excluded_identities',[])}==excludedraw and {r.get('canonical_geometry_sha256') for r in train.get('excluded_identities',[])}==excludedgeo,'TRAIN complete exclusion union')
        check(train.get('dependencies')==reg['dependencies'],'TRAIN frozen source dependency identity')
    val=read(out/'VAL_MANIFEST.json') if (out/'VAL_MANIFEST.json').exists() else None
    if val:check(val.get('registration_sha256')==sha(regpath) and [r.get('id') for r in val.get('cases',[])]==['VAL_1','VAL_2'] and all(r.get('split')=='VAL' for r in val['cases']),'two allocated VAL manifest binding')
    final=read(out/'RESULTS.json')
    check(final.get('proposals')==8 and final.get('model_slots')==9 and final.get('validation_rows')==48 and final.get('formal_maps')==0 and final.get('novelty_claim') is False,'final counts and claim boundary')
    comparisons=read(out/'validation/COMPARISONS.json')
    keys=[(r['map'],r['method'],r['budget_s']) for r in comparisons]
    check(len(keys)==48 and len(set(keys))==48 and set(keys)==expected_keys(),'exact48validationkeys')
    improved=0;fallbacks=0;rawcomplete=0;row_evidence=[];delivered_scores={}
    for row in comparisons:
        name=row['map'];label=f"{name}/{row['method']}/{row['budget_s']}";status=row['delivery_status'];counts[status]=counts.get(status,0)+1
        delivered=status=='delivered';process=row.get('process') or {};child=process.get('raw') or {};selected=row.get('selected')
        if process.get('ended_abs') is not None:
            check(close(process.get('stage_wall_s'),process['ended_abs']-process['started_abs']),label+' external wall reconciliation')
            if process['ended_abs']>process['deadline_abs'] or process.get('hard_killed'):check(not delivered and selected is None,label+' late/hardkill receives no credit')
        if delivered:
            check(name in cases,label+' delivered without eligible case')
            check(process.get('status')=='completed' and process.get('exit_code')==0 and not process.get('hard_killed') and process.get('stage_wall_s',1e9)<=row['budget_s'],label+' parent timed delivery')
            check(isinstance(selected,dict) and selected==child.get('candidate'),label+' selected child binding')
        else:check(selected is None,label+' non-delivery selected notnull')
        candidates=[]
        if isinstance(selected,dict):candidates.append(('selected',selected,True))
        if isinstance(child.get('candidate'),dict):candidates.append(('raw_candidate',child['candidate'],False))
        raw=child.get('raw_construction')
        ev={'map':name,'method':row['method'],'budget_s':row['budget_s'],'delivery_status':status,'delivered':delivered,
            'raw_complete_physical_construction':bool(isinstance(raw,dict) and (raw.get('solution') or raw.get('complete'))),'author_fallback':False,'strict_improvement':False}
        if isinstance(raw,dict):
            if isinstance(raw.get('solution'),dict):candidates.append(('raw_construction',raw,False));rawcomplete+=1
            elif raw.get('complete') and isinstance(raw.get('result',{}).get('solution'),dict):candidates.append(('raw_complete_episode',raw['result'],False));rawcomplete+=1
        for kind,obj,credit in candidates:
            if name not in cases:check(False,label+' candidate without eligible case '+kind);continue
            try:
                instance,anchor,weather,cap,authorrep,author=cases[name]
                rep=replay_weather_solution(instance,anchor,weather,obj['solution'],weather_cost_cap=cap)
                replays.append({'map':name,'method':row['method'],'budget_s':row['budget_s'],'kind':kind,'delivered_credit':delivered and credit,'result':rep})
                check(rep['admissible'],label+' '+kind+' full replay inadmissible')
                check(rep['original_score']['cost']<=anchor.cost+TOL and rep['weather_cost']<=cap+TOL,label+' '+kind+' independently recomputed dual caps')
                saved=obj.get('replay')
                if isinstance(saved,dict):
                    for key in ('M_return','MTC','weather_cost'):check(close(rep.get(key),saved.get(key)),label+' '+kind+' '+key+' mismatch')
                if credit:
                    delivered_scores[(name,row['method'],row['budget_s'])]=rep['M_return']
                    if rep['M_return']<authorrep['M_return']-1e-12:improved+=1;ev['strict_improvement']=True
                    if canonical(obj['solution'])==canonical(author):fallbacks+=1;ev['author_fallback']=True
            except Exception as exc:check(False,label+' '+kind+' replay exception '+repr(exc))
        row_evidence.append(ev)
    models=read(out/'MODELS.json');keys=[(x['seed'],x['regime']) for x in models['records']]
    check(len(keys)==9 and set(keys)=={(s,r) for s in SEEDS for r in REGIMES},'nine model slots')
    def replay_saved(name,solution,recorded,label):
        if name not in cases:check(False,label+' training solution without eligible case');return None
        try:
            instance,anchor,weather,cap,_,_=cases[name]
            rep=replay_weather_solution(instance,anchor,weather,solution,weather_cost_cap=cap)
            replays.append({'map':name,'kind':'saved_TRAIN_'+label,'delivered_credit':False,'result':rep})
            check(rep['admissible'] and rep['original_score']['cost']<=anchor.cost+TOL and rep['weather_cost']<=cap+TOL,label+' TRAIN full replay and dual caps')
            check(isinstance(recorded,dict),label+' missing recorded full replay')
            if isinstance(recorded,dict):
                for key in ('M_return','MTC','weather_cost'):check(close(rep.get(key),recorded.get(key)),label+' '+key+' TRAIN replay mismatch')
            return rep
        except Exception as exc:check(False,label+' TRAIN replay exception '+repr(exc));return None
    reg['_registration_path']=str(regpath)
    extension=audit_models_and_timing(reg,out,check,replay_saved)
    pairwise=[]
    for name in ('VAL_1','VAL_2'):
        for budget in (6,12):
            for seed in SEEDS:
                pm=f'ppo_{seed}';p=delivered_scores.get((name,pm,budget))
                for cm in (f'frozen_bc_{seed}',f'continued_bc_{seed}','author','strict','annealed'):
                    c=delivered_scores.get((name,cm,budget));matched=cm!=f'continued_bc_{seed}' or next(r for r in models['records'] if r['seed']==seed and r['regime']=='continued_bc').get('wall_matched') is True
                    pairwise.append({'map':name,'budget_s':budget,'seed':seed,'ppo':pm,'comparator':cm,'planned_pair_denominator':1,'both_delivered':p is not None and c is not None,'wall_matched_comparison':matched,'ppo_M_return':p,'comparator_M_return':c,'strict_ppo_win':p<c-1e-12 if p is not None and c is not None and matched else None})
    summary={}
    for name in ('VAL_1','VAL_2'):
        for regime in REGIMES:
            for budget in (6,12):
                planned=[r for r in comparisons if r['map']==name and r['method'] in {f'{regime}_{s}' for s in SEEDS} and r['budget_s']==budget]
                success=[r for r in planned if r['delivery_status']=='delivered' and r.get('selected')]
                scores=[r['selected']['replay']['M_return'] for r in success]
                summary[str((name,regime,budget))]={'planned':3,'delivered':len(success),'quality_denominator':len(scores),
                    'success_fraction':len(success)/3,'conditional_mean_M_return':sum(scores)/len(scores) if scores else None,'all_planned_delivered':len(success)==3}
    return {'schema':'ordinary_pilot_saved_result_audit_v1','status':'PASS' if not errors else 'FAIL','errors':errors,
            'registration_sha256':sha(regpath),'auditor_sha256':sha(__file__),'maps':maps,'replays':replays,'policy_family_denominators':summary,
            'model_timing_extension':extension,'row_evidence':row_evidence,'pairwise_comparisons':pairwise,'counts':{'proposal_slots':8,'author_RUN_receipts':calls,'eligible_anchors':len(cases),'validation_slots':48,
            'delivery_statuses':counts,'delivered_strict_improvements':improved,'author_fallbacks':fallbacks,'raw_complete_constructions':rawcomplete},
            'claim_boundary':'two-map exploratory ordinary-control validation; no strongest/innovation/Formal/general superiority'}

def main():
    parser=argparse.ArgumentParser()
    for key in ('project-root','registration','registration-sha256','results','report'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--host-proof')
    args=parser.parse_args();target=Path(args.report)
    if target.exists():raise FileExistsError('preserve existing audit report')
    report=audit(args);target.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    exposure=target.with_name('PILOT_EXPOSURE_EXCLUSIONS.json')
    if exposure.exists():raise FileExistsError('preserve existing exposure sidecar')
    records=[x for x in report['maps'] if isinstance(x.get('raw_sha256'),str) and len(x['raw_sha256'])==64 and isinstance(x.get('canonical_geometry_sha256'),str) and len(x['canonical_geometry_sha256'])==64]
    exposure.write_text(json.dumps({'schema':'ordinary_pilot_exposure_sidecar_v1','namespace':NAMESPACE,'records':records,'slots':report['maps'],
        'registration_sha256':report['registration_sha256'],'future_generation_must_include_this_sidecar':True},sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':report['status'],'errors':len(report['errors']),'counts':report['counts']},sort_keys=True))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())

