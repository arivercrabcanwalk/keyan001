# Liu Semfix Full Reproduction Results

Date: 2026-11-02. This report describes the corrected Python/native port in
this directory. The frozen pre-semfix package, source files, native binary,
results and original tarball remain unchanged under `../reviewer_package/`.

## Protocol and source identity

The rerun used 120 official `Instances_Alg` maps, seeds 0-4 and 500 outer
iterations for both Python profiles. P1 uses 100 location-local iterations and
ALNS weight upper bound 5.0; P2 uses 500 location-local iterations and upper
bound 0.5. Both use 5,000 ALNS iterations per outer candidate. These are
compared against same-seed J1b/J2b Java runs, respectively, not the historical
pre-ALNS-guard J1/J2 diagnostics.

The native source correction is limited to repair operators 2/3 accepting an
opened, still-empty station/drone receiver when Java does. The exact patch is
`differential/empty_station_repair.patch`, SHA256
`cc9b1f663e90174e6beeb8d8ecc25a37ea4638ce092a7c3fb170a25b959052c6`.
Semfix `fidelity_ops_v5.py` SHA256 is
`56508b534fb9f6956da337adef84ad96e12b50cc498eef0b44a35bf3994fb4cb`;
semfix `r6_kernel.c` SHA256 is
`121aa747ebf841f91371c5d8ef19c9010eefe72fd5641d21cd5a647fe4ffa06e`.
The remote Linux native binary used by the reruns has SHA256
`2657d2f7a9f0b00e0710cdeef1f217f23a69d0cdd81523caca81dac88ef99e5c`.

## Full run and archive evidence

The exact remote commands were:

```sh
cd <SERVER_EVIDENCE_PATH>
/opt/conda/bin/python -B run_matrix.py --profile P1 --out results/full_P1 --seeds 0,1,2,3,4 --outer 500 --timeout 600
/opt/conda/bin/python -B run_matrix.py --profile P2 --out results/full_P2 --seeds 0,1,2,3,4 --outer 500 --timeout 600
```

The terminal result for each command was:

```text
COMPLETE profile=P1 maps=120 seeds=5 failures=0
COMPLETE profile=P2 maps=120 seeds=5 failures=0
```

P1 result archive SHA256:
`0be434a811fe607136208757e218fe7f21153055398010dd1ca80225be07de30`.
P2 result archive SHA256:
`67b48b8e8d65b699d4cc629cbe5a5d2d98e2cad8c93d5fd416acfe026a068db2`.
Both archives were transferred and extracted into `results/semfix_full_P1/`
and `results/semfix_full_P2/`; each directory contains all 600 per-run JSON
rows, all 600 compressed complete witnesses, a run manifest and the matching
Linux native binary. Local archive hash checks matched the remote values.

## Independent audit

Command:

```sh
python3 -B audit_semfix_matrix.py
```

Exit status: `0`. Literal output:

```text
SEMFiX_AUDIT P1 600/600 feasible=600 errors=0 java_errors=0 paired={'paired_maps': 120, 'paired_runs': 600, 'definition': '100*(Java cost - Python cost)/Java cost; positive favors Python', 'map_mean_pct': -0.028411300166225728, 'map_median_pct': 0.0, 'map_min_pct': -0.8572710229438614, 'map_max_pct': 0.6169728810141988, 'map_cluster_bootstrap95_pct': [-0.07113392502976283, 0.011720756931353287], 'map_wlt_python': [53, 46, 21]}
SEMFiX_AUDIT P2 600/600 feasible=600 errors=0 java_errors=0 paired={'paired_maps': 120, 'paired_runs': 600, 'definition': '100*(Java cost - Python cost)/Java cost; positive favors Python', 'map_mean_pct': 0.0997582636054712, 'map_median_pct': 0.03328413553112791, 'map_min_pct': -1.149116190587324, 'map_max_pct': 1.8977236750685036, 'map_cluster_bootstrap95_pct': [0.0255356472736774, 0.1772713838959488], 'map_wlt_python': [71, 33, 16]}
```

The auditor verifies all 120 input hashes and five-seed task identities,
source/runner/native hashes, per-row parameters, exact result-file sets,
compressed witness hashes, independently recomputed feasibility and objective.
It also reopens all 1,200 corresponding J1b/J2b Java witnesses and their raw
output hashes before computing the paired distribution. The 95% interval is a
map-cluster bootstrap (20,000 draws, seed 20261102); positive differences mean
Python has a lower cost.

The semfix P1/P2 results both have 100% feasible coverage and no audit errors.
P1's paired interval includes zero; P2's interval is positive and narrow.
All 12 published Table 1 size groups have their rounded paper average and best
inside the semfix run's map-cluster 95% intervals. The source paper's exact
unseeded author random streams remain unknown, so this is parameter-,
constraint-, witness-, and distribution-level reproduction, not literal
trajectory identity.

## Reopen the Review Package

From this directory, run:

```sh
./verify_semfix_package.sh
```

The script reruns the frozen-package 4,200-row audit, the 4-case empty-station
regression, the 209-case Java/Python/C operator differential matrix, and the
full semfix P1/P2 plus Java-pair witness audit. The exact native sources for
the operator matrix are compiled into a temporary directory for the current
host; no archived results or binaries are replaced.
