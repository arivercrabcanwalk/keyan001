# Results Summary

## Liu/SEMFiX reproduction

The accepted reproduction is documented in `analysis_docs/SEMFiX_FULL_RESULTS.md`. It covers 120 official maps, five seeds, P1/P2 settings and 1,200 paired runs. All runs were feasible and passed independent evaluator checks. The two headline mean gaps relative to the released reference are P1 `-0.0284%` and P2 `+0.0998%`; small residual gaps are explicitly retained rather than hidden.

## Route-level RL development

The registered objective is final return makespan `M_return` under a strict per-map author-cost cap (`candidate cost <= Liu author cost + 1e-7`), with mean target completion time (MTC) reported only as a secondary metric. The current best registered non-RL development method is `oldbeam`, mean `J=1169.612132`. The SCST/LOO route policy has mean `J=1188.621808`, which is `1.6253%` worse; it loses on 8/8 development maps. All six SCST/LOO actor seeds selected the initial policy. DQN had some within-seed gains over its own initial checkpoint but did not beat the strongest non-RL method.

The multi-objective review found higher hypervolume for the complete non-RL candidate combination than for the RL combination. Engineering passes (syntax, replay, storage, label and adapter checks) establish implementation integrity, not a scientific advantage.

## Gate status

| Gate | Status | Meaning |
|---|---|---|
| G0 | NOT PASSED | no distinct, literature-grounded new route mechanism admitted |
| G1 | ENGINEERING PASSED | bounded environment/action/replay contracts tested |
| G2 | LIMITED | opportunity diagnostics only; no population/RL inference |
| G3 | NOT PASSED | strongest same-information non-RL not fully qualified |
| G4 | NOT PASSED | no RL candidate beat the strongest non-RL baseline |
| G5 | NOT STARTED | frozen independent formal test not run |
| G6 | NOT STARTED | innovation ablations not run |
| G7 | NOT STARTED | no new paper body drafted from unpassed claims |
| G8 | NOT STARTED | complete research-package/posting readiness not accepted |

See `analysis_docs/ROUTE_RL_STATE.json` and `analysis_docs/E_CONTINUATION_STATE.json` for machine-readable records.
