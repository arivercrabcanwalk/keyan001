#!/usr/bin/env python3
"""Freeze SHA256 of every result/stats artifact in this package."""
from __future__ import annotations
import hashlib, json, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
targets = []
for pat in ("results/**/*.json", "stats/*.json", "analysis/*.py", "harness/*.py",
            "harness/*.sh", "*.md", "*.json", "*.csv", "*.jsonl",
            "public_rollout/**/*.py", "public_rollout/*.md",
            "public_rollout_receipts/receipts/*.json"):
    targets.extend(sorted(ROOT.glob(pat)))
seen, entries = set(), []
for p in targets:
    if not p.is_file() or p.name in ("RESULTS_MANIFEST.json",):
        continue
    rel = p.relative_to(ROOT).as_posix()
    if rel in seen:
        continue
    seen.add(rel)
    entries.append({"path": rel, "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
manifest = {
    "schema": "takeover_completion_results_manifest_v1",
    "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "note": "Freeze taken after the solution-persisting rerun of 03_run_nonrl.py on both sets.",
    "count": len(entries),
    "entries": entries,
}
(ROOT / "RESULTS_MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("files", len(entries), "bytes", sum(e["bytes"] for e in entries))