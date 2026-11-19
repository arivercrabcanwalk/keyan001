# Capacity And Policy-State Review

Date: 2026-11-04.  Scope: read-only review of `weather_full_map.py` state
encoding, active physical-slot capacity guard, original-cost lower bound, and
fit to the official LRPHSD map scale.  No source files were changed and no
training or research-map solve was run.

## Reviewed bytes and evidence

| Item | SHA-256 / source |
|---|---|
| `weather_full_map.py` | `aac5536d13e3b32f3ff2c10712eb32a542f541b15b7ae8a6c5e62577c9e978fd` |
| `weather_policy.py` | `6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826` |
| `../scorer.py` | `c6e156b2d770cec2f663eada37c2d39bff1583f672bda4116f81493484409135` |
| `test_weather_full_map.py` | `617713eef9276610709c69395535785520151a98284106b7fbd8c402c6971029` |
| official input | `<LOCAL_PATH>`, SHA-256 `09e0c708493a60a070f5c6be39f48cea5c3bfc6e6d6a44d2e91f9c4d8910750f` |
| frozen feasible anchor | `<LOCAL_PATH>` |

```bash
python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
# exit 0
# Ran 38 tests in 1.008s
# OK
```

## Findings

### P1: Mixed coordinate normalizations create a Markov-state alias under NFZs

The claimed policy state is not Markov for the weather/NFZ environment.
`_forecast_features` normalizes NFZ vertices by
`max(abs(node.x), abs(node.y))` over all nodes (`weather_full_map.py:431-438`).
Slot and target coordinates are normalized by `large_radius`
(`:452-475` and `:477-513`).  The ratio between these two scales, and inactive
station coordinates that determine the NFZ scale, are not supplied to the
policy.  `weather_policy.py:26-42` receives exactly `global`, `candidates`, and
`mask`; it has no other instance input.

Minimal deterministic reproduction used two stations, with only station 0
active and two targets at `(50,50)` and `(150,0)`.  In state A, an inactive
station at `(1000,0)` sets the NFZ normalization scale to 1000 and the NFZ is
the square `(95,20)-(105,30)`.  In state B, its inactive station is `(2000,0)`
and the NFZ square is exactly doubled, `(190,40)-(210,60)`.  All active physical
objects are identical.  The normalized NFZ vertices, policy state tensor,
candidate matrix, and mask are consequently exactly equal.  The same legal
physical action `(station=0, slot=0, target=1)` is then applied in each state.
It leaves the global tensor equal, but the next candidate matrix differs because
the first NFZ intersects the subsequent `target1 -> target2` leg and the second
does not:

```text
initial_global_equal True
initial_candidates_equal True
initial_mask_equal True
after_same_action_global_equal True
after_same_action_candidates_equal False
after_target2_out_min 0.0001252438814844936 0.0001243503502337262
```

This violates the Markov condition: the same policy observation and action do
not determine the next policy observation.  It is not repaired by the action
mask because the difference concerns a later physical leg.  Use one declared
coordinate scale for targets, stations, slots, and NFZ vertices, or serialize
the NFZ scale ratio plus every coordinate needed to reconstruct the common
frame.  Add this alias pair as a regression test before treating PPO/A2C input
as a full Markov state.

## Capacity Guard: Current Status PASS

The reviewed source sets `MAX_POLICY_SLOTS = 20`, `MAX_POLICY_TARGETS = 128`
(`weather_full_map.py:31-34`), and derives
`global_dim = 40 + 9 * MAX_POLICY_SLOTS + 7 * MAX_POLICY_TARGETS = 1116`
(`:234`). `physical_slots` sums actual available slots across active stations
before reset (`:251-257`); reset builds precisely those slots (`:261-267`).

The official `10_110_7` input and frozen joint anchor now construct:

```text
{'stations': 10, 'targets': 110, 'active_stations': [0, 2, 4, 5, 6, 7, 8, 9],
 'physical_slots': 15, 'limits': (20, 128), 'global_dim': 1116,
 'observed_global_shape': (1116,), 'candidate_count': 227}
```

`test_policy_capacity_uses_active_physical_slots_not_station_count` is in the
38-test pass. It rejects 11 active DABS (22 physical slots) while accepting a
21-station instance with only one active SABS slot. No P0/P1 capacity defect
remains in the reviewed 20-slot/128-target envelope. Existing 336-dimensional
checkpoints are historical synthetic artifacts and are incompatible with the
new 1116-dimensional model contract.

## Items reviewed without a P0/P1 finding

### Original-model cost lower bound

`_original_lower_bound` (`weather_full_map.py:290-314`) accumulates already
committed original travel/service in `static_operating_min`, adds the proposed
direct original leg and service, adds a direct return for every open trip, and
adds all unserved service.  These terms are necessary components of the original
scorer's travel/service accounting (`../scorer.py:150-198`).  At a terminal
state, no target or open-return term remains, so the bound equals the decoded
original operating cost. Independent terminal replay invokes
`validate_candidate` with epsilon zero at `weather_full_map.py:129-132`; the
decode-time original-cap check remains at `:393-399`.

The existing over-cap regression
`test_original_anchor_cap_remains_a_terminal_admission_requirement` passed in
the 38-test run. I found no P0/P1 false acceptance or false rejection in this
necessary-bound construction.  It is deliberately not a complete route lower
bound, which is appropriate for a decode-time feasibility guard rather than an
optimality claim.

### Other state fields

Within the supported 20-slot/128-target envelope, the tensor includes every
active slot's current relative location, accumulated clock, trip energy,
open-trip status and static original operating time (`:456-465`); every target's
location, service, energy, owner and remaining flag (`:466-475`); and all
allowed forecast knots/NFZ schedule/vertices (`:419-443`). Candidates provide
action-specific projected route, energy, duty and weather-cap values
(`:477-513`). This resolves the earlier receipt-only-state defect, but it does
not cure the common-coordinate-frame alias in P1.

## Required disposition

The official `10_110_7` map is representable by the environment, subject to
normal feasibility/weather evaluation. Block any Markov-state claim for NFZ
scenarios until P1 has a regression-tested representation fix. Retain the
current physical-slot guard and original-cost lower bound.
