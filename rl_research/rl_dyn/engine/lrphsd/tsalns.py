"""Independent official-code-aligned TSALNS v2. No learned policy/operator selection.
Core: greedy location+routes; location neighborhoods; feasible swaps and improving 2-opt;
four destroy/four repair families; adaptive weights; simulated annealing.
Known differences from exact public Java routines are explicitly documented.
"""
import copy,math,random,time
from . import greedy
from .problem import normalized
from .metrics import summarize,trip_stats

class Budget:
    def __init__(self, seconds, max_evaluations=None):
        self.start=time.perf_counter();self.seconds=seconds;self.max_evaluations=max_evaluations;self.evaluations=0
    def alive(self):return (self.seconds is None or time.perf_counter()-self.start<self.seconds) and (self.max_evaluations is None or self.evaluations<self.max_evaluations)
    def assess(self, ins, sol, partial=False):
        self.evaluations+=1
        return summarize(ins,sol,partial)

def slots(sol):
    return [(si,di,ti,pos,n) for si,st in enumerate(sol['routes']) for di,trips in enumerate(st) for ti,trip in enumerate(trips) for pos,n in enumerate(trip)]

def insertion_options(ins, sol, nid, stats=None):
    _,_,times,route_stats=stats or summarize(ins,sol,True);p=ins.params;target=ins.nodes[nid];out=[]
    for si,kind in enumerate(sol['station_types']):
        if not kind:continue
        station=ins.stations[si].id
        if ins.dist[station,nid]>ins.radius(kind)+1e-7:continue
        for di in ((0,1) if kind==2 else (1,)):
            trips=sol['routes'][si][di];total=times[si,di]
            for ti,trip in enumerate(trips):
                prev_time,prev_energy=route_stats.get((si,di,ti),(0,0));seq=[station]+trip+[station]
                for pos,(a,b) in enumerate(zip(seq,seq[1:])):
                    fly=(ins.dist[a,nid]+ins.dist[nid,b]-ins.dist[a,b])/p.speed
                    dt=fly+target.service;de=fly*p.flight_energy+target.energy
                    if prev_energy+de<=ins.capacity(di)+1e-7 and total+dt<=ins.duration(kind)+1e-7:
                        out.append((dt*p.time_cost,si,di,ti,pos,total+dt))
            fly=2*ins.dist[station,nid]/p.speed;dt=fly+target.service
            if fly*p.flight_energy+target.energy<=ins.capacity(di)+1e-7 and total+dt<=ins.duration(kind)+1e-7:
                out.append((dt*p.time_cost,si,di,len(trips),0,total+dt))
    return out

def insert(sol, nid, option):
    _,si,di,ti,pos,_=option;trips=sol['routes'][si][di]
    if ti==len(trips):trips.append([nid])
    else:trips[ti].insert(pos,nid)

def remove(sol,nodes):
    removed=set(nodes)
    for station in sol['routes']:
        for di in range(2):station[di]=[[n for n in trip if n not in removed] for trip in station[di]]

def mutate_location(types,rng):
    out=types.copy();which=rng.randrange(4)
    if which==0 and len(out)>1:
        a,b=rng.sample(range(len(out)),2);out[a],out[b]=out[b],out[a]
    elif which==1:
        choices=[j for j,k in enumerate(out) if k<2]
        if choices:out[rng.choice(choices)]+=1
    elif which==2:
        choices=[j for j,k in enumerate(out) if k>0]
        if choices:out[rng.choice(choices)]-=1
    else:
        choices=[j for j,k in enumerate(out) if k>0]
        if choices:out[rng.choice(choices)]=0
    return out

def local_move(ins, sol, cost, rng, budget):
    which=rng.randrange(5);allslots=slots(sol)
    if which==4:
        candidate=copy.deepcopy(sol);changed=False
        for si,station in enumerate(candidate['routes']):
            for di,trips in enumerate(station):
                for ti,trip in enumerate(trips):
                    improved=True
                    while improved and budget.alive():
                        improved=False;depot=ins.stations[si].id
                        for a in range(len(trip)-1):
                            for b in range(a+1,len(trip)):
                                before=depot if a==0 else trip[a-1];after=depot if b+1==len(trip) else trip[b+1]
                                delta=ins.dist[before,trip[b]]+ins.dist[trip[a],after]-ins.dist[before,trip[a]]-ins.dist[trip[b],after]
                                if delta < -1e-8:
                                    trip[a:b+1]=trip[a:b+1][::-1];changed=True;improved=True;break
                            if improved:break
        if changed:
            value,valid,*_=budget.assess(ins,candidate)
            if valid and value<cost-1e-9:return candidate,value
        return sol,cost
    if len(allslots)<2:return sol,cost
    a=rng.choice(allslots);si,di,ti,pos,nid=a
    choices=[b for b in allslots if b!=a and ((b[:3]==a[:3]) if which==0 else ((b[:2]==a[:2] and b[2]!=ti) if which==1 else ((b[0]==si and b[1]!=di) if which==2 else b[0]!=si)))]
    if not choices:return sol,cost
    b=rng.choice(choices);candidate=copy.deepcopy(sol)
    candidate['routes'][si][di][ti][pos]=b[4];candidate['routes'][b[0]][b[1]][b[2]][b[3]]=nid
    value,valid,*_=budget.assess(ins,candidate)
    # Official swap1..4 accept any feasible swap; only 2-opt is improving.
    return (candidate,value) if valid else (sol,cost)

def destroy(ins, sol, which, rng):
    entries=slots(sol)
    if not entries:return []
    counts={}
    for si,di,ti,pos,n in entries:counts[si,di]=counts.get((si,di),0)+1
    eligible=[e for e in entries if counts[e[0],e[1]]>1]
    if which==2:return [rng.choice(eligible)[4]] if eligible else []
    if which==0:
        if not eligible:return []
        def saving(e):
            si,di,ti,pos,nid=e;trip=sol['routes'][si][di][ti];station=ins.stations[si].id
            a=station if pos==0 else trip[pos-1];b=station if pos+1==len(trip) else trip[pos+1]
            return (ins.dist[a,nid]+ins.dist[nid,b]-ins.dist[a,b])/ins.params.speed+ins.nodes[nid].service
        e=max(eligible,key=saving)
        # Public Java deliberately keeps a singleton trip when this is the
        # maximal-saving candidate; do not silently redesign that operator.
        return [e[4]] if len(sol['routes'][e[0]][e[1]][e[2]])>1 else []
    if which==1:
        selected=[]
        for si,station in enumerate(sol['routes']):
            for di,trips in enumerate(station):
                remaining=counts.get((si,di),0);depot=ins.stations[si].id
                for trip in trips:
                    if remaining<=1:break
                    candidates=[]
                    for pos,nid in enumerate(trip):
                        a=depot if pos==0 else trip[pos-1];b=depot if pos+1==len(trip) else trip[pos+1]
                        saving=ins.dist[a,nid]+ins.dist[nid,b]-ins.dist[a,b]
                        if saving>0:candidates.append((saving,pos,nid))
                    # Stable tie order matches scan order; probability is .7 in
                    # ALNSSolver.java, not an invented roulette distribution.
                    for saving,pos,nid in sorted(candidates,key=lambda v:-v[0]):
                        if rng.random()<=0.7:selected.append(nid);remaining-=1;break
        return selected
    candidates=[];weights=[]
    for si,di,ti,pos,nid in eligible:
        trip=sol['routes'][si][di][ti]
        if len(trip)<2:continue
        # In the public helper the current station is not excluded from
        # coverage tests, so both feasible nodes obtain lambda=.8.
        score=sum(0.8/max(ins.dist[nid,other],1e-6) for other in trip if other!=nid)
        if score>0:candidates.append(nid);weights.append(score)
    if not candidates:return []
    low,high=min(weights),max(weights)
    weights=[(1.0 if abs(high-low)<1e-9 else (v-low)/(high-low))+1e-6 for v in weights]
    return [rng.choices(candidates,weights=weights,k=1)[0]]

def repair(ins, sol, pending, which, budget=None):
    pending=list(pending)
    while pending:
        if budget is not None and not budget.alive():return False
        stats=summarize(ins,sol,True)
        nid=pending[0];available=insertion_options(ins,sol,nid,stats)
        if not available:return False
        if which in (0,1):
            # Java minimumRegret chooses min(delta - second_min_delta).
            # The subtracted term is constant across candidates: this is
            # sequential minimum-delta, NOT standard cross-node 2-regret.
            existing=[v for v in available if v[3]<len(sol['routes'][v[1]][v[2]])]
            option=min(existing or available)
        else:
            def score(v):
                delta,si,di,ti,pos,after=v;limit=ins.duration(sol['station_types'][si])
                return 0.6*(limit-after)/limit+0.4/(1+abs(delta))
            if which==3:
                empty_stations=[v for v in available if not any(sol['routes'][v[1]][d] for d in (0,1))]
                empty_drones=[v for v in available if not sol['routes'][v[1]][v[2]]]
                existing=[v for v in available if v[3]<len(sol['routes'][v[1]][v[2]])]
                available=empty_stations or empty_drones or existing or available
            option=max(available,key=score)
        insert(sol,nid,option);pending.remove(nid)
    return True

def alns(ins, sol, rng, budget, config):
    current=copy.deepcopy(sol);cost=budget.assess(ins,current)[0];best=copy.deepcopy(current);best_cost=cost
    temp=config['initial_temperature'];weights=[[1.0]*4 for _ in range(2)];scores=[[0.0]*4 for _ in range(2)];counts=[[0]*4 for _ in range(2)]
    for k in range(config['alns_iterations']):
        if not budget.alive() or temp<=config['final_temperature']:break
        d,r=(rng.choices(range(4),weights=w,k=1)[0] for w in weights)
        candidate=copy.deepcopy(current);pending=destroy(ins,candidate,d,rng);remove(candidate,pending)
        if not repair(ins,candidate,pending,r,budget):temp*=config['cooling_rate'];continue
        value,valid,*_=budget.assess(ins,candidate);improvement=best_cost-value
        accepted=valid and (value<cost or rng.random()<math.exp(min(0,(cost-value)/max(temp,1e-12))))
        reward=(1.0+(2.0*improvement/(1+improvement) if improvement>0 else 0)) if accepted else -0.2
        if accepted:
            current=candidate;cost=value
            if cost<best_cost-1e-9:best=copy.deepcopy(current);best_cost=cost
        for group,j in enumerate((d,r)):scores[group][j]=0.9*scores[group][j]+reward;counts[group][j]+=1
        # Java updates at iter 0, then 50,100,... (counter begins at 5000).
        if k%50==0:
            for group in range(2):
                for j in range(4):
                    if counts[group][j]:weights[group][j]=max(0.1,min(config['weight_upper'],0.8*weights[group][j]+0.2*scores[group][j]/counts[group][j]))
                scores[group]=[0.0]*4;counts[group]=[0]*4
        temp*=config['cooling_rate']
    return best,best_cost

DEFAULT={'outer_iterations':500,'local_iterations':100,'alns_iterations':5000,'initial_temperature':1000.0,'cooling_rate':0.95,'final_temperature':0.001,'weight_upper':5.0}

def solve(ins, seed=0, seconds=2.0, max_evaluations=None, config=None):
    config={**DEFAULT,**(config or {})};rng=random.Random(seed);budget=Budget(seconds,max_evaluations)
    current=greedy.build(ins);cost,valid,*_=budget.assess(ins,current);fallback=False
    if not valid:
        # Preserve invalid raw initializer as evidence, but never reward it.
        current=greedy.build(ins,[2]*len(ins.stations));cost,valid,*_=budget.assess(ins,current);fallback=True
    if not valid:raise ValueError('initial cumulative-time feasibility failed; explicit repair required')
    best=copy.deepcopy(current);best_cost=cost;initial_cost=cost;trace=[{'elapsed':time.perf_counter()-budget.start,'cost':cost,'evaluations':budget.evaluations}];temp=config['initial_temperature'];outer=0
    for outer in range(config['outer_iterations']):
        if not budget.alive():break
        types=mutate_location(current['station_types'],rng)
        try:candidate=greedy.build(ins,types)
        except ValueError:continue
        value,valid,*_=budget.assess(ins,candidate)
        if not valid:continue
        for _ in range(config['local_iterations']):
            if not budget.alive():break
            candidate,value=local_move(ins,candidate,value,rng,budget)
        if budget.alive():candidate,value=alns(ins,candidate,rng,budget,config)
        value,valid,*_=budget.assess(ins,candidate)
        if valid and (value<cost or rng.random()<math.exp(min(0,(cost-value)/max(temp,1e-12)))):
            current=candidate;cost=value
            if cost<best_cost-1e-9:
                best=copy.deepcopy(current);best_cost=cost;trace.append({'elapsed':time.perf_counter()-budget.start,'cost':cost,'evaluations':budget.evaluations})
        temp*=config['cooling_rate']
    return normalized(best),{'algorithm':'independent_tsalns_v2','seed':seed,'objective':best_cost,'initial_objective':initial_cost,'evaluations':budget.evaluations,'elapsed_seconds':time.perf_counter()-budget.start,'outer_iterations_attempted':outer+1,'budget_seconds':seconds,'initializer_feasibility_fallback':fallback,'trace':trace,'config':config}
