#!/usr/bin/env bash
# Corrected held-out comparison: native official Greedy + SMDP PPO.
set -euo pipefail
cd /root/rivermind-data/ca_rl_v1_auditfix_20261030
PY=/opt/conda/bin/python
W=10
SEEDS=1,2,3,4,5
OUT=results/final_corrected_core_6s

mkdir -p "$OUT"
echo "[corrected] non-RL and corrected controller baselines"
$PY -B scripts/run_bench.py --instances test --methods m0,m1d,m2,m5 \
  --seeds "$SEEDS" --seconds 6 --workers "$W" --intensities 0,1 \
  --out "$OUT/base"

echo "[corrected] BC-only policy (stochastic inference)"
$PY -B scripts/run_bench.py --instances test --methods m6bc \
  --seeds "$SEEDS" --seconds 6 --workers "$W" --intensities 0,1 \
  --ppo-model runs/bc_s4/bc.pt --out "$OUT/bc"

echo "[corrected] SMDP PPO stochastic and deterministic inference"
$PY -B scripts/run_bench.py --instances test --methods m6,m6det \
  --seeds "$SEEDS" --seconds 6 --workers "$W" --intensities 0,1 \
  --ppo-model runs/ppo_s5/best.pt --out "$OUT/ppo"

echo "[corrected] paired analysis across all methods"
$PY -B scripts/analyze.py --run "$OUT/base,$OUT/bc,$OUT/ppo" \
  --out "$OUT/analysis" --reference m1d

echo "[corrected] complete"
