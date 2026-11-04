# Liu2026 / CA-RL-TSALNS v5 - verified execution update

Snapshot date: 2026-10-31 UTC
This is an append-only status update. It does not replace the master research plan, experiment protocol, or the original execution ledger.

## 1. Governing research logic

Follow the user-approved plan:
Greedy initialization -> coupling-aware joint neighborhoods -> strong non-RL controls -> BC/PPO/A2C controller validation -> cross-scale generalization -> algorithm freeze -> independent formal evaluation -> paper.

The policy controls explicit macro-neighborhood subtype and intensity. Candidate target/station selection and detailed route construction remain heuristic. This is not a learned per-waypoint flight planner. Do not claim RL superiority unless it beats the strongest non-RL method with identical operators, evaluator, initialization and wall-clock budget.

## 2. Verified phase status

| Phase | Status | Verified evidence | Remaining gate |
|---|---|---|---|
| 0. Source/data/baseline audit | Completed with open paper-protocol replication | baseline_audit.md; source lock; 120-map official suite; independent evaluator; Java/Paper-A1 parameter discrepancy documented | Complete the distinct 30-paper-case reproduction comparison; do not conflate Java, Table A1 and research-budget profiles |
| 1. Joint neighborhoods/reconstruction | Implemented; evidence mixed | 17 explicit operators; 75-D state; 51 masked action slots; 120-map operator audit; scoped/global reconstruction diagnostics | Full-search global Joint-scope experiment is queued behind RL transfer; local reconstruction is not established as superior |
| 2. Strong non-RL controls | Implemented and validated on development maps | 2/6/12s matrix: 3,456 tasks, zero errors, 100% feasibility; 30s matrix completed; 10-seed global-repair and assignment-scope confirmations | Use the selected M2 Global comparator in the final same-budget comparisons; retain M1d variants as secondary controls |
| 3. BC/PPO/A2C | Training and 2/6/12s validation complete; global-scope transfer running | Training artifact audits passed; 3-seed ensemble validation; all BC/PPO/A2C were compared with M2; a 36-batch Local/Global transfer matrix is running | Complete transfer matrix, validate all manifests/hashes/feasibility, analyze against M2 Global |
| 4. Route-RL / GNN | Deferred by design | Current bottleneck evidence does not justify a new network or direct waypoint policy | Reconsider only after mainline evidence identifies a concrete route-level or representation bottleneck |
| 5. Algorithm selection/freeze | Pending | M2 Global is the selected non-PPO development reference; all candidate source and model artifacts exist | Finish RL transfer and Global Joint tests; select candidate using validation only; freeze source/config/model/analysis hashes |
| 6. Independent formal evaluation | Not started | Current 24-map validation split is development-only; historical 24-map test split is not blind; locked_v2 has 60 synthetic maps | Reconcile the latest 30-main + 6-stress maps / 10-seed instruction with the older 60-map / 3-seed protocol before generating or opening any final test set |
| 7. Paper | Partial drafting allowed | Problem, model, algorithm and related-work materials exist | Performance, novelty and submission claims wait for locked independent results |

## 3. M0: 1,440-task parameter-profile validation

Confirmed from both result manifests:
- 6s: 720/720 tasks, zero errors.
- 12s: 720/720 tasks, zero errors.
- Total: 1,440/1,440 tasks.
- Matrix: 24 validation maps x 3 profiles (M0, M0 Frozen, M0 Paper) x 10 solver seeds x 2 budgets.
- All result rows are present and feasible.

This is research-budget parameter-profile validation, not a claim that the full Liu paper stopping protocol has been reproduced. M0 Paper and M0 Frozen remain separate profiles because the paper Table A1 and released Java source differ.

## 4. Current validated development evidence

### 4.1 Strong non-RL comparison

The 2/6/12s v5 validation report covers 3,456 completed tasks with zero errors and 100% feasibility. M1d-family search and M2 improve on M0. M2 Adaptive is the strongest non-RL method by validation mean at 6s and 12s. M1d and M2 are close; direct marginal comparisons among M1d variants are not consistently significant.

A same-source 10-seed global-repair finalist confirmation selected m2_global_asg as the non-PPO reference. It remains the primary reference for the current RL Global Transfer diagnostic.

### 4.2 Existing RL validation result

On the 24-map validation split, averaging solver seeds and the three model seeds within each map:
- 6s: BC is +0.0897%, PPO +0.1025%, A2C +0.0561% relative to M2.
- 12s: BC is +0.0650%, PPO +0.0945%, A2C +0.0818% relative to M2.
Positive means higher/worse cost. These comparisons are significant after the predeclared Holm correction. All three learned methods beat M0, but none beats the strongest non-RL M2. PPO has no demonstrated improvement over BC.

Do not claim RL success from the current validation results.

### 4.3 Assignment-scope evidence

The 10-seed assignment-scope comparison found that global receiver scope improved the full solver relative to local scope for M1d at 6s and 12s, and for M2 at 6s; the 12s M2 contrast did not pass Holm correction. M1d Global and M2 Global were not significantly distinguishable in the paired 10-seed comparison.

### 4.4 Reconstruction evidence

Candidate-level reconstruction comparisons do not establish a general advantage for affected-subproblem reconstruction over full-system reconstruction. Preserve the negative/mixed evidence. The current full-search Joint-scope experiment is a separate validation of whether broadening repair scope changes search performance.

## 5. Active jobs at snapshot

### 5.1 RL Global Transfer

Launcher: /tmp/run_v5_rl_global_transfer.sh
Log: /tmp/v5_rl_global_transfer.log
Planned matrix:
- 2 budgets: 6s and 12s;
- 3 controllers: BC, PPO, A2C;
- 3 model seeds: 11, 23, 37;
- 2 repair scopes: local and global Assignment;
- 24 validation maps x 3 solver seeds per model seed;
- 36 batches x 72 tasks = 2,592 tasks.

At this snapshot, 16 batches were complete with zero errors and the next batch was running. The analysis script checks complete manifests, 72 rows per batch, feasibility, repair-scope metadata, model/source provenance and a single common source hash. Primary comparison is global-scope learned controller versus m2_global_asg; local-vs-global is secondary. These are transfer diagnostics because the checkpoints were trained under local repair.

Do not launch a duplicate RL transfer job. Wait for results/V5_RL_GLOBAL_TRANSFER_COMPLETE.

### 5.2 Global Joint full-search scope test

A watcher is armed and waits for the RL transfer completion marker. It then:
1. Preserves the pre-patch source backup.
2. Applies the post-move station-type receiver-mask correction for Joint moves.
3. Runs a smoke test.
4. Runs the full comparison.

Planned matrix:
- methods: M1d/M2 with local, global Assignment, global Joint, and global Assignment+Joint scopes (8 methods);
- 24 validation maps;
- solver seeds 101-105;
- 6s and 12s;
- 1,920 tasks total.

Do not start this matrix manually while the watcher is armed. Verify its source backup, smoke-test result, manifest, common code hash and feasibility before interpreting results.

## 6. Protocol discrepancies to resolve before freeze

1. The older server FINAL_EVALUATION_PROTOCOL.md specifies 60 locked_v2 synthetic maps and 3 solver seeds. The latest user handoff specifies 30 main new maps plus 6 extension stress-test maps, with 10 solver seeds per formal method. These are not the same protocol. Treat the latest 30+6 / 10-seed instruction as the current planning target, but do not overwrite or open the older locked suite until a new versioned final protocol and instance manifest are prepared.
2. The official paper benchmark contains 30 LRPHSD cases: 21 small cases plus 9 medium/large cases. The 1.12% gap statement refers to the 21 small cases only. Do not describe the paper benchmark as only 21 cases.
3. The server workspace has no Git repository; VERSION_MANIFEST.json still identifies a v4 schema. Before final freeze, create a clean v5 source version, immutable source archive or Git commit, and a v5 manifest with source/config/model/data/analysis hashes.

## 7. Next execution order

1. Let the existing 36-batch RL transfer finish; audit all 2,592 tasks and run its predeclared analysis.
2. Let the armed Global Joint watcher run; audit all 1,920 tasks, then analyze the marginal effect of Joint repair scope.
3. Update the algorithm decision using development validation only. If RL still fails against M2 Global, preserve the negative result and do not retune on final maps.
4. Complete the distinct 30-paper-case reproduction comparison, preserving Java and paper Table A1 profiles separately.
5. Prepare a new formal protocol for 30 main new maps + 6 stress maps and 10 seeds per formal method; hash and lock all 36 maps before the first formal run.
6. Freeze selected source, parameters, reward, state/action schema, models, configs, statistics and analysis scripts. Create a v5 version manifest and immutable archive/commit.
7. Run the locked formal suite once. No tuning after opening it.
8. Produce tables/figures from raw manifests and per-instance outputs; complete ablations, complexity, runtime and novelty analysis; then make a Go/No-Go publication decision.

## 8. Claim boundary

Current evidence supports a strong non-RL improvement over M0 and shows that BC/PPO/A2C have not yet demonstrated an independent gain over M2. It does not support RL superiority, a general Joint-family marginal gain, blind generalization, state-of-the-art claims, or publication readiness.

## 9. Reproducibility and analysis improvements after the initial snapshot

- Archived the M0 profile runner/analyzer, RL Global Transfer runner/analyzer, and Global Joint runner/analyzer into scripts/ so that the evidence does not depend only on temporary /tmp files.
- The Global Joint analysis now includes the missing factorial contrast Global Assignment+Joint versus Global Joint alone. Its predeclared scope-comparison family is therefore 20 tests (5 contrasts x 2 controllers x 2 budgets), with Holm correction. The previous analyzer is preserved as /tmp/analyze_v5_global_joint_scope.pre_factorial_patch.py.
- The armed Global Joint watcher now invokes the project-local runner and analyzer. Shell syntax and Python compilation checks passed.
- At 2026-10-31 14:52:44 UTC, 18 of 36 RL Global Transfer batches were complete with zero errors; batch 19 (12s, BC seed 11, local repair) was running. This is a live snapshot, not a completion claim.

## 10. Provenance safeguard during RL transfer

The benchmark task identity hashes Python files under scripts/. Adding the analysis Python files there while the RL transfer matrix was in flight changed the task code hash for part of one batch. This was detected by inspecting per-row provenance before any statistical analysis.

- The affected 12s BC seed-11 Global batch was preserved in results/v5_rl_global_transfer_12s_bc_s11_global_hash_mismatch_preserved (72 rows; two code hashes).
- It has been removed from the canonical result path and will not be pooled.
- The added analyzer Python files were moved to results/experiment_script_archive/, outside the benchmark code-hash inputs. The scripts/ Python file set is restored to its pre-run state; subsequent RL batches use the original code hash.
- After the currently running launcher exits, rerun the RL transfer launcher. It will skip complete matching batches and regenerate only the missing canonical batch, then rerun the strict analyzer.
- Do not accept the RL completion marker until all 36 canonical batches have 72 rows, zero errors, all feasible, one common source hash matching the selected M2 Global baseline, and the analysis script passes.

## 11. Original paper-case reproduction block prepared

- Created a hash-locked manifest for the 30 original paper cases: 21 small Table 1 cases plus 9 medium/large Table 2 cases. Manifest: results/paper30_original_case_manifest.json.
- Prepared a 300-task controlled comparison: m0paper vs m0frozen, 30 cases x 2 profiles x 5 solver seeds, 12s guard budget. The analysis requires every run to terminate at the 500-outer-iteration limit; any time-budget termination prevents a full-iteration claim.
- This is a corrected V6 Python parameter-profile comparison, not byte-for-byte execution of the official Java source and not a reproduction of the paper's Gurobi comparison.
- The run is queued by a watcher that waits for V5_GLOBAL_JOINT_SCOPE_COMPLETE, so it will not compete with the active RL or Joint experiments.

## 12. RL transfer provenance recovery

A second mixed-hash batch was detected in the 12s BC seed-23 local-scope output. It has been quarantined as v5_rl_global_transfer_12s_bc_s23_local_hash_mismatch_preserved_20261031T1503Z; it will not be used.

The RL transfer resume launcher now validates each existing batch against:
- the selected M2 Global baseline's single source hash;
- the expected model checkpoint SHA256;
- exact method, budget, seed group, map count and task count;
- per-row feasibility, status and repair-scope metadata.

Any invalid existing canonical output is moved to a timestamped preservation directory and rerun into a clean canonical path. The strict analyzer is invoked from the archived analysis directory, outside the benchmark source-hash inputs. A watcher waits for the current original launcher to exit, then starts this provenance-validating resume launcher. No final completion marker is accepted until the strict matrix audit passes.

## 13. RL Global Transfer completed; Global Joint launched

Snapshot: 2026-10-31 16:52 UTC (2026-11-01 00:52 China time).

### RL Global Transfer final audit
- All 36 canonical batches passed strict audit: 2,592/2,592 task rows, all feasible, zero task errors, 72 rows per batch, one source hash per batch, source hash matching the selected M2 Global baseline, and checkpoint SHA256 matching the model seed.
- Two earlier mixed-source batches remain quarantined in timestamped preservation directories and are excluded from analysis.
- The strict analysis completed and results/V5_RL_GLOBAL_TRANSFER_COMPLETE was written.
- Primary global-scope vs M2 Global mean relative cost deltas:
  - 6s: BC +0.0104% (Holm p=0.1465); PPO +0.0588% (Holm p=0.03149); A2C +0.0210% (Holm p=0.07959).
  - 12s: BC +0.0416% (Holm p=0.01367); PPO +0.0699% (Holm p=0.004883); A2C +0.0536% (Holm p=0.00293).
  Positive means worse cost than M2 Global. No learned controller demonstrates an independent gain over M2 Global.
- Global Assignment scope improves each learned controller relative to its own local-scope transfer at both budgets; this does not overturn the primary negative result against M2 Global.

### Global Joint full-search experiment
- The post-move station-type receiver-mask correction was applied and preserved in the source backup.
- A fresh 1-instance smoke test passed: 8/8 methods, all feasible, zero errors, one common source hash.
- The older smoke directory was preserved and not overwritten; the first watcher attempt stopped safely because that directory already existed.
- The idempotent watcher script was repaired and manually relaunched.
- At 2026-10-31 16:52:28 UTC, the 6s full-search batch started: 960 tasks (24 validation maps x 8 methods x 5 seeds). The 12s batch of 960 tasks follows automatically.
- The analysis uses 20 predeclared scope contrasts with Holm correction and checks common source hash and feasibility.

### Remaining queued task
- The 300-task Paper30 parameter-profile comparison (30 original Liu cases x 2 profiles x 5 seeds, 12s guard budget) remains queued behind V5_GLOBAL_JOINT_SCOPE_COMPLETE.
- Its analysis will reject a full-iteration claim if any run fails to complete all 500 outer iterations.

## 14. Latest full-stage results and next development gate (2026-11-01)

### 14.1 All three queued stages completed

- RL Global Transfer: 2,592/2,592 tasks; 36/36 canonical batches passed strict manifest, source-hash, checkpoint-hash, status and feasibility audit. Analysis completed; marker V5_RL_GLOBAL_TRANSFER_COMPLETE exists.
- Global Joint: 1,920/1,920 tasks; 960 at 6s and 960 at 12s; all feasible, zero errors, one common source hash. Analysis completed; marker V5_GLOBAL_JOINT_SCOPE_COMPLETE exists.
- Paper30: 300/300 tasks; 150 per parameter profile; all feasible and all completed 500 outer iterations. Analysis completed; marker V5_PAPER30_PROFILE_COMPLETE exists.
- Total across these three stages: 4,812 tasks.

### 14.2 Main interpretation

- BC/PPO/A2C Global transfer still does not beat M2 Global with corrected significance. BC is closest at 6s but is not significantly better.
- Global Assignment is the only receiver-scope expansion with repeatable development evidence. Global Joint alone does not help; adding it to Global Assignment does not improve on Assignment alone.
- Paper Table A1 parameters have +0.2393% higher cost than the released-Java parameter profile on the 30 original cases in the corrected V6 Python engine. This is a parameter-fidelity diagnostic, not a claim of exact Java reproduction.

### 14.3 Formal test suite v3 generated, not opened

- Created datasets/formal_v3: 30 main maps + 6 extension stress maps.
- All 36 constructive witnesses pass the independent evaluator; no map hash overlaps official Instances_Alg or locked_v2.
- Manifest SHA256: be65b6a0fe2b47b7e2faf123a1c7eb4f18ac92560fe818b61a593467e6b6a37e.
- Generator SHA256: fe5cb5e11142ad67ec9c7fe1176e82f9f6da574326bcf254e49cf1eba4aa41af.
- The first failed generation attempt is preserved and excluded.
- No solver has been run on formal_v3. Do not use it for tuning.

### 14.4 Additional BC Global ablations now running

To diagnose why BC Global is close to but not better than M2 Global, a 6s validation-only matrix has been launched:
- 24 validation maps;
- 3 BC model seeds (11, 23, 37) x 3 solver seeds each;
- M2 Global plus BC Global full and seven ablations: no Joint family, no dynamic action mask, zero Assignment features, zero Drone features, zero operator-history features, zero global-search features, and remove high intensity;
- 1,944 tasks total, all under one source version and Global Assignment repair.
This is development evidence only. It does not open the formal test set.

A6 runtime-reward ablation is not included because it requires retraining under a different reward. A8 GNN remains deferred. A9 controller comparisons (Bandit/Q/PPO/A2C/BC) have already been conducted on validation. The current run targets A3/A4/A5/A7/A10 plus the learned Joint-family ablation.

Paper30 parameter audit detail:
- Paper Table A1 config SHA256: 163e6dccbf904a09efe34a27fbc5dbc836d7fa03762d10a646e03cdc4f945b3d.
- Released-Java-profile config SHA256: bc7728c63336ec3ceb47d6986e94d3fd78fb4bcb0d45c6137e426e7a8bcb1ff4.
- Exact differences in these configs: local_iterations 500 vs 100; weight_upper 0.5 vs 5.0; profile label differs. Output-row provenance hashes were verified against these config bytes.

Formal v3 receiver-diversity revision:
- Before any optimizer access, the first witness-valid map candidate was preserved as datasets/formal_v3_precoverage_revision_20261101.
- The active formal_v3 generator now uses 7.5 km station spacing for main maps and records the number of targets with multiple DABS/SABS receivers. This prevents the main suite from accidentally eliminating Assignment-transfer opportunities.
- Main-map DABS alternative-receiver counts vary by spatial distribution: clustered maps have no multi-receiver targets, uniform maps have some, and boundary maps have many. Stress maps deliberately include both overlapping and single-receiver cases.
- The revised active manifest SHA256 is be65b6a0fe2b47b7e2faf123a1c7eb4f18ac92560fe818b61a593467e6b6a37e; generator SHA256 is fe5cb5e11142ad67ec9c7fe1176e82f9f6da574326bcf254e49cf1eba4aa41af.
- No solver has accessed either candidate suite.

A follow-on M2 Global Joint-family leave-out confirmation is queued behind the BC Global ablation. It will add the M2 Global NoJoint registry entry only after the current BC matrix and strict analysis finish, then run M2 Global vs M2 Global NoJoint on 24 validation maps, 10 paired solver seeds and both 6s/12s budgets. This isolates the Joint-family contribution in the selected non-RL controller without changing code during the active BC matrix.

## 15. Handover snapshot for a fresh-context agent (2026-11-01 03:43:39 UTC)

A detailed fresh-context handover was prepared for the next agent. The current server-side dynamic status at this snapshot:

- RL Global Transfer: 2,592/2,592 completed and strict audit passed.
- Global Joint: 1,920/1,920 completed, zero errors, all feasible.
- Paper30 parameter profile: 300/300 completed, all feasible, all 500 outer iterations completed.
- BC Global ablation: 1,512/1,944 rows present (77.78%); model seed 11 648/648 complete, seed 23 648/648 complete, seed 37 216/648 running. No errors among rows seen.
- M2 Global NoJoint watcher is waiting for V5_BC_GLOBAL_ABLATION_6S_COMPLETE; its two output directories have not started.
- Current runner/launcher processes must be checked live before resuming. Do not trust this static snapshot or relaunch either job.
- Active formal_v3 remains unopened to optimizer. Manifest SHA256: be65b6a0fe2b47b7e2faf123a1c7eb4f18ac92560fe818b61a593467e6b6a37e.
- The handover document itself is delivered to the user as a downloadable Markdown file. It contains the research decisions, results, task status, server connection, evidence index and a copy-paste startup prompt.

No source code or active benchmark configuration was modified while writing this status update.
