import sys, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine')
torch.set_num_threads(1)
from lrphsd.problem import read_instance
from rt.inst import from_lrphsd
from rt.model import Policy
from rt.infer import solve
pol = Policy(); pol.eval()
for nm in ['d5_35_1', 'd10_110_1']:
    tg, st, *_ = from_lrphsd(read_instance(f'/workspace/rl_rt/instances/dev/{nm}.txt'))
    for mode in ['greedy', 'sample:16', 'aug8', 'aug8s:16']:
        solve(pol, tg, st, 0.0, 0.0, mode)
        t = time.perf_counter(); r = solve(pol, tg, st, 0.0, 0.0, mode); print(nm, mode, round((time.perf_counter() - t) * 1000, 1), 'ms', round(r[0], 1))
