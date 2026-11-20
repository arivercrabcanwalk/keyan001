"""Run a selected package in isolation, then freeze its endpoints on Grok's packaged maps."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import runpy
import sys

def select(rows, profile):
    groups=defaultdict(list)
    for r in rows:
        file=Path(r["path"]).stem
        s,n,_=map(int,file.split("_"))
        if r["method"]!="tsalns" or r["sec"]!=10:raise ValueError("unexpected repository reference source")
        groups[(s,n)].append(r)
    # Predetermined by map identity, never reward. Larger profile includes every size family.
    keys=sorted(groups)
    if not keys:raise ValueError("empty original test registry")
    return [r for k in (keys[:1] if profile=="quick" else keys)
            for r in sorted(groups[k],key=lambda v:v["solution"]["instance_sha256"])[:1 if profile=="quick" else 2]]

def original(stage,out,device,profile):
    from rlcore.common import load_plans
    from rlcore.scen import make_env
    from rlcore.model import Policy
    from rlcore import policies,event_learning as learn
    import torch
    torch.set_num_threads(1)
    target=out/"original_maps"; target.mkdir(exist_ok=False)
    cases=select(load_plans("data/plans/test_ts.jsonl"),profile)
    scenarios=(("weather_wind","weather_storm") if stage=="A-weather" else tuple(
        "emerg_"+p+"_"+l for p in ("random","clustered") for l in ("low","mid","high")))
    days=(91001,) if profile=="quick" else (91001,91002)
    models={}; hashes={}
    for name in ("bc","pg"):
        path=out/(name+".pt")
        ck=torch.load(path,map_location="cpu",weights_only=True)
        m=Policy(**ck["arch"]).to(device);m.load_state_dict(ck["model"]);m.eval()
        models[name]=m
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    methods=("reference_order","greedy","local_reopt","frozen_bc","pg")
    plan=dict(dataset="grok_packaged_test_maps",source="nominal TSALNS 10-second stored plans, NOT fixed-wind author solutions",
        scenario=list(scenarios),days=days,weights=hashes,methods=methods,selection="size family then ascending map hash",
        maps=[dict(path=r["path"],sha256=r["solution"]["instance_sha256"]) for r in cases],
        fresh=False,training=False,formal=False)
    (target/"design.json").write_text(json.dumps(plan,indent=2)+"\n")
    count=0
    with (target/"evaluation.jsonl").open("x") as f:
        for r in cases:
            for s in scenarios:
                for day in days:
                    world=None
                    for method in methods:
                        env=make_env(r,day,s)
                        if stage=="A-weather" and (env.wx is None or env.requests):raise RuntimeError("wrong A inputs")
                        if stage=="B" and env.wx is not None:raise RuntimeError("wind in B")
                        if world is not None and world!=env.scenario_input_hash:raise RuntimeError("paired world changed")
                        world=env.scenario_input_hash
                        if method in ("frozen_bc","pg"):
                            actor=learn.TensorRoutePolicy(models["bc" if method=="frozen_bc" else "pg"],device)
                        elif method=="local_reopt":actor=policies.Reopt(budget_s=.01 if stage=="B" else .03)
                        else:actor=policies.make("A1" if method=="reference_order" else "GREEDY")
                        result=learn.rollout(env,actor).metrics
                        f.write(json.dumps(dict(split="public_transfer",scenario=s,day=day,
                            map_sha256=r["solution"]["instance_sha256"],method=method,metrics=result),allow_nan=False)+"\n")
                        f.flush();count+=1
    if count!=len(cases)*len(scenarios)*len(days)*len(methods):raise RuntimeError("incomplete transfer evaluation")
    (target/"summary.json").write_text(json.dumps(dict(rows=count,source=plan["source"],formal=False))+"\n")
    print("Original-map evaluation:",stage,count,target,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=["A-fixed","A-weather","B"])
    p.add_argument("--out",type=Path,required=True);p.add_argument("--seed",type=int,required=True)
    p.add_argument("--device",required=True);p.add_argument("--profile",required=True)
    a=p.parse_args()
    package=Path(__file__).resolve().parents[1]/("rlv3_emergency" if a.stage=="B" else "rlv3_weather")
    if Path.cwd().resolve()!=package:raise ValueError("unexpected working directory")
    sys.path.insert(0,str(package))
    mod={"A-fixed":"explore_weather","A-weather":"explore_dynamic_weather","B":"explore_emergency"}[a.stage]
    sys.argv=["rlcore."+mod,*sys.argv[2:]]
    try: runpy.run_module("rlcore."+mod,run_name="__main__")
    except SystemExit as e:
        if e.code not in (None,0): raise
    if a.stage!="A-fixed":original(a.stage,a.out,a.device,a.profile)
