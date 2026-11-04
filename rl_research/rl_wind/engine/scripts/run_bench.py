#!/usr/bin/env python
"""Run a CA-RL benchmark over instances, methods and seeds in parallel.

Example:
  python -B scripts/run_bench.py --split dev12 --methods m0,m1,m2 --seeds 1,2,3 \
      --seconds 6 --workers 32 --out results/pilot_dev12
"""
import argparse
import hashlib
import json
import os
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
from carl.runner import run_one  # noqa: E402

INST_DIR = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"
DEV12 = ["3_10_1", "3_20_1", "4_20_1", "4_30_1", "5_35_1", "5_35_5",
         "6_50_1", "7_65_1", "8_80_1", "8_80_5", "9_95_1", "10_110_1"]


def select_instances(spec):
    if spec == "dev12":
        return [str(INST_DIR / (n + ".txt")) for n in DEV12]
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
    ap.add_argument("--lams", default="0")
    ap.add_argument("--reserves", default="0")
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
    outdir.mkdir(parents=True, exist_ok=True)
    if (outdir / "manifest.json").exists():
        raise SystemExit("existing manifest: choose a new output directory to preserve run provenance")

    tasks = []
    for p in paths:
        name = Path(p).stem
        for m in methods:
          for lam in [float(x) for x in args.lams.split(",")]:
           for rsv in [float(x) for x in args.reserves.split(",")]:
            for s in seeds:
                tasks.append({"lam": lam, "reserve": rsv,"instance": name, "instance_path": p, "method": m,
                              "seed": s, "seconds": args.seconds, "outdir": str(outdir),
                              "max_steps": args.max_steps,
                              "model_path": args.ppo_model,
                              "families": [int(x) for x in args.families.split(",") if x],
                              "zero_groups": [x for x in args.zero_groups.split(",") if x],
                              "mask_mode": args.mask_mode,
                              "intensities": [int(x) for x in args.intensities.split(",") if x],
                              "cross_exchange": not args.no_cross_exchange,
                              "overwrite": args.overwrite})
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
