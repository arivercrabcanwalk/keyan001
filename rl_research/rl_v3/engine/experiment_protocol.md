# CA-RL-TSALNS v5 — Experiment protocol

## 1. Separate reproduction and research protocols

### Protocol A: Liu paper reproduction
Keep two named reproduction references: (A1) the paper Appendix A Table A1 profile and (Java) the released official Java source profile. They differ: Table A1 lists 500 location-local iterations and weight upper bound 0.5, while Main.java/ALNSSolver.java use 100 local iterations and upper bound 5.0. Both use 500 outer iterations, 5000 ALNS iterations, temperature 1000 and cooling 0.95. Preserve and report each profile separately; do not average or silently reconcile them. The paper Table A1 reward values and Java reward implementation are mapped in reference/evidence/baseline_parameter_reconciliation.md. Do not replace iteration limits with a six-second budget and call it paper reproduction.

### Protocol B: research-budget comparison
Use the same hardware, wall-clock budget, initialization policy, independent evaluator and deadline accounting for all methods. Report 2, 6, 12 and 30 second budgets during development; 6 and 12 seconds are the primary comparison budgets unless a preregistered update says otherwise. Include initialization, search, finalization, controller inference, evaluation and end-to-end times.

## 1.1 Original paper cases

The Liu paper's LRPHSD experiment comprises 30 cases: 21 small cases in Table 1 and 9 medium/large cases in Table 2. The “within 1.12% for all 21 instances” statement refers to Table 1's small cases only. The 30 original cases correspond to geometry seeds 1–3 across the ten paper size groups: 3_10, 3_15, 3_20, 4_20, 4_25, 4_30, 5_35, 6_50, 7_65 and 8_80.

The server's 120-map Instances_Alg suite is an expanded set (12 size groups x 10 geometry seeds), not the paper's original 30 cases. Report paper30 replication and expanded-scale generalization as separate experiment blocks.

## 2. Data

Official Instances_Alg: 120 maps, split by geometry seed within each size group:
- train: 72 maps, geometry seeds 1–6;
- validation: 24 maps, seeds 7–8;
- historical test: 24 maps, seeds 9–10.

Do not treat the historical test as blind; earlier project work has examined it.

locked_v2: 60 generated stress-test maps with a SHA256 manifest and feasible witnesses. It is a separate synthetic stress-test suite, not an official Liu benchmark. Use only after development selection and freeze.

## 3. Methods

Minimum research-budget comparison:
- M0: frozen V6 research-budget baseline;
- M1d: strong scheduled non-RL controller over the same v5 operator set;
- M1d_nojoint: same controller and candidate portfolio without Joint family;
- M1d_noxchg: same controller without cross-drone/cross-trip exchange;
- M2: adaptive weights;
- M3: rule-based bottleneck controller;
- M4: LinUCB contextual bandit;
- M5: tabular Q-learning;
- BC seed 11/23/37;
- PPO seed 11/23/37.

All v5 controller comparisons use identical 17 operators, action mask semantics, native repair, evaluator, initial solution and budget. The only intended difference is controller choice or a declared ablation.

The v4 12-action results are historical and cannot be pooled with v5 results.

## 4. Training

- Train only on the 72-map training split.
- Use the 24-map validation split for checkpoint selection and hyperparameter decisions.
- Train three independent seeds (11, 23, 37).
- BC teacher: M1d, all 72 training maps, 6 seconds per teacher episode, 8 epochs.
- PPO: 60 updates, 8 workers, 0.3-second collection episodes, validation every 5 updates, 2-second validation episodes. Reward v2 combines current-incumbent objective delta, normalized elapsed operator time and a separate global-best bonus; PPO uses SMDP elapsed-time discounts.
- Report BC teacher accuracy, action distribution, PPO entropy, episode transitions, policy inference time, training wall time and all checkpoints.
- Do not select model seeds or checkpoints using locked_v2 or historical test maps.
- Report training compute separately from per-instance inference time.

## 5. Development validation

After all three seeds finish and checkpoint hashes are audited:
1. Evaluate M0, M1d, M1d_nojoint and M1d_noxchg at 6 and 12 seconds on all 24 validation maps and solver seeds 101, 102, 103.
2. Evaluate each BC and PPO seed on the same map/solver-seed matrix and budgets.
3. Add M2–M5 at least at 6 seconds if resources permit; do not compare RL only with a weak random selector.
4. Record complete anytime checkpoints at 0.25, 0.5, 0.75 and 1.0 budget.
5. Record per-operator attempts, candidate generation, feasibility, changes, acceptance, improvement, global-best updates and time.

The primary statistical unit is the map. First average solver seeds and model-training seeds within each map; then perform paired inference across maps. Do not treat repeated seeds as independent maps.

## 6. Statistical analysis

For every paired comparison report:
- mean, median and standard deviation;
- wins/losses/ties by map;
- paired mean difference and relative percentage;
- 95% paired bootstrap confidence interval;
- paired Wilcoxon signed-rank test;
- effect size (rank-biserial and standardized paired difference);
- Holm correction for predeclared multiple comparisons.

Keep exploratory and confirmatory comparisons separate. Do not tune using the locked suite.

## 7. Required ablations

Primary:
- no RL controller (best non-RL controller);
- remove Joint neighborhood;
- remove drone reassignment;
- remove cross-drone/cross-trip exchange;
- full reconstruction versus affected-subproblem reconstruction.

Secondary:
- remove assignment-state block;
- remove drone/trip-state block;
- remove operator-history block;
- remove action mask;
- remove runtime/time component of reward;
- compare fixed schedule, rule, bandit, Q-learning and PPO;
- compare MLP against GNN only if MLP shows a measured cross-scale limitation.

For every ablation, retrain learning models when the training environment or state/action semantics change. Inference-time masking is a sensitivity test, not a substitute for retraining.

## 8. Go / No-Go gates

### Gate 1 — correctness
All candidate outputs independently feasible; all maps, seeds and task counts accounted; code/model/config hashes fixed.

### Gate 2 — strong non-RL search
The v5 joint operator portfolio must provide a stable, explainable benefit over M0 or a credible reason for a different comparison result. Diagnose operator quality and reconstruction cost before adding more learning complexity.

### Gate 3 — RL independent contribution
BC/PPO/bandit/Q must be compared against the strongest non-RL controller with identical operators and budget. A result that only beats M0 does not prove RL adds value.

### Gate 4 — practical and generalizable benefit
Seek a practically meaningful and stable improvement (development target 1–2%, not a guaranteed result), confidence intervals and corrected tests supporting it, robustness across instance structures and unseen scales, and acceptable inference overhead.

### Gate 5 — final blind evaluation
Only after algorithm, checkpoint, protocol and analysis scripts are frozen may locked_v2 be evaluated once. The official historical test remains labelled as historical.

## 9. Publication decision

Writing can proceed on problem definition, model, algorithm and related work while experiments run. Abstract performance claims, novelty claims and final venue choice must wait for validation and locked-test evidence.

A CCF-B+ CS submission requires a generalizable algorithmic contribution, a clear distinction from existing RL-guided search and strong non-RL controls. If the contribution remains primarily LRPHSD-specific optimization engineering, an OR/transportation journal may be a better fit.
