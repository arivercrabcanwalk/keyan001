# 固定风有限航次结构与精确参考内核

当前状态：`STRUCTURAL_REDUCTION_AND_LIMITED_<REMOVED_ENDPOINT>_KERNEL_PASS`。2026-11-14 用户确认连接恢复后，<COMPUTE_HOST> 的一次冻结工程验收已执行；下文“待执行”段落保留为执行前规格，最新事实以本段与末尾接续为准。
仅 root。固定风、简单线性能耗先行，应急后置。此包是新结构推导与既有精确参考器的隔离优化，不是一个已通过 G0 的 RL 算法。

## 已证实事实与证明

当前科学域的源码条件如下；它们不是任意工程 fixture 或未来应急域的默认条件。

| 条件 | 原始来源 |
|---|---|
| 每目标服务能量 0.2、服务时间 10 min | `route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>` |
| 不同目标欧氏距离至少 200 m | 同文件 `proposal_reasons:184–185` |
| 空速 900 m/min，飞行能量率 0.018/min，SD/LD 电池 0.81/1.0 | `route_rl_research/20261103/source_snapshot/lrphsd/problem.py:7–11` |
| 恒风模小于空速，闭趟含完整返航 | `20261112_constant_wind_v1/MODIFIED_FILE/env/constant_wind.py:16–66` |
| 电量是 flight_time×0.018＋服务能量，duty 跨 RETURN 累计 | 同包 `baselines/wind_scorer.py:176–221` |

令一个闭合航次访问 k≥2 个互异目标。相邻目标之间的 k−1 条边各长至少 200 m；最后目标经站点回到首目标的两段距离之和至少是末首目标间距离，也至少 200 m。故闭趟欧氏长度 L≥200k。站点不必满足目标间距条件。k=1 不套用该长度式。

沿用已完成的恒风闭趟分解，设 D=v²−|w|²>0。对位移 d，

```text
S_w(d) = sqrt(D|d|² + (w·d)²)/D
t_w(d) = S_w(d) - w·d/D
```

`S_w(d)≥|d|/v`，因为平方比较后的差为 `D|w|²|d|²+v²(w·d)²≥0`。闭趟势差相消，故 `T_flight≥L/v`。这是复用旧恒风恒等式得到的新条件推论，不将原分解重新计作创新。

因此在本域中，`E≥0.2k+0.018×200k/900=0.204k`。SD 的 k=4 时 `E≥0.816>0.81`；LD 的 k=5 时 `E≥1.02>1`。更大的 k 也被排除：**SD 每趟至多 3 目标，LD 每趟至多 4 目标**。排除间隔分别为 0.006 与 0.02，大于当前 scorer 的 1e−12 能量容差及旧参考器的 1e−7；这里比较的是数学余量，不是假称已完成浮点工程验收。

结论不保证任意 3/4 目标组合可行。风、站点距离、机型资格、覆盖半径、完整返航电量、累计 duty、全图成本 cap 仍须原样检查。异质服务能量、改变电池/空速/飞行能耗、目标间距不足、时间变风或应急重复访问须重新证明；不能沿用上界静默删解。

统一服务时间只使一个 slot 的服务部分变成 `10×目标数`。不同 slot 的飞行时间仍依赖分组与顺序，最优 LD/SD 目标计数不保证相差≤1；不能据此把两机分配化成简单平均分。

## 完整表示与复杂度边界

无时间窗、release、等待/换电开销、共享充电资源、先后顺序约束时，同一目标集合最短闭趟顺序同时降低 flight time、服务不变的 duty、能量和 operating cost。以较短顺序替换原趟不破坏当前 S_const 约束。因此实数模型中存在只采用每集合最短顺序的最优完整解。此支配原理已在旧 `EXACT_MINMAX_REFERENCE.md` 和 `exact_minmax.py` 使用，不是新发现。

结合本次数量上界，每站可行趟可从大小≤3/4 的集合生成；每个集合至多 3!/4! 种目标顺序。反转等价直接复用旧结果，不重复声称新意。逐边浮点评分下，不据实数支配定理声称不同顺序逐位等同；最终保留完整路线并由 heading scorer 独立验收。

趟集合最多 `sum_{j=1}^4 binom(n,j)`，但 exact-once cover、机型和累计 duty 组合仍是组合问题；有限 rank 不意味着整图多项式可解，也不承诺建完整 catalogue 能满足 6s/12s。

## 真实代码差分

原 `20261112_takeover_completion/harness/exact_minmax.py` 已包含 Held–Karp、每 slot 的集合划分 DP、LD/SD 目标集合分配及全局共同 H / operating-cost frontier。无需再造 exact-cover 或公共接线。

第一轮复制该文件并改 **partition_dp 的转移枚举分支**；随后静态接线核对又修正 **main 的 UNKNOWN 下界聚合分支**，详见下节和 LOWER_BOUND_FIX.md。原程序对每个非空 mask 取最小位 p，再扫描含 p 的所有子集，之后才查 energy。修改副本先把满足原 `energy[block] <= cap + PHYS` 的块按最小位索引；每个状态在 catalogue 与原全部子集枚举中选择扫描数量较小的分支。

```text
按 block 从大到小，把能量合格的 block 存入 feasible_by_low
按原 mask 顺序递推
若 catalogue 长度不超过该 mask 原子集数，扫描它并过滤 block⊆mask
否则执行原子集扫描
按原表达式 dur[block] + best[mask ^ block] 更新
保留原 < 并列判定、PHYS、limit、choice 与 transitions 语义
```

这一步不需要把 3/4 作为硬编码正确性条件，dense energy 输入仍是完整原表。若合格块 rank≤r，catalogue 分支扫描数上界为

```text
sum_{p=0}^{n-1} 2^(n-p-1) * sum_{j=0}^{r-1} binom(n-p-1,j)
= O(2^n n^(r-1))       (固定 r)
```

另有 O(2^n) 表扫描和 O(合格块数) 内存。自适应分支的状态扫描数不大于原扫描数，但预建表、列表/位运算开销可能抵消收益。**完整求解器仍计算 dense Held–Karp**；本次没有实现 O(n⁴) trip compiler，也没有改变 max_n_exact、全局 frontier 求解、计时或随机检查。main 的 UNKNOWN 展示下界另有纠错。主副本仍是原零风精确参考器，不能直接作为风感知科学 solver 使用。

## UNKNOWN 下界的实质纠错

静态追踪发现原 main 用已解站 frontier 的最大 M 作为站内下界。若该站还有费用较高、M较低且在全图cap内可行的点，最大M就高于一个合法解，因而不是下界。副本将这两个站内 max 改成 min，跨站 max 保留。仅查看5条已存 UNKNOWN 记录后，所涉多点项都未决定其已存全图下界；8x80_o1 的决定项是单点站，故不改写这5个旧数值或状态。证明、逐行既有数值来源和待执行检查见 LOWER_BOUND_FIX.md。原源码与旧结果JSON保持 hash，第一轮仅改 partition_dp 的完整副本/验证收据留在 PRE_LOWER_BOUND_FIX。

## 等价性论证与未完成的验证

固定 mask 的每个原子集 block 含 mask 最小位 p，且 block⊆mask，故其最小位也为 p。所有通过原 energy 判定的 block 恰好在 `feasible_by_low[p]`，过滤子集后集合相同。目录按 block 递减排列，与原 `s=(s−1)&rest` 的筛选后顺序相同。对 mask 归纳：初值相同，所读更小 mask 的 best 相同，更新加法、严格比较、limit 判定相同，故 best/choice/transitions 相同。该证明覆盖两分支与空集合；它不是已经运行过的二进制输出对照。

本地只执行文档/AST/字节/补丁/回滚检查。`<REMOVED_ENDPOINT>_ENGINEERING.py` 是待执行的独立通用 DP 输入等价性及7个有限 frontier 表核对脚本；不 import 整个旧 solver，不生成地图、评分物理路线或调用作者/ALNS。它只在 <COMPUTE_HOST> 执行。<COMPUTE_HOST> 旧端点本次仍在 TCP 阶段拒绝连接，所以尚无 BASELINE/MODIFIED/ROLLBACK 科研或内核运行收据，不能报告提速或正确性实测 PASS。

## 先例与 G0 边界

Paradiso、Roberti、Laganà、Dullaert，*Operations Research* 68(1), 180–198 (2020)，DOI [10.1287/opre.2019.1874](https://doi.org/10.1287/opre.2019.1874)。本轮实际读取机构库的正式版 PDF，§3 的 trip/journey 表述和 exact-once 约束、§4 的 structure 表述，以及 §8.4 的电池标签；未读完整补充材料。它已覆盖多趟的列表示、覆盖/排程约束与电池资源枚举，其载荷相关能耗和时间窗不同于本域。不能将普通 trip-cover、有限电量枚举或按合格列加速称本项目独立算法创新。

全文来源：[VU 作者机构存档](https://research.vu.nl/ws/portalfiles/portal/122160279/opre.2019.1874_An_exact_solution_framework_for_multitrip_vehiclerouting_problems_with_time_windows.pdf)。本次两条定向搜索亦命中 bounded-size set partition 与 routing enumeration 先例；只记检索记录，不把搜索摘要当全文核实。全网首创性尚未建立。

G0/G3 仍未过；此包不新增一个泛化 RL 公式候选，也不据此启动训练。当前结构结果的作用是复用/加速精确参考，帮助未来在合格人口中测清可改进空间，继而针对确有空间的分组困难设计物理路线学习步骤。

## 下一项有界工作与用户依赖

收到可连接的 GPUHome SSH host/port 后先只读核查 <COMPUTE_HOST> 身份、运行进程及持久卷；不停止不明进程。然后按 `ENGINEERING_PROTOCOL.md` 运行一次内核对照，保留全部输入/结果和失败；不重跑历史物理测试或旧人口。内核通过仍不提升 G0/G3，不自动放大旧 max_n_exact 或启动 408 map-wind。

本轮新增地图、作者/ALNS 求解、模型、训练、checkpoint、消融、Formal、子 agent 均为 0。两主科学 STATE、原 source、40 身份/126 比较、24/24 校准、暴露 DEV 和旧失败保持。当前只缺连接信息，无新增科学合同决策。

## 连接恢复后的实际验收（2026-11-14）

原端点认证恢复，hostname 为 <COMPUTE_HOST>，Python3.10.12，持久卷约41GiB可用；只读进程清单未见科研作业。新隔离目录 `<EXECUTION_PATH>`，传输前登记 INTENT，逐文件SHA一致后只执行冻结的BASELINE/MODIFIED/独立复制后ROLLBACK；无重跑、无repair、无扩输入。

三phase各35/35通用内核输入的best/choice/transitions完全相同，故限定等价性通过；故意删多目标块的负控被抓。7个有限frontier表中，原版有3个会超过已知可行最优值的错误下界，修改版7/7与独立有限组合枚举一致；原版/回滚版如实记录BOUND_STATUS=KNOWN_FAILURE，不当下界语义通过。回滚hash等于原始source，原/回滚完整表结果一致，主修改保留。

BASELINE/MODIFIED/RESTORE_COPY/ROLLBACK均exit0；总child CPU0.499794s，phase wall合计0.500703s，未超45/75秒上限。收据取回并读取核对，见server_evidence/RESUME1/runs。此为局部内核/聚合正确性证据，不是恒风完整物理/精确solver验收、速度结论、科学质量或RL效果。原断连与全部旧失败保留。当前无需用户提供连接信息，G0/G3仍未过。
