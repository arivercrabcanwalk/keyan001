# Trip-family G0: failure-audit cross-response

2026-11-03. My FAILURE_INITIAL.md was frozen at SHA256 340e0daffa2fd3d2c5b8a79ddb9f9707a64ba5a27dbc5f4eb5222bfdbf0ed621 before reading the mechanism and independent trip-family initials. This response follows reading MECHANISM_INITIAL.md bb856b38e271a54d8f1125c618a9b9148e83615fca1ce1206763bc0970cef74f, INDEPENDENT_INITIAL.md 1de23941551655e1e4a1f0a82f8b40c37711ed5f5c6de6024b9ef47f3886a8c0 and INDEPENDENT_CROSS_RESPONSE.md. No additional solver/evaluator/DP/geometry/training/new map/quality run.

## Agreement with the exact reduction

I accept the mechanism author's endpoint-conditioned open continuation: L(x_d,Q,o), already spent open-trip energy/minutes, closed duty, and a possibly empty Q for RETURN. Static depot-rooted trip weights cannot simply be retained after taking a target action; the endpoint and spent energy changed. Fresh empty trips do not belong in the route sequence. A marked open-closure plus fresh-trip column exact cover is the correct standard residual object.

I independently agree that fixed start/end/subset has no nontrivial route-order energy/time Pareto front in this original common-speed additive model. Shortest length weakly improves both resources; subset selection/partition and prefix feasibility remain hard. Increasing Pareto route-order labels without a newly retained conflicting resource cannot be the claimed innovation.

The Bellman externality definition Delta(s,a)=c(s,a)+V*(s')-V*(s) is legitimate. It defines the desired action quantity but does not compute it cheaply or make it a new algorithm. Exact V* is residual DP/SP/lookahead; approximate neural V is a conventional value target until a specific non-direct update or estimator is provided. No G0 pass follows from the definition.

## Qualification from the independent reviewer: accept

A sparse witness family can maintain a **sufficient feasible-suffix invariant** for a restricted constructive policy without retaining every globally feasible next action. The invariant can be proved by carrying a complete suffix witness after each chosen action. This is different from claiming original-domain feasibility completeness. I accept the independent reviewer's distinction: one need not demand exact enumeration or a general IEEE-optimality proof for an ordinary restricted feasible policy.

At the same time a sampled family with no cover cannot certify the original problem infeasible. False exclusions may reduce attainable quality; representation/generation cost and restricted-domain identity must be reported. The simplest same-pool suffix-preserving greedy/beam/BC controller needs exactly the same witness information. A witness-maintenance guarantee alone is established constructive search practice, not automatically a new RL contribution.

I also accept the nearest-precedent distinction. Wang's inspected feature-similarity/soft-constraint groups should not be falsely described as exact LRPHSD flight-plus-service-energy ordered trips. That engineering difference is real relative to Wang's encoder, but standard RCSP/route-column/SP/DP is the closer equivalence test. PIP/LMask/DPDP mechanism inclusion stays UNKNOWN until equation/source-specific evidence exists; title overlap does not prove equality, missing evidence does not prove novelty.

## Failure-attribution consequences

The 11 complete maps' returned references establish numerical benefit from releasing fixed slot owners while reoptimizing the routes. The duty slack and trip-count association in FAILURE_EVIDENCE.json are descriptive, not a causal intervention. In particular:

- 28/29 DABS stations improve; 25 of those use fewer returned trips, three use the same number. This does not prove a pure trip-count-minimization objective, since shorter geometry can matter at the same count.
- All 29 returned joint DABS totals are below600 minutes, the largest158.8593. Consequently the SD-trip witness can be mathematically transferred to LD without increasing time/energy on those returned routes, subject to original numeric boundaries; a chosen mixed witness does not prove two vehicles necessary.
- This does not remove duty globally or infer the optimal representative of unresolved/new stations. Strong controls must nevertheless receive any correctly applicable LD dominance/standard trip-pool engineering.

A future experiment cannot attribute an old-domain gain to learned dual-slot duty competition solely because the action selects a slot. It should contrast packing/geometry information versus duty features, preserve original fixed fees, and compare a genuinely station-joint non-RL route/assignment optimizer. New training must not be justified by the approximately1.53% historical joint-DP versus narrower fixed-owner ALNS difference.

## Specific unresolved request to the mechanism author

Please provide one finite rule F, rather than another object name: its prefix-conditioned input, update after target/RETURN, explicit output fed to the actor, time/storage bound and approximation or invariant. Then name the closest non-neural or prior neural version of exactly F and the test that could refute the extra mechanism. If F is only a residual-cover scalar/dual price/count/attention feature with an actor-critic, state that plainly; it remains a baseline family with no identified increment.

Required experiments, only after F survives G0/G1: same-pool reduced-cost/greedy, beam/enumeration, BC/value and applicable bandit controls; strongest station-joint non-RL; same total construction/update/inference/validation wall-clock; three independent RL training seeds and matched training controls. The representation effect and genuinely cross-step RL effect must be separately testable. This is a comparison obligation, not a permission to run now.

## Disposition

**Agreement: generic H_s trip-family policy is NO_GO as the presently unspecified mechanism; no new complete F has been proposed.** The inquiry remains open to an actually specified non-direct algorithmic increment, not a theorem excluding every trip representation. No new quality, old-map repeated solve/cutoff expansion, G4 training or Formal follows from the current initials. Existing witnesses and failures remain reusable evidence; the next missing deliverable is an algorithm, not another numerical confirmation of the same old opportunity.
