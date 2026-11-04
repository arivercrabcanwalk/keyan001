# Current-source CA-RL state/action ablation protocol — 2026-11-02

**Branch:** /root/rivermind-data/ca_rl_completion_v5_a6_no_runtime_reward_20261101  
**Status:** Prepared; do not launch until the Route-RL Stage-A equal-budget matrix releases the CPU allocation.  
**Evidence class:** Development validation only. Seeds 7–8 have prior checkpoint-selection and development use; this is not a blind test.

## 1. Purpose

Complete the remaining current-source Phase-3 ablations from the original project plan without reopening any test set. This matrix is distinct from the historical 2,640-task ablation package from the older source branch.

## 2. Frozen design

- Maps: 24 validation maps (12 size groups × geometry seeds 7–8).
- Solver seeds: 101, 102, 103.
- Budgets: 6s and 12s.
- Workers: 10 (subject to the verified server CPU quota).
- PPO checkpoint: training_runs_v5_a6_no_runtime_reward_20261101/PPO_seed23/best.pt.
- Common objective, initializer, native kernel, independent evaluator and source version.
- All methods use global Assignment receiver scope where applicable.
- The method-specific masks/feature groups/intensity limits are the only intended differences.
- No historical test seeds, Formal v3, Formal v4 or locked_v2 objective values are used for tuning.

## 3. Method matrix

| Method | Ablation purpose |
|---|---|
| m2_global_nojoint | Strong non-RL NoJoint reference |
| m2_global_asg | Full Joint adaptive-weight control |
| m6_global_asg | Full PPO reference |
| m6_global_nojoint | A1/A2 control: PPO without Joint family |
| m6_global_nomask | A5: remove macro action mask |
| m6_global_zeroasg | A3: remove Assignment state group |
| m6_global_zerodrone | A4: remove SD/LD drone state group |
| m6_global_zerohist | A7: remove history/search-history group |
| m6_global_zeroglobal | A7: remove global search state group |
| m6_global_nohighint | A10: remove high-intensity action level |

Feature-zeroing variants are inference-time ablations using the same frozen PPO checkpoint; they are not retrained ablated policies. This distinction must be explicit in the report. A5 mask ablation is accepted only if all final solutions still pass the independent evaluator.

A6 Runtime Reward is a separate completed ablation and is not repeated here. A9 Bandit/Q-learning/PPO has already been compared in the controller portfolio. A8 GNN remains conditional and is not added without measured MLP representation failure.

## 4. Analysis

- Expected tasks: 24 maps × 3 solver seeds × 10 methods × 2 budgets = 1,440.
- Require exact expected row count, zero task errors, 100% final feasibility and complete provenance.
- Statistical unit: map; average three solver seeds within map.
- Report mean/median/SD, paired map-level deltas, 95% bootstrap CIs, paired Wilcoxon, rank-biserial effect size and Holm correction.
- Primary references: m6_global_asg for within-RL feature/mask/intensity ablations; m2_global_nojoint for overall non-RL comparison; m2_global_asg vs m2_global_nojoint for the Joint-family effect.
- Results are development evidence only and cannot be described as blind or confirmatory.

## 5. Launch gate

Do not start while the Route-RL Stage-A 720-task evaluation is active. After it completes and its result manifest is audited, launch the 6s matrix, then 12s, then run the paired analysis. Do not overlap the two budget matrices.
