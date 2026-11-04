# Formal v3 mapset revision note

Date: 2026-11-01 UTC

The first witness-valid 36-map candidate suite was preserved at datasets/formal_v3_precoverage_revision_20261101. Before any optimizer was run, a design audit identified that the 12 km station spacing gave too few alternative Assignment receivers in the main suite. This would under-test the Global Assignment mechanism that is central to the current development result.

The active datasets/formal_v3 suite was therefore regenerated with 7.5 km station spacing for the 30 main maps, while retaining deliberately tight single-receiver stress cases. The generator now records, for every map, the number of targets with multiple DABS and SABS receivers.

Current active suite:
- 30 main maps; 6 stress maps.
- 36/36 constructive witnesses pass the independent evaluator.
- Zero SHA256 overlap with official Instances_Alg and locked_v2 files.
- Main-map alternative DABS receiver counts vary by distribution: clustered maps have no multi-receiver targets; uniform maps have some; boundary maps have many. This preserves a meaningful Assignment-transfer test without removing tight-coverage stress cases.
- Stress coverage also varies: high-density and boundary-concentration maps include alternative receivers; sparse, tight-coverage, workload-imbalance and combined energy/coverage maps remain intentionally restrictive.
- No optimizer has been run on either candidate suite.

Active generator SHA256: fe5cb5e11142ad67ec9c7fe1176e82f9f6da574326bcf254e49cf1eba4aa41af
Active manifest SHA256: be65b6a0fe2b47b7e2faf123a1c7eb4f18ac92560fe818b61a593467e6b6a37e
