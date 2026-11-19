# Weather Common-Map Development Runner v3

This is a bounded <COMPUTE_HOST> CPU development protocol for direct physical-route
actions `(station, slot, target|RETURN)`. It is development only, not formal
evidence, a best-method result, a novelty result, or a strong-baseline claim.
RL never selects a search operator, neighbourhood, algorithm, repair budget, or
operator strength. Both original and weather costs remain constrained by the
author anchor plus `1e-7`; all construction, checkpoint loading, replay, model
inference, failures, and fallback time remain recorded.

## v1 to v3 amendment

The six Windows development maps already materialized under
`linux_migration_20261104/evidence_local/windows_development_probe_20261104/remote_output`
remain exposed development identities. They are not regenerated, replaced, or
represented as a new precommit. `amend` verifies the old Windows-key v1
registration against the frozen v1 ZIP source bundle, validates every existing
map raw/geometry identity and receipt, then creates a separate v3 registration
and amendment receipt bound to the unchanged materialization. The old
registration, `MATERIALIZATION.json`, instances, scenarios, and receipts stay
untouched.

Every v3 registration has canonical project-relative POSIX dependency keys,
source hashes, the exact six slots, three seeds, PPO/A2C/REINFORCE, fixed last
completed checkpoint selection, fixed optimization hyperparameters, a one CPU
Torch/BLAS limit, 128 steps per episode, 4,096 transitions per algorithm/seed,
and 600 seconds training wall time per algorithm/seed. V3 additionally freezes
12 epochs of behavior cloning over only weather-admissible author-anchor routes
from the eligible `train` maps, followed by 4 online updates of 2 episodes for
each algorithm/seed. The held-out development map never supplies a demonstration.
`DEMONSTRATIONS.json` records the source-solution hash, physical action count,
and independent replay for every warm-start trace. The local execution
registration records the user-authorized <COMPUTE_HOST> weather/NFZ development
intent; it has no inferred G4 permission gate. A fresh v3 `register` path keeps
the old six identities in the generator exclusion set. An amended registration
cannot run `materialize`.

The BC-only controls are the exact saved pre-RL parameter states for seeds
103/211/307. Every algorithm recreates the same seeded BC fit, and a canonical
name/dtype/shape/tensor-byte digest must equal its seed's saved control before
online updates start. Results explicitly label `BC-only`, `BC+PPO`, `BC+A2C`,
and `BC+REINFORCE`, and include the demonstration receipt hash and action count.
BC performs no value loss or value-head update, although shared encoder changes
may change value predictions. It is a supervised initialization, not novel RL.

All experiment and unit-test commands run on <COMPUTE_HOST>. Stage a new bundle in a new
run directory; preserve the old v2 directory. From the staged `lunwen` root:

```bash
g24='route_rl_research/20261103/return_makespan/g24_weather_nfz'
old='<EXECUTION_PATH>'
reg="$PWD/weather_development_v3_amendment.json"
/opt/conda/bin/python3.11 "$g24/comparison/development_runner.py" amend --registration "$reg" --namespace '<COMPUTE_HOST>-weather-development-v3-bc-20261104' --updates 4 --episodes 2 --legacy-registration "$old/legacy_registration.json" --legacy-materialization "$old/legacy_output" --legacy-bundle "$old/legacy_v1.zip"
/opt/conda/bin/python3.11 "$g24/comparison/development_runner.py" import-anchors --registration "$reg" --out "$PWD/output" --source-registration "$old/registration_v2.json" --source-out "$old/legacy_output" --expected-source-registration-sha256 604d0492cb858411e5303daf78030e90b1ff148a10ce35e486a4e049dab302ab --expected-source-anchors-sha256 468bdfdc46d371e16d0cbbe2b9df4e024b131d7422b2a45c30c5f7821d8726ba
/opt/conda/bin/python3.11 "$g24/comparison/development_runner.py" experiment --registration "$reg" --out "$PWD/output"
```

Verify the old server filenames before executing; the source registration and
ledger hashes are mandatory. `import-anchors` performs zero author solves,
checks unchanged physics/scorer/author dependency identities, preserves all
six source statuses (including failures) and all source bytes, writes the old
ledger as `SOURCE_ANCHORS.v2.json`, and creates `ANCHOR_IMPORT_RECEIPT.json` plus
a new v3 ledger. The v2 experiment is retained at its original path rather than
copied into a new run. No map is regenerated. Shared demonstration-construction
wall time is separately recorded once and conservatively charged in full to
every algorithm/seed's 600-second cap. The per-run timer begins before model and
optimizer construction; post-update expiry is a failed run. Deadline/invalid
demonstration/transition-cap failures write terminal `RESULTS.json`.

`experiment/RESULTS.partial.json` is atomically refreshed after each completed
training update and comparison. `TRAINING_UPDATES.jsonl`, `TRAINING_FINAL.jsonl`,
`COMPARISONS.jsonl`, and `DEMONSTRATIONS.json` retain progress and demonstration
provenance; each algorithm/seed writes
its `*_last.pt` and its current JSON receipt after every completed update. An
interruption, failed update, invalid anchor, unavailable optional beam baseline,
or deadline/step/transition/wall-time limit stays in those records. Reusing an
existing `experiment` directory is rejected. The optional direct physical beam
control uses `physical_baselines.beam_construct` only when that frozen source
is present; otherwise it records an unavailable-baseline failure. It does not
support a strong-baseline claim.

For a fresh (not amended) future development allocation, use `register` then
`materialize`, `anchors`, and `experiment` with new paths. That branch excludes
the six old identities and has no exception for replacement. Preserve console
output, registrations, source bundles, all result receipts, and all failures.
