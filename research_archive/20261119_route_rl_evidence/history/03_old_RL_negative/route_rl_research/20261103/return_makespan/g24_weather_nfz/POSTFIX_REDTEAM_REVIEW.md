# Post-Fix Red-Team Review

Date: 2026-11-04 (Asia/Shanghai)  
Scope: current `weather_full_map.py` Markov state, the fixed 20-slot/128-target
schema, PPO/A2C input and checkpoint compatibility, and the strict-v5 receipt.
This review did not modify production code, checkpoints, historical smoke
artifacts, or research state.

## Current Status

**Engineering receipt: PASS.** The current source bytes match all nine
strict-v5 runtime manifest entries; a clean exact smoke reproduction matched the
stored scenario, anchor, observation schema, all six training histories/results,
and all six checkpoint bytes. The existing 39-test focused suite also passes.

**Markov-state claim: BLOCKED.** A physical action from an identical model input
can produce different next legal masks solely because the original LRPHSD anchor
cost is omitted from the tensor passed to PPO/A2C. Therefore the current tensor
is not a sufficient Markov observation over the supported family of anchored
instances. Strict-v5 remains valid as a synthetic interface receipt for its
specific fixture, but it cannot establish a general full-information/Markov
policy contract or authorize quality training with this representation.

## Findings

### P1 - The original-cost constraint is outside the PPO/A2C state

`WeatherFullMapEnv.observation()` returns `original_cost_cap` and
`original_cost_lower_bound` only as receipt fields
([`weather_full_map.py:545-557`](weather_full_map.py)); neither appears in the
`global` vector built at [`weather_full_map.py:517-531`](weather_full_map.py) or
in the candidate vector at [`weather_full_map.py:479-515`](weather_full_map.py).
The actual training interface forwards only `global`, `candidates`, and `mask`
([`rl_algorithms.py:19-35`](rl_algorithms.py)), and the actor-critic consumes
only those tensors ([`weather_policy.py:26-42`](weather_policy.py)). Yet
`_legal()` uses the hidden `anchor.cost` to decide whether each future action is
available ([`weather_full_map.py:373-400`](weather_full_map.py)).

The following deterministic counterexample uses the same instance, forecast,
weather cap, target ownership, station type, current routes, and action. Only
the original feasible anchor route, hence `anchor.cost`, differs. At the initial
state all three model inputs are identical; after the same legal physical action
the global and candidate tensors remain identical, but the legal mask differs.
This violates the Markov transition requirement.

```bash
cd <LOCAL_PATH>
python - <<'PY'
from pathlib import Path
import sys
p=Path.cwd(); root=p.parents[3]
for x in (p,p.parent,root/'reproduction/reviewer_package_semfix'): sys.path.insert(0,str(x))
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from scorer import CostAnchor
from weather_full_map import WeatherFullMapEnv, WeatherMapScenario, WeatherMapAction
from weather_oracle import WindField, WindKnot
params=Parameters(speed=900.,flight_energy=.018,small_battery=99.,large_battery=99.,small_radius=10000.,large_radius=10000.,small_duration=999.,large_duration=999.,time_cost=1.)
instance=Instance('cap',(Node(1,-3000.,-3000.,0.,0.),Node(2,-3000.,0.,0.,0.),Node(3,3000.,-3000.,0.,0.)),(Node(100,0.,0.,0.,0.),),'cap-witness',params)
def solution(order):
    x=empty_solution(instance,[2]); x['routes']=[[ [list(order)], [] ]]; return x
scenario=WeatherMapScenario(WindField((WindKnot(0.,0.,0.),)),name='calm')
tight=CostAnchor.from_solution(instance,solution((2,1,3)))
loose=CostAnchor.from_solution(instance,solution((1,3,2)))
a=WeatherFullMapEnv(instance,tight,scenario,weather_cost_cap=1e9)
b=WeatherFullMapEnv(instance,loose,scenario,weather_cost_cap=1e9)
def tensors_equal(x,y):
    return ((x['global']==y['global']).all() and (x['candidates']==y['candidates']).all()
            and (x['mask']==y['mask']).all() and x['actions']==y['actions'])
print('initial_tensor_and_mask_equal',tensors_equal(a.observation(),b.observation()))
a.step(WeatherMapAction(0,0,1)); b.step(WeatherMapAction(0,0,1))
x,y=a.observation(),b.observation()
print('anchors',tight.cost,loose.cost)
print('post_action_global_equal',(x['global']==y['global']).all())
print('post_action_candidates_equal',(x['candidates']==y['candidates']).all())
print('post_action_actions_equal',x['actions']==y['actions'])
print('post_action_tight_mask',x['mask'].astype(int).tolist())
print('post_action_loose_mask',y['mask'].astype(int).tolist())
print('post_action_actions',[(z.station_idx,z.slot,z.target_id) for z in x['actions']])
print('receipt_only_caps',x['original_cost_cap'],y['original_cost_cap'])
PY
```

Observed output (exit `0`):

```text
initial_tensor_and_mask_equal True
anchors 61.44737854124365 65.56760513290962
post_action_global_equal True
post_action_candidates_equal True
post_action_actions_equal True
post_action_tight_mask [1, 1, 1, 1, 0, 0]
post_action_loose_mask [1, 1, 1, 1, 1, 0]
post_action_actions [(0, 0, 2), (0, 0, 3), (0, 0, None), (0, 1, 2), (0, 1, 3), (0, 1, None)]
receipt_only_caps 61.44737854124365 65.56760513290962
```

The required correction is to make the original-budget state an actual model
input, not only a receipt: include a stable representation of the original cap
and residual lower-bound budget in `global`, plus the corresponding
action-specific original-budget projection where needed. Freeze the revised
schema, invalidate/retrain checkpoints whose input contract changes, and add the
counterexample as a unit regression before asserting Markov sufficiency.

### P2 - strict-v5 does not cryptographically bind checkpoint files to its JSON receipt

The runtime source manifest is sound, but the report writes checkpoint paths and
reload booleans, not SHA-256 values. The save/report path at
[`run_full_map_smoke.py:175-216`](run_full_map_smoke.py) stores a state dict,
strictly reloads it in-process, then emits the JSON without a checkpoint digest.
Consequently a later replacement of a `.pt` at the same path is not detectable
from `full_map_smoke_report.json` alone.

Current file hashes, recorded here for audit, are:

```text
full_map_smoke_20261104_strict_v5/full_map_smoke_report.json
89254ff14c959b0966168467a2aee7860ac15e73cda3ae71ee461d0c93753169
a2c_seed103.pt 07137d4823ace1f60c12ae95a6d1c371050e3e730db793281e4946c772be702d
a2c_seed211.pt 2eca33cf85af3ff68ff7330f0e854c51ac14d79addcb3b92fdbad01beefb79d3
a2c_seed307.pt e4d7e3d083d53f3ba931db23930c159d4f12aead89a9ab01f7b16f72c7a39da7
ppo_seed103.pt 115946ec83cc0790e320faf2074aac7f4ab95ec83b1f6eb330f6937bbfa253b0
ppo_seed211.pt e3ac091580557f6d42abded9087c1b9f3cba9e664012764502607c88de118b0e
ppo_seed307.pt 101876788a75fbbb9c19024a27df827cb552d40de9b177457d9658f4360bd81a
```

This is a provenance-strength gap, not a current reproducibility failure.
Future immutable receipts should include each checkpoint SHA-256 in the report
before writing it, then verify those digests before checkpoint selection or
reuse.

## Verified Non-Findings

### Fixed schema capacity and PPO/A2C structural compatibility

The current state schema is `global_dim=1116`, `candidate_dim=18`, with 20
physical slots and 128 targets (`weather_full_map.py:31-35, 234-235`). The
boundary checks behaved as designed:

```bash
python - <<'PY'
from pathlib import Path
import sys
p=Path.cwd(); root=p.parents[3]
for x in (p,p.parent,root/'reproduction/reviewer_package_semfix'): sys.path.insert(0,str(x))
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from scorer import CostAnchor
from weather_full_map import WeatherFullMapEnv, WeatherMapScenario
from weather_oracle import WindField, WindKnot
params=Parameters(speed=900.,flight_energy=.018,small_battery=99.,large_battery=99.,small_radius=1e6,large_radius=1e6,small_duration=999.,large_duration=999.)
scenario=WeatherMapScenario(WindField((WindKnot(0.,0.,0.),)),name='calm')
def target_case(n):
    inst=Instance(f'n{n}',tuple(Node(i,float(i),0.,0.,0.) for i in range(1,n+1)),(Node(1000,0.,0.,0.,0.),),f'n{n}',params)
    sol=empty_solution(inst,[1]); sol['routes']=[[[],[list(range(1,n+1))]]]
    return inst, CostAnchor.from_solution(inst,sol)
def dabs_case(n):
    inst=Instance(f'slots{n}',tuple(Node(i+1,float(i)*10.+1.,0.,0.,0.) for i in range(n)),tuple(Node(1000+i,float(i)*10.,0.,0.,0.) for i in range(n)),f'slots{n}',params)
    sol=empty_solution(inst,[2]*n); sol['routes']=[[[[i+1]],[]] for i in range(n)]
    return inst, CostAnchor.from_solution(inst,sol)
for n in (128,129):
    inst,anchor=target_case(n)
    try:
        env=WeatherFullMapEnv(inst,anchor,scenario); obs=env.observation()
        print(f'targets={n} accepted global_dim={obs["global"].size} candidate_dim={obs["candidates"].shape[1]} actions={len(obs["actions"])} slots={len(env.slots)}')
    except ValueError as exc: print(f'targets={n} rejected error={exc}')
for n in (10,11):
    inst,anchor=dabs_case(n)
    try: print(f'dabs_stations={n} accepted slots={len(WeatherFullMapEnv(inst,anchor,scenario).slots)} global_dim=1116')
    except ValueError as exc: print(f'dabs_stations={n} rejected error={exc}')
PY
```

Observed output (exit `0`):

```text
targets=128 accepted global_dim=1116 candidate_dim=18 actions=129 slots=1
targets=129 rejected error=v1 policy-state table capacity exceeded
dabs_stations=10 accepted slots=20 global_dim=1116
dabs_stations=11 rejected error=v1 policy-state table capacity exceeded
```

All six saved strict-v5 checkpoints loaded with `weights_only=True`, rebuilt a
`WeatherPointerActorCritic` from their recorded dimensions, passed strict
`state_dict` loading, and produced finite legal logits/value on the current
fixture observation:

```text
checkpoint=a2c_seed103.pt schema=weather_full_map_checkpoint_v1 algorithm=A2C seed=103 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
checkpoint=a2c_seed211.pt schema=weather_full_map_checkpoint_v1 algorithm=A2C seed=211 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
checkpoint=a2c_seed307.pt schema=weather_full_map_checkpoint_v1 algorithm=A2C seed=307 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
checkpoint=ppo_seed103.pt schema=weather_full_map_checkpoint_v1 algorithm=PPO seed=103 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
checkpoint=ppo_seed211.pt schema=weather_full_map_checkpoint_v1 algorithm=PPO seed=211 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
checkpoint=ppo_seed307.pt schema=weather_full_map_checkpoint_v1 algorithm=PPO seed=307 global=1116 candidate=18 hidden=64 actions=11 finite_legal_logits=True finite_value=True
loaded_strictly=6/6 expected_schema=(1116,18,20,128)
```

### strict-v5 evidence matches current bytes

The command below compared every runtime manifest entry in the stored report to
the current file, recreated the exact synthetic run under current bytes, and
compared the reproducible receipt fields and all six model files.

```bash
cd <LOCAL_PATH>
python run_full_map_smoke.py --smoke --output-dir /private<EXECUTION_PATH>
jq -e --slurp '.[0].runtime.source_manifest == .[1].runtime.source_manifest' full_map_smoke_20261104_strict_v5/full_map_smoke_report.json /private<EXECUTION_PATH>
jq -e --slurp '.[0].observation_schema == .[1].observation_schema and ([.[0].training.algorithms.PPO[], .[0].training.algorithms.A2C[] | {seed, complete, result: (.result.replay | {M_return, weather_cost, original_score: .original_score.cost}), checkpoint_reload_verified, checkpoint_inference_round_trip_verified}] | sort_by(.seed, .result.M_return)) == ([.[1].training.algorithms.PPO[], .[1].training.algorithms.A2C[] | {seed, complete, result: (.result.replay | {M_return, weather_cost, original_score: .original_score.cost}), checkpoint_reload_verified, checkpoint_inference_round_trip_verified}] | sort_by(.seed, .result.M_return))' full_map_smoke_20261104_strict_v5/full_map_smoke_report.json /private<EXECUTION_PATH>
for f in ppo_seed103.pt ppo_seed211.pt ppo_seed307.pt a2c_seed103.pt a2c_seed211.pt a2c_seed307.pt; do cmp -s "full_map_smoke_20261104_strict_v5/$f" "/private<EXECUTION_PATH>"; printf '%s identical_checkpoint_bytes=%s\n' "$f" "$?"; done
```

Observed output: both `jq` comparisons printed `true`; all six comparisons
printed `identical_checkpoint_bytes=0` (the `cmp` success exit code). An
independent reproduction made the stronger comparison of schema, scope,
scenario, anchor, greedy receipt, full training histories, runtime/source
manifest, and checkpoint payloads: all matched. Only elapsed time differed:
`35.81573358317837` seconds in strict-v5 versus `35.41090266685933` seconds in
the fresh run.

Current source hashes, all equal to strict-v5 `runtime.source_manifest`:

```text
weather_oracle.py      e39a7a3ece64443275ef853bbf346571dfd55bf3d360e903d699836fde3908d3
weather_replay.py      fbe053c1dc8de62b9cd1811829c103b3e212e92fbf1dc67a04784b2481bb758e
weather_full_map.py    a5626b4fdb28508792a3a36cce7a77e5e8b9816fe913d1be9368efb75f78d26c
weather_policy.py      6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826
rl_algorithms.py       4d546bb9f69a624398ee2231a5777a525ce41792194e60829a8ebd489a1c6101
run_full_map_smoke.py  86875a1b0ce0a38e913a6d0bdbddfb2f627be0067671444d037ca9d86abcf4b7
../scorer.py           c6e156b2d770cec2f663eada37c2d39bff1583f672bda4116f81493484409135
lrphsd/problem.py      f03c2f4201cdea977644d84ab0ad704eb47d4c4389b06b2ac86b9d264463b1cc
lrphsd/__init__.py     3d2731224303ea6ed0d4cb3550607561fad4ed82cbe97b3eda1f03c6ae402fd8
```

### Regression suite

```bash
python -m unittest -v test_weather_pipeline.py test_weather_oracle.py test_weather_full_map.py test_rl_algorithms.py
```

Observed result (exit `0`): `Ran 39 tests in 1.159s`, `OK`.

## Disposition

Keep strict-v5 as a reproducible, negative, synthetic engineering smoke exactly
as scoped in `FULL_MAP_SMOKE_RESULTS_20261104.md`. Do not use it to certify a
general Markov observation or advance training/formal gates. Correct and
regression-test P1, freeze the changed input schema, retrain any affected model,
and regenerate the strict receipt with checkpoint digests before relying on a
new checkpoint artifact as immutable evidence.
