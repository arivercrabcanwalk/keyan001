# G2 driver independent initial review — failure audit

Date: 2026-11-03. This initial is frozen BEFORE receiving peer driver-review replies. Input driver SHA256: 9efe73a538121edee78261c9ac7e962a97dfd6879b121e8bf072fd573988bccf. Protocol v2 SHA256: e44122c48b4435a33b6db52d0a604aeb1caa25ff4e14b2dea517ecef12f31b24. Read-only source inspection; no project imports, synthetic tests, DP/evaluator, map diagnosis, solver or training executed yet.

## Accepted structure

- Fixed station types/station union and optional fixed-slot identity are checked when integrating complete station references; unresolved rows retain parent routes in separate full-map incumbents.
- All original fixed costs and operating time remain in evaluator costs. Parent/fixed/joint and ALNS denominators are complete-map costs, not owner-minute scalars.
- Both fixed-owner and joint station-domain references are attempted in frozen order, with an explicit map scheduling rather than hard end-to-end deadline. End-to-end serialization/validation overrun is reported.
- Complete map status requires accepted fixed and joint references at every station; partial maps are visibly partial and pure reassignment attribution withheld.
- Archived best-of3 is named three runs, retains all three cell rows and sums historical end-to-end time; it is not represented as a single 6s/12s solver.
- v2 transparently replaces the requested hard OS memory claim with a structural allocation-cell bound plus peak records; this is a finite computational design but not RSS/byte enforcement. No hard-resident-memory claim should reappear.

## Concrete issues to test or fix before execution

1. Saved Greedy identity is not checked in this driver version. build(ins) is validated physically but not compared against the already verified canonical archived Greedy complete solution. Frozen source/input alone should normally reconstruct it, but root promised an explicit canonical solution/domain/cost check; add this before deriving station sets. The existing G2_ALNS_GREEDY_PARENTS.json contains full canonical_solution and six-cell identities.

2. archived_comparators calls sha/read/evaluate before per-cell exception handling. Missing/corrupt metadata/solution, parser error or evaluator exception aborts the map/batch instead of preserving that cell as ARCHIVE_UNRESOLVED plus all six expected rows. This conflicts with v2's “Every missing/hash/identity/domain/evaluator mismatch remains a row.” Preflight hash-check reduces but does not eliminate this (TOCTOU, synthetic tests, unexpected evaluator rejection). Need per-cell handling, and no best-of3 value unless all three anchors for that budget pass.

3. The archived solution's own instance name/hash and task_identity/stored status are not locally checked. Current metadata checks instance/hash/method/seed/budget/solution_sha and candidate domain; metadata preflight verifies archive bytes against the preserved manifest, while the prior reuse audit already checked all identities. In the unchanged frozen bundle this transitive identity is supported. Still make local solution instance identity and task identity explicit to avoid using a cross-instance structurally identical witness in fixtures or later refactors; classify mismatches, not silently accept.

4. validate_reference subtracts audit['cost'] before guarding evaluator rejection/malformed output. The original evaluator returns cost=None on station-dimension errors, leading to TypeError and generic UNRESOLVED_EXCEPTION in run_map. The raw result witness then is not necessarily retained, contrary to v2. An evaluator rejection must record its audit and raw result even when cost absent/nonfinite; only compute numeric residuals when valid numbers exist. Domain() similarly assumes well-formed list shape. Synthetic fixtures should cover this path.

5. status names alone are not enough. result.status COMPLETE_* is not sufficient for integration: verifier, domain, cost residual, regression and shape checks must all pass. The current happy path does this. Synthetic tests should deliberately change slot membership for fixed-owner=True, station union, evaluator feasible=False, DP cost prediction, parent regression, and incomplete status; no fallback should be relabelled reference.

6. Partial fixed_owner-to-joint percentages mix coverage when one reference is rejected. run_map labels reassignment_difference_attribution but all-map summaries still include the raw difference; ensure analysis and narrative always preserve “mixed coverage” and report a separate complete-map stratum. This is not an incremental slot-reassignment effect on partial maps.

7. Driver metadata preflight includes prior UNIT_TESTS.json but not the new synthetic DRIVER_TESTS.json or test_g2_driver.py. If these tests are required pre-execution evidence, freeze both test source and receipt before the 24-map run. All receipts should correspond to the driver source version actually executed.

## Planned bounded checks

Only synthetic unit tests of validate_reference, archived_comparators and run_map partial assembly are authorized by root. Use dummy in-memory instance, dummy result and fake evaluator/build/DP functions; no real map or project evaluator/solver import. temp files model six archived cells. Tests should preserve expected rows/statuses and exercise malformed/identity failures. Failures are engineering evidence to fix before the map diagnostic; they are not headroom results.

Current conclusion: NEEDS_FIX_OR_EXPLICIT_PROTOCOL_AMENDMENT for canonical Greedy identity, per-cell archive failure retention, malformed audit guard/raw witness preservation, and new test receipt hash binding. No scientific run authorized by this review.
