"""Offline emergency contract replay, stdlib only, no policy/simulator imports.

Full realized trace is verification data AFTER execution, not policy input.
"""
from __future__ import annotations
import math,hashlib,json

class VerificationError(ValueError):
    pass

def _number(v,label,*,nonnegative=True):
    if type(v) not in (int,float) or not math.isfinite(v) or (nonnegative and v<0):
        raise VerificationError(label+':finite numeric domain')
    return float(v)

def _same(a,b,tol,label):
    if a is None or b is None:
        if a is not b:raise VerificationError(label+':null mismatch')
    elif type(b) is bool:
        if type(a) is not bool or a!=b:raise VerificationError(label+':Boolean mismatch')
    elif type(b) in (int,float):
        if type(a) not in (int,float) or not math.isfinite(a) or abs(float(a)-float(b))>tol:raise VerificationError(label+':numeric mismatch')
    elif a!=b:raise VerificationError(label+':value mismatch')

def _fingerprint(snapshot):
    def canon(value):
        if isinstance(value,float):
            if math.isnan(value):raise VerificationError('NaN identity')
            return 'INF' if value==math.inf else '-INF' if value==-math.inf else value
        if isinstance(value,dict):return {str(k):canon(v) for k,v in value.items()}
        if isinstance(value,(tuple,list)):return [canon(v) for v in value]
        return value
    payload=dict(scenario_id=snapshot['scenario_id'],stations=snapshot['stations'],tasks=snapshot['tasks'],
                 drone_stations=snapshot['drone_stations'],capacities=snapshot['capacities'],trace=snapshot['intervals'],
                 config=snapshot['config'],forecast=snapshot['forecast'])
    return hashlib.sha256(json.dumps(canon(payload),sort_keys=True,allow_nan=False).encode()).hexdigest()

def _flight(origin,destination,start,energy,power,airspeed,intervals,horizon):
    """Independent scalar wind-track equation and interval/energy integration."""
    x,y=origin;tx,ty=destination;dx=tx-x;dy=ty-y;distance=math.hypot(dx,dy)
    if distance==0.:return dict(end=start,energy=0.,failure=None,position=(tx,ty))
    ux,uy=dx/distance,dy/distance;traversed=used=0.;now=start
    for row in intervals:
        end,wx,wy=row;end=min(end,horizon)
        if end<=now:continue
        longitudinal=(wx*dx+wy*dy)/distance;lateral=(wx*dy-wy*dx)/distance
        discriminant=airspeed*airspeed-lateral*lateral
        if discriminant<=0.:return dict(end=now,energy=used,failure='NO_FLY',position=(x+ux*traversed,y+uy*traversed))
        speed=longitudinal+math.sqrt(discriminant)
        if speed<=.05*airspeed:return dict(end=now,energy=used,failure='NO_FLY',position=(x+ux*traversed,y+uy*traversed))
        required=(distance-traversed)/speed;duration=min(required,end-now)
        available=max(0.,energy-used)
        if power>0. and duration*power>available+1e-12:
            duration=available/power;traversed+=duration*speed;now+=duration;used+=available
            return dict(end=now,energy=used,failure='FLIGHT_ENERGY',position=(x+ux*traversed,y+uy*traversed))
        traversed+=duration*speed;now+=duration;used+=duration*power
        if duration==required:return dict(end=now,energy=used,failure=None,position=(tx,ty))
        if now>=horizon:break
    return dict(end=now,energy=used,failure='HORIZON_EXCEEDED',position=(x+ux*traversed,y+uy*traversed))

def replay_snapshot(snapshot,action_log,*,tolerance=1e-7):
    """Reconstruct accepted-action physics; unsupported invalid policy => reject."""
    tol=_number(tolerance,'tolerance');cfg=snapshot['config'];H=_number(cfg['horizon'],'H');speed=_number(cfg['speed'],'airspeed')
    if H<=0 or speed<=0:raise VerificationError('positive H and airspeed required')
    power=_number(cfg['flight_power'],'power');duty_limit=_number(cfg['duty_limit'],'duty');wait_limit=_number(cfg['max_wait'],'wait limit')
    time_cost=_number(cfg['time_cost'],'time cost');fixed=_number(cfg['fixed_cost'],'fixed cost')
    stations={};tasks={}
    for st in snapshot['stations']:
        if type(st['id']) is not int or st['id'] in stations:raise VerificationError('station identities')
        stations[st['id']]=(_number(st['x'],'station x',nonnegative=False),_number(st['y'],'station y',nonnegative=False))
    for t in snapshot['tasks']:
        if type(t['id']) is not int or t['id'] in tasks or t['station_id'] not in stations:raise VerificationError('task identities/owner')
        _number(t['x'],'target x',nonnegative=False);_number(t['y'],'target y',nonnegative=False)
        for key in ('release','energy','service'):_number(t[key],'task '+key)
        if t['release']>H or not isinstance(t['emergency'],bool):raise VerificationError('task release/type')
        deadline=t['deadline']
        if type(deadline) not in (int,float) or math.isnan(deadline) or deadline<t['release'] or (t['emergency'] and not math.isfinite(deadline)):raise VerificationError('deadline')
        tasks[t['id']]=t
    intervals=[];last=0.
    for end,wx,wy in snapshot['intervals']:
        end=_number(end,'trace end');_number(wx,'wind x',nonnegative=False);_number(wy,'wind y',nonnegative=False)
        if end<=last:raise VerificationError('wind order')
        intervals.append((end,wx,wy));last=end
    if not intervals or last<H:raise VerificationError('trace coverage')
    owners=snapshot['drone_stations'];caps=snapshot['capacities']
    if not owners or len(owners)!=len(caps):raise VerificationError('fleet shape')
    drones=[]
    for did,(owner,cap) in enumerate(zip(owners,caps)):
        if owner not in stations or _number(cap,'capacity')<=0:raise VerificationError('fleet ownership/capacity')
        drones.append(dict(id=did,owner=owner,position=stations[owner],at_station=True,energy=0.,duty=0.,ready=0.,failure=None,last_return=0.,trip=[]))
    reserved={};served={};returned={};status={};expected_failures=[];logged_failures=[];last_clock=-1.;frontier_clock=None;pending=set()
    for ordinal,event in enumerate(action_log):
        now=_number(event['time'],'action time');did=event['drone']
        if type(did) is not int or not 0<=did<len(drones):raise VerificationError('drone identity')
        if now<last_clock:raise VerificationError('global log time regression')
        if 'action' in event:
            if now>=H:raise VerificationError('dispatch at/after H')
            if frontier_clock!=now or not pending:
                earlier=[d for d in drones if d['failure'] is None and d['ready'] is not None and d['ready']<now]
                if earlier:raise VerificationError('skipped earlier decision frontier')
                pending={d['id'] for d in drones if d['failure'] is None and d['ready']==now}
                frontier_clock=now
            if not pending or did!=min(pending):raise VerificationError('same-time scheduler order mismatch')
            pending.remove(did)
            d=drones[did]
            if d['failure'] is not None or d['ready']!=now:raise VerificationError('busy/failed or missing frontier action')
            action=event['action'];kind=action['kind']
            if kind=='WAIT':
                w=_number(action['wait_min'],'wait')
                if not d['at_station'] or not 0.<w<=wait_limit:raise VerificationError('invalid wait')
                end=min(H,now+w)
                if end<=now:raise VerificationError('wait no progress')
                d['ready']=end
            elif kind in ('TARGET','RETURN'):
                if kind=='TARGET':
                    tid=action['target_id']
                    if type(tid) is not int or tid not in tasks:raise VerificationError('unknown target')
                    t=tasks[tid]
                    if tid in reserved or t['release']>now or t['station_id']!=d['owner']:raise VerificationError('reserved/unreleased/foreign target')
                    if d['at_station']:d['energy']=0.;d['trip']=[]
                    reserved[tid]=did;status[tid]='IN_FLIGHT';d['trip'].append(tid);destination=(t['x'],t['y'])
                else:
                    if d['at_station'] or not d['trip']:raise VerificationError('return at station/no trip')
                    destination=stations[d['owner']]
                d['at_station']=False
                z=_flight(d['position'],destination,now,max(0.,caps[did]-d['energy']),power,speed,intervals,H)
                d['duty']+=z['end']-now;d['energy']+=z['energy'];d['position']=z['position'];end=z['end'];failure=z['failure']
                if failure=='HORIZON_EXCEEDED':d['ready']=H
                elif failure is not None:
                    d['failure']=failure;d['ready']=None
                    if kind=='TARGET':status[tid]='FAILED'
                    expected_failures.append((did,end,failure))
                elif d['duty']>duty_limit:
                    d['failure']='DUTY_LIMIT';d['ready']=None;expected_failures.append((did,end,'DUTY_LIMIT'))
                elif kind=='RETURN':
                    d['at_station']=True;d['energy']=0.;d['last_return']=end;d['ready']=end
                    for target in d['trip']:
                        if target in served:returned[target]=end
                    d['trip']=[]
                else:
                    available=max(0.,caps[did]-d['energy']);failed=t['energy']>available
                    duration=t['service']*(available/t['energy']) if failed and t['service']>0. else t['service']
                    consumed=(available if failed and t['service']>0. else 0. if failed else t['energy'])
                    remaining=H-end
                    if duration>remaining or (failed and duration>=remaining):
                        consumed=0. if duration==0. else consumed*remaining/duration;duration=remaining
                        d['energy']+=consumed;d['duty']+=duration;d['ready']=H
                    else:
                        d['energy']+=consumed;d['duty']+=duration;end+=duration
                        if failed:
                            status[tid]='FAILED';d['failure']='SERVICE_ENERGY';d['ready']=None;expected_failures.append((did,end,'SERVICE_ENERGY'))
                        elif d['duty']>duty_limit:
                            d['failure']='DUTY_LIMIT';d['ready']=None;expected_failures.append((did,end,'DUTY_LIMIT'))
                        else:served[tid]=end;status[tid]='SERVED';d['ready']=end
            else:raise VerificationError('unknown action kind')
            pass
        elif event.get('event')=='FAILURE':
            reason=event['reason']
            if reason.startswith('INVALID_ACTION:'):raise VerificationError('invalid/policy-error trace retained as NOT_VERIFIED')
            logged_failures.append((did,now,reason))
        else:raise VerificationError('unknown log event')
        last_clock=now
    for d in drones:
        if d['failure'] is None and d['ready']!=H:raise VerificationError('missing trailing ready-frontier action')
    expected_failures.sort();logged_failures.sort()
    if len(expected_failures)!=len(logged_failures):raise VerificationError('missing/spurious failure event')
    for a,b in zip(logged_failures,expected_failures):
        if a[0]!=b[0] or a[2]!=b[2]:raise VerificationError('failure reason/owner mismatch')
        _same(a[1],b[1],tol,'failure time')
    rows=[]
    for tid,t in tasks.items():
        delivered=tid in served;at=served.get(tid)
        rows.append(dict(id=tid,emergency=t['emergency'],release=t['release'],deadline=t['deadline'],served=delivered,served_at=at,returned_at=returned.get(tid),on_time=delivered and at<=t['deadline'],late_by=None if not delivered else max(0.,at-t['deadline']),status=status.get(tid,'AVAILABLE')))
    em=[r for r in rows if r['emergency']];denom=len(em);all_served=all(r['served'] for r in rows);failures=[d['failure'] for d in drones if d['failure']]
    complete=all_served and all((not r['served']) or r['returned_at'] is not None for r in rows) and not failures
    duty_violation=any(d['duty']>duty_limit for d in drones)
    summary=dict(emergency_task_count=denom,emergency_on_time=sum(r['on_time'] for r in em)/denom if denom else None,
      emergency_delivered=sum(r['served'] for r in em)/denom if denom else None,emergency_returned=sum(r['returned_at'] is not None for r in em)/denom if denom else None,
      weighted_lateness=sum((r['late_by'] or 0.)*(10 if r['emergency'] else 1) for r in rows),undelivered=sum(not r['served'] for r in rows),
      deadline_misses=sum(t['deadline']<H and t['id'] not in served for t in tasks.values()),terminal_failures=failures,invalid_actions=0,duty_violation=duty_violation,
      complete_return=complete,makespan=max(d['last_return'] for d in drones) if complete else None,incurred_cost=fixed+time_cost*sum(d['duty'] for d in drones))
    # Miss IDs are latched when an unserved task passes deadline; lateness also counts.
    summary['deadline_misses']=sum(t['deadline']<H and (t['id'] not in served or served[t['id']]>t['deadline']) for t in tasks.values())
    return dict(summary=summary,tasks=rows,drones=drones,all_tasks_mtc=sum(served.values())/len(tasks) if tasks and len(served)==len(tasks) else None,
      mean_response=sum(served[i]-tasks[i]['release'] for i in served)/len(tasks) if tasks and len(served)==len(tasks) else None,
      verifier='stdlib independent offline replay; no original simulator/flight imports')

def verify_result(snapshot,result,*,tolerance=1e-7):
    try:
        _same(result['scenario_id'],snapshot['scenario_id'],tolerance,'scenario_id')
        _same(result['scenario_fingerprint'],_fingerprint(snapshot),tolerance,'scenario_fingerprint')
        r=replay_snapshot(snapshot,result['actions'],tolerance=tolerance)
        for key,expected in r['summary'].items():_same(result[key],expected,tolerance,'summary.'+key)
        actual={t['id']:t for t in result['tasks']}
        if len(actual)!=len(result['tasks']) or set(actual)!={t['id'] for t in r['tasks']}:raise VerificationError('task denominator mismatch')
        for row in r['tasks']:
            for key,expected in row.items():
                if key=='deadline' and expected==math.inf:
                    if actual[row['id']][key]!=math.inf:raise VerificationError('routine infinite deadline changed')
                else:_same(actual[row['id']][key],expected,tolerance,'task.'+str(row['id'])+'.'+key)
        return dict(verified=True,status='VERIFIED_MODEL_OUTPUT',complete_return=r['summary']['complete_return'],reconstruction=r)
    except (VerificationError,KeyError,TypeError,IndexError,OverflowError,ZeroDivisionError) as exc:
        return dict(verified=False,status='NOT_VERIFIED',reason=type(exc).__name__+':'+str(exc),complete_return=False)
