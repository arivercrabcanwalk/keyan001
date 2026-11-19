# Constant-Wind Trip-Reversal Invariant

Let airspeed be `v`, constant wind be `w`, and `|w| < v`. For a displacement
`d`, the repository's track-holding travel-time formula is algebraically

```text
a = v^2 - |w|^2 > 0
T_w(d) = (sqrt(a |d|^2 + (w dot d)^2) - w dot d) / a.
```

Therefore

```text
T_w(d) - T_w(-d) = -2 (w dot d) / a.
```

For a closed trip with leg displacements `d_1,...,d_m`, `sum_i d_i = 0`, so
`sum_i T_w(d_i) = sum_i T_w(-d_i)`. Reversing the target order reverses each
leg of the same closed geometric walk. It preserves trip travel time in real
arithmetic even though individual directed arc times are asymmetric.

The same expression is a Randers-type gauge. The square-root term is a norm
because `a I + w w^T` is positive definite; subtracting the linear form
`w dot d` preserves subadditivity. Thus `T_w(x+y) <= T_w(x) + T_w(y)`. For a
feasible completed reversed trip, every prefix followed by a direct return is
no longer than the remaining suffix of that complete trip. Nonnegative target
service and target-energy terms then imply prefix return-energy and cumulative
duty feasibility. A valid completed cost-cap witness also bounds every prefix
by the environment's necessary cost lower bound.

Under the frozen scorer, flight energy is proportional to travel time and
target energy/service are order-independent sums. Reversal therefore preserves
each trip's real-valued duration and energy, each slot's cumulative duty,
`M_return`, and total cost. It does **not** preserve target completion times,
`M_service`, release/deadline response, or any WX lateness objective. The
claim is limited to fixed uniform wind, the current linear flight-energy
model, complete closed trips, and the approved S objective.

## Exact Orbit Score Estimator

Let `R` be an involution on the supported complete action-trajectory space,
`P_theta(tau)` the full autoregressive trajectory probability,
`S_theta(tau)=grad log P_theta(tau)`, and `A(tau)` the actual scorer-derived
advantage. The exact conditional estimator on the orbit `{tau,R(tau)}` is

```text
g_orbit = [P(tau) A(tau) S(tau) + P(Rtau) A(Rtau) S(Rtau)]
          / [P(tau) + P(Rtau)].
```

This is `E[g_base | orbit]`; it is unbiased and has no greater covariance in
the positive-semidefinite order. If the mathematical reward is exactly
invariant, `A(tau)=A(Rtau)`, it simplifies to
`A(tau) grad log(P(tau)+P(Rtau))`.

An unweighted average of the two scores is generally biased unless the policy
assigns equal probability to both orientations. The finite scorer and its
absolute `1e-7` cost tolerance can distinguish orientations in a narrow
round-off boundary band. The estimator must use both actual rewards there, or
leave that orbit unpaired; it must never silently assume exact binary64
equality. Any paired map must be involutive and preserve support, including
the legal-action and necessary-cost masks.

## Boundary

This derivation proves a candidate symmetry, not an RL advantage, G0 pass,
strong-baseline win, or Formal result. The orbit conditional expectation is a
standard Rao-Blackwell construction. The only possible project-specific delta
is exploiting the constant-wind closed-trip invariant with the exact typed
multi-trip masks and full cost-capped `M_return` scorer. It remains a future
standard RL control unless the engineering and source screen establish a
material new contribution.
