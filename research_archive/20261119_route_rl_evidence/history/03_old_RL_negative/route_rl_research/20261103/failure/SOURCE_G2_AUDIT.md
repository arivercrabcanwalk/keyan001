# Prior G2 Artifacts and Expanded Route-RL Scope: Independent Audit

Date: 2026-11-03. Agent: route_failure_audit. Read-only audit of the 13-file prior-G2 retrieval and the existing route-RL/source/prior-art records. No G2 script, optimizer, evaluator, or training was run or modified.

## Executive decision

1. The claim in `diag_g2_allsizes.py` and `diag_g2_seedmatched.py` that ALNS(6s)-ALNS(120s) is an upper bound on remaining optimal route-quality headroom is mathematically reversed. The observed feasible 120s solution supplies a lower bound on the true opportunity, not an upper bound. The 6s and 120s samples are additionally not nested anytime runs.
2. The exact route DP result is useful and internally cross-checked for **177 fixed greedy drone-ownership sets of size at most 12**. Its `1062` entries per method are six repeated old solver cells for each of those sets, not 1062 independent maps. Three ownership sets were skipped. The reported mean is an ownership-cell-weighted route-operating-minute percentage, not a map-level/full-objective effect.
3. Consequently, these prior artifacts do not establish a universal upper bound below the 0.3% gate, and they do not close the expanded scope where the policy may reassign targets between SD/LD slots inside a fixed station.
4. Allowing the policy to select `(drone slot, target)` or `(drone slot, RETURN)` while station type and target-to-station ownership stay fixed is consistent with “directly choose UAV routes, not search operators.” It is a meaningful widening from Stage A, but it is already the explicit Stage-B design in the old route-RL draft. The widened action domain itself is not a new G0 mechanism or novelty claim.
5. The prior noise run failed with an exception and produced no usable completed summary. Its log must not be cited as a measured noise floor.

## G2 source and result audit

### 1. `headroom_all_sizes.json` is not a strict upper bound

`diag_g2_allsizes.py` compares, per map, the minimum of three 6-second route-SA runs with one 120-second run (seed 101). It calls

`100 * (C6 - C120) / C120`

an upper bound on the gain still available over C6. Let OPT be the fixed-ownership route optimum. Since C120 is a feasible solution, `OPT <= C120`; hence `C6 - C120 <= C6 - OPT`. The observed difference is at most the true remaining gap, not at least the true remaining gap. If C120 is worse than a lucky C6 run, the observation can even be negative while the true gap to OPT is nonnegative. This feasible incumbent cannot cap how much an unrun method might improve C6.

The compared runs are not paired: C6 is best-of-seeds 101/102/103, while C120 is one seed 101. The artifact reports mean +0.006742%, median 0%, maximum +0.280046%, and no map above 0.3%, but the inequality and sampling protocol do not support the script's “no route policy can pass” verdict. Two rows are negative: 4_30_7 (−0.420332%) and 8_80_8 (−0.095411%).

The corresponding log confirms 96 completed feasible jobs (24 maps × three 6s seeds + one 120s seed), so this is a real finite comparison. It is not a certified bound. A corrected reading is only: under these particular runs and starting incumbents, long-budget outcomes usually did not improve much relative to the selected short-budget outcome; seed noise and the ALNS schedule remain material.

### 2. Seed-matched artifact also does not repair the bound

`diag_g2_seedmatched.py` compares best-of-3 at 6s and 120s, and checks raw same-seed costs. It obtains mean +0.030531%, median 0%, maximum +0.520686%, two maps above 0.3%, and two negative map-level differences. The script's rationale that “same seeds imply monotonicity” is false for this implementation.

The route-SA accepts moves using a temperature schedule whose temperature depends on elapsed fraction of the supplied budget. Changing the budget from 6s to 120s changes the trajectory and acceptance decisions, even with the same RNG seed; the 120s run is not a continuation of the 6s run. The saved result records four same-seed non-monotonic cases:

| Map / seed | 6s operating minutes | 120s operating minutes | 120s worse by |
|---|---:|---:|---:|
| 6_50_8 / 102 | 699.057149 | 699.093489 | 0.036339 |
| 6_50_8 / 103 | 697.724326 | 699.093489 | 1.369163 |
| 8_80_8 / 101 | 1087.492355 | 1089.059045 | 1.566690 |
| 8_80_8 / 102 | 1084.430137 | 1089.059045 | 4.628908 |

At best-of-3, 6_50_8 is −0.195848% and 8_80_8 is −0.425037%. These observations contradict both per-seed and best-of-3 monotonicity. Matching seed labels is useful for paired comparisons; it does not make different budget-dependent algorithms an anytime path or a mathematical bound. As above, the 120s feasible incumbent cannot upper-bound OPT headroom.

The 0.030531% mean is a descriptive best-of-three comparison over these 24 exposed maps, not a strict ceiling on the performance of a new route policy. It has no map-bootstrap uncertainty or independent formal status.

### 3. Exact DP scope, repetition, and interpretation

`diag_g2_headroom.py` fixes the station/mode and each target's existing drone owner, then exactly optimizes each drone's closed multi-trip route for owner sets up to 12 targets. The Held–Karp subset tour cost/energy and partition-label DP are appropriate for that restricted subproblem: service is order-independent, trip energy increases with tour length, and the partition labels enforce per-drone duty. The artifact reports 177 solved owner sets, 3 skipped, maximum solved size 12. `dp_self_validation.json` records no feasible solution beating DP on 177 checked sets and no mismatch against brute-force enumeration on 134 sets of size at most 7. This is useful validation for the restricted DP result.

For each exact owner set, six old method cells are collected. Thus each method's `n=1062` equals `177 × 6`; it is repeated solver-seed/budget observations nested within 24 maps and 177 owner sets, not 1062 independent samples. The 0.156895% route-ALNS mean gap (median 0%, max 5.46266%, 84.46% exactly at DP within tolerance) is a descriptive mean of those per-owner-cell route-minute gaps. It is not an independent-map estimate, has no map-level CI, does not weight by full-map objective, and omits three owner sets.

For a **fixed target-to-drone ownership**, an exact route optimum for an owner set bounds that same owner's attainable route cost. This result is informative about old fixed-owner ALNS on the covered sets. It does not bound a policy that can change the partition of a station's targets between its SD and LD slots, because those are different owner sets and the prior DP never optimized over the slot assignment. It also does not provide an upper bound for the 3 skipped sets.

The route percentage's denominator is exact per-owner operating minutes. The project development gate is based on map-level relative change in the complete LRPHSD objective against the strongest equal-budget method. Those quantities are not interchangeable. Even with station types fixed, a new aggregate must form each complete solution, recompute full objective and compare by map; owner-set rows cannot serve as independent map replicates.

### 4. `diag_g2_noise.py` is a failed run

The retrieved `noise_run.log` ends in `AttributeError: 'list' object has no attribute 'get'` at the evaluator-details access in `decompose`. The evaluator returns `details` as a list, while the script treats it as a dict. The exception propagates out of the multiprocessing iterator. The log has no completed-run count, A/A summary, or final output file; the script writes its output only after the failed comprehension. Partial workers may have run before the exception, but their results are not an accepted completed matrix. Do not infer a measured noise floor, full-objective headroom, or use the script's 0.3% discussion as a result. Preserve this as a failed attempt; this audit did not repair or rerun it.

## Does the expanded physical action remain within the user's request?

Yes, provided the learned action only chooses physical drone execution: `(SD or LD slot, eligible target)` or `(slot, RETURN)`. This lets the policy decide which drone flies a target, the order of visits, and how its route is split into trips. It does not choose a search operator, algorithm, neighborhood, destroy/repair action, action intensity, or compute budget. Keep station open/closed status, station type, and target-to-station ownership fixed for this first expanded scope.

This is distinct from Stage A's causal route-only scope, which freezes target-to-drone ownership too. It is **not distinct from the old Stage-B proposal**: that draft explicitly lets the policy “select which drone to advance and then select a feasible next target or RETURN,” with shared DABS state, per-sortie battery and per-drone cumulative duty. The plan change makes this branch in-scope under the user's clarified requirement; it does not make the Stage-B design newly invented.

The source/prior-art record already identifies hierarchical target/drone decisions and multi-route energy masks in Li & Gonsalves (full-text record), and DPTARL includes sequential target/return decisions and dynamic endurance pruning. Those do not establish exact equivalence to LRPHSD's fixed multi-station SABS/DABS, SD/LD slot and cumulative-duty model; key DPTARL/ESWA/RESS/TRE texts remain incomplete in the retrieval ledger. Preserve that distinction: generic `(slot,target/RETURN)` decision granularity is prior-art-adjacent and the old Stage B already stated it; any problem-specific increment remains a hypothesis requiring full-text comparison and a concrete algorithmic rule.

There is also a structural challenge to test rather than assume away: with station and station-owned targets fixed, the objective is additive over drone slots; per-trip energy and per-drone cumulative duty are slot-local, with no shared time-window/synchronization constraint in the fixed LRPHSD model. Jointly assigning each station's targets to its eligible slots and routing each slot may therefore admit a strong assignment-plus-route-DP/branch-and-bound baseline. Interleaving which slot takes the next action may merely serialize two independent route constructions. This does not prove the expanded problem trivial; it means an RL-specific coupling, useful representation, or non-RL gap has to be demonstrated rather than inferred from a joint action space.

## Correct scope for the next G2/G3 design

Do not repeat the prior runs as a new result. Reuse these artifacts with the corrected boundaries:

1. Label the previous exact result “fixed greedy target-to-drone owner route DP diagnostic,” with 177/180 covered owner sets and 1062 nested task-cell observations; retain all three skipped sets.
2. Label both long-budget comparisons “finite ALNS sensitivity diagnostics,” not headroom upper bounds. Retain the negative rows, nonmonotonicity, and noise-run failure.
3. For the expanded scope, freeze station types and target-to-station ownership, but permit direct SD/LD target assignment in every method. On each DABS, compare complete disjoint target partitions plus per-slot energy-feasible multi-trip routes. Include exact assignment+route optimization where tractable, bounded DP/branch-and-bound or beam for larger sets, constructive rules, cross-slot relocate/repack and route-SA/ALNS; share the initial solution, full validator, incumbent/archive policy and wall-clock accounting.
4. Treat any exact solver as an opportunity/reference baseline, not innovation or an RL oracle gain. Aggregate complete solutions at map level with full objective, map bootstrap and the preregistered budgets. The earlier per-owner DP cannot be used to close or promote this expanded scope.
5. G0 remains open. A mechanism beyond the already drafted Stage B action interface, generic hierarchical assignment+routing, and exact/simple joint baselines still needs a specific falsifiable increment. No training authorization or G0 pass follows from this scope clarification alone.

## Artifact identity

The retrieved directory and files are preserved untouched. The transfer manifest records source names, sizes and hashes. Key result identities:

- `headroom.json`: SHA256 `021eaa475567523928f091963531902cdf554752252a34738752b7948060e2d9`.
- `headroom_all_sizes.json`: SHA256 `1ca0b5f8b3c6d87558fec630083833097bea916cc960f57466f35bd435f3c5d1`.
- `headroom_seedmatched.json`: SHA256 `6824f4229a4e4d5b294c2b07d796605f23924aef6f7a058fb2e1ec50adcaa646`.
- `dp_self_validation.json`: SHA256 `1dc4a6b01d5ed57a7a3bec8a696b9d836e6082fe2bdc183ae0169847da8710bc`.
- `noise_run.log`: SHA256 `943e43bfa9806a95d1764ca1ba70bd29784fd4d8344432ddde5ded456fcbe825`.

New runs by this audit: 0. Scripts/results modified: 0.
