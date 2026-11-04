import sys, numpy as np, torch
sys.path.insert(0, '/workspace/rl_rt'); sys.path.insert(0, '/workspace/rl_v3/engine')
torch.set_num_threads(2)
from lrphsd.problem import read_instance
from lrphsd.evaluator import evaluate
from rt.inst import from_lrphsd
from rt.env import Batch
from rt.model import Policy, rollout
from rt.solution import decode, to_solution, makespan
pol = Policy(); torch.manual_seed(1)
for name in ['5_35_1', '10_110_3', '8_80_2']:
    ins = read_instance(f'/workspace/rl_v3/engine/external/LRPHSD/data/Instances_Alg/{name}.txt')
    tg, st, tid, sid = from_lrphsd(ins)
    for rsv in (0.0, 0.1):
        bt = Batch([tg], [st], np.array([0.5]), np.array([rsv]), N=8)
        F, c, mk, lp, s, acts = rollout(pol, bt, record=True)
        bad = 0; md = 0
        for r in range(8):
            ty, ro = decode(acts[r].tolist(), bt.n, bt.ns, tid)
            sol = to_solution(ins, ty, ro)
            if rsv:
                from dataclasses import replace
                from lrphsd.problem import Instance
                p = ins.params; ins2 = Instance(ins.name, ins.targets, ins.stations, ins.sha256, replace(p, small_battery=p.small_battery/1.1, large_battery=p.large_battery/1.1))
            else: ins2 = ins
            ev, m = makespan(ins2, sol)
            if not ev['feasible']: bad += 1; print(ev['issues'][:3])
            md = max(md, abs(ev['cost'] - float(c[r])), abs(m - float(mk[r])))
        print(name, rsv, 'infeasible', bad, 'max |cost/mk diff|', round(md, 6))
