#!/bin/bash
set -euo pipefail
D=/root/rivermind-data/ca_rl_completion_v5_a6_no_runtime_reward_20261101
PY=/opt/conda/bin/python
PPO=/root/rivermind-data/training_runs_v5_a6_no_runtime_reward_20261101/PPO_seed23/best.pt
METHODS=m2_global_nojoint,m2_global_asg,m6_global_asg,m6_global_nojoint,m6_global_nomask,m6_global_zeroasg,m6_global_zerodrone,m6_global_zerohist,m6_global_zeroglobal,m6_global_nohighint
SEEDS=101,102,103
W=10
for SEC in 6 12; do
  OUT="$D/results/v5_state_ablation_20261102_$SEC"s
  if [ -e "$OUT/manifest.json" ]; then
    echo "refusing existing output $OUT"
    exit 3
  fi
  echo "START state ablations $SEC s $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  "$PY" -B "$D/scripts/run_bench.py" \
    --instances val --methods "$METHODS" --seeds "$SEEDS" \
    --seconds "$SEC" --workers "$W" --ppo-model "$PPO" \
    --out "$OUT"
  echo "FINISH state ablations $SEC s $(date -u +%Y-%m-%dT%H:%M:%SZ)"
done
echo "START analysis $(date -u +%Y-%m-%dT%H:%M:%SZ)"
"$PY" -B "$D/scripts/analyze.py" \
  --run "$D/results/v5_state_ablation_20261102_6s,$D/results/v5_state_ablation_20261102_12s" \
  --out "$D/results/v5_state_ablation_20261102_analysis" \
  --reference m2_global_nojoint --baseline m2_global_nojoint
echo "FINISH analysis $(date -u +%Y-%m-%dT%H:%M:%SZ)"
