# Liu2026 / CA-RL-TSALNS v5 — Research Execution Ledger

Last updated: 2026-10-31 (UTC)

## Research objective

Mainline: Greedy initialization -> coupling-aware joint neighborhoods -> strong non-RL controls -> BC/PPO controller -> multi-scale validation -> frozen 60-map stress test.

The policy controls macro-neighborhood subtype and intensity. It does not directly choose arbitrary target IDs, station pairs, or every waypoint. Fine-grained construction and repair remain heuristic.

## Phase status

| Phase | Scope | Status | Evidence / next gate |
|---|---|---|---|
| 0 | Project, source, data, baseline and historical-RL audit | **Completed with open reproduction work** | baseline_audit.md; parameter-profile reconciliation; official Greedy parity 120/120; ten exact certificates; preserve paper-parameter and released-Java profiles separately. Full paper-protocol replication remains a separate gate. |
| 1 | Coupling-aware joint neighborhoods and reconstruction | **Implemented; evidence mixed** | 17 explicit operators, 75-D state, 51 masked action slots; 120-map operator audit; independent evaluator and regression suite. Scoped-vs-full reconstruction: 508 proposals / 21 maps, both 100% feasible; map-level CI for cost difference [-1.217, 2.800], p=0.922; scoped median time 19.7 us vs full 13.3 us (1.96x). No demonstrated overall scoped-repair advantage. |
| 2 | Strong non-RL controllers | **Implemented; current v5 validation running** | M0, M1, M1c, M1d, M2, M3, M4, M5, M1d_nojoint, M1d_noxchg. V3 12-map results are historical development evidence and must not be pooled with current v5 runs. |
| 3 | CA-RL BC/PPO training | **Completed; strict artifact audit PASS** | 72 training maps per seed; three seeds 11/23/37; BC 8 epochs; PPO 60 updates; 12 stochastic/deterministic validation checkpoints; all checkpoint, rollout, map and code hashes checked. |
| 4 | Multi-step Route-RL / GNN exploration | **Deferred by design** | Start only after mainline validation identifies a concrete route-level bottleneck. Must compare with strong insertion, 2-opt, cross-trip, cross-drone and ALNS refinement. |
| 5 | Development selection and algorithm freeze | **Pending** | Select using train/validation only; freeze method, source, configs, models, statistics and analysis before opening locked_v2. |
| 6 | Final locked evaluation | **Pending** | 60 generated locked_v2 maps; synthetic scale/distribution stress test; three solver seeds; 6s and 12s; no tuning after freeze. |
| 7 | Paper and submission decision | **Pending / partial writing permitted** | Problem, model and methods can be drafted; performance and novelty claims wait for locked results and literature comparison. |

## Completed v5 training batch

Directory: ../training_runs_v5_final72

Training source digest: ba402a4d96d176cf3264790540f2882384a6deb161efe628efc892fa4fa339d8

Schemas:
- Model: policy-mlp-tanh-75x64x64x51-v2
- State: carl-state-v4-operator-level-history-75
- Action: carl-action-v4-explicit-17-operators-x-3-intensity-51
- Reward: current-cost-delta-time-best-v2

| Seed | BC teacher records | PPO updates | Validation checks | Best stochastic validation cost | Best iteration | Final stochastic validation cost |
|---:|---:|---:|---:|---:|---:|---:|
| 11 | 1,177,444 | 60 | 12 | 458.038650 | 20 | 458.789845 |
| 23 | 1,245,492 | 60 | 12 | 458.010150 | 5 | 458.626042 |
| 37 | 1,235,708 | 60 | 12 | 458.267774 | 55 | 458.699836 |

Strict audit: PASS.
- 72/72 official training maps per seed and 24/24 validation maps per PPO seed.
- Zero training/validation map-hash mismatches.
- All 17 operator IDs represented in teacher data; 49/51 action slots observed.
- Zero masked teacher labels.
- All BC, PPO-best and PPO-final checkpoints load successfully.
- 60/60 rollout hashes and iteration records verified per PPO seed.
- 12/12 stochastic and deterministic validation records verified per seed.
- Six BC/PPO-best checkpoints have distinct hashes.
- All three seeds share the same source digest.

Interpretation: training engineering is complete, but PPO's selected best validation cost is not evidence of improvement over BC or strong non-RL. All three final validation costs exceed their selected best values. Same-budget paired evaluation is required.

Historical batch ../training_runs_v5_reward_v2_partial_24maps is preserved separately and must not be pooled with final72.

## Active development validation protocol

Launcher: /tmp/run_v5_validation_fixed.sh

- Official validation split: 24 maps (geometry seeds 7–8).
- Solver seeds: 101, 102, 103.
- Budgets: 2, 6, 12, 30 seconds.
- Workers: 8; server CPU quota: 12.
- Non-RL methods: M0, M1, M1c, M1d, M2, M3, M4, M5, M1d_nojoint, M1d_noxchg.
- Learned policies: BC and PPO for all three training seeds.
- Per budget: 720 non-RL tasks + 432 BC/PPO tasks = 1,152 tasks.
- Total planned matrix: 4,608 tasks.
- Every run is independently checked for feasibility and has source / instance / model provenance.
- 6s and 12s are primary confirmatory budgets; 2s and 30s are development/sensitivity budgets.

Analysis:
- scripts/analyze.py: complete method comparison and runtime/anytime diagnostics.
- /tmp/analyze_v5_validation_ensemble.py: average solver seeds and three model-training seeds within each map; compare BC/PPO against M1d, M1d_nojoint and M1d_noxchg; Holm family across 6s/12s comparisons.

## Critical interpretation rules

1. Do not pool v4, v5 partial-24-map and v5 final72 results.
2. Do not call 2/6/12/30-second research-budget runs a reproduction of Liu's paper stopping protocol.
3. Do not claim local reconstruction is superior; current evidence does not support that.
4. Do not claim RL adds value unless it beats the strongest non-RL controller with the same operators, initial solution, evaluator and wall-clock budget.
5. Treat the locked_v2 set as synthetic stress testing, not real-world evidence or the original Liu benchmark.
6. Preserve negative results, failed seeds, original logs and checkpoint hashes.
7. Do not tune on locked_v2 after freeze.

## Next gates

1. Finish all 2/6/12/30s validation runs without errors.
2. Run the map-level BC/PPO ensemble analysis and compare all three strongest non-RL controls.
3. Run the first-layer assignment-only and joint-only validation ablations (families 1 and 3) against M0; retain the full M1d comparison.
4. Complete available controller-state/action-mask sensitivity ablations; label inference-time zeroing as sensitivity analysis, not retrained causal ablation.
5. Decide whether a runtime-reward retraining or Route-RL branch is justified by the mainline evidence.
6. Freeze source/config/model hashes and run the 60-map locked suite once.
7. Produce final statistics, robustness breakdowns, failure rates, compute/inference costs and a Go/No-Go publication decision.
