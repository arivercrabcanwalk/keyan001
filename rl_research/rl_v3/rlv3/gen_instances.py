"""Liu-style instance generator for TRAINING ONLY (test = Liu's 50 official instances).
Targets and stations uniform in [0,15000]^2; service energy 0.2, service time 10 (as in all 120 official files)."""
import random, sys, os, shutil
sys.path.insert(0,'/workspace/rl_v3/engine')
def reserve_ins(ins, r=0.1):
    from dataclasses import replace
    from lrphsd.problem import Instance
    p=ins.params
    return Instance(ins.name, ins.targets, ins.stations, ins.sha256, replace(p, small_battery=p.small_battery/(1+r), large_battery=p.large_battery/(1+r)))
OUT='/workspace/rl_v3/instances/train'
OFF='/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg'
def write(path, nt, ns, rng):
    rows=['CUST_NO          XCOORD           YCOORD           SERVICE_ENERGY   SERVICE_TIME']
    st=[(rng.uniform(0,15000),rng.uniform(0,15000)) for _ in range(ns)]
    tg=[]
    while len(tg)<nt:
        x,y=rng.uniform(0,15000),rng.uniform(0,15000)
        if min(((x-a)**2+(y-b)**2)**0.5 for a,b in st)<=4750: tg.append((x,y))
    k=1
    for x,y in tg:
        rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.2000\t10.0000'); k+=1
    for x,y in st:
        rows.append(f'{k}\t{x:.4f}\t{y:.4f}\t0.0000\t0.0000'); k+=1
    open(path,'w').write('\n'.join(rows)+'\n')
if __name__=='__main__':
    os.makedirs(OUT,exist_ok=True)
    sizes=[(5,35),(6,50),(7,65),(8,80),(10,110)]
    for ns,nt in sizes:
        for i in range(1,25):
            rng=random.Random(900000+ns*1000+i)
            while True:
                p=f'{OUT}/g{ns}_{nt}_{i}.txt'; write(p, nt, ns, rng)
                try:
                    from lrphsd.problem import read_instance
                    from lrphsd.greedy import build
                    from lrphsd.evaluator import evaluate
                    from lrphsd import fidelity_ops_v5 as ops
                    ins=read_instance(p); ops.prepare(ins); assert evaluate(ins, build(ins))['feasible']
                    ins2=reserve_ins(ins); ops.prepare(ins2); assert evaluate(ins2, build(ins2))['feasible']
                    break
                except Exception as e:
                    print('regen',p,str(e)[:60])
    # official non-test size groups are also legitimate training data
    for f in os.listdir(OFF):
        g='_'.join(f.split('_')[:2])
        if g in ('3_10','3_15','3_20','4_20','4_25','4_30','9_95'):
            shutil.copy(f'{OFF}/{f}', f'{OUT}/o{f}')
    print(len(os.listdir(OUT)))
