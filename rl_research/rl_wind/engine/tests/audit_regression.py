import sys, tempfile, json, importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
root=Path(sys.argv[1]).resolve(); sys.path.insert(0,str(root))
from carl.state import action_mask
from carl.search import Trace
spec=importlib.util.spec_from_file_location('analysis_under_test',root/'scripts/analyze.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def context(kind=2):
 return SimpleNamespace(closed_stations=[],open_stations=[0],mirror=SimpleNamespace(types=[kind]),coverage=SimpleNamespace(alt_counts=lambda t:[1]))
def trace_no_future():
 t=Trace(0);t.tick(0,100,4);t.tick(1.2,90,4)
 assert t.anytime()['0.25']==100,t.anytime()
def trace_late_init():
 t=Trace(0);t.tick(1.2,100,4)
 assert t.anytime()['0.25'] is None,t.anytime()
def mask_downgrade():
 m=action_mask(context(),intensities=(0,))
 assert m[0] and m[9],m.tolist()
def mask_no_intensity_escape():
 # Assignment is unavailable; do not resurrect intensity 1 or 2.
 m=action_mask(context(),families=(1,),intensities=(0,))
 assert not m.any(),m.tolist()
def mask_invalid_config():
 for kw in ({'families':()},{'intensities':()},{'families':(-1,)},{'intensities':(3,)}):
  try:action_mask(context(),**kw)
  except ValueError:continue
  raise AssertionError(kw)
def sample(**updates):
 d=dict(method='m1',instance='3_10_1',seed=1,status='ok',feasible=True,cost=100,seconds=6);d.update(updates);return d
def rejected(records):
 with tempfile.TemporaryDirectory() as td:
  for i,d in enumerate(records):Path(td,f'x{i}__s1.json').write_text(json.dumps(d))
  try:mod.load_runs(td)
  except ValueError:return
  raise AssertionError('accepted invalid experiment input')
def duplicate_rejected():rejected([sample(),sample(cost=90)])
def error_rejected():rejected([sample(),sample(method='m2',status='error',feasible=False)])
def budget_rejected():rejected([sample(),sample(method='m2',seconds=12)])
def nonfinite_rejected():rejected([sample(cost=float('nan'))])
def invalid_rejected():rejected([sample(status='invalid',feasible=False)])
checks=[trace_no_future,trace_late_init,mask_downgrade,mask_no_intensity_escape,mask_invalid_config,duplicate_rejected,error_rejected,budget_rejected,nonfinite_rejected,invalid_rejected]
fails=0
for fn in checks:
 try:fn();print('PASS',fn.__name__)
 except Exception as e:fails+=1;print('FAIL',fn.__name__,str(e))
print(f'RESULT {len(checks)-fails}/{len(checks)} passed')
sys.exit(bool(fails))
