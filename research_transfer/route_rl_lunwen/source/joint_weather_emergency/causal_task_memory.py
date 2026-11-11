"""Observed-history task memory; no future handles, training, or novelty claim."""
from __future__ import annotations
from dataclasses import asdict
import copy,math
from emergency_scenario import Observation,TaskView,Action

class CausalTaskMemory:
 def __init__(self):
  self._known={};self._dispatches=[];self._last_time=-math.inf;self._observed_frontiers=0
 def observe(self,observation):
  if not isinstance(observation,Observation):raise TypeError('actual causal Observation required')
  o=observation
  if type(o.now) not in (int,float) or not math.isfinite(o.now) or o.now<0 or o.now<self._last_time:raise ValueError('monotone finite observation clock required')
  if len({t.id for t in o.visible_tasks})!=len(o.visible_tasks):raise ValueError('duplicate visible task identity')
  for t in o.visible_tasks:
   if not isinstance(t,TaskView) or t.release>o.now:raise ValueError('only already-released public task views')
   if t.id in self._known and self._known[t.id]!=t:raise ValueError('contradictory immutable task metadata')
   if t.id in o.served_ids:raise ValueError('served task cannot be currently available')
  # Commit only after the complete incoming observation passed validation.
  self._known.update((t.id,t) for t in o.visible_tasks)
  self._last_time=o.now;self._observed_frontiers+=1
  return self.snapshot(o)
 def record_dispatch(self,observation,action):
  if not isinstance(action,Action) or action.kind not in ('TARGET','RETURN','WAIT'):raise ValueError('actual physical dispatch required')
  # Memory records only decisions already made, never prospective branches.
  snapshot=self.observe(observation);o=observation;d=o.own
  if d.id!=o.acting_drone or d.terminal_failure is not None:raise ValueError('actual acting-drone frontier required')
  if action.kind=='TARGET':
   candidates={t.id:t for t in o.visible_tasks if t.station_id==d.station_id}
   if action.target_id not in candidates:raise ValueError('dispatch task not publicly available to this drone')
  elif action.kind=='RETURN':
   if d.at_station or not d.trip_task_ids:raise ValueError('RETURN requires active trip')
  else:
   if not d.at_station or type(action.wait_min) not in (int,float) or not math.isfinite(action.wait_min) or action.wait_min<=0:raise ValueError('actual positive at-station WAIT required')
  self._dispatches.append({'time':o.now,'drone':o.acting_drone,'action':asdict(action)})
  return snapshot
 def snapshot(self,observation):
  if not isinstance(observation,Observation) or observation.now!=self._last_time:raise ValueError('snapshot requires current observed frontier')
  o=observation;available={t.id for t in o.visible_tasks};served=set(o.served_ids)
  outstanding={tid for d in o.fleet for tid in d.trip_task_ids if tid not in served}
  rows=[]
  for tid,t in sorted(self._known.items()):
   status=('served' if tid in served else 'available' if tid in available else 'in_progress' if tid in outstanding else 'known_absent_status_unknown')
   rows.append({'task':asdict(t),'observed_status':status})
  return copy.deepcopy({'now':o.now,'known_released_tasks':rows,'public_dispatches':self._dispatches,'source':'observed_history_only','predictive_sufficiency_proven':False})
