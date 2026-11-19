"""Complete independent evaluator. Deliberately does not use cached distances,
optimizer objective, incremental statistics, or greedy feasibility routines."""
import math
from collections import Counter

def evaluate(instance, solution, allow_missing=False):
    p=instance.params; issues=[]; fixed=0.0; operating=0.0; counts=Counter(); details=[]
    types=solution.get('station_types'); routes=solution.get('routes')
    if not isinstance(types,list) or not isinstance(routes,list) or len(types)!=len(instance.stations) or len(routes)!=len(instance.stations):
        return {'feasible':False,'cost':None,'issues':['station_dimension'],'details':[]}
    if solution.get('instance_sha256',instance.sha256)!=instance.sha256:issues.append('instance_hash')
    targets={x.id:x for x in instance.targets}
    for si,station in enumerate(instance.stations):
        kind=types[si]
        if type(kind) is not int or kind not in (0,1,2):issues.append(f'type:{si}'); continue
        if kind==1:fixed+=p.small_station_cost+p.small_drone_cost
        if kind==2:fixed+=p.large_station_cost+p.small_drone_cost+p.large_drone_cost
        drones=routes[si]
        if not isinstance(drones,list) or len(drones)!=2:issues.append(f'drone_dimension:{si}');continue
        for di,trips in enumerate(drones):
            if not isinstance(trips,list):issues.append(f'trip_dimension:{si}:{di}');continue
            drone_time=0.0
            for ti,trip in enumerate(trips):
                if not isinstance(trip,list):issues.append(f'trip_format:{si}:{di}:{ti}');continue
                if not trip:continue
                if kind==0:issues.append(f'closed_station:{si}')
                if kind==1 and di==0:issues.append(f'large_drone_at_small_station:{si}')
                valid=[]
                for nid in trip:
                    if type(nid) is not int or nid not in targets:issues.append(f'non_target:{si}:{di}:{ti}');continue
                    counts[nid]+=1;n=targets[nid];valid.append(n)
                    radius=p.small_radius if kind==1 else p.large_radius
                    if math.hypot(n.x-station.x,n.y-station.y)>radius+1e-7:issues.append(f'coverage:{nid}')
                seq=[station]+valid+[station]
                length=sum(math.sqrt((a.x-b.x)**2+(a.y-b.y)**2) for a,b in zip(seq,seq[1:]))
                travel=length/p.speed; service=sum(n.service for n in valid)
                energy=travel*p.flight_energy+sum(n.energy for n in valid)
                capacity=p.large_battery if di==0 else p.small_battery
                if energy>capacity+1e-7:issues.append(f'energy:{si}:{di}:{ti}')
                drone_time+=travel+service
                details.append({'station':si,'drone':di,'trip':ti,'length_m':length,'time_min':travel+service,'energy':energy,'energy_slack':capacity-energy})
            limit=p.small_duration if kind==1 else p.large_duration
            if drone_time>limit+1e-7:issues.append(f'cumulative_time:{si}:{di}')
            operating+=drone_time
    for n in targets:
        if counts[n]>1:issues.append(f'duplicate:{n}')
        if counts[n]==0 and not allow_missing:issues.append(f'missing:{n}')
    return {'feasible':not issues,'cost':fixed+operating*p.time_cost,'fixed_cost':fixed,'operating_minutes':operating,'issues':issues,'details':details,'visited':sum(counts.values()),'missing':sum(counts[n]==0 for n in targets)}
