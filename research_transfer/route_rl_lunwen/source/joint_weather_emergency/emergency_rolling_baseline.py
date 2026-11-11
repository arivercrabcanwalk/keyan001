"""Ordinary causal rolling visible-task beam comparator; engineering only."""
from __future__ import annotations
from dataclasses import dataclass,replace
from types import SimpleNamespace
import math,time
from emergency_scenario import Action,Observation
from emergency_route_bridge import PublicContext,encode
from shared_replay_v2 import Trace,flight

@dataclass(frozen=True)
class PlannerConfig:
 beam_width:int=32
 max_nodes:int=2048
 max_depth:int=32
 wall_seconds:float=.25
 flight_power:float=.018
 def __post_init__(self):
  for x in (self.beam_width,self.max_nodes,self.max_depth):
   if type(x) is not int or x<=0:raise ValueError('positive integer search bounds required')
  for x in (self.wall_seconds,self.flight_power):
   if type(x) not in (int,float) or not math.isfinite(x) or x<0:raise ValueError('finite nonnegative planner constant required')
  if self.wall_seconds<=0:raise ValueError('positive wall bound required')

@dataclass(frozen=True)
class PlanState:
 x:float;y:float;clock:float;energy:float;duty:float;at_station:bool
 remaining:tuple
 actions:tuple=()
 served:tuple=()

class RollingRoutePolicy:
 """Replan only visible owned routes; simulator chooses the acting drone."""
 def __init__(self,context:PublicContext,config=PlannerConfig(),*,clock=time.perf_counter):
  if not isinstance(context,PublicContext) or not isinstance(config,PlannerConfig):raise TypeError('public context and fixed config required')
  self.context=context;self.config=config;self.clock=clock;self.decisions=[]
 def _leg(self,s,x,y,wind,cap,stats):
  stats['flight_integrator_calls']+=1
  trace=Trace(((math.inf,float(wind[0]),float(wind[1])),),scenario_id='causal-current-wind-persistence')
  a=SimpleNamespace(x=s.x,y=s.y,energy=0.,service=0.);b=SimpleNamespace(x=x,y=y,energy=0.,service=0.)
  z=flight(a,b,s.clock,max(0.,cap-s.energy),self.config.flight_power,self.context.speed,trace)
  dt=z['end']-s.clock
  if z['failed'] is not None:return None
  if z['end']>self.context.horizon or s.duty+dt>self.context.duty_limit:return None
  return replace(s,x=x,y=y,clock=z['end'],energy=s.energy+z['energy'],duty=s.duty+dt)
 def _return(self,s,home,wind,cap,stats):
  if s.at_station:return s
  z=self._leg(s,home[1],home[2],wind,cap,stats)
  if z is None:return None
  return replace(z,at_station=True,energy=0.,actions=(*s.actions,('RETURN',None)))
 def _target(self,s,t,wind,cap,stats):
  z=self._leg(s,t.x,t.y,wind,cap,stats)
  if z is None:return None
  energy=z.energy+t.energy;duty=z.duty+t.service;finish=z.clock+t.service
  if energy>cap+1e-12 or duty>self.context.duty_limit or finish>self.context.horizon:return None
  return replace(z,at_station=False,energy=energy,duty=duty,clock=finish,
    remaining=tuple(i for i in s.remaining if i!=t.id),actions=(*s.actions,('TARGET',t.id)),served=(*s.served,(t.id,finish)))
 def _score(self,s,tasks):
  em=routine=0;response=0.
  for tid,at in s.served:
   t=tasks[tid];response+=at-t.release
   if at>t.deadline:
    if t.emergency:em+=1
    else:routine+=1
  seq=tuple((0 if a=='TARGET' else 1,-1 if tid is None else tid) for a,tid in s.actions)
  return (len(s.remaining),em,routine,response,s.clock,s.duty,seq)
 def __call__(self,observation:Observation):
  start=self.clock();enc=encode(observation,self.context);o=observation;d=o.own
  stats={'flight_integrator_calls':0,'projected_nodes':0,'completed_visible_plans':0,'search_stop':'exhausted',
         'wind_model':'current_wind_persistence_only','prediction_is_realized_feasibility_certificate':False}
  if enc.forced_idle:
   action=Action.wait(min(1.,self.context.max_wait));stats.update(forced_idle=True,elapsed_s=self.clock()-start,action={'kind':'WAIT','target_id':None})
   self.decisions.append(stats);return action
  tasks={t.id:t for t in sorted(o.visible_tasks,key=lambda t:t.id) if t.station_id==d.station_id}
  cap=self.context.capacities[d.id];home=self.context.station(d.station_id)
  root=PlanState(d.x,d.y,o.now,d.trip_energy,d.duty,d.at_station,tuple(tasks))
  beam=[root];best=None;best_score=None;deadline=start+self.config.wall_seconds
  max_depth=min(self.config.max_depth,2*len(tasks)+1)
  def consider(state):
   nonlocal best,best_score
   final=self._return(state,home,o.wind_now,cap,stats)
   if final is None or not final.actions:return
   if not final.remaining:stats['completed_visible_plans']+=1
   score=self._score(final,tasks)
   if best is None or score<best_score:best=final;best_score=score
  consider(root)
  stopped=False
  for depth in range(max_depth):
   next_states=[]
   for state in beam:
    candidates=[('TARGET',tid) for tid in state.remaining]
    if not state.at_station:candidates.append(('RETURN',None))
    for kind,tid in candidates:
     if self.clock()>=deadline:stats['search_stop']='wall_bound';stopped=True;break
     if stats['projected_nodes']>=self.config.max_nodes:stats['search_stop']='node_bound';stopped=True;break
     stats['projected_nodes']+=1
     child=(self._target(state,tasks[tid],o.wind_now,cap,stats) if kind=='TARGET' else self._return(state,home,o.wind_now,cap,stats))
     if child is None:continue
     tail=self._return(child,home,o.wind_now,cap,stats)
     if tail is None:continue
     consider(child)
     if child.remaining:next_states.append(child)
    if stopped:break
   if stopped or not next_states:break
   next_states.sort(key=lambda s:self._score(self._return(s,home,o.wind_now,cap,stats),tasks))
   beam=next_states[:self.config.beam_width]
  else:stats['search_stop']='depth_bound'
  if best is None:
   returns=[a for a in enc.actions if a.kind=='RETURN']
   if returns:action=returns[0]
   else:
    target=min(tasks.values(),key=lambda t:(not t.emergency,t.deadline,t.id));action=Action.target(target.id)
   stats.update(fallback=True,predicted_complete_visible=False,predicted_actions=[],predicted_remaining=list(tasks),predicted_score=None)
  else:
   kind,tid=best.actions[0];action=Action.target(tid) if kind=='TARGET' else Action.return_to_station()
   stats.update(fallback=False,predicted_complete_visible=not best.remaining,predicted_actions=list(best.actions),predicted_remaining=list(best.remaining),predicted_score=best_score,
                predicted_return_time=best.clock,predicted_active_duty=best.duty,predicted_served=list(best.served))
  if action not in enc.actions:raise RuntimeError('planner emitted action outside shared physical action set')
  stats.update(action={'kind':action.kind,'target_id':action.target_id},forced_idle=False,elapsed_s=self.clock()-start)
  stats['cooperative_wall_overrun']=stats['elapsed_s']>self.config.wall_seconds
  self.decisions.append(stats);return action
