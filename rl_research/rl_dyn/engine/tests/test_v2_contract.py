import sys,random,tempfile
from pathlib import Path
from dataclasses import replace
import numpy as np
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r))
from lrphsd.problem import read_instance
from lrphsd.greedy import build
from lrphsd import fidelity_ops_v5 as ops
from carl.kernel import CAEngine
from carl.core import Mirror,Coverage
from carl.neighborhood import Context,_joint_downgrade
path=r/'external/LRPHSD/data/Instances_Alg/5_35_1.txt'
def state_contract():
 ins=read_instance(path);ins.params=replace(ins.params,small_station_cost=123,large_station_cost=456);ops.prepare(ins)
 eng=CAEngine(ins)
 try:
  sol=build(ins);eng.load(0,sol);ctx=Context(ins,eng,Mirror(ins,sol),Coverage(ins),random.Random(1))
  for si in ctx.open_stations:
   st=eng.station_stats(0,si);load=max(st[2:4])/ins.duration(sol['station_types'][si]);assert abs(ctx.load[si]-load)<1e-12;assert abs(ctx.slack[si]-(1-load))<1e-12;assert ctx.fixed[si]==ins.fixed(sol['station_types'][si])
 finally:eng.free()
def cache_contract():
 from lrphsd.tsalns_v6 import get_engine,reset_engine
 a=read_instance(path);b=read_instance(path,replace(a.params,time_cost=1));ops.prepare(a);sol=build(a)
 try:
  e=get_engine(a);e.load(0,sol);v=e.cost(0);f=get_engine(b);f.load(0,sol);assert abs(f.cost(0)-2*v)<1e-9
 finally:reset_engine()
def checkpoint_contract():
 import torch
 from carl.state import N_FEATURES
 from carl.actions import N_ACTIONS
 from carl.ppo import PolicyNet,save_model,load_model
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'m.pt';m=PolicyNet();torch.save(m.state_dict(),p)
  try:load_model(p)
  except ValueError:pass
  else:raise AssertionError('legacy accepted')
  save_model(m,p);load_model(p)
def singleton_ppo():
 import torch
 from carl.state import N_FEATURES
 from carl.actions import N_ACTIONS
 from carl.ppo import PolicyNet,ppo_update
 m=PolicyNet();o=torch.optim.Adam(m.parameters(),lr=.001);n=2
 batch=dict(feat=np.zeros((n,N_FEATURES),np.float32),mask=np.ones((n,N_ACTIONS),bool),action=np.zeros(n,np.int64),logp=np.full(n,-np.log(N_ACTIONS),np.float32),ret=np.ones(n,np.float32),adv=np.array([0.,1.],np.float32))
 stats=ppo_update(m,o,batch,epochs=1,minibatch=1);assert all(np.isfinite(v) for v in stats.values());assert all(torch.isfinite(p).all() for p in m.parameters())
f=0
for fn in (state_contract,cache_contract,checkpoint_contract,singleton_ppo):
 try:fn();print('PASS',fn.__name__)
 except Exception as e:f+=1;print('FAIL',fn.__name__,type(e).__name__,str(e)[:120])
print('RESULT',4-f,'/4');sys.exit(bool(f))
