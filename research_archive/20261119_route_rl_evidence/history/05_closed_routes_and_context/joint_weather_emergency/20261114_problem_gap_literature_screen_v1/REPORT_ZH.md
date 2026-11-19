# 固定风多无人机路线问题空白初筛

日期：2026-11-14  
执行：root；静态本地状态核对与公开文献/代码检索；未运行科学计算。

## 裁决

`G0_NO_GO_AS_DISTINCT_ALGORITHM`。本轮没有发现可支持新物理路线构造或参数更新的新机制。普通的“RL 在风场中选下一物理路线动作”已被多篇风感知 UAV 路由/路径规划工作覆盖；不能把 DQN/PPO、attention、N-step、经验回放或把若干约束放进一个模型本身称为算法突破。

存在一个尚待严格核实的**问题定义组合差异**：固定均匀风、简单线性能耗、多无人机各自多趟闭合路线、全队总 operating-cost 硬 cap、目标为最后返航 makespan。当前源筛查未找到单篇论文同时具备全部这些字段，但这只是“未检出”，不是完整的新颖性证明，也不能替代算法 G0。先前已关闭的规范变换、route reversal、列生成反馈、学习型前缀界等不重开。

## 证据对比

| 来源 | 已覆盖 | 与当前固定风合同的差异 | 对新颖性的影响 |
|---|---|---|---|
| Liu et al., JAIS 2023, AM-E | 风影响、充电站、图上物理下一节点 RL；单无人机配送 | 单机；能耗目标；随机风成本；未建多机全队 cap/minmax return | 排除“风感知路线 actor”本身的新意 |
| FSVRPLW, Drones 2022 | 恒风方向、风与载重影响飞行时间、动态规划 | 单机单趟；非多无人机多趟 | 排除“固定风改变路线代价”本身的新意 |
| Cheng et al., TR-B 2020 | 多无人机多趟、时间窗、能量约束、精确 B&C | 无风；非 RL；能耗模型为载荷/距离非线性 | 多趟与能量约束已是既有问题结构 |
| Corberán et al., C&OR 2025 MM-MT-dLARP | 多趟、min-max makespan、有限续航；精确与 matheuristic | truck-launchpoint/arc-inspection；无风、无本项目全队成本 cap、非 RL | makespan 多趟组合也不是独有 |
| U-Plan, 2026 preprint | 多 UAS、POI 分配、wind/NFZ/energy feasibility、minimize makespan | 非同行评审预印本；OR-Tools；单条 start-end route/每机能量约束，未见重复多趟或全队 sum-cap | “多 UAV + 风 + makespan”不可单独主张新颖 |
| Ding et al., Sensors 2026, NPD3QN | 多 UAV、steady 3D wind、RL、5 seeds 与组件消融 | 26-neighbor 连续航迹/避障；无任务分配、多趟、返航 makespan 或电池/总成本 cap | “多 UAV 在稳态风下用 RL”亦已有直接邻近先例 |

## 来源和搜索边界

详细题录、来源等级、方法字段及 GitHub 检查范围见 [SOURCE_MAP.md](SOURCE_MAP.md)。OpenAlex 备用查询返回 HTTP 429；随后继续核对可访问的期刊原文、机构库全文、预印本与公开 GitHub 页面。此检索是定向初筛，不是 WoS/Scopus/CNKI 的系统综述，也没有声称穷尽所有中文或未索引文献。

## 下一项有界工作

静态核对 LRPHSD 原始问题定义与当前固定风实现，逐项抽取：route/slot 决策变量、每趟闭合与电量恢复、全队 cap 的求和边界、`M_return` 的时钟语义、风对 flight time 与线性能耗的函数。与 U-Plan 和 MM-MT-dLARP 做字段级交叉表。若组合差异经独立数据库检索后仍成立，可作为问题/基准贡献候选提交导师评议；它仍不会自动通过算法 G0。新的算法候选必须指出此前未出现的具体物理路线构造或学习更新，并给出相同新路线、同预算强控制和可证伪质量/费用假设。<COMPUTE_HOST> 当前 host/port 未恢复前，不运行本地科学计算或任何科学批次。

## 状态

没有修改模拟器、策略、人口、预算、保护 STATE 或既有结果；没有训练、作者求解、ALNS 求解、新科学地图、Formal 或子 agent。G0/G3 仍未通过，可信 RL 优势未证实。
