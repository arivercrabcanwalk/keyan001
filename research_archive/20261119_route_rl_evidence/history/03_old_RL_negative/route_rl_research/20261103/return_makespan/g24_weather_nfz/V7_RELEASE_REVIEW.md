# V7 Windows Smoke Release Review

Date: 2026-11-04 (Asia/Shanghai)  
Scope: independent, read-only review of `route_rl_windows_cpu_bundle_20261104_v7.zip`, its Windows entrypoint, and post-red-team anchor remediation. No production source, bundle, data, or historical result was modified.

## Release Decision

**BLOCKED for any use that treats `AUTHOR_WEATHER_ANCHOR.json` as proof of an executed J1b author anchor.** The V7 archive-integrity mechanism works when the off-band release digest is actually supplied, and the 61-file static bundle closure works for the current package. V7 remains an unexecuted Windows synthetic smoke release, not an author/RL comparison or a Windows execution result.

## Findings

### P0 - Full forged author-run evidence is accepted as an eligible anchor

`weather_author_anchor.py` verifies hashes and reconstructs scores, but never re-executes the recorded J1b command or otherwise binds the raw output to an executed process. The positive test constructs fake `java`/`javac` tools and a synthetic class ([`test_weather_author_anchor.py:22`](<LOCAL_PATH>)), invokes only `prepare` ([`:37`](<LOCAL_PATH>)), then hand-writes the raw witness, scores, logs, process receipt, and `RUN.json` ([`:52`](<LOCAL_PATH>)). The test accepts that record ([`:86`](<LOCAL_PATH>)).

The verifier explicitly accepts an on-disk JDK receipt and local artifacts ([`weather_author_anchor.py:103`](<LOCAL_PATH>)) and recomputes only their internal consistency ([`:128`](<LOCAL_PATH>)-[`:153`](<LOCAL_PATH>)). This matches its own caveat that an unsigned local filesystem is not an attestation ([`:66`](<LOCAL_PATH>)). A forged feasible route can therefore be labeled an author anchor and define the candidate weather-cost cap.

Required remediation: make anchor generation and verification one append-only execution path with a trusted external receipt, or independently rerun J1b from the frozen source/build and compare its raw output before issuing eligibility. Add a negative test that constructs a complete self-consistent forged record, rather than only the currently rejected minimal JSON.

### P1 - External manifest comparison is implemented, but its enforcement root is operational rather than executable

PowerShell makes `ExpectedManifestSha256` mandatory ([`run_windows_smoke.ps1:6`](<LOCAL_PATH>)), validates lowercase SHA-256 syntax ([`:35`](<LOCAL_PATH>)), and passes it to `verify-tree` ([`:62`](<LOCAL_PATH>)). The verifier compares it to the manifest digest ([`build_windows_bundle.py:193`](<LOCAL_PATH>)-[`:197`](<LOCAL_PATH>)). The runbook independently records both release hashes and asks the operator to hash the ZIP before extraction ([`WINDOWS_RUNBOOK.md:5`](<LOCAL_PATH>)-[`:8`](<LOCAL_PATH>), [`:34`](<LOCAL_PATH>)-[`:36`](<LOCAL_PATH>)).

This is correct conditional on that manual pre-extraction ZIP check. However, the PowerShell path invokes the bundle-resident Python verifier before it makes the manifest decision; a modified archive can alter that verifier. Make the ZIP hash an explicit PowerShell parameter and compute/compare it with `Get-FileHash` before invoking any bundled code, or distribute the verifier from a separately hashed/signed channel.

### P1 - Windows dependency artifacts are not frozen

The run invokes `pip install --only-binary` without `--require-hashes` ([`run_windows_smoke.ps1:66`](<LOCAL_PATH>)); `requirements-smoke-cpu.txt` has only two version pins ([`requirements-smoke-cpu.txt:1`](<LOCAL_PATH>)-[`:4`](<LOCAL_PATH>)). The runbook acknowledges this ([`WINDOWS_RUNBOOK.md:85`](<LOCAL_PATH>)-[`:88`](<LOCAL_PATH>)). Preserve the current receipt as smoke-only; before calling it reproducible, freeze interpreter and wheel hashes and install with `--require-hashes`.

### P1 - Windows portability has not been executed

V7 documentation accurately says that Windows was unreachable and makes no Windows success claim ([`WINDOWS_BUNDLE_V7_VERIFICATION.md:54`](<LOCAL_PATH>)-[`:57`](<LOCAL_PATH>)). The `.exe` resolver has unit coverage, but no actual `run_windows_smoke.ps1` receipt exists. A Windows 11/JDK 17/Python 3.13 execution must be recorded before release-readiness can be asserted.

### P2 - Anchor metadata fields are presence-checked but not semantically verified

`input_path` and `timeout_seconds` are required ([`weather_author_anchor.py:81`](<LOCAL_PATH>)-[`:84`](<LOCAL_PATH>)), but the verifier never checks that the stored path identifies the supplied map or that the timeout is positive/consistent with the command. Hash/command reconstruction still binds the actual map, so this does not bypass feasibility; it does make recorded budget and path provenance unreliable. Validate both fields and test their rejection.

## Confirmed Controls

- Archive SHA-256: `ef6798310a4dcd35657e982d8527159b515774ecdd80f3579e50bab226ca83c9`.
- Manifest SHA-256: `0818772dd33fc4791b8b3cda174db322e953fdafa967de4d7fd9c5a339ada2a5`.
- The archive has 62 ZIP entries: 61 payload files plus `WINDOWS_BUNDLE_MANIFEST.json`.
- The explicit allowlist is 61 files ([`build_windows_bundle.py:28`](<LOCAL_PATH>)-[`:92`](<LOCAL_PATH>)); unlisted G24 Python sources are rejected ([`:108`](<LOCAL_PATH>)-[`:126`](<LOCAL_PATH>)), and unpacked-tree verification rejects missing, altered, symlinked expected, or extra regular payload files ([`:201`](<LOCAL_PATH>)-[`:222`](<LOCAL_PATH>)).

## Executed Verification

All commands below used a fresh extraction at `/private<EXECUTION_PATH>`; no release input was modified.

```text
PYTHONDONTWRITEBYTECODE=1 python3 build_windows_bundle.py verify-tree \
  --root /private<EXECUTION_PATH> \
  --expected-manifest-sha256 0818772dd33fc4791b8b3cda174db322e953fdafa967de4d7fd9c5a339ada2a5
Result: {"file_count": 61, "manifest_sha256": "081877...da2a5", ...}
Exit: 0

PYTHONDONTWRITEBYTECODE=1 python3 build_windows_bundle.py verify-tree \
  --root /private<EXECUTION_PATH> \
  --expected-manifest-sha256 0000000000000000000000000000000000000000000000000000000000000000
Result: ERROR: ValueError: bundle manifest does not match the externally supplied release hash
Exit: 1

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3 -m unittest -v \
  test_build_windows_bundle.py test_weather_oracle.py test_weather_pipeline.py \
  test_rl_algorithms.py test_weather_full_map.py test_weather_scenario_io.py \
  test_weather_author_anchor.py
Result: Ran 48 tests in 3.113s; OK
Exit: 0

PYTHONDONTWRITEBYTECODE=1 python3 \
  /private<EXECUTION_PATH>
Result: Ran 18 tests in 0.875s; OK
Exit: 0

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3 run_full_map_smoke.py --smoke \
  --output-dir /private<EXECUTION_PATH>
Result: report records PPO/A2C, 4 updates, 8 episodes/update, 6/6 complete rows,
        and 6/6 reload/inference-verified checkpoints.
Exit: 0
```

`pwsh`/`powershell` was not installed on this review host, so the PowerShell entrypoint was source-audited rather than executed. No Windows host was available.
