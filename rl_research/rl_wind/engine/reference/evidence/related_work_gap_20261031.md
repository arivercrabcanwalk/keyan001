# Related-work and novelty-risk register (2026-10-31)

This is a first-pass external literature map, not a completed systematic review. Each paper must still be read in full before a novelty claim is finalized.

## 1. Direct LRPHSD / station-based inspection

### Liu, Hu & Cheng (2026), EJOR 334(1), 285–300
“Drone station location and routing optimization for infrastructure inspection.” DOI: 10.1016/j.ejor.2026.04.046.
- Defines LRPHSD: SABS supports one SD; DABS supports SD+LD with heterogeneous battery capacity; jointly chooses station location/type, target assignment and multi-trip routes.
- Proposes MILP and two-stage ALNS (TSALNS).
- This is the target baseline, not a novelty claim for our project.
- Publisher/repository evidence: Optimization Online preprint (2025) and EJOR publication record (2026).

### Cai et al. (2025), Omega 130, 103172
“Optimal allocation and route design for station-based drone inspection of large-scale facilities.” DOI: 10.1016/j.omega.2024.103172.
- Directly related inspection setting: station location, facility assignment, operation-duration constraints and battery-constrained drone routes.
- Abstracted problem assumes homogeneous drones / homogeneous automatic battery-swap stations.
- Uses arc- and route-based formulations, logic-based Benders decomposition, column generation and branch-and-price; solves all small/middle instances and 7/10 large instances within 1000 seconds.
- Rules out claiming that integrated station-based drone inspection location/allocation/routing itself is new.

## 2. RL-guided neighborhood search / ALNS

### Guo et al. (2025), IEEE TPAMI 47(7), 5930–5944
“Learning-Aided Neighborhood Search for Vehicle Routing Problems.” DOI: 10.1109/TPAMI.2025.3554669.
- Multi-agent RL selects perturbation/improvement operators; image-like route representation and CNN state encoder.
- Evaluated on CVRP, MDVRP and cumulative multi-depot VRP with energy constraints.
- Rules out claiming RL-guided neighborhood/operator selection for routing is new.

### GRLOS / LRW (2024), Computers & Operations Research 172, 106791
“A Graph Reinforcement Learning Framework for Neural Adaptive Large Neighbourhood Search.” DOI: 10.1016/j.cor.2024.106791.
- Formulates ALNS operator choice as an MDP.
- GRLOS uses graph RL/GNN; LRW is a learned lightweight roulette-wheel mechanism.
- Uses 28 destroy and 7 repair operators, evaluated across five routing problems and instances up to 1000 customers.
- Rules out claiming GNN-based RL operator selection, learned ALNS operator choice, or multi-problem generalization is new.

### Xiao et al. (2024), Information Sciences 679, 121068
“Adaptive large neighborhood search algorithm with reinforcement search strategy for solving extended cooperative multi task assignment problem of UAVs.” DOI: 10.1016/j.ins.2024.121068.
- Heterogeneous UAVs from multiple base stations; task precedence and time constraints.
- Reinforcement-search-assisted ALNS and tailored task adjustment destroy/repair operators.
- Rules out claiming that combining heterogeneous UAV assignment with reinforcement-guided ALNS is new in general.

### Zou, Hao & Wu (2024), Computers & Operations Research 170, 106758
“A reinforcement learning guided hybrid evolutionary algorithm for the latency location routing problem.” DOI: 10.1016/j.cor.2024.106758.
- Location-routing plus multi-depot cumulative capacitated routing.
- RL guides variable-neighborhood descent order inside a hybrid evolutionary algorithm; strategic oscillation allows feasible/infeasible search.
- Reports 51 new best-known solutions among 59 previously unknown-optimum instances.
- Rules out claiming RL-guided search for a location-routing problem is new.

### Sultana et al. (2024), Operations Research Letters 55, 107136
“Learning to guide local search optimisation for routing problems.” DOI: 10.1016/j.orl.2024.107136.
- Uses RL to allocate local-search effort across operators.
- Supports the conclusion that generic learning-to-guide-local-search is an established direction.

## 3. Composite neighborhoods / integrated location-routing

### Schneider & Löffler (2019), Transportation Science 53(1), 301–318
“Large Composite Neighborhoods for the Capacitated Location-Routing Problem.” DOI: 10.1287/trsc.2017.0770.
- Establishes large composite neighborhoods for capacitated location-routing.
- Rules out claiming composite/cross-level location-routing neighborhoods are new without a more precise distinction.

### Zheng et al. (2026), Engineering Applications of Artificial Intelligence 165, 113453
“A collaborative bi-level optimization approach for smart logistics: Depot location and unmanned aerial vehicle-based pickup-delivery services.” DOI: 10.1016/j.engappai.2025.113453.
- Multi-depot, multi-UAV location-routing under heterogeneous service types and time windows.
- Couples depot location/customer assignment with lower-level multi-UAV scheduling through iterative feedback.
- Rules out claiming feedback-coupled multi-level depot/assignment/UAV routing optimization is new in general.

## 4. Implications for our contribution

A weak story would be: “we add RL to TSALNS and select more operators.” This is not novel enough given TPAMI LaNS, COR GRLOS, Information Sciences RSALNS, COR RL-Hybrid-LRP and other learning-guided search work.

A potentially defensible narrower story is:
- LRPHSD's exact station-type / SD-LD / multi-trip coupling;
- a dependency-aware neighborhood that changes station configuration, cross-station assignment, heterogeneous drone ownership and affected multi-trip routes in one candidate;
- a repair method that recomputes the affected dependency closure while preserving unaffected subproblems;
- a controller that chooses concrete cross-layer move types based on the coupled state and whose value is demonstrated beyond strong non-RL controllers.

Even this remains a hypothesis. Proof obligations:
1. Formalize the affected dependency closure and show unaffected station subsolutions remain unchanged/feasible under each move.
2. Compare local repair with full reconstruction and existing composite LRP neighborhoods.
3. Compare RL against the same operators, masks, candidate generator, budget and tuned non-RL controllers.
4. Test unseen geometry, station counts, target counts and stress structures.
5. Verify that the operator portfolio is not merely a renamed collection of known moves.
6. Complete a full-text search for UAV inspection / heterogeneous battery-swap / multi-trip location-routing papers.

## 5. Recommendation

Continue engineering and development validation, but do not write first, novel or state-of-the-art claims yet. Narrow the contribution after full-text comparison and validation evidence. A strong OR journal may be more natural if the contribution is primarily a problem-specific matheuristic; a CCF-B+ CS venue requires a clearly generalizable learning/search mechanism and stronger evidence than a one-problem operator-selection application.
