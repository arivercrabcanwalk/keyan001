# Weather/NFZ 实施后科学审查

日期：2026-11-04（Asia/Shanghai）  
审查性质：只读；未修改源码、已有结果、协议、数据或状态。  
范围：`g24_weather_nfz` 的 README、实验/设计/文献/实现审计、远端状态、Windows 清单、当前 `STATE.json`，以及 `full_map_smoke_20261104/full_map_smoke_report.json`、当前实现和测试。

## 结论

没有发现把现有 smoke 数值写成“作者算法胜负”、RL 优越性、正式实验或天气实飞结论的已发生表述。相反，README、实验协议、JSON `scope` 和项目状态均将其限定为合成工程夹具；现有全图 smoke 的六个学习输出也全部没有优于其**合成**共同锚点的 `M_return`。因此，本包不能作为作者算法比较、PPO/A2C 胜负、强非 RL 胜负或 G3--G5 证据使用。

但有三个 P1 的研究登记/可复现性阻塞项，以及两个 P2 的文档/动作口径问题。它们不改变当前的“工程 smoke only”定位，也不提供 G4 训练或正式试验准入。

## 已核实的结果边界

- `full_map_smoke_report.json` 的 schema 是 `weather_full_map_synthetic_smoke_v1`，且 `scope` 明确为“synthetic engineering fixture only; not an author-map, registered, or formal result”。其 anchor kind 是 `synthetic static-route anchor replayed through common weather oracle`，不是 Liu 作者在新研究地图上的 `R_Liu`。
- 合成锚点 `M_return=4.769978` 分钟、weather cost `77.632517`。PPO 三 seed 的 `M_return` 为 `7.045658`、`7.114615`、`6.686363`；A2C 三 seed 为 `7.045658`、`7.114615`、`6.409009`。全部经 report replay 标记 `admissible=true`、cap satisfied，但均劣于该合成锚点的 `M_return`。这只是 smoke 的负向工程观察，不能汇总为算法效果。
- 多站 V1 的 reward 和报告终点是 `M_return`，`MTC` 是次级报告项；单站旧夹具的 `-MTC` smoke 不得支持 V1 主端点。该隔离在 `README.md:11,18-21`、`EXPERIMENT_PROTOCOL.md:20-22` 和 `DESIGN_REVIEW.md:79-95` 中写得明确。
- 当前 `STATE.json` 仍为 `G2_V2_FINITE_GRID_AUDIT_AND_METRIC_FREEZE_PENDING`，`new_development_maps=0`、`new_training_calls=0`、`new_formal_maps=0`，且 `root_freeze_complete=false`。故不存在可被重新命名为 weather/NFZ 作者比较的数据集或训练结果。

## P0

无已确认的 P0 科学表述错误。

特别地，未发现把合成天气锚点称作 Liu 作者算法的**胜利**，或从 smoke 推出 PPO、A2C、RL、强基线、MTC 或 `M_return` 的优越性。README `:21,50,61`、实验协议 `:30-32`、本地文献审计 `:76-79,90,94` 和 full-map report 的 scope 都明确禁止这些推断。

## P1

### P1-1：合成锚点在 README/runner 中仍有“author”措辞，容易被错误转写为作者基线

**证据。** `README.md:21` 将 full-map smoke 写成对比 “author-route anchor”；`run_full_map_smoke.py:131-134` 的变量和错误信息分别为 `author_weather` 与 “synthetic author anchor”。但同一 runner 只在 `fixture()` 中手写了五目标 synthetic instance 和 route（`:39-58`），并在 report 中把 anchor 定义为 `synthetic static-route anchor replayed through common weather oracle`（`:150-157`）。项目主协议要求的作者锚点则是每张**新开发图**上的 Liu 完整可行输出 `R_Liu`，逐图 `C_candidate <= C_Liu+1e-7`（`return_makespan/STATE.json:38-45`；`ROUND_DECISION.md:11`）。

**影响。** 现有 scope 防止了当前报告成为错误的胜负声称，但 “author-route/author anchor” 的命名会使后续摘要、图注或人工转述把 synthetic route 误当成作者方法。该锚点没有作者 J1b 运行、作者输入 hash、作者完整输出或注册地图身份。

**准入要求。** 任何研究材料应一律称其为 `synthetic static-route anchor`；只有保存了每图 Liu 输出、天气口径和 hash 的注册 protocol 才能使用 `R_Liu`/author anchor。不得以本 smoke 取代该证据。

### P1-2：不存在已冻结的天气研究数据、完整比较族或公平预算账本；smoke 不能比较 PPO/A2C/非 RL

**证据。** runner 只允许 `--smoke`（`run_full_map_smoke.py:166-175`），包含一个手写 five-target fixture（`:39-58`），一条 greedy rule（`:68-84`），以及每算法三 seed、4 updates、每 update 8 episodes（`:36,105-160`）。它没有 author runner、random/beam/强 weather-aware non-RL、6 s/12 s 计时、checkpoint validation rule、地图 manifest、拒绝/失败分母或 bootstrap；`STATE.json:118` 也明确要求先冻结这些项目，且 `g23_protocol_audit.root_freeze_complete=false`。

`DESIGN_REVIEW.md:143-162` 正确规定将来的相同信息基线、共同 anchor、冷启动全开销、三训练 seed、base-map 统计单位和全冻结 Formal，但这些是**待执行规范**，不是当前 smoke 已满足的事实。PPO 使用 `ppo_update(... epochs=2, minibatch=32)`，A2C 使用一次 `a2c_update`（`run_full_map_smoke.py:115-117`）；在未记录相等优化计算/墙钟的情况下，二者也不能被解释为公平算法排名。

**影响。** 当前 report 中所有六条学习路线相对合成 anchor 的 `M_return` 均更差，仍不能将其视为有统计意义的 PPO/A2C 失败比较；反过来，A2C seed 307 比 smoke greedy 更低的 `M_return` 也不能被摘取为 RL 胜出。更不能将任何结果与 Liu、最强 same-objective non-RL 或正式域相比较。

**准入要求。** 在任何天气质量运行前，按 `DESIGN_REVIEW.md:145-162` 和项目 `STATE.json:118` 冻结 scenario schema/generator/hash、base-map split、author-or-weather-ref anchor 口径、失败分母、方法/seed/checkpoint 选择、6 s/12 s 全 wall-clock ledger、全部同信息 controls、成对 base-map bootstrap。weather 方案若选 `R_ref^F`，只能做独立天气域的条件比较，不能声称直接击败未扩展 Liu（`DESIGN_REVIEW.md:99-106`）。

### P1-3：Windows 可复现实验尚未完成

**证据。** `REMOTE_EXECUTION_STATUS.md:7-10` 记录 <COMPUTE_HOST>、Windows reverse tunnel 和 Windows LAN 均不可达；`:14` 只确认本机 PyTorch/NumPy 完成单站测试和 smoke，远端结果数为零。`WINDOWS_RUNBOOK.md:3-14` 明示 Windows 接入恢复后仍要建立环境、运行完整测试与 `run_full_map_smoke.py`，并保存版本、GPU 查询、stdout/stderr 和 checkpoint。实现审计也确认没有 Windows Python、GPU 或项目路径清单（`IMPLEMENTATION_AUDIT.md:199-220`）。

**影响。** 当前通过的本机 27 项测试不能成为 Windows、GPU、clean-host 或跨平台可重复性的证据。它不妨碍把当前工件保留为本机 smoke，但阻止将其描述为 Windows 验证完成。

**完成条件。** Windows 可达后，完成 runbook 的受控 venv 安装、27-test suite 与 synthetic full-map smoke，保留 Python/PyTorch/CUDA/GPU、命令、完整 stdout/stderr、report 和六个 checkpoint；该完成仍不授权生成研究地图、训练质量矩阵或 Formal。

## P2

### P2-1：若干审计段落已被当前 full-map 实现和测试超越，需避免继续当作当前代码事实引用

**证据。** `DESIGN_REVIEW.md:170-173` 与 `IMPLEMENTATION_AUDIT.md:22-70,105-120` 把“只有单站/单槽、没有 full-map runner/独立 replay”列为当前 P0。当前代码已有 `WeatherFullMapEnv` 的固定 target-station、LD/SD slot、并行 clocks（`weather_full_map.py:218-270,329-363`）、独立 `weather_replay.py`（不 import 主 route planner，`:1-7,175-216`）和相应测试。复核命令

```text
python -m unittest -v test_weather_pipeline.py test_weather_oracle.py test_rl_algorithms.py test_weather_full_map.py
```

于本审查中退出码 0，`Ran 27 tests in 1.110s`，其中包括 zero-weather multi-slot parity、station interleaving 不串行化、fixed ownership、未来预报特征和 primary-oracle 解耦（`test_weather_full_map.py:46-110`）。

**影响。** 旧审计所列的**研究登记**缺口仍然成立，然而“当前只有单站/共享 oracle”的实现判断已经不准确。混用新旧文档会令后续科学评审得到相互矛盾的实现状态。

**处理。** 将旧 P0 表格标为 pre-full-map historical finding，或给出 superseded-by 文件/测试链接；不得删除其历史证据，也不得把已通过的工程测试升级为研究结果。

### P2-2：多站动作的 station 字段与文字中的“station 非策略动作”需要明确定义

**证据。** 设计审查要求 station 为固定环境解码顺序、日志导出为 `(slot,target)`/`(slot,RETURN)`（`DESIGN_REVIEW.md:41-49`）。现实现的 policy action 是 `WeatherMapAction(station_idx, slot, target_id)`（`weather_full_map.py:33-41`），而 action list 同时列出所有 station 的候选（`:357-363`）。目标不能跨站：`_legal` 仅允许 `target_id in remaining[action.station_idx]`（`:329-345`），且 replay 会拒绝 `target_station_changed`（`:115-210`），所以没有发现算子选择、跨站重新分配或预算控制。

**影响。** `station_idx` 目前可解释为固定 owner 的物理 route-state 标识，而不是站点部署/归属动作；但文档没有明确把这一投影与跨 station interleaving 的不变性写成日志契约。后续若把字段称为“station selection”，会违反项目的固定外层边界。

**处理。** 在注册 schema 中声明 `station_idx` 是 immutable owner/state key，记录它不允许 target-station 改变，并保留 decode-order/invariance test；任何新的 station deployment、station-type 或 target-to-station 决策均需独立协议，不得进入 PPO/A2C 输出。

## 文献与指标审计结论

- 文献解释目前是保守的：`DESIGN_AND_LITERATURE_AUDIT.md:12-16` 和 `LOCAL_LITERATURE_AUDIT.md:19-31,72-79` 明确 wind/NFZ、target/RETURN、mask、attention、PPO/A2C 或 MTC 都不是新颖性主张；DPTARL 的数字不被迁移到 LRPHSD；旧 Route-RL PPO 负结果不被用来选择 A2C 或推断普遍无效。未发现需要更正的文献胜负归因。
- `M_return` 是 Liu 已有 latest-completion 语义，项目状态明确它不是新指标；weather V1 也将其保持为主端点。MTC 仅能作为预先冻结的 secondary target-latency statistic，不能以单站 `-MTC` smoke 或单条合成路线取代 `M_return`。未发现当前文档把二者混为一谈。
- 当前天气模型只支持 fully known deterministic forecast、一块 buffered convex NFZ、uniform piecewise wind 和 no WAIT。它不支持 weather uncertainty、真实飞机能耗、一般动态空域、紧急任务或在线重规划（`README.md:20-23`；`EXPERIMENT_PROTOCOL.md:9-15`）。该边界目前陈述正确。

## 最终状态

保留该模块为隔离的合成工程 smoke。完成 P1 的注册冻结和 Windows 可复现性之前，不得用其产物支持作者算法胜负、PPO/A2C 排名、RL 独立贡献、强非 RL 比较、MTC 主结论、`M_return` 改进、天气不确定性或投稿级结论。
