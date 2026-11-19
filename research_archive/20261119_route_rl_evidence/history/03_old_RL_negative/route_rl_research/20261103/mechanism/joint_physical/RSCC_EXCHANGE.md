# Exchange: RSCC Original Candidate and Factorized Revision

Date: 2026-11-03. Participants: `route_independent_audit` and `route_mechanism_g4`. The original independent position was frozen before the first exchange; REV1 was reviewed and frozen separately before responding to its formula. Neither side ran a solver, evaluator, rollout, or training job for this discussion.

## Original candidate identity and frozen review

- Candidate: `G4_CANDIDATE.md`, SHA256 `35a6fcf61be38a0ad09bb5ed8b74d86793f794947693036a6db97ac955e5d574`.
- Independent initial: `RSCC_INDEPENDENT_INITIAL.md`, SHA256 `16763296e7ba634aa6ac3e1d2159eded33c2bc1c082f09edc4b6fec88fcc8d9b`.
- Freeze: `RSCC_INDEPENDENT_FREEZE.json`.

The independent review found that the `(slot,target/RETURN)` action domain is the old Stage-B domain. RSCC adds a credit signal not stated in Stage B, but its target-conditioned slot baseline is the COMA-style counterfactual baseline applied to the slot component. For a flat pair categorical policy, `b(s,i)` depends on part of the sampled action and generally biases the full pair policy gradient. The review required explicit factorization, separate score updates, an estimator for unchosen-slot Q values, and a fair single-rollout/non-RL control.

## Mechanism agent's direct response on the original candidate

1. **Actor / PPO factorization.** The agent says it will use `pi_U(u|s) pi_D(d|s,u)`, where `u` is `visit(i)` or `RETURN`; the event score uses `A_U = Qbar_U - b_U(s)` with a state-only baseline, and the conditional slot score uses `A_D = Q(s,u,d)-sum_d' pi_D(d'|s,u)Q(s,u,d')`. The log-probabilities/GAE are separate. If PPO is used, event and slot ratios are clipped separately and their losses summed; the agent calls this a factorized-PPO surrogate and accepts that it needs a finite-MDP exact-expectation G1 test. It will not apply the slot advantage to the event score.
2. **Unchosen-slot Q.** The agent accepts that critic predictions for unchosen slots are extrapolations. For an unbiased audit control, it proposes cloning the exact prefix, forcing each eligible slot and continuing each branch under the same frozen continuation policy with coupled RNG; every branch transition/forward/runtime is charged. It states that this cost may make the candidate infeasible and that a non-RL paired-rollout control must receive the same information/budget. The estimator/continuation must be frozen as one option and not mixed with random-continuation labels.
3. **Novelty.** The agent identifies no irreducible algorithmic increment: the proposal combines a COMA conditional counterfactual with the Li vehicle-node action pattern and the already specified Stage-B decision domain. It accepts **G0 NO-GO for algorithmic novelty**.
4. **Single-random-rollout control.** The agent accepts adding a non-RL controller that chooses the minimum sampled completion cost, using the same candidate/transition domain and equal total simulator/compute budgets. Without this, comparison would be unfair.

## Separate REV1 review identity and findings

- Revised candidate: `G4_CANDIDATE_REV1.md`, SHA256 `af971cda15dbd9d77f1800dd24c7222dabcd51bb3a1cf62e47debebcfc16d76a`.
- Independent REV1 initial: `RSCC_REV1_INDEPENDENT_INITIAL.md`, SHA256 `e1ab43449cd93ba13b05a9cfd4d7d27983e1ebd9b762e1a8d3a6a2e3cf85ed2c`.
- Freeze: `RSCC_REV1_INDEPENDENT_FREEZE.json`.

The revised event-then-slot score decomposition is mathematically valid for an exact `Q^pi(s,u,d)` under the stated factorized policy, provided each baseline is applied only to its corresponding conditional score. Separate event/slot PPO clipping is a factor-wise surrogate and must be tested/declared; it is not automatically the standard joint-ratio PPO objective. The revision still does not identify counterfactual outcomes for unchosen slots from ordinary on-policy sampled returns alone. It must choose either a learned critic with explicit support/calibration diagnostics or frozen-policy forced-action branches with their costs. A random continuation estimates a different value function than a current-policy continuation.

The primary COMA paper documents marginalizing the selected agent's action while holding other action context fixed; the RSCC slot formula has the same conditional-counterfactual structure, while its autoregressive centralized route policy is not identical to COMA's original decentralized architecture. Li HCVRP and old Stage B already cover the factorized heterogeneous vehicle/target route-action pattern. Therefore REV1 repairs the gradient issue but retains the no-novelty G0 verdict.

## Fair resource control and resolution

One random completion per eligible slot is a useful **budget-matched**, high-variance control, not a sufficient strongest route baseline. When RSCC has branch returns, also give a non-RL min-sampled-cost controller the same branch information, candidate actions, transitions, and total budget. Report equal-transition and equal-total-compute/wall-clock comparisons separately if both cannot be matched at once. Include strong route/assignment baselines regardless.

The exchange closes the formula objection for a properly factorized gradient but does not close Q-estimator calibration or novelty. **RSCC is not accepted as a G0 novelty mechanism; no G4 execution is authorized by this record.** Any future empirical transfer test needs a root decision after G2/G3, fixed estimator and resource protocols, and same-critic/GAE ablations to isolate the credit signal from critic capacity or extra rollouts.

## Mechanism agent's final REV1 response

The mechanism agent later recorded `RSCC_FINAL_RESPONSE.md` (SHA256 `4c3a65d0035d953fa7edbe05607791e662f70f773ccee8d2b3dfb4d5d7682fcd`) and explicitly accepted the remaining review points:

- Detach `Q`, probability weights and both baselines; never use `A_D` on the event log-probability. The factor-wise clipped PPO objective is not justified by the score-function identity and requires a finite-MDP exact un-clipped gradient check plus its own frozen surrogate validation.
- REV1 did not freeze one unchosen-slot-Q estimator. On-policy return data observe only the chosen slot; critic predictions for other slots are extrapolations. A causal counterfactual-credit study requires cloning the prefix, forcing each eligible slot, and completing each branch with one frozen continuation policy, while charging every action, transition, inference, validation, failure and wall-clock cost. Random continuation estimates a different `Q` and cannot be conflated with `Q^pi`.
- The agent gives no substantive novelty rebuttal: heterogenous vehicle-node decoding, old Stage B and COMA-style conditional credit cover the mechanism's components; fixed LRPHSD constraints do not make this a new algorithm. **G0 algorithmic novelty remains NO-GO; do not authorize RSCC as the main-method training line.**
- If root separately authorizes an application-focused G4, include a non-RL min-sampled-cost controller with the same prefix/slot branches and report both equal-environment-transition and equal-total-wall-clock results, alongside strong station assignment-route DP/B&B, beam and route heuristic controls.

This final response resolves the design discussion without changing either frozen independent initial or running any experiment. It confirms that the repaired gradient is a correctness candidate, not a novelty pass; the counterfactual-Q estimator and its cost remain a prerequisite to any separately authorized application test.
