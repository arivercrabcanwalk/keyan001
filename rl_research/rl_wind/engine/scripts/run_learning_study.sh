#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p ../training_runs
for seed in 11 23 37; do
  bc="../training_runs/BC_seed${seed}"
  ppo="../training_runs/PPO_seed${seed}"
  /opt/conda/bin/python -B scripts/bc_pretrain.py \
    --instances 24 --seconds 6 --workers 8 --epochs 8 \
    --seed "$seed" --out "$bc" \
    > "../training_runs/BC_seed${seed}.log" 2>&1
  /opt/conda/bin/python -B scripts/train_ppo.py \
    --iters 60 --workers 8 --episode-seconds 0.3 --max-steps 20000 \
    --lr 0.0002 --entropy 0.04 --epochs 6 \
    --seed "$seed" --eval-every 5 --val-seconds 2 --val-instances 24 \
    --resume "$bc/bc.pt" --out "$ppo" \
    > "../training_runs/PPO_seed${seed}.log" 2>&1
done
printf "BC_AND_PPO_TRAINING_COMPLETED\n" > ../training_runs/TRAINING_COMPLETED
