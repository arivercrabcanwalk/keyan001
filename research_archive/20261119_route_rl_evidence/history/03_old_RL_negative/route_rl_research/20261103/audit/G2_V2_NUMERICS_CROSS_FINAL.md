# Station G2 v2 numerical cross-review and conditional final

Date: 2026-11-03. Reviewer: `route_mechanism_g4`. This review follows my independently frozen initial and an actual exchange with `route_independent_audit` and `route_failure_audit`. It is a source/document review. I ran no additional DP, evaluator, map diagnostic, server job or training for this cross-review. The already authorized synthetic suite was run twice, as recorded below. Earlier reports and freezes remain unchanged.

## Reviewed identities and decision

- Protocol: `6dbfd7135c86fb80543fa8a0c9d1cc6f249fe81ad961d1a3bfcdf658b188e50e`.
- Station DP: `8f4d05da5d0a829b8d6ce0889a10e0f5e990a3e1687505b36e61b28eb1c8da06`.
- Driver inspected for this disposition: `869b10ae554343bf4a4b1de622aff9eeb3a9affe665c0c29209c51678f0661ea`.
- Station test source: `1ae12250b45d654c3d60f587b2edde4c908cc860d75c3fafb3c1b087e6eef87f`.
- Synthetic station-test receipt: `3c2c94f3b35f586741b13adad27eee0ad4686230de4da95f2d3d26fe0ba5056f`.
- Independent evaluator: `ae4f1aa070717865ec58bdd86d1493eb7b54561ab524cbc4f215af0daec19ff0`.

**Conditionally accept this bounded, exposed-data numerical-reference diagnostic.** Final driver tests and a fresh metadata-only freeze must bind the actual driver/protocol bytes before root's single execution. The existing dry-run `16eac6494ef18bd2ac028a15e811e736a57b6a2fac38674a633ef8f53591161d` binds older code and is not the final pre-execution evidence. This review provides no G0 novelty pass, G4 training admission, new-development result, fair-budget solver superiority, RL superiority, Formal evidence or paper-writing admission.

## Response to the independent numerical review

My frozen initial `G2_V2_NUMERICS_INITIAL.md` has SHA256 `64a56374fe2e69bd68406ae757dae788131fd2dab80a0ff69373d47086c65778`; it reviewed protocol e441/DP9b9. Its N1 and N2 objections were valid for those bytes. DP8f4 now checks literal evaluator-style coverage with `hypot > radius + EPS`, and battery with `trip_energy <= battery + EPS`. These two specific objections are resolved. The independent reviewer explicitly corrected its stale predicate wording without altering the frozen initial; I accept that correction and provenance chain.

Remaining accumulation differences are real: target service/energy subset recursion and partition association can differ from reconstructed evaluator order. Protocol6db explicitly freezes them and limits COMPLETE to a numerical recurrence plus independently validated witness. These differences do not invalidate every feasible witness, but they preclude upgrading this computation to a strict real/production-IEEE optimum or an opportunity ceiling. Actual feasibility, raw cost residual and raw regression remain separate acceptance checks. A 1e-8 cost agreement cannot establish energy/duty equivalence.

The existing station-test receipt records the exact command `python3 -m unittest discover -s route_rl_research/20261103/joint_route_env -p test_station_dp.py -v`. Both attempts used only deterministic synthetic fixtures, returned empty stdout, the full unittest report in stderr, `OK`, and exit status 0. The first ran 16 tests in 0.029s against DP9b9; the second ran 16 tests in 0.042s against DP8f4. Test and core identities were stable within both attempts. This is engineering evidence, not a performance or all-IEEE-input proof. I did not rerun it for this review.

The raw DP API validates malformed fixed-owner inputs after some empty-pool early returns. The driver derives valid owners from the frozen complete parent and separately checks complete solution domains on integration, including empty slots. Thus this caller does not rely on an unsupported claim that every possible malformed raw empty-pool request is rejected. Tests and claims should retain that distinction.

## Response to the failure audit and actual exchanged objection

I read `G2_DRIVER_INITIAL_FAILURE.md` and the independent reviewer's readable `G2_DRIVER_CROSS_RESPONSE_INDEPENDENT.md`. I sent concrete agreement and source-location objections to both peers and root. The following changes are present in driver869:

1. Rebuilt Greedy must equal the preserved canonical complete solution before station unions are derived, then pass independent feasibility and exact-once validation. The prior 144-cell archive identity audit supplies the frozen source/input linkage; it is not a substitute for the planned witness rescoring.
2. Each of six expected archive cells has a try/catch and remains an explicit unresolved row on a read/hash/evaluator/identity error. Meta and solution identities, stored status, task identity, schema, station types, union and fixed slot ownership are checked. Best-of-three requires all three valid cells and is labelled three historical runs, with historical costs retained.
3. Missing/nonfinite evaluator costs no longer participate in residual arithmetic in `validate_reference`. Ordinary rejected references retain their raw routes and full audit; independent domain and residual/regression failures prevent integration. A partial incumbent retains the parent's routes for rejected stations and is separately rescored.
4. The independent reviewer correctly found a narrower evidence loss in driverb8f: an evaluator audit could be returned, then lost by a later domain/cost exception before the record update. I independently accepted that objection and asked root to preserve the already obtained audit immediately. Driver869 now stores `record['complete_trial_audit']` and `result.raw_full_trial_audit` immediately after evaluation; the outer station exception records `raw_result` and `raw_trial_audit`. `StationResult` is a dataclass without slots, so this extra diagnostic attribute is supported. Archive rows similarly attach `independent_audit` immediately after evaluation. This fixes the identified retention gap without changing scientific samples, thresholds or recurrence.
5. Failure-agent synthetic driver tests, receipt binding and a refreshed metadata-only dry-run remain the final pre-execution engineering conditions. I did not duplicate those fake-object tests. Hashing a stale receipt alone would not satisfy this condition.

One robustness edge remains descriptive rather than an identified failure on the audited frozen data: best-of-three sums historical times after the per-cell catch, so malformed nonnumeric historical times could still raise outside the cell loop. The preserved archive audit already records the existing cells; if fake tests expose a real missing-time path, root should close it before freezing. No scientific result may be dropped to conceal such an exception.

## Deadlines, resources and interpretation

The driver checks the deadline before every reference, including empty or closed stations. A station reached after expiration is conservatively UNATTEMPTED, rather than being called COMPLETE without invoking the trivial reference. This does not create false completion, but the protocol's empty/closed COMPLETE sentence should be read conditionally on reaching that reference before scheduling expiration; an explicit wording clarification is preferable before freeze. A missing-trivial-status mismatch is not a reason to add work beyond the deadline or relabel it retrospectively.

State/transition caps are structural bounds. Tracemalloc and process RSS are observed high-water values; neither is a hard OS memory guarantee. The 12/360-second settings are scheduling limits; validation and durable output overruns are charged. No new formal memory or general IEEE proof is required to support the limited engineering claim, and none is established here.

All 24 map rows remain in descriptive accounting. Greedy-to-fixed, Greedy-to-joint, fixed-to-joint, and archived-ALNS-to-joint have different meanings. Fixed-to-joint supports numerical reassignment attribution only where both complete-map references are accepted. Partial differences have mixed solve coverage. Any witness-backed gain is realized gain from the chosen parent, not a bound on unresolved opportunity or attainable RL improvement. Full original evaluator cost and all failed/unresolved/negative records must be retained. Source changes after this review need a matching supplement and fresh final receipt; no post-outcome repair or rerun is endorsed.

## Final disposition

The specific numerical predicate and ordinary retention objections are resolved in the reviewed code. Final fake-driver evidence, actual source hashes and fresh metadata-only freeze remain pending root's engineering closure. Root owns the single historical diagnostic. New mechanism approval, strongest non-RL development comparison, genuinely cross-step route RL, at least three independent training seeds, frozen new Formal, innovation ablation and independent G8 acceptance remain distinct unpassed work.
