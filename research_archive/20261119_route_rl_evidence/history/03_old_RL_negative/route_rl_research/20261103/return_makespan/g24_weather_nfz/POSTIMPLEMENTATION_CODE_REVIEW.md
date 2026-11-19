# Post-Implementation Code Review

Date: 2026-11-04

Reviewed files:

- `weather_full_map.py` (`7074bd020d1b47075ea5b95f61a41b4d1b03508c7e1633bc63c141d43848f21e`)
- `weather_replay.py` (`acc6741be557cd9248cb5826d4b0756217b652edb5318b028a3fbf7e5426bdf1`)
- `test_weather_full_map.py` (`ad17ba5a37b830f6e279720146b36037f132e1272ed20830e4a9a1a875d8b26b`)
- `run_full_map_smoke.py` (`ae379f64d07a8aa357805b4502786b4d183e0994ca3d6b9e9332634bf01b0e8f`)

Scope: strict review only. No implementation files were changed. The approved main
contract remains fixed deployment/type/target-station, physical `(slot,target)` or
`(slot,RETURN)` actions, `M_return`, and per-map `C <= C_Liu + 1e-7`.

## Findings

### P0: The full-map package does not enforce the approved original LRPHSD cost cap

`weather_full_map.py:124-125` obtains an original-model score only to test
feasibility. `weather_full_map.py:204-210` admits a candidate solely against a
weather-recomputed cost. `run_full_map_smoke.py:131-136` derives that cap from a
weather replay of its synthetic anchor. Neither path compares the candidate's
original `score_solution(...)["cost"]` to `anchor.cost`, nor calls the parent
`validate_candidate` contract.

The separate weather protocol may intentionally use `C^F`, but this is not the
approved main-line `C <= C_Liu + 1e-7` contract. Consequently, this runner cannot
be used as a D/G3/G4 solver or evidence without an explicit separately approved
weather-domain protocol and a second original-cost admission check.

Reproduction (from this directory, with the reviewer package on `PYTHONPATH`):

```bash
PYTHONPATH=<LOCAL_PATH> python - <<'PY'
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from scorer import CostAnchor, score_solution
from weather_full_map import WeatherMapScenario, replay_weather_solution
from weather_oracle import WindField, WindKnot
p=Parameters(speed=900., flight_energy=.018, small_battery=99., large_battery=99., small_radius=10000., large_radius=10000., small_duration=999., large_duration=999., time_cost=1.)
xy=[(-3000.,-3000.),(-3000.,0.),(3000.,-3000.)]
i=Instance('i',tuple(Node(k+1,*v,0.,0.) for k,v in enumerate(xy)),(Node(100,0.,0.,0.,0.),),'cost-witness',p)
a=empty_solution(i,[2]); a['routes']=[[[[1,2,3]],[]]]
b=empty_solution(i,[2]); b['routes']=[[[[1,3,2]],[]]]
anchor=CostAnchor.from_solution(i,a)
f=WeatherMapScenario(WindField((WindKnot(0.,0.,14.),)),name='northwind')
ra=replay_weather_solution(i,anchor,f,a)
rb=replay_weather_solution(i,anchor,f,b,weather_cost_cap=ra['weather_cost'])
print('original',score_solution(i,a)['cost'],score_solution(i,b)['cost'])
print('weather',ra['weather_cost'],rb['weather_cost'],rb['admissible'],rb['issues'])
PY
```

Observed output:

```text
original 63.614983674153265 65.56760513290962
weather 156.05679347178943 130.57078824919333 True []
```

The candidate is admitted although its original cost is higher by about `1.95`,
not `<= 1e-7`.

### P0: Supplying a cost cap lets an infeasible nonchosen candidate crash observation construction

`weather_full_map.py:397-400` invokes `_weather_lower_bound(action)` outside the
`try` in `_candidate_features`. That lower-bound path reaches `_project_target`
at `weather_full_map.py:323`, then `_minutes` at line 81, which raises when an
unflyable leg is encountered. `_legal` correctly catches this condition and
would mask the action, but `observation()` evaluates candidate features for every
action at line 435 and instead aborts environment construction.

This turns a required explicit `dead_end`/failure result into an exception. It
also affects maps that still have legal actions: one unrelated infeasible
candidate is enough to abort the whole observation when a cap is supplied.

Reproduction:

```bash
python - <<'PY'
from run_full_map_smoke import fixture
from weather_full_map import WeatherFullMapEnv, WeatherMapScenario
from weather_oracle import WindField, WindKnot
inst, _, anchor, _ = fixture()
s = WeatherMapScenario(WindField((WindKnot(0., 0., 0.), WindKnot(150., 0., 100.))), name='mixed')
print(WeatherFullMapEnv(inst, anchor, s).observation()['mask'].astype(int).tolist())
WeatherFullMapEnv(inst, anchor, s, weather_cost_cap=1e9)
PY
```

Observed output:

```text
[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0]
ValueError: crosswind_infeasible
```

With `WindKnot(0., 0., 100.)`, the no-cap environment instead reports
`done=False`, `dead_end=True`, `terminated=True`, and zero legal actions. That
is the required behavior that the capped path fails to preserve.

### P0: The independent replay accepts a physically infeasible crosswind that the primary oracle rejects

`weather_replay.py:59-62` allows crosswind through `airspeed + EPS` and clamps a
negative radicand to zero. The primary oracle rejects at the exact airspeed
boundary. A positive along-wind component then makes the replay route legal even
though the crosswind is strictly greater than airspeed. Therefore the purported
independent replay can certify a solution that the environment cannot construct;
the synthetic anchor itself is currently replayed only through that secondary
path in `run_full_map_smoke.py:131-134`.

Reproduction:

```bash
python - <<'PY'
from weather_oracle import Point, WindKnot, WindField, FlightParams, plan_route
from weather_replay import replay_route
p=FlightParams(speed=900., flight_energy=.018)
w=WindField((WindKnot(0., 1., 15.0000000005),))
a,b=Point(0.,0.),Point(900.,0.)
x=plan_route(a,b,0.,w,p); y=replay_route(a,b,0.,w,p)
print('primary',x.legal,x.failure,x.rejection_reasons)
print('replay',y.legal,y.failure,y.arrival_s,y.energy)
PY
```

Observed output:

```text
primary False crosswind_infeasible ('crosswind_infeasible',)
replay True None 900.0 0.26999999999999996
```

Independent implementations may differ internally, but their accepted/rejected
physical boundary must be identical. This must be resolved before replay can be
used as an admission oracle.

### P1: Forecast tensors are noninjective because NFZ padding has no vertex-count or padding mask

`weather_full_map.py:373-390` zero-pads wind/NFZ tensors but encodes neither the
number of knots nor the number of vertices. A valid vertex `(0,0)` is
indistinguishable from padding. The policy can thus receive exactly the same
`global`, candidate, and legal-mask tensors for different fully known forecasts,
contrary to the full-forecast state contract.

Reproduction uses a valid triangle and a valid quadrilateral that append `(0,0)`:

```bash
PYTHONPATH=<LOCAL_PATH> python - <<'PY'
from test_weather_full_map import fixture
from weather_full_map import WeatherFullMapEnv, WeatherMapScenario
from weather_oracle import WindField, WindKnot, NoFlyZone, Point
i,_,a=fixture(); w=WindField((WindKnot(0.,0.,0.),))
tri=NoFlyZone((Point(0.,-300.),Point(300.,-300.),Point(300.,0.)),0.,1000.)
quad=NoFlyZone((Point(0.,-300.),Point(300.,-300.),Point(300.,0.),Point(0.,0.)),0.,1000.)
x=WeatherFullMapEnv(i,a,WeatherMapScenario(w,tri,name='tri')).observation()
y=WeatherFullMapEnv(i,a,WeatherMapScenario(w,quad,name='quad')).observation()
print((x['global']==y['global']).all(),(x['candidates']==y['candidates']).all(),(x['mask']==y['mask']).all())
PY
```

Observed output: `True True True`. The shapes are behaviorally distinct: for
`plan_route(Point(-600,-600), Point(200,100), 0, w, FlightParams(), zone)`, the
triangle returns direct distance `1063.014581273465`, while the quadrilateral
detours through `(0,0)` with distance `1072.134935173836`.

### P1: The PPO/A2C smoke runner drops all-initial-dead-end cases instead of preserving them as failures

`run_full_map_smoke.py:112-117` filters the batch to rollouts having transitions
and immediately calls `ppo_update`/`a2c_update`. An initially dead environment
has zero transitions, so `valid=[]` reaches `add_gae` and raises rather than
writing a failed seed/map record. This remains after the observation crash above
is corrected and violates the documented failure-denominator behavior.

Reproduction:

```bash
python - <<'PY'
from run_full_map_smoke import fixture, train
from weather_full_map import WeatherMapScenario
from weather_oracle import WindField, WindKnot
i,_,a,_=fixture()
s=WeatherMapScenario(WindField((WindKnot(0.,0.,100.),)),name='all-infeasible')
try:
    train(i,a,s,None,'PPO',103,updates=1,episodes=2)
except Exception as e:
    print(type(e).__name__,e)
PY
```

Observed output: `ValueError rollout must contain at least one transition`.
The same path exists for A2C. No checkpoint, report row, action prefix, or
failure denominator is produced.

### P1: A missing cap still produces a result labelled weather-admissible

Both `replay_weather_solution` (`weather_full_map.py:115-117`) and
`WeatherFullMapEnv` (`224-236`) make `weather_cost_cap` optional. At terminal
time, `step` passes that `None` to the replay (`477-482`), whose `cap_ok` is then
unconditionally true (`205`). `result()` consequently returns a
`weather-admissible` complete route without `C^F <= C_ref^F + 1e-7` ever being
checked. The smoke runner happens to supply a cap, but the exported core API does
not make the required reference/cap provenance mandatory.

For the current calm fixture, executing the complete route with no cap prints:

```text
True None True
```

for `(admissible, weather_cost_cap, weather_cost_cap_satisfied)`. A development
helper may expose an explicitly uncapped mode, but it must not share the same
admission/result label as a cap-protected solver result.

### P1: The observation does not meet the full-map state/receipt contract, and tests do not cover the missing semantics

`weather_full_map.py:423-444` exposes only nine aggregate state values plus the
padded forecast. `weather_full_map.py:392-421` emits per-action summaries, but
there is no explicit active-station state, per-slot position/trip energy/trip
state/clock vector, target-service/energy table, target-pool/served mask, or
forecast padding mask. This prevents verification that PPO/A2C and controls use
the complete common information set required by the weather design.

`test_weather_full_map.py` now has nine tests, including an uncapped initial
dead-end and a weather-cap boundary replay. It still has no test for a capped
impossible candidate, zero-transition PPO/A2C training, NFZ padding,
two simultaneously active LD/SD slots of the same DABS, multiple open trips in
the global cost lower bound, or primary-versus-secondary parity across a knot and
active NFZ. Its nominal NFZ replay test (`test_weather_full_map.py:98-106`) only
executes one primary-oracle target action; it does not call the independent
full-map replay. Its primary-oracle monkeypatch test (`80-89`) covers calm
geometry only and cannot detect the physical-boundary divergence above.

## Verification Performed

```bash
python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
```

Result: exit `0`; `Ran 29 tests`; `OK`.

```bash
python run_full_map_smoke.py --smoke --updates 1 --episodes 2 --output-dir <EXECUTION_PATH>
```

Result: exit `0`; generated six PPO/A2C checkpoints and
`/private<EXECUTION_PATH>`.
The report is correctly labelled synthetic-only, but one A2C and one PPO seed
were incomplete in this run, which confirms that this is an interface smoke and
not an admissible quality comparison.

## Residual Risk

No evidence here supports PPO, A2C, or the weather extension as a research
result. Even after the defects above are fixed, the package still needs a frozen
weather-domain cost protocol, complete independent replay receipts, same-objective
non-RL controls, 6s/12s wall-clock accounting, map-level data separation, and the
separate G4 training authorization before it can contribute to the approved
LRPHSD route-RL claim.

## Re-review Of Current Fixes

Re-reviewed 2026-11-04 after the follow-up implementation. This section
supersedes the finding status above while preserving the original review record.
No implementation file was modified during re-review.

Current reviewed hashes:

- `weather_full_map.py`: `e5329096f2f443f0d1ddb3cafd2859e0779c71224f1467c4a9e32ff2f02f07ff`
- `weather_replay.py`: `fbe053c1dc8de62b9cd1811829c103b3e212e92fbf1dc67a04784b2481bb758e`
- `test_weather_full_map.py`: `c66c5dd4f3f06ab3862bb88539365b572c14625c2188b4467df4573de4d1303d`
- `run_full_map_smoke.py`: `a1e11b5d8a13d57aafa44cdb17c38ad7d6d38815ecfad79ba2f206cd71d35d25`

### Status Of Prior Findings

| Prior finding | Status | Current evidence |
| --- | --- | --- |
| P0: original LRPHSD cap absent | **RESOLVED** | `replay_weather_solution` now invokes `validate_candidate(..., epsilon=0.0)` at `weather_full_map.py:125-128`, rejects `original_cost_or_domain_cap` at `205-206`, and the action mask applies a necessary original-cost bound at `386-390`. Terminal replay requires both original admission and the weather cap. The prior counterexample now prints `False ['original_cost_or_domain_cap'] False`. |
| P0: capped infeasible candidate crashes observation | **RESOLVED** | `_candidate_features` now catches the lower-bound/projector `ValueError` at `441-472`. The prior mixed-wind case has mask `[1,0,0,0,1,0,0,0,1,0,0]`, `float32 (11,18)` candidate features, and `isfinite=True`; no exception occurs. |
| P0: primary/replay crosswind disagreement | **RESOLVED** | Both implementations now use the same strict boundary (`weather_oracle.py:199-207`; `weather_replay.py:58-64`). At crosswind `15.0000000005` for airspeed `15`, both return `False crosswind_infeasible`. |
| P1: forecast padding collision | **RESOLVED** | `_forecast_features` emits wind and NFZ-vertex masks at `410-434`, and observation returns them at `509-513`. The former triangle/quadrilateral collision now yields `global_equal=False`; vertex masks are `[1,1,1,0]` and `[1,1,1,1]`. |
| P1: zero-transition PPO/A2C failure crashes training | **RESOLVED** | `run_full_map_smoke.py:135-144` records `skipped_update_no_transitions` rather than calling an update with an empty batch. Both PPO and A2C reproduce `result=None`, `complete=0`, `failures=['dead_end','dead_end']`, `skipped_update_no_transitions=True`. |
| P1: omitted weather cap returned an accepted terminal result | **RESOLVED for the default/terminal path** | `strict_weather_cap=True` by default; `weather_cost_cap=None` produces `weather_cost_cap_missing` and `weather_cost_cap`, and `WeatherFullMapEnv.result()` rejects the terminal route. A separate public API bypass remains below. |
| P1: full state/receipt and test coverage | **PARTIALLY RESOLVED** | The new receipt exposes slots, targets, original-cost fields and forecast masks (`489-515`), and the focused suite adds the core regressions. The actual PPO/A2C model still does not consume `state_receipt`; see unresolved P1 below. |

### New P1: `strict_weather_cap=False` can label an over-cap route admissible

`weather_full_map.py:208-212` skips all weather-cap rejection when the exported
`strict_weather_cap` argument is set to `False`, including when a concrete cap is
provided and failed. The smoke runner uses that opt-out only for the raw anchor
cost calculation (`run_full_map_smoke.py:158-160`) and correctly replays the
anchor again with a cap at `161-164`; its normal solver path is therefore not
affected. But the public replay API still permits a caller to receive
`admissible=True` for an explicit violated cap:

```bash
python - <<'PY'
from run_full_map_smoke import fixture
from weather_full_map import replay_weather_solution
instance, solution, anchor, scenario = fixture()
for strict in (True, False):
    r = replay_weather_solution(instance, anchor, scenario, solution,
                                weather_cost_cap=0.0, strict_weather_cap=strict)
    print(strict, r['admissible'], r['weather_cost_cap_satisfied'], r['issues'])
PY
```

Observed output:

```text
True False False ['weather_cost_cap']
False True False []
```

The raw-reference mode should be unable to turn a supplied failed cap into an
admissible result. It should either reject whenever a cap is supplied, or return
an explicitly non-admission calculation record rather than reuse `admissible`.

### Unresolved P1: Full state is only a receipt, not PPO/A2C model input

The new `state_receipt` is valuable evidence but is not part of the tensor
interface. `rl_algorithms.py:19-28` forwards only `global`, `candidates`, and
`mask`; `weather_policy.py:26-42` likewise encodes only those arrays. In
particular, the global tensor remains nine aggregate execution values plus
forecast, and candidate scores are independently encoded. The model cannot read
the complete per-slot vector and remaining-target table exposed only in
`state_receipt` (`weather_full_map.py:489-501`). Thus the original requirement
that all controls receive the complete common physical state remains unverified.

### New P2: Source manifest is not a complete loaded-module closure

The improved receipt correctly records runtime versions, platform, Torch config,
and eight hand-selected source hashes at `run_full_map_smoke.py:74-88`; it is
written into both each checkpoint (`173-177`) and the report (`197`). However,
the loaded package initializer is absent. Reproduction after importing the smoke
runner:

```bash
python - <<'PY'
from run_full_map_smoke import _runtime_receipt
import lrphsd
from pathlib import Path
manifest = _runtime_receipt()['source_manifest']
print(Path(lrphsd.__file__).resolve(), str(Path(lrphsd.__file__).resolve()) in manifest)
PY
```

Observed output:

```text
<LOCAL_PATH> False
```

This currently does not change execution, but the receipt must not be treated as
a complete source lock. Include `lrphsd.__file__` at minimum, or record the
deduplicated SHA-256 set of every project-local module actually loaded.

### Verification On The Current Snapshot

```bash
python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
```

Result: exit `0`; `Ran 35 tests`; `OK`.

```bash
python run_full_map_smoke.py --smoke --updates 1 --episodes 2 --output-dir <EXECUTION_PATH>
```

Result: exit `0`; report and six checkpoints generated. All six checkpoints were
loaded using `weights_only=True`, reconstructed with their recorded dimensions,
and accepted by `load_state_dict(..., strict=True)`. Independently recomputed
source hashes matched all eight manifest entries.

```bash
python run_full_map_smoke.py --smoke --updates 1 --episodes 1 --output-dir <EXECUTION_PATH>
```

Result: exit `1`; `FileExistsError: refusing to overwrite nonempty output
directory`. The pre-existing `keep.txt` SHA-256 was unchanged and no report was
created. An empty existing directory was accepted and populated with seven
artifacts (six checkpoints plus the report).

## Second Re-review Of Current Fixes

Re-reviewed 2026-11-04 after the second implementation pass. This section
supersedes the preceding re-review where it differs. No implementation file was
modified during this review.

Current reviewed hashes:

- `weather_full_map.py`: `dadb4e799fbb7c872b24f9911dec5981dc4b84af54ba9b41bd279104ce3a1b54`
- `weather_oracle.py`: `e39a7a3ece64443275ef853bbf346571dfd55bf3d360e903d699836fde3908d3`
- `weather_policy.py`: `6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826`
- `rl_algorithms.py`: `4d546bb9f69a624398ee2231a5777a525ce41792194e60829a8ebd489a1c6101`
- `run_full_map_smoke.py`: `5982185d9071a6e70fb745248bc9a27cb3bdf5184abf7c088597430ccc5c8086`
- `test_weather_full_map.py`: `ed1ef408fde58fae4d99f76b4e1381b5482b9670b89f69598b28d578d4454639`

### Resolved Findings

- **P1 strict weather-cap bypass: RESOLVED.** At `weather_full_map.py:210-216`,
  a supplied cap now fails unconditionally when exceeded; `strict_weather_cap`
  only controls missing-cap handling. With `weather_cost_cap=0.0`, both
  `strict_weather_cap=True` and `False` return
  `admissible=False`, `weather_cost_cap_satisfied=False`, and
  `issues=['weather_cost_cap']`. The regression test
  `test_raw_measurement_mode_cannot_bypass_an_explicit_failed_weather_cap`
  passes.

- **P1 policy full-information interface: RESOLVED within the supported slot
  capacity.** `_policy_state_features` at `442-472` serializes every active
  physical slot and all targets into `global`; observation concatenates it at
  `518-526`; PPO/A2C forward that tensor at `rl_algorithms.py:19-28`. The
  strict-v2 checkpoints record and successfully load `global_dim=336`, and each
  checkpoint produces finite logits for every legal action on a current
  336-dimensional observation. This replaces the former receipt-only state.

- **P2 local source manifest closure: RESOLVED.** The manifest now includes
  `lrphsd/__init__.py` at `run_full_map_smoke.py:80-81`. A fresh dynamic import
  audit found nine file-backed project-local modules and all nine are present;
  no loaded source was unmanifested. The nine strict-v2 report hashes match the
  current source bytes, including `lrphsd/__init__.py`.

- **Original static cost bound: no P0/P1 found.** In the original
  over-cap-route counterexample, actions `1` then `3` remain legal because their
  necessary bounds are respectively `52.82809041582063` and
  `59.4947570824873` below anchor cost `63.614983674153265`; the final target
  action has lower bound `65.56760513290962` and is masked. For the synthetic
  anchor route, every executed physical action had lower bound at or below the
  anchor, and terminal independent replay remained original-admissible and
  exactly equal to the anchor cost. This is the correct behavior for a necessary
  (rather than complete) decode-time bound, backed by exact terminal scoring.

### New P1: Policy-slot capacity guard checks stations, not physical slots

`MAX_POLICY_SLOTS` is eight, and the global state table allocates nine values per
physical slot. But `WeatherFullMapEnv.__init__` checks
`len(self.target_pools) > MAX_POLICY_SLOTS` at `weather_full_map.py:249-254`.
`target_pools` contains every station, while the encoded resource is
`self.slots`, where each active DABS supplies two physical slots.

This fails in both directions:

1. Five active DABS have only five stations but ten physical slots. Construction
   passes the guard, then the feature vector is 354 values instead of 336 and
   `observation()` raises `AssertionError: forecast encoding dimension changed`.
2. Nine stations with one active SABS have one physical slot but are rejected
   before reset with `ValueError: v1 policy-state table capacity exceeded`.

The capacity contract must be checked against `len(self.slots)` after active
slots are built; a distinct station-count limit should exist only if the model
actually encodes one. Add both boundary tests. Until then, the 336-dimensional
policy state is valid only for deployments whose physical slot count is at most
eight and whose station count is also at most eight.

### Strict-v2 Artifact And Test Verification

`full_map_smoke_20261104_strict_v2/full_map_smoke_report.json` exists with four
updates, eight episodes per update, and six complete PPO/A2C rows. Its seven
artifacts comprise the report and six checkpoints. Each checkpoint's recorded
algorithm, seed, runtime receipt, source manifest, `global_dim=336`, and
`candidate_dim=18` match the report. Independent `weights_only=True` loading,
strict state-dict loading, and restored greedy decoding reproduced each stored
result by canonical JSON comparison.

```bash
python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
```

Result: exit `0`; `Ran 37 tests`; `OK`.

The runner's own `checkpoint_reload_verified` flag (`run_full_map_smoke.py:179-187`)
currently proves strict structural restoration, not an in-run restored-model
decode. Independent strict-v2 restored decoding passed, so this is a P2 receipt
strength gap rather than a current behavioral failure.
