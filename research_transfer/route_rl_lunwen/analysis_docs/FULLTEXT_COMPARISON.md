# LRPHSD 相关工作逐项核查与创新性判定

日期：2026-11-02。目的：判断现有 `Global Assignment` 接收站扩域是否足以支撑独立非 RL 方法论文，并给下一轮机制研究划定先行工作边界。此文档只把已核验的正文当作正文证据；题名、摘要和元数据不能证明一个机制不存在。

## 1. 证据等级与检索范围

- **F1：全文已核验。** Liu 2026 正式 PDF 与补充材料、本地 DPTARL 正式 PDF、Frontiers 2026 出版社完整 HTML；Liu 官方 Java `reference/java/official_source/RoutingOperator.java` 的 repair 循环也已核验。
- **F2：出版元数据/摘要已核验，未取得全文。** Cai 2025 Omega、ESWA 2026 fixed-nest hybrid inspection、RESS 2026 nest location、TRE 2026 distributed RL、RLHEA 2024、Q-HGALNS 2026、QL-IPSO-ALNS/JIII 2026、COR 2022 depot-location ALNS、Rave 2025、He 2025。F2 只能支持题目或摘要明确说出的正面事实，不能支持“没有某约束/操作”的反面结论。
- 检索来源：本地 PDF 和服务器官方 Java/冻结实验；Crossref DOI 记录、OpenAlex OA 状态、出版社公开全文。OpenAlex 关键字搜索曾返回 HTTP 429，随后用已知 DOI 单篇检索。没有把未获取的封闭全文冒充已读。
- **特别提醒：** Cai 文章 DOI 含 `2024`，Crossref 的 DOI 创建日期为 2024-08-10，OpenAlex 的 `publication_date` 也为该日；正式期刊卷 130 日期为 2025-01，引用时写 *Omega* 130 (2025) 103172。RESS 文章的 Crossref DOI 创建日期为 2026-04-30，OpenAlex `publication_date` 为同日，但 Crossref 的卷 275 `published` 字段为 2026-11。这是在线/卷期元数据口径差别，不能说它在 2026-11-02 尚未在线；投稿时再核对出版社最终书目信息。

## 2. 决定性核查：Global Assignment 与 Liu 原算法

**Liu 原文。** §4.3.2（印刷页 292；本地 `audit/papers/Liu2026.txt` 行 542–566）明确写 `loadBalanceInsertion` 在 *all stations* 的 drone routes 上探索全部可行插入位置；`prioritizedInsertion` 先遍历空闲站，再遍历空闲无人机，之后插入已有路线。§4.2.2（印刷页 291，行 456–462）已有跨站无人机之间的目标 swap。§4.2.1（印刷页 291，行 445–453）已有开/关/升级/降级站操作。因此“跨站分配”“全开站候选接收域”“跨机/跨趟交换”不能单独标为本项目首创。

**官方 Java。** 服务器冻结的 `reference/java/official_source/RoutingOperator.java`，方法 `greedyInsertMinCost` 约 890–945 行，对每个 removed node 从 `stationIndex=0` 遍历到全部 station、跳过未开站、验证 coverage，然后遍历该站全部 drone routes。其他 repair 例程也有类似全站循环。由此可确认全局接收域不只是论文文字意图，官方实现至少在 cheapest-insertion 分支确实实现了它。

**项目代码差异。** Formal v4 `carl/neighborhood.py` 的 `gen_assignment` 约 327–360 行先挑一个源站和目标站，并以 `1 << dst` 构造局部接收掩码；`apply_move` 约 919–953 行在 `repair_scope_mode='global_assignment'` 时，把 Assignment 的接收掩码改为变更后所有开放站，并清空 drone mask，继续调用原有 `repair_scoped`。它扩大搜索域，但不是一个在 Liu 之前未见的全局插入思想。实现细节和候选顺序可能不同于官方 Java；“范围相同”不等于逐轨迹等价，需由复现线定量检验。

**实验证据与限制。** Formal v4 冻结结果：30 张主地图、10 个求解种子、6/12 秒，M2 Global Assignment 相对 M2 Local 的配对成本差分别为 -0.1010%/-0.1145%，Holm p=0.028609/0.006819；相对 M0 分别为 -0.9709%/-0.3364%。但 M2 Global Assignment 与 M2 Global NoJoint 的差异不显著，Holm p=0.9397（两个预算）。这些是有价值的实现/性能结果，不构成 `Global Assignment` 独立方法新颖性的证据。Formal v4 不是官方 Java 与 Liu 论文表格的等协议复现；M0 的身份也应据复现结果准确命名。

**判定：NO-GO。** 以“Global Assignment receiver-scope 是本文新算法贡献”为主张，当前不够支撑独立非 RL 方法论文。它可以被准确写成“修正或拓宽某一项目实现的接收域后，在冻结实验中得到改进”，或作为更强新机制的基线和消融；不能写成“首次全局分配/首次跨站联合优化”。这个判断只依赖已核验的 Liu 正文和官方 Java，不因 Cai 等封闭全文暂缺而改变。

## 3. 逐篇证据矩阵

| 文献与获取级别 | 模型/决策、约束与算法的可核验事实 | 与 LRPHSD / Global Assignment 的关系 | 原文定位与仍需核查项 |
|---|---|---|---|
| **Liu, Hu & Cheng, EJOR 334 (2026), 285–300; F1.** DOI [10.1016/j.ejor.2026.04.046](https://doi.org/10.1016/j.ejor.2026.04.046) | 两种站型 SABS/DABS、SD/LD、覆盖、多趟、电量及累计工作时间；TSALNS 包含开关站、跨站 swap、destroy-repair、全站可行插入。 | **同一原问题与最直接算法先例。** `Global Assignment` 的扩大接收域与官方 repair 原有范围高度重叠。 | §3–4、印刷页 288–292；尤其 §4.2.1、§4.2.2、§4.3.2；本地 `audit/papers/Liu2026.pdf` 和 `Liu2026_supplement.pdf`。 |
| **Cai et al., Omega 130 (2025) 103172; F2.** DOI [10.1016/j.omega.2024.103172](https://doi.org/10.1016/j.omega.2024.103172) | Liu §2.3 将其列为最接近前作：自动换电站巡检、coverage 与 operation-time；Cai 的 RePEc 摘要明确同质 ABSS/无人机、站点选择与目标分配/路线设计，用 LBBD（BC + stabilized column generation + BP）求解。 | 站点式巡检、分配和路线设计已存在。Cai 不是已证实的 ALNS repair 直接对照，但其站点/分配机制仍须看全文。 | Liu §2.3 印刷页 287；Cai 正文未取到，OpenAlex `closed`、RePEc 明示 ScienceDirect subscribers only。不得从摘要推断其没有特定跨站机制。 |
| **Sun et al., DPTARL, EAAI 179 (2026) 115219; F1.** DOI [10.1016/j.engappai.2026.115219](https://doi.org/10.1016/j.engappai.2026.115219) | 固定单巢、28 天多频次巡检；MILP 目标为路径长度；动作访问目标或回巢；DSP 按周期和“访问+服务+返航”能量掩码；A2C/TAA。 | 对 Route-RL 的逐目标决策、RETURN、掩码和注意力形成直接先例；不是 LRPHSD 的可直接等目标数值基线。 | 正式 PDF §3.2（印刷页 4，式 1–14）、§4.1–4.2（页 5，式 15–24）；本地 `audit/papers/DPTARL.pdf`。 |
| **Zhang et al., Frontiers in Future Transportation 7 (2026); F1.** DOI [10.3389/ffutr.2026.1760027](https://doi.org/10.3389/ffutr.2026.1760027) | S/M/L 站型与对应 UAV，覆盖约束；选址后多站、多趟、能源/充电调度；重叠覆盖目标由瓶颈站迁往其他可行站，受影响 routes 重新 pack。 | **跨站分配 + 受影响多趟路线重构已有明确先例。** 不同点是太阳能/充电、makespan，且单个 nest-type 配同类 UAV；不能笼统声称“首次跨站联合修复”。 | 出版社开放全文 §2.1–2.2、§3.2、§4.2（Cross-tower reassignment）、§5.2.2；§4.2 明确 `one tower at a time` 与 `affected routes are repacked`。 |
| **ESWA 313 (2026) 131625; F2.** DOI [10.1016/j.eswa.2026.131625](https://doi.org/10.1016/j.eswa.2026.131625) | 题名确认固定巢站的变电站/输电塔/配电杆混合巡检任务分配与路线规划；公开摘要/片段称 two-tier ALNS。 | 缩小“固定站+混合巡检+联合分配路线”可宣称空间。 | 全文未取到，OpenAlex `closed`；站型、无人机配置、跨站 repair 范围、基线强度均待原文核查。 |
| **RESS 275 (2026) 112785; F2.** DOI [10.1016/j.ress.2026.112785](https://doi.org/10.1016/j.ress.2026.112785) | 题名确认可靠 UAV nest location 与 multi-level assignment，用于电力设施巡检。 | 多层站点分配不是空白领域。 | 全文未取到，OpenAlex `closed`；Crossref DOI 创建 2026-04-30、卷期发表 2026-11；是否含路由/异构站型/局部修复，不能据题名否定。 |
| **TRE 212 (2026) 104928; F2.** DOI [10.1016/j.tre.2026.104928](https://doi.org/10.1016/j.tre.2026.104928) | 题名确认充电坞选址和巡逻路线，在认知不确定性下使用 distributed RL。 | “RL 参与站点与路线决策”本身已有先例。 | 全文未取到，OpenAlex `closed`；状态/动作/约束与 LRPHSD 的差异待核查。 |
| **RLHEA, COR (2024) 106758; F2.** DOI [10.1016/j.cor.2024.106758](https://doi.org/10.1016/j.cor.2024.106758) | 题名确认为 latency LRP 的 RL-guided hybrid evolutionary algorithm。 | 泛化的“RL 指导 LRP 搜索”不是新颖性。 | 全文未核验；具体 VND 选择及比较基线需原文核实，不沿用旧规划中的未经复核描述。 |
| **Q-HGALNS, Systems 14(10) (2026) 1289; F2.** DOI [10.3390/systems14101289](https://doi.org/10.3390/systems14101289) | Crossref 摘要确认多卡车多无人机配送、Q-learning 依状态选 12 个 destroy-repair 动作；有 NoQ/NoLS/ALNS-AW 消融。 | 普通 Q-learning + ALNS 算子选择已不是充分创新。 | 出版社 HTML 访问返回 403；全文尚未核验，摘要证据不用于推断其没有跨层机制。 |
| **JIII 2026 101224; F2.** DOI [10.1016/j.jii.2026.101224](https://doi.org/10.1016/j.jii.2026.101224) | 题名确认为灾后多卡车多无人机配送的 Q-learning hybrid heuristic。 | 进一步约束“Q-learning 控制启发式”主张。 | 全文未取到，OpenAlex `closed`；旧规划的“QL-IPSO-ALNS”简称与正式书目信息未逐字确认，应以 DOI/正式题名为准。 |
| **COR 2022 105856; F2.** DOI [10.1016/j.cor.2022.105856](https://doi.org/10.1016/j.cor.2022.105856) | 题名确认为带 depot location decisions 的 hybrid ALNS。 | 选址与路线互相作用的 ALNS 不是新颖性；关闭站并重分配目标的具体实现需全文比较。 | 全文未取到，OpenAlex `closed`。 |
| **He et al., INFORMS JOC (2025); F2.** DOI [10.1287/ijoc.2023.0416](https://doi.org/10.1287/ijoc.2023.0416)；**Rave & Fontaine, EJOR 323 (2025); F2.** DOI [10.1016/j.ejor.2024.11.040](https://doi.org/10.1016/j.ejor.2024.11.040)；**Sobhanan et al., Transp. Sci. 59 (2025); F2.** DOI [10.1287/trsc.2023.0369](https://doi.org/10.1287/trsc.2023.0369) | Liu 正文把这些列入算法比较或相关工作；其问题分别为容量 LRP、货运自行车时间窗/载重时间 LRP、神经成本预测的层级 VRP。 | 新方法需在同问题可移植条件下纳入强对照，但不能简单拿不同目标的公开数字排序。 | Liu 正文 §5.2 与参考文献；三篇全文未系统阅读。Sobhanan 有 arXiv OA 版本，但当前报告不把未读版本当已核验。 |

## 4. 候选新机制的先行工作风险

`multi-receiver station closure + bounded affected-subproblem repair` 目前只能作为**待证假说**：关闭一个 SABS/DABS 时，把其目标分散迁往多个覆盖可行的接收站，联合重建这些站内 SD/LD 的多趟路线，并以受影响子问题范围、可行性与计算成本作精确定义。

- Liu §4.2.1 已有 closable station close，§4.3.2 已有全站 repair；即使官方具体 close 只选一个接收站，“多接收站”也可能只是已有两个机制的组合，不能从代码缺口直接推导论文创新。
- Frontiers §4.2 已有重叠覆盖目标向替代站迁移、affected routes repack；其每次单目标且固定选址，但可反复迭代。故“受影响路线局部重建”也不能单独主张首次。
- COR 2022 depot-location ALNS、Cai 2025、RESS 2026 的全文尚未取到；它们可能包含类似多接收站关闭或局部 repair。当前不能证明文献空白。
- 最低实验门槛：同一 LRPHSD 目标与约束、同一初始化/校验器/预算，对比 Liu 官方全站 repair、单接收站 close、分批单目标迁移、完整重建与拟议 bounded repair；测最终成本、可行率、每次候选耗时、受影响站/目标数、搜索迭代数及空间分布泛化。若只是更快实现已有 repair，而性能或复杂度无明确增量，则只能作为工程优化。

## 5. 论文方向建议

1. **当前 Global Assignment 单独成稿：No-Go。** 有实证改善，但主机制先于本项目存在于 Liu 原文和 Java。不能依赖尚未获取的封闭全文来支持“首次”或“明显超越先行方法”。
2. **当前 CA-RL 主张：No-Go。** 宏控制器未超强非 RL；Route-RL Stage A 亦未超 route-only ALNS。DPTARL 和其他学习型搜索进一步收窄一般 RL 技术的新颖性。
3. **可继续的非 RL 研究题：条件式多接收站关闭/异构无人机受影响子问题重建。** 先完成上节全文缺口与算法定义，再在未用于 Formal v4 调参的新开发集做同算子、同预算消融。只有显示独立、稳定、可解释的收益后，再冻结新测试集与论文贡献。不要把 Formal v4 重开为调参集。
4. **复现论文价值：** 完成参数忠实度、可行性和误差来源的审稿级基线，可作为后续论文可复现材料或独立复现说明；它本身不等同新算法论文。

## 6. 全文缺口与获得路径

优先顺序：Cai Omega → COR 2022 depot-location ALNS → ESWA 2026 → RESS 2026 → TRE 2026 → RLHEA → He/Rave/Sobhanan。优先出版社开放全文、作者机构仓储/预印本、已获授权的机构访问；保存版本、页码、下载来源和 SHA256。当前 Crossref/OpenAlex 显示前五篇多为 `closed`，本地与服务器已知项目目录未发现这些 PDF。逐条查询和下一步获取入口见 `fulltext_retrieval_log_20261102.md`。获得每篇全文后更新上表的模型变量、约束、邻域、接收域和实证基线；未获得之前保留 F2，不写缺失性断言。
