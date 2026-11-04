#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rivermind-data/ca_rl_completion_v5_staging/code
cd "$ROOT"
PY=/opt/conda/bin/python
[ -f results/V5_GLOBAL_REPAIR_FINALISTS_10SEED_COMPLETE ] || {
  echo "same-source non-PPO finalist confirmation must complete first" >&2
  exit 9
}
[ -f results/v5_final_nonppo_baseline.txt ] || {
  echo "selected non-PPO baseline file missing" >&2
  exit 10
}
METHODS=m0,m0frozen,m0paper
SEEDS=101,102,103,104,105,106,107,108,109,110
WORKERS=8
for budget in 6 12; do
  out="results/v5_m0_parameter_profile_10seed_${budget}s"
  if [ -e "$out" ]; then
    echo "output exists; preserve and inspect before rerun: $out" >&2
    exit 10
  fi
  echo "[M0_PROFILE_VALIDATION] budget=${budget}s methods=$METHODS"
  "$PY" -B scripts/run_bench.py --instances val --methods "$METHODS" \
    --seeds "$SEEDS" --seconds "$budget" --workers "$WORKERS" --out "$out"
done
"$PY" -B results/experiment_script_archive/analyze_v5_m0_parameter_profile.py
printf "V5_M0_PROFILE_VALIDATION_COMPLETE\n" > results/V5_M0_PROFILE_VALIDATION_COMPLETE
echo "V5_M0_PROFILE_VALIDATION_COMPLETE"
