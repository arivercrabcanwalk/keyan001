"""Approved DEVELOPMENT campaign. Do not expose archived maps or treat pilot statistics as Formal."""
from contextlib import contextmanager
import argparse
import fcntl
import glob
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from rlcore import registration as R
from rlcore.common import load_plans, rel
from rlcore.scen import SCENARIOS, DEV_DAYS, TRAIN_DAY0
from rlcore.evaluate import parse_days


def geom(path):
    from lrphsd.problem import read_instance
    ins=read_instance(path)
    # Translation, row order and node renumbering alone cannot create a fresh identity.
    all_nodes=ins.targets+ins.stations
    x0=min(n.x for n in all_nodes); y0=min(n.y for n in all_nodes)
    def nodes(pool):
        return sorted((n.x-x0,n.y-y0,n.energy,n.service) for n in pool)
    return R.digest([nodes(ins.targets),nodes(ins.stations)])


def freeze_inputs(cfg):
    package=HERE.name
    if cfg.get("phase")!="development" or cfg.get("package")!=package:
        raise ValueError("a separate development ticket for this package is required")
    if cfg.get("device") not in ("cpu","cuda","auto"): raise ValueError("invalid device registration")
    if cfg["device"]=="cuda":
        import torch
        if not torch.cuda.is_available(): raise ValueError("registered CUDA unavailable")
    kind="wx" if package=="rlv3_weather" else "urg"
    scenarios=cfg["evaluation"]
    if (not isinstance(scenarios,list) or not R.unique(scenarios) or
            cfg.get("primary_condition") not in scenarios):
        raise ValueError("register one primary condition and unique evaluation conditions before training")
    if not scenarios or not all(s in SCENARIOS and SCENARIOS[s]["kind"]==kind for s in scenarios+[cfg["train_scenario"]]):
        raise ValueError("cross-paper or unsupported scenario")
    if any(SCENARIOS[s].get("engineering_only") for s in scenarios+[cfg["train_scenario"]]):
        raise ValueError("engineering-only intervention is not admitted to a scientific pilot")
    days=parse_days(cfg["eval_days"])
    if not R.unique(days) or min(days)<0 or max(days)>=TRAIN_DAY0 or set(days)&set(DEV_DAYS):
        raise ValueError("evaluation days overlap training/validation or are invalid")
    seeds=cfg["seeds"]
    if not R.unique(seeds) or len(seeds)<3 or any(type(s) is not int or s<0 for s in seeds):
        raise ValueError("at least 3 distinct independent training seeds")
    for key in ("train_hours","rl_hours","episode_wall_s","campaign_hours"):
        if not R.finite(cfg[key]) or not cfg[key]>0:
            raise ValueError("invalid registered limit "+key)
    if (not isinstance(cfg["comparators"],list) or set(cfg["comparators"])!={"A1","GREEDY","REOPT"}
            or not isinstance(cfg.get("mechanism_receipt"),str) or not isinstance(cfg.get("comparison_receipt"),str)):
        raise ValueError("G0/G3 receipts and prespecified strong comparators required")
    if cfg.get("primary_reference") not in ("REOPT","REOPT-T","TUNED_OVERALL"):
        raise ValueError("primary comparison must be declared against REOPT or the prospectively selected tuned baseline")
    if set(cfg.get("cost_manifests",{}))!=set(scenarios):
        raise ValueError("per-condition registered budgets or full same-wind anchor inputs required")
    rec={}
    for key in ("mechanism_receipt","comparison_receipt","population_registry"):
        fi=Path(cfg[key])
        if not fi.is_file() or fi.stat().st_size==0: raise ValueError("missing "+key)
        rec[key]=R.file_sha(fi)
    for field, gate in [("mechanism_receipt","G0"),("comparison_receipt","G3")]:
        receipt=json.loads(Path(cfg[field]).read_text())
        if (receipt.get("gate")!=gate or receipt.get("status")!="APPROVED_FOR_DEVELOPMENT"
                or receipt.get("package")!=package or set(receipt.get("conditions",[]))!=set(scenarios)
                or receipt.get("ticket_id")!=cfg.get("ticket_id") or not cfg.get("ticket_id")
                or receipt.get("approved_machine_sha256")!=cfg.get("approved_machine_sha256")
                or not receipt.get("reviewer") or not receipt.get("decision_basis")):
            raise ValueError("missing or wrong scoped development admission "+gate)
    for sc,path in cfg["cost_manifests"].items():
        rec["cost:"+sc]=R.file_sha(Path(path))
    population=json.loads(Path(cfg["population_registry"]).read_text())
    excluded=set(population["excluded_raw"]); excluded_g=set(population["excluded_geometry"])
    if not excluded or not excluded_g or population.get("reviewed_prior_exposure") is not True:
        raise ValueError("prior exposure exclusion registry required")
    # Reject all identities shipped as old train/dev/test/fresh, regardless of file renaming.
    for old in (HERE/"data/instances").glob("*/*.txt"):
        excluded.add(R.file_sha(old));excluded_g.add(geom(old))
    from .common import plan_layout, load_ins
    allraw=set(); allgeo=set(); sourcefiles={}; same_nominal={}; split_author={}
    fixed_conditions={"nowind","fixed_e4","fixed_n8"}
    fixed_selection=kind=="wx" and cfg["train_scenario"] in fixed_conditions
    selection=cfg.get("selection_anchor_manifests",{})
    if set(selection) != ({"train_plans","val_plans"} if fixed_selection else set()):
        raise ValueError("register same-wind train/validation author manifests for fixed-wind training only")
    for split in ("train_plans","val_plans","pilot_plans"):
        # A fixed-wind pilot can have a different same-wind author layout per condition.
        paths=cfg[split]
        if split=="pilot_plans":
            if set(paths)!=set(scenarios): raise ValueError("provide an anchor file per registered condition")
            paths=list(dict.fromkeys(paths.values()))
        else: paths=[paths]
        raw_split={}; geo_split={}; condition_maps=None
        for path in paths:
            rr=load_plans(path); raw=set(); geos=set()
            if split!="pilot_plans" and fixed_selection:
                from .fixed_anchor import bind_split_anchors
                manifest=Path(selection[split])
                sourcefiles[str(manifest)]=R.file_sha(manifest)
                split_author[split]=bind_split_anchors(rr,manifest,cfg["train_scenario"])
            nominal=(split!="pilot_plans" and not fixed_selection) or (split=="pilot_plans" and
                     any(sc not in fixed_conditions for sc,p in cfg["pilot_plans"].items() if p==path))
            for row in rr:
                f=Path(rel(row["path"])); h=R.file_sha(f); g=geom(f)
                if row["solution"].get("instance_sha256")!=h or h in raw or g in geos or h in excluded or g in excluded_g:
                    raise ValueError("mismatched, duplicate or exposed population: "+str(f))
                raw.add(h);geos.add(g);sourcefiles[str(f)]=h
                if nominal:
                    plan_layout(load_ins(str(f)),row["solution"])
                    if split=="pilot_plans":
                        sol_sha=R.digest(row["solution"])
                        if same_nominal.setdefault(h,sol_sha)!=sol_sha:
                            raise ValueError("nominal deployment changed between paired pilot conditions: "+str(f))
                raw_split[h]=True;geo_split[g]=True
            if condition_maps is not None and raw!=condition_maps:
                raise ValueError("pilot conditions must share exactly the same base maps")
            condition_maps=raw
            sourcefiles[str(Path(rel(path)))]=R.file_sha(Path(rel(path)))
        expected=population["expected_raw"][split]
        if (not isinstance(expected,list) or len(expected)!=len(set(expected))
                or not expected or set(expected)!=set(raw_split)):
            raise ValueError("missing/extra/duplicate maps relative to the independent population roster: "+split)
        if set(raw_split)&allraw or set(geo_split)&allgeo: raise ValueError("map leakage between splits")
        allraw.update(raw_split); allgeo.update(geo_split)
    # Before spending compute, check every condition's actual anchor/cap and
    # generated input identity. Do not discover invalid paperwork after training.
    from .scen import scenario_input_hash
    check_sources={}
    for sc in scenarios:
        dates=[0] if sc in {"nowind","fixed_e4","fixed_n8"} else days
        body=R.make_manifest(load_plans(cfg["pilot_plans"][sc]),dates,[("REOPT","REOPT")],sc,
                cfg["episode_wall_s"],"REOPT",SCENARIOS,scenario_input_hash,
                json.loads(Path(cfg["cost_manifests"][sc]).read_text()))
        check_sources[sc]=R.digest(body["maps"])
    from importlib.metadata import version
    versions={pkg:version(pkg) for pkg in ("torch","numpy","scipy")}
    code=sorted((HERE/"rlcore").glob("*.py"))+sorted((HERE/"vendor/lrphsd").glob("*.py"))
    return dict(ticket=cfg,receipts=rec,sources=sourcefiles,selection_anchors=split_author,registered_inputs=check_sources,software=versions,python=sys.version,
                platform=platform.platform(), code=R.digest([(p.relative_to(HERE).as_posix(),R.file_sha(p)) for p in code]))


@contextmanager
def resource_lock():
    # One host-wide campaign per user: no competing GPU jobs between these two packages.
    import tempfile
    with open(Path(tempfile.gettempdir())/f"rlv3-hn01-{os.getuid()}.lock","a+") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def supervise(argv,log,remaining,accepted=(0,)):
    if remaining<=0: raise TimeoutError("campaign budget exhausted")
    with log.open("wb") as f:
        proc=subprocess.Popen(argv,cwd=HERE,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            rc=proc.wait(timeout=remaining)
        except BaseException:
            try: os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
            raise
    if rc not in accepted: raise RuntimeError(f"stage exit {rc}; see {log}")
    return rc


def run(cfg,cfg_path,out,workers,*,preflight_only=False):
    machine=Path("/etc/machine-id")
    from hashlib import sha256
    if (cfg.get("site")!="hn01" or not machine.is_file()
            or sha256(machine.read_bytes()).hexdigest()!=cfg.get("approved_machine_sha256")):
        raise ValueError("not the hn01 machine registered in the development ticket")
    if workers<=0: raise ValueError("workers must be positive")
    with resource_lock():
        preflight_start=time.monotonic()
        sealed=freeze_inputs(cfg)
        out.mkdir(parents=True,exist_ok=True)
        impl=R.freeze(out/"freeze.json",dict(schema="rlv3-paired-pilot-v2", role="development_campaign",workers=workers,**sealed))
        limit=cfg["campaign_hours"]*3600
        # Log and debit successful input/host preflight on every resume. External
        # scheduler records rejected invocations as well.
        preflight=out/"preflight-time.json"
        history=json.loads(preflight.read_text()) if preflight.exists() else []
        history.append(time.monotonic()-preflight_start)
        R.publish(preflight,history)
        if preflight_only:
            print("PREFLIGHT VERIFIED:",out/"freeze.json","; no training or evaluation")
            return
        started=time.monotonic()
        ledger=out/"stages.json"
        prior=json.loads(ledger.read_text()) if ledger.exists() else {}
        if any(v["status"]!="OK" for v in prior.values()):
            raise ValueError("unfinished/failed attempt retained; investigate before registering a recovery ticket")
        used=sum(v["wall_s"] for v in prior.values())+sum(history)
        def stage(name,script,flags,products,accepted=(0,)):
            argv=[sys.executable,"-B",str(HERE/"rlcore"/script),*map(str,flags)]
            stamp=R.digest([impl["sha256"],name,argv])
            if name in prior:
                old=prior[name]
                if old["stamp"]!=stamp or any(not p.is_file() or R.file_sha(p)!=old["outputs"].get(str(p)) for p in products):
                    raise ValueError("resume identity/artifact drift: "+name)
                return old["exit_status"]
            t=time.monotonic()
            prior[name]=dict(stamp=stamp,status="STARTED",command=argv,wall_s=0)
            R.publish(ledger,prior)
            try:
                rc=supervise(argv,out/(name+".log"),limit-used-(t-started),accepted)
                shas={str(p):R.file_sha(p) for p in products}
                prior[name].update(status="OK",exit_status=rc,outputs=shas)
                return rc
            except BaseException as e:
                prior[name].update(status="FAILED",reason=repr(e))
                raise
            finally:
                prior[name]["wall_s"]=time.monotonic()-t
                R.publish(ledger,prior)
        sc=cfg["train_scenario"]; tuned=out/"tuned.json"; seeds=cfg["seeds"]
        stage("tune","tune.py",["--plans",cfg["val_plans"],"--scen",sc,"--days",len(DEV_DAYS),"--maps",
              len(load_plans(cfg["val_plans"])),"--workers",workers,"--out",tuned],[tuned])
        from .tune import require_tuned_reference
        teach=require_tuned_reference(json.loads(tuned.read_text()),sc,cfg["primary_reference"])
        arms=["A1=A1","GREEDY=GREEDY","REOPT=REOPT","tuned:"+str(tuned),"TUNED_OVERALL="+teach]
        for s in seeds:
            for arm,extra in [("RL",[]),("STANDARD",["--no_bc","--no_base","--feat_ablate","noplan"]),
                              ("NO_HINT",["--no_base"]),("NO_PHYS",["--feat_ablate","nophys"])]:
                if arm=="NO_PHYS" and HERE.name=="rlv3_emergency": continue
                train_out=out/f"{arm}_s{s}"
                params=["--plans",cfg["train_plans"],"--dev_plans",cfg["val_plans"],"--out",train_out,
                        "--scen",sc,"--seed",s,"--teacher",teach,"--device",cfg["device"],
                        "--workers",workers,"--dev_maps",len(load_plans(cfg["val_plans"])),
                        "--dev_days",len(DEV_DAYS),"--no_ri","--ent",0,"--total_hours",cfg["train_hours"],
                        "--rl_hours",cfg["rl_hours"],*extra]
                ck=train_out/"best.pt"; other=train_out/("init.pt" if arm=="STANDARD" else "bc.pt")
                stage(f"{arm}_s{s}","train.py",params,[ck,other,train_out/"done.json"])
                training=json.loads((train_out/"done.json").read_text())
                if training.get("pg_optimizer_steps",0)<1:
                    raise ValueError(f"{arm}_s{s}: no complete policy-gradient update; attempt retained")
                arms.append(f"{arm}_s{s}=rl:{ck}")
                if arm=="RL": arms.append(f"BC_s{s}=rl:{other}")
                if arm=="STANDARD": arms.append(f"INIT_s{s}=rl:{other}")
        outcomes={}
        for sc in cfg["evaluation"]:
            path=out/(sc+".jsonl"); registration=Path(str(path)+".registry.json")
            # A fixed condition has one realization per map, not fictitious independent days.
            ds="0" if sc in {"nowind","fixed_e4","fixed_n8"} else cfg["eval_days"]
            args=["--plans",cfg["pilot_plans"][sc],"--scen",sc,"--days",ds,"--methods",",".join(arms),
                  "--out",path,"--workers",workers,"--reference",cfg["primary_reference"],
                  "--wall-seconds",cfg["episode_wall_s"],"--costs",cfg["cost_manifests"][sc],
                  "--expected-inputs-sha",sealed["registered_inputs"][sc]]
            # Exit 2 with a written matrix is a scientific failure, not permission
            # to erase the attempt or silently drop remaining registered conditions.
            ev=stage("evaluate_"+sc,"evaluate.py",args,[path,registration],(0,2))
            report=out/("report_"+sc)
            status=stage("report_"+sc,"analyze.py",["--res",path,"--out",report,"--scen",sc],
                  [report/"REPORT.md",report/"gates.json",report/"table.tex",report/"per_episode.csv"],(0,2))
            gate=json.loads((report/"gates.json").read_text())["status"]
            outcomes[sc]=dict(status=gate,evaluator_exit=ev,analyzer_exit=status)
        R.publish(out/"campaign_report.json",dict(phase="development",formal=False,primary=cfg["primary_condition"],conditions=outcomes))
        if any(r["status"]!="PILOT_ACCOUNTED" or r["evaluator_exit"] or r["analyzer_exit"] for r in outcomes.values()):
            print("PILOT BLOCKED: see per-condition reports; all attempted rows retained")
            raise SystemExit(2)
        print("PILOT ACCOUNTED:",out,"; no Formal or publication claim")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticket",required=True); p.add_argument("--out",required=True); p.add_argument("--workers",type=int,default=4)
    p.add_argument("--preflight-only",action="store_true",help="freeze and check real inputs without training")
    a=p.parse_args()
    run(json.loads(Path(a.ticket).read_text()),a.ticket,Path(a.out).resolve(),a.workers,preflight_only=a.preflight_only)
