# Independent G2/G3 Data and Baseline Audit

Date: 2026-11-03 (Asia/Shanghai)  
Role: `nonrl_data_protocol`  
Scope: source/objective<EXECUTION_PATH> audit only. No quality maps, solver-quality calls, training, or Formal runs were launched.

## Frozen starting judgment

`INITIAL.md` was hash-frozen before the source audit at SHA256 `a9d650501ba6c45309e55873743506833e20901ac0a0b071930370b3ba6d0c9e`; receipt is `INITIAL_FREEZE.json`. The source audit confirms that the candidate endpoint is not a new metric, and that a claim against Liu must compare the same M objective under a strict shared cost cap against both author-faithful and same-objective methods.

## Metric and cost semantics

Liu's MILP minimizes total cost: station/drone fixed charges plus the sum of all drones' travel and inspection time cost (`audit/papers/Liu2026.txt:234–236`, model Eq. 1). The paper nevertheless explicitly reports both total cost and latest task completion time in §5.3 (`:756–757`) and discusses the time-cost tradeoff in §5.5. The official implementation's `Check.calculateLatestTime` sums each physical drone's trip times and returns the maximum across drones (`reference/java/official_source/Check.java:594–617`); `calculatePathTime` includes travel and target service (`:22–47`). This is the same operational quantity as the current `M_return` definition for the approved model: all vehicles begin at time zero, each vehicle's trips run sequentially, battery-swap delay is zero, and the score is the maximum cumulative flight-plus-service duration (`return_makespan/scorer.py:162–210`).

Therefore, `M_return` is an **existing Liu performance indicator promoted to the primary optimization objective**, not a newly introduced metric. Liu also explicitly includes `loadBalanceInsertion` over all drone routes with workload and cost terms in Eq. 23/§4.3.2 (`audit/papers/Liu2026.txt:545–561`). Eq. 23's `Tmax` is the allowable duty cap, not current global M, so this does not establish that Liu solves a formal global cost-capped min-max problem; it does rule out claims that Liu ignored time balance. An author-faithful route comparator must preserve this repair.

The current `C <= C_ref` with epsilon 0 and absolute accounting tolerance `1e-7` is a precise **no-cost-increase** rule, stricter than the colloquial “about the same cost.” It is a sound primary rule as already approved. Do not add an after-the-fact relative tolerance. Store complete original cost, fixed and operating components, raw `C-C_ref`, and `M_return` for every method. Fixed costs are unchanged in D because the domain fixes deployment and station types, but they remain in the full-cost audit.

The operational clock is specifically cumulative travel plus service time. It assumes all vehicles start at 0, their own trips execute sequentially, and battery replacement consumes no time. Do not describe it as a real-world wall-clock makespan with shared launch, charging, waiting, release-time, or turnaround effects absent from the model.

## Official instance extent recheck

`audit_instance_extents.py` independently parsed all files in the official input directory using the five-column format and classified targets/stations by positive/zero service energy, matching the official problem reader. For each instance, it computed combined target+station spans and tested whether an axis-aligned square of the published side length can contain the points after arbitrary translation. It did **not** assume that coordinates begin at zero.

Reproduced output:

```text
maps=120
literal absolute [0,L] box fit=36/120
translated fit at paper side=65/120
translated fit with L=15,000 for <=80 targets=120/120
by candidate-site count (paper-side translated fit):
3:24/30  4:19/30  5:2/10  6:0/10  7:0/10  8:0/10  9:10/10  10:10/10
```

The 36/120 figure in the pre-existing audit is only a literal `[0,L]` test and is not by itself evidence of mismatch because Liu does not specify the coordinate origin. The translation-invariant test is stronger: 55 official maps have an x- or y-span larger than the side declared for their family, so they cannot fit an axis-aligned square of that side under any translation. Conversely, use of 15,000 m for all `<=80` target families makes all extents fit, but fit does not establish the actual sampling domain or prove uniform generation.

Liu states uniform node placement and three spacing/coverage constraints—target separation at least 200 m, site separation greater than 2,000 m, and each target's nearest candidate site within DABS radius (`audit/papers/Liu2026.txt:580–584`). The local `external/LRPHSD` tree contains 120 pre-generated map files and no generator source/seed; the official Java solver reads those files. Thus exact author instance regeneration is not currently evidenced. Until the generator or seed is recovered, new maps must be labeled **constraint-reconstructed from published descriptions** with the side length, sampling, rejection, site placement, and service/energy choices frozen explicitly. Do not silently change 14,000 to 15,000 after seeing quality outcomes.

All 120 official input files have prior reproduction and metric exposure; the older Stage-A validation maps are a subset. Use their full SHA256 list plus a canonical coordinate/task-attribute identity manifest as an exclusion set. Renaming, changing whitespace, permuting rows, or translating the same geometry must not turn a known instance into a new development or Formal map. Keep map-generation seeds separate from solver/training seeds. Any new Formal set must be generated only after the method, seed aggregation, compute budget, comparison family, and statistics are frozen.

## Required G2/G3 comparison design

### D: Conditional route comparison (approved primary estimand)

- For each new map, run the frozen Liu original method (the accepted V6/semfix implementation or the unmodified official source under a preregistered runtime wrapper) and retain its complete, independently validated output `R_Liu`. The author's full cost `C_Liu` and `M_Liu` become the per-map reference; set `C_ref=C_Liu`. Use this exact `R_Liu` as the common anchor for all route refinements and as the explicit no-op author comparator. Do not substitute Greedy or a post-hoc best-of-several anchor, and do not use the old 1200 saved solutions as new confirmation data.
- Fix deployment, station types, and target-station ownership; permit station-internal slot assignment and physical target order/trip boundaries. All methods receive the same anchor, instance information, action feasibility rules, and independent evaluator.
- At both 6 s and 12 s, include model/process startup as specified, policy calls, all threshold queries, route construction/repair, validation, retries, and fallback in the D improvement wall-clock. RL and every optimized non-RL comparator receive the same route-improvement wall-clock from the same `R_Liu`; report the author solver's own anchor-generation time separately. Record measured hardware and thread counts. Report training separately; it is not free inference.
- On every map enforce the complete cost cap `C_method<=C_Liu` with epsilon 0 and tolerance `1e-7`; this is a per-map cost requirement, not merely equality of group means. Every candidate receives full feasibility and cost checks. Preserve any invalid, over-cap, late, dead-end, or failed output. Anchor fallback is reported as a method failure/fallback and scores M equal to the author anchor; no valid on-time result is a failed cell, never a deleted map.
- The primary M claim is a prespecified map-level aggregate improvement over `R_Liu` and over the strongest same-objective non-RL method, at both budgets, with the existing mean/CI/win-loss gates. Report each map's `(C_method-C_Liu)`, `(M_method-M_Liu)`, win/tie/loss, and every failure. Do not require an unsupported assertion that RL wins every individual map; the per-map cost cap must hold for all scored outputs while M superiority is assessed by the frozen paired-map statistics.
- Minimum comparator family: (1) no-op anchor; (2) Liu-faithful cost-objective route component including its load-balance insertion, assessed on M; (3) simple cheapest/nearest balanced insertion; (4) same-objective non-RL joint min-max ALNS or route/trip-repacking method under the same cap; (5) a threshold-feasibility/min-max non-RL implementation; (6) exact min-max reference only on a frozen solvable subdomain; (7) ordinary unconditioned direct-route RL; (8) threshold-conditioned direct-route RL if and only if G0 admits it.
- The prior station split-DP is an additive total-operating-time optimizer. Its results are not min-max results. A min-max DP, if developed, needs a separately frozen recurrence/code path and domain; it is a reference on that domain, not a whole-map performance baseline when station solves are incomplete.
- A threshold grid, repeated rollouts, or selecting the best of several candidate routes costs time. Fix the schedule before quality tests and charge all calls and output validation to the same 6/12 s budget. The simple non-RL threshold/repair control gets the same `tau` schedule, cost cap, state information, and candidate-generation/validation resources.
- Liu original cost mode and author load-balance mode remain distinct controls. Beating the cost-only variant's secondary M is an application result, not proof of an RL contribution. RL must also beat the frozen strongest same-objective non-RL and ordinary direct-route RL control.

### E: End-to-end comparison (only for an end-to-end claim)

The approved primary D comparison begins from a shared complete Liu output and therefore supports only a **conditional route-refinement claim**. It does not show that a fixed-deployment, fixed-target-station route policy beats the entire TSALNS system from a raw map: Liu may change locations, station types, and target-to-station assignments, while D fixes them. If claiming end-to-end/system superiority, run a separate E comparison with the original Liu pipeline and a precisely scoped route method on the same new map, same hard deadline, same hardware, and same initialization/outer decisions; charge anchor generation, loading, route search, validation, and output assembly to the same total 6/12 s. Report author cost and `M_return` together. Do not compare a 6/12-second route-only improvement stage against the full author runtime and call it end-to-end. The paper's Table 1 reports an average TSALNS runtime of 6.94 s over the official families (`audit/papers/Liu2026.txt:593–606`), so budget interpretation must be explicit. If E cannot preserve a common outer/initialization protocol within the total budget, keep the claim strictly conditional to D.

## Frozen-data and compute proposal

- Generate 48 exploratory maps at four per each of the 12 published `(candidate sites, targets)` families, stratified before output review. Keep every generated map, including infeasible/poor-opportunity maps and any failed solve, in the denominator and the manifest.
- Allocate the separate maximum 24 calibration/validation maps before results (for example, 12 calibration and 12 validation, with one from each family in each partition). Tune only non-RL controls there and freeze their configurations before the 48-map comparison. The 12/12 allocation is a recommendation, not an already frozen state fact.
- Keep within the authorized first-package ceiling: no more than 48 new opportunity/development maps, 24 separate non-RL calibration/validation maps, and 16 CPU core-hours total for all new non-RL generation, anchors, calibration, baselines, references, evaluation, validation, failures, and analysis. Each extra attempt consumes the same pool. G4 training resources remain a separate package.
- Primary map-level effect: per-map paired percent reduction `(M_anchor - M_method)/M_anchor`, equal weight per map. Report per-map values, mean/median, map bootstrap 95% CI, win/tie/loss, feasible/on-time/fallback rate, and raw cost deltas. Do not treat targets, stations, trips, solver seeds, or training seeds as independent maps.
- Apply the existing 5% mean target, positive map-level CI lower bound, win/loss and 100% on-time-valid/cost-feasible gates at both budgets; use a prespecified comparison-family correction. Do not relax criteria or select a baseline after observing outcomes.

## Mechanism cross-review

The threshold-conditioned candidate from `agents/new_route_mechanism/INITIAL.md` is a generic threshold/goal-conditioned route policy with terminal success `1{feasible, C<=C0, M<=tau}` and optional fixed threshold search. The requested point-by-point reply has been received in `agents/new_route_mechanism/CROSS_RESPONSE.md` (SHA256 `b29f2501b2a68eda7d8fc9b1b0e0547a5bbecf367ea47dfd666cdc6390c80624`), with final disposition in `agents/new_route_mechanism/FINAL_DECISION.md` (SHA256 `baaf5a21177c656074c611ef6d7faa7de0d55f45c84e1a6d238c58980420a713`). The response accepts that M is Liu's existing latest-time indicator, Eq. 23 is a required author-faithful comparator, and the candidate specifies neither a source-distinct route mechanism nor a frozen trainable threshold-reward protocol. The final decision is **NO-GO for this candidate as algorithmic novelty; do not train or revive it by retuning or renaming**. This closes cross-review of this candidate, not the search for a genuinely distinct mechanism; it does not block the approved, bounded G2/G3 opportunity and strong non-RL comparison.

## Current gate accounting

G1's independent dynamic acceptance has now **passed for its tested synthetic engineering contract**: nine dynamic tests and the 15-case independent scorer suite passed; no evaluated source was modified (`agents/final_acceptance/FINAL.md`, `RESULTS.json`). This is not route-quality evidence.

The current scientific boundary remains: zero new maps, solver-quality calls, training, or Formal results. The threshold candidate has a cross-reviewed G0 NO-GO and no replacement mechanism is approved. G2 and G3 are **not passed and have not been executed**. This audit is a protocol recommendation, not a freeze receipt. Before any quality call, root must freeze the final author-solution anchor/configuration, source-reconstructed generator and exposure exclusion, the 48+24 identities, same-objective baseline implementation/parameters, and statistical/time accounting. No RL benefit, innovation result, or project completion is established.

## Artifacts and verification

- `INITIAL.md` / `INITIAL_FREEZE.json`: independent initial judgment and hash freeze.
- `audit_instance_extents.py`: reproducible read-only parser/extent calculation.
- `CROSS_RESPONSE_NEW_ROUTE_MECHANISM.md` / `CROSS_RESPONSE_FREEZE.json`: independent point-by-point mechanism review and reply receipt; see the linked mechanism response and final decision above.
- No solver, map, training, or Formal result was created by this audit. The independent G1 tests are separate engineering evidence; the mechanism cross-response is separate G0 evidence.

