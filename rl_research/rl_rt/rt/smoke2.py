import sys, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt')
torch.set_num_threads(int(sys.argv[1]))
from rt.inst import gen
from rt.env import Batch
from rt.model import Policy, rollout
rng = np.random.default_rng(0); torch.manual_seed(0); pol = Policy()
insts = [gen(110, 10, rng) for _ in range(8)]
bt = Batch([a for a, b in insts], [b for a, b in insts], np.ones(8), np.full(8, 0.1), N=16)
import cProfile, pstats
cProfile.run('r=rollout(pol, bt)', '/tmp/rt.prof')
pstats.Stats('/tmp/rt.prof').sort_stats('tottime').print_stats(12)
