# G0 trip-combination object: independent failure-attribution initial

Date: 2026-11-03. Role: route_failure_audit. Frozen before reading peer mechanism/adversarial/evidence INITIAL reports for this new object. Inputs are ROOT_OBJECT_BOUNDARY.md, already saved one-run station-G2 full witnesses, original model/evaluator source, and historical static LD-absorption decision. No solver, evaluator, DP, new-map generation, training or quality execution. Only standard-library JSON/hash/descriptive arithmetic on existing evidence.

## Observed opportunity and its limits

The sole G2 run contains 24 exposed maps; only 11 have both whole-map fixed-owner and joint-slot numerical references complete. The remaining 13 are partial. Their mixed-coverage contrasts cannot isolate slot reassignment, and no full-domain headroom upper bound is supplied. Old fixed-owner ALNS anchors are a narrower domain; beating those with joint DP does not show strength against station-joint non-RL.

Within the 11 complete maps there are 29 nonempty DABS station pairs. Reading their returned complete witnesses:

- 28 stations have positive fixed-owner-to-joint evaluator operating-minute differences (>1e-8); one ties; none worsens.
- In 25 of those 28 improving stations, the returned joint witness uses fewer nonempty trips. Three improve distance with the same trip count. This is descriptive association of returned witnesses, not an intervention that identifies trip count as the sole causal variable.
- Minimum fixed-owner slot duty slack is 511.4075909903974 minutes, joint 463.43818257707454 minutes, against the DABS duty cap600. Across these 29 stations, the MAXIMUM SUM of the two returned joint slot operating times is158.8593239959563 minutes and fixed-owner169.03459949035306. Thus current positive witnesses do not show a binding duty allocation barrier.
- Four joint witnesses use only LD; other chosen witnesses may use both slots or only SD. Chosen mixed assignment does NOT prove both vehicles are necessary: deterministic tie order may select one of multiple equal-cost representations.

Those observations motivate energy/geometry-sensitive trip grouping and ownership release as the concrete difficulty. They do not prove RL necessity, a novel representation, a failure rate, new development headroom or an effect on unseen maps. They do not justify enlarging the old cutoff or rerunning timeout/size rows.

## Exact standard object underlying H_s

At a fixed physical route prefix s, freeze remaining target set R and each physical slot's current location, residual trip energy and accumulated duty. A column is a slot-tagged sequence that continues that slot from its current location, visits a subset Q of R and returns to its home station, carrying its real sequence-dependent flight, fixed target service/energy and total minutes. Future fresh trips begin at the home station; the current continuation may have different resource offsets.

A completion is an exact cover of remaining targets by compatible continuation/fresh-trip columns, coupled by each slot's cumulative duty and at most one continuation of an already open trip. This is a residual resource-constrained routing / set-partitioning formulation. Selecting the next physical target or RETURN changes the feasible column family and the residual cover. Naming this family H_s, making it a hypergraph, attaching slot tags/energy/duty, counting overlaps, computing column dual prices or learning its value does not itself establish a new mathematical or algorithmic object.

The static model's trip order has no time-dependence, windows, shared chargers or synchronization. Independent closed trips on a slot may be permuted without real cost/resource change. A claim of essential global temporal coupling must identify an actual retained constraint, not add such a process to the original model.

## Falsifiable mechanisms and necessary controls

A viable proposal must specify a tractable statistic/update of H_s, exactly what information is computed at each physical action, how sequence-dependent feasibility is evaluated, whether it is lossless or approximate, and construction/update/wall-clock complexity. Any approximate family must expose missed trip columns and false allowed prefixes, not call itself an exact feasibility mask.

Specific predictions should distinguish competing explanations:

1. If a new H_s interaction feature represents higher-order battery/geometry packing, it should distinguish states whose singleton/pair features agree but whose feasible trip-cover consequences differ. A hand example can establish representational non-equivalence only, not actual solver or RL effect.
2. If “long-term RL credit” is claimed, it should outperform same-input greedy/reduced-cost, beam/enumeration, supervised/BC/value-guided and bandit controls after identical candidate construction costs and budgets. A supervised cost-to-go predictor or exact DP-driven policy is not independent RL evidence.
3. A station-joint route optimizer with ownership release, trip repacking and standard set-partitioning/route-pool/pricing capability is mandatory. Old per-slot ALNS cannot be the strongest baseline for this wider physical domain. Avoid giving H_s candidates or oracle values only to RL.
4. Feature/representation benefit and RL-training benefit are separate. If same H_s feature improves both greedy/BC and RL equally, that may be useful engineering but does not prove the claimed cross-step RL mechanism. Every component needs its own same-resource replacement/ablation.

G2's loose returned duty does not prove duty can be removed on all inputs. Any all-LD representative/absorption use requires its conditions; fixed station/drone purchase fees remain. Such standard dominance also must be available to non-RL controls. It is a warning against attributing a future old-data improvement to duty reasoning without a matching intervention.

## Prior-art boundary and current decision

The root boundary already points to Wang2503.10421 constraint-oriented dynamic hypergraph encoding, SED2AM2503.04085 multi-trip/vehicle-node/remaining-hours decoding, PIP/LMask anticipatory/lazy masks, and DPDP learned DP guidance. I have not newly performed version-specific full-text evidence verification for those sources here; local extracts and root summaries are not a substitute for the evidence agent's versioned source comparison. Therefore detailed inclusion/equivalence to any specific paper is UNKNOWN unless its actual equations are checked. Unknown overlap is not novelty credit.

**Decision: H_s as described is a standard residual trip-column/exact-cover object, not yet a complete new mechanism. G0 remains OPEN/NO_APPROVED_MECHANISM.** This does not disprove every prospective H_s-based algorithm. A specific non-direct increment, a complexity/approximation claim, a counterexample to claimed equivalence, and a frozen falsifiable protocol are still required. No quality or training execution is requested by this initial.

## Actual next exchange

Ask the mechanism agent for exact input/output/update equations and the smallest distinguishability example; ask the adversary whether the proposal reduces to residual set partition/dual pricing/standard constraint hypergraph feature augmentation; ask the evidence agent for the closest version-specific mathematical definitions rather than title-level comparison. Exchange only after all three initials are frozen.
