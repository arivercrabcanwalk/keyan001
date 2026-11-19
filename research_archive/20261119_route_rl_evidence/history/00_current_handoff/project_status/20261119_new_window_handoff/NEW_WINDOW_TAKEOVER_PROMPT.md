# Liu / LRPHSD 多无人机物理路线 RL｜新会话交接

**交接日期：2026-11-19（北京时间）。已核对的最新科学结论：2026-11-14。** 工作区：`<LOCAL_PATH>`。本次只整理本地已有记录，没有连服务器、重跑实验或改变门槛。下文的“已完成”指有结果和收据，不指计划。

## §0　先读这一屏

**研究问题：在不多花钱的前提下，能否让最后一架巡检无人机更早回站？进一步，能否证明额外改善确实来自 RL 学会了选路线，而不是来自重新分配工作、搜索算法或更多计算时间？**

| 新会话首先要知道的事 | 当前结论 |
|---|---|
| 用户选择的方向 | **先做 A：已知固定风、简单能耗、实际飞行路线决策。** 固定风下与强方法公平验证后，再进入天气驱动的动态应急主实验 W。 |
| 已完成 | 三种预定固定风下，24 张新底图、72 个完整同风作者解、2,880 次强非学习对照。执行、性能汇总、独立数值复核和限定范围的 G3 判定均已结束。不要重新启动。 |
| 本批最强基线的平均效果 | 强 ALNS 在 6 秒、12 秒预算下均比作者起始解平均缩短约 **15.73%** 的最终返航时间。**这是非 RL 的条件精修收益。** |
| 尚未证明 | **G0 未过：没有证据证明当前路线学习机制带来增量。** 本轮固定风研究的模型、训练更新、checkpoint、Formal 均为 0。历史上别的合同真做过 RL 训练，结果不支持胜出；二者不要混淆。 |
| 下一个动作 | **回到 G0，而不是再做 G3 汇总。** 先写清一个可被否证的物理路线机制和最小验证方案；明确什么结果属于搜索，什么结果才属于学习。当前不需用户再次批准“开始阅读/设计”。 |

### 阅读顺序与冲突处理

1. 先读工作区的 [AGENTS.md][agents]、[用户要求][req]、[总规划][plan]、[最新状态首条][latest]。这些文件保留了不同时点的旧段落；用**日期、实验合同和具体批次**区分。
2. 当前状态以 [F3 批次 STATE][state]、[G3 最终中文判定][verdict]、[汇总数字][summary]、[独立审计][audit] 为准。[用户批准票据][ticket]说明能做什么，[实际执行冻结][freeze]说明当时登记了什么；它们的旧 `PENDING` 不覆盖终局，终局也不追溯性地改变预登记。
3. 准备下一步时读 [AIR2 原设计及末尾更正][airdesign] → [边界复审][airreview] → [真实工程结果][airrun]，再查 [关闭方向表][closed] 和 [固定风文献对照][survey]。启动命令不是需要再次执行的待办。
4. 想掌握完整来龙去脉，读 [11 月 12 日完整交接][hist] 的 §5–§10，并按其 [历史索引][hidx]、[证据索引][sidx] 回到原文件；11 月 13–14 日的增量见本文。旧交接中的“仅 root 不许子 agent”“先做天气主实验”“G3 待跑”已被后续决定覆盖。若出现更新证据，以**同一合同**下更新的原始收据和用户明确决定为准。

**术语速查：** F3 = 三个固定风条件的这批校准实验；DEV = 开发评测，不是调参集；Formal = 方法、模型、预算和统计方案全部冻结后才开放的全新正式测试；G0–G8 是研究关卡，见 §5。

## §1　场景、动作与评分：一个方案怎样算好

基础是 Liu、Hu、Cheng 的基础设施巡检选址与路径问题（[原文][liu]、[补充材料][liusi]）。原问题联合选择站点、无人机配置和路线，以**建站、配机及运营的总成本**为目标。我们研究其中的条件路线问题，不声称 RL 学会了选址。

1. **先固定大家的起点。** 对每个“地图 × 风”，用保留原强度的风适配作者算法生成完整可行解 `Rw`（作者锚点）。这是完整作者 Main（外层 500、内层名义 5,000、外部超时 1,800 秒），不是限时简化版。固定其启用站、站型、机组和目标所属站。小站可用一架小机，大站可用一大一小；同站内目标给哪架机、访问顺序、何时分趟仍可改变。F3 含 12 个规模族，从 **3 个候选站 / 10 个目标**到 **10 站 / 110 目标**。
2. **策略只选真实动作。** `(slot, target)` 表示哪架机去下一个目标；`(slot, RETURN)` 表示它回所属站并结束本趟。换电恢复本趟电量，**累计工时不清零**。全图目标恰好服务一次、站覆盖半径、机型资格、每趟含返航电量和每机累计工时都要满足。禁止 RL 选邻域、搜索算子、修复强度、算法家族或预算；这不妨碍非 RL 对手使用完整 ALNS。
3. **算每架机的物理时间。** 对每条有方向的航段按恒风及航向补偿算飞行时间，一趟从站出发到回同站；趟时长 = 含返航飞行时间 + 各目标服务时间；趟能耗 = 飞行时间 × 飞行能耗率 + 各目标服务能耗。机组跨趟串行累加。**全队目标 `M_return = max(各机累计工时)`**，不是最后一个目标被访问的时刻，也不是所有机器工时之和。
4. **先验成本，再比时间。** 全图成本 = 固定站/机费用 + 全队累计运营时间 × 单位费用。每个候选必须满足 **`Cw(R) ≤ Cw(Rw) + 1e-7`，epsilon=0**；这里是绝对浮点容差，不是放宽预算。某站可略贵、另一站可节省，但不能跨图平均抵消超支。零风作者解用新风重评分不等于完整同风作者求解。[A 合同][contract]、[模型字段对照][cross]、[冻结物理评分器][scorer]。
5. **再验是否按时交付。** 每法每图的 6/12 秒从启动前到进程真正退出，包含加载、搜索/推理、后处理、评分、输出和回退；早存文件而晚退出仍算晚。共同作者解生成费用单列，不在这 6/12 秒内。本结果不可写成“从零开始、同总墙钟击败原作者 TSALNS”。

## §2　做过哪些方法，结果说明了什么

**三个关键非学习对照：** ① 成本中性整趟重排（B2）：不动趟内路线，只把整趟重新分给有资格的机组，平衡工作量。② 原生强 min-max ALNS（自适应大邻域搜索）：可改变目标分组、趟数和顺序；不是被限制在 RL 候选池里的弱版本。③ 独立共同 H：给各站共同的完工时限 H，各站找低费用方案，再在全图成本上限下组合；F3 用作者完工时间的 1、0.9、0.8 倍三个阈值。**H 是物理完工时限，6/12 秒是算法计算预算，两者不同。** B2 有独立历史实验；本次 F3 四臂是后两种方法各两个预算。

**F3 的比较单位。** 每个规模族 2 张底图，共 24 张。每图有公开恒风 `(0,0)、(240,0)、(0,480) m/min`（无风、向东 4 m/s、向北 8 m/s）；每个地图风单元共享一个合格作者解。两方法 × 两预算 × 各 10 个**求解运行 seed**。2,880/2,880 行按时且合格，四臂各 720 行，缺失、重复、失败和跳过均 0。**独立样本是 24 张底图，不是 72、720 或 2,880，更不是 10 个训练 seed。** [终局收据][receipt]。

| 非学习方法（相对同风作者解） | 6 秒平均降幅 | 12 秒平均降幅 | 地图胜/平/负（6 秒；12 秒） |
|---|---:|---:|---|
| 原生强 ALNS | 15.726630% | 15.727271% | 22/2/0；22/2/0 |
| 独立共同 H | 12.958403% | 14.861506% | 21/3/0；22/2/0 |

每张图内先对三风和 10 个运行 seed 平均 `100 × (1 − M_method/M_author)`，再对 24 图等权平均；没有挑最好 seed。H 减 ALNS 的收益是 **−2.768227、−0.865765 个百分点**，不是百分比。6 秒结果偏向 ALNS；12 秒探索区间跨零，既不能断言有差异，也不能称等效。两个预算的[全局部署基线][deploy]均选原生 ALNS；**未来 RL 仍必须和两种强方法都比**，不能逐图选赢家当作可部署算法。

G3 原判定：`F3_G3_QUALIFICATION_OPPORTUNITY_PASS_LIMITED_DOMAIN_WITH_INFERENCE_PREREG_DEVIATION`。它只证明**三个登记风场下作者和强非 RL 比较已合格，实际可改善幅度和波动已量化**。区间参数是在采集后才确定的（分族地图 bootstrap 50,000 次，seed 2026111419，八个效应做 Bonferroni 校正，每族仅两图），全部是探索性，未算 p 值。不是全项目无条件 G3、17 风泛化、全局最优或剩余 RL 空间的证据。地图现已暴露，基线的选择不是对自身的独立验证。

## §3　历史地图：哪些结果要继承，哪些路不要重走

| 时点 / 分支 | 应带走的结论 |
|---|---|
| 作者复现与旧路线方向 | [V6/SEMFiX 复现包][semfix]已做 120 张官方图 × 5 seed × 2 配置，共 1,200 个配对比较。旧宏控制/算子选择不再是研究对象；[旧 Route-RL Stage A][stagea] 未胜强路线搜索。不要重做复现或 720 任务矩阵，不因改方向自动进入旧 Stage B/C。 |
| 11 月 5 日联合动态 DEV | [旧训练报告][oldrl]确有 SCST、LOO、Double DQN，各 3 个训练 seed。SCST/LOO 的 6 个 seed 都选回初始化；在当时的联合指标 J（越低越好）上，1188.622 对最强登记非 RL 的 1169.612，差约 1.625%。**这是另一个目标与数据集**，既不是固定风阳性，也不是“从来没训练”。 |
| 11 月 12 日无风静态诊断 | 48 张分配图中 47 个作者锚点合格。只重分已有整趟，47 图平均降幅 **11.412%**；36 张预先登记的确认图为 **10.951%**。LPT 在 45/47 图达到整趟重排最优。后续强 ALNS 在 46 张有交付的图上相对重排再降约 **3.041%**；有一张开发大图未交付，不能换成“全体成功”。[原结果][oldstatic]、[后续强对照][oldreport]。这批 48 图不是全新 Formal，也不能与 F3 的 24 图合并归因。 |
| WX 天气／应急旧 pilot | [逐包收据][wxhist]及[关闭表][closed]保留旧 WX-E、WX-C 结果；曾有漏任务导致成本假低、挑最好 seed 导致看似改善。区别“某配方未过”与“路线 RL 永远无效”。WX-H 后置，不因固定风 G3 自动启动。 |
| 11 月 13–14 日 G0 筛查 | 服务噪声候选对最强简单控制 0/4 胜，均匀分块 PGAS 配方 0/3 胜；只关闭相应配方。普通 RETURN、分层解码、潜势奖励、best-of-K 或换一个网络名字不是新算法。[噪声实验][noise]、[分块实验][block]、[文献差异核对][prior]。 |
| F3 交付与原失败 | `execution_v1` 因风向量整数/浮点表示造成身份哈希不匹配而失败；`recovery_v2` 保留失败，只规范输入表示、复用原 24 图与成功 A000 作者解。没有重抽或重跑 A000。后续四臂全部完成；早期“批次运行中”“性能待分析”是历史快照。 |

**论文边界。** 已可用作证据的是“重排能解释多少改善”“强搜索还能改善多少”“怎样在不增加成本、同交付时间下公平比较”。这些支持结构分析和可复核的基准；不等于首创，也不等于 RL 方法论文的核心结论。用户希望做出可投稿的高质量工作，不以保证阳性或达到 CCF-B 替代证据。已有相关问题和算法先例；[固定风调研][survey]、[原论文与 Zhao/Han 逐式对照][papers]可复用，不从零重做查新。

## §4　新会话首轮：只做有区分力的 G0 工作

**当前具体候选 AIR2，不是已经胜出的算法。** 固定已执行的路线前缀，从一个完整可行的余下计划中取至多两条未完成航次，把相关目标重新分组、排序、分给合格机组；把完整候选按它允许的**下一物理动作**分类。学习者若存在，只选下一目标或返航，不选哪两趟、哪个算子或搜索时长。其枚举完整性仅限登记的“两条源趟、至多两条替代趟、固定插入规则”，不是全局精确求解。当前生成器下小机每趟至多 3 个目标、大机至多 4 个；这是特定物理参数下的必要界，不保证候选可行或整图能按时算完。[设计][airdesign]、[更正及边界][airreview]。

**已经知道为什么有更多候选仍不够。** 一张 2 站 / 9 目标的工程例跑通了 13 步完整动作链，但首表和最终完工时间都为 **32.45820945478479**。这验证了接线和可行性，不是科学规模优势。初始候选表记为 B0；从 B0 取到的好路线，即使非常好，收益也属于枚举和组合，不能记到 RL 名下。[工程结果及失败边界][airrun]。

**本轮应产出的不是新训练，而是一页可否证的资格方案：**

1. 只选一个机制，写清输入及公开信息、物理动作、如何生成新分组/次序、一次更新到底改变什么、与最近先例及已关闭方案的具体区别。若与普通策略梯度或现有搜索逐步相同，就承认相同，不虚设一个“标准 RL”重复对照。
2. 冻结一个能区分两种解释的问题：在同信息、同组件、同全图时间内，**不同的物理动作前缀是否会发现 B0 以外、更好且满足成本上限的完整路线？** 记录首次发现来自哪个前缀、候选路线身份、完整评分、搜索与交付耗时。只扩大候选数、只改善首表、或只在给学习者更多时间时有效，均不支持该解释。
3. 先写对照与停止规则（BC 指行为克隆，即用示例监督学习动作）：无学习贪心、用自己前缀收集候选的 independent-COLLECT、共享组件的 BC/标准 RL 及核心消融；原生 ALNS 和共同 H 都保留。跟随 RL 轨迹读取同一批候选的 shadow-COLLECT 只作归因审计，不是独立对手。共享后处理 T 对各组对等、其费用计入预算，原始策略输出和处理后结果分别保存。
4. 预先登记新输入身份、失败/回退处理、资源上限与通过/关闭标准。先看是否存在可归因的增量；达不到就保留负结果，回到针对性设计/查新，不在已暴露 DEV 调参。**此处是下一项建议，未执行，未获新训练或 Formal 票据。**

## §5　何时才能训练、做正式实验、转向应急

- **G0** 负责具体机制和可否证预测；**G1/G2** 已有环境正确性与有限机会证据，只能复用其适用域；**G3** 当前只完成 §2 所述的三风基础。后续同组件比较族和全新 TRAIN/VAL/DEV 的资格仍要逐项落实。G3 不要求先有 RL 胜出，G3 也不代替 G0。
- **G4** 才做真实训练和开发比较：通过机制与适用比较资格、冻结新数据/预算后，每个学习组至少 **3 个从头独立训练 seed**；只在 TRAIN/VAL 选配置与 checkpoint，全部选定模型进 DEV，报告训练充分性和所有失败。若声明 clustered、uniform 均可学习，要区分各自独立重训与直接迁移。**F3 的 10 个运行 seed 不抵训练 seed。** 按注册分母保留启动失败、超时、无效解；计为“回到锚点，改善为零”的统计编码不等于实际按时交付。
- **G5** 冻结方法、模型、预算、统计方案和样本量后做一次全新 Formal；**G6** 做机制消融及独立核验；**G7/G8** 才是论文与完整研究包。旧图、旧 DEV、F3 校准图及派生、工程夹具均不作新 Formal。原 A 的“相对作者平均改善 5%、地图级 95% 区间下界大于 0”不能代替胜强 nonRL；旧成本方向的 0.3% 不移作本次 G3 门槛，后继主比较与阈值须在看新结果前书面冻结。未授权公开或投稿。[后继比较协议][future]。
- **W 是后置的应急实验，不是给 F3 换标签。** 路线策略只读当时已发布的预报。给不同策略同一份不可变的天气轨迹、故障和告警释放；不要让“何时去服务”变成“何时发生故障”。普通巡检和每个应急 job 有独立 ID、释放、截止、完成与未服务分母，物理成本不重复计。已有风暴退出区间和任务账本的**有限工程验证**；目标级故障记录、暴露分母、预报版本和业务响应时窗未完成实证校准。合成例不是现实风险率。W 的准时率/迟到尾部风险及成本约束单列，不能挪用固定风的百分比。[任务账本工程][storm]、[数据缺口][stormdata]。

## §6　到哪里找源码、身份和预算

| 需要什么 | 直接入口 |
|---|---|
| F3 复核链 | [执行冻结][freeze] → [地图清单][maps] / [逐行注册][reg] → [终局收据][receipt] → [地图与 seed 结果目录][results] → [独立数值审计][audit] → [最终判定 JSON][gatejson]。结果目录中的 `ALL_REGISTERED_SEED_ROWS.csv` 保留全部 2,880 行，`ALL_24_MAP_EFFECTS.csv` 是地图效应，另有各风、各族、各单元种子表。源结果摘要 SHA-256：`611a6214fb60393fc808cd8e76c5d7b5676b832f1cfa6a9126edd5c7b0b4ee2d`。 |
| 实际代码（读、复用，不重启原批） | [总 driver][driver]、[完整作者入口][authorcli]、[物理环境][env]与[评分器][scorer]、[原生 ALNS][alns]、[共同 H][commonh]、[共享整趟后处理][publict]、[预算监督器][guard]。原历史校验和材料见[验证记录][verify]。 |
| 运行场所与账 | 只有 **<COMPUTE_HOST>** 可做科学地图/求解/训练/质量评价/统计；root 统一调度远端，本地做文档、源码静查与哈希。F3 远端根：`<EXECUTION_PATH>`；权威账为该根下 `RESOURCE_LEDGER.jsonl`。本地有 [11 月 14 日最后账簿核对][ledger]；当时无活动行，保守扣账 **4.896477 / 48 核时**。这是特定票据，不是之后实验可自由支配的余额；未含训练/Formal。该结论不是 11 月 19 日实时服务器状态。 |
| 原件、暴露与保护 | [终局证据目录][archive]有完整作者、决策、终局与原始输出哈希；当时取回并验过 18,821 份紧凑证据，控制的完整 RAW_RESULT 原件留在 <COMPUTE_HOST>。下批需在原排除并集上**加入 F3 这 24 图**，核原字节及规范几何，不只换 seed 或文件名。旧 40 身份/126 实际比较、24/24 旧校准额度均另账，不挪用。三份历史科学 STATE 的[保护哈希][protected]不可覆盖；新决定写新包。 |
| 协作方式 | 当前允许多 agent，直系及派生子 agent 只用 `model="gpt-6.1-sol"`、`reasoning_effort="xhigh"`、`fork_turns="none"`，显式传参；不降级，不恢复未经核实的旧会话。G4 设计按总规划作独立审查、交换反驳。新会话如需运行，先核是否有并发作业，不从历史 PID、曾经拒连或目录时间戳推断当前状态。旧交接 §0.6 只作既有连接配置索引，不需要在消息里复制凭据。 |

## §7　可直接粘贴到新会话的第一条消息

```text
请接手 Liu/LRPHSD 多无人机物理路线 RL 研究。先完整读取：
<LOCAL_PATH>
按 §0 的顺序核对最新证据，用 §3 和旧交接索引补历史，再从 §4 开始：给出一个能区分“学习发现新路线”与“搜索内核本身获益”的有界 G0 资格方案，写清对照、失败条件及所需资源。固定风 A 先，应急 W 后。不要重跑已完成实验、在暴露 DEV 调参或直接开训练/Formal。科研只在 <COMPUTE_HOST>，root 调度；子 agent 只能 gpt-6.1-sol / xhigh。按“已证实事实、未证实假说、失败或关闭方向、下一项有界工作、是否需要用户决策”简洁汇报，不用再问是否开始。
```

[agents]: ../../AGENTS.md
[req]: ../../USER_RESEARCH_REQUIREMENTS.md
[plan]: ../../RESEARCH_PLAN_ROUTE_RL.md
[latest]: ../../LATEST_STATUS.md
[state]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/STATE.json
[ticket]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/AUTHORIZATION.json
[freeze]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/execution_v1/EXPERIMENT_FREEZE.json
[verdict]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/G3_ADJUDICATION_ZH.md
[gatejson]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/G3_ADJUDICATION.json
[summary]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/results/SUMMARY.json
[results]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/results/
[audit]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/results/INDEPENDENT_AUDIT.json
[deploy]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/results/DEPLOYMENT_BASELINE_FREEZE.json
[hist]: ../20261112_new_window_handoff/NEW_WINDOW_TAKEOVER_PROMPT.md
[hidx]: ../20261112_new_window_handoff/HISTORY_INDEX.json
[sidx]: ../20261112_new_window_handoff/SOURCE_INDEX.json
[liu]: ../../audit/papers/Liu2026.pdf
[liusi]: ../../audit/papers/Liu2026_supplement.pdf
[contract]: ../../joint_weather_emergency/20261113_fixed_wind_A_experiment_survey/S_CONST_APPROVED_CONTRACT.md
[cross]: ../../joint_weather_emergency/20261114_problem_formulation_crosswalk_v1/PAPER_PROBLEM_CROSSWALK.md
[survey]: ../../joint_weather_emergency/20261113_fixed_wind_A_experiment_survey/REPORT_ZH.md
[papers]: ../../joint_weather_emergency/20261112_takeover_completion/PRIOR_ART_EQUATION_AUDIT.md
[prior]: ../../joint_weather_emergency/20261114_prior_art_pressure_test_v1/REPORT_ZH.md
[semfix]: ../../reproduction/reviewer_package_semfix/SEMFiX_FULL_RESULTS.md
[stagea]: ../../stage_a_audit/MODIFIED_FILE.md
[oldrl]: ../../joint_weather_emergency/20261105_deep_revision/REPORT.md
[oldstatic]: ../../joint_weather_emergency/20261112_takeover_completion/G3_REPORT.md
[oldreport]: ../../joint_weather_emergency/20261112_takeover_completion/REPORT_ZH.md
[wxhist]: ../../joint_weather_emergency/20261112_takeover_completion/WX_PILOT_RECEIPTS.md
[closed]: ../../joint_weather_emergency/20261112_takeover_completion/CLOSED_DIRECTIONS.md
[noise]: ../../joint_weather_emergency/20261113_service_noise_g0_v1/REPORT_ZH.md
[block]: ../../joint_weather_emergency/20261113_block_spine_generation_g0_v1/REPORT_ZH.md
[airdesign]: ../../joint_weather_emergency/20261114_solxhigh_research_round_v1/agents/PHYSICAL_RL_DESIGN.md
[airreview]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/agents/AIR2_POST_FIX_REVIEW.md
[airrun]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/engineering/air2_livechain/REPORT_ZH.md
[future]: ../../joint_weather_emergency/20261114_solxhigh_research_round_v1/agents/G3_AND_EXPERIMENT_PROTOCOL.md
[storm]: ../../joint_weather_emergency/20261114_storm_track_job_ledger_v1/REPORT_ZH.md
[stormdata]: ../../joint_weather_emergency/20261114_storm_source_feasibility_v1/REPORT_ZH.md
[maps]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/server_evidence/COMPLETED/20261114T101931Z/execution_v1/POPULATION_MANIFEST.json
[reg]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/server_evidence/COMPLETED/20261114T101931Z/execution_v1/REGISTRATION.json
[receipt]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/server_evidence/COMPLETED/20261114T101931Z/recovery_v2/COMPLETION_RECEIPT_AUDIT.json
[archive]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/server_evidence/COMPLETED/20261114T101931Z/
[verify]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/VERIFICATION.txt
[ledger]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/performance_g3_analysis_v1/FINAL_LEDGER_RECHECK.json
[protected]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/PROTECTED_STATE_HASHES.json
[driver]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/scientific_driver.py
[authorcli]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/full_author_cli.py
[env]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/frozen/global_env.py
[scorer]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/frozen/baselines/wind_scorer.py
[alns]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/frozen/baselines/minmax_alns.py
[commonh]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/common_h_worker.py
[publict]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/public_t.py
[guard]: ../../joint_weather_emergency/20261114_f3_g3_authorized_v1/recovery_v2/MODIFIED_FILE/ticket_guard.py
