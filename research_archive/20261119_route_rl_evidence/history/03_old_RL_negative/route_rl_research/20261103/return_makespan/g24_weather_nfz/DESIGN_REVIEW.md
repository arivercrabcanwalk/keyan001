# 多站异构槽 LRPHSD 天气扩展设计审查

> **Historical pre-implementation review.** Its then-current-code findings describe the
> single-station package as inspected on 2026-11-04. `weather_full_map.py`,
> `weather_replay.py`, and `test_weather_full_map.py` now address the listed engineering
> P0 implementation gaps; the scope, registration, fairness, and Formal-admission gates
> in this document remain in force.

日期：2026-11-04。审查范围是将现有 G24 单站工程夹具扩展为**固定部署、固定站型、固定 target-station 归属**下的多站、异构 LD/SD 槽直接物理路线环境。本文不修改源码，不生成地图，不启动训练，也不改变 G0--G8 或当前 `return_makespan/STATE.json`。

## 审查结论

选择 **日内预报完全已知的临时禁飞区（temporary NFZ）** 作为唯一新增任务情景；保留确定性时变风作为航段时间/能耗物理。暂不加入紧急任务或巡检周期任务。

这是三个选项中唯一能以现有证据和 G24 工程资产直接、可核查地接入的扩展：Liu 材料把 wind/NFZ 列为未覆盖的实用约束，G24 已有时间依赖航段 oracle 和 NFZ 回放；相反，紧急任务会引入 release、优先级、deadline、取消、重规划和可能的中断服务，巡检周期任务会引入跨日/跨周期任务需求。这两者都改变服务需求及评价问题，不是给现有路线状态补一项特征。

建议的第一个可实现版本严格限制为：**一块调用方已缓冲的严格凸 NFZ、半开活动区间 `[on,off)`、空间均匀且全天已知的分段常向量风、无 WAIT/hold**。它是可重复的参数化仿真扩展，不是实飞/气动或不确定天气结论。多 NFZ、非凸区、空间风场、随机预报误差和 WAIT 都不应在该版本中暗中加入。

该工作须作为一个新的天气扩展协议冻结。它不能把当前静态 LRPHSD 的 `R_Liu` 直接改名为天气锚点，也不能以 G24 smoke 充当 G3/G4 或 Formal 证据。

## 本地证据与适配性

已读取：

- `global_env.py`（SHA-256 `b903f7df...d54f5428`）和 `scorer.py`（`c6e156b2...84409135`）：当前主域固定站/型/目标所属站，动作为 `(slot,target)` 或 `(slot,RETURN)`，最终端点为全图 `M_return`，原成本为固定成本加所有 slot 累计 operating time 的 time cost。
- `g24_weather_nfz/weather_env.py`（`aead6150c...04f1c77`）和 `weather_oracle.py`（`a8d67a6f...98504b01a`）：现有代码只能构造一个 station、一个 aircraft slot 的多趟路线；它对单航段在 wind knot 处积分，并以可见图绕开一块凸 NFZ。
- `LOCAL_LITERATURE_AUDIT.md`（`a1147cbf...d4dc2f90`）：DPTARL 说明 target/RETURN、energy mask、attention 和 A2C 已是邻近直接路线先例，不能作为创新；Liu 材料没有已验证的 wind/NFZ 扩展；CVaR 能耗工作只支持不确定性应明示随机源/风险口径；旧 Route-RL PPO 是保留的负结果，不能据此断言 PPO 或 A2C 更优。

由此得到的模型选择是：G24 的 deterministic forecast NFZ 物理层可以复用，但策略、评分、对照和统计必须回归 LRPHSD 多站异构槽语义。PPO 与 A2C 都只能是同动作域的工程对照，不由文献预先选择胜者。

## 冻结的问题定义

### 固定数据与物理实体

对每个冻结实例 `I`，保存：原 LRPHSD 图、实例/参数 hash、固定 station deployment、station type、target-station 归属、预报 `F`、NFZ 几何与活动时间、共同天气可行锚点及其 hash。每个已开启站 `s` 的可用槽为：

- SABS：仅 `d=SD`；
- DABS：`d=LD` 与 `d=SD`；
- 已关闭站不产生动作。

所有槽在物理日程的 `t=0` 同时开始。一个槽内的多趟串行；不同槽和不同站并行。站点的顺序仅是固定的环境解码顺序，绝不改变物理起飞时钟，也不成为策略动作。

预报为

`F = (W, Z)`，其中 `W=((tau_k,w_k))` 是 `tau_0 <= 0` 起、分段常量且空间均匀的风，`Z=(P,on,off)` 是一块调用方已缓冲的严格凸多边形及其半开活动区间。`F` 在 reset 时完整公开给每个方法；这称为 deterministic forecast planning，而不是不确定在线控制。

### 唯一策略动作

在当前固定解码站 `s`，动作集合仅为

`A(x) = {(s,d,i): d in D_s, i in U_s} union {(s,d,RETURN): d in D_s}`。

实现层可保留 station `s` 为隐式 active station，但记录与导出时必须是 `(slot,target)` 与 `(slot,RETURN)`。`i` 是尚未服务、且其固定归属为 `s` 的目标。动作不包含站点选择、目标跨站移动、NFZ 绕行候选编号、搜索算子、邻域、算法、强度、repair 或预算。对一个合法动作，deterministic oracle 按公开 `F` 选择唯一的 earliest-arrival、distance、vertex-order 词典序路径；该路径求解是所有方法共享的物理航段解码，不是学习动作。

RETURN 只有当前槽有非空 trip 时合法。它关闭该趟并回到该站；它将 trip energy 清零，但保留该槽的累计 duty/日历时钟。任务全服务且所有已开 trip 都 RETURN 后，才是一个完成解。

## 马尔可夫状态、转移与奖励

### 状态

令 `p_sd` 为当前物理位置，`b_sd` 为当趟已用能量，`q_sd` 为当趟飞行加服务时间，`c_sd` 为该槽从 0 起的累计日历时间，`r_sd` 为已闭合 trips，`U_s` 为未服务任务。观测至少包含：

1. 每个 active station 的固定类型、坐标、target pool、其 slots 的 `(p,b,q,c,r)`，以及 active-station index/固定 station order；关闭站明确标记。
2. 每个未服务 target 的坐标、服务能耗、服务时长、固定所属站；已服务 mask。不得重新暴露跨站分配动作。
3. 完整 `F`：所有冻结 wind knots 和 NFZ 顶点/`on`/`off`。使用最大 knot/vertex 数的 padded tensor 连同 padding mask，或等价的确定性 feature table；不能只放“当前风”和“下一 knot”，再让 action mask 读取隐藏未来天气。
4. 成本信息：固定成本、所有槽已经产生的 operating minutes、仍未完成 slots 的最短必要返站下界、`C_ref^F`、`C_ref^F-C_lower(x)`，以及当前全图 `P(x)=max_sd(c_sd)`。
5. 对每个 `(d,i)` 和 `(d,RETURN)` 候选的 oracle 特征：outbound/return earliest-arrival minutes、flight energy、distance、是否 detour、到达与返回的 weather/NFZ failure code、投影后的 battery/duty/cost slack。候选 feature 是观测摘要，不能替换完整 `F` 的公开。

所有值使用冻结单位：坐标 m、oracle 时间 s、环境/成本/`M_return` minutes。对同一 `I,F,x`，观测、可行动作和排序必须 bitwise/replay deterministically identical。

### 转移

对于 target 动作，从 `p_sd` 在物理日历时刻 `c_sd` 计算 `L_out=O(p_sd,i,c_sd;F)`；到达服务后，在 `c_sd+t_out+service_i` 计算 `L_back=O(i,station_s,...;F)`，其中 `O` 是同一个确定性的带风/NFZ最早到达 oracle。

执行 target 时：

`p'_sd=i`, `b'_sd=b_sd+e_out+e_i`, `q'_sd=q_sd+t_out+service_i`, `c'_sd=c_sd+t_out+service_i`, `U'_s=U_s\\{i}`。

执行 RETURN 时，计算 `L_back=O(p_sd,station_s,c_sd;F)`，并令：

`c'_sd=c_sd+t_back`, `r'_sd=r_sd + [current_trip]`, `p'_sd=station_s`, `b'_sd=q'_sd=0`。

这说明“环境中先解码了哪一个站”不等于“该站晚些起飞”：每个 slot 的 oracle 出发时间永远由它自己的 `c_sd` 决定。目标完成时间记录为服务结束时的 `c_sd`；最终 RETURN 是 `M_return` 所需的最后物理事件。

### 目标、成本、M_return 与 MTC

在天气扩展中，以 weather-aware 时间重算原路线 operating term：

`C^F = fixed(station_types) + time_cost * sum_(s,d) c_sd(final)`。

主端点为

`M_return^F = max_(s,d) c_sd(final)`。

这恰好保留原 scorer 的“槽内多趟累计、槽间并行、全图取最大值”语义，只是每段 travel 由天气 oracle 给出。`MTC^F = mean_i(completion_i)` 可以作为预先定义的次级报告指标，不能取代 `M_return^F`，也不能用 G24 的 `-MTC` 训练烟雾结果支持主端点结论。

成功完整轨迹的训练 reward 采用势函数差分

`r_t = P(x_t) - P(x_(t+1))`，`P(x)=max_sd(c_sd)`，`gamma=1`。

其和恰为 `-M_return^F`，且只有在最终独立 replay 的 `feasible && C^F <= C_ref^F+1e-7` 时可被记录为成功。dead-end、超 cap、oracle failure、超时及 fallback 均为显式失败结果，保留其 prefix、耗时和失败码；不得以重采样、隐藏 repair 或静默替代路线把失败改成成功。

### 共同锚点与成本口径

当前主协议要求静态问题使用作者完整解 `R_Liu` 和 `C <= C(R_Liu)+1e-7`。作者 evaluator 没有 weather/NFZ 物理，故不能把一个在天气下失效的 `R_Liu` 直接作为天气可行锚点。

天气扩展开始前必须二选一并预注册：

1. **严格作者续接子域。** 只纳入在 `F` 下独立 weather replay 仍完整可行的 `R_Liu`；cap 是其 weather-replayed `C_Liu^F+1e-7`。所有拒绝的 scenario/map 及原因保留，且结果只外推到这个条件子域。
2. **独立天气扩展域，推荐。** 先用冻结、非学习的 weather-aware `R_ref^F` 构造一个完整可行 witness；其输入为同一固定 deployment/type/target-station 和 `F`，输出仍是目标/RETURN 物理路线。每种方法从同一个 `R_ref^F` 开始并满足 `C^F <= C_ref^F+1e-7`。它支持“天气约束下胜共同 weather-aware 强基线”的条件主张，不能被表述为“直接胜未扩展的 Liu 原算法”。

两种口径不能在同一显著性分母混合。推荐第二种，因为它不会把“原路线刚好避开 NFZ”的筛选偏差伪装成适用性；但它需要在当前静态 D 协议之外单独批准。无论哪一种，固定成本仍进入完整 cap，即使在固定 deployment/type 下对方法间为常数。

## 可行性掩码

候选 `(d,i)` 仅在以下全部为真时为合法：

1. `i in U_s` 且 `i` 在固定站 `s` 的覆盖半径内；槽与 station type 匹配，SABS 不出现 LD。
2. `O(p_sd,i,c_sd;F)` 与 `O(i,station_s,c_sd+t_out+service_i;F)` 均存在。每段以所有 wind knots 精确积分；任一段的横风超过空速、沿轨进度非正或内部与活动 NFZ 有正长度时间重叠，均不可行。
3. `b_sd+e_out+e_i+e_back <= battery_sd + 1e-7`；DABS 的 SD/LD 分别使用原模型的容量。与现有 scorer 一致，DABS 的 SD 使用该 DABS 的 cumulative duty limit，而非另造小站 duty limit。
4. `c_sd+t_out+service_i+t_back <= duty_limit_s + 1e-7`；这是把“访问后仍可返站”提前写入 mask，RETURN 的同类条件也必须检查。
5. 以所有已发生 weather time、所有已开 trip 的必要返站、未服务任务的必要 service 为下界，`C_lower(after action) <= C_ref^F+1e-7`。这只是必要条件，不能作为剩余任务一定可完成的证书。

RETURN 只检验当前非空 trip 的 `O(p_sd,station_s,c_sd;F)`、该趟 battery、累计 duty 和全局必要成本下界。mask 与控制方法都只读取公开 `F`，使用相同 oracle、相同浮点容差、相同 target/RETURN 排序。最终 replay 必须能否定一个通过局部 mask 但走入后续死路的 prefix。

## 风与 NFZ 物理边界

每一段方向 `u`、空速 `v_air`、风 `w` 的 track speed 是

`v_g = w.u + sqrt(v_air^2 - ||w-(w.u)u||^2)`。

在每个 wind knot 重新求值并积分 distance；`|w_cross|>v_air` 或 `v_g<=0` 使该段不可行。能耗在 V1 保持当前明确的工程近似 `energy = flight_energy * flight_minutes`，再加 target energy；它不宣称风速-功率、姿态、载荷、爬降、温度、电池健康或真实安全储备。

NFZ V1 仅允许一块凸多边形。对候选 polyline 的每个 edge，计算它穿过 polygon strict interior 的时间区间；与 `[on,off)` 存在正长度交叠即拒绝。切线、沿边和恰好落在 `off` 的接触按现有半开规则处理。没有 WAIT：当 zone 或风随后解除时，该事实不会创建隐式等待路线；它可能形成 `dead_end`，必须如实记录。

## 独立重放器

新 `weather_full_replay.py` 必须独立于训练 env、mask、policy cache 和候选 feature，输入只为 frozen instance/scenario JSON 与完整 route witness。它必须：

1. 从原始 node/station 参数重新计算 fixed deployment/type、固定 target-station、coverage、exact-once 服务、slot/type 可用性、每趟能量、累计 duty、所有 `c_sd` 和 `C^F`。
2. 对每个 leg 独立重新计算 wind-knot 积分、NFZ intersection、canonical detour、服务结束、最终返航，而不是读取 env 记录的 travel time/polyline/mask。
3. 输出每段 departure/arrival、path、wind intervals、NFZ判定、energy、每目标 completion、每 slot duty、`C^F`、`M_return^F`、`MTC^F`、全部失败码和输入/输出 hashes。
4. 对每个完整候选强制进行 static original-model check（适用的 coverage/type/exact-once 约束）和 weather extension check；两者都通过且 cap 通过才是 admitted result。

为真正独立，replay 不应直接调用环境中用于 mask 的 `plan_route`。可共享不可变 scenario schema 和公开公式，但要实现第二个最小 oracle，或用一个独立的 raster/segment verifier 对主 oracle 输出的每一条 leg 再求证。两套实现对小图 exhaustive routes、风 knot、NFZ 边界和随机合法路线必须相互对账。

## 非 RL、PPO 与 A2C 比较

PPO 和 A2C 使用同一个 pointer backbone、完整 forecast observation、动作列表、mask、reward、训练实例分布和策略解码。它们不是创新机制，也不允许 PPO/A2C 选择算子。两者均按至少三独立训练 seed 报告；不能挑选单个最优 seed。固定 checkpoint rule 后，全部入选模型和所有失败都进入 paired-map 汇总。

PPO/A2C 之外，至少冻结以下同信息基线：

- 随机合法 action、earliest-arrival nearest target、可行最小 projected-`P`、贪心多趟分割；
- fixed-width beam，其宽度、oracle calls 和 timeout 计入 6s/12s；
- 同目标 weather-aware station-joint route non-RL（可以使用预先冻结的 VND/ALNS，但它自己的算子固定在非 RL 方法内部，RL 从不选择它们）；
- 共同 `R_ref^F`/`R_Liu^F` 本身；若使用任何 deterministic repair，则各方法都获得相同 repair 且报告 repair 前/后；
- 适用的小图 exact/DP 仅作为 oracle/正确性参考，不作为在大图上伪装的强对照。

每个方法都从相同 common anchor、instance/scenario、可用信息和验证器出发。每个 6s 与 12s run 均从冷启动计入模型加载、forecast/oracle construction、采样/beam、多次尝试、验证、output assembly、失败与 fallback。训练开销另列完整 ledger，不能移入 per-map solver wall-clock，也不能不报告。

## 训练、验证与统计冻结

1. 在 G4 前单独冻结天气 schema、scenario generator version/hash、允许参数格、attempt cap、拒绝/不可行分母、hardware、依赖版本、所有 seed 和数据 identity。不得用 G24 五目标 smoke 或已暴露历史 24 图做开发/验证。
2. 训练图、checkpoint-validation 图、开发图、最终 Formal 图按**地理 base map**切分。若一个 base map 有多个天气 scenario，则先在该 map 内按冻结规则聚合，再把 base map 作为 bootstrap/CI 的统计单位；不能把同一地图的多个风/NFZ 抽样当独立样本。
3. 训练分布中 wind/NFZ 的范围在训练前固定；只允许在 calibration split 完成一次、记账的选择。PPO/A2C 的网络/学习率/rollout/epoch/entropy 等设置在 comparison 前 lock。每 seed 使用统一的最后 checkpoint，或按冻结 validation aggregate rule 选一个 checkpoint；不根据开发图或 Formal 图选择。
4. 开发阶段仅在已批准的资源边界内运行，并逐图保存 raw policy output、replay output、cost gap、M gap、wall-clock、模型/训练 seed、solver seed、failure code。当前 48 + 24 与 16 CPU-core-hour是静态 A 第一包的上限，不自动授权天气训练；天气 G4 还需独立训练包。
5. 两个质量预算均报告 relative map improvement `(M_baseline-M_method)/M_baseline`。RL 独立贡献要求按当前主计划同时胜 anchor 和冻结的 strongest same-objective non-RL；6s/12s 分开分析，全部 admitted map 的 paired bootstrap 95% CI 下界大于 0，5% 是目标而不是已经取得的结果。
6. 全部方法/训练/样本选择冻结后，重新生成且此前未暴露的 Formal set。天气研究只能据此主张该受限 deterministic forecast NFZ 域的条件效果。

## 当前实现的具体缺口与 bug

以下是代码事实，不等于已经观察到的算法失败：

| 优先级 | 位置 | 问题 | 必要修正/验收 |
|---|---|---|---|
| P0 | `weather_env.py:76-359` | `WeatherRouteEnv` 只有一个 station、一个位置、一个 trip、一个 energy/duty clock；没有 LD/SD slot、并行 clocks、station pool 或 fixed target-station。 | 新建 full-map weather env，不能在该类上用循环伪造并行；calm/inactive-NFZ 时必须与 `scorer.score_solution` 的多站 `M_return`、cost、slot duty 对账。 |
| P0 | `weather_env.py:319-321`, `run_experiment.py:131-143` | 当前 reward 为 `-completion/N`，终局为 MTC；cap 是 synthetic nearest route 的 1.25 倍。二者都不符合批准的 `M_return` 和逐图 `epsilon=0` cap。 | 使用全图 `P` 差分 reward 与 `C_ref^F+1e-7`；MTC 只做次级报告。 |
| P0 | `weather_env.py:120`, `weather_env.py:235-270` | mask/oracle 可读取完整 `WindField` 和完整 NFZ 日程，观测只显式给当前风、下一个 knot、NFZ倒计时。若称天气不确定，这会使用未来真实值；即使是已知预报，策略也没有同等完整输入。 | V1 明示 deterministic full forecast，并向所有方法公开完整 padded schedule；或另建带 forecast/realization 分离的 POMDP 协议。 |
| P0 | `weather_env.py:362-440` | 所谓 replay 自行遍历 trips，但直接调用和 mask 相同的 `weather_oracle.plan_route`。它不能独立发现 oracle 的路径/几何/积分错误。 | 按“独立重放器”章节建立第二实现/验证器；禁止读取 env leg records 或 mask。 |
| P1 | `weather_oracle.py:52-75` | `WindField` 未强制 `knots[0].time_s <= 0`；实例可以通过构造，但 reset 在 `wind.at(0)` 抛出 `departure precedes the first wind knot`。 | 在 schema/构造时拒绝该输入，并添加断言其在 env 初始化前失败。 |
| P1 | `weather_oracle.py:277-341` | 仅一块严格凸 NFZ，端点/顶点可见图，无 WAIT。把它泛化描述为一般动态空域会越界。 | V1 固定该范围；多区/非凸/WAIT 需新 contract、oracle、mask、replay 和 controls。 |
| P1 | `weather_env.py:161-202` | cap mask 只对单 slot 的 current prefix、其 return 和剩余 service 计算必要下界；多槽时若不改写会漏掉其他已开 trips 的返站与其 weather cost。 | 全图下界汇总所有 slot 的 spent time、open-trip returns 和未服务 service；保持“necessary only”标记。 |
| P1 | `weather_env.py:283-330` | env 本身没有 `terminated`/failure transition；它在无 mask 时仍 `done=False`，只由 smoke rollout 额外将 dead end 改为 terminal。通用训练器容易循环或漏记失败。 | 环境需公开 `terminated=done or dead_end`、不可变失败原因和可序列化 prefix；所有 runner 用这一语义。 |
| P1 | `run_experiment.py:76-164` | smoke 只记录五目标单夹具、greedy output 和训练 update；没有 full-map cost anchor、强 non-RL、wall-clock ledger、checkpoint protocol 或失败分母。 | 保留其工程角色；注册 runner 必须另建，输出完整 receipts。 |
| P2 | `weather_env.py:43-73`, `weather_oracle.py:78-121` | 参数是抽象、未校准的线性能耗与单风场物理。 | 继续标为参数化仿真；进入任何物理适用性主张前另冻结 aircraft/weather/energy 来源和安全边界。 |
| P2 | `global_env.py:207-398` | 静态 `FullMapRouteEnv` 已正确表示多槽并行与 `M_return`，但其 `StationRouteEnv` 使用距离/固定 speed，不会调用 weather oracle。 | 以它的 action/cost/makespan contract 为蓝本重建天气 full-map 层；不修改其已验收静态语义。 |

## 必须通过的验收测试

1. **零天气回归：** `w=0` 且 NFZ 永不活动时，随机生成的每个完整多站 witness 与 `scorer.score_solution` 在 original feasibility、fixed/operating/full cost、slot duty、target completion、`M_return` 上绝对误差不超过 `1e-7`。
2. **并行语义：** 至少两个站和一处 DABS 的 LD/SD 同时工作；改变固定解码站顺序、同一 station 的 virtual action interleaving，replay 得到相同每-slot clock 与 `M_return=max(clock)`，而不是错误地串行相加。SD 在 DABS 必须复现原 DABS duty limit。
3. **多趟不变量：** RETURN 必须回站、清零 trip energy、保留 slot duty；target 后未 RETURN 不得完成；每目标恰一次、station assignment/type 不变。
4. **风积分：** target outbound 与 RETURN 分别跨 knot；tail/head/crosswind、横风越空速、非正前进和第一 knot 晚于零都要有独立正/负例。
5. **NFZ：** before/on/after、半开 `off`、tangent、inside、绕行、两个并行 slot 在不同日历时刻穿越同一区域均须验证。任何 leg 的 replay 都不得与活动 interior 有正长度重叠。
6. **mask--replay 对抗：** 小实例枚举所有 target/RETURN prefix。mask 放行的完整 witness 必须经独立 replay 成功或以终局 cap/未来死路明确失败；mask 拒绝的 action 必须由其具体物理/cost predicate 复算支持。不得有 fallback 使失败 prefix 显示为成功。
7. **成本 cap：** 对多槽全图分别构造 `C=C_ref^F+1e-7`、`C_ref^F+1e-7+delta` 与局部加成本但全局可补偿的路线；前者 accepted、后者 rejected、第三类不得被错误的 local cap 剪掉。
8. **信息等价：** 将两个 forecast 设计为当前 wind/NFZ 倒计时相同但未来 knot 不同。deterministic V1 的 observation 必须不同并完整编码 future schedule；每个 method/mask/replay 读同一 `F` hash。
9. **重放独立性：** 人为注入主 oracle 的 distance、NFZ 边界和 wind segment bug，独立 replay 至少在相应 fixture 中拒绝或报出不一致；此测试不能 mock 同一函数而通过。
10. **动作边界：** 日志 schema 中每一条 learned decision 只能是 `(slot,target)` 或 `(slot,RETURN)`；检验不存在 operator/neighborhood/algorithm/budget 字段，NFZ detour 是 oracle 输出而非 policy class。
11. **PPO/A2C 公平性：** 固定 seed 下两训练器输出合法 masked action、可复现 checkpoint/hash；同一 config 仅替换更新规则。三 seed 的全部模型、完整失败/超时、加载和推理时间均写入 ledger。
12. **统计身份：** 测试 data loader 拒绝 train/validation/dev/Formal hash 重叠，且把同一 base map 的多天气 scenario 聚合后才进入 bootstrap 单位。

## 实施顺序与 gate

1. 冻结 V1 scenario schema、`R_Liu^F` 或 `R_ref^F` 口径、map/scenario identity 和 failure denominator。
2. 先实现独立 weather replay 与上述 1--9 的合成测试，再实现 weather-aware full-map env；以静态 zero-weather parity 为交付门。
3. 实现并校验同信息 cheap controls 与 strong weather-aware non-RL；此时才可定义天气域 G2/G3 机会和 quality protocol。
4. 在新机制、训练资源与多 Agent G4 设计分别获批前，不训练 PPO/A2C。获批后，PPO/A2C 都进入至少三 seed、同模型/同动作/同 ledger 的比较，而不是预选其一。
5. 只有 development 结果、强 non-RL、独立 replay、成本 cap 和全冻结 Formal 都满足当前门槛后，才可能形成受限 deterministic-NFZ 条件结论。

现有 G24 的 20 项单元测试与静态 full-map 的 37 项测试只证明各自当前工程契约；它们均不证明该天气多站扩展、RL 优越性、创新性或投稿级适用性。
