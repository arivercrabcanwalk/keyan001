#!/usr/bin/env python3
"""Run isolated J1b/J2b Java variants on a stratified map/seed matrix."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from run_matrix import PROFILES, ROOT, execute, write_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("J1b", "J2b"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", default="0,1,2,3,4")
    parser.add_argument("--maps-per-group", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    PROFILES[args.profile] = {"kind": "java", "class_dir": args.profile + "_classes",
                              "guard": True, "local": 100 if args.profile == "J1b" else 500,
                              "weight_upper": 5.0 if args.profile == "J1b" else 0.5}
    instance_dir = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"
    paths = sorted(path for path in instance_dir.glob("*.txt")
                   if int(path.stem.rsplit("_", 1)[1]) <= args.maps_per_group)
    expected_maps = 12 * args.maps_per_group
    if len(paths) != expected_maps:
        raise SystemExit(f"expected {expected_maps} maps, got {len(paths)}")
    seeds = [int(value) for value in args.seeds.split(",")]
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"profile": args.profile, "profile_config": PROFILES[args.profile],
                "variant_build_manifest_sha256": digest(ROOT / "reference" / "java" / (args.profile + "_build_manifest.json")),
                "official_source_lock_sha256": digest(ROOT / "reference" / "java" / "SOURCE_LOCK.json"),
                "runner_sha256": digest(Path(__file__)), "outer": 500, "seeds": seeds,
                "inputs": {path.stem: digest(path) for path in paths}}
    manifest_path = args.out / "run_manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise SystemExit("manifest mismatch")
    else:
        write_json(manifest_path, manifest)
    failures = 0
    for index, path in enumerate(paths, 1):
        for seed in seeds:
            stem = f"{args.profile}__{path.stem}__s{seed}__o500"
            output = args.out / (stem + ".json")
            if output.exists():
                old = json.loads(output.read_text())
                witness = args.out / (stem + ".solution.json.gz")
                if old["status"] != "ok" or not witness.is_file() or digest(witness) != old["solution_sha256"]:
                    raise SystemExit(f"existing task requires review: {output}")
                continue
            row = execute(path, args.profile, seed, 500, args.timeout, args.out)
            write_json(output, row)
            print(json.dumps({key: row.get(key) for key in ("task_identity", "status", "independently_feasible", "independent_cost", "elapsed_seconds", "error")}), flush=True)
            if row["status"] != "ok":
                failures += 1
        print(f"PROGRESS {index}/{len(paths)} maps profile={args.profile}", flush=True)
    print(f"COMPLETE profile={args.profile} maps={len(paths)} seeds={len(seeds)} failures={failures}", flush=True)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
