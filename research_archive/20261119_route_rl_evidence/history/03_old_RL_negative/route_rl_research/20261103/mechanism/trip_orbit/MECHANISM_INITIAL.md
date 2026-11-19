# Independent mechanism initial: exact whole-trip-order score

Date: 2026-11-03. Role: `route_mechanism_g4`. I read `ROOT_TASK.md` SHA256 `20eb114237c0cb204edd75c9c94340177110a3afefbaa194bd7911eaa41937f4` and the frozen original evaluator/source contracts. This report is frozen before reading the other two agents' new trip-orbit initials or substantive findings. It is mathematical design only: no solver, map, evaluator, gradient fixture, training or new-instance generation was executed.

## Independent disposition

This is a **specified conditional-expectation estimator with a concrete subset-DAG implementation**, unlike the preceding unspecified trip-family encoder. Its score identity is correct under the explicit state, support, numerical and cap conditions below. It changes training credit and keeps physical next-target/RETURN inference actions. It supplies neither a new physical constraint nor a new optimization solver.

**Novelty is UNESTABLISHED, and G0/G4 are not passed.** Rao–Blackwellization, differentiating a marginal likelihood and symmetry-aware policy training are established principles. The particular use of disjoint whole-trip permutation blocks gives a tractable exponential dynamic program, which is more specific than generic augmentation, but an application of a standard subset-DAG/forward marginalization may still be the closest equivalence. The evidence agent must determine the actual nearest implemented estimator, rather than treating missing exact-title matches as novelty. Mathematical correctness would at most permit bounded G1 fixtures after root's review.

## Actor and physical environment contract

Fix station/type/target-to-station inputs and both eligible physical slots. The actor has **at most one nonempty open trip at a time**. At a closed-trip boundary, it chooses a legal `(slot,target)` to start a fresh trip. While a trip is open it chooses a legal next target for that same slot or `(slot,RETURN)`. After RETURN all slots are again at their home station; STOP is deterministic only when every target is served and no trip is open. Fresh empty returns are prohibited. No search operator, algorithm ID, budget, learned scheduling label or RL selection of an optimizer is introduced.

Every final collection of independent slot-tagged nonempty trips feasible in the original real additive model can be serialized by this actor. Permute and emit its trips one by one. Per-trip battery is preserved, and per-slot cumulative time at every prefix is no larger than its final nonnegative duty total. This is a statement about representable completed route collections, not equality of probability distributions or equivalence to a history-sensitive multi-open-slot policy.

At every state the actor inputs include remaining target identities/features, fixed station/type data, active slot and endpoint/open-trip route/resource state, and per-slot completed duty. The actor **does not** input the ordered history of closed trips, their serialization index/order, a recurrent hidden state, prior-action cache, trip-order-sensitive teacher state or dropout RNG state. A static encoder cache may be shared if it is a deterministic function of the instance. A dynamic cache must be a deterministic function of the declared canonical state. The ordinary feasibility mask depends only on that state. A lookahead mask is permitted only if it obeys exactly the same state function and is fully included in compute/accounting; an order-sensitive search history breaks the construction.

Training actor probabilities are computed deterministically for the same state/parameters: no independent dropout draw on alternative replays; no batch-normalization dependence on replay batching; no online parameter updates during an orbit sum. Sampling still uses those probabilities. The behavior distribution is the **current on-policy actor**; PPO reuse or off-policy teacher-forcing is not covered by the basic score derivation.

## Orbit definition and exact score

A completed sampled trajectory yields K nonempty blocks. Block `b_j` records its physical slot d_j, ordered target sequence `(i_1,...,i_m)` and explicit final RETURN. All target sets are disjoint and all targets occur exactly once. Distinct blocks therefore have unique identities; sort their tags/target tuples deterministically for DP indexing. Trip reversal, target-order changes, slot reassignment and cross-station assignment are outside this orbit.

Let C be this unordered collection of **slot-tagged ordered blocks**. For each block subset A, replay only its completed blocks into a closed boundary state `s_A` with remaining targets and canonical per-slot accumulated duty. Under the actor contract, `s_A` depends on A, not the sequence used to reach it. For an unchosen block j, let

    w_theta(j | A) = product over the physical actions of b_j
                       pi_theta(action | current deterministic replay state),

including the boundary slot/first-target probability, every extension probability and the RETURN probability. A truly deterministic final RETURN contributes probability1. STOP contributes1. If any action is masked, w is zero. This is the probability of a fixed block, not a decoder that selects a block as a macro action.

Define forward masses

    Z(empty) = 1
    Z(A union {j}) += Z(A) * w_theta(j | A), for j not in A.

Use differentiable log-sum-exp in implementation. `Z(C)=Z(all blocks)` is exactly the sum of the current actor probabilities of the K! block serializations in C. Unique disjoint blocks prevent duplicate counting. The actor does not receive the sampled future blocks at inference; they are retrospective training conditioning information.

For a theta-independent orbit map C(tau), differentiable current-policy support and positive class probability,

    grad log Z(C)
       = sum_{tau in C} [p_theta(tau)/Z(C)] * grad log p_theta(tau)
       = E_theta[grad log p_theta(tau) | C].

If terminal reward R(C) is identical for every member and a detached baseline b(x) depends only on the input instance, then

    g_RB = (R(C)-b(x)) * grad log Z(C)

is the conditional expectation of ordinary on-policy episodic REINFORCE. Consequently its expected gradient is unchanged and its covariance is weakly reduced in the positive-semidefinite sense; no strict variance or learning-speed improvement is guaranteed. K=1 gives the original estimator. A singleton policy-support orbit gives no reduction. A constant-reward or perfectly controlled case can also have no useful improvement.

The weighting is **policy posterior**, not uniform across permutations. Averaging all serialization scores uniformly is generally biased. A uniform sampled permutation of a teacher solution is not on-policy sampling. An orbit-dependent baseline does not become safe merely because it is shared across the orbit: subtracting b(C) gives `sum_C b(C)*grad P_theta(C)`, which is generally nonzero. A baseline may be a fixed instance-only prediction, or a separately justified control variate, but not an unproved action/orbit-dependent cost.

## Complexity and deterministic caps

For each j there are `2^(K-1)` subsets A excluding it. Let L_j be the physical action count of block j including RETURN and let C_actor(n) denote one actor/mask state evaluation including any recomputation. The straightforward exact construction costs

    2^(K-1) * sum_j L_j actor-action evaluations,
    O(K*2^K) scalar log-DP work,
    O(2^K) forward masses plus boundary/state storage,

and potentially `O(2^(K-1)*sum_j L_j)` retained autograd-state memory unless recomputation/checkpointing is specified. Reporting only O(K*2^K) hides the neural/block replay work. Batch processing can improve hardware utilization but does not remove these evaluations. Parameter gradients flow through every w and every log-sum; a detached posterior average over scores must still use correct current-theta weights to represent the same first derivative.

Freeze a **class-invariant** cap using K, n, all block lengths and deterministic predicted state/evaluation counts. For example: exact sum only if K<=K_cap and `2^(K-1)*sum L_j<=B_cap`; otherwise use the original sampled-trajectory score. This is still an unbiased conditional estimator in ideal arithmetic: define a partition whose small-class cells are the complete orbits and whose large-class cells are singleton trajectories. Class invariance is essential. An ordering-dependent local window is not a proved orbit partition. Selecting an orbit method based on the sampled order's likelihood, improvement or elapsed runtime has no such guarantee.

A wall-clock/memory exception is not automatically a valid unbiased fallback event. The implementation should prevent predictable oversize work by the deterministic cap. Unexpected failures are preserved and flagged as failures; if it falls back to raw scores on such events, it must not advertise an exact unbiased estimator without showing that the event and recovery rule are class-invariant. No global polynomial complexity is claimed.

## Critical numerical condition: original raw evaluator is not order invariant

The original evaluator sums trip minutes sequentially inside each slot, then slots/stations sequentially. IEEE addition can depend on within-slot trip order. The same final physical block collection can therefore have slightly different raw cost or duty acceptance across serializations even though its real objective is equal. Existing1e-7 feasibility/1e-8 residual conventions do not make these values bitwise identical, and a numerical tolerance alone is not a proof of exact conditional-expectation identity.

There are three valid ways to state the estimator's target; none should be silently substituted:

1. **Ideal real additive objective:** prove the estimator in real arithmetic and label a production floating implementation as an approximation, preserving all reward/mask discrepancies. This provides the clean mathematical reference but no bit-exact unbiasedness claim.
2. **Canonical numerical objective:** define a deterministic block sorting and canonical boundary-duty accumulation; score a canonical full solution through the original evaluator, so all trajectories in C map to the same actual terminal reward/status. Save raw chronological witnesses and canonical scored witnesses, check feasibility under both if claiming physical feasibility, and give every baseline the same canonical protocol. This changes the representation/rounding convention, not the real model, but must be explicit and pass differential tests. It cannot retroactively alter official benchmark scores or silently repair routes.
3. **Full numerical conditional gradient:** if raw rewards differ across orders, use the exact weighted quantity `sum_{tau in C} p(tau)*R(tau)*score(tau)/Z(C)` rather than `R(sample)*grad log Z(C)`. If rewards/masks require order-dependent partial sums, subset state merging may no longer hold; full path enumeration or an enlarged sufficient state is then needed. O(K*2^K) is not automatically retained.

The root proposal therefore needs a numerical target decision before fixtures. Option2 is implementable as an explicitly canonical route-output protocol, but no canonicalization has been implemented or approved in this report. The one-open state must also use canonical/reproducible resource calculations to ensure a true function s_A; simply hiding ordered history in actor inputs does not make order-sensitive floating duty sums disappear.

## Prior-art distinction and falsifiable tests

This differs operationally from merely sampling several POMO starts or averaging augmentation rewards: it analytically sums current-policy likelihood over all supported whole-trip block orders in a bounded class and differentiates that marginal. It remains an application of Rao–Blackwell/forward-DAG marginalization unless the versioned literature comparison shows a specific non-direct gap. A canonical serialization policy removes duplicate orders by changing construction support; that is a simple mandatory control and may match or exceed the benefit without exponential replay. GFlowNet/trajectory-marginal likelihood methods may be the closer technical comparator than routing augmentation titles.

If G0 source review permits bounded G1, exact independent tiny finite-state fixtures should check: raw expected REINFORCE gradient versus orbit gradient, posterior versus uniform weighting, zero support/K1, deterministic cap singleton fallback, history-sensitive counterexample, reward-order/mask failure, baseline dependence, and numerical log-sum stability. They must be finite synthetic MDPs or constructed route fixtures, not old-map performance experiments. A variance reduction on those fixtures is mathematical/engineering evidence, not stronger routing performance.

Only after source and correctness review would new-development G3/G4 become meaningful: matched total training compute ordinary REINFORCE, canonical serialization, POMO/Sym-NCO-style symmetry controls, BC/value controls and this estimator; same physical inference actions, accounting of orbit replay/backprop costs; at least3 independent training seeds and strongest station-joint non-RL under both frozen inference budgets. A lower per-sample gradient variance can lose at fixed compute. The original full-objective0.3%/CI/feasibility/overrun gates remain unchanged. No old-map rerun or claim of guaranteed improvement follows.

## Current conclusion

The exact rule has a correct conditional-score derivation under declared sufficient-state, on-policy, class-reward and class-invariant-cap assumptions. The raw evaluator/numerical contract is a real unresolved implementation choice. No proof of non-direct novelty, practical advantage, RL superiority or G0/G4 completion exists yet. Freeze this independent initial, exchange the numerical/cap objections, and obtain precise primary-source comparison before authorizing even the bounded fixtures.
