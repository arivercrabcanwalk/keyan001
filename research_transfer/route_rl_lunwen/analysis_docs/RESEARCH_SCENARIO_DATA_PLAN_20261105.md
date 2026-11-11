# 2026-11-05 最新联合研究覆盖
联合天气＋紧急任务模型已在独立工作包实现并完成<EXPERIMENT_SERVER>有界开发；下方“Not implemented/Engineering only”为历史设计时点。当前结果/全部边界见joint_weather_emergency/20261105/REPORT.md。三seed192更新、672评价完成；RL对本轮DEV-best beam主J高4.6773%，未取得性能通过，Formal未开；旧天气/NFZ双cap和资源不改。不得将新动态J与旧指标合并或称论文就绪。

# 2026-11-05 当前实施覆盖
仅root、<EXPERIMENT_SERVER>；旧Windows原生复跑不再列为用户当前交付依赖，历史平台来源仍保留。40新图/40作者/126实际比较，校准验证24/24满，科学预约7.5/16核小时。应急桥接23、全事件轨迹23、REINFORCE微分17和capture-only三算法集成属于工程，无新训练/质量/Formal。应急无NFZ，联合模型仍未实施。5%目标与旧0.3%是不同历史版本，后者不覆盖当前A目标；不得看新结果改门槛。原版快照已保存engineering_execution_closure_20261105/ORIGINALS/。

# Weather and Emergency Scenario/Data Plan

Date: 2026-11-05 (Asia/Shanghai)
Purpose: define the evidence needed to finish the weather/NFZ and emergency
studies without pooling their current, non-integrated simulators. This is a
versioned design record, not an experiment registration or execution receipt.

## Claim tracks

| Track | Current model/action | Primary question | Current status |
|---|---|---|---|
| Weather route study | Fixed deployment, station type, target-station ownership; physical `(slot,target)` / `(slot,RETURN)` | Under per-map original and weather cost caps, can a route policy reduce full-map `M_return` at 6s and 12s? | G0 no-go for a novel mechanism; G3 comparator not calibrated; G4 no complete candidate |
| Emergency event study | Fixed station owner; `TARGET`, `RETURN`, `WAIT` at event frontiers | Does an online policy improve emergency on-time completion while retaining routine service, return, and duty outcomes? | Engineering smoke only; no RL candidate or powered confirmation |
| Joint weather/emergency study | Not implemented | Can the same route decision process handle released emergency tasks under wind/NFZ? | Not registered; requires a new shared schema, replay, objective, and action contract |

Do not combine sample sizes, effect estimates, or pass/fail decisions across these
tracks. The emergency `WAIT` action does not belong to the frozen weather route
action contract. For a future joint study, prefer environment-driven event-time
advancement so the policy still chooses only physical `TARGET/RETURN`; if policy
selected waiting is essential, register a new action domain and matched controls.

## Weather/NFZ map-level design

Use a paired within-map scenario factorial for every newly registered map:

| Factor | Levels |
|---|---|
| Wind regime | calm, mild, adverse; direction and temporal knots vary by scenario seed |
| NFZ | off, on; NFZ-on is stratified as binding and nonbinding using a frozen geometric rule |
| Forecast | exact declared forecast for the initial synthetic benchmark; forecast-error scenarios are a separately registered sensitivity family |

NFZ geometry and activation windows must be generated from frozen map-scale rules,
not copied as one global square. Before any quality outcome is inspected, report
anchor segment intersections, detour rate/length, wind-induced travel-time and
energy change, crosswind infeasibility, anchor weather-battery eligibility, and
complete feasible delivery. Define whether target service/occupancy inside an
NFZ is prohibited or whether only positive-length flight-path overlap is checked.

The primary comparison must use a shared complete feasible author anchor, the
same instance information and independent replay, both per-map cost caps, and
matched 6s/12s external clocks. Calibrate and select the strongest same-objective
non-RL baseline only on disjoint DEV identities. Compare the author anchor,
strict and annealed controls, direct-sampled route annealing, and a bounded beam
or insertion control. Keep anchor-warm-start route improvement separate from
blank-state route construction; do not pool these different estimands.

As reconciled on 2026-11-05, 40 unique research identities have been exposed:
16 opportunity/development and 24 calibration/validation; the latter quota is
24/24 exhausted. Forty author attempts against a separate cap of 48 leave eight
author attempts, not permission to relabel opportunity maps as extra calibration.
Scientific non-RL reservation is 7.5/16 core-hours with no failed-run refund.
The remaining author/resource headroom does not admit another validation rescue.
Any new calibration/confirmation population requires explicit resource revision,
fresh identities and exclusions, and a non-rescue hypothesis before outcomes.
Formal remains unopened and requires a separately frozen power/resource plan.

## Emergency map/scenario design

Treat the mother map/scenario, not seed rows or policy rows, as the independent
unit. Expand beyond the current single emergency task and four repeated
coordinates with a frozen design spanning:

| Dimension | Minimum strata to register |
|---|---|
| Emergency count | 1, 2, and multiple simultaneous/near-simultaneous releases; zero-emergency fixtures are boundary checks only |
| Release and slack | early/late release crossed with generous/tight/near-infeasible slack |
| Wind/forecast | calm, adverse headwind, crosswind; temporally changing wind and predeclared forecast error |
| Routine workload | low/high workload and spatially clustered/dispersed targets |
| Fleet/stations | current single-station/two-drone regression plus separately registered heterogeneous and multi-station strata |
| Horizon/failure | horizon truncation, return feasibility, service energy, duty, missed deadline, and explicit terminal-failure cases |

Routine outcomes and emergency outcomes remain separate endpoints. For the
emergency primary endpoint, use the fixed emergency-task denominator and report
on-time, delivered, returned, lateness, undelivered, invalid action, terminal
failure, duty violation, and complete return for every allocated scenario. A
clairvoyant full-trace policy is an information upper bound only.

The existing emergency action mask means "currently dispatchable", not
"complete-route feasible". The strongest non-RL comparison must therefore use
the same dispatch action domain and independent final evaluator. Before training,
freeze a non-RL rolling-horizon/insertion or bounded beam route planner, the three
rule controls, common scenario inputs, training wall budget, inference clock,
and all failure handling. If an explicit RL `WAIT` action is retained, every
control must receive it and the active-duty versus standby-cost definition must
match the versioned simulator contract.

## Shared experimental and data ledger

For both tracks, store one immutable row per allocated map/scenario/method/seed/
budget. Preserve the proposal ordinal, role (TRAIN/DEV/CONFIRM), geometry hash,
scenario hash, source/build hash, anchor source/hash, weather/trace or NFZ hash,
action-domain hash, method/checkpoint hash, RNG seed, start/end time, CPU/thread
budget, cold-start cost, route-generation cost, replay cost, delivery/fallback
status, complete solution hash, independent-evaluator result, and every failure.

For weather, additionally log per-state/per-candidate physical action and
independent rejection flags for owner/geometry, wind/NFZ outbound and inbound
route, energy, duty, original-cost lower bound, weather-cost lower bound, and
complete-suffix witness status. This is prospective diagnosis only; P3 logs and
results remain unchanged and P3 stays closed.

For emergency, additionally log release frontier, visible/unreleased task IDs,
reservation owner, event queue frontier, per-task release/deadline/completion,
and the difference between global elapsed time and active flight/service duty.
Never drop invalid, late, interrupted, infeasible, over-budget, or missing rows.

## Statistical gates and method attribution

Use map-level paired inference. Weather cells, emergency seeds, method-budget
rows, episodes, and PPO seeds are nested repeated measures, not independent map
counts. Derive sample size from disjoint DEV map-level variance, a predeclared
minimum practical effect, expected anchor/policy attrition, alpha, and target
power; the current weather target is 5% at each budget with map-level 95% CI lower
bound above zero. Resolve the stale 0.3% text in the old plan with a versioned
amendment before observing new outcomes. Pre-register the six weather co-primary
contrasts (three comparators by two budgets) and Holm or an all-contrasts
intersection-union rule. For emergency, set its minimum meaningful change and
primary comparison family before power calculation; the present rule-smoke
differences do not set that threshold.

If RL enters a fresh study, require at least three independent training seeds
and a frozen checkpoint rule. Compare PPO against frozen BC, wall-clock-matched
continued BC, the calibration-selected strongest same-objective non-RL, and the
author anchor. RL utility requires beating the author and strongest non-RL under
both budgets and all caps; a positive benchmark alone does not establish G0
novelty. Do not select seeds, metrics, baselines, or subgroups on confirmation
outcomes. CCF-B-or-higher readiness is an evidence audit, not a fixed row count.

## Current open gates

1. Reconcile the weather 5% target with the stale 0.3% plan text and freeze the
   exact mean operator before further quality outcomes.
2. Freeze fresh train/DEV/confirmation map populations and exclusion manifests;
   perform cluster-aware power analysis before allocating Formal identities; no new allocation here.
3. Wire and hash-register the route-annealing adapter in the weather runner, then
   test matched anchor-start and blank-construction tracks on synthetic fixtures.
4. Diagnose future route failures with action-level rejection ledgers on fresh
   identities; do not replay or reopen P3.
5. Reconcile emergency release hashes and 50-test receipt; obtain a native
   Windows run is no longer an active user requirement after the <EXPERIMENT_SERVER> revision.
   Historical receipts remain unchanged and do not establish native-Windows behavior.
6. Keep joint weather/emergency work closed until one schema, oracle/replay,
   cost model, event contract, mask semantics, baselines, and total budget are
   frozen and independently reviewed.
