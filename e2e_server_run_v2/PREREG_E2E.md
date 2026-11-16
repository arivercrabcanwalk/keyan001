# PREREG_E2E — 全强化学习端到端（设计 A）预注册

> 写于 2026-11-16（JST），在服务器上产生任何正式结果**之前**。正式运行后不得修改本文件的门槛、测试集、天数、统计方法；如必须修改，须在本文件末尾追加“偏离记录”并说明理由。

## 0. 范围与铁律
- 问题：Liu LRPHSD（SABS/DABS 选址 + 多无人机路线）+ 我们的 WX5 动态执行仿真（合成天气，COMPLETE 规则，J5 目标，P=100）。
- **所有 RL 方法内部不使用 ALNS/TSALNS。** 作者 Java TSALNS（`baselines/tsalns_java`，仅加 `-Dsecs/-Dreserve` 补丁）只作为**基线/量尺**。
- **100% 完成率是硬约束**：共享可行性层（COMPLETE 规则：电量/占空/覆盖掩码 + 兜底返回/补派），任何一天完成率 < 100% 即该方法 G3 失败。
- 主目标 J5；makespan 为次要指标（报告但不设门槛）。
- 只用合成天气；训练天与测试天完全不重叠（见 §3）。

## 1. 方法（设计 A，三层全部为 RL 策略）
| 层 | 策略 | 训练 | RL 自有搜索（显式声明） |
|---|---|---|---|
| π_site 选址 | 自回归集合决策 Transformer（覆盖掩码保证可行） | REINFORCE + M 样本共享基线（POMO 式）+ 专家迭代（蒸馏 RL 自有站集邻域搜索的最优结果）；再用仿真 J5 作为奖励微调（A4，每 seed） | **站集邻域搜索**（类型改变/交换，用 π_route 贪心解码打分）；j5 模式下 top-k 站集用仿真 J5 重排（训练天 5e6+） |
| π_route 路线 | LEHD/BQ 式重解码器（6 层编码 + 2 层重解码器，top-k 可行候选），POMO 多起点，Sym-NCO 二面体 ×8 增强 | 共享基线 REINFORCE，课程 35→150 + 单站子问题，GPU bf16 | **EAS-Emb**（测试时对嵌入做梯度自适应，预算内） |
| π_exec 执行 | RL5 架构 + 6 个动作（含 REROUTE：用小路由器重建该站剩余子路线） | PPO（GAE λ=0.95，大批并行环境，熵退火，KL 早停，RL5 热启动），Lagrangian 约束 ot ≤ ot(N6) | 无（REROUTE 为策略动作，单次前向） |
- 纯策略（无搜索）结果必报：`OURS_pure`（贪心站集 + 贪心路线）、`OURS_sample`、`OURS_noEAS`。
- 消融/后备：B-lite = `ABL_B_online`（每次起飞都在线重建，PARCO 式在线构造的简化版）；C = `OURS_full_lns`（学习修复 LNS：路由器重解码站子问题，非 ALNS）。
- 种子：π_exec 与 π_site-J5 用 3 个 seed（0,1,2）；**π_route 与 π_site(static) 只训练 1 个 seed（GPU 预算）**，这一点在结论中注明。

## 2. 预注册门槛（全部 seed 都需通过）
| 门槛 | 定义 | 比较对象 |
|---|---|---|
| G1 静态 | 测试 50 图上作者目标的平均相对差 ≤ **+1%** | 计算量匹配的作者 TSALNS（同秒数 `OURS_full_{b}s` vs `test_ts{b}`，主报告 b=10 s） |
| G2 J5 | 平均 J5 相对差 ≤ **−15%** 且 Holm 校正后 p < 0.05 | TSALNS 计划 + 事件重优化（`TS_Rfc`） |
| G3 完成率 | 所有图×天 100% | — |
| G4 失败数 | 平均失败次数相对差 ≤ **−25%** | `TS_Rfc` |
| G5 加班 | 平均加班分钟 ≤ 参考 | `TS_N6` |
| G6 延迟 | 每天 p99 决策延迟的中位数 ≤ **20 ms** | — |
- 若 G2 只靠执行层（`TS_OURSexec`、`TS_RL5` 已接近 −15%），结论需如实说明增益来源。

## 3. 数据与天数
- 静态测试：Liu 50 图（`data/instances/test`）+ 新生成 fresh 50 图（`gen_fresh.py`，seed 20261116）+ 大图 large（L12_150/L15_200，动态评估用）；fresh_large（F12_150/F15_200/F20_300）已生成，作为可选额外泛化检查（不计入门槛）。
- 训练图：`data/instances/train` 200 图（w5_35…w10_110），开发图 `dev` 20 图。
- 天气天：训练 3e6+（site-J5）、4e6+100k·seed（PPO）、5e6+（j5 重排）；开发 16000–16019；**测试 base 11700–11799；sigma15/ncbias/stress/uniform 12700–12749；large 13700–13749**。

## 4. 统计
- 单位：图（对天取均值后在图层面配对），Wilcoxon 符号秩检验；同一族内 Holm 校正（主比较族：OURS vs 各基线；消融族单独）；图×天交叉 bootstrap 95% CI（2000 次）。
- 静态：Wilcoxon + 胜场数。

## 5. 早停规则（2 h 学习曲线门）
- π_route 先训练 GATE_H=2 h，用 val_aug8 曲线拟合 gap = a + b·h^(−c)（h > 0.05，≥ 6 点）；若外推到 ROUTE_H=12 h 时 gap > **+1.0%**（相对 TSALNS 路线，固定 TSALNS 选址）或无改善 → **停止整个流程**（exit 10），回报曲线，不再花后续 GPU 时间。

## 6. 报告
- 全部门槛通过/失败如实报告；不挑 seed；所有消融（ABL_N6、ABL_RL5、ABL_noRR、ABL_B_online、ABLP_full_static、ABLP_pure、ABLP_noeas）与鲁棒场景都报告。

## 偏离记录
（空）

### 偏离记录 D1（审稿式自查后，在任何正式测试结果产生之前追加；草稿，待作者确认后生效）
- **D1.1 早晨计划适配（R-repack）**：共享启发式 repack（裁剪+最早完工插入+2 轮 relocate）会改写任意静态计划约 89% 目标所在的行程。RL 方法改为 `rl:<route_small>`：π_route 按 t0 预报推得的能量裕度逐站重规划，启发式 repack 仅以 relocate=0 作安全网并记录改动比例；TSALNS 基线保持 v5 的启发式 repack。增加消融 `ABL_heurRepack`。
- **D1.2 完成率口径（R-G3）**：G3 改用与选址无关的 `complete_strict`（只排除"任一候选站开成 DABS 也无法服务"的请求）；崩溃/缺失的 (图,天) 计为未完成。
- **D1.3 主基线（R-primary）**：主比较对象改为在 **dev 图×dev 天**上选出的最强非 RL 基线（TSALNS 预留 0/10/20% × A1/N6/Rfc），写入 `results/primary_baseline.txt`；新增 G2b：对**所有**非 RL 基线 ΔJ5<0 且 Holm p<0.05。Holm 族拆分为"非 RL 基线族"和"RL 分解族"。
- **D1.4 析因臂（R-factorial）**：`TS_OURSexec` 扩展到全部 3 个 seed；新增 `ABL_Rfc_s*`/`ABL_N6_s*`（我们的计划 + 基线执行）；新增 `ABL_scratch`（PPO 不用 RL5 热启动，因 RL5 由 ALNS 计划训练）。
- **D1.5 静态评估（R-static-surv）**：不可行/缺失的计划计为失败，G1 要求全部 50 图可行；报告最大 wall；新增 CPU-only 10 s 臂。
- **D1.6 训练分布（R-dist）**：π_route 课程在 40% 进度（2 h 门之后）起加入 Liu 式 20 km/5000 m 地图；π_site 同样加入。2 h 门不受影响。
- **D1.7 σ×1.5 场景修复（R-sigma15）**：预报残差 x/y 两分量一致放大并刷新 fc_now 缓存。
- **D1.8 TSALNS 运行（R-tsjvm）**：JVM 串行 GC、限制 JIT 线程，记录 CPU 秒；无 Java TSALNS 时正式运行直接停止。
- **D1.9 披露**：π_route 的检查点选择与 2 h 门使用 dev 图上 TSALNS 的选址/路线成本作为量尺；RL5 热启动权重来源于 ALNS 计划上的 ES 训练；冒烟测试曾在 test 5_35_1/2 与 fresh f5_35_1/2 上用极小模型跑过（不用于任何调参）。
