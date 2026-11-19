# Research execution ledger update — Route-RL Stage A

**Timestamp:** 2026-11-02  
**Branch:** <EXECUTION_PATH>  
**Status:** Stage-A evaluation complete and independently audited; Route-RL Stage B is No-Go under the frozen gate.

## 1. Engineering and source freeze

- Separate branch created from the M2 Global NoJoint development reference.
- Stage-A protocol and source freeze recorded.
- 72 training maps (seeds 1–6) and 24 validation maps (seeds 7–8).
- Initial Greedy and independent evaluator: 96/96 feasible.
- Stage-A engineering smoke: Greedy, best insertion, 2-opt and random masked-pointer policy all 96/96 feasible.
- Reward reconciliation maximum absolute error: 4.44e-16.
- Unit tests: 6 passed, 0 failed.
- Frozen station types, target ownership and SD/LD drone ownership.
- No source-code modification after Stage-A freeze.

## 2. PPO training

- Three independent model seeds: 11, 23, 37.
- 60 updates per seed, 8 episodes/update, 4 PPO epochs.
- Best validation mean relative objective delta versus Greedy:
  - seed 11: -0.0283% (best update 30);
  - seed 23: -0.3307% (best update 60);
  - seed 37: +0.9038% (best update 25).
- Mean across model seeds: +0.1816%; median: -0.0283%.
- All validation outputs feasible.
- The three-seed average does not show a stable gain over Greedy.
- Best checkpoint selected for the first equal-budget comparison: seed 23.
- Common training source SHA256: 42869efac1c09addc91666d741f139210730232486e2fc53d2303cedfe59bda0.

## 3. Equal-budget evaluation launched

Matrix:
- 24 validation maps;
- solver seeds 101, 102, 103;
- budgets 6s and 12s;
- methods: Greedy, best insertion, 2-opt, route-only ALNS, Route-RL;
- expected tasks: 720;
- every completed full solution independently evaluated;
- Route-RL inference included in its refinement budget.

Output:
- results/route_rl_stageA/eval_seed23_3solver_6_12/

## 4. Interim observation — not a final result

On the first completed 110-target validation map (10_110_7), average across three solver seeds:
- Route-RL: -0.314% versus Greedy at both budgets.
- Route-only ALNS: -1.557% at 6s and -1.578% at 12s.
- All outputs feasible.

On two smaller maps completed afterward, Route-RL and ALNS were tied in the observed mean. These few maps are not inferential evidence. Do not finalize the go/no-go decision until all 24 maps and the paired analysis complete.

## 5. Decision boundary

- Stage B (joint SD/LD dispatch within DABS) has not started.
- Stage C (cross-station target transfer) has not started.
- No formal test set was opened.
- No blind/generalization claim is permitted.
- If Route-RL does not beat route-only ALNS under the full paired 6s/12s evaluation, close Stage A as a negative result and do not expand it merely to add model complexity.

## 6. Final Stage-A audit (2026-11-02)

The frozen evaluation finished with 720/720 task records, zero task failures, and 720/720 compressed full solutions present. A fresh pass checked each result identity, instance SHA256, solution SHA256, feasibility, and independent evaluator cost; missing/extra/duplicate/error counts were all zero. The current source digest still equals the run manifest digest `42869efac1c09addc91666d741f139210730232486e2fc53d2303cedfe59bda0`. The selected checkpoint digest is `635ad6137705f6ae4236d0eb847620c2041d5ad3d796b65067a102f3bd1018c2`.

The table gives the mean full objective over 24 validation maps and three solver seeds per map. Greedy, insertion, and 2-opt finish much earlier than the stated budget; their objective is a route-quality control, not evidence of equal compute consumption.

| Budget | Greedy | Best insertion | 2-opt | Route-only ALNS | Route-RL |
|---|---:|---:|---:|---:|---:|
| 6 s | 495.009507 | 493.812917 | 494.218892 | 486.044798 | 492.133754 |
| 12 s | 495.009507 | 493.812917 | 494.218892 | 485.978324 | 492.072436 |

Map-level paired benefit is `(ALNS cost - Route-RL cost) / ALNS cost`, averaged over the three solver seeds and then over maps. Positive would favor Route-RL. The 95% intervals are 20,000 map-resampling percentile bootstrap replicates with seed 20261102; they are exploratory because the same validation maps selected the checkpoint.

| Budget | Mean benefit vs route-only ALNS | Median | 95% bootstrap CI | Map W/L/T |
|---|---:|---:|---:|---:|
| 6 s | -0.966725% | -0.986849% | [-1.259282%, -0.679487%] | 0/21/3 |
| 12 s | -0.955678% | -0.898343% | [-1.256179%, -0.664543%] | 0/21/3 |

Route-RL does improve on Greedy by +0.649531% at 6 s and +0.668982% at 12 s, but the strong route-only ALNS improves more. The frozen Stage-A gate therefore fails at both budgets. Close Stage A as a retained negative result; do not launch Stage B, Stage C, a larger network, or a formal Route-RL test on the strength of this result. The selected seed-23 checkpoint does not establish stability across the three trained model seeds. Neither this validation result nor the earlier macro-controller results support an RL-superiority claim.

## 7. Research handoff

Formal v4 already establishes a narrower non-RL result: Global Assignment receiver-scope search improves on M0, M1D Global Assignment and M2 Local on its frozen 30-main-map comparison, while the Joint-family marginal effect is not established and no RL method was in that formal matrix. The next publishable path is to finish full-text novelty comparison and paper-fidelity reproduction, then write only the supported non-RL contribution. Keep Formal v4 closed to tuning and retain its raw solutions, hashes, failure records and statistical protocol. A fresh confirmatory suite is required for any newly revised method or claim.
