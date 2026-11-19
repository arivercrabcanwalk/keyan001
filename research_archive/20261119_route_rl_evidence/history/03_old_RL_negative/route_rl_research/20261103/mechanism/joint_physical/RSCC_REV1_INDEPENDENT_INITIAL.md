# Independent Initial Review: RSCC Factorized Revision

Date: 2026-11-03. Reviewer: `route_independent_audit`. Reviewed identity: `G4_CANDIDATE_REV1.md`, SHA256 `af971cda15dbd9d77f1800dd24c7222dabcd51bb3a1cf62e47debebcfc16d76a`. Prepared before sending any response to the mechanism agent about REV1. No solver, evaluator, rollout, or training was run.

## Decision

REV1 fixes the original flat-pair baseline issue at the ordinary policy-gradient level **provided the implementation really factorizes the policy as** `pi_U(u|s) pi_D(d|s,u)` and applies each advantage only to its matching conditional score. The event/target score uses a state-only baseline; the conditional slot score uses a baseline averaged over eligible slots with the event held fixed. With exact `Q^pi(s,u,d)` values, these are valid score-function baselines.

The fix does not create a new algorithmic increment. The slot advantage is the standard COMA-style conditional counterfactual baseline, and the factorized physical pair action is the already-known heterogeneous vehicle/node policy grammar. The precise conclusion remains: same physical decision domain as old Stage B, corrected factorized-credit application as a new project experiment, but **G0 NO-GO as algorithmic novelty**. At most, a future authorized G4 could evaluate transfer/effectiveness; this review does not authorize it.

## Policy-gradient correctness and remaining implementation conditions

For reward defined as negative original route operating cost, let

`Q^pi(s,u,d) = E_pi[return | state s, event u, slot d forced]`.

Then `Qbar_U(s,u) = E_{d~pi_D}[Q^pi(s,u,d)]` is the correct event-conditional value, and `b_U(s)=E_{u~pi_U}Qbar_U(s,u)` is action-independent for the event score. Likewise `b_D(s,u)=E_{d~pi_D(.|s,u)} Q^pi(s,u,d)` is action-independent for the slot score conditional on `u`. The stated `A_U` / `A_D` signs and gradient-descent loss are consistent with maximizing negative cost. Sharing network parameters does not invalidate the conditional score decomposition.

The implementation must keep the factor log-probabilities and advantages separate. Applying `A_D(s,u,d)` to the event log-probability, or collapsing them into a full-pair advantage, reintroduces the dependency/bias problem. If PPO uses separate event and slot ratios with separate clipping, this is a factor-wise clipped surrogate, not the standard single joint-ratio PPO objective. It is a defensible design choice but must be named/frozen and compared under exact small-MDP expectations; per-head clipping, advantage normalization and shared parameters should be covered in the G1 test. A small-MDP gradient check should verify the unclipped gradient exactly and separately characterize clipping behavior.

## Counterfactual Q identification gap

The revision says action values may be fit from on-policy completed returns, but the trajectory only realizes the sampled `(u,d)` pair. The unchosen eligible slot's same-prefix `Q^pi(s,u,d')` is not an observed on-policy return. A critic can predict it from generalization, but that is an estimate with possible extrapolation error; it must not be described as an observed counterfactual or exact baseline. Require a clear distinction between:

1. a learned action-value critic trained on sampled actions, with state/action support diagnostics and counterfactual calibration against held-out forced-action rollouts; and
2. paired branches that clone the exact prefix, force each eligible slot, then continue with the same frozen policy. This directly estimates the declared `Q^pi` but adds branch samples and compute. Common-random-number coupling can reduce variance but does not erase its cost.

If a random continuation is used instead of the frozen current policy, the estimator is `Q^{random continuation}`, not `Q^pi`; using it as the RSCC advantage changes the estimand and needs its own learning/control justification. Freeze one estimator/continuation; do not mix labels from these estimands silently.

## Novelty and relationship to prior work

- **COMA:** the conditional slot term `Q(s,u,d)-sum_d' pi_D(d'|s,u)Q(s,u,d')` has the same counterfactual-baseline structure as COMA's per-agent advantage, holding the other action context fixed while marginalizing the selected component. See the primary [Foerster et al., Counterfactual Multi-Agent Policy Gradients](https://arxiv.org/abs/1705.08926). Here `u` is the fixed event/target context and `d` is the slot component. A one-central-policy autoregressive application is not identical to COMA's original decentralized multi-agent architecture, but the credit formula is a direct conditional adaptation, not an irreducible new credit rule.
- **Li HCVRP:** the vehicle/node pair action and sequential two-head decoder directly establish the heterogeneous slot/target construction pattern. Reordering factors to event-then-slot rather than vehicle-then-node does not add a physical domain or learning principle.
- **Old Stage B:** it already specified joint SD/LD state and selecting which drone to advance with next target or RETURN. RSCC adds a particular training baseline not stated there, so it is not literally the same complete method; it remains a method already represented by old project scope plus a generic credit-assignment component.
- **Other domain details:** energy, battery, station coverage and cumulative duty are real LRPHSD constraints but do not make the generic counterfactual formula algorithmically distinct without a new rule exploiting them beyond masking and action-value inputs.

## Causal effect and fair comparison

If separately randomized/matched RSCC and factorized PPO runs differ only in the conditional slot-credit signal, a paired map/seed evaluation can estimate the effect of that estimator in this task. To attribute the effect to credit rather than critic capacity, compare against the **same factorized actor and same centralized action-value critic/head, trained on the same data**, but using standard GAE/ordinary advantage; otherwise additional action-value modeling is a confound. Keep the event advantage/control identical and change only the slot component. If branch rollouts or extra returns supervise RSCC, provide an equal-information transition control and count the cost.

Against non-RL methods, equal-budget win/loss is evidence of relative practical utility, not an isolated causal effect of RSCC. To claim the credit mechanism itself caused the utility, the controlled PPO ablation must pass and counterfactual slot-value predictions must be validated. Include the strongest station assignment-and-route methods and the existing full-objective map gates; do not infer superiority from only a PPO comparison.

## Single-random-rollout control

A one-completion-per-slot control is useful if RSCC obtains branched returns. Freeze it as: clone state `s`, force the same event `u` with each eligible slot, follow a specified continuation policy, validate full completion, and record each branch cost. A non-RL controller selecting the lowest sampled completion cost is a required control when those samples are exposed to RSCC. It can be budget-matched, but one sample is noisy and does not replace a strong greedy/beam/DP/assignment-route baseline.

Match both candidate/branch count and all generated transitions. Report (a) equal environment-transition counts and (b) equal total wall-clock/compute if both cannot be made equal in one comparison. Include model inference, cloning, evaluator calls, failed completions and retries. If RSCC instead uses critic extrapolations and does not branch at runtime, do not impute branch-rollout costs to it; still use forced-action rollouts as a bounded audit for critic calibration, and do not let those audit labels leak asymmetrically into training.

## Final status for REV1

The corrected conditional gradient is mathematically plausible and testable under the factorization above. The unresolved Q counterfactual-estimation protocol prevents implementation freeze. The design remains a direct COMA-style adaptation of known factorized heterogeneous routing, not a newly identified G0 mechanism. No training should start under a claim of algorithmic novelty. A G4 transfer experiment would require a separate root decision after G2/G3 and exact estimator/compute controls are frozen.
