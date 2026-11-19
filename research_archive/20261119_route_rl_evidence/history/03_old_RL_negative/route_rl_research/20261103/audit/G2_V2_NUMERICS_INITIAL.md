# Independent initial: G2 v2 protocol and station DP numerical review

Date: 2026-11-03. Reviewer: route_mechanism_g4. This initial was frozen before receiving the peer's v2 verdict. Reviewed protocol SHA256 `e44122c48b4435a33b6db52d0a604aeb1caa25ff4e14b2dea517ecef12f31b24` and DP SHA256 `9b9bb690ac1372c9742e93edb15a8b6465d8ec22e21e1b8c016fea094d20af34`. The earlier initial/cross responses remain unchanged. This review is read-only; it executes no new tests, evaluator, solver, DP or real-map diagnostic. The separately authorized synthetic suite already passed 16 tests under this DP hash and is recorded in `g2_transaction/UNIT_TESTS.json`; it is implementation evidence only.

## Initial decision

**Protocol v2 conditionally acceptable as a bounded historical numerical-reference diagnostic; no execution acceptance until the frozen driver implements the stated reconciliation, domain, timing, archival, unresolved and memory/error accounting.** No real/IEEE optimum, useful opportunity ceiling, same-budget solver win, mechanism novelty or RL advantage follows from this approval. I identify two numerical edge-predicate mismatches to resolve or explicitly classify before real-map execution; neither is repaired by the already passed tiny tests.

## v1 concerns resolved by v2

- Complete numerical references are explicitly distinguished from strict real/IEEE optimality certificates. The scalar DP and trip-permutation pivot justification are stated as mathematical-recurrence reasoning rather than production-evaluator proofs.
- The protocol distinguishes `1e-7` feasibility, `1e-8` DP-to-witness complete-cost reconciliation and a separately defined `1e-8` parent regression screen, keeps raw effects/signs and rejected witnesses, and forbids silent repair.
- The n<=12 station-union cutoff is newly declared, not inherited station-level validation from old whole-instance exact.py. Fixed-owner and joint references use the identical union cutoff.
- Partial candidates are witness-backed realized improvement only; unresolved stations remain in all map rows; no useful full-map opportunity upper bound is claimed because no new lower-bound certificate is introduced. The global numerical-reference status requires both references completed everywhere.
- Greedy->fixed-owner, Greedy->joint, fixed-owner->joint, and archived route-SA->joint have different declared interpretations. Only two whole-map-complete references support the numerical-reference reassignment contrast; partial coverage differences are not called pure reassignment gain.
- 12s is explicitly a scheduling deadline, with independent validation/serialization charged after it; 360s is a batch scheduling cap, not a hard end-to-end performance budget. Fixed-owner-before-joint order and deterministic map/station order are disclosed.
- State/transition limits are explicitly structural rather than falsely labelled as an OS/RSS hard memory limit. Peak allocation/RSS recording is promised. This is an explicit revision of the earlier hard-cap request, not evidence that a byte/RSS cap was implemented.

## Remaining numerical contract checks

### N1: coverage operation differs from the frozen evaluator

DP `_distance` uses `sqrt(dx**2+dy**2)` for both route geometry and coverage, then coverage accepts `radius - distance >= -EPS`. Evaluator coverage instead tests `math.hypot(dx,dy) > radius+1e-7`. These are not the same IEEE predicate at the boundary. Route-length sqrt matches the evaluator's route geometry, but this does not imply that coverage sqrt matches the evaluator's separate hypot coverage test.

Before execution either use the evaluator's literal coverage operation/predicate in the DP precheck, or explicitly preserve this mismatch and route every borderline disagreement through a numerical-unresolved status without silently extending coverage. Because the frozen parent already covers the same union, parent validation is a useful validity check, but should not turn a rejected DP coverage precheck into an unexplained input error. Root should choose the precise handling before any real-map result.

### N2: energy comparison is algebraically but not bitwise equivalent

Trip feasibility uses `battery - trip_energy >= -EPS`, while evaluator uses `trip_energy <= battery+EPS`. This algebraic transformation can move a floating boundary by rounding. Duty uses the evaluator-style `slot_dp <= duty_limit+EPS`, but the DP service sum is sorted-ID low-bit recursion, not route-order service sum, and partition recursion association differs from sequential reconstructed duty.

v2 correctly does not claim exact IEEE equivalence, so this is not an obstacle to a qualified witness reference if all raw DP/evaluator feasibility discrepancies are retained and rejected/ambiguous witnesses are unresolved. A simple conservative improvement is to freeze the literal evaluator-style energy/coverage comparisons for the DP prechecks. This review does not alter the core.

### N3: freeze exact arithmetic by source identity and retain actual slacks

The code defines route edges with sqrt, tour-distance accumulation in path/visit order, division after closing, subset service/energy in decreasing ID-index recursion, strict `<` tie retention with ascending loop indices, and partition submask order. These operations are deterministic under the hashed source but not all spelled out in v2. Retaining the exact source plus DP values and evaluator residuals suffices to define the numerical recurrence; claims must remain at that level. Driver must save evaluator-computed trip and cumulative-duty slacks separately from `slot_duty_slack`/`trip_metrics`, which currently contain DP estimates. Coverage margins and actual evaluator residuals are not produced by the core and must be added by integration.

## Timing, resources and output conditions for driver audit

- Entry/HK/partition/completion budget checks are now caught and returned as `UNRESOLVED_BOUND`; the two synthetic cap tests passed. Empty/closed and early input/status returns intentionally do not consume DP work; driver must not launch new nontrivial references after deadline. `max_transitions` is per WorkBudget/reference, not shared unless deliberately reset, and any deadline detail must remain visible.
- Initialization, target coercion/validation, coverage checks, state estimate, and some bounded array/reconstruction loops occur outside transition checks, so the protocol's admitted scheduling overrun is material. Record full map and core time; do not report exact enforcement at 12.000s. Batch stop must still preserve every pending map/station row.
- No byte/RSS hard cap is implemented here; bounded n/state shapes keep the main arrays finite. Driver must record allocation/RSS and preserve MemoryError or other failures with parent fallback rather than claim a certified resident-memory ceiling. A true forced-process kill cannot be assumed to flush a witness unless the driver explicitly handles it.
- Both reference solutions must be independently integrated into complete parent-map copies, checked for target union/types/fixed ownership and independently evaluated before station completion acceptance. Raw rejected candidates cannot be overwritten by the parent fallback.
- Archived comparator identity/hash checks and full evaluator rescoring must not be omitted or inferred from names. Missing cells remain unresolved. Partial references versus archived anchors retain full original cost and seed/budget identity, but no causal or same-budget claim.
- A numerically complete map is not a certified headroom ceiling. Any reported fixed-owner->joint difference must retain raw values, numerical qualification and both completion states; the fact that joint contains fixed-owner mathematically does not make every floating implementation outcome monotone.

## Execution disposition

No G2 map or server execution is authorized by this initial. After source-predicate disposition and frozen-driver review, this bounded diagnostic can be accepted for the stated reference/realized-improvement purpose only. G0 innovation, G3 strongest-method comparison, G4 training/RL evidence, G5 Formal and G7/G8 remain separate and unpassed.
