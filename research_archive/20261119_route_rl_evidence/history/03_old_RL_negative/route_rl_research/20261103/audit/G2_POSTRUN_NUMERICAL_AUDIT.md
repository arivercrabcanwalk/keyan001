# Station G2 saved-result numerical audit

Date: 2026-11-03. Reviewer: `route_mechanism_g4`. This report reads the one saved collection and recomputes elementary arithmetic, target-domain identities and descriptive totals. It imports no project scientific module and invokes no DP, evaluator, solver, geometry, server or training. Stored evaluator audits are checked for consistency, not represented as a new independent physical rescore. A first read-only aggregation attempt encountered a null empty-slot slack, exited 1 before writing results, and was corrected to exclude null values from numeric minima. No source witness or scientific output was changed.

## Decision and evidence

**PASS the saved-output numerical consistency and bounded descriptive interpretation.** Source `joint_route_env/g2_results_v2/REPORT.json` has SHA256 `830c0883bb93f89abc1a6b9aaac92300d11185cdc53223a0a8ad1a2661c66308`; final metadata freeze has SHA256 `19c2bc761c33a34d6cc0d46a0c0dfa07e215c1f65a9f66cd75ae385cdfeb122c`. My independently generated arithmetic audit is `G2_POSTRUN_NUMERICAL_AUDIT.json`, SHA256 `778fc0ff086bd7290802b918155ab2b9d711b48b4a33b9362936160535916a0c`, and records zero consistency issues plus hashes of each read input. I also read `G2_POSTRUN_INDEPENDENT_AUDIT.md`; its counts and scientific limits agree with the independent calculations here.

The collection preserves 24 maps, 132 station rows, 98 active stations, 11 maps with both complete numerical references and 13 partial maps. Every saved parent equals its canonical archived Greedy parent. All72 parent/fixed/joint saved full-map audits are feasible with empty issue lists; their costs match fixed cost plus0.5 times saved operating minutes. Station types and target unions match the parent; fixed-owner routes retain target slots. Each accepted raw station route list matches the integrated candidate, while each unresolved station retains its parent's list. All144 archived rows remain valid saved anchors. These facts support consistent saved-output accounting, not general solver reliability.

## Independent descriptive calculations

All percentages use each complete original comparator-map cost, including fixed fees. W/T/L uses literal raw signs. These old exposed maps are descriptive units; no new-map confidence or fair-resource claim follows.

|Comparison|All24 mean|11 complete mean|13 partial mean|All24 W/T/L|
|---|---:|---:|---:|---:|
|Greedy to fixed-owner candidate|0.933169%|1.118484%|0.776364%|23/1/0|
|Greedy to joint-slot candidate|3.139719%|4.664512%|1.849509%|23/1/0|
|Fixed-owner to joint-slot candidate|2.230473%|3.586871%|1.082751%|22/2/0|
|Archived6s best-of3 to joint candidate|1.534726%|3.586871%|-0.201705%|16/0/8|
|Archived12s best-of3 to joint candidate|1.531729%|3.586871%|-0.207237%|16/0/8|

The partial-map fixed-to-joint difference mixes solve coverage and cannot isolate assignment gain. The complete-map fixed-owner cost equals the archived best-of-three anchor in every saved complete map; there, joint-slot reassignment plus its coupled routing yields the additional qualified numerical-reference difference. The 11 complete maps are selected by computational coverage, not randomization; selecting them as a fresh development set would reuse exposed outcomes. Partial maps lose against archived anchors on average and have5 wins/8 losses. Both strata must remain visible.

## Numerical/resource checks

The maximum absolute DP-to-evaluator complete-cost residual is `2.2737367544323206e-13`; the maximum DP station-minute versus saved evaluator station-minute difference is `2.842170943040401e-14`. Twenty-four raw cost residuals are negative and remain recorded without clipping or tolerance-based tie relabelling. Accepted feasibility and small residuals support these witnesses, not equivalence of all floating-point orders or strict optimality.

The fixed arm has97 completed,33 size-limit and2 unattempted station rows; the joint arm has95 completed,33 size-limit,2 bounded-time exits and2 unattempted rows. No oversized union is silently replaced by separate smaller-slot references. The34 closed stations include2 conservatively unattempted after a deadline. Of16 SABS stations,15 have paired complete references and zero fixed-to-joint minute difference. Of82 DABS stations,48 have paired complete references, contributing a total `405.56492911842446` numerical DP minutes of difference; this station sum is descriptive and is not a new set of independent statistical replicates.

Among48 completed DABS joint witnesses,31 use both slots,12 use only LD and5 use only SD. This contradicts an interpretation that every observed gain is merely all-LD absorption; it does not establish an innovative algorithm. Minimum saved full-map battery slack is `0.0005342121948004319`, minimum cumulative duty slack is `262.8734051061642` minutes, minimum accepted reference coverage slack is `36.66917974946409` metres, and minimum accepted DP-duty slack is `339.48161600816815` minutes. These particular witnesses provide no evidence that binding cumulative duty drives the main improvement. Battery/route interactions remain possible, but their causal contribution needs a defined new comparison rather than a post-hoc story.

## Research implication and next admissible work

The diagnostic establishes feasible station-internal target-slot/routing opportunity on exposed inputs and corrects the earlier fixed-owner interpretation. The archived ALNS domain fixes slot ownership while this joint domain releases it. Therefore the approximately1.53% average historical-anchor difference does not establish RL superiority or a win against the strongest non-RL method in the same decision domain. A meaningful G3 comparator must jointly decide station-internal slot ownership, route order and trip boundaries with the same information, initialization/candidates and accounted resource budget as the eventual route policy.

This audit does not identify an approved novel mechanism or demonstrate that RL is necessary. Standard partition DP, target-slot serialization, counterfactual credit or new network labels do not become new contributions from this diagnostic. No remaining opportunity upper bound follows for33 size-limited stations or the time/unattempted cases; even completed references remain numerical-qualified. Do not enlarge this old cutoff/pool or rerun failures to seek positives. New mechanism definition, source-grounded precedent contrast, a falsifiable prediction, new-development strongest non-RL comparisons, genuinely cross-step route RL with independent training seeds, frozen Formal, innovation ablations and independent G8 acceptance remain distinct unfinished tasks.
