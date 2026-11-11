"""Joint weather/emergency development controls. Physical actions only."""
from __future__ import annotations
import dataclasses,math,random,time
import numpy as np
import torch
from torch import nn
from emergency_scenario import Action,Task,Station,Scenario,EmergencyConfig,EmergencySimulator
from shared_replay_v2 import Trace
from emergency_route_bridge import PublicContext,encode,GLOBAL_DIM,CANDIDATE_DIM
from emergency_independent_replay import verify_result
from weather_policy import WeatherPointerActorCritic

EXTRA=('conservative_feasible','earliest_completion_slack','emergency','priority','extra_distance','home_energy_margin','relative_finish','miss_penalty','in_progress_tasks','other_drone_nearby')

def snapshot(s):
 return dict(scenario_id=s.scenario_id,forecast=s.forecast,config=dataclasses.asdict(s.config),stations=[dataclasses.asdict(t) for t in s.stations],tasks=[dataclasses.asdict(t) for t in s.tasks],drone_stations=s.drone_stations,capacities=s.capacities,intervals=s.trace.intervals)

def context(s):
 return PublicContext(tuple((t.id,t.x,t.y) for t in s.stations),s.drone_stations,s.capacities,s.config.horizon,s.config.speed,s.config.duty_limit,s.config.max_wait)

def feature_actions(o,c,wind_bound):
 enc=encode(o,c);d=o.own;home=c.station(d.station_id);cap=c.capacities[d.id]
 v=c.speed-wind_bound
 if v<=0:raise ValueError('registered wind bound must be below airspeed')
 ts={t.id:t for t in o.visible_tasks};acts=[];rows=[];prior=[]
 for a,row in zip(enc.actions,enc.candidates):
  if a.kind=='TARGET':
   t=ts[a.target_id];out=math.hypot(t.x-d.x,t.y-d.y);back=math.hypot(t.x-home[1],t.y-home[2]);home_d=math.hypot(d.x-home[1],d.y-home[2])
   dt=out/v+t.service+back/v;energy=(out+back)/v*.018+t.energy
   if d.trip_energy+energy>cap-1e-8 or d.duty+dt>c.duty_limit-1e-8 or o.now+dt>c.horizon-1e-8:continue
   # Completion lower bound uses current observed wind only (not future trace).
   from reference_environment import ground_speed
   vg=ground_speed(t.x-d.x,t.y-d.y,*o.wind_now,c.speed) if out else c.speed
   finish=o.now+out/vg+t.service;slack=t.deadline-finish if math.isfinite(t.deadline) else c.horizon
   score=(30. if t.priority>=10 else 10.) if t.emergency else 0.
   # Fixed rule is an explicit nonRL prior, shared by initial/BC/RL controls.
   base=score*max(0.,1.-max(slack,0.)/30.)-.03*(out+back-home_d)/100.-.01*t.service
   extra=(1.,max(-2.,min(2.,slack/30.)),float(t.emergency),t.priority/10.,(out+back-home_d)/10000.,(cap-d.trip_energy-energy)/cap,(finish-o.now)/30.,score/30.,sum(len(m.trip_task_ids) for m in o.fleet),sum(m.at_station and m.station_id==d.station_id for m in o.fleet)-int(d.at_station))
  else:
   back=math.hypot(d.x-home[1],d.y-home[2]);dt=back/v
   if d.trip_energy+dt*.018>cap+1e-8 or d.duty+dt>c.duty_limit+1e-8:continue
   base=-1.;extra=(1.,0.,0.,0.,0.,(cap-d.trip_energy-dt*.018)/cap,dt/30.,0.,sum(len(m.trip_task_ids) for m in o.fleet),0.)
  acts.append(a);rows.append((*row,*extra,base));prior.append(base)
 return acts,dict(global_features=enc.global_features,candidates=rows,mask=[True]*len(rows)),prior

class ResidualActor(nn.Module):
 def __init__(self):
  super().__init__();self.net=WeatherPointerActorCritic(GLOBAL_DIM,CANDIDATE_DIM+len(EXTRA),64)
  # Zero residual head makes initial policy exactly the declared fixed prior.
  nn.init.zeros_(self.net.query.weight);nn.init.zeros_(self.net.score_bias.weight);nn.init.zeros_(self.net.score_bias.bias)
 def forward(self,g,c,mask):
  c=torch.as_tensor(c,dtype=torch.float32);logits,value=self.net(g,c[:,:-1],mask)
  return logits+c[:,-1],value

def model_input(f):return {'global':f['global_features'],'candidates':f['candidates'],'mask':f['mask']}

class RoutePolicy:
 def __init__(self,c,bound,kind='prior',model=None,stochastic=False,teacher=None):
  self.context=c;self.bound=bound;self.kind=kind;self.model=model;self.stochastic=stochastic;self.teacher=teacher;self.transitions=[];self.timings=[];self.demonstrations=[]
 def __call__(self,o):
  begin=time.perf_counter();acts,f,prior=feature_actions(o,self.context,self.bound)
  if not acts:
   if not o.own.at_station:raise ValueError('no robust return action')
   return Action.wait(min(5.,self.context.max_wait))
  if self.kind=='model':
   x=model_input(f)
   from rl_algorithms import masked_policy_distribution
   with torch.no_grad():
    dist,value=masked_policy_distribution(self.model,x)
    index=int(dist.sample()) if self.stochastic else int(dist.probs.argmax())
    logp=float(dist.log_prob(torch.tensor(index)));val=float(value)
   self.transitions.append({**x,'action':index,'old_logp':logp,'value':val,'reward':0.,'done':False})
  elif self.teacher is not None:
   choice=self.teacher(o);index=acts.index(choice) if choice in acts else int(np.argmax(prior))
   self.demonstrations.append({**model_input(f),'action':index})
  else:
   ts={t.id:t for t in o.visible_tasks};d=o.own
   def key(i):
    a=acts[i]
    if a.kind=='RETURN':return (1e9,0) if any(z.kind=='TARGET' for z in acts) else (-1e9,0)
    t=ts[a.target_id];dist=math.hypot(t.x-d.x,t.y-d.y)
    if self.kind=='nearest':return (dist,t.id)
    if self.kind=='deadline':return (t.deadline if t.emergency else 1e6,dist)
    weight={'mix0.5':.5,'mix1':1.,'mix2':2.}.get(self.kind,1.)
    return (-prior[i]*weight+dist/10000.,t.id)
   index=min(range(len(acts)),key=key) if self.kind!='prior' else int(np.argmax(prior))
  self.timings.append(time.perf_counter()-begin);return acts[index]

class AuthorRoutePolicy:
 """Official static Java route + disclosed online insertion/dispatch adapter."""
 def __init__(self,c,bound,sequences,kind):
  self.context=c;self.bound=bound;self.seq=sequences;self.kind=kind;self.seen=set();self.queues={};self.timings=[]
 def __call__(self,o):
  begin=time.perf_counter();acts,f,p=feature_actions(o,self.context,self.bound);d=o.own
  if not acts:return Action.wait(min(5.,self.context.max_wait)) if d.at_station else Action.return_to_station()
  legal={a.target_id:a for a in acts if a.kind=='TARGET'};available={t.id:t for t in o.visible_tasks};routines=[]
  for trip in self.seq.get(d.id,[]):
   remain=[n for n in trip if n in available]
   if remain:routines=remain;break
  pending=[t for t in available.values() if t.emergency and t.station_id==d.station_id and t.id in legal]
  # A1 dispatches a visible emergency as its own trip; A2 cost-only nearest insertion.
  if self.kind=='author_dispatch' and pending:
   if d.trip_task_ids and any(n>=100000 for n in d.trip_task_ids):
    action=Action.return_to_station() if any(a.kind=='RETURN' for a in acts) else min(acts,key=lambda a:a.target_id or -1)
   else:action=legal[min(pending,key=lambda t:math.hypot(t.x-d.x,t.y-d.y)).id]
  elif self.kind=='author_insert' and (routines or pending):
   candidates=[available[n] for n in routines[:1] if n in legal]+pending
   home=self.context.station(d.station_id)
   def inc(t):return math.hypot(t.x-d.x,t.y-d.y)+math.hypot(t.x-home[1],t.y-home[2])-math.hypot(d.x-home[1],d.y-home[2])
   action=legal[min(candidates,key=lambda t:(inc(t),t.id)).id] if candidates else next((a for a in acts if a.kind=='RETURN'),acts[0])
  else:
   action=legal[routines[0]] if routines and routines[0] in legal else next((a for a in acts if a.kind=='RETURN'),next((a for a in acts if a.kind=='TARGET'),acts[0]))
  self.timings.append(time.perf_counter()-begin);return action

def score(s,r):
 tm={t.id:t for t in s.tasks};rows=r['tasks'];miss=0.;routine_missing=0
 for row in rows:
  t=tm[row['id']]
  if t.emergency and not row['on_time']:miss+=30. if t.priority>=10 else 10.
  elif not t.emergency and not row['served']:routine_missing+=1
 bad=len(r['terminal_failures'])+int(not r['complete_return'])
 makespan=r['makespan'] if r['makespan'] is not None else s.config.horizon
 J=r['incurred_cost']+.5*makespan+miss+1000*routine_missing+10000*bad
 emergency=[row for row in rows if tm[row['id']].emergency];high=[row for row in emergency if tm[row['id']].priority>=10]
 response=[(row['served_at']-row['release']) if row['served'] else s.config.horizon-row['release'] for row in emergency]
 return dict(J=J,cost=r['incurred_cost'],makespan=r['makespan'],complete_return=r['complete_return'],invalid_actions=r['invalid_actions'],duty_violation=r['duty_violation'],terminal_failure_count=len(r['terminal_failures']),routine_missing=routine_missing,emergency_on_time=sum(row['on_time'] for row in emergency)/max(1,len(emergency)),high_on_time=sum(row['on_time'] for row in high)/max(1,len(high)),response=sum(response)/max(1,len(response)),emergency_count=len(emergency),high_count=len(high),miss_penalty=miss)

def execute(s,policy):
 start=time.perf_counter();r=EmergencySimulator(s).run(policy);elapsed=time.perf_counter()-start
 v=verify_result(snapshot(s),r)
 z=score(s,r);z.update(replay_verified=v['verified'],replay_reason=v.get('reason'),elapsed_s=elapsed,decisions=len(getattr(policy,'timings',[])),decision_ms=1000*sum(getattr(policy,'timings',[]))/max(1,len(getattr(policy,'timings',[]))))
 return z,r
