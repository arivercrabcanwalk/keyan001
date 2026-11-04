# CA-RL-TSALNS learning-controller protocol

## Data isolation
- Training: Liu official train split (72 maps; indices 1-6 within each size group).
- Validation: official validation split (24 maps; indices 7-8). Checkpoint selection uses the stochastic policy cost; deterministic argmax is diagnostic only.
- Historical official test split (24 maps; indices 9-10) is not treated as a pristine blind test because it has been inspected in earlier project work.
- The generated locked_v2 suite contains 60 additional feasible maps (8/50, 16/100, 24/200, 32/300 across uniform/clustered/boundary distributions). It is a synthetic scale/distribution stress test, not real-world evidence. Do not use it for tuning.

## Behaviour cloning
- Teacher: M1d scheduled controller, with the same candidate generator, state/action schema, action mask, evaluator and environment as PPO.
- Collect from a seeded subset of 24 of the 72 training maps per BC seed; 6-second teacher episode budget; eight workers, subject to the 12-CPU cgroup cap.
- Save the full (feature, action, mask) dataset in teacher_records.npz, per-episode records in teacher_episodes.json, and checkpoint plus source/data hashes in bc_meta.json.
- Train with masked cross-entropy. Reject infeasible episodes, empty records and masked labels.

## PPO fine-tuning
- Initialize from the corresponding versioned BC checkpoint; old V1/V2 checkpoints are incompatible with model-v1/state-v3/action-v3/reward-v1.
- Provisional starting configuration: 60 iterations, 8 workers, 0.3-second collection episodes, 20,000 max steps, Adam 2e-4, entropy coefficient 0.04, 6 PPO epochs, validation every 5 iterations.
- Use elapsed-time SMDP GAE; truncated episodes, empty rollouts, nonfinite values and masked labels are hard errors.
- Select best checkpoint on the 24-map validation split by stochastic-policy mean cost. Record deterministic argmax separately.
- Save every iteration's rollout arrays, episode metadata, validation per-instance rows, current/best/final checkpoint hashes, optimizer/RNG state and train/validation instance hashes.

## Evaluation sequence
1. Evaluate BC-only and PPO checkpoints on the validation split, with stochastic and deterministic modes.
2. Compare against M1d and M2 using identical 2/6/12/30-second search budgets and the same independent evaluator.
3. Select model and hyperparameters using train/validation only.
4. Freeze source, config, model and manifest hashes.
5. Run the locked 60-map suite once for final generalization evidence. No tuning after inspecting those results.

## Locked-suite construction validation
- The 60 generated maps and 60 constructive witnesses were rechecked on the server using the independent evaluator: 60/60 feasible, 0 SHA256 mismatches, 0 failures. Manifest SHA256: ee7c2d6a45a9534c02997a27096e9a7a90db17b4abe63cd87997149cc77c7a4e.
- This validates suite integrity only; no algorithm has been evaluated on the locked maps yet.

## Pilot validation (not performance evidence)
- Earlier BC/PPO smoke (pre model-schema v1): 2 training maps, 1,469 BC records and 9,547 PPO transitions; retained as historical pipeline evidence only.
- Current model-v1 smoke: 2 training maps, 0.2-second teacher budget, 1 epoch; 1,682 BC state-action records. One PPO update collected 1,789 transitions; stochastic and deterministic validation, rollout NPZ, training-state snapshot, and model-v1 checkpoint hashes saved. Both current checkpoints loaded successfully.
- These tiny smoke runs only validate the pipeline and are excluded from every research comparison.
