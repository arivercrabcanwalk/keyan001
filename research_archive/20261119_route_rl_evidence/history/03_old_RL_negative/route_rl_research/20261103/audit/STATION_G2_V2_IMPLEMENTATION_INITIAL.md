# Independent v2 station split-DP protocol and implementation initial review

Date: 2026-11-03. Reviewer: `route_independent_audit`. This initial assessment was frozen before reading the other reviewers' v2 initial reports or sending this review's objections. No solver, DP, evaluator, tests, training or server tasks were run by this reviewer. Existing tiny-test results were read as evidence, not reproduced.

## Reviewed identities

- protocol: `<LOCAL_PATH>`; SHA256 `6dbfd7135c86fb80543fa8a0c9d1cc6f249fe81ad961d1a3bfcdf658b188e50e`.
- dp: `<LOCAL_PATH>`; SHA256 `8f4d05da5d0a829b8d6ce0889a10e0f5e990a3e1687505b36e61b28eb1c8da06`.
- tests: `<LOCAL_PATH>`; SHA256 `1ae12250b45d654c3d60f587b2edde4c908cc860d75c3fafb3c1b087e6eef87f`.
- test_evidence: `<LOCAL_PATH>`; SHA256 `4244f2bf08841e6d0fe8f2f1a7d399222cdef4180c5c7b2c20f7846d5416bbd0`.
- evaluator: `<LOCAL_PATH>`; SHA256 `ae4f1aa070717865ec58bdd86d1493eb7b54561ab524cbc4f215af0daec19ff0`.

## Independent decision

Conditional acceptance of v2 as one bounded, exposed-data **numerical reference / opportunity diagnostic**, contingent on the still-unreviewed driver, metadata-only dry-run and pre-execution freeze. This does not approve an innovative mechanism or G4 training, does not prove a globally exact IEEE/real optimum, and does not yield a remaining-opportunity upper bound on any unresolved map. No map execution is authorized by this review.

v2 corrects the earlier major interpretation risks: all 24 maps remain in the denominator; fixed-owner and joint-slot references are separate; saved ALNS is an archived anchor, not rerun or represented as a new fair comparison; missing lower bounds leave opportunity INCONCLUSIVE; allocation-cell bounds are no longer claimed as an OS RSS guarantee; 12/360 seconds are scheduling limits with real overruns explicitly charged; both cost reconciliation and regression have separate declared meanings.

## Static code findings

1. The recurrence is structurally appropriate under its declared additive numerical model: Held–Karp retains one shortest closed trip per subset; nonnegative common flight conversion and subset-additive service/energy make this sufficient in real arithmetic; partition DP removes trip-list permutation by a pivot; DABS checks both LD/SD duties on every complete target split, including empty/full. Fixed-owner mode uses the same union and restricts only the final slot masks. RETURN never resets cumulative duty. These are static observations, not a theorem about all production floating-point outcomes.
2. Tiny-test evidence binds matching DP/test/evaluator hashes and records 16 checks PASS, exit 0. The tiny brute enumerator actually enumerates set partitions, within-trip order, trip-list order and DABS ownership, then scores complete solutions only through the independent evaluator. Important boundary/resource/empty/invalid tests are present. This is useful engineering evidence but not an optimality or general failure-rate proof. No new tests were run for this report.
3. DP input/coverage/battery predicates are not literally the evaluator's IEEE predicates. DP coverage uses `sqrt` and `radius-distance>=-EPS`; evaluator coverage uses `hypot` and `distance<=radius+EPS`. DP battery uses `battery-energy>=-EPS`; evaluator uses `energy<=battery+EPS`. Duty uses the same comparison form but accumulation order can differ. Service/target-energy subset sums follow target-ID order, not necessarily the reconstructed visit order, and partition recursion can sum trip costs in a different order from evaluator traversal. Independent acceptance must check actual witness feasibility and preserve raw resource residuals; a small full-cost residual cannot establish all these predicates equivalent.
4. DP malformed fixed-owner inputs are checked after early returns for empty/closed target pools. Therefore an empty pool plus invalid owner mapping can currently return COMPLETE. Frozen valid parent-derived inputs should not encounter this case, but the driver must validate owner identity independently for every station, including empty/closed. Alternatively move owner validation earlier before freezing code. Do not claim the raw function validates every possible owner mapping.
5. The cell rule is an explicit structural budget, not a byte bound. The formula's treatment of outer Python list containers / tuple storage is not a precise peak-memory accounting model. Record its declared estimate plus traced peak and RSS honestly, catch allocation/error outcomes durably, and do not label it an exact or OS-level maximum. Given n<=12 and bounded reconstructions the finite recurrence is bounded, but driver output/parents/audits also consume memory outside that table estimate.

## Driver acceptance checklist (pending)

- Hash-check all frozen sources, all24 map bytes and every expected ALNS solution/meta/archive identity before map solving; preserve missing/mismatch rows and status rather than filtering. Dry-run must import/hash/read metadata only and must not call Greedy, evaluator or DP.
- Produce and preserve one complete Greedy parent/map, fixed/joint full-map candidates, every raw station numerical witness and every rejected witness, independent full-map audits and explicit parent-retaining partial incumbents. No silent min(parent,DP) repair presented as a reference.
- Check station types, per-station target unions and fixed slot owners from complete solutions. Compare Greedy-parent identities and old archive metadata without changing their exposed-data role.
- Start map and batch scheduling clocks at the declared boundary. Check prior to every station reference, continue serialization and validation while charging overruns, and save status for unattempted/size/bound/error/infeasible/numerical rows. Fixed then joint order is frozen. Do not reschedule late hard stations or rerun successes/failures.
- For completed reference replacements calculate expected full original cost from parent operating cost and DP scalar, then record raw evaluator reconciliation and raw parent regression separately. Use 1e-8 cost limits only in those declared roles. Save per-trip resource slacks and coverage/duty slack; near-boundary and accumulation-order discrepancies must stay explicit.
- FULL requires both whole-map references complete and validated. Partial-map fixed-minus-joint is mixed coverage, not causal slot reassignment. No unresolved station LB means map-wide headroom ceiling remains INCONCLUSIVE. Even FULL remains numerical-reference qualified.
- Relative effects use each actual comparator's COMPLETE original cost; all24 map units remain in summaries. Archived best-of3 is three historical runs, not one6s/12s result. Runtime provenance must be read from actual meta and not invented.
- Freeze driver/schema/commands/test/dry-run/reviews before the unique locked output directory is created. Implementation changes made before the freeze require refreshed unit evidence and reviewer identities; post-outcome changes cannot silently replace the one-run protocol.

## Questions for concrete exchange

Mechanism reviewer: please verify whether the driver performs literal resource checks and/or marks predicate boundary discrepancies unresolved. Does any remaining DP-to-evaluator discrepancy threaten the limited descriptive witness claim, as opposed to an exact-optimum claim that v2 already rejects?

Failure reviewer: please verify archive method/budget/seed/source/input and station-domain identities, parent-retaining partial behavior, all24 denominator, and that no fixed-owner-to-joint attribution is computed as pure reassignment on partial maps.

Root: provide final driver and metadata-only dry-run identities. Current acceptance remains conditional until these are reviewed; this review is not a training or execution authorization.
