# Independent Read-Only Review

Date: 2026-11-05

## Scope

This review independently checked the retry package's local frozen script, protocol, freeze records, result JSON, execution receipt, post-run audit, evidence index, and the first-attempt result. It did not connect to <COMPUTE_HOST>, launch code, perform model inference, or run a training/quality experiment. This review is separate from the root-authored static and post-run checks; those are treated as source evidence, not as this review.

## Verdict

The reported diagnostic curve, checkpoint reproduction gate, and update counts are internally consistent with the frozen script and local result files. No numerical or scientific-interpretation discrepancy was found in the audited retry result. The supported result is narrow: a fresh replay of the same seed-103 supervised training sequence reproduces the saved P3 common-BC canonical model and optimizer digests at epoch 400, then reaches exact greedy teacher-label fit on the same 138 saved TRAIN states at the first evaluated fixed-grid checkpoint, epoch 800.

## Findings

1. **Result identity and frozen code:** Local SHA-256 values match the retry evidence index for `fit_curve.py`, protocol, freeze files, `output/RESULT.json`, execution receipt, post-run audit, and diagnosis. The retry result hash is `6b5bb08db09fc0cc8713b7bb66b3ff56c02428b4cd79ea15febf1ef8fea448fb`; the preserved first-attempt result hash is `7a9e59e221605c40bfa93099df2a9ec8018448cfc02d6643a70f0776bca0ca50`.

2. **Attempt relationship:** The retry script retains seed 103, 64-unit model, Adam at 0.001, 0.5 gradient clipping, batch size 64, the same state ordering and `random.Random(103)` shuffle, and the same 400-epoch digest barrier. A local diff shows the scientific schedule is unchanged; attempt 2 extends the wall guard from 120 to 900 seconds and adds attempt/prior-result metadata. Attempt 1 stopped at its 120-second guard with only the epoch-0 evaluation saved. Its actual gradient-step count is not recorded and must remain unknown; the epoch-0 `gradient_steps: 0` is not evidence that the interrupted attempt performed zero updates.

3. **TRAIN denominator and legal labels:** The frozen script requires exactly 138 states, all from `TRAIN_1`, `TRAIN_3`, `TRAIN_4`, `TRAIN_5`, and `TRAIN_6`, with counts 26, 28, 28, 28, and 28. It checks each stored label index is in range and enabled by its mask. No VAL state is admitted by the script's map-name check.

4. **Curve and arithmetic:** The result reports 22/138 at epoch 0, 128/138 at epoch 400, 137/138 at epoch 600, and 138/138 at epoch 800. These counts match the reported accuracies and decreasing mean teacher NLL values (2.4721578800, 0.1599740265, 0.0432403122, and 0.0007024364). With 138 states and batch size 64, each epoch has `ceil(138/64) = 3` batches/optimizer steps. Therefore epochs 400, 600, and 800 correspond to 1,200, 1,800, and 2,400 supervised optimizer updates. The training helper uses supervised negative log-likelihood, backpropagation, gradient clipping, and `optimizer.step()`; these are real supervised optimization updates.

5. **Digest barrier precision:** At epoch 400, both canonical state digests equal the registered checkpoint values: model `b10e1bebae97a9a9c3fcb6b00ad4e56076fe00ff992464c137bd3ec3cbc4afbc` and optimizer `cb72bb56d03d180eddb9b26828e47dabdd3e208c5f565c6c905032020db0f8bf`. The helper defines a canonical digest over state structure, tensor dtype/shape, and tensor bytes, independent of PyTorch container bytes. Thus the result supports exact canonical model/optimizer state-digest reproduction, not byte-for-byte reproduction of the original checkpoint file. The checkpoint file itself is separately reported unchanged by its SHA-256.

6. **Supervised optimization versus RL execution:** This retry performs 2,400 supervised optimizer updates in total, of which 1,200 are the replay through the epoch-400 reproduction barrier and 1,200 extend the same replay to epoch 800. It does not execute PPO/A2C/REINFORCE updates, collect policy trajectories, sample a policy action, construct an environment, call `env.step`, run a solver, read VAL, generate maps, or save a model. Its use of the policy network and masked action distribution is only for masked teacher-label scoring. The result's zero RL/rollout/solver/VAL/map fields are consistent with the script's visible operations. This diagnostic is supervised training on stored states, not an RL run.

7. **Prior P3 outcome remains unchanged:** This result does not reverse the original 0/5 complete free-route common-BC gate. No free rollout or route evaluator was run here. The observed exact fit establishes only fit to the same stored teacher labels at those states; it does not establish route feasibility, cost-cap compliance, route quality, held-out generalization, RL contribution, novelty, Formal status, or a manuscript claim.

## Documentation / Provenance Notes

- `FINAL_IMPLEMENTATION_FREEZE.json` is a pre-execution freeze snapshot and still says `STATIC_GO_PENDING_ONE_SERVER_EXECUTION` / `executed: false`. Read together with the later execution receipt and result; it is not evidence that the retry did not run. Its filename/status pair could be clarified in a future index, without rewriting the frozen record.
- This independent review verifies local artifact hashes and cross-file consistency only. The execution receipt records <COMPUTE_HOST> and the frozen remote input hashes, but this review did not independently observe the remote process or re-hash the server-side source files. Server provenance remains receipt-backed rather than independently witnessed here.

## Evidence Paths

- `../PROTOCOL.md`
- `../INITIAL_IMPLEMENTATION_FREEZE.json`
- `../FINAL_IMPLEMENTATION_FREEZE.json`
- `../fit_curve.py`
- `../output/RESULT.json`
- `../EXECUTION_RECEIPT.json`
- `../POSTRUN_AUDIT.json`
- `../EVIDENCE_INDEX.json`
- `../../P3_teacher_fit_diagnostic_20261104/output/RESULT.json`
- `../../P3_teacher_fit_diagnostic_20261104/fit_curve.py`
- `../../next_stage_protocol_sol_20261104/ordinary_rl_attribution_pilot/P3_fixed_population/implementation/trainer.py`
