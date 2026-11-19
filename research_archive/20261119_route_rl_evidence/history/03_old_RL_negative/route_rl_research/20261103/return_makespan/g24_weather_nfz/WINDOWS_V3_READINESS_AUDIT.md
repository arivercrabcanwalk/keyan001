# Windows V3 CPU Bundle Readiness Audit

> Superseded for execution by `route_rl_windows_cpu_bundle_20261104_v5.zip`.
> A later review found that v3's copied `author_runner.py` only resolved POSIX
> `bin/java` paths and would not start on a standard Windows JDK. The v5
> executable-path fix and its fresh bundle verification are recorded in
> `WINDOWS_BUNDLE_V5_VERIFICATION.md`. This document remains an immutable audit
> of v3's archive closure, not a current Windows-run recommendation.

Date: 2026-11-04 (Asia/Shanghai)  
Audited artifact: `route_rl_windows_cpu_bundle_20261104_v3.zip`  
Artifact SHA-256: `5c09ff8e96af5eb8f18ee12561ec73a12ade87c8f22e2285416f96d2e3888abc`  
Manifest SHA-256: `92b8beca02b6dbeea44cc7d751c7328eabbb109df0b2e355124a70c211090d66`

## Verdict

**READY FOR A BOUNDED WINDOWS CPU ACCEPTANCE RUN once SSH is restored**, subject
to three machine-side preflight conditions: Windows x64 Python launcher with
CPython 3.13, a JDK 17 directory containing `bin\\java.exe` and
`bin\\javac.exe`, and package-index access for the first virtual-environment
install. The archive, manifest, Python source closure, PowerShell path layout,
and Java source closure all passed static or executable checks described below.

This is deliberately **not** a ready-to-run registered-map, 6 s/12 s quality,
or author-versus-RL experiment bundle. It includes no registered/development/
formal map and `run_windows_smoke.ps1` only executes the synthetic weather/NFZ
fixture plus the permanently excluded J1b author-anchor fixture. It therefore
cannot create a Windows scientific-quality result without a separately frozen
and authorized map/anchor bundle.

No Windows execution is claimed. The documented SSH route still returns
`connect failed: Connection refused` and exit 255.

## Package And Manifest

| Check | Observed result |
|---|---|
| Archive structure | 55 entries: 54 manifest payload files plus `lunwen/WINDOWS_BUNDLE_MANIFEST.json`; no duplicate entries. |
| Integrity | `unzip -t` passed; the archive SHA-256 and recomputed canonical manifest SHA-256 match the values above. |
| Extraction safety | All paths are relative below `lunwen/`; no `..`, absolute, encrypted, reserved Windows-name, or case-insensitive collision entry was found. |
| Payload verification | A fresh extraction passed `build_windows_bundle.py verify-tree` with `file_count: 54`. |
| Source identity | Every archived payload hash equals the manifest hash and the current on-disk source hash: `mismatches: []`. |
| Windows extraction compatibility | ZIP entries require only MS-DOS/OS/2/NT FAT compatibility version 2.0, are deflated, and have no extra fields or encryption. |

The exact supplied closure contains 13 weather/RL Python files (including all
four test modules and the Windows runner), `scorer.py`, the author runner and
synthetic fixture, `lrphsd/problem.py`, `lrphsd/evaluator.py`, both Java
profiles, and their source/build manifests. The expected entrypoints are all
present.

## Runtime Dependency Audit

`requirements-smoke-cpu.txt` contains exactly:

```text
numpy==2.5.2
torch==2.12.1
```

The Python source imports only the standard library plus those two packages;
there is no unbundled Python project dependency. The following Windows-targeted
resolver preflight succeeded without installing anything:

```text
python3.13 -m pip install --dry-run --ignore-installed --only-binary=:all: \
  --no-deps --platform win_amd64 --implementation cp --python-version 3.13 \
  --abi cp313 --target <temporary-directory> numpy==2.5.2 torch==2.12.1

Downloading numpy-2.5.2-cp313-cp313-win_amd64.whl.metadata
Downloading torch-2.12.1-cp313-cp313-win_amd64.whl.metadata
Would install numpy-2.5.2 torch-2.12.1
exit 0
```

This proves that the pinned `win_amd64/cp313` candidates resolve. It does not
prove that the Windows host can download the full wheels: that remains a first
run prerequisite. The bundle intentionally has no Windows wheel hashes or
wheelhouse, so the post-run receipt must retain the pip log and installed
package identities before any later freeze.

The local executable check used the same pins under CPython 3.13.12:

```json
{"cuda_available": false, "cuda_version": null, "numpy": "2.5.2", "torch": "2.12.1"}
```

## PowerShell Audit

`run_windows_smoke.ps1` is ASCII/LF text and is validly rooted from its own
location. With the intended extraction layout
`<WINDOWS_PATH>`,
its four-parent calculation resolves to `<WINDOWS_PATH>`,
which is the manifest root.

The runner behavior is appropriate for the bounded smoke:

- `Set-StrictMode -Version Latest` and `$ErrorActionPreference = 'Stop'` are
  enabled.
- It refuses a pre-existing output directory, creates a new venv, masks CUDA,
  disables user site packages and `.pyc` creation, and verifies the manifest
  before creating the venv or installing dependencies.
- Every native phase is piped through `Tee-Object` and fails the PowerShell
  process with the child exit status while retaining a phase log.
- It records Python and Java environment receipts, all 40 Python tests, the
  weather smoke output, both J1b/J2b compile logs, build manifests, and the
  J1b fixture witness artifacts.
- The runner explicitly requires `java.exe` and `javac.exe`; the author runner
  additionally rejects versions other than JDK 17. The script does not attempt
  an implicit Java download or silently substitute another runtime.

The author runner copies each selected source profile to a fresh output build
directory, compiles with `javac -encoding UTF-8`, hashes every emitted class,
and verifies the same JDK identity before its J1b run. Each profile has 15
source files whose hashes match its bundled build manifest; the manifests
record 20 classes and prior compile exit 0. The Java source imports only
`java.io`, `java.nio.file`, and `java.util`, so no third-party Java JAR is
required.

## Executable Tests Run

All commands below used a fresh temporary extraction of the exact v3 archive;
none used registered maps or previous smoke outputs.

```text
unzip -t route_rl_windows_cpu_bundle_20261104_v3.zip
No errors detected in compressed data of route_rl_windows_cpu_bundle_20261104_v3.zip.
exit 0

python3 <extract>/lunwen/route_rl_research/20261103/return_makespan/g24_weather_nfz/build_windows_bundle.py \
  verify-tree --root <extract>/lunwen
{"file_count": 54, "manifest_sha256": "92b8beca02b6dbeea44cc7d751c7328eabbb109df0b2e355124a70c211090d66", "tree": "<extract>/lunwen"}
exit 0

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3.13 -m unittest -v \
  test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py test_weather_full_map.py
Ran 40 tests in 1.168s
OK
exit 0

PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' python3.13 run_full_map_smoke.py \
  --smoke --updates 1 --episodes 2 --output-dir <fresh-output>
{"report": "<fresh-output>/full_map_smoke_report.json", "weather_cost_cap": 77.63251698355198}
exit 0
```

The successful smoke emitted six `.pt` checkpoints and a report with SHA-256
`7a8e02f0353d5d0964c132500672259c3787386c8b3e467fb0bf74a703cc2f83`.
This validates the bundled training/execution path on the same pinned Python
dependencies, not Windows ABI behavior.

## First Authenticated Windows Session

Run the following as soon as the existing `windows` SSH alias accepts a
session. First authenticate and identify the machine; the final command must
show CPython 3.13 and a JDK 17 before the archive is copied.

```powershell
# On the project host (macOS/Linux shell)
BUNDLE='<LOCAL_PATH>'
shasum -a 256 "$BUNDLE"
<CONNECTION_COMMAND_REMOVED>
```

Inside the authenticated Windows session, open PowerShell and run:

```powershell
$ErrorActionPreference = 'Stop'
whoami
hostname
$PSVersionTable.PSVersion
py -3.13 --version
$jdk17 = '<WINDOWS_PATH> Files\Eclipse Adoptium\jdk-17'  # replace only with the discovered JDK 17 directory
& (Join-Path $jdk17 'bin\java.exe') -version
& (Join-Path $jdk17 'bin\javac.exe') -version
Test-Path (Join-Path $jdk17 'bin\java.exe')
Test-Path (Join-Path $jdk17 'bin\javac.exe')
exit
```

Back on the project host, transfer the immutable artifact to the authenticated
account's OpenSSH home directory. This uses an explicit final filename and does
not overwrite an existing extraction.

```powershell
scp "$BUNDLE" 'windows:route_rl_windows_cpu_bundle_20261104_v3.zip'
ssh windows
```

Inside the next Windows PowerShell session, verify, extract, and execute:

```powershell
$ErrorActionPreference = 'Stop'
$expected = '5c09ff8e96af5eb8f18ee12561ec73a12ade87c8f22e2285416f96d2e3888abc'
$jdk17 = '<WINDOWS_PATH> Files\Eclipse Adoptium\jdk-17'  # use the JDK 17 directory confirmed in preflight
$zip = Join-Path $env:USERPROFILE 'route_rl_windows_cpu_bundle_20261104_v3.zip'
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'v3 archive SHA-256 mismatch' }

$base = '<WINDOWS_PATH>'
$extract = Join-Path $base 'route_rl_bundle_v3_20261104'
$out = Join-Path $base 'route_rl_windows_smoke_v3_20261104_001'
New-Item -ItemType Directory -Force -Path $base | Out-Null
if (Test-Path -LiteralPath $extract) { throw "refusing existing extraction: $extract" }
if (Test-Path -LiteralPath $out) { throw "refusing existing output: $out" }
Expand-Archive -LiteralPath $zip -DestinationPath $extract

$work = Join-Path $extract 'lunwen\route_rl_research\20261103\return_makespan\g24_weather_nfz'
Set-Location $work
py -3.13 .\build_windows_bundle.py verify-tree --root (Join-Path $extract 'lunwen')
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run_windows_smoke.ps1 -PythonLauncher py -PythonVersion 3.13 -JavaHome $jdk17 -OutputDirectory $out
$rc = $LASTEXITCODE
Get-ChildItem -LiteralPath $out -Recurse -File | Select-Object FullName,Length
Get-Content -LiteralPath (Join-Path $out 'python_environment.stdout_stderr.txt')
Get-Content -LiteralPath (Join-Path $out 'java_environment.stdout_stderr.txt')
Get-Content -LiteralPath (Join-Path $out 'unittest.stdout_stderr.txt') -Tail 8
if ($rc -ne 0) { exit $rc }
```

Pass criterion: exit 0 and a line beginning
`WINDOWS_CPU_SMOKE_PASS output=`. For failure triage, preserve and retrieve the
whole new `$out` directory. In particular, `pip_install.stdout_stderr.txt`,
`author_J1b_prepare.stdout_stderr.txt`, `author_J2b_prepare.stdout_stderr.txt`,
`author_J1b_smoke.stdout_stderr.txt`, and `RUN.json` distinguish wheel,
JDK/compile, and source-witness failures.

## Outstanding Limits And Next Gate

1. The current refused SSH tunnel is the immediate operational blocker. No
   Windows interpreter, JDK, file transfer, venv, Java compilation, or smoke
   result has yet been observed.
2. The first dependency install needs access to binary `win_amd64/cp313`
   wheels. The pins resolve, but full wheel download and hash capture remain
   Windows-side evidence.
3. The bundle is intentionally fixture-only. A successful smoke is an
   engineering receipt and does not admit G2/G3/G4, establish an RL result, or
   provide an author/RL comparison on a registered map.
