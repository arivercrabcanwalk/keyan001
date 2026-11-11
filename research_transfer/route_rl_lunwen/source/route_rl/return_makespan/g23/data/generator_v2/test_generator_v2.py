from __future__ import annotations

from decimal import Decimal, localcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import generator_v2 as g


class ScriptedCoordinates:
    def __init__(self, points):
        self.words = [word for point in points for word in point]
        self.state = self.draws = 0

    def next53(self):
        word = self.words[self.draws]
        self.draws += 1
        self.state = self.draws
        return word


class ScriptedWords:
    def __init__(self, words):
        self.words = list(words)
        self.state = self.draws = 0

    def next_u64(self):
        word = self.words[self.draws]
        self.draws += 1
        self.state = self.draws
        return word


def fixture_points():
    n = 1 << 53
    return [(0, 0), (n // 2, 0), (0, n // 2)] + [(i * (n // 32), 0) for i in range(1, 11)]


def fixture_result(exclusions=None):
    coords = ScriptedCoordinates(fixture_points())
    labels = ScriptedWords([0] * 9)
    return g._generate(3, 10, coords, labels, exclusions or g.ExclusionIndex([]),
                       {"namespace": "synthetic-fixture-only", "partition": "synthetic",
                        "ordinal": 0}, synthetic=True)


class GeneratorV2Tests(unittest.TestCase):
    def test_original_v1_is_preserved_and_rng_reference_words_match(self):
        original = Path(__file__).resolve().parent.parent / "generator_reconstruction/generator.py"
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                         "b445a318d6a2681015e078f77d3755635a452d0fca571e5c8e75a7fc3c5d04bb")
        rng = g.SplitMix64(0)
        self.assertEqual([rng.next_u64() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])

    def test_fixed_caps_family_side_and_seed_streams(self):
        self.assertEqual((g.SITE_PROPOSAL_CAP, g.TARGET_PROPOSAL_CAP), (32, 1024))
        self.assertEqual([g.paper_side_m(x) for x in (10, 80, 95, 110)],
                         [14000, 14000, 15000, 20000])
        args = ("synthetic-only-seed-check", 3, 10, "opportunity", 1)
        self.assertNotEqual(g.derive_seed(*args, "coordinates"), g.derive_seed(*args, "target_ids"))
        with self.assertRaises(ValueError):
            g.derive_seed("", 3, 10, "opportunity", 1, "coordinates")
        with self.assertRaises(ValueError):
            g.generate_allocated_instance(3, 10, namespace="no-map", partition="opportunity",
                                          ordinal=1, exclusions=g.ExclusionIndex([]))

    def test_exact_predicate_boundaries(self):
        node = lambda i,x,y,k: g.Node(i,Decimal(x),Decimal(y),Decimal("0.2") if k=="target" else Decimal(0),
                                     Decimal(10) if k=="target" else Decimal(0),k)
        site = node(11, 0, 0, "site")
        self.assertIn("site_separation_le_2000m",
                      g.proposal_reasons(node(12,2000,0,"site"),[site],[],14000))
        self.assertEqual(g.proposal_reasons(node(1,5000,0,"target"),[site],[],14000),[])
        self.assertEqual(g.proposal_reasons(node(2,200,0,"target"),[site],
                                            [node(1,0,0,"target")],14000),[])
        self.assertIn("target_separation_lt_200m",g.proposal_reasons(
            node(2,"199.99999999999999999999999",0,"target"),[site],[node(1,0,0,"target")],14000))
        self.assertIn("target_nearest_site_gt_5000m",g.proposal_reasons(
            node(1,"5000.00000000000000000000001",0,"target"),[site],[],14000))

    def test_success_retains_full_trace_and_only_five_columns_go_to_solver(self):
        result = fixture_result()
        self.assertEqual(result["status"], "generated")
        meta = result["metadata"]
        self.assertTrue(meta["synthetic_engineering_only"])
        self.assertEqual(len(meta["node_attempts"]),13)
        self.assertEqual(meta["rng"]["coordinate_final"]["draws"],26)
        self.assertEqual(len(meta["placement_order_private"]),13)
        self.assertFalse(meta["replacement_on_failure"])
        self.assertFalse(meta["accepted_nodes_IID_uniform_over_square"])
        rows = result["solver_input_text"].splitlines()
        self.assertEqual(len(rows),14)
        self.assertTrue(all(len(row.split()) == 5 for row in rows))
        self.assertNotIn("placement", result["solver_input_text"])
        ids = [record["solver_node_id"] for record in meta["placement_order_private"]
               if record["kind"]=="target"]
        self.assertEqual(sorted(ids),list(range(1,11)))
        self.assertNotEqual(ids,list(range(1,11)))

    def test_rejected_node_does_not_restart_accepted_prefix(self):
        points = fixture_points()
        points.insert(1,(0,0))
        result = g._generate(3,10,ScriptedCoordinates(points),ScriptedWords([0]*9),
                             g.ExclusionIndex([]),{"namespace":"synthetic"},synthetic=True)
        self.assertEqual(result["status"],"generated")
        records = result["metadata"]["node_attempts"]
        self.assertEqual(records[1]["rejection_reasons"],["site_separation_le_2000m"])
        self.assertEqual(records[2]["proposal_attempt"],2)
        self.assertEqual(records[2]["placement_position"],2)
        self.assertEqual(result["metadata"]["rng"]["coordinate_final"]["draws"],28)

    def test_site_cap_failure_is_exact_and_retains_partial_identity(self):
        coords = ScriptedCoordinates([(0,0)]*33)
        result = g._generate(3,10,coords,ScriptedWords([]),g.ExclusionIndex([]),
                             {"namespace":"synthetic"},synthetic=True)
        self.assertEqual(result["failure_reason"],"site_proposal_cap_exhausted")
        self.assertEqual(coords.draws,66)
        self.assertEqual(result["metadata"]["accepted_sites"],1)
        self.assertEqual(len(result["metadata"]["node_attempts"]),33)
        self.assertIsNone(result["solver_input_text"])
        self.assertEqual(len(result["raw_sha256"]),64)
        self.assertEqual(len(result["canonical_geometry_sha256"]),64)

    def test_target_cap_failure_is_exact_and_retains_site_prefix(self):
        coords = ScriptedCoordinates(fixture_points()[:3]+[(g.UINT53_DENOMINATOR-1,)*2]*1024)
        result = g._generate(3,10,coords,ScriptedWords([]),g.ExclusionIndex([]),
                             {"namespace":"synthetic"},synthetic=True)
        self.assertEqual(result["failure_reason"],"target_proposal_cap_exhausted")
        self.assertEqual(coords.draws,2*(3+1024))
        self.assertEqual(result["metadata"]["accepted_targets"],0)
        self.assertEqual(result["metadata"]["node_attempts"][-1]["proposal_attempt"],1024)
        self.assertIsNone(result["solver_input_text"])

    def test_randbelow_tail_rejection_removes_modulo_bias(self):
        rng = ScriptedWords([(1<<64)-1,4])
        trace=[]
        self.assertEqual(g.randbelow_unbiased(rng,3,trace),1)
        self.assertEqual([row["accepted"] for row in trace],[False,True])
        self.assertEqual(rng.draws,2)

    def test_label_cap_is_retained_failure_and_never_changes_geometry(self):
        # First shuffle bound=10 rejects the last 6 uint64 words.
        result = g._generate(3,10,ScriptedCoordinates(fixture_points()),
                             ScriptedWords([(1<<64)-1]*128),g.ExclusionIndex([]),
                             {"namespace":"synthetic"},synthetic=True)
        self.assertEqual(result["failure_reason"],"target_id_label_cap_exhausted")
        self.assertEqual(len(result["metadata"]["target_label_word_attempts"]),128)
        self.assertEqual(result["canonical_geometry_sha256"],fixture_result()["canonical_geometry_sha256"])

    def test_raw_and_canonical_collisions_fail_without_extra_coordinates(self):
        good=fixture_result()
        index=g.ExclusionIndex([{"raw_sha256":good["raw_sha256"],
                                 "canonical_geometry_sha256":good["canonical_geometry_sha256"],
                                 "reason":"synthetic-exposed"}])
        result=fixture_result(index)
        self.assertEqual(result["failure_reason"],"exposed_identity_collision")
        self.assertEqual(result["metadata"]["rng"]["coordinate_final"]["draws"],26)
        self.assertIsNone(result["solver_input_text"])
        self.assertEqual({row["match"] for row in result["metadata"]["identity_collisions"]},
                         {"raw_sha256","canonical_geometry_sha256"})

    def test_canonical_identity_is_v1_compatible_translation_order_and_id_invariant(self):
        nodes=g.parse_instance_text(fixture_result()["solver_input_text"])
        with localcontext() as ctx:
            ctx.prec=120
            shifted=tuple(g.Node(n.node_id+100,n.x+Decimal("17.25"),n.y+Decimal("29.5"),
                                  n.energy,n.service,n.kind) for n in reversed(nodes))
        self.assertEqual(g.canonical_geometry_identity(nodes),g.canonical_geometry_identity(shifted))
        path=Path(__file__).resolve().parent/"transaction/ORIGINAL_FILE.py"
        spec=importlib.util.spec_from_file_location("frozen_generator_v1",path)
        original=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=original
        spec.loader.exec_module(original)
        self.assertEqual(g.canonical_geometry_identity(nodes),original.canonical_geometry_identity(nodes))

    def test_default_sources_include_official_pilot_author_smoke_synthetic_and_windows_probe(self):
        paths=g.default_exclusion_paths()
        existing=g.ExclusionIndex.from_paths(paths[:2])
        self.assertEqual(len(existing.records),12121)
        self.assertEqual(len(existing.sources),2)
        self.assertEqual(paths[2].name,"SYNTHETIC_EXCLUSION_MANIFEST.json")
        self.assertEqual(paths[3].name,"WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json")

    def test_research_api_requires_complete_frozen_exclusion_sources(self):
        partial=g.ExclusionIndex.from_paths(g.default_exclusion_paths()[:2])
        with self.assertRaisesRegex(ValueError,"official, pilot"):
            partial.require_research_ready()
        complete=g.load_required_exclusions()
        self.assertEqual(len(complete.records),12131)
        self.assertEqual(len(complete.sources),4)
        with self.assertRaises(ValueError):
            g.generate_allocated_instance(3,10,namespace="synthetic-no-map",
                partition="opportunity",ordinal=1,exclusions=partial)

    def test_official_pilot_author_smoke_and_v2_synthetic_collisions_fail_closed(self):
        index=g.load_required_exclusions()
        data=Path(__file__).resolve().parents[1]
        official_file=Path(__file__).resolve().parents[6]/"reproduction/reviewer_package_semfix/external/LRPHSD/data/Instances_Alg/3_10_1.txt"
        official=g.parse_instance_text(official_file.read_text(encoding="utf-8-sig"))
        official_result=g._finish("generated",None,
            [node for node in official if node.kind=="site"],
            [node for node in official if node.kind=="target"],{"node_attempts":[]},index)
        self.assertEqual(official_result["failure_reason"],"exposed_identity_collision")
        pilot_path=data/"generator_reconstruction/PILOT_CANDIDATES.jsonl"
        with pilot_path.open(encoding="utf-8") as handle:
            pilot=json.loads(handle.readline())
        pilot_nodes=g.parse_instance_text(pilot["raw_instance_text"])
        pilot_result=g._finish("generated",None,
            [node for node in pilot_nodes if node.kind=="site"],
            [node for node in pilot_nodes if node.kind=="target"],{"node_attempts":[]},index)
        self.assertEqual(pilot_result["failure_reason"],"exposed_identity_collision")
        smoke_path=Path(__file__).resolve().parents[2]/"author_baseline/synthetic_smoke/fixture.txt"
        smoke_nodes=g.parse_instance_text(smoke_path.read_text(encoding="utf-8-sig"))
        smoke_result=g._finish("generated",None,
            [node for node in smoke_nodes if node.kind=="site"],
            [node for node in smoke_nodes if node.kind=="target"],{"node_attempts":[]},index)
        self.assertEqual(smoke_result["failure_reason"],"exposed_identity_collision")
        synthetic_result=fixture_result(g.load_required_exclusions())
        self.assertEqual(synthetic_result["failure_reason"],"exposed_identity_collision")


if __name__ == "__main__":
    unittest.main()
