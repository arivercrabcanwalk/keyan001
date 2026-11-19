"""Exact subset-DP verifier for small REAL LRPHSD instances (n <= 12).
Independent of TSALNS/greedy and cached optimizer objective; returns a complete
solution for the separate complete evaluator. Not the reproduced heuristic."""
from .problem import empty_solution
import math,time

def solve_exact(ins, max_targets=12):
    n=len(ins.targets)
    if n>max_targets:raise ValueError('exact verifier size limit exceeded')
    start=time.perf_counter();p=ins.params;N=1<<n;full=N-1
    service=[0.0]*N;se=[0.0]*N
    for mask in range(1,N):
        b=mask & -mask;j=b.bit_length()-1;service[mask]=service[mask^b]+ins.targets[j].service;se[mask]=se[mask^b]+ins.targets[j].energy
    records=[]
    for si,station in enumerate(ins.stations):
        # Direct geometry, not the optimization-side cached distance matrix.
        origin=[math.hypot(t.x-station.x,t.y-station.y)/p.speed for t in ins.targets]
        between=[[math.hypot(a.x-b.x,a.y-b.y)/p.speed for b in ins.targets] for a in ins.targets]
        path=[[math.inf]*n for _ in range(N)];parent={};lasts=[-1]*N;tour=[math.inf]*N;tour[0]=0.0
        for j in range(n):path[1<<j][j]=origin[j]
        for mask in range(1,N):
            bits=[j for j in range(n) if mask>>j&1]
            for j in bits:
                previous=mask^(1<<j)
                if previous:
                    k=min((k for k in bits if k!=j),key=lambda k:path[previous][k]+between[k][j])
                    path[mask][j]=path[previous][k]+between[k][j];parent[mask,j]=k
            last=min(bits,key=lambda j:path[mask][j]+origin[j]);lasts[mask]=last;tour[mask]=path[mask][last]+origin[last]
        partition=[];choices=[]
        for capacity in (p.large_battery,p.small_battery):
            dp=[math.inf]*N;dp[0]=0.0;ch=[0]*N
            trip_ok=[tour[m]*p.flight_energy+se[m]<=capacity+1e-9 for m in range(N)]
            for mask in range(1,N):
                first=mask & -mask;sub=mask
                while sub:
                    if sub & first and trip_ok[sub]:
                        value=tour[sub]+service[sub]+dp[mask^sub]
                        if value<dp[mask]:dp[mask]=value;ch[mask]=sub
                    sub=(sub-1)&mask
            partition.append(dp);choices.append(ch)
        coverage={kind:sum(1<<j for j,t in enumerate(ins.targets) if math.hypot(t.x-station.x,t.y-station.y)<=(p.small_radius if kind==1 else p.large_radius)+1e-7) for kind in (1,2)}
        option=[None]*N;option[0]=(0.0,0,0,0)
        for mask in range(1,N):
            if mask & ~coverage[1]==0 and partition[1][mask]<=p.small_duration+1e-9:
                option[mask]=(p.small_station_cost+p.small_drone_cost+p.time_cost*partition[1][mask],1,0,mask)
            if mask & ~coverage[2]==0:
                large=mask
                while True:
                    small=mask^large
                    if partition[0][large]<=p.large_duration+1e-9 and partition[1][small]<=p.large_duration+1e-9:
                        cost=p.large_station_cost+p.large_drone_cost+p.small_drone_cost+p.time_cost*(partition[0][large]+partition[1][small])
                        if option[mask] is None or cost<option[mask][0]:option[mask]=(cost,2,large,small)
                    if not large:break
                    large=(large-1)&mask
        records.append((option,choices,lasts,parent))
    dp={0:0.0};history=[]
    for si,(options,*_) in enumerate(records):
        new={};pred={}
        for assigned,cost in dp.items():
            rest=full^assigned;sub=rest
            while True:
                option=options[sub]
                if option is not None:
                    key=assigned|sub;value=cost+option[0]
                    if value<new.get(key,math.inf):new[key]=value;pred[key]=(assigned,sub)
                if not sub:break
                sub=(sub-1)&rest
        history.append(pred);dp=new
    if full not in dp:raise ValueError('no feasible complete solution')
    station_masks=[0]*len(ins.stations);mask=full
    for si in reversed(range(len(ins.stations))):mask,station_masks[si]=history[si][mask]
    sol=empty_solution(ins,[records[si][0][mask][1] for si,mask in enumerate(station_masks)])
    for si,mask in enumerate(station_masks):
        options,choices,lasts,parent=records[si];option=options[mask]
        for di,assigned in enumerate(option[2:]):
            while assigned:
                sub=choices[di][assigned];assert sub
                sequence=[];cur=sub;j=lasts[sub]
                while cur:
                    sequence.append(ins.targets[j].id);prev=cur^(1<<j)
                    if not prev:break
                    j=parent[cur,j];cur=prev
                sol['routes'][si][di].append(sequence[::-1]);assigned^=sub
    return sol,{'method':'exact_subset_dynamic_programming','optimal_objective':dp[full],'elapsed_seconds':time.perf_counter()-start,'targets':n}
