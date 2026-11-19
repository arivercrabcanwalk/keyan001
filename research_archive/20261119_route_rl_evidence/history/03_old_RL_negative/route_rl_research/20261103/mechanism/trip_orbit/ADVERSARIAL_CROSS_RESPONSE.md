# Trip-order score: adversarial cross-response

2026-11-03. My `ADVERSARIAL_INITIAL.md` was frozen at SHA256 `5e0801ed8666ecb8c9c032de9913cad37549d7ba3f6571a3d88031419e5f5ca6` before reading `MECHANISM_INITIAL.md`, frozen at `acffb4a25ec0aa4593123ef170aebbbd4af03976ff5f2338efa225e032401bf1`. This response records the actual independent mathematical exchange. The separate `WINDOW_ADVERSARIAL_RESPONSE.md` audits root's later fixed-window supplement. No scientific execution occurred.

## Accepted points

I accept the author's derivation of current-policy posterior-weighted class score, its instance-only baseline condition, the explicit one-open-trip actor restriction, the need to count every physical action in each block query and retained autograd memory, and the distinction between per-sample covariance and fixed-compute training performance. The simple canonical-generation policy remains a mandatory comparator; it changes the sampled policy and cannot be substituted for the orbit likelihood score after unconstrained sampling.

The author correctly identifies raw evaluator order sensitivity as an unresolved production numerical choice. A tolerance does not make different chronological rewards identical. The complete policy-gradient identity needs the sampling policy's states/support and class reward invariance, not only a final pair of near-equal route costs.

## Numerical contract: avoid an unnecessary fixture blocker

I agree that root must explicitly choose the production target before any claim of exact production Rao–Blackwellization. I do **not** require a production evaluator redesign before a finite synthetic correctness fixture. A declared synthetic finite MDP with exactly class-invariant rewards and deterministic boundary states can verify the estimator algebra, counterexamples, caps and log-sum implementation now; its report must say it has not integrated the original route evaluator or proved routing performance. Such a fixture is a falsification tool rather than a G0 novelty or production G1 pass.

For a later physical environment integration, canonical states and canonical final route output can define an explicit deterministic representation of the same real route collection. Sampling and orbit queries must both use that state convention, and the independent original evaluator must check the actual canonical full solution. Store chronological and canonical witnesses, raw costs/status and any boundary discrepancies; do not silently change original benchmark scoring, relax constraints or delete failures. Giving all controls the same output canonicalization is required for a fair protocol. Alternatively, report a numerical approximation to the ideal real estimator without an exact unbiasedness claim. The third full reward-weighted conditional-gradient option may require an expanded state/factorization and cannot simply inherit the small subset DP complexity.

## Fixed-window supplement answers the cap issue

Root's `WINDOW_PARTITION_SUPPLEMENT.md` is a genuine deterministic statistic: an ordered list of unordered sets of c consecutive trip blocks. Every sampled successful trajectory belongs to exactly one such cell; internal permutations stay in it, cross-window moves leave it. Given canonical boundary state, earlier windows' internal orders do not affect the next window start. Hence cell likelihood is the product of window Z values and scores add. This is exact conditional expectation for that partition, not the full orbit when K>c. It is valid independently of whether c divides K. Failure trajectories remain singleton cells.

The initial's warning about an **ordering-dependent arbitrary local peer window** is valid, but should not be read as excluding this formally defined partition. c=1 is the original score; full-orbit K is the coarsest successful cell. General c=2 and c=3 partitions are not nested, so variance need not improve monotonically with c. Freeze c before sampling and include its full replay/backprop compute.

## Additional implementation and estimator points

1. A block query must preserve full original physical-action normalizers. Renormalizing among only the fixed future trip blocks computes a different policy. Deterministic STOP or final RETURN contributes probability1 only if it is actually deterministic in the sampling actor.
2. All unsuccessful samples remain. Keeping only completed route classes is success conditioning and generally changes the original training objective. Ordinary scores on failure identity cells are sufficient for the refined-partition argument.
3. In a two-pass forward/backward implementation, use posterior edge occupancies as detached coefficients of logw; differentiating through those coefficients in that surrogate does not give the desired first derivative. A fully differentiable log-sum DP is an alternative.
4. A Markov lookahead mask is compatible; a history-dependent lookup or RNG/dropout state is not. Fixed masks give differentiable support in theta. Parameter-dependent hard support needs its own boundary treatment.
5. A zero-support branch is allowed. A class sampled under the exact current policy has positive total mass; an underflowed zero or mismatch under replay is an engineering failure to retain, not a reason to resample a more convenient example. An unexpected class-dependent numerical fallback may preserve a refined partition only if its invariant event is established.

## Questions to author and evidence role

The mechanism author should confirm: finite synthetic fixtures can proceed under explicitly synthetic invariant-state/reward semantics; the fixed-window construction is accepted as a partition; full original normalizers and failure identity cells are included; production canonicalization remains a later separate correctness decision.

The evidence role should distinguish exact posterior-weighted marginal likelihood from uniform symmetry augmentation/POMO. Demonstrating that augmentation exists is not proof of equivalence to this score. Conversely, routing application specificity and failure to find an identical title do not establish novelty over generic latent-trajectory marginal likelihood/Rao–Blackwell or subset-DAG algorithms. Use the closest exact method and preserve UNKNOWN accurately.

## Current disposition

Allow only root's bounded synthetic estimator fixture with an explicit target and independent oracle. Equations and a passing fixture cannot establish originality, route solution quality or an RL advantage. New-development G3/G4, three-seed training, strongest station-joint non-RL, full-cost dual-budget evaluation and later Formal remain separate gates. This cross-response rejects neither all future physical-route learning nor all symmetry estimators; it narrows the actual claim to a specific, testable conditional estimator.
