# Liu/LRPHSD Route-RL Context (English)

## Research question

The project studies whether RL can directly construct physical UAV routes in the Liu/LRPHSD multi-station, heterogeneous-fleet, multi-trip setting while keeping each map's cost no higher than the Liu author anchor. The policy may output only the next target or RETURN. It may not select search operators, neighborhoods, destroy/repair, algorithm families, operator intensity or repair budgets.

Deployment, station type, target assignment, exact-once service, trip return, energy/time feasibility and cumulative-duty rules are fixed for the conditional route study. An end-to-end TSALNS claim would require a separate frozen outer-loop comparison.

## Established evidence

The Liu/SEMFiX reproduction covers 120 official maps, five seeds, P1/P2 settings and 1,200 paired runs; all were feasible and independently audited. Exact details are in `analysis_docs/SEMFiX_FULL_RESULTS.md`.

The engineering package implements/tests weather, no-fly zones, dynamic emergency tasks, release times, deadlines, heterogeneous vehicles, multi-trip routes, cumulative duty, independent replay, relational encoders, LOO, SCST, PPO, A2C, discrete SAC, DQN, VFA, behavior cloning, beam and complete-rollout controls.

## Current negative result

The strongest registered non-RL development method, `oldbeam`, has mean `J=1169.612132`; SCST/LOO has `J=1188.621808`, 1.6253% worse, losing on 8/8 development maps. All six SCST/LOO actor seeds selected the initial policy. Some DQN seeds improved over their own initial checkpoint, but none beat the strongest non-RL comparison. A multi-objective review also found higher hypervolume for the complete non-RL candidate combination than for the RL combination.

The honest conclusion is high-fidelity baseline reproduction plus an unfinished/negative route-RL result, not a positive RL superiority claim.

## Gate status

G0 novelty is not passed; G1 engineering contracts are passed; G2 is limited to opportunity diagnostics; G3 strongest-non-RL qualification is not passed; G4 RL superiority is not passed; G5-G8 are not started.

Do not turn engineering admission tests, training logs, auxiliary service metrics or an author adapter into a scientific advantage.
