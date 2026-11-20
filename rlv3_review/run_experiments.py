"""Independent simulations; no test-selected reruns, no pilot or Formal dispatch."""
import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"A-fixed": ("rlv3_weather", "explore_weather"),
          "A-weather": ("rlv3_weather", "explore_dynamic_weather"),
          "B": ("rlv3_emergency", "explore_emergency")}

def seeds_arg(text):
    try:
        values = [int(x) for x in text.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from e
    if not values or len(values) != len(set(values)) or not all(0 <= v < 2**31 for v in values):
        raise argparse.ArgumentTypeError("supply unique seeds in [0,2^31)")
    return values

def stages(part):
    return [s for s in STAGES if part == "both" or s == part or part == s.split("-")[0]]

def write(p, obj):
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    tmp.replace(p)

def code_id():
    h = hashlib.sha256()
    for name in sorted(set(x[0] for x in STAGES.values())):
        for base in ["rlcore", "vendor"]:
            for p in sorted((ROOT/name/base).rglob("*.py")):
                h.update(str(p.relative_to(ROOT)).encode()+b"\0"+hashlib.sha256(p.read_bytes()).digest())
    for p in [Path(__file__), ROOT/"rlv3_review"/"execute_stage.py", ROOT/"run_experiments.sh"]:
        h.update(p.read_bytes())
    return h.hexdigest()

@contextmanager
def host_lock():
    with (Path(tempfile.gettempdir())/f"rlv3-hn01-{os.getuid()}.lock").open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another experiment on this host is active. No run started.")
        yield

def score_rows(stage, seed, rows, dataset="generated_holdout"):
    # Keep seed/condition strata and all scheduled endpoints. No per-map oracle.
    grouped={}
    for r in rows:
        scenario=r.get("scenario") or (r["pattern"]+"_"+r["level"])
        metrics=r["result"] if stage=="A-fixed" else r["metrics"]
        g=grouped.setdefault((scenario,r["method"]),[])
        g.append(metrics)
    scores=[]
    for (scenario,method),group in sorted(grouped.items()):
        def total(key): return sum(int(v.get(key) or 0) for v in group)
        def mean(values):return sum(values)/len(values) if values else None
        good=[v for v in group if v.get("eligible" if stage=="A-fixed" else "complete_strict") and not v.get("fallback")]
        scores.append(dict(dataset=dataset,stage=stage,seed=seed,scenario=scenario,method=method,cases=len(group),
            complete_strict=total("complete_strict"),eligible_on_fixed=len(good) if stage=="A-fixed" else None,
            routine_complete=sum(v.get("routine_total") is not None and v.get("routine_total")==v.get("routine_done") for v in group),
            all_returned=total("all_returned"),mean_M_on_eligible_or_complete=mean([v["M_return"] for v in good if v.get("M_return") is not None]),
            mean_J_all=mean([v["J"] for v in group]) if all(v.get("J") is not None for v in group) else None,
            urgent_high_ontime=total("high_on_time") if stage=="B" else None,
            urgent_high_total=total("high_total") if stage=="B" else None))
    return scores

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--part", choices=["both","A","B","A-fixed","A-weather"], default="both")
    p.add_argument("--profile", choices=["quick","standard"], default="standard")
    p.add_argument("--device", choices=["auto","cpu","cuda"], default="auto")
    p.add_argument("--seeds", type=seeds_arg)
    p.add_argument("--out", type=Path)
    p.add_argument("--timeout-per-stage", type=int, default=7200, help="wall seconds per stage per seed")
    a=p.parse_args()
    if a.timeout_per_stage <= 0: p.error("timeout must be positive")
    import numpy, scipy, torch
    device = ("cuda" if torch.cuda.is_available() else "cpu") if a.device=="auto" else a.device
    if device=="cuda" and not torch.cuda.is_available(): p.error("requested CUDA is not visible")
    if device=="cuda": (torch.ones(1,device="cuda")+1).item()
    seeds = a.seeds or ([101] if a.profile=="quick" else [101,211,307])
    out=(a.out or (Path.cwd()/"experiment_results"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))).resolve()
    matrix=[(s,k) for k in seeds for s in stages(a.part)]
    with host_lock():
        out.mkdir(parents=True,exist_ok=False)
        meta=dict(profile=a.profile, part=a.part, seeds=seeds, device=device, source_sha256=code_id(),
                  matrix=matrix, timeout_per_stage=a.timeout_per_stage, python=sys.version,
                  torch=str(torch.__version__),numpy=numpy.__version__,scipy=scipy.__version__,
                  formal=False, purpose="fresh synthetic exploratory experiments; not a paper conclusion")
        write(out/"RUN.json",meta)
        records=[]; scores=[]
        print(f"Output: {out}; device={device}; {len(matrix)} stages",flush=True)
        for i,(s,k) in enumerate(matrix,1):
            pkg,mod=STAGES[s]
            folder=out/f"{s}-seed{k}"
            cmd=[sys.executable,"-Bu",str(ROOT/"rlv3_review/execute_stage.py"),s,"--out",str(folder),"--seed",str(k),
                 "--profile",a.profile,"--device",device]
            log=out/(folder.name+".log")
            env=dict(os.environ,RLV3_ROOT=str(ROOT/pkg))
            started=time.monotonic()
            print(f"[{i}/{len(matrix)}] {s} seed={k}  {log}",flush=True)
            with log.open("x") as f:
                proc=subprocess.Popen(cmd,cwd=ROOT/pkg,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    rc=proc.wait(timeout=a.timeout_per_stage)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL); proc.wait(); rc=124
                except BaseException:
                    if proc.poll() is None: os.killpg(proc.pid,signal.SIGKILL)
                    proc.wait(); raise
            record=dict(stage=s,seed=k,exit=rc,seconds=round(time.monotonic()-started,3),
                        folder=str(folder),log=str(log),command=cmd)
            if rc==0:
                try:
                    summary=json.loads((folder/"summary.json").read_bytes())
                    rows=[json.loads(x) for x in (folder/"evaluation.jsonl").read_text().splitlines() if x.strip()]
                    if not isinstance(summary,dict) or not rows: raise ValueError("empty summary/results")
                    scores.extend(score_rows(s,k,rows))
                    record.update(summary=str(folder/"summary.json"),evaluation_rows=len(rows))
                    if s!="A-fixed":
                        external=folder/"original_maps"
                        original_rows=[json.loads(x) for x in (external/"evaluation.jsonl").read_text().splitlines()]
                        if not original_rows or len(original_rows)!=json.loads((external/"summary.json").read_text())["rows"]:
                            raise ValueError("incomplete original-map evaluation")
                        scores.extend(score_rows(s,k,original_rows,"grok_packaged_test"))
                        record["original_map_rows"]=len(original_rows)
                except (ValueError,OSError,KeyError,TypeError) as e:
                    record.update(exit=1,error=str(e))
            records.append(record)
            write(out/"RESULTS.json",dict(runs=records,expected=len(matrix),
                complete=len(records)==len(matrix) and all(r["exit"]==0 for r in records),formal=False))
            print(f"  exit={record['exit']}, {record['seconds']}s",flush=True)
        if scores:
            with (out/"SCORES.csv").open("x",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(scores[0]));w.writeheader();w.writerows(scores)
        ok=all(r["exit"]==0 for r in records)
        with (out/"INDEX.csv").open("x",newline="") as f:
            w=csv.writer(f); w.writerow(["stage","seed","exit","seconds","rows","summary","log"])
            for r in records:w.writerow([r["stage"],r["seed"],r["exit"],r["seconds"],r.get("evaluation_rows",""),r.get("summary",""),r["log"]])
        print("DONE" if ok else "INCOMPLETE (see failed stage logs)",out,flush=True)
        return 0 if ok else 1

if __name__=="__main__":sys.exit(main())
