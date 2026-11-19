# 固定站点归属、联合异构无人机路线：机制独立初判

日期：2026-11-03。作者：route_mechanism_g4。本文件回应root最新有界任务：把物理动作扩为(drone,target)/(drone,RETURN)，但固定station与station type、每个target所属station，不选择搜索算子。为新作用域的静态规格与先例判断；无solver/evaluator/训练。之前fixed-drone-ownership H-R NO_GO与旧Stage A负结果保持不变。

## 初判

**新动作域不是旧Stage A；但裸(drone,target)/(drone,RETURN)仍是已有异构多车辆序列路线构造。当前未识别具体非直接创新，G0尚未通过。**

旧Stage B草案已写“which drone to advance and next target or RETURN”；本次应明确为重新定义并检验其域的前置诊断，不把未执行旧Stage B称作新发现，亦不根据旧Stage A失败自动准入训练。

## 1. 完整物理状态与动作契约

输入：原LRPHSD实例I、固定station_types z、每站固定target集合T_s以及至少一份该固定station assignment下可行完整解R0。每个target在唯一T_s里。station或station type不随RL变化。输出：与z和T_s相容的完整多趟route集合。

每站s的合法physical slots：SABS只有SD；DABS有LD与SD。状态包含所有remaining target集合U_s，各合法drone的当前位置p_d、当前trip序列、当前trip能量e_d/物理时间t_d、已关闭trips、累计已完成dutyh_d。所有在途中构造的drone位置都是路线设计状态，不额外引入真实同步、等待、共享充电队列或makespan。原模型无此资源。

动作a=(s,d,i)：选择一架合法无人机d，从其当前endpoint追加尚未服务i∈U_s；这同时产生该target的drone ownership。其station ownership不变。动作a=(s,d,RETURN)：闭合该机非空当前trip，回本station并重置单趟能量/当前endpoint；已完成累计duty增加，不清零。RETURN不转移目标、不选择repair。

target动作mask至少检查：station coverage、未服务、合法slot、追加target+直接返航的单趟energy≤B_d+epsilon，以及累计duty+当前trip+target+返航≤H_z+epsilon。RETURN检查非空和返航energy/duty。此mask仍仅为前缀一步可行；不保证U_s剩余可全部完成。

完成：U_s均空后按固定自动闭合规则把所有非空open trips返航，再由独立evaluator校验完整解；或逐机RETURN到空U_s且无open trip才STOP，须选一种并冻结。禁止空RETURN空转。固定z相同意味着固定费与全target服务费均常数；精确奖励可用负增量原运行费用，并核对最后闭合费用。

在同station内，drone动作执行顺序只是构造次序；没有新物理同步约束。只有共享未服务target集合使drone choices发生排他竞争。不同station在固定T_s时仍可严格分解；SABS仍等价单机路线；DABS才是两机partition+routes的新范围。

## 2. 与fixed-drone domain的实质区别及适用范围

固定drone ownership时是每机单独问题；现在DABS需同时选择哪些targets归LD、哪些归SD，再各自选择多趟访问顺序。旧per-owner DP参考不覆盖这个额外partition域。station partition DP才覆盖它。

但LD较大battery、同速同运行费用使优势并非普遍来自双机竞争：已封存LD吸收条件在多数旧图有效，若整个T_s满足保守总duty上界，则每个SD trip可原样交LD同成本。对CERT站而言，两机的存在不提升最优目标值；仍可能改变构造/算法运行，但那是待测工程效果。其余站INCONCLUSIVE不证明两机必要。station target集合的规模也小：本代理只读旧24图Greedy完整解，得到82个DABS、每站总目标数3–27，均值12.09756；这不是新的求解或性能样本。

## 3. 最近一手先例：已有完全相同的动作语法

### Li等：Deep Reinforcement Learning for Solving the Heterogeneous Capacitated Vehicle Routing Problem

已下载并阅读作者arXiv HTML 2110.02629v2的III–IV相关定义。其policy先vehicle decoder选v，再node decoder选x；作者明确action a_t=(v_t^i,x_t^j)。上下文包含各vehicle last node、累计travel time和partial routes。MDP持续到全customer完成，可回depot补充容量；包含min-sum总时间及min-max长路线两个目标。

直接重叠：异构车辆、每一步vehicle+target联合选择、共享剩余customer、return补充局部容量、多trip累计travel、编码全fleet和partial routes。因此两层decoder、2D pair pointer、joint target-drone action本身不是创新。

本题不同：固定station coverage、SABS/SD与DABS/LD-SD、edge-dependent flight energy+target energy、per-trip battery和per-drone duty上限。Li采用载重容量语义，并未在已读模型中给出本题这些物理约束。差别是问题约束，而非已经识别的新算法规则。不得声称作者包含全部LRPHSD，亦不得从差别推导“首次joint drone routing”。

### PARCO：Learning Parallel Autoregressive Policies for Efficient Multi-Agent Combinatorial Optimization

已下载作者arXiv HTML 2409.03811v3，阅读§4.1–4.7、§5.1及B.1.1中与本域有关部分。其multiple-pointer对多个agents并行给node动作，communication layers共享agent信息，priority conflict handlers处理同customer冲突。HCVRP允许回depot恢复容量；还研究open multi-depot pickup-delivery。作者基线包含Li两阶段vehicle/node selection及2D-Ptr。

直接重叠：fleet状态、agent竞争同customer、候选冲突处理、heterogeneity、并行路线构造及return资源重置。PARCO已使“并行多无人机+通信+冲突attention”成为不可单独主张的新意。其具体任务/目标与本题不同，本文没有审作者代码，不能声称同约束性能已复现。

### 项目内已读先例

DPTARL正文§4直接覆盖target/RETURN、动态energy mask和长跨度策略学习；它是固定单巢周期巡检，没有由本代理证明同本题联合异构fleet完全等价。Frontiers固定nest巡检原文已有跨tower目标重分和affected routes重新pack。旧本地Stage B草案也已经给出DABS两机选择的构想。

主要一手HTML、规范化文本及URL/hash保存在 `evidence/SOURCE_MANIFEST.json`。这里只形成有限最近先例反证，不宣称全文查新穷尽。

## 4. 当前具体创新是什么

**目前没有。** 以下均不作为G0通过依据：
- (drone,target) factorization或2D pair logit；
- 全fleet attention/通信，或candidate竞争的softmax；
- 共同剩余target集合和恰好一次mask；
- 电量/返航/累计dutymask，RETURN重置trip不重置duty；
- 将Li/PARCO适配到本题，或将PPO换A2C/REINFORCE；
- 把station split-DP的Q值当候选特征/teacher或counterfactual advantage。

可能的工程作用不等于论文方法新意，也不证明无未来新机制。新对象须在这些先例之外给具体算法步骤及可推翻预测，不能用“体现结构耦合”替代。

## 5. Station-level完整参照：适用性与实现难点

对固定station s的target集合T，令Q_d(A)是drone d服务子集A的全部电量可行闭合trip partition中的最小总flight长度，并要求 sum_service(A)+Q_d(A)/speed≤H_z；无合法route取+∞。DABS的完整station问题是：

    min_{A ⊆ T} [Q_LD(A) + Q_SD(T \ A)]。

SABS只有Q_SD(T)。给定每个A的精确Q及其完整trip见证，这一式枚举全部drone partition，不需要额外物理同步；加固定费和全部service常数即原station objective。它是完整机会参照，不是新创新，也不意味着多项式时间。17–27目标的大组存在指数成本，root须冻结size/time/memory处理，不允许删大组、在timeout时把incumbent假报最优。

重要实现区别：只给所有energy-feasible trip的单个最短路径，且Q只优化总flight时，因service在A里固定、duty等价flight上界，最短flight若超duty则该A无可行解；若不超则最优合法。不必在Q里另做Pareto time/length，因为同速下time与length线性同向。但trip能量本身含flight+target energy，不能用只按target energy凑容量的bin packing冒充正确Q。浮点和epsilon须统一并独立完整评分，避免把父DP的严格数值标签问题重开为复现阻塞。

## 6. G2与G4可执行边界

支持root冻结一次station-level全组机会诊断，目的在训练前判断是否存在新增partition headroom及同预算DP可解范围。旧180per-owner task结果对新station域不够，但可复用子集内界与已有bytes；不能重复旧720。

- 输入固定全24旧图原始站型与station ownership；所有82个DABS及SABS照入，不筛LD-CERT、不只挑较大组。结果按CERT/INCONCLUSIVE分层但不改变全集。
- 比较旧Greedy、旧route-SA、旧RL的完整station routes与station exact或有界参考，量化“只重排/分趟”和“放开drone ownership”的可分解差额。旧结果已暴露，只作诊断；不叫新开发、Formal或RL性能。
- oracle生成、DP、验证成本均实记；不能把离线站级最优动作免费供给RL而不供其他控制。若DP变成运行时feature/beam/rollout，全部共享信息控制得到相同工具并计其成本。
- G4未来至少需要：joint pair heuristic/beam、Li式双decoder和适用PARCO式路线模型的准确同域控制（移植边界明示）、station partition-DP/强非RL联合路线方法、3 independent training seeds、BC/REINFORCE/PPO等学习增量归因、无后处理与共同后处理拆开。它们是设计对照，不是当前全部实现完成。
- 若station DP在主预算收掉机会或收益低于完整目标0.3%，缩小域研究应关闭；不在旧图放大目标数制造阳性。若尚有空间，也只支持继续具体新机制立项，不能跳G0直训。

**终结论：当前新物理动作域定义可用；联合异构route构造本身与已核primary先例重叠，非直接创新尚未识别。支持有界station-level G2诊断，暂不支持G0通过或G4训练。**
