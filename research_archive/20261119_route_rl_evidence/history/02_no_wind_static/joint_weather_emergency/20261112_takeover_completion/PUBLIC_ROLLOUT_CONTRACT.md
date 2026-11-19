# PUBLIC_ROLLOUT_CONTRACT — 公共因果环境与真实 rollout 的可执行合同

**文件定位**：`joint_weather_emergency/20261112_takeover_completion/PUBLIC_ROLLOUT_CONTRACT.md`。
**性质**：只写**规格与伪码**。本文件不实现、不训练、不求解、不连接 <COMPUTE_HOST>、不产生任何科学结果。所有“应通过”都是**待执行断言**，不是已取得的收据。
**上游依据**：`CAUSAL_ROLLOUT_APPENDIX.md`（裁决 `PUBLIC_STATE_RECONSTRUCTION_REQUIRED`，T1–T7）、`20261105/PROTOCOL.md`、`20261105_deep_revision/{REPORT,FUTURE_TRAIN_ONLY_DECISIONS}.md`、`20261112_public_fault_conditioning/{REPORT.md,MODIFIED_FILE/public_fault_law.py}`、`20261112_wx_e_forecast_v1/src/emergency_scenario.py`、本包 `CODE_MAP.md`、`TAKEOVER_AUDIT.md`、`CLOSED_DIRECTIONS.md`、`PRIOR_ART_EQUATION_AUDIT.md §C`、`CLAUDE_TAKEOVER_PROMPT.md §3/§8/§11-B`。
**证据分级**（全文统一）：`[已证实-代码]` 有源码行号；`[已证实-收据]` 有落盘数字与分母；`[设计-冻结]` 本文新冻结、需上游签字（§12）；`[未证实]` 不得当结论。

---

## 0. 一页速查

| 项 | 冻结值 | 依据 |
|---|---|---|
| 时间基准 | 事件日 `00:00Z` 起算的 `t_min`（float，分钟，binary64）；绝对 UTC = `epoch_utc + t_min`，只在收据里派生 | 本文 §1.3 `[设计-冻结]` |
| 同刻判定 | **精确相等**，`a.t_min == b.t_min`；禁止任何容差分组 | `emergency_scenario.py:697,742-743` `[已证实-代码]` |
| 决策顺序 | 冻结的 `(station_id, slot_index)` 升序；同刻闭包完成后逐个决定，决定即 reservation | `emergency_scenario.py:702`、`:538-539` `[已证实-代码]` |
| 动作 | 仅 `(slot,target)` 与 `(slot,RETURN)`；无 WAIT、无 DIVERT、无 in-flight 中断 | `[设计-冻结]`；越界一律合同违规 |
| 无合法动作 | **不调用策略**：记 `STANDBY` 并由环境推进（≠ WAIT，≠ 动作） | 本文 §6.3 `[设计-冻结]` |
| 预报发布 | `publication_t_min = 0,60,120,…`；`valid=[t_pub, t_pub+180)`；发布**不唤醒**待命 slot | 本文 §5 `[设计-冻结]`（现状无此机制：`emergency_scenario.py:100` `[已证实-代码]`） |
| 粒子 | 模型样本，**不是**公共状态；策略 API 物理上拿不到；只用独立 TRAIN 拟合 | 本文 §3 `[设计-冻结]` |
| 过去 | 前缀账本逐字复制，**不重采、不重算** | 本文 §7.2 |
| 静态 S | `C ≤ C_Liu + 1e-7`、`epsilon=0`、6 s/12 s、`M_return`、`MTC` 辅助——**全部不变** | `scorer.py:269-273,205,210`；§10 |
| W | 成本比 bootstrap 95% 上界 ≤ 1.01、CVaR90——**不替换** | `CLAUDE_TAKEOVER_PROMPT.md §3.3`；§10.3 |
| G0 | 本环境**不是**新机制；不解除 `G0_NO_GO_AS_DISTINCT_ALGORITHM` | `PRIOR_ART_EQUATION_AUDIT.md §C.4`；§10.4 |

---

## 1. 范围、对象与三条分离

### 1.1 覆盖与不覆盖

**覆盖**：一张 Liu 型地图（多站、SABS/DABS、slot、`target_station` 固定、多趟、累计 duty、能量、返航义务）在**事件日**上的一次完整因果执行：外生天气、每小时发布预报、故障告警、背景请求、移动 NFZ；策略只输出物理路线动作；终局按既有合同计分并可独立回放。

**不覆盖**：新算法、新估计器、新信用分配；G0 准入；训练；作者锚点生成（仍在 <COMPUTE_HOST> 用 J1b 隔离 JDK 跑，`code/author_build`）；`C_Liu` 的生成；跨图聚合器实现（只给规则，§7.6）。

### 1.2 三个对象（本合同的心脏）

```text
公共前缀 public_prefix      —— 已发生的、所有方法共享的、不可修改的公共记录（§2.2）
粒子     particle           —— 冻结公共模型的一个样本：与公共记录相容的隐藏过去 + 隐藏当前 + 未来外生流（§2.5）
分支     branch             —— 从前缀 + 粒子构造的一次私有执行（§2.6）
```

三条**不可违反的分离**：

- **S1 信息分离**：策略的输入类型只有 `ObservationFrame`。`Particle` / `Branch` / `EngineState` 在类型与运行时都不出现在策略调用链上（`[设计-冻结]`；现状对照：`emergency_scenario.py:302` 的 `Policy = Callable[[Observation], Action]`、`causal_task_memory.py:45` 的 `predictive_sufficiency_proven=False`）。
- **S2 历史分离**：`t ≤ t_fork` 的一切（动作、服务、成本、失败、发布、告警）来自前缀，逐字复制；分支只能**向前**追加记录（§7.2）。
- **S3 真值分离**：真实私有未来（`Scenario.trace`、私有 `events`）只允许出现在**执行之后**的审计里（`emergency_independent_replay.py:1-4` 已确立同款边界）；分支推进只吃 `particle.future`。

> **一句话**：前缀回答“发生过什么”，粒子回答“现在可能处于什么隐藏阶段、接下来可能发生什么”，分支回答“如果这样做，会发生什么”。三者混同即本合同失败。

### 1.3 时间与单位

| 量 | 单位 | 说明 |
|---|---|---|
| 时间 | 分钟（min），float | `t_min` 相对事件日 `00:00Z`；`utc = epoch_utc + t_min*60s`，只在收据派生 |
| 距离 | 米（m） | 与 instance 坐标同系，不重投影 |
| 速度 | m/min | 静态 `problem.params.speed`；W 空速默认 900 m/min（`emergency_scenario.py:82`） |
| 风 | m/min 分量 `(wx,wy)` | 与 `reference_environment.py:11-23` 同系；风速上限 6 m/s=360 m/min 见 §5.5 |
| 能量 | instance 能量单位（无量纲） | **不计入成本**，只作硬约束（`CODE_MAP §C.1`，`scorer.py:173-174`） |
| 成本 | 与 `scorer.cost` 同币值 | `fixed + 0.5*operating_minutes`（`scorer.py:205`） |
| duty | 分钟 | 跨趟累计，RETURN **不清零**（`global_env.py:156`） |

**时间纪律**：① 不做 `abs(a-b) < tol` 的“同刻”判断；② 时钟单调（`EVENT_TIME_REVERSED` 直接失败，`emergency_scenario.py:334-335`）；③ 正时长事件必须推进 binary64 时间（`WAIT_CLOCK_NO_PROGRESS` 的同款纪律，`:526-528`）；④ 终点恰在 `H` 上的完成事件**可观测**，`> H` 的相位一律截断（`:601-608`）。

### 1.4 两种模式，同一套代码

| | `S_STATIC` | `W_EVENT_DAY` |
|---|---|---|
| 风 | ≡ 0（强制） | 粒子 `future.weather` |
| 预报发布 | 无（`publications=()`） | 每小时 |
| 故障告警 / 背景请求 | 无 | 粒子 |
| NFZ | 无 | 粒子（移动椭圆） |
| 终点 | 全部服务 + 全部返航（无 horizon） | `horizon_min`（默认 480）或全部完成 |
| 终局裁判 | **只** `scorer.score_solution` | W 指标 + 独立回放（§7.5） |
| 成本 | `fixed + 0.5*operating`（唯一） | `wind_clock_cost`（§7.5），并另报 `no_wind_cost` 诊断 |

`S_STATIC` 是 `W_EVENT_DAY` 在“零风、零外生、`horizon=∞`”下的**退化**，且必须逐位复现 `scorer`（义务见 §10.2）。禁止用 W 的任何指标去替代 S 的 cap 与 `M_return`。

---

## 2. 字段级状态对象

### 2.0 对象关系

```text
StaticContext ──┐
                ├──> PublicPrefix ──┐
ObservationFrame┘                   ├──> Branch ──> RolloutReceipt ──> AuditResult
Particle ───────────────────────────┘
```

### 2.1 `StaticContext`（实例级公共常量）

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 校验 / 说明 |
|---|---|---|---|---|---|
| `instance_id` | `str` | — | — | ✅ | 生成器身份 `(namespace,family,partition,ordinal)`，须在 `SPLITS_AND_EXCLUSIONS.json` 中唯一 |
| `raw_sha256` | `str(64)` | — | — | ✅ | 原始实例字节哈希 |
| `canonical_geometry_sha256` | `str(64)` | — | — | ✅ | 几何规范哈希（去重与泄漏检查用） |
| `mode` | `str` | — | — | ✅ | `"S_STATIC"` \| `"W_EVENT_DAY"` |
| `day_id` | `str` | — | UTC 日 | ✅ | `YYYY-MM-DD`，事件日 0 点 |
| `epoch_utc` | `str` | — | UTC | ✅ | `"YYYY-MM-DDT00:00:00Z"`，`t_min` 的原点 |
| `horizon_min` | `float \| None` | min | UTC 相对 | ✅ | S 模式必须 `None`；W 模式 `480.0`（`[设计-冻结]`，见 §12-D5） |
| `stations` | `tuple[StationSpec,...]` | — | — | ✅ | 见下 |
| `targets` | `tuple[TargetSpec,...]` | — | — | ✅ | 见下；**未来任务不在此**（背景请求在粒子内） |
| `slots` | `tuple[SlotSpec,...]` | — | — | ✅ | 见下；`slot_key=(station_id,slot_index)` |
| `params` | `ParamsSpec` | — | — | ✅ | 见下 |
| `anchor` | `AnchorSpec \| None` | — | — | ✅ | S 模式必填；W 模式可空（W 不用 cap） |
| `exclusions` | `tuple[str,...]` | — | — | ✅ | 已暴露身份清单哈希（只登记身份，不泄漏内容） |
| `freeze_hashes` | `tuple[(str,str),...]` | — | — | ✅ | 本实例用到的每个冻结件 `(name, sha256)`：物理核、评分器、粒子模型、预报模型 |

**`StationSpec`**

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 校验 |
|---|---|---|---|---|---|
| `station_id` | `int` | — | — | ✅ | ≥0，唯一；`problem.py` 官方 id |
| `x_m`,`y_m` | `float` | m | — | ✅ | 有限 |
| `kind` | `int` | — | — | ✅ | `0` 关闭 / `1` SABS / `2` DABS（`global_env.py:33-34`） |
| `fixed_cost` | `float` | 币值 | — | ✅ | `kind→{0:0,1:27.8,2:43.4}`（`scorer.py:117-120`） |
| `radius_m` | `float` | m | — | ✅ | **按站型**，不按 slot（`CODE_MAP §G-1`） |
| `duty_limit_min` | `float` | min | — | ✅ | **按站型**；DABS 的 SD 用 large 上界（`global_env.py:52-59`，`scorer.py:153,184`） |
| `service_min` | `float` | min | — | ✅ | 官方合同强制 `0.0`（`problem.py:70`）；非 0 直接拒绝加载 |
| `slot_ids` | `tuple[int,...]` | — | — | ✅ | SABS=`(1,)`；DABS=`(0,1)`；关闭=`()` |

**`TargetSpec`**

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 校验 |
|---|---|---|---|---|---|
| `target_id` | `int` | — | — | ✅ | 唯一；官方 `energy>0` 区分站点/目标（`problem.py:66-70`） |
| `station_id` | `int` | — | — | ✅ | **固定归属**，不可由动作改变（`scorer.py:271-272`） |
| `x_m`,`y_m` | `float` | m | — | ✅ | 有限 |
| `service_min` | `float` | min | — | ✅ | ≥0 |
| `energy` | `float` | 能量 | — | ✅ | >0 |
| `base_class` | `str` | — | — | ✅ | `"ROUTINE"`（W 下可被告警升级）\| `"EMERGENCY_PLANNED"`（S 下全部为 ROUTINE 语义） |
| `release_min` | `float` | min | UTC 相对 | ✅ | S 模式恒 `0.0`；W 模式为“常规任务已存在”的释放时刻（通常 0） |
| `deadline_min` | `float` | min | UTC 相对 | ✅ | S 模式 `inf`；W 常规任务 `inf`，紧急任务有限 |
| `priority` | `int` | — | — | ✅ | ≥0；高优先 `≥10`（`joint_core.py:121-122`） |

**`SlotSpec`**

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 校验 |
|---|---|---|---|---|---|
| `station_id`,`slot_index` | `int` | — | — | ✅ | `slot_index`：`0`=LD（大电池）、`1`=SD（小电池） |
| `battery_capacity` | `float` | 能量 | — | ✅ | `0→large_battery`，`1→small_battery`（`global_env.py:48-51`） |
| `qualification` | `str` | — | — | ✅ | `"LD"`\|`"SD"`；SABS 只有 `1` |
| `radius_m` | `float` | m | — | ✅ | **等于所属站的 `station.radius_m`**（复制值，防实现漂移） |
| `duty_limit_min` | `float` | min | — | ✅ | **等于所属站的 `station.duty_limit_min`**（复制值） |

**`ParamsSpec`**：`speed_m_per_min`、`flight_power`（≡ `problem.params.flight_energy`，每飞行分钟能耗）、`time_cost=0.5`、`cost_tolerance=1e-7`、`physics_tolerance=1e-7`、`epsilon=0.0`、`small_battery`、`large_battery`、`small_duration_min`、`large_duration_min`、`small_radius_m`、`large_radius_m`、`airspeed_m_per_min`、`wind_bound_m_per_min`（mask 用的保守上界，PROTOCOL 的 0/3/6 m/s 分层换算）。**全部取 instance 的 `problem.params`**；历史 pilot 的 `0.81/1.0/480/600` 只属于那个身份，禁止跨身份套用。

**`AnchorSpec`**：`source`（`"J1b"`）、`anchor_solution_sha256`、`anchor_cost`（= `CostAnchor.cost`）、`anchor_m_return`（= `CostAnchor.makespan`，`scorer.py:221-247`）、`station_types:tuple[int,...]`、`target_station:tuple[(int,int),...]`、`anchor_eligible:bool`、`run_json_sha256`。

### 2.2 `PublicPrefix`（公共前缀，不可变）

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 说明 |
|---|---|---|---|---|---|
| `prefix_id` | `str` | — | — | ✅ | `sha256(static_hash, t_fork, ledger)` |
| `static_hash` | `str(64)` | — | — | ✅ | 指向 `StaticContext` 的规范哈希 |
| `t_fork_min` | `float` | min | UTC 相对 | ✅ | 分叉前沿；`≥0`，有限 |
| `frontier_id` | `int` | — | — | ✅ | 单调递增的决策前沿计数 |
| `observations` | `tuple[ObservationFrame,...]` | — | — | ✅ | 只保留**最近一次**为必需；历史可选（存储上限 1 帧/前沿，见 §9.4） |
| `dispatches` | `tuple[DispatchRecord,...]` | — | — | ✅ | 已执行动作，有序 |
| `completions` | `tuple[CompletionRecord,...]` | — | — | ✅ | 已发生回调（含失败/截断） |
| `standbys` | `tuple[StandbyRecord,...]` | — | — | ✅ | 环境推进（非动作） |
| `publications` | `tuple[PublicationRecord,...]` | — | — | ✅ | 已发布预报（含过期版本，只增不改） |
| `alarms` | `tuple[AlarmRecord,...]` | — | — | ✅ | **保留已发布且已服务的告警**（`public_fault_law.py:69-71` 的同款纪律） |
| `pending_decisions` | `tuple[PendingDecision,...]` | — | — | ✅ | 同刻未决定的 slot（§4.5） |
| `reservations` | `tuple[ReservationView,...]` | — | — | ✅ | 当前有效预约 |
| `metrics` | `MetricLedger` | — | — | ✅（只读派生） | 累计账本（§7.1） |
| `crn` | `tuple[(str,int),...]` | — | — | ✅ | 公共随机数登记 `(stream_name, seed)`；用于共同随机数 |
| `ledger_sha256` | `str(64)` | — | — | ✅ | 自身规范哈希（排序键固定后计算） |

**不变量**：`dispatches`/`completions`/`standbys` 的 `t_min` 单调不减；`seq` 全局唯一且递增；`∀ rec ∈ completions: rec.kind ∈ COMPLETION_KINDS`；`∀ res ∈ reservations: res.target_id` 的状态为 `IN_FLIGHT`；`alarms` 中同一 `target_id` 在“首告警”语义下至多一条（§5.6）。

### 2.3 `ObservationFrame`（策略唯一输入）

`[设计-冻结]` 字段严格对应 `emergency_scenario.py:257-282` 的 `Observation`，外加前缀化所需的四组记录。

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 说明 |
|---|---|---|---|---|---|
| `frontier_id` | `int` | — | — | ✅ | |
| `t_min` | `float` | min | UTC 相对 | ✅ | |
| `acting_slot` | `SlotKey=(int,int)` | — | — | ✅ | |
| `own` | `SlotView` | — | — | ✅ | 本 slot |
| `fleet` | `tuple[SlotView,...]` | — | — | ✅ | **全部** slot（含其它站），按 `slot_key` 升序 |
| `released_targets` | `tuple[TargetView,...]` | — | — | ✅ | `release_min ≤ t` 的全部目标（含 `IN_FLIGHT/SERVED/FAILED`）；**未来任务不出现** |
| `served_ids` | `tuple[int,...]` | — | — | ✅ | 升序 |
| `missed_ids` | `tuple[int,...]` | — | — | ✅ | 已过 `deadline` 且未服务 |
| `reservations` | `tuple[ReservationView,...]` | — | — | ✅ | |
| `wind_now` | `tuple[float,float]` | m/min | 当前 | ✅ | 当前观测风，仅当前值 |
| `forecast` | `PublicationRef` | — | — | ✅ | 最新 `publication_t_min ≤ t` 的版本（`version, publication_t_min, content_sha256`） |
| `alarm_ids` | `tuple[int,...]` | — | — | ✅ | 已发布告警（含已服务），升序 |
| `pending_slots` | `tuple[SlotKey,...]` | — | — | ✅ | 本前沿尚未决定的 slot（§4.5） |
| `counters` | `LedgerCounters` | — | — | ✅ | `decisions, dispatches, completions, standbys, publications, alarms, served, missed` |

**`SlotView`**（对应 `DroneView`，`emergency_scenario.py:244-254`，加 slot 维度）：`slot_key`、`station_id`、`slot_index`、`x_m`、`y_m`、`at_station:bool`、`trip_energy:float`（能量）、`duty_min:float`（min）、`trip_started:bool`、`trip_target_ids:tuple[int,...]`、`terminal_failure:str|None`、`committed:bool`（本趟是否已有预约）。

**`TargetView`**：`target_id`、`station_id`、`x_m`、`y_m`、`service_min`、`energy`、`release_min`、`deadline_min`、`priority`、`is_emergency:bool`、`status:str ∈ {AVAILABLE,IN_FLIGHT,SERVED,FAILED,TRUNCATED}`、`alarm_t_min:float|None`。

**`ReservationView`**：`target_id`、`slot_key`、`dispatch_seq:int`、`t_min`。

**`LedgerCounters`**：七个 `int` 计数（上表末列）。

**禁止**：`wind_now` 之外不得出现任何“未来风数组”；`forecast` 只给引用，不内联未来块（全文仍在 `publications` 里，且只到 `valid_to`）。

### 2.4 记录类型（前缀与账本的元素）

| 记录 | 字段（名:类型:单位） | 公开 | 说明 |
|---|---|---|---|
| `DispatchRecord` | `seq:int`；`t_min:float:min`；`frontier_id:int`；`slot_key`；`kind:"TARGET"\|"RETURN"`；`target_id:int\|None`；`action_index:int`（该前沿动作表里的下标）；`observation_sha256:str` | ✅ | 只记录**已执行**的决定；不记录被比较过的候选 |
| `CompletionRecord` | `seq:int`；`t_min:min`；`slot_key`；`kind:str`；`target_id:int\|None`；`x_m,y_m:m`；`trip_energy:能量`；`duty_min:min`；`terminal_failure:str\|None`；`horizon_truncated:bool`；`source_event_seq:int` | ✅ | `kind ∈ {ARRIVE_TARGET, SERVICE_END, RETURN_END, FLIGHT_FAIL, SERVICE_FAIL, RETURN_FAIL, DUTY_LIMIT, FLIGHT_HORIZON, RETURN_HORIZON, SERVICE_HORIZON}`（`emergency_scenario.py:629-675`） |
| `StandbyRecord` | `seq:int`；`t_min:min`；`slot_key`；`reason ∈ {NO_LEGAL_TARGET, ALL_RESERVED, TERMINAL, HORIZON}` | ✅ | **不是动作**，不进 `n_decisions` |
| `PublicationRecord` | `version:int`；`publication_t_min:min`；`valid_from_min:min`；`valid_to_min:min`；`lead_min:min`；`payload:ForecastPayload`；`content_sha256:str`；`error_model_id:str`；`model_id:str` | ✅（发布后） | 只增不改（§5.3） |
| `AlarmRecord` | `target_id:int`；`released_at_min:min`；`deadline_min:min`；`priority:int`；`cls:"EMERGENCY"`；`source:"FAULT"\|"BACKGROUND"` | ✅（发布后） | 告警把 `ROUTINE` 目标升级为紧急并写入期限（§5.6） |
| `ForecastPayload` | `wind_blocks:tuple[(start_min,end_min,wx,wy),...]`；`gust_bound_m_per_min:float`；`confidence:float`；`nfz:tuple[NfzForecastRow,...]` | ✅ | `wx,wy` 为 m/min；块长默认 5 min |
| `PendingDecision` | `frontier_id:int`；`t_min:min`；`slot_key`；`order_index:int` | ✅ | 中途分叉的凭据（§4.5） |
| `MetricLedger` | `served_at:tuple[(int,float),...]`；`returned_at:tuple[(int,float),...]`；`slot_duty_min:tuple[(SlotKey,float),...]`；`slot_operating_min`；`trips_closed:tuple[(SlotKey,int),...]`；`incurred_cost:float`；`failure_codes:tuple[(SlotKey,str),...]`；`n_decisions:int`；`wall_s:float`；`policy_ms_p50,p99:float` | 派生 | `wall_s` 与 `policy_ms` 只入审计，不入策略输入 |

### 2.5 `Particle`（模型样本，**不公开**）

| 字段 | 类型 | 单位 | 时间基准 | 公开 | 说明 |
|---|---|---|---|---|---|
| `particle_id` | `str` | — | — | ❌ | `sha256(model_id, seed, index)` |
| `model_id` / `model_sha256` | `str` | — | — | ❌ | 冻结模型身份（§3.1） |
| `seed` | `int` | — | — | ❌（登记在 `prefix.crn`） | 抽样种子 |
| `weight` | `float` | — | — | ❌ | 条件权重；**不得**作为策略特征 |
| `hidden_past` | `HiddenPast` | — | `[0, t_fork]` | ❌ | 风史 + 阶段日志（§3.5） |
| `hidden_present` | `tuple[HiddenSlotState,...]` | — | `t_fork` | ❌ | 每 slot 的隐藏当前相位 |
| `future` | `ExogenousFuture` | — | `(t_fork, horizon]` | ❌ | 未来外生流 |

**`HiddenPast`**：`wind_history:tuple[WeatherBlock,...]`（覆盖 `[0,t_fork]`，块长 1 min 或 5 min，与模型一致）+ `phase_log:tuple[PhaseSpan,...]`。
**`PhaseSpan`**：`slot_key`；`kind ∈ {AT_STATION, FLIGHT_TO_TARGET, SERVICE, FLIGHT_RETURN}`；`start_min,end_min`；`target_id:int|None`；`from_xy,to_xy:(float,float)`；`energy_delta:float`；`duty_delta_min:float`。

**`HiddenSlotState`**：`slot_key`；`phase:str`（同上四类）；`phase_start_min:min`；`position_xy:(float,float)`；`trip_energy:能量`；`duty_min:min`；`remaining_service_min:min`；`progress:float∈[0,1]`；`energy_consumed_in_phase:能量`；`next_phase_end_min:float|None`（`AT_STATION` 为 `None`）。

**`ExogenousFuture`**

| 字段 | 类型 | 单位 | 时间基准 | 说明 |
|---|---|---|---|---|
| `weather` | `tuple[WeatherBlock,...]` | m/min | `(t_fork,H]` | 真值风；只进物理推进 |
| `forecast_sequence` | `tuple[PublicationRecord,...]` | — | 发布时刻 | 与 `weather` **联合抽样**；进策略视野只经 `publications` |
| `fault_alarms` | `tuple[AlarmRecord,...]` | — | 释放时刻 | 由 `PublicFaultLaw.sample_future` 生成（`public_fault_law.py:191-232`），一个共享粒子 |
| `background_requests` | `tuple[TargetSpec,...]` | — | `release_min` | 背景 Poisson 请求；`release_min ≥ t_fork` |
| `nfz` | `tuple[NfzState,...]` | m, m/min | 时间片 | 移动椭圆；半开区间（`weather_oracle` 语义） |
| `gusts` | `tuple[(start_min,end_min,dx,dy),...]` | m/min | — | 隐藏阵风，只进真值风 |

**`WeatherBlock`**：`start_min,end_min:min`；`wx,wy:float`（m/min）；`gust:bool`。
**`NfzState`**：`start_min,end_min`；`cx,cy`（m）；`vx,vy`（m/min）；`rx,ry`（m）；`theta`（rad）；内部为不可入区（半开）。

> **硬性**：`Particle` 的构造输入只能是 `(StaticContext, PublicPrefix, FrozenParticleModel, seed)`。任何接受 `Scenario/Trace/events/_Drone` 的构造函数都是违规（§3.8）。

### 2.6 `Branch` 与 `EngineState`

| 字段 | 类型 | 公开 | 说明 |
|---|---|---|---|
| `branch_id` | `str` | ❌ | `sha256(prefix_id, particle_id, config_hash)` |
| `static` | `StaticContext` | ✅ | 只读引用 |
| `prefix` | `PublicPrefix` | ✅ | 只读引用（不可变） |
| `particle` | `Particle` | ❌ | 只读引用 |
| `config` | `EngineConfig` | ✅ | 冻结超参（下表） |
| `state` | `EngineState` | ❌ | 可变执行态 |
| `consumed` | `bool` | — | 只能执行一次（§4.8） |

**`EngineConfig`（冻结，改变即新身份）**：`mode`；`horizon_min`；`decision_order="(station_id,slot_index)_asc"`；`publication_wakes_standby=False`；`allow_inflight_interrupt=False`；`duty_policy="station_kind"`；`mask_policy="physics_necessary_with_wind_bound"`；`standby_policy="advance_no_decision"`；`terminal_priority`（§7.4）；`cost_ledger`；`wind_physics:bool`；`max_decisions:int`；`wall_deadline_s:float`。

**`EngineState`**：`now_min:float`；`frontier_id:int`；`slots:tuple[SlotState,...]`；`targets:dict[int,TargetRuntime]`；`events:list[Event]`（`(t_min, order, seq, slot_key, kind, payload)`，按 `(t_min, order, seq)` 排序，`order` = slot 的冻结序）；`pending:tuple[SlotKey,...]`；`metrics:MetricLedger`；`seq:int`；`terminal:str|None`；`standby_reasons:dict[SlotKey,str]`。

**`SlotState`**：`slot_key`；`x_m,y_m`；`at_station:bool`；`trip_energy`；`duty_min`；`trip_started:bool`；`trip_target_ids`；`served_trip_ids`；`terminal_failure:str|None`；`last_return_min:float`；`hidden_phase:str|None`（分支内部用，永不入 `ObservationFrame`）。

**`TargetRuntime`**：`target_id`；`status:str`；`served_at:float|None`；`returned_at:float|None`；`reserved_by:SlotKey|None`；`alarm:AlarmRecord|None`；`deadline_min:float`（告警可改写）；`priority:int`。

### 2.7 公开性矩阵（谁看得见什么）

| 对象 | 策略 μ | 环境引擎 | 独立回放 | 落盘 |
|---|---|---|---|---|
| `StaticContext` | ✅（只读） | ✅ | ✅ | ✅ |
| `ObservationFrame` | ✅（唯一输入） | 产出 | 可选 | ✅（每前沿 1 帧或哈希） |
| `PublicPrefix` | ❌（策略只见帧） | ✅ | ✅ | ✅ |
| `Particle` | ❌ **类型级禁止** | ✅ | ❌（回放只吃动作日志+真值） | 只存 `particle_id/model/sha/seed` |
| `Branch/EngineState` | ❌ | ✅ | ❌ | 只存终局 receipt |
| 真值 `Scenario/Trace` | ❌ | ❌（只在测试夹具里作为“被替换的未来”） | ✅ | 封存 |

### 2.8 fail-closed 校验清单（加载即检查）

`A-01` 时间有限、非负、单调；`A-02` 所有 `slot_key` 属于 `static.slots`；`A-03` `target.station_id` 属于 `static.stations` 且 kind≠0；`A-04` `duty_limit_min/radius_m` 与所属站逐位一致；`A-05` `station.service_min==0`；`A-06` `anchor.station_types` 与实例一致且 `anchor_eligible=True`；`A-07` 任何 float 为 NaN/Inf 直接拒绝（`scorer.py:22,80-84`）；`A-08` `bool` 不得冒充 `int`（`test_g1.py:211-217` 的类型洁癖）；`A-09` 记录 `seq` 唯一递增；`A-10` `publication.version` 严格递增且 `content_sha256` 不可变；`A-11` `reservations` 与 `targets.status` 一致；`A-12` `prefix.ledger_sha256` 与重算一致；`A-13` `∀ t ∈ frame.released_targets: t.release_min ≤ frame.t_min`。

---

## 3. 粒子采样协议

### 3.1 模型冻结与拟合边界

| 项 | 规则 |
|---|---|
| 训练数据 | **只用独立 TRAIN**（`SPLITS_AND_EXCLUSIONS.json` 中 `partition=TRAIN` 的图/日）；不得用 VAL/DEV/FORMAL、不得用已暴露的旧 12 图与 40 身份 |
| 冻结物 | `model_id`、`model_sha256`、参数字典、拟合脚本哈希、拟合数据清单哈希；写入 `StaticContext.freeze_hashes` |
| 拟合对象 | ① 服务时长乘子 `κ` 的分布（每机型、每站型）；② 风史桥接的 OU 参数 `(θ,σ)` 与边界反射规则；③ 预报误差模型 `(bias,σ_e,AR1)`；④ 阵风频率/幅度；⑤ 背景请求强度 `λ`（若沿用 PROTOCOL 的 `Poisson(n/3)` 则登记为固定值而非拟合值） |
| 禁止 | 用 DEV 调参；用真实 `Trace` 拟合；用同一张图既拟合又评估；把粒子权重当特征 |
| 版本纪律 | 改任何参数 = 新 `model_id` + 新身份；旧结果不因新模型重算 |

### 3.2 相容性条件（粒子必须满足，逐条可断言）

| 编号 | 条件 | 检查方式 |
|---|---|---|
| `C1` 位置 | 由 `hidden_present` 反推的 `t_fork` 位置 = 记录位置 | `‖Δ‖ ≤ 1e-9 m` |
| `C2` 能量 | `trip_energy` 与“飞行耗能 + 已服务比例耗能”一致 | `abs(Δ) ≤ 1e-12`（能量单位） |
| `C3` duty | `duty_min` = 已记录 duty（跨趟累计，不受 RETURN 影响） | `abs(Δ) ≤ 1e-12 min` |
| `C4` 完成记录 | 用 `wind_history` 重放已完成的相位，得到的完成时刻与 `CompletionRecord.t_min` 逐条相等 | `abs(Δt) ≤ 1e-9 min` |
| `C5` 生存 | 未完成相位在 `t_fork` 之前**没有**产生完成事件（否则前缀会记录） | 相位终点 `> t_fork` |
| `C6` 一致 | `hidden_present` 的阶段类型与最后一次 `DispatchRecord` 相容（未派遣 ⇒ `AT_STATION`） | 状态机检查 |

不满足任一条 ⇒ 该粒子**不可用**；采样器必须重抽（§3.8），不得“就近修正”。

### 3.3 关于可识别性的硬事实（决定必须有两种假设）

`[已证实-代码]` `emergency_scenario.py:400-409`：服务期能量按 `elapsed/duration` 比例累积。于是：

- 若 `target.energy > 0`：`trip_energy` 的飞行部分可由公开几何算出，剩余部分除以 `energy` 即得**服务进度**（在给定风史下唯一）。
- 若 `target.energy == 0`：能量不携带任何进度信息 ⇒ **alias 成立**：同一公共快照对应不同剩余服务（附录 §2 的解析见证：同一 `(6,0)`、`duty=6`、`trip_energy=3/4`，剩余服务 1 min vs 3 min）。
- 因此：**唯一精确剩余服务不可声称**（`T3`）；任何“保守 ready 上界当真实 ready”的写法都是违规（`CAUSAL_ROLLOUT_APPENDIX §3-1`）。

### 3.4 假设 H1：确定性边界（点质量，仅在可识别时合法）

```python
def sample_hidden_H1(static, prefix, frame, slot, rng, model) -> HiddenSlotState:
    """H1: persisted-wind + energy-pinned progress. Point mass. Raises when not identifiable."""
    view = lookup_slot_view(frame, slot)
    if view.at_station:
        return ready_state(view)                                  # phase=AT_STATION
    rec = last_dispatch(prefix, slot)                             # DispatchRecord
    tgt = static.targets[rec.target_id]
    t_fly = leg_time(rec.origin_xy, tgt.xy, rec.t_min, frame.wind_now, static.params)
    t_arr = rec.t_min + t_fly
    if t_arr > frame.t_min + 1e-12:                               # 仍在飞
        frac = (frame.t_min - rec.t_min) / t_fly
        return HiddenSlotState(phase="FLIGHT_TO_TARGET", progress=frac,
                               position_xy=lerp(rec.origin_xy, tgt.xy, frac),
                               trip_energy=t_fly * frac * static.params.flight_power,
                               duty_min=view.duty_min, remaining_service_min=tgt.service_min,
                               next_phase_end_min=t_arr)
    if tgt.energy <= 0.0:                                         # alias 区：不可识别
        raise PhaseNotIdentifiable("service_energy_zero: H1 invalid, use H2")
    e_service = view.trip_energy - t_fly * static.params.flight_power
    progress = clamp(e_service / tgt.energy, 0.0, 1.0)
    if abs(e_service - progress * tgt.energy) > 1e-9:              # 能量与假设矛盾
        raise ParticleIncompatible("H1 energy residual")
    return HiddenSlotState(phase="SERVICE", progress=progress,
                           position_xy=tgt.xy, trip_energy=view.trip_energy,
                           duty_min=view.duty_min,
                           remaining_service_min=(1.0 - progress) * tgt.service_min,
                           next_phase_end_min=frame.t_min + (1.0 - progress) * tgt.service_min)
```

**用途**：仅作 `C1–C6` 的**下界假设**与单元测试夹具；**不得**作为主协议，因为 ① 它假定“当前风持续”这一非真实历史；② 在 `energy==0` 目标上不存在；③ 会系统性把隐藏阶段压成点质量（`T3` 不允许）。

### 3.5 假设 H2：阶段混合 + 风史桥接（主协议）

```python
def sample_hidden_H2(static, prefix, frame, rng, model, *, max_tries=64):
    """H2: joint (wind-history, per-slot phase) conditional sample.

    One shared wind history keeps slot phases correlated (same storm day).
    Per-slot phase is drawn from the exact conditional support implied by the
    public ledger; a rejection loop enforces C1-C6. Failure is explicit.
    """
    for attempt in range(max_tries):
        # (1) 一条共享风史：OU 桥接，锚定在“公共的风观测”与“已发布预报”上
        w_hist = ou_bridge(model.wind,
                           t0=0.0, t1=prefix.t_fork_min,
                           anchors=public_wind_observations(prefix),   # 回调处的 wind_now
                           pubs=prefix.publications,                   # 只用到 publication_t<=t
                           rng=rng)
        states, ok = {}, True
        for slot in static.slots:                                   # 冻结顺序
            view = lookup_slot_view(frame, slot)
            if view.at_station:
                states[slot] = ready_state(view); continue
            rec = last_dispatch(prefix, slot)
            # (2) 由公共数据导出的支持区间（不得用“当前风”）
            s_lo, s_hi = remaining_service_support(rec, view, w_hist, static)
            #   elapsed_lo = max(0, duty_now - duty_at_dispatch - t_fly_hi)
            #   elapsed_hi = max(0, duty_now - duty_at_dispatch - t_fly_lo)
            #   s_lo = max(0, service - elapsed_hi); s_hi = max(0, service - elapsed_lo)
            if s_hi <= 1e-12:
                ok = False; break                                   # 相位应已结束 -> 前缀矛盾
            # (3) TRAIN 拟合的 kappa 先验，截断到支持区间，等距网格 K 点
            grid = linspace(s_lo, s_hi, model.K)                    # K=17
            w = truncated_kappa_pmf(model.kappa, grid, rec, view, static)
            s_rem = inverse_cdf(grid, w, rng.random())
            # (4) 由 s_rem 反推风史必须满足的飞行耗时，并检查 C1/C2/C3
            st = reconstruct_phase(rec, view, w_hist, s_rem, static)
            if not consistent(st, view, static):                    # C1-C3
                ok = False; break
            states[slot] = st
        if ok and reproduces_completions(prefix, w_hist, states, static):   # C4, C5
            return tuple(states[s] for s in static.slots), w_hist
    raise ParticleIncompatible("no compatible hidden state in %d tries" % max_tries)
```

**支持区间的推导（必须按此写，不得用“当前风”）**：

```text
t_disp        = rec.t_min
d             = dist(origin, target)
t_fly_lo      = d / (airspeed + wind_bound)      # 最快
t_fly_hi      = d / (airspeed - wind_bound)      # 最慢（要求 wind_bound < 0.95*airspeed）
elapsed_lo    = max(0, view.duty_min - rec.duty_at_dispatch - t_fly_hi)
elapsed_hi    = max(0, view.duty_min - rec.duty_at_dispatch - t_fly_lo)
s_lo          = max(0, service - elapsed_hi)
s_hi          = max(0, service - elapsed_lo)
```

这与 `public_phase.py:64-71` 的“服务已耗时下界”同构，但把“当前风上界”换成冻结的 `wind_bound_m_per_min`，从而**不依赖**当前观测（避免把观测当历史）。

### 3.6 假设 H3：完整公共风史重放（条件可用，当前不满足）

若（且仅若）公共接口逐分钟记录风，且**所有方法共享**同一记录，则粒子在风上退化为点质量，只需抽 `s_rem`：

```python
def sample_hidden_H3(static, prefix, frame, rng, model):
    require(prefix.public_wind_ledger_coverage == "1min_full")     # 当前不存在 -> 直接拒绝
    require(prefix.shared_with_all_methods is True)
    w_hist = prefix.public_wind_ledger                                  # 不抽，直接重放
    ...  # 之后同 H2 的 (2)-(4)
```

`[已证实-代码]` 现状不具备该记录：`fast_public_history.py:9` 只保存“派遣前 DroneView、派遣时风、服务和返航时刻”，`CAUSAL_ROLLOUT_APPENDIX §1` 已判定“回调出现的风不足以重建所有过去运动阶段”。**本合同默认 H2**；H3 作为条件分支保留，启用前必须先补公共风账本并重跑 T1/T3。

### 3.7 未来外生流采样（与隐藏过去**联合**）

```python
def sample_particle(static, prefix, *, seed, fault_model, model) -> Particle:
    rng = Random(seed)
    hidden = sample_hidden_H2(static, prefix, last_frame(prefix), rng, model)
    truth  = ou_path(model.wind, prefix.t_fork_min, static.horizon_min, rng)
    truth  = add_gusts(truth, model.gust, rng)
    pubs   = [publish(truth, t, model, rng) for t in model.publication_schedule
              if prefix.t_fork_min < t <= static.horizon_min]
    alarms = fault_model.sample_future(alarm_prefix(prefix), rng.randrange(2**63),
                                       horizon=static.horizon_min)      # public_fault_law.py:191
    bg     = poisson_requests(model.background, prefix, rng)             # release >= t_fork
    nfz    = nfz_path(model.nfz, prefix.t_fork_min, static.horizon_min, rng)
    return Particle(particle_id=..., model_id=model.model_id, seed=seed, weight=1.0,
                    hidden_past=..., hidden_present=hidden, future=ExogenousFuture(...))
```

要点：① 真值与预报**联合**抽样（`publish()` 是 `truth` 窗口加独立噪声），因此“预报含未来信息”在构造上不可能越界（策略看不到 `truth`）；② 预报序列只保留 `publication_t_min > t_fork` 的未来发布，历史发布在 `prefix.publications`；③ 告警用**同一个共享粒子**抽整组（`public_fault_law.py:199-208`），保目标间相关性；④ 背景请求的 `release_min` 必须 `≥ t_fork`，否则视为重采过去（违规）。

### 3.8 采样器接口与拒绝语义

```python
class FrozenParticleModel:
    @classmethod
    def load(cls, path: Path) -> "FrozenParticleModel": ...        # 校验 model_sha256
    def sample(self, static, prefix, *, seed, n_particles,
               fault_model) -> tuple[Particle, ...]: ...
    def check_compatible(self, prefix, particle) -> tuple[bool, str]: ...   # C1-C6

class ParticleIncompatible(ValueError): ...        # 零支持：显式失败，禁止均匀回退
class PhaseNotIdentifiable(ValueError): ...        # H1 在 alias 区被调用
```

**拒绝语义**：`max_tries` 用尽 ⇒ 抛 `ParticleIncompatible`，该 `(prefix, seed)` 行**落盘为失败**并计入分母（§7.5）；禁止“退回 prior”“退回 H1”“放宽区间”三种静默修补。

**禁止事项（逐条可静态检查）**：

1. `Particle` 构造函数只接受 `(StaticContext, PublicPrefix, FrozenParticleModel, seed)`；不许接受 `Scenario/Trace/events/_Drone`（`grep` 断言）。
2. 不许把粒子、`phase`、`remaining_service_min`、`progress`、`weight` 放进 `ObservationFrame`（`T2-A5` 白名单）。
3. 不许把 `particle.future` 的任何字段写入 `prefix.publications`／`prefix.alarms` 的**未发布**时刻。
4. 不许在采样器内读取 `static.anchor`（锚点不参与粒子）。

---

## 4. 事件序（同刻闭包 → 固定顺序决策 → reservation → 回调）

### 4.1 事件类型

| 事件 | 触发者 | 是否产生决策 | 说明 |
|---|---|---|---|
| `TASK_RELEASE` | 外生（粒子） | ✅ 唤醒该站待命 slot | `emergency_scenario.py:719-734` 同构 |
| `ARRIVE_TARGET` | 内部（派遣时预定） | ❌ | 到达即启动服务（`:648-654`） |
| `SERVICE_END` | 内部 | ✅ | `:655-661` |
| `RETURN_END` | 内部 | ✅ | `:662-674` |
| `FLIGHT_FAIL` / `SERVICE_FAIL` / `RETURN_FAIL` | 内部 | ❌（终局） | `:629-644` |
| `DUTY_LIMIT` | 内部 | ❌（终局） | `:645-647` |
| `*_HORIZON` | 内部 | ❌（截断） | `:636-640`，**不是成功** |
| `PUBLICATION` | 外生 | ❌（冻结：不唤醒） | §5.4 |
| `NFZ_BOUNDARY` | 外生 | ❌ | 只改可行域（由回放判定） |

### 4.2 闭包规则

1. 取下一个事件时刻 `t*`，把时钟推进到 `t*`（先把**所有**已排相位累积到 `t*`，`emergency_scenario.py:340-357`）。
2. **所有** `t_min == t*` 的事件必须先全部处理完，才允许出现新的决策前沿（`:694-698`）。
3. 同刻事件排序键：`(t_min, slot_order(slot_key), event_seq)`；`slot_order` 由 `decision_order` 决定，`event_seq` 是入队序号。**不按浮点就近**分组。
4. 处理事件时可能追加同刻新事件（例如 `ARRIVE_TARGET` 触发 0 时长服务的 `SERVICE_END`）；继续闭包直到该时刻队列为空。

### 4.3 决策前沿与固定顺序

```python
def open_frontier(engine):
    engine.pending = tuple(sorted(engine.ready_slots(), key=slot_order))   # 冻结顺序
    engine.frontier_id += 1
```

- `ready_slots()`：`at_station` 且非终局，或刚刚完成回调的 slot。
- 每个 slot 被访问**恰好一次**；访问即从 `pending` 移除（`emergency_scenario.py:703` 的 `decisions.discard`）。
- 所有 slot 在同一前沿看到**同一快照**；唯一允许的例外是 reservation：先决定的 slot 立即占走目标，后决定的 slot 看到它不可用（`:538-539` 置 `IN_FLIGHT` + `reserved_by`）。
- 决策尝试失败（策略抛错/返回非法动作）⇒ `POLICY_CONTRACT_VIOLATION`，**整条 episode 失败**，不转成 WAIT（§6.5）。

### 4.4 派遣即 reservation（不双派）

```python
def apply_physical(engine, slot, action):
    validate_legal(engine, slot, action)                       # §6.2
    if action.kind == "TARGET":
        tgt = engine.targets[action.target_id]
        assert tgt.status == "AVAILABLE"                       # 已被占则非法
        tgt.status, tgt.reserved_by = "IN_FLIGHT", slot         # 立即生效
        engine.slots[slot].trip_target_ids += (tgt.target_id,)
        schedule_phase(engine, slot, "FLIGHT_TO_TARGET", tgt)  # 预定 ARRIVE/SERVICE_END
    else:
        schedule_phase(engine, slot, "FLIGHT_RETURN", None)
    engine.pending = tuple(s for s in engine.pending if s != slot)
    engine.verify_no_double_dispatch()                         # A-11 / T4
```

**不变量 `INV-DD`**：任意时刻 `∀ target: |{slot : target ∈ slot.trip_target_ids ∧ target.status ∈ {IN_FLIGHT, SERVED}}| ≤ 1`。每个派遣后立即断言。

### 4.5 回调与**中途分叉**

前缀可能在“同一时刻有一部分 slot 已决定、另一部分未决定”处被截断（例如 3 slot 同刻，只记录到第 1 个派遣就导出前缀）。此时 `prefix.pending_decisions` 精确记录剩余 slot 及其 `order_index`。

```python
def from_public_prefix(prefix, particle, config) -> CausalEngine:
    e = EngineState.empty(prefix.static, config)
    e.now_min, e.frontier_id = prefix.t_fork_min, prefix.frontier_id
    e.metrics = copy_ledger(prefix.metrics)                    # 过去不重算（§7.2）
    for rec in prefix.dispatches: apply_dispatch_record(e, rec)
    for rec in prefix.completions: apply_completion_record(e, rec)
    e.targets = status_from_prefix(prefix)                     # AVAILABLE/IN_FLIGHT/SERVED/FAILED
    e.reservations = prefix.reservations
    for st in particle.hidden_present:                         # 隐藏当前
        ok, why = check_slot_consistency(prefix, st)           # C1-C6
        if not ok: raise ParticleIncompatible(why)
        e.slots[st.slot_key].load_hidden(st)
        if st.next_phase_end_min is not None:
            e.push(st.next_phase_end_min, st.slot_key, phase_end_event(st))
    for req in particle.future.background_requests:            # 未来请求 -> 释放事件
        if req.release_min <= static.horizon_min:
            e.push(req.release_min, TASK_RELEASE, req)          # 到点才公开（§7.3）
    for alarm in particle.future.fault_alarms:
        if alarm.released_at_min <= static.horizon_min:
            e.push(alarm.released_at_min, TASK_RELEASE, alarm)  # 告警=升级+设期限（§5.6）
    e.pending = tuple(p.slot_key for p in
                      sorted(prefix.pending_decisions, key=lambda p: p.order_index))
    e.consumed = False
    return e
```

**分叉纪律**：

- 已决定的 slot 在 `t_fork` **不得**再次决定：`apply_physical` 若发现该 slot 已在 `t_fork` 有 `DispatchRecord`，抛 `SLOT_ALREADY_DECIDED_AT_FRONTIER`（T4 断言）。
- 已存在的 reservation **不得**释放或重派；分支只能从 `pending` 继续。
- 分支不得回写 `t ≤ t_fork` 的任何记录（§7.2 的 `INV-MONO`）。

### 4.6 环境推进 vs 策略待命

| 情形 | 处理 | 记录 |
|---|---|---|
| 策略有合法动作 | 调用 μ，执行 | `DispatchRecord` |
| **无合法动作**（本站无可用目标 / 全被预约 / 该 slot 终局 / 到 horizon） | **不调用 μ**；slot 进入 standby | `StandbyRecord(reason)` |
| 所有 slot 都在 standby 且无未来事件与释放 | 到 horizon 截断；若 `t < H` 则 `IDLE_DEADLOCK` | 终局码 |
| 环境推进（时钟前进到下一个事件/释放） | 由引擎做，不产生动作 | 仅 `CompletionRecord`/`TASK_RELEASE` |

**“策略待命”在本合同里不存在对应动作**：策略想等，只能等“无合法动作”这一客观状态；有合法动作时必须选一个（§6.3）。

### 4.7 主循环伪码

```python
def run_with_frozen_mu(engine, mu, *, deadline_s, max_decisions) -> RolloutReceipt:
    if engine.consumed: raise BranchAlreadyConsumed()          # 重复 run 不作数
    engine.consumed = True
    # 释放事件在 from_public_prefix 里已按粒子推入事件堆（TASK_RELEASE），
    # 因此主循环只需处理事件堆；堆空且未到 horizon 就是 IDLE_DEADLOCK。
    while True:
        if engine.wall_s() > deadline_s: raise EpisodeTimeout()
        t = engine.next_event_time()
        if t is None:
            engine.publish_until(engine.now_min)               # 记录到期发布（不唤醒）
            engine.terminal = "HORIZON" if engine.at_horizon() else "IDLE_DEADLOCK"
            break
        engine.advance_to(t)                                   # 相位累积，单调
        while engine.events and engine.events[0].t_min == engine.now_min:   # 精确相等
            engine.handle(engine.events.pop(0))                # 追加 pending / 唤醒
        engine.publish_until(engine.now_min)                   # 记录，不唤醒（§5.4）
        if engine.pending:                                     # 闭包后才开前沿
            engine.frontier_id += 1
            for slot in engine.decision_order(engine.pending):  # 冻结顺序的快照
                engine.pending = without(engine.pending, slot)
                if engine.is_terminal(slot): continue
                legal = engine.legal_actions(slot)
                if not legal:
                    engine.record_standby(slot, reason=why_no_action(engine, slot))
                    continue
                frame = engine.observation(slot)               # 不可变 + 哈希
                a = mu(frame)                                  # 策略只见 frame
                if a is None: raise PolicyContractViolation("policy returned None")
                engine.apply_physical(slot, a)
                engine.metrics.n_decisions += 1
                if engine.metrics.n_decisions > max_decisions: raise BudgetExceeded()
        if engine.terminal_condition(): break
    return engine.receipt()
```

**闭包与前沿的顺序不可交换**：先 `advance_to` → 再 `while events[0].t == now` 全部处理 → 再 `publish_until` → 最后开前沿。任何把 `publish_until` 放在闭包之前、或把前沿放在闭包中间的写法，都会让同一时刻的不同 slot 看到不同快照（T4-A6 会抓到这个错误）。

### 4.8 幂等与“重复 run 不作数”

- `Branch.consumed=True` 后再次 `run` ⇒ `BranchAlreadyConsumed`；不得“重跑取更好值”。
- 批量去重键：`(map_id, day_id, particle_id, mu_id, budget_s, config_hash)`。同键第二次出现 ⇒ `DUPLICATE_EPISODE`，不进入分母（但**保留**该行）。
- 复制分支的唯一合法方式：`from_public_prefix(prefix, particle, config)`；**禁止** `copy.deepcopy(engine)` 冒充分叉（会绕过前缀一致性检查）。
- 每个 `DispatchRecord.observation_sha256` 必须能在 `observations` 里找到对应帧；找不到 ⇒ `LEDGER_FRAME_MISMATCH`。

---

## 5. 外生发布语义（预报）

### 5.1 联合生成（先有真值，再有预报）

```python
def publish(truth_blocks, t_pub, model, rng) -> PublicationRecord:
    window = [b for b in truth_blocks if t_pub <= b.start_min < t_pub + model.valid_horizon_min]
    noise  = ar1_ou(len(window), model.error_sigma, model.error_ar1, rng)   # 与真值独立
    payload = ForecastPayload(
        wind_blocks=[(b.start_min, b.end_min, b.wx + n[0], b.wy + n[1])
                     for b, n in zip(window, noise)],
        gust_bound_m_per_min=model.gust_bound,
        confidence=model.confidence,
        nfz=[f.forecast() for f in model.nfz_rows(t_pub)])
    return PublicationRecord(version=model.version_at(t_pub),
                             publication_t_min=t_pub,
                             valid_from_min=t_pub,
                             valid_to_min=t_pub + model.valid_horizon_min,
                             lead_min=0.0, payload=payload,
                             content_sha256=sha256(payload),
                             error_model_id=model.error_id, model_id=model.model_id)
```

**为什么这样不可泄漏**：预报是真值窗口的含噪函数，但当二者都是**同一个联合分布的一次抽样**时，策略要拿到真值必须自己反卷积噪声；噪声流 `rng` 与策略不可达，且 `Particle` 类型级禁止进入策略（§2.7）。`T2` 用“换真值、固定前缀与种子”来实证这一点。

### 5.2 字段与版本

| 字段 | 值 / 规则 |
|---|---|
| `publication_t_min` | `0, 60, 120, …, < horizon_min`（严格每小时，`[设计-冻结]`） |
| `version` | `= publication_t_min / 60`，`int`，严格递增，永不复用 |
| `valid_from_min` | `= publication_t_min`（发布即生效，不提前） |
| `valid_to_min` | `= publication_t_min + valid_horizon_min`，默认 `180.0` |
| `lead_min` | `valid_from - publication`（本版恒 0，留字段给后续“提前发布”变体） |
| `payload.wind_blocks` | 5 min 块，半开区间 `[start,end)`，`m/min` |
| `payload.gust_bound_m_per_min` | 误差包络上界，用于**保守 mask**（不是真值） |
| `payload.nfz` | 移动椭圆预测（中心/速度/半径/朝向/时间片）；真值在 `particle.future.nfz` |
| `content_sha256` | 规范化 JSON 的哈希；`A-10` 断言不可改写 |
| `model_id`/`error_model_id` | 冻结模型身份 |

### 5.3 可见性规则（可执行）

```python
class ForecastBook:
    def visible(self, t_min) -> PublicationRecord | None:
        v = [p for p in self._pubs if p.publication_t_min <= t_min]
        return max(v, key=lambda p: p.version) if v else None
    def assert_no_future_in(self, frame) -> None:
        assert frame.forecast.publication_t_min <= frame.t_min      # T5
```

- 发布前**不可见**：`visible(t)` 严格按 `publication_t_min <= t`；`ObservationFrame.forecast` 只能是 `visible(now)`。
- **不回溯改写**：已发布记录只追加；同 `version` 再次出现即 `PUBLICATION_REWRITE` 失败。
- 过期版本保留在 `prefix.publications`（用于审计与误差统计），但 `frame.forecast` 只指最新可见版本。

### 5.4 发布事件的因果地位（冻结）

**冻结：`publication_wakes_standby = False`。** 理由与后果：

1. 现状模拟器只有“服务完成/返航完成/新任务释放”产生决策前沿（`emergency_scenario.py:655-661,662-674,719-734`）；让发布唤醒等于**改变动作时机**，会把本合同推向已关闭的 `observation-timing/POSMDP` 身份（`CLOSED_DIRECTIONS C25`）。
2. 发布**改变观测内容**（下一个前沿能看到新版本、新 `wind_now` 语境、新 NFZ 预测），因此不是“无作用的摆设”。
3. mask **不**依赖发布（用冻结 `wind_bound_m_per_min`，§6.2），所以发布不会改变合法性、也不需要唤醒。
4. 若上游要“发布即唤醒”，那是**新身份**（§12-D1），必须重跑 T5 并重新登记。

### 5.5 误差模型与登记

- 误差：`AR(1)+OU`，参数 `(bias, sigma, ar1, gust_freq, gust_amp, crosswind_cap)`；`crosswind_cap` 决定“横风不可飞”的触发概率（`reference_environment.py:17-22` 的 `NO_FLY` 分支）。
- 登记：每次发布记录 `error_model_id`；批末报告 `bias / RMSE / 覆盖率（真值落在 gust_bound 内的比例）`，**只作诊断**，不作门槛。
- 风幅分层：沿用 PROTOCOL 的 `0/3/6 m/s` 三档（`0/180/360 m/min`）；`wind_bound_m_per_min` 取该档上界。**合成数据必须标注“合成”**，不得写成 ERA5 验证。

### 5.6 告警与背景请求的发布语义

- **告警**（`source="FAULT"`）：把已存在的 `ROUTINE` 目标升级为 `EMERGENCY`，在 `released_at_min` 写入 `deadline_min = released_at + d`（`d ∈ {15,30}` 按优先级）与 `priority`。**首告警语义**（`[设计-冻结]`，`public_fault_law.py:55-56` 目前**拒绝**重复 crossing，本合同沿用“每目标至多一次”）。
  - 目标已 `SERVED` 时收到告警 ⇒ 记 `ALARM_ON_SERVED`，不计漏服务（写明理由：服务先于告警）。
  - 目标在飞 ⇒ 预约继续；若到达晚于新 `deadline` ⇒ 计 `DEADLINE_FAIL`（迟到量照算）。
  - 目标 `FAILED` ⇒ 告警不可服务，计 `UNSERVED_EMERGENCY`。
- **背景请求**（`source="BACKGROUND"`）：粒子按 `λ` 抽 `(release, station, xy, service, energy, priority, deadline)`；**只在 `release_min` 后**进入 `released_targets`；`release_min > horizon` 的请求记 `BEYOND_HORIZON`，**既不算服务也不算漏服务**（`public_fault_law.py:94-97,227-231` 的同款分列）。

---

## 6. 动作

### 6.1 动作对象

```python
@dataclass(frozen=True)
class Action:
    kind: str                 # "TARGET" | "RETURN"
    target_id: int | None     # TARGET 必填；RETURN 必为 None
```

**没有** `WAIT`、`DIVERT`、`SKIP_NEXT`、`HOLD`、`REPLAN`、算子/邻域/预算字段。`Action("WAIT")` 在构造期即 `ValueError`（不是运行期降级）。

### 6.2 合法性

**S 模式**（与 `global_env.py:78-98` 逐条一致，`[已证实-代码]`）：

```text
(slot,target) 合法 ⇔ 1 slot ∈ slots
                   2 target ∈ remaining ∧ target.station_id == slot.station_id
                   3 dist(station,target) ≤ radius + 1e-7
                   4 trip_energy + travel*flight_power + target.energy + back*flight_power ≤ capacity + 1e-7
                   5 cumulative_duty + trip_elapsed + travel + target.service + back ≤ duty_limit + 1e-7
(slot,RETURN) 合法 ⇔ 1 slot ∈ slots ∧ 2 本趟非空 ∧ 3 回程能量与 duty 满足（:100-106）
```

**W 模式**（同一结构，把 `travel/back` 换成“在 `wind_bound_m_per_min` 下最慢地速”的保守耗时；能量用最慢地速的耗能）：

```text
travel_bound(x,y) = dist(x,y) / (airspeed - wind_bound)      # 要求 wind_bound < 0.95*airspeed
```

- 该 mask 是**必要**而非充分（`global_env.py:351` 的 `necessary_mask_is_completion_certificate=False` 精神）；终局合法性由独立回放裁决（§7.5）。
- **所有方法共享同一 mask**（PROTOCOL “所有方法共用保守可行 mask”），候选池、生成开销、验证开销同给。
- mask **不读** `particle`、不读 `forecast.payload`（只读冻结的 `wind_bound`），因此发布不改变合法性。

### 6.3 无合法动作：两件事必须分开

| | 定义 | 记录 | 计分 |
|---|---|---|---|
| **环境推进** | 引擎内部：时钟前进到下一个事件/释放/发布 | `CompletionRecord`/`TASK_RELEASE`/`PUBLICATION` | 无 |
| **策略待命** | slot 无合法动作，**不调用策略** | `StandbyRecord(reason)` | 不计为动作、不计为成本、不计为服务 |
| **策略等待（非法）** | 策略在有合法动作时想“等” | — | **不存在**；返回 `WAIT`/`None` ⇒ `POLICY_CONTRACT_VIOLATION` |

### 6.4 明确不新增的动作

- 不新增 `WAIT`：历史 WX-E pilot 的 `WAIT_5MIN` 是**隔离版本**，不是普遍许可（`CLAUDE_TAKEOVER_PROMPT §3.1`；`CLOSED_DIRECTIONS C27-C32`）。
- 不新增 `DIVERT`/跨站改降：`WX-C` 的 `DIVERT` 改变“回本站”规则，已 `CLOSE_WX_C_CANDIDATE`（`C33`）。
- 不新增 in-flight 中断/改派：`allow_inflight_interrupt=False`。
- 不新增“跳过目标”：未服务只能由失败/截断产生，不能由策略主动放弃。

### 6.5 违反处置

| 违规 | 结果 |
|---|---|
| 非法 `(slot,target)`（越界/已占/超能量/超 duty） | `POLICY_CONTRACT_VIOLATION`，整条 episode 失败（不静默丢弃该动作） |
| 返回 `None` / `WAIT` / 非 `Action` | 同上 |
| 在已决定的同一前沿再次决定 | `SLOT_ALREADY_DECIDED_AT_FRONTIER` |
| 在 `t < t_fork` 追加记录 | `HISTORY_REWRITE`（`INV-MONO`） |
| 二次 `run` | `BranchAlreadyConsumed` |

全部落盘为 `ERROR` 行，保留在分母（§7.5），不得剔除。

---

## 7. 账本与终局分母

### 7.1 四本账（彼此不可替代）

| 账 | 内容 | 何时写 | 谁能读 |
|---|---|---|---|
| **公共账** `PublicPrefix` | 观测帧、派遣、完成、待命、发布、告警、预约 | 每次前沿/事件 | 所有方法（经帧） |
| **执行账** `EngineState` | slot 物理态、事件堆、隐藏相位 | 分支内 | 仅引擎 |
| **指标账** `MetricLedger` | 服务/返航时刻、duty、运行分钟、成本、失败码、决策数、墙钟 | 单调追加 | 审计 |
| **审计账** `AuditResult` | 独立回放结果、分母、失败分类 | 执行之后 | 报告 |

### 7.2 过去不重采（`INV-MONO`）

- 分支初始化时 `metrics ← copy(prefix.metrics)`，**不重算**；`t ≤ t_fork` 的记录逐字复制。
- 分支只能追加 `t_min ≥ t_fork` 的记录；`t_min == t_fork` 只允许**尚未决定**的 slot 的派遣（§4.5）。
- 断言：`∀ new_rec: new_rec.seq > max(prefix.seq)` 且 `new_rec.t_min ≥ t_fork`。
- 因此“重跑一次拿到更低成本”在结构上不可能：成本是累加的，不是重算的。

### 7.3 未释放任务

- `released_targets` 只含 `release_min ≤ now` 的目标（`A-13`）。
- 未来任务只能来自 `particle.future.background_requests` / `fault_alarms`；未到 `release_min` 的请求**不出现**在任何帧里（T2 的 `obs_hash` 序列断言）。
- `release_min > horizon` ⇒ `BEYOND_HORIZON`，既不服务也不漏服务，单列计数。

### 7.4 终局状态机（优先级从上到下，先命中先定）

| 序 | 终局码 | 触发 | 计分 |
|---|---|---|---|
| 1 | `POLICY_CONTRACT_VIOLATION` | §6.5 | episode 失败；`complete=False` |
| 2 | `NO_ONTIME_VALID_OUTPUT` | 墙钟超时（6 s/12 s 或批次预算） | 失败保留；**不得**用部分结果替代 |
| 3 | `CRASH_FLIGHT_ENERGY` / `CRASH_NO_FLY` / `CRASH_RETURN_FAIL` | `FLIGHT_FAIL`/`RETURN_FAIL` | 该 slot 终局失败；不重启 |
| 4 | `CRASH_SERVICE_ENERGY` | `SERVICE_FAIL` | 同上 |
| 5 | `DUTY_LIMIT` | `duty > duty_limit` | 同上（S 模式 → `issues` + 不可行） |
| 6 | `NFZ_INTRUSION` | 独立回放发现轨迹穿椭圆内部 | episode 失败 |
| 7 | `NO_RETURN` | 有 slot 不在站 | 失败；`makespan=None` |
| 8 | `UNSERVED_EMERGENCY` / `UNSERVED_ROUTINE` | 有目标非 `SERVED` | 漏服务计数 |
| 9 | `DEADLINE_FAIL`（标记，不改第 8 行） | 迟到 | `late_by` 计入 |
| 10 | `TRUNCATED_AT_HORIZON` | `*_HORIZON` | `complete=False`；未完成目标算未服务 |
| 11 | `IDLE_DEADLOCK` | 全 standby 且无未来事件、`t<H` | `complete=False` |
| 12 | `COMPLETE` | 全服务 + 全返航 + 无失败 | 唯一可计成功 |

**七类具名失败的逐条口径（题面要求，逐条给“计分 + 分母”）**：

| 具名失败 | 终局码 | 计分 | 进哪个分母 |
|---|---|---|---|
| **未服务** | `UNSERVED_EMERGENCY` / `UNSERVED_ROUTINE` | `served=False`；紧急按 `miss` 计罚，routine 计 `routine_missing`；`J_diag` 加 `1000/个` | 该 (map,day,particle) 的 `released` 全集（**含**未服务） |
| **期限失败** | `DEADLINE_FAIL` | `late_by = max(0, served_at - deadline)` 计入 `CVaR90` 与 `miss`；服务仍算 `served` | 同上；迟到量按**全部 released**（未服务按 `H-deadline` 截断） |
| **未返航** | `NO_RETURN` | `complete=False`、`makespan=None`；`bad += 1` | 该图全部启动 episode |
| **坠落/失联** | `CRASH_NO_FLY`（横风不可飞：`ground_speed` 抛 `NO_FLY`）/ `CRASH_RETURN_FAIL` | 该 slot 终局失败，不重启、不复用；`bad += 1` | 同上 |
| **能量耗尽** | `CRASH_FLIGHT_ENERGY` / `CRASH_SERVICE_ENERGY` | 同上；目标记 `FAILED`（不再可用） | 同上 |
| **NFZ 入侵** | `NFZ_INTRUSION` | episode 失败（独立回放判定，**不**由引擎自报）；`bad += 1` | 同上 |
| **超时** | `NO_ONTIME_VALID_OUTPUT` | 无有效输出；已发生的部分账本保留但**不算** done | 意向行/启动行/交付行三列分开报（`TAKEOVER_AUDIT §7-3`） |

### 7.5 计分与分母（S 与 W 分列）

**S 模式**（唯一裁判是 `scorer.py`）：

```python
sol    = {"station_types": [...], "routes": [[[trip, ...], ...], ...]}   # routes[si][slot] = [trip,...]
score  = scorer.score_solution(instance, sol)          # cost / M_return / slot_duty / trips / issues
anchor = scorer.CostAnchor.from_solution(instance, anchor_solution); anchor.verify(instance)
gate   = scorer.validate_candidate(instance, sol, anchor, epsilon=0.0)
# gate["cost_budget"] == (1+0.0)*anchor.cost；cap 判定 = cost - budget <= 1e-7（绝对）
# 可采纳 ⇔ gate["admissible"] == original_feasible ∧ domain_valid ∧ cost_cap_satisfied
```

分母：**启动的图数**。每图一行；超时/失败/不可行都保留，标 `NO_ONTIME_VALID_OUTPUT`；**禁止跨图均值抵消超 cap**（`validate_candidate` 逐图，无聚合接口，`CODE_MAP §C.5`）。

**W 模式**（指标是既有 W 合同，不新造）：

| 指标 | 定义 | 分母 |
|---|---|---|
| `complete_service_rate` | `served / released`（含紧急与背景） | 该 (map,day,particle) 的 `released` |
| `high_priority_on_time` | 高优先 `served_at ≤ deadline` / 高优先 `released` | 同上 |
| `CVaR90(lateness)` | 迟到量最差 10% 的均值；未服务按 `H - deadline` 截断；nearest-rank `ceil(0.9n)-1`（`scorer.py:212-215` 同款） | 全部 `released` |
| `cost_ratio` | `incurred / strongest_nonRL_incurred`（同信息/同预算/同粒子） | 每 (map,day) 一个比值 |
| `wind_clock_cost` | `fixed + time_cost * Σ_slot clock_min`（风积分，`weather_full_map.py:213,294-296` 同式） | — |
| `no_wind_cost` | `fixed + 0.5*Σ duration`（**诊断**，`wind≡0` 时才等于 S 成本） | — |
| `J_diag` | `incurred + 0.5*makespan + miss + 1000*routine_missing + 10000*bad`（`joint_core.py:117-128`） | **仅诊断，非门槛** |

**失败计分铁律**：未服务导致的低成本**不是优势**（`CLAUDE_TAKEOVER_PROMPT §3.3`）；terminal failure / 未完整返航各自计入 `bad`；截断不算成功；NaN 不得进入汇总（`A-07`），失败行先落盘再汇总。

### 7.6 聚合规则

- **独立单位 = 地图**。事件日、粒子、训练 seed 都嵌套在图内，不得展开成 n（`TAKEOVER_AUDIT §7-2`）。
- 每 (map, day) 先在粒子上取均值；再在日上取均值；再跨图做配对 bootstrap（10000 次，地图级）。
- 失败图**保留**：`map_mean` 用“该图所有启动 episode 的均值”，失败按失败码计分，不剔除。
- 三种“行”分开报：意向行 / 实际启动 / 按时交付（`TAKEOVER_AUDIT §7-3`）；`intent` 不得当 `completed`。

---

## 8. T1–T7：<COMPUTE_HOST> 可执行测试

### 8.0 公共装置

**夹具**（合成、手写、不上地图）：`fixtures/f01_1s_2t.json`（1 站 2 目标，S 退化）、`f02_3s_6t.json`（3 站 6 目标，含 DABS）、`f03_alias.json`（附录 §2 的 A/B 双机 + P/Q 双风史）、`f04_publication.json`（发布边界）、`f05_storm_day.json`（1 图 1 日，含告警/背景/NFZ）。

**目录**（远端）：`<EXECUTION_PATH>`；**输出**写 `<EXECUTION_PATH>`（`/` 仅约 10 GB，`BRIEF` 硬约束）。

**运行方式**：`<EXECUTION_PATH> 'cd <EXECUTION_PATH> && /usr/bin/python3 -m tests.run_t1 --fixture fixtures/f02_3s_6t.json --out receipts/T1.json'`；只用标准库（3.10.12）。

**收据 schema**（每个 T 一份 JSON，`allow_nan=False`）：

```json
{"test":"T1","status":"PASS|FAIL|ERROR","n_cases":32,"n_pass":32,
 "assertions":[{"id":"T1-A1","pass":true,"detail":"max|dp|=3.1e-13"}],
 "fixtures":["f02_3s_6t"],"model_id":"...","model_sha256":"...",
 "started_utc":"...","elapsed_s":1.23,"command":"...","host":"<COMPUTE_HOST>",
 "failures":[{"case":"p07","code":"C1_POSITION","detail":"..."}]}
```

---

### T1 状态重建一致性

**目标**：给定完整公共前缀 + 固定粒子，重建的过去位置/能量/duty/服务/返航记录与记录值一致；并证明采样器只产出相容粒子。

**构造**：
1. 用 `f02_3s_6t` 跑一条固定策略（`mu="lpt"`）到 `t_fork ∈ {30, 120, 300}` 三个截断点，每个截断点导出 `PublicPrefix`。
2. 每个截断点用 `FrozenParticleModel.sample(prefix, seed=k, n_particles=32)` 抽 32 个粒子。
3. 对每个粒子，从 0 起用 `hidden_past.wind_history` 重放到 `t_fork`，比较 `C1–C4`。
4. 另抽 1000 个候选粒子，统计拒绝率（应 < 5%）。

**断言**：
- `T1-A1` 位置 `max‖Δ‖ ≤ 1e-9 m`；`T1-A2` 能量 `max abs(Δ) ≤ 1e-12`；`T1-A3` duty `max abs(Δ) ≤ 1e-12 min`；`T1-A4` 完成记录逐条 `abs(Δt) ≤ 1e-9 min` 且条数相等。
- `T1-A5` 32/32 粒子通过；`T1-A6` 拒绝率 < 5%（否则模型过紧，见失败处置）。
- `T1-A7` 用 H1 在 `f03_alias` 的 `energy==0` 目标上**抛** `PhaseNotIdentifiable`（证明可识别性判断正确）。

**通过**：A1–A7 全绿，且 3 个截断点 × 32 粒子 = 96/96。
**失败处置**：关闭该重建实现，保留首个反例 JSON（前缀、粒子、偏差）；若拒绝率 ≥5%，先怀疑支持区间推导（§3.5 公式）而非放宽容差。
**产物**：`receipts/T1.json` + `receipts/T1_cases/`。**预算**：≤ 2 CPU-min。

---

### T2 私有未来替换不变性（信息泄漏检测）

**目标**：固定公共前缀与抽样种子，替换“真实私有未来”后，分支的策略输入与输出**逐位不变**。

**构造**：
1. 用 `f05_storm_day` 生成**两个**私有真值：`truth_A`（风/请求/告警流 A）与 `truth_B`（全部不同）。
2. 两个场景**共享**同一 `PublicPrefix`（同一前缀导出）与同一 `Particle`（同 `seed`）。
3. 分别 `from_public_prefix(prefix, particle, config)` + `run_with_frozen_mu(mu)`；`mu` 用同一个确定性策略（`lpt`，无内部随机）。
4. 比较：`obs_sha256` 序列、`DispatchRecord` 序列、`CompletionRecord` 序列、`RolloutReceipt.terminal`。

**断言**：
- `T2-A1` 两次运行的 `obs_sha256` 列表**完全相等**；`T2-A2` 动作序列完全相等；`T2-A3` 终局码与 `M_return`/`cost` 完全相等。
- `T2-A4` 引擎代码路径上不存在 `truth_A/truth_B` 句柄（静态检查：`grep -n "Scenario\|Trace" env/causal_engine.py` 为空；运行时用 `gc.get_referrers` 断言引擎对象不引用 `Scenario`）。
- `T2-A5` `ObservationFrame` 的字段集合 == §2.3 白名单（多一个字段即失败）。

**通过**：A1–A5 全绿。**这是“无泄漏”的唯一实证**。
**失败处置**：按信息泄漏处理，`G3` 不得进入（`CAUSAL_ROLLOUT_APPENDIX §4-T2`）；定位到具体字段后修 `ObservationFrame` 白名单，再重跑 T1。
**产物**：`receipts/T2.json` + 两份 `receipts/T2_{A,B}/`。**预算**：≤ 2 CPU-min。

---

### T3 alias：多相容隐藏阶段，禁止唯一精确剩余服务

**目标**：同一公共前缀允许 ≥2 个相容隐藏阶段；任何“唯一精确剩余服务”的声明被 API 拒绝。

**构造**：按 `CAUSAL_ROLLOUT_APPENDIX §2` 的解析见证做 `f03_alias.json`（用 `fractions.Fraction` 构造，再转 float 校验恒等式）：

- 站 `(0,0)`；A 在 `t=0` TARGET 到 `(6,0)`；空速 2 m/min；`p=1/8`；服务 4 min；`energy=1/2`；容量 4；duty 上界 20。
- 风史 P：全程无风 ⇒ `t=3` 到达，`t=7` 服务结束，`t=6` 时剩余 1 min。
- 风史 Q：`t∈[0,1)` 无风，`t∈[1,5.5)` 沿程风 `-1`，之后无风 ⇒ `t=5` 到达，`t=9` 结束，`t=6` 时剩余 3 min。
- 两史在 `t=6` 的公共观测：位置 `(6,0)`、`duty=6`、`trip_energy=3/4`、目标未完成、`wind_now=0`。

**断言**：
- `T3-A1` 两条历史重建出的 `SlotView` **逐字段相等**（证明前缀不可区分）。
- `T3-A2` 用 H2 在 `t=6` 抽 10,000 个粒子，`remaining_service_min` 的支持同时覆盖 `1.0` 与 `3.0`（各 ≥1 个样本），且取值落在 `[1.0, 3.0]` 内。
- `T3-A3` `model.recover_exact_phase(prefix, slot)` 在 `energy==0` 目标上抛 `PhaseNotIdentifiable`；在 `energy>0` 目标上返回的进度与解析值差 `≤ 1e-12`。
- `T3-A4` 任何 `ObservationFrame` 不含 `remaining_service_min` / `progress` / `phase` 字段（白名单）。
- `T3-A5` `particle.weight` 不出现在任何特征向量（静态检查 + 运行时断言）。

**通过**：A1–A5 全绿。
**失败处置**：若 A2 失败（支持不覆盖双见证），修条件模型；若 A3 无法拒绝唯一化，则把“隐藏 phase”表述**降级**为“仅在零服务能耗任务上成立”（`CODE_MAP §F.3-8` 的降级条款），并保留反例。
**产物**：`receipts/T3.json`。**预算**：≤ 1 CPU-min。

---

### T4 同刻多机中途分叉：保留 reservation、不双派

**目标**：同刻 3 slot 分叉时，已派遣 slot 不被重派，未决定 slot 保留预约与顺序，任何目标只被一个 slot 持有。

**构造**：
1. `f02_3s_6t` 的 1 个 DABS 站 + 1 个 SABS 站（共 3 slot），在 `t=0` 有 2 个可用目标 + 1 个同刻到期的释放。
2. 用“记录型策略”在第一个 slot 决定后**主动截断**，导出 `prefix`（`pending_decisions` 含剩余 2 个 slot，`order_index=1,2`）。
3. 从该前缀 + 3 个不同粒子各分叉一次，继续跑 `mu`。
4. 再尝试一次“重派已决定 slot”的违规分支。

**断言**：
- `T4-A1` 分叉后剩余 slot 看到的 `released_targets` 中，已被预约目标的 `status == "IN_FLIGHT"`（不可选）。
- `T4-A2` 全账本 `INV-DD` 成立：每目标 `|dispatchers| ≤ 1`。
- `T4-A3` `pending_slots` 与 `order_index` 逐项等于前缀记录。
- `T4-A4` 违规分支抛 `SLOT_ALREADY_DECIDED_AT_FRONTIER`，且**不改**任何记录（失败前后 `ledger_sha256` 相等）。
- `T4-A5` 三路分叉合计派遣数 == 期望值（3），目标互异。
- `T4-A6` 同刻事件闭包：在 `t=0` 插入 0 时长服务（`ARRIVE_TARGET→SERVICE_END` 同刻），断言闭包后 `frontier_id` 只 +1（不产生两个前沿）。

**通过**：A1–A6 全绿。
**失败处置**：修事件/回调次序后**重跑 T1–T4**（T4 是顺序类修复的回归门）。
**产物**：`receipts/T4.json` + 3 份分支收据。**预算**：≤ 2 CPU-min。

---

### T5 预报发布：跨 t=60 生效、发布前不可见

**目标**：`v0@0`、`v1@60` 的发布在 `t=60` 精确切换；发布前不可见；发布内容真的变化（不是常量）。

**构造**：`f04_publication.json`：horizon 240，发布时刻 `{0,60,120,180}`，valid 180；在 `t∈{59.999, 60.0, 60.000001}` 各安排一次回调（通过 0 时长服务或释放事件精确命中）。

**断言**：
- `T5-A1` `t=59.999` 的帧 `forecast.version == 0`；`t=60.0` 与 `60.000001` 的帧 `version == 1`。
- `T5-A2` `publication_t_min <= t_min` 对 10,000 个帧全部成立（扫描断言）。
- `T5-A3` `v1.content_sha256 != v0.content_sha256`，且 `v1.payload.wind_blocks` 的窗口起点 `≥ 60`。
- `T5-A4` 在 `t=60` 查询 `version=2` 返回 `None`；`ForecastBook.visible(59.9)` 不含 `v1`。
- `T5-A5` 改写 `v1` 内容后再 `visible` ⇒ `PUBLICATION_REWRITE`。
- `T5-A6` 对照：**当前** `emergency_scenario.Scenario.forecast`（`emergency_scenario.py:100`，常数二元组）在同一夹具上**无法**通过 A1/A3 —— 该对照行必须显式记录为 `BASELINE_CANNOT_PASS`，用来证明本测试不是自证。

**通过**：A1–A6 全绿（A6 预期为 “baseline cannot pass”）。
**失败处置**：撤回“独立 hourly forecast publication 已实现”的表述（`CAUSAL_ROLLOUT_APPENDIX §4-T5`），在报告里写明缺口仍在。
**产物**：`receipts/T5.json`。**预算**：≤ 1 CPU-min。

---

### T6 RETURN 与失败语义

**目标**：RETURN 只清本趟电池、不清累计 duty；截断与服务能量失败不成为成功。

**构造**：`f01_1s_2t` 与 `f02_3s_6t` 各一组：(a) 两趟各 2 目标，中间 RETURN；(b) 服务能量不足（`energy > 剩余容量`）；(c) 恰好 `t=H` 的完成与 `t=H+ε` 的截断；(d) duty 恰好 `= limit` 与 `= limit + 1e-9`。

**断言**：
- `T6-A1` RETURN 后 `trip_energy == 0.0` 且 `trip_elapsed == 0.0`，而 `cumulative_duty == 之前 + trip_elapsed + back`（只增，`global_env.py:156`）。
- `T6-A2` 第 2 趟后 `duty > limit` ⇒ 终局 `DUTY_LIMIT`，`complete=False`，`bad` 计数 +1。
- `T6-A3` 服务能量失败 ⇒ `CRASH_SERVICE_ENERGY`，`complete=False`；该目标 `status=="FAILED"`。
- `T6-A4` `t=H` 完成可观测（`SERVICE_END`），`t>H` ⇒ `*_HORIZON` 且 `horizon_truncated=True`、`complete=False`。
- `T6-A5` `duty == limit` 合法（`≤ limit + 1e-7`），`limit + 1e-9` 失败；边界方向与 `scorer.py` 一致。
- `T6-A6` 任何“低成本的部分路线”都不得进入 `COMPLETE`（用一条只服务 1/2 目标但成本更低的解做反例）。

**通过**：A1–A6 全绿。**失败处置**：完整失败计分；不得以低成本部分路线获胜（T6 失败即 G3 不可进入）。
**产物**：`receipts/T6.json`。**预算**：≤ 2 CPU-min。

---

### T7 硬截止、异常、零样本：持久化收据 + 独立回放

**目标**：外部截止/异常/零样本都有落盘收据；终局解可被独立回放逐项复算。

**构造**：一批 4 条 episode：① 正常完成；② `mu` 在第 3 次决策抛异常；③ 墙钟预算 `0.001 s`（首决策前超时）；④ 粒子采样连续 `max_tries` 失败（零相容样本）。

**断言**：
- `T7-A1` 4/4 都有行，`status ∈ {DONE, TIMEOUT, ERROR, INTERRUPTED}`，无缺行；行文件在任何汇总之前**已 fsync**。
- `T7-A2` 每行含 `episode_key`、`prefix_id`、`particle_id`、`model_sha256`、`config_hash`、`wall_s`、`budget_s`、`terminal`、`failure_code`。
- `T7-A3` 正常行通过 `independent_full_episode_audit`：从动作日志 + 真值重推 `served_at/returned_at/duty/cost/M_return`，与 `MetricLedger` 逐项相等（相对误差 `≤1e-9`）。
- `T7-A4` 异常行含 traceback 哈希，且**不**产生部分候选分。
- `T7-A5` 零样本行 `status=="ERROR"`，`code=="PARTICLE_INCOMPATIBLE"`，且**不**回退 prior。
- `T7-A6` 超时行 `terminal=="NO_ONTIME_VALID_OUTPUT"`，`incumbent=None`，但保留已发生的部分账本。

**通过**：A1–A6 全绿，且 T1–T6 全绿（T7 是批次门）。
**失败处置**：`G3` 保持未通过；不以候选分数代替完整 episode（`§4-T7`）。
**产物**：`receipts/T7.json` + `receipts/T7_rows/`。**预算**：≤ 2 CPU-min。

---

### 8.8 汇总门

```text
PASS(T*) = 该 T 全部断言为真 ∧ 收据可重算（同一命令重跑得到同 status）
PUBLIC_ROLLOUT_ENGINEERING_READY =
    PASS(T1) ∧ PASS(T2) ∧ PASS(T3) ∧ PASS(T4) ∧ PASS(T5) ∧ PASS(T6) ∧ PASS(T7)
```

`PUBLIC_ROLLOUT_ENGINEERING_READY` **只**表示“公共因果环境与真实 rollout 工程可用”，**不**表示 G0/G3/G4 通过，也不授权训练（`CLAUDE_TAKEOVER_PROMPT §11-B/§11-C`）。

---

## 9. 实现清单

### 9.1 新写模块（远端 `code/env/`）

| # | 模块 | 关键接口 | 依赖 | 估计 |
|---|---|---|---|---|
| 1 | `env/public_prefix.py` | `StaticContext/SlotKey/ObservationFrame/...` dataclasses；`load_static_context(instance_path, *, mode, day_id, anchor_path=None) -> StaticContext`；`canonical_hash(obj) -> str`；`validate_static(ctx)`（A-01..A-13） | `problem.py`、`scorer.py`（只读） | 1.0 人日 |
| 2 | `env/forecast_book.py` | `ForecastBook(schedule, valid_horizon_min, error_model)`；`.visible(t)`、`.publications_until(t)`、`.assert_no_future_in(frame)`；`publish(truth, t, model, rng)` | 无（stdlib） | 0.75 人日 |
| 3 | `env/latent_phase.py` | `FrozenParticleModel.load(path)`、`.sample(static, prefix, seed, n_particles, fault_model)`、`.check_compatible(prefix, particle)`；`sample_hidden_H1/H2/H3`；`PhaseNotIdentifiable`、`ParticleIncompatible` | #1、#2 | 1.5 人日 |
| 4 | `env/exogenous_stream.py` | `ou_path/add_gusts/ar1_ou/poisson_requests/nfz_path`；`ExogenousFuture` 组装；全部以 `rng` 为唯一随机源 | #1 | 1.0 人日 |
| 5 | `env/causal_engine.py` | `CausalEngine.from_public_prefix(prefix, particle, config)`；`.legal_actions(slot)`；`.apply_physical(slot, action)`；`.run_with_frozen_mu(mu, deadline_s, max_decisions)`；`.receipt()`；`.verify_no_double_dispatch()` | #1–#4、`reference_environment.ground_speed`、`emergency_scenario` 的事件**语义**（重写，不 import 其 `run`） | 2.0 人日 |
| 6 | `env/episode_audit.py` | `independent_full_episode_audit(static, prefix, receipt) -> AuditResult`；复算物理/覆盖/返航/duty/成本/NFZ | `shared_replay_v2.flight/Trace`、`emergency_independent_replay` 的写法 | 1.0 人日 |
| 7 | `policies/mu.py` | `make_mu(kind, static, *, budget_s) -> Policy`；`kind ∈ {lpt, joint_minmax, rolling_visible_beam, complete_fleet, n4_rollout}` | `g23/nonrl_baseline/baseline.py`、`complete_fleet.py`、`emergency_rolling_baseline.py` | 0.5 人日 |
| 8 | `tests/{run_t1..run_t7}.py` + `tests/run_all.py` | §8 的断言与收据 | 全部 | 1.5 人日 |
| 9 | `drivers/run_episode.py`、`drivers/run_batch.py` | 单条 episode / 批次（intent 登记、逐行落盘、汇总分离） | 全部 | 0.5 人日 |
| 10 | `receipts/schema.py` | 收据 JSON schema + `fsync` 写入器 + `allow_nan=False` | 无 | 0.25 人日 |

**合计 ≈ 10 人日**（单人）；工程测试 CPU ≤ 15 CPU-min；**0 训练、0 作者求解、0 地图质量评价**。

### 9.2 可复用（**不要重写**）

| 复用件 | 路径 | 用它的哪一部分 |
|---|---|---|
| 评分器 | `code/route_rl_research/20261103/return_makespan/scorer.py` | `score_solution`、`CostAnchor.from_solution`、`validate_candidate(epsilon=0)`、`COST_TOLERANCE` |
| 静态 env（参考语义） | `.../return_makespan/global_env.py` | 5 条/3 条合法性、RETURN 语义、三层 mask 的**语义**（S 模式对账用） |
| 交付记账 | `.../return_makespan/delivery.py` | deadline/raw/fallback 写法 |
| 回归测试基线 | `.../return_makespan/test_g1.py` | 37 项，S 模式退化后必须仍全绿 |
| 风物理 | `20261106_complete_fleet_worker/MODIFIED_FILE/reference_environment.py:11-23` | `ground_speed`（横风不可飞） |
| 事件积分 | `.../shared_replay_v2.py:76-112,115-191` | `flight`、`Trace`、`replay`（`duty_contract` 字符串条款） |
| 独立复算 | `.../emergency_independent_replay.py:42-60` | 不 import 策略/模拟器的标量风积分 |
| 事件闭包/回调语义 | `20261112_wx_e_forecast_v1/src/emergency_scenario.py:340-357,617-745` | **只抄语义，不 import `run`** |
| 公共相位上界 | `.../public_phase.py:54-76` | 服务已耗时下界（改成 `wind_bound` 版本） |
| 公共历史帧 | `.../fast_public_history.py:9-56`、`causal_task_memory.py` | 不可变帧、单调时钟、只记已发生决定 |
| 告警条件化 | `20261112_public_fault_conditioning/MODIFIED_FILE/public_fault_law.py:104-232` | `weights`、`sample_future`（共享粒子）、零支持失败 |
| 完整车队 incumbent | `.../complete_fleet.py:24-85` | 已知任务完整补全（作为 `mu` 之一，**不是**未来 rollout） |
| 掩码动作训练底座 | `.../rl_algorithms.py`、`weather_policy.py` | 仅在 G0/G3 通过后才用 |
| 非 RL 强对照 | `.../g23/nonrl_baseline/baseline.py`、`mtc_nonrl/latency_baseline.py` | `solve(inst, anchor, method, budget_s)` |
| NFZ 单腿 | `.../g24_weather_nfz/weather_oracle.py:290-354` | 点到点最早到达（**不是**多目标路线规划器） |

**明确不复用**：`weather_full_map.py` 的定长 `global_dim=42+9*20+7*128`（大图直接拒绝，`CODE_MAP §E`）；`weather_env.py` 的单机玩具；`wx_e_forecast_driver._forecast_direction`（是“初始先验+当前观测”的线性融合，**不是**发布，`CODE_MAP §G-6`）；`rl_ppo`/`rl_dyn`（违反动作合同）。

### 9.3 目录布局（远端）

```text
<EXECUTION_PATH>
  code/env/{public_prefix,forecast_book,latent_phase,exogenous_stream,causal_engine,episode_audit}.py
  code/policies/mu.py
  code/tests/{run_t1..run_t7,run_all}.py
  code/drivers/{run_episode,run_batch}.py
  fixtures/f0*.json
  receipts/T*.json
<EXECUTION_PATH>    # 大输出（/ 只有 ~10 GB）
```

### 9.4 依赖与预算纪律

- 只用 **标准库**（`math, json, hashlib, dataclasses, random, heapq, fractions, pathlib, time`）；**不得**依赖 pandas/scipy/numpy（远端点 5 已确认不可用）。
- 单条 episode 的 `ObservationFrame` 保留策略：每前沿 1 帧（或只留哈希），避免 D 线 12 GB 事故（`TAKEOVER_AUDIT §4.10`）。
- 每批先估 `字节/轨迹`，设输出硬限（建议 2 GB/批），超限先停并落 `OUTPUT_LIMIT`。

### 9.5 完成定义（本合同的验收）

```text
DONE = 10 个模块可 import ∧ T1–T7 全绿 ∧ S 模式退化对账 test_g1 37/37 全绿
       ∧ 收据可重算 ∧ 0 训练 / 0 作者求解 / 0 地图质量结论
```

---

## 10. 与静态 S 合同的关系

### 10.1 不变量（**一个都不改**）

| 项 | 值 | 本环境是否触碰 |
|---|---|---|
| 逐图成本 cap | `C(candidate) ≤ C(R_Liu) + 1e-7`，`epsilon=0` | ❌ 不改（`scorer.py:269-273`） |
| 墙钟 | 整图 6 s / 12 s，`budget_scope=D_improvement_from_common_ready_input` | ❌ 不改（`delivery.py` 契约） |
| 目标 | `min M_return`（`max_s max_slot Σ duration`） | ❌ 不改（`scorer.py:210`） |
| 辅助指标 | MTC（只辅助） | ❌ 不改 |
| `station_types` / `target_station` | 必须与锚点相同 | ❌ 不改（`scorer.py:271-272`） |
| slot 归属 / 趟划分 / 趟内顺序 | 可变 | ✅ 本环境的动作域正是这三者 |
| W 门槛 | 成本比 bootstrap 95% 上界 ≤ 1.01；CVaR90 | ❌ 不改，且**不**替换 S |

### 10.2 S 模式退化义务（可执行）

`S_STATIC` 下必须同时成立：

1. `wind ≡ 0`、`publications=()`、`alarms=()`、`background_requests=()`、`nfz=()`、`horizon=∞`。
2. 同一动作序列在 `FullMapRouteEnv`（`global_env.py`）与新引擎上产生**逐位相同**的 `cost`、`M_return`、`slot_duty`、`trips`：断言 `==`（不是 `≈`）；若不相等，先查累加顺序，**不得**用容差掩盖。
3. 终局解经 `validate_candidate` 判 `admissible` 的比例、`issues` 集合与旧路径一致。
4. `test_g1.py` 37 项全绿（S 模式回归）。
5. **任何** S 模式的报告只能引用 `scorer.score_solution` 的字段；引擎自己的 `no_wind_cost` 只作对账。

**为什么必须逐位相等**：`M_return` 与 `Check.calculateLatestTime` 同结构（`CODE_MAP §C.2`），而 `cost` 是本项目定义（**不等于** Java `calculateTotalCost`，`CODE_MAP §C.3`）。若新引擎自己算 cost，就会悄悄引入第三套定义——这正是 `CODE_MAP §H-1` 警告的三套 `M_return` 并存问题的翻版。

### 10.3 W 与 S 分列（不得互相包装）

- W 实验的每一行必须带 `mode="W_EVENT_DAY"`；其 `M_return`/`cost` 即使被计算出来，也**不得**用于 S 的 cap 判定或 S 的改善百分比。
- S 实验的每一行必须带 `anchor_cost`、`anchor_M_return`、`cost_minus_cap`、`cost_cap_satisfied`。
- 报告必须分两张表；**禁止**把 W 的高优先准时率写进 S 的“5% 改善”叙事（`CLAUDE_TAKEOVER_PROMPT §3.3`）。

### 10.4 本环境**不是**新机制（防止误读）

- 与 Zhao 式 (6)–(7)、(13)–(14) 与 pp.14–15 的 rollout 相比：同族 rollout，只换转移核内容与终局指标 ⇒ **无独立算法增量**（`PRIOR_ART_EQUATION_AUDIT §C.4-1`）。
- 与 Han (2r)–(2t) 相比：共享容量/准备度已是原式 ⇒ 无增量（`PRIOR_ART_EQUATION_AUDIT §C.4-2`）。
- 因此实现本环境**不解锁** G0；`G0_NO_GO_AS_DISTINCT_ALGORITHM` 保持不变。它只把“真实 rollout 强对照（N4）”从“未执行”变成“可执行”。

### 10.5 冲突与采用版本

| 冲突 | 采用 | 依据 |
|---|---|---|
| `emergency_scenario.Scenario.forecast` 是常数二元组 vs “每小时发布” | 采用 `ForecastBook`；旧字段标记 `NOT_A_FORECAST` | `emergency_scenario.py:100`；`CODE_MAP §G-5` |
| `emergency_scenario` 无 slot/站型 vs Liu 模型 | 新引擎用 `StaticContext.slots`；`emergency_scenario` 只提供事件语义 | `CODE_MAP §E` 判定 |
| `shared_replay_v2` duty 是 report-only vs `scorer` 判不可行 | S 模式以 `scorer` 为准；W 模式 duty 违规 = 终局失败 | `shared_replay_v2.py:190`；`scorer.py:184-186` |
| `Observation` 无服务开始/剩余 | 由粒子补；**不给**策略 | `CAUSAL_ROLLOUT_APPENDIX §1`；`CODE_MAP §F.3-8` |
| `weather_full_map` 定长 20 slot/128 target | 不复用其编码器 | `CODE_MAP §G-4` |
| 两份 `emergency_scenario.py` 不同（duty 向量） | 引用时必须写 hash（`01d243…` worker / `43794a…` forecast_v1） | `CODE_MAP §H-5` |

---

## 11. 一句话风险表

| # | 设计选择 | 最怕什么 | 如何证伪 |
|---|---|---|---|
| R1 | 粒子含隐藏过去 + 未来 | 粒子实际泄漏真值（“抽样”退化为复制） | T2（换真值不变）+ §3.8 构造期参数白名单 |
| R2 | H2 用 `wind_bound` 推支持区间 | 区间过宽 ⇒ 粒子“什么都能解释”，等于没条件化 | T1 拒绝率 <5% + T3 支持覆盖且落在 `[1,3]` |
| R3 | 预报与真值联合抽样 | 预报实为真值的确定性函数（噪声为 0） | T5-A3 内容哈希不同 + 误差统计 `RMSE>0` |
| R4 | 发布不唤醒 | 发布变成无作用摆设，W 的“信息价值”不可测 | 比较“发布可见/不可见”两组的决策差异（后续实验，不在本合同） |
| R5 | mask 用 `wind_bound` 而非真风 | 保守 mask 剪掉可行解 ⇒ 人为制造 dead_end | S 模式退化后与 `global_env` 逐位相等（§10.2） |
| R6 | 同刻精确相等 | 浮点抖动导致同一物理时刻分成两个前沿 | T4-A6；§4.2 排序键 |
| R7 | 派遣即 reservation | 同刻两 slot 抢同一目标（双派） | T4-A2 `INV-DD` |
| R8 | 中途分叉复制前缀 | 分叉时重算历史 ⇒ 过去成本漂移 | `INV-MONO` + T4-A4（失败前后哈希相等） |
| R9 | 无合法动作 = standby | 被实现成 WAIT，偷偷加动作 | §6.3 表 + T2-A5 字段白名单 + 账本里无 `WAIT` |
| R10 | 终局用优先级状态机 | 截断/失败被算成“低成本优秀” | T6-A6 + §7.5 铁律 |
| R11 | 只用标准库 | 远端无 pandas/scipy，实现者偷装依赖 | §9.4；import 白名单静态检查 |
| R12 | 逐位复现 `scorer` | 引入第三套 cost/M_return 定义 | §10.2 的 `==` 断言 + `test_g1` 37 项 |
| R13 | 每前沿只留 1 帧 | 审计时无法重建决策上下文 | 每帧留 `observation_sha256` + 可选抽样存帧（§9.4） |
| R14 | 把本环境当 G0 | 用“工程完成”冒充“机制通过” | §10.4 + `GATE_DECISIONS.json` 不自动改 gate |
| R15 | 粒子权重当特征 | 隐式把后验信息喂给策略 | T3-A5 静态 + 运行时断言 |
| R16 | `IDLE_DEADLOCK` 当“无事发生” | 死锁被静默算完成 | §7.4 第 11 行：`complete=False` |

---

## 12. 需上游签字冻结的项（未签则不得实现为默认）

| # | 事项 | 本文默认 | 改变后果 |
|---|---|---|---|
| D1 | 发布是否唤醒待命 slot | **否** | 唤醒 = 新身份（接近 C25 的观测时机域），须重跑 T5 并重登记 |
| D2 | in-flight 是否可中断改派 | **否** | 可中断 = 新动作合同，须重走 G0 |
| D3 | 告警“首告警”语义（每目标至多一次） | **是** | 复发/多单体语义未冻结；改则 `public_fault_law` 需扩展 |
| D4 | duty 上界按站型（DABS 的 SD 用 large） | **是**（与官方 Java 一致） | 改成 per-slot ⇒ 改 evaluator ⇒ 新合同，须重跑全部对照 |
| D5 | W 的 horizon = 480 min | **是** | 改则天气/发布日程与 CVaR90 分母全变 |
| D6 | 背景请求强度 `λ` 用 PROTOCOL 的 `Poisson(n/3)` | **是**（登记为固定值，不拟合） | 拟合 λ 需独立 TRAIN 校准身份 |
| D7 | `J_diag` 只作诊断不作门槛 | **是** | 把 J 当门槛会与 S 的 `M_return` 混淆 |
| D8 | E 的 `Observation` 是否补 `service_start` 遥测 | **不补**（用粒子） | 若补，则需证明该遥测为所有方法公共且不泄漏未来 |

---

## 13. 本合同明确**不**声称的部分

1. **不声称**公共因果环境已实现（本文是规格；当前实现缺口见 `CAUSAL_ROLLOUT_APPENDIX §1-§3`）。
2. **不声称**粒子模型已校准（拟合脚本与 TRAIN 清单尚未执行；参数未知）。
3. **不声称**任何 RL 优势、G0 通过、G3 通过、`5%` 达成。`LPT 整趟重排平均降 M_return 12.8%、中位 17.1%、7/11 图 ≥5%` 属于 **S 线非 RL 结果**（`BRIEF_AGENT_CONTEXT` 第 5 条，证据在远端 `g3_pop/`），与本环境无关，不得混引。
4. **不声称** ERA5/真实气象；W 数据一律标“合成”，除非另行接入并登记。
5. **不声称**本环境能替代完整作者 rolling TSALNS（A3）或 N4 的“更强对照”资格；它只是**使 N4 可执行**。
6. **不声称** `M_return` 是新指标（与 `Check.calculateLatestTime` 同定义）。
7. **不声称** `public_fault_law` 的 18 个概率例可替代 T1–T7（前者是模块恒等式，后者是环境工程验收）。
8. **不声称** WAIT/DIVERT 被任何方式重新准入（§6.4）。

---

## 附录 A：断言编号索引（实现与测试共用）

| 编号 | 含义 | 出现处 |
|---|---|---|
| `A-01…A-13` | 静态/记录层 fail-closed 校验 | §2.8 |
| `C1…C6` | 粒子与公共前缀的相容性 | §3.2、T1、T3 |
| `INV-DD` | 每目标至多一个派遣者 | §4.4、T4 |
| `INV-MONO` | 分支只能向前追加、过去不重算 | §7.2、T4 |
| `INV-VIS` | 未来任务/预报不可见 | §5.3、T5 |
| `T1-A1…A7` … `T7-A1…A6` | 七个测试的断言 | §8 |
| `GATE` | `PUBLIC_ROLLOUT_ENGINEERING_READY` | §8.8 |

## 附录 B：引用文件与行号

| 事实 | 位置 |
|---|---|
| 动作合法性 5 条 / 3 条 | `return_makespan/global_env.py:78-98,100-106` |
| RETURN 不清 duty | `global_env.py:156-160`；`emergency_scenario.py:667`；`shared_replay_v2.py:190` |
| mask ≠ 可完成 | `global_env.py:310-320,351` |
| cost / M_return / MTC | `scorer.py:117-120,162-168,205,210,212-215` |
| cap 与 domain 锁 | `scorer.py:269-273,278-289` |
| 容差 1e-7 为绝对量级 | `scorer.py:17-18`；`CODE_MAP §C.4` |
| Java 成本口径不同 | `CODE_MAP §C.3`（`Check.java:307-344`） |
| 同刻闭包/回调/决策 | `emergency_scenario.py:340-357,617-745` |
| 服务能量按比例累积（alias 成因） | `emergency_scenario.py:400-409` |
| 服务能量不足/截断 | `emergency_scenario.py:590-615` |
| `forecast` 是常数 | `emergency_scenario.py:100` |
| 风物理（横风不可飞） | `reference_environment.py:11-23`；`shared_replay_v2.py:76-112` |
| 独立复算不含策略 | `emergency_independent_replay.py:1-4,42-60` |
| 告警条件化与共享粒子 | `public_fault_law.py:104-232`（尤其 `:120-167,191-232`） |
| `predictive_sufficiency_proven=False` | `causal_task_memory.py:45` |
| 完整车队 incumbent（非未来 rollout） | `complete_fleet.py:9-16,55-85` |
| `J_diag` 公式 | `joint_core.py:117-128` |
| T1–T7 原始条目 | `CAUSAL_ROLLOUT_APPENDIX §4` |
| alias 解析见证 | `CAUSAL_ROLLOUT_APPENDIX §2` |
| 无独立算法增量 | `PRIOR_ART_EQUATION_AUDIT §C.4` |
| 已关闭的观测时机/POSMDP | `CLOSED_DIRECTIONS C25` |
| WX 动作域边界（WAIT/DIVERT） | `CLOSED_DIRECTIONS C27-C33`；`CLAUDE_TAKEOVER_PROMPT §3.1` |

## 附录 C：给实现者的 12 条硬规则（背下来）

1. 策略只看 `ObservationFrame`；粒子、分支、隐藏相位、权重**永不**入帧。
2. `t_min` 精确比较；不写 `abs(a-b)<tol`。
3. 同刻先闭包，再按冻结的 slot 顺序逐个决定。
4. 派遣即 reservation；每目标至多一个派遣者。
5. 无合法动作 → `STANDBY`（环境推进），**不**调用策略，**不**记 WAIT。
6. 前缀逐字复制；分支只能 `t ≥ t_fork` 追加；过去不重算。
7. 一条分支只能 `run` 一次；分叉只能 `from_public_prefix`。
8. 预报 `publication_t ≤ t` 才可见；版本只增不改；发布不唤醒。
9. RETURN 只清本趟电池，累计 duty 只增。
10. 截断、失败、未服务都 `complete=False`，且必须进分母。
11. S 模式用 `scorer.score_solution` 定终局；引擎自算的成本只作对账。
12. 只用标准库；大输出写 `<EXECUTION_PATH>`；先落盘再汇总。

