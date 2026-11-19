# Implementation Audit: Weather/NFZ Route Package

> **Historical pre-implementation audit.** This read-only audit captured the
> single-station code state before `weather_full_map.py`, `weather_replay.py`, and their
> tests were added. Its recorded commands/evidence remain historical; its P0 claims about
> the then-current implementation are superseded by the new modules, while its research
> protocol and Windows findings remain applicable.

Date: 2026-11-04 (Asia/Shanghai)  
Scope: read-only audit of `weather_oracle.py`, `weather_env.py`, `weather_policy.py`,
`rl_algorithms.py`, `run_experiment.py`, tests, and the configured Windows execution
route. No production/source module, remote system, SSH configuration, or remote file
was modified by this audit.

## Disposition

**Engineering smoke package only; not admissible as a multi-station, heterogeneous-slot
LRPHSD D-quality runner.** It correctly keeps its policy action physical in the tested
fixture (target or `RETURN`), and its documents already state that it cannot replace the
original multi-station/heterogeneous-slot `M_return` comparison
([`EXPERIMENT_PROTOCOL.md:5-8`](EXPERIMENT_PROTOCOL.md)). It must remain outside G3/G4
quality evidence until the blockers below are addressed under a separately frozen
protocol. No RL performance, novelty, LRPHSD superiority, calibrated-weather, or
Windows-execution claim is supported by the current artifacts.

## Blocking Findings

### P0 - The environment has one station and one physical execution slot

`WeatherInstance` has one `station` and no station identity, station type, slot set, or
target-to-station map ([`weather_env.py:44-72`](weather_env.py)). `WeatherRouteEnv`
holds one position, one trip, one battery, and one cumulative-duty clock
([`weather_env.py:106-118`](weather_env.py)); actions are only `RouteAction(target_id)`
or `RouteAction()` ([`weather_env.py:75-82`, `235-280`](weather_env.py)). Its
`M_return` is that serial clock ([`weather_env.py:344-358`](weather_env.py)).

This cannot represent a SABS/DABS station, LD/SD eligibility, `(slot,target)` or
`(slot,RETURN)` actions, per-slot battery/duty, concurrent slot clocks, or full-map
`max(slot duty)` makespan. The project LRPHSD route contract already has those required
objects in `global_env.py`: `RouteAction(slot, target_id)` at lines 11-18,
station-dependent slot availability/capacity at 25-60, and full-map `M_return` as a
maximum of station slot loads in `scorer.py:184-215`. A weather implementation needs to
be an adapter inside that domain, not a replacement single-vehicle model.

### P0 - The trained objective is MTC, not the approved primary M_return endpoint

Every target action rewards `-completion / number_of_targets`
([`weather_env.py:310-321`]). The pipeline test explicitly confirms the total reward is
negative MTC, not `M_return` ([`test_weather_pipeline.py:83-90`]). PPO and A2C consume
those rewards unchanged ([`rl_algorithms.py:38-70`, `99-199`]); the smoke report prints
MTC and cost but not policy `M_return` ([`run_experiment.py:168-179`]).

The current approved primary comparison is per-map, strict-cost-capped `M_return`.
MTC remains under metric review in the current state. Consequently this package cannot
be used to train, select checkpoints, rank methods, or state an effect for the approved
endpoint. It would require a predeclared reward/objective relation, selection rule, and
reports for full-map `M_return`; an auxiliary MTC analysis must remain secondary and
fixed before quality runs.

### P0 - Cost/feasibility semantics are not the original full-map anchor semantics

The fixture accepts a single constant fixed cost and time-only variable cost
([`weather_env.py:44-67`, `121-131`]), whereas the LRPHSD scorer preserves fixed
station/drone charges plus total all-slot operating time and validates the complete
solution (`scorer.py:103-215`). The fixture cap is a necessary lower-bound mask, not a
completion certificate ([`weather_env.py:168-202`]); an over-cap route is detected only
after terminal return ([`weather_env.py:322-329`]). The smoke deliberately uses a
relaxed `1.25 * nearest-reference cost` allowance ([`run_experiment.py:131-162`]), not
the approved per-map `C(candidate) <= C(Liu) + 1e-7` rule.

This is appropriate for an isolated smoke test, but it is not a shared Liu anchor, does
not preserve original fixed-cost accounting, and has no authoritative complete-solution
validator. Promotion requires every weather-aware candidate to be materialized in the
existing full-map solution format and accepted by `validate_candidate` (`scorer.py:261-290`)
under the frozen author anchor. All failed/dead-end/over-cap candidates must be retained
and charged in the same 6 s/12 s run budget.

### P1 - The claimed independent replay is not an independent weather oracle

`replay_trips` describes itself as an "Independent physical replay"
([`weather_env.py:362-364`]), but calls the same `plan_route` implementation as the
environment for each outbound and return leg ([`weather_env.py:385-406`](weather_env.py)). The pipeline
test's NFZ check imports private `_integrate_leg`, `_inside_distance_interval`, and
`_time_at_distance` from that same module ([`test_weather_pipeline.py:18-35`]). This
does independently exercise the environment state machine, but it cannot independently
detect a shared geometry, temporal-overlap, or wind-integration defect.

The wording should be limited to an independent *state replay* until a second oracle is
implemented. Required tests include a separate geometry/time implementation or a
trusted reference fixture, exact boundary cases, station/target inside-buffer rejection,
and randomized differential cases.

### P1 - Weather/NFZ model is intentionally narrow and can under-model temporal routing

The oracle supports one spatially uniform, piecewise-constant wind field and one strict
convex NFZ ([`weather_oracle.py:52-75`, `96-121`, `277-340`]). It enumerates only simple
paths and explicitly supplies neither `WAIT` nor cycles ([`weather_oracle.py:9-12`](weather_oracle.py)).
The experiment protocol repeats this limitation ([`EXPERIMENT_PROTOCOL.md:9-15`](EXPERIMENT_PROTOCOL.md)).
With time-varying wind or a temporary NFZ, waiting can be the only or best legal temporal
choice; a "no legal path" result therefore means no immediate/simple-path solution in
this model, not no physically feasible mission under a model that allows waiting. The
visibility graph also permits boundary travel because only positive-length interior
overlap is rejected ([`weather_oracle.py:157-194`, `323-330`](weather_oracle.py)).

Those are defensible explicit simplifications for a synthetic fixture. They are not
validated weather operations, and must not be silently inherited by LRPHSD. Before use
in a registered scenario, freeze whether waiting, multiple/buffered zones, boundary
clearance, spatial wind variation, launches, charging, and turnaround are part of the
model, then give all controls identical information and action availability.

### P1 - No registered experiment runner, comparator suite, selection rule, or ledger

`run_experiment.py` only exposes `--smoke` ([`run_experiment.py:183-198`]), builds one
five-target hand-written instance ([`run_experiment.py:28-42`]), trains four updates,
and greedily evaluates the last model without checkpoint selection/validation
([`run_experiment.py:111-128`]). It has no map manifest/hash/exposure exclusion,
author `R_Liu` anchor, 6 s/12 s timer, candidate ready-time measurement, process or CPU
ledger, frozen non-RL controls, bootstrap analysis, or complete-witness archive.

The required G2/G3 D protocol calls for fixed station types and target-station ownership,
station-internal slot assignment, a same-author-anchor route budget, full independent
validation, and the author plus strongest same-objective non-RL control
([`g23/nonrl_data_protocol/G23_PROTOCOL_AUDIT.md:44-55`]). None is wired to this package.
The output contains no model checkpoints or device/hardware manifest and no Python/
PyTorch dependency lockfile. It therefore has no reproducible Windows or clean-host
execution package.

## Test Evidence And Gaps

Observed commands, from this directory:

```text
python3 -m unittest -v test_weather_oracle test_weather_pipeline test_rl_algorithms
Ran 20 tests in 1.113s
OK

python3 run_experiment.py --smoke --output-dir <EXECUTION_PATH>
exit 0

python3 -m unittest -v test_g1.py   # parent LRPHSD G1 suite
Ran 37 tests in 0.010s
OK
```

The full smoke retained failures rather than deleting them. For both PPO and A2C, seed
103 failed; seed 211 completed under the synthetic cap but had MTC `8.1890617464`, worse
than the nearest-reference MTC `7.3078521913`; seed 307 equalled that reference. This is
an engineering integration outcome, not evidence that either algorithm improves any
endpoint.

Existing coverage verifies basic wind knots, crosswind failure, one convex-zone routing,
masked actions, finite PPO/A2C updates, and fixed-seed update reproducibility. It does
not verify:

- multiple stations, SABS/DABS slot eligibility, LD/SD assignment, parallel starts, or
  global maximum return time;
- equality with the original evaluator for weather-aware full solutions, exact
  `C_Liu + 1e-7` admission, or an anchor fallback/failure denominator;
- a separate oracle, multiple zones, zone-start/zone-end containment, clearance policy,
  waiting, time-dependent path counterexamples, or spatially varying winds;
- model save/load, CPU/GPU device parity/determinism, dependency installation, timed
  process startup/model load/validation, checkpoint selection, or an out-of-sample map
  split;
- matched random/greedy/beam/author-faithful/same-objective non-RL controls, 6 s/12 s
  accounting, three training-seed aggregation, map-level paired statistics, or retained
  raw failure artifacts.

Local execution used Python `3.14.0`, PyTorch `2.13.0`, NumPy `2.4.4`, and CPU only
(`torch.cuda.is_available() == False`). These are local engineering observations, not a
Windows or GPU result.

## Windows And Tunnel Verification

`<REMOVED_SSH_PATH>` was read without alteration. It defines `windows` as user `12198` at
`<NETWORK_ADDRESS>` through `ProxyJump lighthouse`; `lighthouse` is `ubuntu@<NETWORK_ADDRESS>`.
Resolved configuration contains no `LocalForward`, `RemoteForward`, or `DynamicForward`.
There is no `lighthouse` executable; the configured value is an SSH host alias.

All SSH checks used `BatchMode=yes`, a connection timeout, and a temporary
`UserKnownHostsFile=/dev/null` override. They only ran read-only remote commands.

```text
ssh lighthouse <hostname/date/listener inspection>
HOST=VM-0-7-ubuntu
LISTEN_2222=<none; listener listing only had its header>
EXIT=0

ssh windows <read-only Windows inventory command>
channel 0: open failed: connect failed: Connection refused
stdio forwarding failed
EXIT=255

ssh windows-lan <hostname>
ssh: Could not resolve hostname laptop-ojak8vmj.local: nodename nor servname provided, or not known
EXIT=255
```

For the local-forward test, a temporary SSH process created
`<NETWORK_ADDRESS> -> lighthouse:<NETWORK_ADDRESS>`; `lsof` observed the local listener and
`nc -vz <NETWORK_ADDRESS> 22399` connected to it. The SSH process was then killed and waited
for successfully; a post-check found no `22399` listener. The local listener proves
client-side forwarding works. The direct `ssh windows` result and the absent Lighthouse
`:2222` listener prove the reverse-tunnel endpoint is not presently available.

Windows was not reached, so no Windows Python, GPU, or project-path inventory exists.
No remote job, transfer, deployment, process start, configuration change, or deletion
occurred.

## Required Promotion Sequence

1. Freeze the weather scenario contract and decide whether it is a purely synthetic
   stress dimension or an LRPHSD model extension. Preserve the original evaluator as the
   authority unless a weather-aware replacement is independently specified and tested.
2. Implement a weather adapter for the existing fixed-station full-map action domain:
   actions remain only `(slot,target)` and `(slot,RETURN)`, while each slot has its own
   position, trip state, energy, duty, and clock. `M_return` must be the maximum final
   slot clock, with all slots starting at zero.
3. Build an independent complete-solution scorer/oracle, connect the existing author
   anchor and `C <= C_Liu + 1e-7` test, and add multi-station/heterogeneous-slot,
   weather-boundary, fallback, and differential tests before any new map quality call.
4. Freeze the G2/G3 manifest, common anchor, controls, cost/ready-time ledger, and
   statistics. Only then add a registered runner with all outcomes and checkpoints
   retained; do not reuse the smoke fixture for training, tuning, validation, or Formal.
5. Restore a live reverse tunnel or a resolvable LAN endpoint, then run a read-only
   Windows inventory and a clean CPU/GPU smoke with a pinned environment. Windows access
   alone does not authorize map generation, training, or quality runs.

## Artifact Integrity

At audit time SHA256 values were recorded for the package's eight source/test files;
this audit did not alter them. The directory remains an untracked isolated package. This
audit adds only `IMPLEMENTATION_AUDIT.md`.
