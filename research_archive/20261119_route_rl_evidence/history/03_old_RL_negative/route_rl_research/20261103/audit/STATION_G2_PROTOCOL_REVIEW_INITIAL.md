# Independent protocol review: station split-DP G2

Date: 2026-11-03. Reviewer: `route_independent_audit`. Protocol identity reviewed: `route_rl_research/20261103/joint_route_env/G2_STATION_SPLIT_DP_PROTOCOL.md`, SHA256 `808c36e5db14c2c6ac29789777ea8e0dd72c38b0421242a4c8208492b5ce4a2f`. This is a read-only review; no code, solver, evaluator, DP, quality matrix, or training was run.

## Decision summary

The protocol correctly distinguishes a partial feasible candidate from an upper bound on remaining headroom. It explicitly says that replacing only solved stations with independently feasible DP witnesses demonstrates a **realized feasible improvement**, but does not bound remaining opportunity from above. It also keeps partial maps visibly unresolved and separates the long-cap oracle from later 6s/12s equal-budget method comparisons. These are important and correct.

The protocol is not yet sufficient to close the opportunity question across unresolved maps. The hard memory cap is absent; `max_states` and transition counts are not an enforced byte/RSS limit. The all-map feasible parent gives an upper bound on optimum, while headroom above the parent requires a lower bound on optimum. No lower bound is actually specified in the executable protocol for size-capped/time-capped stations. Those maps must remain headroom-UNRESOLVED; do not use their partial candidate cost as the missing optimum lower bound. In addition, parent-to-joint-DP gain mixes ordinary route reordering/repacking with changed LD/SD ownership, and the only baseline stated is Greedy, not the saved strongest route-SA result.

## Findings

### 1. Partial feasible candidate is not an opportunity upper bound

The protocol handles this correctly in `Bounds, limits and unresolved cases`: unresolved stations retain the original feasible parent; a candidate that replaces solved stations can demonstrate an achieved map-level improvement after independent full evaluation; it explicitly “does not bound the remaining opportunity from above.” `PARTIAL_REFERENCE_WITH_UNRESOLVED_STATIONS` also preserves that boundary.

Mathematically, if `B` is a complete feasible parent and `C_partial` is a complete feasible candidate, then `B-C_partial` is an achieved improvement and a lower bound on the best achievable improvement over B. It cannot cap the remaining improvement. For a cap one needs `LB_map <= OPT_map`; only then `(B-LB_map)/B` upper-bounds the possible relative gain. Since the current executable protocol supplies no such lower bound for unresolved stations, its legitimate output there is “opportunity unresolved,” not a full-scope NO-GO.

### 2. Add a hard byte/memory cap

`max_states=2^12` and `max_transition_checks=2,000,000` are useful work bounds but do not bound Python object overhead, cached path/predecessor arrays, evaluator buffers, or process RSS. Add an explicit per-process/per-map memory cap in bytes and state whether it includes input, parent, candidate, route witnesses and evaluator memory. Freeze allocation/preflight and termination behavior; on cap, flush a durable checkpoint if possible and mark current plus unattempted stations `UNRESOLVED_MEMORY_CAP` without dropping their rows. Do not pick the cap after observing size-specific outputs.

### 3. Clarify the `n<=12` cutoff rationale

The current source `exact.py` has a **whole-instance** limit `len(ins.targets)<=12`; this is not the same problem as solving all station pools independently, nor a prior station-level runtime result. A new fixed station-pool cutoff of 12 is acceptable as a conservative predeclared scope cap, provided the text says it is a new diagnostic resource rule inspired by, but not validated by, the old whole-instance cap. All `n>12` pools stay in the table as `UNRESOLVED_SIZE_LIMIT`; a partial fixed-owner or partial slot split must not be relabelled station-exact.

### 4. Keep feasibility, objective reconciliation and improvement separate

The evaluator's `1e-7` values are feasibility allowances (coverage, trip battery, cumulative duty), not cost tolerances. Freeze the edge-distance calculation, route-order length accumulation, service/energy accumulation and tie handling used by the DP, then re-evaluate each reconstructed witness. The old `exact.py` uses different arithmetic ordering and `1e-9` resource limits; it must not be silently reused as though it matched the new protocol.

The absolute `1e-8` map-cost tolerance currently has two possible readings: evaluator-vs-DP reconciliation, and whether a candidate regressed versus the parent. Give it one declared role (preferably DP/reconstructed complete-cost numerical reconciliation only). Always retain raw parent-minus-candidate costs and percentage effects; do not round small wins, losses or ties to zero. If the exact/reference candidate is worse by any amount, retain that row and the parent witness; a non-regressing `min(parent, candidate)` oracle incumbent may be reported only as an explicit separately formed feasible incumbent, not as a silent repair.

The labels `Exact station formulation` and `FULL_STATION_DOMAIN_REFERENCE` should be read as a reference produced by exhaustive DP under the frozen numerical recurrence. They are not by themselves a formal real-arithmetic/production-IEEE certificate. Keep DP scalar, reconstructed route score, independent evaluator score and numerical residual separate. Borderline route feasibility or unresolved arithmetic should block exact-reference status, not be fixed by changing EPS.

### 5. Full objective, baseline and causal decomposition

The planned `(C_parent-C_candidate)/C_parent` denominator is correct for relative effect against that complete parent and retains fixed station cost, all target service/flight operating cost and all station routes. It is superior to route-minutes-only percentages. Preserve the complete `C_parent`, fixed-cost and operating-minute decomposition for every map.

However, the declared parent is Greedy. Parent-to-joint-DP improvement includes route order and trip-repacking gains even when a target keeps its original drone. It cannot be described as the added LD/SD target-reassignment gain. Reuse the saved feasible route-SA/ALNS complete solutions as archived anchors and compute an explicit fixed-owner station reference beside the joint-slot reference when possible. Compare at least:

- Greedy parent -> joint split-DP reference: total route-domain opportunity from that parent.
- Fixed-parent-owner exact/reference -> joint split-DP: additional value of releasing target-to-slot ownership, with complete witnesses/bounds for both.
- Saved best route-SA result -> joint reference: historical remaining room beyond the strongest saved non-RL route optimizer.

If the old fixed-owner scalar artifact has no complete witness or misses groups, do not overclaim the difference; recompute the fixed-owner component in this same station-level run for the attempted size domain or mark the decomposition unresolved. Keep all three distinctions; none turns the oracle into a 6s/12s solver result.

### 6. Samples, timing and interpretation

All 24 exposed Stage-A maps and all 132 station rows must remain, including 98 active, 82 DABS, SABS, closed stations, and every `n>12`/timeout/memory/numerical row. No p-values/generalization claim from this exposed sample. Freeze deterministic sorted map/station traversal and clarify that the 12-second per-map timer begins before parent reconstruction/input processing and ends after candidate full-map evaluator validation and durable output, so late stations cannot be favored by accidental order. Keep a separate DP-core timer if useful. Confirm whether the cap applies to every map independently and set an overall batch-wall cap.

The DP diagnostic is an oracle/reference opportunity with its own compute cap; its runtime is reported but not represented as a fair 6s/12s method. A separate new-development G3/G4 run must give each complete map 6s and 12s total end-to-end budget, with common initialization, model-load convention, all stations, inference/solver generation, validation, failure and fallback cost. Saved old 6s/12s results remain exposed and historical, not a new performance comparison.

## Questions for cross-exchange

1. Root: does the current protocol intend to make any opportunity upper-bound or NO-GO claim on partial maps? If yes, where is the valid `LB_map` for every unresolved station; if none, confirm those rows remain inconclusive.
2. Mechanism agent: do you accept that the partial feasible result is an achieved-gain lower bound, never a remaining-headroom upper bound, and that unresolved stations need a separately validated LB to close the map? Also confirm that the current text needs a hard memory cap and clearer separation of the three baseline/decomposition comparisons above.
3. Failure agent: independently check the exact source/evaluator numerical semantics and whether Greedy-only parent reporting could be misread as remaining opportunity beyond saved route-SA.

## Execution boundary

This review accepts the protocol's no-filtering, complete-map validation, and oracle-versus-method distinction; it does not authorize any run. A root-frozen addendum or corrected protocol must specify the cap, numerical rule and any bounded-headroom claim before execution. No Formal, new-development, RL-superiority, or novelty claim follows from this exposed-data diagnostic.
