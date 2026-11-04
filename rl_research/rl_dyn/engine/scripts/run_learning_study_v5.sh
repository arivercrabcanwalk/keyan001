#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="../training_runs_v5_final72"
mkdir -p "$OUT"
if [ -e "$OUT/TRAINING_COMPLETED" ]; then
  echo "training completion marker exists; refusing to overwrite" >&2
  exit 2
fi
for seed in 11 23 37; do
  bc="$OUT/BC_seed$seed"
  ppo="$OUT/PPO_seed$seed"
  if [ -e "$bc/bc.pt" ] || [ -e "$ppo/history.json" ]; then
    echo "existing partial seed output for $seed; inspect before resume" >&2
    exit 3
  fi
  /opt/conda/bin/python -B scripts/bc_pretrain.py \
    --instances 72 --seconds 6 --workers 8 --epochs 8 \
    --seed "$seed" --out "$bc" \
    > "$OUT/BC_seed$seed.log" 2>&1
  /opt/conda/bin/python -B scripts/train_ppo.py \
    --iters 60 --workers 8 --episode-seconds 0.3 --max-steps 20000 \
    --lr 0.0002 --entropy 0.02 --epochs 6 \
    --seed "$seed" --eval-every 5 --val-seconds 2 --val-instances 24 \
    --resume "$bc/bc.pt" --out "$ppo" \
    > "$OUT/PPO_seed$seed.log" 2>&1
done
printf "BC_AND_PPO_OPERATOR_LEVEL_FINAL_CODE_REWARD_V2_COMPLETED\n" > "$OUT/TRAINING_COMPLETED"
