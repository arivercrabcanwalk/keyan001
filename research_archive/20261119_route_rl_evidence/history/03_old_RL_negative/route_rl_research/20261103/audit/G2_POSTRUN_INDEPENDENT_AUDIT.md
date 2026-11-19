# G2 station split-DP post-run independent audit

Date: 2026-11-03. Reviewer: `route_independent_audit`. This review reads/hash-checks stored JSON and recomputes elementary totals, identities and descriptive summaries. It invokes no project evaluator, DP, geometry, solver, training or server task. Stored evaluator feasibility is checked for consistency; it is not a fresh independent physical rescore by this reviewer.

## Decision and audit identity

**PASS the saved-output accounting and limited numerical-opportunity interpretation.** Source `g2_results_v2/REPORT.json` SHA256 is `830c0883bb93f89abc1a6b9aaac92300d11185cdc53223a0a8ad1a2661c66308`; final pre-execution freeze is `19c2bc761c33a34d6cc0d46a0c0dfa07e215c1f65a9f66cd75ae385cdfeb122c`. The audit JSON `G2_POSTRUN_INDEPENDENT_AUDIT.json` SHA256 is `0be20a6f58f567c39e48097c0ea72f16bef55dcd422187a017f5b50670645fff` and preserves 241 source-file identities, all132 station rows and all descriptive computations. It records zero accounting failures.

The one collection contains 24 maps, 132 stations, 98 active stations, 11 complete numerical-reference maps and 13 partial maps. It preserves 144 archived ALNS cells. All72 complete parent/fixed/joint saved solutions have matching map identity, exact-once target counts, station types and station unions; fixed-owner candidates retain each target's slot. Accepted station route lists match the actual integrated complete solutions. Every unresolved station retains its original parent route list. Stored full and trial audits are feasible with no issues. Full cost equals saved fixed cost plus0.5 times saved operating minutes; minute reconciliation is within2.28e-13 and station contribution sums agree with map percentage effects within2.45e-14. No numerical/implementation rejection, allocation error or station exception occurred.

## What the results show

All percentages below divide by the complete original comparator-map cost, including fixed fees. W/T/L uses raw signs; no tolerance suppresses small effects. These are exposed-data descriptive results without a confidence interval, generalization or fair-budget solver claim.

|Comparison|All24 mean / median|11 complete maps mean|13 partial maps mean|All24 W/T/L|
|---|---:|---:|---:|---:|
|Greedy → fixed-owner candidate|0.933169% /0.781919%|1.118484%|0.776364%|23/1/0|
|Greedy → joint-slot candidate|3.139719% /3.209203%|4.664512%|1.849509%|23/1/0|
|Fixed-owner → joint-slot candidate|2.230473% /2.231861%|3.586871%|1.082751%|22/2/0|
|Archived6s best-of3 → joint candidate|1.534726% /1.805021%|3.586871%|-0.201705%|16/0/8|
|Archived12s best-of3 → joint candidate|1.531729% /1.805021%|3.586871%|-0.207237%|16/0/8|

The partial-map fixed-to-joint contrast is **mixed solve coverage** and cannot be called pure slot reassignment. The all24 positive average versus old ALNS is concentrated in complete maps. All11 complete maps improve on both archived anchors, whereas partial maps yield5 wins and8 losses against either budget anchor. These completion strata arise from computational coverage and correlate with smaller/easier station pools; they are not independent randomized groups. Do not select the complete stratum as though it were a new development set.

On every complete map the fixed-owner numerical-reference cost equals the archived ALNS best-of3 cost exactly in the saved numbers. Thus releasing station-internal slot ownership accounts for the additional qualified fixed-to-joint difference there. The archived ALNS was fixed-owner, while the joint reference permits slot reassignment. This exposes a meaningful larger physical route domain; it does **not** establish that RL or the DP algorithm beats the strongest non-RL solver on the same domain and resources. The next strong non-RL control must be allowed the same station-internal target-slot assignment plus route/trip decisions. Reusing old fixed-owner ALNS as the sole strongest comparator would confound action domain with learning.

## Resource coverage and station types

|Station type|All stations / active|Both references complete|Joint unresolved status|
|---|---:|---:|---|
|Closed|34/0|32|2 unattempted after map deadline|
|SABS|16/16|15|1 size limit|
|DABS|82/82|48|32 size limits,2 map-time bounds|

Across all132 stations the fixed-owner arm has97 complete,33 size-limit and2 unattempted rows; the joint arm has95 complete,33 size-limit,2 map-time-bound and2 unattempted rows. All oversized union pools remain unresolved; no small-slot shortcut is relabelled a full station reference. No valid lower bound is supplied for these unresolved domains, so remaining full-domain opportunity is INCONCLUSIVE. A partial feasible gain cannot cap the remaining gain.

Station-type contributions use each map's complete objective denominator and retain zero-contribution maps. Across all24 maps, SABS contributes0.147386 percentage points to Greedy-to-joint gain; DABS contributes2.992332 points, summing to3.139719%. All fixed-to-joint cost differences arise in DABS, subject to mixed-coverage qualification on partial maps. The saved audit JSON contains complete/partial/type/size-compatible rows for fuller tables without another DP call.

Of48 completed active DABS joint references,31 use both slots,12 place all targets on LD, and5 place all on SD. Forty-seven change at least one target's slot;46 have a strictly positive fixed-to-joint DP-minute difference. These witnesses refute any claim that the observed numerical opportunity consists solely of all-LD absorption, but they do not create a novel mechanism. They remain standard assignment/route-partition effects until a specific additional algorithmic contribution is defined and compared.

Saved accepted reference coverage margins are at least36.669 metres. Saved fixed/joint complete-candidate minimum battery slack is0.0005342; minimum cumulative-duty slack is262.873 minutes (including retained unresolved parent stations); completed DP references have at least339.482 minutes of DP-duty slack. Accordingly these specific witnesses do not support a claim that binding cumulative duty caused their main gain. Battery and routing may matter, but causal attribution needs separate evidence; inventing a duty-credit story from these numbers would overreach.

## Timing and claim limits

Saved core batch time is78.600252s; sum of per-map time through map-record fsync is78.366807s. Maximum map time is12.114574s. Two maps exceed the12s scheduling allowance by0.114574s and0.090705s; the driver reports both overruns. This is a scheduling-capped numerical reference with validation/output charged, not a hard12s fair-budget solver. Archived best-of3 uses three historical runs, about18s or36s total, with different historical hardware/provenance; no cross-hardware time ranking follows.

The audit supports a real, feasible joint-slot route opportunity in the exposed numerical domain and corrects the old fixed-owner opportunity interpretation. It does not prove new-map headroom, mechanism novelty, need for RL, RL superiority, G4 admission, Formal success or G0-G8 completion. Preserve the original one-run output and all negative/partial cases; no rerun, larger cutoff, new seed or post-outcome threshold change is warranted by this audit.
