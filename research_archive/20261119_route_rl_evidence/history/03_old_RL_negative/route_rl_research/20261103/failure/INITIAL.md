# Route-RL旧失败：独立初判（源码取回前冻结）

日期：2026-11-03。代理：route_failure_audit。范围：G0事实归因及G4设计前置；无训练/质量/评估重跑。

## 核心判断

旧Stage A是真正的下一目标/RETURN路线RL，而非算子选择；其失败是有效负结果。当前本地材料支持“现有实现/训练配置未胜强ALNS”，不支持把某个尚未读到的代码缺陷当作已证因果。先补齐原route_rl源码、checkpoint配置、训练日志与推理计数，然后按冻结问题做有界验证；不恢复旧720任务，不直接扩Stage B/C。

## 已支持的事实

1. 冻结站型、目标所属站及所属无人机；每episode构造一个station-drone pair的多趟路线。跨站/跨机重分配未学习。依据：旧路线设计稿§2–3与执行crosswalk Phase4。
2. 动作是下一目标/RETURN；设计状态包含位置、当前trip资源、累计duty及剩余目标，掩码应检查加目标后的返航能量/duty。设计稿并非实际源码，保留这一证据等级区别。
3. 记录称Greedy、insertion、2-opt、随机masked pointer在96图工程检查全部可行，reward与evaluator运行成本误差最大4.44e-16，6项unit通过。仅据记录，不声称本轮再验。
4. 3个训练seed为11/23/37，每个60updates、8episodes/update、4 PPO epochs；据此每seed为480采样episodes（尚待源码确认episode计数含义），非充分训练的定理。
5. checkpoint选择使用24张验证图；最佳validation目标delta相对Greedy为−0.0283%、−0.3307%、+0.9038%，种子不稳定。负delta意味着成本下降，与最终benefit正号约定不同。
6. 完整720任务比较只使用seed23 checkpoint；3个solver seeds不等于3个训练seed效果。旧验证图同时选checkpoint，统计CI属于探索性证据。
7. RL在6s/12s相对ALNS的地图平均benefit为−0.966725%/−0.955678%，W/L/T均0/21/3；相对Greedy为正，不足通过强比较。
8. source digest和checkpoint digest已在旧审计记录中冻结，缺本地原route模块不会推翻旧可行性/结果验收，但限制新的因果归因。
9. 本地audit/source/snapshot.tar.gz及所有现存目录未发现route_rl模块。本轮已向root请求只读取回服务器原模块和日志；由root唯一连接服务器。

## 已否定的归因捷径

- “只要把RL改成直接路线就会有效”：旧Stage A本来即是直接路线。
- “再做3个seed就是新实验”：旧训练已有3seed，缺的是全部选定seed在独立开发协议下比较。
- “单步mask全部合法就保证可完成剩余路线”：一般不成立；但旧实现是否有该缺陷须源码/轨迹验证。
- “奖励与运行成本对得上，训练目标就完全正确”：还须看gamma、归一化、return、terminal失败惩罚及bootstrap；目前未知。
- “扩大网络/训练update数可证明创新”：这是工程/优化假说，不提供独立机制新颖性。

## G4待验证的具体假说（均非已证事实）

|假说|需读证据|可推翻预测|最低检查|
|---|---|---|---|
|H1：策略状态/表示遗漏剩余目标间几何关系|model.forward及candidate/global特征|若状态已编码足够pairwise关系且同状态等价检查无差，排除“完全遗漏”说法|静态张量依赖及不改实例的特征置换检查；不训练|
|H2：折扣/归一化改变了原路线目标|PPO returns/advantages、env reward/terminal|若对所有有限轨迹reward望远镜和gamma=1原目标一致，则排除目标偏置|手算少数冻结轨迹及奖励差分|
|H3：myopic mask使可行前缀进入剩余不可完成域|env.mask/step/fallback和失败轨迹|若有全剩余可行性证书且无fallback，不支持此归因|少量有界小例，保存完成/无完成证据，不选高收益图|
|H4：训练任务尺度失衡/样本太少|batch采样分布、有效episode长度、梯度/entropy/learning curves|若各规模覆盖稳定且曲线已平台，单纯“多训练必胜”被否定|复算现有日志，无新训练|
|H5：推理吞吐/采样策略导致等预算劣势|evaluate路由、samples/second、实际截止和模型load|若完成相同数量候选仍输且推理占比很低，则吞吐不是主因|现有结果计数；必要时冻结≤30s纯吞吐检查，与质量无关|
|H6：固定Greedy归属把大部分强方法收益锁在域外|route_alns真实域及完整ownership|若route_alns同域仍明显胜，则差距来自域内而非仅归属|对旧见证的ownership结构差分，不调用solver|

## G4设计建议：先测机制，再投入训练

动作接口固定为物理target或RETURN，不引入operator/强度/子问题选择。先用源码与旧日志排除目标错位、终止/失败记账和比较域不一致；它们属于工程正确性而非创新。

新的路线机制须由某个可重复观察的结构缺口驱动，并有最近先例具体增量；在缺口尚未识别前不建议特定网络。特别地，“剩余任务可完成性信息”只有在旧mask确为myopic、存在有意义失败/质量差且简单强completion对照不足时，才值得定义新机制；通用lookahead/rollout本身已有先例，非自动原创。

后续G4同初始化/物理动作域比较：greedy/insertion/2-opt基础项、最强route-only ALNS主项、同mask规则/beam/监督以及适用bandit控制。至少3独立训练seed，预冻结checkpoint和seed聚合规则；完整原目标6s/12s各≥0.3%、地图CI下界>0、全最终解独立可行；训练另报、推理与回退计总墙钟。若有后处理，给全部方法相同后处理且做RL前/后消融。

## 最小下一阶段资源

1. 原route_rl/*.py、训练log/summary、checkpoint轻量config、run_manifest和结果计数只读取回：solver/evaluator=0。
2. 静态源码/日志核对：新训练=0，质量=0。
3. 仅对已确认的一项具体疑点另写冻结诊断：最多6个人工正确性输入、至多24条短轨迹；无旧地图质量筛选。若需要吞吐，单进程≤30s且不保留质量排序。此处为提案，未执行。
4. 有效假说与先例差异通过后再估计三seed训练预算；当前材料不足以合理承诺GPU时长或阳性效果。

## 原始证据入口

- stage_a_audit/MODIFIED_FILE.md（最终优先于早期active状态）
- stage_a_audit/VERIFICATION.txt
- stage_a_audit/audit_results.py
- project_status/20261102/source_docs/ca_rl_completion_v5_route_rl_stageA_20261102__PLAN_CROSSWALK_20261102_EXECUTION_STATUS.md（历史状态，部分待办已过时）
- project_status/20261102/novelty_source_docs/ca_rl_completion_v5_joint_selective_dev_20261101__ROUTE_LEVEL_RL_NEXT_STAGE_DRAFT_20261101.md（设计非代码）
- project_status/20261102/server_identity.json（只列共享底层源码hash，不含route_rl源码hash）

初判状态：完成本地证据判断；实际route源码审计等待root取回，不把这一步计作完整G0通过。
