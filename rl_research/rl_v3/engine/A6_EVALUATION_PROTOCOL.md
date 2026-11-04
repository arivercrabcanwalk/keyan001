# A6 validation evaluation protocol

Development-only evaluation; formal_v3 is prohibited.

For each reward-v3 PPO model seed (11, 23, 37), evaluate M2 Global Assignment and the corresponding A6 PPO Global Assignment policy on the same 24 official validation maps, paired solver-seed group, independent evaluator and wall-clock budget:
- seed 11: solver seeds 101, 102, 103
- seed 23: solver seeds 104, 105, 106
- seed 37: solver seeds 107, 108, 109
- budgets: 6s and 12s
- methods: m2_global_asg, m6_global_asg
- workers: 8

Canonical evaluation consists of 12 batches x 72 tasks = 864 tasks. The first 6s/seed-11 batch was initially launched with both methods and a PPO model path; its 72 A6 PPO rows are preserved and used, while its 72 M2 rows are explicitly excluded because the model path was not needed by M2. The six M2 batches are therefore run separately without a model path. A6 PPO is compared map-wise with (a) M2 Global Assignment from the same A6 source version and (b) the reward-v2 PPO Global Assignment rows already collected under the original v5 source. The latter comparison isolates the effect of the explicit runtime reward term on the learned policy; inference uses the same state/action and candidate/repair semantics.

Statistical unit is map. Aggregate the nine runs per map (3 model seeds x 3 solver seeds), then compute paired relative cost deltas, 95% bootstrap CI, Wilcoxon signed-rank, rank-biserial effect and Holm correction across four predeclared tests (two references x two budgets). Report feasibility, runtime and training overhead. No result from this validation evaluation can be used as formal-test evidence.
