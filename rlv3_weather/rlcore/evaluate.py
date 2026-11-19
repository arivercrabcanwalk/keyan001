"""Paired pilot evaluator. Register first, keep failed attempts, enforce cold end-to-end wall budgets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time
import traceback

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from rlcore.common import load_plans, rel
from rlcore import policies as PO
from rlcore import registration as R
from rlcore.scen import make_env, DEV_DAYS, TEST_DAYS, SCENARIOS

def scenario_input_hash(env):
    from rlcore.scen import scenario_input_hash as hash_inputs
    return hash_inputs(env)


def _winit():
    import torch
    torch.set_num_threads(1)


def one(args):
    """In-process DEV tuner; frozen evaluation also measures process startup, loading and actual exit."""
    row, day, scen, name, spec, *registered = args
    t0=time.monotonic()
    identity=dict(path=row["path"], day=day, scen=scen, method=name, spec=spec)
    try:
        if registered:
            h, m, sol, inp = registered[0]
            if R.file_sha(rel(row["path"])) != m or R.digest(row["solution"]) != sol:
                raise ValueError("map or anchor changed")
            if spec.startswith("rl:") and R.file_sha(rel(spec[3:])) != h:
                raise ValueError("checkpoint changed")
        env = make_env(row, day, scen)
        input_sha = scenario_input_hash(env)
        if registered and input_sha != inp:
            raise ValueError("actual weather/request realization does not match frozen input")
        if spec.startswith("rl:"):
            from rlcore.agent import load_policy, RLPolicy
            model, features, base = load_policy(rel(spec[3:]))
            policy = RLPolicy(model, features, greedy=True, base=base)
        else:
            policy = PO.make(spec)
        result = PO.run_episode(env, policy)
        result.pop("per_st_J", None)
        return dict(result, **identity, status="OK", input_sha256=input_sha, wall=time.monotonic()-t0)
    except Exception as e:
        return dict(identity,error=repr(e),tb=traceback.format_exc()[-1200:],status="ERROR",wall=time.monotonic()-t0)


def _child(job, pipe):
    try:
        _winit()
        pipe.send(one(job))
    finally:
        pipe.close()


def bounded(job, limit):
    row, day, scen, name, spec, frozen = job
    failed=dict(path=row["path"],day=day,scen=scen,method=name,spec=spec,input_sha256=frozen[3])
    start=time.monotonic()
    ctx=mp.get_context("spawn")
    recv,send=ctx.Pipe(duplex=False)
    proc=ctx.Process(target=_child,args=(job,send))
    try:
        proc.start()
        send.close()
        if not recv.poll(max(0,limit-(time.monotonic()-start))):
            raise TimeoutError("end-to-end budget expired")
        result=recv.recv()
        proc.join(max(0,limit-(time.monotonic()-start)))
        if proc.is_alive() or time.monotonic()-start>limit:
            raise TimeoutError("worker did not exit by deadline")
        if proc.exitcode!=0:
            raise RuntimeError(f"worker exit {proc.exitcode}")
        result.setdefault("input_sha256",frozen[3])
    except Exception as e:
        result=dict(failed,error=repr(e),status="TIMEOUT" if isinstance(e,TimeoutError) else "ERROR")
    finally:
        recv.close(); send.close()
        if proc.pid is not None:
            if proc.is_alive(): proc.kill()
            proc.join(); proc.close()
    result["wall"]=time.monotonic()-start
    if result["wall"]>limit and result.get("status")=="OK":
        result.update(status="TIMEOUT",error="whole process exceeded deadline")
    return result


def parse_days(s):
    if s in ("dev","test"): return list(DEV_DAYS if s=="dev" else TEST_DAYS)
    if ":" in s:
        a,b=map(int,s.split(":")); return list(range(a,b))
    return [int(x) for x in s.split(",")]


def expand(methods, scen):
    out=[]
    for token in methods.split(","):
        if token.startswith("tuned:"):
            tune=json.loads(Path(rel(token[6:])).read_text())
            out.extend(tune["best"].items())  # trained-on scenario may differ in a predeclared transfer arm
        else:
            name,_,spec=token.partition("="); out.append((name,spec or name))
    if not R.unique([n for n,_ in out]): raise ValueError("duplicate method names")
    return out


@contextmanager
def exclusive(path):
    import fcntl
    with open(path,"a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ("plans","scen","methods","out","reference"): p.add_argument("--"+flag,required=True)
    p.add_argument("--days",default="test"); p.add_argument("--workers",type=int,default=2)
    p.add_argument("--maps",type=int,default=0); p.add_argument("--wall-seconds",type=float,required=True)
    p.add_argument("--costs",help="per-map/day registered caps; for fixed wind, paths to matching full author artifacts")
    p.add_argument("--expected-inputs-sha",help="input population hash recorded before the first training stage")
    a=p.parse_args()
    if a.workers<=0 or a.maps<0: p.error("invalid workers/maps")
    rows=load_plans(a.plans)
    if a.maps: rows=rows[:a.maps]
    days=parse_days(a.days); methods=expand(a.methods,a.scen)
    costs=json.loads(Path(a.costs).read_text()) if a.costs else None
    body=R.make_manifest(rows,days,methods,a.scen,a.wall_seconds,a.reference,SCENARIOS,scenario_input_hash,costs)
    if a.expected_inputs_sha and R.digest(body["maps"])!=a.expected_inputs_sha:
        raise ValueError("changed maps, same-wind budgets, deployment, or events since campaign freeze")
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    registry=Path(str(out)+".registry.json")
    with exclusive(str(out)+".lock"):
        if out.exists() and not registry.exists():
            raise ValueError("unregistered pre-existing result; use a fresh directory")
        doc=R.freeze(registry,body)
        previous=R.read_rows(out) if out.exists() else []
        known,issues,_=R.index(doc,previous)
        if issues: raise ValueError(f"previous attempt retained; cannot overwrite/retry: {issues[:3]}")
        jobs=[]
        for m,s in methods:
            for r in rows:
                meta=body["maps"][r["path"]]
                for d in days:
                    if (r["path"],d,m) not in known:
                        jobs.append((r,d,a.scen,m,s,(body["methods"][m]["checkpoint"],meta["map"],meta["anchor"],meta["days"][str(d)])))
        with out.open("a",encoding="utf-8") as f, ThreadPoolExecutor(max_workers=a.workers) as pool:
            for result in pool.map(lambda j:bounded(j,a.wall_seconds),jobs):
                result["manifest_sha256"]=doc["sha256"]
                f.write(json.dumps(result,allow_nan=False)+"\n"); f.flush()
        _,issues,missing=R.index(doc,R.read_rows(out))
        print(f"registered={len(R.keys(body))} problems={len(issues)} missing={len(missing)}; failures preserved")
        return 2 if issues or missing else 0


if __name__=="__main__": sys.exit(main())
