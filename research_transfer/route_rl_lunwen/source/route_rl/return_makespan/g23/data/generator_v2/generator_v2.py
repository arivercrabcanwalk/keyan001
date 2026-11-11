#!/usr/bin/env python3
"""Sequential conditional-uniform-proposal reconstruction, engineering v2.

Every proposed coordinate uses the published square. Accepted nodes are not
IID and complete maps are not uniform over the globally feasible-map set.
No batch or study-map CLI is provided; root freezes allocation before use.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

PROTOCOL = "constraint-reconstructed-sequential-conditional-uniform-proposal"
GENERATOR_VERSION = "2.0.0-engineering"
RNG_NAME = "SplitMix64"
RNG_VERSION = "2015-02-16-reference-variant-v1"
UINT64_MASK = (1 << 64) - 1
UINT53_DENOMINATOR = 1 << 53
SITE_PROPOSAL_CAP = 32
TARGET_PROPOSAL_CAP = 1024
LABEL_WORD_CAP = 128
HEADER = "CUST_NO XCOORD YCOORD SERVICE_ENERGY SERVICE_TIME"
PUBLISHED_FAMILIES = (
    (3, 10), (3, 15), (3, 20), (4, 20), (4, 25), (4, 30),
    (5, 35), (6, 50), (7, 65), (8, 80), (9, 95), (10, 110),
)
PARTITIONS = ("opportunity", "calibration", "validation")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def paper_side_m(target_count: int) -> int:
    if 1 <= target_count <= 80:
        return 14_000
    if target_count == 95:
        return 15_000
    if target_count == 110:
        return 20_000
    raise ValueError("target count is outside published families")


class SplitMix64:
    """The exact v1 64-bit output transform; not a source of true randomness."""
    name = RNG_NAME
    version = RNG_VERSION

    def __init__(self, seed: int):
        if type(seed) is not int or not 0 <= seed <= UINT64_MASK:
            raise ValueError("seed must be a uint64")
        self.seed = self.state = seed
        self.draws = 0

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & UINT64_MASK
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & UINT64_MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & UINT64_MASK
        value ^= value >> 31
        self.draws += 1
        return value

    def next53(self) -> int:
        return self.next_u64() >> 11


@dataclass(frozen=True)
class Node:
    node_id: int
    x: Decimal
    y: Decimal
    energy: Decimal
    service: Decimal
    kind: str


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("nonfinite decimal")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def render_instance_text(nodes: Iterable[Node]) -> str:
    ordered = sorted(nodes, key=lambda node: (0 if node.kind == "target" else 1,
                                              node.node_id))
    lines = [HEADER]
    for node in ordered:
        lines.append(" ".join((str(node.node_id), _decimal_text(node.x),
                               _decimal_text(node.y), _decimal_text(node.energy),
                               _decimal_text(node.service))))
    return "\n".join(lines) + "\n"


def parse_instance_text(raw_text: str) -> tuple[Node, ...]:
    lines = raw_text.splitlines()
    if not lines or "CUST_NO" not in lines[0]:
        raise ValueError("missing LRPHSD header")
    rows = []
    ids = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5 or not re.fullmatch(r"[+-]?\d+", fields[0]):
            raise ValueError("expected integer ID and four decimal fields")
        node_id = int(fields[0])
        if node_id in ids:
            raise ValueError("duplicate node ID")
        ids.add(node_id)
        x, y, energy, service = (Decimal(field) for field in fields[1:])
        if any(not value.is_finite() for value in (x, y, energy, service)):
            raise ValueError("nonfinite node attribute")
        if min(energy, service) < 0:
            raise ValueError("negative task attribute")
        if energy == service == 0:
            kind = "site"
        elif energy > 0 and service > 0:
            kind = "target"
        else:
            raise ValueError("ambiguous node kind")
        rows.append(Node(node_id, x, y, energy, service, kind))
    if not rows:
        raise ValueError("empty instance")
    return tuple(rows)


def canonical_geometry_identity(nodes: Iterable[Node]) -> str:
    """Byte-compatible with the frozen v1 geometry identity, including attrs."""
    nodes = tuple(nodes)
    if not nodes:
        raise ValueError("canonical identity requires at least one node")
    min_x = min(Fraction(node.x) for node in nodes)
    min_y = min(Fraction(node.y) for node in nodes)

    def rational_text(value):
        return (str(value.numerator) if value.denominator == 1 else
                f"{value.numerator}/{value.denominator}")

    normalized = [{
        "kind": node.kind,
        "x": rational_text(Fraction(node.x) - min_x),
        "y": rational_text(Fraction(node.y) - min_y),
        "energy": rational_text(Fraction(node.energy)),
        "service": rational_text(Fraction(node.service)),
    } for node in nodes]
    normalized.sort(key=lambda row: (
        row["kind"], row["x"], row["y"], row["energy"], row["service"]))
    return sha256_bytes(canonical_json({
        "schema": "translation_row_order_invariant_geometry_v1", "nodes": normalized
    }).encode("ascii"))


def _distance_squared(a: Node, b: Node) -> Fraction:
    dx, dy = Fraction(a.x) - Fraction(b.x), Fraction(a.y) - Fraction(b.y)
    return dx * dx + dy * dy


def proposal_reasons(candidate: Node, sites: list[Node], targets: list[Node],
                      side_m: int) -> list[str]:
    reasons = []
    if not (0 <= candidate.x < side_m and 0 <= candidate.y < side_m):
        reasons.append("outside_published_grid_box")
    if candidate.kind == "site":
        if any(_distance_squared(candidate, site) <= 2000 ** 2 for site in sites):
            reasons.append("site_separation_le_2000m")
    else:
        if not sites or min(_distance_squared(candidate, site) for site in sites) > 5000 ** 2:
            reasons.append("target_nearest_site_gt_5000m")
        if any(_distance_squared(candidate, target) < 200 ** 2 for target in targets):
            reasons.append("target_separation_lt_200m")
    return reasons


class ExclusionIndex:
    """Immutable input-identity view; collision means immediate slot failure."""
    def __init__(self, records: Iterable[dict], sources: Iterable[dict] = ()):
        self.raw = {}
        self.geometry = {}
        self.records = tuple(dict(row) for row in records)
        self.sources = tuple(dict(source) for source in sources)
        for row in self.records:
            for name in ("raw_sha256", "canonical_geometry_sha256"):
                if not re.fullmatch("[0-9a-f]{64}", row.get(name, "")):
                    raise ValueError(f"invalid exclusion {name}")
            self.raw.setdefault(row["raw_sha256"], []).append(row)
            self.geometry.setdefault(row["canonical_geometry_sha256"], []).append(row)

    @classmethod
    def from_paths(cls, paths: Iterable[Path]):
        sources, records = [], []
        for path in paths:
            raw = Path(path).read_bytes()
            manifest = json.loads(raw)
            rows = manifest.get("records")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"empty/malformed exclusion manifest: {path}")
            source = {"path": str(Path(path).resolve()), "sha256": sha256_bytes(raw),
                      "record_count": len(rows), "schema": manifest.get("schema")}
            sources.append(source)
            records.extend(dict(row, exclusion_source=str(Path(path).resolve())) for row in rows)
        return cls(records, sources)

    def collisions(self, raw_sha256: str, canonical_geometry_sha256: str) -> list[dict]:
        result = []
        for mode, records in (("raw_sha256", self.raw.get(raw_sha256, [])),
                              ("canonical_geometry_sha256",
                               self.geometry.get(canonical_geometry_sha256, []))):
            result.extend({"match": mode, "record": row} for row in records)
        return result

    def require_research_ready(self) -> None:
        required = {"PERMANENT_EXCLUSION_MANIFEST.json",
                    "SYNTHETIC_SMOKE_EXCLUSION.json",
                    "SYNTHETIC_EXCLUSION_MANIFEST.json",
                    "WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json"}
        names = {Path(source["path"]).name for source in self.sources}
        if not required.issubset(names):
            raise ValueError("official, pilot, author-smoke, v2-synthetic, and Windows-probe exclusions are required")
        permanent = next(source for source in self.sources
                         if Path(source["path"]).name == "PERMANENT_EXCLUSION_MANIFEST.json")
        if permanent["record_count"] != 12120:
            raise ValueError("permanent v1 official+pilot manifest must contain 12,120 records")
        for source in self.sources:
            if Path(source["path"]).name == "PERMANENT_EXCLUSION_MANIFEST.json":
                manifest = json.loads(Path(source["path"]).read_text(encoding="utf-8"))
                if (manifest.get("combined_record_count") != 12120
                        or manifest.get("combined_raw_sha256_unique") != 12120
                        or manifest.get("combined_canonical_geometry_unique") != 12120):
                    raise ValueError("permanent v1 exclusion manifest summary mismatch")
            elif Path(source["path"]).name in ("SYNTHETIC_SMOKE_EXCLUSION.json",
                                                "SYNTHETIC_EXCLUSION_MANIFEST.json",
                                                "WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json"):
                manifest = json.loads(Path(source["path"]).read_text(encoding="utf-8"))
                if not manifest.get("records") or any(
                    record.get("eligible_for_research") is not False
                    for record in manifest["records"]
                ):
                    raise ValueError("synthetic fixture identities must be explicitly excluded")


def default_exclusion_paths() -> tuple[Path, ...]:
    data_root = Path(__file__).resolve().parent.parent
    return (
        data_root / "generator_reconstruction/PERMANENT_EXCLUSION_MANIFEST.json",
        data_root / "generator_reconstruction/SYNTHETIC_SMOKE_EXCLUSION.json",
        Path(__file__).resolve().parent / "SYNTHETIC_EXCLUSION_MANIFEST.json",
        Path(__file__).resolve().parent / "WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json",
    )


def load_required_exclusions() -> ExclusionIndex:
    index = ExclusionIndex.from_paths(default_exclusion_paths())
    index.require_research_ready()
    return index


def derive_seed(namespace: str, candidate_sites: int, target_count: int,
                 partition: str, ordinal: int, stream: str) -> int:
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("root must provide a frozen non-empty v2 namespace")
    if (candidate_sites, target_count) not in PUBLISHED_FAMILIES:
        raise ValueError("unsupported family")
    if partition not in PARTITIONS or type(ordinal) is not int:
        raise ValueError("invalid partition or ordinal")
    if not 1 <= ordinal <= (4 if partition == "opportunity" else 1):
        raise ValueError("ordinal outside the fixed G23 allocation")
    if stream not in ("coordinates", "target_ids"):
        raise ValueError("invalid RNG stream")
    payload = canonical_json({
        "schema": "route_rl_sequential_v2_seed_v1", "namespace": namespace,
        "family": [candidate_sites, target_count], "partition": partition,
        "ordinal": ordinal, "stream": stream,
    })
    return int.from_bytes(hashlib.sha256(payload.encode("ascii")).digest()[:8], "big")


class LabelExhausted(RuntimeError):
    pass


def randbelow_unbiased(rng, bound: int, trace: list[dict]) -> int:
    """Uniform integer under ideal uint64 words; reject tail to avoid modulo bias."""
    if type(bound) is not int or not 1 <= bound <= 1 << 64:
        raise ValueError("bound outside uint64 range")
    limit = (1 << 64) - ((1 << 64) % bound)
    for attempt in range(1, LABEL_WORD_CAP + 1):
        word = rng.next_u64()
        if type(word) is not int or not 0 <= word <= UINT64_MASK:
            raise ValueError("RNG word outside uint64 range")
        accepted = word < limit
        trace.append({"bound": bound, "limit_exclusive": limit, "word_u64": word,
                      "word_attempt": attempt, "accepted": accepted})
        if accepted:
            return word % bound
    raise LabelExhausted("target-ID unbiased-word cap exhausted")


def shuffled_target_ids(count: int, rng) -> tuple[list[int], list[dict]]:
    ids = list(range(1, count + 1))
    trace: list[dict] = []
    for i in range(count - 1, 0, -1):
        j = randbelow_unbiased(rng, i + 1, trace)
        ids[i], ids[j] = ids[j], ids[i]
    return ids, trace


def _rng_state(rng) -> dict:
    return {"state_hex": f"{rng.state:016x}" if getattr(rng, "state", None) is not None else None,
            "draws": getattr(rng, "draws", None)}


def _coordinate(k: int, side: int) -> Decimal:
    if type(k) is not int or not 0 <= k < UINT53_DENOMINATOR:
        raise ValueError("coordinate bits outside 53-bit support")
    with localcontext() as ctx:
        ctx.prec = 100
        return Decimal(k * side) / Decimal(UINT53_DENOMINATOR)


def _finish(status: str, failure_reason: str | None, sites: list[Node],
            targets: list[Node], metadata: dict, exclusions: ExclusionIndex) -> dict:
    nodes = tuple(targets + sites)
    raw_text = render_instance_text(nodes)
    raw_hash = sha256_bytes(raw_text.encode("utf-8"))
    geometry_hash = canonical_geometry_identity(nodes) if nodes else None
    collisions = exclusions.collisions(raw_hash, geometry_hash) if geometry_hash else []
    if collisions:
        status, failure_reason = "generation_failed", "exposed_identity_collision"
    metadata.update({"status": status, "failure_reason": failure_reason,
                     "raw_sha256": raw_hash, "canonical_geometry_sha256": geometry_hash,
                     "exclusion_sources": list(exclusions.sources),
                     "exclusion_record_count": len(exclusions.records),
                     "identity_collisions": collisions,
                     "retained_slot": True, "replacement_on_failure": False,
                     "accepted_sites": len(sites), "accepted_targets": len(targets)})
    return {"schema": "sequential_constraint_reconstructed_result_v2",
            "status": status, "failure_reason": failure_reason,
            "solver_input_text": raw_text if status == "generated" else None,
            "retained_complete_or_partial_text": raw_text,
            "raw_sha256": raw_hash, "canonical_geometry_sha256": geometry_hash,
            "metadata": metadata}


def _generate(candidate_sites: int, target_count: int, coordinate_rng, label_rng,
              exclusions: ExclusionIndex, allocation: dict, *, synthetic: bool) -> dict:
    """Private core; test RNG injection is restricted to synthetic call sites."""
    if (candidate_sites, target_count) not in PUBLISHED_FAMILIES:
        raise ValueError("unsupported family")
    side = paper_side_m(target_count)
    metadata = {
        "schema": "sequential_constraint_reconstructed_metadata_v2",
        "protocol": PROTOCOL, "generator_version": GENERATOR_VERSION,
        "exact_author_generator_reproduction": False,
        "accepted_nodes_IID_uniform_over_square": False,
        "uniform_over_globally_feasible_map_set": False,
        "proposal_support": "{k*L/2^53:k=0,...,2^53-1}^2; x then y",
        "square_side_m": side, "family": [candidate_sites, target_count],
        "site_proposal_cap": SITE_PROPOSAL_CAP, "target_proposal_cap": TARGET_PROPOSAL_CAP,
        "label_word_cap": LABEL_WORD_CAP,
        "cap_probability_qualification": "ideal independent uniform-grid model only; no fixed-seed PRNG guarantee",
        "allocation_identity": dict(allocation), "synthetic_engineering_only": synthetic,
        "rng": {"algorithm": RNG_NAME, "version": RNG_VERSION,
                "coordinate_initial": _rng_state(coordinate_rng),
                "label_initial": _rng_state(label_rng)},
        "node_attempts": [], "placement_order_private": [], "target_label_word_attempts": [],
    }
    sites, targets = [], []
    for kind, count, cap in (("site", candidate_sites, SITE_PROPOSAL_CAP),
                              ("target", target_count, TARGET_PROPOSAL_CAP)):
        for position in range(1, count + 1):
            accepted = False
            for attempt in range(1, cap + 1):
                before = _rng_state(coordinate_rng)
                x_grid, y_grid = coordinate_rng.next53(), coordinate_rng.next53()
                x, y = _coordinate(x_grid, side), _coordinate(y_grid, side)
                node = Node(target_count + position if kind == "site" else position,
                            x, y, Decimal(0) if kind == "site" else Decimal("0.2"),
                            Decimal(0) if kind == "site" else Decimal(10), kind)
                reasons = proposal_reasons(node, sites, targets, side)
                metadata["node_attempts"].append({
                    "kind": kind, "placement_position": position, "proposal_attempt": attempt,
                    "x_grid_u53": x_grid, "y_grid_u53": y_grid,
                    "x": _decimal_text(x), "y": _decimal_text(y),
                    "rng_before": before, "rng_after": _rng_state(coordinate_rng),
                    "accepted": not reasons, "rejection_reasons": reasons,
                })
                if not reasons:
                    (sites if kind == "site" else targets).append(node)
                    metadata["placement_order_private"].append({
                        "kind": kind, "placement_position": position,
                        "proposal_attempt": attempt, "x": _decimal_text(x), "y": _decimal_text(y),
                        "solver_node_id": node.node_id if kind == "site" else None,
                    })
                    accepted = True
                    break
            if not accepted:
                metadata["rng"].update({"coordinate_final": _rng_state(coordinate_rng),
                                         "label_final": _rng_state(label_rng)})
                return _finish("generation_failed", f"{kind}_proposal_cap_exhausted",
                               sites, targets, metadata, exclusions)
    label_trace = []
    try:
        ids = list(range(1, target_count + 1))
        for i in range(target_count - 1, 0, -1):
            j = randbelow_unbiased(label_rng, i + 1, label_trace)
            ids[i], ids[j] = ids[j], ids[i]
    except LabelExhausted:
        metadata["target_label_word_attempts"] = label_trace
        metadata["rng"].update({"coordinate_final": _rng_state(coordinate_rng),
                                 "label_final": _rng_state(label_rng)})
        return _finish("generation_failed", "target_id_label_cap_exhausted",
                       sites, targets, metadata, exclusions)
    targets = [Node(ids[i], node.x, node.y, node.energy, node.service, node.kind)
               for i, node in enumerate(targets)]
    metadata["target_label_word_attempts"] = label_trace
    for record in metadata["placement_order_private"]:
        if record["kind"] == "target":
            record["solver_node_id"] = ids[record["placement_position"] - 1]
    metadata["rng"].update({"coordinate_final": _rng_state(coordinate_rng),
                             "label_final": _rng_state(label_rng)})
    return _finish("generated", None, sites, targets, metadata, exclusions)


def generate_allocated_instance(candidate_sites: int, target_count: int, *,
                                 namespace: str, partition: str, ordinal: int,
                                 exclusions: ExclusionIndex) -> dict:
    """One preallocated slot; no hidden replacement, quality feedback, or writes."""
    if not isinstance(exclusions, ExclusionIndex) or not exclusions.records:
        raise ValueError("an audited nonempty exclusion index is required")
    exclusions.require_research_ready()
    coordinate_seed = derive_seed(namespace, candidate_sites, target_count, partition, ordinal, "coordinates")
    label_seed = derive_seed(namespace, candidate_sites, target_count, partition, ordinal, "target_ids")
    allocation = {"namespace": namespace, "family": [candidate_sites, target_count],
                  "partition": partition, "ordinal": ordinal,
                  "coordinate_seed_u64": coordinate_seed, "target_id_seed_u64": label_seed}
    return _generate(candidate_sites, target_count, SplitMix64(coordinate_seed),
                     SplitMix64(label_seed), exclusions, allocation, synthetic=False)


def protocol_info() -> dict:
    return {"protocol": PROTOCOL, "version": GENERATOR_VERSION,
            "site_cap": SITE_PROPOSAL_CAP, "target_cap": TARGET_PROPOSAL_CAP,
            "label_cap": LABEL_WORD_CAP, "root_allocation_freeze_required": True,
            "no_study_generation_CLI": True, "PRNG_probability_is_ideal_model_only": True}


if __name__ == "__main__":
    print(canonical_json(protocol_info()))
