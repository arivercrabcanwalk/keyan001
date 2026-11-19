# Independent Initial Review: RSCC Candidate

Date: 2026-11-03. Reviewer: `route_independent_audit`. Reviewed candidate identity: `G4_CANDIDATE.md`, SHA256 `35a6fcf61be38a0ad09bb5ed8b74d86793f794947693036a6db97ac955e5d574`. This initial review was prepared before reading any revised candidate or exchanging these points with the mechanism agent. No solver, evaluator, rollout, or training was run.

## Decision

The physical action scope remains valid and consistent with the user's direction. The `(slot,target/RETURN)` action domain is already the old Stage-B decision domain and overlaps the Li heterogeneous vehicle/node policy grammar. RSCC adds a counterfactual credit estimator not stated in that old Stage-B design, so the entire proposal is not literally identical to Stage B. However, its defining equation is the standard COMA-style counterfactual action baseline specialized to the slot choice while holding the target/event fixed. The domain adaptation does not identify an irreducible algorithmic increment or pass G0 novelty.

**G0 decision: NO-GO as a novelty-bearing method, pending no contrary primary-source evidence.** A controlled experiment might test whether this known credit assignment is useful on the task; that would be empirical transfer/application evidence, not by itself a new algorithm. G4 training is not approved by this review.

## Formula correspondence and policy-gradient issue

The frozen proposal defines, for a selected target `i`,

`b(s,i) = sum_d w_d(s,i) Q(s,(d,i))`,

`A(s,(d,i)) = -Q(s,(d,i)) + b(s,i)`,

where weights are the policy's probabilities over feasible slots for that target. This is the usual counterfactual baseline pattern: hold the event/target fixed, replace the slot component by each feasible alternative, and subtract their policy-weighted value from the selected slot value. It is COMA-style conditional action credit, applied to a route-slot choice. The method is not distinguished from that generic baseline by using route cost or drone constraints.

There is also an implementation correctness issue. The candidate says that a unique centralized policy selects the full pair `(d,i)`, while the baseline depends on `i`, which is part of the sampled pair. For a flat joint categorical policy, this is not an action-independent baseline: subtracting `b(s,i)` from the full pair advantage generally biases the policy-gradient term for choosing `i`. It is valid for the conditional slot factor only if the policy is explicitly factorized, for example `pi(i|s) pi(d|s,i)`, and `b(s,i)` is used only in the conditional slot log-probability update. The target/event-selection score needs a state-only baseline or its own unbiased estimator. PPO clipping and advantage normalization must also respect this factorization. The frozen candidate does not yet make this actor/gradient contract explicit.

The value target for unchosen slot alternatives is underspecified. A critic trained only on executed pairs does not observe realized returns for the unchosen `(d',i)` action; its estimate is model generalization/extrapolation, not an observed counterfactual. To make a rollout-based Q target, the protocol must specify: force the alternative slot at the same prefix, what continuation policy generates the rest of the route, how many rollouts/seeds are used, whether common random numbers are paired, how target uncertainty enters training, and all branch-transition costs. A random continuation and the current-policy continuation estimate different Q functions and cannot be interchanged without changing the estimand.

## Relationship to Stage B and prior methods

- The route action domain is the same as the documented old Stage B: jointly expose DABS state and choose which drone slot to advance with a next target or RETURN under battery and duty constraints. Reversing the factorization order (event then slot versus slot then node) changes parameterization, not the physical problem or action set.
- Li HCVRP uses a vehicle/node pair action and two-stage vehicle/node decoding. This is direct overlap in the pair-action grammar; LRPHSD's energy, station, and cumulative-duty constraints are problem distinctions, not an algorithmic increment.
- RSCC's added formula is a conditional COMA-style counterfactual baseline. That addition is distinct from the old Stage-B draft but is a known generic credit-assignment form. No paper-specific non-reducible rule is identified.
- Thus the precise conclusion is: **same decision domain as Stage B; new-to-this-project training component; not an identified new algorithm.** Do not collapse those three statements into “identical proposal” or “novel contribution.”

## What can be causally identified

A well-controlled RSCC-vs-standard-PPO comparison could estimate the effect of replacing the ordinary advantage signal with conditional slot-counterfactual credit, provided actor factorization, action mask, network capacity, critic data/targets, optimizer, training data, checkpoint rule and all other components are fixed. All trained seeds must be retained. A matched ablation must include the same critic/extra action-value head with ordinary GAE; otherwise the effect is confounded by extra critic capacity or supervision. If counterfactual branch rollouts train `Q`, a standard-PPO control that receives equivalent transition data/information, plus a rollout-based non-RL action-selection control, is required to separate the estimator from extra interaction budget.

Comparison with a strong non-RL assignment-and-route method can establish relative practical performance under the declared resource budget, but it does not alone establish that RSCC caused the gain. A causal mechanism claim additionally requires a component ablation and evidence that gains occur in the predeclared multiple-feasible-slot decisions, without using post-hoc subgroup selection as the main result.

## Single-step random-rollout control

A one-completion rollout for each feasible slot alternative can be a **budget-matched control**, not a sufficient strongest baseline by itself. It is fair only if the rollout policy is frozen (current-policy continuation versus random continuation), the same prefix and alternatives are used, all branch transitions and validation are charged, and both RL and non-RL comparisons receive the same candidate information and total wall-clock/compute. A non-RL controller that chooses the lowest sampled completion cost should be included when those samples are available to RSCC. One rollout per alternative is noisy; it cannot be treated as an exact counterfactual or a strong route optimizer. Report matched environment-transition and matched total-compute comparisons separately if both cannot be held equal simultaneously.

## Specific exchange questions

1. Will the actor be a flat pair categorical or an explicit event-then-slot factorization? If flat, how is the target-dependent baseline made policy-gradient unbiased? If factorized, is the counterfactual advantage applied only to the slot-factor score, leaving target/event score with a state-only baseline?
2. How are unchosen-slot `Q(s,(d',i))` values obtained: a learned critic trained on observed chosen actions, branch rollouts under the current policy, random continuation, or another estimator? What is the frozen estimand and exact cost accounting?
3. What algorithmic increment remains beyond the generic COMA-style conditional baseline, given the old Stage-B domain and Li vehicle/node action construction? If none, will G0 be labeled NO-GO rather than treating empirical transfer as method novelty?
4. Is one random completion per alternative being proposed as a control? If yes, will there be a non-RL min-sampled-cost controller and matched rollout/transitions/computation, with separate matched-sample and matched-wall-clock results?

## Candidate integrity

This review addresses only the frozen `G4_CANDIDATE.md` hash above. Any later revision requires a separate review and exchange; it must not silently replace this initial judgment.
