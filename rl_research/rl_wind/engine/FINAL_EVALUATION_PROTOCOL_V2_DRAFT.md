# CA-RL-TSALNS v5 - final evaluation protocol v2 (DRAFT)

Status: planning draft only. Not frozen, not executed, and not permission to open any held-out data.
This draft reconciles the latest user instruction (30 main new maps + 6 extension stress maps, 10 solver seeds per formal method) with the older server protocol that specified 60 locked_v2 maps and 3 seeds.

## 1. Separate evaluation blocks

### Block A - Liu paper reproduction

Keep this separate from the new-map generalization experiment.

- Paper benchmark: 30 original LRPHSD cases, consisting of 21 small cases (Table 1) and 9 medium/large cases (Table 2).
- The paper's 1.12% average-gap statement refers to the 21 small cases only.
- Use the original case files corresponding to geometry seeds 1-3 in the ten paper size groups.
- Compare the paper Table A1 parameter profile and released Java-source parameter profile separately. Do not merge their outputs or call one the other.
- The official Java source has a documented SABS physical-model inconsistency in the fixed-12 differential audit. Infeasible Java outputs must not be treated as valid objective-quality evidence. Report source behavior and corrected physically feasible port separately.
- Report initialization, location search, routing search, stopping condition, feasibility, objective components, and any deviation from the published implementation.
- The original paper's 5-run convention should be preserved where computationally feasible; exact seed IDs and any deviations must be recorded.

### Block B - independent new-map formal evaluation

Primary test suite:
- 30 main new maps.
- 6 additional extension stress-test maps.
- 10 solver seeds per formal method and per map.
- Main maps and stress maps are separate result strata. Do not pool them without also reporting separate breakdowns.
- These maps must be newly generated, independent of the 72 training maps, 24 validation maps, and the already inspected historical test split.
- The 36-map instance manifest must include each map's generator version, size/distribution stratum, generation seed, feasibility witness, and SHA256 hash.
- The map manifest must be locked before the first formal solver run. The solver must read exactly the names and hashes in the manifest.

The six stress cases should cover distinct structural failure modes, selected before algorithm freeze:
1. high target density / long route pressure;
2. sparse geometry / long inter-target distances;
3. tight station coverage / few feasible receiving stations;
4. strong SD/LD workload imbalance;
5. boundary-concentrated targets;
6. combined coverage and energy stress.

The 30 main maps should be stratified across station/target scales and spatial distributions. Exact cell counts and generation seeds must be recorded in the manifest; do not select maps after observing solver results.

## 2. Primary research-budget protocol

- Primary wall-clock budgets: 6s and 12s, identical for every method.
- Optional 2s and 30s sensitivity runs only if predeclared before the first formal run.
- Use the same hardware, cgroup CPU quota, worker count, instance bytes, initialization policy, evaluator and deadline accounting.
- Include cold model loading, initialization, search, finalization, independent evaluation and end-to-end time in the output. Report the internal solver budget separately from full end-to-end time.
- RL training/teacher-data collection is reported separately; policy inference and controller-state/mask construction are included in per-instance runtime.
- All methods must use the same initial solution or the same deterministic initialization protocol and paired solver seeds.

## 3. Method selection gate

The final method list is not fixed in this draft. It must be selected using development validation only after the current RL Global Transfer and Global Joint experiments finish.

Candidate methods to consider:
- M0 research-budget original baseline;
- M2 Global (selected non-PPO reference from the same-source 10-seed development confirmation);
- M1d Global and/or the predeclared M1d ablation controls;
- BC Global, PPO Global and A2C Global only if their development transfer results justify a formal test.

Do not include a learned method merely to make the final table look complete. If BC/PPO/A2C do not beat M2 Global on development validation with a meaningful, stable, corrected effect, record the negative result and do not claim an RL contribution. The primary non-RL comparator must remain the strongest development-selected non-RL method.

M0 Paper and M0 Frozen are parameter-fidelity diagnostics, not the primary equal-budget comparator. The paper stopping protocol belongs in Block A.

## 4. Statistical protocol

- Statistical unit: map (30 main maps and 6 stress maps reported separately).
- For each map and method, aggregate the 10 solver seeds before paired map-level inference.
- Report all planned tasks, including errors and infeasible outputs. Never condition the cost mean on successful runs only.
- Report mean, median, standard deviation, feasibility/success rate, wins/losses/ties, paired mean and relative differences, 95% paired bootstrap confidence intervals, paired Wilcoxon signed-rank tests, rank-biserial effect size, and Holm correction for the predeclared comparison family.
- Report per-scale, per-distribution and per-stress-scenario results.
- Include runtime, inference overhead, initialization and final validation costs.
- Preserve all raw per-run rows, manifests, logs, output solutions and hashes.

## 5. Freeze gate

Before the first formal run, freeze and hash:
- algorithm structure and exact method list;
- source code and source archive or Git commit;
- state/action/reward schemas and masks;
- model checkpoints and metadata;
- all configs and solver parameters;
- initialization, evaluator and feasibility checker;
- 36-map manifest and feasibility witnesses;
- solver seed list and budgets;
- analysis scripts, test family and statistical procedure.

No hyperparameter, reward, action, model, method, seed, map or analysis change is allowed after the first formal test result is inspected.

## 6. Older locked_v2 suite

The existing locked_v2 suite contains 60 synthetic maps and was designed under an older 3-seed protocol. Preserve it unchanged. Do not silently substitute it for the latest 30+6 / 10-seed plan, and do not open it while selecting algorithms. It may be retained as a separate supplemental stress suite only if a later versioned protocol explicitly includes it.

## 7. Go / No-Go

A claim of RL independent contribution requires a learned controller to beat the strongest non-RL controller under the same operators, initial solution, evaluator and budget, with a meaningful paired effect and corrected statistical evidence, without reducing feasibility.

If this condition fails:
- report RL as a negative or non-confirmatory result;
- retain the strongest non-RL joint-search method as the algorithmic result;
- do not retune on the 36-map test suite;
- reconsider the paper's contribution and venue honestly.

A successful formal result must also show robust behavior across scales and stress structures, fully feasible solutions, acceptable compute overhead, and a clear distinction from prior RL-guided location-routing and ALNS methods.
