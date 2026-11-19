# CLAIM_EVIDENCE_MATRIX — 每项主张到原始证据

日期：2026-11-12。级别说明：**A** = 本轮新取得并可独立复算；**B** = 历史证据，本轮只引用不改写；**C** = 论证/推理，无新实验。

|ID|主张|级别|证据（可直接打开）|分母/口径|反证或限制|
|---|---|---|---|---|---|
|C1|在 S 合同内，把作者解的整趟在站内合法 slot 间做成本中性重排，使 47 张新图 M_return 平均下降 **11.412%**（中位 10.902%，地图级 bootstrap 95% CI [−14.796, −8.179]，27/20/0）|A|`results/g3_pop/EXACT_REASSIGN_RESULTS.json`；`results/g3_confirm/EXACT_REASSIGN_RESULTS.json`；`stats/STATS.json`；`FINAL_TABLES.md`|47 图（12 开发 + 36 确认 − 1 无锚点）|若把 4x20_o1 计入，n=12 开发集均值 −12.894%，量级不变（`G3_INDEPENDENT_AUDIT.md` §6）|
|C2|该效应在**未见**的 36 图上复现：−10.951%，CI [−14.852, −7.354]，20/16/0|A|`results/g3_confirm/PREREG_CONFIRM.json`（生成前登记）；`stats/STATS.json#/replication`|36 图|确认集分析期间有子 agent 读了日志尾部约 20 行结果（`G3_REPORT.md` §1 已披露）；规则与估计量在生成前冻结|
|C3|成本中性的数学值是精确恒等，浮点差 ≤ 5.7e-14（1 ulp 级），远小于 1e-7 容差；47/47 admissible|A|`results/*/EXACT_REASSIGN_RESULTS.json` 的 `cost_delta_vs_anchor`；`G3_INDEPENDENT_AUDIT.md` §4|47 图|45/47 恰为 0，4x30_o1 −5.68e-14、10x110_o1 −2.27e-13|
|C4|1 ms 的 LPT 整趟重排在 **45/47** 图上等于该地板（vs exact：+0.100%，CI [−0.000, +0.270]，0/45/2）|A|`results/*/NONRL_RESULTS.json`；`stats/STATS.json`|47 图|仅 2 图的 6x50 类差分 ~1%|
|C5|路线级下降（joint_minmax）在**仅交付子集**上比地板再降 0.310%（n=35，CI [−0.636, −0.063]）；按 **ITT**（超时退回锚点）反而比地板**差** 3.607%（n=47，CI [+1.250, +6.407]）|A|`stats/STATS.json#/sets/pooled_all`；`G3_INDEPENDENT_AUDIT.md` §5.3|47 图，双口径|两种口径必须并列；只报前者是选择偏差|
|C6|joint_minmax 在 12 s 内对 8x80/9x95/10x110 **全部 12 图**无有效输出；原因是实现开销（每候选 deepcopy + 整图重算），不是空间小|A + C|`results/*/NONRL_RESULTS.json` 的 `failures_by_method`；`MECHANISM_SPEC.md` §3 T5|12/47|该实现因此**不构成**强非RL；不得据此断言路线 headroom 很小|
|C7|"平均改善 5% + 地图级 95% CI 下界 > 0"这一门槛被一个零学习、零路线改变、1 ms 的操作超过 2 倍（11.412 / 5 = 2.28×）|A|C1|47 图|"超过门槛" ≠ "达成研究目标"；只在 S 合同与 Liu 锚点分布上成立|
|C8|4x20_o1 的作者锚点不可用：Java 自报 latest-time 86.56491551657447，scorer 对记录解算得 79.47485804779748，cost 完全相同（Δ=0）；根因是 station#2 的 [12,1] 与 [3,19,17] 两趟 slot 归属在记录端互换|A|`results/g3_pop/author/4x20_o1/{RUN.json, reference.json, return_score.json, stdout.log}`；`G3_INDEPENDENT_AUDIT.md` §6|1 图|两种归属都可行、成本相同；按"失败不补图"该 slot 空置|
|C9|S 合同是确定性全观测 MDP（global_env.py 无随机源），因此 rollout 的 H 条样本退化为 1 条确定性续接、VFA 退化为确定性回归，估计/信用步骤方差恒为 0|C|`MECHANISM_SPEC.md` §2 T6；`global_env.py` 全文 grep|代码级|这是**论证**，不是实验；它只否证"在 S 内引入估计类机制"，不否证 RL 一般|
|C10|S 合同内不存在通过 G0 第③项（相对最近先例的实质新步骤）的机制 ⇒ 不启动训练|C|`G0_DECISION.md` 全文；`MECHANISM_SPEC.md` 10 候选 × 六项；`CLOSED_DIRECTIONS.md` C01–C33；`PRIOR_ART_EQUATION_AUDIT.md` §C|10 候选|W 合同不在本裁决范围；R1–R4 给出重开条件|
|C11|本轮的"成本中性重排"不是新现象，而是对 2026-11-02 已记录的 C04 不变量在新目标（M_return）下的重新计价|B + C|`CLOSED_DIRECTIONS.md` §C04（原文引用含 LD duty 131.944→41.944）|—|必须给 C04 加"不变量是成本、不是 max slot duty"的注记；不得当作新机制|
|C12|交接文档与主 STATE 中的 WX-E 首包数字 `V_cluster=-0.40625`、成本比 `1.20743` 来自已作废 toy；可采信值为 `0.0` / `1.086307`|B|`WX_PILOT_RECEIPTS.md` §3 D1；`TAKEOVER_AUDIT.md` §5 K4；`joint_weather_emergency/20261112_wx_e/results/REAL_PILOT.json`|14 次运行 3,520 行|关闭结论不变（仍 CLOSE），但差距口径须改|
|C13|WX pilot 全部关闭；WX-H 0 运行且 deferred；原完整多站异构 WX-E、真实 N4、uniform 独立重训、Formal、论文包均未执行|B|`WX_PILOT_RECEIPTS.md` §5；`RESEARCH_PLAN_ROUTE_RL.md`|13 包|"pilot 已关" ≠ "原方案已充分执行"|
|C14|旧 40 新身份全部是 family=[3,20]、同一套天气的同一人口抽样，不是 40 个独立人口；120 官方图全部已暴露|B|`SPLITS_AND_EXCLUSIONS.md` §3；JSON 的 `identity_ledger_40`|120 / 40|本轮 48 图覆盖 12 个 family，是新人口|
|C15|Zhao 独立 SI 已取得（HTTP 200，5 页，SHA256 6b9a7dd4…）；Han 在线 SI 存在性仍未核实（文章页 403、CDN 11 URL 404）|B|`PRIOR_ART_EQUATION_AUDIT.md` §D；`evidence_prior_art/si/`|2 篇|403 ≠ 不存在|
|C16|Han (2r)–(2t) 的共享容量写作 Σ_z r_zb ≤ N_b^next，N_b^next 由 (2q) 内生；我方当前合同**没有**该约束|B|`PRIOR_ART_EQUATION_AUDIT.md` §B；`CODE_MAP.md` §D|—|引入它即改合同，属"负差异"|
|C17|Zhao 的 18.58% 是风信息价值（WA vs WU）的摘要数字，正文表格无对应单元、不可复算，且 p.22 同族又写 38.51%|B|`PRIOR_ART_EQUATION_AUDIT.md` §A5|—|不得转用为本项目 RL 优势|

## 不支持的主张（明确列出，防止误引）

|主张|为什么不被支持|
|---|---|
|"RL 能/不能胜过 non-RL"|本轮 **0 次训练**，没有任何 RL 运行|
|"某方法通过 G3"|主门槛是打赢成本中性地板；没有任何方法做到（LPT 0 胜，joint ITT 更差）|
|"路线空间为零"|6x50_o1 上路线搜索再降 0.42%（相对锚点 4.21%）；大图超时是实现开销|
|"W 合同有任何新结果"|本轮未运行任何 W 实验|
|"有 Formal 结果"|无 Formal；本人口是 G3 开发/确认集|
|"11.412% 是新算法/新机制"|C04 已记录同一不变量的方向|
