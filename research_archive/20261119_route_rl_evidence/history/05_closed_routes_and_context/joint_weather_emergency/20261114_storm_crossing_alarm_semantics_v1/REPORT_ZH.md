# 风暴离开时刻驱动告警：有界因果语义修正

## 问题与决定

原 `CausalEngine` 在目标 `SERVICE_END` 时刻写入 `alarm_time = service_done + delay`。这使同一天气轨迹下，策略改变目标服务顺序也会改变“外生”天气告警发布时间，与 WX-E 的“移动风暴单体离开目标后 0–20 分钟”合同不符。本包把场景接口改为隐藏的绝对风暴离开时刻 `storm_crossings=(t_exit,target)`，并在粒子/引擎初始化时按 `t_exit + delay` 预排告警。`trailing_edge_exit_time` 通过移动旋转椭圆与固定目标的二次交点精确计算尾缘退出时刻，并拒绝切线、未穿越与在active window结束前未退出的伪退出。

工程夹具将椭圆中心从目标右侧250m处以10m/min向左移动，半径100m，解析得到尾缘退出`35` min，延迟5 min。两种合法 TARGET 顺序令目标1首次服务时刻分别为`20`、`30`。基线分别在25/35 min释放告警；修正版两分支都在40 min释放。初始前缀中已到期事件即时可见；若首次物理服务发生在告警开放之后，该次服务同时填入基础目标`served`。

## 先例与实验设计边界

动态车辆路径研究已把随机到达任务与路线重算作为标准设置；灾后 UAV 调度也已有滚动时域/MIP、插入启发式和大邻域搜索比较。因此本改动不主张算法新颖性，只修正事件过程的外生性，后续比较必须让所有策略共享同一完整天气轨迹、风暴退出时刻、故障抽样和延迟抽样。

- Botros et al., *Optimizing Task Waiting Times in Dynamic Vehicle Routing*, RA-L 2023: https://autonomousrobots.nl/assets/files/publications/23-wilde-ral.pdf
- *The scheduling problem with delivery and observation in collaboration after the disaster*, Swarm and Evolutionary Computation 2025: https://www.sciencedirect.com/science/article/abs/pii/S2210650225002056

风暴损害建模的主来源还表明，基础设施失效风险通常按随时间/位置变化的天气暴露危险率或风速fragility建模，而不是统一、与风暴强度无关的常数概率：Panteli et al., *Power System Resilience to Extreme Weather: Fragility Modeling, Probabilistic Impact Assessment, and Adaptation Measures*, IEEE TPWRS 2017, https://doi.org/10.1109/TPWRS.2016.2641463; *Probabilistic Resilience Analysis of the Icelandic Power System under Extreme Weather*, Applied Sciences 2020, https://www.mdpi.com/2076-3417/10/15/5089. 这些来源不提供本项目的UAV故障率或延迟参数，但支持下一步把抽样风险条件化于共同风暴轨迹的时空暴露。

上述来源支持动态任务/滚动重规划与强基线选择，不证明本项目的事件参数、物理模型或算法贡献。

## 有界范围

- 仅一个 target 在单个 episode 中有至多一次风暴单体退出记录；多单体/重复退出不隐式折叠，输入直接失败。
- `storm_exit_time` 必须由上游天气轨迹生成器按“尾缘离开目标”给出；本包没有实现其几何计算，也未校准风暴轨迹、故障率或延迟分布。
- 事件记录仍是隐藏粒子数据；策略仅在 release 到达时看到 OPEN/high。
- 现有 W 指标仍按静态 target ID 评分；alarm job 独立 deadline/分母和 CVaR 记录未在本包解决。
- 不运行训练、作者求解、ALNS、Formal 或新科学地图；G0/G3状态不变。

## 验收

双机竞态覆盖两个时点。事件在目标飞行/服务期间释放时，基线把预留目标显示为`OPEN`并允许第二架机重复派发；修正版保持`IN_FLIGHT`，只保留一次派发，并在原服务结束时结清告警。基础任务完成后告警才释放时，基线的重访没有新建reservation，仍允许另一slot重复派发；修正版对每次TARGET（包括重访）都设reservation，只发生一次告警重访派发。

<REMOVED_ENDPOINT>手写物理夹具显示：基线在20/30 min服务下分别于25/35 min释放告警；修正版在相同几何推出的35 min退出和5 min延迟下均于40 min释放。双机负控中，在途告警释放的累计同目标派发为基线2、修改版1；基础服务结束后再释放告警，累计派发为基线3、修改版2（1次基础访问+1次重访）。修正版T1–T12共77/77断言通过，四个修改源码文件编译通过；另副本四个源码文件回滚至基线hash并重现两种基线竞态。

最终旋转椭圆回归发现旧测试使用`== 40.0`比较解析浮点值，<REMOVED_ENDPOINT>返回`39.99999999999999`。测试判据改为绝对误差`<=1e-12`；保留原失败收据，不改几何或环境参数。2026-11-13 18:38Z在<REMOVED_ENDPOINT>单测T11为6/6，完整T1–T12为78/78，四文件`py_compile`、基线/修改版双机竞态夹具和独立副本回滚均通过。旧精确相等失败仍在`runs_remote_terminal/modified_full_rotated_ellipse_final/`，新通过收据在`runs_remote_terminal/modified_full_rotated_ellipse_tolerance_v2/`。

这不是风暴几何生成验证：实际 weather generator 尚须从完整 storm track 计算“尾缘离开目标”的 `t_exit`；告警概率/延迟校准、alarm-job 独立服务义务与 W 指标分母也仍未解决。精确命令、标准输出、退出码和哈希见 `VERIFICATION.txt`。回滚只作用于另一个副本；主修改副本保留供后续审查。
