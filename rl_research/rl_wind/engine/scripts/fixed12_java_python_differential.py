#!/usr/bin/env python3
"""Fixed-12-outer Java/Python differential using a separate instrumented Java build."""
from pathlib import Path
import os,sys,json,subprocess,time,hashlib,shutil,re
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lrphsd.problem import read_instance,normalized
from lrphsd.evaluator import evaluate
from lrphsd.tsalns_v6 import solve as solve_v6,reset_engine

BASE=ROOT/"reference/java"
source=BASE/"instrumented_source"
fixed_src=BASE/"fixed12_source"
fixed_classes=BASE/"fixed12_classes"
java_home=os.environ.get("JAVA_HOME")
if not java_home: raise SystemExit("JAVA_HOME must point to the pinned JDK 17")
java=Path(java_home)/"bin"/"java"
javac=Path(java_home)/"bin"/"javac"
if not java.is_file() or not javac.is_file(): raise SystemExit("JDK 17 java/javac not found")
if fixed_src.exists(): shutil.rmtree(fixed_src)
fixed_src.mkdir(parents=True)
for p in source.glob("*.java"):
    text=p.read_text()
    if p.name=="Main.java":
        text2=re.sub(r"MAX_ITERATIONS\s*=\s*500", "MAX_ITERATIONS = 12", text, count=1)
        if text2==text: raise SystemExit("cannot locate Main.MAX_ITERATIONS=500")
        text=text2
    (fixed_src/p.name).write_text(text)
if fixed_classes.exists(): shutil.rmtree(fixed_classes)
fixed_classes.mkdir(parents=True)
files=sorted(fixed_src.glob("*.java"))
r=subprocess.run([str(javac),"-encoding","UTF-8","-d",str(fixed_classes),*[str(p) for p in files]],
                 capture_output=True,text=True,timeout=120)
(ROOT/"reference/evidence/fixed12_compile.log").write_text(r.stdout+r.stderr)
if r.returncode: raise SystemExit(r.returncode)

suite=[("3_10_1",0),("3_10_1",1),("5_35_1",0),("5_35_1",1),("7_65_1",0),("7_65_1",1)]
inst_dir=ROOT/"external/LRPHSD/data/Instances_Alg"
rows=[]
out=ROOT/"results"/"official_java_fixed12"/("run_"+str(time.time_ns()))
out.mkdir(parents=True,exist_ok=False)
for name,seed in suite:
    path=inst_dir/(name+".txt")
    ins=read_instance(path)
    java_out=out/(name+f"__seed{seed}.java.json")
    cmd=[str(java),"-XX:ActiveProcessorCount=1","-XX:+UseSerialGC","-Xms32m","-Xmx512m",
         f"-Drepro.instance={path}",f"-Drepro.seed={seed}","-Drepro.seconds=0",
         f"-Drepro.output={java_out}","-cp",str(fixed_classes),"test1.Main"]
    jr=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
    (out/(name+f"__seed{seed}.java.log")).write_text(jr.stdout+"\n"+jr.stderr)
    if jr.returncode or not java_out.exists():
        rows.append({"instance":name,"seed":seed,"java_returncode":jr.returncode,
                     "java_output_exists":java_out.exists(),"java_error":jr.stderr[-2000:]})
        continue
    j=json.loads(java_out.read_text())
    js={"schema_version":1,"instance":ins.name,"instance_sha256":ins.sha256,
        "station_types":j["station_types"],"routes":j["routes"]}
    j_audit=evaluate(ins,js)
    reset_engine()
    ps,meta=solve_v6(ins,seed=seed,seconds=None,
        config={"outer_iterations":12,"local_iterations":100,"alns_iterations":5000,
                "weight_lower":0.1,"weight_upper":5.0,"initial_temperature":1000.0,
                "cooling_rate":0.95,"final_temperature":0.001,"strict_deadline":False},
        rng_mode="shared",removed_order="input")
    p_audit=evaluate(ins,ps)
    rows.append({"instance":name,"seed":seed,"java_returncode":jr.returncode,
        "java_cost_reported":j["reference_reported_cost"],"java_cost_recomputed":j_audit["cost"],
        "python_cost":p_audit["cost"],"java_feasible":j_audit["feasible"],
        "python_feasible":p_audit["feasible"],
        "java_audit_issues":j_audit["issues"],
        "python_audit_issues":p_audit["issues"],
        "same_station_types":js["station_types"]==ps["station_types"],
        "same_routes":normalized(js)["routes"]==normalized(ps)["routes"],
        "objective_abs_error":abs(j_audit["cost"]-p_audit["cost"]),
        "python_outer_iterations":meta["outer_iterations_attempted"],
        "python_evaluations":meta["evaluations"],
        "java_integrity_issues":j.get("reference_integrity_issues",[])})
    reset_engine()
summary={"protocol":"fixed 12 outer; Java code profile local=100, ALNS=5000, weights=.1..5, T0=1000, alpha=.95",
         "rng":"shared java.util.Random seed per run; seed is a controlled comparison, not known author seed",
         "instances":len(suite),"completed":sum("java_cost_recomputed" in r for r in rows),
         "java_feasible":sum(bool(r.get("java_feasible")) for r in rows),
         "python_feasible":sum(bool(r.get("python_feasible")) for r in rows),
         "java_infeasible_instances":[r["instance"]+"__seed"+str(r["seed"]) for r in rows if not r.get("java_feasible",False)],
         "same_station_types":sum(bool(r.get("same_station_types")) for r in rows),
         "same_routes":sum(bool(r.get("same_routes")) for r in rows),
         "rows":rows}
(out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps({k:v for k,v in summary.items() if k!="rows"},sort_keys=True))
