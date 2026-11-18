# PREREG_v6 — 预注册（推送即冻结；2026-11-18 MST，正式运行 STAMP=official 之前）

正式测试天 70000–70099（Test-M）、71000–71029（Test-G）、72000–72029（Test-L）、73000–73049（稳健性）在写定时**从未被任何方法运行过**；
dev 天 60000–60029；冒烟（SMOKE=1）只用 79000–79003；本地门槛试点只用 74000–74004；老师训练天 3000000–3000049 / 3100000–3100049；ES 训练 3500000+，ES 验证 3900000+（均与测试不重叠）。
Test-G（data/instances/fresh6，100 张）与 Test-L（data/instances/large6，30 张）由 v6/gen6.py（种子 20261118）在本预注册前生成，
任何方法均未在其上运行。v4/v5 的天号与试点天不复用。

## 0. 为什么有 v6（对 v5 的如实披露）
v5（keyan001 wx5_server_run）结果：seed 2 不显著；RL5 加班高于 A1/POMO/N1；去紧急特征消融优于完整模型；P4a 存在 fc_y bug；P4b 弱；
Test-L 仅 10 图。e2e_v2 进一步显示作者原版 TSALNS 计划在背景故障请求上无法达到严格 100 % 完成（缺口全部来自计划未覆盖或任何候选站
都覆盖不到的背景请求）。v6 的全部改动见 DESIGN_V6_ZH.md §2。

## 1. 设定（所有方法相同）
WX-E6：合成天气；H = 480，T_END = H + 240；共享可行性层同 v5；背景故障请求只从有限支撑集 Ω（wx2/omega.py，实例 sha256 种子，
每点保证被某候选 DABS 覆盖）抽取 → n_unservable_all ≡ 0。稳健性场景 uniform = 故障空间分布均匀（非风暴驱动；仍在 WX-E6 生成器内，n_unservable_all 照常报告）。

## 2. 指标
- **门槛（第一）**：complete_strict = 计划目标全部在窗口内完成 且 所有紧急请求均被服务；分母与选址无关。任一 (map, day) 未完成即该臂
  该测试集门槛失败，其余指标不解释（标注 †）。程序崩溃行计为未完成。
- **主指标 J5** = cost（固定 + 0.5·忙碌分钟 + 备用机）+ 1·OT + 30·late_h + 10·late_n + 100·fails。
- 次要：cost、ontime_h、n_backup、CVaR90(late_h)。附录：makespan、末次作业结束。
- 结构（每计划）：#DABS、#SABS、固定成本、Ω 未覆盖数（必须 0）、Python 修补次数。

## 3. 计划（静态层）
TSC = TSALNS-Cov（作者 Java + Ω 覆盖进 isFeasible + covInit；10 s，大图 30 s；单线程），是**所有执行方法共同的主计划**。
TS = 原版 TSALNS（只报告 Ω 未覆盖数）。TSR = TS + 精确最小费用覆盖修补。PAD = TS 全部升级 DABS。TSCr10 = TSC + 10 % 电池余量。
s2 门槛：进入动态评测的每份计划 Ω 未覆盖 = 0，否则停止。

## 4. 基线与冻结（dev，测试前）
A1、A2、N1_240、S:N1_240、N6 网格 12 配置 → **N6_best**（dev 严格 100 % 中 J5 最小）；S:N6_best、R_/Rfc_/Rfc600e15_（=RfcP）N6_best 及其 S: 版本；
RL5（v5 冻结策略，作为"前一版本"基线，不参与 SB 选择）。**SB** = dev 上所有非 RL 臂中严格 100 % 且 J5 最小者（SB_FREEZE.json）。
**作者门槛**：dev 上 A1、A2（作者计划 + 按计划执行）严格完成率必须 = 1.000，否则 exit 3（不得继续）。O（全知）只报告不检验。

## 5. RL6
5.1 老师：第 0 轮基策略 = TEACHER_BASE（默认 RL5），M = 8 公平孪生未来，标签概率 p = 0.5，λ = 1·OT，β = 0；第 1 轮基策略 / roll-in = 第 0 轮学生，β = 0.5。
    预算 T0_H = T1_H = 2.5 h（墙钟，到时停止；已完成分片全部使用）。
5.2 蒸馏：软目标 CE，τ = 20，Q 差距权重，按 (map, day) 留出 10 %，选 teacher-regret 最小；主模型 5 种子（0–4，bootstrap），nf/ne 3 种子（0–2）。
5.3 约束 ES：250 次迭代（固定）× 20 对偶对 × 16 天，σ/lr 同 run_es6.py 默认；λ_V ≥ 1000；λ_OT = PID(kp 2.0, ki 0.2)，残差 (OT − 0.9·OT_ref)/max(OT_ref,5)
    clip [−1, 2]；OT_ref = SB（若 SB 是重优化类则用 S:N6_best，计算便宜，但**选择仍对 SB**）。未达 250 次迭代的运行不得被选用。
5.4 选择：候选 {distilled, es_best, es_final}，dev（20 图 × 30 天）上严格 100 % 且 dev OT ≤ SB dev OT，取 dev J5 最小；若无候选满足 OT 条件，
    取 J5 + 5·OT 超额 最小并标记 feasible=False（如实报告）。
5.5 班次护盾 SHIELD=1（默认，与 S:* 基线同一规则）；变体：main（5 种子）；nf（屏蔽天气预报特征）、ne（屏蔽紧急特征）、uc（无 OT 约束）、ns（无护盾）各 3 种子；
    noES = 蒸馏模型（main 各种子）。所有变体同老师数据、同 ES 预算。

## 6. 测试集
| 集合 | 计划 | 图 × 天 | 方法 |
|---|---|---|---|
| **Test-M（主）** | test_tsc | 50 × 100（70000–70099） | 全部基线 + RL6 5 种子 + 消融 |
| Test-G | fresh6_tsc | 100 × 30（71000–71029） | 基线 + RL6 |
| Test-L | large6_tsc | 30 × 30（72000–72029） | 基线 + RL6 |
| 稳健性 ×4 | test_tsc | 50 × 50（73000–73049）：stress、sigma15、ncbias6、uniform | 基线 + RL6 |
| 选址变体 ×3 | test_tsr / test_pad / test_tscr10 | 50 × 50（70000–70049） | 基线 + RL6 |
| 作业窗口 | test_tsc，WX_OT=180/300 | 50 × 20（70000–70019） | 基线 + RL6（不重训） |
| 时延分级 | test_tsc | 50 × 20 | RL6R_100ms vs N4fd_32_100ms（基策略 SB 或 S:N6_best）、RL6、SB、O |

## 7. 检验（顺序固定；analyze_v6.py 实现）
① 结构门槛表（Ω 覆盖、#DABS、固定成本）与完成门槛表（所有臂、所有集合）。
② **H1**（Test-M）：RL6（5 种子均值）vs 每个可实现基线 {A1, A2, N1_240, N6_best, S:N6_best, R_N6best, Rfc_N6best, RfcP_N6best, S:RfcP_N6best, SB, RL5} 的 J5，Holm(族内)。
③ **H2**（Test-M）：RL6 vs SB 的 OT、late_h、late_n、fails（越低越好），Holm(4)。
④ 逐种子：每个种子 vs SB 的 J5（Holm 按种子数）；主结论要求 H1-vs-SB 确认 且 ≥ 4/5 种子各自确认。
⑤ 次要指标 vs 全部基线，Holm（整族）。⑥ 消融族 Holm：RL6 vs noES、nf、ne、uc、ns。
⑦ 泛化/稳健性/选址变体：同 H1（对 SB 与 N6_best），各集合单独 Holm。⑧ 时延分级与作业窗口：描述 + 同类检验。
统计单元：地图级（天平均）双侧 Wilcoxon + Holm；天聚类 Wilcoxon；地图×天交叉 bootstrap 2000 次（相对差 95 % CI）；rank-biserial。
**确认** = p_Holm < .05 且 p_day < .05 且交叉 CI 不含 0。

## 8. 计算预算与 ETA（RTX 3090 不需要；~40 CPU 核，W = NCPU − 2）
s1 计划 ≈ 0.6 h（≈ 440 次 TSALNS × 10–30 s / 38）；s3 dev ≈ 0.5 h；s4+s6 老师 ≤ 5 h（墙钟上限）；s5/s7 蒸馏 ≈ 0.5 h；
s8 ES 17 个运行并行 ≈ 8–9 h；s9 选择 ≈ 0.7 h；s10 测试 ≈ 2–3 h；合计 ≈ 18–20 h（上限 24 h）。中断后同一命令续跑，不改设计。

## 9. 不做的事
不用真实天气；不在测试天/测试图上调参；不改变共享层以偏向任何方法；不允许 RL 改选址；不省略 makespan；不丢弃任何种子。
