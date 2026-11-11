"""Causal physical-route inference bridge; no simulator/scenario/future handle.

Shared encoder for ordinary PPO/A2C/REINFORCE inference. No training entrypoint,
no reward definition, no operator selection, no claim of feasibility or novelty.
"""
from __future__ import annotations
from dataclasses import dataclass
import math,time
from typing import Tuple
import torch
from emergency_scenario import Action,Observation
from rl_algorithms import masked_policy_distribution

GLOBAL_FIELDS=('clock','own_x','own_y','at_station','energy_used','duty_used',
 'wind_x','wind_y','forecast_x','forecast_y','drone_index','station_index',
 'owned_visible','other_visible','served_visible_count','missed_visible_count',
 'fleet_mean_energy','fleet_max_duty','fleet_failed_count','home_x','home_y')
CANDIDATE_FIELDS=('TARGET','RETURN','target_x','target_y','delta_x','delta_y',
 'distance','home_distance','service','task_energy','release','has_deadline','deadline',
 'slack','priority','emergency','own_energy','own_duty','clock','drone_index',
 'station_index','home_delta_x','home_delta_y','target_index')
GLOBAL_DIM=len(GLOBAL_FIELDS);CANDIDATE_DIM=len(CANDIDATE_FIELDS)

@dataclass(frozen=True)
class PublicContext:
 """Only declared static metadata, never a Scenario or hidden task schedule."""
 stations:Tuple[Tuple[int,float,float],...]
 drone_stations:Tuple[int,...]
 capacities:Tuple[float,...]
 horizon:float
 speed:float
 duty_limit:float
 max_wait:float
 coordinate_scale:float=10000.0
 def __post_init__(self):
  # Freeze nested sequences too; no caller-owned mutable context is retained.
  object.__setattr__(self,'stations',tuple(tuple(row) for row in self.stations))
  object.__setattr__(self,'drone_stations',tuple(self.drone_stations))
  object.__setattr__(self,'capacities',tuple(self.capacities))
  ids=[]
  for row in self.stations:
   if len(row)!=3 or type(row[0]) is not int:raise ValueError('public station format')
   ids.append(row[0])
   if not all(math.isfinite(float(x)) for x in row[1:]):raise ValueError('public station coordinates')
  if not ids or len(set(ids))!=len(ids):raise ValueError('unique public station ids required')
  if not self.drone_stations or len(self.drone_stations)!=len(self.capacities):raise ValueError('public fleet dimensions')
  if any(type(s) is not int or s not in ids for s in self.drone_stations):raise ValueError('public fixed ownership')
  for v in (*self.capacities,self.horizon,self.speed,self.duty_limit,self.max_wait,self.coordinate_scale):
   if type(v) not in (int,float) or not math.isfinite(v) or v<=0:raise ValueError('positive finite public constants required')
 def station(self,sid):return next(row for row in self.stations if row[0]==sid)

@dataclass(frozen=True)
class EncodedDecision:
 actions:Tuple[Action,...]
 global_features:Tuple[float,...]
 candidates:Tuple[Tuple[float,...],...]
 forced_idle:bool=False
 def observation(self):
  return {'global':self.global_features,'candidates':self.candidates,'mask':tuple(True for _ in self.actions)}

def encode(observation:Observation,context:PublicContext)->EncodedDecision:
 """Encode only released observations; task legality does not imply completion."""
 if not isinstance(observation,Observation) or not isinstance(context,PublicContext):raise TypeError('causal Observation and PublicContext required')
 o=observation;d=o.own;n=len(context.drone_stations)
 if type(o.acting_drone) is not int or not 0<=o.acting_drone<n or d.id!=o.acting_drone:raise ValueError('acting drone identity')
 if d.station_id!=context.drone_stations[d.id]:raise ValueError('fixed drone station mismatch')
 if d.terminal_failure is not None or o.now>=context.horizon:raise ValueError('decision on terminated or horizon state')
 if not math.isfinite(o.now) or o.now<0 or len(o.fleet)!=n or {x.id for x in o.fleet}!=set(range(n)):raise ValueError('causal fleet frontier')
 if any(type(m.id) is not int for m in o.fleet):raise ValueError('fleet integer identity')
 if next(m for m in o.fleet if m.id==d.id)!=d:raise ValueError('own and fleet state disagree')
 for member in o.fleet:
  if member.station_id!=context.drone_stations[member.id]:raise ValueError('fixed fleet ownership mismatch')
 if len({t.id for t in o.visible_tasks})!=len(o.visible_tasks):raise ValueError('duplicate visible task ids')
 if any(t.release>o.now for t in o.visible_tasks):raise ValueError('unreleased task in observation')
 if any(type(t.id) is not int or type(t.station_id) is not int for t in o.visible_tasks):raise ValueError('integer task identities')
 if any(t.station_id not in {s[0] for s in context.stations} for t in o.visible_tasks):raise ValueError('unknown fixed task station')
 if any(t.id in o.served_ids for t in o.visible_tasks):raise ValueError('served task still visible')
 owned=sorted((t for t in o.visible_tasks if t.station_id==d.station_id),key=lambda t:t.id)
 home=context.station(d.station_id);scale=context.coordinate_scale;H=context.horizon
 cap=context.capacities[d.id];D=context.duty_limit
 did=d.id/max(1,n-1);sid=[s[0] for s in context.stations].index(d.station_id)/max(1,len(context.stations)-1)
 def norm(v):return float(v)
 features=(o.now/H,d.x/scale,d.y/scale,float(d.at_station),d.trip_energy/cap,d.duty/D,
  o.wind_now[0]/context.speed,o.wind_now[1]/context.speed,o.forecast[0]/context.speed,o.forecast[1]/context.speed,
  did,sid,float(len(owned)),float(len(o.visible_tasks)-len(owned)),float(len(o.served_ids)),float(len(o.deadline_missed_ids)),
  sum(m.trip_energy/context.capacities[m.id] for m in o.fleet)/n,max(m.duty/D for m in o.fleet),
  float(sum(m.terminal_failure is not None for m in o.fleet)),home[1]/scale,home[2]/scale)
 actions=[];rows=[]
 for index,t in enumerate(owned):
  finite=math.isfinite(t.deadline)
  if math.isnan(t.deadline) or t.deadline==-math.inf:raise ValueError('invalid task deadline')
  row=(1.,0.,t.x/scale,t.y/scale,(t.x-d.x)/scale,(t.y-d.y)/scale,
   math.hypot(t.x-d.x,t.y-d.y)/scale,math.hypot(t.x-home[1],t.y-home[2])/scale,
   t.service/H,t.energy/cap,t.release/H,float(finite),t.deadline/H if finite else 0.,
   (t.deadline-o.now)/H if finite else 0.,float(t.priority),float(t.emergency),
   d.trip_energy/cap,d.duty/D,o.now/H,did,sid,(home[1]-d.x)/scale,(home[2]-d.y)/scale,float(index))
  rows.append(tuple(map(norm,row)));actions.append(Action.target(t.id))
 if not d.at_station and d.trip_task_ids:
  row=(0.,1.,home[1]/scale,home[2]/scale,(home[1]-d.x)/scale,(home[2]-d.y)/scale,
   math.hypot(home[1]-d.x,home[2]-d.y)/scale,0.,0.,0.,0.,0.,0.,0.,0.,0.,
   d.trip_energy/cap,d.duty/D,o.now/H,did,sid,(home[1]-d.x)/scale,(home[2]-d.y)/scale,-1.)
  rows.append(tuple(map(norm,row)));actions.append(Action.return_to_station())
 if len(features)!=GLOBAL_DIM or any(len(v)!=CANDIDATE_DIM for v in rows):raise RuntimeError('schema dimensions')
 if not all(math.isfinite(float(v)) for v in features) or any(not math.isfinite(v) for row in rows for v in row):raise ValueError('nonfinite encoded features')
 if not actions and not d.at_station:raise ValueError('no physical route or station-idle action')
 return EncodedDecision(tuple(actions),tuple(map(norm,features)),tuple(rows),not actions)

class PhysicalRoutePolicy:
 """Model scores TARGET/RETURN only; idle is unlearned event-engine progress."""
 def __init__(self,model,context:PublicContext,*,stochastic=False,generator=None):
  self.model=model;self.context=context;self.stochastic=stochastic;self.generator=generator
  self.decisions=[];self.forced_idle_events=[]
 def __call__(self,observation:Observation)->Action:
  start=time.perf_counter();encoded=encode(observation,self.context)
  if encoded.forced_idle:
   # The network never learns or chooses WAIT duration. Preserve engine rule.
   duration=min(1.,self.context.max_wait)
   self.forced_idle_events.append({'time':observation.now,'drone':observation.acting_drone,'duration':duration,'learned':False})
   return Action.wait(duration)
  self.model.eval()
  with torch.no_grad():
   dist,value=masked_policy_distribution(self.model,encoded.observation())
   if self.stochastic:index=int(torch.multinomial(dist.probs,1,generator=self.generator).item())
   else:index=int(torch.argmax(dist.logits).item())
   action=encoded.actions[index]
   logp=float(dist.log_prob(torch.tensor(index,device=dist.logits.device)).item())
  self.decisions.append({'time':observation.now,'drone':observation.acting_drone,
   'action':{'kind':action.kind,'target_id':action.target_id},'action_index':index,
   'old_logp':logp,'value':float(value.detach().item()),'elapsed_s':time.perf_counter()-start,
   'features':encoded.observation(),'reward_assigned':False})
  return action


def completion_metrics(result):
 """Retain MTC without rewarding omission or silently averaging successful tasks.

 Full-map MTC is absolute completion time, while response subtracts release.
 Both are undefined if any task is unserved. Served-only summaries are explicitly
 descriptive and never substitute for the full endpoint or return feasibility.
 """
 rows=result['tasks'];served=[];response=[]
 if len({r['id'] for r in rows})!=len(rows):raise ValueError('duplicate result task ids')
 for row in rows:
  if row['served']:
   at=row['served_at'];release=row['release']
   if (type(at) not in (int,float) or type(release) not in (int,float)
       or not math.isfinite(at) or not math.isfinite(release) or at<release):
    raise ValueError('invalid completion or release time')
   served.append(float(at));response.append(float(at-release))
 complete=bool(rows) and len(served)==len(rows)
 return {'task_count':len(rows),'served_count':len(served),
  'MTC_all_tasks':sum(served)/len(rows) if complete else None,
  'mean_response_all_tasks':sum(response)/len(rows) if complete else None,
  'MTC_served_only_descriptive':sum(served)/len(served) if served else None,
  'MTC_denominator_rule':'all tasks required; missing service -> null; no implicit zero',
  'complete_return':result['complete_return']}
