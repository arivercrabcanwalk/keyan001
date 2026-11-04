"""Test-set benchmark on Liu's 50 instances (5_35..10_110). Methods:
  norl_m1 : cooled NoRL, single candidate (G=M=1)
  norl_m4 : cooled NoRL, best-of-4 (G=M=4)
  rl:<ckpt>[:G] : learned proposer, G heuristic candidates, policy picks top-4 to repair
Usage: bench.py METHOD OUTFILE LAMS RESERVES SEEDS SECONDS [WORKERS]"""
import sys, os, json, random
sys.path.insert(0,'/workspace/rl_v3')
from multiprocessing import Pool
INST='/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg'
TEST=[f'{s}_{i}' for s in ['5_35','6_50','7_65','8_80','10_110'] for i in range(1,11)]
DEV=[f'g{s}_{i}' for s in ['5_35','6_50','7_65','8_80','10_110'] for i in (19,20,21,22)]
TRDIR='/workspace/rl_v3/instances/train'
def make(method):
    """norl_m1 | norl_m4 | norl:M | rl:CKPT:G[:M[:opt]]"""
    from rlv3.search4 import FirstM
    if method in ('norl_m1','norl_m4'): return FirstM(), (1,1) if method=='norl_m1' else (4,4)
    if method.startswith('norl:'):
        M=int(method.split(':')[1]); return FirstM(), (M,M)
    if method.startswith('rl:'):
        parts=method.split(':'); from rlv3.policy import GreedyScorer
        G=int(parts[2]) if len(parts)>2 else 8; M=int(parts[3]) if len(parts)>3 else 4
        kw={}
        if len(parts)>4 and parts[4]=='nocond': kw['cond']=False
        if len(parts)>4 and parts[4]=='nofilm': kw['film']=False
        return GreedyScorer(parts[1],**kw), (M,G)
    raise ValueError(method)
def run(t):
    method,inst,lam,rsv,seed,sec=t
    import torch; torch.set_num_threads(1)
    from rlv3.search4 import solve4
    from lrphsd.problem import read_instance
    if method.startswith('tp:'):
        parts=method.split(':'); from rlv3.tpolicy import TargetPolicy, FastTargetPolicy
        params={k:__import__('numpy').array(v) for k,v in json.load(open(parts[1])).items()}
        opts=parts[2:]
        Cls=TargetPolicy if 'slow' in opts else FastTargetPolicy
        prop=Cls(params, lam=lam, reserve=rsv, nocond=('nocond' in opts))
        M=G=int([o[1:] for o in opts if o.startswith('M')][0]) if any(o.startswith('M') for o in opts) else 4
    else:
        prop,(M,G)=make(method)
    path=f'{INST}/{inst}.txt' if not inst.startswith(('g','o')) else f'{TRDIR}/{inst}.txt'
    r=solve4(read_instance(path),prop,seed=seed,seconds=sec,M=M,G=G,lam=lam,reserve=rsv)
    r.pop('groups'); r.pop('solution') if os.environ.get('SET')=='dev' else None; r.update(method=method,inst=inst,lam=lam,reserve=rsv,seed=seed,seconds=sec)
    return r
if __name__=='__main__':
    method,out=sys.argv[1],sys.argv[2]; lams=[float(x) for x in sys.argv[3].split(',')]
    rsvs=[float(x) for x in sys.argv[4].split(',')]; seeds=[int(x) for x in sys.argv[5].split(',')]
    sec=float(sys.argv[6]); W=int(sys.argv[7]) if len(sys.argv)>7 else 8
    SET=DEV if os.environ.get('SET')=='dev' else TEST
    tasks=[(method,i,l,r,s,sec) for i in SET for l in lams for r in rsvs for s in seeds]
    done=set()
    if os.path.exists(out):
        for line in open(out):
            j=json.loads(line); done.add((j['inst'],j['lam'],j['reserve'],j['seed']))
    tasks=[t for t in tasks if (t[1],t[2],t[3],t[4]) not in done]
    random.Random(0).shuffle(tasks); print(len(tasks),'tasks',flush=True)
    with Pool(W, maxtasksperchild=20) as p, open(out,'a') as f:
        for k,r in enumerate(p.imap_unordered(run,tasks)):
            f.write(json.dumps(r)+'\n'); f.flush()
            if k%100==0: print(k,flush=True)
