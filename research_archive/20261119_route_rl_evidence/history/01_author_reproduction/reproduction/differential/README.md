# Empty-Station Repair Differential

This diagnostic does not edit the frozen reviewer package. It compares Java J1b
repair operators 2/3 against Python v5 and the r6 native kernel for one opened
DABS with two empty drone slots and one covered, individually feasible target.

The frozen Python/C behavior returns the destroyed state for both operators.
The J1b methods can create a singleton route on the first eligible empty drone.
The source distinction is in `RoutingOperator.loadBalancingInsertion` and
`prioritizedInsertion`: both iterate the two entries of an opened DABS even
when each drone's route list is empty. Python `covered_drones` and C
`covered_pairs` currently skip the station when both route counts are zero.

## Local C/Python Test

Compile baseline and patched native kernels for the current host, then run the
regression test:

```sh
cc -O2 -dynamiclib -o reproduction/differential/patch/libr6kernel_baseline.dylib reproduction/reviewer_package/native/r6_kernel.c -lm
cc -O2 -dynamiclib -o reproduction/differential/patch/libr6kernel_patched.dylib reproduction/differential/patch/r6_kernel.c -lm
PYTHONPATH=reproduction/reviewer_package python reproduction/differential/test/test_empty_station_repair.py
```

On Linux, use shared ELF libraries instead of the macOS dylibs:

```sh
cc -O2 -fPIC -shared -o reproduction/differential/patch/libr6kernel_baseline.so reproduction/reviewer_package/native/r6_kernel.c -lm
cc -O2 -fPIC -shared -o reproduction/differential/patch/libr6kernel_patched.so reproduction/differential/patch/r6_kernel.c -lm
PYTHONPATH=reproduction/reviewer_package python reproduction/differential/test/test_empty_station_repair.py
```

The fixture is shared across implementations: a station at (0,0), a target at
(100,0), service energy 0.01, service time 2 minutes, and default Liu
parameters. Local C/Python uses station id 10 and the Java probe uses station
id 100; both IDs preserve the same geometry while avoiding Java's reserved
node id 0 route-separator behavior. Both DABS drones can serve the target. The
tests verify both operators before
and after the patch, check independent feasibility, and verify that an
infeasible singleton still rolls back. The SABS case is separate because J1b's
storage guard rejects slot 0 at an SABS even though the physical evaluator
merges that storage slot with the small drone.

## Java J1b Probe

Run on a host with JDK 17. Set `PKG` to the frozen reviewer package on that
host and `PROBE` to this checkout's `EmptyStationRepairProbe.java`:

```sh
PKG=/path/to/reproduction/reviewer_package
PROBE=/path/to/reproduction/differential/java/EmptyStationRepairProbe.java
OUT=<EXECUTION_PATH>
mkdir -p "$OUT"
javac -encoding UTF-8 -d "$OUT" "$PKG"/reference/java/J1b_source/*.java "$PROBE"
java -cp "$OUT" test1.EmptyStationRepairProbe 2
java -cp "$OUT" test1.EmptyStationRepairProbe 1
```

The probe was compiled against the pinned J1b source and run over the existing
SSH connection. The exact command and five literal output lines (including the
nearest-insertion whole-candidate rollback case) are in `VERIFICATION.txt`.

For DABS (`kind=2`), both ops should report `slot0` containing target 1,
`source_guard=true`, and `equal_cost_accept_after_guard=true`. For SABS
(`kind=1`), J1b still writes slot 0 but `Round4Guard` rejects that storage
shape; do not use it as the DABS parity conclusion.

## Proposed Isolated Patch

The patched full source copies are `patch/fidelity_ops_v5.py` and
`patch/r6_kernel.c`. `empty_station_repair.patch` contains their exact delta.
Empty whole-station receivers are enabled only for repair operators 2/3;
nearest and min-regret retain the source's existing-route-only behavior.

## Deterministic Operator Matrix

`matrix/run_operator_matrix.py` runs isolated Java/Python/native probes without
editing the frozen reviewer package. It compares all four location operators,
local operators 0-4, and destroy operators 0-3 over deterministic Java RNG
seeds. Destroy results include removed-target sets and post-call RNG sentinels.
Repair operators 0-3 run against a normal insertion fixture, two symmetric
equal-delta insertion choices, a near-capacity/duration fixture, and an ordered
multi-pending boundary fixture. Repair checks compare Java, baseline
Python/C, and the isolated patched Python/C copies. Native repair records raw
and wrapper-final routes; the wrapper reproduces `tsalns_v6` by cloning a
backup slot, checking `valid(slot, True)`, and restoring invalid candidates.
Baseline and patched C both produce an invalid extra trip for repair 0/1 on the
single-target duration fixture; the caller rolls it back. The multi-pending
fixture checks that later pending targets do not escape this caller-level
rollback behavior.

Compile the native libraries using the platform commands above, then run from
the repository root on a host with the configured SSH key and pinned JDK 17
package on the reproduction server:

```sh
python3 reproduction/differential/matrix/run_operator_matrix.py --seeds 16
```

The Java probe source is uploaded to `/tmp`, compiled against the pinned
`reference/java/J1b_source` package, and run remotely. CLI flags allow replacing
the host, port, key, JDK path, package path, run ID, and seed count. A nonzero
exit reports at least one candidate-state, removed-set, RNG-sentinel, or repair
wrapper mismatch. Exact counts, literal output, and the multi-pending rollback
witness are recorded in `matrix/RESULTS.md`.
