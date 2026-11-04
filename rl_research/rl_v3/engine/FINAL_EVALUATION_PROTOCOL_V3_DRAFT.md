# CA-RL-TSALNS v5 - formal evaluation protocol v3 (DRAFT)

Snapshot: 2026-11-01 UTC
Status: protocol draft and test suite prepared; algorithm/method freeze is still pending. No formal optimizer run has been started on datasets/formal_v3.

## 1. Locked data suite

Dataset: datasets/formal_v3/manifest.json
- 30 main maps: 5 scale strata (8/50, 12/100, 16/150, 24/200, 32/300 stations/targets) x 3 spatial distributions (uniform, clustered, boundary) x 2 generation seeds.
- 6 extension stress maps: high-density route pressure; sparse long-distance geometry; tight receiver coverage; SD/LD workload imbalance; boundary concentration; combined coverage/energy stress.
- 36/36 maps have constructive complete-solution witnesses accepted by the independent evaluator.
- Exact SHA256s are in the manifest; no byte-hash overlap was found with any official Instances_Alg file or locked_v2 map.
- Generator SHA256: fe5cb5e11142ad67ec9c7fe1176e82f9f6da574326bcf254e49cf1eba4aa41af.
- Manifest SHA256: be65b6a0fe2b47b7e2faf123a1c7eb4f18ac92560fe818b61a593467e6b6a37e.
- This is a synthetic generalization/stress suite, not Liu original data.
- No solver, controller, or hyperparameter selection may inspect results from this suite before freeze. The maps have only been generated and witness-validated.

A failed first generation attempt (high-density witness assigned all tasks at a station to one drone due an indexing bug) is preserved in datasets/formal_v3_failed_attempt_20261101. It was not used. The corrected generator balances normal target assignments across both DABS drones and assigns high-energy stress targets to LDs; all 36 corrected witnesses pass.

## 2. Development evidence and candidate decision

### 2.1 RL controller gate

The 2,592-task RL Global Transfer matrix completed with strict source/checkpoint provenance, 100% feasibility and zero errors. On the 24-map development validation split:
- 6s vs M2 Global: BC +0.0104% (Holm p=0.1465), PPO +0.0588% (p=0.03149), A2C +0.0210% (p=0.07959).
- 12s vs M2 Global: BC +0.0416% (p=0.01367), PPO +0.0699% (p=0.004883), A2C +0.0536% (p=0.00293).
Positive means higher/worse cost. No learned controller demonstrated a corrected, meaningful improvement over M2 Global. RL is therefore not selected as a primary formal method under the current evidence. The negative result remains reportable.

### 2.2 Non-RL finalist gate

Same-source 10-seed development confirmation:
- M1D Global and M2 Global were statistically indistinguishable at both 6s and 12s.
- M1D Global had a small lower mean at 6s; M2 Global had a small lower mean at 12s.
- M4/LinUCB Global did not beat M2 Global after Holm correction.
M2 Global is retained as the primary non-RL reference because it is the adaptive-weights method and was selected in the pre-existing same-source finalist protocol. M1D Global remains a predeclared secondary finalist.

### 2.3 Joint receiver-scope gate

The 1,920-task full-search Joint scope matrix completed with one source hash, zero errors and 100% feasibility.
- Global Joint scope alone did not significantly improve M1D or M2 over local Joint scope at either budget.
- Global Assignment produced the most consistent gains, especially for M1D at both budgets and M2 at 12s.
- Adding Global Joint to Global Assignment did not significantly improve on Assignment alone.
Therefore the current formal candidate is Global Assignment repair, not Global Joint receiver scope. Joint operators remain in the full method unless the pending BC ablation or other predeclared development evidence justifies removal.

### 2.4 Paper30 parameter fidelity

The 300-task Paper30 parameter comparison completed:
- 30 original cases (21 small + 9 medium/large) x 2 profiles x 5 solver seeds.
- Both profiles: 150/150 runs reached the 500-outer-iteration limit, all feasible.
- Paper Table A1 profile mean cost 374.9804; released-Java parameter profile mean cost 373.6061.
- Paper A1 was +0.2393% higher/worse (95% bootstrap CI [+0.0986,+0.4024]%, Wilcoxon p=0.0002928).
This is a corrected V6 Python engine parameter-profile comparison, not byte-for-byte official Java execution and not the paper's Gurobi comparison.

## 3. Provisional formal method list

Final list must be frozen only after the pending BC state/mask/family ablation and final source audit. Current candidate list:
1. m0: research-budget Original TSALNS baseline.
2. m1d_global_asg: scheduled non-RL controller with global Assignment receiver scope.
3. m2: Adaptive Weights with local receiver scope.
4. m2_global_asg: Adaptive Weights with global Assignment receiver scope (primary proposed method).
5. m2_global_nojoint: same M2 Global configuration with Joint operator family removed (ablation).

Do not include BC/PPO/A2C as primary formal candidates unless a predeclared development result changes the current Go/No-Go decision. M0 Paper/Frozen remain in Block A parameter-fidelity analysis, not as substitutes for equal-budget M0.

## 4. Formal budgets and seeds

- Primary wall-clock budgets: 6s and 12s.
- Solver seeds: 1001-1010, paired across every method and map.
- 10 runs per method per map and per budget.
- Provisional total: 36 maps x 5 methods x 10 seeds x 2 budgets = 3,600 solver tasks.
- Use 8 workers under the current 12-CPU cgroup quota. Run budgets serially to avoid contention.
- All methods share the same input bytes, initialization policy, independent evaluator and wall-clock accounting.
- RL training costs are not relevant to the primary formal method list if no RL method is selected; retain them in the development appendix.

## 5. Statistical analysis

- Statistical unit: map. Average the 10 solver seeds within each map before paired inference.
- Report 30 main maps and 6 stress maps separately.
- Primary main-map comparisons: M2 Global vs M0, M1D Global, M2 Local, and M2 Global NoJoint; 4 contrasts x 2 budgets, one 8-test Holm family.
- Stress-map comparisons use a separate exploratory family; report all six map-level outcomes and uncertainty, do not pool with main maps.
- Report mean, median, SD, feasibility rate, runtime, end-to-end time, wins/losses/ties, paired relative difference, 95% paired bootstrap CI, Wilcoxon signed-rank p, rank-biserial effect, and Holm-adjusted p.
- Preserve every run row, manifest, solution, log, code hash and map hash. Do not delete failed or infeasible rows.

## 6. Freeze gate

Before the first formal optimizer call:
- Freeze exact method registry, configs, source, source archive, environment and CPU quota.
- Freeze the 36-map manifest and every map/witness hash.
- Freeze the solver seed list, budgets, method list and statistical test family.
- Freeze the analysis script and report schema.
- Produce a content-addressed v5 manifest and immutable source archive.
- Create results/FORMAL_V3_FREEZE.json.
- Verify that no formal output directory exists.
After the first formal result is inspected, no code, parameter, method, map, seed or analysis change is allowed.

## 7. Go/No-Go claim boundary

A learned controller can be claimed to have an independent contribution only if it beats the strongest non-RL controller under identical operators, initialization, evaluator and budget, with a meaningful paired effect, corrected statistical evidence and no feasibility loss. Current development evidence does not meet this gate.

If the final formal tests confirm the current evidence, the main algorithmic result will be a strong non-RL TSALNS extension centered on Global Assignment repair, with RL reported as a negative/non-confirmatory result. Do not relabel a non-RL result as CA-RL success.

### 1.1 Receiver-coverage diversity audit

The active formal_v3 mapset was revised before optimizer access to avoid a main-suite design that would make cross-station Assignment transfer mostly impossible. The main maps use 7.5 km station spacing and record, for each target, the number of feasible DABS/SABS receivers. Clustered maps intentionally have few alternative receivers; uniform maps have some; boundary maps have many. The six stress maps separately include overlapping and tightly restricted receiver structures. See FORMAL_V3_MAPSET_REVISION_NOTE.md for the preserved first candidate and the exact coverage audit.
