# CA-RL-TSALNS v5 final-code training audit

Date: 2026-10-31  
Code digest shared by all BC/PPO manifests: 3efbef8bb3003673c27e791a15d8639658d49e1f1c0c72e7fb42e84898ee187d

## 1. Training design

- Three independent seeds: 11, 23, 37.
- BC teacher data: all 72 training maps, six-second episode budget, 8 epochs.
- PPO: 60 updates, 8 workers, 0.3-second collection episodes, validation every 5 updates on all 24 validation maps with 2-second solver budgets.
- Reward: current-cost delta minus elapsed-time cost plus global-best bonus; SMDP GAE discounts by elapsed operator duration.
- All checkpoints use state schema v4 (75 features), action schema v4 (51 slots) and reward schema current-cost-delta-time-best-v2.

## 2. Verified artifacts

| Training seed | BC teacher transitions | PPO updates | Best stochastic validation cost | Best checkpoint SHA256 |
|---:|---:|---:|---:|---|
| 11 | 1,242,841 | 60 | 458.349919 | d68fab0f569e18e8d2ebe3ae198cc2bbf2a54e1db36e0faaeaceb5999489f325 |
| 23 | 1,248,369 | 60 | 457.908968 | 0879ef6ac11a2121a3d0c12898daaa489747cd88c9f4678d6b5c84e4210b2bb7 |
| 37 | 1,246,621 | 60 | 458.451422 | d35e32b8b99d2094bc73732ac6ece14b28362b4657d1ff36e1fb38bf7f155812 |

Each seed has bc.pt, teacher_records.npz, bc_meta.json, PPO best.pt/final.pt, training_state.pt, history.json, run_manifest.json and summary.json. All BC, best and final checkpoints loaded successfully. All code digests match. Every PPO history has exactly 60 updates and 12 validation checks.

## 3. BC label and mask diagnostics

Across the three teacher datasets:
- 1.24 million state-action labels per seed;
- 49 of 51 action IDs observed;
- zero teacher labels violated the recorded action mask;
- mean number of legal actions per state was approximately 31.6/51;
- BC training accuracy was approximately 12.8–13.0% after eight epochs.

The action entropy and low top-class concentration show that the teacher data are not a single-action imitation problem. Accuracy must not be interpreted as policy quality by itself.

## 4. Validation checkpoint observations

The best validation checkpoint for each seed occurred at update 5. Later PPO updates did not improve that seed's best validation value; final stochastic validation was worse than the selected best checkpoint. This is a warning against claiming that PPO fine-tuning has established an advantage. The upcoming same-budget evaluation must compare:
- the BC checkpoint;
- the PPO-selected checkpoint;
- the strongest non-RL controller M1d / M1d_noxchg;
- Original TSALNS M0.

The three best validation costs are close to one another, but no performance claim can be made until these paired baselines are run on the same maps, solver seeds and budgets.

## 5. Logging collision and independent recheck

The original BC_seed11.log contains a FileExistsError at the output-directory creation step. The directory already existed because a successful seed-11 BC invocation had completed and written bc.pt; a second invocation collided before training. The main training launcher nevertheless completed all three seeds and wrote TRAINING_COMPLETED. Evidence:
- BC_seed11/bc_meta.json and teacher_records.npz exist;
- BC_seed11/bc.pt loads successfully;
- PPO_seed11 run_manifest references the same code digest;
- PPO_seed11 completed all 60 updates and produced a valid best checkpoint;
- the full launcher completion marker exists.

A clean independent BC seed-11 recheck was run into BC_seed11_recheck. It completed eight epochs and produced a valid checkpoint under the same code digest. The recheck had a different number of wall-clock-collected teacher transitions (1,223,501), so its checkpoint hash is not expected to match exactly. This confirms the training script's time-budgeted data collection is sensitive to runtime scheduling.

The original collision log is preserved. Do not silently replace it. For future launches, use unique run directories and an atomic lock before starting a seed; do not rely only on checking for bc.pt/history.json after a directory may already have been created.

## 6. Interpretation

Training engineering is complete and checkpoint integrity is verified. This is not evidence that PPO beats BC or the strongest non-RL controller. The next required step is same-budget validation across all 24 validation maps and solver seeds 101, 102, 103, followed by statistical analysis and a single locked-suite evaluation after freeze.
