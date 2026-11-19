# Liu2026 TSALNS reproduction protocol v1

Date: 2026-11-02. The source of truth is the 16-page EJOR 334 (2026) article, its supplementary Table A1, the pinned Java source at commit `d86f5549ebc9c05d65fce16f61b6df4f7cb73158`, and the 120 `Instances_Alg` input files. This protocol is a prospective contract, not a claim that every run below has completed.

## Version identities

| ID | Implementation | Outer / location local / ALNS | ALNS weight bounds | Purpose |
|---|---|---:|---:|---|
| J0 | Pinned Java source with I/O, deterministic shared-RNG and best-so-far instrumentation in a copied tree | 500 / 100 / 5000 | 0.1 / 5.0 | Released-code semantics diagnostic, including infeasible output; **not** the literal uninstrumented binary |
| J1 | J0 with independent feasibility guards **including an added pre-ALNS guard** and sorted removed-node order | 500 / 100 / 5000 | 0.1 / 5.0 | Historical guarded diagnostic; pre-ALNS guard changes search and is **not** a faithful port comparator |
| J2 | J1 with Table A1 parameter substitutions | 500 / 500 / 5000 | 0.1 / 0.5 | Historical guarded paper-parameter diagnostic; **not** a faithful port comparator |
| J1b | J1 without the added pre-ALNS guard; keeps ALNS acceptance and final outer feasibility guards | 500 / 100 / 5000 | 0.1 / 5.0 | Physically feasible Java-code-profile comparator to P1 |
| J2b | J2 without the added pre-ALNS guard; keeps ALNS acceptance and final outer feasibility guards | 500 / 500 / 5000 | 0.1 / 0.5 | Physically feasible paper-parameter comparator to P2 |
| P1 | Corrected Python/native V6, Java-code parameter profile | 500 / 100 / 5000 | 0.1 / 5.0 | Feasible port comparison to J1b; J1 is a guard-position diagnostic only |
| P2 | Corrected Python/native V6, Table A1 profile | 500 / 500 / 5000 | 0.1 / 0.5 | Paper-parameter port comparison to J2b; J2 is a guard-position diagnostic only |
| R | Research-budget TSALNS and CA variants | Wall-clock controlled | Versioned | Later innovation comparisons, never paper reproduction |

All profiles record the other A1 values: gamma 0.9, xi 1, tau 2, phi 0.2, beta 0.8, update period 50, initial temperature 1000, cooling 0.95, lambda1/2/3 0.2/0.5/0.8 and rho 0.6. Parameters must be traced to Java constants and Python/native uses, not merely copied into JSON. A1's pseudo-code best-update expression is checked against actual source control flow and logged as a textual ambiguity if inconsistent.

## Input and witness contract

The formal article reports 120 instances, 12 size groups x 10 maps, with five independent runs per instance. A prior 30-case parameter comparison is a selected subset, not the complete original benchmark. Every run records input SHA256, source tree SHA256, variant patch SHA256, JDK/native hash, seed, exact command, exit status, wall time, raw output, parsed complete solution and independent evaluator report. Never discard failed or infeasible runs or compare their objective as if valid.

The physical model is SABS = one SD; DABS = one SD plus one LD. Each target is visited exactly once, coverage is by station type, battery includes return, and cumulative duty applies to each physical drone across trips. For the *same complete witness*, independent Java/Python objective and constraint calculations must agree to 1e-7 absolute cost and 1e-9 feasibility tolerance. A stochastic final-cost difference is not itself an implementation failure, but its signed paired distribution and failure rate must be reported, rather than asserting trajectory equality.

## Differential ladder and release gates

1. **Source and data lock:** verify all ten official Java source hashes and 120 instance hashes; preserve source unchanged. Compare Java/Python parsed coordinates, service times, energy and physical constants for every map.
2. **Objective and constraints:** evaluate identical complete witnesses in independent implementations. Include known feasible Greedy solutions, exact tiny cases and deliberately invalid SABS/battery/duty/coverage/duplicate cases. Any disagreement is a blocking model error, not an allowed final-cost gap.
3. **Initialization:** on all 120 maps compare station types, target ownership, drone ownership, route order, cost and feasibility. Separate raw Java's two storage slots from the one-physical-SD canonical representation and never normalize away a duty violation.
4. **Operator semantics:** on deterministic micro-instances test each location, route, destroy and repair family, action feasibility, target preservation, adaptive weight bounds, acceptance and cooling. Explicitly check that Java repair searches all open station/drone receivers; a CA implementation that restores this scope cannot be claimed as a new repair idea.
5. **Controlled search:** use the same map and seeded instrumentation for J0/J1/J2/J1b/J2b/P1/P2. Start with 12 outer iterations on representative instances, then 12 size groups x 3 maps x 5 seeds for J1b/J2b. Full 120-map x 5-seed runs for J0/J1/J2/P1/P2 are a separate matrix; do not equate J1/J2 with the faithful guarded comparator. Retain both iteration counts and timing. Java's original unseeded `Random()` is logged as an author-seed unknown, so exact trajectory parity is not required.
6. **Full benchmark:** target the 120 maps x 5 seeds per chosen reproducible profile, plus paper Table 1 group summaries. Before claiming reproduction, report coverage fraction, all invalid/error runs, group mean/best, paired gap distribution, 95% map-cluster bootstrap CI, runtime and known original-paper-vs-source differences. Gurobi's time-limited upper bound is not proven optimum.

The engineering gate for progressing to innovation is 100% independently feasible P1/P2 outputs, objective/constraint agreement for shared witnesses, no unexplained systematic instance-group bias, and an explicit account of J0 invalid outputs. A small final stochastic gap is acceptable when distributions, seeds, hardware and stop protocols are fully disclosed. A later new algorithm must beat a strong, correctly reproduced non-RL baseline under a separate equal-wall-clock protocol.

## Known source discrepancies and novelty implication

The released `Main.java` uses 100 location-local iterations and `ALNSSolver.java` caps weights at 5.0, whereas Table A1 gives 500 and 0.5. Raw Java can place SABS work in both route storage slots; its own feasibility check treats both as SD, while the paper permits one SD. J0 therefore requires independent feasibility auditing. J1/J2 inserted a pre-ALNS guard that can discard locally perturbed but repairable candidates; J1b/J2b remove that extra check but retain final feasibility filters. On a three-map seed-0 diagnostic, the J2 pre-ALNS guard rejected 135, 222 and 199 outer candidates, respectively; on `5_35_1`, no candidate reached ALNS and the result stayed at the Greedy cost. J2's large systematic gap versus P2 is therefore not a valid reproduction comparison. Official `RoutingOperator.java` repair methods iterate all opened stations and drones; the CA branch's `global_assignment` receiver mask is not novel solely by widening this scope. The paper-vs-code and Java-vs-port distinctions remain visible in every table.

## Completion Addendum (2026-11-02)

The first reviewer package is frozen at `reviewer_package/`. A focused Java/Python/native differential found that the Python/native port skipped opened stations whose drone route lists were empty in repair operators 2/3, while the pinned Java implementation considered those receivers. The two-source fix is isolated in `reviewer_package_semfix/`, with the original package and its results left intact. The correction is covered by four regression tests and a 209-case operator/RNG matrix; all effective final states match Java, including wrapper rollback of four invalid raw native candidates.

The semfix package completed a fresh 120-map x five-seed matrix for both P1 and P2: 600/600 independent feasible solutions in each, with no audit errors. Same-seed Java J1b/J2b comparisons cover 1,200 runs and have no feasibility/objective/source/hash audit errors. Cost differences are small: P1 map-cluster mean -0.0284% (95% CI -0.0711% to 0.0117%); P2 +0.0998% (95% CI +0.0255% to +0.1773%), where positive means Python is lower cost. All 12 Table 1 group averages and best values fall inside their semfix map-cluster bootstrap intervals. The full exact commands and literal audit output are in `reviewer_package_semfix/SEMFiX_FULL_RESULTS.md`; run `./reviewer_package_semfix/verify_semfix_package.sh` to reopen the frozen and corrected evidence.

This closes the practical reproduction gate, not original random-trajectory identity: author seeds were not published. Four invalid C intermediate repair candidates differ before the production wrapper restores the source state; these are explicitly retained in the operator report rather than hidden or treated as accepted-state mismatches.
