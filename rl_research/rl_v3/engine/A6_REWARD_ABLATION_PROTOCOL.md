# A6: PPO runtime-reward ablation

Status: isolated training branch, not part of the main v5 source tree.

## Intervention
- Baseline reward-v2: 100 * incumbent_delta / initial_cost - 0.25 * operator_elapsed / episode_budget + 0.02 * global_best_indicator.
- A6 reward-v3: 100 * incumbent_delta / initial_cost + 0.02 * global_best_indicator.
- The explicit elapsed-operator-time reward penalty is removed (REWARD_TIME_WEIGHT=0).
- PPO elapsed-time SMDP GAE discounting is retained unchanged.
- State, action, MLP, optimizer settings, training episodes, validation split, model seeds and BC warm-start weights are held fixed.

## Warm start
The three original BC checkpoints (seeds 11, 23, 37) are reused unchanged. A6 allows only the reward-schema mismatch for this BC initialization; model/state/action schema mismatches remain fatal. The first A6 checkpoint is immediately re-saved under the new reward schema before PPO rollout workers load it.

## Training
Three PPO seeds; 60 updates; 8 workers; 0.3-second episodes; same learning rate, entropy coefficient, PPO epochs and 24-map stochastic validation selection as reward-v2.

## Interpretation
This is a development ablation. It cannot establish an RL contribution unless the resulting policies are evaluated against the same strong non-RL M2 Global reference under matched operators, initialization, evaluator and wall-clock budgets. Validation remains development-only.
