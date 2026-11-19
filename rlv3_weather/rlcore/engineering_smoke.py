"""New handwritten end-to-end engineering fixture; never a scientific run.

Writes a tiny original-format map and matching manual route, invokes the real
registered evaluator with cold, bounded subprocesses, and reads the real report
back. Fixed inputs and day are chosen before execution; no result-based retries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .common import ROOT, load_ins
from .registration import publish, file_sha, read_manifest, read_rows, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="new engineering artifact directory; default is a new temp directory")
    parser.add_argument("--scen", choices=("fixed_e4", "emerg_random_low"))
    args = parser.parse_args()
    default = "fixed_e4" if Path(ROOT).name == "rlv3_weather" else "emerg_random_low"
    scen = args.scen or default
    folder = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="rlv3-engineering-"))
    if args.out:
        folder.mkdir(parents=True, exist_ok=False)
    folder = folder.resolve()
    map_path = folder/"manual_tiny.txt"
    # Two distinct routine jobs and one fixed small station; nothing is optimized.
    map_path.write_text("CUST_NO X Y ENERGY SERVICE\n1 900 0 .2 10\n2 0 900 .2 10\n100 0 0 0 0\n", encoding="utf-8")
    instance = load_ins(str(map_path))
    solution = dict(schema_version=1, instance=instance.name, instance_sha256=instance.sha256,
                    station_types=[1], routes=[[[], [[1], [2]]]])
    plans = folder/"manual_plan.jsonl"
    plans.write_text(json.dumps(dict(path=str(map_path), solution=solution), allow_nan=False)+"\n")
    results, reports = folder/"episodes.jsonl", folder/"report"
    commands = [
        [sys.executable, "-B", "-m", "rlcore.evaluate", "--plans", str(plans),
         "--scen", scen, "--methods", "A1,GREEDY", "--days", "20261119",
         "--out", str(results), "--reference", "A1", "--workers", "1", "--wall-seconds", "15"],
        [sys.executable, "-B", "-m", "rlcore.analyze", "--res", str(results),
         "--scen", scen, "--out", str(reports)],
    ]
    commands_record = []
    env = dict(os.environ, RLV3_ROOT=ROOT, PYTHONDONTWRITEBYTECODE="1",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    for number, command in enumerate(commands):
        proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
        commands_record.append(dict(command=command, stdout=proc.stdout, stderr=proc.stderr,
                                    exit_status=proc.returncode))
        (folder/f"command_{number}.stdout").write_text(proc.stdout)
        (folder/f"command_{number}.stderr").write_text(proc.stderr)
        if proc.returncode:
            publish(folder/"SMOKE.json", dict(status="ENGINEERING_FAILED", formal=False,
                scientific_eligible=False, commands=commands_record, artifact_directory=str(folder)))
            print("ENGINEERING_FAILED", folder)
            return 1
    doc = read_manifest(str(results)+".registry.json")
    rows = read_rows(results)
    _, problems, missing = index(doc, rows)
    gates = json.loads((reports/"gates.json").read_text())
    if problems or missing or len(rows) != 2 or gates["status"] != "ENGINEERING_ACCOUNTED":
        raise ValueError("registered engineering matrix or report failed read-back")
    inputs = {row["input_sha256"] for row in rows}
    if len(inputs) != 1 or inputs != {doc["body"]["maps"][str(map_path)]["days"]["20261119"]}:
        raise ValueError("methods received different exogenous inputs")
    paths = [map_path, plans, results, Path(str(results)+".registry.json"),
             reports/"gates.json", reports/"REPORT.md", reports/"table.tex", reports/"per_episode.csv"]
    hashes = {str(path): file_sha(path) for path in paths}
    for path in paths:
        if not path.read_bytes():
            raise ValueError("empty engineering artifact")
    summary = dict(status="ENGINEERING_PASS", reporting_status=gates["status"], formal=False,
        scientific_eligible=False, author_solve=False, training=False, handwritten_map=True,
        explanation="ENGINEERING_ACCOUNTED audits this handwritten matrix without registered cost caps; it grants no scientific or Formal qualification.",
        scenario=scen, fixed_day=20261119, methods=["A1", "GREEDY"],
        released_requests=[row["n_urgent"] for row in rows],
        registry_sha256=doc["sha256"], artifact_sha256=hashes, commands=commands_record,
        artifact_directory=str(folder))
    publish(folder/"SMOKE.json", summary)
    if json.loads((folder/"SMOKE.json").read_text()) != summary:
        raise ValueError("smoke receipt did not round trip")
    print("ENGINEERING_PASS; ENGINEERING_ACCOUNTED; formal=False; artifacts:", folder)
    return 0


if __name__ == "__main__":
    sys.exit(main())
