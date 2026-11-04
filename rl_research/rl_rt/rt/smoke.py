import sys, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt')
from rt.inst import gen
from rt.env import Batch
from rt.model import Policy, rollout
rng = np.random.default_rng(0)
torch.manual_seed(0)
torch.set_num_threads(2); pol = Policy()
for (ns, n) in [(5, 35), (10, 110)]:
    insts = [gen(n, ns, rng) for _ in range(8)]
    bt = Batch([a for a, b in insts], [b for a, b in insts], np.ones(8), np.full(8, 0.1), N=16)
    t = time.time(); F, c, mk, lp, s, acts = rollout(pol, bt, record=True)
    print(ns, n, 'time %.2fs' % (time.time() - t), 'F %.1f cost %.1f mk %.1f fail %d' % (F.mean(), c.mean(), mk.mean(), s.fail.sum()), acts.shape)
