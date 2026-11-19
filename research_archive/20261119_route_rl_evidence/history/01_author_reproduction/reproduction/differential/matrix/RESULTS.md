# Operator Matrix Results

Date: 2026-11-02

## Scope

The probes compare pinned Java J1b behavior with frozen Python v5, baseline C,
and the isolated empty-station patch. Production/frozen source files were not
edited. The matrix covers four location operators, local operators 0-4, destroy
operators 0-3, and repair operators 0-3. Stochastic operations use seeds 0-15;
repair fixtures are deterministic.

Repair fixtures cover ordinary insertion, symmetric equal-delta choices,
duration-boundary rollback, and an ordered multi-pending duration boundary. The
multi-pending witness uses one DABS at (0,0) with routes `[[[[1]],[]]]`. Target
1 is at (100,100), energy 0.01, service 2; target 16 is at (900,0), energy
0.964, service 598; target 14 is at (600,500), energy 0.01, service 2. Repair
operator 1 receives pending IDs `[16,14]` in that order.

## Matrix Run

Command:

```sh
python3 reproduction/differential/matrix/run_operator_matrix.py --seeds 16
```

Exit status: `0`.

Literal output:

```text
OPERATOR_MATRIX rows=209 pass=209 fail=0 repair_raw_differences=baseline:4,patched:4
OPERATOR_GROUP location cases=64 pass=64 fail=0
OPERATOR_GROUP local cases=65 pass=65 fail=0
OPERATOR_GROUP destroy cases=64 pass=64 fail=0
OPERATOR_GROUP repair cases=16 pass=16 fail=0
repair0/boundary state=True rng=True api_draws=0 baseline_raw_match=False,baseline_rc=1,valid=False,rollback=True,patched_rc=1,valid=False,patched_raw_match=False,rollback=True
repair0/boundary_multi state=True rng=True api_draws=0 baseline_raw_match=False,baseline_rc=1,valid=False,rollback=True,patched_rc=1,valid=False,patched_raw_match=False,rollback=True
repair1/boundary state=True rng=True api_draws=0 baseline_raw_match=False,baseline_rc=1,valid=False,rollback=True,patched_rc=1,valid=False,patched_raw_match=False,rollback=True
repair1/boundary_multi state=True rng=True api_draws=0 baseline_raw_match=False,baseline_rc=1,valid=False,rollback=True,patched_rc=1,valid=False,patched_raw_match=False,rollback=True
```

All 209 effective candidate states and RNG sentinels match. In the four noted
raw repair cases, Java/Python return the source routes, while native C has an
invalid extra-trip candidate. For the ordered op-1 witness, both baseline and
patched C return raw routes `[[[[1],[16],[14]],[]]]` with `valid=False`; the
`tsalns_v6` wrapper restores `[[[[1]],[]]]`. Java's final feasibility guard
and Python v5's `raw_valid` guard also return `[[[[1]],[]]]`.

A trial C change that pre-filtered the duration-invalid first target was
discarded. It skipped 16, inserted 14 into the route, and returned a valid but
different final state `[[[[14,1]],[]]]`; therefore the current isolated patch
preserves the existing wrapper-level behavior instead of adding that local
filter.

## Local Regression Checks

Patched C build command:

```sh
cc -O2 -dynamiclib -o reproduction/differential/patch/libr6kernel_patched.dylib reproduction/differential/patch/r6_kernel.c -lm
```

Result: exit status `0`, no diagnostics.

Empty-station regression command:

```sh
PYTHONPATH=reproduction/reviewer_package python3 reproduction/differential/test/test_empty_station_repair.py
```

Result: exit status `0`; 4 tests passed.

The suite also includes an op-0 multi-pending regression witness: a raw native
candidate can insert both pending IDs but exceed a station duration limit;
`tsalns_v6` restores the destroyed-state snapshot, matching Python v5's
whole-candidate rollback.

Syntax check command:

```sh
python3 -m py_compile reproduction/differential/matrix/run_operator_matrix.py
```

Result: exit status `0`, no diagnostics.
