#!/usr/bin/env python3
"""Build and verify the minimal portable Windows CPU-smoke bundle.

The archive deliberately contains only the import closure needed for the
weather/NFZ engineering smoke and the permanently excluded author-runner
fixture.  It does not package registered maps, prior run outputs, checkpoints,
SSH material, or unrelated project sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import zipfile


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent
PROJECT = PACKAGE.parents[3]
BUNDLE_ROOT = "lunwen"
MANIFEST_NAME = "WINDOWS_BUNDLE_MANIFEST.json"
SCHEMA = "route_rl_windows_cpu_bundle_v1"

# Every payload is project-relative and explicitly enumerated.  Extending this
# list is a release-review event; new source files must never silently enter.
EXACT_FILES = (
    "route_rl_research/20261103/return_makespan/scorer.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/requirements-smoke-cpu.txt",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/requirements-smoke-cpu-win313.txt",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/build_windows_bundle.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/run_windows_smoke.ps1",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/rl_algorithms.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/run_experiment.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/run_full_map_smoke.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_failure_reward.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_build_windows_bundle.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_rl_algorithms.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_weather_author_anchor.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_weather_full_map.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_weather_oracle.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_weather_pipeline.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_weather_scenario_io.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/test_windows_smoke_contract.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_author_anchor.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_full_map.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_policy.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_replay.py",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_scenario_io.py",
    "route_rl_research/20261103/return_makespan/g23/author_baseline/author_runner.py",
    "route_rl_research/20261103/return_makespan/g23/author_baseline/test_author_runner.py",
    "route_rl_research/20261103/return_makespan/g23/author_baseline/synthetic_smoke/fixture.txt",
    "route_rl_research/20261103/return_makespan/g24_weather_nfz/author_anchor_synthetic_scenario.json",
    "reproduction/reviewer_package_semfix/lrphsd/__init__.py",
    "reproduction/reviewer_package_semfix/lrphsd/problem.py",
    "reproduction/reviewer_package_semfix/lrphsd/evaluator.py",
    "reproduction/reviewer_package_semfix/reference/java/SOURCE_LOCK.json",
    "reproduction/reviewer_package_semfix/reference/java/J1b_build_manifest.json",
    "reproduction/reviewer_package_semfix/reference/java/J2b_build_manifest.json",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/ALNSSolver.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Calculator.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Check.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/FileReaderUtil.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/GreedyProbe.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Init.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/LocationOperator.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Main.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Node.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/ReferenceRecorder.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/ReplayRandom.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Round4Guard.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/RoutingOperator.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/Solution.java",
    "reproduction/reviewer_package_semfix/reference/java/J1b_source/SolutionAuditProbe.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/ALNSSolver.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Calculator.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Check.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/FileReaderUtil.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/GreedyProbe.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Init.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/LocationOperator.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Main.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Node.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/ReferenceRecorder.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/ReplayRandom.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Round4Guard.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/RoutingOperator.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/Solution.java",
    "reproduction/reviewer_package_semfix/reference/java/J2b_source/SolutionAuditProbe.java",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def project_files() -> list[Path]:
    """Resolve the audited source closure and reject accidental additions."""
    paths = {PROJECT / relative for relative in EXACT_FILES}
    declared_g24_python = {PROJECT / relative for relative in EXACT_FILES
                           if relative.endswith(".py") and "/g24_weather_nfz/" in relative}
    actual_g24_python = set(PACKAGE.glob("*.py"))
    unexpected = actual_g24_python - declared_g24_python
    if unexpected:
        raise ValueError(f"unlisted g24 Python sources: {sorted(str(path) for path in unexpected)}")
    resolved = []
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"required regular source file missing: {path}")
        try:
            path.relative_to(PROJECT)
        except ValueError as exc:
            raise ValueError(f"source escapes project root: {path}") from exc
        resolved.append(path)
    return sorted(resolved, key=lambda item: item.relative_to(PROJECT).as_posix())


def manifest_for(files: list[Path]) -> dict:
    entries = []
    for path in files:
        relative = path.relative_to(PROJECT).as_posix()
        entries.append({
            "archive_path": f"{BUNDLE_ROOT}/{relative}",
            "project_path": relative,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    unsigned = {
        "schema": SCHEMA,
        "bundle_root": BUNDLE_ROOT,
        "layout": (
            "The archive unpacks to lunwen/. Run the PowerShell script under "
            "route_rl_research/20261103/return_makespan/g24_weather_nfz/."
        ),
        "purpose": "CPU-only synthetic weather/NFZ and isolated author-anchor smoke",
        "excluded": [
            "registered/development/formal maps", "prior smoke outputs and checkpoints",
            "SSH material", "unrelated project sources",
        ],
        "files": entries,
    }
    return {**unsigned, "manifest_sha256": sha256_bytes(canonical_json(unsigned))}


def write_zip(output: Path, files: list[Path], manifest: dict) -> None:
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    temp = output.with_suffix(output.suffix + ".tmp")
    if temp.exists():
        raise FileExistsError(f"temporary archive exists; preserve it or remove it explicitly: {temp}")
    try:
        with zipfile.ZipFile(temp, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                name = f"{BUNDLE_ROOT}/{path.relative_to(PROJECT).as_posix()}"
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
            info = zipfile.ZipInfo(f"{BUNDLE_ROOT}/{MANIFEST_NAME}", date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, manifest_bytes, compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
        temp.replace(output)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def verify_tree(root: Path, expected_manifest_sha256: str | None = None) -> dict:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    supplied_hash = manifest.pop("manifest_sha256", None)
    if manifest.get("schema") != SCHEMA or manifest.get("bundle_root") != BUNDLE_ROOT:
        raise ValueError("unexpected bundle schema or root")
    expected_hash = sha256_bytes(canonical_json(manifest))
    if supplied_hash != expected_hash:
        raise ValueError("bundle manifest hash mismatch")
    if expected_manifest_sha256 is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256):
            raise ValueError("expected manifest SHA-256 must be lowercase hexadecimal")
        if supplied_hash != expected_manifest_sha256:
            raise ValueError("bundle manifest does not match the externally supplied release hash")
    expected = {MANIFEST_NAME}
    seen_archive_paths = set()
    seen_project_paths = set()
    for entry in manifest.get("files", []):
        if set(entry) != {"archive_path", "project_path", "sha256", "bytes"}:
            raise ValueError("malformed manifest file entry")
        archive_path = PurePosixPath(entry["archive_path"])
        expected_path = PurePosixPath(BUNDLE_ROOT) / PurePosixPath(entry["project_path"])
        if archive_path != expected_path or ".." in archive_path.parts:
            raise ValueError(f"unsafe manifest archive path: {entry['archive_path']}")
        if entry["archive_path"] in seen_archive_paths or entry["project_path"] in seen_project_paths:
            raise ValueError(f"duplicate manifest payload path: {entry['project_path']}")
        seen_archive_paths.add(entry["archive_path"])
        seen_project_paths.add(entry["project_path"])
        relative = Path(*PurePosixPath(entry["project_path"]).parts)
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"payload file missing or not regular: {relative}")
        if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            raise ValueError(f"payload hash mismatch: {relative}")
        expected.add(relative.as_posix())
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if actual != expected:
        raise ValueError(f"bundle tree differs from manifest: unexpected={sorted(actual - expected)} "
                         f"missing={sorted(expected - actual)}")
    return {"manifest_sha256": supplied_hash, "file_count": len(manifest["files"]),
            "tree": str(root)}


def safe_extract(archive_path: Path, target: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("archive has duplicate entry names")
        for name in names:
            entry = PurePosixPath(name)
            if entry.is_absolute() or ".." in entry.parts or not entry.parts or entry.parts[0] != BUNDLE_ROOT:
                raise ValueError(f"unsafe archive path: {name}")
        archive.extractall(target)
    return target / BUNDLE_ROOT


def verify_archive(archive_path: Path, expected_manifest_sha256: str | None = None) -> dict:
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    with tempfile.TemporaryDirectory(prefix="windows_bundle_verify_") as temporary:
        root = safe_extract(archive_path, Path(temporary))
        result = verify_tree(root, expected_manifest_sha256)
    return {**result, "archive": str(archive_path), "archive_sha256": sha256_file(archive_path)}


def build(output: Path) -> dict:
    output = output.expanduser().resolve()
    if output.suffix.lower() != ".zip":
        raise ValueError("output must have a .zip suffix")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"output parent does not exist: {output.parent}")
    files = project_files()
    manifest = manifest_for(files)
    write_zip(output, files, manifest)
    verified = verify_archive(output)
    return {"bundle": str(output), "bundle_sha256": sha256_file(output),
            "manifest_sha256": manifest["manifest_sha256"], "source_file_count": len(files),
            "verified": verified}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    build_parser = actions.add_parser("build", help="create a new, non-overwriting ZIP bundle")
    build_parser.add_argument("--output", type=Path, required=True)
    verify_zip = actions.add_parser("verify", help="verify archive paths and all payload hashes")
    verify_zip.add_argument("--bundle", type=Path, required=True)
    verify_zip.add_argument("--expected-manifest-sha256")
    verify_dir = actions.add_parser("verify-tree", help="verify an unpacked lunwen bundle tree")
    verify_dir.add_argument("--root", type=Path, required=True)
    verify_dir.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            result = build(args.output)
        elif args.action == "verify":
            result = verify_archive(args.bundle, args.expected_manifest_sha256)
        else:
            result = verify_tree(args.root, args.expected_manifest_sha256)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
