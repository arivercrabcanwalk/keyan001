"""Gate-1 data: best-of-G logging with all G candidates repaired (G=M=8)."""
import sys, os, random, json, numpy as np
sys.path.insert(0,'/workspace/rl_v3')
from multiprocessing import Pool
TR='/workspace/rl_v3/instances/train'; OUT='/workspace/rl_v3/data/g1'
def run(t):
    name, lam, rsv, seed = t
    from rlv3.search4 import solve4, FirstM
    from lrphsd.problem import read_instance
    ins=read_instance(f'{TR}/{name}.txt')
    try:
        r=solve4(ins,FirstM(),seed=seed,seconds=6.0,M=8,G=8,lam=lam,reserve=rsv,log_groups=True)
    except Exception as e:
        return name, str(e)
    g=r['groups']
    def pad(x,fill):
        out=np.full((8,)+x.shape[1:],fill,dtype=np.float64); out[:len(x)]=x; return out
    g=[(pad(x[0],0.0),pad(x[1],np.nan),x[2],x[3],len(x[1])) for x in g]
    np.savez_compressed(f'{OUT}/{name}_l{lam}_r{rsv}_s{seed}.npz', X=np.stack([x[0] for x in g]).astype(np.float32) if g else np.zeros((0,8,1)),
        V=np.stack([x[1] for x in g]) if g else np.zeros((0,8)), cur=np.array([x[2] for x in g]), op=np.array([x[3] for x in g]), n=np.array([x[4] for x in g]),
        meta=np.array([lam,rsv,seed,r['init_obj']]))
    return name, len(g)
if __name__=='__main__':
    names=sorted(f[:-4] for f in os.listdir(TR))
    rng=random.Random(5); tasks=[]
    for n in names:
        for s in (1,2):
            lam=rng.choices([0,0.1,0.2,0.5,1,2],[1,1,1,2,3,2])[0]; rsv=rng.choice([0.0,0.1])
            tasks.append((n,float(lam),rsv,s))
    rng.shuffle(tasks)
    with Pool(8) as p:
        for k,(n,c) in enumerate(p.imap_unordered(run,tasks)):
            if k%40==0: print(k,n,c,flush=True)
