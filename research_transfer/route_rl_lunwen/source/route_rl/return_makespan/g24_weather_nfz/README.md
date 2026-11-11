# 参数化风场与临时禁飞区路线 RL 工程包

## 已实现范围

这个目录是与现有 LRPHSD 原模型隔离的、区域无关的参数化天气工程包。它不改变 `source_snapshot`、原 evaluator、既有 G1/G2 结果或已冻结的作者基线。

- 单站工程夹具的物理动作只有 `RouteAction(target_id)` 与 `RouteAction()`（RETURN）；策略不会选择搜索算子、邻域、算法或计算预算。
- 以 `900 m/min = 15 m/s` 为空速，风场为时间分段常向量；每条航段在风速切换点精确积分。
- 临时禁飞区是凸多边形，在半开时段 `[on_s, off_s)` 生效。路径在端点和多边形顶点形成的可见图中枚举，不暗中插入等待。
- 目标动作只有在飞抵、服务并保留返站所需的电量、累计 duty 和全图成本下界均可行时才合法。横风超过空速、沿航迹非正推进、活跃禁飞区交叠都会被掩码排除。
- 奖励在每一个目标服务完成时加 `-completion_time / N`，整条完整轨迹的回报即 `-MTC`；其中 `MTC = mean(target completion time)`。最终仍需 RETURN，且完整方案单独重放并检查成本上限。
- `weather_policy.py` 是可变动作集 pointer actor-critic；`rl_algorithms.py` 提供同一掩码动作语义下的 PPO、同步 A2C 与 REINFORCE 更新。

## 多站固定外层扩展（V1）

在完成本地全文与在线一手来源审计后，V1 选择**预报已知的日内临时凸禁飞区**，不把紧急到达任务或跨日周期任务混入该问题。原因和文献边界见 `LOCAL_LITERATURE_AUDIT.md`、`DESIGN_AND_LITERATURE_AUDIT.md` 与 `DESIGN_REVIEW.md`。

- `weather_full_map.py` 固定原 LRPHSD anchor 的站点、站型和 target-station 归属；其动作仅为 `(station, slot, target)` 或 `(station, slot, RETURN)`。DABS 有 LD/SD 并行槽，SABS 仅有 SD；每个槽拥有独立物理时钟和多趟状态，主奖励的望远镜和为 `-M_return`，MTC 仅作为次级报告项。
- `weather_replay.py` 独立实现风 knot 积分、严格内部禁飞重叠和可见图枚举。`replay_weather_solution` 不读取环境状态或调用主环境使用的 `plan_route`，并同时调用原 scorer 检查未改变的 LRPHSD 解语义。
- V1 是完整预报、单一调用方缓冲的凸 NFZ、均匀分段风、无 WAIT 的参数化仿真。它不是随机天气、真实机型能耗、一般动态空域、线上紧急重规划或 Formal 实证。
- `run_full_map_smoke.py` 以共同天气重放的 synthetic static-route reference 为严格成本 cap，对比该 reference、规则 greedy、PPO 和 A2C。该五目标合成运行只验证接口和失败保留，不能代替作者地图的比较。

这里的风、能耗和禁飞区参数是可复现的工程夹具，不是某地区天气记录、机型认证包或实飞安全结论。

多站动作中的 `station_idx` 是固定 target owner 和该 owner 的物理 slot state 的不可变键。它不表示站点部署、站型选择、跨站目标分配或任何算子选择；不同站 action 的交错解码也不会改变各槽在 `t=0` 开始的独立时钟。

V1 policy observation feeds a fixed-width Markov tensor to every policy/control:
known wind/NFZ values plus padding masks、原始 LRPHSD 成本 cap 和当前必要下界、每个 slot 的位置/时钟/能耗/开航程/原模型累计时间，以及每个 target 的坐标/服务/能耗/固定 owner/未服务标记。每个动作候选还包含其执行后的原始成本余量。当前工程 schema 上限为 20 个 physical slots 和 128 个 targets，覆盖冻结 Liu-family 的最大 `10_110` envelope（十处 DABS 时 20 slots）；超过上限会显式拒绝，而不是静默截断。

## 目录

| 文件 | 用途 |
|---|---|
| `weather_oracle.py` | 风速积分、禁飞区几何和最早到达可见路径 |
| `weather_env.py` | 单站、多趟的物理路线环境和独立重放评分 |
| `weather_full_map.py` | 固定外层的多站 LD/SD 并行槽环境、`M_return` 势差奖励和完整候选导出 |
| `weather_replay.py` | 不依赖环境/主 oracle 的第二套风/NFZ 路径重放 |
| `formal_contracts_20261105/` | 可执行 weather/emergency 不变量证明、源码哈希和 JSON 收据 |
| `WINDOWS_BUNDLE_V15_VERIFICATION.md` | 当前源构建的 64-file CPU bundle、Win313 依赖哈希锁、replay 边界事务与 2,178-check release audit；Windows 执行仍待外部主机 |
| `current_release_audit_20261105/` | 当前天气/紧急源、形式化合同、回滚与 V14 payload 的绑定审计 |
| `paper_readiness_audit_20261105/` | 机器可重跑的论文准入审计、证明边界与 G4-G8 blocker 证据；当前为 NOT_READY_FOR_CLAIMED_RL_PAPER |
| `weather_policy.py` | 只对目标/RETURN 打分的 actor-critic |
| `rl_algorithms.py` | 掩码 PPO/A2C rollout 更新 |
| `run_experiment.py` | 三个固定 seed 的真实端到端烟雾训练 |
| `run_full_map_smoke.py` | 多站固定外层的 PPO/A2C/规则基线合成烟雾训练 |
| `smoke_20261103/` | 已运行的工程烟雾报告和完整 JSON 轨迹 |
| `EXPERIMENT_PROTOCOL.md` | 注册地图实验接入规则与禁止混用项 |
| `REMOTE_EXECUTION_STATUS.md` | 远端 Windows/<EXPERIMENT_SERVER> 连通性实测记录 |
| `linux_migration_20261104/<EXPERIMENT_SERVER>_execution_20261104/` | <EXPERIMENT_SERVER> v1-to-v2 开发批次的冻结收据、J1b、训练和比较输出 |

## 复现命令

```bash
cd <LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/g24_weather_nfz
python -m unittest -v test_weather_pipeline.py test_weather_oracle.py test_rl_algorithms.py test_weather_full_map.py
python run_experiment.py --smoke --output-dir smoke_20261103
python run_full_map_smoke.py --smoke --output-dir full_map_smoke_20261104
python3 formal_contracts_20261105/verify_contracts.py
```

第二条命令只运行已经声明为 synthetic engineering fixture 的五目标烟雾案例。它并不执行原项目的注册地图、强非 RL 比较、质量矩阵或 Formal。

## 已运行烟雾结果

固定实例有 5 个目标、三段风 `(2,0)`, `(-3,4)`, `(1,-2) m/s`，切换时刻为 `0/180/420 s`；凸禁飞区在 `[45,390) s` 活跃。确定性最近可行目标参考解为 `[[4,3,0,1,2]]`，独立重放结果为 `MTC=7.307852 min`、`M_return=14.544162 min`、`cost=16.544162`。烟雾成本上限预先设为该参考成本的 `1.25`，即 `20.680202`。

| 算法 | seed 103 | seed 211 | seed 307 |
|---|---|---|---|
| PPO | 无完整贪心输出，已保留 | 完整，MTC 8.189062，cost 17.569709 | 完整，MTC 7.307852，cost 16.544162 |
| A2C | 无完整贪心输出，已保留 | 完整，MTC 8.189062，cost 17.569709 | 完整，MTC 7.307852，cost 16.544162 |

这些数值只证明物理环境、两种更新路径、失败保留和重放验证实际运行。它们不是算法效果、区域天气效果、强基线胜出或 Formal 结论。
