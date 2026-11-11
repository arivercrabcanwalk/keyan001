# Current Status (evidence-bounded)

Date of exported state: 2026-11-11. This file is a compact handoff; the complete sanitized status ledger is `analysis_docs/LATEST_STATUS_SANITIZED.md`.

## What is established

- Liu/SEMFiX official implementation reproduction: 120 official maps, 5 seeds, P1/P2 configurations, 1,200 paired runs; all feasible and independently audited. P1 mean difference: -0.0284%; P2 mean difference: +0.0998%.
- The route-RL action contract is physical only: `(slot, target)` or `(slot, RETURN)`. The policy does not choose search operators, neighborhoods, destroy/repair, algorithm family, operator intensity, or repair budget. Deployment, station type, target-station assignment, and cumulative-duty rules are fixed for the conditional route study.
- Weather, no-fly-zone, dynamic emergency tasks, deadlines, release times, heterogeneous vehicles, multi-trip routes, cumulative duty, independent replay, relation encoders, LOO, SCST, PPO, A2C, discrete SAC, DQN, VFA, behavior cloning, beam and complete-rollout controls have been implemented or engineering-tested.

## What is not established

- RL superiority is not established. The best registered non-RL `oldbeam` development mean is `J=1169.612132`; SCST/LOO is `J=1188.621808`, 1.6253% worse, and all 8/8 development maps are behind.
- Six SCST/LOO actor seeds selected the initial policy. Some DQN seeds improved over their own initial policy, but none beat the strongest non-RL comparison. A historical multi-objective check also found the complete non-RL candidate combination with higher hypervolume than the RL combination.
- G0 new-mechanism novelty, G3 strongest-non-RL qualification, G4 RL superiority, G5 formal test, G6 innovation ablation, G7 paper drafting, and G8 complete research-package acceptance are not passed.

## Interpretation

The honest current conclusion is a high-fidelity reproduction plus a negative/unfinished route-RL result. Engineering admission tests and training logs are not performance evidence. Do not convert auxiliary MTC/service improvements, author adapters, or a training score into an RL or metric novelty claim.
