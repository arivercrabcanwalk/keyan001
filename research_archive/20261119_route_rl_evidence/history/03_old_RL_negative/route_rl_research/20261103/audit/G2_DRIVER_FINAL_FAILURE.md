# G2 driver cross-response and bounded engineering acceptance

Date: 2026-11-03. Reviewer: route_failure_audit. Initial driver review was frozen as G2_DRIVER_INITIAL_FAILURE.md (cbb384bfce62b2f6635540be0f06c944a8b52b0b556288b6c70154d32eafc7a3) before driver-review peer exchange. Later source fixes and synthetic-only tests are identified below. Initial/earlier files are unchanged.

## Reviewed final identities

- driver run_station_g2.py: 869b10ae554343bf4a4b1de622aff9eeb3a9affe665c0c29209c51678f0661ea.
- protocol: 6dbfd7135c86fb80543fa8a0c9d1cc6f249fe81ad961d1a3bfcdf658b188e50e.
- station DP: 8f4d05da5d0a829b8d6ce0889a10e0f5e990a3e1687505b36e61b28eb1c8da06.
- test_g2_driver.py: 5ad1d85ad3c9549b47da511ff96eb26d68e02e521da996e7c060db6625e72a4e.
- g2_transaction/DRIVER_TESTS.json: da109fd0b0d6412a9789aac8c6ee6c8f4109d58691841e1ba6141ce56c041c86.
- archived ALNS identity audit freeze: ../failure/G2_ALNS_REUSE_FREEZE.json, 3d41ab85c7dd14ef8d1fc23ff5ec8ea0cea3f3914a84908066f50dbb7b20d391.

## Response to peers and resolved objections

I read G2_DRIVER_CROSS_RESPONSE_INDEPENDENT.md and G2_V2_NUMERICS_CROSS_FINAL.md after the independent initials. I agree with their arithmetic boundary: literal coverage and battery fixes in station DP8f4 resolve the obsolete predicate wording; remaining summation association does not invalidate independently feasible witnesses, but precludes stronger IEEE/real optimum and opportunity-ceiling claims. No new all-IEEE proof or formal memory certificate is required to support this specifically qualified numerical reference.

Driver869 resolves my concrete initial objections:

1. Newly rebuilt Greedy must equal the complete canonical archived parent before station pools are derived; then it is independently evaluated and exact-once targets checked. Canonical saved parents derive from the separately verified 144 Greedy companions, all six cells/map semantically identical.
2. Every expected ALNS archive cell now has a try/catch. Missing/corrupt/exception cells remain rows, and a budget's best-of3 is disabled unless all three cells pass. Meta/solution/task/schema/input/source linkage and fixed station/slot domains are preserved. Best-of3 is explicitly three historical runs.
3. Missing/nonfinite evaluator cost is guarded in normal validate_reference rejection; raw result routes and independent trial audit remain. The independent reviewer's narrower “audit obtained then lost on later exception” objection is valid and resolved: driver869 attaches audit immediately to record/result, with raw_trial_audit and raw_result in outer exceptions. Archive rows likewise save independent_audit before subsequent validation operations.
4. Deadline is checked before every reference, including empty/closed pools. Reached-after-expiration rows are unattempted; they are not mislabeled complete. Overrun accounting is explicit scheduling rather than hard end-to-end time.
5. Fixed/joint full-map incumbents retain parent routes for unresolved station references and are re-evaluated completely. Full map requires both references accepted for every station. Partial fixed-minus-joint remains mixed coverage, not a pure slot-reassignment effect. All original costs/targets/stations remain in full-map denominators.

One limited robustness issue remains outside the audited frozen archive: malformed nonnumeric historical end_to_end_seconds can fail best-of3 summation after the per-cell catch. Existing 144 archived metadata values and preserved hashes are the supported data, not arbitrary future JSON. Do not claim the driver accepts every malformed historical field; if those inputs change, refresh engineering review rather than dropping a failed cell.

## Synthetic-only verification

Exact command:
python3 -m unittest discover -s route_rl_research/20261103/joint_route_env -p test_g2_driver.py -v

Latest captured result: stdout empty; stderr lists all nine tests as ok, “Ran 9 tests in 0.073s”, “OK”; exit status 0. Source hashes before/after match driver869, protocol6db and final test5ad. Receipt retains earlier attempts and explicit fixture-error corrections.

The nine tests use in-memory dummy instance/result, fake evaluator/build/solve_station and temporary archive files. They import driver module only; no real map, project evaluator, station DP or solver runs:
- missing/null-cost reference rejection preserves witness/audit;
- fixed-slot owner change rejected while fake evaluator feasible and station union unchanged;
- cost reconciliation failure is distinct from feasibility;
- missing archive keeps all six rows and disables affected best3;
- archive solution identity mismatch preserves raw meta/solution;
- archive null-cost evaluator rejection preserves audit/meta/solution;
- canonical parent mismatch blocks before solve;
- expired batch creates unattempted statuses with zero fake solve calls;
- partial joint result retains original parent full routes, valid incumbent and unresolved opportunity label.

These tests are engineering checks, not physical feasibility/performance or failure-rate evidence. The separate station-DP tiny exhaustive suite was run by the mechanism/root agent, not duplicated here. No real-map DP/evaluator, training, quality matrix, server task or Formal run was executed by this reviewer.

## Final bounded disposition

Accept driver869 plus protocol6db/DP8f4 for root's ONE frozen historical numerical-reference diagnostic, **conditional on a fresh metadata-only pre-execution freeze** that binds these exact sources, latest passed driver/station receipts, all input/source/archive identities, canonical parent file and the three-agent final reviews. A previous dry-run that binds older code is stale. Metadata includes DRIVER_TESTS.json by hash but does not itself assert latest_exit_status or driver-hash equality; root's final pre-execution verification must explicitly check both (they match in the identities above) before creating the unique run output directory.

This is engineering acceptance for the declared inputs, not generic parser validation or scientific gate completion. Every unresolved station/map remains; no certified LB/headroom ceiling is introduced. Greedy-to-joint is total route-domain gain, fixed-to-joint attribution requires complete references, archived ALNS-to-joint is historical opportunity with explicitly three-run best3. All-map summaries may include mixed-coverage descriptive differences only when so labelled.

G0 novelty, G3 strongest equal-budget development, G4 genuine route-RL superiority/three training seeds, new Formal, innovation ablation, paper drafting and G8 remain unpassed by this review. Root retains exclusive execution ownership. No scientific output has informed this disposition.
