# 独立反方初判：prior fixed-owner G2 证据质量与新站内动作域

日期：2026-11-03。任务：只读审计 `prior_g2_retrieval` 已有脚本、JSON及日志；不运行代码、不重算结果、不连接服务器。另依据root最新范围澄清，判断允许的DABS站内(drone slot,target)/ (drone,RETURN)物理路线决策及station-level exact split-DP诊断。

## 裁决摘要

1. 旧fixed-owner exact DP算法结构合理，已对全小尺寸作过134组独立暴力枚举对拍；但留存证据不足以把其跨图按所有无人机组统计的均值宣称为完整地图headroom，也没有对每个n=8..12解保存可独立评分的DP最优完整路线witness。177个被精确求值的固定ownership集合、3个因n>12跳过。
2. `headroom.json`的route-only ALNS距按机DP平均0.156895%是**每无人机组×方法cell的未加权route-minutes gap**，n=1062=177×6，不是地图级样本或完整目标收益。它不能作G2的0.3%通过/失败判断。
3. `headroom_all_sizes.json`和`headroom_seedmatched.json`的6s→120s差值不是剩余理论机会的上界。它们比较随机可行解且未建立嵌套/单调路径；且可行的120s route解给的是最优值上界，不是最优值下界，故差值方向无法封住剩余机会。noise run已异常退出，没有测量噪声证据。
4. 此前按机G2**不覆盖**root现在允许的station-level任务在同站SD/LD之间重新分派。若仍考虑固定站/站型/目标所属站下直接RL，应单独审查站级exact split-DP。这个G2有意义，但与新颖性G0、RL必要性G4分开。
5. DABS动作`(drone slot,target)` / `(drone,RETURN)`在用户给定范围内是物理分配及路线动作，不是算子选择；但generic双车/异构VRP的顺序构造、pointer/attention、energy mask与RETURN已有先例。允许该动作不等于G0创新通过。最可证伪下一步是冻结范围内按站exact split-DP机会审计，先证明有可优化headroom，再论证具体非直接机制和RL增量。

## 一、精确DP对象与算法审计

### 1. 目标与约束

对冻结station、mode、drone slot和owned target set，脚本最小化完整trip闭合后的`travel_minutes + service_minutes`总和。Station fixed cost、service总和和time-cost系数固定。每趟电量为`flight_minutes * flight_energy + sum(target_energy)`，每机累计duty为其全部闭合trip operating minutes之和。原独立evaluator中speed、service、flight-energy和mode duration与该目标一致；脚本从同一已审计Greedy归属取ownership并在每方法route中检查target set exact cover。

### 2. Held–Karp与trip/partition DP

源码对每个target子集求最短station-closed tour travel time，并加子集固定service，energy用`shortest_flight_minutes * flight_energy + fixed_target_energy`。因为flight-energy系数为正常数、子集target energy与顺序无关，最短travel同时使energy最小；若该最短tour超battery，则该子集任意次序都不可能可行。这一筛选逻辑成立。

其后集合分割DP只组合互不相交的可行trip子集，边际tour operating minutes被同时加到cost和duty label。objective中的operating term与duty量相同；若某无人机owned集合存在可行初始完整路线，最短energy-feasible route partition总duty不会比初始路线更大，所以该精确route optimum也满足duty。无效完整解/空trip不会作为分区trip。

浮点边界使用`cap + 1e-7`、`duty + 1e-7`，与现存independent evaluator阈值一致。geometry路径分别以`math.hypot`和浮点加和递推计算；临界margin仍须报告，标作对冻结evaluator谓词的数值最优参考，避免声称严格实数/位级全路径证明。

### 3. 证书强度边界

- `dp_self_validation.json`记载177集合对所有已存可行方法解“DP不高于feasible cost”零违反；该方向能发现DP高估，但单独不能发现DP错误低估。
- 134个n≤7集合以集合partition+trip permutation brute force对拍零不一致。这显著支持小规模DP递推，但没有扩到n=8..12。
- G2程序保存的逐组值是`exact_optimum`标量，没有DP trip/route parent reconstruction或DP primal witness可供independent evaluator逐组重评分。现存方法解是upper-bound证据，不能单独证明n=8..12标量就是exact optimum。
- 若要称某组certified exact，需要完整DP parent重建到route，原independent evaluator可行并同值；同时保留递推/下界证书或等价的穷举/独立实现校验。当前已有数据可称可信的DP参考，避免升级成超出留档证据的独立形式证书。

## 二、统计口径与跳过组

`headroom.json`：177个route ownership set被exact solve；另外3组跳过，最大已解规模12。每个set比较同图3个solver seed×2个预算，共6个方法路线成本，所以每个方法`n=1062`。这些1062项重复使用24张地图、共享map的station/ownership/data；独立统计单位应是地图，而不是ownership或task cell。

校正汇总应按`map × method × budget × solver seed`处理：在图内先把**所有无人机的route operating minutes相加**，保留同图seed配对；再用原完整objective组成完整cost。路线层节约为`time_cost * (baseline_total_route_minutes - comparator_total_route_minutes)`；相对full-cost效应分母必须是同一个完整解的`fixed_cost + time_cost * total_route_minutes`。先在每图平均求解seed差异，再对地图求平均/CI；地图bootstrap为单位。不得把每站、每机或1062个cell当独立样本，也不得只对177组按相对百分比等权平均。

3个n>12组必须明确保留。用现有exact值可报告177组子集的地图内partial aggregate；该值不是完整地图route optimum。任何全图优化空间上界必须给跳过组安全lower bound，或给出有效的DP下界/全局限界；如尚无界，结果应标未决，不能删掉三组或用“小比例”推断影响很小。若只报177集合的paired诊断，应明确目标总体为“exact-cover子集”，不宣布固定owner整图结论。

route-only exact机会的full-cost公式应从同一完整map solution读取station types与固定成本。对同一Frozen ownership，固定项保持不变，因此可由全图总route-minutes改善换算为full-cost delta；但比例会被fixed term稀释。前述0.156895%是相对route operating minutes的task-cell gap，不是full objective节约。

## 三、G2b/G2d误把有限ALNS解差当剩余机会上界

### G2b (`headroom_all_sizes.json`)

- 24张已暴露Stage-A验证地图；每图6s跑3个solver seed，120s跑1个seed，分别取min。所记mean差0.006742%、median0、max0.2800456%，0/24地图超过0.3%，但两图出现负差。seed数量和路径不匹配，不能推导upper bound。
- 从优化方向看，`C_120`是一个可行解，因此`OPT <= C_120`；它提供optimum的upper bound。剩余潜力是`C_6 - OPT`，所以`C_6 - C_120 <= C_6 - OPT`，它是潜力的lower bound（若值为负则仅有负的松界），并非脚本文字宣称的upper bound。需OPT有效lower bound方可封住最大潜力。
- ALNS两个预算均从同一个base初解重新启动。并且SA温度使用`elapsed/budget`，故6s与120s同seed不构成较短轨迹的嵌套延长；“长budget一定不差”没有算法保证。
- 指标为route operating minutes，不是full objective比例；固定项会稀释相对改善。

### G2d (`headroom_seedmatched.json`)

- 6s与120s都取3 seed best，mean差0.030531%、median0、max0.520686%，2/24超过0.3%，2图负值。
- 同一seed出现4个`C_120 > C_6`非单调pair。脚本自己记录该现象并标`NO`，反证其“seed匹配即可单调”的前提。导致点包括不同budget温度日程与重启，不是精确机会界。
- 这仍可视作24张已暴露图上的有限样本经验差，不是正式基线性能、RL机会定理或噪声校正后的估计。

### noise run

`noise_run.log`显示第一次A/A噪声脚本在`decompose`访问`ev['details'].get(...)`时抛`AttributeError: 'list' object has no attribute 'get'`。没有noise输出或噪声floor；不允许引用草稿中的“噪声小于/大于0.3%”主张。该异常发生于已有任务，不应在此次只读审计中重跑。

## 四、root澄清后的物理动作域及先例审查

当前用户允许：站点位置、站型及每个target所属station固定；同一station内部策略可为DABS在SD/LD slots间分派target，并通过`(drone,target)`及`(drone,RETURN)`构造异构route/trip。禁止RL选算子、算法、邻域和强度。

旧fixed-owner G2在每个完整初解的target-to-drone ownership内优化route顺序/分趟；它对上述新域只是一项**弱子域**。其结果不能回答“换SD/LD slot assignment后还有多少空间”，也不能以新slot动作域反证G2无价值。必须在root新澄清后重新立scope。

但“central controller逐步选择哪个slot访问哪个target并何时return”在算法结构上是异构multi-vehicle routing/dispatch的顺序构造。已留档的直接或邻近先例包括：DPTARL单固定nest、energy action pruning、A2C/topology attention；Li & Gonsalves truck-drone dual decoder与多趟return；多智能体能量约束inspection tours；Frontiers多站重派和affected route repacking；以及一般heterogeneous multi-UAV/multi-depot routing文献。部分条目是全文，部分只摘要/preview，需尊重既有证据等级。直接动作集合、RETURN、attention、mask或“joint SD/LD”标签都不足G0创新。

另一个结构性风险：LRPHSD无route synchronization、arrival-time coupling或makespan项；在固定station target-set下，两个drone真实路线是无时间顺序的集合。策略在何时“推进”SD还是LD的构造时交错顺序不是物理决策；有意义的物理选择是target归属、route order和trip partition。若RL动作先选slot再target，需把interleaving view变换的等价解/对称性处理说明清楚，避免把构造顺序当研究变量。

## 五、station-level exact split-DP机会诊断建议（仅协议建议，未执行）

### 数学对象

固定station `s`、mode与station-owned target set `T_s`。若SABS，唯一SD slot服务`T_s`；若DABS，允许把`T_s`任意拆为`A`给LD、`T_s\\A`给SD，两个slot各自再分成station-closed trips。对每个drone `d` 和子集`A`，定义`Q_d(A)`为energy-feasible trips的最小总operating minutes；若该最小解超过station-mode duty limit或无可行trip partition，则记不可行。固定全站service总和后，station精确route成本为：

```text
min_A Q_LD(A) + Q_SD(T_s \\ A)
subject to each slot energy-feasible, duty <= H_mode;
each target appears in exactly one slot and exactly one closed trip.
```

此formulation直接覆盖target-to-SD/LD分派、路线顺序及trip partition。按slot subset与trip partition复用Held-Karp/子集DP；保留可行完整路线parent。所有station独立于其他station，因为station ownership/mode已冻结且目标全在单站服务。

### 为什么值得先做（但不预设会成功）

这是唯一直接覆盖root新动作域的精确机会分析；固定owner per-drone G2可能遗漏SD↔LD重新分派带来的headroom。station-level exact若运行成本可控并逼近旧route方法，将关闭这条更大RL动作域；若精确规模爆炸，则只识别出可能需要近似的空间，不等于RL必要。

### 证伪/停止规则

- 先只读静态统计旧24图每站`|T_s|`、mode、LD/SD初始load及可行性边界，报告所有station，不按结果剔除或放大。旧图已暴露，仅作诊断。
- 冻结split-DP公式、所有target/no-empty-trip精确覆盖、每slot battery和累计duty、输入/代码hash、数值阈值、time/memory cap及route witness接口。
- 明确使用原evaluator的`1e-7` battery/duty可行谓词，保留每条route margin与求和顺序；小规模station用独立ordered-trip/partition穷举对拍。超过预算的station保留incumbent、有效lower bound、gap及完整状态，不以局部exact代替整站exact。
- 对每图，聚合所有station总route-minutes与full evaluator objective，地图为统计单位。每图/方法每seed都要保留完整站级route集合；固定费用用同一mode真实计入。report均值/CI、逐地图gap、DP耗时内存、未解集和route witness复核。
- 若所有(或预声明占比)station可在稳定资源内exact，且strong route baseline full-cost与exact reference距离/机会低于冻存开发门槛，station-level RL收益线NO-GO。
- 若大station超限，只能说机会未决/需要大规模可扩展lower bound；绝不能用小station或24旧图发现的positive/negative趋势外推未见地图。
- 即使exact gap确实大，G0仍需具体超越异构vehicle route construction/dispatch先例的机制；G4还必须证明RL相对共享同一split-DP候选/信息的strong non-RL、beam/lookahead、监督及规则控制有独立收益。

### 统计与公平比较

旧验证图上的exact工作是oracle机会诊断，不是6/12s公平solver对决。若转入新开发/开发RL试验，双方固定同station/mode/target ownership、同初始化/全图外层、相同6s/12s完整墙钟；把模型load、candidate/DP生成、所有station序列构造、validation、失败回退计入。路线改善另拆分，主要门槛仍按完整original objective。exact结果不能人为免费给RL lookahead；若给RL availability/completion signal，strong non-RL和其他学习控制共享同样信息并计生成成本。

## 当前独立建议

- prior fixed-owner G2只能保留为部分精确参考及在24张暴露地图上的有限ALNS经验差，不采用“理论上remaining opportunity <0.3%”结论。
- 站内SD/LD物理路线分派已被root明确纳入允许范围，所以可立station-level split-DP G2诊断；但在先例审计、具体新机制、同成本强非RL及RL增量未通过前，G0/G4仍未过。
- 下一执行决策应先冻结station级DP与lower-bound/route-witness质量合同，而非启动训练。此文为独立初判，不执行这些工作。
