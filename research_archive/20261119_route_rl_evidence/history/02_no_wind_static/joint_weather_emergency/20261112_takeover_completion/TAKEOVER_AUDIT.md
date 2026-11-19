# TAKEOVER_AUDIT — 2026-11-12 接手审计与全史矩阵

**文件定位**：`joint_weather_emergency/20261112_takeover_completion/TAKEOVER_AUDIT.md`。本文件是本轮接手工作线程的正式产物，只做**本地静态审计**：读取原字节、对齐协议与分母、建立历史矩阵、登记冲突与四张状态表。**不新增任何科学结果**，不修改历史文件，不连接 <COMPUTE_HOST>，不运行求解/训练/评价/地图生成。

**执行身份与边界**：接手审计文档线程（DeepSeek Harness，2026-11-12 Asia/Shanghai）。本轮没有服务器实收据产出；文中出现的 <COMPUTE_HOST> 事实均为**引用既有收据**（注明路径），不是本次观测。

**读取规模**：`HISTORY_INDEX.json` 收录 5,908 条记录、按 SHA256 去重 3,130 个不同哈希、897 条快照/副本提示、204 个包、378,202,023 字节；后缀分布 `.md 1,797／.json 1,075／.txt 2,896／.pdf 118／.ris 17／.bib 5`。本审计用该索引做**去重导航**（例如 `LATEST_STATUS.md` 有 85 份副本、`AGENTS.md` 同哈希 7 条路径、`ROUND_DECISION.md` 19 份），只读 canonical 路径一次，不把重复快照当独立证据。

**一句话结论**：复现已完成且可信；旧算子控制、旧 Stage A、联合动态 RL、方法族 A/B、D/E、全部 WX pilot 均为**保留的负结果或未完成**；G0 = NO-GO，G3/G4 未通过，G5–G8 未完成；整体研究未完成，无可信突破，不得写正向论文结论。

---

## 1. 结论摘要（先看这 12 条）

1. **复现是唯一“完成”级成果**：120 官方图 × 5 seed × P1/P2 = 1,200 配对运行全部可行、独立审计 600/600 + 600/600、1,200 份 Java witness 重开；P1 地图均值差 −0.0284113%（CI 含 0），P2 +0.0997583%（CI 全正）。证据 `reproduction/reviewer_package_semfix/SEMFiX_FULL_RESULTS.md`。
2. **旧 CA-RL 宏控制（算子选择）失败**：1,440 行消融中 PPO 相对 NoJoint 成本 **更高**（6s +0.079127%，Holm18 p=0.228271；12s +0.038654%，p=1）。证据 `execution/20261102/state_ablation/analysis/REPORT.md`。
3. **旧 Route-RL Stage A 失败**：720 任务全部可行，但相对 route-only ALNS 为 −0.966725%（6s）／−0.955678%（12s），地图 W/L/T 0/21/3；相对 Greedy 的 +0.649531%／+0.668982% 不足以过闸。证据 `stage_a_audit/MODIFIED_FILE.md`。
4. **return_makespan 账本**：40 个新身份、40 次作者尝试（上限 48）、126 次实际比较（旧 66 + 新 60）、非 RL 84／RL 36／BC-only 6；隔离校准验证 **24/24 已满**；科学 non-RL **预约 7.5/16 核小时**（预约额，非实耗结算）。证据 `route_rl_research/20261103/return_makespan/STATE.json`。
5. **G3 未通过**：两批 8 新图、80 意向行、60 次实际比较、47 按时交付、5 超时、8 导入失败、20 锚点不合格跳过；第二批天气锚点仅 2/4（`calibration_5` `battery:2:0:0`、`calibration_8` `battery:1:1:0`）；73 次回放发现 **10 条被丢弃的改善 incumbent**（一批 6、二批 4）。证据 `.../g24_weather_nfz/status_reconciliation_g3_20261105/ROUND_DECISION.md`。
6. **联合天气—应急深度重构负结果**：9 运行、768 优化器步、960 保存轨迹、1,184 评价行；登记最强 non-RL `oldbeam` J=**1169.612132**，SCST/LOO J=**1188.621808**（**+1.6253%**，8/8 DEV 图落后，区间 [14.390618, 23.703597]）；6 个 actor seed 全部选回 initial。证据 `joint_weather_emergency/20261105_deep_revision/REPORT.md`。
7. **瓶颈诊断**：TRAIN-only 8×SCST（3 seed × 256 updates）只带来 −0.025376% 的均值变化；限幅 `prior + 6*tanh(raw/6)` 使 2/16（prior 续接）与 3/16（oldbeam 续接）状态下最低 J 候选不可达；去限幅（unbounded）诊断拟合 12/16 vs 16/16。**限幅是部分解释，不是全部差距的证明**。证据 `joint_weather_emergency/20261105_bottleneck_diagnosis/REPORT.md`。
8. **方法族 A/B/C**：A 的 LOO 385.3993135（−1.0467% vs 自身 initial，仍不及 deadline）；B 的 13 后端 × 3 seed 中最低完整 RL 为 LOO 393.652424，但 `author_dispatch` 392.967769 更低（差 +0.174227%，6W/6L，p=0.7866）；C 只把 3 个控制器资格定为 `QUALIFIED_REPRESENTATIVE_NOT_STRONGEST_GLOBAL`（J 367.0909614／368.4344257／373.8004826）。证据 `.../20261105_method_screen/SCREEN_DESCRIPTIVE.json`、`.../20261106_method_family_B/readonly_audit/B_METHOD_DECISION.md`、`.../20261106_control_qualification_C2_infrastructure/STATE.json`。
9. **D 因输出硬限终止**：30 流中 18 完整审计、3 部分、9 未见训练目录；2,880 VAL + 26,880 SELECT = **29,760 评价键全部 PLANNED_NO_RECORDED_INTENT**；输出 **12,045,821,536 B > 12,000,000,000 B** 硬限，原 driver exit **−9**；wall 19,361.69 s、cgroup CPU 60,944.76 s。证据 `20261106_server_recovery/D_TERMINAL_RECONCILIATION/RESULT.json`。
10. **E 未科学准入**：`E_ENGINEERING_ADMISSION_PROGRESS_NOT_SCIENTIFICALLY_ADMITTED`；两包 25 项与 16 项工程检查通过，但 `scientific_E_training_started=false`、9 项 pending。证据 `20261106_E_continuation_acceptance/STATE.json`。
11. **WX 全线关闭**：v1、real v2、forecast v1、risk v1、v3–v8 六包、WX-C v3 全部 `CLOSE_*`；最近候选 v6 的 V_cluster 仅 +0.020833 < +0.05 且 uniform-shrink 失败。WX-H 仍 deferred（0 运行）。证据 `20261112_wx_e*/REPORT*.md`、`20261112_wx_c_spatial_diag_v3/REPORT.md`。
12. **G0 仍 NO-GO**：本轮及上一轮共 5 个 G0 关闭 + reserve v5 静态 HOLD；没有任何新机制通过“完整输入输出／数学对象／最近先例逐式差异／可证伪预测／同信息强 non-RL／失败关闭条件”六项。证据 `project_status/20261112_*/STATE.json`、`project_status/20261112_g0_reserve_v5_static_audit/MODIFIED_FILE/PRE_RUN_REVIEW.md`。

---

## 2. 权威链：哪一份文件说了算

按“最新用户覆盖 → 主科学 STATE → 终局收据 → 包内 REPORT → 早期计划”排序。审计中一切冲突按此链裁决，并在 §5 逐条登记。

| 层级 | 文件 | 为什么是这一层 |
|---|---|---|
| L0 合同 | `AGENTS.md`、`USER_RESEARCH_REQUIREMENTS.md`、`RESEARCH_PLAN_ROUTE_RL.md` | 含 2026-11-03 动作域纠正（只做物理路线，不做算子选择）与 2026-11-05 root-only 覆盖 |
| L1 总入口 | `LATEST_STATUS.md` | 倒序累积；**首项最新**，旧项是历史。本审计读取的首项为 2026-11-12 公共告警条件化 |
| L2 主科学状态 | `route_rl_research/20261103/return_makespan/STATE.json`（72,223 B） | 40 身份／126 比较／24-24／7.5 核小时／G0–G8 的机器可读主账本；`status=JOINT_DEVELOPMENT_COMPLETE_NEGATIVE_3SEED672_EVALUATIONS; G0_G3_G4_NOT_PASSED` |
| L2b 第二科学状态 | `joint_weather_emergency/20261106_E_continuation_acceptance/STATE.json` | E 未科学准入 + 原 D 终止的权威状态 |
| L3 终局收据 | `.../20261106_server_recovery/D_TERMINAL_RECONCILIATION/RESULT.json` 等 | 进程 exit、输出字节、覆盖计数；优先于任何“TRAINING/正在跑”文字 |
| L4 包内 REPORT | 各 `REPORT*.md` | 数字与口径的一手描述；与 JSON 冲突时以 JSON 为准（见 K4/K5） |
| L5 早期计划 | `EXECUTION_PLAN.md` 表体、`route_rl_research/20261103/STATE.json` | 自述已被覆盖（`SUPERSEDED_BY_APPROVED_RETURN_MAKESPAN_EXECUTION_STATE`），只作历史 |

**明确不作权威的**：`20261113_wx_e_reserve_v5` 目录名与其中 READY 字样（日期晚于本机日期、schema 仍是 v3、已被 9 项源码事实推翻）；各 STATE 里的 `TRAINING`／`PENDING_AUDIT` 字样（无终局收据时不构成完成）；旧 goal 的 `active`（交接时原 goal 实为 paused）。

---

## 3. 历史矩阵（主表）

> 说明：为可读性，单元格只放**关键量与分母**；完整叙述、哈希与逐项失败在 §4 分阶段明细。所有“行/图/日/seed”均为报告中登记的分母。预算列写**实际消耗**；只有预约额时标“预约”。

| # | 阶段 | 问题／动作／目标 | 数据身份（地图／事件日／seed） | 算法与 baseline | 实际执行量 | 主要结果（数字＋分母） | 失败／关闭原因 | 剩余项 | 预算消耗 | 原始证据 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 早期静态机制筛查 R2–R7＋证书＋Formal v4 | 在原模型内找可发表的非 RL 机制与强对照；判断 Global Assignment／跨站交换／站型定价是否独立创新 | Formal v4：30 主图×10 求解 seed×6/12s；R2：12 已暴露图；R4：12 旧图 144 donor；R7：132 raw 图 | exact oracle／ALNS／SA／MIP／DP 证书；Formal v4 十方法 | 1,440 消融行（24×3×10×2）；360 任务（12×3×5×2）；132 图 50,040 对扫描；Formal v4 约 600 行（30×10×2，按设计推算） | Formal v4：M2 Global Assignment vs M2 Local −0.1010%／−0.1145%（Holm p=0.028609／0.006819），vs NoJoint p=0.9397；R2 oracle 0.003655%（3/12 正）；R4 0.073871%（5/12 正）；R5/R6/R7 全 NO_GO；LD 吸收全 CERT 102/120 与 8/12 | 均非独立创新或样本太小；Global Assignment 被 Liu 正文与官方 Java 覆盖 | 无新 Formal；10 小图 DP 旧声明仍 UNVERIFIED | R2–R7 几乎 0 求解；R4 实际 M 合计 1.176594748 s；LD 扫描 7.897 s＋独立验收 0.498 s | `related_work/fulltext_comparison_20261102.md`；`research_round2..7/20261102/ROUND_DECISION.md`；`research_certificates/*/ROUND_DECISION.md`；`execution/20261102/ROUND_DECISION.md` |
| 1 | Liu／SEMFiX 官方复现 | 忠实复现 TSALNS 的 P1／P2，验证独立可行、成本分布与论文表 | 120 官方 `Instances_Alg`（12 组×10）×seed 0–4（5）×P1／P2 | V6 Python/native（P1／P2）vs J1b／J2b Java | 1,200 配对运行；审计 600+600；重开 1,200 Java witness；32,442,312＋32,433,336 次评估；各 3,000,000 次 ALNS 迭代 | P1 地图均值 −0.0284113%（600 配对／120 图；CI [−0.071134, +0.011721] 含 0；W/L/T 53/46/21）；P2 +0.0997583%（600；CI [0.025536, 0.177271]；71/33/16）；12 个 Table 1 组均值与最优落在 95% CI 内 | 未复现作者无种子 RNG 的轨迹同一性；作者 MILP 的 t_f 口径未知 | 不再重跑；仅剩口径／边界补充 | Python 侧 elapsed 合计 4,344 s≈1.21 h（P1 1,483 s／P2 2,861 s）；Java J1b／J2b 另计 | `reproduction/reviewer_package_semfix/SEMFiX_FULL_RESULTS.md`、`REPRO_PROTOCOL.md`、`SEM_FIX_PROVENANCE.md` |
| 2 | 旧 CA-RL 宏控制／算子选择 | PPO 选择 destroy／repair 等算子与强度，能否胜强非 RL | 24 图×3 求解 seed×10 方法×2 预算；已暴露开发图；checkpoint seed 23 | PPO 宏控制 vs NoJoint 及 9 个 state 干预 | 1,440 完整解行（6s／12s 各 720）；1,440 独立重评分；18 项 Holm | PPO 相对 NoJoint 成本 **+0.079127%**（6s；CI +0.013283..+0.143807；Holm18 p=0.228271）、**+0.038654%**（12s；Holm18 p=1）；仅 12s `nohighint` 过 Holm（+0.061171%，p=0.00439453，方向是退化） | 未证明胜强非 RL；用户 2026-11-03 明确排除算子选择动作 | 关闭，仅作历史负结果 | 720×6＋720×12＝12,960 solver-s≈3.6 核小时 | `execution/20261102/state_ablation/analysis/REPORT.md` |
| 3 | 旧 Route-RL Stage A（720 任务） | RL 直接输出站内物理目标／返航，能否胜 route-only ALNS | 72 TRAIN 图（seed 1–6）、24 VAL 图（seed 7–8）；求解 seed 101／102／103；模型 seed 11／23／37 | PPO 指针网络 vs Greedy／insertion／2-opt／route-only ALNS | 24×3×2×5＝720 任务，720/720 完整解；训练 3×(60 updates×8 ep×4 epoch) | VAL 相对 Greedy：−0.0283%／−0.3307%／+0.9038%，均值 +0.1816%；等预算 vs ALNS：6s **−0.966725%**（CI [−1.259282, −0.679487]；W/L/T 0/21/3）、12s **−0.955678%**（0/21/3）；对 Greedy +0.649531%／+0.668982% | 冻结 gate 双预算失败；Stage B／C 未启动 | 不入 Stage B／C；不扩大网络 | 360×6＋360×12＝6,480 solver-s≈1.8 核小时 | `stage_a_audit/MODIFIED_FILE.md`；`route_rl_research/20261103/source_snapshot/ROUTE_RL_STAGEA_FINAL_AUDIT_20261102.md` |
| 4 | return_makespan（g23／g24_weather_nfz） | 固定部署、逐图 C≤C_Liu+1e-7、6s／12s 改善 M_return；建立 40 新身份与 G3 | 40 新身份（original6／calibration4／P2 8／P3 14／newG3 8；STATE 另记 16 opportunity＋24 calibration／validation，两者对应关系未给交叉表）；120 官方＋12,000 pilot 候选永久排除 | 作者 J1b 锚点；strict／annealed 非 RL；PPO／BC／REINFORCE | 40 作者尝试；126 比较（旧 66＋新 60）；非 RL 84（旧 24＋新 60，含 8 导入失败）、RL 36、BC-only 6；G3 二批 80 意向／60 启动／47 按时／5 超时／20 跳过 | G3 未过：一批 4/4 锚点、strict 四图均值 −8.792529%（逐图 30.309156／0／4.860960／0，仅已交付）；二批天气 2/4，两图 −1.033778592%／−0.127702999%；73 回放；10 条被丢弃改善 incumbent（6＋4） | 最强 non-RL 未建立；24/24 校准额度满；导入失败与交付偏差导致比较不对称 | G3 重开需新假说＋新数据／资源修订 | 作者额度 40/48；科学 non-RL 预约 7.5/16 核小时（预约，不是实耗） | `.../g24_weather_nfz/status_reconciliation_g3_20261105/ROUND_DECISION.md`；`return_makespan/STATE.json` |
| 5 | 联合天气—应急 20261105 深度重构 | 动态 J 下 SCST／LOO／DDQN 能否胜最强 non-RL 与作者在线适配 | 32 TRAIN＋4 VAL＋8 DEV（GitHub 已暴露源图的新联合分配）；DEV 每图 4 事件日；seed 103／211／307 | SCST／LOO／DoubleDQN vs oldbeam、deadline、mix0.5／1／2、prior、author_dispatch／insert、nearest、alignedJbeam | 9 运行；480 迭代；768 优化器步；960 轨迹（另封存 6 步／22 轨迹）；320 控制＋864 模型＝1,184 评价；1,184 独立回放 | oldbeam J=**1169.612132**（8 图×4 日、3 seed 等权）；SCST=LOO=**1188.621808**（**+1.6253%**；区间 [14.390618, 23.703597]；0/8 胜）；DDQN 1335.818453（+14.2104%）；6/9 运行选回 initial；148/192 条 last 路线与 initial 相同 | 无 RL 优越性；32 更新／96 episode 不是收敛证据 | 不在同一 DEV 调参；不追加 epoch | 每 run 训练墙钟上限 300 s；总墙钟 2,400 s 未重置；无总 CPU 收据 | `joint_weather_emergency/20261105_deep_revision/REPORT.md` |
| 6 | 瓶颈诊断 TRAIN-only 8×SCST | 8 倍训练能否自愈；`prior+6*tanh(raw/6)` 限幅是否锁死动作 | TRAIN0–3 固定 8 个 monitor 场景（2 个未参与更新的日）；seed 103／211／307 | 原 SCST 256 updates vs 32；bounded vs unbounded 监督拟合；DDQN 排序 | 768 updates／2,304 episodes；96 监测；16 控制；178 分支；2,599 回放；2×400 监督步 | 256 步均值 890.028036（−0.025376% vs initial；+1.924917% vs oldbeam 873.219292）；7/2,022 多候选改选；10/16（prior）与 12/16（oldbeam）状态有更低 J 候选，其中 2／3 个 >12 不可达；拟合 12/16 vs 16/16；DDQN top1 6/16→1–3/16 | 限幅只解释部分可达性；未证明解释全部差距 | 不据此重开训练 | 3×约 760 s（760.33／758.57／544.88）；梯度 200–271 s/seed | `joint_weather_emergency/20261105_bottleneck_diagnosis/REPORT.md` |
| 6A | 方法族 A（method_screen） | 44 新图上 3 类 RL 能否胜登记控制 | 24 TRAIN／8 VAL／12 SELECT；seed 103／211／307 | linear VFA／neural VFA／LOO vs nearest／deadline／prior／fleet／author | 9 运行；2,400 SELECT 行（2,336 DONE／64 TIMEOUT）；4,560 训练日；510 迭代 | LOO J=385.3993135（−1.0467% vs 自身 initial；−0.03196% vs deadline）；linear 389.1695、neural 389.2625；未胜强 non-RL | fleet 控制超时使登记族推断保留；仅描述性 | 未作确认性结论 | wall 2,628.7 s；训练 CPU 763.0 s；10 核小时预约 | `.../20261105_method_screen/{RESULT.json,SCREEN_DESCRIPTIVE.json,SUPERVISOR_END.json}` |
| 6B | 方法族 B（13 后端） | 13 后端×3 seed 在同一人口谁最好 | 12 图×4 事件日×3 seed；44 新图（复用） | 12 RL（VFA／PFA／SCST／LOO／PPO／A2C／DQ／dueling／quantile／SAC／ES）＋5 完整控制＋3 作者适配 | 39 运行；8,256 SELECT 意向（8,112 DONE／144 TIMEOUT）；146 工程测试 | LOO 393.652424 为最低完整 RL；`author_dispatch` **392.967769** 更低（差 +0.174227%；6W／6L；CI [−3.974,+5.481]；p=0.7866）；fleet 类 12/48 TIMEOUT（12s）不可排名 | 未胜强控制；非收敛名次 | 充分训练另审 | wall 9,249.3 s；32 核小时预约 | `.../20261106_method_family_B/readonly_audit/B_METHOD_DECISION.md` |
| 6C | 控制资格 C | 三个强 non-RL 能否被命名为“最强” | 8 个 qual 图；512 行 | complete_fleet／causal_anticipatory_fleet／source_faithful_rolling | 512 行／512 回放；PASS_ACCOUNTING | J=367.0909614／368.4344257／373.8004826；状态 `QUALIFIED_REPRESENTATIVE_NOT_STRONGEST_GLOBAL`；原 C `INTERRUPTED_INCOMPLETE_RETAINED` | 只到“代表”不是“最强”；原 C 未完成 | 需新证据才能命名最强 | worker wall 合计 841.5 s | `.../20261106_control_qualification_C2_infrastructure/STATE.json` |
| 6D | D 充分训练（训练侧） | 10 配置×3 seed 的充分预算训练／评价 | 32 TRAIN／8 VAL／24 SELECT；30 流 | set／relational LOO／PPO／SAC、linear VFA、SAC uniform／PER、prior 退火 | 30 流；2,880 VAL＋26,880 SELECT＝29,760 键 | 见第 7 行（输出硬限终止） | 见第 7 行 | — | 见第 7 行 | `.../20261106_sufficient_training_D/`；`D_TERMINAL_RECONCILIATION/` |
| 6M | 多目标 HV 复核 | 换多目标后 RL 是否整体领先 | B 的 12 图×4 日×3 seed 重评；8,256 意向 | 完整非 RL 19 候选 vs RL 12 候选 | 68 单元（62 完整／6 含失败）；4,334 算术检查 | HV：0.054164 vs 0.048132；0.151586 vs 0.115263；0.155546 vs 0.137607；0.056842 vs 0.049723；RL 覆盖更好地图 3/12、2/12、3/12、2/12；0% 成本 cap 下 RL 4/12 vs 非 RL 12/12 | 事后候选集；候选数／生成成本不同；部分强控制超时 | 偏好条件化 RL 未训练 | 重评 8,256 意向；父 CPU 0.028461 s＋子 1.407091 s（原容器重评另计） | `.../20261106_github_multiobjective_check/REPORT.md` |
| 7 | D 资源终止 | 30 流能否完成并给出统一比较 | 同 6D | 同 6D | 18 完整审计／3 部分／9 未见目录；29,760 评价键 0 intent | 输出 12,045,821,536 B > 12,000,000,000 B；exit −9；wall 19,361.69 s；cgroup CPU 60,944.76 s；0 评价排名 | 输出硬限终止；无统一选模与科学比较 | 不重启、不扩限、不压缩原日志 | 60,944.76 CPU-s≈16.93 核小时（含工程开销）；输出 12.046 GB（十进制） | `.../D_TERMINAL_RECONCILIATION/RESULT.json`、`REPORT.md` |
| 8 | E 工程准入 | E 的标签与原始 J 组合是否达到科学准入 | 两工程包（learning label audit v2；originalJ author portfolio v2） | 25 项＋16 项工程检查 | 25／16 test functions；各 24 文件重开 | `E_ENGINEERING_ADMISSION_PROGRESS_NOT_SCIENTIFICALLY_ADMITTED`；`scientific_E_training_started=false`；9 项 pending | 未科学准入；原 D 不重启 | 9 项 pending（存储／driver／排除清单／typed reserve／NFZ／作者锚点／功效／VAL／HV） | children CPU 18.89 s＋34.15 s；wall 18.96／34.30 s | `20261106_E_continuation_acceptance/STATE.json` |
| 9 | WX-E 各 pilot（v1／real v2／forecast v1／risk v1／v3–v8） | 版本化 TARGET／WAIT_5MIN／RETURN 能否改善高优先准时且成本 ≤1% | v1：2 模式×4 图×8 方法；real v2：2×8×8；forecast：2×16×8；risk：2×32×8；v3–v8 各 2×16×8 | STATIC_STANDBY／STORM_PREPOSITION／ROLLOUT_8／128／BC／RL×3 | 64＋128＋256＋512＋6×256＝2,496 行 | v1(REAL) V_cluster 0.0、V_uniform 0.3333、成本 55.3720 vs 50.9727（+8.63%）；real v2 V=0、80/128 不完整、480 未服务；forecast V −0.0952381、256/256；risk V −0.0260417、成本 90.4603／89.7473＝1.00794；v3–v8 V=0／0／−0.010417／+0.020833／+0.001736／−0.090278 | 全部 `CLOSE_NO_FULL_RUN`；N4 真实 MC 未实现；ROLLOUT 只是记账控制 | 全车队异构／真实 N4／Formal 未做 | 无 CPU 收据；REAL_PILOT 在线 2.34 ms/日（clustered STATIC_STANDBY 均值） | `20261112_wx_e*/REPORT*.md`；`results/REAL_PILOT.json` |
| 10 | WX-C spatial diag v3 | 在途应急扩展是否有同成本空间 | 64 固定场景×5 行×2 模式 | baseline vs expanded（DIVERT 仅诊断） | 320＋320 行；回放率 1.0 | clustered gap＝uniform gap＝0.1666667（1/6）；uniform-shrink 失败 | `CLOSE_WX_C_CANDIDATE`；未训练 | 完整在途方案（20 图×50 日等）未做 | 无 CPU 收据 | `20261112_wx_c_spatial_diag_v3/REPORT.md` |
| 11 | 公共告警条件化 | 用已告警密度＋未告警生存因子更新后验，再抽整组未来告警 | 合成有限粒子／目标；无地图、无路线 | prior fixture vs conditional | 18 例；probe 2 模式 | 后验 (0.5,0.5)→(3/7,4/7)；早期粒子内未来告警 1/3；r=5 时 late 权重 0 | 标准 Bayes／右删失工程；未接入 simulator／planner／训练 | 多单体语义、连续 likelihood、独立预报发布未冻结 | 18 例单次约 0.04 s；科研运行 0 | `20261112_public_fault_conditioning/REPORT.md`、`server_evidence/TEST_RECEIPTS.json` |
| 12 | reserve v5 静态 HOLD | 预审 READY 是否成立 | 单站同质合成；1 站 3 机 24 应急 | v5 driver vs 原字节 | 0 运行；9 项静态发现 F1–F9 | `HOLD_G0_NO_GO`；`scientific_run_admitted=false` | rollout 仅分数扰动；LIU_ADAPTER 非作者锚点；BC 行=规则教师；uniform 未独立重训；无共同墙钟；NaN 写盘风险 | 不得用修复 F1–F9 替代新机制 | 0 | `project_status/20261112_g0_reserve_v5_static_audit/{HANDOVER_RECONCILIATION.md,MODIFIED_FILE/PRE_RUN_REVIEW.md}` |
| 13 | 五个 G0 关闭候选 | 各候选是否有独立算法增量 | 文献／解析／静态；无地图 | centered dual score；observation timing；joint-event；original prompts-CFA-PbP；Zhao-Han 全文 | 0 实验；0 训练；0 新图 | 裁决：`G0_NO_GO_CENTERED_DUAL_SCORE_STANDARD_AND_STATIC_ZERO`；`G0_NO_GO_OBSERVATION_TIMING_STANDARD_POSMDP`；`G0_NO_GO_AS_DISTINCT_ALGORITHM`；`G0_NO_GO_ORIGINAL_PROMPTS_CFA_PBP_AUDITED`；`G0_NO_GO_AS_DISTINCT_ALGORITHM_FULLTEXT_AUDITED` | 无独立构造／估计步骤；均被先例覆盖或静态恒零 | 只接受一个明确新步骤 | 0；仅文档与文件检查 | `project_status/20261112_{cfa_final_si_review,observation_timing_g0_review,g0_joint_event_screen,original_prompts_cfa_audit,zhao_han_fulltext_audit}/STATE.json` |

---

## 4. 分阶段明细（数字、分母、证据）

### 4.0 早期静态机制筛查（R2–R7、证书、Formal v4）

- **R2 条件完整趟释放**：48 个强 non-RL 完整状态、12 张已暴露图、1,152 候选、2,304 次 exact／greedy 调用；exact oracle 地图平均改善 **0.0036553114455582913%**，正号 3/12，未过标签前冻结门槛；Linux 独立重核 2,304 完整解 errors=0。证据 `research_round2/20261102/ROUND_DECISION.md`。
- **R2 下界**：地图平均“最大可能改善上界”由 12.344646914% 收紧为 **7.171842089%**（必要飞行费用下界均值 51.984130050，实际 107.415778068）；明确“不是可实现的收益”。同上文件。
- **R3 generic 多站**：G0 NO_GO；原拟 49 调用×48 状态＝2,352 质量标签**在执行前取消**（0 质量调用、0 训练）。证据 `research_round3/20261102/ROUND_DECISION.md`。
- **R4 标准强对照池**：12 旧图、144 强 donor、36 完整输出；地图均值 **0.07387133490701707%**（中位数 0；5 提高 7 零）；bootstrap [0.006290972%, 0.165519227%]；12 图 station modes 均不变。证据 `research_round4/20261102/ROUND_DECISION.md`。
- **R5 swap／k-cycle**：G0 `NO_GO／NO_EXECUTABLE_RESEARCH_INCREMENT`；k=2 已在 Liu 官方 `RoutingOperator.swap4`；10 次完整 evaluator 调用；两个完整 witness 恰达全局下界 3352/45。证据 `research_round5/20261102/ROUND_DECISION.md`。
- **R6 站型 argmin／envelope**：条件性精确 + N13 反例（F1=100、F2=1 时 default 105 vs argmin 6）；共 70 次原始 evaluator 调用；G0 NO_GO。证据 `research_round6/20261102/ROUND_DECISION.md`。
- **R7 双 slot 多趟 crew 列**：`NO_GO_AS_WRITTEN／NON_DIRECT_INCREMENT_NOT_IDENTIFIED`；0 evaluator／0 枚举／0 LP／0 训练。证据 `research_round7/20261102/ROUND_DECISION.md`。
- **证书**：energy-duty projection（8 纯测试＋9 微例＋6,360 assignment／trip 排列＋2,070 见证，0 假拒绝）；`dominance_not_lumpability`（条件性 LD 吸收**不是**当前搜索过程的精确状态商，operator 9 的 mask 反例）；`ld_absorption_scope`（132 raw 图、780 站、50,040 对；官方 120 图中 102 全 CERT／18 部分／615 CERT 站；开发 12 图中 8 全 CERT）。三者都是**基础消维**，不是创新。证据 `research_certificates/*/ROUND_DECISION.md`。
- **Formal v4 / Global Assignment**：30 主图×10 求解 seed×6／12s；M2 Global Assignment vs M2 Local −0.1010%／−0.1145%（Holm p=0.028609／0.006819），vs M0 −0.9709%／−0.3364%；vs M2 Global NoJoint **p=0.9397**（不显著）。判定：Global Assignment 的接收域扩大在 Liu §4.3.2 与官方 Java `greedyInsertMinCost`（约 890–945 行）已有先例，**不能当独立新算法**。证据 `related_work/fulltext_comparison_20261102.md`。
- **360 任务 bounded exact block（2026-11-02）**：12 新图×3 求解 seed×5 方法×6／12s＝**360**，360/360 完成、独立审计 errors=0、源码无漂移、与 3,063 历史文件／527 唯一 bytes 哈希无交集；E 对 NoJoint **+0.417354%／+0.431922%**，但对 M2 Full Joint **−1.019956%／−1.075544%**、对 M1D **−1.200328%／−1.277971%**；8 项 Holm 全未过 0.05；576 次块调用中 318 次严格改善当前解（7 次差值 ≤1e-8）。gate=NO_GO。证据 `execution/20261102/ROUND_DECISION.md` §4、`EXECUTION_LEDGER.md`。
- **completion/（V5／V6 工程）**：120 实例 14,400 步轨迹尝试（可行 2,179／3,376／2,548／2,883，零失败）、10 官方实例 exact DP 目标一致、252 项首批开发评估；`TASKS.md` 的“2/6/12/30s 1008 任务／60 未见图测试”等 7 项**仍未按原名交付**（后续 Stage A／Formal v4 是不同身份，不能算同一交付）。证据 `completion/{TASKS.md,VERIFICATION.txt}`。
- **paper_direction/PREREGISTRATION.md（2026-11-02 设计 gate）**：明确 Formal v4 只支持“`global_assignment` 在冻结合成套件上胜更窄 Python 控制”，**不是** Liu 官方优越性测试；无新方法通过、无盲测套件、无摘要级 SOTA 声明。证据 `paper_direction/PREREGISTRATION.md`。

### 4.1 Liu／SEMFiX 官方复现（1,200 配对）

- **协议**：`REPRO_PROTOCOL.md` 冻结 J0／J1／J2／J1b／J2b／P1／P2 七个身份；P1＝100 location-local／权重上界 5.0，P2＝500／0.5，均 500 outer×5,000 ALNS；比较对象分别是 J1b／J2b，不是被 pre-ALNS guard 污染的 J1／J2。
- **执行**：两条远程命令终局分别为 `COMPLETE profile=P1 maps=120 seeds=5 failures=0` 与 P2 同形；归档 SHA256 P1 `0be434a8…07de30`、P2 `67b48b8e…a068db2`；每目录 600 行 JSON＋600 压缩完整 witness＋manifest＋Linux native binary。
- **审计**：`audit_semfix_matrix.py` exit 0；P1 600/600 feasible、java_errors=0、paired_maps=120／paired_runs=600、map_mean_pct **−0.028411300166225728**、median 0.0、min −0.8572710229438614、max +0.6169728810141988、bootstrap95 **[−0.07113392502976283, +0.011720756931353287]**、W/L/T（Python）53/46/21。P2 map_mean_pct **+0.0997582636054712**、median 0.03328413553112791、min −1.149116190587324、max 1.8977236750685036、CI **[0.0255356472736774, 0.1772713838959488]**、71/33/16。
- **语义**：定义是 `100*(Java cost − Python cost)/Java cost`，正数偏向 Python；P1 区间含 0 ⇒ 不能说 Python 更好；P2 区间全正且窄 ⇒ Python 略优但幅度 <0.18%。
- **预算（本审计按行求和）**：P1 `elapsed_seconds` 合计 **1,483.0 s**、评估 **32,442,312**、ALNS 迭代 **3,000,000**；P2 **2,861.1 s**、**32,433,336**、**3,000,000**。Java 侧 J1b／J2b 的求解时间未在这 600 行内，未合计。
- **残余**：作者未播种 `Random()` 的轨迹同一性未知；MILP／Gurobi 的 t_f 口径未取得源码；精确容量边界三方（Java `>`、`checkPathEnergy` `<`、scorer `≤+1e-7`）不一致仍待三类边界案例。

### 4.2 旧 CA-RL 宏控制／算子选择（1,440 消融）

- **身份**：24 图×3 求解 seed×10 方法×2 预算；PPO checkpoint 选 seed 23，24 图已用于 checkpoint 选择与开发，**不是盲测**。
- **验收**：1,440/1,440 独立重评分、1,440/1,440 可行、错误 0、最大成本绝对误差 0；源汇总 SHA256 `7d20ca22…223bc`；PPO checkpoint SHA256 `fbf2e883…3ae68`。
- **结果**：完整 PPO（`m6_global_asg`）在两个预算的平均成本都高于 NoJoint：6s **+0.079127%**（点态 CI +0.013283%..+0.143807%，Holm18 p=0.228271）；12s **+0.038654%**（CI −0.008394%..+0.087140%，Holm18 p=1）。18 项 Holm 中只有 12s `nohighint` 过 0.05（+0.061171%，p=0.00439453，方向是去掉高强度动作后变差）。
- **预算**：每行平均 solver 秒 6.00026／12.00030（表内），故 720×6＋720×12＝**12,960 solver-s≈3.6 核小时**（不含接收与重评分开销）。
- **结论边界**：不支持“RL 稳定优越”；不显著 ≠ 等价；推理期特征置零不是重训因果消融。

### 4.3 旧 Route-RL Stage A（720 任务）

- **训练**：72 TRAIN 图（seed 1–6）、24 VAL 图（seed 7–8）；3 个模型 seed 11／23／37，各 60 updates×8 episodes×4 PPO epochs；奖励对账最大绝对误差 4.44e-16；6 单测通过；Greedy 与独立 evaluator 96/96 可行。
- **VAL 结果**：seed 11 −0.0283%（best update 30）、seed 23 −0.3307%（update 60）、seed 37 **+0.9038%**（update 25）；均值 +0.1816%、中位 −0.0283% ⇒ 三 seed 不稳定，选 seed 23 作等预算对照。
- **720 任务终局**：720/720 记录、0 任务失败、720/720 压缩完整解；缺失／多余／重复／错误均为 0；源 digest 仍为 `42869efa…9bda0`；选中 checkpoint `635ad613…018c2`。
- **等预算**（24 VAL 图×3 求解 seed 的地图均值）：6s Greedy 495.009507／insertion 493.812917／2-opt 494.218892／ALNS **486.044798**／Route-RL 492.133754；12s ALNS **485.978324**／Route-RL 492.072436。相对 ALNS 的地图配对收益 6s **−0.966725%**（CI [−1.259282%, −0.679487%]，W/L/T **0/21/3**）、12s **−0.955678%**（[−1.256179%, −0.664543%]，0/21/3）；相对 Greedy 为 +0.649531%／+0.668982%。
- **预算**：360×6＋360×12＝**6,480 solver-s≈1.8 核小时**；训练开销另计（报告未给 CPU 总量）。
- **关闭**：Stage A gate 双预算失败；Stage B（DABS 内 SD／LD 联合调度）、Stage C（跨站转移）未启动；无 Formal。

### 4.4 return_makespan（g23／g24_weather_nfz）

- **目标与合同**：`min M_return`，逐图 `C(candidate) <= C(R_Liu)+1e-7`、epsilon=0；6s／12s 整图墙钟；5% 均值与地图级 95% CI 下界 >0 是**目标**（`objective.achieved=false`）；MTC 辅助。
- **生成器**：G2 pilot 12,000 提案只接受 **67**（0.5583%），11,933 拒绝；(3,20) 与 (10,110) 家族 0/1,000 ⇒ Wilson 下界为 0，不能支持 99% 生成成功率上限；120 官方图＋12,000 pilot 提案永久排除。证据 `G23_ROOT_STATUS.md`、`g23<EXECUTION_PATH>`。
- **身份与额度**：40 唯一新身份＝original6／calibration4／P2 8／P3 14／newG3 8（STATE `research_counts.scope`），并另记 16 opportunity＋24 calibration／validation；作者尝试 40/48（余 8）；实际比较 126＝旧 66＋新 60；比较族累计 RL 36／BC-only 6／非 RL 84（旧 24＋新 60，含 8 次真实导入失败调用）；隔离校准验证 **24/24**；科学 non-RL **预约 7.5/16 核小时**（`reserved_scientific_nonRL_core_hours=7.5`，余 8.5；不退款、不改名挪用）。
- **G3 第一批**：4/4 天气锚点合格；40 次比较调用＝27 按时＋5 超时＋8 `multineighborhood_v2` 导入失败；strict 四图均值 **−8.792529%**（逐图 30.309156%／0%／4.860960%／0%），明确“仅该批已交付结果，不是 RL 结果”。
- **G3 第二批**：8 新图、8 作者尝试、**80 意向／60 实际比较**（该批 40 意向中 20 比较）、47 按时、5 超时、8 导入失败、**20 锚点不合格跳过**；原目标 4/4 有效但天气仅 **2/4**（`calibration_5` `battery:2:0:0`，`calibration_8` `battery:1:1:0`）；两合格图 6s −1.033778592%、12s −0.127702999%（不冒充四图验证）。
- **回放审计**：73 次独立 replay；交付解均满足双成本 cap；发现 **10 条**保存的可行改进 incumbent 被内层截止语义丢弃（一批 6、二批 4）；“strict 临时赢家”资格撤回，未补计、未修复后重跑。
- **天气 v2／v3**：v2 6 图（3_20 家族）、6 作者解全可行、3 天气合格、9 训练运行／9 episode／**0 完整**（9 dead-end）、22 次计时比较（18 RL／4 non-RL）、16 次作者回退交付、6 次 deadline 无交付、0 完整候选；v3 复用 6 图、9 运行／72 episode／**0 完整**、28 比较（18 RL／4 physical non-RL／6 BC-only）、13 回退、15 无交付、0 候选。
- **P3 fixed14**：14 新图、6 TRAIN／8 VAL 提案、5／7 合格；1 个 BC 阶段 1,200 步／400 epoch／55,200 次动作呈现；**0 个 TRAIN 完整**、0 PPO、0 VAL 调用（192 行跳过）；终局 `first_common_BC_gate_failed_stop`。教师态审计 138 态 top1 128（92.75%），RETURN 38/38、TARGET 90/100；拟合诊断 2,400 步才精确拟合同一 138 态。
- **ordinary RL attribution pilot**：8 新图、5 合格 TRAIN、**0 合格 VAL**、0 训练、1 个 BC 阶段被 SIGINT 中断、48 VAL 行跳过、exit 255、0 模型 0 checkpoint；结论 `STOPPED_INSUFFICIENT_VALIDATION_SUPPORT_NO_SCIENTIFIC_RESULT`。

### 4.5 联合天气—应急 20261105（v1 与深度重构 v2）

- **v1（第一包，192 步）**：24 TRAIN＋8 DEV 输入；32 作者调用全可行；3 RL seed、192 updates、768 训练 episode、288 控制＋384 模型＝672 评价；RL best J 689.814976 对 beam 658.991990（**+4.677293%**），对 BC −1.637089%；行成本非劣 beam 仅 10/96；3 个 BC／API seed 失败、6 个并发 seed 进程被丢弃；Formal 0。证据 `joint_weather_emergency/20261105/REPORT.md`、主 STATE `joint_weather_emergency_20261105`。
- **v2 深度重构**：`PROTOCOL_V2.md`＋`AMENDMENT_01`（登记链 revision1→2 公开修订，不能声称从未修订）；44 次新分配输入的官方 Java 静态求解全部可行（32 TRAIN＋4 VAL＋8 DEV）；取消强制 BC，initial 纳入 VAL 选择；SCST 用同日 2 采样＋1 贪婪 baseline，LOO 用同日 K4／留一，DoubleDQN 96 episodes／双 minibatch／目标网络。
- **执行量**：9 运行（3 算法×3 seed）、480 迭代、**768 优化器步**、**960 保存轨迹**；另封存 6 次完成更新／22 条轨迹（`total_optimizer_steps_including_archived=774`、`total_saved_training_episodes_including_archived=982`，属**总账分母**，不进模型选择）；320 控制＋864 模型＝**1,184 评价行**，独立回放 1,184，TRAIN 回放 960，`PASS_ACCOUNTING` errors=0。
- **主结果（J 越低越好，8 图×4 日、3 seed 等权）**：oldbeam **1169.612132**（+0.0000%）；deadline 1179.950349（+0.8839%）；mix0.5 1180.387228（+0.9213%）；mix1 1181.786834（+1.0409%）；mix2 1182.550798（+1.1062%）；prior **1188.621808**（+1.6253%）；author_dispatch 1224.147731（+4.6627%）；author_insert 1273.191304（+8.8559%）；nearest 1287.091015（+10.0443%）；alignedJbeam 1326.970946（+13.4539%）；scst_best＝loo_best＝1188.621808（+1.6253%）；ddqn_best 1335.818453（+14.2104%）。
- **每 seed**：9 运行中仅 2 个（ddqn_103、ddqn_307）选中的权重与 initial 不同；6 个 actor 运行（scst／loo 各 3）**全部选回 initial**；last 权重 L2 确有 0.31–0.42 变化，但 192 条 last 评价中 **148 条**物理 TARGET／RETURN 序列与 initial 完全相同。
- **SCST 训练流**：192 条采样 TRAIN 轨迹中 151 条 J 高于同一更新的自身贪婪，41 条更低；每 seed 平均差 +24.942599／+25.711609／+22.190262。
- **区间**：scst vs oldbeam +1.6253%，地图 0/8，配对 bootstrap [14.390618, 23.703597]；vs author_dispatch −2.9021%（8/0，[−45.139908, −25.794608]）；vs author_insert −6.6423%（8/0）；ddqn vs oldbeam +14.2104%（0/8）。明确“8 图探索性、非确认性 p 值”。
- **预算**：每 run 训练墙钟上限 300 s、总墙钟上限 2,400 s（未重置）；报告未给总 CPU 收据，故只能报“≤9×300 s 训练上限＋1,184 次评价回放”。

### 4.6 瓶颈诊断（TRAIN-only 8×SCST）

- **设计**：同模型／同优化器／同超参／同种子／同日随机流，3 seed 各 256 updates（=768 episodes／seed，合计 2,304）；checkpoint 32 与原 v2 last **逐 tensor 精确一致** ⇒ 前 32 步是重现而非新方法。
- **监测**：固定 TRAIN0–3×2 个未参与更新的日＝8 场景；96 次监测；16 控制；178 分支；2,599 次独立物理回放。
- **曲线**（J 越低越好）：seed103 890.253946→890.052373→892.008986→891.129536（+0.098353%）；seed211 →890.035824（−0.024501%）；seed307 →888.918748（−0.149979%）。256 步跨 seed 均值 **890.028036**（−0.025376% vs initial；+1.924917% vs oldbeam 873.219292）。
- **限幅结构事实**：得分＝`prior + 6*tanh(raw/6)`，两动作最大相对改变 <12 分；7/2,022 个多候选 callback 改变 prior 选择；平均规则前二分差 2.137823／2.184760／2.146261，而平均动作间修正幅度只有 0.004390／0.012188／0.007463，最大绝对修正 0.014324／0.028818／0.019117。
- **可达性**：4 TRAIN 图固定 16 状态×≤6 候选＝178 条强制一步完整轨迹（同一真实 TRAIN 未来、独立物理回放）；prior 续接 **10/16** 有更低 J 候选、其中 **2** 个 prior 差 >12 不可达；oldbeam 续接 **12/16**、**3** 个不可达。
- **表示能力**：同 seed103 初始权重、仅 bounded／unbounded 差异、Adam 1e-3、400 监督步：bounded 6/16→8/16→11/16→**12/16**；unbounded 6/16→9/16→14/16→**16/16**。这是同状态受控诊断，不是 RL 性能消融。
- **Q 排序**：ddqn_103_initial 排序正确率 50.00%、top1 6/16、regret 2.756360；last 分别 49.03%／3／4.114511、48.06%／1／8.119466、53.88%／2／3.920612。
- **预算**：每 seed 运行 760.33／758.57／544.88 s；其中采样＋回放 463.48／463.50／326.52，梯度 270.64／267.77／200.08，监测 17.42／18.39／12.27，保存 4.70／4.88／3.32；监督拟合 2×400＝800 步另计。

### 4.7 方法族 A／B／C

- **A（`20261105_method_screen`）**：44 新图（24 TRAIN／8 VAL／12 SELECT）；3 方法×3 seed＝9 运行；2,400 预登记 SELECT 行（2,336 DONE／64 TIMEOUT）；4,560 训练日、510 迭代／优化器步、训练 CPU 763.009203223 s；墙钟 2,628.715 s；10 核小时预约。结果：LOO 385.3993135118879（−1.0466776210066753% vs 自身 initial；−0.03196152322280099% vs deadline）、linear VFA 389.1695416、neural VFA 389.2625007；`rl_superiority=false`、`formal=false`。
- **B（`20261106_method_family_B`）**：13 后端×3 seed＝39 运行；8,256 意向 SELECT（8,112 DONE／144 TIMEOUT）；墙钟 9,249.307261 s；32 核小时预约；146 工程测试。12s 主结果：LOO **393.652424**（−0.9934428468 vs 自身 initial，3 seed 均变）、SCST 394.456662、neural PFA 395.090060、linear PFA 395.770425、discrete SAC 396.729504、linear VFA 396.962540、PPO／A2C 397.533506、neural VFA 397.602376、dueling 407.873691、quantile 408.588309、double Q 412.758157；控制侧 nearest 399.830028、deadline 393.378725、prior 397.602376、author_insert 396.074023、**author_dispatch 392.967769**。`fleet_insert／fleet_rollout／complete_fleet` 各 12/48 TIMEOUT（12s）、36/48（6s），明确“不作完整排名”。裁决字符串：`DESCRIPTIVE_LIMITED_BUDGET_SCREEN_NOT_CONVERGED_OR_STRONGEST_DOMINANCE`。
- **C（`20261106_control_qualification_C2_infrastructure`）**：512 行／512 回放、`PASS_ACCOUNTING`、错误 0、失败 intent 0、worker wall 合计 841.5037615 s；三控制器 selected 全为 `heavy`：complete_fleet J=**367.0909613711476**、causal_anticipatory_fleet **368.43442574583986**、source_faithful_rolling **373.800482626391**；状态 **`QUALIFIED_REPRESENTATIVE_NOT_STRONGEST_GLOBAL`**；原 C `INTERRUPTED_INCOMPLETE_RETAINED`、未重启、未调参、0 RL 训练。

### 4.8 D：30 流、29,760 评价键、12.046 GB 硬限

- **设计**：10 配置×3 seed＝30 流；32 TRAIN／8 VAL／24 SELECT；2,880 VAL＋26,880 SELECT＝**29,760** 键；内层训练与在线 cap 小计 116.8 核小时，外候选 144 核小时／72 h 是**申请**而非已启动承诺。
- **终局**：2026-11-06T08:22:00Z 因 `TOTAL_OUTPUT_BYTES_LIMIT` 停止，原 driver **exit −9**；输出 **12,045,821,536 B**，硬限 12,000,000,000 B，轮询越限 45,821,536 B；原监督 wall 19,361.690845 s、whole-container CPU 60,944.763211 s（含已披露工程开销，非纯训练）。
- **覆盖**：30 流＝**18 完整核账 PASS（复用原审计）＋3 部分（关系 SAC 仅部分训练）＋9 未见训练目录**；“无目录不独立证明从未启动”。3 条部分流的 4x 模型／backend 与 policy identity 均与 CAP 及文件 SHA 匹配，但训练未完成 ⇒ 不作全训练 PASS。
- **评价**：2,880＋26,880 键逐一保留，全部 `PLANNED_NO_RECORDED_INTENT`，覆盖解析错误 0；`evaluation_errors=0`。缺 intent 只说明登记覆盖缺失，**不能**据此断言全服务器绝无运行，也**不能**从 checkpoint 推出已完成统一比较。
- **资源与完整性**：原 D 未修改、原文件重哈希未变；终局核对自身 CPU 11.957961654 s／wall 11.989277 s 单独报，不塞回原监督；3 次 cap identity 重载；0 forward／0 质量评价／0 训练／0 optimizer step。
- **裁决字符串**：RESULT.json `status=PASS_TERMINAL_PLAN_RECONCILIATION_STUDY_INCOMPLETE`、`stop=TOTAL_OUTPUT_BYTES_LIMIT`、`original_exit_status=-9`；E STATE 的字段值是 `RESOURCE_TERMINATED_INCOMPLETE_RECONCILED`（任务书／BRIEF 写作 `D_RESOURCE_TERMINATED_INCOMPLETE_RECONCILED`，指同一状态，前缀 D 是身份标注而非字段原文）。两者不矛盾：前者是“终局核对通过但研究未完成”，后者是“资源终止且已对账”。

### 4.9 E：工程准入 ≠ 科学准入

- **状态**：`E_ENGINEERING_ADMISSION_PROGRESS_NOT_SCIENTIFICALLY_ADMITTED`；`scientific_E_training_started=false`；`original_D_status=RESOURCE_TERMINATED_INCOMPLETE_RECONCILED`；`original_D_restart=false`。
- **两包检查**：`20261106_E_learning_label_audit_v2` **25** 个 test functions（source manifest `0f58d961…`，24 个服务器文件重开，children CPU 18.893338 s、wall 18.959033 s）；`20261106_E_originalJ_author_portfolio_v2` **16** 个 test functions（`37f7736c…`，24 文件重开，children CPU 34.149842 s、wall 34.296582 s）。
- **9 项 pending**：full_new_population_storage_resource_admission、scientific_driver、fresh_exclusion_registry_with_D、typed_reserve_control_qualification、scenario_grid_generation_no_inside_NFZ、author_anchor_fidelity_scientific_source_binding、TRAIN_only_event_day_power_estimation、VAL_selection_objective_fixed、HV_fixed_reference_and_primary_contrast_family。
- **6 项 known limitations**：detached log-prob 算术不是独立梯度重建；作者适配器只对既有实现验证、真实锚点 provenance 仍缺；原 J 与作者策略是重复 portfolio 点而非不同前沿；七流存储探针仍不完整未重跑；G0／最强 nonRL／静态严格 cap／Formal／G8 全未过；两个失败工程包缺完整进程 CPU 收据。
- **含义**：25／16 项**不构成** E 科学准入；registration 文件存在也不等于正式冻结协议。

### 4.10 WX-E 五类 pilot 与 v3–v8

- **共同合同**：动作是版本化 `TARGET／WAIT_5MIN／RETURN`；legacy `route_rl` 的 `TARGET／RETURN` 源码未改；所有方法共享 mask、事件流与独立 stdlib 回放；`WAIT_5MIN` **不是**当前静态动作合同。
- **v1**：64 行＝2 模式×4 图×8 方法。**可采信文件是 `results/REAL_PILOT.json`**（含 `simulator`、`complete_return`、`invalid_actions`、`scenario_fingerprint`、`toy_pilot_invalidated=true`）：V_cluster **0.0**、V_uniform **0.3333333**、RL 成本 55.371981291828945 vs non-RL 50.9727037026624（比 **1.08631**，即 +8.63%），`CLOSE_NO_FULL_RUN`。该文件内 64 行中 **24 行** `failed=true`／`complete_return=false`（uniform 模式下 BC、RL×3、ROLLOUT_8／128 各 4 行），合计 24 个未服务任务。
- **v1 的无效副本**：同目录 `results/PILOT.json` 是更早的简化版（V_cluster **−0.40625**、V_uniform −0.25、成本 70.28768007238395／58.21266710872297＝1.2074293029918841），**不含** `complete_return`／`invalid_actions`／`simulator` 字段，已被 REPORT 与 REAL_PILOT 标记为 invalidated。主 STATE 的 `continuation_20261112_wx_e` 与接手指令 §5.4 引用的是这份无效副本（见 §5 K4）。
- **real v2**：128 行＝2×8×8；128/128 回放验证、terminal failure 0，但 **80 行不完整**、未服务合计 **480**（每个 BC／RL 行 6 个未服务）；V_cluster＝V_uniform＝**0.0**；表面成本比 0.756726813901237 只因不完整路线被计入，**不可采信**；3 seed×30 optimizer steps，训练日志每更新 909–912 transitions。
- **forecast v1**：256 行＝2×16×8；**256/256 完整服务**、256/256 回放；V_cluster **−0.09523809523809523**、V_uniform +0.0014880952380953438；RL 成本 88.33112038501943 vs 最强 non-RL（clustered 为 `ROLLOUT_128`）93.63879794673824（比 0.9433）；成本条件过、时效失败 ⇒ `CLOSE_NO_FULL_RUN`。
- **risk v1**：512 行＝2 模式×32 身份×8 方法；**512/512 完整服务**、512/512 回放；V_cluster **−0.02604166666666663**、V_uniform **−0.02408854166666663**；RL 成本 90.46030993643605 vs 最强完整 non-RL（`STATIC_RULE`）89.74725959419959（比 **1.00794**，在 1% 内）；TRAIN 合成身份 2000–2063、EVAL 3100–3131、seed 103／211／307 各 220 updates；首次运行在 gate 的 `NaN` JSON 序列化处失败，三个 checkpoint 保留、**不重训**重开评价；失败与恢复均在 `results/pilot.log`、`results/PILOT_SAVED_EVAL.json`。
- **v3–v8**：每包 256 行（2×16×8）、256/256 回放。V_cluster／V_uniform／RL 成本／最强 non-RL 成本：v3 0.000000／0.000000／72.815546／76.804559；v4 0.000000／0.000000／77.125969／78.465380；v5 −0.010417／−0.067708／97.679972／89.924530；v6 **+0.020833**／+0.036458／80.920968／89.924530；v7 +0.001736／+0.083333／89.416587／100.735812；v8 −0.090278／+0.019097／80.041236／81.936255。全部 `CLOSE_NO_FULL_RUN`。v6 另含 1 条不完整 `RL_103` uniform 行（`complete_service_rate=0.9375`、`incomplete_rows=1`、`unserved_total=1`），保留但不作完整路线优势。v3／v4 过易（所有方法 high-priority on-time=1.0）；v8 的相位条件径向几何把 clustered 效应反号，证伪该特定机制。
- **WX-H**：`20261112_wx_h_v1` 只有 4 个源码文件，无结果；状态 `deferred`（0 运行）。

### 4.11 WX-C spatial diag v3

- **执行**：同一冻结 64 场景人口，baseline 与 expanded 各 **320 行**＝64 场景×5 行，服务器 Python 3.10.12，回放率 **1.0**；行级独立审计 320/320 有效、320/320 回放、`oracle vs CONTINUE` 成本 gate 率 1.0、同源 fingerprint 不一致 0。
- **结果**：expanded clustered gap＝**0.16666666666666666**（1/6），uniform gap＝**0.16666666666666666**（1/6）；clustered 阈值通过但 **uniform-shrink 失败** ⇒ `CLOSE_WX_C_CANDIDATE`。
- **边界**：这是机会诊断，不是训练／求解器比较／Formal／创新／RL 优越性；固定小数点 fingerprint 规范化属工程修正。DIVERT 不进当前静态动作合同。

### 4.12 公共告警条件化（18 例）

- **对象**：有限共享风暴假说、有限目标集、每目标一次故障机会、均匀告警延迟；同时用已公开告警密度与至今未告警生存因子更新权重，再在同一潜在粒子下抽整组未来告警；输入只有模型假说与公共告警账本，**不读** Scenario／Trace／隐藏任务／events。
- **手写例**：两粒子等先验、p=1/2、最大延迟 20、离开时刻 0／20、t=10 无告警：prior fixture 输出 (0.5,0.5)，条件化输出 **(3/7, 4/7)**（0.428571／0.571429）；early 粒子内未来告警 1/3；正告警 r=5 使 late 粒子权重为 0。
- **工程覆盖**：已发布且已服务告警不重采；horizon 后告警与“不会告警”分列；零支持显式失败；同目标重复 crossing、未知 ID、重复告警、未来告警混入历史、错误发布阶段、非法参数全部拒绝；极小天气似然用 log 归一化。
- **预算与裁决**：<COMPUTE_HOST> Python 3.10.12，18 例全过（单次探针约 0.04 s，见 `server_evidence/TEST_RECEIPTS.json`）；科研实验／训练／作者求解／质量评价／新地图 **0**。裁决仍是 `G0_NO_GO_CENTERED_DUAL_SCORE_STANDARD_AND_STATIC_ZERO`（沿用上一具体候选关闭，不把本模块改名为该候选）。

### 4.13 reserve v5 静态 HOLD 与五个 G0 关闭

- **reserve v5（`20261113_wx_e_reserve_v5`）**：`MODIFIED_FILE/PRE_RUN_REVIEW.md` 裁决 **`HOLD_G0_NO_GO`**、`scientific_run_admitted=false`；9 项源码事实：F1 ROLLOUT_16／128 只对候选分数做 Bernoulli 扰动（327–344 行），未做路线前瞻；F2 `LIU_ADAPTER` 手写评分（302–324 行）却进入 `NON_RL`（48 行）并据此选最强（543–545 行）；F3 评价表 BC 行在 `model=None` 时调用 `_reserve_teacher`（358–367、527–528 行）；F4 每 seed 只训一次模型、同模型评两模式（523–532 行），不是 uniform 独立重训；F5 coverage 是纯几何特征（74–87 行）；F6 单站同质、预报固定不更新（42–45、95–191 行；`src/emergency_scenario.py` 445–475 行）；F7 只计时不实施 6s／12s 共同截止（355–378、419–429 行）；F8 uniform gate 缺 `v_uniform>0`（555 行）且成本用 pooled 1%；F9 `allow_nan=False` 在失败分支可能丢结果收据（548–554、559 行）。
- **centered-dual-score**：`G0_NO_GO_CENTERED_DUAL_SCORE_STANDARD_AND_STATIC_ZERO`；基本运算已有 Brown／Smith／Sun 2010 与 PD-MCTS（arXiv:1704.05963v1）原式；当前固定实例／参数／物理动作使下一构造状态确定 ⇒ 惩罚项恒零、`L_nu=L_0`。0 实验。
- **observation-timing／POSMDP**：`G0_NO_GO_OBSERVATION_TIMING_STANDARD_POSMDP`；静态 `FullMapRouteEnv` 时间是构造账本，无天气／请求发布回调；WX-E 参考源 `wind_now` 为全局当前风、`forecast` 为固定初始元组；动作相关持续时间进入信念更新与历史条件化前瞻已有先例（ChronosPerseus v1、POMCP、Cho wind-IPP v1）。
- **joint-event-screen**：`G0_NO_GO_AS_DISTINCT_ALGORITHM`；解析反例为“同边际概率、每批固定两个请求、最优 TARGET 动作反转”，说明单请求 coverage 丢失资源争用信息，但共享联合分布的 non-RL 同样能用该信息；Zhao／Han DOI 经 CrossRef HTTP200 核实。
- **original-prompts-CFA-PbP**：`G0_NO_GO_ORIGINAL_PROMPTS_CFA_PBP_AUDITED`；三份原 prompt 找到并冻结（WX-E 两副本同 SHA256 `d0b26500…d23aa`）；99 条书目本轮 82 verified／2 mismatch／15 manual_needed，后由 bibliography 包推进到 **97／2／0**（分母仍 99）；新增 CIRRELT-2024-34（41 页）与 Zhang EJOR 2023（20 页）先例核对。
- **Zhao／Han 全文**：`G0_NO_GO_AS_DISTINCT_ALGORITHM_FULLTEXT_AUDITED`；49 页（Zhao 27＋Han 22）、2 篇正文逐式、独立 SI 0；Zhao 式 (14) 线性后决策 VFA、pp.14–15 greedy-base 真实 MC rollout、pp.9/12 RE；Han 式 (2r)–(2t) 共享容量准备度；两者都使“天气＋RL／共享容量”不再是充分差异。

---

## 5. 冲突清单：谁和谁矛盾、采用哪一份、依据什么

> 判定规则：**更新的明确覆盖 > 终局收据 > 主科学 STATE > 包内 REPORT 文字 > 早期计划／进行中文字**。只列会改变结论或分母的冲突；纯措辞差异不列。

### K1 `route_rl_research/20261103/STATE.json` 早期字段 vs `return_makespan/STATE.json` 主状态

| 项 | 早期文件（2026-11-03） | 主状态（2026-11-12） |
|---|---|---|
| status | `SUPERSEDED_BY_APPROVED_RETURN_MAKESPAN_EXECUTION_STATE` | `JOINT_DEVELOPMENT_COMPLETE_NEGATIVE_3SEED672_EVALUATIONS; G0_G3_G4_NOT_PASSED` |
| G1 | `SMOKE_24_MAP_REPLAY_AND_ONE_RANDOM_LEGAL_PASS; GENERAL_POLICY_RELIABILITY_UNESTIMATED` | 8+6+5+35 invocations PASS、7 originals unchanged、timing amendment disclosed |
| G2 | `BOUNDED_EXPOSED_STATION_NUMERICAL_OPPORTUNITY_DIAGNOSTIC_COMPLETE; 11_FULL/13_PARTIAL` | `CONDITIONAL_NONRL_CALIBRATION_IMPROVEMENTS_ONLY; NO_RL_OR_POPULATION_INFERENCE; SECOND_BATCH_2_OF4` |
| 计数 | `new_training_started=false`、`new_quality_matrix_started=false` | 40 身份／40 作者／126 比较／24-24／7.5 核小时 |
| 指向 | `continuation_state = …/return_makespan/STATE.json` | 自身即主账本 |

**采用**：主状态。**依据**：早期文件自己声明 SUPERSEDED 并给出 continuation 指针；主状态晚 9 天且含 G3 两批、P3、weather v2/v3 等后续收据。**保留**：早期文件仍可证明 2026-11-03 时点 G0 未立项、G1 只有 smoke。

### K2 `EXECUTION_PLAN.md` 内部矛盾（覆盖条款 vs Gate 表）

- 第 2 行（2026-11-05 当前覆盖）：40 身份／126 比较／24-24／7.5 核小时。
- 第 18–26 行 Gate 表：G2 “新图未生成”、G3 “代码实现与质量运行未做”、G4 “未开始”。
- **采用**第 2 行与主 STATE。**依据**：第 2 行标题即“当前覆盖”并写“下方保留早期计划”“不重复旧计划未生成/未训练任务”；Gate 表是执行前计划。**风险**：只读 Gate 表会误得“从未生成/从未训练”。

### K3 D：`TRAINING` 状态 vs 终局 `exit −9`

| 文件 | 说法 |
|---|---|
| `20261106_sufficient_training_D/STATE.json` | `status=TRAINING`、`runs=30`、`formal=false` |
| `D_TERMINAL_RECONCILIATION/RESULT.json` | `stop=TOTAL_OUTPUT_BYTES_LIMIT`、`original_exit_status=-9`、18/3/9、29,760 键 0 intent |
| `20261106_E_continuation_acceptance/STATE.json` | `original_D_status=RESOURCE_TERMINATED_INCOMPLETE_RECONCILED`、`original_D_restart=false` |

**采用** RESULT.json + E STATE。**依据**：终局收据时间 2026-11-06T08:27Z 晚于停止 08:22Z；D REPORT 明确“原 STATE.json 遗留 TRAINING 原样保留”是**有意保留历史**，不是当前状态；接手指令 §5.3 也写明“已过时”。**注意**：两个字符串并不互相否定——`PASS_TERMINAL_PLAN_RECONCILIATION_STUDY_INCOMPLETE` 指对账 PASS、研究未完成；`RESOURCE_TERMINATED_INCOMPLETE_RECONCILED` 指资源终止已对账。

### K4 WX-E v1：`PILOT.json`（−0.40625）vs `REAL_PILOT.json`（0.0）— **本审计最重要的数字冲突**

| 来源 | V_cluster | V_uniform | RL／non-RL 成本 | 比值 | 备注 |
|---|---:|---:|---|---:|---|
| `20261112_wx_e/results/PILOT.json` | **−0.40625** | −0.25 | 70.28768007238395／58.21266710872297 | 1.2074293 | 无 `complete_return`／`invalid_actions`／`simulator`；有 `trace`／`seed` |
| `20261112_wx_e/results/REAL_PILOT.json` | **0.0** | 0.3333333 | 55.371981291828945／50.9727037026624 | 1.08631 | 有 `simulator`／`complete_return`／`invalid_actions`／`scenario_fingerprint`／`toy_pilot_invalidated=true` |
| `20261112_wx_e/REPORT.md` | 0.0 | 0.3333333 | 55.371981291828945／50.9727037026624 | +8.63% | 明说“第一个简化 toy 输出保留但被明确作废” |
| `20261112_wx_e/STATE.json` | 0.0 | 0.3333333 | 同上 | — | `scientific_pilot = results/REAL_PILOT.json`，`toy_pilot_status=INVALIDATED_ENGINEERING_ONLY` |
| `return_makespan/STATE.json` → `continuation_20261112_wx_e` | −0.40625 | −0.25 | 70.28768007238395／58.21266710872297 | 1.2074293 | 与 PILOT.json 完全一致 |
| 接手指令 §5.4 表 | −0.40625 | — | — | ≈1.20743 | 与主 STATE 旧块一致 |

**采用**：`REAL_PILOT.json`（V_cluster=0.0、比值 1.08631）。**依据**：①REAL_PILOT 含 simulator 身份、完整返航与非法动作字段，是“可采信的 pilot”；②REAL_PILOT 内含 `toy_pilot_invalidated=true`，REPORT 与包 STATE 都把前一份定为 invalidated；③PILOT.json 缺完整返航／非法动作字段，是 toy；④两者**同目录同日期**，不能靠 mtime 判，只能靠内容与自身裁决字段。
**后果**：接手指令 §5.4 与主 STATE 的该块**引用了作废副本**，属需更正的 stale 数字；两个版本都导致 `CLOSE_NO_FULL_RUN`，因此**不改变 gate 结论**，但会误导“差多少”的判断（8.63% vs 20.7%）。

### K5 WX-E v1 REPORT 文字“28 failed rows” vs JSON 24

- `REPORT.md`：“28 failed rows and 24 unserved-task counts remain”。
- `REAL_PILOT.json`：64 行中 `failed=true` **24** 行、`complete_return=false` **24** 行、`unserved>0` **24** 行、`timed_out` 0；`PILOT.json` 则 0 failed。
- **采用** 24。**依据**：JSON 是逐行原始记录，REPORT 是概述文字；24 可由 6 个 uniform 方法×4 图精确解释，28 无对应分解。

### K6 `20261112_weather_rl_goal_audit` 的 `PLAN_EXECUTED_WITH_GATES_NO_BREAKTHROUGH` vs `PROMPT_RECONCILIATION`

- goal audit（较早，同日）：把 WX-E／WX-C 记为 `COMPLETE, CLOSED`，并给总裁决 `PLAN_EXECUTED_WITH_GATES_NO_BREAKTHROUGH`。
- `PROMPT_RECONCILIATION.md`（较晚）：明确该字符串“**只限已登记 pilot 按闸门结束，不能解释为三方案全量已执行**”；原全套多站异构、真实 N4、作者组、完整 Formal 与统计**均未完成**。
- **采用** PROMPT_RECONCILIATION。**依据**：它是后出的专门更正文件，且逐项对齐了原 prompt 与收据；goal audit 自己的表也写 99 书目 `NOT PROVEN`、三份 prompt `PARTIAL`，与“全部执行”自相矛盾。

### K7 书目计数：82／2／15 vs 97／2／0

- `20261112_original_prompts_cfa_audit`（同日较早）：82 verified／2 mismatch／15 manual_needed。
- `20261112_bibliography_primary_completion`（同日晚）：**97 verified／2 mismatch／0 manual_needed**。
- **采用** 97／2／0 为当前，82／2／15 为历史阶段。**依据**：后者明确“15 个 manual_needed 经正式会议／出版社或机构来源解决”，并保留原 99 身份与分母；两文件不冲突，是同一 work stream 的两阶段。第 12、45 条作者字段错误在最终态**仍如实登记**。

### K8 B：`STAGE_B_COMPLETE_PENDING_AUDIT` vs `B_METHOD_DECISION`

- `20261106_method_family_B/STATE.json`：`status=STAGE_B_COMPLETE_PENDING_AUDIT`、`best_rl=PENDING_AUDIT`。
- `readonly_audit/B_METHOD_DECISION.json`：`POST_ACCOUNTING_DESCRIPTIVE_COMPLETE`，LOO 393.652424、author_dispatch 392.967769。
- **采用**后者取数，**但**保留 `winner_claim=DESCRIPTIVE_LIMITED_BUDGET_SCREEN_NOT_CONVERGED_OR_STRONGEST_DOMINANCE`。**依据**：审计文件是 STATE 之后生成的核账产物；STATE 的 PENDING 是当时状态，不是否定。

### K9 深重构 768／960 与 774／982

- `20261105_deep_revision/REPORT.md`：768 优化器步、960 保存轨迹（模型选择口径）。
- 主 STATE `joint_weather_emergency_v2_20261105`：`total_optimizer_steps_including_archived=774`、`total_saved_training_episodes_including_archived=982`（含另存 6 步／22 轨迹）。
- **采用** 768／960 作**模型选择与评价分母**，774／982 作**总计算账**。**依据**：REPORT 明确“初版内存复制过慢尝试另保存 6 次完成更新／22 条轨迹，不纳入模型选择”；两者不是同一分母，禁止混用。同理 v1 的 192 步／672 评价是**另一批**，不与 v2 合并成统计样本（合计算力 966 步／1,750 轨迹／1,856 行仅作资源账）。

### K10 G3 的“30 合格图／9 失败锚点／2-of-4”不是矛盾

- `weather_eligible_maps=30`、`weather_anchor_failed_maps=9`、`total_unusable_anchors=10`、`endpoint_anchor_failed_maps=1`（全 40 身份口径）。
- `ROUND_DECISION`：第一批 4/4、第二批 **2/4**（批次口径）。
- **处理**：不裁决“谁对”，而是**强制标分母**。本文件所有 G3 数字均写“第一批／第二批／全 40 身份”。**依据**：STATE 自己给了 `weather_eligible_definition`（“Joint original+weather eligible complete author anchors；纯 weather replay admissible 是 25，含 P2VAL2 endpoint failed”）。

### K11 C 与 C2：`C_UNOBSERVED` vs `COMPLETE_PENDING_ROOT_REVIEW`

- `20261106_root_acceptance/STATE.json`：`status=…_C_UNOBSERVED_…`。
- `20261106_control_qualification_C2_infrastructure/STATE.json`：`COMPLETE_PENDING_ROOT_REVIEW`、512 行／512 回放、`original_C=INTERRUPTED_INCOMPLETE_RETAINED`。
- **采用** C2 结果 + “原 C 中断保留”。**依据**：C2 是**新基础设施包**，不是原 C 的续跑；512 行有 replay 与 accounting。不得写成“原 C 完成”。

### K12 `LATEST_STATUS.md` 的累积顺序

- 85 份同名文件中，canonical 是根目录那份，**倒序累积**：首项=2026-11-12 公共告警；其后依次为 CFA 仓库（11-12）、centered-dual-score（11-12）、书目（11-12）、observation timing（11-12）、original prompts（11-12）、Zhao/Han（11-12）、joint-event（11-12）、reserve v5（11-12）、risk v1（11-12）、WX-C v3（11-12）。
- **采用**首项为最新；旧项为历史。**依据**：文件自身按“日期 + 主题”倒序；主 STATE 的 `latest_status_entry` 指向最新条目。

### K13 `20261105_research_continuation/REPORT.md` 的“正在训练” vs B 终局

- 该文件多段写 “B13 训练中／正在 8256 意向 SELECT／bestRL UNKNOWN／goal active”。
- B `SUPERVISOR_END.json`：`exit_status=0`、`timeout=false`、`elapsed_s=9249.30726144882`；`B_METHOD_DECISION` 给出完整核账。
- **采用** B 终局。**依据**：进度文字是**当时快照**（文件自身标注 01:02–03:28 多个时点）；终局收据在后。**保留**：PROGRESS_0130／0136 等可作过程证据，但不能当终态。

### K14 `completion/TASKS.md` 的“执行中/待验收” vs 后续收据

- `TASKS.md` 列 7 项未打勾（2/6/12/30 秒 1008 任务、官方 Java 轨迹差异、微型最优性、checkpoint 训练、60 未见图测试、消融／统计、最终 Go/No-Go）。
- 后续有 Formal v4（30 图×10 seed）、Stage A 720、R2–R7 裁决等。
- **采用**后续收据。**依据**：`TASKS.md` 是早期执行台账（无日期、无 SHA），后续包有冻结协议与终局；但其中“60 未见图测试／最终 Go-No-Go”确实**未被同名交付**，已归入“未执行”表而不是当作完成。

### K15 目录日期 `20261113_*` 晚于本机日期

- `20261113_wx_e_reserve_v1..v5` 的 mtime 是 2026-11-12，目录名却写 11-13；v5 源码／schema／协议仍用 v3。
- **处理**：目录名**不构成**新身份或执行日期；沿用 `PRE_RUN_REVIEW` 的登记。**依据**：审查包已逐行核对源码仍是 v3，且本地无结果文件。

---

## 6. 四张表

> 每行都带证据路径；“已关闭”= 有正式关闭裁决且不得改名复活；“未执行”= 计划存在但无真实执行收据。数字均带分母，口径见 §7。

### 6.1 已知（已证实事实，可复核）

| # | 已知事实 | 关键数字与分母 | 证据 |
|---|---|---|---|
| 1 | Liu／SEMFiX 复现完成且独立审计通过 | 120 图×5 seed×P1／P2＝1,200 配对；600/600＋600/600 可行；P1 −0.0284113%、P2 +0.0997583% | `reproduction/reviewer_package_semfix/SEMFiX_FULL_RESULTS.md` |
| 2 | 参数、约束、witness 级一致（非轨迹同一性） | 12 个 Table 1 组均值/最优落在 map-cluster 95% CI 内；J1b／J2b 1,200 witness 重开 | 同上；`REPRO_PROTOCOL.md` |
| 3 | 旧 PPO 宏控制未胜强非 RL | 1,440 行；+0.079127%（6s）／+0.038654%（12s）；Holm18 仅 1 项显著且方向为退化 | `execution/20261102/state_ablation/analysis/REPORT.md` |
| 4 | 旧 Route-RL Stage A 输给 route-only ALNS | 720 任务；−0.966725%／−0.955678%；0/21/3 | `stage_a_audit/MODIFIED_FILE.md` |
| 5 | 40 新身份／126 比较／24-24／7.5 核小时账本成立 | 40 作者尝试（上限 48）；比较 66+60；非 RL 84／RL 36／BC 6 | `return_makespan/STATE.json` |
| 6 | G3 未通过且比较不对称 | 80 意向／60 比较／47 交付／5 超时／8 导入失败／20 跳过；10 条改善 incumbent 被丢弃 | `.../status_reconciliation_g3_20261105/ROUND_DECISION.md` |
| 7 | 联合 DEV 最强登记 non-RL 是 oldbeam | J=1169.612132（8 图×4 日、3 seed 等权） | `20261105_deep_revision/REPORT.md` |
| 8 | SCST／LOO 未产生选中后学习增益 | J=1188.621808（+1.6253%，0/8 图）；6/6 actor seed 选回 initial；148/192 last 路线不变 | 同上 |
| 9 | ±6 限幅造成真实可达性损失 | 2/16（prior）与 3/16（oldbeam）状态最低 J 候选不可达；7/2,022 改选 | `20261105_bottleneck_diagnosis/REPORT.md` |
| 10 | A／B 均未出现 RL 胜强非 RL | A：LOO 385.3993；B：LOO 393.6524 vs author_dispatch 392.9678（p=0.7866，6W/6L） | `method_screen/SCREEN_DESCRIPTIVE.json`；`method_family_B/readonly_audit/B_METHOD_DECISION.md` |
| 11 | C 只到“代表”不是“最强” | 512 行／512 回放；J 367.0910／368.4344／373.8005 | `control_qualification_C2_infrastructure/STATE.json` |
| 12 | D 因输出硬限终止且已对账 | 12,045,821,536 B>12,000,000,000 B；exit −9；18/3/9；29,760 键 0 intent | `D_TERMINAL_RECONCILIATION/RESULT.json` |
| 13 | E 只完成工程检查 | 25＋16 test functions；`scientific_E_training_started=false`；9 pending | `20261106_E_continuation_acceptance/STATE.json` |
| 14 | WX-E／WX-C 具体 pilot 全部关闭 | v1 0.0／+8.63%；real v2 80 不完整；forecast −0.0952381；risk −0.0260417；v6 +0.020833；WX-C 1/6＋1/6 | `20261112_wx_e*/REPORT*.md`；`20261112_wx_c_spatial_diag_v3/REPORT.md` |
| 15 | 公共告警模块 18 例通过 | (0.5,0.5)→(3/7,4/7)；0 地图／0 训练 | `20261112_public_fault_conditioning/REPORT.md` |
| 16 | G0 无获准机制；reserve v5 HOLD | 5 个 G0 关闭 + F1–F9；0 运行 | `project_status/20261112_*/STATE.json`；`.../PRE_RUN_REVIEW.md` |

### 6.2 未知（未证实，不得当结论）

| # | 未知项 | 为什么未知 | 证据／缺口 |
|---|---|---|---|
| 1 | 作者 MILP／Gurobi 的 t_f 口径与 cap 定义 | 未取得源码 | `project_status/20261112_claude_takeover_audit/AUDIT_CLARIFICATIONS.md` A2 修订 |
| 2 | 精确容量边界哪一侧为准 | Java `>`、`checkPathEnergy` `<`、scorer `≤+1e-7` 三方不一致，未做三类边界案例 | 同上 A5 修订；`scorer.py` |
| 3 | 是否存在尚未核到的实质新 G0 机制 | NO-GO 只证明当前候选不成立，不是不可能性定理 | `project_status/20261112_g0_joint_event_screen/MECHANISM_SPEC.md` |
| 4 | 充分预算下 RL 能否胜最强 non-RL | A／B 都是 ≤300 CPU 秒／512 日的有限筛选，非收敛 | `20261106_method_family_B/readonly_audit/B_METHOD_DECISION.md` |
| 5 | 真实公共因果 rollout 是否可实现 | 缺完整前缀续接、隐服务阶段、独立预报发布 | `project_status/20261112_causal_rollout_capability_audit/CAUSAL_ROLLOUT_APPENDIX.md` |
| 6 | 作者无种子 RNG 的真实分布 | 作者用未播种 `Random()` | `REPRO_PROTOCOL.md` §5 |
| 7 | Zhao 独立 SI／Han 在线 SI 是否存在 | Zhao 明确声明未随文；Han 所供 PDF 无 SI 声明，在线存在性未核实 | `20261112_zhao_han_fulltext_audit/SI_STATUS.json` |
| 8 | CFA 2025 最终版 PFA／oracle 定义 | 只取得 coredata，FULL 401 | `20261112_cfa_final_si_review/ACCESS_STATUS.json` |
| 9 | reserve v1–v5／WX-H v1 是否在远端执行过 | 本地 results／models 全空；未连服务器核实 | `20261112_g0_reserve_v5_static_audit/HANDOVER_RECONCILIATION.md` |
| 10 | D 的 9 个“无目录”流是否从未启动 | 无目录不是独立证明 | `D_TERMINAL_RECONCILIATION/REPORT.md` |
| 11 | 10 条被丢弃 incumbent 若保留会否改变 G3 | 未补计、未重跑 | `.../status_reconciliation_g3_20261105/ROUND_DECISION.md` |
| 12 | 40 身份的 16 opportunity／24 calibration 与 original6/…/newG3 8 的逐项映射 | STATE 只给两个合计，未给交叉表 | `return_makespan/STATE.json` `research_counts.scope` |
| 13 | 旧“10 小图精确最优”声明 | ld_absorption 包明确 `UNVERIFIED` | `research_certificates/20261103/ld_absorption_scope/ROUND_DECISION.md` |
| 14 | 本轮 <COMPUTE_HOST> 现状 | 本审计未连接；只有他人 11-12 07:16 UTC 与 15:52 CST 的只读收据 | `BRIEF_AGENT_CONTEXT.md`；`AUDIT_CLARIFICATIONS.md` |

### 6.3 已关闭（有正式关闭裁决，不得改名复活）

| # | 关闭对象 | 关闭裁决 | 证据 |
|---|---|---|---|
| 1 | whole-station exact／partial-trip／R3 generic／energy-duty projection／R5 swap-kcycle／R6 envelope／R7 crew 列 | 各自 ROUND_DECISION；G0 NO_GO 或 NON_DIRECT_INCREMENT | `research_round2..7/*/ROUND_DECISION.md`；`research_certificates/*/ROUND_DECISION.md` |
| 2 | Global Assignment 作为独立新算法 | NO-GO（被 Liu §4.3.2 与官方 Java 覆盖） | `related_work/fulltext_comparison_20261102.md` |
| 3 | 旧 CA-RL 宏控制／算子选择 | 未胜强非 RL；用户 11-03 明确排除 | `execution/20261102/state_ablation/analysis/REPORT.md`；`AGENTS.md` |
| 4 | 旧 Route-RL Stage A／B／C | gate 双预算失败；B／C 未启动 | `stage_a_audit/MODIFIED_FILE.md` |
| 5 | P3 fixed14 | `first_common_BC_gate_failed_stop` | `return_makespan/STATE.json` `P3_fixed_population` |
| 6 | ordinary RL attribution pilot | `STOPPED_INSUFFICIENT_VALIDATION_SUPPORT` | 同上 `ordinary_rl_attribution_pilot` |
| 7 | 8× SCST 延训（瓶颈） | 只作诊断，不重开训练 | `20261105_bottleneck_diagnosis/REPORT.md` |
| 8 | D 原 30 流 | 硬限终止，不重启 | `D_TERMINAL_RECONCILIATION/RESULT.json` |
| 9 | WX-E v1／real v2／forecast v1／risk v1／v3–v8 | 全部 `CLOSE_NO_FULL_RUN` | `20261112_wx_e*/REPORT*.md` |
| 10 | WX-C v3 | `CLOSE_WX_C_CANDIDATE` | `20261112_wx_c_spatial_diag_v3/REPORT.md` |
| 11 | reserve v5 | `HOLD_G0_NO_GO` | `.../PRE_RUN_REVIEW.md` |
| 12 | centered-dual-score | `G0_NO_GO_…_STATIC_ZERO` | `20261112_cfa_final_si_review/STATE.json` |
| 13 | observation-timing／POSMDP | `G0_NO_GO_OBSERVATION_TIMING_STANDARD_POSMDP` | `20261112_observation_timing_g0_review/STATE.json` |
| 14 | joint-event-screen／original-prompts-CFA-PbP／Zhao-Han | 三个 NO_GO | `20261112_g0_joint_event_screen/STATE.json`；`20261112_original_prompts_cfa_audit/REPORT.md`；`20261112_zhao_han_fulltext_audit/STATE.json` |
| 15 | G3 的 24/24 校准额度 | 已满，不退款、不改名挪用 | `return_makespan/STATE.json` `resource_envelope` |

### 6.4 未执行（计划存在，但无真实执行收据）

| # | 未执行项 | 应有而未有的收据 | 证据／状态 |
|---|---|---|---|
| 1 | G5 全新 Formal | 0 新 Formal 地图／0 运行 | 主 STATE `new_formal_maps=0`、`gates.G5=NOT_STARTED` |
| 2 | G6 创新消融 | 0 运行 | 同上 `G6` |
| 3 | G7 正文 | `paper_writing_enabled=false` | 同上 |
| 4 | G8 完整研究包与投稿就绪 | `project_complete=false`、`publication_ready=false` | 同上；E STATE |
| 5 | 任何新 G0 机制的训练 | G0 未过，训练准入未开 | `gates.G0`；`new_mechanism_approved=false` |
| 6 | 原 WX-E 完整协议（多站异构、OU 风、移动椭圆单体、独立预报发布、背景 Poisson、600 TRAIN／20 DEV×10 日） | 只有有界 pilot | `PROMPT_RECONCILIATION.md` §WX-E |
| 7 | WX-H（1／10／100 ms 价值前瞻） | 0 运行，仅 4 个源码文件 | `20261112_wx_h_v1/`；`gates` |
| 8 | WX-C 完整在途方案（CONTINUE／SKIP_NEXT／RETURN_HOME／DIVERT，20 图×50 日） | 只有 v3 诊断 | `PROMPT_RECONCILIATION.md` §WX-C |
| 9 | N4 真 MC rollout 强对照 | `ROLLOUT_8/128` 只是记账控制 | `20261112_wx_e/REPORT.md`；`CAUSAL_ROLLOUT_APPENDIX.md` |
| 10 | 忠实完整作者 rolling TSALNS／A3 1s／3s 周期重优化 | 只有两个命名在线适配 | `20261105_deep_revision/REPORT.md` §8；`NEXT_FULL_BASELINE_SPEC.md` |
| 11 | uniform 独立重训 | 同模型评两模式 | `PRE_RUN_REVIEW.md` F4；`PROMPT_RECONCILIATION.md` |
| 12 | 多目标偏好条件化 RL 训练 | 只对已得结果重评 HV | `20261106_github_multiobjective_check/REPORT.md` §5 |
| 13 | E 的 9 项 pending（含 scientific driver、排除清单、typed reserve、NFZ 几何、功效／VAL／HV reference） | 0 | `20261106_E_continuation_acceptance/STATE.json` |
| 14 | A5 三类容量边界案例 | 0 | `AUDIT_CLARIFICATIONS.md` A5 |
| 15 | Zhao 独立 SI／Han 在线 SI／CFA 最终 PFA-oracle | 0 | 各包 `SI_STATUS.json`、`ACCESS_STATUS.json` |
| 16 | 旧“10 小图精确最优”验证 | 声明 UNVERIFIED | `ld_absorption_scope/ROUND_DECISION.md` |

---

## 7. 口径与分母（读数字前必须知道的事）

1. **两套合同分列，不得互换。** 静态／条件路线合同 **S**：固定部署／站型／目标归属；逐图 `C(candidate) <= C(R_Liu)+1e-7`、epsilon=0；同一整图 6s／12s 下改善 `M_return`；还须同时胜忠实 Liu 锚点与同目标最强合格 non-RL。动态天气／应急合同 **W**：高优先准时率、迟到 CVaR90、独立冻结的成本约束（历史 WX 用成本比 bootstrap 95% 上界 ≤1.01）。本文件中 `J=1169.612132` 等属**联合动态 J**，**不是** `M_return`，也**没有**通过 S 的逐图 cap。
2. **独立单位是地图。** 事件日、求解 seed、训练 seed 都**嵌套在图内**，不能展开成独立 n。Stage A／Formal v4 的 720／600 行、联合 DEV 的 96 图日行、WX 的 512 行，都不等于 720／600／96／512 张独立地图。
3. **三种“行”不可混用**：意向行（intent）≥ 实际启动行 ≥ 按时交付行。G3 是 80 意向／60 启动／47 按时；D 是 29,760 键全部无 intent。把 intent 当 completed 会系统性夸大执行量。
4. **评价行 ≠ 独立模型**：联合深重构 1,184 行 = 320 控制（8 图×4 日×10 控制）+ 864 模型（8 图×4 日×9 模型×3 checkpoint）；模型侧只有 9 个训练 run。
5. **训练统计量 ≠ 总算力**：768／960 是模型选择口径；774／982 含另存尝试；v1 的 192／768／672 是另一批。合计算力可以相加，**效应不可合并**。
6. **预算单位四分**：①solver-s（6s／12s×行数，可精确求和）；②CPU-s／核小时（报告或 cgroup 收据）；③**预约额**（7.5/16、10、32 核小时是 reservation，不等于消耗）；④墙钟（含并发与 I/O）。本文件逐行标注用的是哪一种；未给 CPU 收据的包只报 wall 或“无收据”。
7. **百分比方向**：成本／J 的“+”表示更差；`benefit`／收益的“+”表示更好；SEMFiX 的定义是 `100*(Java−Python)/Java`，正数偏向 Python。引用时必须带方向词，不能只写数字。
8. **比值与字节**：55.371981291828945／50.9727037026624 = **1.08631**（+8.63%）；90.46030993643605／89.74725959419959 = **1.00794**；88.33112038501943／93.63879794673824 = **0.94331**；69.36025515744755／91.65824956019068 = **0.756727**（不完整行，不可采信）。12,045,821,536 B = **12.046 GB（10⁹）** = **11.22 GiB（2³⁰）**；“超过 12 GB 硬限”按十进制成立。
9. **失败与超时不得剔除**：D 的 144 TIMEOUT、G3 的 5 超时＋8 导入失败、WX 的 24／80／1 条不完整行、联合深重构的 3 个失败 BC seed 全部保留在分母。任何“只算 DONE”的均值都不被本文件采信。
10. **工程测试 ≠ 科学证据**：39+112+8、18、25／16、146、214、222 等测试数只证明实现契约，不证明策略质量、创新或 RL 优势；反之，工程 PASS 也不自动放行科学 gate。
11. **“完成”的四种含义**：复现完成（SEMFiX）、工程完成（E、reserve v5 检查）、有界 pilot 完成并按闸门关闭（WX）、科学 gate 通过（**一个都没有**）。本文件从不把前三者写成第四种。

---

## 8. 证据与限制

### 8.1 本审计实际做了什么

- 用 `HISTORY_INDEX.json`（5,908／3,130／897／204 包）做去重导航，按 canonical 路径直读约 70 份文件（清单见 §9）；对重复快照（`LATEST_STATUS.md` 85 份、`ROUND_DECISION.md` 19 份等）只读一份。
- 对关键 JSON 做结构读取与**少量派生算术**（均已在正文标注“本审计求和/推算”）：SEMFiX 600 行 `elapsed_seconds` 求和；WX-E REAL_PILOT 行级计数（24 failed／24 unserved）；成本比值；核小时换算；`HISTORY_INDEX` 统计。
- 对冲突执行“内容＋日期＋终局收据”三条件裁决（§5），并明确写出采用哪一份、依据什么。

### 8.2 本审计没有做什么（避免被误读为已核实）

- **没有连接 <COMPUTE_HOST>**，没有新的 hostname／CPU／磁盘／进程观测。文中服务器事实全部是引用既有收据（`BRIEF_AGENT_CONTEXT.md` 的 15:52 CST 收据、`AUDIT_CLARIFICATIONS.md` 的 07:16 UTC 只读收据）。
- **没有重跑**任何求解／训练／评价／地图生成；没有重新打开 1,200 份 witness、29,760 个 D 键或 8,256 条 B 行；没有重算 SEMFiX 成本。
- **没有修改**任何历史文件；本文件是本包新增的唯一产物。
- **不是独立研究者审计**：同一执行者的第二遍阅读不能标为第三方独立验收；历史独立审计身份按其原收据保留。

### 8.3 已知的证据弱点

- **报告文字与 JSON 可能不一致**：WX-E 的 `PILOT.json` vs `REAL_PILOT.json`（K4）、REPORT “28 failed rows” vs JSON 24（K5）已实证。凡遇冲突，本文件采用逐行 JSON，并保留 REPORT 原文差异。
- **部分包无 CPU 收据**：WX 六个 pilot、Stage A 训练、联合深重构只有 wall／上限／逐行 `online_ms`，没有总 CPU；本文件不虚构。
- **四舍五入**：REPORT 表里的 J 多为 6 位小数（如 1169.612132），STATE 给 1169.6121315113576；本文件优先引 STATE／JSON 全值，表格处保留报告舍入值并注明。
- **HISTORY_INDEX 是导航，不是权威**：它自己的 `limits` 写明“preferred duplicate path 是启发式，不是权威；快照不等于独立证据”。本文件按此使用。
- **未核项仍可能改变结论**：作者 MILP 口径、容量边界、真实公共 rollout、SI 全文五项若将来补齐，可能改变“未证实”而非“已证实”的清单——但**不会**把已关闭的 pilot 重新打开。

---

## 9. 直接读取清单（canonical，去重后）

> 以下为本审计**逐字读取**的文件（不含仅用于计数/结构检查的目录列举）。路径相对 `<LOCAL_PATH>`。

**合同与入口（7）**：`AGENTS.md`、`USER_RESEARCH_REQUIREMENTS.md`、`RESEARCH_PLAN_ROUTE_RL.md`、`LATEST_STATUS.md`、`route_rl_research/20261103/return_makespan/STATE.json`、`EXECUTION_PLAN.md`、`joint_weather_emergency/20261106_E_continuation_acceptance/STATE.json`。

**交接与索引（4）**：`joint_weather_emergency/20261112_takeover_completion/BRIEF_AGENT_CONTEXT.md`、`project_status/20261112_claude_handoff/CLAUDE_TAKEOVER_PROMPT.md`（全文 627 行，分段读）、`HISTORY_INDEX.json`（统计）、`project_status/20261112_claude_takeover_audit/{TAKEOVER_AUDIT.md,AUDIT_CLARIFICATIONS.md}`（上一轮静态审计，仅作对照）。

**复现（3）**：`reproduction/reviewer_package_semfix/{SEMFiX_FULL_RESULTS.md,REPRO_PROTOCOL.md,SEM_FIX_PROVENANCE.md}`。

**旧控制与 Stage A（3）**：`execution/20261102/{ROUND_DECISION.md,state_ablation/analysis/REPORT.md}`、`stage_a_audit/MODIFIED_FILE.md`。

**return_makespan（5）**：`REMAINING_TASKS.md`、`G23_ROOT_STATUS.md`、`G1_SPEC.md`、`g24_weather_nfz/status_reconciliation_g3_20261105/{ROUND_DECISION.md,STATUS_IDENTITIES.json}`。

**联合天气／应急（6）**：`joint_weather_emergency/20261105/PROTOCOL.md`、`20261105_deep_revision/{REPORT.md,FUTURE_TRAIN_ONLY_DECISIONS.md,NEXT_FULL_BASELINE_SPEC.md}`、`20261105_bottleneck_diagnosis/REPORT.md`、`20261105_route_claim_audit/REPORT.md`。

**方法族（6）**：`20261105_rl_method_survey/{RL_RESEARCH_AND_SELECTION_20261106_1011.md,TRANSFER_DESIGNS_20261106_0558.md}`、`20261105_research_continuation/REPORT.md`、`20261105_method_screen/{RESULT.json,SCREEN_DESCRIPTIVE.json,SUPERVISOR_END.json}`、`20261106_method_family_B/{STATE.json,readonly_audit/B_METHOD_DECISION.md,B_METHOD_DECISION.json}`、`20261106_control_qualification_C/{RESULT.json}`、`20261106_control_qualification_C2_infrastructure/STATE.json`。

**D／E／多目标（5）**：`20261106_server_recovery/D_TERMINAL_RECONCILIATION/{REPORT.md,RESULT.json}`、`20261106_github_multiobjective_check/REPORT.md`、`20261106_root_acceptance/STATE.json`、`20261106_multiobjective_round_E_bootstrap/ROUND_E_REGISTRATION_DRAFT.json`（结构）。

**WX 包（9）**：`20261112_wx_e/{REPORT.md,STATE.json,results/PILOT.json,results/REAL_PILOT.json}`、`20261112_wx_e_real/REPORT_V2.md`、`20261112_wx_e_forecast_v1/REPORT.md`、`20261112_wx_e_risk_v1/REPORT.md`、`20261112_wx_e_v8/REPORT_V3_V8.md`、`20261112_wx_c_spatial_diag_v3/REPORT.md`。

**公共告警／G0 关闭（8）**：`20261112_public_fault_conditioning/{REPORT.md,server_evidence/TEST_RECEIPTS.json}`、`project_status/20261112_g0_reserve_v5_static_audit/{HANDOVER_RECONCILIATION.md,MODIFIED_FILE/PRE_RUN_REVIEW.md}`、`project_status/20261112_cfa_final_si_review/STATE.json`、`project_status/20261112_observation_timing_g0_review/STATE.json`、`project_status/20261112_g0_joint_event_screen/STATE.json`、`project_status/20261112_zhao_han_fulltext_audit/STATE.json`。

**早期轮次／证书／文献（10）**：`research_round2..7/20261102/ROUND_DECISION.md`（6）、`research_certificates/*/ROUND_DECISION.md`（3）、`related_work/fulltext_comparison_20261102.md`。

**状态与审计（4）**：`route_rl_research/20261103/STATE.json`、`completion/TASKS.md`、`audit/20261104_github_rigor/RESEARCH_RIGOR_REPORT.md`、`project_status/20261112_weather_rl_goal_audit/REPORT.md`。

**先例／书目／能力（3）**：`project_status/20261112_original_prompts_cfa_audit/{REPORT.md,PROMPT_RECONCILIATION.md}`、`project_status/20261112_causal_rollout_capability_audit/CAUSAL_ROLLOUT_APPENDIX.md`。

**登记与协议（1）**：`project_status/20261112_bibliography_primary_completion/BIBLIOGRAPHY_AUDIT.json`（结构＋计数）。

---

## 10. 下一项有界工作（本审计的建议，不是新执行）

1. **先修文档层唯一实质错误**：把 `return_makespan/STATE.json` 的 `continuation_20261112_wx_e` 与接手指令 §5.4 的 WX-E 数字改为 `REAL_PILOT.json` 的 0.0／1.08631，并在字段上标 `source=REAL_PILOT`、`toy_invalidated=true`。这不改任何科学结论，只消除 stale 引用（K4）。**不要**改历史文件原字节——在新登记文件里加更正条目。
2. **补一个 G0 对象或写 NO-GO**：唯一获准的下一步仍是“一个具有明确新构造/估计步骤的物理路线机制”六件套，或 `NO_NEW_DISTINCT_MECHANISM_NO_TRAINING` 的关闭裁决；不得用修复 F1–F9、换网络、换 seed 替代。
3. **在动任何新实验前先做两件零成本核对**：①A5 三类容量边界案例（精确等于／±ε/2）；②把 `REAL_PILOT` 的 24／64 不完整行与 REPORT 的 28 对齐（若 28 有别的定义，写明分母）。
4. **资源纪律**：旧账 40／126／24-24／7.5 核小时／作者 40-48 不得重算或退款；任何新大规模 W 研究须独立人口、排除清单、资源登记与新的硬上限（D 的 12 GB 教训）。

---

*本文件由接手审计线程生成；所有数字均可在 §9 列出的原始文件中复核。若与后续终局收据冲突，以更新且更接近终局的收据为准，并在新文件中登记，不覆盖本文件。*



