# CA-RL-TSALNS v5 — Coupling-aware operator and reconstruction design

## 1. Design objective

The target is not a generic RL operator selector. It is a hierarchical search controller for LRPHSD whose choices explicitly correspond to station, target assignment, heterogeneous drone allocation, multi-trip routing, and coupled changes across these layers.

The policy selects a concrete macro-neighborhood subtype and search intensity. The operator-specific candidate generator still chooses the concrete station/target subset; this is the deliberate first-stage action-space boundary.

## 2. Hierarchical decision structure

At each decision epoch:
1. Encode the incumbent and search trajectory.
2. Construct a structural feasibility mask for available operator/intensity combinations.
3. Select one of 17 operators and a supported intensity.
4. Generate a candidate using the selected operator's generator.
5. Apply it to an isolated native-kernel slot.
6. Repair only the affected station/drone scope where move semantics allow it.
7. Run native complete/physical checks and the independent evaluator.
8. Apply simulated-annealing acceptance; update current solution and global best separately.
9. Return reward and elapsed wall time to the controller.

The learner never bypasses repair or feasibility validation.

## 3. State representation (75 dimensions)

| Block | Features | Meaning |
|---|---:|---|
| Global search | 13 | incumbent/best cost ratios, gap, used/remaining time, temperature, stagnation, acceptance/improvement, step and instance scales |
| Station structure | 10 | open/SABS/DABS shares, max/mean/std load, fixed-cost share, station duration slack, work concentration |
| Assignment coupling | 8 | alternative coverage share, coverage count, nearest-station share, detour, max station target share, assignment entropy, transfer opportunity, load range |
| Drone and trip | 10 | SD/LD work share, trip counts, per-drone energy slack, low-slack share, trip size, route-cost share |
| Operator history | 34 | 17 operator-specific feasibility/success rates and 17 operator-specific improvement rates |

The fixed-length vector is cheap to compute. It is more granular than the prior 49-D family-aggregated state because history is maintained per concrete operator. It still aggregates some station/drone structure; a typed graph encoder remains a later hypothesis, not an assumed improvement.

## 4. Action vocabulary

Each operator occupies three intensity slots. Intensity levels request different destroy/reconstruction sizes; 2-opt has one supported slot because it is not a destroy-size operation.

| ID | Family | Operator | Candidate semantics |
|---:|---|---|---|
| 0 | Location | open | open a closed station and reconstruct |
| 1 | Location | close | close a station and reassign its targets |
| 2 | Location | upgrade | SABS to DABS |
| 3 | Location | downgrade | DABS to SABS when all constraints can be repaired |
| 4 | Location | swap | exchange types of two open stations |
| 5 | Assignment | transfer | move targets between coverage-compatible open stations |
| 6 | Assignment | drone_reassign | move targets between LD and SD at one DABS, with receiver-energy prefilter |
| 7 | Routing | relocate | station-local target reinsert/relocation |
| 8 | Routing | two_opt | intra-trip 2-opt |
| 9 | Routing | cross_drone | positional target exchange between SD and LD |
| 10 | Routing | cross_trip | exchange between two trips of one drone |
| 11 | Routing | classic | classic destroy/repair |
| 12 | Joint | open_steal | open station, absorb selected targets, reconstruct |
| 13 | Joint | close_shift | close station, shift its targets to receiving stations |
| 14 | Joint | upgrade_absorb | upgrade SABS and absorb additional targets |
| 15 | Joint | downgrade_reallocate | downgrade DABS and reallocate affected targets |
| 16 | Joint | swap_absorb | swap station types and reconstruct both affected stations |

This is a 51-slot masked action tensor, not 51 always-legal actions. Operator IDs are versioned in carl/actions.py.

## 5. Dynamic action mask

The mask checks inexpensive structural preconditions:
- station availability and type;
- whether another station can cover transferred targets;
- whether a DABS has energy-feasible receiver targets;
- whether route/trip structures exist for 2-opt or exchanges;
- whether a joint station/assignment change has a structural opportunity.

The mask is not a substitute for:
- complete target coverage;
- unique service;
- station operating-duration limits;
- SD/LD energy and return-to-station constraints;
- route validity and full objective recomputation.

The mask cache is invalidated whenever Context.refresh() recomputes the incumbent statistics.

## 6. Affected-subproblem reconstruction

For a move with a limited station mask:
- remove only explicitly selected target IDs;
- change only explicitly selected station types;
- pass station and drone masks into scoped native repair;
- leave non-masked station routes untouched;
- check completeness and physical feasibility for the entire candidate.

For station opening/closing/type changes that require complete reassignment, the implementation may use the official greedy rebuild path. Therefore local reconstruction must only be claimed for operators whose implementation actually uses scoped repair.

Required experiment: compare affected-subproblem repair and full-system reconstruction on identical move proposals. Measure candidate feasibility, cost delta, changed-station count, changed routes, repair time, total candidate time, acceptance and global-best update rates.

## 6.1 Dependency closure and preservation invariant

Represent a feasible incumbent by station variables y_s (closed/SABS/DABS), target ownership z_is, drone ownership u_id, and trip-route variables x_idrk. For a proposed move m, let S0(m), T0(m), D0(m), and R0(m) be the directly edited stations, targets, drones and trips.

Define a dependency closure C(m) as the least fixed point of the following expansion:
1. include every station whose type or open/closed state changes;
2. include every target whose station or drone ownership changes;
3. include the source and receiving stations of every moved target;
4. include every drone and trip containing a moved target;
5. when a changed station type invalidates a target's current owner, include every currently open station that is a feasible receiver for that target, plus the receiver drone/trip subproblem;
6. repeat until no new target, station, drone or trip is introduced.

A scoped repair is valid only if it preserves all variables outside C(m):
(y_s, z_is, u_id, x_idrk) after = (y_s, z_is, u_id, x_idrk) before
for every station/target/drone/trip component outside C(m).

This is a preservation invariant, not a claim that the candidate is globally feasible. After local repair, the entire candidate must still pass global coverage, unique-service, station-duration, energy/return and objective validation.

The current implementation represents an approximation to C(m) through Move.station_mask, Move.drone_mask, Move.ids, Move.kinds, Move.stages and Move.polish. It does not yet materialize a general fixed-point closure object. Therefore the paper may claim scoped repair and empirically measured preservation only for operators whose masks and tests establish it. The full-reconstruction comparison is required to quantify the quality/efficiency trade-off.

## 7. Reward and SMDP

The current reward schema remains best-cost-improvement-v1, with complete objective cost change, time-normalized search cost and a global-best signal. Each transition also records elapsed operator duration. PPO uses elapsed-time discounts in GAE.

Do not equate:
- candidate generated;
- candidate feasible;
- candidate accepted;
- current incumbent improved;
- global best improved.

These are separate counters and separate signals. Reward ablations must compare pre-registered alternatives on validation only.

## 8. Candidate research contributions (not established)

Potential contributions to test:
1. LRPHSD-specific cross-layer operator portfolio spanning station type, target assignment, SD/LD allocation and multi-trip routes.
2. Affected-subproblem repair that updates only the dependency closure of a station/assignment change.
3. A feasibility-aware operator-level controller choosing cross-layer actions from the state of this coupled structure.
4. Cross-scale generalization across station counts, target counts and geometric distributions.

None is novel merely because it is implemented. The literature already contains RL-guided neighborhood selection, RL-guided location-routing, composite location-routing neighborhoods and station-based drone inspection models. Novelty requires a demonstrated mechanism and evidence beyond these precedents.
