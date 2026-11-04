# Liu TSALNS parameter reconciliation — paper Table A1 vs official Java source

Date: 2026-10-31  
Purpose: prevent conflating the paper's supplementary parameter table with the released Java implementation.

## 1. Paper source: Appendix A, Table A1

The Optimization Online preprint / supplementary material lists:
- Adaptive reward: gamma=0.9, xi=1, tau=2, phi=0.2.
- Weight smoothing beta=0.8, update period h=50.
- Weight bounds: 0.1 to 0.5.
- Simulated annealing: alpha=0.95, initial temperature 1000.
- Operator parameters: lambda3=0.8, lambda2=0.5, lambda1=0.2, rho=0.6.
- Stopping: Kmax=500 outer iterations, K'_max=500 local-search iterations, K''_max=5000 ALNS iterations.

Source: Liu, Hu & Cheng, “Drone Station Location and Routing Optimization for Infrastructure Inspection,” Appendix A, Table A1. PDF lines 793–899 in the opened Optimization Online preprint.

## 2. Released official Java source inspection

The checked-in source at reference/java/official_source was read directly:
- Main.java: MAX_ITERATIONS=500, INITIAL_TEMPERATURE=1000, COOLING_RATE=0.95.
- Main.java location-stage local search loop is 100 iterations, not 500.
- ALNSSolver.java: maxIterations=5000, initialTemp=1000, coolingRate=0.95, finalTemp=1e-3, updateInterval=50.
- ALNSSolver.java adaptive reward: accepted base reward 1.0; rejected penalty -0.2; accepted improvement adds 2 * improvement/(improvement+1).
- ALNSSolver.java score decay is 0.9; weight smoothing retains 0.8 of old weight and adds 0.2 of average score.
- ALNSSolver.java clamps weights to [0.1, 5.0], not [0.1, 0.5].
- RoutingOperator.java hardcodes similarity parameters 0.8, 0.5, 0.2 and load-balance coefficients 0.6/0.4.

Thus the released Java implementation differs from Table A1 in at least two material settings: location local-search iterations (100 vs 500) and upper adaptive weight bound (5.0 vs 0.5). The reward and decay mechanisms are implemented in Java as the Table A1 values imply.

## 3. Existing V6 profiles

| Profile | Outer | Location LS | ALNS | Weight upper | Meaning |
|---|---:|---:|---:|---:|---|
| paper_parameters.json | 500 | 500 | 5000 | 0.5 | Paper Table A1 profile |
| frozen_v6.json | 500 | 100 | 5000 | 5.0 | Released Java source profile |
| research_budget.json | 100000 cap | 100 | 5000 | 5.0 | Research wrapper; wall-clock deadline governs stopping |

The V6 Python port implements the reward terms (0.9 decay, 1 base reward, 2 improvement enhancement, -0.2 rejection penalty), 0.8/0.2 smoothing, and 50-iteration updates. The C/native route operators port the official Java operator coefficients.

## 4. Reproduction claims allowed

- “Released Java source profile”: use 500 outer, 100 location-local iterations, 5000 ALNS iterations, upper weight 5.0, and the Java reward/smoothing/update rules.
- “Paper Table A1 parameter profile”: use 500 outer, 500 local, 5000 ALNS, upper weight 0.5, and Table A1's other settings.
- “Research-budget profile”: use the frozen Java-source parameterization under an explicitly stated wall-clock budget.

Do not describe paper_parameters.json as a byte-for-byte reproduction of the released Java source. Do not describe a six-second budget as the paper's original stopping protocol.

## 5. Remaining source verification

Before claiming exact reproduction:
1. Run official Java and V6 on the same instances and fixed seeds with all stochastic calls aligned where possible.
2. Compare initialization, location move selection, destroy/repair, reward updates, cooling, acceptance and final objective.
3. Explain every difference, including Java's unseeded default Random() and any deterministic instrumentation.
4. Run paper Table A1 and released Java profile separately; never combine their results.
