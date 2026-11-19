# G2 Station Split-DP Opportunity Diagnostic Protocol

Date: 2026-11-03. Freeze before implementation execution.

## Question and scope

Measure the route-only opportunity from reassigning station-owned targets between eligible physical drone slots and reoptimizing closed multi-trip routes, holding every station location, station type, and target-to-station assignment fixed. This is a historical exposed-data diagnostic, not new development, a formal test, an innovation, or evidence that RL is necessary.

The only decisions in the DP witness are physical target ownership by eligible slot, route visit order, and trip boundaries/returns. No search operator or solver operator is selected.

## Frozen inputs

- Use all 24 Stage-A validation map names and SHA256 identities in `source_snapshot/ROUTE_RL_STAGEA_FREEZE_20261102.json` under `data_split.validation_maps`; no filtering.
- Re-read and hash-check each instance before use. Reconstruct its deterministic Greedy parent with the frozen source snapshot `lrphsd/greedy.py`; independently validate the complete parent.
- Freeze each station's `station_type` and its target set `T_s`, defined as the union of that station's parent route targets. Verify exact once-only coverage, no cross-station overlap, and complete target identity before optimization.
- Record source code/input hashes, process wall time, per-map wall time and per-station time. Include Greedy construction and full evaluator costs in end-to-end diagnostic accounting.
- Do not use any DP label, route, feature, or action as input to a trained policy. No training, search tuning, new maps, solver quality matrix, or Formal run is included.

## Exact station formulation

For every nonempty station pool with `n=|T_s|<=12`, enumerate every target subset and every eligible slot. The size cutoff is on the complete station union, before any slot split; it is fixed from the existing small-instance exact-DP limit and is not tuned from results. For each nonempty trip subset `Q`, use the shortest closed station-rooted Hamilton tour through `Q`. Its operating time is `tour_length/speed + sum(service_i)` and its trip energy is `(tour_length/speed)*flight_energy + sum(energy_i)`. Reject a trip if any target violates the fixed station-type coverage radius or if trip energy exceeds the slot battery plus `1e-7`.

For each slot and target subset `A`, subset partition DP minimizes the sum of trip operating times over an exact partition of `A` into nonempty battery-feasible trip subsets. A fixed pivot in every partition recurrence removes only permutation symmetry among trips. The minimum route time is feasible only if it is at most the station-type duty limit plus `1e-7`; duty accumulates across all trips and RETURN does not reset it. Because route objective contribution and duty use the same operating minutes, one scalar minimum-time label per subset is sufficient.

- Closed station (`kind=0`): target set must be empty; both physical slots remain empty.
- SABS (`kind=1`): only SD slot 1 is eligible; use small battery, small radius, and small duration.
- DABS (`kind=2`): slots 0=LD and 1=SD are both eligible; use large battery for LD and small battery for SD; both slots use the DABS station's large radius and large duration.
- DABS station optimum reference: enumerate every subset `A subset T_s` for LD, including `A=empty` and `A=T_s`; SD receives exactly `T_s\\A`. Minimize the two feasible slot route-time values. Do not replace per-slot duty checks with a joint total-duty check.
- Empty slots are valid and have no trips. Empty trips are never emitted.
- Coverage, energy, duty, duplicates, station/type compatibility, and full original objective are rechecked using the frozen independent evaluator. Its `1e-7` feasibility convention is used; it is not a cost-rounding tolerance.

The implementation must return complete target-ID route sequences and trip boundaries with parent pointers. It must also preserve both the source and candidate complete solution for each map. An independent evaluator rejection, malformed witness, duplicate/missing target, changed station type/ownership, or candidate cost regression beyond the predeclared `1e-8` absolute map-cost reconciliation tolerance marks the affected station/map `NUMERICAL_OR_IMPLEMENTATION_UNRESOLVED`; it must not be silently repaired or claimed optimal.

## Bounds, limits and unresolved cases

- Every station in all 24 maps remains in the output denominator.
- A nonempty station with `n>12` is `UNRESOLVED_SIZE_LIMIT`; no partial fixed-owner solve may be relabelled station-exact.
- Any station exceeding the predeclared 12-second per-map wall-clock cap, transition/state bound, or producing evaluator/numerical inconsistency is unresolved. The cap is diagnostic compute, not a 6s/12s solver-quality comparison.
- `max_states=2^12` masks per station/slot; `max_transition_checks=2,000,000` per station. If an implementation reaches a bound, preserve its last valid incumbent/witness if available and mark unresolved; never call an incumbent an optimum.
- For unresolved stations, retain the original parent routes in the candidate full map. A candidate that replaces only solved stations can demonstrate a **realized feasible improvement** if the full evaluator confirms it; it does not bound the remaining opportunity from above.
- A map is `FULL_STATION_DOMAIN_REFERENCE` only when all its stations are complete, all witnesses reconstruct, and the complete candidate passes the independent evaluator. Otherwise the map is `PARTIAL_REFERENCE_WITH_UNRESOLVED_STATIONS`, even if its partial candidate is feasible.

## Outcomes and aggregation

Per map, record the full original parent and candidate evaluator costs, fixed-cost and operating-minute decomposition, percentage change `(C_parent-C_candidate)/C_parent`, all station statuses, DP route witnesses, slacks, independent evaluator results, and elapsed/wall-clock accounting. Per station, preserve pool size, type, eligible slots, slot target masks, trips/sequences, DP objective, evaluator objective and residuals, battery/duty/coverage margins, status and timing.

The primary unit for descriptive summaries is the map, never a station, slot, seed-cell, transition, or evaluator call. Include all 24 maps, with unresolved maps visible; report completeness count, mean/median map effects, win/tie/loss counts, and the full per-map table. Do not compute confirmatory p-values or generalize to unseen maps from this exposed set. A DP optimum/reference is not a 6s/12s fair-budget method result; include its runtime separately and later compare actual methods under the frozen end-to-end budgets in G3/G4.

Positive station/map effects quantify only this fixed-outer-decision route opportunity. They do not prove algorithmic novelty, RL superiority, sufficient G4 headroom on new maps, or full LRPHSD global optimality. No G0/G4 gate is auto-passed by this result.

## Pre-execution verification

Before processing the 24 frozen maps, the DP must pass:

1. Exhaustive brute-force equivalence on declared tiny SABS and DABS fixtures, including an empty slot, a multi-trip solution, heterogeneous batteries, DABS duty/radius semantics, and a rejected infeasible witness.
2. Witness reconstruction plus independent full evaluator on every tiny fixture.
3. JSON/schema validation and a dry-run that reads hashes/config only and launches no solver.

The protocol and implementation hashes must be saved before the 24-map diagnostic is run. All results and failures are retained; this protocol is not adjusted after observing map outcomes.
