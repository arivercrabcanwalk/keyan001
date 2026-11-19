# G4待审候选：按目标竞争的物理路线反事实信用

日期：2026-11-03。状态：候选研究设计，不是创新成立、G0通过、训练许可或预注册。

## 候选名称与目标

暂称 route-slot counterfactual credit (RSCC)。station/mode/每站target集合固定；中央策略每一步只输出物理动作 `(drone slot, next target)` 或 `(drone slot, RETURN)`。RSCC不选择搜索算子、算法、邻域、强度、repair预算或模型外solver。

设计动机是假说而非已证实原因：站内共享remaining-target集合让一个target只能归一个slot，LD与SD电池/duty限制又不同；旧Stage-A按机独立episode和全局增量运行时间奖励没有比较“把同一竞争target给另一个slot”的未来路线代价。需要检查这种route-slot credit是否比普通central PPO更能学习target partition与多趟路线。

## 状态、动作、转移与奖励

每个station的central Markov state含：固定station/type及地理target features；remaining target mask；每个合法physical slot的current node、open-trip energy/time、closed-trip duty、capacity、cumulative-duty slack、closed trips摘要。DABS含LD/SD两个slot，SABS含SD。状态不含虚构同步时钟、makespan或共享充电资源。

动作集为全部满足物理资格的 `(d,i)` 与各非空合法trip的 `(d,RETURN)`。选择`(d,i)`只把target i分给d并追加到该d当前trip；动作同时改变物理路线和target ownership。RETURN回固定station，重置trip endpoint/energy/time并累计该机duty；不得清空已累计duty。除固定epsilon下的单趟battery、coverage、exact-once与累计duty外不加新限制。所有最终解由独立evaluator验收。

step reward为独立evaluator operating cost的精确负增量（flight+service，原time_cost系数/归一化冻结）；terminal reward含全部必要返航。站点/站型及全部service总数在station任务内为常数，但主实验仍以完整原objective比较。reward-sum与完整评分逐任务核对。

## 反事实slot信用

普通baseline使用标准PPO centralized critic `Q_φ(s,a)`。RSCC候选用同一state-action critic估计完成代价。对当前target i可合法分配的slots E_i(s)，定义counterfactual baseline：

    b(s,i) = Σ_{d∈E_i(s)} w_d(s,i) Q_φ(s,(d,i))
    A_RSCC(s,(d,i)) = -Q_φ(s,(d,i)) + b(s,i)

`w_d`为冻结策略在可行slot集合上的概率，候选pair依然由唯一central policy选择。RETURN动作继续用标准GAE advantage，或采用明确的同state route continuation credit；选择其一、做公式/单元测试并在看数据前冻结。候选价值以从同一前缀完成到terminal的on-policy完整原objective回报监督/回归，不用DP oracle label。若用common-random-number paired rollouts作Q目标，生成所有counterfactual分支的推理/模拟成本纳入训练与运行总账，并对非RL控制提供同等信息/预算。

该组件目标是降低同一target在异构slot间竞争时的延迟credit噪声。它只是adapted COMA-style counterfactual advantage / centralized actor-critic的候选，不是已证明新算法；station间/slot间可分性还可能使它完全多余。G0是否新颖须核原始COMA、heterogeneous-VRP actor-critic及现行类似方法；单有应用适配不能叫first。

## 最近先例与严格差异测试

1. Li et al., arXiv:2110.02629v2 HCVRP：每一步动作明确为vehicle-node pair，有heterogeneous vehicle decoder/node decoder、full fleet/partial routes context及return补充资源。它直接覆盖RSCC的联合slot-target action grammar。不同仅LRPHSD station coverage、SD/LD flight energy及per-trip battery/cumulative duty；约束差别本身不证明学习机制新颖。
2. PARCO, arXiv:2409.03811v3：multi-agent route construction、agent-node pointers、通信和客户冲突解决。它进一步否定generic多机协同/冲突处理的新颖性。
3. COMA式counterfactual baseline及集中式多agent actor-critic是RSCC advantage公式的直接先例。因此当前算法主张是将通用slot counterfactual应用于固定站异构路线，不认独立算法增量。DPTARL已有dynamic energy pruning及inspection long-horizon RL；Stage-B旧草案已提出slot-target dispatch。

只有找到一个被这些基线均未覆盖、来自LRPHSD原模型且保留物理路线动作的不可约规则，才能重新提交G0。未知全文不作为原创证据。

## 可推翻预测

P1：在同central actor、action mask、训练实例、训练步数、optimizer、总训练计算、模型选择规则和新开发图下，RSCC相对standard PPO改善station joint outcome，并相对强非RL有真实收益；若只相对Greedy或只训练回报提升，失败。

P2：若RSCC有效，收益应集中于一个target对多个slot均可行且estimated residual route cost差异明显的竞争决策；在SD/LD slot价值近似相等、或一slot被mask排除时不应出现系统性收益。事后只解释，主要效应仍用全地图总体和冻结分层。

P3：若station split-DP/min-cost assignment或同预算non-RL heuristic在固定问题上达到相同/更好成本，学习信用没有独立作用；若额外counterfactual计算吞掉推理/预算收益，则RSCC失败。

P4：若RSCC只因使用DP/beam/更多rollouts或非RL post-refinement获益，给其他控制等信息/工具/后处理后差异消失，则不通过。

## G2/G3/G4执行次序与最低对照

- 先root冻结新允许站内分派域的机会诊断。旧24图已暴露，仅报告机会，不称新开发或Formal。对每个station pool求`min_A Q_LD(A)+Q_SD(T\A)`精确/有界reference，SABS用Q_SD；计DP与完整父任务开销，timeout保留incumbent/LB，不能假报exact。
- G3若通过G0，使用新几何/地图seed开发集；同一station/mode/init/evaluator、地图身份、信息、线程/设备及总墙钟。至少对比strong station partition-DP/limited-DP+routes、Li-style heterogeneous slot-target PPO、station ALNS/route-SISR/strong assignment-and-routing heuristic、规则/greedy、同域beam与BC/监督策略。
- G4需至少三个完全独立training seeds；每seed checkpoint由冻结开发规则选择，所有模型都参加同一新开发矩阵。RSCC与standard PPO除counterfactual credit外控制相同。训练成本独立报告；inference/model-load/action evaluation/paired rollout与后处理计进预算。每种控制覆盖同一动作信息与生成域。
- 6s和12s完整原objective主比较均需平均改善≥0.3%、地图bootstrap95%下界>0、正向地图胜负平衡、100%独立可行和overrun合格。每地图先汇总求解seed，不把决策数/trajectory当独立样本；比较族预声明并校正。
- G0仍不通过此文件自动解除；没有新训练启动。
