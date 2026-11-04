#!/usr/bin/env python
"""PPO training for the CA-RL macro-action controller.

Collects episodes in parallel (one process per episode), updates a shared MLP,
validates on the held-out validation split and keeps the best checkpoint.
"""
import argparse
import json
import os
import random
import sys
import time
import hashlib
import platform
from multiprocessing import Pool
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carl.core import split_instances  # noqa: E402
from carl.ppo import (PolicyNet, collect_episode, flatten_episodes,  # noqa: E402
                      ppo_update, save_model)
from carl.runner import run_one  # noqa: E402

INST_DIR = ROOT / "external" / "LRPHSD" / "data" / "Instances_Alg"


VAL_LAMS = (0.0, 0.5, 1.0, 2.0)
VAL_RESERVES = (0.0,)


def evaluate_checkpoint(pool, model_path, paths, seconds, seed=7, workers=8,
                        intensities="0,1,2", deterministic=False):
    from carl.search import reference_point
    outdir = Path(model_path).parent / ("eval_" + str(time.time_ns()) + ("_det" if deterministic else "_stochastic"))
    tasks = [{"instance": Path(p).stem, "instance_path": str(p), "method": "m6",
              "seed": seed, "seconds": seconds, "outdir": str(outdir),
              "model_path": str(model_path), "overwrite": True,
              "deterministic": deterministic,
              "lam": VAL_LAMS[i % len(VAL_LAMS)],
              "reserve": VAL_RESERVES[(i // len(VAL_LAMS)) % len(VAL_RESERVES)],
              "intensities": [int(x) for x in intensities.split(",") if x]}
             for i, p in enumerate(paths)]
    res = pool.map(run_one, tasks, chunksize=1)
    if len(res) != len(paths) or any(r.get("status") != "ok" for r in res):
        raise ValueError("incomplete or invalid validation checkpoint")
    def score(r):
        c, m = reference_point(r["instance"])
        return r["cost"] / c + r["lam"] * r["makespan"] / m
    costs = [score(r) for r in res]
    rows = [{"instance": r["instance"], "seed": r["seed"], "cost": r["cost"],
             "solver_seconds": r.get("solver_seconds"),
             "evaluation_seconds": r.get("evaluation_seconds"),
             "end_to_end_seconds": r.get("end_to_end_seconds"),
             "task_identity": r.get("task_identity")} for r in res]
    return {"mean_cost": float(np.mean(costs)) if costs else float("inf"),
            "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--episode-seconds", type=float, default=0.30)
    ap.add_argument("--max-steps", type=int, default=20000)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--entropy", type=float, default=0.04)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--eval-every", type=int, default=5)
    ap.add_argument("--val-seconds", type=float, default=2.0)
    ap.add_argument("--val-instances", type=int, default=24)
    ap.add_argument("--resume", default=None)
    ap.add_argument("--allow-reward-schema-mismatch", action="store_true",
                    help="allow BC warm-start across reward schemas; core model/state/action schemas must still match")
    ap.add_argument("--intensities", default="0,1,2")
    ap.add_argument("--lams", default="0,0.25,0.5,1,2,4",
                    help="preference set; one lambda sampled per training episode")
    ap.add_argument("--reserves", default="0",
                    help="battery-reserve set; one sampled per training episode")
    args = ap.parse_args()
    LAMS = [float(x) for x in args.lams.split(",")]
    RESERVES = [float(x) for x in args.reserves.split(",")]

    try:
        quota_text = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota_text[0] != "max":
            quota = max(1, int(int(quota_text[0]) / int(quota_text[1])))
            if args.workers > quota:
                print(f"[train] cgroup quota={quota}; clamping workers {args.workers}->{quota}",
                      flush=True)
                args.workers = quota
    except (OSError, ValueError, IndexError, ZeroDivisionError):
        pass

    torch.set_num_threads(1)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    splits = split_instances(INST_DIR)
    train_paths = [str(p) for p in splits["train"]]
    val_all = [str(p) for p in splits["val"]]
    rng = random.Random(args.seed)
    val_paths = rng.sample(val_all, min(args.val_instances, len(val_all)))

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def code_digest():
        items = []
        for directory in ("carl", "lrphsd", "native", "scripts", "configs"):
            items.extend(p for p in sorted((ROOT / directory).glob("*"))
                         if p.is_file() and p.suffix in (".py", ".c", ".so", ".json", ".sh"))
        for source_dir in ("official_source", "instrumented_source"):
            items.extend((ROOT / "reference" / "java" / source_dir).glob("*.java"))
        lock = ROOT / "reference" / "java" / "SOURCE_LOCK.json"
        if lock.exists():
            items.append(lock)
        items = sorted(set(p for p in items if p.is_file()))
        return hashlib.sha256("".join(sha(p) for p in items).encode()).hexdigest()
    outdir = Path(args.out)
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit("training output directory is non-empty; choose a new directory")
    outdir.mkdir(parents=True, exist_ok=True)
    model = PolicyNet()
    if args.resume:
        from carl.ppo import load_model
        model = load_model(args.resume,
                           allow_reward_schema_mismatch=args.allow_reward_schema_mismatch)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    ckpt = outdir / "current.pt"
    best_ckpt = outdir / "best.pt"
    save_model(model, ckpt)
    rollouts_dir = outdir / "rollouts"
    rollouts_dir.mkdir(exist_ok=True)
    train_hashes = {Path(p).stem: sha(p) for p in train_paths}
    val_hashes = {Path(p).stem: sha(p) for p in val_paths}
    run_manifest = {
        "algorithm": "CA-RL-TSALNS-PPO-operator-state-v4",
        "seed": args.seed, "argv": sys.argv,
        "args": vars(args), "workers": args.workers,
        "python": platform.python_version(), "torch": torch.__version__,
        "numpy": np.__version__, "cpu_quota": Path("/sys/fs/cgroup/cpu.max").read_text().strip()
            if Path("/sys/fs/cgroup/cpu.max").exists() else None,
        "model_schema": __import__("carl.ppo", fromlist=["MODEL_SCHEMA"]).MODEL_SCHEMA,
        "state_schema": __import__("carl.state", fromlist=["STATE_SCHEMA"]).STATE_SCHEMA,
        "action_schema": __import__("carl.state", fromlist=["ACTION_SCHEMA"]).ACTION_SCHEMA,
        "reward_schema": __import__("carl.state", fromlist=["REWARD_SCHEMA"]).REWARD_SCHEMA,
        "reward_ablation": ("remove_explicit_runtime_penalty" if args.allow_reward_schema_mismatch else None),
        "train_instances": train_hashes, "validation_instances": val_hashes,
        "code_sha256": code_digest(),
        "resume_checkpoint": str(args.resume) if args.resume else None,
        "resume_checkpoint_sha256": sha(args.resume) if args.resume else None,
        "started_unix": time.time(),
    }
    (outdir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=1))
    history = []
    best_val = float("inf")
    pool = Pool(processes=args.workers)
    t0 = time.time()
    try:
        for it in range(1, args.iters + 1):
            model.eval()
            save_model(model, ckpt)
            tasks = []
            for w in range(args.workers):
                p = train_paths[(it * args.workers + w) % len(train_paths)]
                tasks.append({"instance": Path(p).stem, "instance_path": p,
                              "seed": args.seed * 1000 + it * 97 + w,
                              "seconds": args.episode_seconds,
                              "max_steps": args.max_steps,
                              "model_path": str(ckpt),
                              "lam": rng.choice(LAMS), "reserve": rng.choice(RESERVES),
                              "intensities": [int(x) for x in args.intensities.split(",") if x]})
            t_col = time.time()
            episodes = pool.map(collect_episode, tasks, chunksize=1)
            col_s = time.time() - t_col
            batch = flatten_episodes(episodes)
            rollout_path = rollouts_dir / f"iteration_{it:04d}.npz"
            np.savez_compressed(rollout_path, **batch)
            episode_meta = [{k: v for k, v in ep.items() if k != "transitions"}
                            for ep in episodes]
            (rollouts_dir / f"iteration_{it:04d}_episodes.json").write_text(
                json.dumps(episode_meta, indent=1, default=str))
            model.train()
            stats = ppo_update(model, opt, batch, epochs=args.epochs,
                               minibatch=4096, entropy_coef=args.entropy)
            rec = {"iter": it, "episodes": len(episodes),
                   "transitions": int(len(batch["feat"])),
                   "mean_episode_cost": float(np.mean([e["cost"] for e in episodes])),
                   "mean_initial_cost": float(np.mean([e["initial_cost"] for e in episodes])),
                   "mean_steps": float(np.mean([e["steps"] for e in episodes])),
                   "mean_policy_ms_per_step": float(np.mean([
                       e.get("counters", {}).get("policy_seconds", 0.0) / max(e["steps"], 1) * 1000.0
                       for e in episodes])),
                   "mean_decision_ms_per_step": float(np.mean([
                       e.get("counters", {}).get("decision_seconds", 0.0) / max(e["steps"], 1) * 1000.0
                       for e in episodes])),
                   "mean_best_updates": float(np.mean([
                       e.get("counters", {}).get("best_updates", 0) for e in episodes])),
                   "mean_episode_reward": float(np.mean([
                       sum(t["reward"] for t in e["transitions"]) for e in episodes])),
                   "collect_seconds": col_s,
                   "rollout_sha256": hashlib.sha256(rollout_path.read_bytes()).hexdigest(),
                   "rollout_records": len(batch["feat"]),
                   "checkpoint_input_sha256": sha(ckpt), **stats}
            if it % args.eval_every == 0 or it == args.iters:
                model.eval()
                save_model(model, ckpt)
                # Select checkpoints using the stochastic policy that is the
                # primary deployment mode; Argmax is logged only as a diagnostic.
                val_stochastic = evaluate_checkpoint(pool, ckpt, val_paths,
                                                     args.val_seconds, seed=7,
                                                     intensities=args.intensities,
                                                     deterministic=False)
                val_deterministic = evaluate_checkpoint(pool, ckpt, val_paths,
                                                        args.val_seconds, seed=7,
                                                        intensities=args.intensities,
                                                        deterministic=True)
                val_cost = val_stochastic["mean_cost"]
                val_det_cost = val_deterministic["mean_cost"]
                (outdir / f"validation_{it:04d}_stochastic.json").write_text(
                    json.dumps(val_stochastic, indent=1))
                (outdir / f"validation_{it:04d}_deterministic.json").write_text(
                    json.dumps(val_deterministic, indent=1))
                rec["val_cost_stochastic"] = val_cost
                rec["val_cost_deterministic"] = val_det_cost
                rec["val_cost"] = val_cost
                if val_cost < best_val:
                    best_val = val_cost
                    save_model(model, best_ckpt)
                    rec["best_checkpoint_sha256"] = sha(best_ckpt)
                    rec["best"] = True
            history.append(rec)
            torch.save({"iteration": it, "model_state": model.state_dict(),
                        "optimizer_state": opt.state_dict(),
                        "python_rng_state": random.getstate(),
                        "numpy_rng_state": np.random.get_state(),
                        "torch_rng_state": torch.get_rng_state()},
                       outdir / "training_state.pt")
            print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v)
                              for k, v in rec.items()}), flush=True)
            with open(outdir / "history.json", "w") as f:
                json.dump(history, f, indent=1)
    finally:
        pool.close()
        pool.join()
    save_model(model, outdir / "final.pt")
    summary = {"iters": args.iters, "best_val": best_val,
               "best_ckpt": str(best_ckpt), "final_ckpt": str(outdir / "final.pt"),
               "best_checkpoint_sha256": sha(best_ckpt) if best_ckpt.exists() else None,
               "final_checkpoint_sha256": sha(outdir / "final.pt"),
               "training_state_sha256": sha(outdir / "training_state.pt"),
               "elapsed": time.time() - t0, "selection_metric": "stochastic_val_cost",
               "validation_instances": val_hashes, "validation_seconds": args.val_seconds,
               "train_instances": train_hashes, "code_sha256": run_manifest["code_sha256"],
               "run_manifest": str(outdir / "run_manifest.json"), "argv": sys.argv}
    with open(outdir / "summary.json", "w") as f:
        json.dump(summary, f, indent=1)
    print(f"[train] done in {time.time() - t0:.1f}s, best val {best_val:.4f}")


if __name__ == "__main__":
    main()
