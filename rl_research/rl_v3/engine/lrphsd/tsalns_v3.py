"""Source-matched round-3 engine; old v2 remains runnable and unchanged.
Candidate semantics use raw Java storage. Formal mode adds complete physical
acceptance checks and rolls back a failed/partial repair; trace mode may replay
the unguarded reference solely to locate semantic differences.
"""
import copy,math,time
from collections import Counter
from . import fidelity_ops as ops,greedy
from .java_random import JavaRandom
from .evaluator import evaluate

DEFAULT={'outer_iterations':500,'local_iterations':100,'alns_iterations':5000,'initial_temperature':1000.,'cooling_rate':.95,'final_temperature':.001,'weight_upper':5.}

def solve(ins,seed=0,seconds=None,config=None,events=None,removed_tape=None,physical_guard=True):
    config={**DEFAULT,**(config or {})};ins.dist=ops.source_distances(ins);rng=JavaRandom(seed);start=time.perf_counter();evaluations=0
    counters=Counter();timings=Counter();trace=[]
    def alive():return seconds is None or time.perf_counter()-start<seconds
    def cost(sol,fixed=True):
        nonlocal evaluations
        evaluations+=1
        value=0.0
        for si,s in enumerate(sol['routes']):
            if fixed:
                kind=sol['station_types'][si];p=ins.params
                if kind==2:value=value+p.large_station_cost+p.large_drone_cost+p.small_drone_cost
                elif kind==1:value+=p.small_station_cost+p.small_drone_cost
            for d in s:
                if fixed:value+=sum(ops.path_time(ins,si,t) for t in d)*ins.params.time_cost
                else:
                    for t in d:value+=ops.path_time(ins,si,t)*ins.params.time_cost
        return value
    def emit(stage,step,op,sol,**extra):
        if events is not None:
            events.append({'stage':stage,'step':step,'op':op,'random_calls':len(rng.draws),'state':{'station_types':sol['station_types'].copy(),'routes':copy.deepcopy(sol['routes'])},'evaluations':evaluations,**extra})
    def measured(name,fn,*args):
        t=time.perf_counter();value=fn(*args);timings[name]+=time.perf_counter()-t;counters[name]+=1;return value
    def physically_valid(sol,partial=False):
        if not physical_guard:return True
        t=time.perf_counter();result=evaluate(ins,ops.physical(sol),allow_missing=partial)['feasible'];timings['physical_guard']+=time.perf_counter()-t;counters['physical_guard']+=1
        return result
    current=measured('greedy',greedy.build,ins);initial=cost(current);current_cost=initial;best=ops.clone(current);best_cost=initial
    if not physically_valid(current):raise ValueError('initializer invalid under complete physical contract')
    emit('initial',0,-1,current);temperature=config['initial_temperature'];outer_done=0
    trace.append({'elapsed':time.perf_counter()-start,'cost':best_cost,'evaluations':evaluations})
    def alns(sol):
        nonlocal evaluations
        cur=ops.clone(sol);cur_cost=cost(cur,False);local_best=ops.clone(cur);local_cost=cur_cost
        temp=config['initial_temperature'];weights=[[1.]*4 for _ in range(2)];scores=[[0.]*4 for _ in range(2)];counts=[[0]*4 for _ in range(2)]
        for k in range(config['alns_iterations']):
            if not alive() or temp<=config['final_temperature']:break
            d,r=[rng.choices(range(4),w,k=1)[0] for w in weights]
            destroyed=measured('destroy',ops.destroy_candidate,ins,cur,d,rng)
            oldset={n for _,_,_,_,n in ops.positions(cur)};newset={n for _,_,_,_,n in ops.positions(destroyed)}
            removed=[n for n in ins.target_ids if n in oldset-newset]
            if removed_tape is not None:
                assert removed_tape,('removal_tape_exhausted',k)
                ordered=removed_tape.pop(0);assert set(ordered)==set(removed),('removed_set',ordered,removed);removed=ordered
            emit('destroy',k,d,destroyed,repair_op=r,removed=removed)
            candidate=measured('repair',ops.repair_candidate,ins,destroyed,removed,r)
            value=cost(candidate,False);improvement=local_cost-value
            accepted=value<cur_cost or rng.random()<math.exp((cur_cost-value)/temp)
            if not physically_valid(candidate):accepted=False;counters['candidate_guard_rejections']+=1
            emit('repair',k,r,candidate,accepted=accepted,temperature=temp,weights_d=weights[0].copy(),weights_r=weights[1].copy(),scores_d=scores[0].copy())
            counters['alns_candidates']+=1;counters['alns_accepted']+=accepted
            if accepted:
                cur=candidate;cur_cost=value
                if value<local_cost:local_best=ops.clone(candidate);local_cost=value;counters['alns_best_improved']+=1
            reward=(1.+(2.*improvement/(improvement+1) if improvement>0 else 0)) if accepted else -.2
            for group,index in enumerate((d,r)):scores[group][index]=.9*scores[group][index]+reward;counts[group][index]+=1
            if k%50==0:
                for group in range(2):
                    for j in range(4):
                        if counts[group][j]:weights[group][j]=max(.1,min(config['weight_upper'],weights[group][j]*.8+(scores[group][j]/counts[group][j])*.2))
                    scores[group]=[0.]*4;counts[group]=[0]*4
            temp*=config['cooling_rate']
        return local_best,local_cost
    for outer in range(config['outer_iterations']):
        if not alive():break
        outer_done=outer+1
        types=measured('location',ops.location,current['station_types'],rng)
        emit('location',outer,-1,{'station_types':types,'routes':current['routes']})
        try:candidate=measured('greedy',greedy.build,ins,types)
        except ValueError:counters['location_uncovered']+=1;continue
        if not ops.raw_valid(ins,candidate,time_check=False):continue
        for j in range(config['local_iterations']):
            if not alive():break
            op=rng.randrange(5);candidate=measured('local',ops.local_candidate,ins,candidate,op,rng)
            emit('local',j,op,candidate)
        emit('local_end',outer,-1,candidate)
        candidate,_=alns(candidate)
        value=cost(candidate);probability=1. if value<current_cost else math.exp((current_cost-value)/temperature)
        accepted=probability>rng.random()
        if not physically_valid(candidate):accepted=False;counters['outer_guard_rejections']+=1
        if accepted:
            current=candidate;current_cost=value
            if value<best_cost:
                best=ops.clone(candidate);best_cost=value;trace.append({'elapsed':time.perf_counter()-start,'cost':best_cost,'evaluations':evaluations})
        counters['outer_accepted']+=accepted
        emit('outer_end',outer,-1,current,current_cost=current_cost,best_cost=best_cost,temperature=temperature)
        temperature*=config['cooling_rate']
    final=ops.physical(best)
    emit('final',config['outer_iterations'],-1,best,best_cost=best_cost,budget_alive=alive())
    elapsed=time.perf_counter()-start
    return final,{'algorithm':'independent_tsalns_v3','seed':seed,'initial_objective':initial,'objective':best_cost,'evaluations':evaluations,'elapsed_seconds':elapsed,'outer_iterations_attempted':outer_done,'config':config,'physical_guard':physical_guard,'removed_order':'recorded_reference_tape' if removed_tape is not None else 'input_target_order; differs from unspecified Java identity-HashSet','trace':trace,'timings':dict(timings),'counters':dict(counters),'termination':'time_budget' if not alive() else 'configured_iterations','random_draws':len(rng.draws)}
