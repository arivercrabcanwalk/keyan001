# Trip-order orbit score: independent adversarial initial

2026-11-03. Reviewer: route_independent_audit. This report is written before reading any peer trip-orbit initial. Input: `ROOT_TASK.md` and the retained original additive routing/state definitions. No DP, evaluator, solver, training, new maps, quality experiment or server task executed. The mathematics below is derived independently; bibliographic originality remains a separate primary-source inquiry.

## Initial decision

**CONDITIONALLY VALID EXACT MARGINAL-SCORE ESTIMATOR; NOT A NOVELTY OR EFFECT PASS.** The stated whole-trip orbit is a genuine equivalence class of completed route serializations in the real additive, no-synchronization model. Under a canonical history-free actor and complete orbit probabilities, the subset recurrence computes that class likelihood, and its score is the exact conditional expectation of the on-policy trajectory score. The law of total covariance gives a per-sample covariance reduction. This is a specific finite estimator suitable for a small correctness fixture, rather than the previously unspecified hypergraph object. It is also standard marginal likelihood/Rao–Blackwellization applied to a route symmetry until a precise non-direct increment is established. It licenses no quality or training run by itself.

## Probability space and exact derivation

Fix an instance x and actor parameters theta. A trajectory tau is a complete sequence of physical `(slot,target)/(slot,RETURN)` actions under the proposed one-open-trip actor; probabilities include their full original action-softmax normalizers. Let C(tau) be the unordered collection of its nonempty, slot-tagged, internally ordered trip blocks. Disjoint served-target sets make the blocks distinct. The map tau -> C is independent of theta. Do not add trip reversal, SD/LD reassignment, empty trips or changed internal orders to this class.

For a successful class C with K blocks, each permutation is one action trajectory. At a closed boundary A, let s_A contain precisely the unserved targets and canonical sum of completed minutes on each physical slot, plus fixed instance data; no path-dependent hidden state is allowed. For j outside A,

    w(j|A) = product over every physical action in block j,
             pi_theta(action | its exact state after A and block-j prefix).

Masked actions have probability zero. Every legal alternative remains in the actor normalizer, including physical actions that would lead to a different class; do not renormalize over only the sampled K blocks. Teacher forcing is only a way to query these original probabilities.

    F(empty)=1,
    F(B)=sum_{j in B} F(B minus {j}) * w(j|B minus {j}),
    Z_C=F(all).

This is an exact sum over serializations if s_A is order-independent. A masked permutation contributes zero, not a replacement route. A sampled class has Z_C>0 at the sampling parameters. For differentiable fixed support,

    grad log Z_C
      = sum_{tau in C} [p_theta(tau)/Z_C] grad log p_theta(tau)
      = E_theta[grad log p_theta(tau) | C].

Let R_C be the common terminal reward and b(x) an instance-only baseline detached from the actor score. Conditional expectation of ordinary REINFORCE is

    G_RB(C)=(R_C-b(x))*grad log Z_C = E[G_raw(tau)|C].

On-policy sampling of classes by sampling tau, and retaining all outcomes, therefore gives the same expected policy gradient. Cov(G_raw)-Cov(G_RB) is positive semidefinite by total covariance, for each fixed instance and current parameter value. This is not a claim of lower error per second, better optimization with Adam/PPO, a winning solution or lower total training cost. Gradient clipping, adaptive optimization, minibatch normalization and biased practical estimators change the inference one may draw from this identity.

Failures must remain in the probability space. They may keep the ordinary score, using singleton classes for each failed trajectory. Dropping failures, resampling until success or conditioning the minibatch on completed solutions changes the training distribution and generally biases the original objective. A finite failure reward and its original penalty semantics must be specified.

## Complexity and an exact occupancy-gradient implementation

There are K*2^(K-1) block-probability edges, not K! full paths. If block j has l_j target visits plus RETURN, the direct physical-action evaluations total

    2^(K-1) * sum_j(l_j+1) = (N+K)*2^(K-1),

before counting each network/encoder/mask forward's own cost. Both boundary construction and within-block state/mask costs count. DP scalar storage is O(2^K); storing every neural forward activation may be far larger and must not be advertised as O(2^K) total memory. This remains exponential in K.

An exact two-pass alternative computes backward B(A), B(all)=1, and edge posterior

    q(A,j)=F(A)*w(j|A)*B(A union {j})/Z_C.

Then grad log Z_C=sum_{A,j} q(A,j)*grad log w(j|A). A recomputed gradient surrogate `sum stop_gradient(q)*log w` has this exact local gradient; differentiating through q in that surrogate adds unwanted terms. Direct differentiable log-sum DP is also valid. This is ordinary forward/backward marginal-score machinery, not a separate novelty claim. Log-domain evaluation is required for numerical robustness; an underflowed zero Z is an engineering failure, not evidence of zero mathematical support.

## Explicit counterexamples to tempting replacements

**Uniform rather than conditional averaging.** Consider three trajectories with probabilities p1=theta, p2=theta^2, p3=1-theta-theta^2 for an open interval where these are positive. Class C={1,2} has reward1; class D={3} has reward0. J=theta+theta^2, so J'=1+2theta. At theta=1/5, Z_C=6/25 and its score is35/6. The true expected gradient is7/5. Uniformly averaging the two class scores5 and10 gives15/2 and an expected gradient9/5, not7/5. Conditional weights must be5/6 and1/6.

**Canonical teacher forcing after unconstrained sampling.** In the same example, always using canonical trajectory1's score5 after observing class C gives expected gradient6/5 rather than7/5. Canonicalization of final route storage/reward can be harmless, but replacing the sampled score by the canonical path score is not this unbiased estimator. A genuinely canonical-generation policy changes its trajectory distribution/domain; it is a valid separate control only with its own defined normalized policy. If the canonical likelihood happens to equal class likelihood times a theta-independent factor, scores coincide, but that is an additional property, not generally true.

**Off-policy teacher forcing.** Class C sampled at theta_old=1/5 has mass6/25. At theta=3/10, its current mass is39/100 and current class score160/39. Applying that current score unweighted to old samples has mean64/65, while the current J'=8/5. On-policy sampling at the current parameter or a correct class-level importance weight is required. Multiple epochs reusing a batch are not automatically unbiased REINFORCE; a frozen-data PPO-like surrogate needs a separate derivation and must not inherit the raw variance theorem. Teacher solutions from a route optimizer are likewise not on-policy samples.

**Action/class-dependent baseline.** A detached baseline b(C)=R_C is constant within each orbit but makes the displayed gradient zero, although J'=7/5 above. Thus detached or orbit-constant is not sufficient. The stated instance-only b(x) is safe. A state-dependent/per-step baseline requires conditional expectation of its full score terms, or another correctly derived control variate; it cannot simply be pulled outside the class score. A reward-average baseline containing the same sample also needs its own correction.

## State, masks, floating arithmetic and replay

One-open-trip serialization represents every final slot-tagged independent-trip collection in real arithmetic: battery is per trip, and nonnegative duty makes every partial sum no greater than the final feasible total. It does not imply equality to the old interleaved actor's trajectory distribution. The inference action domain/serialization restriction is part of the method and must be given to controls.

History-free is a mathematical condition, not a label. A recurrent decoder can remember whether block a preceded block b; both orders then have the same subset A but different hidden state and subsequent probabilities. Such states cannot merge in this DP without incorporating the relevant hidden state or explicitly integrating histories. Route-history embeddings, history-keyed caches, tabu/no-good state or order-dependent beam context create the same issue. A lookahead mask that is a deterministic function of the canonical Markov state does NOT inherently break merging; a history-dependent or approximate cache-based mask can.

Stateful dropout or per-query stochastic network noise makes independently re-queried w values differ from the sampled policy's probabilities. Either use deterministic policy forwards, or define an explicit latent random object and conditional policy consistently at sampling and every orbit query. An unbiased estimate of Z does not make grad log of that random estimate unbiased.

Floating addition is not associative. Whole-trip order may change accumulated duty, masks, probabilities and reward by rounding; a rounded mask at a boundary can change support. The implementation must use one canonical class-invariant sum/reconstruction rule for boundary state and reward, or document a bounded numerical approximation rather than assert exact RB for the original replay. Canonical state must be used during initial sampling as well as DP teacher forcing. Different internal summation from a stored environment state invalidates an exact likelihood assertion even if costs later agree within tolerance. Fixed canonical trip IDs/order, stable sums and explicit tolerances are suitable engineering choices, but small test agreement is not an all-IEEE theorem.

Interleaved open slots break the proposed boundary-state reduction and are explicitly excluded. If multiple stations are placed in a single class, station tags and the actual station-selection action probabilities must also be defined; a per-station orbit estimator with fixed station scheduling avoids accidentally omitting those factors.

## Caps, support and partition requirements

K=1 gives the original score; an empty completed task has K=0, Z=1 and zero score. Empty RETURN loops and duplicate block paths are excluded. A class sampled on-policy has positive Z; changing theta, masks or a checkpoint before rescoring can violate that guarantee.

A deterministic cap such as K<=K_max is class-invariant. Applying RB on accepted classes and raw score on rejected trajectories is unbiased, because it conditions on a refined fixed partition of the complete trajectory space. Accepted-class computation must include the whole declared class, including every zero-probability permutation and every probability denominator. DP enumeration order must be deterministic from class content, not the sampled serialization.

A sampled-order window, first-m-block subset, order-dependent timeout or data-dependent failure rule is not automatically a partition: overlapping sets can condition different samples on different events. Mixing raw and conditional scores under such a rule can be biased. A partial-orbit scheme could be valid if a fixed equivalence relation/partition is fully defined and the sampled trajectory lies in its own cell; that needs proof, not informal augmentation. Numerical failure fallback should be deterministic for the class, otherwise call it an approximate estimator and measure its bias. A conservative class-invariant K cap plus raw fallback is the simplest initial fixture semantics.

## Fixture criteria and current judgment

The root small fixture should enumerate all valid physical serializations for a tiny completed set, compare direct sum with subset-DP logZ and gradients, compare forward/backward edge occupancy, and verify the correct conditional weights rather than uniform averaging. Include a zero-support order, K=0/1, class-invariant cap/raw fallback, an intentionally history-dependent counterexample and the explicit three-trajectory counterexamples above. Use analytic derivatives or independent finite differences to avoid testing a recurrence only against itself. Report actual commands/outputs/status without converting the fixture into a map-performance experiment.

The evidence agent must compare standard latent-trajectory marginal likelihood, Rao–Blackwell policy-gradient estimators, routing symmetry methods and canonicalization. The subset DP is a real explicit algorithmic proposal and a worthwhile bounded correctness inquiry; valid algebra and an exponential-to-factorial summation saving do not by themselves demonstrate publishable originality over that literature. Current recommendation: allow only the already requested bounded correctness fixture under these stated semantics; G0 novelty/effect, G4 and Formal remain unpassed.
