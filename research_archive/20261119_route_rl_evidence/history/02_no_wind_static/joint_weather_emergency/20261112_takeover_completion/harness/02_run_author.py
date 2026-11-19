#!/usr/bin/env python3
"""Run faithful Liu author anchors (J1b) for every generated map.

Registers a batch INTENT before any solver call.  One frozen seed per map
derived from (namespace, map sha256).  Resumable: an existing RUN.json with
anchor_eligible=True is never re-run.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys, time

R = pathlib.Path("<EXECUTION_PATH>")
C = R / "code"
AB = C / "route_rl_research/20261103/return_makespan/g23/author_baseline"
SOURCE_ROOT = C / "reproduction/reviewer_package_semfix"
SCORER = C / "route_rl_research/20261103/return_makespan/scorer.py"
JDK = R / "runtime/jdk17"
BUILD = R / "author_build"
SEED_NS = "takeover-20261112-g3-author-seed-v1"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--families", default="all")
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--max-maps", type=int, default=0)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    index = json.loads((out / "population_index.json").read_text())
    maps = [m for m in index["maps"] if m["status"] == "generated"]
    if args.families != "all":
        keep = {x.strip() for x in args.families.split(",")}
        maps = [m for m in maps if f"{m['sites']}x{m['targets']}" in keep]
    if args.max_maps:
        maps = maps[: args.max_maps]

    # Freeze intent before executing anything.
    intent = {
        "schema": "takeover_g3_author_intent_v1",
        "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "namespace": index["namespace"],
        "partition": index["partition"],
        "profile": "J1b",
        "seed_namespace": SEED_NS,
        "outer_iterations": 500,
        "alns_iterations": 5000,
        "author_source_hashes": index.get("author_source_hashes"),
        "maps": [{"name": m["name"], "raw_sha256": m["raw_sha256"],
                  "path": m["path"]} for m in maps],
        "budget_cpu_core_seconds_estimate": len(maps) * args.timeout,
    }
    (out / "AUTHOR_INTENT.json").write_text(json.dumps(intent, indent=2, sort_keys=True) + "\n")

    prepared = False
    results = []
    for m in maps:
        name = m["name"]
        dest = out / "author" / name
        run_json = dest / "RUN.json"
        if run_json.exists():
            prev = json.loads(run_json.read_text())
            if prev.get("anchor_eligible"):
                results.append({"name": name, "status": "cached",
                                "anchor_eligible": True})
                print(f"[skip] {name} cached anchor_eligible", flush=True)
                continue
        dest.mkdir(parents=True, exist_ok=True)
        if not prepared:
            p = run([sys.executable, "author_runner.py", "prepare", "--profile", "J1b",
                     "--java-home", str(JDK), "--build-dir", str(BUILD),
                     "--source-root", str(SOURCE_ROOT), "--scorer-path", str(SCORER)], cwd=AB)
            if p.returncode:
                print(p.stdout, p.stderr, file=sys.stderr)
                return 2
            prepared = True
        sha = sha256_file(pathlib.Path(m["path"]))
        seed = int.from_bytes(hashlib.sha256((SEED_NS + ":" + sha).encode()).digest()[:8], "big") & ((1 << 63) - 1)
        common = ["--source-root", str(SOURCE_ROOT), "--scorer-path", str(SCORER),
                  "--java-home", str(JDK), "--build-dir", str(BUILD)]
        t0 = time.perf_counter()
        p = run([sys.executable, "author_runner.py", "run", "--profile", "J1b",
                 "--instance", m["path"], "--seed", str(seed),
                 *common, "--out", str(dest), "--timeout", str(args.timeout)],
                cwd=AB)
        elapsed = time.perf_counter() - t0
        ok = run_json.exists() and json.loads(run_json.read_text()).get("anchor_eligible")
        row = {"name": name, "status": "ok" if ok else "failed",
               "anchor_eligible": bool(ok), "wall_s": round(elapsed, 3),
               "seed": seed, "returncode": p.returncode}
        if not ok:
            row["stdout_tail"] = p.stdout[-2000:]
            row["stderr_tail"] = p.stderr[-2000:]
        results.append(row)
        print(json.dumps(row), flush=True)
    (out / "AUTHOR_RESULTS.json").write_text(json.dumps(
        {"schema": "takeover_g3_author_results_v1", "rows": results,
         "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        indent=2, sort_keys=True) + "\n")
    ok = sum(1 for r in results if r.get("anchor_eligible"))
    print(json.dumps({"total": len(results), "anchor_eligible": ok}))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
