#!/usr/bin/env python
"""Write a deterministic SHA256 manifest of the CA-RL v1 deliverable."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["carl", "scripts", "tests", "native", "lrphsd", "docs"]
TOP = ["README.md", "baseline_audit.md", "joint_neighborhood_design.md",
       "experiment_protocol.md", "CA_RL_TSALNS_v1_REPORT.md", "paper_draft.md"]
SKIP_SUFFIX = {".pyc", ".so", ".dylib", ".pt", ".jsonl", ".log"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    files = []
    for d in INCLUDE:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix in SKIP_SUFFIX:
                continue
            if p.name.startswith("._") or "__pycache__" in p.parts:
                continue
            files.append(p)
    for name in TOP:
        p = ROOT / name
        if p.exists():
            files.append(p)
    entries = [{"path": str(p.relative_to(ROOT)), "sha256": sha256(p),
                "bytes": p.stat().st_size} for p in files]
    manifest = {"root": str(ROOT), "n_files": len(entries), "files": entries}
    (ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    lines = [f"{e['sha256']}  {e['path']}" for e in entries]
    (ROOT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
    print(f"wrote MANIFEST.json with {len(entries)} files")


if __name__ == "__main__":
    main()
