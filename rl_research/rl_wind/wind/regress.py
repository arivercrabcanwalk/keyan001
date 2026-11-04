"""Regression: wind = 0 -> effective distances == geometric; solver + simulate reproduce the original evaluator."""
import wind, math, numpy as np
from lrphsd.problem import read_instance
from lrphsd.evaluator import evaluate
from rlv3.search4 import solve4, FirstM
from wind.model import make_planning_instance, simulate, effective_dist
LIU = '/workspace/rl_wind/engine/external/LRPHSD/data/Instances_Alg'
ctx0 = dict(W=0.0, theta=0.0, sigma=0.0, gust=0.0, gmax=0.0, tau=60.0)
for name in ['5_35_1', '8_80_3']:
    ins = read_instance(f'{LIU}/{name}.txt')
    q = make_planning_instance(ins, ctx0, 0.0)
    md = max(abs(q.dist[k] - ins.gdist[k]) for k in ins.gdist)
    r0 = solve4(read_instance(f'{LIU}/{name}.txt'), FirstM(), seed=1, seconds=1.0, M=1, G=1)
    r1 = solve4(q, FirstM(), seed=1, seconds=1.0, M=1, G=1, max_steps=r0['steps'])
    ev = evaluate(ins, r1['solution']); sim = simulate(ins, r1['solution'], ctx0, S=4)
    print(name, 'max|deff-d|', md, 'obj nowind/wind0', round(r0['objective'], 4), round(r1['objective'], 4),
          'eval', round(ev['cost'], 4), 'sim cost', round(float(sim['cost'][0]), 4), 'fails', sim['failed'].sum())
# wind on: asymmetry check
ctx = dict(W=6.0, theta=0.0, sigma=0.0, gust=0.0, gmax=0, tau=60.0)
E = effective_dist(ins, 6 * 60, 0)
a, b = ins.stations[0].id, ins.targets[0].id
print('asym', ins.gdist[a, b], E[a, b], E[b, a])
q = make_planning_instance(ins, ctx, 0.0)
r = solve4(q, FirstM(), seed=1, seconds=1.0, M=1, G=1)
sim = simulate(ins, r['solution'], ctx, S=4)
print('wind6 plan obj', round(r['objective'], 3), 'feasible(forecast eval)', r['feasible'], 'sim cost (no deviation)', round(float(sim['cost'][0]), 3), 'fails', sim['failed'].sum())
