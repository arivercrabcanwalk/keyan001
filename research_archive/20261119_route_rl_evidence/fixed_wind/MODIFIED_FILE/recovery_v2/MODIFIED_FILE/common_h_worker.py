"""Fixed three-H independent control; one full-map end-to-end deadline."""
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json
import os
import socket
import sys
import time

assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(BASE/'frozen'),str(BASE)]
from route_method import load_input,payload_for,write_json
from schedule_credit import Context
from baselines import wind_scorer
import independent_control as control

NAMESPACE='f3-g3-20261114-authorized-v1'
RHO=(1.0,.9,.8)

def run(instance,anchor,run_seed,*,started,budget,reserve=.25):
    if not 0<budget<float('inf') or not 0<=reserve<budget:
        raise ValueError('FINITE_BUDGET_AND_SMALLER_RESERVE_REQUIRED')
    end=started+budget-reserve
    search_start=time.perf_counter()
    banks=[[] for _ in instance.stations]
    seen=[set() for _ in banks]
    passes=[]
    for j,rho in enumerate(RHO):
        cutoff=search_start+(end-search_start)*(j+1)/len(RHO)
        seed_json=json.dumps({'schema':'f3_g3_common_h_pass_seed_v1','namespace':NAMESPACE,
                             'run_seed':run_seed,'pass_index':j},sort_keys=True,separators=(',',':'))
        seed=int.from_bytes(hashlib.sha256(seed_json.encode()).digest()[:8],'big')
        config={'base_seed':seed,'rounds':2**31-1,'max_evaluations_per_station':2**31-1,
                'operator_order':['rebalance','merge','relocate','swap','move_trip','split']}
        result=control.generate(instance,anchor,rho*anchor.makespan,config,deadline=cutoff)
        added=[]
        for si,bank in enumerate(result['banks']):
            n=0
            for old in bank:
                key=json.dumps(old['routes'],separators=(',',':'))
                if key in seen[si]:continue
                seen[si].add(key);row=deepcopy(old)
                row['id']=('S%d:anchor'%si if row['anchor'] else 'H%d:'%j+row['id'])
                banks[si].append(row);n+=1
            added.append(n)
        passes.append({'index':j,'rho':rho,'H':rho*anchor.makespan,'seed_u64':str(seed),
                       'absolute_cutoff':cutoff,'finished_at':time.perf_counter(),
                       'added_bank_rows':added,'station_searches':result['station_searches']})
    ctx=Context(banks,sum(instance.fixed(k) for k in anchor.station_types),instance.params.time_cost,anchor.cost)
    H,selected,cost=ctx.solve()
    solution=anchor.solution()
    for si,row in enumerate(selected):solution['routes'][si]=deepcopy(row['routes'])
    score=wind_scorer.validate_candidate(instance,solution,anchor)
    assert score['admissible'] and score['cost']==cost and score['M_return']<=H
    return solution,{'mode':'independent_three_H_union','rho':RHO,'passes':passes,'banks':banks,
                     'selected_ids':[r['id'] for r in selected],'selected_H':H,
                     'absolute_final_deadline':started+budget,'reserve_s':reserve,
                     'shared_parent_pool_used':False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--budget',type=float,required=True)
    parser.add_argument('--seed',type=int,required=True)
    args=parser.parse_args()
    bundle,instance,anchor,input_hash=load_input(args.bundle)
    started=float(os.environ['ROUTE_DELIVERY_STARTED'])
    solution,details=run(instance,anchor,args.seed,started=started,budget=args.budget)
    payload=payload_for(instance,anchor,solution,input_hash,'common_h')
    payload['details']=details
    payload['method_output_ready_elapsed_s']=time.perf_counter()-started
    write_json(args.result,payload)
    print('METHOD=common_h THREE_H_UNION=true COMPLETE_OUTPUT_DURABLE=true',flush=True)

if __name__=='__main__':main()
