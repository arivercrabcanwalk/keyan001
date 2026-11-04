"""Independent reconstruction of official Init.java, not a TSP/CVRP proxy.
Nearest-feasible append is the OFFICIAL-CODE profile; paper prose instead says
cheapest insertion. Both facts are recorded in REPRODUCTION_GAPS.md."""
from .problem import empty_solution

def station_set(ins):
    remaining=set(ins.target_ids); types=[0]*len(ins.stations)
    while remaining:
        best=None; covered=set()
        for si,station in enumerate(ins.stations):
            if types[si]:continue
            for kind in (1,2):
                candidate={n for n in remaining if ins.gdist[station.id,n]<=ins.radius(kind)}
                # Strict > and iteration order reproduce public Java tie handling.
                if len(candidate)>len(covered):best=(si,kind);covered=candidate
        if best is None:raise ValueError('targets outside all coverage circles')
        types[best[0]]=best[1];remaining-=covered
    return types

def build(ins, types=None):
    p=ins.params;types=list(types if types is not None else station_set(ins));sol=empty_solution(ins,types)
    assignments=[[] for _ in types]
    for nid in ins.target_ids:
        choices=[si for si,s in enumerate(ins.stations) if types[si] and ins.gdist[s.id,nid]<=ins.radius(types[si])]
        if not choices:raise ValueError('uncovered target')
        si=min(choices,key=lambda j:ins.dist[ins.stations[j].id,nid]);assignments[si].append(nid)
    for si,kind in enumerate(types):
        if not kind or not assignments[si]:continue
        station=ins.stations[si].id
        if kind==2:
            ordered=sorted(assignments[si],key=lambda n:ins.dist[station,n]); groups=[ordered[::2],ordered[1::2]]
            if not groups[1]:groups[1].append(groups[0].pop(0))
        else:groups=[[],assignments[si]]
        for di,pending0 in enumerate(groups):
            pending=list(pending0)
            while pending:
                trip=[];last=station;energy=0.0;elapsed=0.0
                while True:
                    feasible=[]
                    for nid in pending:
                        node=ins.nodes[nid];fly=ins.dist[last,nid]/p.speed;back=ins.dist[nid,station]/p.speed
                        if energy+fly*p.flight_energy+node.energy+back*p.flight_energy<=ins.capacity(di) and elapsed+fly+node.service+back<=ins.duration(kind):feasible.append(nid)
                    if not feasible:break
                    nid=min(feasible,key=lambda n:ins.dist[last,n]);node=ins.nodes[nid]
                    fly=ins.dist[last,nid]/p.speed;energy+=fly*p.flight_energy+node.energy;elapsed+=fly+node.service
                    trip.append(nid);pending.remove(nid);last=nid
                if not trip:raise ValueError('unserviceable target: fail-fast instead of official infinite loop')
                sol['routes'][si][di].append(trip)
    return sol
