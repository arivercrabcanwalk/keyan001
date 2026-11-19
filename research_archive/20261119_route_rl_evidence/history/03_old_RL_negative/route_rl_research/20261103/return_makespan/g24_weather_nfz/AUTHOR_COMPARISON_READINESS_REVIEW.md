# Author-Algorithm Comparison Readiness Review

Date: 2026-11-04 (Asia/Shanghai)  
Scope: read-only inspection of the current `g24_weather_nfz` Windows bundle,
runbook, execution entrypoints, author wrapper, and approved comparison state.
No source, data, bundle, remote host, or prior result was changed.

## Decision

**NOT READY for a true author-algorithm weather/RL comparison on Windows.**

The current V3 ZIP is a hash-verifiable, CPU-only **synthetic engineering
smoke bundle**.  It can exercise the weather/NFZ unit tests, a hard-coded
five-target PPO/A2C fixture, and an isolated J1b author fixture after its
Windows executable-path defect is fixed.  It cannot execute the approved
per-map comparison: Liu `R_Liu` anchor on every new map, strict original-cost
admission, matched 6 s and 12 s route-improvement runs, strongest same-objective
non-RL controls, and paired map statistics.

This is consistent with the approved state: `STATE.json` records zero new
development maps, zero research-map quality calls, G3 quality runs pending, and
defines the required reference as one complete feasible Liu solution per new
map with `C(candidate) <= C_Liu + 1e-7` at both 6 s and 12 s.

## What The Current Windows Path Actually Runs

1. `build_windows_bundle.py:1-7,29-46` explicitly constructs a minimal
   synthetic-smoke closure.  Its only author input is
   `g23/author_baseline/synthetic_smoke/fixture.txt`; registered/development/
   formal maps, prior outputs, and checkpoints are explicitly excluded.
2. `run_windows_smoke.ps1:57-75` verifies the bundle, builds a venv, runs four
   test modules, invokes `run_full_map_smoke.py --smoke`, compiles J1b/J2b, and
   runs J1b on that one fixture.  There is no manifest loop, no author/RL
   hand-off, no non-RL family, and no 6 s/12 s command.
3. `run_full_map_smoke.py:42-61` creates its instance, static route anchor,
   wind knots, and NFZ in source.  Its only runtime switch is `--smoke`;
   without it the CLI exits with `only the explicit synthetic --smoke fixture
   is available` (`:222-230`).  The report itself says it is not an author-map,
   registered, or Formal result (`:200-208`).
4. `WINDOWS_RUNBOOK.md:3-8,55-69` makes the same boundary explicit: no
   registered maps, author quality comparison, 6 s/12 s matrix, new map
   generation, or research training is packaged or run.
5. The bundle archive is locally self-verified: V3 SHA-256 is
   `5c09ff8e96af5eb8f18ee12561ec73a12ade87c8f22e2285416f96d2e3888abc` and
   `WINDOWS_BUNDLE_V3_VERIFICATION.md` records 40 local unit tests passing.
   This establishes only archive closure and local synthetic execution.

## Author Baseline Status

`g23/author_baseline/author_runner.py` is a useful one-instance static-LRPHSD
anchor wrapper.  It accepts an arbitrary textual LRPHSD input, verifies locked
J1b/J2b sources, retains raw author output, independently validates feasibility
and cost, and checks the author-reported latest time against `M_return`
(`author_runner.py:278-333`).  Thus it can produce an auditable `R_Liu` once
given a frozen map, a prospective seed, a compatible JDK, and a declared
timeout.

It is **not** a weather comparison runner.  It accepts neither weather/NFZ
scenario input nor a weather anchor policy; it does not call
`weather_full_map.py`; and it does not execute or score RL/non-RL candidates.
The current PowerShell entrypoint only uses its J1b fixture invocation.

### P0: Windows JDK Path Defect

The supplied smoke route cannot complete author preparation on a normal Windows
JDK as written.  `run_windows_smoke.ps1:37-40` correctly validates
`bin\\java.exe` and `bin\\javac.exe`, while `author_runner.py:126-139` looks
only for `java_home / "bin" / "java"` and `... / "javac"`; `command_for()`
also emits `bin/java` (`:202-212`).  Those extensionless paths are not regular
executables in a standard Windows JDK.  Since PowerShell calls `prepare` at
`:72-74`, the first author compile will fail with a missing JDK executable
before it can run even the synthetic author fixture.

This defect has not yet been exercised on Windows because
`WINDOWS_EXECUTION_ATTEMPT_20261104.md:5-27` records refused SSH forwarding
(exit 255) and no transfer, Python setup, JDK compile, author run, or
registered-map run.

## Comparison-Specific Gaps

### P0: No registered data or author anchors are in the bundle

The ZIP manifest deliberately rejects additional payload files.  It therefore
contains no new constraint-reconstructed map, exposure-screened map manifest,
per-map seed, `R_Liu`, author witness, or weather/NFZ scenario.  The existing
`g23<EXECUTION_PATH>` is generator engineering plus exclusion manifests; it
does not contain the frozen study-map allocation or generated research maps.

### P0: No executable comparison orchestrator

There is no entrypoint that, for each frozen map, derives the author seed,
creates and validates `R_Liu`, freezes its fixed deployment/station types/
target owners, loads the common weather scenario, then calls every candidate
from that same anchor.  `WeatherFullMapEnv` supports the required fixed-outer
physical route state, but it is a Python API, not a map/scenario loader and
registered comparison runner.

### P0: The fair-cap and weather-anchor semantics are not frozen

The approved primary rule is original full cost
`C(candidate) <= C(R_Liu) + 1e-7`, with `M_return` compared per map.  The
weather package additionally requires a common weather cost cap; its protocol
requires that cap to come from a common feasible reference in the same weather
scenario (`EXPERIMENT_PROTOCOL.md:19-24`).  A frozen comparison protocol must
say, before any quality run, whether and how the static Liu `R_Liu` is replayed
under weather, what happens when it is weather-infeasible, and how original
cost admission and weather-domain admission jointly determine eligibility.
The hard-coded fixture currently uses a synthetic static route and its own
weather cap, not `R_Liu`.

### P0: No matched quality controls, time ledger, or analysis pipeline

The path includes synthetic greedy, PPO, and A2C only.  It does not implement
or execute the frozen Liu-faithful route control including load-balance
insertion, a same-objective joint min-max non-RL control, a threshold/min-max
control, or the required ordinary direct-route RL control.  It also has no
common cold-start 6 s/12 s wall-clock ledger that charges loading, candidate
generation, validation, retries, model inference, fallback, and failures.
There is no per-map result table or paired bootstrap/statistical-family
analysis.

### P1: Windows runtime provenance remains incomplete

Windows was never reached.  The V3 runbook freezes Python 3.13 and package
versions but explicitly states that accepted Windows interpreter and wheel
artifact hashes are still unfrozen (`WINDOWS_RUNBOOK.md:71-73`).  The current
requirements file is not a `--require-hashes` wheel lock.  A successful
Windows comparison also needs a recorded CPU model/core allocation, JDK binary
hash/version, Python/PyTorch/NumPy wheel hashes, source/bundle manifest, and
per-command stdout/stderr.

## Required Artifacts Before A Windows Comparison Run

The following are concrete required inputs/deliverables.  They must be frozen
and hash-recorded before the first research-map author run; no existing smoke
result may be promoted in their place.

| Category | Required artifact | Required contents |
|---|---|---|
| Data identity | `study/MAP_MANIFEST.json` and immutable `study/maps/*.txt` | Map partition/family/ordinal, raw input SHA-256, canonical geometry identity, generator version/namespace/trace, and an exclusion decision against official, pilot, and synthetic identities. |
| Weather identity | `study/WEATHER_SCENARIO_MANIFEST.json` and one serialized scenario per map | Map hash binding; wind knots; NFZ vertices/on/off interval; flight/energy parameters; scenario hash; fixed policy for weather-infeasible author anchors. |
| Author plan | `study/AUTHOR_ANCHOR_FREEZE.json` | J1b primary profile and source lock; prospective per-map seed namespace and derived seed; Java/JDK identity; timeout; expected output path; declaration that J2b is sensitivity-only and never selected per map. |
| Author results | `study/author_anchors/<map-id>/` | `RUN.json`, raw `reference.json`, complete `solution.json`, independent evaluator result, `return_score.json`, stdout/stderr, hashes, and an `anchor_eligible` decision for each map. |
| Scientific protocol | `WEATHER_AUTHOR_COMPARISON_PROTOCOL.md` | D-only claim boundary; original and weather cap semantics; `R_Liu` replay rule; fixed outer fields; all comparators; 6 s/12 s definition; startup/loading/validation/fallback accounting; failure denominator; seed/checkpoint policy; paired statistics and multiplicity rule. |
| Source: platform fix | Updated `author_runner.py` plus `test_author_runner_windows_paths.py` | Resolve and invoke `java(.exe)`/`javac(.exe)` through one platform-aware JDK helper; cover Windows `JavaHome` paths and run at least the author fixture on actual Windows JDK17. |
| Source: ingestion | `weather_scenario_io.py` plus tests | Strict parse/validate/hash of the frozen weather scenario serialization, including schema bounds and map binding; no hard-coded research scenario. |
| Source: orchestration | `run_author_weather_comparison.py` and `run_windows_comparison.ps1` | Reject unlisted/mismatched inputs; run author anchors; materialize fixed-outer candidates; invoke all frozen methods from the same anchor; enforce both admissibility checks; preserve every failed/late/dead-end result; write a complete ledger. |
| Source: controls | Frozen implementations/configs for author-faithful, same-objective non-RL, ordinary direct-route RL, and required simple controls | Each receives identical map/scenario/anchor, information, action legality, cost caps, 6 s/12 s budget, and post-processing policy. |
| Validation | `comparison_validator.py` and independent replay receipts | Per candidate, preserve original evaluator/scorer result, weather replay, cost deltas from `R_Liu`, `M_return` deltas, feasibility/admission status, and output hashes. |
| Analysis | `analyze_author_comparison.py` and frozen analysis schema | Per-map paired data; valid/on-time/fallback rates; W/T/L; mean/median; map bootstrap 95% CI; comparison-family correction; no seed/checkpoint/method selection after viewing quality results. |
| Windows closure | New comparison bundle, `WINDOWS_COMPARISON_MANIFEST.json`, and `requirements-windows.lock` | Include all frozen sources, maps, scenarios, configurations, controls, and no prior quality outputs; lock interpreter and exact wheel artifacts with `--require-hashes`; record the actual Windows execution receipt. |

## Permitted Interpretation Of Existing Evidence

The V3 archive may be described as locally verified synthetic engineering
infrastructure after its JDK path defect is fixed and after an actual Windows
smoke is captured.  It does **not** support a claim that Liu was run on
Windows, that an author baseline was compared with weather/RL, that RL improved
`M_return`, or that any G3/G4 quality gate has started or passed.
