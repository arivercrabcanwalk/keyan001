#!/usr/bin/env python3
"""Compare the pinned Java Init.java initial solution with Python's official-code port."""
from pathlib import Path
import os,sys,json,subprocess,time,csv,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lrphsd.problem import read_instance,normalized
from lrphsd.greedy import build
from lrphsd.evaluator import evaluate
BASE=ROOT/"reference/java"
lock=json.loads((BASE/"SOURCE_LOCK.json").read_text())
manifest=json.loads((BASE/"build_manifest.json").read_text())
java_home=os.environ.get("JAVA_HOME")
if java_home:
    java=Path(java_home)/"bin"/"java"
else:
    java=Path(shutil.which("java") or "")
if not java.is_file(): raise SystemExit("JDK 17 required: set JAVA_HOME or put java on PATH")
inst_dir=ROOT/"external/LRPHSD/data/Instances_Alg"
files=sorted(inst_dir.glob("*.txt"))
assert len(files)==120, f"expected 120 official instances, got {len(files)}"
cmd=[str(java),"-XX:ActiveProcessorCount=1","-XX:+UseSerialGC","-Xms32m","-Xmx512m",
     "-cp",str(BASE/"classes"),"test1.GreedyProbe",*[str(p) for p in files]]
proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
out=ROOT/"results"/"official_java_greedy"/("run_"+str(time.time_ns()))
out.mkdir(parents=True,exist_ok=False)
(out/"java.stdout.log").write_text(proc.stdout)
(out/"java.stderr.log").write_text(proc.stderr)
if proc.returncode: raise SystemExit(f"Java GreedyProbe failed: {proc.returncode}")
java_rows={}
errors=[]
for line in proc.stdout.splitlines():
    if line.startswith("REFERENCE_JSON="):
        name,payload=line[len("REFERENCE_JSON="):].split("\t",1)
        java_rows[name]=json.loads(payload)
    elif line.startswith("REFERENCE_ERROR="):
        errors.append(line)
rows=[]
for path in files:
    ins=read_instance(path)
    own=build(ins)
    a=evaluate(ins,own)
    ref=java_rows.get(path.name)
    row={"instance":ins.name,"input_sha256":ins.sha256,
         "python_feasible":a["feasible"],"python_cost":a["cost"],
         "java_present":ref is not None}
    if ref:
        b=evaluate(ins,ref)
        row.update({"java_reported_cost":ref["reference_reported_cost"],
                    "java_recomputed_cost":b["cost"],
                    "java_feasible":b["feasible"] and not ref.get("reference_integrity_issues"),
                    "same_station_types":own["station_types"]==ref["station_types"],
                    "same_routes":normalized(own)["routes"]==normalized(ref)["routes"],
                    "objective_abs_error":abs(a["cost"]-b["cost"]),
                    "java_integrity_issues":ref.get("reference_integrity_issues",[])})
    rows.append(row)
summary={"official_repository":lock["repository"],"official_commit":lock["commit"],
         "instrumented_build_manifest_sha256":hashlib.sha256((BASE/"build_manifest.json").read_bytes()).hexdigest(),
         "instances":len(files),"java_outputs":len(java_rows),"java_errors":errors,
         "python_feasible":sum(r["python_feasible"] for r in rows),
         "java_feasible":sum(bool(r.get("java_feasible")) for r in rows),
         "same_station_types":sum(bool(r.get("same_station_types")) for r in rows),
         "same_routes":sum(bool(r.get("same_routes")) for r in rows),
         "objective_match_1e7":sum(r.get("objective_abs_error",float("inf"))<1e-7 for r in rows),
         "rows":rows}
(out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
with (out/"rows.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}))
    w.writeheader();w.writerows(rows)
print(json.dumps({k:v for k,v in summary.items() if k!="rows"},sort_keys=True))
ok=(summary["instances"]==120 and summary["java_outputs"]==120 and not errors and
    summary["python_feasible"]==120 and summary["java_feasible"]==120 and
    summary["same_station_types"]==120 and summary["same_routes"]==120 and
    summary["objective_match_1e7"]==120)
if not ok: raise SystemExit(2)
print("OFFICIAL_JAVA_GREEDY_DIFFERENTIAL_PASS")
