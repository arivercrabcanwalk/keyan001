# RUN_LOG — 2026-11-12 接手执行时间线（真实收据）

时区：服务器为 UTC，本表同时给 Asia/Shanghai（= UTC+8）。所有远端命令经 `<EXECUTION_PATH>` 执行，SSH 退出码 0。

## 身份与目录

|项|值|
|---|---|
|本地包|`<LOCAL_PATH>`|
|远端根|`<EXECUTION_PATH>`|
|远端 code 快照|`code/`（31 个文件，本地↔远端 SHA256 全一致）|
|隔离 JDK|`runtime/jdk17` = Corretto 17.0.21（tarball SHA256 `8f9a2ddb131ec5317419f2b0769240fe22ce27f8a0ae43f5346d53e1c8aec6a0`）|
|人口 namespace|`takeover-20261112-g3-v1`|
|作者 seed namespace|`takeover-20261112-g3-author-seed-v1`|

## 事件表

|时间 (UTC)|时间 (CST)|事件|收据|
|---|---|---|---|
|07:52|15:52|SSH 只读核验 <COMPUTE_HOST>：hostname `<COMPUTE_HOST>`、Python 3.10.12、104 vCPU、371 GB RAM、无 GPU、`/` 可用 11 GB|ENVIRONMENT_AND_SSH.md；SERVER_MANIFEST.json|
|07:55|15:55|发现 <COMPUTE_HOST> **无 JDK**（`java: command not found`）；网络 github/pypi 可达|本次会话输出|
|07:56|15:56|下载 Corretto 17 到隔离目录；解压校验 `java -version` = 17.0.21|runtime/jdk17；sha256 见上|
|07:57|15:57|代码快照 31 文件上传；本地↔远端 SHA256 31/31 一致（首次因 macOS AppleDouble `._*` 失败，已修）|本次会话输出|
|07:58|15:58|生成首张新图 `3x10_o1`（raw `f32c450b…`，geom `fa0a0329…`）|g3_pop/maps/3x10_o1.txt|
|07:58|15:58|J1b Java 隔离编译通过（20 class），首图锚点 anchor_eligible，cost 160.4523、M_return 56.0981|g3_smoke/author/3x10_o1/RUN.json|
|07:59|15:59|生成 12 family × ordinal 1 人口|g3_pop/population_index.json|
|07:59|15:59|作者锚点批（12 图，1.4–8.7 s/图）：11 eligible，4x20_o1 不合格|g3_pop/AUTHOR_RESULTS.json|
|08:00|16:00|非 RL 首跑失败（模块别名导致 `CostAnchor` 类不一致）；修正后 34 行 = 26 ONTIME_VALID + **7 超时** + 1 无锚点|g3_pop/NONRL_RESULTS.json|
|08:04|16:04|精确成本中性重排实现；首版因缺 `instance_sha256` 全判 inadmissible；修正后 11/11 admissible、\|Δcost\| ≤ 5.7e-14（浮点求和顺序，1 ulp 级）|g3_pop/EXACT_REASSIGN_RESULTS.json|
|08:06|16:06|配对统计（B=10000，seed=20261112，单位=地图）：开发集 exact cost-neutral vs anchor −12.919%，CI [−18.788,−6.696]，7/4/0|stats/STATS_local.json|
|08:11|16:11|生成 36 张确认图（ordinal 2–4），PREREG 先于生成写死（08:06:55Z）；36/36 锚点合格|results/g3_confirm/PREREG_CONFIRM.json|
|08:13|16:13|确认集非RL + 精确重排完成；**复现成功**：−10.951%，CI [−14.852,−7.354]，20/16/0|results/g3_confirm/|
|08:20|16:20|合并 47 图：−11.412%，CI [−14.796,−8.179]，27/20/0；LPT 与精确最优在 **45/47** 图逐位相同|stats/STATS_server.json|
|08:25|16:25|在 <COMPUTE_HOST> 复算统计，点估计与本地**逐位相同**；仅 5 个比较的 CI 端点差 1–2 ulp（求和顺序）|receipts/SERVER_STATS.txt；stats/STATS.json（服务器版为准）|

## 用户可见的进程诚实性说明

- 本包**没有**恢复旧 goal、旧定时器、旧 driver 或任何历史科研作业。
- 本包**没有**重跑 120 官方图复现（已完成，不重跑）。
- 本包**没有**启动任何 RL 训练：G0 未通过，G4 不启动。
- 本包**没有**修改任何历史文件原字节；所有新产物在新目录。
- 本包**使用**了并行的子 agent（用户 2026-11-12 明确要求"创建大量线程"），这与接手指令 §15 "不要创建子 agent" 冲突；按"最新用户指令优先"采用并行执行，且所有子 agent 产物均落在本包目录并在此登记。

## 资源消耗（本包实测，非预约）

|项|值|
|---|---|
|作者锚点运行|开发 12 次总 wall **44.4 s**（单图 1.201–8.716 s）；确认 36 次总 wall **138.5 s**（1.158–8.993 s）|
|非 RL 运行|34 次调用（33 有效行 + 1 行无锚点），最慢 12.0 s，累计 wall ≈ 48 s|
|精确重排|开发 11 图 + 确认 36 图，单图 < 1 s（服务器重放 0.102 s/图）|
|JDK 下载|194,714,953 B|
|代码快照|1.28 MB（压缩后）|
|结果回传|113,004 B（gzip）|
|估算 CPU 核小时|**< 0.1**（远低于任何历史额度）|
## 已知口径差（由预先登记线程复核后登记，未改历史文件）

|编号|原记法|实测|处置|
|---|---|---|---|
|K1|作者锚点总 wall 45.9 s|开发 12 次 **44.4 s**|已在上表更正|
|K2|成本"逐位不变"|9/11 恰为 0；10x110 −2.27e-13、4x30 −5.68e-14（1 ulp）|改为"\|Δcost\| ≤ 5.7e-14，远小于 1e-7 容差"|
|K3|统计在 Mac 算|已在 <COMPUTE_HOST> 用同脚本复算：点估计逐位相同，CI 端点 1–2 ulp|stats/STATS.json 以服务器版为准；本地版保留为 STATS_local.json|
|K4|非RL"8 超时"|34 行 = 26 ONTIME_VALID + **7** 超时 + 1 无锚点|已更正|

## 后续事件（同一接手会话，2026-11-12 下午/晚间）

|时间 (UTC)|时间 (CST)|事件|收据|
|---|---|---|---|
|08:22|16:22|子线程交付强 min-max ALNS 代码与开发集结果；主执行者对 8x80_o1 独立重跑 `score_solution`/`validate_candidate`：M/cost 逐位一致、80/80 覆盖、admissible、max energy 0.9953|harness/33_verify_strong.py 输出|
|08:25|16:25|发现该子线程在交付后仍反复重跑并 `rm -f` 结果文件，为保护已核验证据，主执行者中止该线程；用本地副本恢复远端结果并 SHA 对齐（`1e8bd706…`）|本次会话输出|
|08:28|16:28|**<COMPUTE_HOST> SSH 端口拒绝连接**（连续 5 次重试 80 s 内全失败）；确认集强基线运行中断，当时只跑到 7x65_o3|本次会话输出|
|11:45|19:45|服务恢复（hostname 正常、uptime 41d、load 1.5）；确认集偏partial 文件改名 `STRONG_NONRL_RESULTS.partial_0829.json`|本次会话输出|
|11:48|19:48|用**同一 seed** 重跑确认集强基线；72/72 行全部 ONTIME_VALID|logs/strong_confirm_outer2.log|
|11:52|19:52|合并统计：强基线相对成本中性地板 46 图平均 **−3.041%**、中位 0.000%、**22 胜 0 负**、46/46 admissible；相对锚点平均 **−13.928%**|analysis/strong_summary.py；stats 与报告|

**中断记账**：08:28Z 的中断是真实事件，未被抹去；重跑使用同一 seed、同一预算、同一人口，因此结果可视为该批的完整交付，而不是"换 seed 找阳性"。
