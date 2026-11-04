#!/usr/bin/env bash
# Formal CA-RL-TSALNS v1 experiment suite (run on hn01).
# Everything is written to a fresh run directory; nothing is overwritten.
set -euo pipefail
cd /root/rivermind-data/ca_rl_v1_auditfix_20261030
PY=/opt/conda/bin/python
PPO=${PPO:-runs/ppo_s4/best.pt}
W=10

echo "[formal] main 6s test split"
$PY -B scripts/run_bench.py --instances test \
  --methods m0,m0p,m1,m1c,m1d,m2,m3,m4,m5,m6 \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W \
  --intensities 0,1 --ppo-model "$PPO" \
  --out results/formal_test_6s

echo "[formal] budget sensitivity 2s / 12s (5 seeds)"
$PY -B scripts/run_bench.py --instances test --methods m0,m1d,m2,m5,m6 \
  --seeds 1,2,3,4,5 --seconds 2 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --out results/formal_test_2s
$PY -B scripts/run_bench.py --instances test --methods m0,m1d,m2,m5,m6 \
  --seeds 1,2,3,4,5 --seconds 12 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --out results/formal_test_12s

echo "[formal] ablations on test (5 seeds, 6s)"
$PY -B scripts/run_bench.py --instances test --methods m6_nojoint \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --families 0,1,2 --out results/abl_no_joint
$PY -B scripts/run_bench.py --instances test --methods m6_nomask \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --mask-mode all --out results/abl_no_mask
$PY -B scripts/run_bench.py --instances test --methods m6_zeroasg \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --zero-groups assignment --out results/abl_zero_assignment
$PY -B scripts/run_bench.py --instances test --methods m6_zerodrone \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --zero-groups drone --out results/abl_zero_drone
$PY -B scripts/run_bench.py --instances test --methods m6_zerohist \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1 \
  --ppo-model "$PPO" --zero-groups history --out results/abl_zero_history
$PY -B scripts/run_bench.py --instances test --methods m6_int2 \
  --seeds 1,2,3,4,5 --seconds 6 --workers $W --intensities 0,1,2 \
  --ppo-model "$PPO" --out results/abl_intensity_all

echo "[formal] analyses"
$PY -B scripts/analyze.py --run results/formal_test_6s \
  --out results/formal_test_6s/analysis --reference m1d
$PY -B scripts/analyze.py --run results/formal_test_2s \
  --out results/formal_test_2s/analysis --reference m1d
$PY -B scripts/analyze.py --run results/formal_test_12s \
  --out results/formal_test_12s/analysis --reference m1d
$PY -B scripts/analyze.py --run results/formal_test_6s,results/abl_no_joint,results/abl_no_mask,results/abl_zero_assignment,results/abl_zero_drone,results/abl_zero_history,results/abl_intensity_all \
  --out results/ablation_analysis --reference m6
echo "[formal] done"
