# Liu2026 TSALNS reproduction audit package

This package records 120 official `Instances_Alg` maps x five solver seeds x seven versioned profiles = **4,200 full-result rows and compressed complete solutions**. The original ten Java files are locked to commit `d86f5549ebc9c05d65fce16f61b6df4f7cb73158`; modified Java sources, build manifests and all run manifests are separate. No profile is silently substituted for another.

## Verify the archived experiment

After extracting the archive, run `./verify_reviewer_package.sh` from its root. Requirements: Python 3, `jq`, `shasum`, `tar` and enough memory to reopen the compressed solutions. This command checks the ten official Java source hashes, reopens and independently scores all 4,200 solution files, checks run/solution/input/source hashes and 1,200 correct-guard Java/Python pairs, recomputes all Table 1 map-cluster intervals, rejects seven deliberately invalid test cases, and re-solves ten small instances by exact subset dynamic programming. Expected last line:

```text
REVIEWER_PACKAGE PASS rows=4200 paired_correct_guard=1200 exact=10 mutations=7
```

The command writes only to a temporary directory. It compares regenerated audit JSON byte for byte with the saved `results/` summaries and returns nonzero on a mismatch.

## Profiles and interpretation

| Profile | Meaning | Feasible final outputs |
|---|---|---:|
| J0 | Instrumented released Java semantics, no full physical repair guard | 142/600 |
| J1 / J2 | Historical diagnostic guards with an extra pre-ALNS rejection, code / paper parameter sets | 600/600 each |
| J1b / J2b | Correct guard position, Java code / paper Table A1 parameter sets | 600/600 each |
| P1 / P2 | Python/native port, Java code / paper Table A1 parameter sets | 600/600 each |

The faithful feasible-port contrasts are **J1b versus P1** and **J2b versus P2**, not J1/J2 versus P1/P2. Their 120-map paired cost differences are -0.028411% and +0.099758% respectively (`100*(Java-Python)/Java`; positive favors Python). The original J0 output is independently infeasible in 458/600 runs, so its feasible-only costs are not an all-run baseline. Published Table 1 author seeds are unknown. All printed group averages and best values fall inside map-cluster 95% intervals for the four correct-guard profiles, but this is not a byte-level or trajectory reproduction.

## Re-run from source

The recorded remote environment is in `REPRO_ENVIRONMENT.md`. For a fresh experiment, extract a **second copy** of the archive, move its `results/` directory to `archived_results/`, then run `JAVA_HOME=/path/to/jdk17 PYTHON=/path/to/python3 ./run_all.sh` from that second copy. This preserves the archived outputs while generating new `results/full_{profile}/` directories. The matrix is 4,200 fixed-iteration solver tasks and can take hours. The generated run manifests bind the new machine/toolchain and seeds. Do not mix a fresh machine's rows with archived manifests or compare fixed-iteration cost with a later 6/12-second research budget as equal-time results.

## Files

- `reference/java/official_source/` and `SOURCE_LOCK.json`: immutable official source and per-file SHA256.
- `reference/java/{instrumented_source,guarded_source,paper_guarded_source,J1b_source,J2b_source}/`: separately versioned variants.
- `external/LRPHSD<EXECUTION_PATH>`: 120 original input maps.
- `results/full_{profile}/`: manifest, per-task JSON, compressed complete solution, Java raw output when applicable, stdout/stderr and run log.
- `results/{full_matrix_audit,postguard_full_audit,published_table1_comparison,table1_bootstrap}.json`: generated summaries.
- `results/exact_3_10_certificates/`: ten independent exact witnesses and hashes.
- `REPRO_PROTOCOL.md`: parameter, constraint and differential contract.

The printed-paper group gaps, unknown author random streams and remaining operator-order analysis are documented in the accompanying reproduction report. A small final-cost gap is tolerated only after feasibility, objective and full-output audits pass; no unpublished profile is called the literal original Liu binary.
