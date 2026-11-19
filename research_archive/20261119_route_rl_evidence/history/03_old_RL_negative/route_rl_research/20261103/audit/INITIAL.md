# 独立反方初判：直接路线RL的目标空间、强对照与G4风险

2026-11-03。作者：route_independent_audit。独立阅读源码、现成记录和一手全文摘录后冻结；冻结前未读取另两位代理初稿。仅只读旧JSON/gzip/源码，没有solver/evaluator/训练/新地图执行。初判不是新性能结果或新颖性全面结论。

## 1. 当前最重要判定

固定站点、站型和目标的station/drone ownership后，本问题按物理无人机严格可分。旧24图的实际180个非空无人机目标组中，目标数中位数6，最大17，177/180组不超过12，179/180组不超过16。该结构意味着新强对照应加入**按无人机精确或有界subset-DP并保留完整解回退的非RL方法**，而非仅胜过旧route-only ALNS便宣称超过最强非RL。

这些大小来自现有Greedy完整解的结构计数，不是求解/性能实验；它们不证明DP在6s内全部完成，也不证明ALNS已最优。固定ownership的真实ALNS剩余gap仍未知，优先用冻结的小规模精确机会诊断回答。训练加量前先查该gap，避免对几乎可直接求解的小组训练一个更慢的序列策略。

## 2. 原模型内的可分性与duty关系（直接推论，不主张原创）

evaluator.py:固定费只依赖station_types；每个target的service不依赖路线或机型；全部无人机使用同一speed和time_cost。对于固定ownership，令F为固定费、S为目标服务时长和、L_d为无人机d所有闭合trips的总长度：

    C = F + time_cost * S + time_cost/speed * sum_d L_d.

每趟能量约束及每机累计duty均只涉及该无人机；无跨机同步、共享充电容量或时间窗。因此分别优化各d的能量可行trip集合，并取最短总长度，可得固定ownership全局最优。累计duty为S_d+L_d/speed≤H_d；已知该ownership有可行初解时，忽略duty求得的最短能量可行L_d不会比初解更长，因而其最优解同样满足duty。这里是在理想一致实数/谓词下的目标结构；实现仍要遵守原epsilon和独立完整解校验。

结论边界：duty在构造中仍能使坏前缀陷入死路，不能从策略状态删除其检查；但它在该固定ownership最终最优问题中不是与总flight相冲突的另一优化目标。纯trip列表顺序也不是新的物理自由度。不得据此宣称全部LRPHSD容易或所有RL无效。

## 3. 源码核查：旧比较是什么、尚缺什么

### 3.1 确实是直接路线决策

env.py的动作是remaining target或RETURN，最后目标后auto-return；不选择ALNS算子。RETURN重置当前trip，但累计duty不清零。旧动作类型与用户当前要求一致，这不是本次才新增的创新。

### 3.2 旧非RL名为ALNS，实际是三类邻域的SA

heuristics.py `_candidate_neighbor`随机选2-opt、within-drone relocate或跨trip swap；`route_alns_solution`用SA接受与全图best。此入口没有标准destroy/repair和自适应权重，不能因名字ALNS就视为已覆盖当前最强路线非RL。它仍然实测胜旧RL，负结果有效保留。新研究须准确命名为旧three-neighborhood route-SA，并加入强插入/多趟split/DP等已存在的非RL结构。

### 3.3 保留完整图rollout的best，未利用无人机间可分性

evaluate.py `run_policy_budget`每次重构所有drone task，只保留全图candidate；各task在不同rollout上的好解未单独存留再组合。heuristics.py同样只保留全图current_cost刷新时的best_routes。可分解问题上保留每机最优再组装可非劣，但这是标准工程改进，必须同等给RL、随机、监督和非RL，而非单独包装成RL收益或创新。

### 3.4 时间核查

旧6s/12s是refinement预算，initializer和model load单独记录。完整新总墙钟对比须计共同初始化和加载约定，不把旧refinement自动称全流程6s/12s。第一rollout强制执行且只有rollout边界预测剩余时间，理论上可能overrun；现成144条RL记录中，6s/12s各72条，search_seconds超过预算1%的记录均为0，故没有实证支持“旧RL因过时而失败”。

只读现成metadata得到：6s rollout min/median/max=46/205/785；12s=91/409/1577。6s route_decisions=6552/8644/9120，12s=13126/17349/18296（min/median/max）。重复全图采样成本已发生；不能声称只做过一次贪心解码。未作新推理或新rollout。

### 3.5 表示与训练只能先判风险

policy.py target_head对每候选独立MLP，RETURN只读global context，critic才读candidate embedding均值。候选间packing结构没有直接进入RETURN head；全局summary有剩余数/均站距/最小站距/均service，但非完整剩余集合关系。它是具体表示限制，可通过对照检验；仅改成attention、池化或GNN属于工程修正，不能自动满足创新G0。

训练60×8=480 station-drone episodes/model，4次PPO epochs；不是480张完整图训练遍历。是否欠训练是待证，不能用小训练量推导加量必胜。旧选中seed23完整评估与其它训练seed的验证结果混淆应避免。

## 4. 最近先例与原创性边界

- DPTARL正式全文（audit/papers/DPTARL.txt，§4，含动作a=0回巢、visit+service+return energy、DSP和A2C/TAA）直接覆盖目标/返航、动态能源mask和策略训练。其28日多频次与LRPHSD不同，不能直接拿其公开数字作本题基线。
- 旧ROUTE_LEVEL_RL_PRIOR_ART_AUDIT及ADDENDUM已记录pointer/attention、RETURN、多rollout、能源feasibility先例。对仅snippet/README的工作，保留其证据等级，不伪称完整算法审计。
- 新机制若只叫residual duty、return-aware attention、per-drone incumbent、增加训练或DP教师，现有证据不足以认定独立方法创新。必须给出比这些标准组件更具体的非直接规则及可推翻预测。
- 本初判不新上网、不新增缺失全文结论。

## 5. 建议的G4强对照与冻结要求

1. 同fixed ownership强非RL：旧route-SA、最优插入+充分2-opt、能量可行多趟split/DP、按机subset-DP（规模/截止预先冻结）及适用标准强route优化。DP是baseline/tool，不是新贡献。
2. 同物理动作/候选信息控制：随机masked策略、greedy/lookahead、beam、BC/监督；若引入RL之外的completion bound、候选池、每机incumbent，全部控制共享并计成本。
3. 每个3独立训练seed的选定checkpoint在新开发图全部评测；训练成本单列，不能选择最幸运模型。RL无后处理与共同后处理分开，全部结果保留。
4. 主筛选沿用完整原目标6s/12s改善≥0.3%、map-level bootstrap95%下界>0、win balance、最终独立可行、受控overrun和冻结比较族。路线费用分母仅副指标。
5. 固定站点、初始归属、源/模型/实例身份、线程/设备、加载冷/热约定、全部采样生成和失败回退均对齐。若其他方法从初解改进而RL从零重建，须明确这是方法差异并给共同完整初解回退，而非隐藏在计时外。
6. 至少有一项对照区分RL长期信用与同等训练/信息的BC，另有RETURN/分趟结构消融。无真跨步学习不能称RL机制验证。

## 6. 可证伪门槛与下一有界建议

- 若冻结的fixed-ownership exact参考证明最强非RL在新开发范围主预算已达参考或剩余gap小于完整目标0.3%，该fixed-scope创新路线不通过机会门槛；不降低分母或挑较弱基线。
- 若增益来自per-drone best组合、候选生成、教师/DP或后处理而RL不胜同工具简单控制，则学习增量失败。
- 若换关系编码后仅训练/旧验证改善、未胜新开发最强对照，则G4失败。
- 下一阶段建议：先有界查每机能量TSP-subset→partition DP的time/gap与规模分布；root冻结协议后才运行，禁止本代理自行求解。现成小组计数可支持成本估计但不是运行时证据。

当前裁决：支持继续G0/G2具体机会与故障诊断；不支持立即大训练或称新机制已成立。最迫切风险是固定ownership把原问题降成许多至多17目标的小子问题，现有强非RL对照尚未针对它充分利用结构。
