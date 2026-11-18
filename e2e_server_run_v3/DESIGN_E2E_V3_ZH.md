# E2E-RL v3 设计文档（论文二：纯端到端 RL，扩展 Liu et al. EJOR 2026 LRPHSD / TSALNS）

> 本文件面向审稿人与实验执行者。RL 方法内部**不调用作者的 ALNS/TSALNS 任何算子**；TSALNS 只作为对照组出现。
> 所有天气为合成天气；所有 v3 新建文件位于 `e2e_server_run_v3/`，不修改用户原始代码/检查点。

## 0. v2 结论与 v3 必须修复的问题

| v2 问题 | 证据 | v3 对策 |
|---|---|---|
| 作者方法在我们场景里不是 100 % 完成 | 作者 TS 计划严格完成率上界 84.7 %（服务器）/ 87.4 %（本地 G0） | 覆盖可行层 CFL + 四种"作者适配"对照组，全部本地验证 G0=100 % |
| 增益主要来自多开站 | v2 开 6.8 个 DABS vs TS 4.0；PAD（作者路线+全开 DABS）100 % 完成且 PAD+RL5 与纯 RL 打平 | 主比较全部使用**同一选址 S\***（MinCov 精确最小覆盖）→ #站、固定成本逐实例相等（构造性公平） |
| 执行层 ≈ v5 RL5；REROUTE 无用；OT 约束从未满足；从零训练失败 | ABL_noRR=0 %；ABL_scratch +25 % | 新动作 OFFLOAD（跨站转移）、ExIt+ES 双阶段、PID-Lagrangian 相对 OT 约束、dev 选择保证不劣于初始化 |
| 唯一干净的胜利是静态路由 −0.98 %（10 s，1 seed），预算越大优势越小 | | 5 seeds、预算 1/3/10/30/60 s、学习修复 LNS（NLNS/RRC 风格）anytime 搜索、fresh/large 泛化 |
| 无逐实例原始数据 | | `analyze_v3.py` 输出紧凑 CSV（map, day, method, seed, J5, cost, ot, late_h, late_n, fails, complete_strict, n_dabs, fixed_cost, latency） |

## 1. 关键结构性发现（决定实验设计）

严格完成（每个可服务请求都必须被服务）要求选址覆盖 Q_ρ = (目标点 ⊕ 半径 ρ 圆盘) ∩ U，ρ = 3000 m（背景请求抖动 σ=500 m 的 6σ），以 250 m 环离散化。精确求解（ns≤11 枚举 3^ns；更大用 HiGHS MILP + no-good cut）：

* 论文测试集（50 图）：最小 DABS 数均值 6.86/7.2，**96 % 的图最小成本覆盖唯一**，可行选址平均仅 1.74 个。
* 因此 v2 的 "6.8 个 DABS" 本质上就是可行域的下界 —— 在本场景里"选址学习"几乎没有自由度，任何来自选址的"增益"在测试集上都不可信。
* 大图（L12/L15、F12/F15/F20）：13.5 站，最小 DABS 8.9，+45 固定成本内约 18.7 个可行覆盖，0 % 唯一 → **选址学习只在大图上评估（G8）**。

结论：主比较 = 相同 S\* 下比较路由层+执行层；选址层单独在有自由度的大图上评估，且同时报告固定成本与 #DABS。

## 2. 作者方法的场景适配（对照组，均已本地 G0 验证 100 %）

| 名称 | 定义 | 选址 | 路由 | 本地 G0（base 21700-21799 ×50 图 / stress 22700-22749） | #DABS | 固定成本 |
|---|---|---|---|---|---|---|
| TS（原版） | 作者 TSALNS | 作者 | 作者 | **失败**：上界 0.874（v2 服务器 0.847） | 4.32 | — |
| TS-CR | TS + 覆盖修复（只升级站点，路线不动） | 修复后 | 作者 | PASS 1.000 / 1.000 | 6.92 | 303.7 |
| PAD | 作者路线 + 全开 DABS | 全 DABS | 作者 | PASS | 7.20 | 312.5 |
| **TS-CC** | Java 补丁：LocationOperator.isFeasible 增加覆盖约束（CovExt），初始解贪心修复 | 作者在可行域内搜索 | 作者 | PASS | 6.86 | 301.6 |
| **TS-FIX(S\*)** | Java 补丁：选址固定为 S\*，作者 ALNS 只优化路由；预算 1/3/10/30/60 s，10 s 重复 3 次 | S\*（与我们相同） | 作者 | PASS | 6.86 | 301.6 |

* 补丁文件 `baselines/tsalns_java/tsalns_cov_v3.patch`（114 行，仅加约束/固定，不改搜索算子）；`run_tsalns.py` 恢复 TRIP 输出中丢失的"开站但无航次"的站点（否则 5_35_8 会被误判不可行），并用官方评估器重算成本（只升级，不会比 Java 目标更便宜）。
* 执行层对每个作者计划都交叉 {A1（作者式直接执行）、N6 规则、Rfc/RfcP（事件触发 TSALNS 风格重优化）、RL5（v5）、OFF+N6、RLR（RL5+同等 100 ms 搜索）}。
* 本地试点（50 图×4 天，新测试日）：所有作者组合严格完成率 100 %；RL5 下 J5：TS-CR 8328、TS-FIX 8493、TS-CC 8468、PAD 8178；N6 约 1.09 万。→ 静态成本低（TS-FIX 737.8 < TS-CR 751.4）≠ 动态 J5 低，说明 **J5 感知路由（π_route-J5）有真实空间**；规则式 OFFLOAD 反而 +1–2 %，说明转移必须"学会何时用"。

## 3. v3 RL 架构（逐层）

### L0 覆盖可行层（CFL，`e2e/coverage.py`）——不是学习层，是硬约束
精确最小覆盖、upgrade-only 修复、可行覆盖枚举、逐日请求缺口核查（`verify_coverage.py`，G0）。所有 RL 臂和作者臂共享。

### L1 π_site（`e2e/site_v3.py`）
* 动作空间 = **精确可行覆盖集合**（预算 MinCov+Δ，Δ=90；Δ=0 即 eqcost），MinCov 必在候选中 → 可行性构造性保证，不再"学可行性"。
* 特征：固定成本、#DABS/#SABS、相对 MinCov 增量、π_route 批量贪心路由成本、覆盖冗余度、负载均衡、距离统计（实例内中心化，置换不变）。
* 训练：大尺寸生成图，每图采样 m=4 个覆盖，奖励 = −K 个训练天气日的平均 J5（π_route 计划 + 同 seed 的 π_exec），共享基线 REINFORCE；dev 选择。
* 对照：MinCov、TS-CC、SimOpt-J5（非学习：最便宜 C=12 个覆盖 × K 天仿真取最优，同等仿真器）。

### L2 π_route（`route_train.py` + `plan_v3.py` + `lns.improve_v3`）
* 模型：沿用 v2 LEHD 风格（重解码器）POMO 策略；v3 课程以 60 % 概率采样 CFL 可行选址（测试分布 = 近全 DABS）。
* dev 标尺 = TS-FIX(S\*) 在 dev 图上的路由成本（同选址 → 纯路由差距）。
* 测试时搜索（全部 RL 自有）：POMO×aug8 → EAS-Emb（30 % 预算）→ 学习修复 LNS（NLNS/RRC：破坏=1 站/近邻 2–3 站/目标区域，修复=π_route 在子问题上的 POMO 批量；算子权重自适应；record-to-record 接受）。预算 1/3/10/30/60 s，与 TS-FIX 同预算。
* **π_route-J5**（`route_j5.py`，双层）：以 π_exec 执行计划的仿真 J5 为奖励的 REINFORCE 微调（同图 m 个计划同天气 → 配对低方差），加静态成本锚定 w=0.3；dev J5 选择。

### L3 π_exec（`exec_v3.py` + `exec_train_v3.py`）
* 动作：LAUNCH / HOLD / SERVE0-2 / **OFFLOAD**（把本机最后一个未开始航次交给另一站预计最早完工的无人机；须在半径内、能量≤0.9、值勤余量足、对方完工早≥5 min；每个航次最多转移一次 → 无乒乓、有限步终止）。
* 初始化：v5 RL5 权重嵌入 6 动作网络、OFFLOAD 偏置 −8 → **与 RL5 逐决策完全一致**（已本地验证 J 逐位相同）。
* 阶段 X（Expert Iteration）：公平孪生天气（只用 t 时刻可观测信息）rollout 搜索给出各合法动作的 Q；软 Q 目标（τ=20）+ 0.3 行为策略锚定蒸馏；DAgger 式累积。OFFLOAD 何时有益由搜索显式评估后学到。
* 阶段 E（ES，同 v5 机制但用于新动作空间/我们的计划分布）：对偶 antithetic + 公共随机数，目标 F = J5 + 1000·违约 + λ_OT·(ot − ot_ref)，ot_ref 为初始化策略同日加班；λ 用 PID-Lagrangian 更新。
* **dev 选择包含初始化本身** → best.pt 在 dev 上不劣于 RL5；只有严格完成=100 % 且 OT ≤ ref+ε 的检查点可被选中。
* 测试：OURS（贪心，~1 ms）与 OURS+S（策略先验剪枝的公平 rollout，100 ms，与 RLR 同算力）。
* 消融：ExIt 从零（第 0 轮基准=N6 规则，不用 RL5 权重）、ES-only、nooff。

## 4. 公平性协议（审稿人视角）
1. **严格完成 100 %**：所有臂共享同一可行层（handover/rebalance/backup/latest-departure/URG_FORCE），G0 预先保证作者臂覆盖可行；G3 要求每个臂每个场景 100 %。
2. **不靠多开站**：主比较选址逐实例相同（S\*），#DABS/固定成本逐行写入 CSV；PAD（全开站）作为"多开站上界"对照；选址层另在大图报告固定成本。
3. **算力匹配**：静态在同 wall-clock 预算比较（Java 单核串行 GC；我们记录设备与 wall）；执行搜索 OURS+S vs RLR 同 100 ms。
4. **数据隔离**：训练天气 5e6–9e6，dev 26000-26019，测试 21700+/22700+/23700+（新）；j5rr 与 SimOpt 只用训练天气。
5. **多 seed**：所有训练策略 5 seeds；superiority 需 Holm 校正 p<0.05 且 ≥4/5 seeds 同向；地图×天两级 bootstrap CI。
6. 若用 v2 路由检查点暖启动（`ROUTE_INIT`），会写入 state/curve 并必须在论文中报告；默认不用。

## 5. 文献调研要点（2023–2026 NCO 与相关）
* 构造式：POMO（Kwon 2020）、Sym-NCO（Kim 2022）、**LEHD**（Luo 2023，重解码器泛化）、BQ-NCO（Drakulic 2023）、ICAM（Zhou 2024）、ELG（Gao 2024）、INViT（Fang 2024）、MatNet（Kwon 2021）、PARCO（Berto 2024，并行多智能体构造）。→ 采用 LEHD 风格 + POMO 共享基线。
* 改进式/搜索：DACT（Ma 2021）、NeuOpt（Ma 2023）、**NLNS**（Hottung & Tierney 2020）、RRC/L2R（Luo 2024 / Ye 2024）、**EAS**（Hottung 2022）、SGBS（Choo 2022）。→ EAS + 学习修复 LNS 作为 anytime 机制（解决"预算越大优势越小"）。
* 生成式：DIFUSCO（Sun 2023）、T2T（Li 2023）、GFlowNets（Zhang 2023）——对带容量/能量/多站耦合的本问题可行性处理困难，未采用（风险分析见 §6）。
* 选址 RL：设施选址/p-median 的 GNN+RL（Wang 2023 等）——普遍在可行域无约束；本问题可行域极小，故改为"精确可行集上的学习选择器"。
* 多智能体执行：MAPPO（Yu 2022）；约束 RL：RCPO（Tessler 2019）、**PID-Lagrangian**（Stooke 2020）；**ExIt / AlphaZero**（Anthony 2017；Silver 2017）；ES（Salimans 2017，v5 已验证有效）。

## 6. 风险分析
| 风险 | 缓解 |
|---|---|
| 执行层只与 RL5 打平（v2 情形） | 初始化=RL5 且 dev 选择包含初始化 → 不劣；增益来源：OFFLOAD（新能力）、我们计划分布上的再训练、ES 续训；G4 预注册，若不通过则如实报告 |
| ExIt 搜索信号弱（v5：RLR≈RL5） | 软目标+锚定防漂移；ES 阶段兜底；ExIt-scratch 只作为消融 |
| π_route-J5 牺牲静态成本 | 静态锚定 w=0.3；静态与动态分别报告；G7 量化 |
| 大预算下静态优势消失 | 学习修复 LNS 随预算持续改进；1–60 s 全曲线 + fresh/large |
| 选址在测试集无自由度 | 主比较固定 S\*；选址单独在大图（G8） |
| Java 未构建 | run_all 拒绝全量运行（ALLOW_NO_TS=1 仅供 smoke） |
| 仿真卡死（OFFLOAD 乒乓） | 每航次只转移一次；dyn_eval 每天 600 s 超时写 error 行 |
