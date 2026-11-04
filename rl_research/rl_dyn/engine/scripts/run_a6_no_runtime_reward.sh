#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="../training_runs_v5_a6_no_runtime_reward_20261101"
BASE="../ca_rl_completion_v5_staging/training_runs_v5_final72"
mkdir -p "$OUT"
if [ -e "$OUT/A6_TRAINING_COMPLETED" ]; then
  echo "A6 completion marker exists; refusing to overwrite" >&2
  exit 2
fi
for seed in 11 23 37; do
  ppo="$OUT/PPO_seed$seed"
  bc="$BASE/BC_seed$seed/bc.pt"
  [ -f "$bc" ] || { echo "missing BC warm-start checkpoint: $bc" >&2; exit 3; }
  [ ! -e "$ppo" ] || { echo "A6 output exists; preserve and inspect: $ppo" >&2; exit 4; }
  /opt/conda/bin/python -B scripts/train_ppo.py \
    --iters 60 --workers 8 --episode-seconds 0.3 --max-steps 20000 \
    --lr 0.0002 --entropy 0.02 --epochs 6 \
    --seed "$seed" --eval-every 5 --val-seconds 2 --val-instances 24 \
    --resume "$bc" --allow-reward-schema-mismatch --out "$ppo" \
    > "$OUT/PPO_seed$seed.log" 2>&1
done
printf "A6_PPO_NO_EXPLICIT_RUNTIME_REWARD_COMPLETED\n" > "$OUT/A6_TRAINING_COMPLETED"
echo "A6_TRAINING_COMPLETED"
