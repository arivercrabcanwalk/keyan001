"""Calibrate work units: time per step (M=1) vs time per extra eval."""
import sys; sys.path.insert(0,'/workspace/rl_ppo')
from ppo.common import load
from ppo import dac
import time, json
res=[]
for name in ['5_35_1','7_65_3','10_110_2']:
    ins=load(name)
    for mi in (0,3):
        for lam in (0,1):
            r=dac.solve_dac(ins, dac.Static((1,mi,0,1,0)), 3000, seed=1, lam=lam, S=1)
            res.append(dict(name=name,M=dac.M_LEVELS[mi],lam=lam,steps=r['steps'],evals=r['evals'],wall=r['wall']))
            print(res[-1],flush=True)
json.dump(res,open('/workspace/rl_ppo/results/calib.json','w'))
