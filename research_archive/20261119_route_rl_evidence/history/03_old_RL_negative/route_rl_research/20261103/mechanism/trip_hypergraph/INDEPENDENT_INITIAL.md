# Trip-combination object: independent adversarial initial

2026-11-03. Reviewer: route_independent_audit. This initial is frozen before reading either peer's trip-combination initial or exchanging their substantive findings. I read the root object boundary, the six saved primary/search text records and the existing environment/closed G2 report. No DP, evaluator, solver, training, new-instance generation or server task was executed for this review.

## Initial disposition

**OBJECT_DEFINED; ALGORITHM_UNDEFINED; G0_NOT_PASSED.** The root boundary identifies a legitimate physical-route object, but does not yet specify an algorithmic increment. This is not a finding that every future trip representation is impossible or that learned routing cannot work. It means a family of feasible continuation trips, even with energy/minutes/overlap attributes, is already a route-column/remaining-subset object. A concrete representation/update rule and a non-direct difference from the closest precedents remain required before a quality experiment is defined.

Reviewed boundary: `ROOT_OBJECT_BOUNDARY.md`, SHA256 `fdcabbd880087399469b1b11d335f7869d58a857de51a859d5cfbf2f83ea4e8c`.

## Exact structural challenge

Let U be the remaining targets at a fixed station, and let each physical slot d have endpoint p_d, open-trip energy e_d, elapsed open-trip minutes t_d and closed-trip duty h_d. A feasible residual completion contains exactly one closure of each nonempty open trip, plus any number of fresh station-to-station trips. A column records slot d, subset Q, an ordered path from its specified start to the station, and its added energy/minutes/cost. An open-trip closure with Q empty must remain representable: RETURN is a real physical action. Fresh empty trips are unnecessary and must not create empty-return loops.

Choosing such columns requires exact cover of U, the open-trip closure obligations, and aggregate duty by slot; mutually overlapping target sets cannot both be selected. Each chosen column must satisfy its own slot battery including the already-spent energy of an open trip. These are ordinary resource-constrained route columns coupled by exact cover and slot resource rows. A hypergraph view is a useful representation of these columns, but does not alter the problem or establish a new algorithm.

For the current LRPHSD model, start, finish, target subset and slot fixed, the target service-energy and service-time sums are constants. Flight energy, added minutes and original operating cost are all nondecreasing affine functions of the same flight length, with shared speed/flight-energy/time-cost parameters. Thus a shorter path for that column weakly dominates a longer path in all three quantities. There is no new energy/time Pareto trade-off within such a fixed column under this model. The hard combinatorics are selecting target subsets, assigning them to slots and partitioning into trips, rather than discovering a newly conflicting physical clock. This argument uses the stated model; it does not assert exact real/IEEE optimality of a finite floating implementation.

A family that omits feasible columns is only a restricted pool. Failure to find an exact cover in that pool does not certify global infeasibility. Conversely, local legal next-target/RETURN checks or pairwise compatibility do not certify existence of a residual complete cover. Any proposal that turns sparse-family emptiness into a hard physical mask must provide a separate soundness argument or explicitly report false exclusions and changed search domain. A learned feasibility prediction cannot silently become a certificate.

## Primary evidence boundaries

1. **SED2AM**, arXiv:2503.04085v1, saved `evidence/route_g0_primary_open.json` (plain-text web record despite its extension), §§3–4, source lines 125–151: multiple trips, vehicle/next-node action, remaining capacity and remaining working hours are already explicit; depot resets capacity while working hours are consumed. Adding persistent cumulative duty or a two-level vehicle/target decoder therefore does not identify a new mechanism. The paper's capacity/time-dependent routing is not a proof that it implements LRPHSD flight-plus-service-energy batteries.
2. **Wang et al.**, arXiv:2503.10421v1, saved `evidence/route_g0_hypergraph_primary.json`, §3.2, source lines 127–154: similarity-threshold memberships, constraint-oriented hyperedges, learned reconstruction and soft violation penalties already exist. It would be inaccurate to attribute exact LRPHSD ordered-trip energy certificates to that source. Replacing its soft constraint groups by real feasible trip witnesses is a specific engineering difference, but route-column/RCSP/set-partition methods remain a closer mathematical equivalence test for that difference. The v1 and v2 bibliographic identities must remain distinct.
3. **PIP/LMask/DPDP** have been located as primary records. The currently inspected local extracts do not establish all their technical details. Their exact masking/backtracking/dominance rules require source-level comparison before making a claimed difference. UNKNOWN does not establish novelty, and does not establish equivalence either.

## Questions a complete candidate must answer

- What exact finite information is supplied to the actor at each prefix, and how is it constructed and updated after `(slot,target)` and `(slot,RETURN)`? Include open-trip closures and future depot trips, not just one form of continuation.
- Which precise operation differs from standard route-column generation, remaining-subset DP, learned feature augmentation, preventative masking or neural-guided DP? Give an equation, invariant or explicit counterexample, rather than only a new name.
- What are the worst-case work/memory and the frozen practical caps? Are limits errors, an incomplete representation or a fallback? Retain the parent solution and all failures; no sparse pool is an infeasibility oracle.
- If the actor receives trip witnesses, marginal-cover scores, branch completions, a teacher or dual information, which non-RL and BC controls receive exactly the same information? Shared generation, updates, model loading, inference and all fallback/validation costs must enter the appropriate budget.
- Which behavioral prediction is falsified if a simpler non-RL residual-cover rule or same-information BC/beam matches the RL? A valid test must distinguish representation, extra computation and genuine cross-step learning.

## Required comparisons and attribution

The completed historical G2 only motivates a station-joint problem domain. Its complete-map fixed-owner reference equals the historical fixed-owner ALNS anchor, and releasing ownership creates the extra gap. A new baseline must therefore support target-slot reassignment, trip partition and route order. It cannot retain fixed owners and be called the strongest same-domain control.

At minimum the eventual comparison family needs a strong station-joint non-RL route/assignment solver; shared-physical-action greedy/beam/BC and an applicable bandit; a generic prior-art-style route policy; and a simple controller that uses exactly any additional trip-family information supplied to the proposed RL. All are subordinate to the existing original-objective, 6s/12s, 0.3%, map-level CI and three-training-seed contract. This list defines comparison obligations, not permission to execute them now.

The saved complete G2 witnesses have loose cumulative duty, so there is presently no observational basis to make binding duty scarcity the main causal explanation. This does not prove duty can never bind on new data. Likewise, LD dominance on many old configurations does not eliminate energy-feasible multi-trip routing, but it weakens claims that two-slot competition itself supplies the new effect.

## Next bounded deliverable

A mechanism author can now specify one concrete finite representation/update and its precise prior-art increment. The independent reviewers should challenge that object and freeze an experiment only if the claims survive. The present object boundary alone licenses no new quality run, G4 training or Formal. No old-map rerun, timeout expansion, new network name or changed seed repairs the missing algorithm definition.
