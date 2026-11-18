# 公平对照协议 v6（审稿人向；实现见 v6/fairproto.py，可被其他实验线复用）

**P0 数据契约**：每行 = (plan_set, map, method, day, scenario)。紧凑字段（raw_compact.csv）：map, day, scenario, plan_set, method, seed,
J5, cost, ot, late_h, late_n, fails, complete_strict, n_dabs, fixed_cost, latency_p99_ms（+ latency_mean_ms, n_backup, ontime_h, n_urgent）。

**P1 完成率优先**：complete_strict = 计划目标全部完成 且 所有紧急请求均被服务（作业窗口内）；分母与选址无关（只排除任何候选站
作为 DABS 都覆盖不到的请求，WX-E6 中按构造为 0）。任一 (map, day) < 100 % → 该臂在该集合门槛失败，其余指标不解释（†）。崩溃行 = 未完成。

**P2 选址平价**：每个假设只比较执行**同一份计划**的臂（同站型、同路线 → 同 #DABS、同固定成本），`check_parity()` 逐行校验。
选址变体（TSALNS-Cov / TSR / PAD / TSCr10）是独立计划集，**每个执行方法都在其上重跑** → 增益不可能来自多开站；选址效应与调度效应正交报告。

**P3 最强公平基线 SB**：测试前仅在 dev 上，于全部非 RL 臂（含护盾版本、重优化各预算）中按"严格 100 % 下 dev J5 最小"选出并冻结（SB_FREEZE.json）。

**P4 等信息**：所有策略观察同一可观测状态（预报、临近预报、告警、机队状态）；公平 rollout 只从可观测信息采样未来；全知 O 只报告不检验、不加粗。

**P5 等算力 / 时延分级**：实时类（≤ 100 ms/决策，报告 p99）与前瞻类（100 ms 仿真内截止 rollout）。RL 在本类内比较，并对所有更慢的方法比较。
训练预算固定（ES 迭代数固定；未达者不得被选用），老师预算按墙钟上限，并报告总 CPU 时间。

**P6 统计**：单元 = 地图（天平均）双侧 Wilcoxon + 预注册族内 Holm；天聚类 Wilcoxon（同一天天气在地图间共享）；地图×天交叉 bootstrap（2000）
给相对差 95 % CI；rank-biserial。**确认** = p_Holm < .05 且 p_day < .05 且 CI 不含 0。逐种子全部报告（不丢种子）；主结论用种子均值，且要求 ≥ 4/5 种子各自确认。

**P7 新鲜数据**：测试天从未用于训练/调参；Test-G/Test-L 地图在预注册前生成、此前无任何方法运行。

## 作者方法适配的"精准设计"清单（逐条回答审稿人）
1. 作者代码原样使用（third_party/LRPHSD，git clone），只通过一个最小补丁（baselines/tsalns_java/tsalns_v6.patch）加入：Ω 覆盖进
   `LocationOperator.isFeasible`、贪心 `covInit`、时间预算/电池余量参数、RESULT 行输出 covOK。算子、SA 参数、接受准则不变。
2. 时间预算：10 s / 实例（大图 30 s），单线程，所有计划集相同；报告目标值与 Python 修补次数（期望 0）。
3. 原版 TSALNS 不能达到 100 % 的原因被量化报告（Ω 未覆盖点数），而不是被隐藏。
4. 事后修补（TSR，精确 MILP 最小费用覆盖）与全 DABS（PAD）作为对照，回答"内生覆盖约束 vs 事后补站"的成本。
5. 作者计划 + 6 类执行规则（A1/A2/N1/N6 网格/护盾/重优化 R/Rfc/RfcP）都在同一共享可行性层内执行；N6 网格与 SB 在 dev 上冻结。
6. 作者门槛：dev 上 A1/A2 严格 100 % 是运行继续的前提（`v6.freeze --what author`，失败 exit 3）。
