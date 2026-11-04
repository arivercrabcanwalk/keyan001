import sys, time, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine')
torch.set_num_threads(1)
from lrphsd.problem import read_instance
from rt.inst import from_lrphsd
from rt.model import Policy
from rt.infer import solve
from rt.fast import Fast
from rt.solution import decode as dec, to_solution, makespan
pol = Policy(); 
if len(sys.argv) > 1:
    from rt.model import load_policy; pol = load_policy(sys.argv[1])
pol.eval(); fs = Fast(pol)
for nm in ['d5_35_1', 'd8_80_2', 'd10_110_1']:
    ins = read_instance(f'/workspace/rl_rt/instances/dev/{nm}.txt')
    tg, st, tid, sid = from_lrphsd(ins)
    for kap, rsv in [(0.0, 0.0), (2.0, 0.1)]:
        r1 = solve(pol, tg, st, kap, rsv, 'greedy')
        fs.solve(tg, st, kap, rsv, 'greedy')
        t = time.perf_counter(); r2 = fs.solve(tg, st, kap, rsv, 'greedy'); dt = (time.perf_counter() - t) * 1000
        a1 = [x for x in r1[3] if x >= 0]; a2 = [x for x in r2[3] if x >= 0]
        t = time.perf_counter(); r3 = fs.solve(tg, st, kap, rsv, 'sample:64'); dt3 = (time.perf_counter() - t) * 1000
        ty, ro = dec(r2[3], len(tg), len(st), tid); ev, mk = makespan(ins, to_solution(ins, ty, ro))
        print(nm, kap, rsv, 'same_actions', a1 == a2, 'F torch/fast', round(r1[0], 2), round(r2[0], 2), 'greedy ms', round(dt, 2),
              'sample64 ms', round(dt3, 1), 'F', round(r3[0], 1), 'eval feas', ev['feasible'], round(ev['cost'] - r2[1], 4))
