# Independent G0 mechanism initial: prefix-conditioned trip families

Date: 2026-11-03. Reviewer: `route_mechanism_g4`. This initial is written and frozen before reading either peer's new trip-hypergraph initial. Inputs are `ROOT_OBJECT_BOUNDARY.md`, the accepted saved G2 numerical audit, the original problem/source definitions and the already located primary-source extracts. This task performs mathematical/source reasoning only. It runs no maps, solver, evaluator, geometry, training or new quality diagnostic. This is an internal research-design record, not manuscript text.

## Independent decision

**The generic prefix-conditioned feasible-trip family is a valid physical-route object, but currently NO_GO as a new mechanism.** I can specify it exactly; under LRPHSD's current additive metric model it reduces to prefix-conditioned shortest-path/subset tour computations plus a tagged set-partition model. Naming, counting, encoding or attending to this object does not supply a non-direct algorithmic increment. A new tractable update or estimator could be investigated, but none is established merely by the boundary description. No new training should start from this initial.

The G2 results motivate allowing station-internal target ownership to change, rather than training against fixed-owner ALNS alone. They do not establish that a learned trip representation is required, that cumulative duty binds, or that any proposed network is novel. The saved DABS witnesses use both, LD-only and SD-only allocations; this variation is an output fact, not evidence that dual-slot competition is necessary for the optimum.

## Exact state and complete object

Fix one station, its type and its assigned target set. State s records the remaining targets U; for each eligible physical slot d, endpoint x_d, current open-trip travel/service minutes t_d^open, current open-trip energy e_d^open, already closed-trip duty t_d^closed and fixed station/slot resource data. Coverage and physical eligibility remain unchanged. The policy outputs only (d,i) for an unserved physical target or (d,RETURN). RETURN retains accumulated duty. All targets must be served exactly once; every trip returns to this same station.

Let v be speed and alpha be flight energy per minute. A target i has nonnegative service minutes p_i and service energy q_i. Let L(o,Q,o) be the shortest closed metric tour through exactly Q from station o. For a future fresh trip define

    T(Q) = L(o,Q,o)/v + sum_{i in Q} p_i
    E(Q) = alpha*L(o,Q,o)/v + sum_{i in Q} q_i.

For a nonempty open prefix ending at x_d, let L(x_d,Q,o) be the shortest path visiting exactly Q and returning to o. Its candidate continuation has

    T_open_d(Q) = t_d^open + L(x_d,Q,o)/v + sum_{i in Q} p_i
    E_open_d(Q) = e_d^open + alpha*L(x_d,Q,o)/v + sum_{i in Q} q_i.

The empty Q continuation denotes returning now when a prefix is open. It does not emit an empty trip when the slot is at the station. A member of H_s must carry the concrete shortest-path witness, target set, slot tag, T/E values and coverage/resource eligibility; a bare subset or a static depot-rooted tour does not suffice for an open-prefix continuation. The physical evaluator still verifies complete witnesses. These equations describe real additive reasoning; no all-IEEE optimality result is claimed.

Because service contribution is subset-additive and alpha/v is nonnegative, a shorter path weakly improves both time and flight energy. Thus, for a fixed target subset and endpoints, retaining a minimum-length witness is sufficient for this mathematical reference. A Pareto family of route orders is unnecessary in this original model: time and energy cannot trade off through route order when service sums are fixed. A new method whose only change is a larger route-order Pareto label set would add redundant states here.

## Residual cover reduction and exact externality

For each open slot choose a continuation subset Q_d, possibly empty, and choose future fresh-trip variables z_{d,Q}. These choices must be disjoint and cover U exactly once:

    sum_d 1[i in Q_d] + sum_{d,Q containing i} z_{d,Q} = 1, for every i in U.

Each selected continuation/trip must meet its slot battery bound. Each slot must also satisfy

    t_d^closed + T_open_d(Q_d) + sum_Q T(Q)*z_{d,Q} <= duty_limit_d,

with the open term omitted or adapted for an initially empty prefix. The objective minimizes the corresponding remaining operating minutes, retaining already incurred minutes and fixed station/vehicle costs when scoring the full map. This is a standard tagged set-partition problem with per-slot resource rows and at most one marked open continuation per slot. Full trip order inside a slot has no extra cost or scheduling meaning under the original absence of time windows, shared chargers or synchronization.

The exact opportunity externality of a physical action a is the Bellman quantity

    Delta(s,a) = immediate_operating_cost(s,a) + V*(s_after_a) - V*(s).

Computing V* by residual subset DP, set partition/pricing or complete cover enumeration is a conventional exact/lookahead reference. A policy that receives Delta as a teacher receives an expensive optimal cost-to-go signal; that is not a new route mechanism by itself. Its full teacher/online generation cost and access must be aligned with non-RL controls.

For n residual targets, a conventional subset tour computation costs O(n^2*2^n) time and O(n*2^n) storage; enumerating all partition transitions costs O(3^n) in the ordinary recurrence, with separate slot-assignment work. The accepted station DP already uses this family of operations. Truncating H_s or retaining only a sampled trip pool reduces cost but loses exactness and creates candidate-generation dependence. Such a pool is a restricted standard set-partition reference unless a specific additional update or learning principle is supplied.

## Two structural checks any candidate must pass

**Downward closure.** For fresh trips in a metric with nonnegative service minutes/energy, deleting an unserved target from a feasible trip and shortcutting its adjacent edges cannot increase travel length, time or energy. Hence each slot's feasible fresh-trip subset family is downward closed. A claimed externality that depends only on losing infeasible proper subsets or on a pairwise eligibility relation should be checked against this fact. Higher-order battery-feasible combinations can still matter; downward closure does not make pairwise compatibility sufficient, and generic higher-order capacity structure already occurs in ordinary CVRP.

**Nested DABS batteries.** In a DABS station both slots share the large-station coverage and duty limit, while SD battery is smaller. Every fresh SD-feasible trip is therefore LD-feasible under the same route witness in real arithmetic. There is no class of targets or trips physically exclusive to SD in this scope. Any representation that markets a generic heterogeneous bipartite assignment conflict should expose what remains after this nesting and the existing conditional LD-absorption result. Duty can still limit aggregating all trips on LD on some instances; the existing witness slack and absorption certificates neither establish universal redundancy nor establish dual-slot necessity on new maps.

Appending a target changes the open endpoint and already spent energy; it is not correctly modeled by deleting all hyperedges containing that target and keeping stale depot-rooted weights. A valid incremental update must either condition sequence witnesses on the new prefix, recompute the prefix-conditioned costs, or expose approximation/error. The object boundary contains no such update algorithm yet. General lazy recomputation, caching and subset DP are established engineering choices and require an actual increment before novelty is asserted.

## Closest precedents and required contrast

The locally retrieved primary extracts identify the relevant overlap; exact-version full reading remains the evidence agent's task.

- Wang et al., arXiv2503.10421v1, sections3.2–3.3, already dynamically constructs constraint-oriented hyperedges and combines them with a physical route decoder and route history. The shared local extract is `evidence/route_g0_hypergraph_primary.json` (web-text content despite its suffix). A claim restricted to constraint-feasible trip hyperedges or high-order attention is therefore not sufficient. Do not mix the v1 record with the later v2 title/author metadata.
- SED2AM, arXiv2503.04085v1, sections3–4, has vehicle/trip construction and fleet/routing state with remaining working hours. Service-plus-flight battery equations distinguish LRPHSD's application, not automatically the decoder principle.
- Existing local Li HCVRP and PARCO evidence already covers heterogeneous vehicle-node decisions and shared remaining-target contexts. The physical action form is correct but not new.
- Residual tour/partition DP and set partition/pricing already implement complete trip-combination optimization. DPDP already learns guidance for a restricted DP. PIP/LMask establish future infeasibility/learned masking/backtracking precedents. Renaming these mechanisms or giving them a route-only output layer does not establish a new object.

## A falsifiable design contract, not an approved mechanism

If root identifies a specific proposed update F that compresses or updates H_s, it should provide full input/output equations and cost accounting before any experiment. The following predictions distinguish useful functionality from generic augmentation:

1. F must respond to an action's effect on joint residual cover/partition opportunities beyond the immediate direct-return mask. Its claimed higher-order information should differ on a fully specified counterexample that a named simpler representation actually cannot distinguish; a blanket claim about all pairwise neural networks is unjustified.
2. Its update must match its declared exact or approximate semantics on all small independent exhaustive fixtures, including nonempty prefixes, RETURN, both batteries, empty slots and resource boundaries. Prefix-conditioned witnesses must be checked, not assumed from a static pool.
3. On new development data, any effect must survive same-action rules, greedy/beam, supervised teacher features and a strong station-joint non-RL solver with the same trip-family information and total generation/inference/search wall time. Better results than fixed-owner ALNS do not test this hypothesis.
4. At matched training compute, genuine cross-step RL must add reproducible value beyond BC/supervised initialization or bandit/simple value selection, with at least three independent training seeds and all selected models evaluated. Extra cover enumeration cannot be supplied only to RL or hidden as preprocessing.
5. On the original full objective and both frozen budgets, the existing effect/CI/feasibility/overrun gates remain. No observed old-map stratum becomes a new development set; no old-pool enlargement or repeated DP is authorized here.

At present F is unspecified. This contract is therefore a concrete rejection criterion and design boundary, not a substitute algorithm or a G0 pass. My current outcome is **NO_GO for generic trip-hypergraph/cover-feature policy; specific incremental mechanism remains UNIDENTIFIED**. I will exchange this exact reduction and boundary with the independent and evidence reviewers after all initials are frozen.
