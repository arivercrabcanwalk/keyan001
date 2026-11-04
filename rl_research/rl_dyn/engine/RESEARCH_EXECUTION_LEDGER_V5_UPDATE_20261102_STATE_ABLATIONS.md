# Research execution ledger update — current-source CA-RL ablations

**Date:** 2026-11-02  
**Source branch:** /root/rivermind-data/ca_rl_completion_v5_a6_no_runtime_reward_20261101  
**Status:** Method-registry smoke passed; full 6s/12s validation matrix submitted.

## 1. Current-source ablation protocol

- 24 validation maps (geometry seeds 7–8).
- Solver seeds 101–103.
- Budgets 6s and 12s.
- Ten methods:
  m2_global_nojoint, m2_global_asg, m6_global_asg, m6_global_nojoint,
  m6_global_nomask, m6_global_zeroasg, m6_global_zerodrone,
  m6_global_zerohist, m6_global_zeroglobal, m6_global_nohighint.
- Expected full matrix: 1,440 tasks.
- Same PPO seed-23 checkpoint, same evaluator, same instance set and same source version.
- Feature-zeroing variants are inference-time ablations and will be labelled accordingly; they are not described as separately retrained policies.
- A6 runtime-reward ablation and A9 bandit/Q-learning/PPO portfolio are already completed separately.
- GNN-PPO remains conditional, not part of this matrix.

## 2. Smoke acceptance

- 24 maps × 10 methods × 1 solver seed = 240 tasks.
- Budget: 0.2s, engineering smoke only.
- 240/240 rows completed.
- 0 task errors.
- 240/240 final solutions independently feasible.
- All ten method aliases loaded successfully.
- Smoke artifacts:
  results/v5_state_ablation_smoke_20261102/SMOKE_REPORT_20261102.json
  results/v5_state_ablation_smoke_20261102/SMOKE_REPORT_20261102.md

## 3. Full matrix

The 6s and 12s matrices are submitted through:
scripts/run_state_ablations_v5_20261102.sh

Expected output directories:
- results/v5_state_ablation_20261102_6s
- results/v5_state_ablation_20261102_12s
- results/v5_state_ablation_20261102_analysis

No test-set maps are used. All results are development validation evidence.
