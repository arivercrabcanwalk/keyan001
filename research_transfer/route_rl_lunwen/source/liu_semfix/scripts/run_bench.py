#!/usr/bin/env python
"""Run a CA-RL benchmark over instances, methods and seeds in parallel.

Example:
  python -B scripts/run_bench.py --split dev12 --methods m0,m1,m2 --seeds 1,2,3 \
      --seconds 6 --workers 32 --out results/pilot_dev12
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time

# Single-thread every numerical library so that parallel workers do not
# contend on shared cores (fairness of the wall-clock budget).
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carl.core import split_instances  # noqa: E402
from carl.runner import run_one, resolve_method_config, task_identity  # noqa: E402

INST_DIR = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"
DEV12 = ["3_10_1", "3_20_1", "4_20_1", "4_30_1", "5_35_1", "5_35_5",
         "6_50_1", "7_65_1", "8_80_1", "8_80_5", "9_95_1", "10_110_1"]


def environment_fingerprint(cpu_quota):
    def version(package):
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_quota": None if cpu_quota is None else float(cpu_quota),
        "numpy": version("numpy"),
        "torch": version("torch"),
    }


def select_instances(spec, formal_freeze_path_override=None):
    if spec == "dev12":
        return [str(INST_DIR / (n + ".txt")) for n in DEV12]
    if spec == "formal_v3":
        formal = ROOT / "datasets" / "formal_v3"
        freeze_path = (Path(formal_freeze_path_override) if formal_freeze_path_override
                       else ROOT / "results" / "FORMAL_V3_FREEZE.json")
        if not freeze_path.is_file():
            raise SystemExit("formal_v3 optimizer blocked: results/FORMAL_V3_FREEZE.json is missing")
        freeze = json.loads(freeze_path.read_text())
        if freeze.get("status") != "FROZEN":
            raise SystemExit("formal_v3 optimizer blocked: freeze status is not FROZEN")
        manifest_path = formal / "manifest.json"
        if not manifest_path.is_file():
            raise SystemExit(f"formal_v3 manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text())
        rows = manifest.get("rows")
        if (manifest.get("counts") != {"main": 30, "stress": 6, "total": 36}
                or not isinstance(rows, list) or len(rows) != 36):
            raise SystemExit("formal_v3 manifest must declare exactly 30 main and 6 stress maps")
        names = set()
        paths = []
        for row in rows:
            name = row.get("name")
            expected_hash = row.get("instance_sha256")
            witness_hash = row.get("witness_sha256")
            if (not isinstance(name, str) or not name or Path(name).name != name
                    or name.endswith(".txt") or name.startswith("._") or name in names):
                raise SystemExit(f"invalid/duplicate formal_v3 map name: {name!r}")
            names.add(name)
            path = formal / (name + ".txt")
            witness = formal / (name + ".witness.json")
            if not path.is_file() or not witness.is_file():
                raise SystemExit(f"formal_v3 instance/witness missing for {name}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise SystemExit(f"formal_v3 instance SHA256 mismatch: {path}")
            if hashlib.sha256(witness.read_bytes()).hexdigest() != witness_hash:
                raise SystemExit(f"formal_v3 witness SHA256 mismatch: {witness}")
            paths.append(str(path))
        actual_names = {
            q.stem for q in formal.glob("*.txt")
            if q.is_file() and not q.name.startswith("._")
        }
        if actual_names != names:
            raise SystemExit("formal_v3 file/manifest set mismatch")
        return paths
    if spec == "formal_v4":
        formal = ROOT / "datasets" / "formal_v4"
        freeze_path = (Path(formal_freeze_path_override) if formal_freeze_path_override
                       else ROOT / "results" / "FORMAL_V4_FREEZE.json")
        if not freeze_path.is_file():
            raise SystemExit("formal_v4 optimizer blocked: results/FORMAL_V4_FREEZE.json is missing")
        freeze = json.loads(freeze_path.read_text())
        if freeze.get("status") != "FROZEN":
            raise SystemExit("formal_v4 optimizer blocked: freeze status is not FROZEN")
        manifest_path = formal / "manifest.json"
        if not manifest_path.is_file():
            raise SystemExit(f"formal_v4 manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text())
        rows = manifest.get("rows")
        if (manifest.get("counts") != {"main": 30, "stress": 6, "total": 36}
                or not isinstance(rows, list) or len(rows) != 36):
            raise SystemExit("formal_v4 manifest must declare exactly 30 main and 6 stress maps")
        names = set()
        paths = []
        for row in rows:
            name = row.get("name")
            expected_hash = row.get("instance_sha256")
            witness_hash = row.get("witness_sha256")
            if (not isinstance(name, str) or not name or Path(name).name != name
                    or name.endswith(".txt") or name.startswith("._") or name in names):
                raise SystemExit(f"invalid/duplicate formal_v4 map name: {name!r}")
            names.add(name)
            path = formal / (name + ".txt")
            witness = formal / (name + ".witness.json")
            if not path.is_file() or not witness.is_file():
                raise SystemExit(f"formal_v4 instance/witness missing for {name}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise SystemExit(f"formal_v4 instance SHA256 mismatch: {path}")
            if hashlib.sha256(witness.read_bytes()).hexdigest() != witness_hash:
                raise SystemExit(f"formal_v4 witness SHA256 mismatch: {witness}")
            paths.append(str(path))
        actual_names = {
            q.stem for q in formal.glob("*.txt")
            if q.is_file() and not q.name.startswith("._")
        }
        if actual_names != names:
            raise SystemExit("formal_v4 file/manifest set mismatch")
        return paths
    if spec == "locked_v2":
        # The manifest, not a broad filesystem glob, is the authority for the
        # held-out suite. macOS may leave AppleDouble files named ._*.txt in
        # copied directories; these are metadata, never benchmark instances.
        locked = ROOT / "datasets" / "locked_v2"
        manifest_path = locked / "manifest.json"
        if not manifest_path.is_file():
            raise SystemExit(f"locked_v2 manifest missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text())
        rows = manifest.get("rows")
        if not isinstance(rows, list) or len(rows) != 60:
            raise SystemExit("locked_v2 manifest must declare exactly 60 maps")
        expected_names = set()
        paths = []
        for row in rows:
            name = row.get("name")
            expected_hash = row.get("sha256")
            if (not isinstance(name, str) or not name or Path(name).name != name
                    or name.endswith(".txt") or name.startswith("._")):
                raise SystemExit(f"invalid locked_v2 map name: {name!r}")
            if name in expected_names:
                raise SystemExit(f"duplicate locked_v2 map in manifest: {name}")
            expected_names.add(name)
            path = locked / (name + ".txt")
            if not path.is_file():
                raise SystemExit(f"locked_v2 map missing: {path}")
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise SystemExit(f"locked_v2 SHA256 mismatch: {path}")
            paths.append(path)
        actual_names = {
            p.stem for p in locked.glob("*.txt")
            if p.is_file() and not p.name.startswith("._")
        }
        if actual_names != expected_names:
            extra = sorted(actual_names - expected_names)
            missing = sorted(expected_names - actual_names)
            raise SystemExit(f"locked_v2 file/manifest mismatch: extra={extra[:5]} missing={missing[:5]}")
        return [str(p) for p in paths]
    if spec in ("all", "train", "val", "test"):
        splits = split_instances(INST_DIR)
        if spec == "all":
            out = splits["train"] + splits["val"] + splits["test"]
        else:
            out = splits[spec]
        return [str(p) for p in sorted(out)]
    paths = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        p = Path(token)
        if p.exists():
            paths.append(str(p))
            continue
        cand = INST_DIR / (token if token.endswith(".txt") else token + ".txt")
        if cand.exists():
            paths.append(str(cand))
            continue
        for c in sorted(INST_DIR.glob(token)):
            paths.append(str(c))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", default="dev12")
    ap.add_argument("--methods", default="m0,m1")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ppo-model", default=None)
    ap.add_argument("--max-steps", type=int, default=500000)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--families", default="0,1,2,3")
    ap.add_argument("--zero-groups", default="")
    ap.add_argument("--mask-mode", default="normal")
    ap.add_argument("--intensities", default="0,1,2")
    ap.add_argument("--no-cross-exchange", action="store_true")
    args = ap.parse_args()

    # Respect Linux cgroup CPU quota; host-visible CPU count can be misleading.
    quota = None
    try:
        quota_text = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota_text[0] != "max":
            quota = max(1, int(int(quota_text[0]) / int(quota_text[1])))
    except (OSError, ValueError, IndexError, ZeroDivisionError):
        pass
    if quota is not None and args.workers > quota:
        print(f"[bench] cgroup quota={quota} CPUs; clamping workers {args.workers}->{quota}",
              flush=True)
        args.workers = quota

    if args.workers < 1 or not (0 < args.seconds < float("inf")):
        raise SystemExit("workers and finite seconds must be positive")
    paths = select_instances(args.instances)
    if not paths:
        raise SystemExit("no instances selected")
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    if not methods or len(methods) != len(set(methods)):
        raise SystemExit("methods must be nonempty and unique")
    if not seeds or len(seeds) != len(set(seeds)):
        raise SystemExit("seeds must be nonempty and unique")
    if len(paths) != len(set(paths)):
        raise SystemExit("instance selection contains duplicates")
    outdir = Path(args.out)

    tasks = []
    for p in paths:
        name = Path(p).stem
        for m in methods:
            for s in seeds:
                tasks.append({"instance": name, "instance_path": p, "method": m,
                              "seed": s, "seconds": args.seconds, "outdir": str(outdir),
                              "max_steps": args.max_steps,
                              "model_path": args.ppo_model,
                              "families": [int(x) for x in args.families.split(",") if x],
                              "zero_groups": [x for x in args.zero_groups.split(",") if x],
                              "mask_mode": args.mask_mode,
                              "intensities": [int(x) for x in args.intensities.split(",") if x],
                              "cross_exchange": not args.no_cross_exchange,
                              "overwrite": args.overwrite})
    formal_freeze = None
    formal_freeze_sha256 = None
    formal_manifest_sha256 = None
    source_archive_sha256 = None
    source_manifest_sha256 = None
    development_evidence_sha256 = None
    analysis_script_sha256 = None
    protocol_sha256 = None
    generator_sha256 = None
    source_code_sha256 = task_identity(tasks[0])[1]["code_sha256"]
    method_effective_configs = {
        method: resolve_method_config(method, tasks[0]) for method in methods
    }
    method_baseline_config_sha256 = {}
    for method in methods:
        method_task = next(task for task in tasks if task["method"] == method)
        method_baseline_config_sha256[method] = task_identity(method_task)[1]["baseline_config_sha256"]
    common_settings = {
        "instances": args.instances,
        "families": [int(x) for x in args.families.split(",") if x],
        "intensities": [int(x) for x in args.intensities.split(",") if x],
        "zero_groups": [x for x in args.zero_groups.split(",") if x],
        "mask_mode": args.mask_mode,
        "cross_exchange": not args.no_cross_exchange,
        "ppo_model": args.ppo_model,
        "overwrite": bool(args.overwrite),
    }
    environment = environment_fingerprint(quota)
    if args.instances == "formal_v3":
        freeze_path = ROOT / "results" / "FORMAL_V3_FREEZE.json"
        formal_manifest_path = ROOT / "datasets" / "formal_v3" / "manifest.json"
        formal_freeze = json.loads(freeze_path.read_text())
        formal_freeze_sha256 = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        formal_manifest_sha256 = hashlib.sha256(formal_manifest_path.read_bytes()).hexdigest()
        archive_path = ROOT / formal_freeze["source_archive_path"]
        source_manifest_path = ROOT / formal_freeze["source_manifest_path"]
        development_evidence_path = ROOT / formal_freeze["development_evidence_manifest_path"]
        analysis_path = ROOT / formal_freeze["analysis_script_path"]
        protocol_path = ROOT / formal_freeze["protocol_path"]
        source_archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        source_manifest_sha256 = hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
        development_evidence_sha256 = hashlib.sha256(development_evidence_path.read_bytes()).hexdigest()
        analysis_script_sha256 = hashlib.sha256(analysis_path.read_bytes()).hexdigest()
        protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        if source_archive_sha256 != formal_freeze.get("source_archive_sha256"):
            raise SystemExit("formal_v3 immutable source archive SHA256 mismatch")
        if source_manifest_sha256 != formal_freeze.get("source_manifest_sha256"):
            raise SystemExit("formal_v3 source content manifest SHA256 mismatch")
        if development_evidence_sha256 != formal_freeze.get("development_evidence_manifest_sha256"):
            raise SystemExit("formal_v3 development evidence manifest SHA256 mismatch")
        if analysis_script_sha256 != formal_freeze.get("analysis_script_sha256"):
            raise SystemExit("formal_v3 analysis script SHA256 mismatch")
        if protocol_sha256 != formal_freeze.get("protocol_sha256"):
            raise SystemExit("formal_v3 protocol SHA256 mismatch")
        if formal_freeze.get("formal_v3_manifest_sha256") != formal_manifest_sha256:
            raise SystemExit("formal_v3 freeze/map-manifest SHA256 mismatch")
        generator_path = ROOT / "results" / "experiment_script_archive" / "make_formal_v3.py"
        generator_sha256 = hashlib.sha256(generator_path.read_bytes()).hexdigest()
        if formal_freeze.get("generator_sha256") != generator_sha256:
            raise SystemExit("formal_v3 generator SHA256 mismatch")
        if formal_freeze.get("source_code_sha256") != source_code_sha256:
            raise SystemExit("formal_v3 freeze/source-code SHA256 mismatch")
        if formal_freeze.get("method_baseline_config_sha256") != method_baseline_config_sha256:
            raise SystemExit("formal_v3 baseline parameter profile hash mismatch")
        if formal_freeze.get("common_settings") != common_settings:
            raise SystemExit("formal_v3 common CLI settings differ from freeze")
        if formal_freeze.get("environment") != environment:
            raise SystemExit("formal_v3 execution environment differs from freeze")
        if args.overwrite or args.ppo_model is not None:
            raise SystemExit("formal_v3 forbids overwrite and external model checkpoints")
        if methods != formal_freeze.get("methods"):
            raise SystemExit("formal_v3 method list differs from frozen protocol")
        if seeds != formal_freeze.get("solver_seeds"):
            raise SystemExit("formal_v3 solver seeds differ from frozen protocol")
        if float(args.seconds) not in [float(x) for x in formal_freeze.get("budgets_seconds", [])]:
            raise SystemExit("formal_v3 budget differs from frozen protocol")
        if method_effective_configs != formal_freeze.get("method_effective_configs"):
            raise SystemExit("formal_v3 effective method configs differ from frozen protocol")
        if args.workers != formal_freeze.get("workers") or args.max_steps != formal_freeze.get("max_steps"):
            raise SystemExit("formal_v3 worker/max-step settings differ from frozen protocol")
        if len(paths) != 36 or len(tasks) != 36 * len(methods) * len(seeds):
            raise SystemExit("formal_v3 task matrix size differs from frozen protocol")
        expected_outdir = ROOT / "results" / f"v5_formal_v3_{int(args.seconds)}s"
        if outdir.resolve() != expected_outdir.resolve():
            raise SystemExit(f"formal_v3 output path must be {expected_outdir}")
        if outdir.exists():
            raise SystemExit(f"formal_v3 output directory already exists; refusing overwrite/resume: {outdir}")
    formal_v4_manifest_sha256 = None
    if args.instances == "formal_v4":
        freeze_path = ROOT / "results" / "FORMAL_V4_FREEZE.json"
        formal_manifest_path = ROOT / "datasets" / "formal_v4" / "manifest.json"
        formal_freeze = json.loads(freeze_path.read_text())
        formal_freeze_sha256 = hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        formal_v4_manifest_sha256 = hashlib.sha256(formal_manifest_path.read_bytes()).hexdigest()
        archive_path = ROOT / formal_freeze["source_archive_path"]
        source_manifest_path = ROOT / formal_freeze["source_manifest_path"]
        development_evidence_path = ROOT / formal_freeze["development_evidence_manifest_path"]
        analysis_path = ROOT / formal_freeze["analysis_script_path"]
        protocol_path = ROOT / formal_freeze["protocol_path"]
        source_archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        source_manifest_sha256 = hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
        development_evidence_sha256 = hashlib.sha256(development_evidence_path.read_bytes()).hexdigest()
        analysis_script_sha256 = hashlib.sha256(analysis_path.read_bytes()).hexdigest()
        protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        if source_archive_sha256 != formal_freeze.get("source_archive_sha256"):
            raise SystemExit("formal_v4 immutable source archive SHA256 mismatch")
        if source_manifest_sha256 != formal_freeze.get("source_manifest_sha256"):
            raise SystemExit("formal_v4 source content manifest SHA256 mismatch")
        if development_evidence_sha256 != formal_freeze.get("development_evidence_manifest_sha256"):
            raise SystemExit("formal_v4 development evidence manifest SHA256 mismatch")
        if analysis_script_sha256 != formal_freeze.get("analysis_script_sha256"):
            raise SystemExit("formal_v4 analysis script SHA256 mismatch")
        if protocol_sha256 != formal_freeze.get("protocol_sha256"):
            raise SystemExit("formal_v4 protocol SHA256 mismatch")
        if formal_freeze.get("formal_v4_manifest_sha256") != formal_v4_manifest_sha256:
            raise SystemExit("formal_v4 freeze/map-manifest SHA256 mismatch")
        generator_path = ROOT / "results" / "experiment_script_archive" / "make_formal_v4.py"
        generator_sha256 = hashlib.sha256(generator_path.read_bytes()).hexdigest()
        if formal_freeze.get("generator_sha256") != generator_sha256:
            raise SystemExit("formal_v4 generator SHA256 mismatch")
        if formal_freeze.get("source_code_sha256") != source_code_sha256:
            raise SystemExit("formal_v4 freeze/source-code SHA256 mismatch")
        if formal_freeze.get("method_baseline_config_sha256") != method_baseline_config_sha256:
            raise SystemExit("formal_v4 baseline parameter profile hash mismatch")
        if formal_freeze.get("common_settings") != common_settings:
            raise SystemExit("formal_v4 common CLI settings differ from freeze")
        if formal_freeze.get("environment") != environment:
            raise SystemExit("formal_v4 execution environment differs from freeze")
        if args.overwrite or args.ppo_model is not None:
            raise SystemExit("formal_v4 forbids overwrite and external model checkpoints")
        if methods != formal_freeze.get("methods"):
            raise SystemExit("formal_v4 method list differs from frozen protocol")
        if seeds != formal_freeze.get("solver_seeds"):
            raise SystemExit("formal_v4 solver seeds differ from frozen protocol")
        if float(args.seconds) not in [float(x) for x in formal_freeze.get("budgets_seconds", [])]:
            raise SystemExit("formal_v4 budget differs from frozen protocol")
        if method_effective_configs != formal_freeze.get("method_effective_configs"):
            raise SystemExit("formal_v4 effective method configs differ from frozen protocol")
        if args.workers != formal_freeze.get("workers") or args.max_steps != formal_freeze.get("max_steps"):
            raise SystemExit("formal_v4 worker/max-step settings differ from frozen protocol")
        if len(paths) != 36 or len(tasks) != 36 * len(methods) * len(seeds):
            raise SystemExit("formal_v4 task matrix size differs from frozen protocol")
        expected_outdir = ROOT / "results" / f"v5_formal_v4_{int(args.seconds)}s"
        if outdir.resolve() != expected_outdir.resolve():
            raise SystemExit(f"formal_v4 output path must be {expected_outdir}")
        if outdir.exists():
            raise SystemExit(f"formal_v4 output directory already exists; refusing overwrite/resume: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)
    if (outdir / "manifest.json").exists():
        raise SystemExit("existing manifest: choose a new output directory to preserve run provenance")
    try:
        quota_text = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        cpu_quota = None if quota_text[0] == "max" else float(quota_text[0]) / float(quota_text[1])
    except (OSError, ValueError, IndexError, ZeroDivisionError):
        cpu_quota = None
    manifest = {"instances": paths, "methods": methods, "seeds": seeds,
                "seconds": args.seconds, "tasks": len(tasks), "workers": args.workers,
                "cpu_quota": cpu_quota, "cross_exchange": not args.no_cross_exchange,
                "max_steps": args.max_steps, "families": args.families,
                "intensities": args.intensities, "zero_groups": args.zero_groups,
                "mask_mode": args.mask_mode, "started": time.time(),
                "method_effective_configs": method_effective_configs,
                "method_baseline_config_sha256": method_baseline_config_sha256,
                "common_settings": common_settings,
                "environment": environment,
                "source_code_sha256": source_code_sha256,
                "formal_freeze_sha256": formal_freeze_sha256,
                "formal_v3_manifest_sha256": formal_manifest_sha256,
                "formal_v4_manifest_sha256": formal_v4_manifest_sha256,
                "source_archive_sha256": source_archive_sha256,
                "source_manifest_sha256": source_manifest_sha256,
                "development_evidence_manifest_sha256": development_evidence_sha256,
                "analysis_script_sha256": analysis_script_sha256,
                "protocol_sha256": protocol_sha256,
                "generator_sha256": generator_sha256,
                "argv": sys.argv}
    with open(outdir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"[bench] {len(paths)} instances x {len(methods)} methods x {len(seeds)} seeds "
          f"= {len(tasks)} tasks, {args.seconds}s budget, {args.workers} workers", flush=True)
    t0 = time.time()
    done = 0
    errors = 0
    with Pool(processes=args.workers) as pool:
        for res in pool.imap_unordered(run_one, tasks, chunksize=1):
            done += 1
            if res.get("status") in ("error", "invalid"):
                errors += 1
                print("[error]", res.get("instance"), res.get("method"), res.get("seed"),
                      res.get("error", "")[:200], flush=True)
            if done % max(1, len(tasks) // 20) == 0 or done == len(tasks):
                print(f"[bench] {done}/{len(tasks)} done, {errors} errors, "
                      f"{time.time() - t0:.1f}s", flush=True)
    manifest["finished"] = time.time()
    manifest["errors"] = errors
    with open(outdir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"[bench] finished in {time.time() - t0:.1f}s, errors={errors}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
