# V8 Windows Smoke Release Review

Date: 2026-11-04 (Asia/Shanghai)  
Scope: review only of V8 changes to author-anchor provenance and pre-Python release verification. No production source, archive, historical result, or existing review was modified.

## Decision

**Blocked for an author-anchor provenance claim.** V8 correctly closes the V7 gaps for a retained witness under a trusted, immutable JDK: it validates the input path and bounded timeout, re-executes the reconstructed command, and byte-compares `reference.json`. It also adds a native PowerShell manifest-file check before bundle Python. The trust roots remain incomplete, and the claimed byte comparison of the reported clock is not implemented.

## Findings

### P0 - The accepted V8 path still cannot establish that J1b source was executed

V8 re-executes `java_path` and compares its output ([`weather_author_anchor.py:163`](<LOCAL_PATH>)-[`:179`](<LOCAL_PATH>)), but JDK identity is only a self-recorded local file hash plus an easily emulated `-version` response ([`author_runner.py:137`](<LOCAL_PATH>)-[`:150`](<LOCAL_PATH>)). It is not checked against an external JDK distribution/tree hash.

The V8 positive test demonstrates the remaining gap. It writes fake `java` and `javac` programs ([`test_weather_author_anchor.py:23`](<LOCAL_PATH>)-[`:42`](<LOCAL_PATH>)). The fake compiler produces a synthetic class, while the fake Java executable ignores the classpath and writes a canned raw witness and clock ([`:31`](<LOCAL_PATH>)-[`:35`](<LOCAL_PATH>)). The test hand-writes the retained evidence ([`:61`](<LOCAL_PATH>)-[`:97`](<LOCAL_PATH>)) and V8 accepts it ([`:99`](<LOCAL_PATH>)). Re-execution proves that the current local executable regenerates those bytes, not that the frozen J1b class was ever run.

Required remediation: establish an external trusted JDK runtime/compiler tree (or signed digest) before compilation and re-execution, then compile the frozen sources in a fresh directory under that trusted toolchain. Add a negative test whose fake Java ignores the classpath; it must be rejected rather than used as the positive success fixture.

### P1 - The reported source clock is not byte-compared

V8 hashes `reference.json`, but parses both clocks as `float` and compares numeric values ([`weather_author_anchor.py:150`](<LOCAL_PATH>)-[`:179`](<LOCAL_PATH>)). This contradicts the V8 verification statement that the reported clock's bytes must equal ([`WINDOWS_BUNDLE_V8_VERIFICATION.md:15`](<LOCAL_PATH>)-[`:18`](<LOCAL_PATH>)).

On an isolated V8 test fixture, I changed the retained stdout clock from `1.2222222222222223` to `1.22222222222222230`, updated its retained artifact hash, and V8 returned literal `{"status": "eligible"}`. The formatting differs but both parse to the same float. Preserve and compare the exact matched clock token or the exact stdout byte sequence; add a format-only negative regression test.

### P1 - Native pre-Python validation protects manifest bytes, not the bundle payload

The new PowerShell path correctly requires both external values ([`run_windows_smoke.ps1:6`](<LOCAL_PATH>)-[`:10`](<LOCAL_PATH>)), computes `Get-FileHash` for the manifest, and rejects a mismatch before the first Python invocation ([`:37`](<LOCAL_PATH>)-[`:45`](<LOCAL_PATH>), [`:71`](<LOCAL_PATH>)). This fixes V7's sequencing issue for the manifest itself.

It does not protect a modified `build_windows_bundle.py` with the original manifest left intact. PowerShell then executes that modified bundle-resident verifier at line 71, and the modified program can bypass checking its own manifest entries. The manual ZIP hash step in the runbook ([`WINDOWS_RUNBOOK.md:35`](<LOCAL_PATH>)-[`:37`](<LOCAL_PATH>)) remains operational rather than enforced. Require an externally supplied ZIP SHA-256 and compare it natively before invoking bundle code, or implement the manifest's entry-hash verification in PowerShell.

### P1 - Windows execution and wheel artifact reproducibility remain open

V8 accurately reports that Windows has not been reached ([`WINDOWS_BUNDLE_V8_VERIFICATION.md:45`](<LOCAL_PATH>)-[`:49`](<LOCAL_PATH>)). No PowerShell/Windows execution receipt exists. The dependency install remains version-pinned but not artifact-hash-locked ([`run_windows_smoke.ps1:75`](<LOCAL_PATH>), [`requirements-smoke-cpu.txt:1`](<LOCAL_PATH>)-[`:4`](<LOCAL_PATH>)). This remains a release-readiness blocker, although documentation does not falsely claim a Windows result.

## Confirmed V8 Controls

- ZIP SHA-256: `059d6484cbb1ec05f9b7d3202653b9be5133964d69a677931f3ccdf6ae5e691c`.
- Canonical manifest SHA-256: `1e9519e8c0b9d91785b9da0983c0d3caab3d6c5ffd2511d85ac5eb1c1e412aa8`.
- Raw manifest-file SHA-256: `38e27f09c4cf45ad11c7b222ef28ed1c61aa67e8a8aad6fdc26023bab87418b0`.
- The refreshed runbook and V8 verification document carry all three values ([`WINDOWS_RUNBOOK.md:6`](<LOCAL_PATH>)-[`:9`](<LOCAL_PATH>), [`WINDOWS_BUNDLE_V8_VERIFICATION.md:6`](<LOCAL_PATH>)-[`:10`](<LOCAL_PATH>)).
- Fresh V8 archive has 62 ZIP entries: the 61-file payload and manifest. The exact-current source copies for `weather_author_anchor.py`, its test, and `run_windows_smoke.ps1` match the archive.
- Input-path and timeout validation are now present ([`weather_author_anchor.py:93`](<LOCAL_PATH>)-[`:97`](<LOCAL_PATH>)); its regression test is present ([`test_weather_author_anchor.py:117`](<LOCAL_PATH>)-[`:128`](<LOCAL_PATH>)).

## Executed Verification

The following commands used a fresh extraction at `/private<EXECUTION_PATH>` and did not modify V8 release inputs.

```text
PYTHONDONTWRITEBYTECODE=1 python3 build_windows_bundle.py verify-tree \
  --root /private<EXECUTION_PATH> \
  --expected-manifest-sha256 1e9519e8c0b9d91785b9da0983c0d3caab3d6c5ffd2511d85ac5eb1c1e412aa8
Result: {"file_count": 61, "manifest_sha256": "1e9519...12aa8", ...}
Exit: 0

PYTHONDONTWRITEBYTECODE=1 python3 build_windows_bundle.py verify-tree \
  --root /private<EXECUTION_PATH> \
  --expected-manifest-sha256 0000000000000000000000000000000000000000000000000000000000000000
Result: ERROR: ValueError: bundle manifest does not match the externally supplied release hash
Exit: 1

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3.13 -m unittest -v \
  test_build_windows_bundle.py test_weather_oracle.py test_weather_pipeline.py \
  test_rl_algorithms.py test_weather_full_map.py test_weather_scenario_io.py \
  test_weather_author_anchor.py
Result: Ran 49 tests in 4.497s; OK
Exit: 0

PYTHONDONTWRITEBYTECODE=1 python3 test_author_runner.py
Result: Ran 18 tests in 0.930s; OK
Exit: 0

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3 run_full_map_smoke.py --smoke \
  --updates 1 --episodes 2 --output-dir /private<EXECUTION_PATH>
Result: weather_cost_cap 77.63251698355198; six checkpoints passed reload/inference checks.
Exit: 0
```

No `pwsh`/`powershell` executable or Windows host was available; PowerShell was source-audited only.
