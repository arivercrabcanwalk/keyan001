# G24 Design and Literature Audit: Time-Windowed No-Fly Zones

**Date:** 2026-11-04  
**Scope:** an online-first, primary-source literature and design audit for the existing `g24_weather_nfz` engineering fixture. This document proposes no new method, reports no quality result, and changes no historical G0--G8 decision.

## Decision

**Prioritize a deterministic, pre-announced temporary no-fly zone (NFZ), not an emergency-task arrival process.**

This is a modelling choice, not a novelty claim. The existing G24 action contract already lets the policy choose only a physical next target or `RETURN`; its weather/NFZ oracle changes the time, energy, and legality of those physical legs. An emergency-task process instead changes the target set and introduces release time, priority, deadline, cancellation, and possible pre-emption semantics. The latter is a different online scheduling problem, absent from the current state, action contract, replay format, and primary endpoint.

The narrow claim supportable after this audit is:

> A fixed-deployment, route-construction experiment can test whether a direct target/`RETURN` policy responds to **known scheduled airspace closures and forecast wind** under the same deterministic route oracle as every comparator.

It cannot claim that temporary NFZs, wind-aware UAV routing, target/`RETURN` decoding, feasibility masking, PPO, A2C, MTC, or any combination of those ingredients is new.

## Online Primary Sources

The table distinguishes sources whose full primary text was inspected from sources for which only publisher/Crossref metadata and an abstract were available. It does not infer omitted model features from unavailable text.

| Source | Access and inspected evidence | What it establishes | Limit for G24 |
|---|---|---|---|
| Liu, Hu & Cheng, *EJOR* 334 (2026), 285--300, DOI [10.1016/j.ejor.2026.04.046](https://doi.org/10.1016/j.ejor.2026.04.046), [author manuscript](https://optimization-online.org/wp-content/uploads/2025/08/LRPHSD.pdf) | Full author manuscript inspected; local formal PDF is `audit/papers/Liu2026.pdf`. Section 3 defines fixed arc time `t_ij`, fixed inspection time, multi-trip return/swap, fixed station/drone cost, SABS/DABS and SD/LD. | LRPHSD jointly contains station location/type, target assignment, multi-trip routing, return, per-trip energy and station-duration constraints. | Its arc parameters are static; it does not instantiate a timed wind field or a timed NFZ. It is the parent problem, not a weather/NFZ baseline. |
| Thibbotuwawa, Bocewicz, Radzki, Nielsen & Banaszak, “UAV Mission Planning Resistant to Weather Uncertainty,” *Sensors* 20(2), 515 (2020), DOI [10.3390/s20020515](https://doi.org/10.3390/s20020515), [author-hosted version of record](https://vbn.aau.dk/ws/files/406320703/sensors_20_00515_v2.pdf) | Full publisher PDF inspected from Aalborg University’s repository. It explicitly treats forecast weather as known time windows, with a wind-speed/direction vector per window; wind changes reachability and energy. | Wind-conditioned mission planning, energy/range effects, and forecast time windows are established. | Its model assumes a route starts and ends within a flying weather window. G24 integrates a leg across wind knots, so it is not a reproduction or numerical comparator. Neither source validates G24’s abstract energy scale. |
| Jia, Liu, Wang, Wang & Wang, “Time-dependent vehicle--UAV path optimization for urban dynamic traffic restriction and no-fly zone” (Research Square preprint, 2025), DOI [10.21203/rs.3.rs-7807942/v1](https://doi.org/10.21203/rs.3.rs-7807942/v1), [primary PDF](https://www.researchsquare.com/article/rs-7807942/latest.pdf) | Full posted manuscript inspected. It specifies NFZ restricted periods, detouring an UAV along a zone edge while active, and direct cooperation when the restriction is inactive; it also models time-dependent traffic, truck/UAV cooperation, delivery deadlines and a composite cost. | Timed NFZ activation and detour routing are already present in a public, original model. | It is a truck--drone delivery MILP/heuristic preprint, not fixed-station power inspection, direct RL, `M_return`, or a fair numerical comparator. It has rectangular edge-tracking detours; G24 currently uses a strictly convex buffered polygon and a visibility graph. |
| Wei, Fan, Ren & Diao, “Time-Dependent Vehicle Routing Problem with Drones Under Vehicle Restricted Zones and No-Fly Zones,” *Applied Sciences* 15(4), 2207 (2025), DOI [10.3390/app15042207](https://doi.org/10.3390/app15042207) | Publisher/Crossref record and its official abstract inspected. The publisher PDF endpoint was not retrievable in this session. | The official abstract states that vehicle-restricted zones, NFZs, time-dependent road networks and detour rules jointly change costs/plans. | It is only title/abstract-level support here. Do not use it to claim a specific NFZ activation or RL mechanism, and do not count it as independent proof beyond the Jia preprint without a full-text comparison. |
| Mao & Jia, “Research on the optimization of delivery routes for vehicles with drones under no-fly zone restrictions,” *PLOS ONE* 20(10), e0335614 (2025), DOI [10.1371/journal.pone.0335614](https://doi.org/10.1371/journal.pone.0335614), [official full text](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0335614&type=printable) | Full publisher PDF inspected. It has no-fly-zone restrictions, multi-objective delivery planning, and multiple customers per UAV subject to endurance. | NFZ-constrained UAV routing is established even apart from timed-NFZ work. | Its NFZ customers are assigned to vehicles, rather than flying a timed detour around an active zone. It is not evidence for a temporary zone, wind, or inspection-route RL. |
| Sun, Gao, Xue & Yu, “Deep reinforcement learning for periodic UAV task allocation and path planning with a Fixed Nest Station in power inspection,” *Engineering Applications of Artificial Intelligence* 179, 115219 (2026), DOI [10.1016/j.engappai.2026.115219](https://doi.org/10.1016/j.engappai.2026.115219) | Full local formal PDF inspected (`audit/papers/DPTARL.pdf`); DOI/publisher record also checked. It has a fixed nest, visit/return route construction, action pruning under endurance/periodicity, attention, actor-critic training, and ALNS/PPO/DQN comparisons. | Direct target/return construction, feasibility pruning and route-RL comparison are existing inspection-RL ingredients. | Its periodic single-nest task allocation problem, linear time energy and daily sortie convention differ from fixed-outer LRPHSD. No weather, timed NFZ, online emergency arrival or original-LRPHSD cost cap is instantiated. |
| Fei, Liu, Bao, Zhu & Zou, “RISE: Rolling-Inspired Scheduling for Emergency Tasks by Heterogeneous UAVs,” *Drones* 6(10), 310 (2022), DOI [10.3390/drones6100310](https://doi.org/10.3390/drones6100310) | Official Crossref metadata and abstract inspected; publisher full PDF was unavailable to this session. The abstract specifies dynamic task arrival, heterogeneity, task grouping, deadlines and rolling optimization. | Emergency UAV work makes task-arrival/priority/deadline/rolling allocation a first-class problem. | This is exactly why emergency tasks should not be silently folded into G24: the required state, objective, comparator and information model differ. No full-text negative claim is made. |
| Schulman et al., “Proximal Policy Optimization Algorithms” (2017), [arXiv:1707.06347](https://arxiv.org/abs/1707.06347); Mnih et al., “Asynchronous Methods for Deep Reinforcement Learning” (ICML 2016), [PMLR](https://proceedings.mlr.press/v48/mniha16.html); Achiam et al., “Constrained Policy Optimization” (ICML 2017), [PMLR](https://proceedings.mlr.press/v70/achiam17a.html) | Primary public records and abstracts inspected. PPO is a generic sampled-policy surrogate method; A2C is the conventional synchronous actor-critic counterpart to A3C-style actor-critic; CPO formulates policy search with expected constraints. | PPO/A2C/CPO are algorithmic controls, not a contribution supplied by their use. | CPO’s CMDP/expected-cost framing does not remove the need for per-output route replay, hard action masking, and a full-map cap validator. It is not a substitute for an exact legal-route evaluator. |

### Retrieval boundary

No official author code was located for the cited timed-NFZ, weather, or emergency-task papers in this retrieval. Therefore this audit does **not** state that no code exists. The inspected G24 code is the only implementation basis for G24-specific claims.

## Why Temporary NFZ Is the Correct First Extension

### Fit to existing action semantics

`WeatherRouteEnv` exposes `RouteAction(target_id)` and `RouteAction()` only. The first is an immediate commitment to a physical target; the second is physical return to the launching station. It explicitly excludes operator/search/budget decisions ([`weather_env.py:84`](weather_env.py:84)). A scheduled NFZ makes one of those candidate legs illegal or longer at its departure time, so it can enter the candidate projection, action mask, and deterministic replay without inventing another decision class.

The current implementation already contains the required minimal primitives:

- A known piecewise-constant vector wind field with strictly increasing knots ([`weather_oracle.py:40`](weather_oracle.py:40)).
- One strictly convex, caller-buffered NFZ active on the half-open interval `[on_s, off_s)` ([`weather_oracle.py:96`](weather_oracle.py:96)).
- Departure-time-specific leg integration across wind changes ([`weather_oracle.py:209`](weather_oracle.py:209)).
- A finite endpoint/vertex visibility oracle that rejects positive-length active-zone interior overlap ([`weather_oracle.py:277`](weather_oracle.py:277)).
- An action mask which checks projected arrival, service, return-to-station energy, cumulative duty, and a necessary cost bound ([`weather_env.py:147`](weather_env.py:147)).
- A full trip replay that independently reconstructs legs, energy, duty, cost, MTC and `M_return` ([`weather_env.py:362`](weather_env.py:362)).

### Why emergency tasks are not equivalent

An emergency-task experiment must freeze, at minimum: a release-time process; the spatial/energy/service attributes of each arriving task; priority or penalty; deadline; cancellation; whether an in-progress trip may divert; and the exact online observation available when the task arrives. It then needs a rolling non-RL comparator and a primary score that includes the old and newly arrived demand. G24 begins with the complete static task set at `reset` ([`weather_env.py:106`](weather_env.py:106)); it has none of those variables.

Conflating the two changes would wrongly attribute any effect to route RL when it could arise from task admission, scheduling priority or changing denominator/endpoint. A future emergency branch can use a four-cell design (static; NFZ only; arrivals only; both), but it needs its own registered problem and evaluator.

## Exact Difference From LRPHSD and the Existing Route Study

| Dimension | LRPHSD / approved route study | Current G24 fixture | Consequence |
|---|---|---|---|
| Outer decisions | Liu jointly defines station site/type, target ownership and SD/LD routing. The approved route study fixes outer deployment/ownership. | One station and one execution slot. | G24 cannot stand in for the multi-station, heterogeneous, parallel physical system. |
| Movement time | Liu gives a fixed arc travel time `t_ij`; no departure-time weather function is part of the base model. | Time depends on direction and departure time under a uniform, piecewise-constant vector wind. | A weather experiment must apply the same oracle to every method; it cannot reuse static-LRPHSD results as weather scores. |
| Airspace | No timed-NFZ primitive is present in the base LRPHSD model. | One buffered strictly convex polygon and known activation interval. The oracle chooses a legal visibility-graph detour, not the policy. | This is a narrow environmental extension. It is not general 3D path planning, multi-NFZ air traffic management, or a trajectory-learning contribution. |
| Policy action | Project rule: physical `(slot, target)` or `(slot, RETURN)` only. | Physical `(target)` or `RETURN` only. Waypoint selection is delegated to the common deterministic oracle. | The RL does not select a path-search operator or a geometric detour algorithm. All controls must receive the same oracle. |
| Time/turnaround | Approved main study uses physical parallel slots and sequential trips per machine, zero turnaround. | Sequential trips of one aircraft, zero ground turnaround. | Single-slot `M_return` is cumulative duty, not full-map maximum return time. |
| Energy | Liu has per-trip battery and station work-duration structure. | `flight_energy * flight_minutes` plus static target service energy; parameters are explicitly uncalibrated. | Do not represent the fixture as aircraft-calibrated or use it to state wind-power/energy realism. |
| Endpoint and cap | Current approved primary endpoint is full-map `M_return`, under original hard constraints and `C <= C_ref + 1e-7`. | Training reward sums to `-MTC`; smoke cap is `1.25 *` nearest-route synthetic reference. | Neither MTC smoke result nor a 25% synthetic cap answers the approved `M_return`, epsilon-zero question. |
| Information | Any future uncertainty study must separate policy forecast information from realized evaluator information. | Forecast/schedule is deterministic and the oracle sees it for projected actions. | Call it **known forecast / scheduled-closure planning**, never uncertainty robustness or surprise re-planning. |
| Waiting | No latent wait should exist in a direct route policy. | The oracle never inserts `WAIT` or a cycle ([`weather_oracle.py:9`](weather_oracle.py:9)). | A scenario where waiting is necessary is outside current G24 semantics; do not silently make it feasible. |

## Required Experimental Contract Before Any Registered Run

### 1. Freeze the scope as deterministic scheduled closures

For each instance, freeze: target/station/slot identifiers; the forecast wind knots; NFZ vertices after buffering; `[on_s, off_s)`; aircraft/energy parameters; reference solution; source and generator hashes; and the seed. The policy may see exactly the pre-announced forecast/schedule that every non-RL comparator may see. A newly announced or stochastic closure is a different information model and requires a new protocol.

### 2. Preserve the direct physical action domain

In the eventual fixed-outer multi-slot environment the action must remain `(slot, target)` or `(slot, RETURN)`. A deterministic oracle may transform an endpoint-to-endpoint leg into its allowed polyline. It must not expose or learn a selector for an operator, neighbourhood, repair strength, solver family, or wall-clock allocation.

### 3. Handle the absence of `WAIT` honestly

The fixture's no-wait design is valid only in a restricted data regime. Before accepting an episode, the generator/replay must establish that every intended feasible witness can complete with immediate leg departure or an available geometric detour. Any candidate that becomes feasible only by holding until an NFZ expires is outside this contract and must be recorded as such, not repaired by hidden waiting.

Adding explicit `WAIT` is possible only as a new **physical** action, with new mask/replay/control tests and a re-frozen comparator class. It must not be hidden inside `plan_route` or treated as zero-cost.

### 4. Make replay authority independent enough for the claim

The existing `replay_trips` is a necessary second execution path, but it calls the same `plan_route` oracle. Before research results, add an evaluator-level check that independently verifies: each segment's time interval; polygon interior/time overlap; wind-knot integration; energy; route closure; target coverage; station/slot concurrency; and original full-map cost/`M_return`. The original evaluator remains authoritative for unchanged LRPHSD semantics; the weather extension needs a separately versioned evaluator contract.

### 5. Keep the primary endpoint and cost protection

The G24 `MTC` reward may be retained only as a development/secondary descriptive statistic. Registered quality results must be scored by the approved full-map `M_return` after all returns, with the original hard constraints and a common epsilon-zero cap. A policy must never obtain a better endpoint simply by changing the metric, discarding a failed map, or reverting to a synthetic 25% allowance.

### 6. Test minimal temporal and geometric boundary cases

Required before map-level comparison:

1. Leg enters before the NFZ opens, while inside, and after it closes.
2. Exact `on_s` and `off_s` half-open boundary behavior.
3. Tangency and polygon-boundary following.
4. Crosswind-infeasible and non-positive along-track progress.
5. Wind-knot crossed during a leg.
6. NFZ makes a direct leg illegal but a visibility detour legal.
7. The no-wait counterexample, classified as out of scope rather than silently delayed.
8. Full return, battery, duty, cost-cap and target-exact-once replay on a multi-trip witness.

### 7. Do not estimate flight physics from the smoke fixture

The default `900 m/min` speed and abstract energy-per-minute parameter are intentionally uncalibrated ([`weather_oracle.py:79`](weather_oracle.py:79)). A real-region/real-aircraft claim needs separately frozen, citable weather observations, aircraft performance/energy data, buffer policy, and uncertainty/risk model. These values cannot be back-filled from smoke outcomes.

## PPO, A2C, CPO, and Non-RL Comparison Design

### Algorithm decision

**Use PPO and synchronous A2C as equal-footing route-policy controls only.** Both fit the fixed, variable-size masked discrete physical action list. Neither is selected as the research method in advance. DPTARL makes target/return pruning and actor-critic a direct inspection precedent; the historical Route-RL PPO Stage A remains a negative result and is not a licence to retry the same problem under a new name.

**CPO is optional, not a replacement for hard feasibility.** Its expected-constraint machinery can become a diagnostic comparator only after a fully specified constrained-MDP objective and equal compute plan exist. It cannot discharge the requirements for a hard route mask, terminal replay, complete solution, and full-map cost cap.

### Minimum comparison ladder

1. **Oracle-free regression:** original static evaluator/route study unchanged, with V6/semfix artifacts preserved.
2. **Common-oracle non-learning controls:** random legal; nearest legal; deterministic greedy; beam; and a no-learning myopic construction. Each sees the same forecast/NFZ fields, action legality and detour oracle as RL.
3. **Strong same-objective non-RL:** fixed-outer joint multi-trip route method adapted to the timed oracle, including route order, trip partition and legal slot-target decisions; small-domain DP/exhaustive reference where tractable. It must be stronger than the synthetic nearest neighbour.
4. **Route-RL controls:** ordinary masked PPO and ordinary masked synchronous A2C, each with at least three independently trained seeds, fixed checkpoint selection and the same policy information/action domain. If another mechanism is proposed later, it must beat these controls and the strong non-RL family under the frozen protocol.

For every method, charge: oracle computation; feature generation; model loading; inference/decoding; search/beam; validation; defensive fallback; and failures. Keep every map in the denominator. A fallback can make a final output legal but cannot erase the source method's failure, cost, time, or pre-fallback endpoint.

## Explicit Non-Claims

This audit does not support any of the following:

- first use of temporal NFZs, NFZ detours, or weather-aware UAV routing;
- first RL for target/`RETURN` route construction, feasibility masks, pointer/attention, PPO, or A2C;
- aircraft-calibrated wind, energy, airspace, safety, or real-flight validity;
- superiority of PPO, A2C, CPO, or any learned policy;
- an LRPHSD quality result, a strong-baseline comparison, a G3/G4 admission, or a Formal result;
- an online emergency-task claim; or
- a new algorithmic contribution from placing an existing method in a weather/NFZ fixture.

## Implementation Status and Next Gate

The current package is appropriately an isolated engineering fixture. Its own documentation already labels the smoke case as synthetic and excludes G3/G4/G5 admission ([`README.md:29`](README.md:29), [`EXPERIMENT_PROTOCOL.md:24`](EXPERIMENT_PROTOCOL.md:24)). The smoke configuration uses MTC and a 25% exploration allowance, so it remains a software integration test only.

The next legitimate work is not new PPO/A2C training. It is a G0/G1 design freeze: select the primary `M_return`/epsilon-zero formulation already recorded by the project; define the deterministic scheduled-NFZ information/evaluator contract; integrate it at the fixed-outer multi-slot physical level; and complete the boundary, replay and common-oracle controls above. Only the separate G2/G3 gates can establish opportunity and a strong same-objective non-RL reference before any G4 training decision.

