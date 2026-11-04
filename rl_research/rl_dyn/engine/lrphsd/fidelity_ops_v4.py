"""Incremental, source-traced candidate generation for the round-3 code profile.
Raw SABS array slots are storage, not two physical drones. Candidate semantics
are compared before the solver's separate complete-physical acceptance guard.
"""
import copy,math
RUNTIME=None

def clone(sol):
    return {**sol,'station_types':sol['station_types'].copy(),'routes':[[[trip.copy() for trip in drone] for drone in station] for station in sol['routes']]}

def source_distances(ins):
    return {(a.id,b.id):math.sqrt((a.x-b.x)**2+(a.y-b.y)**2) for a in ins.nodes.values() for b in ins.nodes.values()}

def physical(sol):
    out={**sol,'routes':[[[list(t) for t in drone] for drone in station] for station in sol['routes']]}
    for si,kind in enumerate(out['station_types']):
        if kind==1:
            out['routes'][si][1]=out['routes'][si][0]+out['routes'][si][1]
            out['routes'][si][0]=[]
    out.pop('_storage_profile',None)
    return out

def _path_time(ins,si,trip):
    if not trip:return 0.0
    depot=ins.stations[si].id;seq=[depot]+trip+[depot];value=0.0
    for k,(a,b) in enumerate(zip(seq,seq[1:])):
        value+=ins.dist[a,b]/ins.params.speed
        if k>0:value+=ins.nodes[a].service
    return value

def _path_energy(ins,si,trip,segment=False):
    depot=ins.stations[si].id;seq=[depot]+trip+[depot];p=ins.params
    if not segment:return sum(ins.dist[a,b] for a,b in zip(seq,seq[1:]))/p.speed*p.flight_energy+sum(ins.nodes[n].energy for n in trip)
    energy=0.0
    for k,(a,b) in enumerate(zip(seq,seq[1:])):
        energy+=ins.dist[a,b]/p.speed*p.flight_energy
        if k>0:energy+=ins.nodes[a].energy
    return energy

def capacity(ins,kind,di):return ins.params.large_battery if kind==2 and di==0 else ins.params.small_battery

def raw_valid(ins,sol,time_check=True):
    if RUNTIME is not None:
        RUNTIME.counts["source_energy_query_api_requests"]+=1
        RUNTIME.counts["source_time_query_api_requests"]+=bool(time_check)
    for si,kind in enumerate(sol['station_types']):
        for di,trips in enumerate(sol['routes'][si]):
            if kind and any(path_energy(ins,si,t)>capacity(ins,kind,di) for t in trips):return False
            if time_check and sum(path_time(ins,si,t) for t in trips)>ins.duration(kind):return False
    return True

def different_indices(rng,length):
    a=rng.randrange(length);b=rng.randrange(length)
    while b==a:b=rng.randrange(length)
    return a,b

def location(types,rng,which=None):
    result=types.copy();which=rng.randrange(4) if which is None else which
    if which==0:
        if len(types)<2:return result
        a,b=different_indices(rng,len(types));result[a],result[b]=result[b],result[a]
    else:
        choices=[i for i,k in enumerate(types) if (k<2 if which==1 else k>0)]
        if choices:
            i=rng.choice(choices);result[i]=result[i]+1 if which==1 else result[i]-1 if which==2 else 0
    return result

def local_candidate(ins,sol,which,rng):
    candidate=clone(sol);routes=candidate['routes'];types=sol['station_types']
    if which==4:
        for si,station in enumerate(routes):
            depot=ins.stations[si].id
            for drone in station:
                for trip in drone:
                    improved=True
                    while improved:
                        improved=False
                        for a in range(len(trip)-1):
                            for b in range(a+1,len(trip)):
                                before=depot if a==0 else trip[a-1];after=depot if b+1==len(trip) else trip[b+1]
                                current=ins.dist[before,trip[a]]+ins.dist[trip[b],after]
                                proposed=ins.dist[before,trip[b]]+ins.dist[trip[a],after]
                                if proposed<current:
                                    trip[a:b+1]=reversed(trip[a:b+1]);improved=True
        return candidate
    if which==0:
        stations=[i for i,k in enumerate(types) if k]
        if not stations:return sol
        si=rng.choice(stations);drones=[i for i,trips in enumerate(routes[si]) if trips]
        if not drones:return sol
        di=rng.choice(drones);trips=[i for i,t in enumerate(routes[si][di]) if len(t)>1]
        if not trips:return sol
        ti=rng.choice(trips);trip=routes[si][di][ti];a,b=different_indices(rng,len(trip))
        trip[a],trip[b]=trip[b],trip[a]
    elif which==1:
        si=rng.randrange(len(routes))
        # Raw Java has zero drone-list entries at a closed/unused station;
        # the JSON codec pads two empty slots for the canonical dimensions.
        if not any(routes[si]):return candidate
        di=rng.randrange(len(routes[si]));trips=routes[si][di]
        if len(trips)<2:return candidate
        a,b=different_indices(rng,len(trips))
        if not trips[a] or not trips[b]:return candidate
        pa=rng.randrange(len(trips[a]));pb=rng.randrange(len(trips[b]))
        trips[a][pa],trips[b][pb]=trips[b][pb],trips[a][pa]
    elif which==2:
        stations=[i for i,k in enumerate(types) if k==2]
        if not stations:return sol
        si=rng.choice(stations);large,small=routes[si]
        if not large or not small:return sol
        a=rng.randrange(len(large));b=rng.randrange(len(small))
        if not large[a] or not small[b]:return sol
        pa=rng.randrange(len(large[a]));pb=rng.randrange(len(small[b]))
        large[a][pa],small[b][pb]=small[b][pb],large[a][pa]
    else:
        stations=[i for i,k in enumerate(types) if k]
        if len(stations)<2:return sol
        a,b=different_indices(rng,len(stations));sa,sb=stations[a],stations[b]
        if not any(routes[sa]) or not any(routes[sb]):return sol
        da=rng.randrange(len(routes[sa]));db=rng.randrange(len(routes[sb]))
        ta,tb=routes[sa][da],routes[sb][db]
        if not ta or not tb:return sol
        a=rng.randrange(len(ta));b=rng.randrange(len(tb))
        if not ta[a] or not tb[b]:return sol
        pa=rng.randrange(len(ta[a]));pb=rng.randrange(len(tb[b]))
        ta[a][pa],tb[b][pb]=tb[b][pb],ta[a][pa]
    return candidate if raw_valid(ins,candidate,time_check=which>=2) else sol

def positions(sol):
    return [(si,di,ti,pi,n) for si,station in enumerate(sol['routes']) for di,trips in enumerate(station) for ti,trip in enumerate(trips) for pi,n in enumerate(trip)]

def destroy_candidate(ins,sol,which,rng):
    candidate=clone(sol);routes=candidate['routes'];types=sol['station_types']
    counts={(si,di):sum(map(len,trips)) for si,s in enumerate(routes) for di,trips in enumerate(s)}
    entries=[e for e in positions(candidate) if types[e[0]] and counts[e[0],e[1]]>1]
    if which==2:
        if not entries:return sol
        si,di,ti,pi,_=rng.choice(entries);routes[si][di][ti].pop(pi)
        return candidate if raw_valid(ins,candidate) else sol
    if which==0:
        best=None;gain=-math.inf
        for si,di,ti,pi,nid in entries:
            trip=routes[si][di][ti];new=trip[:pi]+trip[pi+1:]
            saving=(path_time(ins,si,trip)-path_time(ins,si,new))*ins.params.time_cost
            if saving>gain and path_energy(ins,si,new,True)<capacity(ins,types[si],di):
                gain=saving;best=(si,di,ti,pi)
        if best:
            si,di,ti,pi=best
            if len(routes[si][di][ti])>1:routes[si][di][ti].pop(pi)
        return candidate if raw_valid(ins,candidate) else sol
    if which==1:
        for si,s in enumerate(routes):
            depot=ins.stations[si].id
            for di,trips in enumerate(s):
                remaining=counts[si,di]
                for trip in trips:
                    options=[]
                    for pi,nid in enumerate(trip):
                        if remaining==1:continue
                        a=depot if pi==0 else trip[pi-1];b=depot if pi+1==len(trip) else trip[pi+1]
                        saving=ins.dist[a,nid]+ins.dist[nid,b]-ins.dist[a,b]
                        if saving>0:options.append((saving,pi))
                    options.sort(key=lambda x:-x[0])
                    for _,pi in options:
                        if rng.random()<=0.7 and remaining>1:
                            trip.pop(pi);remaining-=1;break
        return candidate
    candidates=[];scores=[]
    for si,di,ti,pi,nid in entries:
        trip=routes[si][di][ti]
        if len(trip)<2:continue
        score=0.0
        for other in trip:
            if other==nid:continue
            cover_a=any(k and ins.dist[ins.stations[j].id,nid]<=ins.radius(k) for j,k in enumerate(types))
            cover_b=any(k and ins.dist[ins.stations[j].id,other]<=ins.radius(k) for j,k in enumerate(types))
            weight=.8 if cover_a and cover_b else .5 if cover_a or cover_b else .2
            score+=weight/max(ins.dist[nid,other],1e-6)
        if score>0:candidates.append((si,di,ti,pi));scores.append(score)
    if not candidates:return sol
    low,high=min(scores),max(scores)
    weights=[(1.0 if abs(high-low)<1e-9 else (x-low)/(high-low))+1e-6 for x in scores]
    si,di,ti,pi=rng.choices(candidates,weights,k=1)[0];routes[si][di][ti].pop(pi)
    return candidate

def covered_drones(ins,sol,nid,require_routes=False):
    for si,kind in enumerate(sol['station_types']):
        if not kind or ins.dist[ins.stations[si].id,nid]>ins.radius(kind):continue
        # Init represents an open station with no assigned targets by zero
        # drone entries. JSON padding must not create insertion opportunities.
        if not any(sol['routes'][si]):continue
        for di,trips in enumerate(sol['routes'][si]):
            if require_routes and not trips:continue
            yield si,di,trips,capacity(ins,kind,di),ins.duration(kind)

def options_in_drone(ins,si,di,trips,cap,limit,nid):
    depot=ins.stations[si].id;total=sum(path_time(ins,si,t) for t in trips)
    for ti,trip in enumerate(trips):
        old_time=path_time(ins,si,trip)
        for pos in range(len(trip)+1):
            new=trip[:pos]+[nid]+trip[pos:]
            if path_energy(ins,si,new,True)>cap:continue
            newtime=path_time(ins,si,new);after=total-old_time+newtime
            if after>limit:continue
            a=depot if pos==0 else trip[pos-1];b=depot if pos==len(trip) else trip[pos]
            delta=ins.dist[a,nid]+ins.dist[nid,b]-ins.dist[a,b]
            yield (si,di,ti,pos,delta,after,newtime-old_time)

def apply_option(sol,nid,option):
    si,di,ti,pos,*_=option;trips=sol['routes'][si][di]
    if ti==len(trips):trips.append([nid])
    else:trips[ti].insert(pos,nid)

def repair_candidate(ins,sol,pending,which):
    candidate=clone(sol)
    for nid in pending:
        best=None;newpath=None;bestscore=-math.inf;min_delta=math.inf
        if which==3:
            # Actual code prioritizes first empty storage drone, NOT emptiest
            # station and NOT load-balance score on existing insertion.
            for si,di,trips,cap,limit in covered_drones(ins,candidate,nid):
                if not trips and path_energy(ins,si,[nid],True)<=cap and path_time(ins,si,[nid])<=limit:
                    newpath=(si,di,0,0);break
            if newpath:
                apply_option(candidate,nid,newpath);continue
        for si,di,trips,cap,limit in covered_drones(ins,candidate,nid,require_routes=which in (0,1)):
            found=False;total=sum(path_time(ins,si,t) for t in trips)
            for option in options_in_drone(ins,si,di,trips,cap,limit,nid):
                delta=option[4]
                if which in (0,1):
                    if delta<min_delta:min_delta=delta;best=option;found=True
                else:
                    score=(.6*(limit-option[5])/limit+.4/(1+abs(option[6]*ins.params.time_cost))) if which==2 else 1/(1+delta)
                    if score>bestscore:bestscore=score;best=option;newpath=None
            if which==0 and not found:
                base=ins.dist[ins.stations[si].id,nid]
                if base<min_delta:min_delta=base;newpath=(si,di,len(trips),0)
            if which==2:
                single_time=path_time(ins,si,[nid]);after=total+single_time
                if path_energy(ins,si,[nid],True)<=cap and after<=limit:
                    score=(limit-after)/limit
                    if score>bestscore:bestscore=score;best=None;newpath=(si,di,len(trips),0)
        if best is not None:
            apply_option(candidate,nid,best);continue
        if newpath is not None:
            apply_option(candidate,nid,newpath);continue
        if which in (1,3):
            mincost=math.inf
            for si,di,trips,cap,limit in covered_drones(ins,candidate,nid,require_routes=which==1):
                single=path_time(ins,si,[nid]);cost=single*ins.params.time_cost
                if path_energy(ins,si,[nid],True)>cap:continue
                feasible=cost<=limit if which==1 else sum(path_time(ins,si,t) for t in trips)+single<=limit
                if feasible and cost<mincost:mincost=cost;newpath=(si,di,len(trips),0)
            if newpath:
                apply_option(candidate,nid,newpath);continue
        if which in (2,3):return sol
        # nearest/min-regret silently leave this target missing in public code.
    return candidate if raw_valid(ins,candidate) else sol

def path_time(ins,si,trip):
    if RUNTIME is not None:
        if RUNTIME.cache:return RUNTIME.path_time(si,trip)
        RUNTIME.counts['route_time_api_calls']+=1
    return _path_time(ins,si,trip)

def path_energy(ins,si,trip,segment=False):
    if RUNTIME is not None:
        if RUNTIME.cache:return RUNTIME.path_energy(si,trip,segment)
        RUNTIME.counts['route_energy_api_calls']+=1
    return _path_energy(ins,si,trip,segment)
