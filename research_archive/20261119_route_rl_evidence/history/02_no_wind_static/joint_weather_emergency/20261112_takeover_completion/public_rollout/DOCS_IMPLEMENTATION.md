# public_rollout — 实现说明、模块映射与验收诚实性

日期：2026-11-12。运行机：<COMPUTE_HOST>（Python 3.10.12，仅标准库）。
实现依据：`../PUBLIC_ROLLOUT_CONTRACT.md`（§2 对象、§3 粒子、§4 事件序、§5 发布、§6 动作、§7 账本、§8 T1–T7）。

## 1. 模块映射（合同 §9.1 的 10 个模块 → 实际 6 个文件）

| 合同 §9.1 模块 | 本实现文件 | 说明 |
|---|---|---|
| #1 `env/public_prefix.py` | `env/core.py` | StaticContext / PublicPrefix / ObservationFrame / 记录类型 / 哈希 / A-01..A-13 |
| #2 `env/forecast_book.py` | `env/forecast_book.py` | 版本化发布、可见性、禁止改写 |
| #3 `env/latent_phase.py` | `env/latent_phase.py` | FrozenParticleModel、H2 采样、相容性、拒绝唯一相位 |
| #4 `env/exogenous_stream.py` | `env/exogenous_stream.py` | 移动椭圆 NFZ、背景 Poisson 释放、**`AlarmLaw`（逐目标预抽故障概率与延迟）**；引擎的 `_reveal_alarms` 负责到期公开 |
| #5 `env/causal_engine.py` | `env/causal_engine.py` | 事件闭包、固定顺序、reservation、中途分叉、终局 |
| #6 `env/episode_audit.py` | `env/episode_audit.py` | 独立全 episode 复算（自有物理循环，不 import 引擎）；T7-A3 已改为真实调用 |
| #7 `policies/mu.py` | `policies/mu.py` | 只有 `lpt` / `nearest` / `idle`；**未实现** joint_minmax/beam/N4 |
| #8 `tests/run_t*.py` | `tests/run_all.py` + `tests/mutation_check.py` | T1–T8 在一个文件里 |
| #9 `drivers/` | `drivers/run_episode.py` | intent 先写并 fsync，行在汇总前 fsync 落盘 |
| #10 `receipts/schema.py` | `tests/run_all.py` 内的 `_receipt` | 无独立 schema 模块 |
| 额外交付 | `env/metrics_w.py` | W 三指标：高优先准时率（分母含未服务任务）、迟到 CVaR90（保留 0 迟到）、成本比 bootstrap CI |

`env/snapshot.py` 是合同没列但必需的第 11 个文件：把运行中的引擎导出成 `PublicPrefix`。

## 2. 物理与语义实现要点

- 沿程风：`ground = airspeed + along_track_wind`，`along = (u·dx + v·dy)/dist`，速度下限 1e-3。
- 能耗：飞行 `time · flight_energy`；服务 `target.energy` 在服务结束时一次性结算（合同允许按比例，本实现取结束时结算，见 §3 H-2）。
- duty：飞行 + 服务累计；**RETURN 只清 trip_energy，不清 duty**（T6-A1 断言）。
- 决策前沿：先闭包同刻事件，再按 `sorted(slots)` 固定顺序逐 slot 决策；`decided_here` 阻止同前沿重派。
- 动作域：只有 `(slot,target)` 与 `(slot,RETURN)`；无 WAIT/DIVERT。

## 3. 与合同的已知偏差（必须在引用时带上）

| 编号 | 偏差 | 影响 |
|---|---|---|
| H-1 | ~~立即到达~~ **已修复（第五轮）**：改为两阶段 `IDLE → FLYING → SERVING`，位置/能量/duty 只在**到达时刻**推进 | 修好后 W 的截止期才有意义：`served_at = 出发 + 航段 + 服务`，T10 的手算与引擎一致 |
| H-2 | 服务能耗在服务结束一次性结算，不是按比例累积 | 与 `emergency_scenario` 的比例累积不同；相位别名的结论不依赖这一点 |
| H-3 | 告警生成律已实现（`AlarmLaw`：逐目标预抽 p 与 [0,20] 延迟，**先抽后验**），但**参数 p=0.2、延迟 U[0,20] 是工程默认值，不是拟合值** | 分布语义可测；参数的物理依据仍缺（需真实故障数据或独立 TRAIN 校准） |
| H-4 | 只有 3 个非学习基策略，没有 N4/beam/joint_minmax | 不影响 T1–T7，但不足以支撑 G3 |
| H-5 | 只有单 episode driver，没有批次 driver 与并行调度 | 不可直接用于科学批次 |

## 4. 验收诚实性：每条断言到底验了什么

**2026-11-12 第二轮更新：原先 6 条弱断言已全部改成真断言，现在 52 条断言全部有判别力。**

| 断言 | 原先的问题 | 现在的实现 |
|---|---|---|
| T1-A1..A4 | 只比了能量 | 拆成 4 条独立断言：**隐含地速是否落在风支撑内**（A1）、能量代数复算 ≤1e-12（A2）、**duty 不小于已用时间**（A3）、**完成记录条数带入前缀**（A4） |
| T3-A1 | 手写前缀自证 | 真的构造 P/Q 两条风史（到达 t=3 / t=5），断言两者的 **SlotView 逐字段相等** 而剩余服务不同 |
| T3-A3 | 只验"拒绝" | 实现 `k = fe − E_service/dur` 的**可识别性判据**：k≠0 时返回解析值并断言 =1.0，k=0 时拒绝。alias 与可识别两种情形都测 |
| T4-A3 | 空断言 | snapshot 现在记录 `pending_order`，断言**每个分叉都逐项恢复** pending 列表 |
| T5-A6 | 只声明不执行 | 真的实现 `ConstantForecastBaseline`（复刻 `emergency_scenario.Scenario.forecast` 的常数元组语义）并执行，记录 `version_stable=True, content_stable=True` ⇒ **BASELINE_CANNOT_PASS** |
| T6-A5 | `abs(limit−limit)` 恒真 | 直接测分类器边界：`duty==limit → 无终局`、`limit+1e-9 → 无终局`、`limit+1e-6 → DUTY_LIMIT`；并断言 mask 在严格站上拒绝该目标 |

#### 4.0 W 模式（第三轮新增 T8，5 条断言）

| 断言 | 验什么 |
|---|---|
| T8-A1 | t=0 时**未释放**的背景请求在帧里**完全不可见**（不是标成 UNRELEASED，而是不出现）—— 这修掉了一个真实的泄漏：早期实现会把未释放目标列成 UNRELEASED，等于泄露其存在 |
| T8-A2 | t=60 时该请求变为 OPEN 且可选 |
| T8-A3 | 处于活动 NFZ 内的目标在 t=0 **不可选** |
| T8-A4 | 椭圆失效（t>40）后同一目标**可选** |
| T8-A5 | 航段穿越活动 NFZ 时该目标**被拒绝**（沿航线 12 点采样） |

实现要点：`MovingNFZ` 为匀速平移椭圆，`blocks_leg` 保守采样；`poisson_releases` 用独立指数间隔生成背景请求；NFZ 几何随帧公开（`ObservationFrame.nfz`），因此它不是私有信息。

## 4.1 由此发现的实现事实（值得单独记）

**`DUTY_LIMIT` 终局无法通过合法动作到达**——`legal_actions` 会先拒绝任何会越过 duty 上限的动作。
因此 `_check_duty` 只是一个浮点边界守卫，而不是一条常见失败路径。这不是缺陷（mask-first 是合同要求），
但意味着 **"duty 失败"必须由 scorer 层计分，而不是期待引擎自然产出该终局**。
T6-A5 现在同时断言这两件事。

### 4.2 仍然存在、但不属于"弱断言"的边界

- T2-A4 是对**源码文本**的检查（无 `Scenario`/`Trace`/`truth` 标识符）+ T2-A1/A2/A3 的行为等价性；它不能证明"绝对无泄漏"，只能证明"在该引擎的代码路径上没有读取私有真值的入口"。
- T5-A6 的基线是**忠实复刻语义**的类，不是原 `emergency_scenario` 的实例（那需要导入整个天气包）。这一区别在断言 detail 里写明。

## 4.5 独立全 episode 复算（原 H-4 缺口，已闭合）

`env/episode_audit.py` 用**自己的物理循环**（不 import 引擎）从动作日志 + 粒子重推每个 slot 的位置、trip energy、duty、served_at、M_return、operating_minutes，并与账本逐项比对（相对误差 ≤1e-9）。

首次运行它**确实不一致**（重算 M_return 30.0141 vs 账本 30.0000，相对误差 4.7e-4），
原因是复算里的沿程风投影写错（只用 u 分量）；修正为 `along = (u·dx + v·dy)/dist` 后一致。
这条记录保留：**它证明这个复算不是照抄引擎——照抄的话第一次就会"通过"**。

### 4.05 告警律（第四轮新增 T9，5 条断言）

告警是**外生**且**到期才公开**的：调度存放在粒子的 `future.faults` 里，引擎的 `_reveal_alarms` 只在 `t >= t_at` 时把目标重新置为 OPEN（priority=high）；二次到访后写入 `ALARM_SERVICED` 并清空告警。终局 `COMPLETE` 要求**既无缺失目标、也无未处理告警**。

| 断言 | 验什么 |
|---|---|
| T9-A1 | t<30 的所有帧里都看不到该告警 |
| T9-A2 | t≥30 后该目标以 OPEN/high 出现 |
| T9-A3 | 二次到访后被记为 ALARM_SERVICED，告警清空 |
| T9-A4 | duty 上限使二次到访物理不可达时，终局是 **PARTIAL_COVERAGE** 而不是 COMPLETE |
| T9-A5 | 告警处理完毕后终局回到 COMPLETE |

## 4.06 单 episode driver（第四轮）

`drivers/run_episode.py`：先把 intent（`episode_key`/静态哈希/seed/mu/releases/faults）写入并 **fsync**，再运行，最后把行 **fsync** 追加到 `rows.jsonl`。崩溃只能丢失"正在跑的那一行"，不会丢掉"曾经尝试过"这一事实。实测：f02、seed=7 → 6/6 服务、COMPLETE、wall 0.0029 s。

### 4.07 W 指标与 T10（第五轮，5 条断言）

`env/metrics_w.py` 实现 W 合同 §7.5 的三项指标，**每条都写明分母**：

| 指标 | 定义 | 分母/边界 |
|---|---|---|
| 高优先准时率 | `high_on_time / high_total` | `high_total` 是静态上下文声明的**全部**高优先任务，**未服务的也计入** |
| 迟到 CVaR90 | 每任务迟到的最差 10% 的均值 | 迟到为 0 的**保留**在分布里；未服务任务按 +∞ 计入（迫使尾部） |
| 成本比 | `candidate / reference` 的逐图配对比 | 地图级 bootstrap CI（默认 10000 次），并直接给出 `upper_le_threshold`（阈值 1.01） |

T10 用**零风**夹具做手算校验：航段 10 min + 服务 10 min = 20 min，截止期 15 → 迟到 5；两条高优先都迟到 ⇒ 准时率 0/2；`[0,5,5]` 的 CVaR90 = 5.0（最差 10% 取 1 个）——引擎输出与手算逐位一致。

### 4.08 告警生成律与 T11（第六轮，5 条断言）

`AlarmLaw(prob, delay_lo, delay_hi)` 在 episode 开始**之前**为每个目标抽一次：是否发生故障、以及故障距扫掠的延迟（`-1` 表示无故障）。因此告警**不可能**以策略行为为条件；它只在该目标真的被扫掠时才兑现。

| 断言 | 验什么 |
|---|---|
| T11-A1 | 2000×3 = 6000 次抽样中故障比例 0.1945，落在 p=0.2 的 4σ 带内（4σ=0.0207） |
| T11-A2 | 全部 1167 个有限延迟都在 [0, 20] |
| T11-A3 | 告警时间不早于该目标的**首次完成时刻**（不是派遣时刻） |
| T11-A4 | 告警时间 = 首次完成 + 抽到的延迟（逐位） |
| T11-A5 | p=0 时一个告警都不产生 |

**同时修掉一个真实 bug**：原先每次服务完成都会再排一次告警，导致二次到访后又冒出一个新告警。现在用 `alarm_seen/alarm_done` 保证**每个目标至多一次故障**。

## 5. 变异检验（证明测试不是空转）

`tests/mutation_check.py` 注入 4 个缺陷，验证对应测试会失败：

| 注入缺陷 | 期望被抓 | 实测 |
|---|---|---|
| 引擎读取私有 truth 句柄 | T2 | **FAIL（被抓）** |
| RETURN 不清 trip_energy | T6 | **FAIL（被抓）** |
| `visible()` 忽略发布时间 | T5 | **FAIL（被抓）** |
| 采样器返回点质量相位 | T3 | **FAIL（被抓）** |
| 告警提前公开 | T9 | **FAIL（被抓）** |
| 忽略告警律 | T9 | **FAIL（被抓）** |
| 公开未释放的背景请求 | T8 | **FAIL（被抓）** |
| 忽略 NFZ 几何 | T8 | **FAIL（被抓）** |

8/8 被抓 ⇒ 这八条测试有判别力。**未做变异检验的断言（含上述 7 条弱断言）不在此保证内。**

## 6. 相位可识别性（为什么拒绝返回唯一剩余服务）

记录到的 `trip_energy = fe·e + E_service·(T−e)/dur`。
别名夹具里 `fe = 1/8`、`E_service = 1/2`、`dur = 4`，于是 `fe − E_service/dur = 0`，
该式对 e **恒等于 0.75**，即任意 `e ∈ [0,6]` 都相容 ⇒ 剩余服务 `= e − 2 ∈ [0,4]`。
两个解析见证（剩余 1 与 3）都落在这个支撑内。
因此 `recover_exact_phase` 一律抛 `PhaseNotIdentifiable`；任何返回点值的实现都是在编造信息。
这也**修正**了 `CODE_MAP.md` 早期「service energy>0 时被 trip_energy 钉住」的说法：该说法只在服务能耗为零时成立，别名夹具本身就是反例。

## 7. 运行

```bash
R=<EXECUTION_PATH>
cd $R/code && python3 -m tests.run_all --out $R/receipts   # T1-T7
cd $R/code && python3 -m tests.mutation_check --out $R/receipts  # 4 个变异体
```

真实收据：`receipts/SUMMARY.json`（READY=true）、`receipts/T1..T11.json`、`receipts/MUTATION.json`（8/8 caught）、`receipts/driver/`（intent + rows.jsonl）。
本包副本见 `../../public_rollout_receipts/`。