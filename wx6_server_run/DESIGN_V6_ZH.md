# DESIGN_V6 — WX-E6 / RL6：v5 的独立成文升级版（论文 1，扩展 Liu et al., EJOR 2026 LRPHSD）

> 配套文件：`PREREG_v6.md`（预注册：门槛、Holm 族、天号、种子、选择规则、ETA）、`docs/PROTOCOL_FAIR_V6_ZH.md`（审稿人向公平对照协议）、
> `v6/fairproto.py`（协议的可复用实现）、`README_ZH.md`（运行命令）。所有时间为 America/Phoenix (MST)。

## 0. 一句话
在 Liu, Hu & Cheng (EJOR 334, 2026, 285–300) 的 LRPHSD（异构电池换电站 SABS/DABS 选址 + 多趟巡检路径，TSALNS 求解）之上，
加入**天气不确定 + 动态紧急故障点**的执行阶段（WX-E）。论文 1 的贡献：(i) 一个**选址无关的严格 100 % 完成**评测设定（WX-E6），
使作者方法本身就能 100 % 完成；(ii) 作者算法的**最小侵入式适配族**（TSALNS-Cov / TSR / PAD / TSCr10）与执行规则族；
(iii) **RL6**：以公平 rollout 为老师的近似策略迭代 + 蒸馏 + 约束 ES 的 1 ms 调度策略；(iv) 预注册的公平对照协议。

## 1. 文献调研（2023–2026 为主，按设计决策组织）
| 主题 | 代表工作 | 对 v6 的直接影响 |
|---|---|---|
| 基础问题 | Liu, Hu, Cheng 2026 EJOR（LRPHSD、TSALNS，SABS 单机 / DABS 双异构机） | 静态层完全复用作者模型、实例（test 50 张）与 Java 源码；只在作者自己的可行性测试里加一个约束 |
| 无人机设施选址 | Dukkanci, Campbell & Kara 2024 EJOR 316(2) 综述（drone facility location）；Toregas 1971（集合覆盖 LSCP）；Church & ReVelle 1974（MCLP）；固定半径 UAV 集合覆盖（C&OR 2020） | 应急可达性在选址文献里是**覆盖约束**而非事后补丁 → TSALNS-Cov 把有限支撑集 Ω 的覆盖写进作者的 `LocationOperator.isFeasible`；TSR 用精确最小费用集合覆盖修补 |
| SDVRP 的 RL | Hildebrandt, Thomas & Ulmer 2023 C&OR 150（综述）；Ulmer et al. 2018/2020（offline–online ADP、SDVRP 建模） | RL 最有效的位置是"在强组合层之上做评估/调度"，而不是端到端替代 MIP/ALNS → RL6 只做执行期调度（LAUNCH/HOLD/SERVE），路线来自作者算法 |
| 模仿 anticipatory/rollout 专家 | Baty et al. 2024 TS（EURO-NeurIPS 2022 动态 VRPTW 冠军：模仿全知/预期专家 + CO 层）；Greif et al. 2024（Anticipative-DAgger，动态库存路径）；Kool et al. 2023 PMLR（竞赛）；Ross et al. 2011（DAgger）；Anthony et al. 2017 / Silver et al. 2017（expert iteration） | v5 直接用 ES 在 1.6 万维参数上搜索，信用分配弱；v6 先用**公平 rollout 老师**（只用可观测信息，非全知）生成 Q 值标签，软目标蒸馏，DAgger 第二轮纠正分布偏移，最后 ES 只做微调 |
| Rollout / 近似策略迭代 | Bertsekas 2019/2021（Rollout, Policy Iteration & Distributed RL）；Bertsekas 2022（Lessons from AlphaZero）；Ulmer 2018 改进保证 | 基策略为确定性规则时 rollout 不劣于基策略 → 老师在 RL5 之上做一步改进，学生继承改进且 1 ms 推理 |
| 约束 RL | Altman 1999（CMDP）；Tessler et al. 2019（RCPO）；Stooke et al. 2020（PID Lagrangian）；Alshiekh et al. 2018（shielding） | v5 的加班高于 A1/N1：对偶上升步长不随尺度变化、振荡。v6 用**相对残差 PID-Lagrangian**（目标 OT ≤ 0.9·OT_SB）+ 硬"班次护盾"（可开关、消融） |
| ES | Salimans et al. 2017（OpenAI-ES） | 保留：对偶采样、CRN、中心秩；固定迭代数 = 等算力 |
| ML-for-VRP 的公平测试 | Accorsi, Lodi & Vigo 2022 ORL 50(2)（调参用独立数据、报告总时间、多次运行均值 + Wilcoxon）；Ulmer et al. 2020 EURO J Transp Logist（SDVRP 建模规范） | 预注册、dev/test 分离、等信息、时延分级、地图级 Wilcoxon + Holm + 天聚类 + 交叉 bootstrap、每种子单独报告 |
| 无人机应急调度 RL | TRE 2025（卡车–无人机多智能体 DRL 应急响应）；IEEE TII 2025（多 UAV 重规划，上层部署 + 下层 MARL 指派，911 数据） | 同一"上层选址/部署 + 下层 RL 调度"结构；我们区别在：上层就是作者的精确/元启发式模型，下层与之严格同计划对比 |

## 2. v5 的弱点 → v6 的整改（逐条）
| v5 弱点 | 根因（诊断） | v6 整改 |
|---|---|---|
| **作者方法到不了严格 100 %**（e2e_v2：TS 计划严格完成 < 1） | 全部缺口来自**背景故障请求**：184 个"某候选站可覆盖但计划没开"，192 个"任何候选站都覆盖不到"；风暴目标点总被覆盖 | **WX-E6 生成器**：每张图有限的、与计划无关的故障易发支撑集 Ω = 目标 ∪ 每目标 K=4 个抖动点（N(0,500 m)，种子 = 实例 sha256），抖动点重抽直到被某候选 DABS 覆盖；背景请求只从 Ω 抽 → n_unservable_all ≡ 0，严格完成率**分母与选址无关** |
| 作者计划只覆盖目标，不保证覆盖 Ω | 作者模型里没有应急覆盖约束 | **TSALNS-Cov**：在作者自己的位置可行性函数里加 covOK(Ω)，加作者风格的贪心 covInit；Python 精确 MILP 修补作安全网（计数并报告，冒烟/试点中 0 次） |
| 增益可能来自"多开站" | 不同方法跑不同计划 | **同计划执行**：所有执行方法跑同一份计划（#DABS、固定成本逐行相同，`check_parity` 校验）；选址变体 TSR/PAD/TSCr10 作为独立计划集，**全部方法**在其上重跑 |
| seed 2 不显著 | ES 从 POMO 初始化，单种子方差大 | 老师蒸馏给所有种子相同的强初始化（bootstrap 种子），ES 只微调；**5 种子**；主结论要求 ≥4/5 种子各自确认 |
| 加班高于 A1/POMO/N1 | 绝对/固定步长对偶不收敛；HOLD 拖到 H 之后 | 相对残差 PID-Lagrangian（clip [−1,2]），选择规则要求 dev OT ≤ SB；可选班次护盾（若 t+DT+剩余计划 > H 则屏蔽 HOLD）；H2 把加班作为对 SB 的**优越性**检验 |
| 去掉紧急特征的消融反而更好 | v5 紧急特征噪声大、ES 难利用 | 新增可观测的 anticipatory/协调特征（期望紧急数、独占覆盖、竞争者 ETA 优势、加班影响），老师标签直接监督其用途；消融 nf/ne 用**同管线**（同老师数据、同 ES 预算）3 种子 |
| P4a fc_y bug、P4b 弱 | 外加实验与主线不同代码路径 | 删除 P4a/P4b；改为预注册的稳健性 4 场景（stress / sigma15 / ncbias6 / uniform）+ 3 个选址变体，全走同一评测器 |
| Test-L 只有 10 张图 | — | Test-L = 30 张大图（G12_150 / G15_200 / G20_300 ×10）；新增 Test-G = 100 张新生成图；Test-M = 作者 50 图 × 100 新天 |
| 统计单薄 | — | 地图级 Wilcoxon + Holm（族预注册）、天聚类 Wilcoxon、地图×天交叉 bootstrap、rank-biserial；紧凑原始 CSV 全量上传 |

## 3. WX-E6 设定（所有方法相同）
- 静态层：作者 LRPHSD 实例；SABS 半径 4000 m（1 机），DABS 5000 m（2 异构机）。
- 执行层（wx2/sim.py，继承 v5 共享可行性层）：动作 LAUNCH / HOLD / SERVE0–2；备用机兜底、时间再平衡、最晚出发、URG_FORCE；
  H = 480 min，作业窗口 T_END = H + 240。
- 目标 **J5 = cost + 1·OT + 30·高优迟到分钟 + 10·普通迟到分钟 + 100·失败**；makespan 只进附录。
- 合成天气 only（WX-E 风场 + 预报/临近预报误差，σ 修正版）；场景键含 GEN_TAG，旧缓存不会混用。
- **Ω（wx2/omega.py）**：确定性（实例 sha256）、与任何计划无关；`write_cov_file` 给 Java、`uncovered(plan)` 给门槛检查。
  环境变量 WX_BG_MODE 可切回 v5 的旧背景（仅供复现 v5/e2e_v2 的缺口诊断，正式运行不使用）。稳健性场景：stress（λ 3.5, p_f 0.5）、
  sigma15（OU + 预报残差 ×1.5）、ncbias6（临近预报偏差 0.6 + 风暴移速 +30 %）、uniform（故障空间均匀）。

## 4. 作者方法适配族（审稿人最关心）
| 臂 | 构造 | 回答的问题 |
|---|---|---|
| **TSC = TSALNS-Cov（主计划）** | 作者 Java 原码 + 补丁：`LocationOperator.isFeasible` 增加 covOK(Ω)；`Main` 读取 `-Dcov=file`，`covInit` 贪心把初始解修成覆盖可行（作者 SA 不会离开不可行初始解）；其余算子、参数、时间预算不变（10 s；大图 30 s） | "如果作者当初就知道要覆盖 Ω，他的算法给出什么计划？"——最忠实的适配 |
| TS（原版） | 作者原码不改 | 只报告其 Ω 未覆盖数（不可能严格 100 %），不进入动态评测 |
| TSR | TS 计划 + 精确最小固定成本集合覆盖修补（scipy MILP，只升级/新开站，不动路线） | 事后修补 vs 内生约束：修补贵多少 |
| PAD | TS 计划所有站升级为 DABS | 最朴素的"多开站"上界（报告 #DABS、固定成本） |
| TSCr10 | TSALNS-Cov + 10 % 电池余量 | 作者式"静态鲁棒化"能否替代动态调度 |
| 执行规则（同计划） | A1 按计划立即执行、A2、N1_240、N6 网格 12 配置（dev 冻结 N6_best）、S:* 班次护盾版本、R_/Rfc_/RfcP（=Rfc600e15）事件触发 ALNS 全量重优化 | 作者计划 + 合理执行规则能做到多好 |
| SB | dev 上所有非 RL 臂中、严格 100 % 且 J5 最小者，测试前冻结 | 最强公平基线，H1/H2 的核心对手 |

**100 % 的保证链**：Ω 每点可被某候选 DABS 覆盖（生成时保证）→ 所有进入评测的计划覆盖 Ω（s2 门槛，失败即停）→ 共享层兜底
（备用机、再平衡、URG_FORCE）→ dev 上作者臂 A1/A2 严格 100 %（s3 author gate，失败 exit 3）→ 测试中任何臂 < 100 % 即在门槛表
标注，其其他指标不解释。本地试点（dev，TSR 计划）：A1/A2/N1/N6/Rfc/RL5 及其护盾版严格完成率均为 1.000，n_unservable_all = 0。
**本地门槛（推送前，作者 test 图 10 张 × 5 天 74000–74004，1050 次运行，0 错误）**：

| 计划集 | 静态目标 | 固定成本 | #DABS | A1 | A2 | N1_240 | N6_60_0.25 | S:N6 | Rfc_N6 | RL5 | 严格完成（全部臂） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TSC（主） | 697.5 | 256.6 | 5.4 | 1506 | 1517 | 1421 | 1509 | 1491 | 1374 | 1235 | 1.000 |
| TSR | 656.7+补站 | 258.2 | 5.5 | 1570 | 1595 | 1625 | 1561 | 1561 | 1456 | 1239 | 1.000 |
| PAD | 656.7+升级 | 312.5 | 7.2 | 1532 | 1539 | 1491 | 1494 | 1495 | 1292 | 1271 | 1.000 |
| TS（原版） | 656.7 | 211.3 | 4.1 | — 10/10 图 Ω 未覆盖 3–6 点，不进入动态评测 | | | | | | | — |

TSALNS-Cov 的 Python 修补 0/10（覆盖完全由作者算法内生满足）。表中 J5 为均值。

**"增益不来自多开站"的保证**：主检验所有臂执行同一 TSC 计划（#DABS、固定成本逐行相同）；RL6 不能改选址；选址变体上同样全方法重跑，
于是"选址效应"与"调度效应"被正交分解（表 7：同一方法跨计划集 vs 同一计划集跨方法）。

## 5. RL6 方法
1. **表示**：token 打分网络（numpy，共享 MLP 75→96→64→1，对每个合法动作 token = [全局 56 维, 动作 16 维, 类型 one-hot 3] 打分，
   softmax/argmax）；参数量小、1 ms 级、p99 ≈ 4 ms。特征全部可观测（feat6.py 文档列出每一维）。
2. **老师（API）**：在训练图 × 训练天上，以 roll-in 策略仿真；每个有 ≥2 合法动作的决策以概率 p 打标签：
   Q(s,a) = E_M=8 公平孪生未来[ J5(a，此后基策略) + λ·OT ]，CRN。第 0 轮基策略 = RL5（v5 最佳 1 ms 策略）；
   第 1 轮基策略与 roll-in = 第 0 轮学生，β = 0.5（DAgger 混合）。
3. **蒸馏**：软目标 CE（τ = 20，按 Q 差距加权），按 (map, day) 留出 10 % 选 teacher-regret 最小；每种子不同 bootstrap。
4. **约束 ES 微调**：F = J5 + λ_V·V + λ_OT·OT；λ_V ≥ 1000（严格完成违规），λ_OT 由相对残差 PID（kp 2.0, ki 0.2，残差 clip [−1,2]）
   驱动到 OT ≤ 0.9·OT_ref；固定 250 次迭代 × 20 对偶对 × 16 天，等算力。
5. **选择（dev）**：候选 {distilled, es_best, es_final}，要求严格 100 % 且 dev OT ≤ SB 的 dev OT，取 dev J5 最小。
6. **班次护盾**（SHIELD=1 默认；ns 变体为无护盾消融）：若 HOLD 后剩余计划无法在 H 内完成则屏蔽 HOLD——这是一条与 S:* 基线相同的
   硬规则，基线也有护盾版本，因此不构成不公平优势。
7. **时延分级**：RL6（1 ms 类）对所有实时基线；RL6R_100ms（以 RL6 为基策略的 100 ms rollout）对 N4fd_32_100ms（同时延 rollout，基策略 = SB 或 S:N6_best）。

## 6. 实验矩阵（详见 PREREG_v6 §6）
Test-M（作者 50 图 × 100 天，主）· Test-G（100 新图 × 30 天）· Test-L（30 大图 × 30 天）· 稳健性 4 场景 × 50 天 ·
选址变体 TSR / PAD / TSCr10 × 50 天 · 作业窗口 180/300 · 时延分级 rollout · 消融（noES、nf、ne、uc、ns）。

## 7. 风险与应对
- 若 RL6 在 dev 上不优于 SB：选择规则照常执行，结果如实报告（预注册不允许事后改设计）；论文 1 的贡献 (i)(ii)(iv) 不依赖 RL6 胜出。
- 老师预算（T0_H/T1_H 小时）到时即停，已有分片照常使用；分片可续跑。
- Java 不可用 → setup.sh 失败退出（作者基线是必需的，不允许跳过）。
