"""Part A: online routine tower inspection in changing wind; never creates urgent jobs.

Synthetic forecast/truth, fixed nominal deployment, public forecasts only. Both
weather conditions use the same evaluation maps but are different distributions:
wind vs forced storm is not a causal estimate of the effect of no-fly cells.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

import torch

from . import event_learning as learn, policies
from .common import seed_all
from .explore_weather import build_population, CORPUS_SEED
from .model import Policy
from .scen import make_env

CONDITIONS=("weather_wind","weather_storm")
METHODS=("reference_order","greedy","local_reopt","frozen_bc","pg")
CONFIG=dict(quick=dict(bc_worlds=3,bc_epochs=2,pg_steps=3,rollouts=3,eval_maps=2,eval_days=1,d=32,layers=1),
            standard=dict(bc_worlds=32,bc_epochs=4,pg_steps=48,rollouts=4,eval_maps=16,eval_days=2,d=64,layers=2))

def env_for(row,day,scen):
    if scen not in ("weather",*CONDITIONS):
        raise ValueError("Part A requires a wind scenario")
    env=make_env(row,day,scen)
    if env.wx is None or env.requests:
        raise ValueError("dynamic A: weather required, urgent tasks forbidden")
    return env

def put(path,x):
    path.write_text(json.dumps(x,allow_nan=False,ensure_ascii=False,indent=2)+"\n")

def aggregates(rows):
    out={}
    for s in CONDITIONS:
        for m in METHODS:
            sub=[r for r in rows if r["scenario"]==s and r["method"]==m]
            passed=[r["metrics"] for r in sub if r["metrics"]["complete_strict"] and not r["metrics"]["fallback"]]
            n=len(sub)
            out[s+"/"+m]=dict(cases=n,complete=len(passed),mean_J_all=sum(r["metrics"]["J"] for r in sub)/n,
                mean_M_complete_only=sum(r["M_return"] for r in passed)/len(passed) if passed else None,
                routine_unserved=sum(r["metrics"]["unserved"] for r in sub),
                failed_drones=sum(r["metrics"]["failed"] for r in sub))
    return out

def run(out,seed,device,profile):
    if not out.is_absolute(): raise ValueError("absolute out required")
    out.mkdir(parents=True,exist_ok=False)
    cfg=CONFIG[profile]; seed_all(seed); torch.set_num_threads(1)
    pop,_=build_population(out,seed=CORPUS_SEED,profile=profile)
    maps={s:[r for r,condition,_ in vals if condition=="fixed_e4"] for s,vals in pop.items()}
    put(out/"config.json",dict(seed=seed,corpus_seed=CORPUS_SEED,config=cfg,device=device,
        conditions=CONDITIONS,train_distribution="weather (mix)",methods=METHODS,
        reference="same synthetic deployment initialized from E4 singleton order, not author TSALNS",
        holdout_rule="fixed final BC and PG; no validation choice",formal=False))
    def factory(idx,start):
        rs=maps["train"]
        return env_for(rs[idx%len(rs)],start+idx//len(rs),"weather")
    arch=dict(d=cfg["d"],heads=4,layers=cfg["layers"])
    model=Policy(**arch).to(device)
    data,teacher=learn.collect_bc(lambda i:factory(i,1000000),policies.make("GREEDY"),cfg["bc_worlds"])
    bc_records=learn.fit_bc(model,data,cfg["bc_epochs"],device=device,seed=seed)
    bc_sha=learn.parameter_sha(model)
    torch.save(dict(model=model.state_dict(),arch=arch,seed=seed,stage="bc"),out/"bc.pt")
    pg=copy.deepcopy(model)
    with (out/"training.jsonl").open("x") as f:
        def log(r):
            f.write(json.dumps(r,allow_nan=False)+"\n"); f.flush()
        for r in bc_records:log(r)
        pg_records=learn.train_pg(pg,lambda i:factory(i,2000000),cfg["pg_steps"],cfg["rollouts"],
            device=device,seed=seed,on_record=log)
    if learn.parameter_sha(model)!=bc_sha: raise RuntimeError("frozen BC changed")
    pg_sha=learn.parameter_sha(pg)
    torch.save(dict(model=pg.state_dict(),arch=arch,seed=seed,parent=bc_sha,stage="pg"),out/"pg.pt")
    eval_rows=[]
    with (out/"evaluation.jsonl").open("x") as f:
        for row in maps["test"][:cfg["eval_maps"]]:
            for scen in CONDITIONS:
                for day in range(90000,90000+cfg["eval_days"]):
                    world=None
                    for method in METHODS:
                        env=env_for(row,day,scen)
                        policy=(learn.TensorRoutePolicy(model if method=="frozen_bc" else pg,device)
                            if method in ("frozen_bc","pg") else policies.make(
                                {"reference_order":"A1","greedy":"GREEDY","local_reopt":"REOPT"}[method]))
                        result=learn.rollout(env,policy).metrics
                        if result["n_urgent"] or (world and world!=result["input_sha256"]):
                            raise RuntimeError("scenario contamination or unequal exogenous input")
                        world=result["input_sha256"]
                        item=dict(split="test",method=method,scenario=scen,day=day,
                                  map_sha256=row["solution"]["instance_sha256"],metrics=result)
                        f.write(json.dumps(item,allow_nan=False)+"\n");f.flush()
                        eval_rows.append(item)
    expected=len(maps["test"][:cfg["eval_maps"]])*len(CONDITIONS)*cfg["eval_days"]*len(METHODS)
    if len(eval_rows)!=expected:raise RuntimeError("incomplete evaluation")
    put(out/"summary.json",dict(status="complete",formal=False,profile=profile,seed=seed,source="simulation",
        methods=METHODS,summary=aggregates(eval_rows),evaluation_rows=len(eval_rows),
        bc_optimizer_steps=sum(r["optimizer_steps"] for r in bc_records),pg_optimizer_steps=len(pg_records),
        pg_changed_updates=sum(r["parameters_changed"] for r in pg_records),bc_sha=bc_sha,pg_sha=pg_sha,
        note="No dynamic author cap: report all-cell penalized J, completion, then return time among completed routes."))
    print("A dynamic weather complete:",out,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile",choices=CONFIG,required=True);p.add_argument("--device",choices=["cpu","cuda"],required=True)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--seed",type=int,required=True)
    args=p.parse_args()
    run(args.out,args.seed,args.device,args.profile)
