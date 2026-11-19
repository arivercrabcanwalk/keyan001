#!/usr/bin/env python3
"""Build official-source + independent complete-feasibility guard variant."""
from pathlib import Path
import os, shutil, subprocess, json, hashlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reference" / "java"
src = BASE / "instrumented_source"
guarded = BASE / "guarded_source"
classes = BASE / "guarded_classes"

if guarded.exists():
    shutil.rmtree(guarded)
guarded.mkdir(parents=True)

for p in src.glob("*.java"):
    text = p.read_text()
    if p.name == "Main.java":
        needle = "Node[] stationNodes = stationNodesList.toArray(new Node[0]);"
        assert needle in text
        text = text.replace(needle, needle + """
        Round4Guard.init(targetNodes,stationNodes);
""")
        needle = "List<List<List<List<Node>>>> initRoute =Check.deepCopyRoute(route1);"
        assert needle in text
        text = text.replace(needle, needle + """
        if(Boolean.getBoolean("repro.guard") && !Round4Guard.valid(initStationType,initRoute))
            throw new IllegalStateException("invalid initial solution");
""")
        needle = "            ALNSSolver solver = new ALNSSolver();"
        assert needle in text
        text = text.replace(needle, """
            if(Boolean.getBoolean("repro.guard") && !Round4Guard.valid(newStationType,newRoutes)) continue;
""" + needle)
        needle = "            double newCost = Check.calculateTotalCost(newRoutes,newStationType,"
        assert needle in text
        text = text.replace(needle, """
            if(Boolean.getBoolean("repro.guard") && !Round4Guard.valid(newStationType,newRoutes)) continue;
""" + needle)
    elif p.name == "ALNSSolver.java":
        needle = "            boolean accepted = acceptNewSolution(currentCost, newCost, temperature);"
        assert needle in text
        text = text.replace(needle, needle + """
            if(Boolean.getBoolean("repro.guard") && !Round4Guard.valid(stationTypes,newRoute))
                accepted=false;
""")
    if p.name == "RoutingOperator.java":
        old = "        return new ArrayList<>(removed);"
        new = """        List<Node> sortedRemoved = new ArrayList<>(removed);
        sortedRemoved.sort((a,b) -> Integer.compare(a.getNodeNo(), b.getNodeNo()));
        return sortedRemoved;"""
        assert old in text
        text = text.replace(old, new)
    (guarded / p.name).write_text(text)

(guarded / "Round4Guard.java").write_text((BASE / "Round4Guard.java").read_text())
if classes.exists():
    shutil.rmtree(classes)
classes.mkdir(parents=True)

java_home = os.environ.get("JAVA_HOME")
if not java_home:
    raise SystemExit("set JAVA_HOME to JDK 17")
javac = Path(java_home) / "bin" / "javac"
java = Path(java_home) / "bin" / "java"
cmd = [str(javac), "-encoding", "UTF-8", "-d", str(classes),
       *[str(p) for p in sorted(guarded.glob("*.java"))]]
r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
(ROOT / "reference" / "evidence" / "guarded_java_compile.log").write_text(r.stdout + r.stderr)
if r.returncode:
    raise SystemExit(r.returncode)

version = subprocess.run([str(java), "-version"], capture_output=True, text=True)
manifest = {
    "official_commit": json.loads((BASE / "SOURCE_LOCK.json").read_text())["commit"],
    "guard": "Round4Guard independent feasibility contract; enforces SABS small-drone-only",
    "guarded_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(guarded.glob("*.java"))},
    "class_files": len(list(classes.rglob("*.class"))),
    "java_version": version.stderr or version.stdout
}
(BASE / "guarded_build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("GUARDED_JAVA_BUILD_OK", manifest["class_files"], "classes")
