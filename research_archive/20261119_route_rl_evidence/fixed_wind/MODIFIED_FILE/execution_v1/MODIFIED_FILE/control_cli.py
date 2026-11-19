"""Full control-process clock starts in the guard before Python startup/imports."""
import os,time
STARTED=float(os.environ['CONTROL_PROCESS_STARTED'])
from pathlib import Path
import argparse,json,socket,sys
assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(BASE/'frozen'),str(BASE)]
os.environ['PYTHONPATH']=str(BASE/'frozen')+os.pathsep+str(BASE)
from route_delivery import run
p=argparse.ArgumentParser()
p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--budget',type=int,choices=[6,12],required=True)
p.add_argument('--method',choices=['strong','common_h'],required=True)
p.add_argument('--seed',type=int,required=True)
a=p.parse_args()
def command(result):return [sys.executable,str(BASE/'common_h_worker.py'),'--bundle',str(a.bundle.resolve()),'--result',str(result),'--budget',str(a.budget),'--seed',str(a.seed)]
d=run(a.bundle,a.out,budget_s=a.budget,method=a.method,seed=a.seed,
      command_factory=command if a.method=='common_h' else None,started_at=STARTED)
from source_closure import loaded_modules
loaded_modules(a.out/'LOADED_MODULES.json')
print(json.dumps({'delivery_status':d['delivery_status'],'admission_wall_s':d['admission_wall_s'],'budget_s':a.budget},sort_keys=True),flush=True)
