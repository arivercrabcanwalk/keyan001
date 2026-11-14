# WX3 文献调研（2026-11-14 JST）：动态派遣 / 待命-放飞 / RL+前瞻 / 约束与风险 RL / 评测规范

> 范围：2022–2026 为主，少量奠基文献（DAgger、ExIt、API、PPO、CVaR-PG）因方法直接相关而列入。
> 所有条目的链接均已在 2026-11-14 用 curl 或检索核实可访问（少数出版社页面对脚本返回 403，已用检索结果交叉确认 DOI）。
> 作者名只在检索结果中能确认时才写，否则只写题名。「做法」一栏只写能从摘要/正文公开信息确认的内容；拿不准的细节不写。

## 1. 与本题最接近的问题线：随机动态车辆路径（SDVRP）与「等待还是出发」

| # | 文献 | 刊物/会议（CCF） | 与我们的关系 | 基线 / 统计 / 实例 / 消融（可确认部分） |
|---|---|---|---|---|
| 1 | Hildebrandt, Thomas, Ulmer. *Opportunities for reinforcement learning in stochastic dynamic vehicle routing*. 2023. https://doi.org/10.1016/j.cor.2022.106071 | Computers & OR（CCF-B） | 综述：RL 在 SDVRP 中要么限制动作空间、要么退化为资源分配；呼吁 RL 与 OR 结合（规则/前瞻+学习）。**我们的「待命/放飞」离散动作 + 计划层 ALNS 恰好是它说的「限制动作空间」路线，必须在文中正面承认并论证。** | 综述性；强调与 ADP/前瞻基线比较。 |
| 2 | Ulmer, Goodson, Mattfeld, Thomas. *On modeling stochastic dynamic vehicle routing problems*. EURO J. Transp. Logist. 2020. https://www.sciencedirect.com/science/article/pii/S219243762030008X | EJTL | 路径型 MDP 建模规范：状态、决策时刻、动作=（暂定）路线计划。审稿人会按这个框架检查 MDP 定义是否完整。 | 建模论文。 |
| 3 | Ulmer, Goodson, Mattfeld, Hennig. *Offline–Online ADP for Dynamic Vehicle Routing with Stochastic Requests*. Transp. Sci. 2019. https://doi.org/10.1287/trsc.2017.0767 | Transp. Sci.（CCF-B 级 OR 顶刊） | **离线价值函数 + 在线 rollout 的混合**，并给出「以确定性规则为基策略的 rollout 不劣于基策略」的改进保证。直接支撑我们的 API/ExIt 叙事。 | 基线：短视策略、纯 VFA、纯 rollout；比较质量-计算时间。 |
| 4 | Ulmer. *Budgeting Time for Dynamic Vehicle Routing with Stochastic Customer Requests* (ATB). Transp. Sci. 2018. https://pubsonline.informs.org/doi/10.1287/trsc.2016.0719 | Transp. Sci. | 「预判式时间预算」：通过模拟估计 (时刻, 剩余时间) 的价值，属于 anticipatory waiting/预算类启发式。**可作为文献型基线的思想来源（按时间和剩余能力做阈值的预判规则）。** | 与文献基准启发式比较。 |
| 5 | Klapp, Erera, Toriello. *The Dynamic Dispatch Waves Problem for same-day delivery*. EJOR 2018. https://doi.org/10.1016/j.ejor.2018.05.032 | EJOR（CCF-B） | 经典「等待 vs 派车」：等得越久越能合并，但越可能超时。我们的 HOLD/LAUNCH 是同一权衡的无人机+天气版本。 | 与先验/确定性派车策略比较；含上界。 |
| 6 | Chen, Ulmer, Thomas. *Deep Q-learning for same-day delivery with vehicles and drones*. EJOR 2022. https://doi.org/10.1016/j.ejor.2021.06.021（预印本 https://arxiv.org/abs/1910.11901） | EJOR | **最贴近的「RL + 无人机 + 动态请求 + EJOR」先例**：DQN 决定用车/无人机/拒绝。说明 EJOR 接受「小离散动作 + 规则执行层」的 RL 设计。 | 与多种启发式（含距离/时间阈值规则）比较，多种车队与需求设置。 |
| 7 | Baty, Jungel, Klein, Parmentier, Schiffer. *Combinatorial Optimization-Enriched ML to Solve the Dynamic VRP with Time Windows*. Transp. Sci. 58(4) 2024. https://arxiv.org/abs/2304.00789 | Transp. Sci. | EURO-NeurIPS 2022 动态 VRP 赛题冠军：**模仿「全知（anticipative）预言机」的决策**，用 CO 层把学习到的打分变成可行派遣。**与我们最相关的方法论先例：从带特权信息的专家学习可实现策略。** | 与竞赛基线/贪心派遣比较；多实例；消融学习层。 |
| 8 | Li, Cai, Zhao. *Optimizing same-day delivery with vehicles and drones: hierarchical DRL*. TR-E 193, 2025. https://doi.org/10.1016/j.tre.2024.103878 | TR-E（CCF-B） | 第一层专门决定**车辆出发时机**（等/走），说明「出发时机学习」是 TR-E 认可的主题。 | 与基准方法比较；跨分布/车队规模泛化。 |
| 9 | Cui, Li, Jia, Meng. *Dynamic collaborative truck-drone delivery with en-route synchronization and random requests*. TR-E 192, 2024. https://doi.org/10.1016/j.tre.2024.103802 | TR-E | 动态请求下的卡车-无人机 RL；做了多场景（电池续航、动态/非协同对照）。 | Solomon 改造实例 + 新加坡真实数据；多天实例。 |
| 10 | *Reinforcement learning for humanitarian relief distribution with trucks and UAVs under travel time uncertainty*. TR-C 2023. https://doi.org/10.1016/j.trc.2023.104401 | TR-C（CCF-B） | 不确定性下 UAV 调度；同时比较 VFA 与 PFA 两种 RL，并与数学规划和动态启发式比较。**说明审稿人期待「多种 RL 形态 + 非 RL 强基线」。** | Solomon 实例 + 两个真实案例。 |
| 11 | *Cooperative Learning-Based Joint UAV and Human Courier Scheduling for Emergency Medical Delivery Service*. IEEE T-ITS 2024. https://doi.org/10.1109/tits.2024.3486789 | IEEE T-ITS（CCF-B） | 紧急配送 UAV 实时调度的 DRL；T-ITS 典型写法：问题新 + 多基准 + 案例。 | 多场景对比 + 真实案例。 |
| 12 | Joe, Lau. *DRL Approach to Solve DVRP with Stochastic Customers*. ICAPS 2020. https://ojs.aaai.org/index.php/ICAPS/article/view/6685 | ICAPS（CCF-B） | 用 TD 学到的价值函数**引导启发式搜索**做实时重规划（学习+搜索）。 | 与短视、AVI、MSA（多场景）比较，按动态度分组。 |
| 13 | Shah, Lowalekar, Varakantham. *Neural ADP for On-Demand Ride-Pooling*. AAAI 2020. https://ojs.aaai.org/index.php/AAAI/article/view/5388 | AAAI（CCF-A） | 神经价值函数 + ILP 指派；说明「学价值、用优化执行」在 A 类会议的接受度。 | 真实纽约出租车数据，与领先基线比较。 |
| 14 | *The drone latency location routing problem under uncertainty*. TR-C 2023. https://doi.org/10.1016/j.trc.2023.104322 | TR-C | 无人机 + 不确定飞行时间的鲁棒优化；说明天气/能耗不确定性在 TR-C 的建模惯例。 | 鲁棒优化对照。 |

## 2. RL + 前瞻（rollout）、rollout 专家蒸馏、近似策略迭代 / Expert Iteration

| # | 文献 | 要点 | 对我们的用途 |
|---|---|---|---|
| 15 | Bertsekas. *Rollout, Policy Iteration, and Distributed RL*. Athena 2020. https://web.mit.edu/dimitrib/www/Rollout_Complete%20Book.pdf | rollout = 一步策略改进；近似策略迭代（API）= 反复 rollout + 用网络近似新策略；并行化。 | **理论骨架**：我们的方法 = 以学习策略为基策略的 rollout 改进 + 网络近似（API）。 |
| 16 | Lagoudakis, Parr. *RL as Classification: Leveraging Modern Classifiers*. ICML 2003. https://cdn.aaai.org/ICML/2003/ICML03-057.pdf | 用 rollout 估计各动作 Q，把策略改进变成分类/回归。 | 直接对应「rollout Q 标签 → 网络」。 |
| 17 | Lazaric, Ghavamzadeh, Munos. *Analysis of Classification-based Policy Iteration Algorithms*. JMLR 17, 2016. https://jmlr.org/papers/v17/10-364.html | 给出 rollout 次数、样本数与误差传递的界。 | 支撑 M（rollout 次数）与标注量的设计及「迭代不发散」的论证。 |
| 18 | Anthony, Tian, Barber. *Thinking Fast and Slow with Deep Learning and Tree Search* (ExIt). NeurIPS 2017. https://proceedings.neurips.cc/paper_files/paper/2017/hash/d8e1344e27a5b08cdfd5d027d9b8d6de-Abstract.html | 「慢专家（搜索）↔ 快学徒（网络）」交替：网络指导搜索、搜索产生更好标签。比 REINFORCE 强。 | 我们的迭代：π_k 作 rollout 基策略 → 更好的 Q 标签 → π_{k+1}。 |
| 19 | Ross, Gordon, Bagnell. *A Reduction of Imitation Learning ... to No-Regret Online Learning* (DAgger). AISTATS 2011. https://proceedings.mlr.press/v15/ross11a.html | 在学徒自己的状态分布上收集专家标签，聚合数据。 | 我们每轮都在 π_k 访问的状态上打标签并聚合。 |
| 20 | Ross, Bagnell. *Reinforcement and Imitation Learning via Interactive No-Regret Learning* (AggreVaTe). 2014. https://arxiv.org/abs/1406.5979 | 不模仿专家动作，而是学**专家的 cost-to-go**，对代价敏感，理论上可超过专家。 | **关键选择**：用 Q（cost-to-go）回归而非硬标签模仿（我们 v2 的 DAgger 硬标签只到 dev J≈5005）。 |
| 21 | Chen, Zhou, Koltun, Krähenbühl. *Learning by Cheating*. CoRL 2019. https://arxiv.org/abs/1912.12294 | 先训练带特权信息的专家，再蒸馏到只用可观测输入的学生。 | 讨论「特权 rollout」的利弊；我们改用**无特权（twin）rollout**，从根上避免审稿质疑。 |
| 22 | *Multiagent Reinforcement Learning for Autonomous Routing and Pickup Problem with Adaptation to Variable Demand*（2022 预印本；基于 API 的一步前瞻 + GNN 近似 rollout）. https://arxiv.org/abs/2211.14983 | 用网络近似 rollout 策略、在线再做一步前瞻，优于其他 rollout-RL 与经典 OR 方法。 | 与我们「网络 + 时延受限前瞻（WX-H）」同构，可作对比。 |
| 23 | Kwon et al. *POMO*. NeurIPS 2020. https://proceedings.neurips.cc/paper/2020/hash/f231f2107df69eab0a3862d50018a9b2-Abstract.html；Kool et al. *Attention, Learn to Solve Routing Problems!* ICLR 2019. https://arxiv.org/abs/1803.08475 | NCO 主流训练范式（共享基线 REINFORCE、注意力解码）。 | 我们 v2 用的是 POMO 式共享基线；v3 将其降为可选微调，主方法换成 API。 |

## 3. 约束 / 多目标 / 风险敏感 RL

| # | 文献 | 要点 | 用途 |
|---|---|---|---|
| 24 | Tessler, Mankowitz, Mannor. *Reward Constrained Policy Optimization*. ICLR 2019. https://arxiv.org/abs/1805.11074 | 拉格朗日乘子慢时间尺度更新，约束写进奖励。 | 高优准时率 / CVaR 约束的标准做法。 |
| 25 | Stooke, Achiam, Abbeel. *Responsive Safety in RL by PID Lagrangian Methods*. ICML 2020. https://proceedings.mlr.press/v119/stooke20a.html | 纯积分型乘子更新会振荡，PID 型更稳。 | 若做在线乘子更新，用 PI 型；我们在 API 中改为「标签层标量化 + dev 上对偶选择」，更稳定、可复现。 |
| 26 | *Learning to Solve Soft-Constrained Vehicle Routing Problems with Lagrangian Relaxation*（2022 预印本）. https://arxiv.org/abs/2207.09860 ；*Learning to Handle Complex Constraints for Vehicle Routing Problems*（2024 预印本）. https://arxiv.org/abs/2410.21066 | 路由 RL 中用拉格朗日把时间窗/容量违反并入奖励。 | 说明「拉格朗日约束 + 路由 RL」在 VRP 社区是公认做法。 |
| 27 | Tamar, Glassner, Mannor. *Optimizing the CVaR via Sampling*. AAAI 2015. https://arxiv.org/abs/1404.3862 ；Greenberg et al. *Efficient Risk-Averse RL* (CeSoR). NeurIPS 2022. https://arxiv.org/abs/2205.05138 | CVaR 策略梯度；纯 CVaR 目标样本效率低，需从风险中性逐步过渡。 | 我们把日度 cvar_h 作为标签向量中的一项，用乘子加权；不做纯 CVaR-PG（样本效率差、易不稳）。 |
| 28 | Lin, Yang, Zhang. *Pareto Set Learning for Neural MOCO*. ICLR 2022. https://arxiv.org/abs/2203.15386 | 偏好条件网络一次学出整条帕累托前沿。 | 备选：权重条件策略画出 J–准时率前沿（作为附加图，不作主张）。 |

## 4. 评测与统计规范（审稿人据此挑刺）

| # | 文献 | 要点 |
|---|---|---|
| 29 | Accorsi, Lodi, Vigo. *Guidelines for the computational testing of ML approaches to VRPs*. Oper. Res. Lett. 50(2) 2022. https://doi.org/10.1016/j.orl.2022.01.018 | 要和**真正的 SOTA OR 方法**比、相同硬件和时间预算、标准/多样实例、报告时间与差距分布，不要只和弱基线比。 |
| 30 | Agarwal et al. *Deep RL at the Edge of the Statistical Precipice*. NeurIPS 2021. https://arxiv.org/abs/2108.13264 | 少种子下要报区间估计（分层 bootstrap CI、IQM、概率改进），不能只报均值。 |
| 31 | Demšar. *Statistical Comparisons of Classifiers over Multiple Data Sets*. JMLR 7, 2006. https://www.jmlr.org/papers/v7/demsar06a.html | 多数据集比较用 Wilcoxon 符号秩/Friedman+事后检验，多重比较要校正。 |

## 5. 这些论文怎么选基线、做统计、选实例、做消融（共性）

1. **基线三层**：(i) 业界/作者规则（我们：A1/A2，TSALNS 计划 + 紧急优先）；(ii) 调好的强规则族（N1–N3 网格，dev 选最优）；(iii) **前瞻/ADP 类**（rollout、MSA、VFA）并给**相同时延预算**的对照；外加 (iv) 全知上界（O / anticipative oracle）。缺 (iii) 的同预算对照是最常见的拒稿理由之一（Accorsi 2022；Hildebrandt 2023）。
2. **统计**：OR 期刊多报均值+相对差距+箱线图，越来越多要求配对检验；ML 会议要求多种子 + 区间（Agarwal 2021）。我们采用：实例层配对 Wilcoxon + Holm + 效应量（匹配秩二列相关 r）+ 实例层 bootstrap CI + 胜率；种子维度报每种子与三/五种子均值。
3. **实例**：标准实例改造（Solomon/Liu-50）+ 新生成的更大/更难集 + 真实案例。我们没有真实气象（用户要求），所以必须做**多个合成情景 + 分布外测试**，并在标题/摘要中写明「合成天气」。
4. **消融**：每个组件拿掉一次（特征、网络结构、标签类型、约束项、迭代轮数、rollout 次数 M）；以及「学习的价值是否来自信息」——随机价值网络/打乱特征对照。

## 6. 常见审稿意见清单（逐条对应 v3 设计）

| 常见意见 | 我们过去的风险 | v3 对策 |
|---|---|---|
| 基线太弱/没调参 | N1 已网格调参 ✔ | 保留；再加文献型预判等待启发式（ATB 思想）与**同时延** rollout |
| 基线用了不公平信息，或 RL 用了基线没有的信息 | **N4 rollout 共享真实天气（隐性全知）**——之前没发现 | 修正为 twin（无特权）rollout：N4f；原 N4 改名 N4p 只作「特权参照」，不作基线 |
| 只比 J，主指标不显著 | v2 的 P1 失败 | 多目标标签 + 拉格朗日权重在 dev 上按「所有主指标不劣于 N1」对偶选择；预注册成「J 与失败显著改进 + 高优准时/CVaR 非劣（并争取显著）」 |
| 种子少 / 算力不等 | v2 种子 0 算力少 | 5 种子、**按标签天数与 epoch 固定算力**（不用墙钟） |
| 只在训练分布上测 | 只有 Test-A | Test-A + Test-B（作者 TSALNS 计划，不同计划结构）+ Test-C 压力情景 + P4 扰动（修正速度扰动） |
| 统计不规范 | 已有 Holm | + 效应量 + 分层 bootstrap + 预注册检验族 |
| 时延对比不公平 | N4d 有缺陷 | 修正 N4d（完整轮次、均值、真截止）；同机同核计时；报 p50/p99 |
| 结论过度（「风暴感知」） | P3 失败 | 机制改写为「待命-放飞时机 + 失败规避」，P3 只作探索性分析 |
| 可复现性 | 已有逐位复现 ✔ | 继续：固定种子、标签分片哈希、单入口脚本 |

## 7. 补充（2026-11-14 第二轮，因本地试点结果而加）：轨迹级直接策略搜索 / 进化策略（ES）与等待策略经典文献

| # | 文献 | 刊物/会议（CCF） | 与我们的关系 |
|---|---|---|---|
| 32 | Salimans, Ho, Chen, Sidor, Sutskever. *Evolution Strategies as a Scalable Alternative to Reinforcement Learning*. 2017. https://arxiv.org/abs/1703.03864 | arXiv（OpenAI-ES，被大量 CCF-A 工作引用为标准 RL 基线/方法） | **v3 主学习器的直接来源**：对偶（antithetic）扰动 + 中心化秩 + 只靠 CPU 大规模并行；对稀疏/延迟回报、长时域不敏感；不需要价值函数。正适合我们「40 核无 GPU、每天模拟 0.2 s、回报在一天结束才知道」。 |
| 33 | Mania, Guy, Recht. *Simple random search provides a competitive approach to reinforcement learning*. NeurIPS 2018（CCF-A）. https://arxiv.org/abs/1803.07055 | NeurIPS | 证明随机搜索（ARS）在连续控制上可与 PPO/TRPO 竞争；同时强调**多种子、报告分布**的评测规范（审稿人会拿来要求我们报每个种子）。 |
| 34 | Such et al. *Deep Neuroevolution: Genetic Algorithms Are a Competitive Alternative for Training Deep Neural Networks for RL*. 2017. https://arxiv.org/abs/1712.06567 | arXiv | 无梯度方法训练深网络的另一证据；支撑「轨迹级黑盒优化 = 合法的 RL 训练方式」。 |
| 35 | Choromanski et al. *Structured Evolution with Compact Architectures for Scalable Policy Optimization*. ICML 2018（CCF-A）. https://arxiv.org/abs/1804.02395 | ICML | ES 方差缩减（结构化/正交噪声）与紧凑策略网络；我们用「共同随机数（同一批天）+ 对偶扰动」做方差缩减，属同一思路。 |
| 36 | Mitrović-Minić, Laporte. *Waiting strategies for the dynamic pickup and delivery problem with time windows*. Transp. Res. Part B 38(7), 2004. https://doi.org/10.1016/j.trb.2003.09.002 | TR-B | 经典等待策略（drive-first / wait-first / 动态等待 / 预判式等待）；**我们的文献型基线 N6（预判储备）就是它与 Ulmer ATB 思想在本问题上的实现**。 |

**为什么在试点后把主学习器从「逐状态 rollout 标签回归（API/ExIt）」改成「轨迹级 ES + 约束标量化」**（详见 DESIGN_ZH.md §3）：
本地试点表明，逐状态的 rollout Q 标签（M=8）在留出天上几乎不可预测（梯度提升树留出遗憾 87 vs 常数「总是待命」76；QNet dev J 5406 劣于 N1 5050）。原因是「放飞/待命」的优劣主要由未来天气决定，单状态标签方差远大于可从可观测特征中学到的信号。而 ES 直接在**整天的目标**上比较策略、用共同随机数（同一批天）抵消天气方差，这正是 Salimans 2017 / Mania 2018 所说的「回报延迟、信用分配困难时黑盒策略搜索更稳」。rollout 专家（公平 twin）保留为**可选的在线前瞻层**（RL+前瞻，§2 文献 Bertsekas/Ulmer），并作为上界参照。

**补充审稿风险（试点中发现）**：本仿真器的天气种子只由「天号」决定，同一天号在所有地图上共享天气（风暴标志、风场、阵风相同，雷暴单体位置随包围盒变）。因此 Test-A「50 地图 × 30 天」在天气维度上只有 30 个独立样本（16 个风暴日）。仅以地图为单位做 Wilcoxon 会被质疑「伪重复」。v3 的对策：主检验仍用预注册的地图级单位（n=50），但**同时要求**天级聚类检验（n=30，按天先对地图取平均）与「地图×天」交叉 bootstrap CI 方向一致，才宣称显著。
