import argparse,json,time,resource,hashlib,subprocess,sys,platform
from pathlib import Path
from .problem import read_instance
from .evaluator import evaluate
from .greedy import build
from .tsalns import solve
from .exact import solve_exact

def main():
    a=argparse.ArgumentParser();a.add_argument('--instance',required=True);a.add_argument('--algorithm',choices=['greedy','tsalns','exact'],required=True);a.add_argument('--seed',type=int,default=0);a.add_argument('--seconds',type=float,default=2.0);a.add_argument('--output',required=True);a.add_argument('--config');args=a.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(Path(args.config).read_text()) if args.config else {};ins=read_instance(args.instance)
    source_hash=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in sorted((root/'lrphsd').glob('*.py')))).hexdigest()
    try:revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:revision=None
    started=time.perf_counter();metadata={}
    try:
        if args.algorithm=='greedy':solution=build(ins);metadata={'algorithm':'independent_official_profile_greedy','seed':args.seed}
        elif args.algorithm=='exact':solution,metadata=solve_exact(ins)
        else:solution,metadata=solve(ins,args.seed,args.seconds,config=cfg.get('algorithm',cfg))
        solver_seconds=time.perf_counter()-started;check_start=time.perf_counter();audit=evaluate(ins,solution);audit_seconds=time.perf_counter()-check_start
        if 'objective' in metadata and abs(metadata['objective']-audit['cost'])>1e-7:raise AssertionError('independent objective mismatch')
        result={'status':'ok' if audit['feasible'] else 'invalid','instance':ins.name,'instance_sha256':ins.sha256,'algorithm_source_sha256':source_hash,'git_revision':revision,'python':platform.python_version(),'seed':args.seed,'objective':audit['cost'],'feasible':audit['feasible'],'solver_seconds':solver_seconds,'independent_evaluation_seconds':audit_seconds,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'metadata':metadata,'audit':audit}
        (out/'solution.json').write_text(json.dumps(solution,indent=2)+'\n')
    except Exception as e:
        result={'status':'failed','instance':ins.name,'instance_sha256':ins.sha256,'algorithm_source_sha256':source_hash,'git_revision':revision,'seed':args.seed,'feasible':False,'objective':None,'error_type':type(e).__name__,'error':str(e),'solver_seconds':time.perf_counter()-started}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');(out/'config.json').write_text(json.dumps({'argv':sys.argv,'config':cfg},indent=2)+'\n')
    print(json.dumps({k:result.get(k) for k in ('status','instance','objective','feasible','solver_seconds')},sort_keys=True),flush=True)
    return 0 if result['status']=='ok' else 2
if __name__=='__main__':raise SystemExit(main())
