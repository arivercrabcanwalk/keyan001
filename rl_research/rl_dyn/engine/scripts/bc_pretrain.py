#!/usr/bin/env python
"""Collect teacher trajectories and pretrain the PPO policy by behaviour cloning."""
import argparse
import json
import os
import random
import sys
import hashlib
import platform
from multiprocessing import Pool
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_name] = "1"

import torch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carl.bc import collect_task, train_bc  # noqa: E402
from carl.core import split_instances  # noqa: E402
from carl.ppo import save_model  # noqa: E402

INST_DIR = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", type=int, default=24)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--intensities", default="0,1,2")
    args = ap.parse_args()

    try:
        quota_text = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota_text[0] != "max":
            quota = max(1, int(int(quota_text[0]) / int(quota_text[1])))
            if args.workers > quota:
                print(f"[bc] cgroup quota={quota}; clamping workers {args.workers}->{quota}",
                      flush=True)
                args.workers = quota
    except (OSError, ValueError, IndexError, ZeroDivisionError):
        pass

    torch.set_num_threads(1)
    splits = split_instances(INST_DIR)
    paths = [str(p) for p in splits["train"]]
    rng = random.Random(args.seed)
    rng.shuffle(paths)
    paths = paths[:args.instances]
    tasks = [{"instance": Path(p).stem, "instance_path": p,
              "seed": args.seed * 31 + i, "seconds": args.seconds,
              "max_steps": 200000,
              "intensities": [int(x) for x in args.intensities.split(",") if x]}
             for i, p in enumerate(paths)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    with Pool(processes=args.workers) as pool:
        results = pool.map(collect_task, tasks, chunksize=1)
    records = [r for res in results for r in res["records"]]
    if not records:
        raise ValueError("teacher collection produced no state-action records")
    features = np.asarray([r[0] for r in records], dtype=np.float32)
    actions = np.asarray([r[1] for r in records], dtype=np.int64)
    masks = np.asarray([r[2] for r in records], dtype=bool)
    if not masks[np.arange(len(actions)), actions].all():
        raise ValueError("teacher dataset contains a masked action label")
    np.savez_compressed(out / "teacher_records.npz",
                        features=features, actions=actions, masks=masks)
    episode_rows = [{k: v for k, v in res.items() if k != "records"} for res in results]
    (out / "teacher_episodes.json").write_text(json.dumps(episode_rows, indent=1, default=str))
    print(f"[bc] {len(results)} instances, {len(records)} state-action pairs", flush=True)
    model = train_bc(records, epochs=args.epochs, seed=args.seed)
    save_model(model, out / "bc.pt")
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    code_files = []
    for directory in ("carl", "lrphsd", "native", "scripts", "configs"):
        code_files.extend(p for p in sorted((ROOT / directory).glob("*"))
                          if p.is_file() and p.suffix in (".py", ".c", ".so", ".json", ".sh"))
    for source_dir in ("official_source", "instrumented_source"):
        code_files.extend((ROOT / "reference" / "java" / source_dir).glob("*.java"))
    lock = ROOT / "reference" / "java" / "SOURCE_LOCK.json"
    if lock.exists():
        code_files.append(lock)
    code_files = sorted(set(p for p in code_files if p.is_file()))
    code_hash = hashlib.sha256("".join(sha(p) for p in code_files).encode()).hexdigest()
    instance_hashes = {Path(t["instance_path"]).stem: sha(t["instance_path"]) for t in tasks}
    metadata = {
        "teacher": "M1d_scheduled_joint",
        "instances": [{"name": t["instance"], "seed": t["seed"],
                       "sha256": instance_hashes[t["instance"]]} for t in tasks],
        "records": len(records), "feature_shape": list(features.shape),
        "action_shape": list(actions.shape), "mask_shape": list(masks.shape),
        "epochs": args.epochs, "seconds": args.seconds, "seed": args.seed,
        "intensities": args.intensities, "workers": args.workers,
        "python": platform.python_version(), "torch": torch.__version__,
        "numpy": np.__version__, "model_schema": __import__("carl.ppo", fromlist=["MODEL_SCHEMA"]).MODEL_SCHEMA,
        "state_schema": __import__("carl.state", fromlist=["STATE_SCHEMA"]).STATE_SCHEMA,
        "action_schema": __import__("carl.state", fromlist=["ACTION_SCHEMA"]).ACTION_SCHEMA,
        "reward_schema": __import__("carl.state", fromlist=["REWARD_SCHEMA"]).REWARD_SCHEMA,
        "code_sha256": code_hash, "teacher_records_sha256": sha(out / "teacher_records.npz"),
        "teacher_checkpoint_sha256": sha(out / "bc.pt"),
    }
    (out / "bc_meta.json").write_text(json.dumps(metadata, indent=1))
    print("[bc] saved", out / "bc.pt")


if __name__ == "__main__":
    main()
