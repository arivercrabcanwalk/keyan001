#!/usr/bin/env python3
"""Rebuild a transparent, instrumented copy of the pinned Liu2026 Java TSALNS source."""
from pathlib import Path
import os,sys,subprocess,hashlib,json,difflib,re,shutil
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"reference/java"
official=BASE/"official_source"
src=BASE/"instrumented_source"
classes=BASE/"classes"
lock=json.loads((BASE/"SOURCE_LOCK.json").read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
current={p.name:sha(p) for p in sorted(official.glob("*.java"))}
if current != lock["sha256"] or len(current) != lock["file_count"]:
    raise SystemExit("official Java source hash mismatch; refusing to build")
if lock["commit"] != "d86f5549ebc9c05d65fce16f61b6df4f7cb73158":
    raise SystemExit("unexpected official repository commit")
if src.exists(): shutil.rmtree(src)
src.mkdir(parents=True)
changes=[]
for p in sorted(official.glob("*.java")):
    original=p.read_text()
    modified=original.replace("new Random()", "ReplayRandom.RNG").replace("Math.random()", "ReplayRandom.RNG.nextDouble()")
    modified=re.sub(r"Collections\\.shuffle\\((\\w+)\\)",r"Collections.shuffle(\\1, ReplayRandom.RNG)",modified)
    if p.name=="Main.java":
        assert 'String filePath = "PATH";' in modified
        modified=modified.replace('String filePath = "PATH";','String filePath = System.getProperty("repro.instance");')
        modified=modified.replace("long startTime = System.currentTimeMillis();","ReplayRandom.start();\n        long startTime = System.currentTimeMillis();")
        modified=modified.replace("iter < MAX_ITERATIONS;", "iter < MAX_ITERATIONS && ReplayRandom.inBudget();")
        modified=modified.replace("i < 100;", "i < 100 && ReplayRandom.inBudget();")
        needle="double temperature = INITIAL_TEMPERATURE;"
        modified=modified.replace(needle,"ReferenceRecorder.save(bestSolution1,targetNodes,stationNodes,bestCost);\n        "+needle)
        needle="temperature *= COOLING_RATE;"
        modified=modified.replace(needle,"ReferenceRecorder.save(bestSolution1,targetNodes,stationNodes,bestCost);\n            "+needle)
    elif p.name=="ALNSSolver.java":
        modified=modified.replace("temperature > finalTemp;", "temperature > finalTemp && ReplayRandom.inBudget();")
    (src/p.name).write_text(modified)
    if original != modified:
        changes.extend(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),
                                            fromfile="official/"+p.name,tofile="instrumented/"+p.name))
for name in ("ReferenceRecorder.java","GreedyProbe.java","ReplayRandom.java","SolutionAuditProbe.java"):
    shutil.copyfile(BASE/name,src/name)
diff="".join(changes)
(ROOT/"reference/evidence/reference_instrumentation.diff").write_text(diff)
if classes.exists(): shutil.rmtree(classes)
classes.mkdir(parents=True)
java_home=os.environ.get("JAVA_HOME")
if java_home:
    javac=Path(java_home)/"bin"/"javac"
    java=Path(java_home)/"bin"/"java"
else:
    javac=Path(shutil.which("javac") or "")
    java=Path(shutil.which("java") or "")
if not javac.is_file() or not java.is_file():
    raise SystemExit("JDK 17 required: set JAVA_HOME or put java/javac on PATH")
compile_cmd=[str(javac),"-encoding","UTF-8","-d",str(classes),*[str(p) for p in sorted(src.glob("*.java"))]]
r=subprocess.run(compile_cmd,capture_output=True,text=True,timeout=120)
log=r.stdout+r.stderr
(ROOT/"reference/evidence/java_compile.log").write_text(log)
if r.returncode: raise SystemExit(r.returncode)
version=subprocess.run([str(java),"-version"],capture_output=True,text=True,timeout=10)
instrumented={p.name:sha(p) for p in sorted(src.glob("*.java"))}
manifest={"repository":lock["repository"],"official_commit":lock["commit"],
          "official_source_sha256":current,"instrumented_source_sha256":instrumented,
          "instrumentation_diff_sha256":sha(ROOT/"reference/evidence/reference_instrumentation.diff"),
          "instrumented_java_files":len(instrumented),"class_files":len(list(classes.rglob("*.class"))),
          "javac":str(javac),"java_version":version.stderr or version.stdout,
          "compile_command":compile_cmd,"compile_exit":r.returncode,
          "semantic_warning":"RNG objects are replaced by one seeded shared java.util.Random; seed is an experimental control, not the unknown author seed. Budget checks and best-so-far recording are instrumentation."}
(BASE/"build_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print("JAVA_REFERENCE_BUILD_OK",len(instrumented),"sources",manifest["class_files"],"classes")
print(version.stderr or version.stdout)
