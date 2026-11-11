# G0 Reassessment After P3 Closure

Date: 2026-11-05 (Asia/Shanghai)
Scope: read-only reconciliation of the current route-RL claim, local primary-text audits, current calibration evidence, and newly checked publisher records. No maps, author solves, route-quality calls, training, or Formal runs were executed.

## Decision

**G0 remains NO-GO for a distinct algorithmic contribution.** The approved physical action boundary remains correct: an action emits `(slot,target)` or `(slot,RETURN)`, never a search operator, neighborhood, algorithm family, or compute budget. That boundary is a scope constraint, not an innovation claim.

The present project can still ask whether an ordinary route policy has empirical utility on this constrained application. A positive result would not establish a new RL mechanism, and the present evidence does not yet establish positive RL utility either.

## Evidence Reconciled

| Evidence | Supports | Does not support |
|---|---|---|
| Local DPTARL full-text audit | Direct target/return route construction, energy-feasibility pruning, attention, and actor-critic are established route-RL ingredients. | A fair numerical baseline for fixed-outer LRPHSD or novelty of the current action vocabulary. |
| Chen et al. (2024) local full-text audit | RL path planning under turbulent wind is already a published UAV direction, with low-level control actions. | The project's heterogeneous multi-trip problem or a dual-cost-cap method. |
| Yang et al. (2025) local full-text audit | UAV inspection has published RL for siting/coordinated routing and dynamic conditions. | The project's fixed outer decisions, final-return objective, or equal-cost route-only effect. |
| Gao et al. (2026) publisher abstract | Fixed-nest hybrid inspection jointly treats heterogeneous task allocation and UAV route planning, using a two-tier ALNS for intra-day route and inter-day assignment. | Its exact constraints and neighborhoods beyond the abstract, or a result on the project's objective/caps. |
| Ren et al. (2025) COR and Peng et al. (2025) TRE | Publisher/metadata records identify time-dependent EV-drone routing with variable speed/NFZ and multi-agent RL for dynamic truck-drone emergency response. | Detailed action, constraint, and algorithm boundaries; both full texts remain uninspected. |
| Four-map <EXPERIMENT_SERVER> calibration | Both frozen standard controls delivered 16/16 rows under both caps; each reported a four-map mean M_return reduction of 4.620653%. | A powered map-level result, the strongest-NONRL designation, generalization, RL attribution, or an innovation claim. |
| Closed P3 and teacher-state fit diagnostic | The P3 common-BC free-route gate failed; later supervised replay reached exact labels only on the same 138 stored TRAIN states. | P3 rescue, route feasibility/quality, RL benefit, or permission to start PPO/VAL on that exposed population. |

## Closest Comparisons

1. **Direct route RL:** DPTARL already uses next-target/return construction and feasibility filtering. These cannot be presented as the proposed mechanism.
2. **Weather and airspace:** turbulent-wind UAV RL and timed-NFZ/time-dependent vehicle-drone routing are already present. The project's deterministic wind/NFZ instance is a domain-specific extension, not evidence of method novelty.
3. **Inspection allocation and routing:** a 2026 fixed-nest hybrid-inspection paper reports task allocation plus route planning with a two-tier ALNS. Even if its setting differs, the broad application-level combination is not empty.
4. **Non-RL route search:** the current strict and annealed controls are standard baselines. Their four-map calibration outcomes are useful for freezing future comparisons, but the code and evidence do not establish a strongest same-objective comparator.

## Candidate Screen

No currently named candidate clears G0:

- target/RETURN action masks, attention, and pointer decoding are established components;
- residual-budget, dual-price, or threshold conditioning remains a standard constrained/goal-conditioned route policy;
- event-pair/two-step features remain standard model-based lookahead absent a non-equivalence proof;
- product-form trajectory credit remains covered by the inspected general estimator;
- caching, BC, endpoint fidelity, and better delivery accounting are engineering/control improvements, not a new RL mechanism.

No replacement candidate is registered here. A future candidate must specify an exact physical state-to-action/update rule, show non-equivalence to the closest direct-route, mask/backtracking, safety-filter, product-form, and constrained-RL precedents, and make a falsifiable prediction against a same-information non-RL substitute before any quality run.

## Gate Status and Next Valid Work

- G0: no approved distinct algorithmic mechanism.
- G1: engineering and bounded synthetic contracts have substantial evidence; generalization is not established.
- G2: four-map exploratory non-RL calibration exists; independent-map opportunity and statistical support remain open.
- G3: strict and annealed controls are implemented and have calibration results; strongest same-objective weather-aware non-RL is not established.
- G4: prior direct-route runs have no complete candidate; P3 is closed; no new RL advantage is established.
- G5/G6/G7/G8: Formal, innovation ablation, manuscript, and complete package acceptance remain incomplete.

The next scientific run requires a **distinct, complete registration** with fresh identities/exclusion accounting and a predeclared strongest non-RL comparator. P3 is not reopened. No result from calibration maps, old validation maps, toy fixtures, or the teacher-fit diagnostic may be promoted to development/formal evidence. If no substantively different candidate passes the static G0 screen, the defensible path is to report an application/control study only after a valid ordinary-RL comparison, without claiming a novel algorithm or promising a CCF-B outcome.

## Primary-Source Records

- Gao et al., *Task allocation and route planning for UAV-based hybrid inspection ... from a fixed nest*, *Expert Systems with Applications* 313 (2026), DOI [10.1016/j.eswa.2026.131625](https://doi.org/10.1016/j.eswa.2026.131625). The publisher abstract states a fixed-nest hybrid inspection problem and a two-stage/two-tier ALNS for task assignment and routes.
- Ren et al., *Time-dependent electric vehicle-drone routing problem ... variable drone speeds and no-fly zones*, *Computers & Operations Research* (2025), DOI [10.1016/j.cor.2025.107141](https://doi.org/10.1016/j.cor.2025.107141). Bibliographic/title evidence only; full text not inspected.
- Peng et al., *Multi-agent deep reinforcement learning-based truck-drone collaborative routing with dynamic emergency response*, *Transportation Research Part E* (2025), DOI [10.1016/j.tre.2025.103974](https://doi.org/10.1016/j.tre.2025.103974). Bibliographic/title evidence only; full text not inspected.
- Voigt et al., *Hybrid adaptive large neighborhood search for vehicle routing problems with depot location decisions*, *Computers & Operations Research* 146 (2022), DOI [10.1016/j.cor.2022.105856](https://doi.org/10.1016/j.cor.2022.105856). Publisher abstract establishes a population-based HALNS for LRP/MDVRP/2E-VRP; it is a comparator family precedent, not a direct project benchmark.

The local detailed full-text/metadata matrix remains `next_stage_protocol_sol_20261104/evidence/near_papers/CURRENT_NOVELTY_MATRIX.md`. Unknown closed full texts remain unknown; no absence claim is inferred.
