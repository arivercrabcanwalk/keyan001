# Official Java source: parameter and physical-model audit

Date: 2026-10-30. Source is pinned by reference/java/SOURCE_LOCK.json to repository commit d86f5549ebc9c05d65fce16f61b6df4f7cb73158; all ten official .java files passed SHA256 verification. A separate instrumented copy was compiled with Amazon Corretto JDK 17.0.21. The official source directory remains unchanged.

## Parameter discrepancy

| Item | Pinned official Java source | Liu2026 supplementary protocol (paper_parameters.json) |
|---|---:|---:|
| Outer iterations | 500 | 500 |
| Local search iterations per outer iteration | 100 (Main.java) | 500 |
| ALNS iterations | 5000 (ALNSSolver.java) | 5000 |
| Operator weight lower bound | 0.1 | 0.1 |
| Operator weight upper bound | 5.0 (ALNSSolver.java) | 0.5 |
| Initial temperature | 1000 | 1000 |
| Cooling rate | 0.95 | 0.95 |

Therefore the checked-in Java source is not parameter-identical to the supplementary parameter protocol. Keep three identities separate: pinned source-code profile, paper supplementary profile, and wall-clock research-budget profile. Do not label the pinned source's defaults as the supplementary protocol.

## Physical-model discrepancy: SABS drone count

The paper model defines SABS as one small drone. In the pinned Java source:

- Init.generateRoutes1 initially places SABS work in smallDroneRoutes (route slot 1).
- Solution.java stores two route slots at every station (slot 0 described as large drone, slot 1 as small drone).
- Check.isOverallSolutionValid sets hasLargeDrone = (stationType == 2).
- Check.checkStationPathsEnergy nevertheless iterates over both route slots. For a small station, hasLargeDrone is false, so both slots are checked using the small-drone battery capacity. It does not reject a nonempty slot 0.
- Several RoutingOperator routines use the same (stationType == 2 && droneIndex == 0) ? largeBattery : smallBattery rule. Thus a small station can acquire work in both route slots, effectively permitting two small-drone route lists despite the one-small-drone SABS model.

The independent Python evaluator enforces the one-drone SABS contract and rejects these solutions as large_drone_at_small_station. This is a source-code/model mismatch, not a Python cost-rounding discrepancy.

## Fixed-12 trajectory differential

Protocol: 6 runs = 3 official instances × 2 controlled seeds; 12 outer iterations; local=100; ALNS=5000; weight range 0.1–5.0; T0=1000; cooling=0.95. Instrumentation replaces separate Java RNG construction with one shared seeded java.util.Random, records best-so-far output, and adds cooperative budget checks. The chosen seeds are controlled comparison seeds, not recovered author seeds. This is not an exact reproduction of the author's unknown random trajectory.

| Instance | Seed | Java independent feasible? | Python feasible? | Same station types? | Same routes? | Absolute objective difference |
|---|---:|---:|---:|---:|---:|---:|
| 3_10_1 | 0 | No | Yes | Yes | No | 0.333876 |
| 3_10_1 | 1 | No | Yes | Yes | No | 0.333876 |
| 5_35_1 | 0 | Yes | Yes | Yes | No | 27.506843 |
| 5_35_1 | 1 | Yes | Yes | No | No | 4.569556 |
| 7_65_1 | 0 | No | Yes | No | No | 1.498390 |
| 7_65_1 | 1 | Yes | Yes | Yes | No | 0.149604 |

Summary: Java independently feasible 3/6; Python 6/6; station-type equality 4/6; route equality 0/6. Java's reported objective agrees with independent recomputation to floating-point tolerance, but that does not make the infeasible route assignments valid. No exact trajectory parity is established.

## Decision

1. Do not use the invalid Java outputs as feasible objective comparisons.
2. Preserve official source unchanged and retain its outputs as source-behavior evidence.
3. Before claiming faithful reproduction, either obtain author clarification/corrected source or document a separately named physically corrected reference implementation.
4. The paper-parameter V6 profile remains a separate protocol; it must not be conflated with the pinned Java code profile.
