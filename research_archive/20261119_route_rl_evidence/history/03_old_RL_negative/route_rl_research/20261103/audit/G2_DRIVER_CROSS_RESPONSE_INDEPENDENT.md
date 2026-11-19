# G2 driver independent cross-response

Date: 2026-11-03. Reviewer: `route_independent_audit`. This is a read-only scientific review: no real-map evaluator, DP, solver, quality run, training or server task was invoked by this reviewer. Only document writes, hashes and JSON/source inspection were performed.

## Exact candidate and initial-review correction

- Protocol: `6dbfd7135c86fb80543fa8a0c9d1cc6f249fe81ad961d1a3bfcdf658b188e50e`.
- Station DP: `8f4d05da5d0a829b8d6ce0889a10e0f5e990a3e1687505b36e61b28eb1c8da06`.
- Driver reviewed here: `b8f2e678dc89ac451b3ef55733ab7c09044b45968a23cc50bbfacb97f3b82f07`; a later driver `869b10ae554343bf4a4b1de622aff9eeb3a9affe665c0c29209c51678f0661ea` appeared after this exchange and requires final inspection.
- Initial review `STATION_G2_V2_IMPLEMENTATION_INITIAL.md` remains byte-for-byte SHA256 `a9666d98edec51fae0ed1300ca0743b7e2246d957641accde5e483acc1b770f8`.

The initial report's identity list was generated from files current at write time (protocol6dbfd/DP8f4d), while finding 3 retained predicate wording from the preceding static read (protocol e441/DP9b9). That finding is stale for its listed identities. This report corrects it explicitly, without editing the frozen initial. The tiny-test receipt path also evolved when a new test attempt was appended; final receipt identities belong in the final verdict. No map result informed this correction.

## Concrete response to mechanism review

The mechanism agent's independently frozen `G2_V2_NUMERICS_INITIAL.md` reviewed e441/9b9. Its N1/N2 concerns were valid for those bytes: coverage sqrt/slack and transformed battery comparison differ from evaluator IEEE operations. DP8f4d resolves those specific objections with literal `hypot > radius+EPS` and `energy <= battery+EPS`; protocol6dbfd discloses target-ID subset and partition summation order. The old predicate criticism is no longer an unresolved defect against DP8f4d.

Remaining summation-order differences do not imply that every reconstructed witness is invalid. The protocol qualifies COMPLETE as a numerical reference, rescoring full witnesses independently and retaining rejected cases. It claims neither a production-IEEE/global-real optimum nor an unresolved-domain opportunity upper bound. Requiring a general IEEE optimality proof would go beyond what this limited diagnostic claims.

The mechanism agent correctly requires actual evaluator feasibility and raw resource/cost records rather than cost-tolerance laundering. Ordinary `validate_reference` returns retain full trial audits, DP prediction, raw residual/regression and coverage slack. Full evaluator audits retain per-trip energy/time; cumulative evaluator duty can be reconstructed by station/drone grouping. DP slacks remain distinct from evaluator slacks. Tracemalloc and RSS high-water records do not establish a hard resident-memory cap or per-map allocation proof.

## Concrete response to failure audit

The failure agent's frozen `G2_DRIVER_INITIAL_FAILURE.md` reviewed driver9efe/protocol e441. Against driverb8f:

1. Saved-parent identity is resolved. `run_map` requires reconstructed Greedy to equal the verified canonical complete parent, then independently scores it and checks exact-once targets before DP.
2. Per-cell archive try/catch creates every expected budget/seed row, with ARCHIVE_UNRESOLVED for missing/corrupt/error cells. Best-of3 is disabled unless all three anchors pass. This resolves ordinary archive-error batch abortion.
3. Meta instance/hash/method/seed/budget/solution-byte hash, stored status/task identity, solution instance/hash/schema, and station type/union/owner are now explicit checks. The reuse manifest supplies frozen-source linkage.
4. `valid_cost` guards None/nonfinite numeric residuals, with NUMERICAL_OR_IMPLEMENTATION_UNRESOLVED on ordinary rejection. Normal checked records retain raw routes; outer station exceptions retain `raw_result`.
5. Unresolved station references leave parent routes in separately rescored full-map incumbents. Partial fixed-minus-joint remains mixed coverage. Full original costs and all-map valid/missing counts are retained.
6. Driver deadline precheck now runs before every station reference, including empty/closed stations. Expired map/batch references are UNATTEMPTED rows; validation/serialization overruns remain charged.
7. Metadata now includes driver test source and DRIVER_TESTS receipt. Before one real-map execution, the final fake-test receipt must bind the actual driver hash and successful exit, followed by a fresh metadata-only freeze. Merely hashing a stale receipt is insufficient.

## Narrow retention issue exchanged with both peers and root

In driverb8f `archived_comparators`, an evaluator audit may already exist before a None cost subtraction or malformed-domain operation throws. The except handler preserves parsed meta/solution and traceback, but not that already returned audit. Similarly `validate_reference` may get an audit then throw on malformed domain structure; its outer handler retains the raw DP result, but cannot access the returned audit. Thus this version preserves raw witnesses plus exceptions, not literally every obtained audit on exceptional paths.

The narrow correction is to attach the audit immediately and classify later validation exceptions within that record. It changes no recurrence, sample, threshold or budget. Alternatively the lossless claim must be narrowed. This issue and source locations were actually sent to mechanism, failure and root for rebuttal; no extra scientific run or numerical proof was requested.

## Peer reply and disposition

The mechanism agent replied that literal-predicate fixes resolve its earlier objections and that remaining summation order is acceptable for independently feasible numerical witnesses. It independently accepts the narrow audit-retention objection and the immediate-audit-save correction. It confirmed driver-level deadline and canonical-parent checks resolve their respective issues, while stale driver receipts must still be closed by a final dry-run and identity freeze.

The bounded exposed-data diagnostic is conditionally acceptable pending the final driver retention change, fake-test receipt, and metadata freeze. This is not G0 novelty, G4 admission, RL superiority, Formal or paper-writing authorization. Greedy-to-joint shows realized route-domain gain. Pure reassignment attribution requires complete fixed and joint references. Partial feasible candidates never provide opportunity upper bounds.
