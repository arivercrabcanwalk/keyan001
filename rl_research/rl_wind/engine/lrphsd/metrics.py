"""Optimizer-side cached evaluation; independent evaluator is in evaluator.py."""
import math
from collections import Counter

def trip_stats(ins, si, trip):
    station=ins.stations[si].id;p=ins.params;seq=[station]+trip+[station]
    travel=sum(ins.dist[a,b] for a,b in zip(seq,seq[1:]))/p.speed
    return travel+sum(ins.nodes[n].service for n in trip),travel*p.flight_energy+sum(ins.nodes[n].energy for n in trip)

def summarize(ins, sol, allow_missing=False):
    p=ins.params;cost=sum(ins.fixed(k) for k in sol['station_types']); times={}; stats={};seen=Counter();valid=True
    for si,drones in enumerate(sol['routes']):
        kind=sol['station_types'][si]
        for di,trips in enumerate(drones):
            total=0.0
            for ti,trip in enumerate(trips):
                if not trip:continue
                if not kind or (kind==1 and di==0):valid=False
                for n in trip:
                    if n not in ins.target_ids:return math.inf,False,{},{}
                    seen[n]+=1
                    if ins.gdist[ins.stations[si].id,n]>ins.radius(kind)+1e-7:valid=False
                duration,energy=trip_stats(ins,si,trip);stats[si,di,ti]=(duration,energy);total+=duration
                if energy>ins.capacity(di)+1e-7:valid=False
            times[si,di]=total;cost+=total*p.time_cost
            if kind and total>ins.duration(kind)+1e-7:valid=False
    if any(v>1 for v in seen.values()):valid=False
    if not allow_missing and set(seen)!=set(ins.target_ids):valid=False
    return cost,valid,times,stats
