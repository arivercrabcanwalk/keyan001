"""Full 500/5000 same-wind Main; reuses the fixed recorder's qualification.

Shared anchor generation is charged separately, never a 6/12-second arm.
No scientific gate is inferred from an individual valid wind witness.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import math
import re
import socket
import sys
import time


def main():
    assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
    parser=argparse.ArgumentParser()
    parser.add_argument('--instance',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--wind',type=float,nargs=2,required=True)
    parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--timeout',type=int,choices=[1800],required=True)
    parser.add_argument('--expected-input-sha256',required=True)
    parser.add_argument('--expected-source-manifest-sha256',required=True)
    args=parser.parse_args()
    started=time.monotonic()
    source=args.source_root.resolve();out=args.out.resolve();inp=args.instance.resolve();args.build=args.build.resolve()
    assert args.build.resolve()==source/'builds/wind_adapted_fixed'
    assert 0<=args.seed<2**63 and all(math.isfinite(x) for x in args.wind)
    spec=importlib.util.spec_from_file_location('fixed_fullsolve',source/'validation/fullsolve_driver.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    assert old.ROOT==source
    man=old.verify_build('wind_adapted_fixed')
    assert old.sha(args.build/'BUILD_MANIFEST.json')==args.expected_source_manifest_sha256
    assert old.sha(inp)==args.expected_input_sha256
    instance=old.problem.read_instance(inp)
    out.mkdir(parents=True,exist_ok=False)
    raw_path=out/'reference.json'
    argv=[str(old.JDK/'bin/java'),*old.VM,f'-Drepro.instance={inp}',
          f'-Drepro.seed={args.seed}','-Drepro.seconds=0',
          f'-Drepro.wind.x={args.wind[0]}',f'-Drepro.wind.y={args.wind[1]}',
          '-Drepro.guard=true',f'-Drepro.output={raw_path}',
          '-Dengineering.postMainDelayMillis=0','-cp',str(args.build/'classes'),'test1.FullSolveEntry']
    role='AUTHORIZED_F3_G3_SHARED_FULL_AUTHOR_ATTEMPT'
    old.save(out/'INTENT.json',{'argv':argv,'instance_sha256':instance.sha256,'wind':args.wind,
              'seed_i63':str(args.seed),'source_manifest_sha256':old.wind_scorer.identity(man),
              'run_role':role,'outer_iterations':500,'alns_iterations':5000,
              'repro_seconds':0,'external_main_timeout_s':1800,'repairs':0})
    proc,stdout,stderr=old.execute(argv,out,args.timeout,out/'main')
    result={'status':'REJECTED','process':proc,'main_returned':'FULL_MAIN_RETURNED=true' in stdout,
            'wind_witness_qualified':False,'scientific_G3_qualified':False,
            'raw_exists':raw_path.exists(),'final_output_issues':[]}
    if raw_path.exists():
        try:
            raw=old.read(raw_path)
            text=' '.join(map(str,raw['station_types']))+'\n'
            for si,station in enumerate(raw['routes']):
                for di,trips in enumerate(station):
                    for trip in trips:text+=' '.join(map(str,[si,di,*trip]))+'\n'
            witness=out/'witness.txt';witness.write_text(text)
            audit_argv=[str(old.JDK/'bin/java'),*old.VM,
                   f'-Drepro.wind.x={args.wind[0]}',f'-Drepro.wind.y={args.wind[1]}',
                   '-cp',str(args.build/'classes'),'test1.WitnessAuditMain',str(inp),str(witness)]
            ap,ao,_=old.execute(audit_argv,out,2,out/'source_audit')
            assert ap['exit_status']==0 and not ap['timed_out'],'SOURCE_AUDIT_FAILED'
            matches=re.findall(r'^FULL_WITNESS_AUDIT=(.+)$',ao,re.M)
            assert len(matches)==1,'SOURCE_AUDIT_MISSING'
            audit=json.loads(matches[0]);old.save(out/'SOURCE_SCORE.json',audit)
            try:
                final=old.final_main(stdout,instance);old.save(out/'FINAL_MAIN.json',final)
                result['final_output_issues']=old.compare_final(raw,final,audit)
            except (ValueError,AssertionError,KeyError) as exc:
                result['final_output_issues'].append(str(exc))
            rec={'anchor_identity':'AUTHOR_ALGORITHM_WIND_ADAPTED_FINAL_RECORD_FIXED','run_role':role,
                 'source_manifest_sha256':old.wind_scorer.identity(man),'source_hashes':man['source_hashes'],
                 'raw_output_sha256':old.sha(raw_path),'instance_sha256':instance.sha256,
                 'parameter_sha256':old.wind_scorer.parameter_identity(instance),'source_wind':args.wind,
                 'source_M_return':audit['M_return'],'source_guard_passed':audit['guard'],
                 'process':{'exit_status':proc['exit_status'],'timed_out':proc['timed_out']}}
            old.save(out/'QUALIFICATION_RECORD.json',rec)
            q=old.qualify_output(instance,raw_path.read_bytes(),rec,wind=args.wind,verified_source_manifest=man)
            if result['final_output_issues'] or not result['main_returned']:
                q.update(source_record_qualified=False,wind_witness_qualified=False,issued_cost_anchor=None,
                         status='FINAL_MAIN_OUTPUT_REJECTED')
                q['issues']+=result['final_output_issues'] or ['full_main_not_returned']
            old.save(out/'QUALIFICATION.json',q)
            result['wind_witness_qualified']=q['wind_witness_qualified']
            if q['wind_witness_qualified']:
                old.save(out/'QUALIFIED_WIND_SOLUTION.json',q['wind_solution'])
                result['status']='FULL_AUTHOR_WIND_WITNESS_QUALIFIED'
        except Exception as exc:
            result['audit_exception']={'type':type(exc).__name__,'message':str(exc)}
    if proc['timed_out']:result['status']='TIMEOUT'
    result['output_ready_including_audit_s']=time.monotonic()-started
    result['input_sha256']=instance.sha256
    old.save(out/'RUN.json',result)
    from source_closure import loaded_modules
    loaded_modules(out/'LOADED_MODULES.json')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
