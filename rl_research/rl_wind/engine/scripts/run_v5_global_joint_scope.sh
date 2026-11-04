#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rivermind-data/ca_rl_completion_v5_staging/code
cd "$ROOT"
PY=/opt/conda/bin/python
METHODS=m1d,m1d_global_asg,m1d_global_joint,m1d_global_all,m2,m2_global_asg,m2_global_joint,m2_global_all
SEEDS=101,102,103,104,105
WORKERS=8
for budget in 6 12; do
  out="results/v5_joint_scope_full_search_${budget}s"
  if [ -e "$out" ]; then
    echo "output exists; preserve and inspect: $out" >&2
    exit 10
  fi
  echo "[JOINT_SCOPE_FULL_SEARCH] budget=${budget}s methods=$METHODS"
  "$PY" -B scripts/run_bench.py --instances val --methods "$METHODS" \
    --seeds "$SEEDS" --seconds "$budget" --workers "$WORKERS" --out "$out"
done
"$PY" -B results/experiment_script_archive/analyze_v5_global_joint_scope.py
printf "V5_GLOBAL_JOINT_SCOPE_COMPLETE\n" > results/V5_GLOBAL_JOINT_SCOPE_COMPLETE
echo "V5_GLOBAL_JOINT_SCOPE_COMPLETE"
