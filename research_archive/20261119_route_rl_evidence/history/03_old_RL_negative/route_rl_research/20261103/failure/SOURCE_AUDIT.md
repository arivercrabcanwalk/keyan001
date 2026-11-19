# Route-RL Stage A：冻结初判后的源码审计补充

日期：2026-11-03。作者：route_failure_audit。只读核查root从服务器取回的Stage A snapshot；未重跑训练、solver/evaluator或720结果。根证据：`source_snapshot/`共1605文件；root报告逐文件与服务器SHA匹配。

## 结论

旧Stage A确实是直接选路线的RL，但它只在贪心初解给定的每架无人机任务集合内逐步选下一目标/RETURN。已有720任务负结果成立：它优于Greedy、落后已实现route-only方法。现在可以确定旧实现存在若干代理目标/搜索策略限制；现有日志仍不足以把约0.96%落后因果归到任何一条限制。尤其固定ownership问题严格可分且目标组很小，所以按机精确解必须先成为G2机会参照，再决定是否投入新的RL训练。

## 源码事实、含义与因果边界

|源文件/位置|可直接确认的事实|可支持的结论|不能据此声称|
|---|---|---|---|
|`route_rl/env.py:44-61, 285-291`|固定站型及target owner；每episode是一个station-drone任务组；assemble只替换routes|旧Stage A没有学站点/owner，但确实构造物理路线|动作类型本身是新创新|
|`route_rl/env.py:94-164`|合法target须当步追加后可立即闭合当前trip且满足电量/累计duty；RETURN须当前trip非空且返航可行；没有检查全部剩余目标是否存在完整partition|mask是局部物理可行mask，不是全剩余集合可完成性证书|该缺口造成旧720失败；训练、验证路径未记录死路，720输出全可行|
|`route_rl/env.py:109-110, 166-185`|候选特征有nearest_other；global含剩余数量、平均/最小站距、平均服务时长|actor输入并非完全忽略其他目标的全部信息|“完全没有集合上下文”|
|`route_rl/policy.py:55-75`|target logit对每候选独立由candidate特征+global计算；RETURN logit只由global计算；候选mean embedding只进critic|actor没有一般候选两两关系的显式交互；RETURN不读取剩余候选embedding pool|这已证明表示是负结果原因；attention/GNN自然是创新|
|`route_rl/train.py:62-94, 97-109, 239-242`|每episode从541个map-drone task中均匀随机抽一个；γ=1、λ=.95；每任务reward为负运行分钟/其direct成本尺度|不存在γ折扣造成末端目标折损；样本单位不是完整地图；采样按task而非按map均匀|reward准确等于完整地图目标的训练估计|
|`route_rl/train.py:37-40, 120-168`|PPO minibatch在transition层打平；actor/value/entropy loss按决策transition均值计算；每update8个episode、4 epochs|minibatch目标对更长任务/较多决策有更多state更新权重|这种transition权重造成了质量差的因果结论|
|`route_rl/evaluate.py:37-84, 182-184`|每个rollout重建该图所有固定owner route；只按全图完整解cost更新incumbent；同一policy内跨rollout不保留各drone独立best|可分离问题未采用component archive；完整地图每次重采样所有路线有额外推理开销|旧比较计算错误；加archive后必然胜ALNS|
|`route_rl/evaluate.py:37-84`|每行包含6/12秒内rollout和route decisions；模型在run manifest单独load|6/12秒定义是refinement时间；完整end-to-end应统一初始化、模型载入冷/热计时|旧metadata显示RL超时是事实|
|`route_rl/env.py:294-302`|非主路径helper用`generator=`调用`policy_step`，但其参数名为`torch_generator`; `rg`未发现该helper在训练/评估路径调用|存在未调用helper的接口错误|该dead code解释720结果|

### 奖励代理的精确边界

env对每task设置 `reward_scale=max(2*sum(d_station,target)/speed + sum(service),1)`；`gamma=1`使单个episode的负reward和等于该task路线运行时间除以reward_scale的负值，reward对task operating time有望远镜一致性。这解释了为何已记录“单task reward reconciliation误差4.44e-16”可以为真。

但完整图目标的变化是所有task时间改变量之和乘time_cost；PPO采样的期望是按541个task均匀抽样后再以各自reward_scale归一化。transition级loss还按每个decision加权。这不是完整图总成本变化的无偏估计，亦非旧结果统计出错；它是G4里应预先对齐或专门消融的**已确认目标权重差异**。其是否造成旧RL落后未被单独测量。

## 完整目标按固定owner严格可分

由回传`lrphsd/evaluator.py:15-48`：令固定项为F，固定目标服务时间总和为S，每个无人机d的所有闭合路线飞行总长度为L_d，则

`C = F + time_cost * (S + sum_d L_d / speed)`.

覆盖/站点适格已在冻结owner内；每趟energy只涉及该无人机该trip；累计duty只涉及该机的service+flight总时间；无跨机同步/共享容量。因此固定owner时可独立求每机的最短能量可行多趟路线。若初始完整解已可行，则该机最短能量可行解的L_d不超过原解，固定S下duty不会更差。数学目标分解成立。

旧24图有180个非空owner组，中位6目标，177组≤12，179组≤16，最大17（见独立审计初判）。这使按机subset/partition DP成为必要的强G2参照；这些计数不证明DP在6/12秒全解，也不证明收益机会低于0.3%。必须对全部冻结组报告完成/超时/gap与成本，不能按方便程度筛组。

## 旧训练/推理量与实际测量

- 541个训练task；每seed480 episode。现有history统计：seed11/23/37 transitions分别3854/3964/4020，总CPU训练时间58.51/61.12/63.11秒。480比541少61次draw，但task身份未落日志；不得把按相同RNG流程重构的覆盖统计写成原生实测日志。
- 完整720地图级比较只有seed23 checkpoint。旧selected validation delta与强ALNS差距是有效负结果；它不估计3 checkpoint聚合策略的效果。
- 144个RL结果行：平均每图rollouts为6秒245、12秒503，最小46/91、最大785/1577；没有记录`search_seconds > budget*1.01`。这反驳“旧结果因已观测超时造成”的说法。
- model load平均manifest值约0.0123秒且计在独立字段、不计run_one预算；很小但公平的新协议仍应明确加载口径。
- RL完全地图rollout的counts与route-SA局部邻域iterations量纲不同；不能直接把245 rollouts与513k iterations解释为谁更快。

## 交叉审计结果与最终分歧

1. 对`audit/INITIAL.md`（反方）提出的可分性挑战：接受。按机exact/DP是G2与大规模训练投资前强对照，不预先宣称有0.3% headroom；不跑求解是当前子任务边界。
2. 对`mechanism/INITIAL.md`中的completion-aware H-R提出挑战：固定owner下这是标准remaining-set feasible-trip/partition DP（或suffix RCSP）完成性核查的直接特化；普通myopic-mask反例只证安全性缺口，不证RL必要性。机制代理答复接受“当前G0 NO-GO as written”，没有提出可辩护的不可约算法增量。三方一致不立项、不训练H-R。
3. 对每机incumbent：标准独立分解工程。RL与所有非RL对照可共享component archive和同一独立全解验证，不写为RL创新。
4. 对旧Route-RL输强基线的因果归因：仍未确定。已确认的task reward权重、actor关系结构、随机采样和整图best策略是可检验候选，而非已证原因；旧可行性结果说明完备mask不是已观察到的主要失败故障。
5. `run_policy_task` generator关键字错仅在未调用helper；训练实际走`collect_episode→policy_step(torch_generator=...)`，validation走`run_task_deterministic→policy_step(default)`，720 evaluation走`evaluate.run_policy_budget→policy_step(torch_generator=...)`。不是旧失败原因。

## 退出条件与建议

当前不能将固定owner路线G0判为新算法通过。建议root继续有限G2：先对全部180个已暴露owner组做按机exact/partition DP机会诊断并保留所有超限；这仅能回答固定owner开发空间和非RL难度，不是新地图验证、RL效果或创新证据。若全规模的最强DP同总预算达到/接近完整目标，路线RL候选关闭；若有残差，只说明有机会，再另做新机制查新与预注册开发协议。所有方法统一per-drone archive、共同完整初解、完整目标和计时。

本审计实际执行：只读本地源码/JSON/meta、hash及静态RNG流程复核；新solver=0、新evaluator=0、新质量任务=0、新训练=0。
