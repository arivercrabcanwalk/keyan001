# 本地文献与实现审计：风、临时禁飞区与直接路线 RL

**审计日期：** 2026-11-04
**审计对象：** `return_makespan/g24_weather_nfz`，以及项目内与 UAV 巡检、LRPHSD、DPTARL、风/天气、禁飞、紧急任务、PPO/A2C 直接相关的本地全文、阅读笔记和审计记录。
**方法：** 使用 `find`/`rg` 限定候选，实际阅读本地 PDF 的文本提取、相应原文/笔记和 G24 源码。历史目录中的同内容副本不重复计为独立来源。本文不运行或声称任何新的科学比较；下文的“工程事实”仅来自代码、测试或既有 smoke 记录。

## 1. 结论

1. **G24 的动作边界合规。** `WeatherRouteEnv` 的策略动作只有 `RouteAction(target_id)` 和 `RouteAction()`（RETURN）；PPO/A2C 都只在同一个掩码后的物理动作集采样。没有策略输出搜索算子、邻域、修复预算或算法 ID。
2. **G24 是合适的确定性天气/NFZ 工程前置件，不是 LRPHSD 实验。** 它正确地把风、临时禁飞区、返航、单趟能量、累计 duty 和一个成本 cap 放入一个单站单槽的可回放环境；但它不是 Liu 的多站异构 SD/LD 问题，既不保留原始完整成本定义，也不计算全图多槽 `M_return`。
3. **“风/不确定性”目前只能写成确定性风场。** 当前实现使用已知、空间均匀、分段常量的风及精确时间积分；没有随机场、预测误差、阵风、空间相关、风致功率模型或机会/鲁棒约束。将其称为“weather uncertainty”会超出代码和本地证据。
4. **先研究临时禁飞区，紧急任务另立动态协议。** NFZ 改变既有航段的时空可行性，可在不改变“下一个目标/RETURN”主体动作语义下接入。紧急任务需要释放时间、优先级、截止期、是否可抢占和新的服务指标，改变任务集与比较问题；不能把二者统称为同一类动态约束，更不能从当前 G24 推出紧急调度效果。
5. **PPO 与 A2C 均只是可运行控制，尚无算法选择证据。** DPTARL 给出了 A2C 直接路线的相邻先例，但问题不同。G24 的三 seed 合成 smoke 中每种算法都有一个不完整解、一个劣于 reference 的完整解和一个与 reference 持平解；它不能支持 PPO、A2C、RL 或任一方法优于非 RL。旧 LRPHSD Route-RL PPO Stage A 已在暴露验证图上输给强 route-only ALNS，必须保留为负结果。

## 2. 逐来源审计

| 来源路径 | 可验证主张（文献事实或工程事实） | 对本项目的适配与不适配 |
|---|---|---|
| [`audit/papers/Liu2026.pdf`](<LOCAL_PROJECT>/audit/papers/Liu2026.pdf)；文本 [`Liu2026.txt`](<LOCAL_PROJECT>/audit/papers/Liu2026.txt) | **文献事实。** LRPHSD 同时决定站点位置/类型、目标归属和多趟路线；有 SABS/DABS 与 SD/LD，约束包括覆盖、每趟电量、站点 operating duration、每目标一次服务及返站。文中明确假设固定巡航高度、平静无风，且不考虑禁飞区（文本第 224--230 行）；结论将风和禁飞区列为未来可纳入约束（第 920--925 行）。L--L 配置被解释为适合如 emergency fault inspection 一类时间关键应用（第 807--813 行），但论文没有在线紧急任务到达、优先级、deadline、抢占或重规划模型。 | **适配：** G24 选择风/NFZ 是对作者明示缺口的工程扩展，且多趟、返站、能量/duty 的方向相容。**不适配：** 不能把原论文的“紧急故障巡检”措辞误写为紧急任务模型；不能把单站单槽 G24 当 LRPHSD 端到端替代或作者基线。作者已报告 latest task completion time，故 G24 的时效指标不能被写成新指标。 |
| [`audit/papers/Liu2026_supplement.pdf`](<LOCAL_PROJECT>/audit/papers/Liu2026_supplement.pdf)；文本 [`Liu2026_supplement.txt`](<LOCAL_PROJECT>/audit/papers/Liu2026_supplement.txt) | **文献事实。** 本地 supplement 是 Liu 模型/实验材料的补充，而非天气、NFZ 或在线需求的独立模型；本次读取未发现将 wind/NFZ 或紧急到达纳入其已完成实验的证据。 | **不适配：** 不能以 supplement 没有某一字符串来证明全领域不存在该问题；它只支持“作者这套 LRPHSD 材料未给出该扩展的已验证实现/实验”的保守表述。 |
| [`audit/papers/DPTARL.pdf`](<LOCAL_PROJECT>/audit/papers/DPTARL.pdf)；文本 [`DPTARL.txt`](<LOCAL_PROJECT>/audit/papers/DPTARL.txt) | **文献事实。** DPTARL 面向单固定巢、28 天异频的 PIPUFN；以飞行加服务时间计能耗、处理单趟电池和每日 sorties。其动作中 `a=0` 是返巢，DSP 在解码时按周期和“访问+服务+返巢”能源条件剔除不可行动作，TAA 表征拓扑，训练范式是 **A2C**，不是 PPO。论文与 ALNS、PPO、DQN 比较；摘要所报 16.64% 平均路径缩短与 9.89% flight-efficiency 提升只属于该论文的 PIPUFN 实验。原文只将 wind resistance/acceleration 作为线性放电简化所忽略的气动因素之一；本地全文没有风场、NFZ、紧急到达或不确定性决策模型。 | **适配：** 它是“逐目标/RETURN、可行性 mask、attention、actor-critic”已经存在的直接路线 RL 先例；G24 的物理动作和 mask 因而不是方法新颖性。**不适配：** 周期巡检、固定巢、每日趟数和目标函数与 LRPHSD 的固定外层、严格逐图成本 cap、站内 SD/LD 联合路线及 `M_return` 不同；不得迁移其数字为 LRPHSD 对比结果。 |
| [`related_work/fulltext_comparison_20261102.md`](<LOCAL_PROJECT>/related_work/fulltext_comparison_20261102.md) | **既有阅读审计事实。** 将 DPTARL 限定为“目标/RETURN、能源 mask、attention、A2C”的直接路线先例，且明确不同问题不构成公平数值基线。 | **适配：** 支持把 DPTARL 作为概念/设计边界来源。**不适配：** 不把它的性能表当项目实证，也不将其组件的存在误当作当前 G24 已验证有效。 |
| [`related_work/source_material/ROUTE_LEVEL_RL_PRIOR_ART_AUDIT_20261101.md`](<LOCAL_PROJECT>/related_work/source_material/ROUTE_LEVEL_RL_PRIOR_ART_AUDIT_20261101.md) 和 [`...ADDENDUM_20261101.md`](<LOCAL_PROJECT>/related_work/source_material/ROUTE_LEVEL_RL_PRIOR_ART_AUDIT_ADDENDUM_20261101.md) | **既有阅读审计事实。** pointer/attention、RETURN、可行性 mask 与 PPO/A2C 的组合不是独立新颖性；对仅有摘要/snippet 的文献保留全文未知边界。 | **适配：** G24 应定位为环境/控制实现，不应把网络、mask 或 PPO/A2C 改名为创新机制。**不适配：** 缺全文的邻近来源不能支持“无人做过天气/NFZ RL”之类的排他性主张。 |
| [`route_rl_research/20261103/audit/INITIAL.md`](<LOCAL_PROJECT>/route_rl_research/20261103/audit/INITIAL.md) 与 [`failure/SOURCE_AUDIT.md`](<LOCAL_PROJECT>/route_rl_research/20261103/failure/SOURCE_AUDIT.md) | **项目审计事实。** 旧 Route-RL 有目标/RETURN 与局部物理 mask；其训练按 station-drone task/transition 加权，不等同完整地图目标的无偏估计。DPTARL 已被列为直接先例。现有审计把旧表示、采样和奖励权重仅列为待检验失败解释，不把它们当已证因果。 | **适配：** G24 若以后进入研究协议，训练奖励、单位、checkpoint 选择、完整目标重放和计时必须预先冻结。**不适配：** 不可把当前较简单的 pointer actor 或“补一个风特征”称为对旧失败的已验证修复。 |
| [`stage_a_audit/MODIFIED_FILE.md`](<LOCAL_PROJECT>/stage_a_audit/MODIFIED_FILE.md)；镜像 [`source_snapshot/ROUTE_RL_STAGEA_FINAL_AUDIT_20261102.md`](<LOCAL_PROJECT>/route_rl_research/20261103/source_snapshot/ROUTE_RL_STAGEA_FINAL_AUDIT_20261102.md) | **项目结果事实，非外部文献。** 旧 PPO 直接选择固定所属机的下一目标或 RETURN；3 个训练 seed，720/720 完整解独立重评分。已选 seed 的 24 张暴露验证图上，Route-RL 相对 route-only ALNS 的地图级平均 benefit 为 6 s `-0.966725%`、12 s `-0.955678%`，W/L/T 均为 `0/21/3`。 | **适配：** 说明“直接物理路线 PPO”已被做过且该 Stage A 是保留的负结果。**不适配：** 它没有天气、NFZ 或紧急任务；验证图已暴露且 checkpoint 参与选择，不能外推为 RL 普遍无效，也不是 G24 或新方向的重跑许可。 |
| [`research_round3/.../PPO_FACILITY_SWAP2023.txt`](<LOCAL_PROJECT>/research_round3/20261102/evidence/sources/PPO_FACILITY_SWAP2023.txt) | **文献事实。** 该本地全文是 graph facility location/relocation 的 swap-based RL，策略做设施位置的交换改进，不是 UAV 的逐航段目标/RETURN 构造。 | **不适配：** 它的 swap 改进动作属于当前用户明确排除的非物理路线控制，不得移植为 RL 动作、基线替代或创新来源；最多作为历史上“PPO 可用于组合优化”的非同域背景。 |
| [`research_round2/.../RL_LNS2021.txt`](<LOCAL_PROJECT>/research_round2/20261102/evidence/sources/RL_LNS2021.txt) | **文献事实。** 该本地全文学习 LNS destroy operator，即选择变量子集后由 IP repair。 | **不适配：** 与“RL 只选择无人机物理路线”的要求直接冲突；只能作为旧算子选择路径的反例，不得纳入 G24/PPO/A2C 比较主线。 |
| [`project_status/20261103/metric_replan/evidence/cvar2021_v1.pdf`](<LOCAL_PROJECT>/project_status/20261103/metric_replan/evidence/cvar2021_v1.pdf)；文本 [`cvar2021_v1.txt`](<LOCAL_PROJECT>/project_status/20261103/metric_replan/evidence/cvar2021_v1.txt) | **文献事实。** 该 UAV 能耗风险工作将环境与动力学噪声建成分布，以 Monte Carlo 形成能耗/风险分布并使用 CVaR；它也指出简化解析能耗通常遗漏 crosswind 等效应。 | **适配：** 支持“若研究不确定性，就需显式定义随机源、能耗分布和尾部风险口径”的方法论。**不适配：** 不是 LRPHSD 路线 RL 结果，不能替代 cost cap、可行性验证或提供任何参数。 |
| [`project_status/20261103/metric_replan/evidence/energy2018_cirrelt_report.pdf`](<LOCAL_PROJECT>/project_status/20261103/metric_replan/evidence/energy2018_cirrelt_report.pdf)；文本 [`energy2018_cirrelt_report.txt`](<LOCAL_PROJECT>/project_status/20261103/metric_replan/evidence/energy2018_cirrelt_report.txt) | **文献事实。** 多趟 drone routing 可具有 payload/distance 驱动的非线性能耗；该报告警示线性近似会遗漏能量不可行路线。 | **适配：** 支持把当前 `flight_energy * flight_minutes` 明示为工程简化，并在进入物理研究前另行校准/验证。**不适配：** 不提供风场、NFZ、RL 或 Liu 参数，也不证明当前简化足够准确。 |
| [`return_makespan/agents/metric_endpoint_screen/FINAL_DECISION.md`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/agents/metric_endpoint_screen/FINAL_DECISION.md) | **项目审计事实。** Liu 已使用 total cost 和 latest completion time；平均目标服务完成时间（MTC）至多可作为未来成本受保护 LRPHSD 评估的附加 target-latency 统计，不是新的路线指标类别。 | **适配：** G24 以 `-MTC` 做合成环境的可对账奖励可以作为工程选择。**不适配：** 当前批准主终点仍为全图 `M_return`；不经新的冻结协议，不能把 G24 的 MTC 训练/烟雾结果转写为该主终点结果。 |
| [`g24_weather_nfz/README.md`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/README.md)、[`EXPERIMENT_PROTOCOL.md`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/EXPERIMENT_PROTOCOL.md)、[`REMOTE_EXECUTION_STATUS.md`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/REMOTE_EXECUTION_STATUS.md) | **工程事实。** 该包明确自称区域无关、单站单执行槽、合成工程包；其协议明确无 WAIT、随机风、爬降、充电排队、飞控动力学、地形或通信遮挡，并禁止把 smoke 越过 G3/G4/G5。 | **适配：** 文档和代码范围一致，当前定位恰当。**不适配：** 不得重新命名为真实风场验证、注册质量矩阵、作者比较或 Formal。 |

## 3. G24 源码忠实性审查

### 3.1 已实现且合适的工程语义

| 实现证据 | 已实现的工程事实 | 审计判断 |
|---|---|---|
| [`weather_env.py:75`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:75)、[`weather_env.py:235`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:235)、[`weather_policy.py:8`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_policy.py:8) | Action list 是剩余 target 加 RETURN；policy 对可变候选集打分，mask 后采样。 | **合规。** 是直接物理路线决策，不含算子选择。 |
| [`weather_oracle.py:197`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py:197)--[`weather_oracle.py:256`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py:256) | 分段常量风按航迹方向求可达地速，在 knot 处逐段积分；横风超过空速或前进速度非正时拒绝航段。 | **适合确定性夹具。** 避免了平均化跨 knot 风的明显错误；并不等于真实飞控/风致能耗模型。 |
| [`weather_oracle.py:277`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py:277)--[`weather_oracle.py:341`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py:341) | 在端点与严格凸多边形顶点构成的有限可见图中枚举简单路径；航段内部与 NFZ 活跃半开区间有正长度时间交叠时拒绝。 | **适合协议所限定的一块严格凸、已缓冲 NFZ。** 这不是多/非凸区、连续避障、最小转弯半径或空域程序的通用证明。 |
| [`weather_env.py:148`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:148)--[`weather_env.py:202`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:202)、[`weather_env.py:362`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:362) | mask 在目标动作上检查到达、服务、返站后的能量/duty 与必要成本下界；replay 独立重放 coverage、路线、返航、能量、duty 和 cap。 | **工程上合理。** replay 是必要的独立核验。成本检测是必要下界，终局仍要重放，不能把局部 mask 当全部剩余目标一定完成的证书。 |
| [`rl_algorithms.py:99`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/rl_algorithms.py:99)、[`rl_algorithms.py:165`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/rl_algorithms.py:165) | PPO 的 clipped update 与同步无 clipping A2C 共用同一已掩码动作语义。 | **工程接口合理。** 这只表明两种更新路径存在且使用同一动作域，不表明二者中任一者适合最终研究。 |

### 3.2 不能越过的缺口

1. **任务域缩减。** G24 是一个 station、一个执行槽；Liu 的 LRPHSD 是多站、异构 SD/LD、可并行槽、站点/目标覆盖关系和完整成本。单机累计时间虽在该夹具中可记作 `M_return`，却不是原问题全图最大返航时间。
2. **成本与主目标不一致。** 合成 smoke 的 cap 是 nearest-route reference 的 `1.25` 倍（[`run_experiment.py:131`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/run_experiment.py:131)），不是当前研究的逐图作者锚点 `C <= C_Liu + 1e-7`。每个 target 的 reward 和为 `-MTC`（[`weather_env.py:319`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:319)），不等于获批主目标 `M_return`。
3. **完全已知的确定性日程。** oracle 和 action mask 使用整个 `WindField`/NFZ 日程来判定未来航段，而观察向量只显式放入当前风、下一个 knot 的时间和 NFZ 当前/起止倒计时（[`weather_env.py:235`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_env.py:235)）。在“日内预报完全已知”的确定性试验中可接受；若被称作不确定风，mask 将使用未来真实实现，形成信息口径不一致。
4. **无 WAIT/hold。** oracle 明确不插入等待（[`weather_oracle.py:9`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_oracle.py:9)）。因此临时 NFZ 或逆风后来解除时，环境可能把“等待后可飞”的物理问题呈现为无合法动作。此处不是隐藏 bug，而是协议已声明的模型边界；若引入 WAIT，必须以独立的物理动作契约、mask、replay 和强非 RL 控制重新冻结，不能在 oracle 内暗中等待。
5. **风只改变飞行时间和线性能耗。** `energy = flight_energy * flight_minutes`。没有风速-功率、载荷、姿态、爬降、温度、电池状态或安全余量模型；`900 m/min` 和能量单位也明示为未校准。它不能产生空气动力学可信度结论。
6. **没有紧急任务。** 全部 target 在 `reset` 时已知且静态；没有 release time、service priority、deadline、取消、抢占或在线重规划。临时 NFZ 测试绝不能被转述成 emergency-task 试验。

## 4. 风与不确定性建模建议

以下均为**后续工程/研究设计建议，不是当前已完成实现或实验结论**。

1. **先冻结信息结构。** 为每张地图定义 forecast `F_t` 与真实风/NFZ 情景 `omega`。策略 observation 只可用 `F_t`、已观测风、已发布 NFZ 与已服务任务；独立 replay 才读取 `omega`。若要使用 day-ahead 完全已知日程，则把问题明确标为 deterministic forecast planning，而不是不确定控制。
2. **明确不确定对象与抽样单位。** 至少区分风向/风速 forecast error、空间相关、knot 的时间误差、NFZ 的公告/解除时刻；每个地图的场景族、随机 seed、训练/开发/正式切分和拒绝/失败分母都要冻结。不能把同一地图的多个天气抽样当作独立地图样本。
3. **在数学上选择一个风险口径。** 选择并预注册下列之一：所有冻结情景硬可行；航段/任务级 chance constraint；或相同 cap 下的 CVaR/最坏分位 MTC、`M_return`、能耗。CVaR 本地来源支持尾部风险思路，但不替项目自动选择阈值或分布。
4. **保持物理路线动作不变。** 风险信息可进入 observation、candidate features 和 feasibility/replay；策略仍然只选择 `(slot, target)` 或 `(slot, RETURN)`。若未来另行批准 WAIT/hold，也应被写成显式物理操作，而不是任何搜索算子。
5. **将动力学与能耗校准分层。** 在区域/机型材料可用前，保留“参数化工程夹具”标签。进入实证前，需要单独冻结风速、巡航/地速关系、能耗与安全储备的来源，且对绕行、逆风、横风和返航做独立回放测试。

## 5. 临时禁飞区与紧急任务的选择建议

**推荐先做临时 NFZ 的确定性/预报已知版本；把紧急任务留作独立后续问题。**

理由：Liu 原文明确把 wind/NFZ 列为尚未包含的实用约束，G24 也已有可回放的时变航段 oracle。NFZ 的变量是航段时间、几何可达性和能量/返航余量，能够沿现有直接路线动作接入。它仍不是新颖性证明，且需要与同信息的非 RL 路线方法比较。

紧急任务应在另一个协议中定义为新 target 的 release time、空间位置、服务时长、优先级/加权等待、deadline、取消规则及是否允许已开始 trip 改道。它会改变服务需求与评价目标，而不只是把既有航段变为不可行。若将来同时研究两者，应建立四格情景（静态、仅 NFZ、仅紧急到达、二者）并保持每格相同信息/预算；当前 G24 不具备该比较所需状态、动作、重放器或基线。

## 6. PPO/A2C 适配评估与当前证据

| 问题 | 审计结论 |
|---|---|
| 两种算法能否用在直接路线动作上？ | **可以作为工程控制。** 它们在 G24 共享 action list、mask、actor-critic 和独立 replay 语义；DPTARL 的 A2C 是相邻但不同问题的路线先例。 |
| 能否由本地文献选择 A2C 或 PPO 为最终算法？ | **不能。** DPTARL 的 A2C 结果不在 LRPHSD 域；PPO facility-swap/LNS 文献还属于被排除的动作范式。旧 LRPHSD PPO 负结果也不等于 A2C 必然更好。 |
| G24 smoke 证明了什么？ | **只证明了训练管线能跑。** [`SMOKE_REPORT.md`](<LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz/smoke_20261103/SMOKE_REPORT.md) 的五目标夹具中，PPO 和 A2C 均为：seed 103 未完成；seed 211 完整但 MTC `8.189062`、劣于 reference `7.307852`；seed 307 与 reference 持平。cap 为 `20.680202`，不是 epsilon=0 科学 cap。 |
| 最低的后续比较要求是什么？ | G2/G3 后先冻结新地图、天气/NFZ 信息结构、完整成本锚点、`M_return` 评分、失败处理、训练/模型/采样预算、至少 3 个训练 seed 和 checkpoint 规则。PPO/A2C 必须与随机/规则/贪心/beam、同目标强非 RL 路线法共享物理动作、信息、初始化、验证器和全部生成/加载/推理/回退成本。RL 还必须胜作者锚点与冻结的最强同目标非 RL，才能讨论 RL 独立贡献。 |

## 7. 本次实现复核

在未修改任何 G24 主代码的前提下执行：

```text
cd <LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz
python -m unittest -v test_weather_oracle.py test_weather_pipeline.py test_rl_algorithms.py
```

结果：退出码 `0`，`Ran 20 tests in 1.210s`，`OK`。覆盖风 knot 积分、横风/非正前进拒绝、NFZ 半开边界与绕行、mask/replay、MTC 对账、PPO/A2C masked update 和固定 seed 可复现性。该测试通过只支持上述工程行为；不构成真实风场、紧急任务、LRPHSD 路线质量、PPO/A2C 优越性或投稿级结论。

## 8. 结案边界

本审计不批准新机制、不启动训练、不生成地图、不改变 G0--G8 状态，也不改写旧 Route-RL Stage A 负结果。当前 G24 可保留为隔离的确定性风/NFZ 直接路线工程包；进入注册研究前，必须先完成与当前 `return_makespan/STATE.json` 一致的数据/对照冻结，并将任何不确定性、WAIT 或紧急任务扩展作为新的可检验契约。
