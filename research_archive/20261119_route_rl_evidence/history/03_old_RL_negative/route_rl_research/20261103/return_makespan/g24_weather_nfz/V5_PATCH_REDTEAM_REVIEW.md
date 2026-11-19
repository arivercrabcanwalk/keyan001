# V5 Patch Red-Team Review

Date: 2026-11-04 (Asia/Shanghai)  
Scope: the Windows JDK executable resolver, `weather_scenario_io.py`,
`weather_author_anchor.py`, `run_windows_smoke.ps1`, and the V5 bundle/verifier.
No production source was modified during this review.

## Result

The `.exe` resolver corrects the prior obvious Windows JDK path defect, and the
current V5 archive is internally consistent.  It is **not** sufficient to call
an arbitrary weather-anchor receipt an author-algorithm anchor, and its
in-bundle verification does not authenticate a transferred archive.  Windows
execution itself remains unobserved.

The V5 documents correctly limit the current artifact to synthetic smoke and
explicitly do not claim an author-versus-RL result.  The P0 below blocks any
future extension of its weather-anchor receipt into that comparison without a
provenance fix.

## Findings

### P0 - A hand-authored `RUN.json` can become an "author" weather anchor

`prepare_author_weather_anchor()` checks only a mutable eligibility flag,
status, input hash, and the hash of `solution.json`
([`weather_author_anchor.py`](weather_author_anchor.py#L42) lines 47-58).  It
does not validate the claimed profile, frozen Java source identity, JDK/build
receipt, runner hash, process exit/timeout record, witness audit, raw Java
output, original scorer receipt, or an externally frozen author-run manifest.

The positive unit fixture itself writes precisely such a minimal synthetic
`RUN.json` ([`test_weather_author_anchor.py`](test_weather_author_anchor.py#L21)
lines 21-28), and the preflight accepts it.  Independent reproduction with a
one-target feasible solution and a four-field hand-written record returned:

```text
{'status': 'eligible', 'profile_present': False, 'source_identity_present': False}
exit 0
```

Consequently, any feasible, manually supplied solution can be relabeled as an
author anchor after its local solution digest is updated.  That invalidates the
provenance needed for the required per-map `R_Liu` comparison, even though it
does not change the explicit synthetic-only scope of the current V5 receipt.

Require the preflight to either reproduce and verify the complete G23 author
record from trusted source/build locks or require a separately frozen, signed
run manifest.  It must validate profile, profile/source hashes, JDK/build
identity, process outcome, witness audit, and hashes/cross-consistency of raw,
solution, scorer, and evaluator artifacts.  Add rejection tests for every
missing or altered field and one acceptance test using a genuine G23 run.

### P1 - The V5 manifest proves internal consistency, not transferred-artifact provenance

`build_windows_bundle.py` derives every payload hash and the manifest hash from
the payload it is asked to verify
([`build_windows_bundle.py`](build_windows_bundle.py#L81) lines 81-105), while
the Windows entrypoint executes that same bundled verifier
([`run_windows_smoke.ps1`](run_windows_smoke.ps1#L57) line 57).  No immutable
expected manifest or archive hash is supplied to the runtime.

The verifier accepts a well-formed manifest with no payload entries
([`build_windows_bundle.py`](build_windows_bundle.py#L133) lines 133-170).
An independent temporary-tree reproduction returned:

```text
{'manifest_sha256': '3a1ba5dd07627757194f008b56f1da5463f603428da6fbafe41af0eb1ab578de',
 'file_count': 0, 'tree': '<temporary>/lunwen'}
exit 0
```

Thus a substituted archive can replace the sources, verifier, and manifest,
then recompute their self-consistent hashes.  `WINDOWS_BUNDLE_V5_VERIFICATION.md`
records the expected ZIP SHA-256, but the PowerShell workflow neither requires
that value before extraction nor verifies a detached signature.  The current
hashes detect accidental payload drift after a trusted extraction; they do not
establish the trust of a transferred ZIP.

Freeze the expected V5 archive SHA-256 outside the archive (or preferably use a
detached signature), verify it with `Get-FileHash` before extraction, and make
the tree verifier require the frozen manifest digest and exact file list.  Add
a negative test that repacks a changed source plus regenerated manifest and
confirms the release verification rejects it.

### P1 - Windows portability is still a release blocker, despite the correct resolver patch

The resolver now returns `java.exe` and `javac.exe` when `os.name == "nt"`
([`author_runner.py`](../g23/author_baseline/author_runner.py#L126) lines
126-149), which is the correct repair.  The only focused resolver test models
the filename selection without running a Windows process
([`test_author_runner.py`](../g23/author_baseline/test_author_runner.py#L102)
lines 102-108); the PowerShell unit-test invocation does not include that test
([`run_windows_smoke.ps1`](run_windows_smoke.ps1#L64) line 64).

More importantly, V5 records that no Windows host was reached or archive
executed ([`WINDOWS_BUNDLE_V5_VERIFICATION.md`](WINDOWS_BUNDLE_V5_VERIFICATION.md#L41)
lines 41-43).  The source-level test coverage cannot establish PowerShell 5.1
argument passing, Windows `py -3.13`/venv/pip behavior, actual `.exe`
execution, or the J1b/J2b compile-and-run sequence.

Run the unmodified PowerShell entrypoint on a clean Windows PowerShell 5.1 host
with Python 3.13 and JDK 17, retaining all logs and receipts.  This must cover
bundle verification, package installation, both Java profiles, the J1b
fixture, and the weather-anchor preflight before asserting a Windows smoke
pass.  It remains only a synthetic engineering pass, not a comparison result.

### P2 - The builder silently expands its intended source closure

`project_files()` says it rejects accidental additions, but `GLOBS` includes
every `g24_weather_nfz/*.py`
([`build_windows_bundle.py`](build_windows_bundle.py#L44) lines 44-48 and
[`build_windows_bundle.py`](build_windows_bundle.py#L64) lines 64-78).  A new
Python file is therefore silently added to a future bundle and incorporated
into a freshly self-generated manifest rather than rejected.  This is at odds
with the claimed fixed V5 closure and makes source inclusion review dependent
on noticing a changed file count.

Replace that glob with a static file allowlist, or freeze and enforce the exact
manifest file list/digest.  Add a test that creates an unexpected `.py` file
and expects the builder to fail.

## Checks Performed

| Command | Observed result |
| --- | --- |
| `python3 build_windows_bundle.py verify --bundle route_rl_windows_cpu_bundle_20261104_v5.zip` | Exit 0; archive SHA-256 `c81385e6bd65ddddf42f46ca71f185926dfb724afafe1e6bcfbef3ff5e4d7c1b`, manifest SHA-256 `ea91d62b2b156a64f7037818dfffc6587adaa8d3ebeee159fa181e2ed422d493`, 59 payload files. |
| `PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/Caskroom/miniconda/base/bin/python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py test_weather_scenario_io.py test_weather_author_anchor.py` | Exit 0; 45 tests passed. |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_author_runner.py` from `g23/author_baseline` | Exit 0; 18 tests passed. |
| V5 ZIP name audit | 60 unique entries; no backslash, absolute, `..`, colon, or Windows-reserved-name entry found. |
| Minimal self-consistent empty manifest and minimal forged author-run fixtures | Both were accepted as described in P1 and P0, exit 0. |

No bad import was observed in the executed source closures.  The delivered ZIP
also rejects malformed archive path names during `safe_extract`; this review
found no path traversal in the delivered V5 archive.  The relevant remaining
hash/path issue is absence of an external provenance binding, not an observed
ZIP-slip path in V5.
