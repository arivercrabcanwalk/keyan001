# Independent static statistical design review

Date: 2026-11-14. Review scope: frozen design, proposed post-collection analysis, and claim boundaries. No numerical/scientific analysis, scoring, solver execution, server operation, training, or protected-state/source edit was performed by this reviewer. The sole new artifact is this memo.

## Conclusion

The proposed map-level aggregation is defensible for an explicitly post hoc exploratory summary. The main risks are overstating precision, treating anchor gains as end-to-end author superiority, and broadening this completed nonRL foundation batch into an RL or whole-project pass.

This authorized three-wind G3 nonRL foundation does not require a positive RL result or an admitted RL mechanism. A scoped completion decision can follow the opportunity/variance summary, technical accounting, and frozen nonRL deployment-selection rule. G0/AIR2, training admission, RL independent contribution, Formal, and G8 remain separate.

## Frozen facts and analysis boundary

1. The two new frozen contracts do not prescribe a hypothesis test, bootstrap method, confidence level, multiplicity correction, or numerical superiority threshold. They prescribe equal wind/family weights, map-level replication, ITT treatment, and reporting of all seeds. Pre-execution registration concerns the population and execution plan; a newly selected analysis is not retrospectively preregistered. Historical 5% RL objectives and retained 0.3% cost-era language are not retrospective G3 gates. Sources: `agents/G3_EXECUTION_FREEZE.md:131-157`; `/Users/USER/Documents/ChatGPT/lunwen/RESEARCH_PLAN_ROUTE_RL.md:295-297`.

2. The frozen independent unit is a base map: n=24, with two maps per each of twelve fixed families. Three winds are repeated measurements; ten nonRL run seeds are repeated computational runs, not additional maps or independent training seeds. The fixed-wind domain does not establish all-weather generalization. Sources: `agents/G3_EXECUTION_FREEZE.md:11,131,157`.

3. Every planned row remains in the analysis record. Invalid/late delivery receives virtual anchor coding separately from an actual on-time fallback; ineligible-anchor quality remains undefined and its skip/reliability record is retained. Source: `agents/G3_EXECUTION_FREEZE.md:153-157`; `execution_v1/EXPERIMENT_FREEZE.json:62-67`.

All package-relative source paths above and below resolve from `/Users/USER/Documents/ChatGPT/lunwen/joint_weather_emergency/20261114_f3_g3_authorized_v1/`.

## Estimand and aggregation

Use one explicit mean estimand:

```text
u_i,w,r,m,D = 1 - M_i,w,r,m,D / M_author,i,w
U_i,m,D     = mean over the 3 fixed winds and 10 run seeds of u
Delta_i,D   = U_i,commonH,D - U_i,ALNS,D
Overall     = mean over the 24 maps
```

With exactly two maps per family, the last mean equals the frozen equal-family mean. Gains multiplied by 100 are percentage points. A ratio of pooled makespan means is a different estimand. Seed medians, minima, and best-of-ten results remain secondary descriptions; they should not replace the mean after inspection. Sources: `agents/G3_EXECUTION_FREEZE.md:131,157`.

The frozen seed indices may be paired as computational blocks, but the freeze explicitly does not assume identical random streams between methods. Averaging the fixed seed panel within each map avoids pretending that such a shared-randomness guarantee exists. Source: `agents/G3_EXECUTION_FREEZE.md:131`.

## Uncertainty and multiplicity

A family-stratified paired map-cluster bootstrap is a reasonable exploratory interval procedure. Resample two maps with replacement within each fixed family. Every sampled map carries its complete wind x seed x method x budget block, and the same sampled clusters feed every contrast. Interpret intervals as uncertainty across generated maps conditional on the fixed twelve-family mixture, three winds, author-anchor convention, and ten-seed panel.

With only two maps per family, bootstrap calibration is fragile. Show all twenty-four paired map vectors and descriptive leave-one-family-out sensitivity. Do not resample winds as independent weather observations or infer generalization over arbitrary wind directions/speeds. The frozen generator is explicitly not an IID uniform-map generator. Sources: `agents/G3_EXECUTION_FREEZE.md:17,157`.

No p value is necessary to complete this foundation's descriptive purpose. A map-level sign-flip test, if ever added later, would require a justified independent, sign-symmetric paired-effect null. Algorithm labels were not randomly assigned; balanced alternating execution order does not make sign-flipping an exact randomized-treatment test. A zero-mean null alone is insufficient. Source: `agents/G3_EXECUTION_FREEZE.md:133`.

Parent's subsequently reported analysis intent specifies 50,000 family-stratified map-cluster bootstrap draws, seed 2026111419, an eight-contrast family, pointwise 95% intervals, Bonferroni 99.375% percentile intervals, no p values, complete map vectors, and leave-one-family-out sensitivity. This is coherent as a post-collection exploratory interval plan, provided all eight contrasts are explicitly enumerated before execution and all are reported. The Bonferroni level is nominally appropriate for eight intervals; it does not cure small-stratum bootstrap coverage limitations. A percentile interval is not a hypothesis-test p value. No numerical execution or analysis-intent file verification was undertaken by this reviewer.

## Author, cost, timing, and reliability claims

The full author run is outside each control's 6/12-second refinement budget, and its cost remains separately visible. Each map-wind cell has one frozen author seed. Contrasts condition on that realized anchor; they do not estimate the author algorithm's expected performance across author seeds. Source: `agents/G3_EXECUTION_FREEZE.md:19,99-109`.

The defensible performance description is conditional route refinement from the same full same-wind author anchor, under the same per-row full-author cost cap. A mean cost ratio is not proof of the required individual cap. Preserve actual per-row cap diagnostics and acceptance evidence. A whole-system end-to-end superiority claim requires its separate E protocol. Sources: `agents/G3_EXECUTION_FREEZE.md:11,99-109`; `/Users/USER/Documents/ChatGPT/lunwen/USER_RESEARCH_REQUIREMENTS.md:291-293`.

When all registered controls are accepted, accepted and ITT summaries coincide for this batch only after the analysis input has retained every planned row. Continue to separate actual anchor-equivalent output, actual fallback, and virtual ITT coding. Report observed acceptance descriptively. Structured repeated calls do not support an independent-binomial general-reliability claim with n=2880. Cell seed SD measures computational variability; an SD pooling winds and seeds mixes environmental variation with computational variation. Sources: `agents/G3_EXECUTION_FREEZE.md:155-157`; `/Users/USER/Documents/ChatGPT/lunwen/LATEST_STATUS.md:3-7`.

## Deployment selection and oracle summaries

Taking the better method separately per map, wind, or seed is an optimistic oracle rather than a deployable baseline. If displayed, label it descriptive hindsight opportunity. Preserve both methods' complete results. Source: `agents/G3_EXECUTION_FREEZE.md:157`.

Parent's subsequently reported choice of one global method per budget by mean normalized makespan, with exact ties assigned to ALNS, is a valid calibration rule for future use when frozen before new DEV. Its performance on the opportunity data remains selection-affected; this is post-collection calibration, not preregistered superiority or independent validation. Requiring both controls in future RL comparisons avoids attributing a selection artifact to an RL contribution. Strict binary64 win/tie/loss reporting is consistent with the parent intent; no invented time epsilon is needed. The interpretation should distinguish exact numerical ties from practical equivalence.

## G3 closure boundary

The scoped freeze explicitly says G3 establishes complete qualification, strong nonRL controls, and opportunity/variance in these three fixed scenarios, and does not require prior RL/Formal positivity. A null method comparison would not invalidate that purpose. Sources: `agents/G3_EXECUTION_FREEZE.md:157,177`.

A blanket full-project G3 pass still needs an itemized audit against the broader comparator and data-split obligations. The new batch's complete counts alone are insufficient for that broader label. The broader plan includes applicable random/rule/greedy/beam/supervised/BC/bandit comparators and new train/validation/development identity rules; current applicability and completion should be stated explicitly. Source: `/Users/USER/Documents/ChatGPT/lunwen/RESEARCH_PLAN_ROUTE_RL.md:361-368`.

G0/AIR2 and RL admission remain pending under the actual execution freeze, with training and Formal still zero. No scoped nonRL foundation completion changes that boundary. Source: `execution_v1/EXPERIMENT_FREEZE.json:67-69`.

## Reporting guidance used

The review applied `/Users/USER/.codex/skills/nature-statistics/SKILL.md` and its `references/common-failure-modes.md`, `references/statistical-reporting.md`, and `references/reviewer-checklist.md`. The operative guidance is to distinguish measurements, independent units, and claims; preserve paired/nested structure; define multiplicity; report effect sizes and uncertainty; avoid invented preregistration, tests, exclusions, or mechanistic conclusions.
