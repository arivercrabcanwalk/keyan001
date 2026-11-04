import sys, time; sys.path.insert(0,'/workspace/rl_v3')
from rlv3.search4 import solve4, FirstM
from lrphsd.problem import read_instance
INST='/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg'
ins=read_instance(f'{INST}/7_65_1.txt')
for M,G in ((1,1),(4,4)):
    t=time.time(); r=solve4(ins,FirstM(),seed=1,seconds=3,M=M,G=G,lam=1.0,log_groups=(M>1),log_every=5)
    print(M,G,round(r['objective'],2),r['steps'],r['evals'],r['feasible'],len(r['groups']),round(time.time()-t,2))
