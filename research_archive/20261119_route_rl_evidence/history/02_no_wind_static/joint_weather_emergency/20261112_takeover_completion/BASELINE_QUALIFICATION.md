# BASELINE_QUALIFICATION — G3 最强 non-RL 基线族：资格、分层与结果前冻结的择优规则

- **status**: FROZEN_SPECIFICATION_ONLY（规格冻结；不含新科学结果；不改变 G0=NO-GO 与 G3 未通过）
- **生成**: 2026-11-12T08:15:23Z（本地 CST 16:05–16:20；服务器快照 08:05–08:16 UTC）
- **范围**: 只做"谁有资格当对照、如何在结果前择优、如何计分"。不新建基线、不运行新方法、不改历史文件、不宣称任何 gate 通过。
- **一句话**: 本轮新证据把 G3 的最低门槛从"作者锚点 R_Liu"换成"**1 ms、零学习、零路线改变**的成本中性整趟重排"（11 图 M_return 平均 −12.92%，95% CI [−18.79, −6.70]，7/11 图 ≥5%）。因此本文件把该重排冻结为 practical floor，并规定：**任何 RL／新方法主张必须先赢它，再赢同域最强 A2 对照**，而不是打赢作者锚点。

---

## 0. 判定标记、证据边界与暴露声明

### 0.1 标记（全文统一）

| 标记 | 含义 |
|---|---|
| [已证实-代码] | 本地/服务器源码逐行可核，带文件:行 |
| [已证实-收据] | 有落盘 JSON/日志/哈希，带路径与分母 |
| [算术] | 由已证实数字直接推算，正文写明算式 |
| [未证实] | 假说、推测或未核到收据；不得当结论 |
| [规格] | 本文件新写的要求/伪码；**未执行**，不产生证据 |

### 0.2 本文件实际读了什么（未读的不冒充已读）

| 文件 | 用途 |
|---|---|
| 本包 BRIEF_AGENT_CONTEXT.md、TAKEOVER_AUDIT.md（§6/§7）、CODE_MAP.md（§A.1/A.2/A.5/C.1–C.4）、PRIOR_ART_EQUATION_AUDIT.md（§C）、PAPER_EQUATION_COMPARISON.md（§A.2/B.9/B.12–B.14）、SPLITS_AND_EXCLUSIONS.md（§7）、CLOSED_DIRECTIONS.md（标题层） | 合同、口径、先例差异 |
| project_status/20261112_g0_joint_event_screen/STRONG_NONRL_SPEC.md、20261112_zhao_han_fulltext_audit/NONRL_QUALIFICATION_ADDENDUM.md、20261112_cfa_repository_version_audit/NONRL_QUALIFICATION.md | G3 资格三份上位规格 |
| joint_weather_emergency/20261105_deep_revision/NEXT_FULL_BASELINE_SPEC.md、REPORT.md §8 | 完整强基线缺什么 |
| route_rl_research/20261103/return_makespan/{G23_ROOT_STATUS.md, EXECUTION_PLAN.md, ROUND_DECISION.md, scorer.py, delivery.py} | S 合同实现与口径 |
| g23/nonrl_baseline/baseline.py、g23/author_baseline/author_runner.py | 两个已有实现逐行 |
| 本包 results/g3_pop/{population_index,AUTHOR_RESULTS,NONRL_RESULTS,EXACT_REASSIGN_RESULTS}.json、author/*/RUN.json、stdout.log | 本轮 12 图收据 |
| 服务器：g3_pop/AUTHOR_INTENT.json、g3_confirm/PREREG_CONFIRM.json、prereg_20261112/{STATS_self.json, compute_stats_server.py, replay/}、harness/*.py、logs/confirm.log（尾部） | 意图、预注册、统计口径、在跑状态 |
| project_status/20261112_claude_handoff/CLAUDE_TAKEOVER_PROMPT.md §11（G3 基线族） | A1/A2/A3、N1–N5、Han、O 的原始登记名 |

### 0.3 暴露声明（必须与本文件一起引用）

我在只读检查确认集进程状态时读了 <EXECUTION_PATH> 的末尾约 20 行，看到 4x25_o2–o4、4x30_o2–o4、5x35_o2–o3、9x95_o2–o3 的 LPT/joint_minmax 行（status 与 delta_M_return_pct）。

- 本文件**没有**使用这些数值，也没有据此调整任何规则（本文件的规则由原理定：全分母、失败归零、逐图并列，见 §4.4）。
- 但按本项目披露惯例，这已使"confirm 尚未被任何人看过"这一条件不成立。建议：确认集统计在 04_exact 跑完后由一次性冻结脚本自动产出，并把这次暴露写入收据；若要求"零暴露"，需由另一位执行者重跑或由独立方核算。
- 该暴露**不影响** ordinal 1（12 图，dev）的任何数字；dev 数据本来就在 G3_DEV 分析中被看过。

---

## 1. 共享合同层（A、B 两节共用，避免逐条重复）

### 1.1 S 合同（静态、固定部署、逐图 cost cap、整图 6s/12s）

| 项 | 冻结定义 | 代码/收据 |
|---|---|---|
| 实例与身份 | 一张图 = 一个 canonical geometry；事件日/求解 seed 嵌套在图内，不作独立 n | SPLITS_AND_EXCLUSIONS.md §7.1–7.3 |
| 部署域 | station_types 与 target→station 归属**固定**，任何方法不得改 | scorer.py:269–272（domain_issues） |
| 合法动作（物理） | 只允许"站内 slot 分配 / 趟内顺序 / 趟的拆分合并"；等价于 (slot,target) 与 (slot,RETURN) 的路线语义；**禁止** WAIT、改降、跨站改派 | CODE_MAP.md §B.1/B.3；global_env.py:78–98 |
| 成本 cap | 逐图 C(candidate) ≤ C(R_Liu) + 1e-7，epsilon=0；**整图** cap，不是逐站；不允许跨图相抵 | scorer.py:273–277, 47–50；CODE_MAP.md §A.2 |
| 目标 | 最小化 M_return = max over (station,slot) of duty；与 Java Check.calculateLatestTime 同定义 | scorer.py:210；PAPER_EQUATION_COMPARISON.md §C.4 |
| 完整解 | 所有目标恰好服务一次、所有机返航、全部 slot 满足能量与累计 duty；否则 admissible=False | scorer.py:191–216, 288 |
| 墙钟 | 整图 6s（主）/12s（次）；覆盖"从共同 ready 输入开始的增量"，不含锚点生成 | delivery.py:62–64 |
| 交付 | 只交付截止前校验通过的完整 incumbent；晚到校验不得变成有效输出；允许回退到锚点并记录原因 | delivery.py:40–58, 79–85 |
| 失败 | raw_inadmissible / raw_validation_late / raw_worse_than_anchor 三类单列；失败与超时不得剔除分母 | delivery.py:40–45；TAKEOVER_AUDIT.md §7.9 |

### 1.2 W 合同（动态天气/应急，与 S 分列）

| 项 | 冻结定义 | 位置 |
|---|---|---|
| 信息 | 只用公共 H_t（已发布预报/版本/valid time、告警台账、已承诺动作）；禁真未来 trace | STRONG_NONRL_SPEC.md；NONRL_QUALIFICATION_ADDENDUM.md §五项检查 |
| 动作 | 仍为物理 (slot,target)/(slot,RETURN)；RETURN 回所属站换电但**不清零**累计 duty | BRIEF §合同 1 |
| 指标 | 高优先准时率、迟到 CVaR90、冻结成本约束（成本比 bootstrap 95% 上界 ≤1.01） | BRIEF §合同 3；WX_PILOT_RECEIPTS.md §8.3 |
| 预算 | 单决策 50/500ms 与"与 RL 端到端相近"两视图；**不得**把单决策 6s 累加成整图与 6s 比 | STRONG_NONRL_SPEC.md；NONRL_QUALIFICATION_ADDENDUM.md §五项检查-5 |
| 联合 J | J = incurred + 0.5*makespan + miss + 1000*routine_missing + 10000*bad，**不是** M_return | CODE_MAP.md §C.5（joint_core.py:117–128） |

### 1.3 三条不得互换

1. S 的 M_return 与 W 的 J／准时率／CVaR 不得互为替代；W 的成本比不得拿来证明 S 的 cap。
2. L1（离线/不限时）与 L0（6s/12s）不得混入同一张主比较表；L2（不同信息/动作域）只能作参考。
3. "意向行 ≥ 启动行 ≥ 按时交付行"三种行不得混用；本文件一律写"按时交付/启动/意向"。

---

## 2. A 节：S 合同基线族逐条资格

### 2.0 族成员总表（本文件冻结的分层与动作域标签）

动作域：A1 = 整趟重排（只改 slot 分配，成本中性）；A2 = A1 + 趟内顺序/目标 relocate/split/merge（站内）；A3 = 增改站型/部署（S 合同禁止）；A4 = 跨站改派（S 合同禁止）。

| id | 名称 | 层 | 动作域 | 预算 | 本轮新人口已跑 | 资格 |
|---|---|---|---|---|---|---|
| R_Liu | 忠实作者锚点（J1b/J2b） | L1（参考级） | A0（作者全算法） | 1800s/map 上限 | 是（12/12 调用，11 合格） | 合格：**cap 与参考级**，不是"最强 non-RL" |
| author_loadbalance | 作者 loadBalance 构造 | L0 | A2 构造（插入式） | 6s/12s | 否 | 待实现（Java 侧可调用） |
| cheap_balance | cheap 平衡 | L0 | A2 构造 | 6s/12s | 否 | 待实现（规格） |
| joint_minmax | 同目标站内联合 min-max 下降 | L0 | A2 | 6s/12s | 是（12 图 ×2 预算） | 合格但**失败率高**（6s 4/11 无输出） |
| threshold_feasibility | threshold 可行性构造 | L0 | A2 构造 | 6s/12s | 否 | 待实现；不得与已关闭的 threshold-conditioned policy 混名 |
| matheuristic_assign | 适用 matheuristic（指派/DP） | L0（若 ≤6s）/L1 | A1→A2 | 6s/12s 或离线 | 部分（A1 的精确解已算） | 部分合格 |
| route_only_alns | 强 route-only ALNS | L0 | A2 | 6s/12s | 否（旧 Stage A 有实现） | 待移植；历史上是最强 A2 |
| lpt_intact_trip | 多趟 repacking（整趟 LPT） | L0 | A1 | 6s（实测 1–8 ms） | 是（11 图） | 合格：**practical floor 的可部署版** |
| exact_cost_neutral_reassign | 成本中性整趟重排（精确最优） | L1 | A1 | 离线（无预算声明） | 是（11 图，重放字节一致） | 合格：**floor 证书**，不可当 6s 竞争者 |

### 2.1 忠实作者锚点 R_Liu（id: R_Liu）

| 项 | 内容 |
|---|---|
| 信息集 | 完整实例（坐标/服务时间/能耗/站型/参数）+ 官方 Java 源码与 Table A1 参数；无任何公共历史以外的信息（静态问题） |
| 动作域 | 作者完整 TSALNS：外层选址 500 + 路线局部搜索 + ALNS destroy/repair；对本项目而言是"给定部署下的完整路线解" |
| 墙钟 | 每图 1800s 上限（意图登记 budget_cpu_core_seconds_estimate=21600=12×1800）；实测 12 图合计 46.3s，最大 8.716s（10x110_o1） |
| 后处理 | 无。解直接进独立 evaluator（scorer.validate_candidate），成本与 M_return 双账 |
| 失败处理 | eligible 需同时满足：exit 0 且未超时；source integrity issues 为空；独立 evaluator 可行且其成本与 scorer 成本差 ≤1e-7；源报告成本与 scorer 成本差 ≤1e-7；源报告 latest_time 与 M_return 差 ≤1e-7。任一不满足即不 eligible，该图**不补、不换 seed、保留在册**（author_runner.anchor_eligible/audit_raw） |
| 已实现 | 是：g23/author_baseline/author_runner.py（prepare/plan/run/derive-seed）+ 服务器 author_build/J1b（20 classes）+ runtime/jdk17 |
| 资格判定 | **合格**，但角色是"cap 来源 + 参考级"，**不是** G3 的最强 non-RL |

必须写死的三条口径：

1. **J1b vs J2b**（author_runner.py:25–30 [已证实-代码]）：J1b = 发布版 Java 参数（local_iterations=100、weight_upper=5.0）；J2b = 论文 Table A1 参数（local_iterations=500、weight_upper=0.5）。两者 outer=500、alns_iterations=5000 名义相同。本轮新人口全部用 **J1b**（每图 RUN.json.source_identity.profile 为 "J1b"）。任何"作者原法"表述必须写明用的是哪一档；J1b 不等于 J2b，不得混用同一张表。
2. **ALNS 名义 5000、实际 270 次**（PAPER_EQUATION_COMPARISON.md §B.12/B.13 [已证实-代码+算术]）：Java 停止条件是 temperature > 1e-3，T0=1000、alpha=0.95，解 1000·0.95^k ≤ 1e-3 得 k=270（末温 9.6688e-4）。引用"5000 次 ALNS"必须同时写"实际 270 次 destroy-repair/外层候选"。
3. **不得用式(1)字面弧和重算成本**（PAPER_EQUATION_COMPARISON.md §A.2-2 [已证实-代码]）：式(1)/(8) 把 t_f 记在每条弧（每趟 n+1 次），实现按每目标一次（n 次）。本项目成本只能取 scorer.py 与 lrphsd/evaluator.py 这一对；用式(1)字面重算会系统性高出 10%–30% 量级。

本轮实测（分母=12 图，namespace takeover-20261112-g3-v1，partition opportunity，ordinal 1）：

| 图 | 作者 wall_s | eligible | 说明 |
|---|---:|---|---|
| 3x10_o1 | 1.401 | 是 | cost/M_return 双账一致 |
| 3x15_o1 | 1.627 | 是 | |
| 3x20_o1 | 1.979 | 是 | |
| 4x20_o1 | 1.884 | **否** | source_latest_time_mismatch：Java 86.56491551657447 vs scorer 79.47485804779748（Δ=7.090057468777）；成本差 2.84e-14（一致）、独立可行（无 issues） |
| 4x25_o1 | 2.950 | 是 | |
| 4x30_o1 | 3.101 | 是 | |
| 5x35_o1 | 3.076 | 是 | |
| 6x50_o1 | 4.074 | 是 | |
| 7x65_o1 | 4.502 | 是 | |
| 8x80_o1 | 5.663 | 是 | |
| 9x95_o1 | 7.321 | 是 | |
| 10x110_o1 | 8.716 | 是 | |

- 合格率 11/12。**4x20_o1 判不 eligible 是正确的**：作者自报的 latest time **高于**独立 M_return，若拿它当锚点会**放宽**对照（把 anchor 变差），因此不能用；但方向是保守的，所以不是"作者解不可行"。差异来源未证实（见 §9.2 H-2），**不许**用重跑或换 seed 去"修好"它。
- 锚点 seed 规则 [已证实-收据]：seed = SHA256("takeover-20261112-g3-author-seed-v1" + ":" + map_sha256)[:8] big-endian & (2^63−1)（harness/02_run_author.py:18,85）。我对 12 个 RUN.json 逐一复算，**12/12 一致**；seed 只由 namespace 与图哈希决定，未按结果挑。

### 2.2 作者 loadBalance（id: author_loadbalance）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S：实例 + 固定部署；逐目标插入时读站型、覆盖半径、逐机电池与 maxAllowedTime、当前逐机时长与原成本 |
| 动作域 | **构造**：一次一个目标，选 loadBalance 得分最高的插入位置（站内既有趟插入点，或新建一条 [站,目标,站] 趟）；不删点、不换站 |
| 墙钟 | 单次构造，n 个目标 × 可行位置扫描；本项目规模下远小于 6s（未实测） |
| 后处理 | 无（构造完即解）；若要接 A1 重排，必须作为共享后处理计时钟 |
| 失败处理 | 构造不出完整解 → 该图记失败，不补图；不得静默回退到锚点后当成"作者 loadBalance 结果" |
| 已实现 | **否**（规格+可调用点）。Java 侧存在 RoutingOperator.loadBalancingInsertion（official_source/RoutingOperator.java:1119 起），内部用 calculateLoadBalanceScore（:1179 调用点、:1640 定义）；但 test1.Main 只跑完整 TSALNS，没有"只跑构造"的入口 → 需在隔离 build 里加一个 driver 类（不改 accepted source），或由 Python 端口复刻 |
| 资格判定 | **合格对照（待实现）**；不得称"作者算法"，只能称"作者 loadBalance 插入构造" |

公式（PAPER_EQUATION_COMPARISON.md §B.9 [已证实-代码]）：score = 0.6·(T_max − T_after)/T_max + 0.4·1/(1 + |C_after − C_before|)，rho 硬编码 0.6（Java:1652）；与原文式(23) 一致。

**必须写明的实现陷阱**（[已证实-代码]，fidelity_ops_v5.py:446–448 注释 + Java repair 分支）：Java 的 repair 算子名叫 loadBalancing，但对"已有趟插入"实际优先"第一个空存储机"，**不是**按式(23) 选最空站、也不是按 loadBalance 分数。所以：
- 若目标是"作者 loadBalance 构造"，必须直接调用 loadBalancingInsertion（它用式(23)），不能拿 ALNS 的 loadBalancing repair 冒充；
- 若目标是"作者完整 ALNS 内的 loadBalancing 算子"，那是另一个身份，且其行为要按代码口径描述（"优先空机"），不得按论文文字描述。

### 2.3 cheap 平衡（id: cheap_balance）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S（实例 + 固定部署 + 当前逐 slot 负载） |
| 动作域 | 构造：按固定顺序（如目标 id 升序或最远优先）逐点插入，选择"当前 duty 最小的可行 slot/位置"，tie-break 固定（slot 升序、位置升序） |
| 墙钟 | 单遍构造，远小于 6s |
| 后处理 | 无；若接 A1 重排须共享计时钟 |
| 失败处理 | 无可行插入 → 记失败该图；不得回退后仍标该法 |
| 已实现 | **否**（纯规格）。注意：joint_minmax 的 LPT 起点（baseline.py:38–70）在**动作域上**就是一种 cheap 平衡，但它作用在**锚点的整趟**上（A1），不是逐目标构造，**不能**当 cheap_balance 用 |
| 资格判定 | 合格对照（待实现）；作用是"证明强对照不是靠弱构造"，不能当最强 |

### 2.4 同目标 joint minmax（id: joint_minmax）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S + 共同锚点 R_Liu（整趟集合、站型、target_station） |
| 动作域 | A2：趟内 2-opt 反转、目标 relocate（跨趟/跨 slot）、单目标 split_relocate、跨趟 swap、两趟 merge（两个方向）；全部限定在**同一站内** |
| 墙钟 | 整图 6s/12s；实测 6s 下 0.06–6.00s，12s 下 0.06–12.01s；超时即 NO_ONTIME_VALID_OUTPUT |
| 后处理 | delivery.finalize_result：raw 不优/不可行/晚到时回退锚点；raw 与 fallback 双记录 |
| 失败处理 | 6s：4/11 图无有效输出（7x65、8x80、9x95、10x110）；12s：3/11（8x80、9x95、10x110） |
| 已实现 | **是**：g23/nonrl_baseline/baseline.py（solve(method="joint_minmax")，"deterministic_station_joint_route_vnd_v1"）+ harness/03_run_nonrl.py |
| 资格判定 | 合格但**当前不足以充当"最强 A2"**：失败率使其在任何"零失败"主张里直接出局（§4.4） |

本轮实测（分母=11 张 anchor 合格图；逐图值见 §6.1）：6s 交付 7/11，均值 vs 锚点 −15.4876%（n=7，条件化，不可当主结论），vs floor −0.6012%（W/T/L 1/6/0）；12s 交付 8/11，vs floor −0.5990%（W/T/L 2/6/0）。两张图真正赢 floor：6x50_o1（134.628815 vs 140.543544，−4.2085% 相对 floor）与 7x65_o1@12s（228.245347 vs 229.585577，−0.5838%）。

### 2.5 threshold 可行性（id: threshold_feasibility）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S；规则只用公开量：逐 slot 剩余 duty、逐趟能量余量、覆盖半径、目标服务时间 |
| 动作域 | 构造/修复：仅当"新负载 ≤ 阈值·上限"才允许插入；阈值是**冻结常数或冻结网格**（如 0.9/0.95/1.0），不得按图调 |
| 墙钟 | 单遍/少遍，远小于 6s |
| 后处理 | 无；若接后处理须共享 |
| 失败处理 | 阈值过紧 → 构造失败该图；阈值网格须**在新 calibration 上预登记**，不得在 test 图选阈值 |
| 已实现 | **否**（规格） |
| 资格判定 | 合格对照（待实现）。**必须与已关闭身份区分**：ROUND_DECISION.md:38 与 TAKEOVER_AUDIT.md §6.3 关闭的是"threshold-conditioned **policy**（把阈值条件化当机制）"，G0_NO_GO；本项的"threshold 可行性"是**非学习构造对照**，只作对照，任何"阈值随状态学出来"的写法都算复活已关闭身份 |

### 2.6 适用 matheuristic（id: matheuristic_assign）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S + 锚点整趟集合（A1 版）；A2 版还需允许趟内重排的目标集合 |
| 动作域 | 最小版：整趟→slot 的 0/1 指派（等价于 §2.9 的精确解，可用穷举/DP/MILP）；扩展版：指派 + 趟内顺序（TSP-path，站内 ≤10 点可精确 DP）；完整路线 MILP 属 L1 |
| 墙钟 | A1 版实测毫秒级；A2 版若用 MILP 需在 6s 内或降级为 L1 |
| 后处理 | 无（解本身即最优/近似最优）；与 A1 精确解并存时取 M_return 更小者 |
| 失败处理 | MILP 无解/超时 → 记失败并保留求解器日志；不得把"未到最优"报成"最优" |
| 已实现 | **部分**：A1 的精确最优已实现并跑过（harness/04_exact_reassign.py，穷举 2^m，站点独立）；A2 的指派+顺序 matheuristic **未实现** |
| 资格判定 | 合格（A1 部分已构成 floor 证书）；A2 版待实现 |

### 2.7 强 route-only ALNS（id: route_only_alns）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S（完整实例 + 固定部署）；不使用任何未来/私有信息 |
| 动作域 | A2：站内 target 级 destroy/repair + 2-opt + 插入，**只改路线不改部署** |
| 墙钟 | 整图 6s/12s，与 RL 同预算（旧 Stage A 记录：6s/12s 双预算、3 solver seed） |
| 后处理 | 无；若要接 A1 重排必须共享并计时钟 |
| 失败处理 | 超时/无解 → 记失败；Stage A 记录显示 720 任务全部可行，但那是旧人口 |
| 已实现 | **是（旧人口/旧分支）**，**未在新人口**：<EXECUTION_PATH> 的 route_alns_solution(instance, initial_solution, budget_seconds, seed=0)；本包 code 副本只含 delivery.py/global_env.py/scorer.py/g23，**没有** lrphsd 或 route_rl |
| 资格判定 | **必须补跑**：它是历史上唯一真正赢过 RL 的 A2 强对照（Stage A：Route-RL 相对 route-only ALNS 的收益 −0.966725%（6s）/−0.955678%（12s），W/T/L 0/21/3，720 任务；见 TAKEOVER_AUDIT.md §6.1-4）。在它跑上新人口之前，不能说"最强 non-RL 已建立" |

### 2.8 多趟 repacking（id: lpt_intact_trip）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S + 锚点的整趟集合（**只读趟内容，不改趟内顺序**） |
| 动作域 | A1：把整趟按 LPT（时长降序）分配到本站合法 slot；每趟能量必须 ≤ 该 slot 电池，slot 累计 duty 必须 ≤ 上限；越界则整站回退原分配 |
| 墙钟 | 实测 0.001–0.008s（NONRL_RESULTS.wall_s）；output_ready 约 1.26ms（3x10_o1 记录 0.0012596s） |
| 后处理 | delivery：raw 若比锚点差则回退锚点（本轮 7x65_o1 就触发 raw_worse_than_anchor，交付=锚点） |
| 失败处理 | 单站装不下 → 该站用原分配；全图仍交付完整解 |
| 已实现 | **是**：baseline.py:38–70（_lpt_repack）+ 03_run_nonrl.py（method="lpt"，只跑首个预算 6s，因为它是确定性的且远快于预算） |
| 资格判定 | **合格且是 floor 的可部署版**；但它是 A1，不是"最强 A2" |

**口径缺陷（[未证实-影响]，必须实测后才可引用）**：baseline.py:52–58 对 kind==2 站的 slot 1 用了 small_duration 作 duty 上限；而 scorer.py:184 与作者 evaluator.py:42 用的是 "kind==1 ? small_duration : large_duration"（即 kind==2 两个 slot 都用 large_duration）。也就是说 **LPT 比官方口径更保守**，可能因此把本可放进 slot 1 的趟挤到 slot 0。这**可能**是 6x50_o1 上 1.36% 差距的原因之一，但未验证（见 §9.2 H-1）。

### 2.9 成本中性整趟重排（精确最优，id: exact_cost_neutral_reassign）

| 项 | 内容 |
|---|---|
| 信息集 | 同 S + 锚点完整解（每趟的目标序列、站型、target_station） |
| 动作域 | A1 的**精确最优**：每站独立地把"整趟集合"分到该站合法 slot，最小化 max(slot duty) |
| 墙钟 | **无预算声明**（离线证书，L1）：穷举 2^m，m=该站趟数；本轮 m ≤ 10（最大 9x95_o1 站 1 有 10 趟），2^10=1024，毫秒级；脚本不记 wall_s |
| 后处理 | 无（结果直接进 scorer.validate_candidate，epsilon=0） |
| 失败处理 | 任一站无可行指派 → SystemExit 并保留（本轮 11/11 成功；4x20_o1 因锚点不合格跳过） |
| 已实现 | **是**：harness/04_exact_reassign.py；服务器重放 <EXECUTION_PATH> 与 g3_pop 版本 **字节一致**（sha256 7737e1861167274193a566cb92cc382a5ef907a3fd27ae2c7e5f6c66523443f6） |
| 资格判定 | **合格：practical floor 的证书级定义**；因无 6s 预算，**不得**计入 L0 主比较表 |

为什么它是"精确"（[已证实-代码+算术]）：

1. 逐站独立：M_return = max over 站 of (站内 max over slot duty)，站与站之间无耦合（固定 target_station、无跨站调机），所以逐站最小化 station makespan 等于全局最小。
2. 逐站精确：可行指派集合就是 2^m 个（每趟选一个合法 slot），脚本穷举全部分配并取 max(loads) 最小，因此是该类**可证明的最优**，不是启发式。
3. 成本不变（**要点，但不是"逐位"**）：改动只换 slot，不换趟内容，duration 只依赖 (站, 趟内序列)，所以 Σduration 不变，cost = fixed + 0.5·Σduration 不变。实测 cost_delta_vs_anchor：9 图为 0，4x30_o1 为 −5.68e-14，10x110_o1 为 −2.27e-13（float64 求和顺序差），|Δ| ≤ 2.27e-13，比 cap 容差 1e-7 小 6 个数量级。**因此正确表述是"数学上恒等、数值上 ≤ 2.3e-13"，不是"逐位不变"。**
4. 可行性保持：能量按趟不变且原锚点已可行；duty 上限在脚本内逐 slot 检查（limit = small_duration if kind==1 else large_duration，04:53），与 scorer.py:184 同口径。

本轮结论：11 图平均 M_return **−12.9189%**，中位 **−17.0592%**，W/T/L **7/4/0**，95% CI（map bootstrap，B=10000，seed 20261112）**[−18.7882, −6.6955]**；7 图降幅 ≥5%（25.83/22.78/22.74/20.48/19.89/17.06/13.34），4 图恰好 0（3x20、4x25、7x65、9x95——这些图的锚点在该类内已是最优）。

---

## 3. B 节：W 合同基线族逐条资格

分层规则：**学习式 non-RL** = 有权重/回归/示范学习但**没有 RL 更新**（须单列离线训练数据与资源）；**非学习** = 纯规则/搜索。二者都属 non-RL，但不得混为一行。

| id | 名称 | 类别 | 信息 | 动作域 | 预算 | 状态 | 缺什么 / 风险 |
|---|---|---|---|---|---|---|---|
| A1 | 忠实 TSALNS 静态计划 + 标注清楚的在线派单/绕行适配 | 非学习 | 静态计划用完整实例；在线只用公共 H_t | TARGET/RETURN（+明确标注的适配） | 整日 + 在线预算分列 | **未实现** | 需说明哪些算子忠实复用、哪些因事件状态重写；不得叫"完整原法" |
| A2 | 作者相关插入式动态适配 | 非学习 | 同 A1 | 同 A1 | 同上 | **未实现** | 必须写"与原作者算法的距离"；不得冒充完整原法 |
| A3 | 完整车队事件 + 周期重优化（原方案 1s/3s 档单列） | 非学习 | 公共 H_t + 冻结在飞承诺 | A2 | 1s/3s 周期 + 整日 | **部分**：有因果 rolling beam 与 complete-incumbent rollout，**无** 1s/3s 周期重优化 | 现有实现：emergency_rolling_baseline.py（PlannerConfig beam_width=32/max_nodes=2048/max_depth=32/wall_seconds=0.25）、complete_fleet.py（CompleteFleetRollout）、fleet_history_controls.py；均为旧联合 J 域、旧人口 |
| N1 | 固定 reserve / static(T) 规则 | 非学习 | 公共 | TARGET/RETURN | 整日 | **未实现** | 需在**新 calibration** 上预登记网格 |
| N2 | 走廊可飞阈值 | 非学习 | 公共风/NFZ 预报 | TARGET/RETURN | 整日 | **未实现** | 阈值不得按 test 图调 |
| N3 | 风暴感知资源保留/预置 | 非学习 | 公共预报 + 资源 | TARGET/RETURN | 整日 | **未实现** | 与已 HOLD 的 reserve v5 **机制**身份不同：N3 是**对照**，不得注册为新 G0 机制（reserve v5 = HOLD_G0_NO_GO，TAKEOVER_AUDIT.md §6.3-11） |
| N2+N3 | 组合规则 | 非学习 | 同上 | 同上 | 整日 | **未实现** | 组合须事前登记，不得结果后拼接 |
| N5 | 按公开天气类别自适应的规则 | 非学习 | 公共天气类别 | 同上 | 整日 | **未实现** | "自适应"须是冻结查表，不得在线拟合 |
| N4 | 真实共同生成模型 + 公共后验 + 候选后全部事件 causal rollout | 非学习（rollout 控制） | 公共 H_t + 冻结 mu + 共同抽样器 | TARGET/RETURN | RL p99 档 + M=32/更充足参考（分列） | **未实现**（只有 8/128 次分数扰动，明确不算该控制） | 缺公共分叉/发布历史/hidden phase（CAUSAL_ROLLOUT_APPENDIX）；伪码在 STRONG_NONRL_SPEC.md |
| Han_capacity | Han 共享容量准备度 sum_z r[z,b] ≤ N[b]^next | 非学习 | 公共预测 lambda_z + 真实可用时刻/duty | TARGET/RETURN（禁改降） | 整日 | **未实现** | 只能叫 Han-inspired adaptation；必须用 (2r) 总量约束，禁止区域各自用满全队；适配伪码在 NONRL_QUALIFICATION_ADDENDUM.md |
| vfa_linear | 线性后决策 VFA | **学习式 non-RL** | 公共 afterstate 特征 | TARGET/RETURN | 推理同预算 | **有实现但旧域**：20261106_method_family_B/ORIGINALS/method_lab.py 的 LinearAfterstateVFA（method="linear_vfa"） | 绑定旧联合 J 人口；离线回归数据/资源须单列；不得当"纯非学习规则" |
| supervised_value | 监督值拟合 | **学习式 non-RL** | 公共 | TARGET/RETURN | 推理同预算 | **未实现**（W 域） | 需与 VFA 分列，标签来源与算力单列 |
| bc_initial | BC 初始策略 | **学习式 non-RL** | 示范数据 | TARGET/RETURN | 推理同预算 | **有历史实现**（carl/bc.py；旧联合 J 人口，含失败 seed 保留） | 必须在任何 RL 更新前独立保存与单独评价；不得把 initial 收益记成 RL 增量 |
| api_only | API-only（只模仿先验、无 RL 更新） | **学习式 non-RL** | 示范 | TARGET/RETURN | 同预算 | **未实现**（全仓 grep 无 api_only/action_prior 实现） | 需与 BC 区分，并单列训练成本 |
| nolearn_beam | 无学习 beam / 场景规划 | 非学习 | 公共 H_t | TARGET/RETURN | 0.05/0.5s 或 0.25s（已实现档） | **有实现（旧域）**：同上 A3 的三个文件；执行过 16 episode（prior/oldbeam/fleet50ms/fleet500ms，4 TRAIN 图×4 日） | 不是整日完整矩阵；结论只能是"该 16 episode 的诊断" |
| scenario_capacity | 样本需求替代 lambda_z 的场景容量控制 | 非学习 | 公共预测 + 样本 | TARGET/RETURN | 整日 | **未实现** | 必须叫"场景容量控制"，不能说成完整 Han 方法 |
| O_oracle | 完美信息/更大预算参考 | 非学习（参考级） | **非公共**（完美未来或更大预算） | 视参考定义 | 不限/大预算 | **未实现**（W 域）；CFA 的 ODS Oracle 属**另一问题/另一版本**，不能移植 | 必须标明"限时启发式 or 界"；不得当最优性证书；不得混入同信息主比较 |

W 侧三条判据（沿用上位规格，不放宽）：

1. 缺任一关键控制（真 rollout、共享容量、同信息、预算对等、失败完整记录）→ G3 未通过（STRONG_NONRL_SPEC.md §G3）。
2. 学习式 non-RL 可以参评"最强 non-RL"（NONRL_QUALIFICATION.md 第 4 条明确"无 RL 更新的学习式规划依然属于 non-RL"），但其离线训练数据/资源必须单列，且不得把收益记成 RL 增量。
3. W 的任何结果不得写进 S 的 cap 证据；S 的 M_return 也不得替代 W 的准时率/CVaR。

---

## 4. C 节：择优规则（结果前冻结、可机器执行）

### 4.1 分层键与三层

每个方法必须带三元组 (I, B, A)：I = 信息集；B = 预算视图；A = 动作域。**只有三元组相同的比较才进主表。**

| 层 | 定义 | 用途 | 本轮实例 |
|---|---|---|---|
| L0 | 同信息 + 最大合法动作域（S 的 A2）+ 整图 6s（主）/12s（次） | **唯一主比较层** | joint_minmax、route_only_alns、matheuristic_assign、loadbalance、cheap_balance、threshold |
| L0-A1 | 同信息 + A1（整趟重排）+ 6s | **门槛层（floor）**，不单独作主比较 | lpt_intact_trip（1 ms） |
| L1 | 同动作域但离线/不限时 | 证书与上界参考 | exact_cost_neutral_reassign、完整路线 MILP、不限时 ALNS |
| L2 | 不同信息（完美未来）或不同动作域（跨站/改降/WAIT） | 只作参考，**永不**进主比较 | O_oracle、CFA oracle、Han 原始大动作域成绩 |

### 4.2 "最强合格 non-RL"的两种合法选法（都必须事前声明）

**SELECT_FROZEN**（单方法冻结）：
1. 在**选择集**（calibration/selection，非 test）上，对每个候选算逐图相对改善；
2. 排序键 =（选择集平均相对改善 升序，最差图改善 升序，平均 wall 升序，method_id 字典序）；
3. 取第 1 名，**冻结为唯一对照**，test 上原样跑，不得替换。

**PORTFOLIO_6S**（组合冻结）：
1. 事前登记成员表与运行顺序、每个成员的时限配额（默认等分 6s/k，或按冻结顺序吃剩余时间）；
2. test 每图在**一个 6s 时钟**内顺序跑全部成员，每次交付前校验；
3. 交付截止前**最后一个通过校验的完整 incumbent**（可按 M_return 取最好，但必须已校验且 ≤ 截止）；
4. 所有成员耗时、失败、校验全部计入 6s 与收据。
→ 组合法**不产生** test-time 选择偏差，因为它是一个**事前定义、成本自负**的方法。

### 4.3 禁止的选法（机器可检查）

1. **SELECT_PER_MAP_POST_HOC**：在 test 图上按方法取值 argmin 后当作"对手水平"。判据：交付表里出现"对手列的取值不是单一 method_id 的逐图取值"。
2. **条件化分母**：只在交付成功的图上比较（见 §4.7 的现行实例）。
3. **换对手**：同一主张前后用不同对照（如先比锚点、被反驳后改比"最弱 A2"）。
4. **弱化对手**：给对手更短预算、更小动作域、更少 seed、或在对手实现里留已知缺陷而不修（如 §2.8 的 duty 口径）。
5. **只报顺眼图**：不列全部图、不列 W/T/L、不列失败图。

### 4.4 计分：cap、失败、分母

| 情形 | 计分 | 依据 |
|---|---|---|
| 按时交付且 admissible | 用其 M_return | delivery.py:83–85；scorer.py:288 |
| 超 cap（> C_Liu + 1e-7） | **该图判失败**，不得进入任何均值 | scorer.py:47–50, 277 |
| 不可行（缺目标/重访/能量/duty/覆盖） | 该图判失败 | scorer.py:216 |
| NO_ONTIME_VALID_OUTPUT | 记失败；统计时按 **anchor 归零补值**（impute = anchor M_return，标签 fallback_anchor_imputed），并单列失败数 | 本文件 [规格]；依据 delivery.py:47–58 的语义（回退即锚点） |
| 未跑/无 intent | 不得算"完成"；单列 PLANNED_NO_INTENT | BRIEF §15；TAKEOVER_AUDIT.md §7.3 |

**优越性主张的硬条件**：failures == 0 且 cap_violations == 0。理由：floor（1 ms）在 11/11 图上零失败；一个在 4/11 图上无输出的方法不构成"赢过 floor"的证据，无论均值多好。

### 4.5 主比较层

- **主**：L0-A2-6s（同信息、最大合法动作域、整图 6s），逐图配对。
- **次**：同层 12s；L0-A1-6s（floor）。
- **参考**：L1（exact、MILP、不限时）、L2（oracle）。
- 任何"RL 胜最强 non-RL"的主张，必须在**主层**同时赢 **(i) floor** 与 **(ii) 事前冻结的 A2 强对照**；只赢锚点或只赢 floor 都不成立。

### 4.6 统计

| 项 | 冻结值 | 依据 |
|---|---|---|
| 独立单位 | **地图**；日/seed 嵌套，不展开 | SPLITS_AND_EXCLUSIONS.md §7.2 R7 |
| 配对 | 同图同锚点配对差 | 现行脚本 prereg_20261112/compute_stats_server.py |
| 主统计量 | 逐图相对变化 pct = 100·(M_cand − M_ref)/M_ref 的均值 + 中位 | 同上 |
| CI | percentile bootstrap，B=10000，seed=20261112，按图重抽 | STATS_self.json.bootstrap |
| W/T/L | 容差 1e-9（d < −TOL 记 win，> TOL 记 loss） | compute_stats_server.py TOL |
| 二级检验 | 配对 Wilcoxon / sign test；族内 Holm，族**事前**声明 | STRONG_NONRL_SPEC.md；TAKEOVER_AUDIT.md §7 |
| 方向 | 必须写方向词：M_return 负=更好；改善正=更好 | TAKEOVER_AUDIT.md §7.7 |

### 4.7 现行统计脚本的具体偏差（必须先修）

服务器文件 <EXECUTION_PATH> eef73b6262fef648e15b74161c4c2a463b11c6b695bf565818f6340b9c927738）：

- 第 81–82 行：if r.get("status") != "ONTIME_VALID": continue；第 40 行再取交集 → 非交付图**静默移出**。
- 后果（STATS_self.json 实值）：joint_minmax_6s 的 n=**7**、joint_minmax_12s 的 n=**8**，而 anchor 合格图是 **11**。于是"vs exact"的 −0.60% 是**条件在交付成功**上的估计，不能当"该法在 11 图上赢 floor"。
- 修正（[规格]，尚未执行）：分母固定为"全部 anchor 合格图"；失败按 anchor 归零补值；同时输出（a）全分母补值结果、（b）失败计数、（c）成功子集结果（标 conditional）、（d）逐图并列。
- 由于 confirm（36 图）尚未分析，此刻修脚本属于**事前**规范，不是结果后改口径；但因 §0.3 的暴露，建议由独立执行者落地。

### 4.8 机器可执行规格（伪码）

    INPUT  maps M (all anchor-eligible), methods registry, layer L, budget b
    FOR each map m in M:
        ref_anchor[m]   = anchor_M_return(m)             # from EXACT_REASSIGN_RESULTS
        floor[m]        = exact_cost_neutral_M_return(m)  # certificate
        FOR each method k in L:
            row = run(k, m, budget=b)                     # delivery.finalize_result
            value[k][m] = row.chosen_M_return if row.ontime_valid and row.admissible
                          else impute(ref_anchor[m])      # failure => no improvement credited
            fail[k][m]  = not (row.ontime_valid and row.admissible)
    # gates
    gate_delivery[k] = (sum(fail[k]) == 0)
    gate_cap[k]      = (count(cap_violation) == 0)
    # floor gate: paired, all maps, no conditioning
    d_floor[k] = [ pct(value[k][m] - floor[m], floor[m]) for m in M ]
    gate_floor[k] = mean(d_floor[k]) < 0 and ci_upper(d_floor[k]) < 0
    # strongest gate: same but against the frozen A2 comparator
    gate_strong[k] = mean(d_strong[k]) < 0 and ci_upper(d_strong[k]) < 0
    CLAIM_OK[k] = gate_delivery[k] and gate_cap[k] and gate_floor[k] and gate_strong[k]

对应的冻结 JSON 在 BASELINE_REGISTRY.json（同目录）；字段名与本节一致。

---

## 5. D 节：对称性清单

| # | 项 | 要求 | 检查方式 | 现状 |
|---|---|---|---|---|
| 1 | 合法动作 / mask | 所有方法同一最大合法域（S 的 A2）；不得给对照更窄的域，也不得给 RL 更宽 | 逐方法声明 (I,B,A)；mask 必须来自同一 global_env/scorer 语义 | 部分：A1 法（LPT/exact）属**故意更窄**的 floor 层，必须标层，不能冒充 A2 |
| 2 | 候选生成 | 同池；生成/枚举/校验成本计入时钟；不得把一方算好的候选免费送另一方 | 收据里记 candidate_validation_calls（joint_minmax 166–10201 次，随图规模） | 合格（同实现内） |
| 3 | 公共历史 / 信息 | S：实例+锚点；W：公共 H_t，禁真未来、禁私有事件队列 | 逐方法声明；W 侧须有"只用 observation+dispatch"字段（fleet_history_controls.py:19） | S 合格；W 待建 |
| 4 | 模型 | W：同一预测模型/抽样器/后验，向所有方法开放 | 模型 hash 与抽样器 hash 登记 | 未建 |
| 5 | 外生随机数 | S：无外生随机；W：同流同 seed（CRN），mode 分支不得改变后续流 | 抽样器 RNG 子流登记 | 未建 |
| 6 | 初始化 | 同一锚点/同一 initial 解；RL 的 BC initial 独立保存 | anchor_solution_sha256 逐图一致 | 合格（S：同一 anchor） |
| 7 | 合法后处理 | 同一后处理集合、同一开关、同一计时钟；含 §2.9 的 A1 重排；必须做"有/无后处理"两版 | 后处理前后 solution sha 与 M_return 双记 | **当前缺口**：exact/LPT 是 A1 方法，不是"共享后处理"；尚未以共享后处理形式提供给 A2 方法 |
| 8 | 完整成本 cap | 逐图 epsilon=0、绝对 1e-7、不得跨图相抵 | validate_candidate 每次单图；无跨图聚合接口（CODE_MAP.md §C.5 末段） | 合格 |
| 9 | 6s/12s 硬 deadline | 整图；含加载/编码/候选/校验/交付；超时不得改用晚到校验；不得把单决策预算累加当整图 | delivery.py:42–58, 79–82 | 实现合格；**口径缺口**：03/04 里实例读取、solution.json 反序列化、CostAnchor.from_solution 在计时外（共同成本，需显式记为 setup_excluded_shared） |
| 10 | incumbent delivery | 同一 finalize_result 语义；raw+fallback 双记录；失败原因三分类 | status/fallback_reason 字段 | 合格 |
| 11 | 失败记录 | 逐图逐行落盘；分母不缩；无 intent 单列 | 结果 JSON 每图一行 + intent 文件 | **缺口**：02 写 AUTHOR_INTENT.json，03/04 **不写** intent（服务器 g3_pop 只有 AUTHOR_INTENT.json） |
| 12 | 计费口径 | solver-s / CPU-s / 预约核时 / 墙钟四分，逐行标 | 报告字段 | 部分（本轮只有 wall_s 与 core-s 预约） |

---

## 6. E 节：凭本轮新证据重排资格

### 6.1 逐图事实（dev：namespace takeover-20261112-g3-v1，ordinal 1，11 张 anchor 合格图）

| 图 | anchor M_return | floor（exact） | LPT 6s | jm 6s | jm 12s | floor 降幅 |
|---|---:|---:|---:|---:|---:|---:|
| 3x10_o1 | 56.098082 | 44.611068 | 44.611068 | 44.611068 | 44.611068 | −20.4767% |
| 3x15_o1 | 106.981343 | 92.714578 | 92.714578 | 92.714578 | 92.714578 | −13.3358% |
| 3x20_o1 | 66.823954 | 66.823954 | 66.823954 | 66.823954 | 66.823954 | 0 |
| 4x20_o1 | — | — | — | — | — | anchor 不合格（不补） |
| 4x25_o1 | 120.941553 | 120.941553 | 120.941553 | 120.941553 | 120.941553 | 0 |
| 4x30_o1 | 130.685099 | 96.926409 | 96.926409 | 96.926409 | 96.926409 | −25.8321% |
| 5x35_o1 | 177.082681 | 136.814586 | 136.814586 | 136.814586 | 136.814586 | −22.7397% |
| 6x50_o1 | 182.001595 | 140.543544 | 142.459844 | 134.628815 | 134.628815 | −22.7789% |
| 7x65_o1 | 229.585577 | 229.585577 | 229.585577 | FAIL | 228.245347 | 0 |
| 8x80_o1 | 240.788110 | 199.711613 | 199.711613 | FAIL | FAIL | −17.0592% |
| 9x95_o1 | 247.677949 | 247.677949 | 247.677949 | FAIL | FAIL | 0 |
| 10x110_o1 | 318.736864 | 255.354056 | 255.354056 | FAIL | FAIL | −19.8856% |

（值来自 results/g3_pop/EXACT_REASSIGN_RESULTS.json 与 NONRL_RESULTS.json；FAIL = NO_ONTIME_VALID_OUTPUT。）

### 6.2 floor 的两个对象（必须分开写）

1. **exact_cost_neutral_reassign（证书级 floor）**：A1 类可证明最优；离线；无 6s 声明。11 图均值 −12.9189%，中位 −17.0592%，7/4/0，CI [−18.7882, −6.6955]。
2. **lpt_intact_trip（可部署 floor）**：1–8 ms，6s 内；11 图均值 −12.8232%，中位 −17.0592%，7/4/0，CI [−18.6560, −6.6624]；与 exact 的差 = W/T/L 0/10/1，均值 +0.1240%（CI [−2.1e-15, +0.3719]），唯一差距在 6x50_o1：142.45984397583175 vs 140.54354419176312（+1.9162998 min = +1.3635% 相对 exact / +1.0529 个百分点相对 anchor）。

结论：**"1 ms 零学习重排已在 10/11 图上达到 A1 精确最优"** 是本轮最强的负面事实；它使"5% 平均改善 + CI 下界大于 0"不再是 RL 的成就，而是 floor 的成就。

### 6.3 资格阶梯（重排后）

| 级 | 对象 | 含义 | 对主张的作用 |
|---|---|---|---|
| T0 | R_Liu | cap 来源 + 参考级 | 只用来定义 cap 与"相对作者"的参照；**赢它不算赢强对照** |
| T1 | floor（LPT 1 ms / exact 证书） | practical floor | **必须赢**（§6.4） |
| T2 | A2 强对照（route-only ALNS、joint_minmax、matheuristic、loadBalance、cheap、threshold） | 同信息同预算最强族 | **必须赢**（冻结后不可换） |
| T3 | L1/L2（离线、oracle、不同动作域） | 参考 | 只解释潜力，不进主张 |

### 6.4 must_beat（机器可执行）

    "must_beat": {
      "required": ["exact_cost_neutral_reassign", "strongest_eligible_A2_L0_6s"],
      "floor_operational": "lpt_intact_trip",
      "tolerance": {"rel": 1e-9, "abs": 1e-9},
      "per_map_rule": "candidate_M_return < reference_M_return - max(abs_tol, rel_tol*|reference_M_return|)",
      "aggregate_rule": "mean paired pct < 0 AND ci95_upper(mean paired pct) < 0",
      "failure_policy": {"impute": "anchor_M_return", "label": "fallback_anchor_imputed",
                         "require_zero_failures": true},
      "denominator": "all anchor-eligible registered maps; no post-hoc exclusion",
      "unit": "map"
    }

说明三点：

1. **对 floor 用 exact（更强），对可部署性用 LPT**：因为 exact ≤ LPT 逐图成立（本轮 11/11），赢 exact 自动赢 LPT；而 LPT 用来证明"floor 可在 6s 内被任何方法复现"，因此 floor 不是不可达的理想。
2. **per-map 严格**：不允许"6 图赢、5 图输、均值赢"。若某方法在某图输给 floor，说明它连"对锚点做一次整趟重排"都没做，属实现缺陷。
3. **零失败**：见 §4.4。joint_minmax 当前 6s 有 4/11 失败，因此**它现在连资格主张的门都进不去**（但仍是必须报告的对照，失败保留）。

### 6.5 由此作废的三种说法

| 说法 | 为何作废 | 替代 |
|---|---|---|
| "相对作者锚点平均改善 5%，CI 下界大于 0，所以方法有效" | floor 用 1 ms 就做到 −12.92%（CI 上界 −6.70%），锚点不是强对照 | 必须写"相对 floor"与"相对 A2 强对照"两列 |
| "RL 赢作者锚点，所以赢最强 non-RL" | 同上；锚点连 A1 重排都没做 | 用 T2 冻结对照 |
| "在交付成功的 7 图上均值 −0.6%，所以优于 floor" | 条件化分母（§4.7） | 全分母 + 失败归零 + 失败计数 |

---

## 7. F 节：当前可运行性

### 7.1 已有实现（可直接跑，带入口）

| 方法 | 入口 | 跑过新人口 | 备注 |
|---|---|---|---|
| R_Liu（J1b/J2b） | g23/author_baseline/author_runner.py（prepare/plan/run/derive-seed）；harness/02_run_author.py | 是（12/12，11 合格） | 服务器 build: author_build/J1b，JDK: runtime/jdk17 |
| joint_minmax | g23/nonrl_baseline/baseline.py:solve(method="joint_minmax")；harness/03_run_nonrl.py | 是（6s/12s） | 失败率高 |
| lpt_intact_trip | 同上 method="lpt" | 是（6s） | 1–8 ms |
| exact_cost_neutral_reassign | harness/04_exact_reassign.py | 是（11 图；重放字节一致） | 无预算声明 |
| 生成器/人口 | harness/gen_maps.py + g23<EXECUTION_PATH> | 是（g3_pop 12 图、g3_confirm 36 图） | namespace/partition/ordinal 冻结 |
| 统计 | prereg_20261112/compute_stats_server.py | 是（dev 一次性） | 有 §4.7 偏差，须修 |

### 7.2 有实现但不在新人口/不在本包（需移植或重跑）

| 方法 | 路径 | 状态 |
|---|---|---|
| route_only_alns | <EXECUTION_PATH> route_alns_solution(instance, initial_solution, budget_seconds, seed) | Stage A 旧人口已跑（720 任务）；新人口**未跑**；本包 code 副本无 lrphsd/route_rl |
| 无学习 beam / complete-fleet rollout（W） | joint_weather_emergency/20261106_complete_fleet_worker/MODIFIED_FILE/{emergency_rolling_baseline.py, complete_fleet.py, fleet_history_controls.py} | 旧联合 J 域已跑 16 episode；W 整日矩阵未建 |
| 线性 VFA（学习式 non-RL） | joint_weather_emergency/20261106_method_family_B/ORIGINALS/method_lab.py: LinearAfterstateVFA | 旧域；不适用 S |
| BC initial | reproduction/reviewer_package_semfix/carl/bc.py（旧联合 J 人口） | 旧域；须独立保存与评价 |

### 7.3 只有规格（无实现）

author_loadbalance（Java 可调用点存在，无 driver）、cheap_balance、threshold_feasibility、matheuristic_assign 的 A2 版、A1/A2/A3、N1/N2/N3/N2+N3/N5、N4 真实 causal rollout、Han_capacity、supervised_value、api_only、scenario_capacity、O_oracle。

### 7.4 意图与收据缺口（[已证实-收据]）

- 服务器 g3_pop 有 AUTHOR_INTENT.json（3038 B），但 **03/04 批次没有 intent 文件**（harness 代码里也没有写 intent 的逻辑）。
- AUTHOR_INTENT.json 的 author_source_hashes 字段为 **null**；作者源码绑定只存在于每图 RUN.json.source_identity。
- 本地包 results/g3_pop 副本**缺** AUTHOR_INTENT.json（只在服务器）；本地 10_gen_pop.sh 在服务器上不存在（文件集不一致）。
- 预注册 PREREG_CONFIRM.json 引用的 "G3_DEV_REPORT.md" 在服务器与本地均**不存在**（悬空引用）。

---

## 8. G 节：禁止清单（每条都可由收据机器检查）

1. **禁止按 test 每图选最优方法**：交付表中"对照"列的取值若来自多个 method_id 的逐图 argmin，即为违规。
2. **禁止只报顺眼对手**：必须列全部已登记对照的逐图值，含失败。
3. **禁止弱化对手**：不得缩短对手预算、缩小其动作域、减少其 seed、或保留已知实现缺陷（§2.8 的 duty 口径、joint_minmax 无 anytime 化）而不修。
4. **禁止用均值掩盖逐图超 cap**：任何均值必须与"逐图 admissible 计数"同表；cap 违规一律判该图失败。
5. **禁止条件化分母**：不得只在交付成功的图上算均值（§4.7 现行实例）。
6. **禁止把 L1/L2 混入主比较**：exact/oracle/不限时结果不得与 6s 方法同列为主结果。
7. **禁止把 A1 floor 冒充 A2 最强对照**：LPT/exact 只能出现在 floor 行。
8. **禁止复活已关闭身份**：threshold-conditioned policy、reserve v5、joint-event-screen 等（TAKEOVER_AUDIT.md §6.3）不得以"对照"名义改写成机制主张；N3 只作对照。
9. **禁止把作者锚点当"最强 non-RL"**。
10. **禁止在 confirm 上做事后择优**：36 图一次性进统计，不丢图、不换图、不按结果选子集。

---

## 9. 五段式结论

### 9.1 已证实事实（可复核）

1. 成本中性整趟重排（A1 精确）在 11 张 anchor 合格图上把 M_return 平均降 **12.9189%**，中位 **17.0592%**，**7/11 ≥5%**，W/T/L **7/4/0**，CI **[−18.7882, −6.6955]**（B=10000，seed 20261112，按图重抽样）。证据：results/g3_pop/EXACT_REASSIGN_RESULTS.json、prereg_20261112/STATS_self.json。
2. 该重排**数学上不改成本**（只换 slot），实测 |Δcost| ≤ 2.27e-13，远小于 cap 容差 1e-7；11/11 行 admissible。同一脚本重放字节一致（sha256 7737e186…）。
3. **1 ms 的 LPT 在 10/11 图达到该精确最优**；唯一差距 6x50_o1（+1.3635%，1.9163 min）。证据：NONRL_RESULTS.json、STATS_self.json.lpt_optimality_gap。
4. joint_minmax（A2）在 6x50_o1 把 M_return 再降到 **134.628815**（相对 floor −4.2085%），7x65_o1@12s 到 **228.245347**（−0.5838%）；但 6s 有 **4/11**、12s 有 **3/11** 图 NO_ONTIME_VALID_OUTPUT。
5. 作者锚点 12 图 11 合格；4x20_o1 因 Java latest_time 86.56491551657447 不等于 scorer 79.47485804779748 判不 eligible，成本与可行性均一致；判定方向保守（自报更差），拒绝是正确的。
6. 锚点 seed 规则可复算：12/12 与 RUN.json 一致（namespace takeover-20261112-g3-author-seed-v1）。
7. 已有一个 36 图确认集在 **2026-11-12T08:06:55Z** 预注册（PREREG_CONFIRM.json），primary estimand 正是 floor vs anchor；08:11Z 时 03 仍在跑、04 未跑。
8. 现行统计脚本把非按时交付行丢弃，导致 joint_minmax 的 n=7/8（应为 11）。

### 9.2 当前未证实假说（不得当结论）

- **H-1**：6x50_o1 上 LPT 的 1.36% 差距，部分来自 baseline.py:52–58 对 kind==2 slot 1 用了 small_duration（scorer.py:184/evaluator.py:42 用 large_duration）。**检验**：在 <COMPUTE_HOST> 用 scorer 口径重算该图 LPT，看是否降到 140.5435；若降到，则 LPT 与 exact 在 11/11 图重合，floor 的"精确 vs 可部署"差别消失。
- **H-2**：4x20_o1 的 latest-time 差异来源（Java 比 scorer 高 7.09）未定位。**不解释、不重跑、不换 seed**；只能做静态诊断（用 stdout 打印的 Final results 路线逐 subpath 复算，与 86.5649 对账）。
- **H-3**：joint_minmax 的超时可工程消除（增量评估、只对接受移动做全图校验、anytime 化），从而成为真正 6s 竞争者。**未验证**；在验证前它按 §4.4 记失败。
- **H-4**：route-only ALNS 在新人口上是否仍是最强 A2（旧人口 Stage A 证据：Route-RL 相对它 −0.967%/−0.956%）。**未验证**；必须补跑后才能写"最强 non-RL 已建立"。
- **H-5**：floor 的 dev 效应能否在 36 图 confirm 上复现（预注册 decision rule：同号且 CI 排除 0）。**未验证**，且我已在 §0.3 披露暴露。

### 9.3 失败或关闭

- G3 **未通过**：同信息完整强 non-RL 缺 route-only ALNS 的新人口结果、缺作者 loadBalance/cheap/threshold/matheuristic 实现、W 侧几乎全缺；比较仍不对称（§4.7）。
- joint_minmax 6s 在 7x65/8x80/9x95/10x110 **无按时有效输出**（保留在册）。
- LPT 在 7x65_o1 的 raw 解**比锚点差**（fallback raw_worse_than_anchor，交付=锚点）——说明 LPT 不单调，必须保留"取优回退"。
- 已关闭身份（threshold-conditioned policy、reserve v5、joint-event-screen 等）不得借本文件复活。

### 9.4 下一项有界工作（每项带产物与关闭条件）

1. **修统计脚本并跑 dev 全分母版**：改 compute_stats_server.py（失败归零 + 全分母 + conditional 单列）；产物 STATS_self_v2.json；关闭条件：11 图分母、joint_minmax n=11 且失败数 4/3 单列。
2. **修 LPT duty 口径并重跑 12 图**：把 baseline.py:52–58 改为按 kind 决定上限；产物 NONRL_RESULTS_v2.json；关闭条件：6x50_o1 LPT 值报出，若 =140.543544 则 H-1 成立。
3. **把 route-only ALNS 移植到新人口并跑 6s/12s**：产物 results/g3_pop/ROUTE_ALNS_RESULTS.json；关闭条件：11 图逐图 ONTIME/失败，含 cap 校验与 seed 规则。
4. **做共享后处理版（POSTPROC=exact_reassign on/off）**：对 joint_minmax 与未来的 A2 方法各跑两版；产物 2x2 表；关闭条件：能分离"路线内容"与"slot 打包"的贡献。
5. **实现 author_loadbalance（隔离 build 的 driver 类）与 cheap_balance/threshold 三件套**：产物各自结果 JSON；关闭条件：三者在 11 图上均按时交付或明确记失败。
6. **补 intent 收据**：为 03/04 增加 INTENT 写出（含源码 hash、registry hash），并核对 AUTHOR_INTENT 的 author_source_hashes=null 是否需重登记。关闭条件：每个批次目录都有 INTENT.json 且 hash 非空。

### 9.5 是否需要用户决策

不需要。本文件只冻结资格与规格，未消耗新资源、未开新人口、未改任何历史文件；confirm 的 36 图已在既有登记下运行，不因本文件改变。

---

## 10. 证据索引

### 10.1 本地（相对 <LOCAL_PATH>

- joint_weather_emergency/20261112_takeover_completion/results/g3_pop/{population_index,AUTHOR_RESULTS,NONRL_RESULTS,EXACT_REASSIGN_RESULTS}.json
- joint_weather_emergency/20261112_takeover_completion/results/g3_pop/author/<map>/{RUN.json,solution.json,return_score.json,stdout.log}
- joint_weather_emergency/20261112_takeover_completion/harness/{02_run_author.py,03_run_nonrl.py,04_exact_reassign.py,gen_maps.py,10_gen_pop.sh}
- joint_weather_emergency/20261112_takeover_completion/{CODE_MAP.md,TAKEOVER_AUDIT.md,PRIOR_ART_EQUATION_AUDIT.md,PAPER_EQUATION_COMPARISON.md,SPLITS_AND_EXCLUSIONS.md,CLOSED_DIRECTIONS.md}
- route_rl_research/20261103/return_makespan/{scorer.py,delivery.py,g23/nonrl_baseline/baseline.py,g23/author_baseline/author_runner.py,EXECUTION_PLAN.md,ROUND_DECISION.md,G23_ROOT_STATUS.md}
- project_status/20261112_claude_handoff/CLAUDE_TAKEOVER_PROMPT.md §11
- project_status/20261112_{g0_joint_event_screen/STRONG_NONRL_SPEC.md, zhao_han_fulltext_audit/NONRL_QUALIFICATION_ADDENDUM.md, cfa_repository_version_audit/NONRL_QUALIFICATION.md}
- stage_a_audit/{BASELINE.md,MODIFIED_FILE.md}

### 10.2 服务器（<EXECUTION_PATH>

- g3_pop/AUTHOR_INTENT.json（3038 B）、g3_pop/{AUTHOR_RESULTS,NONRL_RESULTS,EXACT_REASSIGN_RESULTS}.json
- g3_confirm/PREREG_CONFIRM.json（1025 B，registered_at_utc 2026-11-12T08:06:55Z）
- prereg_20261112/STATS_self.json（sha256 95dac248dc395ac4e80bd3e6396ba471af2b5c00ad533cfc7b6c3dc7dc077411）
- prereg_20261112/compute_stats_server.py（sha256 eef73b6262fef648e15b74161c4c2a463b11c6b695bf565818f6340b9c927738）
- prereg_20261112/replay/EXACT_REASSIGN_RESULTS.json（sha256 7737e1861167274193a566cb92cc382a5ef907a3fd27ae2c7e5f6c66523443f6，与 g3_pop 版字节一致）
- author_build/J1b/classes、runtime/jdk17、logs/{author_pop1.log,confirm.log}
- <EXECUTION_PATH>

### 10.3 版本钉死与并发覆盖（重要）

本文件 §6.1 的逐图值钉死在下列**本地快照**（本包 results/g3_pop，写入时间 2026-11-12 16:03 CST / 08:03 UTC）：

| 文件 | bytes | sha256 |
|---|---:|---|
| AUTHOR_RESULTS.json | 2,429 | 51c5ce97426217f717a786a3700be74d1a43578da02cfc9bf9e334c32f374604 |
| NONRL_RESULTS.json | 37,206 | 94e11a7c90038f49a4413259bcc4a8657f62bccbc6cd0d0b764d366c37e763aa |
| EXACT_REASSIGN_RESULTS.json | 44,096 | 7737e1861167274193a566cb92cc382a5ef907a3fd27ae2c7e5f6c66523443f6 |
| population_index.json | 8,126 | 05a0f7c1b4fa5b8eef3964aa691322683cef0e234dba40cc9a9fd929e8d85692 |

并发事实（[已证实-收据]，只读观察）：服务器 g3_pop/NONRL_RESULTS.json 在 08:03Z 时为 37,206 B / sha 94e11a7c…，到 **08:16Z 已被覆盖**为 40,284 B / sha 14cda35b11882a03fba306e0716b341be99f3459147f0888bd257342e5171789，覆盖者是另一个正在跑的 03_run_nonrl.py --out .../g3_pop 进程（非本线程，未干预）。含义：

1. 本文件的 dev 表与 STATS_self.json 都属于 **08:03Z 版本**；若新版修了 §2.8 的 duty 口径或加了方法，逐图值会变，任何引用必须写明版本。
2. 新跑完的 g3_confirm（08:13Z 已有 EXACT_REASSIGN_RESULTS.json 139,893 B、NONRL_RESULTS.json 120,841 B）是**确认集**收据，与 dev 表分列，不得混用。
3. 若需要"未覆盖的 dev 原件"，本包 results/g3_pop 的本地快照即为冻结副本（上表哈希）。
