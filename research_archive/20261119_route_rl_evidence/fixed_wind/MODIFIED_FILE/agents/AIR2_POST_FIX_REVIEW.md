# AIR2 边界修正后完整链静态审查

日期：2026-11-14。审查身份：physical_rl_design_20261114；GPT-6.1-Sol / xhigh。

**结论：修正后的 dedicated advance 与登记的两趟重闭合域在静态结构上相容；完整链仍待 root 在 EXECUTION_HOST 的新冻结工程包验证。此文件不是 AIR2、G0 或 G3 的执行通过记录。** 本审查只阅读源码、文档和哈希；没有运行组合枚举、数值/物理程序、远端任务、模型或训练，只新建本文件。原六配置失败批保持关闭、repair=0；有限 boundary adapter 的 7/7 结果不替代本次完整链验收。

## 1. 审查对象与证据边界

以下路径均相对 `/Users/USER/Documents/ChatGPT/lunwen/`，行号属于本次读取的冻结源码。

|对象|路径与范围|SHA256|
|---|---|---|
|当前修正 kernel|`joint_weather_emergency/20261114_solxhigh_research_round_v1/boundary_advance/MODIFIED_FILE.py`，18–28、245–375|`791846864403d2caba01bf372b408cc773a816fc8f29f00b634e91e71bdff628`|
|完整费用组合器|`joint_weather_emergency/20261114_solxhigh_research_round_v1/air2_kernel/frozen/schedule_credit.py`，21–122|`0642db80faa95c06e01a563426e3d14e55a89eac6acbc0624e6fb39231d4bdae`|
|原物理环境|`joint_weather_emergency/20261114_solxhigh_research_round_v1/air2_kernel/frozen/global_env.py`，28–215|`af66c8e77c0d9d2e7dc1a9ac7effb80431173f6ff992bac8a182c231fb4be269`|
|原固定风 scorer|`joint_weather_emergency/20261114_solxhigh_research_round_v1/air2_kernel/frozen/baselines/wind_scorer.py`，145–232|`0698b6e0d7aae5f138840dba7f33f2093e4664f2d99c6e6cd1f41a1305ebd153`|

同时参照本轮 `agents/PHYSICAL_RL_DESIGN.md` 的六项规格及其 append-only 边界纠错，以及本授权包 `AUTHORIZATION.json`。当前拟用的两站 6+3 目标、风 `(180,60)` 是新手写工程输入，不是授权科学人口的三个风场，也不计作新地图科学优势。新 48 核时、10 solver seeds 授权不自动授予训练、Formal 或 G0/G3 通过。

## 2. rank、前缀、插入与 RETURN 的静态裁决

1. **rank 绑定正确放在完整原计划趟上。** `remaining`（274–277）包括开放趟的完整 `prefix+suffix`，不把已服务 prefix 从选中目标并集删除。311–316 检查每条源趟 rank、目标不重与并集至多 8；327–328 再检查替代趟 typed rank。两个源趟同 slot 时，至多当前第一趟带开放 prefix；`done` 从不成为源趟。`rank_by_slot=(4,3)` 仅在此前已证明的物理域有效，仍需原 scorer，不能单凭节点数判可行。
2. **原 prefix 逐字固定。** 289 行固定 `(done,prefix)`；334–341 要求选中开放趟的新替代趟在原 slot 以完整 prefix 开头且恰好一条。当前开放趟未选中时，342–345 保留 `base[0]`，替代趟插在它之后。两个 slot 都开放且都选中时，两条互不重目标的 prefix 必须落在各自 slot 的两条不同替代趟；合并或换 owner 不符合这些检查。
3. **插入位置是登记的固定前端块，不是任意插入。** 其他替代趟在当前开放趟之后、未选中整趟之前；空 prefix 的 slot 以新趟为先，未选中趟相对次序不变（340、345、347–349）。枚举 ordering、cut 和 owners 也枚举两条新趟同 slot 的相对顺序。只替换至多两趟，不能声称覆盖早返航后需三趟的所有合法分支。
4. **必须区分“候选当前趟结束”与“原见证本来想返航”。** `next_tokens`（245–254）对候选 `suffix!=empty` 输出首 target，对候选 `prefix!=empty && suffix==empty` 输出 RETURN。尤其 `prefix!=empty, suffix==empty, future!=empty` 的 identity 行必须先 RETURN，不能提升 future 后直接发 target。若重闭合选中当前趟并合法扩展 prefix，其新 suffix 可以非空，此时 next action 可以是 TARGET；原 W 的 RETURN 计划不是已经执行的物理动作。两种情况不可混为一项断言。
5. **RETURN 后才提升 future。** `norm` 只在 prefix 与 suffix 都空时提升 future（18–23）。`advance_next_token` 对 TARGET 直接做 `prefix+(target,), suffix[1:]`，不经 remove/norm（372–374）；因此 singleton 消费后保留空 suffix 的开放趟。RETURN 验证非空 prefix 与空 suffix 后，将该趟放进 done，再 norm（368–370）。静态上已切断旧 singleton+future 合趟路径。
6. **转换只做一次。** bucket 存 pre-action 候选；专用 advance 只移动其执行边界，之后真正 `env.step(a)` 一次。`force(old_W,a)` 若仍用作旧 commit 的锁，只比较允许的 done/prefix；不得用它替换候选 pre→post 转换，更不能在实际 step 后重复消费同一 target。每行须核完整 `routes(pre)==routes(post)`，不只核 target multiset。

这些是源码结构裁决，不是全域证明或动态 replay 结果。源 W 的完整合法性、h/W 一致性、调用方前提和独立有限域完整性仍须验收。

## 3. 调用前提、disabled slot 与原物理 replay

调用方应从实际 `StationRouteEnv.slots` 绑定 `(1,)` 或 `(0,1)`（环境 31–54），并拒绝重复、空的非终局 slots、bool/其他非 int slot。kernel 的 `k in (0,1)` 成员测试本身没有提供这些强类型/唯一性保证。advance 的 slot/target 已使用 `type(...) is int`，但它没有 enabled-slot 参数，仍需调用方物理资格检查。

271–273 只显式拒绝 disabled slot 的 pending prefix/suffix/future，未显式拒绝该 slot 的非空 done。完整原 scorer 在 small station 的 LD 有非空 trip 时拒绝（155–158）；因此有效初始 W 加原 scorer 回调可兜住，但包装器更应入口拒绝 disabled slot 的任何非空 route，不能把“无合格行”解释成有效状态动作全部不可行。score 回调须真正绑定固定部署、target-station、精确覆盖、含回站能耗、累计 duty 和原风，不得用 rank 或自写近似 receipt 替代。

完整 continuation 验收应先在新 `StationRouteEnv` 中按原顺序 replay 已执行 h，再比对 done/prefix、remaining、位置、趟内 energy/elapsed、累计 duty；随后从动作 bucket 选 W_a，advance 一次、step 一次，再完成它的所有后续 TARGET/RETURN。每个 slot 的最后 RETURN 都必须执行；环境 `done` 还要求所有开放趟关闭（92–94）。RETURN 仅重置趟内状态，累计 duty 在 170–178 行增加而不清零。

最终用原 scorer 复核完整路线、cap、M_return、每 slot duty 和恰好一次覆盖。环境逐 step 累加与 scorer 逐 trip 再逐 slot 的浮点结合次序不同，数值一致性应使用执行前冻结容差，不能声称位级相等。只从空环境 replay 完整候选，不证明“保存的非空物理 prefix 可继续”；也不能用 unrestricted 公共 T 重排已执行趟来伪造 prefix certificate。

## 4. row-limit、deadline 与 COMPLETE 的真实语义

- `row_limit` 检查在成功物理 scorer 返回之后（293–297），限制的是 retained valid rows，不限制原始尝试、唯一但无效候选、score 调用数或 `seen` 内存；`seen.add` 在 scorer 之前。`distinct_structural_candidates_scored` 在回调异常或不合法输入下也不应脱离真实收据解释。
- 当前到限抛 `FROZEN_AIR2_ROW_LIMIT`；deadline 由外部 `check` 抛出。函数没有 partial-result 返回分支；352 行的 COMPLETE 只在整个函数正常返回时成立。调用方若捕获异常，只能记未完成/失败、保留此前完整已发布见证与回退，不得把局部 bucket 标 COMPLETE，也不得将缺失动作标为物理不可行。
- 默认 `check=lambda:None` 不提供任何时间界；科学路径必须传全程 deadline。每次 scorer 前有检查，但 scorer 返回后至发布之间仍需再查，防止最后一次外部评分跨过截止而候选被接受。组合、原 scorer、序列化和进程完整退出也算 6s/12s。
- `pairs` 一次物化所有源趟对（307–308），其数量随趟数平方增长；单对至多 8 目标并不保证全站编译符合时限。资源控制须覆盖 worker CPU、memory、wall 和端到端 child exit；不得用按期写出半成品取代完整退出。

## 5. 完整 bank cap 组合与 Context 的最小复用

局部 row 应先按原物理可行性入 bank，不能按“其余站固定 anchor”的 single replacement cap 预筛。动作站可能更贵，而另一站的便宜 row 提供全图融资；最终只接受完整同风原 scorer 下的 `C<=C_Liu+1e-7` 和最小可行 threshold H。

`Context.__init__`（30–57）要求每站 permanent anchor 且 anchor 组合 cap 合格；这与 action-restricted bank 不必相容。原 W 若不兼容动作 a，不能为了满足构造器而塞进 a 的 bank。它只作整个链的独立 fallback。root 提出的最小 threshold view 可调用**未改** `Context.minimum(view,H,removed=None)`：所需字段为 immutable `banks`、`cache`、`work`、`fixed`、`time_cost`；83 行的短路使此调用无需 `station`。不调用 deletion 或 `solve`，后者依赖永久 anchor 并在无解时报 `ANCHOR_LOST_AFTER_DELETION`。

需要同时保留以下包装条件：

1. 绕过构造器也绕过非 anchor 检查：每 row 唯一 id、恰好两项有限非负 duties、`m==max(duties)`、非空全站 banks、有限非负 fixed/time_cost/cap（39–53）。须显式等价校验；empty action bucket 或某 threshold 缺站则返回 `NO_BANK_WITNESS`，原 W fallback 不掺入。
2. **每个 action-restricted bank view 使用独立新 cache。** `minimum` 的 cache key 只有 H（63–79），没有 bank/action 身份。跨动作共享或原地更改 bank 后复用 cache，会返回其他动作的见证。外层若缓存，key 必须包含不可变完整 bank/action 身份。
3. `minimum` 只求 threshold 内最小字面费用，不执行 cap（83–84）。在所有有限 candidate m 上二分并于每次查询后调用原 cap 判据；finite 非负域与不可变 banks 下 allowed 集随 H 扩大。全部 H 无证人时显式返回 no-bank，不触发 anchor 丢失语义。time_cost=0 不除法；非有限和溢出不进入可接受交付。
4. 保留 station 顺序、slot0→slot1 的字面 binary64 累加：`(operating+d0)+d1`（71–72），最后 `fixed+operating*time_cost`。最终 selected 的 action station 必须仍在该 bucket；重新组装完整 solution 并由原 scorer 独立验 cap/M。不能先做站内实数求和或交换 slot/station 次序再冒称原费用相等。

## 6. 最小新反例目录：在 root 冻结的新工程中一次登记

下列是源码分支的最小有限突变建议，不是本 agent 已运行的实验，不授权重开旧六配置批或对暴露输入调参。root 已计划的 empty / singleton-prefix / already-RETURN 三状态不自动覆盖“待 RETURN 且有 future”、双开放 slot、disabled done 和 limit 异常分支。

|类别|最小输入/调用|应见结果与失败信号|
|---|---|---|
|singleton TARGET 接 future|候选 `p=(), suffix=(a,), future=((b,...),)`；消费 a|advance 后 `p=(a,), suffix=(), future` 原样；完整 trip 划分不变，下一 token 为 RETURN。出现 `(a,b,...)` 合趟即失败。|
|非空 p 的 RETURN 边界|候选 `p=(a,), suffix=(), future=((b,...),)`；分别查询 identity 与可合法扩展的 row|identity 必先 RETURN，RETURN 后 future 才提升；选中当前趟并扩展的 row 可以 TARGET。禁止把两者统一写成永远 RETURN 或永远提升。另查已 RETURN 的 h 保持 done 不动。|
|双开放 prefix|两个 slot 分别 p0、p1 非空；一轮只选一个当前趟，另一轮同时选两个|未选 prefix/当前趟完整固定；同时选时各自 owner/prefix 固定，不能把两个 prefix 合并、互换或移动到 future。|
|disabled slot|small station 仅 `(1,)`；分别注入 disabled LD pending 与 LD done|pending 入口拒绝；done 由包装器或原 scorer 拒绝，不能返回可执行 LD bucket。重复/bool enabled-slot 也应被包装器拒绝。|
|row-limit/deadline|冻结很小 row_limit；以及使 `check` 在登记阶段抛出的确定性截止注入|留原异常收据；不发布 COMPLETE/物理 UNSAT，不推进 env；此前已验证完整 fallback 保留。另设 scorer 跨截止返回，发布前检查应拒收。|
|融资/anchor/cache|动作站只有 locally-over-cap row，远站有便宜融资 row；原 W 不兼容动作 a；两个不同动作依次查询同 H|全图融资可接受时保留；不得选回不兼容 W。每动作 fresh cache 防串证人。empty bucket、H 缺站、所有 H 超 cap 均 no-bank，fallback 独立；time_cost=0 与非法 duties/m 单独做接口负控。|

“精确登记域完整性”还应由**独立写法**列举新小输入的期望源趟/分组/顺序/owner/插入位置，并比对完整 route hash 集与每个 bucket；不能用同一 `next_tokens` 或同一 permutations/cut 生成逻辑自证。此检查覆盖的是固定至多两输出趟域，三趟早返分支明确不在本域。

## 7. 收益归因与剩余 G0 六项缺口

设首表完整候选 bank 为 B0，各 action bucket 用同一个 raw 目标返回最优 W_a，且 B0 每条非终局路线至少属于一个 next-action bucket，则 `min_a M_raw(W_a)=F_raw(B0)`。首表即时改进属于 kernel/完整 bank 组合，不属于策略学习。终局空动作情况应单独处理。后续学习主张只能来自所到 `(h,W)` 改变后发现 B0 之外的新完整 grouping/order 及更好的交付，记录首次发现轮次、源 pair、实际编译/查询/评分成本和最终 bank 值；raw 与公共 T 交付目标保持同口径。

旧 1-relocation 是同信息局部支持参照，不能当 RL。shadow-COLLECT 镜像 RL 实际访问表和 bank，只作归因审计且交付必同 bank；independent-COLLECT 使用自己的 prefix、同 kernel/信息/deadline，不免费获得 RL 后来发现的表。相同 kernel、动作 law、网络与普通 PG 就是同一个 AIR2-RL 实现，不另造伪独立“标准 RL”arm，也无需发明新的通用 PG 原语才允许研究具体路线操作。

|G0 项|此刻可指认的内容|仍缺证据/验收|
|---|---|---|
|1 输入输出与物理动作|`(I,h,W,B)`、pre-action row、`(slot,target/RETURN)` 与 dedicated advance 已具体化|新完整链实际 h/W 身份、禁用 slot、全过程原物理合法性；不能仅凭 boundary adapter 通过。|
|2 精确步骤与一次更新|固定 AIR2 表→bucket→full cap→一步→新 W；更新为普通联合 score PG|独立有限登记域完整性、完整 scorer/replay/融资/cache/截止验收；尚无真实 actor/训练更新证据。|
|3 最近主源与逐步差分|新增定位限于两趟重闭合的固定动作索引及其路线迭代组合|一般 exact-LNS/rollout 已有先例，代码可实现性不证明创新；源码/主源比较仍应限定实际差分。|
|4 可证伪预测|新 row、前缀边界、完整 bank 融资和 B0 外后续发现均可记录|新冻结工程结果及反例收据；有限工程成功不外推科学质量。|
|5 强控制与收益归因|1-relocation、同 kernel greedy/independent-COLLECT、BC/标准 RL 的公平信息边界已明示|没有同预算科学质量、学习增量、多 seed 或消融证据；不把 kernel 枚举改进报为 RL。|
|6 停止/资源/失败保留|旧失败关闭；新工程一次冻结；48 核时/10 solver seeds 独立授权|完整新包实际资源账本、deadline/完整退出和 G0/G3 gate 结果；训练/Formal 不在当前授权内。|

本审查建议 root 完成一个新冻结完整链的有限工程验收并保留全部失败；不要求扩大旧批、增加通用 PG 发明或把验收结果预记为 G0/G3 通过。
