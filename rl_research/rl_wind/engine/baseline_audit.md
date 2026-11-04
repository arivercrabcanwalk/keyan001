# CA-RL-TSALNS v5 — Baseline and implementation audit

Audit date: 2026-10-31  
Working tree: /root/rivermind-data/ca_rl_completion_v5_staging/code  
Immutable predecessor: ca_rl_completion_v4_staging

## 1. Target problem

Liu, Hu and Cheng's LRPHSD jointly chooses station location/type (SABS/DABS), target-to-station assignment, heterogeneous SD/LD allocation, and multi-trip routes under coverage, station operating-duration, drone energy and return constraints. The objective includes fixed station construction/configuration costs and operating/flying costs.

Three algorithm identities must remain separate:
- official Java source and paper-parameter protocol;
- frozen V6 reproduction profile;
- research-budget CA-RL profile.

A six-second research-budget profile is not the paper's original stopping protocol.

## 1.2 Original paper benchmark versus expanded project suite

The paper's computational section reports 21 small LRPHSD instances in Table 1 and 9 medium/large LRPHSD instances in Table 2, i.e. 30 LRPHSD cases in total. Table 1 contains seven size groups with three instances each; Table 2 contains three size groups with three instances each. The sentence reporting an average gap within 1.12% for “all 21 instances” refers to the 21 small cases in Table 1, not all paper LRPHSD cases. The nine medium/large cases are separately summarized as TSALNS beating Gurobi in 7/9 and matching in 2/9; Gurobi was run with a 3600-second limit.

The server's Instances_Alg directory contains 120 maps: 12 size groups x 10 geometry seeds. The original 30-paper-case subset is seeds 1–3 for the ten paper size groups (3_10, 3_15, 3_20, 4_20, 4_25, 4_30, 5_35, 6_50, 7_65, 8_80). The extra 9_95 and 10_110 groups and seeds 4–10 form an expanded project suite. This distinction is now explicit in the protocol; do not describe all 120 as the original paper dataset.

## 1.1 Paper Table A1 versus released Java source

A source reconciliation is recorded in reference/evidence/baseline_parameter_reconciliation.md. The paper's Appendix A Table A1 specifies 500 location-local iterations and an upper ALNS weight bound of 0.5. The released Java Main.java uses 100 location-local iterations; ALNSSolver.java clamps weights to 5.0. Both use 500 outer location iterations, 5000 ALNS iterations, initial temperature 1000 and cooling 0.95. The released Java ALNSSolver also implements reward decay 0.9, accepted base reward 1, improvement enhancement 2, rejection penalty -0.2, smoothing 0.8/0.2 and update period 50.

Therefore paper_parameters.json and frozen_v6.json are intentionally separate. The former is a Table A1 parameter profile; the latter follows the released Java code profile. Neither may be silently called the other.

## 2. Inherited baseline evidence

- Official Java source lock is stored in reference/java/SOURCE_LOCK.json.
- Official initialization semantics have a C implementation, r6_rebuild_official_greedy, differentially checked against Python greedy initialization on all 120 official Instances_Alg cases.
- Ten small cases have exact-solver certificates, rechecked by tests/test_carl.py.
- The independent evaluator checks full feasibility and objective components.
- Parameter profiles are separate: paper_parameters.json, frozen_v6.json and research_budget.json.

Historical v4 artifacts remain intact, but v4 PPO/BC models use a 49-feature, 12-action schema and cannot be loaded into v5. Their negative result applies to the old controller/environment pair, not automatically to v5.

## 2.1 Official Java source versus paper-parameter protocol

The pinned official Java source is locked by SOURCE_LOCK.json and compiled in an instrumented copy. A source audit found a material discrepancy:
- Main.java: 500 outer iterations and 100 route-local-search iterations per outer iteration;
- ALNSSolver.java: 5,000 ALNS iterations, weight range 0.1–5.0, T0=1000 and cooling=0.95.
The supplementary paper-parameter profile instead specifies 500 local-search iterations and weight upper bound 0.5. The project therefore keeps paper_parameters.json, frozen_v6.json and research_budget.json separate.

A fixed-12-outer Java/Python differential was run on six controlled instance/seed pairs. The Java source output passed the independent Python evaluator on only 3/6 runs; Python passed 6/6. Routes matched on 0/6 runs. The source audit traced this to a physical-model inconsistency: the official Java validator can accept work in both route slots at an SABS, effectively allowing two small-drone route lists although the paper model specifies one small drone. This is not an exact trajectory parity result. See reference/evidence/official_java_fixed12_audit.md.

Consequently, report the pinned-source behavior, the corrected physically feasible paper-parameter port, and the wall-clock research-budget baseline as three distinct protocols. Do not use infeasible Java outputs as valid solution-quality comparisons.

## 3. Defect motivating redesign

The v4 policy selected only one of four families (Location/Assignment/Routing/Joint) and an intensity. The actual subtype was selected inside a random candidate generator. The learner therefore did not choose whether to open/close/upgrade/downgrade a station, perform a cross-drone exchange, or perform a cross-trip exchange.

The previous audit also found the original destroy(1,1) same-source/same-destination no-op. The v4 repair changed it to destroy(3,1) and added regression coverage. This was an implementation defect, not a scientific result.

## 4. v5 implementation

### 4.1 Versioned state and action schemas

- State schema: carl-state-v4-operator-level-history-75.
- Action schema: carl-action-v4-explicit-17-operators-x-3-intensity-51.
- Reward schema: current-cost-delta-time-best-v2.
- Feature vector: 75 values: 13 global search, 10 station, 8 assignment, 10 drone/trip, and 34 per-operator history features.
- Action vector: 51 slots = 17 explicit operator types x 3 intensity slots. 2-opt exposes intensity 0 only; unsupported slots are masked.
- Old checkpoints fail schema validation by design.

### 4.2 Explicit operators

| Family | Operator IDs | Operations |
|---|---:|---|
| Location | 0–4 | open, close, upgrade, downgrade, station-type swap |
| Assignment | 5–6 | cross-station transfer, within-DABS SD/LD reassignment |
| Routing | 7–11 | relocate/reinsert, 2-opt, cross-drone exchange, cross-trip exchange, classic ALNS |
| Joint | 12–16 | open+steal, close+shift, upgrade+absorb, downgrade+reallocate, type-swap+rebuild |

The policy chooses the subtype directly. Candidate target/station selection remains inside the operator-specific generator; the policy does not yet choose arbitrary target IDs or station pairs.

### 4.3 Feasibility and reconstruction

The dynamic mask is a cheap necessary-condition filter, not a feasibility certificate. Native repair/physical guards and the independent evaluator remain authoritative.

Assignment and Joint moves use scoped repair masks where possible. Station-opening/closing/type changes that require a complete reassignment can still use the official greedy rebuild path. Do not describe all moves as local-only reconstruction.

Context.refresh() invalidates its structural-availability cache. This prevents a stale action mask after the incumbent changes.

### 4.4 All-instance operator coverage audit

results/v5_operator_coverage_audit.json records 10 attempts per available operator on each of the 120 official instances, with each candidate passed through native guards and the independent evaluator.

Verified:
- 120 maps processed;
- zero exceptions;
- 11,253 feasible sampled candidates;
- all four operator families generated feasible candidates;
- SD/LD drone reassignment available on 119/120 maps and 1,190/1,190 sampled candidates feasible;
- cross-drone exchange available on 119/120 maps and 672/1,190 sampled candidates feasible;
- cross-trip exchange available on 118/120 maps and 693/1,180 sampled candidates feasible.

After correcting the reciprocal-coverage precondition, Location-type swap and Joint type-swap are now structurally available on 78/120 initial greedy incumbents. The revised audit generated and independently validated 450/450 sampled candidates for each swap operator. A mixed-type transition test also upgrades a station, then successfully executes both swap operators on the resulting feasible state.

## 5. Engineering verification

Latest full BUILD_AND_TEST.sh run passed:
- protocol/audit regression: 10/10;
- native regression: classic and rebuild branches both nonempty, 34/40 repair calls;
- core CA tests: 7/7, including the updated 17-operator candidate audit;
- v2 contracts: 4/4;
- state contracts: 5/5;
- PPO/SMDP contracts: 3/3;
- separate v5 operator-level contracts: 8/8;
- locked-v2 manifest selector passed separately after the fix.

The old family test was replaced. It had called generate(ctx, family, intensity) with IDs 0–3 after the API changed to operator IDs, so it did not test the full portfolio. The new test iterates all 17 operator IDs and aggregates feasible candidates by family.

## 6. Training status

The final reward-v2 training completed for three independent seeds in ../training_runs_v5_final72:
- each BC teacher used all 72 official training maps (seeds 1–6 within each size group);
- BC state/action/mask records: seed 11 = 1,177,444; seed 23 = 1,245,492; seed 37 = 1,235,708;
- each dataset has 75 features and 51 action-mask slots; 49 distinct action IDs were observed and zero teacher labels violated their masks;
- each PPO run completed 60 updates and selected its best checkpoint on the same 24-map validation split;
- PPO best validation costs: seed 11 = 458.03865; seed 23 = 458.01015; seed 37 = 458.26777.

The independent results/v5_training_artifact_audit.json passed. It checked all 72 training-map names and hashes, all 24 validation-map names and hashes, checkpoint hashes, state/action/reward/model schema, finite teacher features, mask-valid teacher labels and a shared training-code hash across seeds.

An earlier sparse-reward batch and an initial 24-map batch were preserved separately and are not part of the final training:
- ../training_runs_v5_reward_v0_partial;
- ../training_runs_v5_reward_v1_partial;
- ../training_runs_v5_reward_v2_partial_24maps.

The final reward-v2 formula is:
r = 100 * (J_current_before - J_current_after) / J_initial
    - 0.25 * elapsed_operator_time / episode_budget
    + 0.02 * I(global_best_updated).
It rewards accepted incumbent improvement, penalizes elapsed operator time and separately marks global-best updates. SMDP GAE additionally discounts by elapsed time.

The 2/6/12-second common-budget validation matrix is now running. Training completion is not a performance claim; the RL contribution remains unproven until comparison with the strongest v5 non-RL controller.

## 7. Data splits and evaluation

The official 120-instance set is split by geometry seed within each size group:
- train: seeds 1–6 (72 maps);
- validation: seeds 7–8 (24 maps);
- historical test: seeds 9–10 (24 maps).

The historical test has been used in prior project work and is not blind.

A separate locked_v2 suite contains 60 generated stress-test maps. Its manifest is authoritative; selection verifies exactly 60 names and each SHA256 and ignores AppleDouble metadata files. It is a separate synthetic stress test, not an official Liu benchmark.

## 8. Open issues / no premature claims

1. v5 training and its artifact audit are complete; the 2/6/12-second validation matrix is still running.
2. Strong non-RL operator-level baselines must be rerun under v5; v4 costs are not comparable.
3. Mixed SABS/DABS reachability is covered by the transition test and the 78/120-map operator audit; broader dynamic reachability during long searches remains to be profiled.
4. Measure per-operator availability, generation, feasibility, acceptance, improvement, best-update rate and wall-clock cost.
5. Compare scoped reconstruction with full reconstruction on identical move proposals and budgets.
6. Run the 30-instance paper-parameter versus pinned-source-parameter controlled comparison; a full original-iteration reproduction remains separate because the official Java source has the documented SABS physical-model defect.
7. Run locked-suite evaluation only after development selection and code/checkpoint freeze.
8. No RL gain, novelty, generalization, CCF-B acceptance or publication readiness is claimed.

## 9. Reproducibility artifacts

- Code: this directory.
- Operator audit: results/v5_operator_coverage_audit.json.
- Build/test: bash BUILD_AND_TEST.sh.
- Training launcher: scripts/run_learning_study_v5.sh.
- v4 code and historical results remain unchanged.
