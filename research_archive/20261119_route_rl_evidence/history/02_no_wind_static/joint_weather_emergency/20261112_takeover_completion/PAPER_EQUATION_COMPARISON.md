# PAPER_EQUATION_COMPARISON — Liu (2026) 原文 / 作者 Java / 已验收 evaluator 逐式比对

生成：2026-11-12（Asia/Shanghai）。作者：接手线程（DeepSeek Harness）。本文件只做静态比对，**未连服务器、未运行任何求解器或科研计算**；所有数值均来自既有收据文件。
本文件服务于接手包 `joint_weather_emergency/20261112_takeover_completion/`，不修改任何历史文件。

路径约定：全部相对项目根 `<LOCAL_PATH>`。行号一律指用 read/grep 工具打开该文本时看到的行号（页码映射方法见 §0.2）。

| 代号 | 文件 |
|---|---|
| **P** | `audit/papers/Liu2026.txt`（1,044 行；对应 PDF `audit/papers/Liu2026.pdf`） |
| **S** | `audit/papers/Liu2026_supplement.txt`（538 行；对应 `audit/papers/Liu2026_supplement.pdf`） |
| **J** | `reproduction/reviewer_package_semfix/reference/java/official_source/`（作者官方 10 文件，commit `d86f5549ebc9c05d65fce16f61b6df4f7cb73158`） |
| **E1** | `route_rl_research/20261103/return_makespan/global_env.py`（398 行） |
| **E2** | `route_rl_research/20261103/return_makespan/scorer.py`（290 行） |
| **PP** | `route_rl_research/20261103/source_snapshot/lrphsd/problem.py`（80 行，复现端 Instance/Parameters 契约） |

---

## 0. 交付范围、阅读证据与身份

### 0.1 实际读了什么（区分全文 / 定位读）

| 材料 | 阅读程度 | 证据 |
|---|---|---|
| Liu 正文 | **全文逐行读完**（1–1,044 行，含摘要、§1–§6、式 (1)–(23)、Algorithm 1–2、Table 1–3、Fig. 1–11、参考文献表头） | 本文件所有 P:行号均可复核 |
| Liu 补充材料 | **全文逐行读完**（1–538 行，Appendix A–D、Algorithm A.1–A.2、Table A1、Table B1–B7 抽样核对、Table D1） | S:行号 |
| 作者 Java | **全文读完 9/10 文件**（Check 714、Init 389、Main 301、ALNSSolver 321、LocationOperator 146、Solution 152、Node 101、Calculator 27、FileReaderUtil 51 行）；RoutingOperator 1,824 行采用"方法索引 + 关键方法全文 + 删除/插入/可行性分支逐段"，**未逐字读完全部** | J:行号；未读段列在 §0.4 |
| evaluator | E1、E2 **全文读完**；另读 PP 全文 | E1/E2/PP 行号 |
| 复现协议 | `REPRO_PROTOCOL.md`(39 行)、`SEMFiX_FULL_RESULTS.md`(96 行)、`SEM_FIX_PROVENANCE.md`(14 行)、`REPRO_ENVIRONMENT.md`(18 行) **全文读完** | §F |

**未做**：未打开 PDF 做视觉核对（只用文本抽取 + 页脚数字定位页码）；未运行 Java/Python 求解；未连接 <COMPUTE_HOST>；未读作者 GitHub 网页版（只读本地 pinned 副本）。因此本文件不声称"复现成功"，只声称"原文与两份实现的静态映射已核对"。

### 0.2 页码映射方法（可复核）

P 每页末尾有一行纯页码（页脚）。用 grep 匹配"整行只有 286–300 的数字"得到：

| 页 | 页脚所在 P 行 | 该页正文范围（P 行） |
|---|---|---|
| 286 | 137 | 1–137 |
| 287 | 208 | 138–208 |
| 288 | 286 | 209–286 |
| 289 | 368 | 287–368 |
| 290 | 441 | 369–441 |
| 291 | 513 | 442–513 |
| 292 | 586 | 514–586 |
| 293 | 660 | 587–660 |
| 294 | 728 | 661–728 |
| 295 | 788 | 729–788 |
| 296 | 816 | 789–816 |
| 297 | 868 | 817–868 |
| 298 | 916 | 869–916 |
| 299 | 996 | 917–996 |
| 300 | 1,043 | 997–1,043 |

由此：**式 (1)–(10) 在 p.288（P:251–284）**；**式 (11)–(22) 在 p.289（P:290–321）**；**无风/无禁飞假设在 p.288（P:226–227）**；**future work 在 p.299（P:923–925）**。
S 的页眉数字位于 S:1(31)、42(32)、101(33)、139(34)、277(36)、440(39)、503(40)，故 **Table A1 在补充材料 p.32（S:65–88）**，**Appendix D 在 pp.39–40（S:450–537）**，**Table D1 在 p.40（S:509–525）**。

### 0.3 文件身份（SHA256，本次实算）

```text
6ce376536ca63cfd65fe3a99c58e9f3517ae45972a4682fecb42f320522dd7c0  audit/papers/Liu2026.pdf
31cea3a0a405a6efed43562a39293cdac846ef9c11d36c30fc7d6f4d797b5cee  audit/papers/Liu2026.txt
fad4aeacde3976b41148b267db9f639e13861e5483f54d0a0ad5217978b49b31  audit/papers/Liu2026_supplement.pdf
fefcf2ee4718834942175545e4430f3ce1a2e2f61fdbb966c0ed744b7ec3038c  audit/papers/Liu2026_supplement.txt
ea0f541cb5eb0b90772e8fc1cadc62e72ba3338d6a6d005dae0ac43abbd54d23  .../official_source/Check.java        （= SOURCE_LOCK.json 记录值）
03180c23fb52f55ae42f7131576694e3ccd7ee11145e161ce7359f0994c12ed1  .../official_source/Main.java         （= SOURCE_LOCK.json）
030f80be3257a28f9aae4aba7b8e540592260188c2f9a1f805a5786f2ef0bb43  .../official_source/ALNSSolver.java   （= SOURCE_LOCK.json）
b903f7df68cbb1d2faae6fb324ef3ed3ab1f3592c1c56aa2144eddedd54f5428  route_rl_research/20261103/return_makespan/global_env.py
c6e156b2d770cec2f663eada37c2d39bff1583f672bda4116f81493484409135  route_rl_research/20261103/return_makespan/scorer.py
```

作者源码身份：`reproduction/reviewer_package_semfix/reference/java/SOURCE_LOCK.json` 记录 repo `https://github.com/lps11735/LRPHSD.git`、commit `d86f5549…`、路径 `code/TSALNS`、10 文件哈希；`official_source` 标注为 immutable。本文全部 J 引用均指该 immutable 副本，不指 instrumented/guarded 变体。

### 0.4 RoutingOperator 未逐字读的段（诚实边界）

已逐段读：swap3/swap4 全文（J:146–295）、swap1/swap2 仅签名与结构（J:7–145）、2-opt 仅签名附近（J:365–424）、四个 destroy 主体（J:425–843）、similarity（J:845–882）、nearestInsertion（J:1004–1117）、loadBalancingInsertion 主体（J:1119–1204）、minimumRegretInsertion（J:1260–1384）、prioritizedInsertion（J:1386–1575）、calculateRegret/isSubPathValid/deltaCost/loadBalanceScore（J:1578–1653）。
未逐字读：`swap1/swap2` 完整索引逻辑、`twoOptOperator` 主体、`greedyInsertMinCost`（J:890–1002，**死代码**）、`swapPointsBetweenDrones`（J:298–364，**死代码**）。这些不影响 §A/§B 的结论，因为它们在官方入口不可达（证据见 §A.2-3 的 grep 结果）。

---

## A. 模型映射表

### A.1 主表（21 项）

"一致"列取值：**一致** / **数值等价**（表示不同、口径相同）/ **部分一致**（有可枚举差异）/ **不一致** / **不适用** / **Java 自检不完整**（模型层一致、作者校验层缺失）。

| # | 模型要素 | 原文（页 / 式 / 行） | Java 类.方法（行） | evaluator 函数（行） | 一致? | 关键证据与差异 |
|---|---|---|---|---|---|---|
| 1 | 图与节点集：J=目标、I=候选站 | p.287 §3.1 P:201–202 | Main.main P:49–58（SERVICE_ENERGY>0 为目标，否则为站）；FileReaderUtil.readNodesFromFile J:9–49（5 列） | PP:read_instance 55–71（energy>0 → target；energy==0 → station；**要求站 service==0**，PP:70）；E2:score_solution 92–105 | 一致 | 官方实例 `external/LRPHSD<EXECUTION_PATH>`：目标 nodeNo 1–10、serviceEnergy 0.2、serviceTime 10；站 nodeNo 11–13、serviceEnergy 0、serviceTime 0 |
| 2 | 站型 SABS / DABS | p.287 P:203–206、Fig.1 p.285 P:80–90 | stationTypes int（0 关闭 / 1 SABS / 2 DABS）：Solution.java:23,86–92；Check.java:270–274 | E2:112–120；E1:33–38（非 1/2 直接报错） | 一致 | 三处都是单值编码，故"每址至多一站型"由类型系统强制 |
| 3 | 机型 SD / LD 与机数 k_s,k_l | p.287 P:232–233；式(15) p.289 P:303–307 | 每站固定 2 槽（先 large 后 small）：Init.generateRoutes1 J:275–278；槽 0=LD、槽 1=SD 由 Check.java:465–467、551–555 隐含 | E1:47（SABS 只有 slot 1，否则 (0,1)）；E2:121（每站必须 2 槽）、142–143（SABS 槽 0 有 trip 即违规） | **部分一致** | 原文：SABS 只部署 1 架 SD，DABS 同时容纳 1 SD + 1 LD。Java 的 SABS 也有 2 个存储槽，且 `prioritizedInsertion` 会把任务写进 SABS 的**空槽 0**（J:1417–1434，电池按 SD 取，J:1418–1419），Check 的总体校验把槽 0 当 SD（J:551–555）→ 原始 Java 可能出现"1 个 SABS 用 2 架 SD"的解；evaluator 直接判 `large_drone_at_small_station`（E2:142–143）。这与 `REPRO_PROTOCOL.md:40` 的记载一致 |
| 4 | 覆盖约束（通信/服务半径） | 式(7) p.288 P:273–274；半径定义 p.287 P:204–206 | Init.allocateTargetsToStations J:204–217（distance <= radius）；Init.calculateCoverage J:171–181；各插入算子 J:935、1034、1145、1412、1450 | E2:153–155（distance > radius + 1e-7 才违规）；E1:82–84（> radius + EPS，EPS=1e-7，E1:8） | **数值等价（容差略异）** | Java 无容差、含等号；evaluator 允许半径外 1e-7。半径 4000/5000 m，1e-7 m 量级差异不影响真实实例，但等号边界上的构造实例会分歧 |
| 5 | 每目标恰好服务一次 | 式(2)(5) p.288 P:255–271 | 分配阶段一目标一站（J:204–224）；插入/删除保持"移除-重插"（findRemovedNodes J:1687–1710）；**无显式唯一性校验** | E2:191–195（missing/duplicate）；E1:63–64,170 | **Java 自检不完整** | Java 的 `isOverallSolutionValid` 只查能量（J:484–525），`checkStationOperation` 只查时间（J:131–190）；覆盖、唯一性、指派一致性都不在作者自检内 → 必须靠独立 evaluator。这正是 `REPRO_PROTOCOL.md:29–31,39–40` 的动机 |
| 6 | **部署位置**与站型选择：只能在候选站集 I 内选址，且每址至多一种站型 | §3.1 p.287 P:201–203；式(6) p.288 P:273 | stationTypes 单 int（Solution.java:23）；选址算子只改这个数组（LocationOperator J:13–121）；无连续选址 | types 逐站 0/1/2（E2:112–120） | 一致 | 三处都只允许"候选站子集 + 类型"，不存在坐标决策；`LocationOperator.isFeasible` 只查覆盖（J:127–145） |
| 7 | **原目标成本（完整式）** | **式(1) p.288 P:251–254**：min 站点固定项 + Σ_iΣ_dΣ_(j,k)∈A c_t·x·(t_jk + t_f) | Check.calculateTotalCost J:253–289（固定成本 J:270–274；可变成本 = c_t × Σ_drone calculateDroneTime J:281–284）；calculateDroneTime J:307–344 | E2:117–120（固定）+ E2:162–175（每趟 duration）+ E2:187,197–198,204–205（cost = fixed + operating×time_cost） | **数值等价，但原文式有 t_f 计费口径缺陷** | 详见 §B.1：式(1) 把 t_f 记在**每条弧**上（每趟 n+1 次），实现按**每个目标**记一次（n 次）。正文 P:235–236 的描述（"sum of travel time and inspection time"）支持实现语义 → 判定：**采用实现语义**，式(1) 的字面弧和不可用于重算成本 |
| 8 | 固定成本（站 + 机） | 式(1) 第一项 P:251–253；数值 p.293 P:613–618 | J:270–274（type2 = c_l+c1+c2；type1 = c_s+c1） | E2:117–120 同式；PP:51–53 Instance.fixed 同式 | 一致 | DABS 即使 LD 槽为空也照收 c1+c2（J:271 与式(1) 的 z_li(c1+c2) 一致；E2:120 也一致） |
| 9 | 单位时间成本 c_t 与服务时间 t_f | p.288 P:220–224；p.293 P:617–618（c_t=0.5） | Check.java:13 FLIGHT_COST_PER_MIN=0.5（calculatePathCost J:75 用它）；Main.java:29 传入 0.5 | PP:20 time_cost=0.5；E2:198 | 一致 | 注意 calculatePathCost 用**静态常量** 0.5，不读 unitTimeCost 参数；若改 c_t，ALNS 内部排序不会跟着变（对排序无影响，但属参数接线缺陷） |
| 10 | 换电：每趟满电出发 | 式(17)(18) p.289 P:311–314；文字 p.287 P:229–233 | 逐趟独立算能量：Check.checkStationPathsEnergy J:538–585（consumedBattery > batteryCapacity → false，J:577）；checkPathEnergy J:122–128 | E2:167–175（每 trip 独立 energy）；E1:159（RETURN 时 trip_energy=0） | 一致 | 电池在趟间重置；换电时间为 0（P:230–232；E2 文件头注释 E2:1–6 也声明无 charging/turnaround 时间） |
| 11 | 多趟 | 式(13)–(15) p.289 P:295–307；w 变量 p.288 P:246–248 | 嵌套列表 routes[station][drone][trip][node]（Solution.java:8；Check 注释 J:8–11）；w 未显式建模，趟边界由列表给出 | E2:126–139（routes[si][slot][trip]）；E1:152–161（RETURN 关闭 trip） | 一致 | 论文用 w 连接相邻两趟；实现用容器结构，二者等价 |
| 12 | **累计 duty**（站工作时段约束） | **式(8) p.288 P:275–278**；文字 p.287 P:218–219 | Check.checkStationOperation J:131–190：按**每架无人机**跨所有趟累加（J:149,178），超过按站型的 T 则 false（J:181–183） | E2:131（每槽 duty=0）→ E2:175（duty += 每趟 duration）→ E2:184–186（duty > limit + 1e-7 违规）；E1:93–106（duty 在 _target_legal/_return_legal 内闭合） | **数值等价，但有 3 处口径差** | ① 式(8) 同样把 t_f 记在每条弧上（n+1 次/趟），实现按目标 n 次；② Java 把"最后节点服务时间"写在弧循环**内部**（J:173–174），若无条件成立会按 (n+1) 次累加——因站 serviceTime 恒为 0（PP:70）而无害；③ Java 用严格 >（等于可行），evaluator 用 > + 1e-7 |
| 13 | 服务与返航限制（能量含返航） | 式(9)(10) p.288 P:280–284；文字 P:229–230 | Check.calculatePathEnergy J:96–119（逐弧 travel×p1 + 目标 serviceEnergy）；路径以站结尾故含返航段；插入时 checkPathEnergy J:123 | E2:162–167（length 含首末返航段；energy = travel×flight_energy + Σ serviceEnergy）；E1:85–98（+ back×flight_energy） | **数值等价（等号边界不同）** | Java checkPathEnergy 用严格 <（energy==battery 判不可行，J:123）；evaluator 用 > capacity + 1e-7（等号可行，E2:173）。量级 1e-7，属构造边界 |
| 14 | 站工作时段 T_s / T_l | p.287 P:205–206；p.293 P:624–625（8 h / 10 h） | Main.java:13–14（480 / 600 min） | PP:14–15（480 / 600） | 一致 | — |
| 15 | 参数集（速度、能耗率、电池、半径、成本） | p.287 P:220–224；p.293 P:613–625；S p.32 Table A1 | Main.java:10–29（900 m/min、0.018/min、0.81/1.0、4000/5000、22.8/30.4/5/8、0.5） | PP:8–20（同值，逐个对齐） | 一致 | 论文 15 m/s = 900 m/min；p2=0.020 与实例 serviceEnergy=0.2 = 0.02×10 min 自洽 |
| 16 | TSALNS 外层（选址层） | p.290 Algorithm 1 L3–18（P:372–392）；§4.2.1 p.291 P:445–453 | Main.main **500** 次（J:32,141）；每次 LocationOperator.applyRandomNeighborhood（J:144）→ isFeasible（J:149）→ 全部路线用 Init.generateRoutes1 重生成（J:155–158）→ 100 次路线局部搜索（J:170–196）→ ALNS（J:199–211）→ 全成本 SA 接受（J:214–221） | 不适用（evaluator 只评分，不搜索） | **部分一致** | ① 论文列 5 个选址算子（Upgrade/Degrade/Swap/Close/**Open**，P:449–453），Java 只有 4 个（J:111–121 nextInt(4)），**没有 Open**；Open 只能由 swap 与关闭站交换间接实现；② Close 不检查"可重分配"（J:84–105 只挑已开站），改由 isFeasible 的全覆盖检查善后（J:127–145）；③ 论文 Algorithm 1 未给外层接受准则，Java 用 SA（J:219–221）；④ 升级/降级都只走一步（0→1→2、2→1→0），与论文一致（P:449–450） |
| 17 | TSALNS 路线层（局部搜索 + ALNS） | p.290 Algorithm 1 L9–17（P:379–391）；§4.2.2 p.291 P:455–462；§4.3 p.291 P:464–505；S p.32 Algorithm A.1 | 局部搜索：**100** 次随机算子（J:170–196），**无接受准则**（算子内部不可行则回退）；ALNS：标称 **5000**（J:10），但因 temperature > finalTemp（J:11,57）在 **270 次** 处停止 | 不适用 | **不一致（3 处）** | ① Table A1 的 K'_max=500（S:86），代码写 100（J:170）；② Algorithm A.1 的 K''_max=5000（S:88）在代码中被温度下限截断：T0=1000、α=0.95，解 1000·0.95^k ≤ 1e-3 得 k=270（末温 9.6688e-4）→ **实际每个外层候选只跑 270 次 destroy-repair**；③ 论文 Algorithm 1 L13 要求局部搜索 "Accept when improved"，代码对 100 次算子**不做接受判定**（J:170–196 直接赋值） |
| 18 | ALNS 算子族 | destroy p.291–292 P:507–539；repair p.292 P:541–567 | destroy 4 个（J:122–160）：greedyRemove / probabilisticGreedy / randomRemove / similarityRemove；repair 4 个（J:162–179）：nearestInsertion / minimumRegret / loadBalancing / prioritized | 不适用 | **部分一致** | ① similarityRemove 论文/Algorithm A.2 一次删**一对**（S:59–60），代码一次只删**一个**（J:833–840）；② maxRegretInsertion 的 k=1 在论文里恒等于 0（退化），代码的 calculateRegret（J:1578–1588）取"与次优之差"再选**最小**值（J:1319–1325）→ 实际退化为 cheapest insertion；③ probabilisticGreedyRemove 每架无人机最多删 1 个（J:683–696），删完**不做**可行性复检（J:702） |
| 19 | ALNS 得分/权重更新 | §4.3 p.291 P:472–501（η 与 w 公式） | ALNSSolver.updateOperatorWeights J:212–237（ξ=1/−0.2，J:222；τ=2·ΔC/(1+ΔC)，J:223–225；γ=0.9，J:229）；updateAllWeights J:239–265（β=0.8，J:246；clamp 0.1/5.0，J:246,255；每 50 次重置统计，J:234,261–264） | 不适用 | **部分一致** | w_ub：Table A1 = **0.5**（S:75），代码 = **5.0**（J:246,255）；论文 η 在 "improved" 时给 ξ，代码在 **accepted** 时给 ξ（被接受的劣解也拿 +1）；论文 ΔC 相对 current，代码 improvement = bestCost − newCost（J:86）相对 **best-so-far** |
| 20 | SA 接受与降温 | §4.3 p.291 P:502–505；S p.32 Algorithm A.1 L10–17 | Main J:219–221（外层）；ALNSSolver.acceptNewSolution J:181–187；降温 J:110（α=0.95） | 不适用 | 一致（除 §A-17 的停止条件） | P_acc = 1 if ΔC<0 else exp(−ΔC/T)，三处同式 |
| 21 | "latest task completion time"（M_return 的来源） | p.295 §5.3 P:756–757（**只有文字指标名，无公式**） | Check.calculateLatestTime J:594–618（详见 §C） | E2:210 M_return = max(station_makespan)；E2:190 station_makespan = max(slot_duty) | **定义为同一量**（见 §C 的 4 个前提） | 论文把它当第二性能指标；代码把它当输出量；evaluator 把它当主目标。三者数值定义一致 |

### A.2 三处"表示层"差异必须展开（它们决定能否把 Java 结果当锚点）

**A.2-1 SABS 的第 0 槽可被写满（原始 Java 的模型偏差）**
- 触发点：`prioritizedInsertion` 第 1 步遍历所有已开站的**空槽**，为空槽新建一条 trip（J:1405–1436；槽 0 对 SABS 恒为空）。电池容量按 `(stationTypes==2 && droneIdx==0) ? largeBattery : smallBattery` 取（J:1418–1419）→ SABS 槽 0 用 SD 电池。
- 自检：`checkStationPathsEnergy` 对 SABS（hasLargeDrone=false）把两个槽都当 SD（J:551–555）→ 自检通过。
- 后果：一个 SABS 实际并行使用 2 架 SD，违反原文 §3.1（P:92–93）与式(12)（P:292–294）的意图；成本不变（槽 0 不另收机费，J:270–274）。
- evaluator 的处置：kind==1 且 slot==0 且有 trip → 记 `large_drone_at_small_station`（E2:142–143），original_feasible=False（E2:216）。
- 复现包的处置：`REPRO_PROTOCOL.md:40` 明确 "Raw Java can place SABS work in both route storage slots… J0 therefore requires independent feasibility auditing"；`SEMFIX_FULL_RESULTS.md:76` 报 P1/P2 均 600/600 独立可行。

**A.2-2 t_f 的计费口径（式(1) 与式(8) 同病）**
- 式(1)：Σ_(j,k)∈A c_t x (t_jk + t_f)，A 含"站→首目标"与"末目标→站"两条弧（A 定义 P:202；式(3) 要求从站出发、回站 P:259–263）。一趟 n 个目标有 n+1 条弧 → 字面计 (n+1)·t_f。
- 式(8) 同样是弧和（P:275–278），字面也计 (n+1)·t_f，且返航段也计入 T。
- 实现：calculatePathTime / calculateDroneTime 逐弧加 travel，服务时间按**目标**加（J:38–40、330–332），每趟恰 n 次；evaluator 同理（E2:162–166）。
- 数量级（估算，仅示量级）：t_f=10 min、c_t=0.5 → 每趟多 5 个成本单位；3_10 实例总成本量级约 146、趟数量级约 10 → 字面重算可能高出 10%–30% 量级（不是 0.1% 级；精确值取决于该图实际趟数，本文未重算）。**结论：任何"按式(1) 重算成本"的审计都会与作者代码/数据冲突；必须按实现语义（每目标一次）计算。** 这是原文排版/建模笔误，不是实现错误（正文 P:235–236 与 p2·t_f=serviceEnergy 的实例数据都支持实现语义）。

**A.2-3 死代码与不可达路径（防止后续误用）**
以下方法在 `official_source` 中**定义但从未被调用**（grep 全目录仅 1 处命中，即定义本身）：
- `Check.checkStationOperationLRP`（J:192–250）——J:231 把服务时间写成 `serviceTime * serviceTime`，显然是复制错误；不可作为 LRP 口径依据。
- `Check.checkEnergyConstraints`（J:447–481）——它把**跨趟**能量累加后与单块电池比较（J:471–476），与"每趟换电"（式(17)(18)）矛盾；若被误用会禁止多趟。
- `Check.calculateSolutionTime`（J:292–304）——所有无人机时间**求和**，不是 M_return。
- `RoutingOperator.greedyInsertMinCost`（J:890–1002）、`swapPointsBetweenDrones`（J:298–364）。
- `Check.calculatePathLength` 只被能量/打印路径使用（J:418,565）。

**A.2-4 参数接线**：`calculatePathCost` 用静态 0.5（J:13,75），而 `calculateTotalCost` 用传入的 unitTimeCost（J:260,284）。Main 两处都传 0.5（J:29,126），故当前无差异；但任何改 c_t 的实验都不能只改 Main 的常量。

---

## B. 逐式差异（原文 vs Java vs evaluator）

格式：**原文** → **Java** → **evaluator** → **差异与判定**。

### B.1 式(1) 目标函数（p.288，P:251–254）

- 原文：min Σ_i[ z_li·c_l + z_si·c_s + z_li·(c1+c2) + z_si·c1 ] + Σ_i Σ_d Σ_(j,k)∈A c_t · x^i_d_jk · (t_jk + t_f)。
- Java：totalCost = Σ_station fixed(type) + Σ_drone calculateDroneTime(dronePaths) × unitTimeCost（J:263–288），其中 calculateDroneTime = Σ_trip( Σ_arc d/v + Σ_target service )（J:310–343）。
- evaluator：fixed（E2:117–120）+ operating × time_cost（E2:198,205），operating = Σ_si Σ_slot duty（E2:187），duty = Σ_trip(travel + Σ service)（E2:166,175）。
- 差异：
  1. **t_f 口径**：式(1) 每条弧加 t_f（n+1 次/趟）；Java/evaluator 每目标一次（n 次）。判定：实现正确、式子笔误，见 §A.2-2。
  2. 式(1) 的求和下标是"弧"，实现是"无人机×趟×目标"；在"每趟从站出发并回站"的可行解上两者只差上述 t_f 项。
  3. 固定成本：式(1) 用 z_li/z_si 线性化；Java 用 if/else（J:270–274）；evaluator 同 if/else（E2:117–120）。**逐站等价**。
  4. 无四舍五入：Java 打印全 double（J:271,284）；evaluator 保存全 double；论文 Table 1 才四舍五入到 2 位（P:594–606）。
- 判定：**成本函数在"每目标一次服务时间"的语义下三方一致**；用式(1) 字面弧和重算会系统性偏大。

### B.2 式(2)–(6) 结构与指派约束（p.288，P:255–274）

- (2) 每目标恰被访问一次；(5) 每目标恰指派给一架无人机；(6) 每址至多一种站型。
- Java：全靠"目标集合 → 站 → 无人机 → trip"的容器结构保证（Init.allocateTargetsToStations J:184–228；删除/插入算子保持节点数）。**没有显式校验**。
- evaluator：E2:191–195 逐 ID 计数；重复/缺失即 issue（E2:192–195），original_feasible=False（E2:216）。
- 差异：**Java 的自检不含 (2)(5)(6)(7)**（isOverallSolutionValid 只查能量 J:484–525；checkStationOperation 只查时间 J:131–190）。因此"Java 输出可行"只等于"能量+时间可行"，不等价于原文可行。复现包因此要求独立审计（`REPRO_PROTOCOL.md:29–31`）。

### B.3 式(7) 覆盖（p.288，P:273–274）

- 原文：v·t_ij·y^d_ij ≤ z_si·R_s + z_li·R_l，即指派目标必须落在所属站半径内。
- Java：Calculator.calculateDistance(station,target) ≤ radius（J:175、213；插入算子 J:935、1034、1145）；半径按站型取（J:208）。
- evaluator：_distance(station,node) > radius + PHYSICS_TOLERANCE 才记 coverage（E2:153–155），PHYSICS_TOLERANCE=1e-7（E2:18）；E1 同（E1:83，EPS=1e-7）。
- 差异：**容差**。Java 严格 ≤；evaluator ≤ radius+1e-7。浮点上 Java Math.sqrt(Math.pow(dx,2)+Math.pow(dy,2))（J:23）与 Python math.hypot（E2:35）可能差 1 ulp（约 1e-12 m 量级），远小于 1e-7。

### B.4 式(8) 站工作时段 / 累计 duty（p.288，P:275–278）

- 原文：Σ_(j,k)∈A x^i_d_jk·(t_jk + t_f) ≤ T_l·z_li + T_s·z_si，对每架无人机在其所属站上成立。
- Java：checkStationOperation 对每个站、每架无人机累加 **所有趟** 的 distance/speed + service（J:148–185），与按站型的 T 比较（J:145），accumulatedTime > maxAllowedTime 即 false（J:181–183）。
- evaluator：duty 每槽跨趟累加（E2:131,175），duty > limit + PHYSICS_TOLERANCE 记 cumulative_duty（E2:184–186）；E1 在动作级提前闭合（E1:93–98、105–106）。
- 差异：
  1. t_f 每弧 vs 每目标（同 §B.1）。
  2. Java 的 lastNode.getServiceTime() 写在弧循环**内部**（J:173–174），每趟会被加 (n+1) 次；因站 serviceTime=0（PP:70；官方实例站行 serviceTime=0）而无害。**若换成站有非零服务时间的扩展模型，这里会悄悄多算。**
  3. 严格 > vs > + 1e-7：accumulatedTime == T 时 Java 判可行、evaluator 也判可行（需要 > T+1e-7 才违规）→ **此条一致**；只有 T < t ≤ T+1e-7 的构造解会分歧。
  4. **关键语义**：Java/evaluator 的 duty 都是"跨趟累计、换电不清零"；这正是当前研究合同"RETURN 回所属站换电池但不清零累计 duty"（`BRIEF_AGENT_CONTEXT.md:19`）的原文与代码依据（式(8) + J:149,178 + E2:175）。
  5. 论文自己承认该约束在小实例不紧：S:447–448 "even stringent station duration limits do not become binding"；P:859–861 同义。→ 在 Liu 的 120 图上 duty 不 binding，但在 W/应急扩展里会成为紧约束。

### B.5 式(9)–(10) 能量与返航（p.288，P:280–284）

- 原文：(9) e_k + p2·t_f + p1·t_jk ≤ e_j + (1−x)·M_jk，M_jk = Q_l + p2·t_f + p1·t_jk（P:329）；(10) p1·t_ji ≤ e_j + (1−x)·M，M = Q_l（P:331）。
- Java：calculatePathEnergy 逐弧 travelTime × energyRate + 目标 serviceEnergy（J:96–119）；每趟与电池容量比较（J:574–579）；返航段因路径以站结尾而自动包含。
- evaluator：energy = travel × flight_energy + Σ node.energy（E2:167），energy > capacity + 1e-7 违规（E2:173）；length 用 [station]+nodes+[station]（E2:162–163）。
- 差异：**等号边界**。checkPathEnergy 用严格 <（J:123）→ energy==capacity 判不可行；evaluator 用 > capacity+1e-7 → 等号可行。另：式(9) 的 e_j 是"访问 j 后剩余电量"，实现是"整趟累计消耗"，在"每趟满电"（式(17)(18)）下等价。
- **陷阱**：checkEnergyConstraints（J:447–481）把能量跨趟累加，与换电矛盾，是死代码（§A.2-3）；不得当作式(9)(10) 的实现。

### B.6 式(11)–(12) 指派一致性（p.289，P:290–294）

- 原文：(11) 2x ≤ y_j + y_k（只能服务指派给它的目标）；(12) Σ_j y_ij^2 ≤ (1−z_si)|J|（SABS 不配 LD，不能有 LD 任务）——原文印的是 y_ij 的平方，按上下文应为 LD 的 y（y^{d2}_ij）的笔误。
- Java：y 变量不存在，指派由"节点属于哪个站的哪个槽的哪条 trip"隐含（Solution.java:8）；式(12) 由"槽 0 在 SABS 正常路径下为空"实现（Init J:268–272 只填小站槽 1）。
- evaluator：槽 0 在 SABS 有 trip → 直接 issue（E2:142–143）。
- 差异：**Java 的式(12) 不是硬约束**——prioritizedInsertion 可写 SABS 槽 0（J:1417–1434），自检仍通过（J:551–555）。这是 A.2-1 的另一面。

### B.7 式(13)–(15) 多趟与机数（p.289，P:295–307）

- 原文：(13)(14) 用 w 连接"前一 trip 末目标"与"后一 trip 首目标"；(15) ΣΣx − ΣΣΣw ≤ k_l·z_l + k_s·z_s。
- 解读：(15) 左边 = 出发弧数 − trip 间连接数 = **实际使用的无人机数**（每架 t 趟贡献 t−1 个 w），故 k_s、k_l 是"站内可用机数"。论文正文只给"每站足够电池、SABS 1 架 SD、DABS 1 SD+1 LD"（P:229–233、P:92–93），**未给 k_s、k_l 的数值**；由语义推得 k_s=1、k_l=2。
- Java：槽位数固定 2（Init J:275–278），无 w；SABS 槽 0 例外见 A.2-1。
- evaluator：必须 2 槽（E2:121–124），SABS 槽 0 必须空（E2:142–143）；E1 的 slots 直接由站型决定（E1:47）。
- 差异：表示不同、语义等价；**唯一实质差异是 A.2-1 的 Java 例外**。

### B.8 式(16)–(22) 站点互连与域（p.289，P:309–321）

- (16) x^i_d_ij = 0（站间不直连）：Java 的 subpath 形如 [station, targets…, station]（Init J:320；各算子 subRoute.get(0) 为站，J:1615），故站间弧不存在 → 一致。
- (17)(18) 每趟满电：见 §B.5 → 一致。
- (19)–(22) 0-1/非负：Java 用 int/double 容器、evaluator 用类型检查（E2:96–102,112–120）→ 一致。

### B.9 式(23) loadBalanceInsertion 得分（p.292，P:557–558）

- 原文：score = ρ·(T_max − T_after)/T_max + (1−ρ)·1/(1+|C_after − C_before|)，ρ=0.6（S:83）。
- Java：calculateLoadBalanceScore = 0.6·((maxAllowedTime − newDroneTime)/maxAllowedTime) + 0.4·(1/(1+|newCost−originalCost|))（J:1640–1653）。
- evaluator：不适用（评分器不搜索）。
- 差异：**一致**（ρ 硬编码 0.6，与 Table A1 相同；T_max 用按站型的 maxAllowedTime；C 用 calculatePathCost = 0.5×时间）。若未来把 ρ 参数化，需同时改 J:1652。

### B.10 similarity 公式（p.292，P:527–533）

- 原文：Sim(j,j') = λ_k / δ(j,j')，k=3 若"站 i 能覆盖 j' **且** 站 i' 能覆盖 j"；k=2 若单向；k=1 否则；λ3 > λ2 > λ1，Table A1 给 λ3=0.8、λ2=0.5、λ1=0.2。
- Java：calculateSimilarity（J:845–882）用"**任一已开站**是否覆盖 a/b"判类（J:855–869），再返回 0.8/d、0.5/d、0.2/d（J:871–881），距离下限 1e-6（J:850）。
- 差异（三处）：
  1. **判类条件不同**：论文要求"对方所属站能覆盖自己"（互覆盖）；代码只看"是否存在某个已开站覆盖"，而循环**包含自己所属站**（J:855–869）→ 由于目标必然落在自己站半径内，aCoveredByOther/bCoveredByOther 几乎恒为 true → **相似度几乎恒为 0.8/δ，退化为纯距离反比**。
  2. λ 命名反向：代码变量 lambda1=0.8、lambda2=0.5、lambda3=0.2（J:871–873），论文 λ3 最大。数值映射正确、命名易误读。
  3. 论文正文说"removing two nearby targets simultaneously"（P:522–523）、Algorithm A.2 选一对 (j*,k*) 并删两个（S:59–60）；代码只删**一个**（J:833–840）。同时代码在 min–max 归一化后统一 +1e-6 防零权重（J:811）。
- 影响：similarityRemove 的实际行为是"按 Σ Sim 的轮盘选 1 个点"，不是论文描述的"成对移除"；任何"复现 similarityRemove 语义"的声明都必须按代码口径。

### B.11 ALNS 得分/权重（p.291，P:474–501）

- 原文：s(t+1) = γ·s(t) + η；η = ξ + τ·ΔC/(1+ΔC) if improved else −φ；w(t+1) = max(w_lb, min(w_ub, β·w(t) + (1−β)·s_total/h))；P(w_i) = w_i/Σw。
- Java：baseReward = accepted ? 1.0 : −0.2（J:222）；若 accepted && improvement>0 再加 2.0·improvement/(improvement+1)（J:223–225），其中 improvement = bestCost − newCost（J:86）；score = 0.9·score + reward（J:229–231）；每 50 次 w = clamp(0.8w + 0.2·(score/count), 0.1, 5.0)（J:234–247），随后清零 score/count（J:261–264）；选择用 rand ≤ Σw 累积（J:189–198）。
- 差异：
  1. w_ub：Table A1 **0.5**（S:75）vs 代码 **5.0**（J:246,255）。这是 `REPRO_PROTOCOL.md:39` 记录的已知差异；P1 用 5.0、P2 用 0.5（`REPRO_PROTOCOL.md:14–15`）。
  2. "improved" → 代码是"accepted"：被 SA 接受的**更差**解也拿 ξ=+1（论文应给 −φ）。
  3. ΔC 基线：论文相对 current（Algorithm A.1 L10：ΔC = Φ(S'') − Φ(S)，S:25），代码相对 **best-so-far**（J:86）。
  4. 窗口：论文 s_total/h 是滑动窗口；代码用"每 50 次清零"的块窗口（J:234,261–264），并保留 0.9 衰减（等于每次更新都带历史）。
  5. selectOperator 用 rand ≤ accum（J:195），相等时偏向低索引（测度零）。
- 影响：这些是"参数/实现层面"的差异，不影响模型可行性，但会影响"复现的是哪一版 TSALNS"的表述；不得把代码版称作"严格按论文 η 公式的实现"。

### B.12 SA 接受与停止（p.291，P:502–505；S:26–27）

- 原文：P_acc = 1 if ΔC<0 else exp(−ΔC/T)；每轮 T ← αT；ALNS 跑 K''_max=5000。
- Java：acceptNewSolution（J:181–187）与 Main（J:219–221）同式；temperature *= 0.95（J:110）。
- **停止条件差异**：for (iter=0; iter<5000 && temperature>finalTemp; iter++)（J:57），finalTemp=1e-3（J:11）→ T0=1000、α=0.95 时 **270 次**后退出（末温 9.6688e-4），不是 5000 次。Python 端口同样实现该停止（`source_snapshot/lrphsd/tsalns_v6.py:21,184`：final_temperature 1e-3）。
- 判定：**论文 K''_max=5000 是名义上限**；实际每次外层候选约 270 次 ALNS 迭代。引用"5000 次 ALNS"时必须注明这一截断。

### B.13 三层迭代次数汇总

| 层 | 论文（S:84–88 Table A1） | Java（官方源） | P1（`REPRO_PROTOCOL.md:14`） | P2（`:15`） |
|---|---:|---:|---:|---:|
| 外层 K_max | 500 | 500（J:32） | 500 | 500 |
| 路线局部搜索 K'_max | 500 | **100**（J:170） | 100 | 500 |
| ALNS K''_max | 5000 | 5000 名义 / **270 实际**（J:10–11,57） | 5000 名义 / 270 实际 | 同 |
| w_ub | 0.5 | **5.0**（J:246） | 5.0 | 0.5 |

### B.14 Table A1 参数逐项核对（S:65–88）

| 参数 | Table A1（S 行） | Java（J 行） | 一致? |
|---|---|---|---|
| γ 得分衰减 | 0.9（S:67） | 0.9（J:229） | 一致 |
| ξ 基础奖励 | 1（S:68） | 1.0（J:222） | 一致 |
| τ 增强因子 | 2（S:69） | 2.0（J:224） | 一致 |
| φ 拒绝惩罚 | 0.2（S:70） | 0.2（J:222） | 一致 |
| β 权重平滑 | 0.8（S:72） | 0.8（J:246–247） | 一致 |
| h 更新周期 | 50（S:73） | 50（J:20,234） | 一致 |
| w_lb | 0.1（S:74） | 0.1（J:246） | 一致 |
| w_ub | **0.5**（S:75） | **5.0**（J:246） | **不一致** |
| α 降温 | 0.95（S:76） | 0.95（J:8,110） | 一致 |
| T0 | 1000（S:78） | 1000（J:7） | 一致 |
| λ3/λ2/λ1 | 0.8/0.5/0.2（S:79–82） | 0.8/0.5/0.2（J:871–873，变量名反向） | 数值一致、命名反向 |
| ρ | 0.6（S:83） | 0.6（J:1652） | 一致 |
| K/K'/K'' | 500/500/5000（S:84–88） | 500/100/5000(270)（J:32,170,10–11） | **不一致** |

### B.15 容差、浮点、舍入、tie-break 汇总

| 主题 | 原文 / Java | evaluator | 差异与后果 |
|---|---|---|---|
| 成本容差 | Java 无容差（double 全精度比较，J:182,219） | COST_TOLERANCE = 1e-7 **绝对成本单位**（E2:17,47–50）；S 合同 cap：cost ≤ anchor.cost·(1+epsilon) + 1e-7，epsilon=0（E2:273–277；`BRIEF_AGENT_CONTEXT.md:19`） | evaluator 的 1e-7 是"绝对 + 只向上给"的松弛；对 cost≈150–1000 的相对量级 1e-10~1e-9 |
| 物理容差 | Java 覆盖/能量/时间都用严格比较（J:123,175,181,577） | PHYSICS_TOLERANCE = 1e-7（E2:18）用于覆盖 E2:154、能量 E2:173、duty E2:185；E1 用 EPS = 1e-7（E1:8,83,98,106） | 仅等号附近的构造解分歧；真实实例不受影响 |
| 浮点距离 | Math.sqrt(Math.pow(dx,2)+Math.pow(dy,2))（J:22–24） | math.hypot(dx,dy)（E2:35）；端口用 sqrt(dx^2+dy^2)（`source_snapshot/lrphsd/evaluator.py:33,35`） | 1 ulp 级差异（约 1e-12 m），远低于 1e-7 |
| 求和顺序 | Java 逐弧顺序累加（J:29–41） | Python 先 sum(length) 再除速度（E2:163–165） | 结合律差异，约 1e-13 相对；`REPRO_PROTOCOL.md:24` 要求同一 witness 上 Java/Python 成本一致到 **1e-7 绝对**、可行性到 **1e-9** |
| 四舍五入 | Java 打印全 double（J:271,284） | evaluator 存全 double（E2:196–215） | 论文 Table 1/2/3 才四舍五入到 2 位（P:594–606）；BstGAP 用 UB 做分母（P:639–640, S:117–118） |
| tie-break（选址） | Init.stationSet 用严格 >：同覆盖保留**先出现**的站；同一站内先试 SABS 覆盖、仅当大半径覆盖**严格更大**才选 DABS（J:35–44） | 不适用（评分器） | 与论文"same coverage 优先 SABS"（P:363–365）**方向上一致**，但"先出现索引"这一层论文未写 |
| tie-break（插入） | 所有插入算子用严格 < 或 > 保留**首个**最优位置；扫描序 = 站升序→槽升序→trip 升序→位置升序（J:971,1073,1184,1321,1483） | 不适用 | 确定性 tie-break，无随机；复现端口须保持同序 |
| tie-break（算子选择） | selectOperator 用 rand ≤ accum → 相等偏向低索引（J:195）；applyRandomNeighborhood 用 nextInt(4)（J:113） | 不适用 | 测度零；但端口若用 < 会改变极少数决策 |
| latest-time | 论文只有文字名（P:756–757） | E2:210 | 见 §C |

### B.16 原文自身的一处记号不一致（影响读表）

- §3.1（P:201–202）：J = {1,…,m} 是**目标**，I = {m+1,…,m+n} 是**候选站**。
- §5.1（P:611）："|J| is the number of candidate locations, |I| is the number of targets" —— 与 §3.1 **相反**。
- 实例文件名 3_10_1 的真实内容：10 个目标（nodeNo 1–10）+ 3 个站（nodeNo 11–13）→ 第一位是**站数**、第二位是**目标数**，即与 §5.1 的句子一致、与 §3.1 的集合定义相反。
- 结论：读 Table 1 时 3_10 = 3 候选站 / 10 目标；引用 §3.1 的 J/I 时必须注明这一冲突（采用"文件名第一位=站数"的实测口径）。

---

## C. Check.calculateLatestTime 的精确定义与 M_return 同一性

### C.1 代码逐行（J = `reproduction/reviewer_package_semfix/reference/java/official_source/Check.java`）

```java
594  public static double calculateLatestTime(
595          List<List<List<List<Node>>>> paths,
596          double droneSpeed) {
598      double latestTime = 0.0;
601      for (List<List<List<Node>>> stationPaths : paths) {          // 每站
603          for (List<List<Node>> dronePaths : stationPaths) {       // 每架无人机（槽）
604              double totalDroneTime = 0.0;
607              for (List<Node> subPath : dronePaths) {               // 每趟
608                  double subPathTime = calculatePathTime(subPath, droneSpeed);
609                  totalDroneTime += subPathTime;
610              }
613              latestTime = Math.max(latestTime, totalDroneTime);    // 取最大
614          }
615      }
617      return latestTime;
618  }
```

calculatePathTime（J:22–48）：

```java
29  for (int i = 0; i < path.size() - 1; i++) {
34      double travelTime = Calculator.calculateDistance(currentNode, nextNode) / droneSpeed;
35      totalTime += travelTime;
38      if (i > 0 && i < path.size() - 1) {
39          totalTime += currentNode.getServiceTime();      // 内部目标的服务时间
40      }
41  }
44  Node lastNode = path.get(path.size() - 1);
45  totalTime += lastNode.getServiceTime();                 // 末节点（=站）的服务时间
```

### C.2 数学定义

对任一完整解，令 D 为所有（站, 槽）对，T_d 为槽 d 的 trip 集合，trip r = [s, j_1,…,j_k, s]：

```text
time(r) = Σ_{a=1..k+1} dist(x_{a-1}, x_a)/v  +  Σ_{b=1..k} service(j_b)  +  service(s)     （x_0 = x_{k+1} = s）
L       = max_{d ∈ D}  Σ_{r ∈ T_d} time(r)
```

- 站点服务时间 service(s) = 0（PP:70 强制；官方实例站行 serviceTime=0）→ 末项为 0，且 time(r) 就是"该趟的行驶时间 + 全部目标服务时间"。
- 因此 L = **所有物理无人机中，累计（行驶+服务）时间最大的那架的总时间**，且**包含最后一趟的返航段**。

### C.3 evaluator 的对应实现（E1/E2）

- 逐趟 duration：duration = length/speed + Σ service，length 为 [station]+nodes+[station] 的折线长（E2:162–166）。
- 逐槽累加：duty += duration（E2:175）；duty > limit + 1e-7 记违规（E2:184–186）。
- 逐站取最大：station_makespan.append(max(station_loads, default=0.0))（E2:190）。
- 全图取最大：result["M_return"] = max(result["station_makespan"], default=0.0)（E2:210）。
- 动作级同义：E1 的 cumulative_duty（E1:69）在 RETURN 时 += trip_elapsed + back（E1:156），potential = max(cumulative_duty + trip_elapsed)（E1:266–269）是同一量的进行时版本；终局时 potential = max_d duty_d = M_return。

### C.4 判定：**M_return 与 Check.calculateLatestTime 是同一数学定义**

逐项对齐：

| 项 | Java | evaluator |
|---|---|---|
| 每趟 = 行驶 + 目标服务 | J:34–40（+J:45 的 0） | E2:162–166 |
| 跨趟累加、不重置 | J:607–610 | E2:131,175 |
| 对"每架无人机/槽"取 | J:603 | E2:126,189 |
| 对全图取最大 | J:613 | E2:190,210 |
| 含返航段 | 路径以站结尾（J:320） | [station]+nodes+[station]（E2:162） |
| 空趟忽略 | path.size()<=2 → 0（J:24–26,52–54） | if not trip: continue（E2:137–139） |

**结论：在下列 4 个前提下，M_return ≡ Check.calculateLatestTime，不是新指标：**

1. 解的站 serviceTime = 0（否则 Java 的 J:45 会把站服务算 1 次、而 J:173–174 的 duty 路径会算 n+1 次，两者不一致）；
2. 解在 evaluator 意义下"结构合法"（2 槽、SABS 槽 0 为空；否则 Java 会把 SABS 的第 2 架 SD 也算进 max，得到 evaluator 拒绝的解，二者不可比）；
3. 只对完整解比较（Java 的 calculateLatestTime 不检查 T 上限；evaluator 的 M_return 对不可行解也照算，但 admissible 要求 original_feasible，E2:288）；
4. 无 NaN/Inf（E2:169–171 会拦）。

**必须同时记住的两个"不是 M_return"的量：**

- Check.calculateSolutionTime（J:292–304）= **所有**无人机时间之和 → 与成本同向，不是 M_return。
- evaluator 的 M_service = max target completion（E2:211）= 最后一个**目标**的服务完成时刻（不含返航）→ 这才是论文文字"latest task completion time"（P:756）的字面读法。当前 S 合同用的是 M_return（含返航），不要混用；两者在单趟单目标时相同，多趟时 M_return ≥ M_service。

---

## D. 原文摘录（无风/无禁飞；future work）

### D.1 无风、无禁飞假设（p.288，P:226–227）

> "…we neglect the energy usage during the ascent and descent phases and assume that all drones operate at a fixed cruising altitude. **Furthermore, missions are assumed to be conducted under calm, windless conditions, and no-fly zones are not considered.** All time-related parameters are expressed in minutes."

- 完整上下文 P:224–228：能耗只计 hovering + cruising（引 Raj & Murray 2020；Zhang et al. 2021），忽略升降。
- 同页 P:222–224 定义 t_ij = Euclidean/v、p1（巡航）、p2（悬停）、t_f（每目标固定检查时间）——**风会改变 t_ij 与 p1，NFZ 会改变可行弧集**，这两条正是被显式排除的。

### D.2 future work（p.299，P:923–925）

> "**Future work may also consider partitioning inspection targets into multiple groups with heterogeneous inspection times, which is particularly relevant in post-disaster relief scenarios. In addition, other practical operating constraints, such as wind conditions and the existence of no-fly zones, can be incorporated into the model.**"

- 前一句（P:920–923）是"把 DABS 的机型配置也变成决策变量"的扩展与"需要专门高效算法"的方向；S:450–537（Appendix D）给了该扩展的模型 (D.1)–(D.8) 与 Table D1 的初步结果（平均 UB 465.59 → 442.58，p.40）。
- 因此 P:923–925 一句话同时点名了四件事：**异质服务时间 / 灾后场景 / 风 / 禁飞区**。

---

## E. 哪些扩展是原文支持的"动机"，而不是算法新颖性

### E.1 原文明确写为 future work（可直接引用为动机）

| 扩展 | 原文位置 | 原文措辞强度 | 能支持什么 | 不能支持什么 |
|---|---|---|---|---|
| 风（wind） | P:226–227（排除）；P:924–925（future work） | 明确"未考虑"+"可纳入" | 问题重要性、模型扩展的合法性、与 Liu 基准的可比性边界 | 不能支持"风下路径是本文首次提出"；更不能支持 RL 必胜 |
| 禁飞区（no-fly zones） | 同上 | 同上 | NFZ 作为新增约束的合法性 | 同上；也不能支持"NFZ 几何处理"是新颖算法 |
| 异质服务时间 / 分组检查 | P:923–924 | 明确 future work | "heterogeneous service" 扩展的动机 | 不能支持具体分组机制的新颖性 |
| 灾后（post-disaster relief） | P:923–924；P:769–770（time-critical missions 含 disaster assessments）；P:125–126（引 Chowdhury et al. 2021 灾后巡检） | 场景动机 | 应急/灾害场景的合法性、时间目标的现实性 | 不能支持"灾后应急"本身是贡献 |
| 站内机型配置作为决策 | P:920–923；S:450–537、Table D1 p.40 | "natural direction for future research" + 初步数值 | 异构部署扩展的动机与已知收益量级（成本可再降） | Table D1 是 **Gurobi 限时**结果（S:529–530），不是启发式/RL 的对照 |

### E.2 论文正文支持、但未建模的"第二指标"

- P:756–757："Two performance indicators are used: the total cost and the latest task completion time." → **时间指标在原文是第二指标，不是目标函数**（目标函数是式(1) 的成本）。
- P:767–774、P:804–814：讨论 L-L 配置"更适合 time-critical missions"、异构配置"cost/time 折中" → 支持"以返航完工时间为目标"的**问题动机**，但原文从未以 min-max 时间为目标求解。
- 因此：当前 S 合同"cap 成本、min M_return"是**在原文模型内换目标**，属于合同选择，不是原文结论；引用时必须写清"目标置换由本项目定义"。

### E.3 原文不支持的（不得声称）

- 不支持"天气是随机过程/需要预报"：原文确定性、无风（P:226），没有随机性、没有 time window、没有在线到达。W 方向的随机事件流必须自带先例（Zhao/Han/CFA 等），不能挂到 Liu 名下。
- 不支持"多站协同/跨站改降"：原文站间不直连（式(16)），任务归属由覆盖 + 最近站分配；跨站改降是新增动作域。
- 不支持"RL/学习"：全文无学习、无 RL、无数据驱动决策；TSALNS 是元启发式。
- 不支持"120 图上的 P1/P2 差异是算法改进"：P1/P2 是**复现端口 vs Java**的参数档差异（§F），不是新算法。

### E.4 对 G0 的含义（一句话）

P:923–925 给了"为什么可以做风/NFZ/异质服务"的**问题合法性**，但**没有给任何算法步骤**；G0 需要的"实质新数学步骤"必须相对 TSALNS、Zhao VFA/rollout、Han 共享容量等先例逐式说明，不能引用这段 future work 充当新颖性证据。

---

## F. 120 地图复现协议与结果（P1 ≈ −0.0284%、P2 ≈ +0.0998%）的原始出处

### F.1 协议文件（prospective contract）

| 内容 | 位置 |
|---|---|
| 协议主体（版本身份 J0/J1/J2/J1b/J2b/P1/P2/R；输入与 witness 契约；差分阶梯；放行门） | `reproduction/reviewer_package_semfix/REPRO_PROTOCOL.md:1–39` |
| 120 图 × 5 seed × 5 独立运行；12 组 × 10 图 | `REPRO_PROTOCOL.md:22` |
| 同一 witness 上 Java/Python 成本 1e-7、可行性 1e-9 | `REPRO_PROTOCOL.md:24` |
| P1 = 500/100/5000 + w_ub 5.0；P2 = 500/500/5000 + w_ub 0.5 | `REPRO_PROTOCOL.md:14–15` |
| 已知源码差异（100 vs 500；5.0 vs 0.5；SABS 两槽） | `REPRO_PROTOCOL.md:39` |

### F.2 输入

- 120 个官方实例：`reproduction/reviewer_package_semfix/external/LRPHSD<EXECUTION_PATH>`（本次实点 **120** 个文件；12 组 × 10 图，命名 = 站数_目标数_索引）。
- 格式：5 列 CUST_NO XCOORD YCOORD SERVICE_ENERGY SERVICE_TIME（`3_10_1.txt` 首行 header；目标 serviceEnergy=0.2、serviceTime=10；站 serviceEnergy=0、serviceTime=0）。
- 参数契约：`source_snapshot/lrphsd/problem.py:6–27`（速度 900、p1 0.018、Q_s 0.81、Q_l 1.0、R 4000/5000、T 480/600、站/机成本 22.8/30.4/5/8、c_t 0.5）。

### F.3 运行与行数（既有收据，本次未重跑）

| 项 | 证据 |
|---|---|
| 命令 | `cd <EXECUTION_PATH> /opt/conda/bin/python -B run_matrix.py --profile P1 --out results/full_P1 --seeds 0,1,2,3,4 --outer 500 --timeout 600`（P2 同，--profile P2）——`SEMFiX_FULL_RESULTS.md:31–35` |
| 终局 | COMPLETE profile=P1 maps=120 seeds=5 failures=0 / COMPLETE profile=P2 maps=120 seeds=5 failures=0——`SEMFiX_FULL_RESULTS.md:39–42` |
| 行数 | 每档 600 per-run JSON + 600 压缩完整解（`results/semfix_full_P1/` 共 1,202 项 = 600 json + 600 .solution.json.gz + run_manifest.json + libr6kernel.so）——`SEMFiX_FULL_RESULTS.md:48–51`，本次实点 1,202 |
| 归档哈希 | P1 `0be434a8…de30`；P2 `67b48b8e…db2`——`SEMFiX_FULL_RESULTS.md:44–47` |
| 环境 | Java 17.0.21、Python 3.11.14、12 核配额——`REPRO_ENVIRONMENT.md:5–12` |

### F.4 结果与**符号约定**（极易误读）

审计脚本 `reproduction/reviewer_package_semfix/audit_semfix_matrix.py`；审计输出 `results/semfix_full_matrix_audit.json`（顶层键 P1/P2）；报告 `SEMFiX_FULL_RESULTS.md:63–66`。

定义：pct = 100 × (Java cost − Python cost) / Java cost，**正值 = Python 更便宜**（`SEMFiX_FULL_RESULTS.md:64–65`；`semfix_full_matrix_audit.json` 的 paired.definition）。

| 档 | 配对 | mean pct | median | 95% map-cluster bootstrap | W/T/L（Python 视角） | 可行/错误 |
|---|---|---:|---:|---|---:|---|
| **P1**（对 J1b） | 120 图 × 5 seed = 600 | **−0.028411300166225728** | 0.0 | [−0.07113, +0.01172]（含 0） | 53 / 46 / 21 | 600/600 可行，0 error（audit_errors=[]、java_audit_errors=[]） |
| **P2**（对 J2b） | 600 | **+0.0997582636054712** | 0.03328413553112791 | [+0.02554, +0.17727]（不含 0） | 71 / 33 / 16 | 600/600 可行，0 error |

**读法（必须写进任何引用）**：
- P1 的 −0.0284% 意味着"P1 端口平均比同 seed 的 J1b **贵** 0.0284%"，且 95% CI 跨 0 → 在该 map-cluster bootstrap 口径下**不能拒绝"P1 与 J1b 无差异"**（不等于证明完全相同）；
- P2 的 +0.0998% 意味着"P2 端口平均比 J2b **便宜** 0.0998%"，CI 全正 → P2 略优，但量级 0.1%，属端口/随机流差异，不是算法改进；
- 合计 **1,200 配对运行**（600 + 600），与 `BRIEF_AGENT_CONTEXT.md:19` 的"1,200 配对运行"一致；"120 官方地图 × 5 seed × P1/P2"是 120×5×2；
- 论文 Table 1 的 12 组均值/最优均落在 semfix 的 map-cluster 95% 区间内（`SEMFiX_FULL_RESULTS.md:78–82`；`results/published_table1_comparison.json`、`results/table1_bootstrap.json`）。

### F.5 重开方式与独立性

- 一键重开：`reproduction/reviewer_package_semfix/verify_semfix_package.sh`（重跑 4,200 行审计、4 例空站回归、209 例 Java/Python/C 算子差分、P1/P2 + Java 配对 witness 审计）——`SEMFiX_FULL_RESULTS.md:84–96`。
- 审计做了什么：校验 120 输入哈希与 5 seed 任务身份、源码/runner/native 哈希、逐行参数、结果文件集合、压缩 witness 哈希、**独立重算可行性与目标**；并重开 1,200 份 J1b/J2b witness 与其原始输出哈希——`SEMFiX_FULL_RESULTS.md:68–74`。
- 空站修复的边界：semfix 只改 repair 2/3 接受"已开但为空的站/机"接收者，与 Java 对齐（`SEM_FIX_PROVENANCE.md:3–12`；patch `differential/empty_station_repair.patch`，哈希 `cc9b1f66…52c6`）→ **这是"恢复作者可达域"，不是新算子**；不得写成改进。

### F.6 该协议自己列出的、与本节结论相关的已知差异

1. Main.java 100 次局部 vs Table A1 500（`REPRO_PROTOCOL.md:39`）；
2. ALNSSolver w_ub 5.0 vs 0.5；
3. 原始 Java 可把 SABS 任务放进两个槽，其自检都当 SD 而论文只允许 1 架 SD；
4. J1/J2 的 pre-ALNS guard 不是忠实端口（J1b/J2b 才是），J2 在 5_35_1 上整轮没进 ALNS、停在 Greedy 成本（`REPRO_PROTOCOL.md:39`）；
5. 作者 Random() 未播种，精确轨迹不可复现 → 本复现是"参数/约束/witness/分布级"，不是逐轨迹同一（`REPRO_PROTOCOL.md:32`；`REPRO_ENVIRONMENT.md:18`）。

---

## G. 结论清单与对当前合同的影响

### G.1 三方一致的项（可作为"忠实 Liu 锚点"的基础）

1. 站型/机型/机数的语义（SABS 1 SD；DABS 1 SD + 1 LD），前提是 SABS 槽 0 为空（§A-3、§B.6）。
2. 目标函数在"每目标一次服务时间"语义下三方一致；固定成本逐站一致（§B.1、§B.14 的参数）。
3. 覆盖半径、每趟满电换电、返航能量、站工作时段（按无人机跨趟累计）、每目标恰一次（作为模型约束）——语义一致（§B.3–B.8）。
4. SA 接受公式一致（§B.12）。
5. **M_return 与 Check.calculateLatestTime 是同一数学定义**（§C），前提 4 条。

### G.2 不一致 / 必须显式标注的项

| # | 差异 | 影响面 |
|---|---|---|
| 1 | 式(1)/(8) 的 t_f 按弧计（n+1） vs 实现按目标（n） | 任何"按原文式重算成本/时段"的审计会系统性偏大；必须用实现语义 |
| 2 | Java 的 SABS 第 0 槽可写满，自检仍通过 | 原始 Java 输出不可直接当可行锚点；必须过 E2 审计（J0 已知有 invalid） |
| 3 | Java 自检不含覆盖/唯一性/指派一致性 | "Java 可行" ≠ "原文可行" |
| 4 | ALNS 名义 5000 实际 270（温度下限） | 引用"5000 次 ALNS"必须改口径；这也是 P1/P2 每次外层候选的实际搜索量远小于名义值的直接原因 |
| 5 | K'_max 100 vs 500；w_ub 5.0 vs 0.5 | 版本身份必须写 P1 还是 P2；不能统称"复现了论文 TSALNS" |
| 6 | similarityRemove 删 1 个 vs 论文删 2 个；代价类判定退化 | 不能声称"复现了 similarity 算子的覆盖冗余语义" |
| 7 | maxRegret 实际退化为 cheapest（calculateRegret + 取最小） | 两个 repair 算子近似同质；算子消融的解释要改 |
| 8 | 死代码 checkEnergyConstraints（跨趟能量） | 若被误用会错误禁止多趟 |
| 9 | 原文 §3.1 与 §5.1 的 J/I 记法冲突 | 读表/写协议必须用"文件名第一位=站数" |

### G.3 对 S / W 合同的具体影响（有界、可执行）

1. **S 合同（逐图 cap）**：C(R_Liu) 必须由"实现语义"重算（fixed + c_t × Σ duty），不能用式(1) 字面弧和；M_return 用 Check.calculateLatestTime 定义（= E2:210），不要用 calculateSolutionTime（求和）或 M_service。
2. **W 合同（天气/应急）**：Liu 的 duty 在 120 图上不紧（S:447–448），所以"累计 duty 在风下变紧"是**新增效应**，必须自己证明紧约束出现（不能让读者以为 Liu 已处理）；同时 wind/NFZ 的合法性引用 P:226–227 + P:923–925 即可，不要夸大。
3. **基线资格**：J1b/J2b 才是可比的 Java 档；J0（原始）只能作"作者代码行为诊断"，因为 SABS 槽 0 与 270 次截断会让它系统性偏离论文语义。
4. **不得声称**：P1/P2 的 ±0.03%/±0.10% 是"改进"；similarity/maxRegret 的论文语义已被复现；M_return 是新指标；风/NFZ 是本文首次提出。

### G.4 未解决缺口（留给后续线程，附具体入口）

1. **逐字核验未读段**：RoutingOperator swap1/swap2/twoOpt 主体（J:7–145、365–424）与 swapPointsBetweenDrones（死代码）未逐字读；若将来要复用这些算子，需补读。
2. **PDF 视觉核对**：式(1) 的求和下标、式(12) 的 y 上标、式(23) 的分式排版只用文本抽取判断；若要在论文中引用式号，建议用 PDF 目视确认（P:251–254、P:292–294、P:557–558）。
3. **站 serviceTime 非零的扩展**：一旦 W 场景给站加服务/周转时间，J:173–174 与 J:45 的口径会分叉，必须在新的 evaluator 里显式定义（当前合同要求 station service=0，PP:70）。
4. **calculateLatestTime 在 SABS 槽 0 解上的行为**：本文只做静态推断（会多算一架 SD 的时间），未用真实 J0 输出验证；若要量化 J0 的 invalid 率，需读 `results/full_J0/` 的现成行（本次未读）。
5. **P1/P2 的逐图分布**：本文只引用了 `semfix_full_matrix_audit.json` 的汇总；逐图/逐 seed 明细在 `results/semfix_full_P1/*.json`（600 行）与 `P2`（600 行），未逐行核对。

---

### 附：一句话总结

Liu (2026) 的**模型**（站型/机型/覆盖/换电/多趟/累计 duty/成本）在"每目标一次服务时间"的实现语义下与作者 Java、已验收 evaluator 三方一致；**式(1)/(8) 的 t_f 按弧计费是原文笔误**；**TSALNS 的实现与论文有两处硬差异**（K'_max 100 vs 500、w_ub 5.0 vs 0.5）与一处软差异（ALNS 实际 270 次）；**原始 Java 的 SABS 双槽是模型偏差**，必须由 evaluator 拒绝；**M_return 就是 Check.calculateLatestTime**，不是新指标；风/禁飞/异质服务/灾后只被原文列为 future work（p.299），可作动机、不可作新颖性。

