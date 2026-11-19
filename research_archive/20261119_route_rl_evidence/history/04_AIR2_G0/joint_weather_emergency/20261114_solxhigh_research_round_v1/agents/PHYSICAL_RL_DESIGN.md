# 物理路线 RL：按下一动作索引的两趟重闭合

日期：2026-11-14。执行者：本轮 GPT-6.1-Sol / xhigh 设计 agent。状态：`CONCRETE_G0_CANDIDATE_ENGINEERING_TESTABLE`；G0/G3 **尚未通过**。本 agent 只静态阅读、主源阅读与本文件编辑；没有运行物理/数学数值、求解、模型或训练，也没有修改 root 入口、科学 STATE 或旧结果。

## 结论与唯一新增操作

候选缩写 `AIR2`（action-indexed reclosure of two sorties）。从空物理前缀和公开完整见证 W 出发，RL 每步仍只输出 `(slot,target)` / `(slot,RETURN)`。固定公共内核先在 **动作前仍有效的 W** 中选择两条计划航次，枚举其至多 8 个目标的至多两趟重新分组、访问次序和 typed 指派；真实已执行前缀逐字固定。每条完整候选按它兼容的下一物理动作建立 bucket。同一重闭合表供所有动作查询，再由既有完整费用组合器生成动作 a 的完整后继见证 W_a。actor 选择 a 后，只执行 a；W_a 是下一状态的公开未执行尾计划。

**新步骤只在这里**：`两条原计划趟 → 全部至多两趟重闭合 → 下一物理动作索引`。普通 REINFORCE 是学习组件，不是新增估计器。`remove_target/force/完整见证/跨站donor/共同H/commit` 都已存在，不能重新当贡献；本候选的 kernel 收益也不能直接归为 RL 收益。

最关键边界：这里的“精确”仅指**登记的两条源趟、至多两条替代趟、固定插入规则**的有限域。不是 ≤8 目标任意趟数精确 cover，不是完整物理域 oracle，也不证明一般两趟邻域具有新颖性。

## G0-1：输入、输出与物理动作映射

科学合同沿用固定风 A、简单能耗、完整作者同风 Rw 的固定站型/部署/target-station，逐图 `C<=C_w(Rw)+1e-7`，最小含最后返航的 `M_return`。科学 6s/12s 包括载模、表编译、组合、原 scorer、序列化和进程退出；T_anchor 单列。应急后置。

状态显式为 `z=(I, h, W, B)`：I 为公开实例及风；h 为全部已执行 TARGET/RETURN 的原物理状态；W 是与 h 兼容的完整可行见证；B 是本次构造已实际得到的完整候选池。不得把只依赖 h 的 actor 冒称这里充分状态，W 的分组/顺序/身份均是公开信息，全部控制相同。

- 每 slot 的已完成趟、当前开放趟实际前缀 p、累计 duty、趟内能量固定。RETURN 仅清本趟电池，不清 duty。
- 计划趟是 W 中的一条完整站点闭趟；它可以包含真实开放前缀 p，也可以完全未执行。已完成趟不参加重闭合。
- `SD<=3 / LD<=4` 仅在 generator_v2 的 service=10、energy=.2、目标间距≥200、speed=900、flight_energy=.018、SD=.81/LD=1 和已证明恒风域适用。编译入口必须绑定这个域；仍逐趟核能量，不能把 3/4 当充分可行性。
- actor 不输出趟对、算子、repair 强度、算法或预算。趟对由固定目录顺序处理。actor 输出的是经过完整证人验证的物理动作。未查询动作标记 `UNEVALUATED`，不记为物理不可行。
- 从 h 为空开始同样运行；初始 W=Rw（工程为手写完整 anchor，不冒充 Rw）。故不是只在已有完整路线中挑编号；物理前缀、后续分组与访问次序会逐步改变。

## G0-2：候选表、精确伪码与一次更新

### 2.1 预动作两趟有限域

对站 i 的每个登记趟对 `(r1,r2)`（亦允许单趟退化情形），取其目标并集 Z。**在 force 之前取 Z**；此时每原趟≤4，故 `|Z|<=8`。先 force 再随意取两趟会出现 5+4=9 个目标，不能套本界。

对 Z 的所有分成 1 或 2 个非空有序目标列表的方式枚举：每列表选择合法 slot；按该 slot 容量限到≤3/4；计算全部内部排列，逐边含返站评分。此处不只保存每集合最短顺序，避免用实数支配冒称原 binary64 的完全同一域。选中趟以外的目标次序和所属 slot 不变。

插入规则固定为：

1. 含真实开放前缀的替代趟，必须仍在原 slot，且以完整 p 逐字开头；它占该 slot 的当前第一条待完成趟。两个不同 slot 的非空 p 必须进入两条不同趟，禁止合并、换 slot 或互换先后。
2. 其余替代趟作为一个连续块，放在目标 slot 已完成趟和当前真实开放趟之后、其余未执行整趟之前；未选中趟的相对顺序保留。两条替代趟同 slot 时，两种相对顺序均枚举。空趟不输出。这是固定的“未执行整趟前端插入”，不是任意插入位置全域。
3. 某 slot 在 h 中为空且新趟进入该 slot，则它的下一物理动作是新首目标；它在 W 中原来尚未执行的其他趟顺延。已经完成的趟永不后移。
4. 整站覆盖必须恰好一次，目标站归属、slot 资格、半径、电量、累计 duty 均调用原合同核对。保留完整路线和原次序累加值，不只保存同组矩阵。

对每个完整站候选 s，表行包含：

```text
station_id, pair_source_ids, full_station_routes, full_route_hash,
exact original-order slot_duty[0:2], trip_energies, local_M,
prefix_identity, actual_prefix_preserved,
next_action_per_enabled_slot, source=identity|old_1reloc|AIR2,
group_hash(for diagnosis only), internal_order_hash,
compile_status=COMPLETE|DEADLINE_PARTIAL, physical_score_receipt
```

`next_action(slot,s,h)` 的定义：若 slot 当前 p 非空且 s 的当前趟恰为 p，则输出 RETURN；若其当前趟严格延长 p，则输出 p 后的第一个 target；若 p 为空而尚有趟，则输出第一趟首目标；否则该 slot 无下一动作。一个 s 最多进入两个动作 bucket，不通过任意插入 RETURN 人为制造新路径。

**commit 格式必须转换一次**。表保存的是 pre-action 完整计划，现成 `CompletionSession.commit` 期待已force后的 `(done,prefix,suffix,future)` 表示。取得动作 a 的pre-plan后，在该候选上做 `post_plan[i]=force(pre_plan[i],a.slot,a.target)`；因为a恰是它的next token，完整 `routes(post_plan)==routes(pre_plan)`，只移动公开的“已经执行”边界。再以旧W的 `force(W[i],a)` 作为锁，调用 `_preserves(post_plan,locked_W)`；保存相同source_identity、H、完整solution/hash。传给commit的是post_plan，不能把pre-table的未执行表示直接塞入result.plan，也不能真正env.step后再次force导致重复执行。

`|Z|<=8` 对**两个完整原计划趟**成立，包括它们各自已经执行的开放前缀；不是只数未服务尾节点。已完成趟不在Z；其他未选中开放趟保留在上下文。两个源趟若同slot，至多其中首条含该slot当前p；若分别含两个slot的p，则必须恰好保留两条前缀锚定趟。所有p目标也参与恰好一次覆盖核对，不能把它们丢出Z后重新当未服务目标排列。

候选集合为 `identity(W) ∪ 旧单relocation候选 ∪ AIR2候选`。保留旧域有两个理由：保证无新增候选时不丢已验证路线；**两趟 replacement 并不覆盖一次早返航后需要三趟才能续完的分支**，这种分支不得以“≤8”误称已穷举。这里只声称 AIR2 域内精确，旧域 UNION 不能当完整动作 oracle。

### 2.2 跨站费用与完整动作证人

站 i 的 `A_i[a]` 为兼容下一动作 a 的完整站候选；其他站为全部已编译 `A_j`。对每个共同 H，调用现成按原站/slot 顺序的字面费用组合器：动作站仅允许 `A_i[a]`，其他站允许各自 `A_j`，同时 `m_j<=H`。在所有已见候选 m 值上选最小可行 H；输出完整 W_a，并用原 `wind_scorer.validate_candidate` 复核全图。有限 bank 无见证的语义仍是 `NO_BANK_WITNESS`，不是物理 UNSAT。

局部row只按原物理可行性入池，**不能先按“其余站固定anchor”的完整cap筛掉**；它可能正是需要远站融资的较贵动作站。single-replacement cost/超cap只是诊断，最终组合才执行完整cap。

因此某个动作站的较贵、更快分组可由另一站更省费用的两趟重闭合支付。固定 H 后各站独立求费用的分解仍成立，本候选没有声称“必须联合 actor”或推翻共同 H 强独立控制。`time_cost=0` 不做除法；NaN/overflow 拒绝；浮点临界不以站内先求和替代原顺序。

**prefix 查询中不调用不受限 T**：公共整趟重排会移动已执行趟，不能拿它伪造 h 兼容。T 只在完整离线候选的共同交付路径使用；raw/T 后均保存且重新验 cap。若未来实现 prefix-preserving T，须单独定义并向全部控制开放。

### 2.3 唯一构造/更新循环

```python
def one_air2_trajectory(theta, I, anchor, shared, deadline):
    env = shared.empty_physical_env(I, anchor)
    W = anchor.solution()                 # public full feasible witness
    bank, logp = [W], []
    while not env.done:
        h = env.public_physical_state()
        # Pre-action W; compile once and index all compatible next actions.
        tables = shared.compile_pair_rows(W, h, deadline,
                   outputs_at_most_two=True, include_identity_and_old_1reloc=True)
        WA = shared.full_cap_action_witnesses(tables, h, anchor, deadline)
        bank.extend(WA.values())         # COLLECT control receives exactly these too
        if not WA or deadline.expired():
            return shared.deliver_best_or_anchor(bank), sum(logp), "STOP_WITH_RECEIPTS"
        logits = actor(theta, I, h, W, WA) # unrestricted trainable logits; physical actions
        a, lp = sample_softmax(logits, support=WA.keys())
        shared.assert_complete_witness_compatible(WA[a], h, a)
        env.step(a.slot, a.target_or_RETURN) # one genuine physical step only
        W = WA[a]                        # only the unexecuted tail may have changed
        logp.append(lp)
    bank.append(shared.complete_raw(env))
    return shared.score_T_full_cap_and_deliver(bank, anchor), sum(logp), "COMPLETE"

def one_update(theta, fresh_TRAIN_I, anchor, K, shared):
    # Formula only; no model/update/training has been run in this agent task.
    runs = [one_air2_trajectory(theta, fresh_TRAIN_I, anchor, shared,
                              shared.frozen_work_budget()) for _ in range(K)]
    U = shared.anchor_normalized_best_deliverable_M(runs, anchor)
    b = shared.sample_independent_frozen_baseline(fresh_TRAIN_I, anchor)
    loss = -stop_gradient(U - b) * sum(run.logp for run in runs)
    return loss                       # one ordinary joint-score backward/update
```

一次学习目标是实际构造及候选收集的交付结果；全部抽样轨迹、失败/未获胜动作都保留 score。确定的表编译/组合不添加随机 score 项。不得只训练最终赢家、只乘 cap 合格轨迹或沿用旧独立删除信用。学习实现须固定 kernel 工作配额以使支持/停机法则不依赖 θ；若用实时终止改变候选支持，其实际运行律与梯度目标须另行记录，不能直接宣称上述简单 law 精确。

logit 不继承旧动态 J 的固定 `prior+6*tanh(r/6)` 排序上界。旧 J 根因是提醒，未外推成当前固定风的实证原因；这里也不需要重跑旧诊断。

### 2.4 真正源码入口

以下均是本轮实际静态定位，**本 agent 未编辑这些文件**：

- `joint_weather_emergency/20261113_prefix_completion_interface_v1/MODIFIED_FILE/compiler.py::remove_target / force / neighborhood / Compiler.local / donor / query`：旧 `neighborhood` 明确为 identity 或一次未执行 target relocation；旧 `query` 已有 action→local→remote donor→完整 cap。
- 同包 `prefix_completion.py::CompletionSession.query_action / commit / _preserves`：保留 public identity、原环境 legal、完整 scorer 和实际 env.step；它们是现成接线。AIR2 不能在 force 后裸替换 `neighborhood`，应新增 pre-action `compile_pair_rows(witness,observation)`，再将 row witness 适配回 query_action/commit 的格式。
- `joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/MODIFIED_FILE/independent_h.py::local_row / combine_at_H`：复用 row duty/原 scorer 与 Context 的字面成本路径；不要调用它的 unrestricted projected_slots/T 来检查 prefix。
- 其导入的 `schedule_credit.py::Context.minimum(H)` 是既有公共组合入口；用相同银行/动作限制构造 Context，不另造总成本的浮点替代公式。
- `joint_weather_emergency/20261114_bounded_sortie_reference_v1/REPORT_ZH.md` 的 rank 证明与有限内核验收直接复用；不把旧零风 exact_minmax 整个当风感知 solver 导入。

## G0-3：最近主源与逐步差分

本轮使用 nature-academic-search 的定向主源读取流程。学术 search MCP/AgentKey discovery 未在实际工具目录中出现，使用可用 web 主源；没有安装或修改客户端。不是系统新颖性检索。

|最近对象|已经有的操作|AIR2 唯一可辨别增量/边界|
|---|---|---|
|本项目 compensating_tail / CompletionSession|下一动作强制、未执行单target relocation、H下donor、完整见证后commit|把一个target邻域换成两个原趟≤8目标的精确≤2趟重闭合，并一次建表索引全部下一物理动作；其余全部复用|
|本项目 action_conditioned_repack|闭趟集合/内部次序不变，只在两个typed slot间重分配；开放趟固定|AIR2 允许目标跨这两趟重新同组和内部换序；不只换slot；仍不扩大 full-support 原物理完整域|
|Falkner等 NCH-LNS，arXiv:2205.00772v2，§1.2、§2/Alg1、§2.1–2.2|神经逐节点重构、固定破坏/修复、局部搜索与候选人口已有|AIR2不是“学习重构+LNS”首创。区别仅在完整累计duty/cap见证中，固定rank两趟精确表按原物理下一动作共用；此特定组合的新颖性待核|
|Weber等 AAMAS2024，arXiv:2305.15596v2，§2 Eq1、§3 TMAR|对候选物理动作接base rollout，顺序多agent rollout已有|不把full witness/action-conditioned completion叫新rollout。AIR2的表编译及融资内核是任务结构组合；未继承其cost-improvement theorem|
|已有GaS/heterogeneous Split/Paradiso多趟trip-cover|序列后Split、资源标签、trip列与覆盖已有|AIR2不是对一条固定giant tour作连续Split，而是两个旧趟目标全重组；普通set partition/精确局部搜索也不主张原创|

本轮实际读取范围与 URL：

1. [NCH-LNS v2 PDF](https://arxiv.org/pdf/2205.00772)：网页提取 lines34–199，重点 §1.2、§2、Alg1、§2.1–2.2；不是全文实验复现。最初试 `html/2205.00772v3` 返回404，随后 abs 显示只有 v1/v2，再读有效 PDF；不将404当缺论文或已读。
2. [Distributed Online Rollout正式会议论文作者PDF](https://web.mit.edu/dimitrib/www/Multivehicle_Routing_2023.pdf)：lines251–290（§2/Eq1），以及返回中§3 TMAR的相关说明；未核其完整证明/补充实验。
3. 直接复用旧包 DPN v2、SED2AM v1、GaS、heterogeneous Split、Paradiso 的已存阅读；本轮没有把重复查读计成新发现。

主源已经覆盖通用 learned repair/rollout；这里仅可提出“特定结构组合＋待检验差分”。**不能以通用框架能表达AIR2自动判全盘无效，也不能以未检出完全相同命名宣布原创。**

## G0-4：可证伪预测与最小新工程输入

最先验证结构而非训练。仅 root 在 <COMPUTE_HOST>，0作者solve/强ALNS质量批次/模型/参数更新/科学地图。以下输入一次冻结；任何结果都不拿来调几何、H、pair宽度或采样。

统一：wind=(160,-100)，speed=900，flight_energy=.018，service=10，energy=.2，SD=.81，LD=1；其他半径、费用、duty直接沿当前 problem 参数。目标置于400m方格；固定target-station。anchor 的完整 C/M 只在 <COMPUTE_HOST> 由原 scorer 求，若任一原anchor非法，记录 `INPUT_FAILED` 并关闭本次fixture，不改坐标救结果。

|ID|站/目标与 anchor（站内局部坐标；F2站1坐标整体+6000m x）|登记目的|
|---|---|---|
|E1|单大站(0,0)。1(600,-400),2(600,0),3(600,400),4(1800,-400),5(1800,0),6(1800,400)。LD:[1,4,2]；SD:[3,6,5]|非连续Split的两趟多target重组；empty及prefix=LD TARGET1|
|E2|两大站(0,0)/(6000,0)。站0：1(2000,-600),2(2400,-600),3(2400,-200),4(2000,-200),5(400,-600),6(800,-600)。LD:[1,2,3,4]，SD:[5,6]。站1局部：7(1200,400),8(1600,400),9(1600,800),10(1200,800),11(400,400),12(800,400)。LD:[7,11,12]，SD:[8,9,10]|候选 recipient 4/2→3/3 提速可能更费，donor 3/3→4/2 可能节省；**这些是待测而非已证物理结果**。empty及prefix=站0 LD TARGET1|
|E3|单小站(0,0)，仅SD。1(400,0),2(800,0),3(400,400),4(800,400)。SD:[1,2],[3,4]，LD空|SD四目标趟必须拒；empty及prefix=SD TARGET1，RETURN分支固定p不能再延伸/搬动|

每配置只编译一次；两个起点共6配置。只处理本表两条原计划趟的唯一pair，各站没有再挑pair。所有row与兼容动作bucket保留，不随机抽样，也不借旧4几何/32对/校准24满额重跑。

**固定反例/负控**：

- 组合标签例：`{a,b,c,d}|{e,f,g,h} → {a,c,e,g}|{b,d,f,h}`。单次一target relocation无法产生此分组，而两趟表可表示；这只是离散域差分，不是合法几何质量证据。
- 已执行 p 的删改/逆序/换slot、SD装4目标、跨站换target、RETURN后把已closed趟重新接target，必须被拒。
- 旧公共T若移动已执行趟，不得用作prefix证书；保留原row再评分为负控。
- E3早RETURN可能需要原两趟变三趟。AIR2≤2趟表允许漏它，但不得报告已证明无可行续接；identity+旧域仍单列。
- 费用负控只对已得到完整证人的复制结果改变cap，检查完整原scorer拒绝；不把改cap输入当科学图或新质量样本。

三个可证伪预测：

P1：AIR2表出现旧identity/单relocation没有的真实同组/内部次序，且至少一个新row通过完整原scorer和空状态动作重放。若只有原分组slot移动则候选操作实现失败。

P2：E2至少找到一个完整动作证人，动作站单替换超cap，公共组合后在cap内，并且动作站/远站至少一个发生多target重分组；其M是否真正降低全部如实记录。若没有，只关闭当前固定实例上的融资/支持差分主张，不换几何找阳性。

P3：候选按同一完整table进行独立枚举，动作bucket与物理前缀兼容关系完全相同；在同实际工作量下，共用表少于逐动作重新编译的趟资源求值次数。wall/CPU必须同时报告，少次数不自动当加速。

## G0-5：强控制与收益归因

最小工程只作接线/支持核对：OLD_1RELOC、AIR2_SHARED_TABLE、AIR2_PER_ACTION_RECOMPILE（同一有限域/完整row集合）、独立验收。没有模型时不声称RL赢了。

后续若G0/G3另获准，至少保留：

|控制|相同信息/内核|必须区分的结论|
|---|---|---|
|COLLECT + witness-follow|获得所有已算W_a和公共bank，物理动作只跟随当前最佳完整见证|内核和候选收集自身能达到多少|
|同kernel一阶贪心|按已得完整W_a的M/C/稳定id选下一物理动作|学习是否胜过立即最好completion|
|同kernel BC/监督|相同网络和全部标签，teacher费用完整计账|不是把监督数据或更多求解白送RL|
|同kernel标准flat/hierarchical RL|同全部公开W、WA、原动作支持和普通终局PG|相同law/网络/PG时它就是AIR2-RL本身，不另列虚假的独立arm。可比较的是旧kernel同RL与AIR2 kernel同RL，以及不同真实网络因子化；不虚设一个不存在的新估计器|
|强minmax ALNS + commonH独立新生成|保留原生merge/split/relocate/swap/ruin、风感知物理域、跨站费用融资、完整6s/12s交付|主科学竞争对象；不降成只能单站立即接受/旧静态bank|

全部W_a必须进入同次构造的公共bank，包括actor未选的动作。这里分开两个对象：**shadow-COLLECT** 跟随RL实际访问的h/W免费镜像收相同bank，只作归因审计，交付必与该bank相同；**independent-COLLECT** 用自己的witness-follow/greedy前缀和同kernel、同信息、同deadline，不免费读取RL以后发现的表，它才是独立科学控制。不能把shadow的必然平局当路径学习无效。

若结果只由第一轮已枚举row决定，不能归因于后续RL。必须报告raw、T后、完整cap、前缀行为、实际新分组/顺序，以及首次编译与最后完整bank分别达到的M；不能因最终M相同就一律称T抹平。

### 跨agent反驳后的精确增量对象

`rl_failure_design_20261114` 指出确定性等式：非终止状态下，若初次已编译有限完整域B0中每条schedule至少落入一个合法next-action bucket，且W_a是该bucket按相同raw M/cap目标的最优解，则

```text
min_a M_raw(W_a) = F_raw(B0).
```

因此第一次表的全部即时收益已被公共bank收取，RL选择哪一个a不会再创造第一次表的即时最优值。若bucket优化使用同一T后交付目标，相应等式也成立；若仅raw目标最优后再T，不混同两个优化域。AIR2中的RL可检验增量只能是：所选a改变后续(h,W)，使后续表发现B0以外、完整cap合格且更好的分组/顺序。必须记录 `F(B0), F(B_final)`、每个首次改善的产生轮/源pair/完整路线身份、是否B0已经出现，以及真实新增编译费用。若后续没有新的更好域，AIR2只得到公共内核效果。

我对其学习稿的具体反驳也已交换：两次续接replicate均正只构成冻结筛选代理，不证明总体Q更好；margin投影后的整体actor不继承冻结suffix条件PG的无偏性质。对方已接受补边界；同数据margin-only仍是必须的强控制。本轮不把它自动叠到AIR2工程上，也不因此启动训练。

## G0-6：事前停止条件、资源边界与下一具体动作

本文件冻结的是上面一次新工程设计，不是训练准入。建议 root 在 <COMPUTE_HOST> 编码前保留原hash/隔离copy/diff/rollback；旧失败原件不动。可冻结总child CPU≤180s、phase wall合计≤240s、单进程≤1GiB，repair最多1次仅正确性/验收问题；不重跑成功计时、不为质量修输入。phase预算可按BASELINE20/MODIFIED60/AUDIT80/ROLLBACK20 CPU分配，传输另记。root若已有更严资源合同，采用更严上界而不静默扩预算。

直接枚举保守上界（重复未去除前）可写 `8*(n-1)*n! + 2*n!`，n<=8，包含两趟slot/相对序保守重复；不是低复杂度保证。工程最大n=6，每pair不到约3.1万原始枚举项；这只是符号上界，没有在Mac执行组合计算。新工程可明确设 `max_raw_attempts_per_pair=31000`；原Compiler的4000候选guard属于旧单relocation域，不静默抬高或复用为本新域已验限额。达到上限/期限仅收已有完整证人，pair标记PARTIAL，不能称全域枚举完成。科学域pair数随未执行趟数平方增长，完整表可能很贵；不能据n<=8自动承诺6s/12s。缓存key必须含原路线、两条源趟、物理prefix、typed/风/参数和固定插入规则；全图预算传入内层每次deadline检查，不能每站获得独立600s。

任何一项即停止依赖解释：

1. 原scorer/重放/前缀/bucket独立验收不一致；任何四目标SD或已执行target移动通过；任何非完整见证进入可执行mask。
2. P1失败：没有新增合法分组/顺序。只保留失败/组件，不包装G0通过。
3. P2失败：当前固定工程融资差分关闭，不追加类似toy、不调成本、H、坐标、pair个数。
4. 共享表与逐动作重编译row/bucket不一致；内核时间/内存超限；或只减少计数而端到端更慢，则共享效率主张关闭。
5. 后续新TRAIN上同kernel COLLECT/贪心/BC/标准RL已解释全部收益，则学习增量关闭；不把这一结果外推成RL普遍无效。
6. 后续6s/12s完整交付未胜强ALNS/commonH控制，则该候选的科学优势主张关闭，不降低基线/成本cap或删除失败seed。

**给 root 的最关键下一操作**：仅新增一个隔离 `compile_pair_rows(W,h)`，先让它返回“完整路线＋每slot下一动作”记录；以E1/E2/E3跑一次无模型工程，复用CompletionSession的public_identity/scorer/commit与Context组合。先证明具体新row、prefix、跨站完整cap，再考虑学习，结束新adapter/旧记录器/旧实验的重复扩展。若AIR2仅能被表述为exact-LNS公共组件，照实保留这种定位；目前已经有可指认、可实现、可失败的增量，无须为新通用PG原语继续无限筛查。

## 静态阅读与本文件核验范围

已读：AGENTS最新覆盖；LATEST_STATUS前80行；USER_RESEARCH_REQUIREMENTS/RESEARCH_PLAN_ROUTE_RL最新相关段；任务指定五包的MECHANISM_SPEC/REPORT（multitrip包为实际PHYSICAL_ROUTE_ITERATION）；另外deadline分解、trip-group、prefix completion、conflict credit、two-round complement、block-spine及bounded-sortie报告。源码只静态读取上述Compiler/CompletionSession/independent_h入口。已有旧失败直接复用，未再跑。

本文件落盘后的验证只检查文件存在、六项结构、指定函数/输入/停止条件文字以及读回；不是物理baseline、G0通过或RL证据。所列工程/训练伪码均为待实现规格。

## 2026-11-14 失败后纠正：force不是纯next-token推进

**本附记覆盖§2.1中“a是next token则force(pre_plan,a)保持完整routes”的错误断言；原句和原稿保留，不覆写。** root报告，本轮真实<REMOVED_ENDPOINT>工程的BASELINE已被 `routes(post)==routes(pre)` 断言拦下，原6配置批次repair=0并停止，不重开。此失败不是AIR2表通过；G0/G3仍未过。本agent只静态复核源码并附记，没有运行或重跑该工程。

静态根因：旧 `Compiler.force` 先调用 `remove_target`，后者对每slot执行 `norm`。若候选当前趟为单TARGET(a)、prefix为空、future非空，remove使suffix空；norm先把future首趟提升为suffix，随后force才把a放入prefix，因而把原两趟合成一趟。漏查的是这个中间归一化顺序，不能用“最终a已在prefix”推导完整路线不变。

新pre-action适配必须使用专用 **`advance_next_token`**，它只推进已知兼容完整候选的执行边界，不从全站搜索/删除target：

```python
def advance_next_token(station_pre, slot, target_or_RETURN):
    out = list(station_pre)
    done, prefix, suffix, future = out[slot]
    if target_or_RETURN is not None:
        a = target_or_RETURN
        assert suffix and suffix[0] == a  # exact next token of this candidate
        # Do not call remove_target or norm before extending prefix.
        out[slot] = (done, prefix + (a,), suffix[1:], future)
    else:
        assert prefix and not suffix     # this candidate really returns now
        out[slot] = norm((done + (prefix,), (), (), future))
    return tuple(out)
```

TARGET分支直接把suffix首位移入prefix；即使它是单目标趟，future也保持原位。RETURN仅在suffix空时将prefix闭合到done，随后norm才允许提升下一未来趟。其他slot不变。上述是修正规格伪码，本agent未执行它。

适配后的验收对象为：`post=advance_next_token(pre,a)`；独立检查完整 `routes(post)==routes(pre)`、恰好一个执行边界变化、其他slot不变；`force(old_W,a)` **只作done/prefix锁参考**，不得再作为候选pre→post完整计划转换，也不以它的完整routes断言候选路线不变。source_identity、solution/hash和原scorer仍绑定实际候选。实际env.step仅执行一次。

root正在单独进行该专用边界推进的隔离有限测试；本文件不预报其结果，也不把该局部修复测试当AIR2原失败6配置恢复、AIR2表验收或学习证据。之后若另开AIR2工程，必须是新的明确冻结批次，保留本次失败及原错误设计；当前附记不构成重开许可。
