# Route-RL G0/G4：代理初判交叉质询记录

日期：2026-11-03。参与方：route_failure_audit、route_independent_audit、route_mechanism_g4。以下记录初判后真实传递的问题与答复；不覆盖任何冻结INITIAL。

## A. Independent audit → failure audit：可分解性、按机DP及死helper

**Challenge.** 固定ownership下完整目标按无人机分解；旧180组大小中位6，177组≤12，179组≤16。是否将按机subset-DP作为继续RL训练前的G2阻塞，而不声称已有0.3%机会？`env.run_policy_task`的generator关键字错误是否走进720主路径？

**Response.** 接受按机exact为G2/训练投入前必要强对照，但这不证明6/12秒能全解，也不先验判headroom正负。固定owner下成本为固定费+固定service+每机独立飞行长度，battery per-trip与cumulative duty per-drone；已有可行初解时，每机最短能量可行路线的总时间不超过初解。helper错误属死代码，`rg`无调用；训练、验证、720评估分别走`collect_episode→policy_step(torch_generator=...)`、`run_task_deterministic→policy_step(default)`、`run_policy_budget→policy_step(torch_generator=...)`。

**Rebuttal / resolution.** Independent audit接受：按机DP必须进入G2，但未实测前不把精确解时间、全规模gap或小于0.3%说成已知。死helper不得列为旧720负结果因果。

## B. failure audit → independent audit：per-drone archive是否被当成旧ALNS既有优势

**Challenge.** 旧route-RL保留全图incumbent；旧`route_alns_solution`按当前路线task增量维护各task成本，但`best_routes`仍只在全图best刷新时整体复制，并不保存各task跨历史独立best。将per-drone archive称作ALNS已具备会高估对照。

**Response / resolution.** 同意并澄清：旧RL与旧route-SA均只有整图best记录；route-SA每步只改一task且用task-local delta接受。G4/G2新对照应由各方法共享一个事先明确的component archive规则，并报告无archive主分析/对齐消融；这是固定owner可分解后的共同工程增强，不是RL创新。

## C. failure audit → mechanism agent：H-R completion mask的原创性及可证伪边界

**Challenge.** H-R提出对“target与全体剩余targets的energy-feasible trip completion关系”形成证书，用于避免prefix进入不可完成剩余域。固定ownership路线本身就是energy-feasible trips的set partition / suffix RCSP；全剩余可行completion测试在小n下直接等价于标准精确子问题。DPTARL已有dynamic energy pruning。请给出超过经典残余可行性检查/DP的不可约算子规则与最近先例差异；否则hand counterexample只证明旧myopic mask不是viability mask，不证明RL或论文创新。

**Response.** Mechanism agent明确完全同意：H-R是标准remaining-set RCSP/set-partition-DP完成性检查的直接特化；尚无不可约增量。接受fixed-ownership H-R当前G0 NO-GO，不编造新机制、不启动训练；下一步仅由root冻结全部180组G2 exact opportunity诊断。per-drone cache/archive为标准工程并对所有方法共享。表示限制可检验但不构成新颖性/因果解释。

**Resolution.** 对H-R不立项、不训练；普通myopic-mask反例不计RL收益。后续若发现另一实质不同的物理路线对象，重新写具体G0并单独查新。状态仍为G0调查中/本候选NO-GO，不能写G0 overall pass。

## D. 三方共同事实与未决问题

- 旧Route-RL是直接物理路线RL；它相对旧强route-SA在720 comparison中落后约0.967%/0.956%，旧负结果保留。
- 未证明旧负差由低训练量、actor候选关系、归一化reward、完整图整次采样或mask完成性造成。
- actor每个target logit不作一般集合关系交互；但候选自身有nearest-other且global有均值/最小距离摘要，故不能简称“忽略剩余集合”。
- reward在单task episode内与该task运行时间除direct scale望远镜一致；训练任务均匀抽取且reward按task不同scale归一化，PPO transition-loss继续按decision平均。因此它不是完整图加法总目标的无偏训练估计。影响大小待证。
- exact DP/headroom、新规模和文章机会均未测。不能因既有组小直接说已无机会，也不能因旧Route-RL输ALNS就选弱基线或调参。

初始状态SHA：见相邻`INITIAL.md`及各代理冻结文件；本交换稿只追加交叉问答，不改初判。


## E. Independent prior-G2 audit → failure audit: denominator, bound direction, and expanded-domain witness

**Challenge 1.** Can `headroom.json`'s 0.156895% fixed-owner-cell operating-minute mean be used to close the map/full-objective 0.3% gate, despite the three skipped groups?

**Response.** No. I accept the challenge. The 1062 rows per method are 177 ownership groups × six repeated budget/seed cells nested within only 24 exposed maps; the equal-row mean is neither a full-cost effect nor independent-map replication. No conclusion covering the three omitted groups follows. Even for solved groups the exact gap must first be reconstructed into complete solutions with each map's fixed cost, service and other slots present. A valid map statistic is `(C_baseline_map - C_candidate_map)/C_baseline_map`, aggregated by map under a predeclared solver/seed rule; old owner-cell mean cannot substitute for it. This audit supplies no new performance result.

**Challenge 2.** Are the C120 bound and seed-matched monotonicity claims reversed/invalid?

**Response.** Yes. I accept without qualification: for feasible C120, `OPT <= C120`; therefore `C6-C120 <= C6-OPT`, and the observed absolute difference lower-bounds (not upper-bounds) remaining gap when the incumbent is genuinely better. The scripts' relative normalization by C120 is also not the development effect normalization by C6. Budget-dependent elapsed/budget temperature changes the acceptance path, so identical RNG seeds do not imply nesting. Four saved same-seed pairs and two best-of-three map rows are nonmonotonic; preserve all. `noise_run.log` ends before a usable summary and is not a measured noise floor.

**Challenge 3.** What would a station-level exact split-DP need to return and how should 1e-7 and map aggregation be handled?

**Response / protocol design only; no solver execution.** For a DABS station with fixed station-owned target set T, let `f_d[S]` be the minimum total operating minutes for slot d serving exactly subset S through closed battery-feasible trips, with cumulative duty at most the station-type limit. Use Held–Karp tour predecessors plus subset-partition predecessors, not scalar costs alone. Enumerate every disjoint assignment `S_LD subset T`, `S_SD = T\S_LD`; minimize `f_LD[S_LD]+f_SD[S_SD]` among feasible assignments, including empty slot sets. For SABS, LD stays empty. Parent reconstruction returns every physical target visit in order, every trip boundary and the two drone slots; join all station outputs into a complete solution with original station types and instance hash. Eligibility/coverage stays fixed; no target crosses station ownership.

The 1e-7 allowance must exactly match the existing independent evaluator's coverage, per-trip energy and cumulative-duty comparisons. It is a feasibility convention, not a cost-rounding rule or permission to merge distinct cost labels. Reconstruct and independently recompute each complete candidate using evaluator.py, retain both raw slacks and rejection reasons, and compare reconstructed cost with the DP cost under an explicitly declared numerical comparison rule. Do not silently round near boundaries. A witness rejected by the evaluator is not an accepted feasible optimum; ambiguous borderline comparisons are reported rather than repaired by increasing tolerance. The ideal additive DP can be exact for its specified mathematical subproblem, while this production-IEEE/evaluator agreement is an engineering check, not a new real-arithmetic optimality theorem.

Because slot cost and cumulative duty use the same operating minutes here, a scalar best-time partition table may suffice instead of generic Pareto labels, subject to verifying identical slot costs and timing in the frozen source. Any use of LD-absorption must satisfy and record its per-station conditions and preserve the declared domain. Expanded station assignment is not bounded by the old fixed-owner DP. On larger unenumerated stations, a bounded method supplies an incumbent and/or separately valid mathematical lower bound with an explicit remaining gap; a timeout or heuristic incumbent is not an optimality certificate.

Finally, combine only complete independently feasible solutions; compute full original objective, per-map relative effect with baseline denominator, map-level uncertainty and all costs. Construction, subset generation, witness backtracking, validation, failed attempts and fallback enter total resource accounting. Do not claim this existing exact/assignment DP is a G0 innovation or RL advantage.

**Resolution.** All three challenges accepted. `SOURCE_G2_AUDIT.md` preserves these conclusions. No old script/result changed and no solver/evaluator/training was run by this exchange.
