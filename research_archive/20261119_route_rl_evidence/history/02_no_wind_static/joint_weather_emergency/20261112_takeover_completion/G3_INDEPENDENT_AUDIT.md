# G3 独立复核（G3_INDEPENDENT_AUDIT）

复核时间：2026-11-12 16:05–16:18 Asia/Shanghai（服务器 UTC 08:05–08:18）。
复核主机：<COMPUTE_HOST> `<COMPUTE_HOST>`，Python 3.10.12（**仅标准库**，无 pip），JDK 不参与本复核。
访问方式：`<EXECUTION_PATH>` 只读读取远端结果；**未修改** `<EXECUTION_PATH>` 任何字节，所有新文件只写我自己的 `<EXECUTION_PATH>` 与本地本包目录。
复核原则：**不信任何已有 JSON 的汇总字段**，全部从 `maps/*.txt` + `solution.json` + `scorer.py` 重算；仅把存储值当作"被检验对象"。

## 0. 判定（先给结论）

| 问题 | 判定 | 依据 |
|---|---|---|
| 这 11 张图的锚点、NONRL、精确重排数字可复现吗？ | **可以，逐位复现** | 作者 12/12、LPT 11/11、joint_minmax 22/22、精确重排 12/12 全部重算一致；作者侧 18 个标量 + 5 个结构字段的最大偏差为 **0.0**（§2） |
| 可以作为 G3 的"最强合格 non-RL 地板"证据吗？ | **可以** | `exact_cost_neutral` 11/11 admissible、Δcost ≤ 2.3e-13、纯枚举 <1 s（§4） |
| 可以作为"5% 目标失去判别力"的证据吗？ | **可以，且是本轮最强结论** | 一个零学习、零路线、零成本的重排即达 −12.919%（2.58× 门槛）（§5） |
| 可以作为"某方法通过 G3"的证据吗？ | **不可以** | 主门槛 `lpt vs exact` = 0 胜/10 平/1 负；joint_minmax 只在 2 图胜出、3 大图全超时，ITT 下比地板差 +3.69%（§5.3、§6） |
| 可以作为"新机制/新发现"吗？ | **不可以** | 该操作已被旧闭合方向 **C04** 以定理级记录关闭；C04 自己的探针就把一个 DABS duty 从 131.944 移到 41.944 而成本不变（§8） |

一句话：**数字是真的，地板是真的，但"改善"不是新的，也不构成任何方法通过 G3。** 本包 §7.1 的 S 合同要求"同时胜忠实 Liu 锚点**与**同目标最强合格 non-RL"（`TAKEOVER_AUDIT.md:412`），本轮把后者从"作者锚点"抬到了一个毫秒级可算的组合下界，而没有任何方法站到它上面。

## 1. 复核对象

| 文件 | 远端路径（只读） | sha256（本审计实测） |
|---|---|---|
| 人口索引 | `g3_pop/population_index.json` | `05a0f7c1b4fa5b8e…` |
| 作者意图 | `g3_pop/AUTHOR_INTENT.json` | `04b2ac52f26f3bd2…` |
| 作者汇总 | `g3_pop/AUTHOR_RESULTS.json` | `51c5ce97426217f7…` |
| 非 RL 逐行 | `g3_pop/NONRL_RESULTS.json` | `94e11a7c90038f49…` |
| 精确重排 | `g3_pop/EXACT_REASSIGN_RESULTS.json` | `7737e18611672741…` |
| 每图锚点 | `g3_pop/author/<map>/{RUN,solution,return_score,independent_audit,reference}.json + stdout.log` | 每图 `RUN.json#/artifacts` 声明的哈希 **12/12 全部对上** |

完整 64 位哈希见 `stats/STATS.json#/provenance/result_files_sha256`。**上表是复核读取时的版本**：population_index / AUTHOR_RESULTS / EXACT_REASSIGN 在 16:12 与 16:16 两次复查一致；`NONRL_RESULTS.json` 在 **16:15:30 被并行线程原地重写**（34 行 → 22 行 → 读到 25 行），详见 §7 D13——本审计以 **94e11a7c…** 版本为准，逐行快照保存在 `audit_g3/g3_audit_raw.json`。

代码身份（本审计实际 import 的三个文件）：`scorer.py` `c6e156b2d770cec2…`、`g23/nonrl_baseline/baseline.py` `8f5c195664c1d3c3…`、`lrphsd/problem.py` `f03c2f4201cdea97…`。
人口：namespace `takeover-20261112-g3-v1`，partition `opportunity`，12 图，12 个唯一 `raw_sha256`、12 个唯一 `canonical_geometry_sha256`，状态全为 `generated`，排除记录 **12,131** = 12,120（PERMANENT）+1（synthetic smoke）+4（v2 synthetic）+6（Windows probe）——加总与索引字段一致。

## 2. 逐图作者锚点重放（12/12）

对每个 `solution.json` 重新 `scorer.score_solution`，并另写一个**独立第二时钟**（只用折线长度/speed + service，不调用 scorer 的内部函数）：

| map | 重算 cost | 重算 M_return | Δcost vs 存储 | ΔM vs 存储 | instance 哈希链 | solution_sha256 | seed 派生 | RUN.artifacts | 第二时钟 Δ | stdout latest |
|---|---|---|---|---|---|---|---|---|---|---|
| 3x10_o1 | 160.4523223663 | 56.0980821726 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 处不符 | 0.0 | 一致 |
| 3x15_o1 | 171.1365540816 | 106.9813430089 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 3x20_o1 | 250.1789437109 | 66.8239536946 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| **4x20_o1** | 249.4112658864 | **79.4748580478** | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | **不一致（86.5649155166）** |
| 4x25_o1 | 303.4640424913 | 120.9415533987 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 1.5e-14 |
| 4x30_o1 | 317.8826100354 | 130.6850986017 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 3.0e-14 |
| 5x35_o1 | 373.2586748214 | 177.0826809469 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 6x50_o1 | 479.8245266796 | 182.0015949306 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 7x65_o1 | 600.5632582001 | 229.5855769694 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 8x80_o1 | 692.5286116546 | 240.7881097611 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 9x95_o1 | 881.6416447004 | 247.6779486777 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |
| 10x110_o1 | 1006.0276002415 | 318.7368639110 | 0.0 | 0.0 | ✅ | ✅ | ✅ | 0 | 0.0 | 一致 |

- 比对字段（每图）：cost、M_return、M_service、operating_minutes、operating_cost、fixed_cost、total_distance_m、total_energy、mean/p90 target completion、visited/nonempty/ignored 计数、original_feasible、issues、solution/parameter/instance 哈希（18 项）；外加 `slot_duty`、`station_makespan`、`trips`、`target_completion`、`target_station`（5 个结构字段）。**全部 0 偏差（不是 ≤1e-9，是 bit-identical）**。
- `instance_sha256` 链：`population_index.raw_sha256 = 文件 sha256 = problem.read_instance().sha256 = solution.instance_sha256 = return_score.instance_sha256 = RUN.input_sha256`，12/12 全等。
- seed：`sha256("takeover-20261112-g3-author-seed-v1:"+raw_sha256)[:8] & (2^63−1)` 重算，12/12 与 `RUN.json#/seed` 相同（事前冻结、与成本/M 无关）。
- 上表 "stdout latest" 差异是 Java 打印浮点与 Python 求和的末位差（1.5e-14 / 3.0e-14），witness 判据是 1e-7，不影响合格性；**唯一真实不一致是 4x20_o1**（见 §6）。
- 附带发现：我最初把 `target_completion` 判为"不等"，追查后是**我的比较器**把 int 键与 str 键按不同顺序序列化造成的假差异；改为按字符串键逐值比较后最大差 **0.0**。此处记录以免读者误以为存在数据差异。

## 3. NONRL 逐行重放（34 行）

34 行 = 26 `ONTIME_VALID` + 7 `NO_ONTIME_VALID_OUTPUT` + 1 `ANCHOR_NOT_ELIGIBLE`（4x20_o1）。

**3.1 LPT（11 行）**：我**自己重写**了 LPT（按 (−duration, tuple) 排序、挑当前最轻且物理可行的 slot，1e-7 容差），再与官方 `baseline.solve(method="lpt")` 双重执行：

| 检查 | 结果 |
|---|---|
| 我的独立 LPT vs 存储 `chosen_M_return` | 11/11 相同（10 图逐位；7x65_o1 差 2.8e-14，浮点求和顺序） |
| 官方实现对存储行重放 | 11/11 相同 |
| `chosen_cost == anchor_cost`（成本中性） | 11/11 精确相等 |
| fallback 逻辑独立复算 | 11/11 一致；7x65_o1 正确判 `raw_worse_than_anchor`（LPT 给出 229.5856，锚点 229.5856，浮点上不优于锚点 → 回退锚点） |
| `delta_M_return_pct` 与 `chosen_M_return` 自洽 | 11/11 |

**3.2 joint_minmax（22 行）**：用同一预算（6s/12s）重跑 `baseline.solve`：

| 检查 | 结果 |
|---|---|
| 8 条"按时交付"行 | `chosen_M_return` 与 `chosen_cost` **逐位复现**（3x10、3x15、3x20、4x25、4x30、5x35、6x50、7x65@12s） |
| 7 条超时行 | 全部复现为 `NO_ONTIME_VALID_OUTPUT` |
| `candidate_validation_calls` | 与存储相差 ≤31（0.4%），说明墙钟切割点有微差，但未改变交付值——这一点必须如实记录：**这些行不是位级可复现，只是结果可复现** |
| 行内一致性 | `chosen_cost ≤ anchor_cost + 1e-7` 全部成立；`chosen_M_return > anchor` 的行 0 条；`ontime_valid_output` 与 `status` 全部自洽 |
| **可审计性缺陷** | 34 行**均未落盘 chosen_solution/chosen 哈希**（`baseline.solve` 返回里有 `chosen_solution`，`03_run_nonrl.py` 只存了标量）。因此 joint_minmax 行只能"重跑复现"，不能"从产物复现"——这是流程缺陷，建议下一轮把 `chosen_solution` 与 `candidate_certificates` 落盘 |

## 4. 精确成本中性重排重放（12 行）

我**独立重写**了每站穷举（不调用 `04_exact_reassign.py` 的 `trip_metrics`，用 scorer 的 `_distance`/params 重算 duration/energy），再 `validate_candidate(epsilon=0)`：

| map | 重算精确 M | 验证后 M | admissible | Δcost vs 锚点 | 与存储 Δ | 存储分配 = 我的分配 | 每站最大枚举数 |
|---|---|---|---|---|---|---|---|
| 3x10_o1 | 44.6110680447 | 44.6110680447 | ✅ | 0.0 | 0.0 | ✅ | 4 |
| 3x15_o1 | 92.7145784121 | 92.7145784121 | ✅ | 0.0 | 0.0 | ✅ | 4 |
| 3x20_o1 | 66.8239536946 | 66.8239536946 | ✅ | 0.0 | 0.0 | ✅ | 4 |
| 4x20_o1 | 69.4448042001 | 69.4448042001 | ✅ | 0.0 | —（无存储行） | — | 8 |
| 4x25_o1 | 120.9415533987 | 120.9415533987 | ✅ | 0.0 | 0.0 | ✅ | 4 |
| 4x30_o1 | 96.9264089039 | 96.9264089039 | ✅ | **−5.684e-14** | 0.0 | ✅ | 4 |
| 5x35_o1 | 136.8145855998 | 136.8145855998 | ✅ | 0.0 | 0.0 | ✅ | 8 |
| 6x50_o1 | 140.5435441918 | 140.5435441918 | ✅ | 0.0 | 0.0 | ✅ | 32 |
| 7x65_o1 | 229.5855769694 | 229.5855769694 | ✅ | 0.0 | 0.0 | ✅ | 4 |
| 8x80_o1 | 199.7116134546 | 199.7116134546 | ✅ | 0.0 | 0.0 | ✅ | 16 |
| 9x95_o1 | 247.6779486777 | 247.6779486777 | ✅ | 0.0 | 0.0 | ✅ | 32 |
| 10x110_o1 | 255.3540561525 | 255.3540561525 | ✅ | **−2.274e-13** | 0.0 | ✅ | 32 |

- 12/12 `admissible=True`、`domain_valid=True`、`cost_cap_satisfied=True`、`issues=[]`。
- **但"成本逐位不变"不成立**：9/11 图 Δcost 恰为 0.0，4x30_o1/10x110_o1 各差 −5.68e-14/−2.27e-13（重排改变的是各 slot duty 的求和顺序）。cap 是 1e-7，故结论不受影响，但报告里的"逐位不变/Δcost=0"应改为"≤2.3e-13"（§7 D1）。
- 该类最优的**结构性上限**（重要，供后续 RL 主张使用）：4/11 图零改善，其中 7x65_o1 与 4x25_o1 的瓶颈站是 **kind=1 单槽站**（固定 duty 229.5856／120.9416），任何"只重排不改路线"的操作都不可能改善；3x20_o1 与 9x95_o1 则是锚点在该类内**已最优**。因此 12.9% 的均值不是"这一类还能挖 12.9%"，而是"已挖到该类上限"。

## 5. 聚合统计（B=10000，seed=20261112，单位=地图）

口径：`d_m = M(method) − M(base)`，百分比 `100·d_m/M(base)`；配对、按地图重采样、percentile CI（排序索引 250 与 9749）；`|ΔM| ≤ 1e-9 min` 记平局。完整 14 组比较见 `stats/STATS.json`。

### 5.1 对作者锚点

| 比较 | n | 平均差 | 中位 | 95% CI | W/T/L | ≥5% 图数 |
|---|---|---|---|---|---|---|
| exact cost-neutral vs anchor | 11 | **−12.9189%** | −17.0592% | [−18.7882, −6.6955] | 7/4/0 | 7 |
| LPT 6s vs anchor | 11 | −12.8232% | −17.0592% | [−18.6560, −6.6624] | 7/4/0 | 7 |
| joint_minmax 6s vs anchor（仅交付的 7 图） | 7 | −15.4876% | −20.4767% | [−22.7497, −7.3806] | 5/2/0 | 5 |
| joint_minmax 12s vs anchor（仅交付的 8 图） | 8 | −13.6246% | −16.9062% | [−21.2097, −5.9038] | 6/2/0 | 5 |

### 5.2 主门槛：相对成本中性精确最优

| 比较 | n | 平均差 | 中位 | 95% CI | W/T/L |
|---|---|---|---|---|---|
| **LPT 6s vs exact** | 11 | **+0.12395%** | 0.0000% | [−1.07e-15, +0.37186] | **0/10/1** |
| joint_minmax 6s vs exact（仅交付 7 图） | 7 | −0.6012% | 0.0000% | [−1.8036, −1.5e-15] | 1/6/0 |
| joint_minmax 12s vs exact（仅交付 8 图） | 8 | −0.5990% | 0.0000% | [−1.6511, −1.5e-15] | 2/6/0 |

LPT 唯一一处劣势是 6x50_o1：142.4598 vs 精确 140.5435（+1.9163 min，+1.3635%）。其余 10 图在 5.7e-14 内相同（7 图逐位）。**注意 4x25_o1 的 LPT 值比"精确最优"低 1.4e-14**——纯浮点，不是真的更优。

### 5.3 ITT（把无有效输出的图计为"零改善"，按 `TAKEOVER_AUDIT.md:419` 的"失败与超时不得剔除"）

| 比较 | n | 平均差 | 中位 | 95% CI | W/T/L |
|---|---|---|---|---|---|
| joint_minmax 6s vs anchor（ITT） | 11 | −9.8557% | 0.0000% | [−16.6376, −3.2796] | 5/6/0 |
| joint_minmax 12s vs anchor（ITT） | 11 | −9.9088% | −0.5838% | [−16.6376, −3.3857] | 6/5/0 |
| **joint_minmax 6s vs exact（ITT）** | 11 | **+3.7437%** | 0.0000% | [−0.7652, +9.7398] | 1/8/2 |
| **joint_minmax 12s vs exact（ITT）** | 11 | **+3.6907%** | 0.0000% | [−0.8182, +9.7398] | 2/7/2 |

即：**"路线级搜索在地板之上再降 0.599%"只在"它按时交付的那 8 张图"上成立**。一旦把 3 张超时图按纪律计入，它比地板**差 3.7%**。这是本轮最重要的一致性裁决（§7 D2）。

### 5.4 5% 门槛

`|−12.9189| / 5 = 2.58×`；7/11 图 ≥5%。**一个 1 毫秒、零学习、零路线改变的操作就跨过了"5% 平均 + CI 下界>0"**——门槛的判别力被证否（不是"目标达成"）。

## 6. 失败分母：4x20_o1 的两种情形

**排除理由（独立确认）**：Java 自报 `latest completion time = 86.56491551657447`，scorer 对 recorded solution 算得 `79.47485804779748`，差 7.09 ≫ 1e-7；cost 一致到 2.84e-14，20/20 目标覆盖，无 issue。`RUN.json#/witness_audit.audit_errors = ["source_latest_time_mismatch"]`，`anchor_eligible=false` —— 判定逻辑正确（fail-closed）。

**根因（我这轮新做的证据）**：把 Java stdout 里的路线块解析出来重建分区，**11/12 图与 `reference.json` 在 slot 级完全一致**；只有 4x20_o1 的 station index 2（Java 打印为 "Station 3"）不一致：

- `reference.json`：slot0(large) = {[12,1], [6,7,16]}，slot1(small) = {[3,19,17]}
- Java 打印：large = {[6,7,16], [3,19,17]}，small = {[12,1]}
- 即 `[12,1]` 与 `[3,19,17]` 的 slot 归属互换；用打印分区重算时钟恰得 **86.56491551657447**（与 Java 自报逐位相同）。
- 两种归属成本相同、都可行，M_return 却从 86.565 变 79.475 → 锚点的 M 在记录端有歧义，**不能作锚点**。

**两种情形**：

| 情形 | 锚点 | 精确重排 M | 改善 | 11/12 图聚合 |
|---|---|---|---|---|
| 不计入（本包采用） | — | — | — | n=11，均值 **−12.9189%**，CI [−18.7882, −6.6955] |
| 计入，用 scorer 伪锚点 79.4749 | 79.4749 | 69.4448 | **−12.6204%** | n=12，均值 **−12.8940%**，CI [−18.2545, −7.2144] |
| 计入，用 Java 自报 86.5649 | 86.5649 | 69.4448 | **−19.7772%** | （仅该图，供对照） |

结论：**排除与否不改变量级，也不抬高结论**（n=12 的均值反而略小）。该图的排除是"守恒"的，不是"挑好看的"。但它暴露一个真实风险：`reference.json` 的 slot 归属并非绝对可信，只是本轮 12 图里 11 图与打印输出逐站对上——这一点必须写进证据限制。

## 7. 一致性检查：发现的全部不符（含很小者）

| ID | 断言（已有文档） | 实测 | 影响 |
|---|---|---|---|
| **D1** | "总运行分钟不变 ⇒ 成本**逐位**不变，Δcost=0" | 9/11 恰为 0；4x30_o1 −5.684e-14、10x110_o1 −2.274e-13 | 文档级；cap 1e-7 不受影响，但"逐位"应改为"≤2.3e-13" |
| **D2** | "路线级搜索在地板之上只再降 0.599%（n=8）" | 该 0.599% 是**仅交付 8 图**的条件统计；ITT 下 **+3.69%**（比地板差），CI [−0.82, +9.74] | **统计级**；与本包"失败不得剔除"纪律冲突，必须双口径报告 |
| **D3** | brief："joint_minmax 只在 6x50_o1 再降" | 7x65_o1@12s 也胜出：228.2453 vs 229.5856（−0.584%），故 W/T/L=2/6/0 而非 1/7/0 | 文档级（`G3_DEV_REPORT.md` §3.3 的 2/6/0 是对的，摘要句错了） |
| **D4** | "LPT 在 10/11 图与精确最优**完全相同**" | 5.7e-14 内相同；逐位相同 7 图；6x50 差 1.9163 min = 1.3635% | 文档级措辞 |
| **D5** | "成本中性重排是**新**科学事实" | 旧闭合方向 **C04**（2026-11-02，定理级）已记录同一操作，且其探针本身把 DABS duty 131.944→41.944 而成本不变 | **框架级**，见 §8 |
| **D6** | 报告指向 `results/g3_pop/*`、`stats/STATS.json` | 复核时本地 `results/` 为空、`stats/` 不存在 | 文档级；本审计已交付 `stats/STATS.json` |
| **D7** | 新人口 `takeover-20261112-g3-v1` 已登记 | `SPLITS_AND_EXCLUSIONS.md/.json`、`SERVER_MANIFEST.json` 均未登记该 namespace 与 12 图 | 登记级；只有 `population_index.json` 自证 |
| **D8** | "每图单次运行" | 3x10_o1 跑了两次（`g3_smoke` 07:58 + `g3_pop` 07:59），同 seed、同输出 160.45232236633666 | 流程级；无选择路径，但未登记 |
| **D9** | witness 用 1e-7 比对 latest-time | 4x25_o1 差 1.5e-14、4x30_o1 差 3.0e-14（打印 vs 重算） | 信息级 |
| **D10** | 草稿报告的 7 组 bootstrap 数字 | **全部复现**：均值/中位差 0.0，CI 端点最大差 1.8e-15（独立重采样抽签），n 与 W/T/L 全同（见 §10 与 `stats/STATS_self.json`） | 一致（非缺陷） |
| **D11** | "每站穷举实测最大 32768 种分配" | 实际每站最大枚举数 **32**（9x95_o1 st1、6x50_o1 st2、10x110_o1 st3）；32768 是 2^15 理论上界 | 文档级；不影响最优性 |
| **D12** | `stats/STATS.json` 只有一份、由本审计拥有 | 16:13:58 另一执行线程写入同名文件（schema `takeover_g3_stats_full_v1`，含 **36 图确认集 o2/o3/o4**），覆盖了本审计刚写入的文件；该文件现以 `stats/STATS_local.json`（`bdd84d0b…`）与 `stats/STATS_server.json`（`5aa72a93…`）两个变体存在；本审计的 dev-set 版本为 `stats/STATS.json`（早期快照 `stats/STATS_INDEPENDENT_AUDIT.json`，`4f79a947…`） | 归属级；**那 36 张确认图不在本审计范围内**，其数字未经我复核 |
| **D13** | 四个结果文件在复核期间已冻结 | **`NONRL_RESULTS.json` 在 16:15:30（CST）被并行线程原地重写**：本审计读的 34 行版本（sha `94e11a7c…`）→ 22 行 → 我复读时 25 行。所幸**当时在场的 25 行与本审计的逐行快照字段级完全相同（0 处差异）**；但字节级 provenance 已断。同时新增 `EXACT_RESULTS.json`(98,970 B)/`exact/`/`solutions/`/`EXACT_INTENT.json`（16:10–16:15），**不在本审计范围** | **provenance 级**；任何复跑必须先冻结文件哈希 |

## 8. 与旧闭合方向 C04 的关系（本审计认为最重要的一条）

`CLOSED_DIRECTIONS.md:29`（C04，2026-11-02，**定理级**）：

> 站型向量、每趟站与目标顺序、整趟多重集固定时 `C = F(z) + c_t·Σ[service(r)+length(r)/v]`，把完整趟重分配到可行 slot 或重排趟序**既不改善成本也不改善目标**……LD duty 131.944→41.944 而成本不变。

判读：
1. 在**旧目标（成本）**下这句话成立，且本轮 11 图再次验证（Δcost ≤2.3e-13）。
2. 在**当前目标（M_return）**下这句话**不成立**——"目标"已经换成 max slot duty，而 C04 自己的探针就把该 duty 从 131.944 降到 41.944（−68%），只是当时没有把它当目标。
3. 因此本轮 12.9% 不是"新现象"，而是**把 2026-11-02 已观测到的量在新目标下重新计价**。这既解释了为什么它"免费"，也说明它**不能被当作新机制或 RL 创新**（这正是 C04 的禁止用法："当作新邻域产生改进或 RL 创新"）。
4. 需要的是一个**带日期的注记**（不改历史字节）：C04 的不变量是"成本不变"，**不是**"max slot duty 不变"；在 M_return 目标下该操作等价于一个纯 min-max 负载均衡下界。

同时，C04 记录的"subset-sum/partition 结构，不是新 GAP 数学"与本轮的精确枚举一致：每站最多 32 种可行分配、11 图全部 <1 s。

## 9. 证据等级与下一项有界工作

**已证实事实**
- 11 张合格锚点、34 行 NONRL、12 行精确重排、7 组聚合统计**全部可独立复现**（B=10000, seed=20261112）。
- `exact_cost_neutral` 在 11/11 图上 admissible、成本中性（≤2.3e-13）、平均 M_return −12.9189%（CI [−18.7882, −6.6955]），7/11 图 ≥5%，是当前**可计算的最强同目标 non-RL 地板**。
- 1 ms 的 LPT 在 10/11 图上等于该地板（0 胜/10 平/1 负，均值 +0.124%）。
- joint_minmax 只在 2 图胜出地板，且 3 张大图 6s/12s 全部无有效输出；ITT 下比地板差 +3.69%。

**未证实假说（不得当结论）**
- "路线级 headroom 为正"：只有 6x50_o1（−4.21%）与 7x65_o1@12s（−0.58%）两个点，n=2，不能外推。
- "RL 也打不赢地板"：本轮没有任何 RL 运行，不能推出。
- "全规模精确最优"：`EBD949`/exact-minmax 未在本审计范围内，未引用。

**失败/关闭**
- 4x20_o1 锚点不合格（记录端 slot 归属互换），保留原行、不补图、不进汇总。
- joint_minmax 7 行超时（6s：7x65/8x80/9x95/10x110；12s：8x80/9x95/10x110），保留原行。
- C04 的"目标不变"表述在 M_return 目标下失效，**需注记**（非重开）。

**下一项有界工作（建议，按优先级）**
1. 把 `chosen_solution` / `candidate_certificates` 落盘，使 NONRL 行**可从产物**复现（现在只能重跑复现）。
2. 在 `stats/STATS.json` 与报告里把 joint_minmax 的**双口径（delivered-only / ITT）**并列，禁止只报前者。
3. 给 C04 加日期注记（成本不变量 vs duty 可变），并在 `SPLITS_AND_EXCLUSIONS` 登记 `takeover-20261112-g3-v1` 12 图与 4x20_o1 空位。
4. 若要把地板抬高，唯一有意义的对象是**改变趟集合/路线**（C04 已判"更大对象"），并在 11 图上同时报"vs 锚点"与"vs 成本中性地板"；单图胜利不算通过。

## 10. 产物与复现

| 产物 | 路径 | sha256 |
|---|---|---|
| 本文件 | `G3_INDEPENDENT_AUDIT.md` | — |
| 统计（dev set，本审计） | `stats/STATS.json` | `11f4fb2c8142d86db8d6dd91fb1d4cffbefc3977e60c47272dcfb078702fa286` |
| 本审计早期快照 | `stats/STATS_INDEPENDENT_AUDIT.json` | `4f79a947534dd160a4efd43ac0ca209ecf95af2f0eef7d1eff8c4640aec95802` |
| 并行线程统计（**未复核**，36 图确认集） | `stats/STATS_local.json` / `stats/STATS_server.json` | `bdd84d0b…` / `5aa72a93…` |
| 执行线程自算统计（dev set） | `stats/STATS_self.json` | `f3f3a17a6ddf711ca0437d9305f90ec47dee05ab4ac995a8f47ca2cbcf67eba7` |
| 原始复核记录 | `audit_g3/g3_audit_raw.json` | `0f599bf53cd5b8ddf1e568d9e498a2c4414cd0fca8f5294bebb9b8431264694e` |
| 补充检查 | `audit_g3/g3_followup.json` | `9d153a17868c9c4c634d1511ec2d412f910405e79fa4fbd8f98b99bb2b3381e9` |

远端复现（只读，脚本在我的目录）：`<EXECUTION_PATH> followup.py, build_stats.py}`；`audit.py` 82 s 内完成 12 图重放 + 22 次 joint_minmax 重跑；`JOINT_REPLAY=0` 可跳过重跑（1.1 s）。
所有数字均可由 `audit_g3/g3_audit_raw.json` 与 `stats/STATS.json` 重算：前者含每图每行的 recomputed/stored 对与偏差，后者含 14 组比较的 CI、per-map 与 13 条 discrepancy。

**与执行线程自算统计的交叉验证**：`stats/STATS_self.json`（16:05 由执行线程自己算出）与本审计的 7 组 dev 比较**逐项吻合**——n 与 W/T/L 完全相同，均值/中位差 0.0，CI 端点最大差 1.8e-15（两侧独立重采样）。即"执行者自算"与"独立复核"在 dev set 上没有分歧；分歧只在**口径**（D2 的 delivered-only vs ITT）与**表述**（D1/D3/D4/D11）。

**文件漂移说明（D13）**：复核期间 `g3_pop/NONRL_RESULTS.json` 被并行线程原地重写（16:15:30，34 行 → 22 行 → 25 行），`g3_pop/` 下新增 `EXACT_RESULTS.json`/`exact/`/`solutions/`/`EXACT_INTENT.json`。本审计**只对 08:03–08:05 UTC 的四个文件负责**（sha 见上表）；当时在场的 25 行重写结果与本审计快照字段级一致，但这不等于新文件整体已复核。**建议在写论文/STATE 前对 g3_pop 做一次哈希冻结**。

**并发写入说明（D12）**：16:13:58 另一线程写入了同名 `stats/STATS.json`（含 36 图确认集 o2/o3/o4，schema `takeover_g3_stats_full_v1`）。该内容随后被它自己改名为 `stats/STATS_local.json` / `stats/STATS_server.json`（16:15:00）；本审计的 dev-set 版本留在 `stats/STATS.json`，其早期快照为 `stats/STATS_INDEPENDENT_AUDIT.json`。本审计**未删除、未改写**那两个确认集文件。**本审计对该 36 图确认集一无所知**：未读其原始文件、未重算、不背书其 −10.95%（n=36）等数字；若该集要进入结论，需要另一份同等级复核。
