#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
SEEDS="101,102,103"
MODEL_SEEDS="11 23 37"
WORKERS=8
PRIMARY_REF="m1d_noxchg"
mkdir -p results
FREEZE="results/LOCKED_EVAL_FREEZE.json"
if [ -e "$FREEZE" ]; then
  echo "locked evaluation freeze already exists; refusing to overwrite" >&2
  exit 2
fi
/opt/conda/bin/python - <<'PY'
import json, hashlib, platform
from pathlib import Path
root=Path(".")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
suite=json.loads((root/"datasets/locked_v2/manifest.json").read_text())
models={}
for seed in (11,23,37):
    for kind,rel in (("bc",f"../training_runs/BC_seed{seed}/bc.pt"),
                     ("ppo",f"../training_runs/PPO_seed{seed}/best.pt")):
        p=Path(rel)
        if not p.is_file(): raise SystemExit(f"missing frozen checkpoint: {p}")
        models[f"{kind}_seed{seed}"]={"path":str(p),"sha256":sha(p)}
        meta=p.parent/("bc_meta.json" if kind=="bc" else "summary.json")
        if not meta.is_file(): raise SystemExit(f"missing artifact metadata: {meta}")
        models[f"{kind}_seed{seed}"]["metadata_sha256"]=sha(meta)
freeze={
 "protocol":"locked_v2 final evaluation v1",
 "dataset_manifest_sha256":sha(root/"datasets/locked_v2/manifest.json"),
 "instances":{r["name"]:r["sha256"] for r in suite["rows"]},
 "budgets_seconds":[6,12],"solver_seeds":[101,102,103],"workers":8,
 "methods":["m0","m1d","m1d_nojoint","m1d_noxchg",
            "m6_bc_s11","m6_bc_s23","m6_bc_s37",
            "m6_ppo_s11","m6_ppo_s23","m6_ppo_s37"],
 "primary_reference":"m1d_noxchg",
 "non_rl_comparators":["m1d","m1d_nojoint","m1d_noxchg"],
 "models":models,
 "training_code_manifest_sha256":sha(root/"VERSION_MANIFEST.json"),
 "python":platform.python_version(),
 "warning":"Synthetic stress-test suite; no tuning after this freeze."
}
(root/"results/LOCKED_EVAL_FREEZE.json").write_text(json.dumps(freeze,indent=2)+"\n")
print("LOCKED_EVAL_FROZEN",len(freeze["instances"]),"maps",len(models),"checkpoints")
PY
for budget in 6 12; do
  dirs=()
  base="results/locked_baselines_${budget}s"
  /opt/conda/bin/python -B scripts/run_bench.py \
    --instances locked_v2 --methods "m0,m1d,m1d_nojoint,m1d_noxchg" \
    --seeds "$SEEDS" --seconds "$budget" --workers "$WORKERS" --out "$base"
  dirs+=("$base")
  for seed in $MODEL_SEEDS; do
    bc_method="m6_bc_s${seed}"
    bc_dir="results/locked_${bc_method}_${budget}s"
    /opt/conda/bin/python -B scripts/run_bench.py \
      --instances locked_v2 --methods "$bc_method" --seeds "$SEEDS" \
      --seconds "$budget" --workers "$WORKERS" \
      --ppo-model "../training_runs/BC_seed${seed}/bc.pt" --out "$bc_dir"
    dirs+=("$bc_dir")
    ppo_method="m6_ppo_s${seed}"
    ppo_dir="results/locked_${ppo_method}_${budget}s"
    /opt/conda/bin/python -B scripts/run_bench.py \
      --instances locked_v2 --methods "$ppo_method" --seeds "$SEEDS" \
      --seconds "$budget" --workers "$WORKERS" \
      --ppo-model "../training_runs/PPO_seed${seed}/best.pt" --out "$ppo_dir"
    dirs+=("$ppo_dir")
  done
  joined=$(IFS=,; echo "${dirs[*]}")
  /opt/conda/bin/python -B scripts/analyze.py \
    --run "$joined" --reference "$PRIMARY_REF" \
    --out "results/locked_combined_${budget}s_analysis"
  /opt/conda/bin/python -B scripts/analyze_diagnostics.py \
    --run "$base" --reference "$PRIMARY_REF" \
    --out "results/locked_baseline_${budget}s_diagnostics"
done
