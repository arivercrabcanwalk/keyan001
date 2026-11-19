# Station split-DP：独立数学审计初判（交叉交流前冻结）

日期：2026-11-03。角色：独立反方。范围：固定站点、站型及 target→station 归属；允许同站 DABS 内 LD/SD 重新分派、每机多趟及趟内重排。本文为公式与源码静态审计，没有运行求解器、evaluator 或训练，没有读取本轮 station-DP 协议或其他代理的 station-DP 交叉意见。

## 1. 输入、输出与不变量

输入为原始 `Instance`、冻结完整可行基准解以及由该解导出的站点目标集合 T_s。站点索引、原目标 ID、station_types、实例 hash、参数全部保持。T_s 必须等于该站全部非空 trips 中目标的并集，且与其他站集合不交；重复或缺失不是待优化对象，应判输入失败。

- kind=0：仅允许 T_s 为空，两个槽都空；不可把目标转往别站。
- kind=1 (SABS)：仅 SD 即 di=1 可非空；LD 即 di=0 必须空。
- kind=2 (DABS)：LD 即 di=0 与 SD 即 di=1 均可使用，也均可为空。
- 容量由槽决定：di=0 为 large_battery，di=1 为 small_battery。
- **coverage 和累计 duty 由站型决定，不由 drone 槽决定。** SABS 使用 small_radius/small_duration；DABS 的两个槽均使用 large_radius/large_duration。DABS 内 SD 不应错误套 small_duration 或 small_radius。

输出需为完整 schema 解和逐站证据；不能只输出最小 operating 数字。解保持固定费用、每目标恰好一次及原站归属，并交由独立 evaluator 重算原目标。

## 2. 趟内最短路为何足以判能量与时间

固定站点 s、非空目标子集 Q。令 L_s(Q) 为从 s 出发、访问 Q 中每目标恰好一次并回到 s 的最短闭合 Hamilton tour 长度。令

    service(Q) = Σ(i∈Q) service_i
    target_energy(Q) = Σ(i∈Q) energy_i
    τ_s(Q) = L_s(Q)/speed + service(Q)
    e_s(Q) = flight_energy*L_s(Q)/speed + target_energy(Q).

原模型中 speed>0，flight_energy≥0，service 和 energy 非负；服务与目标能耗总和只依赖集合。长度越短，飞行时间、总运行时间和能耗均不增。因此：

1. 任一给定 Q 的可行趟均可换成最短闭合 tour，时间与能耗不会增加。
2. 最短闭合 tour 若超过槽电池容量，则 Q 不存在更长但电池可行的顺序；flight_energy=0 时能量与长度无关，结论仍成立。
3. 最短闭合 tour 若电池可行，它同时最小化该 Q 的运行时间和能耗，不存在需保留的能量—时间 Pareto 折中。

Held–Karp 状态 H[M,j] 为 s→M 全部目标→j 的最短开路径；基例 H[{j},j]=d(s,j)，递推 H[M,j]=min(k∈M\{j}) H[M\{j},k]+d(k,j)，闭合值 L_s(M)=min(j∈M) H[M,j]+d(j,s)。保留 predecessor 和最终 endpoint 才能回溯真实原目标 ID 列表。

该论证依赖当前模型中相同速度/飞行耗能系数、无时间窗/载荷相关航耗/同步/顺序相关服务/固定单趟代价等。不得未经再审扩展到含这些约束的其他模型。

## 3. 单槽 trip-partition DP

令 d 为合法槽，容量 B_d，累计 duty 上限 D_s。可行非空 trip mask 集为

    Q_d = {Q≠∅ : 所有 i∈Q 满足站型 coverage 且 e_s(Q)≤B_d+ε}.

定义 F_d(∅)=0。对非空 A，取其中固定 pivot a(A)，递推

    F_d(A) = min [τ_s(Q) + F_d(A\Q)]
                  Q⊆A, a(A)∈Q, Q∈Q_d.

无可行分割时 F_d(A)=+∞。pivot 只去掉无关的 trip 排列对称性，不删分区。保存每个 A 选中的 Q 以回溯全部非空 trips。

**cost 与 duty 是同一个总运行分钟数，不需要二维 Pareto label。** 对同一 A，一个较小 F 同时更省成本和 duty；一个更大的 partial 值不会因其他资源维度而变优。单槽可行值为

    f_d(A) = F_d(A), 若 F_d(A)≤D_s+ε；否则 +∞。

因后续 trip 时间非负，可将超过 duty 的中间状态剪枝；但只在完整数学/数值契约下用相同阈值，不能每次 RETURN 重置累计 duty，也不能每趟分别获得一次 ε 的额外 duty。

空槽 f_d(∅)=0，必须显式支持，不能沿用旧代码 n=0 返回 None 的语义。正 energy 目标保证非空 mask 真正包含需服务目标，空 trip 不参与 DP。

## 4. 同站 LD/SD split 与完整性证明

SABS 的站内最小运行时间为 f_SD(T_s)，LD 留空。

DABS 的站内最小运行时间为

    Z_s = min(A⊆T_s) f_LD(A) + f_SD(T_s\A).

枚举包括 A=∅ 和 A=T_s，允许两个端点方案。两槽分别满足各自 battery 和累计 duty；不能仅用总 duty≤2D_s 替代各槽 duty。

完整性：任一固定站型/归属的可行站解确定唯一的 LD 目标集合 A 及其补集，每槽的 trips 构成该集合的一份分区。各趟换为最短闭合 tour 不增加资源；分区 DP 最多更优，因此枚举值不大于任一可行解。反之，任一有限 DP 值均能回溯为覆盖 A/补集且无重复的完整 trips，各趟与各槽资源满足条件，所以枚举值可实现。两方向给出理想实数/明确定义容差模型中的固定站域最优性。

当前原模型不同站之间无共享时间/电池/车辆资源，固定 target→station 后，整图的站内可行集合是笛卡尔积，原目标可加，因此所有站均被完整求解时，逐站最小值拼接给出**固定站点/站型/目标站归属域**的最优解，而非完整 LRPHSD 全局最优。

结构自检：相同 DABS duty 下 LD battery≥SD battery，故任一 SD 可行 trip 亦 LD 可行，F_LD(A)≤F_SD(A)。这不代表 LD 必能接下全部 T_s，因为累计 duty 仍有上限；不得把双槽退化为单槽而跳过 split。

## 5. 原目标、完整 witness 与机会统计

原目标为

    C = Σ_s fixed_cost(kind_s) + time_cost*Σ_s operating_minutes_s.

固定 station_types 意味着所有开站/无人机固定费用不变，即使某槽空闲也不退固定费用。目标恰好一次服务意味着 Σservice 亦固定，但实现应保留它并由 evaluator 重算。time_cost 可为 0，此时路线改进不等于原目标改进。

每个输出至少保存：原始输入路径/hash、参数、完整基准/输出解、各站 T_s 与 n、种类/合法槽、每槽分配、trip masks 与原目标序列、长度/服务/能量/累计 duty、HK/partition/split 状态与耗时、独立完整 evaluator 的 feasible/cost/issues、总墙钟及失败。该参照的 DP 计算与生成成本必须记录，不能冒充 6s/12s 同预算 solver。

主统计单位是地图，主效应以完整原目标作分母，例如 (C_baseline−C_DP)/C_baseline。站点/槽/cell 不冒充独立地图；多个种子/预算先按冻结规则地图内聚合。若要称 oracle 上限，必须对应冻结完整物理域且所有相关站均完整求解，并明确实数/数值语义。此旧暴露数据诊断不构成创新、RL效果、全新开发或 Formal。

## 6. ≤12 阈值与 unresolved 边界

阈值按 **站的并集 |T_s|≤12**，不是按单槽大小。对 >12 的站全部保留并标 unresolved，不得省略记录、分别按当前槽小集合求解后称 station-exact，或在统计时从分母移除。

- 一张图所有相关站均 complete 且有效重建/重评分，才可称 complete fixed-station DP reference。
- 任一相关站 >12 或失败，则该整图带 unresolved；可把该站保留原基准 routes 并与小站的可行 DP 解拼接，得到实际可实现的改善下界，但不是该图机会的上界或零空间证明。
- 不得将 unresolved 站强行视为无改善，也不得由小站均值推断全部图过/不过 0.3%。
- HK 复杂度 O(n²2^n)，锚定 partition 各槽 O(3^n)，split O(2^n)；应对外记录工程墙钟而非只用理论复杂度断言可落在 6s/12s。

## 7. 1e-7、浮点与 exact 声明

当前 evaluator 对 coverage、每趟 energy、每槽累计 duty 使用 `> limit+1e-7` 判失败。DP 阈值应明确使用 ε=1e-7，且每个总约束仅比较一次；不得用额外 `1e-7` 的 tie/pruning 规则把真正更短状态丢掉。

HK 用 hypot/逐边除 speed，而 evaluator 用 sqrt、先总长度后除 speed；这些在实数下相同，但生产 IEEE 次序/舍入可能不同。数学完整性证明不自动等于全部 IEEE 路径比较的 bit-exact 全局最优证明。需要保留：

1. 使用完整 evaluator 验证回溯解可行并重算原目标；DP 标量与 evaluator 不同则记录数值残差及 slack，不取代 evaluator 值。
2. 以 evaluator 的距离/求和顺序对输出候选重新计算；边界不足、HK 最短值与重评分不一致时标 numerical-unresolved，而不是默默放宽阈值/修复后称 exact。
3. 对清晰远离边界、正确实现和穷尽状态的结果可报告 fixed-domain DP reference；严格实数证书需另给严谨算术，尚未建立时保留此边界，不新造“完美形式证书”阻塞已有工程参照。
4. 输出比有效基准更差且超过冻结对账误差，或错误宣告可行基准域 infeasible，是实现/数值失败而非负 headroom。

## 8. 独立初判

公式上 **CONDITIONALLY PASS 作为标准非RL固定站域机会/强参照**：HK + 两槽 subset partition + station split 在上述模型和阈值语义下完整。它不是原创机制，不是 G0/G4 的阳性结论。当前没有看到本轮协议、实现或结果，因此工程正确性、样本冻结、全地图覆盖、机会大小和同预算效果全部尚未判定。

本阶段只写数学审计；新增 solver/evaluator/训练/Formal 调用均为 0。冻结之后才接收本轮协议并实际交叉质询。
