# Liu reproduction execution environment

Captured from the remote reproduction host on 2026-11-02. All matrix rows were generated under this environment, with one sequential worker and Java launched with `-XX:ActiveProcessorCount=1 -XX:+UseSerialGC -Xms32m -Xmx512m`.

| Item | Observed value |
|---|---|
| Java | Amazon Corretto / OpenJDK 17.0.21 LTS |
| Python | CPython 3.11.14 at `/opt/conda/bin/python` |
| GCC | 11.4.0 |
| OS / kernel | Ubuntu 22.04, Linux 6.8.0-138-generic, x86_64 |
| CPU | Intel Xeon Platinum 8269CY; 104 logical CPUs visible, 52 physical cores |
| Container quota | 12 CPU cores; memory limit 45,097,156,608 bytes (42.0 GiB) |
| Host RAM | 371 GiB; this is not the container memory quota |
| Frozen pre-semfix native binary SHA256 | `45ed9265ebfdac0d9cb17ecda56b874988989421c180d9c1d09c3feb8e9492f2` (`../reviewer_package/` original P1/P2 manifests) |
| Semfix native binary SHA256 | `2657d2f7a9f0b00e0710cdeef1f217f23a69d0cdd81523caca81dac88ef99e5c` (`results/semfix_full_P1/libr6kernel.so` and `results/semfix_full_P2/libr6kernel.so`) |
| Official Java source | Commit `d86f5549ebc9c05d65fce16f61b6df4f7cb73158`; ten per-file hashes in `reference/java/SOURCE_LOCK.json` |

Each run manifest binds every input SHA256, parameter profile, solver seed, source/runner hash and the version-specific native binary hash. The frozen pre-semfix and corrected semfix matrices are separate; never combine or relabel their rows. Per-run JSON records command, elapsed time, exit status, independent objective/feasibility, raw-output hash and complete-solution hash. The original Java entry point has unseeded `Random()`; deterministic seeds in this reproduction are an instrumentation change and do not reveal the authors' unpublished random streams.
