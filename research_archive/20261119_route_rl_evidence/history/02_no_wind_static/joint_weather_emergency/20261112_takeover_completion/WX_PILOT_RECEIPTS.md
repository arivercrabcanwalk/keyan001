# WX Pilot 实收据与边界核对（2026-11-12）

**任务范围**：核对 2026-11-12 产生的全部 WX pilot 与三份原 prompt（WX-E / WX-H / WX-C）的实收据与边界。
**阅读范围**：任务指定的 6 份 REPORT、`PROMPT_RECONCILIATION.md`、3 份 ORIGINALS prompt，以及各包的 `STATE*.json`、`PROTOCOL.md`、`VERIFICATION*.txt`、`DECISION*.md`、`G0_REVIEW.md`、`REVIEW.md`、`RESULTS_SUMMARY.md` 与原始结果 JSON。
**复算方法**：对每份原始结果 JSON 做行级只读复算（行数、按 mode×method 的均值、成本比、complete/replay 计数、逐行 trace 比对）。只做算术复算，**没有**计算任何新的统计量（未做 bootstrap、Wilcoxon、Holm、CI）。
**边界声明**：本核对**未连接 <COMPUTE_HOST>**、未修改任何历史文件、未启动任何实验或训练；服务器端原件未在本任务重开，所有“服务器实收据”均转引自包内文件。服务器路径、驱动版本与最终哈希若与包内记录冲突，按“包内记录优先、冲突单列”处理（见 §3）。

---

## 0. 结论摘要

1. 2026-11-12 的 WX 线共 **13 个包 / 14 次有结果文件的运行**（WX-E 线 10 个包，WX-C 线 3 个包；含 1 次已作废 toy、1 次仅本地 WX-C v1、1 次被 v3 取代的 WX-C v2），合计 **3,520 行**结果；其中 server 运行 **3,200 行**，剔除作废 toy 后 **3,136 行**（见 §1 表 1）。
2. 所有有裁决的包都是 **CLOSE**：`CLOSE_NO_FULL_RUN`（WX-E 全部）与 `CLOSE_WX_C_CANDIDATE`（WX-C）。**没有任何 PASS_EXPAND、没有全量训练、没有 Formal、没有 WX-H 运行**。
3. 被交接 prompt、`RESEARCH_PLAN_ROUTE_RL.md` 与 `return_makespan/STATE.json` 广泛引用的“WX-E 首包 `V_cluster=-0.40625`、成本比 `1.20743`”来自 **已被本包明确作废的 toy 文件** `results/PILOT.json`；可采信的真实 64 行结果是 `V_cluster=0.0`、`V_uniform=1/3`、成本比 **1.086307**（§2.1、§3-D1）。
4. v3–v8 的 `V_cluster` **口径不统一**：v5/v6 用“单个最好 RL seed（RL_103）−对照”，v7/v8 用“3-seed pooled−对照”。v6 报告的 `+0.0208333` 是单 seed 值；同一数据 3-seed pooled 为 **−0.012153**（符号相反）（§2.5、§3-D9）。
5. v6 的 EVAL 地图种子与 v5 **完全相同**（600–615），非 RL 行成本逐位相同；v6 PROTOCOL 写的是 800–815，与代码不符。“v6 是最接近候选”不是独立人口确认（§3-D7/D10）。
6. 成本门槛的“最强完整 non-RL”对照并非始终取真正最优：v3/v4 排除了更便宜且 H 相同的 `ROLLOUT_128/ROLLOUT_8`；若按最低成本对照，v3 成本比 **1.0546**、v4 **1.0384**，成本门槛会失败（§3-D8、§8）。
7. WX-C 的“两模式各 320 行”不成立：实际每次运行 **320 行**（每模式 160 行 = 32 场景 × 5 方法），两种模式合计 320 行/次（§2.6、§3-D6）。
8. 原三方案中**完整多站异构 WX-E、真实 N4、uniform 独立重训、Formal、论文包**均未执行；pilot 关闭只关闭各自的有界身份（§5 逐项）。
9. `v9/v10 + 换 seed` 被禁止不是文风问题：它同时违反预先登记的一次性 gate、同一机制不得在已暴露 DEV 继续调参、以及不得用版本/seed 轮换碰到显著（§6）。
10. WX-H 是 **DEFERRED（未准入，非科学证伪）**：依赖 WX-E G-a 通过、G0/G3 通过、H1 定义与 gate 真值表冻结、V 的单因素归因设计，而这些前提全部未满足（§6.3）。

---

## 1. 分母与盘点

**统一分母定义**：本文件中的 1 row = 1 张图（map/scenario）× 1 个事件日（event day）。所有 WX pilot 都是“单日多图”，**没有一包做过“每图 30 天”**；因此任何“按天再对天平均”的原合同统计（WX-E §3.6/§8）都未真正执行。除特别注明，n 指图数（map 为统计单位）。

表 1：2026-11-12 WX 运行盘点

| 运行 | 目录 | 结果文件 | 行数 | 图×日 | 时长/站/机 | 有裁决 | 备注 |
|---|---|---|---:|---|---|---|---|
| WX-E toy | `20261112_wx_e` | `results/PILOT.json` | 64 | 2 模式 × 4 图 × 1 日 | 180 min / 1 站 / 2 机 | 是（但作废） | 简化单机 toy driver；`INVALIDATED_ENGINEERING_ONLY` |
| WX-E real 首包 | `20261112_wx_e` | `results/REAL_PILOT.json` | 64 | 2 × 4 × 1 | 180 min / 1 站 / 2 机 | 是 | 唯一可采信的 64 行；无独立回放字段 |
| WX-E real v2 | `20261112_wx_e_real` | `results/REAL_PILOT_V2.json` | 128 | 2 × 8 × 1 | 300 min / 1 站 / 2 机 | 是 | 3 seed × 30 updates |
| WX-E forecast v1 | `20261112_wx_e_forecast_v1` | `results/PILOT.json` | 256 | 2 × 16 × 1 | 360 min / 1 站 / 2 机 | 是 | 3 seed × 60 updates |
| WX-E risk v1 | `20261112_wx_e_risk_v1` | `results/PILOT_SAVED_EVAL.json` | 512 | 2 × 32 × 1 | 420 min / 1 站 / 2 机 | 是 | 3 seed × 220 updates；NaN 恢复后评价 |
| WX-E v3 | `20261112_wx_e_v3` | `results/REAL_PILOT_V3.json` | 256 | 2 × 16 × 1 | 420 min / 1 站 / 2 机 | 是 | 30 updates；H 天花板 |
| WX-E v4 | `20261112_wx_e_v4` | `results/REAL_PILOT_V4.json` | 256 | 2 × 16 × 1 | 300 min / 1 站 / 2 机 | 是 | 30 updates；H 天花板 |
| WX-E v5 | `20261112_wx_e_v5` | `results/REAL_PILOT_V5.json` | 256 | 2 × 16 × 1 | 360 min / 1 站 / 2 机 | 是 | 30 updates；成本超限 |
| WX-E v6 | `20261112_wx_e_v6` | `results/REAL_PILOT_V6.json` | 256 | 2 × 16 × 1 | 360 min / 1 站 / 2 机 | 是 | 60 updates；“最接近”但复用 v5 EVAL |
| WX-E v7 | `20261112_wx_e_v7` | `results/REAL_PILOT_V7.json` | 256 | 2 × 16 × 1 | 360 min / 1 站 / 2 机 | 是 | 60 updates；pooled 3-seed |
| WX-E v8 | `20261112_wx_e_v8` | `results/REAL_PILOT_V8.json` | 256 | 2 × 16 × 1 | 360 min / 1 站 / 2 机 | 是 | 60 updates；几何假设反向 |
| WX-C v1 | `20261112_wx_c_spatial_diag_v1` | `results/BASELINE.json` 等 | 320 | 64 场景 × 1 frontier | 360 min | **否** | 仅本地工程，`SERVER_RUN_PENDING` |
| WX-C v2 | `20261112_wx_c_spatial_diag_v2` | `results/SERVER_EXPANDED.json` | 320 | 64 × 1 frontier | 360 min | 是（被 v3 取代） | 首次 server 运行 |
| WX-C v3 | `20261112_wx_c_spatial_diag_v3` | `results/SERVER_EXPANDED.json` | 320 | 64 × 1 frontier | 360 min | 是 | 跨运行时规范化后的终局 |

**行数合计**：64 + 64 + 128 + 256 + 512 + 6×256 = **2,560 行**（WX-E 线，含 toy）；WX-C v1/v2/v3 各 320 行 = **960 行**；全部 **3,520 行**。其中 server 运行 = 3,520 − 320（v1 仅本地）= **3,200 行**；再剔除作废 toy 64 行 = **3,136 行**。
**站/机**：所有 WX-E 包均为 `Station(0,0,0)` 单站；机型容量 v2 `(2.0,2.0)`、v3 `(2.6,2.6)`、其余 `(2.8,2.8)`，即**同质 2 机**，无 SABS/DABS、无 SD/LD。
**时长**：首包 180 min、v2/v4 300 min、forecast/v5–v8 360 min、risk/v3 420 min，均**不是**原 prompt 的 480 min。

---

## 2. A. 每个 pilot 一张卡

### A-1 `20261112_wx_e`（WX-E-v1 首包；含 toy 与 real 两份 64 行）

| 项 | 值（含分母） |
|---|---|
| 身份/目录 | WX-E-v1 pilot；`joint_weather_emergency/20261112_wx_e` |
| 实际行数 | **toy 64 行**（`results/PILOT.json`，已作废）+ **real 64 行**（`results/REAL_PILOT.json`，可采信） |
| 图/日 | 2 模式（clustered/uniform）× **4 图/模式** × **1 日/图** × 8 方法 = 64 行/文件 |
| V_cluster | **0.0**（clustered 全部方法 H=1.0，4 图均值；分母 4 图） |
| V_uniform | **0.3333333333333333**（RL 2/3 − 最强 non-RL 1/3；分母 4 图 × 3 个 high-priority 任务/图） |
| 成本比 | **1.086307**（55.371981291828945 / 50.9727037026624，+8.63%）；对照 `STATIC_STANDBY` |
| 完整服务率 | **40/64 = 0.625**（24 行 incomplete，24 terminal failures，`unserved_total=24`，`invalid_actions=0`） |
| 独立回放率 | **未记录 0/64**：行内无 `replay_verified` 字段，VERIFICATION 亦未声明独立回放 |
| checkpoint 数 | **0**（未训练；RL_103/211/307 只是冻结策略标签） |
| seed | 103 / 211 / 307（标签，无优化器）；real 行只有 `map`=0–3（每模式 4 图）而无 `seed` 字段；toy 行才有 `seed`=100–103 与 `policy_seed` |
| 更新步数 | **0** |
| 预注册裁决字符串 | `CLOSE_NO_FULL_RUN`（STATE status=`REAL_PILOT_COMPLETE_GATE_CLOSED_NO_FULL_RUN`） |
| 关闭原因 | gate 三条件全 false：`clustered_delta_at_least_0.05=false`、`cost_noninferiority_1pct=false`、`uniform_shrinks_half=false`（V_cluster=0 时 `uniform_shrink_ratio=null`） |
| 证据 | `REPORT.md`、`STATE.json`、`PROTOCOL.md`、`DECISIONS.md`、`VERIFICATION.txt`、`results/REAL_PILOT.json`（SHA256 `60a6b6b6ae18059698bd77c2d60eedc7c1a534541c1597b0f9d168ac84332a73`） |

**toy 文件单独记录（因为它被外部引用）**：64 行、2×4×8；`V_cluster=-0.40625`、`V_uniform=-0.25`、`uniform_shrink_ratio=0.6153846153846154`；`cost_rl=70.28768007238395`、`cost_nonrl=58.21266710872297`、`cost_ratio=1.2074293029918841`；0 failed / 0 unserved；裁决同为 `CLOSE_NO_FULL_RUN`（审计串 `PASS_AUDIT_CLOSE`）。**该文件已被 `VERIFICATION.txt` 第 4 行与 `STATE.json` 的 `toy_pilot_status=INVALIDATED_ENGINEERING_ONLY` 明确作废**，原因是“simplified single-vehicle toy driver”。

**真实运行边界**：单站 2 机、180 min、base fixture 的非紧急任务 + 6 个风暴释放故障（其中 3 个 high-priority，deadline 15/20 min）；对照只有 8 个方法，`ROLLOUT_8/128` 是 public-state scoring controls（`REPORT.md` 第 21 行、`STATE.json` `baseline_implementation_boundary`），不是完成的 MC rollout。

### A-2 `20261112_wx_e_real`（real v2）

| 项 | 值（含分母） |
|---|---|
| 身份/目录 | WX-E real v2；`20261112_wx_e_real` |
| 实际行数 | **128 行** = 2 模式 × **8 图/模式** × 8 方法 |
| 图/日 | 16 图 × 1 日；300 min；1 站 2 机 |
| V_cluster | **0.0**（clustered 全部 H=1.0；分母 8 图） |
| V_uniform | **0.0** |
| 成本比 | **0.756727**（69.36025515744755 / 91.65824956019068）；对照 `STATIC_STANDBY`；**该比值不可采信**（见下） |
| 完整服务率 | **48/128 = 0.375**；`incomplete_return_rows=80`，`unserved_task_total=480`（每个不完整行 6 个未服务任务） |
| 独立回放率 | **128/128 = 1.0** |
| checkpoint 数 | **3**（`rl_103.pt / rl_211.pt / rl_307.pt`；SHA256 记于 `STATE_V2.json`；文件本身不在本地包） |
| seed | 103 / 211 / 307（真训练，3 个独立初始化） |
| 更新步数 | **30 步/seed**；训练日志每次 update 记录 909–912 transitions |
| 预注册裁决字符串 | `CLOSE_NO_FULL_RUN` |
| 关闭原因 | `cluster_delta_ge_0.05=false`、`uniform_shrinks_half=false`；`cost_le_1pct=true` 只因不完整行被拿来比成本 |
| 证据 | `REPORT_V2.md`、`STATE_V2.json`、`VERIFICATION_V2.txt`、`results/REAL_PILOT_V2.json`（SHA256 `b338f6ff708c4af185043411d38f35064cce34be7d44bc798df45d500c5f2b1a`，与记录一致） |

**关键实测**：`BC`、`ROLLOUT_128` 与 3 个 RL seed 在 **16/16 图**上的动作 trace **完全相同**（逐行 JSON 比较 0 差异）；clustered 每行恒定 6 个未服务任务；`STATIC_STANDBY` 与 `ROLLOUT_8` 完整服务。因此 0.7567 的“成本优势”是“少服务 6 个任务”的会计结果，不是路线质量；`REPORT_V2.md` 第 36 行也明确写了这一点。

### A-3 `20261112_wx_e_forecast_v1`（WX-E-FBU v1）

| 项 | 值（含分母） |
|---|---|
| 身份/目录 | forecast-update pilot；`20261112_wx_e_forecast_v1` |
| 实际行数 | **256 行** = 2 模式 × **16 图/模式** × 8 方法 |
| 图/日 | 32 图 × 1 日；360 min；1 站 2 机 |
| V_cluster | **−0.09523809523809523**（RL 3-seed pooled 48 行均值 − `ROLLOUT_128`；分母 16 图） |
| V_uniform | **+0.0014880952380953438**（同一对照 `ROLLOUT_128` 的 uniform H=0.830357） |
| 成本比 | **0.943318**（88.33112038501943 / 93.63879794673824） |
| 完整服务率 | **256/256 = 1.0** |
| 独立回放率 | **256/256 = 1.0** |
| checkpoint 数 | **3**（代码 `torch.save`；本地包无 `models/` 目录、无 SHA 记录） |
| seed | 103 / 211 / 307；训练图 1200–1211，评价图 1100–1115 |
| 更新步数 | **60 步/seed**（BC 8 epochs；来自 driver 常量，非运行日志收据） |
| 预注册裁决字符串 | `CLOSE_NO_FULL_RUN`（STATE status=`PILOT_CLOSED_NEGATIVE`） |
| 关闭原因 | `cluster_delta_ge_0.05=false`（−0.095 ≪ 0.05）、`uniform_shrinks_half=false`；成本条件 true |
| 证据 | `REPORT.md`、`REVIEW.md`、`PROTOCOL.md`、`STATE.json`、`results/PILOT.json`（SHA256 `3146bda36dd991c1a2d3d0766d104126218997fb2895c0ec56d4d3d8b6f7d5e2`）、`results/pilot.log` |

**边界**：所谓“60 min 公共风更新”实现为连续融合 `alpha_t=min(0.85,0.28·floor(t/60))`，**不是**带 publication time/version 的独立预报发布事件；14 个 emergency 全部 high-priority、deadline=release+13 min，与“40% high / 20–45 min”原设定不同。

### A-4 `20261112_wx_e_risk_v1`（risk-sensitive public-belief v1）

| 项 | 值（含分母） |
|---|---|
| 身份/目录 | risk-sensitive public-belief pilot；`20261112_wx_e_risk_v1` |
| 实际行数 | **512 行** = 2 模式 × **32 图/模式** × 8 方法 |
| 图/日 | 64 图 × 1 日；420 min；1 站 2 机 |
| V_cluster | **−0.02604166666666663**（3-seed pooled 96 行 − `STATIC_RULE` H=1.0） |
| V_uniform | **−0.02408854166666663**（同一对照 uniform H=0.974609） |
| 成本比 | **1.007945**（90.46030993643605 / 89.74725959419959）≤1.01 |
| 完整服务率 | **512/512 = 1.0** |
| 独立回放率 | **512/512 = 1.0** |
| checkpoint 数 | **3**（`models_reopened=[103,211,307]`；SHA256 在 `AUDIT_LOCAL.json`；文件不在本地包） |
| seed | 103 / 211 / 307；训练图 2000–2063，评价图 3100–3131 |
| 更新步数 | **220 步/seed**（BC 20 epochs） |
| 预注册裁决字符串 | `CLOSE_NO_FULL_RUN`（STATE status=`PILOT_CLOSED_NEGATIVE`；G0=`NO_GO_AS_DISTINCT_NOVELTY_PILOT_ONLY`） |
| 关闭原因 | `cluster_delta_ge_0.05=false`、`uniform_shrinks_half=false`（V_uniform<0，不满足“positive”）；成本与完整服务条件 true |
| 证据 | `REPORT.md`、`STATE.json`、`PROTOCOL.md`、`G0_REVIEW.md`、`VERIFICATION.txt`、`results/PILOT_SAVED_EVAL.json`（SHA256 `dd11fcb7491180edf0324855b487dbabdbd5e0eae74728a9e18ceb4003521004`，与记录一致）、`AUDIT_LOCAL.json`（`PASS_INDEPENDENT_RESULT_AUDIT`） |

**边界**：对照 `STATIC_RULE` 是按 H 选出的最强（H=1.0），但按成本最低选则是 `FORECAST_RULE`（87.781342），此时成本比 **1.030519 > 1.01**（§8）。`ROLLOUT_8` 虽被称为“同预算主对照”，H=0.990234 也高于 RL pooled 0.973958。

### A-5 v3–v8（六个独立包）

表 2：v3–v8 逐包实收据（每包 = 2 模式 × 16 图 × 1 日 × 8 方法 = **256 行**）

| 包 | V_cluster | V_uniform | 成本比（RL/对照） | 完整服务 | 回放 | updates | 评价图种子 | 裁决 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| v3 | 0.000000 | 0.000000 | 0.948063（72.815546/76.804559） | 256/256 | 256/256 | 30 | 300–315 | `CLOSE_NO_FULL_RUN` |
| v4 | 0.000000 | 0.000000 | 0.982930（77.125969/78.465380） | 256/256 | 256/256 | 30 | 400–415 | `CLOSE_NO_FULL_RUN` |
| v5 | −0.010417 | −0.067708 | 1.086244（97.679972/89.924530） | 256/256 | 256/256 | 30 | 600–615 | `CLOSE_NO_FULL_RUN` |
| v6 | +0.020833 | +0.036458 | 0.899876（80.920968/89.924530） | **255/256** | 256/256 | 60 | **600–615（同 v5）** | `CLOSE_NO_FULL_RUN` |
| v7 | +0.001736 | +0.083333 | 0.887635（89.416587/100.735812） | 256/256 | 256/256 | 60 | 900–915 | `CLOSE_NO_FULL_RUN` |
| v8 | −0.090278 | +0.019097 | 0.976872（80.041236/81.936255） | 256/256 | 256/256 | 60 | 1100–1115 | `CLOSE_NO_FULL_RUN` |

**逐包备注**：
- **v3/v4 是天花板包**：两包在两种模式下**所有 8 个方法的 H 都等于 1.0**（分母 5 个和 9 个 high-priority 任务/图），因此 `V=0` 是“无区分度”，不是“RL 与最强 non-RL 打平”的科学结论；`REPORT_V3_V8.md` 第 32 行也承认“v3/v4 were too easy”。
- **v5**：首次把 deadline 压到 release+10 min（12 个全 high-priority），H 降到 ~0.45；RL 输 `ROLLOUT_128` 且成本比 1.086 > 1.01。
- **v6**：`V_cluster=+0.0208333` 是 **RL_103 单 seed**（0.489583 − 0.468750）；同包 3-seed pooled 为 0.456597 − 0.468750 = **−0.012153**。另有 1 条不完整行（`RL_103` uniform、`complete_service_rate=0.9375`、1 个未服务）；该行保留但不可作为完整路线优势。
- **v7**：PROTOCOL 明确“pooled 3-seed，不挑 seed”，gate 也确为 pooled（`rl_pool_n_clustered=48`）；结果 +0.001736，增益坍塌。
- **v8**：phase-conditioned 径向几何把 clustered 效应反转为 **−0.090278**，该几何假设被证伪。
- **checkpoint**：6 包代码都 `torch.save` 3 个 `rl_{103,211,307}.pt`，但本地 `results/models/` 全为空，`STATE_V3_V8.json` 也没有模型 SHA → “3 个 checkpoint”是代码级事实，**无法从本地复核**。
- **证据**：`REPORT_V3_V8.md`、`STATE_V3_V8.json`、各包 `PROTOCOL.md/DECISION.md/results/REAL_PILOT_V*.json`；哈希 `v3 379636ff…`、`v4 04e22c53…`、`v5 1975c1ad…`、`v6 a5043553…`、`v7 3978c5ef…`、`v8 737839da…`（与 `STATE_V3_V8.json` 逐项一致）。

### A-6 `20261112_wx_c_spatial_diag_v3`（WX-C 空间诊断终局）

| 项 | 值（含分母） |
|---|---|
| 身份/目录 | WX-C spatial opportunity diagnostic v3；`20261112_wx_c_spatial_diag_v3` |
| 实际行数 | **320 行/次运行** = **160 clustered + 160 uniform** = 64 场景 × 5 方法；baseline 与 expanded 各一次，共 640 行 |
| 图/日 | **64 场景**（clustered 4200–4231、uniform 5200–5231，各 32）× **1 个决策 frontier**；无“日”维度 |
| V_cluster / gap | **0.16666666666666666 = 1/6**（best-action H − `CONTINUE` H；分母 32 场景） |
| V_uniform / gap | **0.16666666666666666 = 1/6**（uniform-shrink 失败） |
| 成本比 | oracle 相对 `CONTINUE` 的**逐行**成本比最大 **0.9873788674**（≤1.01 的 gate 全过）；非“RL vs non-RL”比 |
| 完整服务率 | 行内 `valid_rate=1.0`、`replay_rate=1.0`；无 complete-service 概念（每场景 1 个 frontier） |
| 独立回放率 | **320/320 = 1.0**（baseline 与 expanded 各自 320/320） |
| checkpoint 数 | **0**（`training_started=false`、`solver_started=false`） |
| seed | 无训练 seed；场景种子 4200–4231 / 5200–5231 |
| 更新步数 | **0** |
| 预注册裁决字符串 | `CLOSE_WX_C_CANDIDATE`（STATE status=`SERVER_TERMINAL_CLOSE_WX_C_CANDIDATE`） |
| 关闭原因 | `uniform_gap_le_half_clustered=false`（uniform gap 1/6 > 0.5×1/6）；clustered 阈值与 replay 条件通过 |
| 证据 | `REPORT.md`、`PROTOCOL.md`、`STATE.json`、`VERIFICATION.txt`、`results/SERVER_BASELINE.json`（`b23c975b…`）、`results/SERVER_EXPANDED.json`（`da3cf82b…`）、`results/INDEPENDENT_AUDIT.json` |

**v1/v2 边界**：v1 STATE 为 `LOCAL_ENGINEERING_READY_SERVER_RUN_PENDING`，只有本地工程结果，无科学裁决；v2 完成 server 运行（同样 320 行、gaps 1/6），但无 STATE/报告，已被 v3 的跨运行时 fingerprint 规范化取代（v3 与本地递归数值比较 0 差异、同源 fingerprint mismatch=0）。

---

## 3. 不一致清单（逐项对账后单列）

> 采信规则：**原始结果 JSON > STATE > VERIFICATION > REPORT > 全局 STATE/交接摘要**；当上游摘要使用了下游已作废文件时，以上游原文引用但明确标注。

| 编号 | 不一致 | 证据 | 采信/处理 |
|---|---|---|---|
| **D1** | 交接 prompt §5.4、`RESEARCH_PLAN_ROUTE_RL.md` L21、`return_makespan/STATE.json` L1234 记 WX-E 首包 `V_cluster=-0.40625`、`V_uniform=-0.25`、成本比 `1.2074293`；但 `20261112_wx_e/REPORT.md` L14-15 与 `REAL_PILOT.json` 是 `V_cluster=0.0`、`V_uniform=0.3333333`、成本比 `1.086307` | 全局 STATE L1234；`REPORT.md` L14-15；`VERIFICATION.txt` L4 明确 toy 作废 | **采用 REAL_PILOT 的 0.0 / 1.086307**；-0.40625 只属于已作废 toy |
| **D2** | `REPORT.md` L12 写“**28 failed rows** and 24 unserved-task counts”；JSON 实为 **24 failed rows**、24 行带 unserved、`unserved_total=24` | `results/REAL_PILOT.json` 行级计数 | 采用 **24**；28 无对应字段 |
| **D3** | `20261112_wx_e/STATE.json` 的 `server_result` 指向 `results/PILOT.json`（toy），而 `scientific_pilot` 指向 `REAL_PILOT.json` | `STATE.json` L22 与 L32 | 采信 `scientific_pilot`；`server_result` 字段是错的 |
| **D4** | `REPORT.md` L14 的 `V_uniform=0.3333` 与全局 STATE 的 `-0.25` 同时存在，且全局 STATE 未登记 real 64 行 | 同上 | 同 D1；全局账本缺 real 64 行条目 |
| **D5** | 首包哈希链自相矛盾：`STATE.json` 记 driver `e9c7bca8` + result `60a6b6b6`；`VERIFICATION.txt` L28 称“final server SHA”为 driver `82704a81` + result `ca516994`。本地根副本 `wx_e_real_pilot.py`= `e9c7bca8`（无 hidden centroid、含 wall_budget/timed_out），`MODIFIED_FILE/wx_e_real_pilot.py`= `82704a81`（**仍含硬编码 `math.hypot(t.x-5600.,t.y-1800.)`**、无 wall 字段）；本地 result `60a6b6b6` 行内含 wall/timed_out，说明它与根副本配对，而 `ca516994` **不在本地** | `STATE.json` server_hashes；`VERIFICATION.txt` L28/L31；两副本 diff | 采用 **本地 60a6b6b6** 的行数据；**“final rerun” 的 ca516994 不能本地复核**，且 L31“no hidden centroid”只对根副本成立 |
| **D6** | `REPORT.md`/LATEST_STATUS/交接 prompt 称 WX-C“两模式各 320 行”；实际每次运行 320 行、每模式 **160 行**（32 场景 × 5 方法） | `SERVER_EXPANDED.json` 行级计数；`INDEPENDENT_AUDIT.json` `rows=320, scenarios=64, rows_per_scenario=5` | 采用 **160/模式、320/run** |
| **D7** | v6 PROTOCOL 写“EVAL seeds 800–815”，driver 实际用 **600–615**（与 v5 相同），且 v6 的 8 个非 RL 方法与 v5 成本逐位相同 | `wx_e_v6/PROTOCOL.md` L10；`wx_e_v6_driver.py` L427；v5/v6 结果均值 | 采用 **代码事实**；v6 不是 fresh identity |
| **D8** | v3/v4 的“最强完整 non-RL”= `STATIC_RULE`，但 `ROLLOUT_128`（v3，69.0457）/`ROLLOUT_8`（v4，74.2773）更便宜且 H 相同；按最低成本对照，成本比变为 v3 **1.0546**、v4 **1.0384**（均 >1.01） | 结果 JSON 分方法均值；gate 字段 | 采用 gate 记录值但标注**对照选择敏感**；不能宣称成本条件稳健 |
| **D9** | v5/v6 的 `V_cluster`/`cost_rl` 用**单个最好 RL seed（RL_103）**，v7/v8 用 **3-seed pooled**（`rl_pool_n=48`）。v6 单 seed +0.020833，pooled **−0.012153**；v5 单 seed −0.010417，pooled −0.020833 | 逐 seed 均值复算；v7 PROTOCOL L12-15 | 采用“**口径不一致**”：v6 的“最接近”不成立为 3-seed 结论 |
| **D10** | `REPORT_V3_V8.md` L7 称“Each package used separate train/evaluation identities”；v5/v6 的评价图种子完全相同（600–615） | 两包 driver + 结果均值 | 采信代码；该句对 v5/v6 为假 |
| **D11** | `VERIFICATION_V2.txt` L44-46：`RESTORED_SHA256` 与 baseline 相同，但 `RESTORED_MATCH_RESULT=1`（`cmp -s` 返回 1 表示不同） | 实际 SHA256：两个 STATE 均为 `abdef773…` | 采信“**一致**”；该字段是假阴性记录 |
| **D12** | 所有训练包的 checkpoint 文件都不在本地包内：v2/risk 只有 SHA256，forecast/v3–v8 连 SHA 都没有；本地 `results/models/` 为空 | 目录清单 + STATE/AUDIT | “3 个 checkpoint”仅为代码/服务器事实，**本地不可复核** |

**附：口径型（非错误但会影响结论）差异**
- `V_cluster` 的对照选择：risk 按 H 选 `STATIC_RULE`（成本比 1.00795），按最低成本选 `FORECAST_RULE` 则 **1.03052**（失败）；forecast 按 H 选 `ROLLOUT_128`（0.94332），按最低成本 `BC` 则 0.95960（仍过）。
- v2 的“成本过”是完整服务缺失造成的：`BC=ROLLOUT_128=RL` 三者 trace 全同、均少服务 6 个任务。

---

## 4. B. 四态矩阵（历史拟议 / 已经执行 / 缺少实现 / 已关闭）

> 说明：一个条目只给一个主状态；“已经执行”允许标注降级口径。WX-H 的“已关闭”= **DEFERRED 未准入**，不是科学证伪。

### 4.1 WX-E（`PROMPT_WXE_storm_urgent.md`）

| # | 原要求（条款） | 状态 | 实际形态与依据 |
|---|---|---|---|
| E1 | 480 min 事件日；天气每 5 min 更新（§3.1） | **缺少实现** | 各包 180/300/360/420 min；wind trace 只有 3–5 段，不是 5 min 更新（`emergency_scenario.py` Trace；各 driver `HORIZON`） |
| E2 | Liu 多站 SABS/DABS、SD/LD、多趟、回本站换电、累计 duty（§0/§3.1） | **缺少实现** | 全部 `Station(0,0,0)` 单站、2 台同质机；每趟原子单目标；无站型/机型（各 driver `Scenario(...)`） |
| E3 | 移动椭圆单体、禁飞、前沿 +5–8 m/s（§3.3） | **缺少实现** | 无单体/NFZ 对象，只有风 trace |
| E4 | OU 风误差、隐藏阵风、60 min 独立预报发布、σ0/κ、ERA5 或标注合成（§3.2） | **缺少实现** | 合成确定性风；forecast v1 用 `alpha_t=min(0.85,0.28·floor(t/60))` 连续融合，无 publication time/version（`PROTOCOL.md`、driver L128） |
| E5 | 单体扫掠→故障 p_f~U(0.2,0.4)、离开后 0–20 min 告警（§3.4） | **缺少实现** | emergency 任务在运行前按固定 release 生成，无扫掠触发（各 driver `_scenario`） |
| E6 | 背景 Poisson 请求，期望=目标数/6（§3.4） | **缺少实现** | 固定 12/14/16 个任务，release 为等差网格（driver L90/L112/L102） |
| E7 | 40% high-priority、deadline 20/45 min（§3.4） | **缺少实现** | 各包 3/5/8/9/12/14/16 个 high，deadline 10–55 min 不等 |
| E8 | 动作 `LAUNCH_PLANNED/HOLD_5MIN/SERVE(j)`（§1.1/§3.5） | **已经执行**（降级映射） | 版本化 `TARGET/WAIT_5MIN/RETURN`；`WAIT_5MIN`=`WAIT(5.0)`；多目标航次未实现（`20261112_wx_e/PROTOCOL.md` L11） |
| E9 | 观测含单体、站上测风、已告警故障统计（§3.5） | **缺少实现** | 观测只有 released tasks、`wind_now`、`forecast`、fleet state（`Observation`） |
| E10 | J=fixed+0.5·busy+0.5·makespan+30/10·late+P·fail（§3.6） | **缺少实现** | 从未计算 J；只报 cost=flight+service+wait+decision-min（各 driver `_score`） |
| E11 | 主指标 H 与 CVaR90（§3.6） | **已经执行**（CVaR 未入门槛） | H 是 gate；`lateness_cvar90` 每行记录，gate 未使用（risk 仅作 reward） |
| E12 | 成本比 bootstrap 95% CI 上界 ≤1.01（§3.6） | **缺少实现** | 只有单点 map-mean 比值；无 bootstrap/CI（全包 grep 无） |
| E13 | A1/A2/A3（TSALNS/TS-insert/TS-reopt 1s/3s）（§4） | **缺少实现** | 无作者方法、无 TSALNS/TS-insert/TS-reopt |
| E14 | N1–N5 网格与组合（§4） | **缺少实现** | 只有 STATIC_RULE/FORECAST_RULE/ROLLOUT_8/128/BC；无网格调参记录 |
| E15 | N4 真实 MC rollout（同生成模型、后验、M=32 参考）（§4） | **缺少实现** | `ROLLOUT_8/128` 是 public-state scoring controls（`REPORT.md` L21、`STATE.json`） |
| E16 | O 千里眼（§4） | **缺少实现** | WX-E 无 oracle 行（WX-C 有 `ORACLE_BEST`，但只 1 个 frontier） |
| E17 | 600 TRAIN、20 DEV×10 日、Test-A 50×30、Test-B 50×30（§5） | **缺少实现** | TRAIN 12–24 图、EVAL 4–32 图/模式、每图 1 日 |
| E18 | BC→DAgger/API→REINFORCE-POMO K=8、1500 iter、3 seed（§6） | **已经执行**（缩减） | 只有 BC（5–20 epochs）+ REINFORCE 30–220 updates；无 DAgger/API、无 POMO K=8 证据 |
| E19 | 预注册 G-a/G-b/G-c（O/N4/KL）（§7） | **缺少实现** | 被替换为 `V_cluster≥0.05 + cost≤1.01 + uniform-shrink`；无 O、N4、KL |
| E20 | Formal：30 日/图、Wilcoxon、Holm、bootstrap 10,000、P1–P4（§8） | **缺少实现** | 无任何 Formal/检验/重采样；P1–P4 未执行 |
| E21 | 交付物 PREREG/SPLITS/PILOT/results jsonl/FINAL_TABLES/STATS/ENV/REPORT_ZH（§9） | **缺少实现**（部分） | 有 PROTOCOL/REPORT/STATE/VERIFICATION/结果 JSON；无 PREREG、SPLITS、STATS、ENV、中文报告 |
| E22 | 诚实规则：不删失败、不改分母、不事后换基线（§10） | **已经执行**（有瑕疵） | `all_failures_retained=true`、toy 被作废、失败行保留；但 D8/D10 的对照与人口选择存在口径问题 |
| E23 | 本 pilot 身份 | **已关闭** | 首包/real v2/forecast/risk/v3–v8 全部 `CLOSE_NO_FULL_RUN` |

### 4.2 WX-H（`PROMPT_WXH_value_guided_lookahead.md`）

| # | 原要求（条款） | 状态 | 实际形态与依据 |
|---|---|---|---|
| H1 | 以 WX-E 的 G-a 通过为前提（§0/开头） | **已关闭（依赖未满足）** | WX-E 全部 gate 关闭，无 G-a 通过（`PROMPT_WXH` L3/L45） |
| H2 | H0/H1/H1'/H2/H3/H2-rand 方法族（§3） | **缺少实现** | 无任何 WX-H 运行；`20261112_wx_h_v1/` 只有 `src/` 四个源文件，无 PROTOCOL/STATE/结果 |
| H3 | V_φ 训练（πθ 到日终回报、K=8、20 万状态、≤50 epoch）（§4） | **缺少实现** | 无 V_φ、无训练 |
| H4 | 1/10/100 ms 单线程硬截止预算（§5/§1） | **缺少实现** | 无任何预算曲线；静态 6s/12s 也不可用 1/10/100 ms 代替（reconciliation L40） |
| H5 | G-H1/G-H2/G-H3 与 P1–P3（§6/§7） | **缺少实现** | 无 gate 运行；且原文件定义冲突（到日终 vs 截断接零；AND vs OR，reconciliation L35-36） |
| H6 | 归因：H2 同时换 base/truncation/leaf value 的混杂（§3） | **缺少实现** | 未做单因素设计（reconciliation L37） |
| H7 | 固定同 base/tree/candidates/samples，比较 zero/trained/random V 与 prior（§3） | **缺少实现** | 未执行；random-V 不显著不能证明 trained-V（reconciliation L38） |
| H8 | 交付 wx_h/PREREG/PILOT/results/BUDGET_CURVES（§8） | **缺少实现** | 无 |
| H9 | 程序状态 | **已关闭（DEFERRED）** | `wx_h: deferred`（`20261112_wx_e/STATE.json`）；v8 `not_started_gate_closed`（`STATE_V3_V8.json`） |

### 4.3 WX-C（`PROMPT_WXC_inflight_contingency.md`）

| # | 原要求（条款） | 状态 | 实际形态与依据 |
|---|---|---|---|
| C1 | 在途 ≤1 ms 决策、降低失败率/天、成本 ≤+1%（§0/§1） | **缺少实现** | v3 只测 1 个 frontier 的 H gap；无时延、无失败率/天 |
| C2 | CONTINUE/SKIP_NEXT/RETURN_HOME/DIVERT(s)（§1） | **已经执行**（诊断版） | 4 动作 + 5 方法（CONTINUE/RETURN/URGENCY/FORECAST_DIVERT/ORACLE），但每场景只 1 次决策（`PROTOCOL.md` L11-21） |
| C3 | DIVERT 改降最近站、转场计成本（§1） | **已经执行**（未入现行合同） | 诊断内实现；handoff §7.3 明确不是当前动作许可（`STATE.json` `action_domain`） |
| C4 | 真实在途风/单体、穿越即失败、回流、停飞 60 min、U=20（§3） | **缺少实现** | 行内 `failure=null`；无停飞/回流/未完成罚 |
| C5 | dev 20 图 × 50 日（§5） | **缺少实现** | 64 场景、1 frontier、无日维度 |
| C6 | 基线 (a) 余量、(b) 机会约束 MC、(c) EWR、(d) 鲁棒、(e) MC M=64、(f) 千里眼、(g) 作者（§4） | **缺少实现** | 只有 4 个规则 + `ORACLE_BEST`；无 MC/1 ms/作者 |
| C7 | 空间诊断 G-a/G-b/G-c（失败/天 −50%/−20%、1 ms 半幅）（§5） | **缺少实现** | 被替换为 H gap ≥0.05、uniform ≤half、cost ≤1%（`PROTOCOL.md` L44-51） |
| C8 | RL 训练（BC/DAgger/POMO/风险变体/3 seed/防坍缩）（§6） | **缺少实现** | `training_started=false` |
| C9 | 统计与 P1–P3（Liu-50×30 + 50×30、Wilcoxon/Holm/CI）（§7） | **缺少实现** | 无 test 人口、无统计 |
| C10 | 交付 HEADROOM/PREREG/SPLITS/results/FINAL_TABLES/STATS/PARETO/ENV/REPORT_ZH（§8） | **缺少实现**（部分） | 有 PROTOCOL/REPORT/STATE/VERIFICATION/结果 JSON；无其余 |
| C11 | 本候选身份 | **已关闭** | `CLOSE_WX_C_CANDIDATE` |

---

## 5. C. “pilot 已关 ≠ 原方案已充分执行”：缺口清单

**总判断**：2026-11-12 关闭的是**具体有界 pilot 身份**，不是三份原 prompt 的完整方案。交接 prompt §5.4（L202）原文即：“原完整多站异构 WX-E、真实 N4、独立 uniform 重训、Formal 和论文包都没有因此完成；不能把‘pilot 已关’说成‘原三方案已充分执行’。”`PROMPT_RECONCILIATION.md` L52 同判：“有界 pilot 身份已按各自闸门关闭；原全套方案未完成”。

### 5.1 完整多站异构 WX-E 缺什么
- **站与机**：需要 N 个站、SABS/DABS 站型、SD/LD 机型、机型-任务资格；现全部为 1 站 + 2 台同质机（`Station(0,0,0)`；容量 `(2.0,2.0)`/`(2.6,2.6)`/`(2.8,2.8)`）。
- **多趟与计划巡检**：需要 Liu 实例的 planned targets、站内 target→slot→trip 联合分配、多趟装填、回本站换电；现为“一个 TARGET = 一个单目标任务”，无 planned multi-target trip（`PROTOCOL.md` L11）。
- **累计 duty 与物理约束**：duty_limit 有（270/320/390 min），RETURN 不清 duty 有；但无站型/机型差异、无完整能量-返航合同。
- **天气/单体**：需要 480 min、5 min 更新、OU 误差、隐藏阵风、移动椭圆单体与禁飞、扫掠后故障；现只有 3–5 段合成风 trace。
- **任务流**：需要背景 Poisson、p_f 故障、40% high/20–45 min 截止；现为固定 12–16 个任务、deadline 10–55 min。
- **对照**：需要 A1/A2/A3 + N1–N5 + O；现只有 5 个非 RL 规则/扰动控制。
- **结论边界**：现结果只能支持“单站同质 2 机、单日、合成风下的负结果”，不能外推为完整 WX-Storm/Liu 结果（reconciliation L21）。

### 5.2 真实 N4 缺什么
- 原 N4：**同一生成模型**下采样单体演化/故障/背景请求，用**公共后验**更新风暴方向 δ，基策略取 dev 最强 N1–N3；两档：(a) 单次决策预算=RL p99、(b) M=32 不限预算参考（`PROMPT_WXE` L109-111）。
- 现状：`ROLLOUT_8/128` 被明确记为 public-state scoring controls，不是完成的 MC rollout（`REPORT.md` L21；`STATE.json` `baseline_implementation_boundary`）。
- 缺：公共后验更新、隐藏阶段条件化、完整因果续接到终局、同预算硬截止、M=32 参考档、全部实际墙钟入账（reconciliation L23；`CAUSAL_ROLLOUT_APPENDIX.md` T1–T7）。

### 5.3 独立 uniform 重训缺什么
- 原 P3：把“故障跟随风暴路径”换成“空间均匀分布的故障”，**期望数不变，在 dev 上重训，在 test 上评估**，RL 相对 N3 的优势应缩到一半以下（`PROMPT_WXE` L152）。
- 现状：uniform 只是**同一模型的评价反事实**；训练集同时含 clustered/uniform 两种 train 场景（各 driver `train = [... for clustered in (True, False) ...]`），没有“只在 uniform 上重训”的独立 checkpoint。
- 结果：`V_uniform` 只能说明“同一策略在 uniform 评价集上的差”，不能检验“机制依赖是否在重训后消失”。reconciliation L26 同样把“Uniform 独立重训”列为未完成。

### 5.4 Formal 缺什么
- 需要：方法/源码/模型/训练 seed 聚合/baseline 与择优/生成器/人口/预算/硬件/超时规则/指标/统计族**全部冻结并写 hash**，然后才开放 Formal（handoff §13）。
- 现状：最大 n=32 图/模式、每图 1 日、无 held-out Formal、无 PREREG/SPLITS/STATS、无配对检验/CI/校正；`formal_started=false`（各 STATE）。
- 因此：现有数字都属 development/pilot，不能当 Formal 结论。

### 5.5 论文包缺什么
- 需要：完整逐图/逐日/逐 seed 原始结果与完整解、失败/超时、数据与模型 hash、生成器与排除清单、源码与环境、复现命令、训练全成本、统计脚本与全比较族、主张-证据矩阵（handoff §14）。
- 现状：只有 action trace + 聚合 gate；无完整解文件、无 STATS/FINAL_TABLES、无 claim-evidence 矩阵、无中文报告；G7/G8 未开始。
- 没有阳性结果可写：所有 gate 关闭，不能先写正向论文。

---

## 6. D. 为什么禁止 v9/v10 加 seed 继续救；WX-H deferred 的前提

### 6.1 v9/v10 + 换 seed 的禁止依据
1. **身份级一次性 gate**：每个包的 PROTOCOL 都在运行前写死“任何条件失败 → 关闭该候选、不启动全量”。`REPORT_V3_V8.md` L46-47：“WX-E is closed after the preregistered bounded v3-v8 review… Any future WX-E reopen requires a new protocol, fresh map identities, and an explicit gate.”
2. **交接 prompt 的明文禁止**（§5.4 L202）：“未完成原方案不等于准许给同一失败候选加 v9/v10、换 seed 后继续救结果。”
3. **不得在已暴露 DEV 调参**（§11 C.6 L476）：“失败后关闭这个机制与身份，不在其 DEV 继续调参。”；§12.8 L543：“任何新候选须有实质新原因、前置登记和资源身份，不能用 seed／网络／版本号轮换直到碰巧赢。”
4. **实证上就是同一候选的版本轮换**：v3→v8 已用 6 个版本 × 3 seed（≥18 个 seed 级估计），最好值 +0.0208（单 seed）仍低于 0.05；随后 v7 pooled +0.0017、v8 −0.0903。继续加 v9/v10 等于**在已暴露人口上做 optional stopping / seed shopping**，任何“显著”都不可解释。
5. **没有新机制**：G0 裁决为 NO-GO（多个包/审计重复确认），v9/v10 不会产生新的数学对象；换 seed/网络/几何不构成“实质新原因”。
6. **没有新人口与新预算**：v5/v6 复用同一 EVAL 600–615；`PROMPT_RECONCILIATION` L52 明确“本更正没有分配新数据、预算或科学运行”。旧 7.5/16 核小时预约不等于新的训练额度。

**可替代的合法路径**（若将来重启 WX-E）：新 G0 对象（明确新构造/估计步骤）→ 新冻结人口（新 generator seed、多日、排除清单）→ 事前冻结唯一 gate 与统计族 → 资源登记 → 3 个独立训练 seed → 最强同信息 non-RL。缺一项都不准入。

### 6.2 WX-H deferred 的前提条件（逐项未满足）
1. **WX-E G-a 通过**（`PROMPT_WXH` L3：“必须在 WX-E 完成 pilot（G-a 通过）之后”）：WX-E 从未通过任何 gate。
2. **G0 与 G3 通过**（handoff §7.2 L313：“当前 WX-H deferred。前提与 G0/G3 没过时不启动”）：当前 G0=NO-GO、G3 未通过。
3. **冻结 H1 定义与 gate 真值表**：到日终 vs 截断接零；AND vs OR（reconciliation L35-36）。
4. **冻结单因素归因设计**：H2 不得同时更换 base policy、截断和叶价值（reconciliation L37）。
5. **直接检验 trained-V vs zero/random-V 差值及 CI**：random-V 不显著不证明 trained-V 有效（reconciliation L38）。
6. **V 的目标策略匹配**：V_φ 按 πθ 回报训练，换 μ 后须说明匹配或偏差（reconciliation L39）。
7. **预算语义**：1/10/100 ms 单线程硬截止，不能用静态 6s/12s 替代（reconciliation L40）。
8. **真实 rollout 底座**：WX-H 需要 N4 级真实因果续接，而 N4 本身尚未实现（§5.2）。

**结论**：WX-H 现在既不是“已证伪”，也不是“可以跑”；它是**未准入**。一旦 1–8 满足，才可按原规划的 1/10/100 ms 预算曲线与消融执行。

---

## 7. E. 首次失败的工程细节与“不能漏记失败”的方法论含义

### 7.1 risk v1 的 NaN 序列化失败（可完整复原）
- **运行**：`wx_e_risk_driver.py --pilot results/PILOT.json`（<COMPUTE_HOST>，PID=4231，nohup）。3 条训练流全部完成（各 220 updates，3 个 checkpoint 已写盘），512 行评价也已算完；**唯一失败发生在最终写文件**。
- **报错原文**（`results/pilot.log` 保留）：
  ```
  File ".../wx_e_risk_driver.py", line 545, in _pilot
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
  ValueError: Out of range float values are not JSON compliant: nan
  ```
- **根因（比“随机 NaN”更具体）**：崩溃版本的 gate 代码写死了 `len(pooled_cluster) != 48`（= 16 图 × 3 seed，来自 v8 的旧人口），而 risk v1 实际是 32 图/模式 → pooled 96 行，检查恒为真 → `vc=vu=cr=cn=float("nan")`；该 NaN 被原样塞进 `gate` 字典（没有 `isfinite → None` 保护），`allow_nan=False` 于是抛错。
- **证据链**：`ROLLBACK_COPY/modified_driver.py`（28,495 B，运行版本）第 521 行是 `!= 48`、第 533 行是 `"V_cluster": vc`、第 545 行正是 traceback 的 `write_text`；当前 `wx_e_risk_driver.py`（33,316 B）已改为 `!= 96` + `isfinite else None` + 新增 `--saved-eval`。两版 `FEATURES` 均为 28，checkpoint 可兼容加载。
- **恢复**：`--saved-eval results/PILOT_SAVED_EVAL.json` 只加载 3 个 checkpoint（`models_reopened=[103,211,307]`）、**不重训**（`training_reopened=false`），重跑评价，得到 512/512 完整且 512/512 回放的 `PILOT_SAVED_EVAL.json`（`serialization_recovery=true`）。独立审计 `PASS_INDEPENDENT_RESULT_AUDIT`。
- **真相细节**：第一次运行的 512 行评价**只存在于内存**，随崩溃丢失；现存 512 行是第二个进程重算的。因此“首次运行产出了 512 行”是错的，“首次运行的 3 个 checkpoint + 第二次评价产出 512 行”才对。

### 7.2 另外两类“首次失败”也必须保留
- **首包 toy 被误当科学结果**：`results/PILOT.json` 的 -0.40625/1.20743 一度进入全局 STATE 与 plan；`VERIFICATION.txt` L4 事后把它标为 `INVALIDATED`。这不是崩溃，而是**来源错误**，危害更大——它让“首包有强负结果”写进了上游摘要（D1）。
- **首包 real 的两次事后修正**：CVaR 对 unserved 的 `horizon−deadline` 语义、`STORM_PREPOSITION` 的 hidden centroid 读取（`VERIFICATION.txt` L30-31）。两次都在 <COMPUTE_HOST> 重跑，gate 不变，但**产生了新的 driver/result 哈希**，并留下 D5 的哈希链矛盾。
- **WX-C 跨运行时 fingerprint**：v1 只本地、v2 首 server、v3 做定点规范化；v3 用递归数值比较（rel_tol=abs_tol=1e-12）与同源 fingerprint 比对证明 0 差异，才把 320 行固定为终局。

### 7.3 方法论含义（为什么“不能漏记失败”）
1. **失败阶段必须可区分**：训练失败、评价失败、序列化失败、传输失败是不同事件。risk v1 若只写“pilot failed”，就会丢掉“3 个 checkpoint 已完成、512 行可恢复”这一事实；反之若只写“512 行完成”，就会丢掉“第一次运行 exit 1、评价被重算”。
2. **NaN 必须 fail-closed**：NaN 进入 gate 字段会让门槛“看起来不适用”。这里 `allow_nan=False` 的硬失败是**正确行为**；修法应是修分母/检查（48→96）并把非有限值显式记成 `null` + 失败标记，而不是允许 NaN 落盘。
3. **checkpoint 是崩溃间唯一的桥**：如果训练只在最后一次性保存，这次失败会丢掉 660 个 update 的全部计算；反之，重开评价必须**明确标注未重训**，否则 512 行会被误读为“第二次独立训练”。
4. **“成本更低”必须与完整服务绑定**：v2 的 0.7567 与首包的“低成本”都来自少服务任务；后续协议把 complete-service 写成 gate 的前置条件（`REPORT_V2`/v3 起），这是从失败里得到的正确修正。
5. **上游摘要不得继承下游已作废数字**：D1 说明，一个被本地明确作废的 toy 结果，只要进入全局 STATE/plan，就会被后续 prompt 当成“首包实收据”继续引用。失败与作废必须沿同一哈希链向上撤回，而不是只写在包内 REPORT。

---

## 8. F. WX 合同门槛原文 vs 实测口径

### 8.1 原文（逐条）
- **成本比**：“成本约束：RL 成本相对‘最强 NoRL’的比值，其 **bootstrap 95% CI 上界 ≤ 1.01**。”（`PROMPT_WXE` §3.6 L100）
- **CVaR90**：“迟到 CVaR₀.₉，即**迟到分钟分布最差 10% 的均值（按天计算，再对天取平均）**。”（§3.6 L93）
- **J**：“J = 固定 + 0.5·忙碌时间 + 0.5·计划 makespan + 30·高优先迟到分钟 + 10·普通迟到分钟 + P·失败，P∈{50,100,200}，主报 P=100。”（§3.6 L92）
- **P1**：“高优先准时率至少 **+2 个百分点**，CVaR₀.₉ 至少 **−10%**，且成本约束成立。”（§8 L148）
- **G-a**：“O 相对 N1–N3 最好者：J 至少 −3%，或高优先准时率至少 **+5 个百分点**；**并且** N4(b) M=32 相对最好者：J 至少 −0.8%。”（§7 L133-135）
- **G-b**：“每 seed 训练 ≤2 h 后，dev 上 RL 相对最好者：J 至少 −0.5%，或高优先准时率至少 **+1.5 个百分点**，3 个 seed 中至少 2 个达到。”（§7 L136）
- **G-c**：“KL(RL‖BC) > 0.01，且 ≥5% 的决策与 N3 不同。”（§7 L137）
- **统计**：“每张图对天取平均，n=50；配对 Wilcoxon 双侧；Holm 校正；bootstrap 95% CI（按图重采样 10,000 次）。”（§8 L143-146）
- **P3/P4**：uniform 故障重训后优势缩到一半以下；σ×1.5、单体速度 +30% 的退化不超过 N3（§8 L152-153）。
- **WX-C**：“失败/天至少 −50%”“−20%”“成本 ±0.5%”“1 ms”（`PROMPT_WXC` §5 L51-53）；P1：“失败/天至少 −15%，成本 CI 上界 ≤ +1%”（§7 L69）。
- **交接总述**：“成本比 bootstrap 95% CI 上界 <= 1.01、每日迟到最差 10% 的均值 CVaR90”（handoff §3.3 L85）。

### 8.2 实测口径（逐项差异）

| 合同量 | 原文定义 | 实测定义 | 差异与后果 |
|---|---|---|---|
| 成本比 | 比值 + **bootstrap 95% CI 上界** ≤1.01 | **单点 map-mean 比值**（各包 gate `cost_rl/cost_nonrl`） | 无重采样、无上界；risk 的 1.00795“通过”只是点估计，CI 上界未知 |
| CVaR90 | 迟到分钟最差 10% 均值，**按天再平均** | 每行 `lateness_cvar90`（按任务取尾部；unserved 记 `horizon−deadline`） | 尾部单位（任务 vs 天）、是否含零迟到、未服务处理未被 gate 冻结；且**不入门槛**（只在 risk 作 reward） |
| J | fixed+0.5 busy+0.5 makespan+30/10 late+P fail | **从未计算 J**；只报 cost=flight+service+wait+decision-min | 成本口径不同；“成本约束”不是 J 的约束 |
| 高优先准时率门槛 | P1 +2pp；G-b +1.5pp（2/3 seeds）；G-a +5pp（O） | 单门槛 **+0.05（5pp）**，按 pooled 或 single-seed | 数值、比较对象、统计单位都不同 |
| G-a | O −3% J 或 +5pp，且 N4(b) −0.8% J | 无 O、无 N4 | 未执行 |
| G-b | ≤2h 训练、−0.5% J 或 +1.5pp、2/3 seeds | 30–220 updates、无 J | 未执行 |
| G-c | KL>0.01 且 ≥5% 决策不同 | 未记录 KL/动作改变率 | 未执行 |
| 统计 | n=50 图、Wilcoxon、Holm、bootstrap 10,000 | 无检验、无 CI、n=4–32 图、1 日/图 | 未执行；不能引用任何 p 值 |
| uniform 机制 | 独立重训后再测 | 同一模型换评价分布 | 未执行（§5.3） |
| 鲁棒性 | σ×1.5、速度 +30% | 无 | 未执行 |
| WX-C 指标 | 失败/天 −50%/−20%/−15%；成本 ±0.5%；1 ms | 高优先准时 **gap 1/6**；oracle 成本比 ≤1%；**无失败率、无时延** | 指标被替换；1/6 的 95% 区间未计算（每模式 32 场景，出现增益的场景数很少） |

### 8.3 成本比对照选择敏感（同包不同对照）

| 包 | gate 对照（按 H 选） | gate 比值 | 最低成本对照 | 最低成本比值 | 结论是否翻转 |
|---|---|---:|---|---:|---|
| v3 | `STATIC_RULE` 76.8046 | 0.9481 | `ROLLOUT_128` 69.0457 | **1.0546** | 是（>1.01） |
| v4 | `STATIC_RULE` 78.4654 | 0.9829 | `ROLLOUT_8` 74.2773 | **1.0384** | 是（>1.01） |
| v5 | `ROLLOUT_128` 89.9245 | 1.0862 | 同左 | 1.0862 | 否（已失败） |
| v6 | `ROLLOUT_128` 89.9245 | 0.8999 | 同左 | 0.8999 | 否 |
| v7 | `STATIC_RULE` 100.7358 | 0.8876 | `ROLLOUT_8` 95.6854 | 0.9345 | 否 |
| risk | `STATIC_RULE` 89.7473 | 1.0079 | `FORECAST_RULE` 87.7813 | **1.0305** | 是（>1.01） |
| forecast | `ROLLOUT_128` 93.6388 | 0.9433 | `BC` 92.0496 | 0.9596 | 否 |
| v2 | `STATIC_STANDBY` 91.6582 | 0.7567 | `ROLLOUT_128` 69.3603（不完整，应排除） | 1.0000 | 不适用（不完整） |

**要点**：原文只写“最强 NoRL”，未冻结“按 H 还是按成本选”。实测中 v3/v4 排除了更便宜且 H 相同的 rollout 控制，risk 用 H-最优而非成本最优，导致“成本过/不过”依赖对照选择。这是**口径缺口**，不是算术错误；未来协议必须事前写死对照选择规则与 tie-break。

---

## 9. G. 判定、未决与下一项有界工作

### 9.1 判定（可直接引用）
- **已证实事实**：13 个包、3,520 行结果（含 toy 与 WX-C v1）全部落在本地包内；server 运行 3,200 行；10 个 WX-E 包与 1 个 WX-C 候选全部按各自 preregistered gate 关闭；可采信的 WX-E `V_cluster` 为：首包 0、v2 0、forecast −0.0952、risk −0.0260、v5 −0.0104、v7 +0.0017、v8 −0.0903，最大值为 v6 单 seed +0.0208（<0.05）；WX-C 的 clustered/uniform gap 同为 1/6。
- **未证实/不可引用**：任何 RL 优势、任何机制新颖性、任何“成本条件稳健通过”、任何“pilot 已充分执行原方案”、任何“v9 会有希望”。
- **失败/关闭**：WX-E 全部身份、WX-C candidate、WX-H（DEFERRED）。
- **冲突采信**：D1–D12 已列；最关键的是 **D1（首包数字）**、**D5（首包哈希链）**、**D9（v5/v6 单 seed）**、**D10（v6 复用 v5 人口）**。

### 9.2 仍未解决（需要后续有界工作）
1. 首包 `ca516994` “final” 结果在服务器是否存在、其行级 CVaR/STORM_PREPOSITION 语义是否与本地 60a6b6b6 一致（需 <COMPUTE_HOST> 只读核对；本任务未连服务器）。
2. v3–v8 与 forecast 的 checkpoint 是否仍在 <COMPUTE_HOST>，SHA 是否可补录（本地全缺）。
3. v5/v6 单 seed gate 是“实现偏差”还是“事后选择”：需查 driver 历史版本与提交时间线（本地只有最终文件）。
4. WX-C 1/6 gap 的 95% 区间与“32 场景中几个场景有增益”——本文未计算（不做新统计）。
5. 全局 STATE/plan/交接 prompt 的 D1 数字是否应加“toy/invalidated”标注（属于文档更正，不是新实验）。

### 9.3 下一项有界工作（建议，不含新科学）
- **只做文档级更正**：在 `20261112_takeover_completion/` 内新增一份 `WX_NUMBER_CORRECTIONS.md`，把 D1/D6/D9/D10 以“原引用→实收据→采用值”三列写清；不改历史文件。
- **只读服务器核对**（若父 agent 允许连 <COMPUTE_HOST>）：核对 `ca516994`、6 个包的 `results/models/*.pt` SHA、以及 `<EXECUTION_PATH>` 下各包是否仍有 `PILOT.json` 初版；不重跑任何 pilot。
- **不建议**：v9/v10、任何 seed 轮换、任何“把 WX-E 包装成 S 已通过”的写法。

**是否需要用户决策**：本核对范围内**不需要**。若父 agent 要连服务器补齐 D5/checkpoint 证据，需要一次明确的“只读 <COMPUTE_HOST>”授权；否则以上全部结论已可由本地包闭环。

---

## 10. 证据索引（本地路径 + 关键哈希）

**必读 6 份 REPORT + reconciliation（逐份通读）**
- `joint_weather_emergency/20261112_wx_e/REPORT.md`（21 行）
- `joint_weather_emergency/20261112_wx_e_real/REPORT_V2.md`（53 行）
- `joint_weather_emergency/20261112_wx_e_forecast_v1/REPORT.md`（51 行）
- `joint_weather_emergency/20261112_wx_e_risk_v1/REPORT.md`（58 行）
- `joint_weather_emergency/20261112_wx_e_v8/REPORT_V3_V8.md`（55 行）
- `joint_weather_emergency/20261112_wx_c_spatial_diag_v3/REPORT.md`（40 行）
- `project_status/20261112_original_prompts_cfa_audit/PROMPT_RECONCILIATION.md`（52 行）

**三份原 prompt**
- `.../ORIGINALS/PROMPT_WXE_storm_urgent.md`（175 行；SHA256 `d0b265003cf5fb6a4ccaa5ffc5e76dcb8a2beed1faec8cdac7ee7fbe753d23aa`，与带 (1) 副本同哈希）
- `.../ORIGINALS/PROMPT_WXH_value_guided_lookahead.md`（61 行；SHA256 `e17be3a0d05cff80eeafcb4a80d2d0384b4488790501104011d864a6001e00ff`）
- `.../ORIGINALS/PROMPT_WXC_inflight_contingency.md`（83 行；SHA256 `b8376447bf587b2800f61c761dafd01b311258cd7d570ada403c4ee32d44a72c`）

**原始结果与哈希（本次实际计算，未改文件）**
| 文件 | SHA256（本地） | 与记录一致 |
|---|---|---|
| `20261112_wx_e/results/REAL_PILOT.json` | `60a6b6b6ae18059698bd77c2d60eedc7c1a534541c1597b0f9d168ac84332a73` | 与 STATE 一致；与 VERIFICATION 的 ca516994 不一致（D5） |
| `20261112_wx_e/results/PILOT.json`（toy） | `26e02e93a0384e4eb72965f3574521f771d8831c32b5d634bcd24c277d25bd1d` | 一致（已作废） |
| `20261112_wx_e_real/results/REAL_PILOT_V2.json` | `b338f6ff708c4af185043411d38f35064cce34be7d44bc798df45d500c5f2b1a` | 一致 |
| `20261112_wx_e_forecast_v1/results/PILOT.json` | `3146bda36dd991c1a2d3d0766d104126218997fb2895c0ec56d4d3d8b6f7d5e2` | 无记录可对 |
| `20261112_wx_e_risk_v1/results/PILOT_SAVED_EVAL.json` | `dd11fcb7491180edf0324855b487dbabdbd5e0eae74728a9e18ceb4003521004` | 一致 |
| `20261112_wx_e_v3/results/REAL_PILOT_V3.json` | `379636ffa1ad545c60e367982775f4bd422ed8a0947d2edcd9c88406abc91c71` | 一致 |
| `20261112_wx_e_v4/results/REAL_PILOT_V4.json` | `04e22c53f6d9b0df97ab2b637a74d09ba4c8b37a5a8c1f9307a6040b785da370` | 一致 |
| `20261112_wx_e_v5/results/REAL_PILOT_V5.json` | `1975c1ad00e52d324c3158378953dac83bf8b626e82ffc980dc311895b7282ce` | 一致 |
| `20261112_wx_e_v6/results/REAL_PILOT_V6.json` | `a504355391fbbefd0841f5779c1f4889625620665622696a7833fb580d19d0a6` | 一致 |
| `20261112_wx_e_v7/results/REAL_PILOT_V7.json` | `3978c5ef936acf97e701b1907b1bae5c3fcaaec0158d1e506368225917bc100b` | 一致 |
| `20261112_wx_e_v8/results/REAL_PILOT_V8.json` | `737839da5d319c248ea378c1947fd6dc505db4079733e976f59d42e852d68be0` | 一致 |
| `20261112_wx_c_spatial_diag_v3/results/SERVER_EXPANDED.json` | `da3cf82b5ac872d4eea7531448c1b558eab79464f1f2041b95cabc4f7be205d0` | 无记录可对 |
| `20261112_wx_c_spatial_diag_v3/results/SERVER_BASELINE.json` | `b23c975b7867479126b3a59f3f26247da515d2fce54f5e3d5cffd7a57e387f49` | 无记录可对 |

**其他关键证据**
- `20261112_wx_e/VERIFICATION.txt`（toy 作废 L4；final hash L28；CVaR/centroid 修正 L30-31）
- `20261112_wx_e/STATE.json`（`toy_pilot_status`、`server_result` 指向 toy、`scientific_pilot`）
- `20261112_wx_e_real/VERIFICATION_V2.txt`（L44-46 假阴性 `cmp`）
- `20261112_wx_e_risk_v1/results/pilot.log`（NaN traceback，line 545）
- `20261112_wx_e_risk_v1/ROLLBACK_COPY/modified_driver.py`（崩溃版本：`!= 48`、raw NaN）
- `20261112_wx_e_v8/STATE_V3_V8.json`（6 包聚合、v6 不完整行）
- `20261112_wx_c_spatial_diag_v3/results/INDEPENDENT_AUDIT.json`（rows=320, scenarios=64, rows_per_scenario=5）
- `route_rl_research/20261103/return_makespan/STATE.json` L1227-1248（全局账本的 WX-E 首包 = toy 数字）
- `LATEST_STATUS.md` L65（“PLAN_EXECUTED_WITH_GATES_NO_BREAKTHROUGH 只限已登记 pilot”）、L103-105（risk 收据）
