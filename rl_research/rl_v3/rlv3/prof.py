import sys,cProfile,pstats; sys.path.insert(0,'/workspace/rl_v3')
import torch; torch.set_num_threads(1)
from rlv3.search4 import solve4
from rlv3.policy import GreedyScorer
from lrphsd.problem import read_instance
ins=read_instance('/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg/8_80_1.txt')
p=GreedyScorer('/workspace/rl_v3/models/bc_s0.pt')
cProfile.run("r=solve4(ins,p,seed=1,seconds=4,M=4,G=8,lam=1.0)",'/tmp/rl.prof')
print(r['steps'],r['evals'])
pstats.Stats('/tmp/rl.prof').sort_stats('tottime').print_stats(18)
