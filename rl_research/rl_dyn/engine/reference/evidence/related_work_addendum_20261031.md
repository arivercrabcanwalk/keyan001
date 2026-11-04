## 4. Additional late-2026 RL-ALNS competitors found in a second search pass

### Fan et al. (2026), Systems 14(10), 1289
“Q-Learning-Driven Adaptive Operator Selection in an Adaptive Large Neighborhood Search for Multi-Truck–Multi-Drone Cooperative Delivery Routing.”
DOI: 10.3390/systems14101289.
- Q-HGALNS uses Q-learning to select among 12 state-dependent destroy–repair actions for coupled multi-truck/multi-drone routing, with payload, endurance, synchronization and battery-swapping constraints.
- Its discrete state combines search phase, recent improvement status and time-window pressure; its 12 actions are the Cartesian product of four destroy and three repair operators. This is a direct precedent for a state-dependent Q-learning ALNS controller.
- Its reported ablation compares against ALNS-AW; the complete algorithm's overall mean cost is 0.678% lower than ALNS-AW. This is particularly important: it already compares Q-learning with an adaptive-weight non-RL controller, as we must.
- It reports 12 Solomon-derived scenario groups with 30/50/100 customers. The paper explicitly says prior RL work already focused on neighborhood/operator selection.
- Distinction to test: our v5 has a 75-feature coupling state and 17 explicit LRPHSD macro-neighborhood types, including station open/close/type changes, cross-station assignment, SD/LD ownership changes, cross-drone/trip exchanges and combined station/assignment/route changes. It still delegates exact target/station subset selection to the operator-specific generator, so it is not a low-level target-selection policy.
- Distinction to investigate: truck–drone cooperative delivery and sortie synchronization versus fixed LRPHSD station candidates, SABS/DABS station types, one SD plus one LD at DABS, station operating-duration and multi-trip inspection routes.
- Search record: https://www.mdpi.com/2079-8954/14/10/1289

### QL-IPSO-ALNS (2026), post-disaster multi-truck/multi-drone relief routing
“A Q-learning based Hybrid Heuristic Algorithm for Multi-Truck and Multi-Drone Routing Problem in Post-Disaster Relief Distribution.”
- Available online 5 October 2026 in Journal of Industrial Information Integration (article 101224; authors Xiaofei Kou, Tianlong Liu, Hao Liu, Gangyan Xu and Peng Sun).
- Combines improved particle swarm optimization, ALNS and Q-learning-based adaptive operator selection; uses a three-layer encoding/decoding scheme and targeted destroy/repair.
- The model considers multi-truck/multi-drone relief delivery, urgency-differentiated deadlines and flexible coordination modes. It is a direct recent precedent for Q-learning-assisted ALNS in heterogeneous multi-drone routing.
- Further rules out generic claims about Q-learning-driven operator choice in multi-truck/multi-drone problems. Distinguish the relief-distribution fleet/coordination setting from fixed SABS/DABS infrastructure and LRPHSD station-duration / multi-trip inspection structure.
- Distinguishing dimensions to examine: relief priorities and deadlines, truck-drone cooperation and population-based global search versus fixed infrastructure station selection/type and station-drone multi-trip inspection.
- Search record: https://www.sciencedirect.com/science/article/abs/pii/S2452414X26001652

### ALNS-RL for satellite-assisted geohazard monitoring (2026)
“Reinforcement learning-enhanced routing for multiple unmanned aerial vehicles in satellite-assisted geohazard monitoring with emergency prioritization.”
- Multi-UAV inspection/monitoring under limited endurance and dynamic emergency priorities; ALNS enhanced with deep Q-learning for state-aware operator selection.
- This is close to the inspection application itself, so a generic claim that RL-guided ALNS is new for UAV inspection is not defensible.
- Distinguishing structure to verify: rolling-horizon task-priority updates versus station location/type, heterogeneous SD/LD station configuration and multi-trip station-based routes.
- Search record: https://www.sciencedirect.com/science/article/abs/pii/S0952197626023523

### QALNS for heterogeneous UAV emergency healthcare (2025)
“Optimizing task assignment and routing operations with a heterogeneous fleet of unmanned aerial vehicles for emergency healthcare services.”
Computers & Operations Research 174 (2025), 106890.
- Explicitly proposes QALNS, incorporating Q-learning into ALNS for task assignment and routing with heterogeneous UAV fleets.
- This is another direct precedent for learning-assisted ALNS under heterogeneous UAV assignment.
- Search record: https://www.sciencedirect.com/science/article/pii/S0305054824003629

## 5. Revised contribution filter

After these additions, the paper must not position its contribution as “Q-learning/PPO selects ALNS operators for heterogeneous UAV routing.” That mechanism is already present in multiple 2025–2026 works.

A defensible contribution requires evidence for all of the following:
- LRPHSD-specific dependency closure across fixed station type, target ownership, SD/LD ownership and multi-trip routes;
- a precise affected-subproblem repair rule with a preservation invariant and a controlled comparison against full reconstruction;
- a controller that chooses concrete cross-layer transformations rather than only a generic destroy/repair pair;
- a strong non-RL comparator at least as strong as adaptive weights, plus direct comparisons to bandit/Q-learning/PPO;
- a reproducible advantage on unseen instance structures, not merely one set of fixed-size maps.

If the results show that M2 adaptive weights or another non-RL controller matches PPO, the paper should not claim an RL-specific contribution. The joint-neighborhood/repair contribution may still be publishable, but the paper's framing and venue must change accordingly.
