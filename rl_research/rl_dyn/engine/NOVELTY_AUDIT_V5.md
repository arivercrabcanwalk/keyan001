# CA-RL-TSALNS v5 — Preliminary novelty audit

Date: 2026-10-31  
Scope: public literature search on RL-guided location-routing, UAV station/dock location and patrol routing, heterogeneous multi-drone routing, and learning-guided ALNS. This is a preliminary screening, not a claim that the literature review is exhaustive.

## Executive conclusion

The broad research claims are already occupied:

- RL for a location-routing problem is not new: RLHEA (Computers & Operations Research, 2024) combines facility location with multi-depot cumulative capacitated vehicle routing and uses Q-learning to choose VND neighborhood order.
- Joint UAV station placement and UAV routing is not new: the fixed automated station (FAS) urban cruising problem (Transportation Research Part A, 2024) jointly optimizes station locations and UAV routes with coverage, power and charging constraints.
- RL for UAV dock placement plus patrol routing is not new: Gao, Ye and Zhou (Transportation Research Part E, 2026) use distributed MARL for dock siting followed by time-space-network patrol/charging optimization.
- RL-guided ALNS / destroy-repair selection for multi-drone routing is not new: QL-IPSO-ALNS (Journal of Industrial Information Integration, 2026) and Q-HGALNS (Systems, 2026) use Q-learning for adaptive neighborhood or destroy-repair selection.
- BC followed by RL for heterogeneous fixed/mobile drone delivery coordination is also not new: Bi et al. (Transportation Research Part C, 2026) propose MIP-BC-TD3.

Therefore, CA-RL-TSALNS must not claim to be the first RL location-routing method, first RL UAV station-location method, first RL-guided ALNS for heterogeneous drones, or first BC+RL fixed-station drone system.

The potentially defensible contribution is narrower and problem-specific: a coupling-aware, cross-level neighborhood system for the LRPHSD structure in Liu et al. (2026), explicitly integrating station type decisions (SABS/DABS), coverage-feasible target ownership, SD/LD fleet assignment, battery/return feasibility, and multi-trip routes; plus a controller that allocates search effort using these structural features and hard action masks. This distinction still requires full-text comparison and experimental proof.

## Literature comparison

| Work | Problem and decisions | Learning/search role | Overlap with CA-RL-TSALNS | Important difference / gap |
|---|---|---|---|---|
| Liu, Hu & Cheng (2026), EJOR 334(1), 285–300, “Drone station location and routing optimization for infrastructure inspection” | LRPHSD: choose station locations and types; SABS serves one drone, DABS supports two heterogeneous drones; construct multi-trip routes; minimize total cost | Two-stage adaptive large neighborhood search (TSALNS), no RL in the original method | Defines our target problem and exact constraints | Original baseline is non-RL; our extension must preserve its model and demonstrate gains without changing the problem |
| Zou, Hao & Wu (2024), Computers & Operations Research 170, 106758, DOI 10.1016/j.cor.2024.106758, “A reinforcement learning guided hybrid evolutionary algorithm for the latency location routing problem” | Latency location-routing combines facility location and multi-depot cumulative capacitated VRP; homogeneous vehicles and depot selection | RLHEA: Q-learning chooses the order of seven VND neighborhoods; MPEAX crossover; strategic oscillation | Direct prior art for RL-guided location-routing and learning neighborhood order | No heterogeneous drones, battery/return constraints, station types, or multi-trip SD/LD fleet coupling; RL state is the set of already-explored neighborhoods, not a structural station-drone-target encoder |
| “Fixed Automated stations location and UAVs routing problems in urban road Networks: A tailored Branch-&-price algorithm” (2024), Transportation Research Part A 189, 104201, DOI 10.1016/j.tra.2024.104201 | Jointly deploy fixed automated stations and route homogeneous UAVs over an urban road network; signal coverage, power and charging constraints; UAV may land/recharge at a different FAS | Exact/integer optimization with tailored branch-and-price, no RL | Direct prior art for coupled UAV station siting, coverage, charging and routing | Homogeneous UAVs; urban road cruising/full road coverage rather than LRPHSD target inspection, SABS/DABS type choice and heterogeneous SD/LD multi-trip routing |
| Gao, Ye & Zhou (2026), Transportation Research Part E 212, 104928, DOI 10.1016/j.tre.2026.104928, “UAV charging dock location and patrol path planning under epistemic uncertainty using distributed reinforcement learning” | UAV charging dock placement at tower-based signal stations plus patrol/charging schedule | Two-stage: independent station agents use DMARL to decide dock installation; a time-space network then optimizes travel, patrol and charging; adaptive weighted round-robin controls patrol frequencies | Direct prior art for RL-based UAV dock siting and patrol routing | The abstract describes a two-stage deployment-then-routing architecture, not a single RL-controlled cross-layer ALNS; no evidence in the abstract of SABS/DABS, SD/LD reassignment, or multi-trip route reconstruction. Full text must be checked |
| Kou et al. (2026), Journal of Industrial Information Integration, 101224, DOI 10.1016/j.jii.2026.101224, “A Q-learning based Hybrid Heuristic Algorithm for Multi-Truck and Multi-Drone Routing Problem in Post-Disaster Relief Distribution” | Multi-truck/multi-drone coordination, direct vs drone service, drone launch/recovery, payload/endurance, synchronization and urgency-aware deadlines | QL-IPSO-ALNS combines IPSO, ALNS and Q-learning adaptive operator selection | Direct prior art for Q-learning-controlled ALNS in multi-drone resource allocation and routing | Truck-carried drones and disaster delivery; the abstract does not describe fixed station siting, SABS/DABS type choice, or LRPHSD's station coverage decisions |
| “Q-Learning-Driven Adaptive Operator Selection in an Adaptive Large Neighborhood Search for Multi-Truck–Multi-Drone Cooperative Delivery Routing” (2026), Systems 14(10), 1289, DOI 10.3390/systems14101289 | Multi-truck/multi-drone delivery with payload, endurance, synchronization, battery swapping and soft time windows | Q-HGALNS: state-dependent Q-learning selects among 12 destroy-repair action combinations; shared decoder/cost evaluator; annealing and restart | Very direct prior art for Q-learning selection among destroy-repair macro-actions in multi-drone routing | Delivery routing rather than station-location LRPHSD; no demonstrated SABS/DABS siting and coverage-aware station-type decisions in the abstract |
| Bi et al. (2026), Transportation Research Part C 191, 105857, DOI 10.1016/j.trc.2026.105857, “Coordinated drone delivery via hybrid training: From optimization to reinforcement learning” | Hybrid architecture of fixed drone stations, mobile trucks and supply trucks; heterogeneous agents allocate dynamic orders | MIP generates expert trajectories, BC transfers to distributed policies, TD3 fine-tunes for stochastic demand | Direct prior art for MIP/BC/RL hybrid training in a fixed-station and heterogeneous drone logistics system | Dynamic last-mile delivery and mobile-truck coordination; the abstract does not establish LRPHSD's station siting/type choice and multi-trip infrastructure inspection structure |
| Mara et al. (2026), International Journal of Production Research 64(4), 1514–1540, DOI 10.1080/00207543.2025.2609948, “A decomposition-based evolutionary algorithm for drone-assisted electric routing problem with drone stations” | Integrated EV, drone and drone-station routing; drone-as-a-service; minimize makespan | Decomposition-based evolutionary algorithm, no RL | Non-RL prior art for integrated drone-station routing and third-party drone resources | Different EV/tandem delivery setting; no stated SABS/DABS and heterogeneous SD/LD multi-trip inspection |
| Zang et al. (2026), Drones 10(6), 414, DOI 10.3390/drones10060414, “Hierarchical Reinforcement Learning for Large-Scale Heterogeneous UAV Mission Planning via MCTS and Transformer” | Heterogeneous UAV task allocation and individual routes under payload and flight-range constraints | Hierarchical DRL: MCTS-guided upper-level workload allocation and Transformer lower-level route generation | Prior art for heterogeneous UAV allocation/routing and hierarchical RL | No fixed station location/type optimization or LRPHSD station coverage/charging structure |
| Liu, Zhu & Zhang, “Heterogeneous drone-truck routing problem with En-route operations” (TRE article 105114; issue listing indicates November 2026) | Heterogeneous drones, multi-visit sorties, en-route launch/recovery and payload-dependent energy | RLD-ALNS: DQN selects destruction operators/intensities; MLP proxy screens feasibility | Highly relevant emerging work for RL-guided ALNS and heterogeneous multi-visit drone routing | No fixed station siting in the abstract. Publication/online date should be verified relative to 2026-10-31 before treating it as an already published paper |

## RLHEA (2024) details that matter

The full paper was inspected. Its Q-learning mechanism is more than generic operator selection:

- State: the set of neighborhood structures already explored during the current VND pass.
- Action: choose one of the remaining neighborhoods not yet explored (a dynamic action set).
- Policy: epsilon-greedy Q-learning.
- Reward: immediate improvement in the current solution, plus a global-best bonus that increases when a new best is found later in the neighborhood sequence; historical rewards are discounted.
- Neighborhoods: relocate, swap (including depot swap), 2-opt/2-opt*, 2-relocate, node-arc swap, arc-arc swap, and Swap*.
- Search can enter infeasible regions under a dynamically adjusted penalty (strategic oscillation).

Implication: our action mask and best-improvement bonus are not novel in isolation. The differentiator must be the LRPHSD-specific coupling state, station/target/drone/trip joint operators, explicit resource/coverage feasibility, runtime-aware reward, and proof that PPO adds value over a strong non-RL controller and a Q-learning baseline.

## Recommended claim boundary

### Do not claim
1. First RL for location-routing.
2. First RL for UAV station/dock placement plus routing.
3. First RL-guided ALNS for multi-drone routing.
4. First BC+RL framework for fixed-station heterogeneous drone delivery.
5. Novelty merely because PPO chooses one of 17 operators or 51 operator-intensity actions.

### Potentially defensible if experiments support it
1. A problem-specific cross-level neighborhood family for simultaneous station-type change, coverage-feasible target transfer, SD/LD reassignment and affected multi-trip route reconstruction in LRPHSD.
2. A coupling-aware state representation that preserves station-target-drone-trip relationships rather than only aggregate search statistics.
3. A feasibility-aware macro-action controller with explicit action masks and time-sensitive reward, tested against fixed, adaptive-weight, rule-based, contextual-bandit, Q-learning and strong joint-search controls.
4. An empirical result that local affected-subproblem reconstruction is better than full reconstruction in identifiable operation/scale regimes. Current 508-proposal evidence does not establish this; local repair was slower and had no significant overall cost advantage.
5. A robust cross-scale gain on held-out LRPHSD instances, with the same candidate operators and wall-clock budget, if the final validation and locked tests confirm it.

## Required follow-up before any novelty statement

- Obtain and read the full text of Gao et al. 2026, Kou et al. 2026, Q-HGALNS 2026, and Bi et al. 2026; abstracts alone are insufficient for a definitive difference claim.
- Add RLHEA (2024) as a direct prior-art comparator or reproduce its Q-learning neighborhood-order principle in our solver.
- Add QL-IPSO-ALNS / Q-HGALNS-style Q-learning destroy-repair selection as a strong baseline where the problem mapping is fair.
- Compare against the 2024 FAS branch-and-price and 2026 drone-station evolutionary methods conceptually and, where possible, on compatible subproblems.
- Search the exact LRPHSD and related heterogeneous UAV station-location literature again before paper submission.
- Do not make any CCF-B acceptance promise; contribution strength and venue fit depend on final evidence.

## Source links / identifiers

- RLHEA 2024: https://doi.org/10.1016/j.cor.2024.106758
- FAS station-location and UAV routing 2024: https://doi.org/10.1016/j.tra.2024.104201
- Gao et al. 2026 DMARL dock placement: https://doi.org/10.1016/j.tre.2026.104928
- QL-IPSO-ALNS 2026: https://doi.org/10.1016/j.jii.2026.101224
- Q-HGALNS 2026: https://doi.org/10.3390/systems14101289
- MIP-BC-TD3 2026: https://doi.org/10.1016/j.trc.2026.105857
- Drone-assisted EV routing with stations 2026: https://doi.org/10.1080/00207543.2025.2609948
- Heterogeneous UAV mission planning 2026: https://doi.org/10.3390/drones10060414
- Emerging HDTRP-ELR: https://doi.org/10.1016/j.tre.2026.105114
