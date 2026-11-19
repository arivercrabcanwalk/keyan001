#!/usr/bin/env python3
"""Generate the frozen new G3 population with the audited v2 generator.

Identity = (namespace, family, partition, ordinal).  A fresh namespace is used
so every map is a new identity that appears in no exclusion manifest.
The allocation is fixed by generator_v2.derive_seed: opportunity ordinals 1..4,
calibration/validation ordinal 1 only.

Usage:
  python3 gen_maps.py --namespace NS --partition opportunity --out DIR [--ordinals 1,2,3,4] [--families all|SxT,...]
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--partition", required=True, choices=["opportunity", "calibration", "validation"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--ordinals", default=None)
    ap.add_argument("--families", default="all")
    ap.add_argument("--generator-dir", default=None)
    args = ap.parse_args()

    gen_dir = pathlib.Path(args.generator_dir) if args.generator_dir else (
        pathlib.Path(__file__).resolve().parents[3] /
        "route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>")
    sys.path.insert(0, str(gen_dir))
    import generator_v2 as G

    if args.ordinals:
        ordinals = [int(x) for x in args.ordinals.split(",")]
    else:
        ordinals = [1, 2, 3, 4] if args.partition == "opportunity" else [1]

    if args.families == "all":
        families = list(G.PUBLISHED_FAMILIES)
    else:
        families = [tuple(int(y) for y in x.split("x")) for x in args.families.split(",")]

    out = pathlib.Path(args.out)
    (out / "maps").mkdir(parents=True, exist_ok=True)
    exclusions = G.load_required_exclusions()
    index = {
        "schema": "takeover_g3_population_v1",
        "namespace": args.namespace,
        "partition": args.partition,
        "generator_protocol": G.PROTOCOL,
        "generator_version": G.GENERATOR_VERSION,
        "rng": {"name": G.RNG_NAME, "version": G.RNG_VERSION},
        "exclusion_sources": list(exclusions.sources),
        "exclusion_record_count": len(exclusions.records),
        "maps": [],
    }
    for sites, targets in families:
        for ordinal in ordinals:
            result = G.generate_allocated_instance(
                sites, targets, namespace=args.namespace, partition=args.partition,
                ordinal=ordinal, exclusions=exclusions)
            meta = result["metadata"]
            name = f"{sites}x{targets}_{args.partition[0]}{ordinal}"
            if result["status"] != "generated":
                entry = {"name": name, "status": result["status"],
                         "failure_reason": result["failure_reason"],
                         "sites": sites, "targets": targets, "ordinal": ordinal,
                         "allocation": meta.get("allocation")}
                index["maps"].append(entry)
                print(f"FAILED {name}: {result['failure_reason']}", file=sys.stderr)
                continue
            text = result["solver_input_text"]
            path = out / "maps" / f"{name}.txt"
            path.write_text(text, encoding="utf-8")
            entry = {
                "name": name, "status": "generated",
                "sites": sites, "targets": targets, "ordinal": ordinal,
                "path": str(path), "raw_sha256": result["raw_sha256"],
                "canonical_geometry_sha256": result["canonical_geometry_sha256"],
                "allocation": meta.get("allocation"),
                "accepted_sites": meta.get("accepted_sites"),
                "accepted_targets": meta.get("accepted_targets"),
                "side_m": meta.get("side_m") or meta.get("side"),
            }
            index["maps"].append(entry)
    (out / "population_index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    ok = sum(1 for m in index["maps"] if m["status"] == "generated")
    print(json.dumps({"generated": ok, "total": len(index["maps"]),
                      "index": str(out / "population_index.json")}))
    return 0 if ok == len(index["maps"]) else 1

if __name__ == "__main__":
    raise SystemExit(main())
