"""Prospectively bounded <EXPERIMENT_SERVER> joint development experiment."""
from __future__ import annotations
import os,sys,json,math,random,time,hashlib,dataclasses,subprocess,pathlib,concurrent.futures,traceback,argparse
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
import numpy as np,torch
from joint_core import *
from emergency_rolling_baseline import RollingRoutePolicy,PlannerConfig
from rl_algorithms import behavior_clone_update,masked_policy_distribution
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parent
DATA=ROOT/'data';OUT=ROOT/'results';DATA.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
GITHUB=pathlib.Path('<SERVER_PATH>')
sys.path.insert(0,str(GITHUB/'engine'))
from lrphsd.problem import read_instance
from lrphsd.evaluator import evaluate
JAVA='<SERVER_EVIDENCE_PATH>'
CLASSES='<SERVER_PATH>'
SEEDS=[103,211,307]

def write(path,x):
 p=pathlib.Path(path);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2));tmp.replace(p)
def append(path,x):
 with open(path,'a') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n')
def update_state(**kw):
 p=ROOT/'STATE.json';s=json.loads(p.read_text());s.update(kw);write(p,s)

def register():
 if (DATA/'REGISTRATION.json').exists():return json.loads((DATA/'REGISTRATION.json').read_text())
 records=[];seen=set()
 for split,count,filename in [('TRAIN',24,'train_ours.jsonl'),('DEV',8,'dev_ours.jsonl')]:
  rows=[json.loads(l) for l in (GITHUB/'plans'/filename).read_text().splitlines()][:count]
  for i,row in enumerate(rows):
   p=pathlib.Path(row['path']);sha=hashlib.sha256(p.read_bytes()).hexdigest()
   if sha in seen:raise ValueError('overlapping source map identity')
   seen.add(sha);records.append(dict(id=split.lower()+str(i),split=split,path=str(p),sha256=sha,identity='EXPOSED_DEVELOPMENT',ordinal=i))
 x=dict(schema='joint_development_registration_v1',records=records,train_seeds=SEEDS,dev_event_days=[550100,550101,550102,550103],author_seed=20261105,author_budget_s=3.,worker_max=3,formal=False,frozen_before_quality=True)
 write(DATA/'REGISTRATION.json',x);return x

def author_one(rec):
 folder=DATA/'author'/rec['id'];folder.mkdir(parents=True,exist_ok=True)
 receipt=folder/'RUN.json'
 if receipt.exists():return json.loads(receipt.read_text())
 raw=folder/'reference.json';cmd=[JAVA,'-XX:ActiveProcessorCount=1','-XX:+UseSerialGC','-Xms32m','-Xmx512m','-Drepro.instance='+rec['path'],'-Drepro.seed=20261105','-Drepro.seconds=3','-Drepro.output='+str(raw),'-Drepro.guard=true','-cp',CLASSES,'test1.Main']
 start=time.perf_counter();out=dict(record=rec,command=cmd,status='failed',eligible=False)
 try:
  proc=subprocess.run(cmd,capture_output=True,text=True,timeout=30);out.update(exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
  (folder/'stdout.log').write_text(proc.stdout);(folder/'stderr.log').write_text(proc.stderr)
  if proc.returncode==0 and raw.exists():
   sol=json.loads(raw.read_text());ins=read_instance(rec['path']);z=evaluate(ins,sol);out.update(solution=sol,static_audit=z,eligible=bool(z['feasible']),status='ok' if z['feasible'] else 'infeasible')
 except Exception as e:out.update(error=repr(e))
 out['elapsed_s']=time.perf_counter()-start;write(receipt,out);return out

def make_scenario(author,day):
 rec=author['record'];ins=read_instance(rec['path']);sol=author['solution'];owner={};seq={};dids=[];caps=[];stations=[];radii={};k=0
 for si,kind in enumerate(sol['station_types']):
  if not kind:continue
  st=ins.stations[si];stations.append(Station(si,st.x,st.y));radii[si]=ins.radius(kind)
  for di in (0,1):
   if kind==1 and di==0:continue
   dids.append(si);caps.append(ins.capacity(di));seq[k]=sol['routes'][si][di]
   for trip in seq[k]:
    for n in trip:owner[n]=si
   k+=1
 if set(owner)!=set(ins.target_ids):raise ValueError('author route coverage mismatch')
 map_seed=int(rec['sha256'][:12],16);rng=np.random.default_rng((map_seed+day)%(2**63))
 H=720.;W=[0.,180.,360.][int(rng.integers(3))];phi=float(rng.uniform(0,2*math.pi));forecast=(W*math.cos(phi),W*math.sin(phi))
 intervals=[]
 for t in range(15,721,15):
  angle=phi+float(rng.normal(0,.35));intervals.append((float(t),W*math.cos(angle),W*math.sin(angle)))
 tasks=[Task(n.id,owner[n.id],n.x,n.y,n.energy,n.service,0.,math.inf,0,False) for n in ins.targets]
 count=int(rng.poisson(len(tasks)/3));releases=np.sort(rng.uniform(0,240,count))
 for i,release in enumerate(releases):
  st=stations[int(rng.integers(len(stations)))];rad=radii[st.id]*math.sqrt(float(rng.uniform(.01,1)));angle=float(rng.uniform(0,2*math.pi));high=bool(rng.random()<.4)
  tasks.append(Task(100000+i,st.id,st.x+rad*math.cos(angle),st.y+rad*math.sin(angle),.05,2.,float(release),float(release)+(15. if high else 30.),10 if high else 1,True))
 cfg=EmergencyConfig(horizon=H,duty_limit=480.,fixed_cost=sum(ins.fixed(k) for k in sol['station_types']),max_wait=5.)
 s=Scenario(rec['id']+'_day'+str(day),tuple(stations),tuple(tasks),tuple(dids),tuple(caps),Trace(tuple(intervals)),cfg,forecast)
 return s,W,seq

class GuardedBeam:
 def __init__(self,c,w):self.c=c;self.w=w;self.base=RollingRoutePolicy(c,PlannerConfig(beam_width=32,max_nodes=128,max_depth=16,wall_seconds=.03));self.timings=[]
 def __call__(self,o):
  start=time.perf_counter();acts,f,p=feature_actions(o,self.c,self.w)
  if not acts:return Action.wait(5.) if o.own.at_station else Action.return_to_station()
  proposed=self.base(o);chosen=proposed if proposed in acts else acts[int(np.argmax(p))];self.timings.append(time.perf_counter()-start);return chosen

def collect(author,day,model,stochastic):
 s,w,seq=make_scenario(author,day);p=RoutePolicy(context(s),w,'model',model,stochastic);m,r=execute(s,p)
 if not m['replay_verified']:raise ValueError('RL independent replay: '+str(m))
 return m,r,p,s

def eval_model(model,authors,days):
 vals=[]
 for a in authors:
  for day in days:vals.append(collect(a,day,model,False)[0]['J'])
 return float(np.mean(vals))

def warm_start(model,opt,demos,seed,remaining_s=None):
 # The shared helper accepts episodes and a Random instance, not a seed keyword.
 return behavior_clone_update(model,opt,[{'transitions':demos}],epochs=2,minibatch=64,rng=random.Random(seed),deadline=remaining_s)

def optimize_group(model,opt,episodes,costs):
 # Exact predeclared K=4 leave-one-out update, extracted for integration coverage.
 if len(episodes)!=4 or len(costs)!=4:raise ValueError('registered group size is four')
 loss=torch.zeros(());entropy=torch.zeros(());scale=1000.
 for k,items in enumerate(episodes):
  if not items:continue
  baseline=sum(costs[j] for j in range(4) if j!=k)/3.;adv=(baseline-costs[k])/scale
  logs=[];ents=[]
  for item in items:
   dist,_=masked_policy_distribution(model,item);logs.append(dist.log_prob(torch.tensor(item['action'])));ents.append(dist.entropy())
  loss=loss-adv*torch.stack(logs).sum()/4.;entropy=entropy+torch.stack(ents).mean()/4.
 opt.zero_grad();(loss-.005*entropy).backward();torch.nn.utils.clip_grad_norm_(model.parameters(),.5);opt.step()
 return loss

def train_one(seed,registration):
 torch.set_num_threads(1);torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
 dst=OUT/'models'/str(seed);dst.mkdir(parents=True,exist_ok=True);statusfile=dst/'STATUS.json'
 authors=[json.loads((DATA/'author'/r['id']/'RUN.json').read_text()) for r in registration['records'] if r['split']=='TRAIN'];authors=[a for a in authors if a['eligible']]
 dev=[json.loads((DATA/'author'/r['id']/'RUN.json').read_text()) for r in registration['records'] if r['split']=='DEV'];dev=[a for a in dev if a['eligible']]
 if not authors or not dev:raise ValueError('no eligible author maps')
 begin=time.perf_counter();model=ResidualActor();torch.save(model.state_dict(),dst/'initial.pt');opt=torch.optim.Adam(model.parameters(),lr=1e-3)
 demos=[]
 for i,a in enumerate(authors[:8]):
  s,w,_=make_scenario(a,440000+i);teacher=GuardedBeam(context(s),w);p=RoutePolicy(context(s),w,'prior',teacher=teacher);m,r=execute(s,p)
  if not m['replay_verified']:raise ValueError('BC teacher replay')
  demos.extend(p.demonstrations)
 demos=demos[:2048]
 # Supervised warm start is a control, not RL credit.
 write(dst/'BC_DEMONSTRATIONS.json',demos)
 bc_stats=warm_start(model,opt,demos,seed,max(.001,900-(time.perf_counter()-begin))) if demos else {'updates':0}
 write(dst/'BC_UPDATES.json',bc_stats)
 torch.save(model.state_dict(),dst/'bc.pt');write(dst/'BC.json',dict(demonstrations=len(demos),elapsed_s=time.perf_counter()-begin,optimizer_stats=bc_stats))
 best=float('inf');best_iteration=None
 for update in range(64):
  if time.perf_counter()-begin>900:break
  a=authors[update%len(authors)];day=450000+seed*100+update;episodes=[];costs=[]
  for sample in range(4):
   m,r,p,s=collect(a,day,model,True);episodes.append(p.transitions);costs.append(m['J'])
   append(dst/'EPISODES.jsonl',dict(update=update+1,sample=sample,map=a['record']['id'],day=day,metrics=m,snapshot=snapshot(s),result=r))
  # Leave-one-out baseline uses independent trajectories on the SAME exogenous day.
  loss=optimize_group(model,opt,episodes,costs)
  log=dict(update=update+1,seed=seed,J_mean=float(np.mean(costs)),J_std=float(np.std(costs)),loss=float(loss.detach()),elapsed_s=time.perf_counter()-begin,episodes=4)
  if update in (0,15,31,47,63):
   value=eval_model(model,dev[:2],[550000]);log['checkpoint_dev_J']=value
   if value<best:best=value;best_iteration=update+1;torch.save(model.state_dict(),dst/'best.pt')
  append(dst/'TRAIN.jsonl',log);write(statusfile,dict(status='TRAINING',**log));print('TRAIN',seed,update+1,round(log['J_mean'],3),flush=True)
 torch.save(model.state_dict(),dst/'last.pt')
 if not (dst/'best.pt').exists():torch.save(model.state_dict(),dst/'best.pt')
 write(statusfile,dict(status='DONE',updates=update+1,seed=seed,elapsed_s=time.perf_counter()-begin,best_iteration=best_iteration,best_dev_J=best))
 return json.loads(statusfile.read_text())

def controls(reg):
 rows=[]
 existing=set()
 if (OUT/'CONTROLS.jsonl').exists():
  for line in (OUT/'CONTROLS.jsonl').read_text().splitlines():
   r=json.loads(line);existing.add((r['map'],r['day'],r['method']))
 for rec in reg['records']:
  if rec['split']!='DEV':continue
  a=json.loads((DATA/'author'/rec['id']/'RUN.json').read_text())
  if not a['eligible']:continue
  for day in reg['dev_event_days']:
   s,w,seq=make_scenario(a,day);write(DATA/(s.scenario_id+'.json'),snapshot(s))
   for name in ['nearest','deadline','prior','mix0.5','mix1','mix2','beam','author_dispatch','author_insert']:
    if (rec['id'],day,name) in existing:continue
    if name=='beam':p=GuardedBeam(context(s),w)
    elif name.startswith('author'):p=AuthorRoutePolicy(context(s),w,seq,name)
    else:p=RoutePolicy(context(s),w,name)
    m,r=execute(s,p);row=dict(map=rec['id'],day=day,method=name,**m);append(OUT/'CONTROLS.jsonl',row);append(OUT/'CONTROL_TRACES.jsonl',dict(map=rec['id'],day=day,method=name,result=r));rows.append(row)
    if not m['replay_verified']:raise ValueError('control independent replay '+str(row))
  print('CONTROLS_DONE',rec['id'],flush=True)
 return rows

def evaluate_models(reg):
 for seed in SEEDS:
  for stage in ['initial','bc','best','last']:
   model=ResidualActor();model.load_state_dict(torch.load(OUT/'models'/str(seed)/(stage+'.pt'),weights_only=True));model.eval()
   for rec in reg['records']:
    if rec['split']!='DEV':continue
    a=json.loads((DATA/'author'/rec['id']/'RUN.json').read_text())
    if not a['eligible']:continue
    for day in reg['dev_event_days']:
     m,r,p,s=collect(a,day,model,False);append(OUT/'MODELS.jsonl',dict(map=rec['id'],day=day,method='RL' if stage in ('best','last') else stage,stage=stage,seed=seed,**m));append(OUT/'MODEL_TRACES.jsonl',dict(map=rec['id'],day=day,stage=stage,seed=seed,result=r))
   print('EVAL_DONE',seed,stage,flush=True)

def summarize():
 rows=[]
 for fn in ['CONTROLS.jsonl','MODELS.jsonl']:
  if (OUT/fn).exists():rows += [json.loads(l) for l in (OUT/fn).read_text().splitlines()]
 groups={}
 for row in rows:
  name=row['method'] if 'stage' not in row else row['method']+'_'+row['stage'];groups.setdefault(name,[]).append(row)
 summary={}
 for name,rs in groups.items():
  summary[name]=dict(n=len(rs),J=float(np.mean([r['J'] for r in rs])),on_time=float(np.mean([r['emergency_on_time'] for r in rs])),high_on_time=float(np.mean([r['high_on_time'] for r in rs])),response=float(np.mean([r['response'] for r in rs])),complete=sum(r['complete_return'] for r in rs),replay_verified=sum(r['replay_verified'] for r in rs),invalid_actions=sum(r['invalid_actions'] for r in rs),terminal_failures=sum(r['terminal_failure_count'] for r in rs),cost=float(np.mean([r['cost'] for r in rs])))
 write(OUT/'SUMMARY.json',summary);print(json.dumps(summary,indent=2),flush=True)
 return summary,len(rows)

def acquire_driver_lock(path=None):
 import fcntl
 handle=open(path or ROOT/'DRIVER_EXCLUSIVE.lock','a+')
 try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:handle.close();return None
 handle.seek(0);handle.truncate();handle.write(str(os.getpid()));handle.flush()
 return handle

def main():
 torch.set_num_threads(1);reg=register();update_state(status='AUTHOR_RUNNING',registration=str(DATA/'REGISTRATION.json'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:author=list(pool.map(author_one,reg['records']))
 write(DATA/'AUTHOR_SUMMARY.json',dict(total=len(author),eligible=sum(a['eligible'] for a in author),failed=[a['record']['id'] for a in author if not a['eligible']]))
 update_state(status='CONTROLS_RUNNING',new_author_attempts=len(author));controls(reg)
 update_state(status='TRAINING_RUNNING',new_training_runs_started=3)
 # Fresh Python processes isolate Torch RNG/thread state for the three seeds.
 procs=[]
 for seed in SEEDS:
  log=open(OUT/('train_'+str(seed)+'.log'),'w');p=subprocess.Popen([sys.executable,__file__,'--seed',str(seed)],stdout=log,stderr=subprocess.STDOUT);procs.append((seed,p,log))
 exits={}
 for seed,p,log in procs:exits[str(seed)]=p.wait();log.close()
 write(OUT/'TRAIN_EXITS.json',exits)
 if any(v!=0 for v in exits.values()):update_state(status='TRAINING_FAILED',train_exits=exits);return 1
 update_state(status='MODEL_EVALUATION_RUNNING',new_training_runs=3);evaluate_models(reg);summary,count=summarize()
 update_state(status='DEVELOPMENT_COMPLETE_NOT_FORMAL',new_training_runs=3,new_quality_rows=count,publication_ready=False,summary=str(OUT/'SUMMARY.json'))
 write(ROOT/'DONE.json',dict(status='DEVELOPMENT_COMPLETE',formal=False,publication_ready=False,exit_status=0));return 0

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int);args=parser.parse_args()
 if not args.seed:
  driver_lock=acquire_driver_lock()
  if driver_lock is None:print('DUPLICATE_DRIVER_REJECTED_EXIT73',flush=True);sys.exit(73)
 try:
  if args.seed:train_one(args.seed,json.loads((DATA/'REGISTRATION.json').read_text()));sys.exit(0)
  import fcntl
  execution_lock=open(ROOT/'EXECUTION.lock','a+')
  try:fcntl.flock(execution_lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('ALREADY_RUNNING_NO_DUPLICATE',flush=True);sys.exit(73)
  execution_lock.seek(0);execution_lock.truncate();execution_lock.write(str(os.getpid()));execution_lock.flush()
  sys.exit(main())
 except Exception as e:
  traceback.print_exc();write(ROOT/('ERROR_'+str(args.seed)+'.json'),dict(error=repr(e),traceback=traceback.format_exc()));sys.exit(1)
