# Independent initial: station split-DP G2 diagnostic protocol

Date: 2026-11-03. Agent: route_independent_audit. Independent protocol design from the frozen source, old-data identity manifest and previous accepted audit corrections. Prepared before reading new G2 draft(s) or exchanging this G2 position with the other agents. No solver, evaluator, DP, rollout, training or server job was run. This is a proposed acceptance contract, not root's execution authorization.

## Initial decision

A single bounded station-level diagnostic is justified because the old fixed-owner DP does not optimize the LD/SD partition of a station-owned target set. It can test added assignment headroom and numerical tractability in the already exposed old 24-map scope. It cannot pass G0 novelty, demonstrate RL necessity, establish new-development superiority or authorize G4. The protocol is not executable until root freezes input/algorithm/validation identities, concrete caps and output/state rules.

## 1. Scope and input identity

- Freeze all 24 `data_split.validation_maps` names/hashes from the Stage-A freeze, original parameters, frozen Greedy complete solutions and their hashes, fixed station types and each station-owned target set, plus evaluator/source hashes. Map seeds 7/8 are already exposed; retain that role.
- Include every station record: closed/empty, SABS and DABS, not just easy or LD-absorption-CERT stations. Known structural counts are 132 stations / 98 active and 82 DABS; these are a manifest-reconciliation check, not performance results. Recompute identity counts only when assembling the frozen manifest, before solving. A mismatch blocks the batch rather than silently changing scope.
- Same station/type/target-to-station assignment must hold in every candidate. LD/SD target ownership may change only within DABS. SABS has only physical SD at storage slot 1; empty slot routes are legal. Empty/closed station records remain in complete map arrays and original fixed cost.
- Old SA/RL/best-insertion routes are saved empirical anchors. Their station/target ownership must be checked against this input; no optimizer reruns are needed to reuse them. Missing/invalid anchor cells remain explicit, not silently dropped.

## 2. Exact reference and witness

For station-owned target set T, define shortest depot-closed tour length l(B) for each nonempty target subset B with ordered predecessor reconstruction. For slot d, a trip is energy-feasible exactly when `(l(B)/speed)*flight_energy + sum_energy(B) <= battery_d + EPS`; service is not flight energy. Its operating time is `tau(B)=l(B)/speed+sum_service(B)`. The common positive flight-energy coefficient and order-independent target energies imply that a minimum-length tour also minimizes trip energy for that subset.

Define `F_d(empty)=0` and `F_d(A)=min_{nonempty B subset A}[tau(B)+F_d(A\B)]` over energy-feasible B. Canonicalizing B to contain a fixed member of A avoids duplicate trip-order enumeration without changing the mathematical domain. Keep both tour and partition predecessors. Define `Q_d(A)=F_d(A)` if `F_d(A)<=H_mode+EPS`, otherwise infeasible. Costs and duty use the same operating minutes here; a scalar minimum suffices in this mathematical subproblem rather than an unnecessary cost/time Pareto frontier. When assigning a *different* subset A to a drone, initial fixed-owner feasibility is not inherited: test duty for every A.

DABS station value is `min_{A subset T}[Q_LD(A)+Q_SD(T\A)]`, including empty sets. SABS value is `Q_SD(T)`. **The DABS duty limit is the large-station duration for both physical slots**, as in the frozen evaluator; it is not small_duration for the SD just because that slot is SD. Coverage radius depends on station mode, not slot battery type. If initial pool is valid its coverage remains unchanged, but reconstruct/revalidate it.

Reconstruct ordered trips for every slot of every station and assemble the original complete solution format with original instance hash and station types. Re-evaluate the whole map independently; return a DP scalar alone is insufficient. Retain raw complete route witness, parents/derivation identity, each trip's energy/slack and each slot's duty/slack, objective decomposition and a deterministic tie-break rule.

## 3. Floating feasibility and correct status

Freeze the existing independent evaluator comparisons (`EPS=1e-7` for coverage, battery, cumulative duty), exact geometry implementation and accumulation order used by DP/reconstruction, and the separate numerical objective-agreement tolerance before seeing values. EPS is a feasibility allowance, not permission to round/merge cost labels. Do not silently increase tolerance or repair a returned witness.

If a nominally optimal reconstruction is rejected by the evaluator, keep the rejected candidate and explicit failure; it is not an accepted optimum. A stricter feasibility-domain DP gives a feasible reference but its optimum is not a lower bound for the full evaluator-admitted domain. Use an engineering numerical-optimal-reference label unless equivalent ideal-domain enumeration/bounds are adequately established; do not claim production-IEEE/real-arithmetic formal optimality from same-score validation alone.

The correctness phase must freeze an independent small-station exhaustive implementation that enumerates disjoint LD/SD assignment, all target permutations and all cut positions into nonempty closed trips. Choose small inputs by size/identity before costs, include empty/single-slot cases, SABS slot legality, per-trip battery boundary, cumulative duty across returns, both slots empty where legal, and DABS SD large-mode duty. This is a future G1 correctness requirement; no enumerator ran for this review.

## 4. Resource cap and unresolved policy

Root must choose exact numeric values before execution; this review does not infer runtimes from n. A reasonable *proposed bounded first-pass design*, subject to root's available-server memory/CPU freeze, is: one worker/thread, deterministic sorted map/station traversal, exact station DP attempted only for n<=16, at most 120 s wall time and 1 GiB additional working memory per attempted station, plus a fixed whole-batch cap. n>16 is retained as SIZE_CAP_UNATTEMPTED, not TIMEOUT and not solved. A checked matrix-size estimate must prevent allocation before memory cap. No adaptive second pass, changed n, seeds, timeout or beam sweep follows the first result. If root selects another cap it is a preregistered design choice, not a post-result rescue.

Every station has an initial independently valid complete route upper bound from the fixed complete anchor. Keep it if an attempt fails. Report status in {TRIVIAL_EMPTY, EXACT_REFERENCE_ACCEPTED, TIMEOUT_WITH_WITNESS, MEMORY_CAP_WITH_WITNESS, SIZE_CAP_UNATTEMPTED, NUMERICAL_UNRESOLVED, INVALID_WITNESS, INPUT_INVALID}; do not conflate timeout, initial route and optimality. Keep safe lower bounds for unresolved stations or state explicitly that no useful bound is known.

A valid station lower bound may relax battery/duty and use `sum_service(T)+max(MST({station} union T), 2*max_i dist(station,i))/speed` for nonempty T: the union of all closed station tours is connected and reaches every target; its total length is at least the MST and at least a round trip to every target. These are a maximum, not a sum. Bound implementation/numerical conservatism must be independently checked before treating it as certified; an incumbent or restricted-domain optimum is not a lower bound. A weaker nonnegative-flight bound is acceptable but may leave the decision unresolved.

Count input preparation, subset/tour generation, predecessor storage, search, bound computation, reconstruction, independent validation, failures and fallback. Record CPU and total wall seconds, peak memory, threads, hardware, software, code/input identities, termination reason, and durable checkpoints. This is an extended opportunity reference, not automatically a 6/12-second solver.

## 5. Full-map opportunity interval and decision

For each station retain `LB_s <= OPT_s <= UB_s`, with UB backed by a complete independently feasible route. Combining all stations and unchanged fixed costs gives `LB_m <= OPT_m <= UB_m` in the fixed-station joint domain. If a bound's validity is not established, the corresponding whole-map upper-headroom conclusion is unresolved. Do not delete the station or average only solved groups.

For saved baseline complete cost `B_{m,r,b}` at budget b and solver seed r, the remaining achievable improvement to the ideal joint-domain optimum satisfies:

`(B-UB_m)/B <= (B-OPT_m)/B <= (B-LB_m)/B`.

Use B as denominator, not UB/OPT, and retain negative raw lower differences; the anchor supplies a feasible fallback so a best-observed UB may also be reported. Freeze whether the common diagnostic UB uses the initial anchor only or the pooled saved witnesses, and label pooled solutions as an oracle/reference rather than a new same-budget solver. Never charge a best-of-three seed result as one 6-second run.

Compute the paired relative percentages within each map/seed/budget, average the declared solver seeds within each map, then average the 24 maps. Preserve all 24 map rows. Map bootstrap may describe variability in these exposed diagnostics; it is not confirmation/generalization. No n=station/task/transition pseudoreplication.

**Opportunity decisions:** (a) if the valid full-scope upper bound on mean gain is below 0.3% for an applicable budget, the unchanged double-budget 0.3% criterion cannot pass on this diagnostic set; label diagnostic NO_GO, not universal impossibility on new maps. (b) a verified feasible UB giving gain above 0.3% establishes observed opportunity on old maps, not RL superiority or G0; (c) if the interval straddles the threshold because of unresolved stations, label INCONCLUSIVE. The fraction of exact stations or median gap cannot replace the full-map bound. Do not use CI of an incumbent difference to manufacture an optimality bound.

To isolate newly released LD/SD ownership headroom from old route optimization, require the fixed-owner optimum/reference and joint-station optimum/reference separately. For genuine valid brackets `[L_fix,U_fix]` and `[L_joint,U_joint]`, the extra optimum difference is in `[L_fix-U_joint, U_fix-L_joint]`, intersected with nonnegativity from feasible-domain nesting. Old per-owner scalar references lacking complete witnesses may be descriptive only; do not attribute all baseline-to-joint improvement to slot reassignment.

## 6. Separate same-budget solver experiment

If G2 is later used as G3/G4 comparison, run a **separately frozen new-development** experiment with full map total 6s/12s, not per-station 6s/12s, and same initializer/inputs/hardware/info/validator. All initialization, model load convention, all station construction/DP generation, bounds, validation and fallback enter that timer. A 120-second-per-station oracle is not an equal-budget method. Any offline oracle information supplied to RL is supplied to same-information rules/beam/BC and strong non-RL with generation/query costs. Old 24-map diagnostic outputs remain exposed.

## Initial questions for actual cross-exchange

1. Failure audit: can you exhibit a valid LB for every unresolved station and preserve complete witness-backed UB? Confirm that failure/size cap is not replaced by exactness, that DABS SD duty uses H_large, and that an EPS-stricter restricted optimum is not a full-domain LB.
2. Mechanism: do you accept that only the *complete-map upper headroom bound*, not most-stations solved, can close this diagnostic scope? If big stations remain unresolved, does the result stay INCONCLUSIVE without expanding n/caps based on the first result?
3. Both: do you accept that baseline-to-joint improvement includes ordinary reordering/repacking and cannot be called LD/SD assignment gain without the fixed-owner reference; and that old diagnostic opportunity does not grant G0/G4 or fresh-development status?

## Current boundary

This review permits preparing/finalizing an auditable protocol, not execution. New mechanism approval, training, Formal, innovation/RL superiority, and paper permission remain false. Only root can freeze and schedule the one bounded diagnostic.
