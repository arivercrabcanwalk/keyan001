# 独立机制初判：直接路线 RL 的可证伪对象与 G4 门槛

日期：2026-11-03。代理：route_mechanism_g4。身份：源码取回后独立初判；写作时已收到root要求正面回应按机精确DP挑战及独立反方的具体问题，但未阅读failure代理INITIAL全文。不是交叉讨论后的终局裁决。

## 裁决

**当前没有可以据此通过G0的新RL路线机制。G0继续调查 / NO-GO-as-yet。G4可先共同设计，但暂不训练。**

直接选择下一目标与RETURN的动作类型已在旧Route-RL Stage A中实现，而且相关文献已有先例。现有最清楚的源码假说是：旧actor对每个remaining target独立打分，候选间没有完整剩余路线/组合作用；但这还只是函数类差异，不等于一个有实证必要性或文献增量的新机制。固定ownership问题在已检查样本很小并严格可分；按无人机精确优化是必须先纳入的强非RL对照。因此我不把“换成集合注意力”“加lookahead”“给更大网络/更多训练”提交为G0机制。

## 独立源码观察

服务器回取的Stage A source snapshot包含1605文件且root报告与远端逐项SHA匹配。本判断重点读取：`route_rl/env.py`、`policy.py`、`train.py`、`evaluate.py`，以及原evaluator和Stage A结果。

1. 物理动作确为下一assigned target或RETURN；最后目标后自动返航。每个episode只构造一个station-drone固定ownership集合的多趟路线。不含搜索算子选择，符合用户方向，但这种动作定义不是新增贡献。
2. `env.py`候选mask逐个检查coverage、追加该target后的trip电量和“截至该target并立即返航”的累计duty；RETURN另检查当前trip返航。该mask保证当前动作/单趟可行，不显式证明选择后所有remaining targets还能被分成可行剩余trip。这指出一个可检验的完成性风险，尚未证明旧数据确有dead-end或质量损失。
3. `policy.py` actor的target logit为共享global向量与该target 16维特征拼接后逐target MLP。该特征含 `nearest_other`，global含剩余目标数、平均/最小站距、平均service等摘要；故不应说策略“完全不知道其他候选”。更准确的限制是缺少一般候选两两相容关系：给定global摘要及两个候选各自特征时，第三个候选不能直接进入这两者的相对logit差。RETURN head只看global，critic才接收candidate embedding均值。
4. GAE使用gamma=1、终端没有遗漏reward bootstrap；环境route reward累计所有飞行及service并归一化，现有审计称其与运行时间误差4.44e-16。因此现有证据不支持把负结果归因于明显reward与路线运行目标不一致。归一化的尺度/学习稳定性仍待另审。
5. 每模型seed 60 updates×8 episodes/update；由源码可见每个episode是随机抽取一个map-drone task，不是一个全图轨迹遍历。是否样本不足未被证明。train validation在24个已暴露验证图上挑checkpoint；full 720对比只用seed23 checkpoint，因此完整跨模型种子不确定性没有进入主比较。
6. `evaluate.py`每次rollout都重建所有owned drone task并只保留全图成本best candidate；没有在一次完整构造中显式缓存每个无人机跨rollout的独立incumbent。不过固定ownership下按机可分，给所有方法加per-drone cache是共同工程增强，不是RL创新。第一rollout再加后续随机rollout可能影响吞吐，但已有计数未证明超预算造成旧失败。
7. 旧结果确实可行且不偏Greedy：Stage A 720/720完整解独立核查通过；Route-RL优于Greedy，但route-only SA/ALNS基线更好，6s/12s平均落后约0.967%/0.956%，0/21/3胜平负。它是有效失败结果，不应通过改网络或改名字重跑来冲销。

## 关键反方：fixed-ownership 路线是否值得RL

独立审计提供的旧24图结构计数为180个非空无人机任务集合，中位6目标，最大17；177/180不超过12，179/180不超过16。我的独立初判已接纳这个挑战。对固定station、mode、drone ownership，原evaluator成本可写作固定项+常数服务项+各无人机独立闭合路线长度项；trip电池约束按trip独立，累计duty与每机总时间相加而无跨机同步约束。若初解已证明ownership可行，则去掉任一无人机较差的可行路线不会增加该机总长度/duty。因此每机先找最短energy-feasible多趟路线可构成**非常强的精确非RL参照**；这是目标可分性的直接推论，不是新贡献。

固定ownership原Route-RL研究如果在这些小集合上仍无法胜过精确求解，则route-only RL的实际价值空间很窄。按机subset/partition DP可能是廉价强基线，但运行时尚未测；不能假定它一定在全部规模6/12秒内完成，也不能因为旧小图小就声称所有未来规模容易。

## G2有界证伪建议（等root冻结后执行；此稿不启动solver）

目标不是证明RL而是先判断固定ownership路线空间有无可学剩余收益。建议按冻结的完整旧24图、不筛图共180个owned task集合，逐组报告尺寸、机型、站型、能源紧度、路线初始成本及路线总墙钟。

- 对n≤16的组，用按机exact算法作为最强机会参照：预计算每个target子集/最后节点的最短闭合可行trip；再以子集partition DP组合energy-feasible trips，给完整路线及cost。17目标组也照样纳入，不事先筛出“方便算”的图；若exact超资源限制，记录超限并保留该组，不删除。
- root冻结实际算法、time/memory cap、比较输入/代码hash之后再跑。输入为旧Greedy初始解抽取的固定ownership与原始实例；这些图已暴露，只能是机会/工程诊断，不可用作新开发或Formal优越性证明。
- 同时比较旧强route baseline、旧RL和exact reference的目标空间；把固定站点费用和固定ownership下不变的service常数列出，主效果依然按完整原objective记账。计算精确收益上界仅用于G2；exact oracle不算新solver/RL收益。
- 证伪条件：如果大多数组在6/12秒总预算内精确解完，且余下incumbent-to-exact平均gap低于完整目标0.3%，fixed-ownership RL候选关闭；转而重新审视是否有另一个、物理路线而非算子选择的原模型决策域。若残差只出现在n>16少数组，也须证明在预注册目标实例分布中有足够占比，不能靠放大规模制造任务。
- 此G2不能回答新实例泛化、文献原创性或RL可实现收益，也不应挑DP较慢的组再宣称通过。

## G4共同设计要点（设计阶段，无训练授权）

### 候选可证伪假说 H-R

**H-R（尚未成立）：** 当固定ownership下存在多个各自可行但组合选择不同的剩余目标子集时，显式使用“候选target与全体剩余targets的energy-feasible trip-completion关系”能降低路线构造进入不可完成剩余域的概率及/或最终路线成本；该效果在共享物理动作、信息、计算预算的监督/beam/简单规则下仍有可分辨的跨步RL额外收益。

它不是新颖性主张。相对普通step-mask/target-wise评分的具体对象应是一个候选-剩余集合的**可完成性证书/关系摘要**，通过候选是否留有至少一种合法trip partition/return completion的证据影响target/RETURN动作排序。若该证书只等价于通用lookahead/label-DP现成算法，或按机exact DP更快/更强，该方案应关闭。先例检索目前确认generic action pruning、attention、RETURN、energy-aware route assembly均已有先例；对completion oracle/DP、hypergraph/feasibility-preserving rollout的最接近先例还须专项核查，未检索前不声称差异。

可证伪预测P1：在按整个剩余集合精确可解的小型手工见证上，逐步“单个target+即时RETURN”mask应可产生一个全局不能完成剩余服务的前缀，或者迫使明显更差的partition；若枚举有限所有小见证均不出现，mask死路解释减弱。P2：给所有策略相同的completion证书/候选域后，beam/非RL规则的改进若与RL相同，学习增量为零；P3：RL的额外收益应在多个相互竞争trip partition的状态上出现，而不是仅靠feasibility修复、更多 rollout 或共同后处理。

### 为什么现在不直接训练

“完成性lookahead”是最小可测假说，但仍高度可能是工程性mask，且exact route DP在当前子问题尺度上正是更强同信息基线。故先以不涉及模型的3–6个预声明小型手工构造做状态轨迹/完整partition检查即可；禁止旧图质量搜索、扫参数、网络比较或训练。即使P1找到例子，也只是说明即时mask不充分，不说明路线质量收益、原创性或RL必要性。只有新Agent实际交换后G0同意具体先例增量，且G2 exact headroom实测非零，才应立项G1/G3/G4。

### 相对已有文献

已检索材料明示DPTARL含energy/endurance动态action pruning与长期奖励；pointer/attention、RETURN、battery masks、multi-trip routes也都已有直接先例。候选H-R与它们的暂定区别不是“更好mask”或“加入attention”，而是具体针对LRPHSD固定ownership路线中的跨多个closed trips剩余集合可完成性关系。是否超出标准subset-DP、ESPPRC/RCSP标签、beam lookahead及DPTARL动作pruning，仍未知；Cai/Voigt等缺失全文不会作原创证据。

## 当前建议

1. **NO-GO新训练；NO-GO宣称G0通过。**
2. root冻结下先完成全180 task的成本/规模静态整理，再决定是否授权一次按机exact机会诊断；另有纯可知人工轨迹才用于证伪即时mask。
3. 旧720保持负结果原样，训练seed、地图、预算、checkpoint选择规则都不因本建议变化。
4. 若G2显示exact几乎收掉机会，固定ownership Route-RL就不作为论文主线；可提出新的物理路线决策域假说，但不能转成算子选择。
5. G4如将来进入新开发，除Greedy/insertion/2-opt/强route-SA(ALNS准确命名)外，必须包含按机exact/受限DP、同物理动作beam、规则、监督、至少3 RL seed；训练成本另报、推理计预算。分别保存route-only因果结果与固定共同外层的完整objective。

**初判结论冻结：目前没有证明新RL机制、创新或任何胜非RL效果。completion-aware relation假说仅为下一步最小证伪候选；若没有相对标准DP/feasibility lookahead的可辩护增量则不立项。**
