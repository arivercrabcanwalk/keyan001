"""Frozen four-map G3 non-RL comparator calibration. No training or Formal entrypoint."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

for _name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
    os.environ[_name]='1'

NAMESPACE = '<COMPUTE_HOST>-g3-nonrl-calibration-20261105-v1'
METHODS = ('greedy', 'beam', 'strict', 'annealed', 'multineighborhood_v2')
BUDGETS = (6, 12)
EXPOSURE_MANIFEST = Path(__file__).resolve().parent / 'ALL_PRIOR_MAP_EXPOSURES.json'
RESOURCE_RESERVATION = Path(__file__).resolve().parent / 'RESOURCE_ALLOCATION.json'

class PhaseDeadline(BaseException):
    pass

def allocations():
    return [{'id':f'calibration_{i}','generator_namespace':NAMESPACE+f':slot{i}',
             'partition':'calibration','ordinal':1} for i in range(1,5)]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp')
    temp.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
    os.replace(temp,p)


def setup(root):
    root=Path(root).resolve()
    g=root/'route_rl_research/20261103/return_makespan/g24_weather_nfz'
    multi=g/'next_stage_protocol_sol_20261104/strong_control/multineighborhood_v2'
    for path in (g,g.parent,g/'comparison',g/'next_stage_protocol_sol_20261104',
                 g/'next_stage_protocol_sol_20261104/strong_control',
                 multi,Path(__file__).resolve().parent,
                 root/'reproduction/reviewer_package_semfix'):
        sys.path.insert(0,str(path))
    import development_runner as r
    return r,g


def validate_registration(path):
    value=read(path)
    if value['namespace']!=NAMESPACE or value['slots']!=[f'calibration_{i}' for i in range(1,5)]:
        raise ValueError('four-map G3 calibration allocation mismatch')
    if value.get('generator_allocations')!=allocations():raise ValueError('per-slot generator allocation mismatch')
    if value['methods']!=list(METHODS) or value['budgets_s']!=list(BUDGETS) or value['seed']!=103:
        raise ValueError('method/budget/seed mismatch')
    fixed={'schema':'g3_nonrl_calibration_v1','family':[3,20],'partition':'calibration',
           'author_profile':'J1b','author_timeout_s':180,'author_seed_namespace':NAMESPACE+':J1b',
           'phase_wall_cap_s':2160,'generation_wall_cap_s':120,'parent_timeout_grace_s':2,
           'packaging_reserve_s':.25,'scenario_rule':'fixed-global-square-and-wind-v1',
           'no_replacement':True,'training_calls':0,'formal_maps':0}
    if any(value.get(k)!=v for k,v in fixed.items()):raise ValueError('immutable registration setting mismatch')
    if (Path(value.get('identity_exclusion_manifest','')).resolve()!=EXPOSURE_MANIFEST.resolve() or
            value.get('identity_exclusion_manifest_sha256')!=sha(EXPOSURE_MANIFEST)):
        raise ValueError('identity exposure manifest mismatch')
    for path,digest in value['dependencies'].items():
        if sha(Path(value['project_root'])/path)!=digest:
            raise ValueError('dependency changed: '+path)
    for path,digest in value.get('external_dependencies',{}).items():
        if sha(path)!=digest:raise ValueError('external author dependency changed: '+path)
    return value


def register(args):
    r,g=setup(args.project_root)
    r.require_v1_probe_exclusions()
    ledger=read(args.resource_ledger)
    if not (ledger.get('existing_reserved_core_hours')==6.3 and
            ledger.get('new_phase_core_hours_reservation')==.6 and
            ledger.get('charged_reservation_total_core_hours')==6.9 and
            ledger.get('original_cap_core_hours')==16 and
            ledger.get('phase_wall_cap_s')==2160 and ledger.get('new_author_runs')==4 and
            ledger.get('new_calibration_proposals')==4 and ledger.get('new_comparison_rows')==40):
        raise ValueError('bounded resource reservation fields invalid')
    paths=[Path(key) if Path(key).is_absolute() else Path(args.project_root)/key
           for key in r.dependencies()]
    # Freeze this driver plus local standard controls and outer timer sources.
    multi = g/'next_stage_protocol_sol_20261104/strong_control/multineighborhood_v2'
    paths += [Path(__file__).resolve(),g/'next_stage_protocol_sol_20261104/incumbent_search.py',
              g/'next_stage_protocol_sol_20261104/strong_control/annealed_control.py',
              multi/'route_annealing.py',
              multi/'runner_adapter.py',
              EXPOSURE_MANIFEST,RESOURCE_RESERVATION,
              g/'timed_physical_delivery_20261104/delivery.py',
              Path(__file__).resolve().parent/'PROTOCOL.md',
              Path(__file__).resolve().parent/'INITIAL_SPEC.md',
              Path(__file__).resolve().parent/'AMENDMENT.md',
              Path(__file__).resolve().parent/'build_exposure_manifest.py',
              Path(__file__).resolve().parent/'test_phase_driver.py',
              g/'next_stage_protocol_sol_20261104/strong_control/INITIAL_SPEC.md',
              Path(args.resource_ledger).resolve()]
    root=Path(args.project_root).resolve()
    dependencies={str(p.resolve().relative_to(root)):sha(p) for p in paths}
    # verify_build pins published source identity, JDK, snapshots and class files.
    build=Path(args.build_dir)/'J1b'
    r.author_runner.verify_build(r.REPRO,'J1b',Path(args.java_home),Path(args.build_dir))
    external={str(p.resolve()):sha(p) for p in build.rglob('*') if p.is_file()}
    value={'schema':'g3_nonrl_calibration_v1','namespace':NAMESPACE,
           'project_root':str(root),'slots':[f'calibration_{i}' for i in range(1,5)],
           'generator_allocations':allocations(),
           'family':[3,20],'partition':'calibration','methods':list(METHODS),
           'budgets_s':list(BUDGETS),'seed':103,'author_profile':'J1b',
           'author_timeout_s':180,'author_seed_namespace':NAMESPACE+':J1b',
           'java_home':args.java_home,'build_dir':args.build_dir,
           'phase_wall_cap_s':2160,'generation_wall_cap_s':120,'parent_timeout_grace_s':2,
           'packaging_reserve_s':.25,'scenario_rule':'fixed-global-square-and-wind-v1',
           'dependencies':dependencies,'external_dependencies':external,'resource_ledger_sha256':sha(args.resource_ledger),
           'identity_exclusion_manifest':str(EXPOSURE_MANIFEST),
           'identity_exclusion_manifest_sha256':sha(EXPOSURE_MANIFEST),
           'method_order':list(METHODS),'primary_calibration_budget_s':12,
           'selection_rule':'choose_nonRL_method_with_lowest_mean_delivered_M_return_at_12s_on_all_four_eligible_maps; deadline_no_delivery_quality_is_author_fallback_and_delivery_rate_is_reported_separately; ties_use_frozen_method_order',
           'no_replacement':True,'quality_claim':'exploratory_calibration_only',
           'training_calls':0,'formal_maps':0}
    if Path(args.registration).exists():raise FileExistsError(args.registration)
    write(args.registration,value)
    return value


def generate_four(registration,out,runner,remaining=lambda:1e9):
    """No replacement. Fake runner injection is exclusively for server tests."""
    exclusion_paths=[*runner.generator.default_exclusion_paths(),
                     Path(registration['identity_exclusion_manifest'])]
    exclusions=runner.generator.ExclusionIndex.from_paths(exclusion_paths)
    exclusions.require_research_ready()
    seen_raw=set();seen_geometry=set()
    rows=[{'id':name,'status':'not_started','reason':'not_started'} for name in registration['slots']]
    write(Path(out)/'MATERIALIZATION.json',{'slots':rows})
    for ordinal,name in enumerate(registration['slots'],1):
        d=Path(out)/name;d.mkdir(parents=True,exist_ok=False)
        row={'id':name,'status':'budget_skipped','reason':'phase_budget_exhausted'}
        if remaining()>10:
            try:
                allocated=allocations()[ordinal-1]
                result=runner.generator.generate_allocated_instance(3,20,namespace=allocated['generator_namespace'],
                    partition='calibration',ordinal=1,exclusions=exclusions)
                write(d/'generation.json',result)
                row.update(status=result['status'],reason=result['failure_reason'],
                           raw_sha256=result.get('raw_sha256'),geometry_sha256=result.get('canonical_geometry_sha256'))
                if result['status']=='generated':
                    raw,geometry=result['raw_sha256'],result['canonical_geometry_sha256']
                    if raw in seen_raw or geometry in seen_geometry:
                        row.update(status='generation_failed',reason='within_allocation_identity_collision')
                    else:
                        seen_raw.add(raw);seen_geometry.add(geometry)
                        (d/'instance.txt').write_text(result['solver_input_text'],newline='\n')
                        if sha(d/'instance.txt')!=raw:raise ValueError('instance identity mismatch')
                        write(d/'scenario.json',runner.scenario(raw))
            except Exception as error:
                row.update(status='generation_failed',reason=f'{type(error).__name__}: {error}')
        rows[ordinal-1]=row
        write(Path(out)/'MATERIALIZATION.json',{'slots':rows})
    return rows


def verify_case(directory,expected):
    for relative,digest in expected.items():
        if sha(Path(directory)/relative)!=digest:raise ValueError('case artifact changed: '+relative)


def verify_generated_identity(directory,out,case,runner,registration):
    row=next(x for x in read(Path(out)/'MATERIALIZATION.json')['slots'] if x['id']==case)
    generation=read(Path(directory)/'generation.json')
    raw=sha(Path(directory)/'instance.txt')
    if row['status']!='generated' or raw!=row.get('raw_sha256') or raw!=generation.get('raw_sha256'):
        raise ValueError('pre-author materialization raw identity mismatch')
    allocated=next(x for x in allocations() if x['id']==case)
    identity=generation['metadata']['allocation_identity']
    expected={'namespace':allocated['generator_namespace'],'family':[3,20],
              'partition':'calibration','ordinal':1,
              'coordinate_seed_u64':runner.generator.derive_seed(allocated['generator_namespace'],3,20,'calibration',1,'coordinates'),
              'target_id_seed_u64':runner.generator.derive_seed(allocated['generator_namespace'],3,20,'calibration',1,'target_ids')}
    if identity!=expected:raise ValueError('pre-author generator allocation mismatch')
    nodes=runner.generator.parse_instance_text((Path(directory)/'instance.txt').read_text())
    geometry=runner.generator.canonical_geometry_identity(nodes)
    if geometry!=row.get('geometry_sha256') or geometry!=generation.get('canonical_geometry_sha256'):
        raise ValueError('pre-author geometry identity mismatch')
    if read(Path(directory)/'scenario.json')!=runner.scenario(raw):raise ValueError('pre-author scenario mismatch')
    exclusion_paths=[*runner.generator.default_exclusion_paths(),
                     Path(registration['identity_exclusion_manifest'])]
    exclusions=runner.generator.ExclusionIndex.from_paths(exclusion_paths)
    if exclusions.collisions(raw,geometry):raise ValueError('pre-author exclusion collision')
    return raw


def worker(args):
    # Parent deadline includes this interpreter's import and source validation.
    registration=validate_registration(args.registration)
    r,g=setup(registration['project_root'])
    directory=Path(args.out)/args.case
    anchors=read(Path(args.out)/'ANCHORS.json')
    row=next(x for x in anchors['slots'] if x['id']==args.case)
    if row['status']!='eligible':raise ValueError('case is not eligible')
    verify_case(directory,row['artifact_hashes'])
    case=r.load_case(directory)
    author=read(directory/'author/solution.json')
    fallback=r.replay_weather_solution(*case[:3],author,weather_cost_cap=case[3])
    if not fallback['admissible']:raise ValueError('fallback fails complete replay')
    raw=None
    remaining=args.deadline-time.perf_counter()-registration['packaging_reserve_s']
    if remaining>0:
        if args.method=='strict':
            from incumbent_search import optimize
            raw=optimize(*case[:3],author,weather_cost_cap=case[3],budget_s=remaining,seed=103)
            episode={'complete':raw['delivery_status']=='delivered',
                     'result':{'solution':raw['solution'],'replay':raw['replay']},
                     'failure':None if raw['delivery_status']=='delivered' else 'deadline'}
        elif args.method=='annealed':
            from annealed_control import optimize
            raw=optimize(*case[:3],author,weather_cost_cap=case[3],budget_s=remaining,seed=103)
            episode={'complete':raw['delivery_status']=='delivered',
                     'result':{'solution':raw['solution'],'replay':raw['replay']},
                     'failure':None if raw['delivery_status']=='delivered' else 'deadline'}
        elif args.method=='multineighborhood_v2':
            from runner_adapter import run_episode
            episode=run_episode(case,author,deadline_s=remaining,seed=103)
            raw=episode.get('search_receipt')
        elif args.method=='greedy':
            episode=r.run_episode(case,model=None,deadline=remaining,max_steps=128)
        elif args.method=='beam':
            episode=r.beam_episode(case,remaining,max_steps=128)
        else:
            raise ValueError('method is not a frozen physical-route comparator')
    else:
        episode={'complete':False,'failure':'deadline','result':None}
    proposed=episode.get('result') if episode.get('complete') else None
    solution=proposed['solution'] if proposed is not None else author
    replay=r.replay_weather_solution(*case[:3],solution,weather_cost_cap=case[3])
    selected=solution if replay['admissible'] and replay['M_return']<fallback['M_return'] else author
    selected_replay=replay if selected is solution else fallback
    # Serialization is inside parent timer; raw records preserved even if late.
    episode_receipt={key:value for key,value in episode.items()
                     if key not in ('result','transitions')}
    print(json.dumps({'candidate':{'solution':selected,'replay':selected_replay},
                      'fallback':fallback,'raw_search':raw,'source_case':args.case,
                      'method':args.method,'registration_sha256':sha(args.registration),
                      'candidate_complete':episode.get('complete',False),
                      'candidate_failure':episode.get('failure'),
                      'episode_receipt':episode_receipt},
                     allow_nan=False,sort_keys=True),flush=True)


def collect_process(command,*,budget_s,grace_s=2,popen=subprocess.Popen,clock=time.perf_counter):
    started=clock();deadline=started+budget_s
    process=popen(command+['--deadline',repr(deadline)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    timed_out=False
    try:stdout,stderr=process.communicate(timeout=budget_s+grace_s)
    except subprocess.TimeoutExpired:
        timed_out=True;process.kill();stdout,stderr=process.communicate()
    except BaseException:
        process.kill();process.communicate()
        raise
    raw=None;parse_error=None
    try:raw=json.loads(stdout)
    except Exception as e:parse_error=f'{type(e).__name__}: {e}'
    elapsed=clock()-started
    admissible=(isinstance(raw,dict) and isinstance(raw.get('candidate'),dict)
                and raw['candidate'].get('replay',{}).get('admissible') is True)
    delivered=not timed_out and process.returncode==0 and elapsed<=budget_s and admissible
    return {'selected':raw['candidate'] if delivered else None,'raw_child':raw,
            'raw_stdout':stdout,'stderr':stderr,'exit_code':process.returncode,
            'parent_elapsed_s':elapsed,'budget_s':budget_s,'hard_killed':timed_out,
            'delivery_status':'delivered' if delivered else ('deadline_no_delivery' if elapsed>budget_s or timed_out else 'failed_no_delivery'),
            'parse_error':parse_error}


def author_worker(args):
    registration=validate_registration(args.registration)
    r,g=setup(registration['project_root']);directory=Path(args.out)/args.case
    try:
        raw=verify_generated_identity(directory,args.out,args.case,r,registration)
        seed=r.author_runner.seed_for_input(raw,registration['author_seed_namespace'])
        result=r.author_runner.run_one(directory/'instance.txt','J1b',seed,directory/'author',r.REPRO,
            g.parent/'scorer.py',Path(registration['java_home']),Path(registration['build_dir']),180)
        if not result['anchor_eligible']:raise ValueError('author_anchor_ineligible')
        receipt=r.prepare_author_weather_anchor(directory/'instance.txt',directory/'author',directory/'scenario.json')
        write(directory/'weather_anchor.json',receipt)
        entry={'status':'eligible','reason':None,'author_status':result['status'],'author_seed':seed,
               'artifact_hashes':{name:sha(directory/name) for name in ('instance.txt','scenario.json','weather_anchor.json','author/solution.json','author/RUN.json')}}
    except Exception as error:entry={'status':'anchor_failed','reason':f'{type(error).__name__}: {error}'}
    print(json.dumps(entry,sort_keys=True,allow_nan=False),flush=True)


def isolated_author(command,timeout_s,receipt_path=None):
    """Own process group includes child Python and its Java; always reap on abort."""
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        stdout,stderr=p.communicate(timeout=timeout_s)
    except BaseException as error:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        stdout,stderr=p.communicate()
        receipt={'exit_code':p.returncode,'stdout':stdout,'stderr':stderr,'killed_process_group':True,
                 'error':f'{type(error).__name__}: {error}'}
        if receipt_path is not None:write(receipt_path,receipt)
        if isinstance(error,subprocess.TimeoutExpired):
            return {'status':'anchor_failed','reason':'author_worker_hard_timeout','author_process':receipt}
        raise
    receipt={'exit_code':p.returncode,'stdout':stdout,'stderr':stderr,'killed_process_group':False}
    if receipt_path is not None:write(receipt_path,receipt)
    if p.returncode!=0:return {'status':'anchor_failed','reason':f'author_worker_exit{p.returncode}','author_process':receipt}
    entry=json.loads(stdout);entry['author_process']=receipt
    return entry


def run(args):
    started=time.perf_counter()
    registration=validate_registration(args.registration)
    r,g=setup(registration['project_root'])
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    remaining=lambda:registration['phase_wall_cap_s']-(time.perf_counter()-started)
    comparisons=[];anchors=[]
    terminal_error=None
    previous_handler=signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(PhaseDeadline('whole_phase_2160s_guard')))
    signal.setitimer(signal.ITIMER_REAL,max(.001,remaining()))
    try:
        generation_command=[sys.executable,str(Path(__file__).resolve()),'materialize',
                            '--registration',str(Path(args.registration).resolve()),'--out',str(out.resolve())]
        try:
            generation=subprocess.run(generation_command,capture_output=True,text=True,timeout=120)
            write(out/'GENERATION_PROCESS.json',{'exit_code':generation.returncode,'stdout':generation.stdout,'stderr':generation.stderr})
        except subprocess.TimeoutExpired as error:
            write(out/'GENERATION_PROCESS.json',{'exit_code':None,'hard_timeout':True,'stderr':str(error)})
        material=read(out/'MATERIALIZATION.json') if (out/'MATERIALIZATION.json').exists() else {'slots':[]}
        rows={x['id']:x for x in material['slots']}
        rows=[rows.get(name,{'id':name,'status':'generation_failed','reason':'generation_process_did_not_finish'}) for name in registration['slots']]
        for row in rows:
            if row['status']=='not_started':row.update(status='generation_failed',reason='generation_process_did_not_finish')
        write(out/'MATERIALIZATION.json',{'slots':rows})
        _execute_remaining(args,registration,r,g,out,remaining,rows,anchors,comparisons)
    except (Exception,PhaseDeadline) as error:
        terminal_error=f'{type(error).__name__}: {error}'
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous_handler)
        existing={x['id']:x for x in anchors}
        anchors[:]=[existing.get(name,{'id':name,'status':'phase_failed','reason':terminal_error or 'phase_not_completed'}) for name in registration['slots']]
        write(out/'ANCHORS.json',{'slots':anchors,'registration_sha256':sha(args.registration)})
        seen={(x['map'],x['method'],x['budget_s']) for x in comparisons}
        for name in registration['slots']:
            for method in METHODS:
                for budget in BUDGETS:
                    if (name,method,budget) not in seen:
                        comparisons.append({'map':name,'method':method,'budget_s':budget,'seed':103,
                                            'delivery_status':'phase_failed_skipped','reason':terminal_error or 'phase_not_completed','selected':None})
        write(out/'COMPARISONS.json',comparisons)
        write(out/'RESULTS.json',{'rows':len(comparisons),'proposals':4,'training_calls':0,'formal_maps':0,
                                'elapsed_s':time.perf_counter()-started,'phase_cap_s':2160,'terminal_error':terminal_error,
                                'quality_claim':'calibration_only_not_strongest_or_RL_evidence',
                                'registration_sha256':sha(args.registration)})


def _execute_remaining(args,registration,r,g,out,remaining,rows,anchors,comparisons):
    r.author_runner.verify_build(r.REPRO,'J1b',Path(registration['java_home']),Path(registration['build_dir']))
    for row in rows:
        entry=dict(row);d=out/row['id']
        if row['status']=='generated' and remaining()>185:
            try:
                validate_registration(args.registration)
                command=[sys.executable,str(Path(__file__).resolve()),'author',
                         '--registration',str(Path(args.registration).resolve()),'--out',str(out.resolve()),'--case',row['id']]
                entry.update(isolated_author(command,min(185,remaining()-1),d/'AUTHOR_PROCESS.json'))
            except Exception as error:entry.update(status='anchor_failed',reason=f'{type(error).__name__}: {error}')
        elif row['status']=='generated':entry.update(status='budget_skipped',reason='insufficient_author_budget')
        anchors.append(entry);write(out/'ANCHORS.json',{'slots':anchors,'registration_sha256':sha(args.registration)})
    for row in anchors:
        for method in METHODS:
            for budget in BUDGETS:
                record={'map':row['id'],'method':method,'budget_s':budget,'seed':103}
                if row['status']!='eligible':record.update(delivery_status='anchor_ineligible_skipped',reason=row['reason'],selected=None)
                elif remaining()<budget+3:record.update(delivery_status='phase_budget_skipped',selected=None)
                else:
                    validate_registration(args.registration)
                    command=[sys.executable,str(Path(__file__).resolve()),'worker','--registration',str(Path(args.registration).resolve()),
                             '--out',str(out.resolve()),'--case',row['id'],'--method',method]
                    record.update(collect_process(command,budget_s=budget,grace_s=2))
                comparisons.append(record);write(out/'COMPARISONS.json',comparisons)


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('register')
    for name in ('project-root','registration','resource-ledger','java-home','build-dir'):p.add_argument('--'+name,required=True)
    p=sub.add_parser('run');p.add_argument('--registration',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('materialize');p.add_argument('--registration',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('author')
    for name in ('registration','out','case'):p.add_argument('--'+name,required=True)
    p=sub.add_parser('worker')
    for name in ('registration','out','case','method'):p.add_argument('--'+name,required=True)
    p.add_argument('--deadline',type=float,required=True)
    args=parser.parse_args()
    if args.command=='register':register(args)
    elif args.command=='run':run(args)
    elif args.command=='materialize':
        registration=validate_registration(args.registration)
        r,g=setup(registration['project_root'])
        generate_four(registration,args.out,r)
    elif args.command=='author':author_worker(args)
    else:worker(args)


if __name__=='__main__':main()
