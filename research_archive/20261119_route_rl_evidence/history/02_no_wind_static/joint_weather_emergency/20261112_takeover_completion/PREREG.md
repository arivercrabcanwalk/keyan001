# PREREG — G3 开发集再分析协议与 G4 准入门槛（冻结）

> **效力边界（必读，写在最前）：本 PREREG 是在已经看过 11 张 opportunity 图的作者锚点、LPT、joint_minmax 与精确成本中性重排结果之后写的。**
> 因此它**不是**盲验 prereg，**不能**当作 Formal 的事前协议使用。它的唯一合法身份是：
> (a) G3 开发集 P1（ordinal 1，12 family）的**再分析协议**；
> (b) 后续任何 RL／强 non-RL 方法**能否进入 G4** 的事前门槛；
> (c) 已登记确认集 P2（ordinal 2–4）的**分析口径补充**（口径在此冻结，但 P2 的数值本文件一个也没读）。
> Formal 必须**另冻新人口**：新 namespace／新 partition／新 day 区间／新天气内容哈希／事前冻结的方法与代码哈希（见 §9.3）。把本文件当 Formal prereg 引用即为违规。

冻结时间：2026-11-12T08:12Z 起（= 16:12 CST）；本文件最后一次落盘的字节身份见 RESOURCE_LEDGER.jsonl 的 PREREG-00 事件与 §1 哈希表。执行者：接手包工作线程（DeepSeek Harness）。
所有实验在 <COMPUTE_HOST>（<COMPUTE_HOST>，Python 3.10.12，Corretto JDK 17.0.21，单进程串行）执行；Mac 只做文档、静态审查、传输与哈希（唯一偏离及补救见 §12-D1）。

---

## 0. 一页速查

| 项 | 冻结值 |
|---|---|
| 人口 P1 | namespace takeover-20261112-g3-v1，partition opportunity，ordinal 1，12 family；12 图生成成功，**11 图锚点合格** |
| 排除 | 12,131 条（12,120 官方+pilot／1 合成烟测／4 v2 合成／6 Windows 探针）；12 图双哈希**零碰撞**（本次复核） |
| 对照 | 作者锚点 J1b；LPT 6 s；joint_minmax 6 s/12 s；**精确成本中性重排**（主对照） |
| 主门槛 | 相对 exact_cost_neutral_reassign 的逐图配对改善均值 > 0 **且** 地图级 bootstrap 95% CI 下界 > 0 |
| 平凡参照线 | 5.0%（历史目标）／12.9189%（成本中性基线对锚点的实测均值） |
| 预算 | 作者 ≤1800 s/图；路线 6 s/12 s 硬墙钟；内存 ≤4 GB/进程；单次输出 ≤2 GB（分块+gzip）、全矩阵 ≤6 GB；**总 CPU 上限 60.0 核小时**（§5） |
| 统计 | 地图为独立单位；配对差；bootstrap B=10000（percentile）；Holm 族；超时按 ITT 记锚点值（§8） |
| 可见性 | P1 已看；P2 已登记且本文件未读其数值；P3/Formal 未生成 |

---

## 1. 冻结输入与字节身份（全部实算，不是引用）

远端根 R = <EXECUTION_PATH>

| 文件 | 字节 | sha256（本次实算） |
|---|---:|---|
| g3_pop/population_index.json | 8,126 | 05a0f7c1b4fa5b8eef3964aa691322683cef0e234dba40cc9a9fd929e8d85692 |
| g3_pop/AUTHOR_INTENT.json | 3,038 | 04b2ac52f26f3bd25a06d5621458d66f3ebe6d6917c33e175c69cec717ccb278 |
| g3_pop/AUTHOR_RESULTS.json | 2,429 | 51c5ce97426217f717a786a3700be74d1a43578da02cfc9bf9e334c32f374604 |
| g3_pop/NONRL_RESULTS.json | 37,206 | 94e11a7c90038f49a4413259bcc4a8657f62bccbc6cd0d0b764d366c37e763aa |
| g3_pop/EXACT_REASSIGN_RESULTS.json | 44,096 | 7737e1861167274193a566cb92cc382a5ef907a3fd27ae2c7e5f6c66523443f6 |
| prereg_20261112/replay/EXACT_REASSIGN_RESULTS.json（独立重放） | 44,096 | 7737e1861167274193a566cb92cc382a5ef907a3fd27ae2c7e5f6c66523443f6（**字节相同**） |
| stats/STATS_self.json（本地） | 7,414 | f3f3a17a6ddf711ca0437d9305f90ec47dee05ab4ac995a8f47ca2cbcf67eba7 |
| prereg_20261112/STATS_self.json（服务器复算） | 7,412 | 95dac248dc395ac4e80bd3e6396ba471af2b5c00ad533cfc7b6c3dc7dc077411 |
| SPLITS_AND_EXCLUSIONS.json（本包） | 97,034 | 6bd12d2841d39b519d34c1898d810958b035d071421897dd9f71fc060508379e |
| g3_confirm/PREREG_CONFIRM.json（并行线程，见 §9.2） | — | 2fe9460aa0374f03ef89c3bb09d90d8815cc559c842caa36c92d19e54950fe66 |
| g3_confirm/population_index.json | — | b1ffcb6736d62d0ce6fabb11456e5183abf2130dd9f66479a675751dc61d70c7 |
| runtime/corretto17.tar.gz | 194,714,953 | 8f9a2ddb131ec5317419f2b0769240fe22ce27f8a0ae43f5346d53e1c8aec6a0 |
| runtime/jdk17/bin/java | — | 674d1d9312e2054c065de0a128f9b0b8e5f12781e86d57f974a705bd89bd3b97 |
| harness/04_exact_reassign.py | 6,492 | e120cd7f2e18b8038b150c1c881ce0c4c3ca07a57f1c152c4d9382dfdfd6aec3 |
| prereg_20261112/compute_stats_server.py | 4,271 | eef73b6262fef648e15b74161c4c2a463b11c6b695bf565818f6340b9c927738 |

统计脚本的服务器复算与本地结果**点估计逐位相同**，仅 4 个 CI 端点在最后 1–2 ulp 不同（例：−6.695504390121136 vs −6.695504390121138；相对差 ≤3e-16），不改变任何判定（§11-K3）。

---

## 2. 人口 P1（冻结）

| 项 | 值 |
|---|---|
| namespace | takeover-20261112-g3-v1 |
| partition | opportunity |
| ordinal | 1（每 family 仅 1 张；**不得事后加 ordinal**） |
| family | 12 个：(3,10) (3,15) (3,20) (4,20) (4,25) (4,30) (5,35) (6,50) (7,65) (8,80) (9,95) (10,110) |
| 生成器 | v2 2.0.0-engineering；协议 constraint-reconstructed-sequential-conditional-uniform-proposal；RNG SplitMix64（2015-02-16-reference-variant-v1） |
| 图数 | 12 生成成功；**11 锚点合格**（4x20_o1 = ANCHOR_NOT_ELIGIBLE，不补图） |
| 判定时点 | 锚点合格判定完成于 AUTHOR_RESULTS.json 的 mtime 08:00:33Z，**早于**任何方法结果（NONRL 08:03:42Z、EXACT 08:05:14Z）⇒ 该排除与任何方法的表现无关 |

### 2.1 逐图双哈希（population_index.json 取值 ＋ 本次独立复算，24/24 一致）

复算方法：raw 用 sha256sum；canonical 用 generator_v2.parse_instance_text ＋ canonical_geometry_identity。结果 BAD=[]。

| map | sites×targets | 字节 | raw_sha256 | canonical_geometry_sha256 |
|---|---|---:|---|---|
| 3x10_o1 | 3×10 | 1,551 | f32c450b27fe556d1fc52bf297ec9c0503f5c3e68506a91456872ee7a0d47243 | fa0a03295bd339c1697799f7866fdb7063e4c40d27c79259513d9e1811ada6ea |
| 3x15_o1 | 3×15 | 2,171 | bc3f9d54661809cf1e5f50b7ad562a2a9f566df74b8f24d49fd48d81df958b7b | 5d21665d24ca480b777e129ab243ad4fbce6686bc073ae415c79780b5ba16a9b |
| 3x20_o1 | 3×20 | 2,752 | 38bd5346b59b8be8fb21c8bee2d038ca085b96b7cd1da883232da465423d6651 | 31df13416caf2f982a3b2146a6a96053b2aa7b12eac2ce76434ad612757cdb74 |
| 4x20_o1 | 4×20 | 2,852 | 4c1dad25ecc2be3c0034f0fdf9739babc012254abbd745ea063f8637ce1f8781 | ab9878335685790df978f7c24bda30e09e0684039af72c87059b4d06c3d9a370 |
| 4x25_o1 | 4×25 | 3,469 | e173dab64634fd8788e7f7ca8a85c8cb8fd144444dba82f55cfd31eabe8246d1 | a20c5362c7c57bb9b0dbaa3eb226710a19e06408ef3f5dbfef480273af15bd1a |
| 4x30_o1 | 4×30 | 4,058 | 1a3b3534815b284173ece990b02afbdaeac4947f3665221e5928ade1561ae0ad | 9b05c3bae01f0b85e849b3e0d11cfd10cb50bfa4fba08df0148139898ddcfd5b |
| 5x35_o1 | 5×35 | 4,752 | 938f793dfd908b3b793f0ee7c7986bab3e0d9f25a2dbfe56eff4e8054211eb2c | e1d31d561facd87678dd59d7c29c7872ca68bb3ee8d658d6017ddc2c89c8dbdf |
| 6x50_o1 | 6×50 | 6,655 | 67a83103d5158dfc3a3fafce23e441d3e532c9c678ae8d4268272fbbb46189b0 | e43e8502d11b46f4a21f9e866b1b988a2a2d9f7e04678945a1ecc77c77a220a4 |
| 7x65_o1 | 7×65 | 8,555 | 01f30896c4d8ec0734cf1d42434cfbcaafd1f1a7fa83a0f3a035a3884dc137ad | 900b546b363a72c4ea03b4deeb31fa9245588319fcaddcbdb558426ba703167d |
| 8x80_o1 | 8×80 | 10,411 | daf0afc82dd1b96565c9bc4c74e8bd5077b550c9245d6fe65096dc9e6d83c16c | 03b23e6f7722adedbc41ada06205189cdb717b59515875f21bfaea3d4f6b103a |
| 9x95_o1 | 9×95 | 12,539 | e0ae8575009433bbdaf42256c7809948c54d54f17259cf22fd859c5335cc3679 | f7bb9c19deb6fafb8b53b31e5defb586697a1bdac937db1589a9d6d8ac36ea23 |
| 10x110_o1 | 10×110 | 14,071 | 920bee0182957d36b99ef9944f75b8ec4b69666f6981d9eb8e21b975304eda34 | 4501db540ab34244bc0d67508008aa19a79f929fff920e25d214faea3aecc319 |

地图字节合计 73,836 B；g3_pop/ 合计 545,546 B（du -sb）。

### 2.2 4x20_o1 的处置（冻结，不得改写）

- 作者 Java 自报 latest completion time = 86.56491551657447；独立 scorer 对 recorded solution 算得 M_return = 79.47485804779748。
- 两者 cost 完全一致（249.41126588643058，Δ=0），20/20 目标服务、无 issue；差值恰为 45.11378648015091 ＋ 41.45112903642357。
- 定位为**记录端**：station#2 的 [6,7,16]（45.114）与 [3,19,17]（41.451）在 reference.json 的 slot 归属与 Java 打印的 large/small 归属互换；两种归属均可行的、成本相同。
- 裁决 anchor_eligible=false → **不进任何汇总，不补图，不退款**。分母恒为 11，且该判定早于任何方法结果。
- 证据：g3_pop/author/4x20_o1/{RUN.json, independent_audit.json, reference.json, return_score.json, stdout.log}。

---

## 3. 排除清单与零重叠证明

| 项 | 值 |
|---|---|
| 清单文件（本包） | SPLITS_AND_EXCLUSIONS.json，sha256 6bd12d28…8379e，97,034 B |
| 排除记录总数 | **12,131** |
| 组成（population_index.exclusion_sources，逐源 sha256） | 永久 v1 官方+pilot 90ea8233… = **12,120**；合成烟测 6e62b161… = **1**；v2 合成 623be2a4… = **4**；Windows 开发探针 8d78dfd7… = **6** |
| 本人口核对 | ExclusionIndex.from_paths(default_exclusion_paths()).require_research_ready() 通过；12 图 ×（raw, canonical）**零碰撞**（本次实跑输出 with_collision 0） |
| 已暴露人口 | 120 官方（1,200 配对全暴露）、40 g24 新身份（16 opportunity ＋ 24 calibration/validation，额度 24/24 满）、620 GitHub 发布实例、96 Stage A、32 joint、44 deep_revision、44 method_family_B、64 sufficient_training_D、12 个 WX 包 —— **可用于新选模的旧地图 = 0** |
| 新人口规则 | 沿用 SPLITS_AND_EXCLUSIONS.md §7.2 R1–R10（双哈希登记、排除双查重、只换 seed/namespace 不算新人口、family ≥3、day 区间不重叠、天气内容哈希独立、map 为 n、锚点失败不补图、跑前登记资源与字节上限、已暴露永久退出） |
| 本人口性质 | **新 namespace ＋ 新 family 组合**（12 family vs 旧 40 图全为 [3,20]），但仍是 **G3 开发集**，不是 Formal |

---

## 4. 方法冻结（5 个身份 ＋ 1 个空槽）

| method_id | 定义 | 实现／证据 | 状态 | 备注 |
|---|---|---|---|---|
| author_j1b | 作者 Java，J1b profile：outer 500，路线局部搜索 100，ALNS **名义 5000 / 实际 270**（for iter<5000 && temperature>finalTemp；T0=1000，α=0.95，finalTemp=1e-3 ⇒ 270 次后退出），w_ub=5.0；seed = sha256(“takeover-20261112-g3-author-seed-v1:” ＋ input_sha256)[:8] | author_build/J1b/classes；逐图 RUN.json 含源码/字节码/build/DEP 哈希 | 已执行（12 图，11 合格） | 270 的代码依据见 PAPER_EQUATION_COMPARISON.md §B.12/B.13（J:10–11,57） |
| lpt_6s | 站内 LPT（最长处理时间优先）把锚点整趟分配到合法 slot；预算 6 s，实际毫秒级 | harness/03_run_nonrl.py | 已执行（11/11 ONTIME_VALID） | 零学习、零路线改变 |
| joint_minmax_6s / joint_minmax_12s | 路线级确定性下降（g23/nonrl_baseline/baseline.py），目标 min-max，保持成本 cap | 同上 | 已执行（22 单元：15 有效、7 超时） | 每预算为**独立单元**，禁 best-of-budget（§7.3） |
| exact_cost_neutral_reassign | **主对照**。只把锚点的整趟（station→perm→station 闭合巡回）整体重分配到该站其他合法 slot；每站穷举（slot=1 平凡；slot=2 且 trip≤15 ⇒ ≤32,768），取 min max_slot duty | harness/04_exact_reassign.py（sha256 e120cd7f…） | 已执行（11/11 OK，11/11 admissible） | 独立重放 0.102 s **字节一致**（§11-K2） |
| strong_minmax_alns | 允许改变趟划分/路线的强 min-max ALNS，作为“出成本中性类”的强 non-RL | harness/exact_minmax.py 与 logs/strong_nonrl/（并行线程，未交付） | **未交付，槽位冻结** | 交付前须冻结代码 sha256 与方法版本；**只能进 P2/P3 作主比较**，P1 仅可描述（§9.4） |

### 4.1 成本中性类的数学前提（地板定义）

把整趟重分配不改变任何一趟的内容、顺序、能量或时长 ⇒ 每站 operating_s 不变 ⇒ cost = fixed ＋ 0.5·operating 不变 ⇒ cap C ≤ C_Liu ＋ 1e-7 恒满足。实测 Δcost：9/11 图恰为 0，10x110_o1 为 −2.27e-13、4x30_o1 为 −5.68e-14（相对 ≤2.3e-16，求和顺序的 1 ulp，非真实成本变化）。**故本类内最小化 M_return 是纯 min-max 负载均衡，与路线内容无关**；它给出任何方法必须超越的**可计算地板**。

---

## 5. 预算与硬限（冻结，跑前登记）

| 项 | 硬限 | 依据 |
|---|---|---|
| 作者锚点 | ≤1800 s/图（RUN.json timeout_seconds=1800） | 12 图实测 1.401–8.716 s |
| 路线／非 RL 方法 | **6 s / 12 s 硬墙钟**，超时即 NO_ONTIME_VALID_OUTPUT，不得加时重跑找阳性 | 合同 S；实测 7/22 joint_minmax 单元超时 |
| 内存 | ≤4 GB/进程 | JVM −Xms32m −Xmx512m；Python harness <300 MB |
| 输出 | 单次 ≤2 GB（分块 ＋ gzip ＋ 索引；禁止为省空间删原始失败事件）；**全矩阵新增 ≤6 GB** | 远端 / 可用 9.6 GB（08:08Z 实读 df）；吸取 D 包 12,046,821,536 B 超限 exit −9 的教训 |
| 磁盘预检 | 开跑前 df 可用 ≥5 GB，否则不启动 | 同上 |
| 并行度 | ≤4 并发进程 | 104 核但磁盘/内存约束；墙钟 ≈ CPU/4 |
| **总 CPU 上限** | **60.0 核小时** | §5.1 逐项推导 |

### 5.1 60.0 核小时的推导（可逐项复算）

| 组件 | 单元 | 数量 | 单元成本 | 核小时 |
|---|---|---:|---:|---:|
| A 作者锚点（P1 12 ＋ P2 36 = 48 图，按硬限计） | 图 | 48 | 1800 s | 24.00 |
| B 路线／强 non-RL：48 图 × 2 预算 × 10 方法 | run | 960 | 12 s | 3.20 |
| C 精确重排 ＋ 全规模精确 min-max 上界 | run | 96 | 60 s | 1.60 |
| D B＋C 全量独立重放一次 | — | — | — | 4.80 |
| E RL 训练（**仅 G4 准入后**）：3 seed × 4 机制 × 2 h | run | 12 | 7200 s | 24.00 |
| F RL/rollout 评价：48 图 × 3 seed × 2 预算 | run | 288 | 12 s | 0.96 |
| G 工程测试（T1–T7）与统计复算 | — | — | — | 1.00 |
| **合计** | | | | **59.56 → 上限取整 60.0** |

已消耗（实测，§11）：作者 12 图 **46.294 s** 墙钟（单核 JVM 代理 CPU）＋ 非 RL 33 个有墙钟记录的单元（26 ONTIME_VALID ＋ 7 超时）**80.938 s** ＋ 精确重排重放 **0.102 s** ＋ 统计复算（秒级）＋ JDK 安装／代码同步（分钟级）≈ **0.06 核小时**，为上限的 0.1%。**未使用任何历史额度，未恢复任何旧 driver。**

### 5.2 RESOURCE_LEDGER.jsonl 的字段语义（冻结，防误读）

- 每行一个事件，固定 12 键：ts_utc／exp_id／kind／maps／methods／budget_cpu_s／actual_cpu_s／wall_s／bytes_written／exit／evidence_path。
- **actual_cpu_s 是“单核墙钟代理”，不是 cgroup 实测**：本包未安装进程级 CPU 计数器；对 ActiveProcessorCount=1 的 JVM 与单线程 Python，CPU-s ≈ wall_s。连墙钟都无收据的写 null，**不估算、不编造**。
- exit：进程退出码（整数）；收据只有状态字而无退出码时写状态字（如 "TIMEOUT_NO_VALID_OUTPUT"），不伪造数字。
- exp_id 可与 EXPERIMENT_MATRIX.csv 的一行或多行对应；多条用分号连接表示同一执行批。
- bytes_written：该事件新增字节（未压缩）；null 表示未计量。
- 事件只增不改：失败与超时逐条保留（7 条超时、1 条锚点不合格、2 条无字节收据的首版失败）。
- ts_utc 精度规则：(a) 有文件 mtime 或 generated_at_utc 的用真实秒；(b) 只有分钟级收据的取该分钟的 :00；(c) 同一分钟内必须保持因果顺序时，后一事件顺延到下一分钟边界，并在 evidence_path 指向分钟级收据。文件按 ts_utc 非降序排列。
- **不得对 actual_cpu_s 求和当作总量**：失败行与被其所属批次的 end 行会重叠计时（同一次运行既计入批次总量，又单列一行），基础设施事件（JDK、代码同步）另计。正确总量口径见 §5 与 §5.1。

---

## 6. 指标（冻结）

| 指标 | 定义 | 单位／分母 |
|---|---|---|
| M_return | 站点累计 duty 的最大值；**与作者 Check.calculateLatestTime 同一数学定义**（PAPER_EQUATION_COMPARISON.md §C.4 判定） | 每 (map, method, budget) 一个标量 |
| cost | 完整成本（fixed ＋ 0.5·operating），由 scorer.validate_candidate 独立重算 | 同上 |
| admissible | 完整解 ＋ 覆盖/能量/duty/机数 ＋ cost ≤ C_Liu·(1+eps) ＋ 1e-7，eps=0 | 布尔，逐图。**单图违规即整方法失格**，不得跨图平均抵消 |
| W/T/L | 逐图比较，abs(Δ) ≤ 1e-9·max(1, abs(base)) 记 tie | 图 |
| 主效应 | I_m = 100·(M_cn(m) − M_method(m)) / M_cn(m)，正 = 更好 | 图；配对 |
| 区间 | 地图级 percentile bootstrap，**B=10000**，按地图有放回重采样，报均值差与均值差% | 图 |
| p 值 | 配对符号翻转置换检验（双侧；n≤12 精确枚举 2^n，n>12 用 100,000 次 Monte Carlo，seed 冻结） | 图 |
| 多重比较 | **Holm** 步降；族 = 同一次提交中所有声明的主门槛检验（默认每方法 × 每预算一个检验） | 族 |
| 参照线 | R1 = 5.0%（历史目标）；R2 = **12.9189%**（成本中性基线对锚点的实测均值） | 描述性，不是门槛 |

---

## 7. 门槛（在看任何新结果前写死）

### 7.1 主门槛（唯一可宣称“方法有效”的门槛）

对任一方法 X（含将来的 RL／强 non-RL），在 P1 的 11 张合格图上：

1. 逐图配对改善均值 mean(I_m) > 0，且
2. 地图级 bootstrap **95% CI 下界 > 0**（等价于 Δ 的 CI 上界 < 0），且
3. 该比较在 Holm 族内 p_adj < 0.05，且
4. 通过 §7.2 的 S3/S4（可靠性与合格性）。

**“优于作者锚点”不构成达标。** 锚点只是一个不做 slot 均衡的成本最优解；打赢它已被一个 1 ms、零学习、零路线改变的 LPT 拿到（10/11 图与精确最优同值）。因此任何“我们比锚点改善 X%”的表述只能作为描述性背景。

### 7.2 次要门槛（全部同时报告，缺一不得宣称通过）

| ID | 门槛 | 说明 |
|---|---|---|
| S1 | 对锚点改善均值 > 0 且 CI 下界 > 0 | 平凡；仅用于对齐历史表述 |
| S2 | 对 lpt_6s 改善均值 > 0 且 CI 下界 > 0 | 1 ms 零学习基线也必须打赢 |
| S3 | 可靠性：注册单元中 ONTIME_VALID 比例 ≥ 90%，且大图（8x80/9x95/10x110）不得全灭 | joint_minmax 当前 15/22 = 68.2%，**已不满足** |
| S4 | 合格性：admissible 100%，cap 违规 0 次 | 任一违规即失格 |
| S5 | 完整解：每图每单元都须有可独立重放的完整解与 witness | 缺解按 §8 计 |

### 7.3 明确禁止（写死，违反即作废）

1. 每图取 6 s／12 s 的较好者再比较（best-of-budget 择优）；
2. 每图挑不同方法，或只报“顺眼对手”；
3. 从分母剔除超时/不可行/NULL 单元后算均值；
4. 用跨图平均掩盖单图 cap 违规；
5. 看到 P1 结果后改方法再回 P1 主张（P1 只允许已冻结的 5 个身份）；
6. 把 strong_minmax_alns（在看到 P1 结果后才开发）拿到 P1 作主比较。

### 7.4 参照线（描述性，不设门槛）

- R1 = 5.0%：历史“A 方向目标”。**已被平凡基线越过**（成本中性重排 12.9189%，7/11 图 ≥5%）。
- R2 = 12.9189%：成本中性基线自身对锚点的均值（中位 17.0592%，CI [−18.788, −6.696]，7 胜/4 平/0 负）。方法相对**锚点**的改善若 ≈12.9%，说明它只是重复了这个平凡操作。

---

## 8. 失败／超时／不可行／NULL 的计分与分母（不得剔除）

**主分析 = ITT（intent-to-treat）**：每个已注册单元 (map, method, budget) 都必须出现在分母里。

| 情形 | 计分（主分析） | 敏感性分析 |
|---|---|---|
| NO_ONTIME_VALID_OUTPUT（6/12 s 内无有效输出） | 该单元 M_return := 锚点值（即“什么都没做”），于是 I_m ≤ 0；并按 S3 计入失败率 | 仅 ONTIME_VALID 单元（available-case），必须同表报告 |
| 不可行（infeasible／违反 cap／能量或 duty 失败） | 同上，且按 S4 **整方法失格**（不进主门槛判定） | 同上 |
| NaN／崩溃／无完整解 | 同上；同时记 exit != 0 与收据路径 | 同上 |
| 锚点不合格的图（4x20_o1） | **不进人口**（分母 11/12），且该判定早于任何方法结果（§2.2） | 不适用 |
| 方法整体未交付 | 不产生单元；不得在矩阵里写成“失败”或“更好” | — |

**符号与方向约定**（防止把改善写成退化）：I_m > 0 = 方法更好（M_return 更低）。所有表格同时给 mean(I) 与 mean(Δ)，且 Δ = −I·M_cn/100。

当前已发生的失败（保留，不重跑）：7 个 joint_minmax 超时单元（10x110 6/12 s、7x65 6 s、8x80 6/12 s、9x95 6/12 s）、4x20_o1 锚点不合格、非 RL 首跑模块别名失败、04_exact_reassign 首版缺 instance_sha256 全判 inadmissible（§12-D2）。

---

## 9. 数据可见性（冻结）

### 9.1 P1 = G3 开发集（已看）
ordinal 1、12 图，**本文件的全部数值都来自它**。用途：定义地板、定义门槛、产生待确认效应。**不得**再作为任何方法的“确认”人口。

### 9.2 P2 = 确认集（已登记；本文件未读其数值）
- g3_confirm/PREREG_CONFIRM.json（sha256 2fe9460a…，registered 08:06:55Z）：同 namespace、partition opportunity、ordinal **2/3/4**、12 family、**36 图**；主估计量 = exact_cost_neutral vs 锚点的 M_return 配对变化 ＋ 地图级 bootstrap CI；裁决规则 = 同号且 95% CI 排除 0 才算复制。
- 该预注册由并行线程完成，锚点批于 08:07–08:10Z 运行。**本 PREREG 刻意未读取 g3_confirm/AUTHOR_RESULTS.json 与 NONRL_RESULTS.json 的任何数值**，以保留 P2 的确认性。
- 本文件对 P2 只做两件事：确认其口径与 §6/§8 一致；声明 strong_minmax_alns 与任何新方法**只能**在 P2/P3 作主比较。

### 9.3 P3 = Formal（未生成，另冻）
必须：新 namespace（≠ takeover-20261112-g3-v1）、新 partition 名、family ≥3 且配额冻结、全新 day 区间（不与 R5 所列任何旧区间重叠）、独立天气/预报内容哈希（≠ 25916a05…）、方法/源码/二进制/训练 seed/阈值全部先冻结并写 hash，**然后**才生成图。已看过的 P1/P2 图**永久禁止**进入 Formal。

### 9.4 方法可见性
strong_minmax_alns、任何 RL 变体、任何在看到 P1 结果后写出的代码，都属“已见 P1”的方法：只能用 P2/P3 作主比较；在 P1 上只允许作描述性附注，且必须标注“非盲”。

---

## 10. 统计实现（冻结到可复算）

- bootstrap：random.Random(20261112)，对地图下标有放回抽 n 次取均值，B=10000；CI = 排序后 means[250] 与 means[9749]（percentile，双尾各 2.5%）。实现见 prereg_20261112/compute_stats_server.py（sha256 eef73b62…）。
- 单位：**地图**。事件日、求解 seed、训练 seed 一律嵌套在图内，禁止展开成独立 n。
- 置换检验：符号翻转（±1 均匀），统计量 = 配对差均值；双侧 p = P(abs(T*) ≥ abs(T))；n≤12 精确枚举 2^n，n>12 用 100,000 次 MC（seed 同 20261112）。
- Holm：族内按 p 升序，p_adj_(i) = max over j≤i of min(1, (k−j+1)·p_(j))。
- 容差：tie 判定 1e-9·max(1, abs(base))；成本 cap 1e-7 绝对值。

---

## 11. 与已交付收据的一致性核对（声称 vs 实测）

| # | 已交付说法 | 本次实测 | 处置 |
|---|---|---|---|
| K1 | RUN_LOG.md：作者 12 次总 wall **45.9 s** | AUTHOR_RESULTS.json 12 行求和 **46.294 s**（1.401–8.716） | 采用 46.294（行级可复算）；45.9 属舍入/口径差，不改历史文件 |
| K2 | G3_DEV_REPORT.md：成本中性重排“成本逐位不变” | 9/11 图 Δcost 恰 0；10x110_o1 −2.27e-13、4x30_o1 −5.68e-14（相对 ≤2.3e-16） | 表述收紧为“逐位不变，或 ≤1 ulp（求和顺序）”；cap 仍恒满足 |
| K3 | 本地 stats/STATS_self.json | 服务器复算点估计逐位相同，4 个 CI 端点差 1–2 ulp | 两版并存、均登记哈希；判定不变 |
| K4 | RUN_LOG.md：非 RL “**8 超时**” | 34 行 = 26 ONTIME_VALID ＋ **7** NO_ONTIME_VALID_OUTPUT ＋ 1 ANCHOR_NOT_ELIGIBLE | 采用 7 超时 ＋ 1 无锚点（行级可核）；8 疑似把 4x20_o1 计入 |
| K5 | “11 图平均降 12.92%” | 12.9189%（中位 17.0592%，7/4/0，CI [−18.788, −6.696]） | 一致 |
| K6 | “LPT 10/11 与精确最优同值，6x50_o1 差 1.35 个点” | 10/11 相对差 ≤2.2e-14；6x50_o1 142.4598 vs 140.5435 = **1.3635%** | 一致（“1.35 个点”实为 1.36%） |
| K7 | “joint_minmax 只在 6x50_o1 再降 4.2%” | 6x50_o1 −4.2085%；7x65_o1 12 s 再降 −0.5838%；其余有效单元为 0 或超时 | 更精确：**2 图**有额外下降，6x50_o1 最大 |
| K8 | 12 图双哈希 | raw 12/12、canonical 12/12 复算一致 | 一致 |

---

## 12. 已知证据弱点与偏离（不隐藏）

- **D1（进程偏离，已补救）**：stats/STATS_self.json 首次在 Mac 生成（B=10000）。已按“科研计算不得在 Mac”的要求在 <COMPUTE_HOST> 复算（prereg_20261112/compute_stats_server.py），结果见 §11-K3；此后所有统计一律在服务器。
- **D2（不可变收据缺口）**：04_exact_reassign.py 首版（缺 instance_sha256，全判 inadmissible）与 03_run_nonrl.py 首跑（模块别名导致 CostAnchor 类不一致）**没有留下独立失败收据**——输出被修正版覆盖，仅 RUN_LOG.md 有文字记录。这是本包唯一无法用字节复核的失败；后续脚本必须先写失败行再写成功行。
- **D3（样本量）**：n=11，其中 4 图成本中性类 headroom 恰为 0（3x20、4x25、7x65、9x95）。因此在“打赢地板”这个门槛上，实际只有 7 张图可能提供正效应；功效有限，这正是 P2（36 图）存在的理由。
- **D4（锚点单次运行）**：每图 1 次、seed 由输入哈希派生（未按成本选 seed），无锚点内方差估计；锚点方差不是本文推断对象。
- **D5（joint_minmax 非最强）**：15/22 有效、7 超时，且只在 2 图超出地板 ⇒ 它**不构成**大图强基线，只能当“路线级下降不给力”的存在性证据。
- **D6（270 的适用边界）**：270 是 Java 官方源在当前参数（T0=1000、α=0.95、finalTemp=1e-3）下的确定性截断，不是“作者实际跑了 270 次”的历史声明。

---

## 13. 变更控制

1. 本文件一旦落盘即为冻结字节；任何修改必须新建 PREREG_v2.md 并写明差异与理由，**不得就地编辑**。
2. 新增方法必须先在其外登记 METHOD_REGISTRATION（代码 sha256、版本、预算、失败关闭条件），再在 P2/P3 作主比较。
3. 门槛（§7）在任何新结果产生前不得放宽；只能新增更严的门槛。
4. 与并行线程产物（g3_confirm/*、logs/strong_nonrl/*）冲突时，以各自的事前登记文件为准；本文件不追溯改写它们。

---

## 14. 四态结论（本文件的直接出口）

**14.1 已证实事实（本包实测，路径＋分母）**
1. P1 12 图双哈希 24/24 与 population_index.json 一致；对 12,131 条排除表零碰撞（g3_pop/population_index.json；prereg_20261112/ 复算输出）。
2. 成本中性精确重排在 11 图上平均降 M_return **12.9189%**（中位 17.0592%，7/4/0，CI [−18.788, −6.696]；stats/STATS_self.json，B=10000，seed 20261112）。
3. 1 ms LPT 在 **10/11** 图与精确最优同值；唯一差距 6x50_o1 为 **1.3635%**（NONRL_RESULTS.json vs EXACT_REASSIGN_RESULTS.json）。
4. 路线级 joint_minmax 只在 2/8 有效图超出地板（6x50 −4.2085%、7x65 12 s −0.5838%），且 7/22 单元超时（NONRL_RESULTS.json）。
5. 独立重放 04_exact_reassign.py 在 0.102 s 内产出**字节相同**的结果文件（sha256 7737e186…）。

**14.2 未证实假说（不得当结论）**
1. “RL 能打赢地板”——未训练、未执行（G0 NO-GO）。
2. “大图上存在可稳定获得的出类 headroom”——仅 1 图（6x50）有 4.2%，其余大图 joint_minmax 全超时；strong_minmax_alns 未交付。
3. “锚点方差／求解 seed 波动不影响结论”——未做锚点多 seed。
4. “P1 效应能在 P2 复制”——P2 数值本文件未读，未检验。

**14.3 失败或关闭**
- 4x20_o1 锚点不合格（记录端 slot 归属互换）：关闭，不补图。
- joint_minmax 在 8x80/9x95/10x110 的 6 s 与 12 s 全超时：该实现不作大图强基线。
- 03_run_nonrl.py 首跑、04_exact_reassign.py 首版：失败保留（无字节收据，见 D2），不重跑找阳性。

**14.4 下一项有界工作（有产物、有停止条件）**
1. **B1（≤1 核小时）**：strong_minmax_alns 冻结代码后，仅在 **P2 的 36 图**跑 6 s/12 s，对 exact_cost_neutral 做 §7.1 检验；若 S3 不达 90% 或 CI 含 0，关闭该实现，不进 G4。
2. **B2（<0.1 核小时）**：P2 的 exact_cost_neutral 与 LPT 按本文件 §6/§8 口径分析，检验 P1 的 12.92% 是否复制（P2 已有自己的 prereg，本项只复用口径，不改其裁决规则）。
3. **B3（0 计算）**：把 §11 的 4 条口径差（K1/K2/K4/K7）写进新的 RUN_LOG 勘误附录，不改历史字节。
4. **B4（0 计算）**：为 Formal 起草独立 prereg（新 namespace/day/weather ＋ 方法冻结清单 ＋ 60 核小时预算拆分）；G0/G3 未过前**不生成任何 Formal 图**。
---

## 15. 附：EXPERIMENT_MATRIX.csv 的列与状态字（机器可读补充）

- 列：exp_id, hypothesis, population, methods, train_seeds, weather_mode, budget, metrics, expected_runs, depends_on_gate, hard_cap, artifacts, stop_condition, **status**（前 13 列为规定列，第 14 列 status 为本文件新增，用于满足“每行标明已执行／未执行／被 G0 阻塞”的要求）。
- status 取值（四态，互斥）：
  - EXECUTED：已有真实收据与结果行（7 行：D-ENV-01/02、D-OPP-01/02/03、D-COST-01/02）；
  - IN_FLIGHT：已登记、已开跑但本文件不消费其结果（1 行：D-GEN-01，对应 g3_confirm 的 36 图）；
  - NOT_EXECUTED：有计划、无真实执行（6 行）；
  - BLOCKED_G0：依赖 G0（或 G0＋G3）通过才允许启动，当前一律不得开跑（5 行）。
- 覆盖：§11 阶段 D 的 8 个实验族全部有行——ENV 3、OPP 5、TRN 1、RLI 1、CMP 1、ABL 2、GEN 3、COST 3，共 19 行。
- 与 PREREG 的关系：矩阵只登记“要回答什么、分母多少、硬限多少、何时停”；门槛与统计口径以本文件 §6–§8 为准，两者冲突时以 PREREG 为准。
