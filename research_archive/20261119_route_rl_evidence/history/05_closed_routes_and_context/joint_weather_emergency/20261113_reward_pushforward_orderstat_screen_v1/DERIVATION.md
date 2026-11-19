# Reward Pushforward and Fixed-Budget Objective

## Objects

Let `tau` be a physical actor trajectory, `x(tau)` its complete raw typed route schedule, `T(x)` the unchanged public cost-neutral slot reassignment, and `y=T(x)` the full delivered schedule. The frozen scorer supplies feasibility, complete cost, and `M_return` for `y`. Write `p_theta(tau)` for the actual autoregressive route-policy probability.

## Policy-gradient objective

For any fixed scalar scorer `R(y)` (including a feasibility-first encoding of the frozen full-map contract),

```text
J(theta) = E_{tau~p_theta}[R(T(x(tau)))]
         = sum_y p_theta^Y(y) R(y)
```

where `p_theta^Y(y) = sum_{tau:T(x(tau))=y} p_theta(tau)`. Differentiating the trajectory expectation gives

```text
grad J = E_{tau~p_theta}[R(T(x(tau))) grad log p_theta(tau)].
```

Thus a many-to-one `T` does not bias the on-policy score-function estimator. It changes the policy-induced delivered distribution `p_theta^Y`; that is part of the objective's induced sampler, not an estimator error. A valid action-independent or leave-one-out baseline remains valid. The identity applies to the score actually returned by the unchanged full scorer; it does not license dropping infeasible or failed rows.

## Why the GFN multiplicity derivation differs

If a GFN explicitly targets raw-terminal mass `p_X(x) proportional to r(T(x))`, then its pushforward is

```text
p_Y(y) proportional to r(y) * |{x : T(x)=y}|.
```

An auxiliary normalized conditional `q(x|y)` is needed only if the chosen GFN objective requires `p_Y(y) proportional to r(y)` with that exact raw-terminal construction. The conditional-mass identity is correct, but that distribution-matching objective is not the frozen fixed-wind requirement (`min M_return` subject to complete same-wind cost cap). Therefore exact fiber proposal construction is not a prerequisite for ordinary route-policy gradient optimization and must not be used to block G0 progress. If GFN is later retained as a standard control, state its target distribution and its own normalization requirements explicitly.

## Exact deployment-budget objective

For a fixed inference budget of `K` independent policy rollouts, let `S(y)` be the registered scalar score that ranks admissible complete schedules ahead of inadmissible outcomes and ranks admissible schedules by lower `M_return`. Then

```text
J_K(theta) = E[max_{i=1..K} S(Y_i)]
grad J_K = E[max_i S(Y_i) * sum_{i=1..K} grad log p_theta(tau_i)].
```

This follows by applying the score-function identity to the joint iid batch law. The finite-sample order-statistic objective is directly covered by OrderGrad; top-1 rank weights recover best-of-K. The derivation is useful as a future strong RL control aligned with inference-time selection, not a novel mechanism. The actual experiment must use the full fixed-wall-clock candidate pipeline (including `T`, scorer, retries, and timeouts), because a fixed `K` may not represent a six-/twelve-second deployment budget when per-candidate cost varies.

## Decision

1. Keep the exact T-fiber `q` question open only as a GFN-specific implementation question; remove it as a general route-learning gate.
2. Register OrderGrad-style top-1/best-of-K as a standard candidate/control for a later admitted fixed-budget RL comparison.
3. Continue G0 on a genuinely route-physical construction/update difference. No training, checkpoint, scientific population, or Formal is admitted by this derivation.

