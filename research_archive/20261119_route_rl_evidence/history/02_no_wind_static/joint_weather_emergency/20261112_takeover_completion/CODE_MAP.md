# CODE_MAP — 代码地图与 evaluator 精确合同

生成时间：2026-11-12 16:0x Asia/Shanghai（DeepSeek Harness 子线程）
作者身份：本次接手包 `20261112_takeover_completion` 的代码审查线程；**不是**独立研究者或独立模型审计。
工作方式：**只读静态阅读 + 本机 AST 结构分析**。未运行任何旧 driver、未运行任何测试、未连 <COMPUTE_HOST>、未做科研计算、未修改任何历史文件。
git 状态：`route_rl_research/20261103/return_makespan/` 与 `joint_weather_emergency/` 在本仓库中为 **untracked**（`git status --porcelain` 均输出 `??`），本次未写入其中任何文件；本文件是本包内新增产物。

本文件回答 7 件事（A–G）：调用链、动作空间精确语义、成本与 M_return、约束的真实支持程度、逐文件可复用性、测试覆盖与缺口、"名字不代表能力"清单。

---

## 0. 阅读范围、字节冻结与判定标记

### 0.1 已读文件与 SHA256（本次审查冻结到这些字节）

| 文件 | 行数 | SHA256 |
|---|---|---|
| `route_rl_research/20261103/return_makespan/global_env.py` | 398 | `b903f7df68cbb1d2faae6fb324ef3ed3ab1f3592c1c56aa2144eddedd54f5428` |
| `.../return_makespan/scorer.py` | 290 | `c6e156b2d770cec2f663eada37c2d39bff1583f672bda4116f81493484409135` |
| `.../return_makespan/delivery.py` | 86 | `cbf8be5dd267b3315913d0db0a904cf8562690ef0de2265e176705380141b9e0` |
| `.../return_makespan/test_g1.py` | 317 | `cf606aa439a90d8b0f4725d8208947b9f0e553c565fd5b0bb5099dde64d10920` |
| `.../return_makespan/save_execution_state.py` | 127 | `c2ba1d3ed8b797333a3882c04a6a24f172d4a61c6af16547e543f5fcf09d412c` |
| `.../return_makespan/transaction/MODIFIED_FILE.py`（=global_env 副本） | 398 | 内容同 global_env.py |
| `.../return_makespan/transaction/ORIGINAL_FILE.py`（旧 station_env） | 197 | 旧 cost 域 API，见 §E |
| `.../g23<EXECUTION_PATH>` | 463 | `7a5f2e5c06acf7c70cccc55b20a1f8f1d30c481f73b14390b2b66b77894781e8` |
| `.../g24_weather_nfz/weather_oracle.py` | 354 | `c529cae8823a9685f91ca5e5549bdd69aab2f3d13cfd5198874c38a85f8a3034` |
| `.../g24_weather_nfz/weather_env.py` | 440 | `aead6150c5e7a91743977be6185111a9d271a317ba15c17689ca5c4cd04f1c77` |
| `.../g24_weather_nfz/weather_full_map.py` | 627 | `c7db62049f8d6011153e0cf9139a9098a92d07fc62977f5359c18ffb23069b25` |
| `.../g24_weather_nfz/weather_policy.py` | 52 | `6f15e10030b0ab7e4baef6b7c6fe5297dbf120ec606338d7198a1dfe81985826` |
| `.../g24_weather_nfz/rl_algorithms.py` | 281 | `a9679133e93b3d2edf613102667827ad02427d49cfcea657d930b1004eb029fd` |
| `route_rl_research/20261103/source_snapshot/lrphsd/evaluator.py` | 48 | `ae4f1aa070717865ec58bdd86d1493eb7b54561ab524cbc4f215af0daec19ff0` |
| `route_rl_research/20261103/source_snapshot/lrphsd/problem.py` | 80 | `f03c2f4201cdea977644d84ab0ad704eb47d4c4389b06b2ac86b9d264463b1cc` |
| `joint_weather_emergency/20261106_complete_fleet_worker/MODIFIED_FILE/emergency_scenario.py` | 962 | `01d243274f054f512cf68f84c7a56b62866769e6795e645bb917034ecde5ffe1` |
| `.../MODIFIED_FILE/joint_core.py` | 134 | `a06001792abbb0b736ccc9d7492da1ee1c2addf5ffc15c6554c8ed4f1d60b300` |
| `.../MODIFIED_FILE/complete_fleet.py` | 85 | `3777783df831b1b085f676418646bb68d267cb49fa98aad71dca4d053cc0a120` |
| `.../MODIFIED_FILE/shared_replay_v2.py` | 191 | `2351a85dfae21ff9fe8b2b6dd1bdf34dfe9b16453a35064291a55aafcbc15278` |
| `.../MODIFIED_FILE/emergency_independent_replay.py` | 215 | `6bbeb0f47c925b29d7f2dd488f41d18150f60fba24bbe7f7b642348936d62f9f` |
| `.../MODIFIED_FILE/public_phase.py` | 76 | `0383af60cb3459fb18742839a7f41de2d1d7815bd255532388ab565c7c4c3465` |
| `.../MODIFIED_FILE/fast_public_history.py` | 69 | `cd3f17933f5454f521a6e251cc0f7476f6155a9bd8829ba1e63d8ebe0e39a68a` |
| `joint_weather_emergency/20261112_wx_e_forecast_v1/src/emergency_scenario.py` | 962 | `43794ae3ec936c8160c66178be706b37949d0233af2aded46e171dc2c872bdc6` |
| `.../20261112_wx_e_forecast_v1/wx_e_forecast_driver.py` | 556 | `fec59c92d856d0e820f13ce0276cb93512f6323a11890e4e2faf9b40542d2b09` |
| `joint_weather_emergency/20261112_public_fault_conditioning/MODIFIED_FILE/public_fault_law.py` | 232 | `88abd7e476e5b20e99afb552c51fa0b9c776ebd6875169dcfc69f776e9208727` |
| `reproduction/reviewer_package_semfix/reference/java/official_source/Check.java` | 715 | `ea0f541cb5eb0b90772e8fc1cadc62e72ba3338d6a6d005dae0ac43abbd54d23` |

未读完（结构性列出，未用于本文件结论）：`g24_weather_nfz/weather_replay.py`、`weather_scenario_io.py`、`weather_author_anchor.py`、`fleet_history_controls.py`（15.7 KB，beam 主体）、`route_trainers.py`（27 KB）、`rl_research/rl_dyn/dyn/*`、`rl_wind/wind/*` 的逐文件语义。对这些只做文件级/头注释级判定，并在 §E 明确标注"未逐行核实"。

### 0.2 判定标记（全文统一）

- **[已证实-代码]**：可直接由本文件引用的源码行读出，读者可复核。
- **[已证实-收据]**：引用包内既有 REPORT/STATE/RECEIPTS 的既有结论（本文件不复算）。
- **[未证实]**：静态推断、需要运行或对照原始数据才能确认。
- **[未实现]**：代码中确实不存在的能力。
- **[关闭]**：历史已关闭身份，本文件不建议复活。

---

## A. 类/函数调用链

### A.1 静态合同 S 线（fixed station / slot / target-station，最小 M_return）

```
Instance(params, targets, stations, sha256)
  └── StationRouteEnv(instance, station_idx, station_type, target_ids)
        ├─ __init__      global_env.py:32-60   校验 SABS(1)/DABS(2)、唯一 target、slot 集合、容量/半径/duty 上界
        ├─ reset()       :62-72   remaining=set(all)；routes/current_pos/current_trip/trip_energy/trip_elapsed/cumulative_duty 清零
        ├─ observation() :113-141 生成 actions 与 mask（含 dead_end）
        ├─ step()        :143-183 单站 cost 域；reward = -cost_delta * time_cost
        └─ result()      :185-197 routes / operating_minutes / route_variable_cost
  └── FullMapRouteEnv(instance, anchor, epsilon=0.0, cost_tolerance=1e-7, station_order=None, use_necessary_cost_mask=True)
        ├─ __init__      :216-245 anchor→CostAnchor；anchor.verify(instance)；cost_budget = anchor.cost*(1+epsilon)
        │                        target_pools 来自 anchor.target_station；station_order 必须是"非空站"的排列
        ├─ reset()       :247-255 每站建一个 StationRouteEnv；total_reward=0；_terminal_score=None
        ├─ active_station:257-259 station_order 中第一个未完成的站（固定程序顺序，非动作）
        ├─ potential     :265-269 max over (站,slot) of (cumulative_duty + trip_elapsed)
        ├─ necessary_cost_lower_bound(action?) :275-303 fixed + time_cost*(spent + service_left + returns)
        ├─ _actions_and_masks() :310-320 三层：physics / cost / mask
        ├─ observation() :336-356 actions, physics_mask, necessary_cost_mask, mask, budget, lower_bound, status
        ├─ step()        :358-383 只作用于 active_station；reward = Δpotential；done 时 validate_candidate
        ├─ candidate()   :385-392 用 anchor 的 station_types/target_station/instance_sha256 重建完整 solution
        └─ result()      :394-398 完成且 admissible 才返回，否则 RuntimeError（无隐藏兜底）
```

**step 的完整回调顺序 [已证实-代码]**（`global_env.py:358-383\)：

1. `if self.terminated: raise RuntimeError`（完成的或已判 dead_end 的 episode 不能再走）
2. `if not self.legal(action): raise IllegalAction`；`legal` 是**对当前 mask 的成员检查**（:330-334），因此 untyped / 越界 / 被 cost mask 剪掉的动作为非法
3. `si, before = self.active_station, self.potential`
4. `self.station_envs[si].step(action)` —— **忽略**站点局部 reward（:364 注释 "Ignore old local operating-cost reward"）
5. `reward = before - self.potential`（:366）；`total_reward += reward`
6. 若 `self.done`：`self._terminal_score = validate_candidate(instance, candidate(), anchor, epsilon, cost_tolerance)`（:368-371）
7. `obs = self.observation()`；`info` 含 `physical_station / physical_slot / visited_target / is_return / episode_reward / reward_is_complete_objective / failure / terminal_score`（:374-382）
8. 返回 `(obs, reward, obs["terminated"], info)`

**奖励 [已证实-代码]**：`FullMapRouteEnv` 的 reward 是 **potential 的差分**，potential 单调不减，故每步 reward ≤ 0，整条 episode **telescoping 到 `-M_return`**。`test_g1.py:190-195` 断言 `result()["reward"] == -8.0` 且 `score["M_return"] == 8.0`，并显式断言 `reward != -operating_minutes`（即"奖励不是成本"）。注意：`reward_is_complete_objective` 只有终局 admissible 时才为 True；终局不可行时 reward 仍是 `-M_return`，但被标记为不可用。

**终止条件 [已证实-代码]**：
- `done = active_station is None`，即**所有站的 remaining 为空且所有 slot 的 current_trip 为空**（`global_env.py:74-76, 261-263`）——**必须显式 RETURN 收尾**，只访问完目标不算 done（`test_g1.py:219-224`）。
- `dead_end = not done and not any(mask)`（:322-324）。
- `terminated = done or dead_end`（:326-328）。
- status ∈ `COMPLETE_ADMISSIBLE / COMPLETE_INVALID / DEAD_END / RUNNING`（:340-342）。

### A.2 独立 full-map evaluator 的调用链与口径

```
score_solution(instance, solution)            scorer.py:53-217
  ├─ 结构/身份校验（instance_sha256、维度、node 有限性、非负）:77-102
  ├─ 逐站：fixed cost / slot 维度 / 逐 trip
  │    ├─ closed_station、large_drone_at_small_station      :140-143
  │    ├─ coverage（站型半径）                              :153-155
  │    ├─ completion（M_service 用）                        :148-161
  │    ├─ 全长序列 [station]+trip+[station] → length/travel/duration/energy  :162-168
  │    ├─ energy > capacity + 1e-7 → issues                 :173-174
  │    └─ duty += duration；limit 按**站型**                :175-186
  ├─ 恰好一次：counts[nid]==1 否则 missing/duplicate         :191-195
  └─ cost = fixed + operating*time_cost; M_return = max(station_makespan)
     M_service = max(completion); mean / p90(nearest rank)    :204-215

CostAnchor.from_solution / .solution() / .verify()            scorer.py:220-258
validate_candidate(instance, solution, anchor, epsilon, cost_tolerance)  :261-290
  ├─ domain：station_types 与 target_station 必须与 anchor 完全一致（:269-272）
  ├─ budget = (1+epsilon)*anchor.cost；cap_ok = cost - budget <= tolerance（:273-277, 47-50）
  └─ admissible = original_feasible and domain_valid and cap_ok（:288）
```

关键点：**cap 是整图 cap，不是逐站 cap**（`validate_candidate` 只算一次 `result["cost"]`）；因此"某站成本上升、另一站下降、整图不变"是允许的（`test_g1.py:88-95` 的 `test_global_cap_allows_local_cost_increase` 专门断言这一点）。

### A.3 g23 生成器调用链

```
generate_allocated_instance(candidate_sites, target_count, namespace, partition, ordinal, exclusions)  generator_v2.py:439-452
  ├─ exclusions.require_research_ready()                       :226-253（强制 4 个排除清单；PERMANENT 必须 12,120 条）
  ├─ derive_seed(namespace, family, partition, ordinal, stream) :272-289（sha256(canonical_json)[:8]）
  ├─ SplitMix64(coordinate_seed) / SplitMix64(label_seed)       :55-76
  └─ _generate(...)                                             :359-436
       ├─ 先 site（cap 32）后 target（cap 1024），逐个 proposal；坐标 = k*L/2^53（:327-332）
       ├─ 拒绝理由：outside_published_grid_box / site_separation_le_2000m /
       │            target_nearest_site_gt_5000m / target_separation_lt_200m（:173-186）
       ├─ target id 用无偏 randbelow 做 Fisher-Yates（:296-319）
       └─ _finish：渲染 5 列文本、raw_sha256、canonical_geometry_sha256、与排除清单碰撞则 fail closed（:336-356）
```

生成器**没有** study-map CLI（`protocol_info()["no_study_generation_CLI"]=True`，:455-459），必须在 root 侧冻结 allocation。

### A.4 W 线（天气/NFZ）三条互不相同的调用链

**(a) leg 级物理 oracle → 单机环境 → 多站环境**

```
weather_oracle.plan_route(start, end, departure_s, wind, params, no_fly_zone)   weather_oracle.py:290-354
  ├─ 节点集 = {start, end} ∪ NFZ 顶点；只枚举 **simple path**（不重复节点，不插 WAIT，不成环）
  ├─ 每条边 _integrate_leg：按 wind knot 分段积分，_track_speed = along + sqrt(airspeed^2 - cross^2)  :199-210
  ├─ NFZ：只拒绝"正长度内部段"与 [on_s, off_s) 有交的边  :159-196, 336-343
  └─ 返回最早到达的 RouteResult（含 polyline/segments/distance/energy/arrival/legal/failure）

weather_env.WeatherRouteEnv(instance: WeatherInstance)          weather_env.py:84-359
  ├─ 单机、单站、无 slot、无站型、无 fixed cost 结构；能量上限 energy_capacity 一个标量
  ├─ mask：_legal_target → _target_projection（去程 plan_route + 回程 plan_route + energy + duty）:147-157,177-189
  ├─ step：RETURN 分支 :294-308（cost 用 minutes；completion 记 service 结束时刻）
  └─ 另有 replay_trips 独立复算 :362-440

weather_full_map.WeatherFullMapEnv(instance, anchor, scenario, weather_cost_cap)   weather_full_map.py:233-628
  ├─ 多站 + 每 slot 一个独立 clock（clock_s），全部 slot 从 0 起、各自推进（真并行）
  ├─ mask = 物理(energy/duty/coverage) ∧ weather_cost_cap 下界 ∧ **original anchor cap 下界** :377-405
  ├─ 终局 replay_weather_solution（独立 oracle：weather_replay.replay_route）+ validate_candidate :119-230, 600-605
  └─ reward = Δpotential，potential = max(clock_s/60) :289-291, 598
```

**(b) 联合应急事件模拟器（`EmergencySimulator`）**

```
EmergencySimulator(scenario).run(policy)                       emergency_scenario.py:690-745
  loop:
    _release_until(now)                      :340-357  先按新 frontier 结算所有 event，再放行 release<=now 的任务，latch 逾期
    while events[0].time == now: _handle_event(pop(0))   :697-698   同刻事件闭包先排空
    if now < horizon: for did in sorted(decisions): obs=observation(did); a=policy(obs); _apply_action   :701-715
    else: decisions.clear()
    若无事件：跳到下一个 UNRELEASED 的 release（仅当站内还有可用机）   :718-735
    now = events[0].time（严格等于，绝不按容差分组）      :736-743
  → result()                                 :747-815
```

事件对象是 `(when, seq, drone_id, kind, payload)`，排序键 `(time, drone_id, seq)`（:329-338）；**同刻多机因果顺序由 drone id 唯一决定**，且 `run` 里用 `decisions` 集合保证"同一时间戳的每个决策看到同一 frontier"。

`_handle_event` 的分派（:617-675）：`FLIGHT_FAIL / RETURN_FAIL / SERVICE_FAIL → terminal failure`；`FLIGHT_HORIZON / RETURN_HORIZON / SERVICE_HORIZON → 只是截断，不算失败`；`duty > limit → DUTY_LIMIT 失败`；`ARRIVE_TARGET → _start_service`；`SERVICE_END → SERVED + decisions.add`；`RETURN_END → 回站、清 trip、清 energy、decisions.add`。

**(c) 独立复算（`emergency_independent_replay`）**

`verify_result(snapshot, result)`（:200-215）→ `replay_snapshot`（:65-198）：只用 action log 重新积分，**不 import 原 simulator / Trace**；并强制"同一时间戳内必须按 drone id 升序决策"（:103-116），`INVALID_ACTION` 直接判 NOT_VERIFIED（:171）。

### A.5 incumbent / deadline 交付

`delivery.finalize_result(instance, raw_solution, anchor, started_at, budget_s, clock=perf_counter, epsilon=0, cost_tolerance=1e-7)`（`delivery.py:16-86`）：

```
validate(raw) → 三种拒绝：raw_inadmissible / raw_validation_late / raw_worse_than_anchor   :40-45
若拒绝：validate(anchor.solution())，只有 admissible 且 <= budget_s 才采用                  :47-58
record 里同时保留 raw 与 fallback 两套 solution+score+时间戳                               :60-78
再取一次 elapsed；若 ready > budget_s 则把 chosen 置 None                                   :79-82
status = ONTIME_VALID / NO_ONTIME_VALID_OUTPUT；ontime_valid_output = chosen is not None    :83-85
```

契约边界 [已证实-代码]：`budget_scope="D_improvement_from_common_ready_input"`、`anchor_generation_included=False`（:62-63）—— **6 s / 12 s 只覆盖"从共同 ready 输入开始的增量"，不含 anchor 生成**；调用方必须在模型加载/构造之前启动时钟（:2-5 与 :64 的字段名 `caller_start_must_precede_model_load_and_construction`）。

RL/启发式侧的 incumbent：`complete_fleet.CompleteFleetRollout.decide`（`complete_fleet.py:55-84`）对每个候选首动作先贪心补全成**完整解**（`complete()` :24-54，按 urgency/distance 排名、逐机推进、必要时 RETURN、最后全体返航），再用**完整 J** 比较（`_key`）取最优；若没有完整候选则回退到 prior 最优动作并把 `fallback=True`、`incomplete_candidates` 计入 receipt（:79-80）。它**不会**把不完整方案当 incumbent（:54 `return p if self.evaluate(p,tasks)['complete_return'] else None`）。

---

## B. 动作空间的精确语义

### B.1 静态域的两个动作

```python
RouteAction(slot: int, target_id: Optional[int] = None)
  target_id is None  ⇔  RETURN                     global_env.py:11-18
```

**动作列表的生成顺序（决定 RL 的 action index）[已证实-代码]**（`global_env.py:113-118`）：

```
actions = [ (slot, nid) for nid in sorted(remaining) for slot in slots ] + [ (slot,) for slot in slots ]
```

即 **target 主序、slot 次序**，最后才是各 slot 的 RETURN。索引随 `remaining` 缩小而漂移，任何缓存 action index 的实现必须同时缓存 observation。`FullMapRouteEnv` 的 actions **只包含当前 active station 的**（:314），因此跨站不会出现在同一个动作表里。

#### (slot, target) 合法性 —— 5 个条件全部满足才行

```python
# global_env.py:78-98
1  slot in self.slots                        # SABS 只有 {1}；DABS {0,1}（:47）
2  target_id in self.remaining               # 未访问过 → 天然"恰好一次"
3  dist(station, target) <= self.radius + EPS          # EPS=1e-7（:8）
4  trip_energy[slot] + travel*flight_energy + target.energy
       + back*flight_energy <= capacity[slot] + EPS
       travel = dist(current_pos[slot], target)/speed
       back   = dist(station, target)/speed
       capacity = large_battery if slot==0 else small_battery          # :48-51
5  cumulative_duty[slot] + trip_elapsed[slot] + travel + target.service + back
       <= duty_limit + EPS
```

四个必须点出的语义：

- **条件 4 已包含"回到站"的那一段**（`back`），所以任何被接受的目标之后都仍然存在一条合法的直接返航；这是"逐目标可行 ⇒ 可返航"的不变式。
- 条件 4 用的是 **本趟累计 trip_energy**（跨目标累加），不是单段能量。
- 条件 5 用的是 **跨趟累计 `cumulative_duty`** 加本趟已用 `trip_elapsed`，再加本段与回程；即 duty 是**整个任务周期**的口径，不是单趟。
- `self.radius` 与 `self.duty_limit` **只由 station_type 决定，不区分 slot**（:52-59）。DABS 站的 slot 1（小型机）因此使用 **large_radius = 5000 m 与 large_duration = 600 min**。这与官方 Java `checkStationOperation`（`Check.java:145`：`maxAllowedTime = (type==2)? maxTimeLarge : maxTimeSmall`）逐字一致，也与 `scorer.py:153,184`、`evaluator.py:32,42` 一致；`test_g1.py:127-130` 专门把它固化为合同（`test_sd_at_dabs_uses_dabs_duration`）。见 §G-1。

#### (slot, RETURN) 合法性 —— 3 个条件

```python
# global_env.py:100-106
1  slot in self.slots
2  bool(self.current_trip[slot])            # 不允许空趟 RETURN
3  trip_energy[slot] + back*flight_energy <= capacity[slot] + EPS
   cumulative_duty[slot] + trip_elapsed[slot] + back <= duty_limit + EPS
   back = dist(current_pos[slot], station)/speed
```

RETURN **不要求** `remaining` 为空，因此允许"打一趟、回站、再出去"的多趟结构。

### B.2 三层 mask（`FullMapRouteEnv`）

```python
# global_env.py:310-320
physics = 站点 env 的 mask（上面的 5 条 / 3 条）
cost    = physics and (necessary_cost_lower_bound(action) - cost_budget <= cost_tolerance)
mask    = physics and (cost_ok or not use_necessary_cost_mask)
```

- `necessary_cost_lower_bound`（:275-303）= `fixed_cost + time_cost*(spent + service_left + returns)`：
  - `spent` = 已发生的 `operating_minutes`（+ 被投影动作的耗时）
  - `service_left` = 所有站**剩余目标**的 service 之和（- 被投影目标的 service）
  - `returns` = 所有"仍在飞"的 slot 从当前位置直接回站的飞行时间之和（对投影动作做增量替换）
  - **不含**未来在目标之间的转场时间 → 是 admissible 下界，只能剪掉"已经确定超 cap"的前缀。
- 因此：**mask 通过 ≠ 能完成**。代码把这一点写进观测：`necessary_mask_is_completion_certificate = False`（:351），并在 docstring 明说（:207-214）。`test_g1.py:226-235` 用 `small_duration=6.5` 构造"第一步合法、第二步后 dead_end"，断言 `terminated=True` 但 `done=False`、`info['failure']=='dead_end'`、`result()/candidate()` 抛 RuntimeError。
- `use_necessary_cost_mask=False` 只是**关闭剪枝**，终局仍由 `validate_candidate` 拒绝（`test_g1.py:237-246` 断言 `status=='COMPLETE_INVALID'`、`cost_cap_satisfied==False`、`reward_is_complete_objective==False`）。

### B.3 RETURN 之后的精确状态变化（静态域）

| 量 | RETURN 前 | RETURN 后 | 代码位置 |
|---|---|---|---|
| `current_pos[slot]` | 最后访问目标 | `station.id` | :157 |
| `current_trip[slot]` | 非空 list | `[]` | :158 |
| `routes[slot]` | 已关闭的若干趟 | **追加** `list(current_trip)` | :155 |
| `trip_energy[slot]` | 本趟累计 | **0.0**（换电） | :159 |
| `trip_elapsed[slot]` | 本趟累计 | **0.0** | :160 |
| `cumulative_duty[slot]` | D | **D + trip_elapsed + back**（只增，**不清零**） | **:156** |
| `operating_minutes` | C | C + back | :174 |
| `remaining` | — | 不变（RETURN 不改变覆盖） | — |
| reward | — | `-(potential 下降)` = 0（因为 potential 含 cumulative_duty，RETURN 不减少它） | :366, :265-269 |

**"RETURN 不清零累计 duty"的代码位置（逐行，这是本合同最容易被误实现的一行）**

1. `route_rl_research/20261103/return_makespan/global_env.py:156`
   ```python
   self.cumulative_duty[slot] += self.trip_elapsed[slot] + back
   ```
   紧接着 :159-160 只清零 `trip_energy` 与 `trip_elapsed`。**没有任何地方把 `cumulative_duty` 赋 0**（全文只在 :69 初始化、:156 累加、:180 导出、:268 读作 potential 出现）。
2. 观测里把它暴露给策略：`:131 "cumulative_duty": self.cumulative_duty[slot]`（每 slot 字段）；`potential` 也读它（`:268`）。
3. 单机天气版同一语义：`g24_weather_nfz/weather_env.py:301` `self.cumulative_duty_min += self.trip_elapsed_min`（此前 :298 已把 `back_min` 加进 `trip_elapsed_min`）。
4. 多站天气版：用"从不重置的 clock"表达同一件事 —— `weather_full_map.py:196` `state.clock_s = route.arrival_s`（RETURN 分支），而 `reset()` 里每个 slot 的 `clock_s=0.0`（:72, :275），**全程没有第二次赋 0**；`:585-586` 只清 `current_trip` 与 `trip_energy`。
5. 联合事件模拟器：`emergency_scenario.py:667` `d.trip_energy = 0.0`（换电），duty 在 `_accrue_event` `:409 d.duty = payload["base_duty"] + elapsed` 里只增；`:645-647` 在**每个事件**上检查 `d.duty > duty_limit → DUTY_LIMIT`。
6. 独立复算：`shared_replay_v2.py:190` 显式写出合同字符串 `duty_contract='original_station_kind_limit_report_only_no_reset'`；`:148-151` RETURN 只把 `energy` 归零（下一趟 `energy=0.` 在 `:155` 的 trip 循环开头），`duty=t` 是该机全程时钟（:175）。`emergency_independent_replay.py:148` 同样只 `d['energy']=0.`，`:139` `d['duty'] += z['end']-now`。
7. 回归测试：`test_g1.py:255-261` `test_return_preserves_duty_and_resets_energy` 断言访问 3 分钟后 `cumulative_duty[0]==3.0` 且 `trip_energy[0]==0.0`、`trip_elapsed[0]==0.0`。

> 结论 [已证实-代码]：**RETURN 换电只重置 trip 级能量/计时，累计 duty 单调保留**；在 6 个实现（2 个静态、2 个天气、2 个联合/复算）中语义一致，没有发现"RETURN 清零 duty"的实现。唯一的措辞差异是 `shared_replay_v2` 把 duty 超限记为 **report-only**（`feasible = complete and not duty_violation`，:183-186），而静态 evaluator 把 duty 超限记成 **issue → 不可行**（`scorer.py:184-186`）。二者不是同一个门槛，引用时必须说明。

### B.4 其他域的动作语义（与主线的距离）

| 域 | 动作 | 与静态合同的关系 |
|---|---|---|
| 联合应急 `emergency_scenario` | `TARGET / RETURN / WAIT(min≤max_wait)`（:204-227, :464-485） | **WAIT 只在隔离 W 域存在**（`WAIT` 仅当 `at_station` 且 `actionable`）；主 static 域没有 WAIT。brief §3.1 已明确"不能由旧 pilot 反推一般许可" |
| 联合应急 mask | `TARGET` 只列 `AVAILABLE ∧ station_id==own.station_id`；`RETURN` 需 `not at_station ∧ trip_started`；`WAIT` 需 `at_station`（:464-485） | 不含能量/duty 预筛；能量与 duty 是**执行期失败**（SERVICE_ENERGY / FLIGHT_ENERGY / DUTY_LIMIT） |
| 联合控制 `joint_core.feature_actions` | 在 shared mask 上再按"wind_bound 鲁棒"筛：`v = speed - bound`，`dt=out/v+service+back/v`，能量/ duty/horizon 不足即丢弃（:23-46） | 这是**所有方法共享**的必要性筛（:46 `mask=[True]*len(rows)`），但**不是** evaluator；evaluator 仍是 `emergency_independent_replay` |
| `rl_research` 旧线 | CA-RL：20 operator × 3 intensity = 60 动作（`rl_dyn/engine/carl/actions.py:6-31`）；PPO-DAC：温度/修复候选数/家族/强度/重启 5 头（`rl_ppo/ppo/agent.py:1-5`） | **违反现行动作合同**，不可作为 RL 动作空间（见 §E） |
| `rl_rt` | 每步动作 = targets(n) 再接 tokens(3*ns)，token 会**开站并选站型**（`rl_rt/rt/env.py:1-8`） | 与"部署/站型固定"冲突 |

---

## C. 成本与 M_return 的精确计算

### C.1 静态 evaluator（唯一权威口径）

```
fixed      = Σ_si fixed(kind_si)
             kind 0 → 0
             kind 1 → small_station_cost + small_drone_cost            = 22.8 + 5.0 = 27.8
             kind 2 → large_station_cost + small_drone + large_drone   = 30.4 + 5.0 + 8.0 = 43.4
             （默认参数见 problem.py:8-22；实现见 scorer.py:117-120 / evaluator.py:16-17）

operating  = Σ_si Σ_slot Σ_{trip≠∅} duration(trip)
duration   = length([station]+trip+[station]) / speed  +  Σ_{n∈trip} n.service
             （scorer.py:162-168）

cost       = fixed + time_cost * operating        time_cost = 0.5（= Java FLIGHT_COST_PER_MIN）
             （scorer.py:205；evaluator.py:48）

M_return   = max_si max_slot duty(si,slot)        duty = Σ_{trip≠∅} duration(trip)
             （scorer.py:131,175,184,190,210）
M_service  = max_n completion(n)
             completion(n) = duty_before_trip + Σ_{k≤n}(travel_k + service_k)   （scorer.py:148-161,211）
MTC        = mean(completion)                    p90 = nearest-rank ceil(0.9n)-1（:212-215）
```

**成本包含 / 不包含什么 [已证实-代码]**：

| 项 | 是否计入 cost | 位置/理由 |
|---|---|---|
| 站点固定成本、无人机购置成本 | ✅ 计入（按站型一次性） | `scorer.py:117-120` |
| 飞行时间 × time_cost（**含**出站与回站两段） | ✅ | `scorer.py:162-168, 205` |
| 目标服务时间 × time_cost | ✅ | 同上 |
| 能耗（flight_energy / target.energy） | ❌ **不计入成本**，只作硬约束 | `scorer.py:173-174`；`result["total_energy"]` 只是诊断字段 |
| 换电时间、充电时间、周转时间、发射/回收/同步时间 | ❌ **明确不计** | `scorer.py:1-6` docstring："There is no added charging, turnaround, launch-pad, or synchronization time." |
| 跨站/跨机调度开销、等待时间 | ❌ | 所有 slot 在 t=0 同时可用，各 slot 串行无等待 |
| 罚项（不可行/超 cap） | ❌ 不入 cost；用 `issues` + `admissible=False` 表达 | `scorer.py:216, 288` |

距离一律用 `math.hypot` **现算**，刻意不读 `instance.dist`（`scorer.py:33-35`；`test_g1.py:168-173` 把 dist 全置 0 后断言 cost/M_return 不变）。

### C.2 与 Java `Check.calculateLatestTime` 的逐项对应

Java 侧（`Check.java`）：

```java
calculateLatestTime(paths, speed)                       // :594-618
  latestTime = max over station, max over drone of Σ_{subPath} calculatePathTime(subPath, speed)

calculatePathTime(path, speed)                          // :22-48
  if path.size() <= 2: return 0
  for i in 0..size-2: totalTime += dist(node_i, node_{i+1}) / speed
                      if 0 < i < size-1: totalTime += node_i.service
  totalTime += lastNode.service
```

对应关系 [已证实-代码]：

| Python | Java | 一致性条件 |
|---|---|---|
| `duty(si,slot) = Σ_{trip} duration` | `Σ_{subPath} calculatePathTime` | 一趟 trip ↔ 一个 subPath |
| `length([station]+trip+[station])/speed` | 相邻对距离求和 / speed（含两端站点） | subPath 必须是 `[station, …, station]` |
| `Σ_{n∈trip} n.service` | 循环内对"中间点"加 service + 末尾点 service | 末尾点是站点且 **station.service == 0** |
| `max_si max_slot` | `max over station, max over drone` | 同构 |
| 空 trip 跳过（`scorer.py:137-139`） | `size<=2 → 0` | 一致 |

必要条件由数据合同保证：`problem.py.read_instance` 强制 `station service must be zero under official contract`（`problem.py:70`），且官方数据用 `energy==0` 区分站点、`energy>0` 区分目标（:66-70）。所以 **在官方数据 + `[station,…,station]` 表示下，`scorer.M_return ≡ Check.calculateLatestTime`**。这是"同定义"的严格依据；`scorer.py:210` 与 `Check.java:613` 是同一个 max-max-Σ 结构。

### C.3 **必须写明的口径冲突：Java 的 cost / duty / energy 与 Python evaluator 不是同一函数** [已证实-代码]

Java 里存在第二套"跳过站点边"的累加逻辑：

```java
// Check.java:307-344  calculateDroneTime —— 被 calculateTotalCost(:281) 与 calculateSolutionTime(:299) 调用
for (i = 0; i < subPath.size()-1; i++) {
    if (currentNode.getNodeNo() == 0 || nextNode.getNodeNo() == 0) continue;   // ← 跳过所有与站点相连的边
    subPathTime += dist(current, next) / speed;
    if (i > 0 && i < size-1) subPathTime += currentNode.service;
    subPathTime += lastNode.service;                                          // ← 在循环内重复加
}
// Check.java:131-190 checkStationOperation —— 同样的 skip 与同样的循环内重复加
// Check.java:96-119 calculatePathEnergy —— 同样 skip 站点边；:122 checkPathEnergy 用它
```

后果（按算术直接得出，不是实验）：

- 单目标一趟 `[0, n, 0]`：**没有一条边存活**，`calculateDroneTime = 0`，`checkStationOperation` 的 `subPathTime = 0`，`calculatePathEnergy = 0`。即该趟的飞行成本、飞行时长、飞行能耗全部被官方 Java 记为 0。
- 双目标一趟 `[0,a,b,0]`：只统计 `dist(a,b)/speed + service(a) + service(0)`，漏掉 `dist(0,a)`、`dist(b,0)` 与 `service(b)`。
- 而 `calculatePathTime`（:22-48，被 `calculateLatestTime` 调用）**不跳过**站点边，是全长口径。
- 官方 Java 内部因此自相矛盾：**同一份代码里，"最新时间"用全长，"成本/累计 duty/可行性电量"用跳过站点边的口径**；`printRemainingBattery`（:417-427）又用全长（`calculatePathLength`）。`Main.java:126,214,272` 用 `calculateTotalCost` 作目标，`Main.java:97` 用 `checkStationOperation` 作 duty 闸门，`Check.java:471` 用 `calculatePathEnergy` 作能量闸门。

由此得到三条可以被直接检验、且对 S/W 合同有影响的结论：

1. **"官方成本"在本项目只能指 `lrphsd/evaluator.py` + `scorer.py` 这一对**（两者 cost 定义一致，`test_g1.py:72-80` 断言 `evaluate` 与 `score_solution` 的 `feasible/cost/operating_minutes` 相同），**不能**指 `Check.calculateTotalCost`。
2. Python evaluator 在 cost、duty、energy 三个维度都**严格强于** Java 的闸门（因为多算了非负的站点边与服务时间）。所以"Python 判可行 ⇒ Java 判可行"成立；**反向不成立**。任何"复现与 Java 逐位一致"的表述都需要限定到 M_return（latest time），而不是 cost。
3. 本次静态审查**没有找到**任何把 `score_solution` 的 cost 与 `Check.calculateTotalCost` 对账的测试或收据（`test_g1.py` 只与 `lrphsd.evaluator` 对账）。 → 见 §F 缺口 2，以及 §H 的建议核对项。这是 [未证实] 的台账缺口，不是新发现的错误结论。

### C.4 浮点与容差

| 常数 | 值 | 语义 | 位置 |
|---|---|---|---|
| `EPS` | 1e-7 | 静态 env 内物理比较（能量/半径/duty） | `global_env.py:8`，用法 :83,98,106 |
| `COST_TOLERANCE` | 1e-7 | **绝对**成本容差（不是相对 slack） | `scorer.py:17`，docstring 明写 |
| `PHYSICS_TOLERANCE` | 1e-7 | scorer 内 energy/coverage/duty | `scorer.py:18` |
| `epsilon` | 0.0（合同） | `budget=(1+epsilon)*anchor.cost` | `scorer.py:273`；`global_env.py:231` |
| `allow_nan=False` | — | solution 含 NaN/Inf → 直接判不可行（fail closed） | `scorer.py:22, 80-84`；`test_g1.py:162-166` |

判定实现是 `cost - budget <= tolerance`，且先做 `_finite_nonnegative` 三点检查（`scorer.py:38-50`）；因此 `cost_within_cap(1e6+5e-8, 1e6) == True`、`(1e6+2e-7) == False`（`test_g1.py:182-186`）—— **在大成本量级上 1e-7 是绝对量，不是 uLP 级容差**。

量级换算（算术，非实验）：double 在 1e6 上的 ulp = 2^-33 ≈ 1.164e-10，所以 1e-7 绝对容差 ≈ 860 ulp ≈ 1e-13 相对量。含义有两条，必须同时说：
- 它**足以吸收求和顺序与舍入差异**（这正是容差存在的理由，不会把数值等价的解误判为超 cap）；
- 它**不足以掩盖任何实质成本上升**：在 1e6 的图上放宽 1e-7 等于放宽 0.00000001%。
因此既**不能**把 `cost <= anchor.cost + 1e-7` 说成"严格 ≤"，也**不能**说成"有意义的松弛"；正确表述是"数值容差级、非经济级"。此点建议在 PREREG 中显式写明（见 §H-3）。

`validate_candidate` 还会回填 `raw_cost_minus_cap`、`raw_cost_minus_anchor`、`cost_cap_satisfied`、`domain_valid`、`admissible`（`scorer.py:278-289`），因此"卡在 cap 边界多少"是可审计的，不需要外部重算。

### C.5 W 线的三套成本（不可互换）

| 口径 | 公式 | 位置 | 何时有效 |
|---|---|---|---|
| 静态原成本 | `fixed + 0.5*operating_minutes`（无风、无等待） | `scorer.py:205` | S 合同、以及 W 里的 `original_admission` |
| 天气成本 | `fixed + 0.5*Σ_slot clock_min`（clock 由风积分得到；需外部给 `weather_cost_cap`） | `weather_full_map.py:213, 294-296` | W 的 `weather_cost`；cap 缺失时 `strict_weather_cap` 会记 `weather_cost_cap_missing`（:214-220） |
| 联合 J | `J = incurred_cost + 0.5*makespan + miss + 1000*routine_missing + 10000*bad` | `joint_core.py:117-128` | 历史联合协议（oldbeam 1169.612132 等）的 `J`，**不是** M_return |
| 单机天气 | `fixed_cost + time_cost*operating_min`；`M_return = cumulative_duty_min` | `weather_env.py:344-359` | 单机玩具域 |
| 联合 incurred | `fixed + time_cost*Σ_drone duty`；`makespan = max last_return_time` | `emergency_scenario.py:783-786, 778` | 事件日域，且 `complete` 时才有 makespan |

**跨图比较的硬约束 [已证实-代码]**：`validate_candidate` 每次只处理一张图的一个解，没有任何跨图聚合函数；因此"逐图 cap"不是靠调用方自律，而是**没有提供合并接口**。任何"平均改善"必须由外部脚本先逐图判 admissible、再聚合，且 `delivery` 的 `status` 会把超时/超 cap 的图明确标成 `NO_ONTIME_VALID_OUTPUT`（`delivery.py:83-85`），不会静默丢图。

---

## D. 各约束的代码位置与"当前真实支持程度"

★ = 已实现且有测试；◐ = 已实现但口径与 Liu 原文/物理直觉有差距；✗ = 未实现。

| 约束 | 程度 | 代码位置 | 说明 |
|---|---|---|---|
| 多站 | ★ | `global_env.py:235-243, 257-263`；`weather_full_map.py:259-275`；`scorer.py:111` | 站集合来自 instance；`station_order` 由程序固定，不是动作 |
| 站型 SABS/DABS（异构） | ★ | `global_env.py:33-34, 47`；`scorer.py:113-120, 140-143` | SABS 只有 slot 1；DABS 有 (0,1)；站型 0 视为关闭 |
| 机型异构 LD/SD | ◐ | 容量 `global_env.py:48-51` 按 slot；半径 `:56-59` 与 duty `:52-55` 按**站型** | 只有"电池容量"真正异质；**续航与航程对两台机相同**（DABS 的 SD 用 large_radius/large_duration）。与官方 Java 一致，但物理上名不副实 |
| 多趟 | ★ | `global_env.py:64, 155, 158`；`scorer.py:126-189`（`routes[si][slot] = [trip,…]`） | 每 slot 一个 trip 列表；RETURN 关闭当前趟 |
| 累计 duty | ★ | `global_env.py:93-97, 156`；`scorer.py:175,184-186` | 跨趟累计、不因 RETURN 清零；上界按站型 |
| 能量 | ★ | `global_env.py:87-92, 104, 166`；`scorer.py:167,173-174` | 按趟计（含回程），目标能耗 + 飞行能耗；换电无时间成本 |
| 返航 | ★ | `global_env.py:74-76, 100-106, 152-161`；`scorer.py:162` | 显式 RETURN 动作；done 要求所有 trip 已关闭；M_return 含最后一段回程 |
| 恰好一次服务 | ★ | 由 `remaining` 集合保证（`global_env.py:79, 170`）；`scorer.py:191-195` 复验 | 重复/缺失都进 issues |
| 完整覆盖 | ★ | `scorer.py:191-195`；`global_env.py:74-76` | 缺失目标 → 不可行；不完整 → `result()` 抛错 |
| 固定部署/站型/target-station | ★ | `scorer.py:269-272`；`global_env.py:235-237` | 不是"软约束"，是 domain 不匹配即不可行 |
| 整图成本 cap（非跨图均值） | ★ | `scorer.py:261-289` | 只有单图接口，无聚合接口 |
| 站内 target-slot / trip / order 联合域 | ◐ | slot 可换（`test_g1.py:104-107`）；trip 划分自由；**target→station 固定** | 与 brief §3.1"站内 LD/SD 的目标归属和路线可按当前协议联合决定"**存在措辞差异**：代码里 target→station 固定，slot 自由。见 §H-2 |
| 站点共享容量（Han 的 Σ_z r[z,b] ≤ N[b]） | ✗ | — | 代码里的 "capacity" 只有电池容量；没有任何"每站可同时服务的机数/预留"约束。brief §G3 把 Han-inspired 共享容量列为**待实现对照**，与代码一致 |
| 换电/充电/周转/发射同步时间 | ✗ | `scorer.py:1-6` 明确"no added" | 换电零耗时；这是**已声明的模型简化**，不是 bug |
| 等待（WAIT） | ✗（静态域） | `global_env.py` 无 WAIT；`emergency_scenario.py:220-227` 才有 | 静态/条件路线域不允许等待 |
| 天气/NFZ 与静态成本合成单一目标 | ✗ | `weather_full_map.py:377-405` 要求同时满足**两个** cap | 没有"W 的单一 evaluator"；W 只能并列表述 |
| 事件日 480 min 时间轴 / 5 min 天气 / 60 min 预报发布 | ✗ | `emergency_scenario.py` 的 horizon 默认 180；`wx_e_forecast_driver.py:42` HORIZON=360 | 原 WX-E 的 480 min / 5 min / 60 min 三件套在代码里都不存在；forecast 是常数元组（见 §G-5/6） |
| 隐藏 phase 的条件采样 | ◐ | `public_phase.py:25-76`（下界式重建，`prediction_only=True`） | 有"公共历史 + 已注册风界"的可审计重建；**不是**真正的私有未来采样；`predictive_sufficiency_proven` 明确为 False |
| 随机事件流 / 需求的联合采样 | ✗（S/W 主环境） | `generator_v2` 只生成静态点集；`emergency_scenario` 的 release 是冻结 fixture | 没有"外生事件流 + 同刻事件闭包"的通用生成器；只有 `make_fixture` 的 4 个 level × seed |

补充的量化事实（由 `problem.py` 默认参数直接算，不是实验）：`small_battery/flight_energy = 0.81/0.018 = 45 min`、`large_battery/0.018 = 55.56 min` 是**单趟飞行时间**的上界；而 duty 上界是 480 / 600 min。因此 duty 约束只有在"同一 slot 完成约 10 趟以上"时才会先于能量触发。**duty 在默认参数下几乎从不 binding**，这解释了为什么 `test_g1.py` 里 duty 相关的两个测试都要把 `small_duration` 调到 6.5 / 7.0 才能构造违反。任何以"累计 duty 是主要瓶颈"为前提的机制假设都需要先做这个量级检查。

---

## E. 逐文件可复用性判定

| 文件 | 判定 | 理由（含证据） |
|---|---|---|
| `return_makespan/scorer.py` | **可直接复用** | 独立 evaluator（不用 dist 缓存、不 import optimizer）；M_return 与 `Check.calculateLatestTime` 同结构；cap/容差/domain 全部 fail-closed。唯一需注意：它的 cost 定义**不等于** `Check.calculateTotalCost`（§C.3），必须作为"本项目定义"冻结 |
| `return_makespan/global_env.py` | **可直接复用**（作为 S 域的 reference env） | 三层 mask + dead_end + terminal validate 完整；RETURN 语义正确；reward = −M_return 可对账。改造点：slot 半径/duty 按站型（若要与"小机短航程"物理一致，必须新增 per-slot 上界——这会改变 evaluator，属于**新合同**，需先冻结） |
| `return_makespan/delivery.py` | **可直接复用** | deadline/raw/fallback/记账完整，且明确不含 anchor 生成时间。仅需在调用侧保证 `started_at` 早于模型加载 |
| `return_makespan/test_g1.py` | **可直接复用**（作为回归基线） | 37 项，覆盖 scorer/env/delivery 三层；不依赖地图数据（只用 `agents/audit/FIXTURES.json` + 合成 instance） |
| `g23<EXECUTION_PATH>` | **需改造** | 机制（SplitMix64 + 顺序条件拒绝 + 无偏 label + 排除碰撞）可复用；但 ①每目标 `energy=0.2 / service=10` 是**常量**，生成图的任务属性完全同质，与官方数据（异质）不同；②site–target 分离只用 **5000 m**（large_radius），不按站型；③metadata 已诚实标注 `exact_author_generator_reproduction=False`、`uniform_over_globally_feasible_map_set=False`。要用于新 population 必须先冻结新的属性分布与可服务性条件 |
| `g24_weather_nfz/weather_oracle.py` | **可直接复用（leg 级物理核）** | `plan_route` 是 finite visibility graph + 简单路 + 精确风积分；明确不插 WAIT、不成环；NFZ 半开区间与切线边界有测试。**不可**当"多目标巡检路线规划器"用（见 §G-2） |
| `g24_weather_nfz/weather_env.py` | **需改造**（仅作玩具/单机诊断） | 单机单站、无 slot、无站型、无 fixed 结构；`M_return = cumulative_duty_min`；每步两次 `plan_route` 全路径枚举，`step` 内又调两次 `observation()`（:286-289）→ 复杂度高，不适合 6 s/12 s 全图预算 |
| `g24_weather_nfz/weather_full_map.py` | **需改造后复用**（W 线最接近主线的多站实现） | 优点：真并行的 per-slot clock、三层 mask、终局独立 replay、`forecast_is_fully_known=True` 诚实标注。缺陷：①`back_min=0 if inbound illegal`（:341）使 mask 只是必要界，可能制造 dead_end；②`weather_cost_cap` 必须外部冻结，环境不生成；③`global_dim = 42 + 9*20 + 7*128` 固定，`>20 slot` 或 `>128 target` 直接拒绝（:239,264-265）→ **大图不可扩展**；④原名 `MAX_POLICY_SLOTS=20` 注释称 10 站 × 2，但 SABS 只 1 slot，20 是上界而非典型值 |
| `g24_weather_nfz/weather_policy.py` + `rl_algorithms.py` | **可直接复用（训练底座）** | pointer + masked Categorical；PPO/A2C/REINFORCE/BC 都在同一 masked 动作空间；BC 明确"只更新策略、不更新 value 头"（:100-110）；`add_gae` gamma/lam 校验。**不构成新机制** |
| `g23/nonrl_baseline/baseline.py`、`mtc_nonrl/latency_baseline.py` | **可直接复用（强 non-RL 对照）** | LPT repack / joint minmax / Smith 规则 / VND/ILS，全部以 `validate_candidate` 为唯一裁判，并走 `finalize_result` 记账。允许非 RL 使用邻域，不违反"RL 不得选算子" |
| `g23/author_baseline/author_runner.py` | **可直接复用（作者锚点）；本机不可运行** | 需要 JDK 与 Java 源码 profile；`prepare/plan/run` 分离、超时回收、hash 锁定。**只在 <COMPUTE_HOST> 或指定环境运行**；本次未运行 |
| `joint_weather_emergency/20261106_complete_fleet_worker/MODIFIED_FILE/*` | **需改造，部分不可用** | 可用：`emergency_scenario`（事件闭包、同刻因果、horizon 截断、duty/energy 失败语义）、`shared_replay_v2.replay`（wind 版独立复算）、`emergency_independent_replay`（stdlib 复算 + 调度顺序校验）、`public_phase`（公共下界重建）、`fast_public_history`（不可变公开帧）。不可直接当"主线环境"：①动作含 **WAIT**；②`Scenario` 无站型/slot/target-station（drone 直接 `station_id` 归属）；③`emergency_scenario` 的 `forecast` 只是常数二元组；④`CompleteFleetRollout` 的 "rollout" 是**已知任务上的贪心补全 + 全 J 比较**，不是未来随机事件的真 rollout（其 receipt 自带 `wind_model='current_wind_persistence_only'`） |
| `20261112_wx_e_forecast_v1/src/emergency_scenario.py` | **与 worker 版同源、少一个功能** | 与 worker 版差异只有 `drone_duty_limits`（per-drone duty 向量）被移除（diff 已核）。引用 W 结果时必须写清用哪份 hash（见 §I-1） |
| `20261112_wx_e_forecast_v1/wx_e_forecast_driver.py` | **不可用作"独立预报发布"证据** | `_forecast_direction`（:58-72）把**初始预报方向**与**当前观测风向**线性融合，`update_weight = min(0.85, 0.28*floor(now/60))`；"hourly public updates" 实际读的是 `obs.wind_now`（观测），不是带 version/valid-time 的发布预报。见 §G-6 |
| `20261112_public_fault_conditioning/MODIFIED_FILE/public_fault_law.py` | **可直接复用（但仅模型层）** | 有限粒子 + 右删失似然 + 零支持显式失败（`IncompatiblePublicHistory`，:162）；`sample_future` 用**同一粒子**抽整组未来以保留相关性（:199-208）；public ledger 保留已服务告警（:69-71, 211-215）。**未接入 simulator/planner**（:1-6 自述），weather likelihood 由调用方给，模块不拟合 |
| `audit/.../published/rl_research/rl_ppo/` | **不可用（违反动作合同）[关闭]** | PPO-DAC 的输出是 `(T 温度, M 修复候选数, F 家族, I 强度, R 重启)` 五头（`rl_ppo/ppo/agent.py:1-5`，`specs.py:1-43`）→ 直接控制搜索算子/强度/重启预算。brief §3.1 明确"不得选择搜索算子、邻域、destroy/repair、算法家族、操作强度、修复预算；换名称也不合规" |
| `.../rl_research/rl_dyn/`（含 `engine/carl/`） | **不可用（算子控制）[关闭]** | `carl/actions.py:1-31`：20 个 operator（loc_open/asg_transfer/route_two_opt/joint_swap_absorb/btl_offload…）× 3 强度 = 60 动作；`neighborhood.py` 1087 行是邻域实现。属旧 CA-RL 宏控制，历史负结果 |
| `.../rl_research/rl_v3/`、`rl_wind/` 的 `engine/lrphsd/` | **部分可复用（evaluator 字节一致）** | `rl_v3/engine/lrphsd/evaluator.py` 与 `source_snapshot/lrphsd/evaluator.py` **SHA256 完全相同**（`ae4f1a…`）；`rl_dyn` 的 evaluator 亦同。但 `rl_wind/engine/lrphsd/problem.py` **不同**（81 行，`9446db…`）→ "同一个 evaluator" 只在 evaluator.py 层面成立，风版 problem 已改 |
| `.../rl_research/rl_rt/` | **需改造（且与固定部署冲突）** | `rt/env.py:1-8` 的动作含 `3*ns` 个 token，token 会开站并选 SABS/DABS → 直接决策部署与站型，违反"部署、站型固定"。构造式注意力+POMO 的**解码骨架**可复用 |
| `.../rl_research/rl_wind/wind/*`（66 个文件） | **关闭 / 仅历史** | 按 brief 与 AGENTS：电量余量、按航次修正、锋面排序等方向已失败；本次未逐行核实，不给正面复用建议 |

---

## F. 现有测试覆盖与真正的缺口

### F.1 `test_g1.py`：37 项，分三层

**ScorerTests（20 项）** —— 断言的是 evaluator 本身：
- `test_parallel_clock_and_all_completion_metrics`（:61-70）：与 `FIXTURES.json` 的 `expected_anchor` 逐字段对齐 operating_minutes / fixed_cost / cost / M_return / M_service / mean / p90 / 每目标 completion。
- `test_original_evaluator_same_cost_and_feasibility`（:72-80）：**新旧 evaluator 对账**（`lrphsd.evaluate` vs `score_solution`）——这是唯一的"两套实现互相验证"测试。
- `test_final_return_is_not_service_completion`（:82-86）：同一解 `M_return=5.0` 而 `M_service=3.0`，明确"返航不是服务完成"。
- `test_global_cap_allows_local_cost_increase`（:88-95）：整图 cap 下允许某站成本上升。
- `test_target_station_fixed_even_with_coverage`（:97-102）、`test_station_type_cannot_change`（:109-112）：domain 锁。
- `test_slot_assignment_can_change`（:104-107）：slot 可换。
- `test_small_station_rejects_large_slot`（:114-116）、`test_closed_station_rejected`（:118-120）。
- `test_cumulative_duty_not_per_trip`（:122-125）：两趟各 1 目标在 `small_duration=7` 下违反 → duty 跨趟。
- `test_sd_at_dabs_uses_dabs_duration`（:127-130）：**把小机在大站用大站 duty 上界固化为合同**。
- `test_trip_energy_not_outbound_only`（:132-135）：能量必须含回程。
- `test_coverage_checked`（:137-140）。
- `test_duplicate_missing_bool_float_and_malformed_fail`（:142-149）：`True/1.0/'bad'/None/{}` 全部 fail closed。
- `test_empty_trips_ignored_but_counted`（:151-154）、`test_hash_missing_or_wrong_rejected`（:156-160）、`test_nan_inf_input_rejected`（:162-166）。
- `test_distance_cache_not_used`（:168-173）。
- `test_anchor_immutable_and_fields_reverified`（:175-180）。
- `test_absolute_tolerance_and_nonfinite_cap`（:182-186）。

**EnvironmentTests（10 项）** —— 断言 step/reward/mask 的因果：
- `test_complete_reward_is_negative_global_makespan`（:190-195）：`reward == -M_return` 且 `reward != -operating_minutes`。
- `test_station_decode_order_does_not_create_waiting`（:197-203）：换 station_order 后 completion/M_return/reward 全等 → "解码顺序不创造等待"。
- `test_global_compensation_route_is_not_pruned_by_local_cap`（:205-209）。
- `test_illegal_and_untyped_action_is_nonmutating`（:211-217）：`RouteAction(0)/RouteAction(True,1)/RouteAction(0,True)/RouteAction(0,999)` 都 illegal，且 step 抛错后 observation 逐字段不变 —— **类型洁癖 + 非变异**。
- `test_done_requires_return`（:219-224）。
- `test_explicit_dead_end_not_completion_certificate`（:226-235）。
- `test_disabled_cost_mask_still_rejects_terminal_cap_violation`（:237-246）。
- `test_active_cost_mask_prunes_known_overcap_prefix`（:248-253）。
- `test_return_preserves_duty_and_resets_energy`（:255-261）。
- `test_old_station_api_remains_cost_based`（:263-267）：旧 API 的 reward 仍是 `-4.0`（cost 域）。

**DeliveryTests（7 项）** —— 断言 deadline/记账（:270-313）：on-time、raw 失败保留 + fallback 计入、raw late + fallback late → 无 ontime 输出、record 组装时间计入、fallback 校验时间计入、`raw_worse_than_anchor` 触发 fallback、非单调时钟被拒。

### F.2 其它测试的实际断言（按文件，摘要）

| 测试文件 | 数量 | 断言的核心性质 |
|---|---|---|
| `g23<EXECUTION_PATH>` | 14 | RNG 参考词一致；cap/family/side/seed 流固定；**谓词边界**；失败保留部分身份；拒绝节点不重启已接受前缀；`randbelow` 无模偏；label cap 失败不改几何；raw+canonical 碰撞 fail closed；**默认排除源必须是 5 类**（official/pilot/author-smoke/v2-synthetic/Windows-probe） |
| `g23/nonrl_baseline/test_baseline.py` | 7 | LPT 在等成本下平衡整趟；joint minmax 不劣于 LPT 且不超 cap；**global cap 拒绝会抬高成本的 split**；deadline 失败不被改写成合法路线；slot/duty 合同；邻域保守恒；SABS 从不用 large slot |
| `g23/mtc_nonrl/test_latency_baseline.py` | 5 | Smith 规则在等 cost/makespan 下降低 MTC；所有方法都返回完整可行且 capped 的解；seed 可复现；候选生成保 target 多重集；deadline 失败保留 raw 且不报 ontime |
| `g23/author_baseline/test_author_runner.py` | 18 | 非连续 id、重复保留为失败、**source cost/clock 不一致必须 block anchor**、NaN cost、Java int32 id 范围、路径按参数传、Windows 才加 .exe、seed 前瞻兼容、plan 只写 invocation 不解、profile 与 accepted manifest 逐字一致、prepare 只复制 hash-locked、**超时 kill 并保留输出但仍 block anchor**、非零退出即便有 witness 也 block |
| `g24_weather_nfz/test_weather_full_map.py` | 23 | 零风回放到原多 slot clock/cost；时间性关闭不掩盖可行 anchor 前缀；**"当前不可返航"可以之后变为可行**；同点目标与 RETURN 保持出发时刻；**交错解码不串行化 slot clock**；SABS 无大 slot 且归属不可移；replay 不耦合主 oracle；**forecast 特征暴露未来时刻表**；主 NFZ 绕行被独立 oracle 复现；风必须覆盖 0；初始 dead_end 有稳定 failure code；**weather cap 边界严格**；原始 anchor cap 是终局准入门；capped observation 不抛异常地屏蔽不可飞候选；主/复算共享 crosswind 边界；forecast 填充 mask 区分"合法零顶点"；策略 global 张量真的含 slot/target 状态表；容量按**活跃物理 slot** 而非站数；NFZ 坐标与策略同坐标系；原成本 cap 同时进入策略状态与候选投影；**无 cap 的终局解不算 weather-admissible**；训练记录零 transition failure |
| `g24_weather_nfz/test_weather_oracle.py` | 12 | 900 m/min 与抽象能量默认值；tail/head/cross 地速；crosswind 不可行与非正前进；跨时间格精确积分；**knot 之后的 crosswind 失败不被隐藏**；直飞在 on 前/off 后；半开区间边界；**切线边合法、内部边在激活时被拒**；绕多边形顶点；**等到达绕行用稳定顶点序 tie-break**；段时连续无隐式等待；无合法路时报告 wind 不可行 |
| `g24_weather_nfz/test_weather_pipeline.py` | 3 | 参考物理 + NFZ + cost + MTC；精确物理 mask 与 env result 一致；rollout 与两种更新都用 masked 可变动作 |
| `g24_weather_nfz/test_failure_reward.py` | 5 | 有界罚项压过可行 makespan 与真实 dead_end；终局 replay 拒绝被罚；λ=1 保持终局失败顺序；零 transition failure 被计数并跳过更新；**PPO/A2C 把 gamma/lam 钉死为 1** |
| `g24_weather_nfz/test_rl_algorithms.py` | 10 | 被排除动作的 logit 精确为 −inf；PPO/A2C 更新有限；clip 比例上报；REINFORCE masked；BC 只用合法动作；BC 提升概率但保留独立 value 偏置；共享 encoder 下 BC **不冻结特征且不动 value 头参数**；BC 遵守过期 deadline；A2C 不依赖 old_logp 也不做 clipping；固定 seed + shuffle 可复现 |
| `g24_weather_nfz/test_weather_author_anchor.py` | 9 | 已核 witness → weather anchor；重执行必须匹配 raw witness / source clock / 成功且有输出；JSON score 整数键按序列化序；重复/冲突键被拒；**手写最小 run 被拒**；solution hash 不匹配被拒；输入路径与超时被语义检查 |
| `g24_weather_nfz/engineering_emergency_causal_memory_20261105/test_memory.py` | 11 | **同一当前观测 + 同一 encoded 张量可以对应不同未来**（service 10 vs 20，`served_at` 11 vs 21，`test_exact_current_observation_alias_and_retained_history_distinction`）；只接受 Observation 不接受 Scenario；不保留未来 release / 未来 trace 句柄；输出变异不回写；当前缺席不删除已知任务；时间回退被拒；矛盾元数据不提交；注入未发布任务被拒；public dispatch 不可变；非法/算子型动作被拒；**明确 `predictive_sufficiency_proven=False`** |
| `20261106_complete_fleet_worker/test_worker.py` | 6 | complete kind 路由到真正的 complete planner；候选包含全部已知任务与返航；独立 replay 与全任务 MTC；legacy fleet 身份保留；worker 硬预算传输；**不把 privileged scene 传给 complete backend** |
| `return_makespan/agents/final_acceptance/test_dynamic_acceptance.py` | 240 行 | 未逐行读取（结构上属动态验收层） |
| `return_makespan/agents/audit/test_root_scorer.py`、`check_product_credit.py` | 196 / 146 行 | 未逐行读取 |

### F.3 **没有测试的关键因果性质**（逐条给"应测什么"）

1. **`M_return` 与 Java `Check.calculateLatestTime` 的对照**：没有。现有测试只对照 `FIXTURES.json` 的 `expected_anchor`（来源需另行核实）。→ 需要一个"官方 Java 输出 latest time ↔ `score_solution` 的 M_return"的差分测试（可在 <COMPUTE_HOST> 用既有 Java profile 跑）。
2. **`cost` 与 Java `Check.calculateTotalCost` 的对照**：没有，而且按 §C.3 两者**定义不同**，不可能一致。→ 应在 PREREG/复现台账中显式写"本项目成本 = lrphsd/scorer 定义（全长序列 + 全部服务）"，并说明与 Java 目标的差异及其对"忠实锚点"的影响。
3. **多图聚合层的"逐图 cap 不得被均值抵消"**：没有聚合器单测。`validate_candidate` 是逐图接口，但没有任何测试断言"一个超 cap 的图不能被 5 个改善图抵消"。→ 需要聚合器 + 一个"3 图里 1 图超 cap"的负例测试。
4. **`StationRouteEnv` 的 dead_end/terminated**：旧 API 没有这两个概念（只有 `done`），也没有测试。→ 若下游仍用旧 API，需明确它不能表达"卡死"。
5. **多次 RETURN 的 duty 复合累计**：只测了"1 目标 + 1 次 RETURN = 3.0"（`test_g1.py:255-261`）。→ 需要"2 趟各 2 目标"的显式累计断言 + "刚好顶到 duty 上界"的边界断言。
6. **`weather_full_map` 的 "RETURN 不清 duty"**：没有显式测试。现有 `test_zero_weather_reproduces_original_multi_slot_clock_and_cost` 只是间接（零风时与静态一致）。→ 需要"有风、两趟、clock 单调"的测试。
7. **联合域的 "RETURN 不清 duty"**：只有 `shared_replay_v2.py:190` 的字符串合同与 `emergency_independent_replay` 的复算，没有"duty 超限必失败"的公开单测。→ 需要"第 2 趟后 duty 越界 → terminal failure"测试。
8. **相位别名的普适性**：alias 只在 `service_energy = 0` 的 fixture 上成立。因为 `_accrue_event` 在服务进行中按 `elapsed/duration` **比例累积能量**（`emergency_scenario.py:400-409`），`service_energy>0` 时 `trip_energy` 会泄漏已服务比例 → 观测可反推剩余服务时长。→ **必须补一个 `service_energy>0` 的反例测试**，否则"两个相同公共快照可对应不同剩余服务时长"的表述过强。这是 §G 里最需要纠正的一条 [未证实→已定位]。
9. **"固定公共前缀 + 改变私有未来 → 规划输出不变"**：没有端到端测试。`test_memory.py` 只测 memory 层不保留未来。`test_no_privileged_scene_passed_to_complete_backend` 只测 worker 不传 Scenario。→ 需要"两个只差私有未来的 episode，在同一公共前缀上 policy(obs) 相同"的测试。
10. **"预报发布前不可见"**：没有，因为代码里 `Scenario.forecast` 是一个常数二元组（`emergency_scenario.py:100`），`trace` 是全程已知的 `_execution_trace`（:311）——**策略看不到 trace，但环境本身没有"发布事件"**。→ 若要声称"独立预报发布"，必须先实现 publication time/version/valid-time，再测"发布前不可见"。
11. **同刻多机不双派**：有（`decisions` 集合 + `emergency_independent_replay.py:103-116` 的 frontier 校验），但只在 2 机 fixture 上。→ 需要 ≥3 机 + 同刻三向分叉的测试。
12. **硬截止返回真实 incumbent 与失败收据**：`delivery` 7 项覆盖得比较完整；但 **6 s / 12 s 整图墙钟**没有任何测试（`test_g1.py` 不含任何地图级 runner）。→ 需要"全图 6 s/12 s + 超时必须落 NO_ONTIME_VALID_OUTPUT"的集成测试。
13. **`M_return` 在 `station_order` 全部排列下的不变性**：只测了 2 个站的两个排列（`test_station_decode_order_does_not_create_waiting`）。→ 3 站 6 排列的等价性测试。
14. **`necessary_cost_mask` 的"必要性"（soundness）**：`test_active_cost_mask_prunes_known_overcap_prefix` 只证明"会剪"，没有证明"从不误剪可行解"。→ 需要一个"随机可行完整解 vs mask 未剪"的性质测试（或反例搜索）。

---

## G. "名字不代表能力"清单

按严重程度排序。每条都给出代码位置，便于复核。

1. **`radius` / `duty_limit` 的名字是站级的，却被用在两个机型上。**
   `global_env.py:52-59` 只有 `self.radius` / `self.duty_limit`（按 station_type）；`scorer.py:153,184` 也一样。结果：**DABS 的小型机（slot 1）拥有 large_radius 5000 m 与 large_duration 600 min**。`test_g1.py:127-130` 把它固化成"合同"。所以"异构机型"在代码里实际只有**电池容量**是异质的；"小机航程短"这件事**没有实现**。与官方 Java 一致（`Check.java:145`），因此不是移植错误，而是**模型本身的简化**——但任何"续航/半径异构"的叙事都必须先改合同。

2. **`weather_oracle.plan_route` 的 "route" 是点到点单腿。**
   它只解 `start → end` 的最早到达（`weather_oracle.py:290-354`），不排序多目标、不含服务时间、不含电池容量、不含返航义务、不含 duty。把它当"多目标巡检路线规划器"会直接错。它的真实能力是：**给定一条腿的起讫与出发时刻，返回考虑时变风与 NFZ 的最早到达与能耗**。

3. **`WeatherRouteEnv` 的 "weather route env" 是单机玩具。**
   单站、单机、无 slot、无站型、无 fixed cost 结构（`weather_env.py:44-54`）；`M_return` 直接等于 `cumulative_duty_min`（:352）；reward 是 `-completion/N`（:321）而不是 makespan 差分。它**不能**代表"多站异构"。

4. **`WeatherFullMapEnv` 的 mask 不是"可完成"，而且它自己承认。**
   `_project_target` 在回程腿当前不可行时把 `back_min` 置 0（`weather_full_map.py:339-341`），注释明说这是 necessary bound；条目 `forecast_is_fully_known=True`（:569）说明这是**全知预报**，不是发布式预报。另外 `global_dim` 把策略状态**定长**到 20 slot / 128 target（:239），超出直接 `ValueError`（:264-265）——名字叫 full map，实际是"冻结上界的 medium map"。

5. **`Scenario.forecast` 名字是 forecast，值是常数。**
   `emergency_scenario.py:100` `forecast: Tuple[float, float] = (0.0, 0.0)`，只在 `make_fixture` 里赋成 `wind[0]`（:892）。**没有发布时间、版本、有效期、误差分布**。因此"预报"在这个模块里等价于"一个已知的初始风向先验"。

6. **`wx_e_forecast_driver._forecast_direction` 是"初始先验 + 当前观测"的线性融合，不是新预报。**
   `wx_e_forecast_driver.py:58-72`：`w = min(0.85, 0.28*floor(now/60))`，`forecast = (1-w)*initial + w*wind_now`。所谓 "hourly public updates" 读的是 `obs.wind_now`（当前观测），**不是被发布的预报**。payload 自称 `hourly_public_updates=True`（:538）容易误读。

7. **`CompleteFleetRollout` 的 "rollout" 不是随机未来的 rollout。**
   它把**已知任务集**用确定性规则补全（`complete_fleet.py:24-54`：按 `(clock, id)` 排序的机、按 urgency/distance 选目标），再用完整 J 比较；其 receipt 自带 `wind_model='current_wind_persistence_only'`、`forecast_is_realized_certificate=False`（:58）。它是**已知任务的完整 incumbent 构造器**，不是"对未来外生事件抽样并续接"。这正是交接 §8 所说"不是未来随机事件真实 rollout"的代码证据。

8. **`public_phase.forecast_public_phase` 是下界重建，不是未来预测。**
   `PublicPhaseForecast.prediction_only=True`、`future_trace_access=False`（`public_phase.py:22-23`）；服务剩余用 `elapsed_lower` 下界（:64-71）。名字里的 forecast 容易被读成"已实现预测未来"。

9. **`causal_task_memory` / `fast_public_history` 的 "causal" 只是"只用已观测历史"。**
   它们不声称 Markov 充分（`causal_task_memory.py:45` `'predictive_sufficiency_proven': False`），也不构造 VFA 后决策态（`route_method_adapter.py:1-6` 自述）。"causal" ≠ "充分状态"。

10. **`generator_v2` 的协议名带 "constraint-reconstructed … uniform-proposal"，但不是作者生成器复现、也不是可行图集合上的均匀分布。**
    metadata 已诚实写出三项 False（`generator_v2.py:368-370`），且每目标 `energy=0.2/service=10` 是常量（:392-393），site–target 分离固定 5000 m（:183）。协议名比能力长。

11. **`rl_algorithms.behavior_clone_update` 名叫 BC，实际只做策略头极大似然。**
   docstring 自述"applies no value loss and does not update value-head parameters"（:100-110），`test_rl_algorithms.py` 还专门断言"共享 encoder 会变、value 头参数不变"。所以"BC 之后 critic 未训练"是设计，不是 bug。

12. **`joint_core.ResidualActor` 名为 actor，初始策略**恰好**是规则先验。**
   零初始化 `query/score_bias`（`joint_core.py:51-52`），因此"initial = prior"是构造出来的；这解释了历史上"六个 actor seed 全选 initial"时"RL 增量未建立"的读法：初始模型与规则在本体上不可区分。

13. **旧 `StationRouteEnv.result()["reward"]` 与 `FullMapRouteEnv.result()["reward"]` 同名不同义。**
   前者 = `-operating_minutes*time_cost`（cost 域，`global_env.py:194-196`）；后者 = `-M_return`（makespan 域，:394-398）。`test_g1.py:263-267` 与 `transaction/probe.py` 正是靠这个差异做 API 判别。任何跨模块读 `reward` 的代码都必须知道自己在哪个域。

14. **`test_g1.py` 名字是 G1，内容是 env/scorer/delivery 的单元回归，不含任何地图质量、Java 对照或墙钟。**
    37 项全部是合成 fixture（`small_instance` + `agents/audit/FIXTURES.json`）。"G1 通过"**不能**推出"evaluator 与 Java 一致"或"策略有效"。

15. **`MAX_POLICY_SLOTS = 20` 的注释称"10 站 × 2"，但 SABS 只有 1 slot。**
    `weather_full_map.py:31-34`。真实上界依赖站型组合；用它做容量论证会高估约 2 倍。

16. **`rl_research` 目录名是"RL 扩展研究"，其主结果是算子/搜索控制。**
    `rl_ppo`（DAC 控温度/候选数/强度/重启）与 `rl_dyn/carl`（60 个 operator×intensity 动作）都不是"物理路线 RL"。按现行合同它们**只能作为历史负结果**引用。

17. **`weather_env.WeatherRouteEnv.dead_end` 每次访问都重算全量 observation。**
    `weather_env.py:134-135` `not any(self.observation()["mask"])`，而 `observation()` 对每个候选调两次 `plan_route`（全路径枚举）。名字只是属性访问，成本是 O(候选×路径数)。在 6 s/12 s 全图预算下这是不可接受的实现方式（这也与 `weather_full_map` 另写一套的原因一致）。

18. **`public_fault_law` 的 "fault law" 不拟合任何东西。**
    它只做"给定冻结粒子 + 外部 weather log-likelihood → 条件权重 → 抽一个粒子 → 按目标独立抽未来"（`public_fault_law.py:120-232`）；`:1-6` 明说 weather likelihood 必须来自另行冻结的公共观测模型，模块不拟合。它是**推断/采样层**，不是模型学习层。

---

## H. 采用版本、冲突与需要上游决定的点

**H-1 [已证实-代码] 三套 M_return 定义并存，不可互换。**
- 静态：`max_s max_slot duty`（`scorer.py:210`），含最后回程，无风。
- 多站天气：`max_slot clock_min`（`weather_full_map.py:226`），clock 由风积分，含回程。
- 联合事件：`max_drones last_return_time`（`emergency_scenario.py:778`），且只在 `complete` 时非 None。
→ 建议：任何"M_return 改善 X%"都必须写明是哪一个；S 合同用第 1 个，W 合同用第 2/3 个并单独注册。

**H-2 [需上游决定] "站内 LD/SD 的目标归属可联合决定"与代码不一致。**
brief §3.1 写"部署、站型、目标所属站固定；站内 LD/SD 的目标归属和路线可按当前协议联合决定"。代码里 `validate_candidate` 把 **`target_station` 完全锁死**（`scorer.py:271-272`），可变的只有 **slot 内顺序与 slot 归属**（`test_slot_assignment_can_change`）。也就是说"目标→站"固定、"目标→slot"自由。若上游希望"目标→站"可变，那是新合同，必须改 evaluator 并重跑全部对照——**不能靠改措辞**。

**H-3 [需上游决定] 1e-7 是"数值容差级"，不是"经济松弛级"。**
见 §C.4 的量级换算：在 1e6 成本上 1e-7 ≈ 860 ulp ≈ 1e-13 相对量，只吸收求和舍入，容不下任何实质退化。因此：①不得把它表述成"允许微小成本上升"；②若研究设计确实需要一个经济上可解释的松弛（例如 0.1%），必须**新增**一个显式相对容差参数并冻结，且与现有 1e-7 数值容差**分开报告**。

**H-4 [需上游核对] "与 Java 成本一致"这一说法在任何现有收据里都找不到支撑。**
`test_g1.py` 只与 `lrphsd.evaluator` 对账；Java 的 cost/duty/energy 用的是"跳过站点边"的另一套函数（§C.3）。→ 建议在 TAKEOVER_AUDIT 里把"Python 可行 ⇒ Java 可行（严格更强）"作为采用的表述，并把"逐位一致"限制到 M_return。

**H-5 [已证实-代码] 两份 `emergency_scenario.py` 有实质差异。**
worker 版（`01d243…`）多出 `drone_duty_limits` / `effective_duty_limits` / `duty_schema` / `duty_limit_for()` 与 fingerprint 的 duty 字段；forecast_v1 版（`43794a…`）没有。引用 W 结果时必须写明用了哪份 hash，否则"duty 上界"的含义会变。

**H-6 [已证实-代码] `rl_wind/engine/lrphsd/problem.py` 与 `source_snapshot` 不同**（`9446db…` vs `f03c2f…`），而 evaluator 三处同 hash。因此"所有子项目共用同一 evaluator"只在 `evaluator.py` 层成立。

---

## I. 未解决缺口（本文件明确不声称解决）

1. 未核实 `agents/audit/FIXTURES.json` 的 `expected_anchor` 是**由 Java 生成**还是由 Python 生成。若来自 Python，则 `test_parallel_clock_and_all_completion_metrics` 是自证而非对照。→ 需要查该 fixture 的 provenance（`g24_weather_nfz/linux_migration_20261104/transaction/*` 与 `reference/java/*` 的 manifest 可能给了来源）。
2. 未核实 120 官方地图复现时是否把 Java cost 与 Python cost 做过差分；本文件只证明"两者定义不同"。
3. 未逐行读 `weather_replay.py`、`fleet_history_controls.py`、`route_trainers.py`、`rl_wind/wind/*`，因此 §E 对它们的判定是"文件级"而非"逐行"。
4. 未评估 `weather_full_map` 的 `plan_route` 全路径枚举在最坏图（4 NFZ 顶点 + 端点 = 6 节点）下的实际 wall time；只从代码结构判断它随顶点数阶乘增长。→ 6 s/12 s 预算下必须实测（在 <COMPUTE_HOST>）。
5. 未检查 `emergency_scenario` 在 `horizontal=180` 之外（如 480 min、5 min 天气格）是否被任何 driver 使用过；只读到默认值与 forecast driver 的 `HORIZON=360`。
6. 未检查 `git` 之外是否存在同名文件的其他副本（如远端 `<EXECUTION_PATH>`），因此"当前主线代码"只在本机范围内确定。

---

## J. 建议的下一项有界工作（每项都有明确产物与关闭条件）

1. **[0.5 人日，本机静态] 建立"M_return/cost 三方对照表"。**
   输入：3 张官方图 + 3 张 g23 图；产物：一张表，列 `score_solution.cost`、`evaluator.evaluate.cost`、手算 `Check.calculateTotalCost` 的"跳过站点边"版、`Check.calculateLatestTime` 与 `M_return`。通过条件：M_return 逐位一致；cost 差异恰好等于"被跳过的站点边 + 末尾目标 service"之和。关闭条件：若差异不可解释，冻结"本项目成本定义"并把 Java 目标标为参考。
2. **[1 人日，<COMPUTE_HOST>] 用已冻结 Java profile 生成 1 张图的 latest time 与 cost 收据**（不重跑 1200），把 H-4 变成 [已证实-收据]。
3. **[0.5 人日，本机] 补 §F.3 的第 5/6/7/8 项测试**（多趟 duty 复合、weather 两趟 clock、联合 duty 失败、`service_energy>0` 的别名反例）。产物：4 个新测试 + 一份"哪些因果性质现在有测试"的对照表。关闭条件：4 个测试全绿；若第 8 项反例证明别名不成立，则把"隐藏 phase"表述降级为"在零服务能耗任务上成立"。
4. **[0.5 人日，本机] 补聚合层负例测试**（§F.3 第 3 项）：3 图里 1 图超 cap，断言聚合结果不得把该图算成改善。
5. **[需上游决定] H-2 与 H-3**：站内归属的可变范围、容差口径。这两项不决定，任何后续"cap 下改善"的比较都可能是不同合同的比较。

---

## K. 一页速查（给上游的最小事实集）

- 动作：`(slot,target)` 5 条合法性、`(slot,RETURN)` 3 条合法性；**RETURN 只清 trip 能量/计时，累计 duty 只增**（`global_env.py:156`）。
- mask：physics ∧ necessary-cost lower bound；**通过 mask ≠ 能完成**（`necessary_mask_is_completion_certificate=False`）。
- reward：`Δpotential`，telescoping 到 `−M_return`；不是 `−cost`。
- cost：`fixed + 0.5*operating`，operating 含**两端站点边**与**全部服务**；能耗不计入成本，只作硬约束；换电/周转/同步时间为 0。
- M_return：`max_s max_slot Σ_trip(往返飞行时间 + 服务时间)`；与 `Check.calculateLatestTime` 同结构，依赖 `station.service==0`。
- 容差：`1e-7` **绝对**（@1e6 约 860 ulp / 1e-13 相对）——只吸收舍入，不是经济松弛。
- 未实现：站点共享容量、换电时间、WAIT（静态域）、发布式预报、事件日 480 min 时间轴、per-slot 航程/duty 异构、跨图聚合器。
- 不可用（违反动作合同）：`rl_ppo`（算子 DAC）、`rl_dyn/carl`（60 operator×intensity）、`rl_rt`（会选站型/开站）。
- 测试：`test_g1.py` 37 项全绿是"evaluator+env+delivery 的单元回归"，**不是**质量或 Java 一致性证据；14 项关键因果性质仍无测试（§F.3）。
