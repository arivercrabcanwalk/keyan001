# SPLITS_AND_EXCLUSIONS — 已暴露人口与新人口可用性规则

生成：2026-11-12 16:01 CST ｜ 机器可读版：`joint_weather_emergency/20261112_takeover_completion/SPLITS_AND_EXCLUSIONS.json`
本文件只做**汇总与判定**，不重跑任何求解/训练；所有数字均来自实际打开的 manifest、STATE、生成记录与结果行。

---

## 0. 一句话结论

旧账本里的「40 新身份」在**地图层面**确实是 40 张互不相同的几何（40 个唯一 `canonical_geometry_sha256`、40 个唯一 `raw_sha256`），
但在**人口层面**它们全部来自同一个生成器版本（`2.0.0-engineering`）、同一个 family（`[3,20]`）、同一个 14000 m 方、同一套天气内容。
所以：**40 张新图 ≠ 40 个独立人口；只换 seed/namespace 后缀得到的是同一人口的更多抽样。**
120 官方 Liu 图已被 1200 次配对运行全部暴露，**不能**再充当「新 Formal」。

| 人口 | 图数 | 是否已全部暴露 | 可否用于新选模 |
|---|---:|---|---|
| 官方 Liu Instances_Alg | 120 | 是（1200 次配对运行） | **否** |
| g24 新身份（40 图小计） | 40 | 是（40 作者尝试 / 126 比较） | **否** |
| ├ opportunity 侧 | 16 | 是 | 否 |
| └ calibration/validation 侧 | 24 | 是（额度 24/24 满） | 否 |
| GitHub 发布实例 | 620 | 是（逐文件哈希） | 否 |
| 旧 Stage A | 96 | 是（720 任务） | 否 |
| joint 20261105 / deep_revision | 32 / 44 | 是 | 否 |
| method_family_B / sufficient_training_D | 44 / 64 | 是（D 为不完整终局） | 否 |
| WX-E 各 pilot / WX-C v3 | 12 包 | 是（全部 CLOSE_*） | 否 |

**可用于新选模的旧地图数 = 0。**

---

## 1. 证据纪律

- 每条断言都带路径；行号用 `:NN` 写在路径后。
- 三类标注贯穿全文：**【事实】**＝已在文件里读到；**【假说】**＝推断但无逐行证据；**【关闭】**＝已裁决不得重启。
- 与交接文档（`CLAUDE_TAKEOVER_PROMPT.md`）摘要不一致者，以包内同期收据为准，并在 §8 单列。

---

## 2. Q1 — 120 官方 Liu 地图

### 2.1 ID 列表来源文件（权威）

`route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>`

- `schema = exposed_instance_exclusion_manifest_v1`；`records` 长度 **120**；`canonical_geometry_count = 120`；`raw_sha256_count = 120`（三者相等即无重复）。
- 每条记录含 `name`（如 `3_10_1.txt`）、`family`（如 `[3,10]`）、`raw_sha256`、`canonical_geometry_sha256`。
- `source_data_dir = reproduction/reviewer_package_semfix/external/LRPHSD<EXECUTION_PATH>`；上游审计 `g23<EXECUTION_PATH>`。
- 命名规则：`<sites>_<targets>_<1..10>.txt`；12 个 family × 10 = 120。

### 2.2 独立交叉核对（不同文件、不同来源）

`reproduction/reviewer_package_semfix/results/semfix_full_P1/` 下有 120 个 instance 名 × seed 0-4 = 600 行；
逐行 `input_sha256` 与上述 manifest 的 `raw_sha256` **一一相等**（例：`10_110_1` → `88b60a8bf3ebc004754f1bde2d9bad8ddb4e385ee4bd4c74740a8330b5b6d7fa`）。
`SEMFiX_FULL_RESULTS.md` 收据：`COMPLETE profile=P1 maps=120 seeds=5 failures=0`（P2 同）。合计 **1200 次配对运行**。

### 2.3 是否已全部暴露

**【事实】是，120/120 全暴露。** 每张图都跑过 P1+P2 × 5 seed，并归档 600 份压缩完整解 witness；不存在「没跑过」的官方图。

### 2.4 能否作「新 Formal」

**【事实】否。** 四条独立理由：

1. 作者公开 benchmark，完整解与对照行都已被本项目看过，无 held-out 性；
2. 已做 1200 次配对运行与审计，之后任何调参都会污染；
3. 静态图：无风、无 NFZ、无事件日（`SEMFiX_FULL_RESULTS.md` 记录协议为静态 Instances_Alg），不构成 W 合同人口；
4. 交接合同第 303 行本身也写「Liu 官方地图做天气扩展外部 benchmark，不因此变成从未暴露的 Formal 新图」。

**允许的未来用途**：静态外部 benchmark / 回归对照，须另注册为 `EXPOSED_BENCHMARK`，不得计入 Formal 分母。

---

## 3. Q2 — 旧 40 新身份的 40 个 ID 与 126 实际比较

### 3.1 40 个 ID 的来源文件（不是交接摘要）

| 角色 | 条数 | manifest 路径 |
|---|---:|---|
| `legacy_initial_six` | 6 | `g24_weather_nfz/linux_migration_20261104/<REMOVED_ENDPOINT>_bc_v3_execution_20261104/output/MATERIALIZATION.json` |
| `calibration_four` | 4 | `g24_weather_nfz/calibration_four_execution_20261104/EXPOSURE_EXCLUSIONS.json` |
| `ordinary_p2_eight` | 8 | `g24_weather_nfz/ordinary_pilot_execution_20261104/independent_audit/PILOT_EXPOSURE_EXCLUSIONS.json` |
| `p3_fixed14` | 14 | `g24_weather_nfz/P3_fixed14_execution_20261104/independent_audit/PILOT_EXPOSURE_EXCLUSIONS.json` |
| `g3_first_batch` | 4 | `g24_weather_nfz/g3_nonrl_calibration_20261105/server_original/output/MATERIALIZATION.json` |
| `g3_nonrl_validation` | 4 | `g24_weather_nfz/g3_nonrl_validation_20261105/server_original/output/MATERIALIZATION.json` |

汇总件：`g24_weather_nfz/status_reconciliation_g3_20261105/EXPOSURE_EXCLUSIONS_40.json`（`record_count=40`、`canonical_geometry_sha256_unique=40`、`raw_sha256_unique=40`、`eligible_for_research=false`）。
注意其 `sources` 数组只列 5 组共 36 条，与实际 40 条不符（见 §8 C1）；**采用 `records` 数组**。

### 3.2 40 图明细（逐图可核）

生成器统一为 `2.0.0-engineering`，RNG `SplitMix64 2015-02-16-reference-variant-v1`，
seed 由 `first8bytes(SHA256(canonical_json{schema,namespace,family,partition,ordinal,stream}))` 导出（`g23<EXECUTION_PATH>`）。
40 图 **family 全为 `[3,20]`、方边 14000 m**；天气内容去 `instance_sha256` 后哈希统一为 `25916a056f7f910751b623c54bddf1d5565376a661f1867a4f2291a4b7570d3f`（仅 1 个天气条件）。

| # | map_id | 包 | split/partition | coord seed(u64) | author seed | geometry(16) | 锚点 | 质量比较 | 可新选模 |
|---|---|---|---:|---|---|---|---|---|
| 1 | `calibration_1` | legacy6 | CALIBRATION | 16848264560810711812 | 8061040517756394818 | `8a338e764f9526c7` | **failed** | 0 | 否 |
| 2 | `opportunity_1` | legacy6 | TRAIN/opportunity | 3510608308860296805 | 4725616345236868539 | `2eb7aa002e8c758e` | **failed** | 0 | 否 |
| 3 | `opportunity_2` | legacy6 | TRAIN/opportunity | 11326821000534890435 | 5589274143055571466 | `3090355d2320f61c` | eligible | unknown | 否 |
| 4 | `opportunity_3` | legacy6 | TRAIN/opportunity | 7424519560581483456 | 7448771392250967152 | `03e112076adff430` | **failed** | 0 | 否 |
| 5 | `opportunity_4` | legacy6 | TRAIN/opportunity | 315944167743769220 | 8176171210666833424 | `c1fed2c363badf70` | eligible | unknown | 否 |
| 6 | `validation_1` | legacy6 | VALIDATION | 7287840944253383520 | 6552377845290530962 | `0b83230f16b710f4` | eligible | unknown | 否 |
| 7 | `calibration_1` | cal4 | CALIBRATION | 9696769517328402219 | 5416193097313746951 | `eea4ad8cf13d3ec6` | eligible | 4 | 否 |
| 8 | `calibration_2` | cal4 | CALIBRATION | 3199714144076287646 | 7050745614158280690 | `c37099bfb6ca9775` | eligible | 4 | 否 |
| 9 | `calibration_3` | cal4 | CALIBRATION | 1920062422051144663 | 3882061849787976752 | `5bbce7dfab635f39` | eligible | 4 | 否 |
| 10 | `calibration_4` | cal4 | CALIBRATION | 4623427792268789899 | 6883377457131737141 | `175ef26852838279` | eligible | 4 | 否 |
| 11 | `TRAIN_1` | P2 | TRAIN/opportunity | 10315716839356301853 | 9037025135220550923 | `b46b8c04d465b7b5` | eligible | 0 | 否 |
| 12 | `TRAIN_2` | P2 | TRAIN/opportunity | 11212163679001289909 | 3243719861758967425 | `9b523d535621cf8e` | eligible | 0 | 否 |
| 13 | `TRAIN_3` | P2 | TRAIN/opportunity | 16536284684707784461 | — | `9179e8427cc9a540` | **failed** | 0 | 否 |
| 14 | `TRAIN_4` | P2 | TRAIN/opportunity | 10377320674945614890 | 3208087635824869580 | `65ede185ee413dbd` | eligible | 0 | 否 |
| 15 | `TRAIN_5` | P2 | TRAIN/opportunity | 1772161236358993587 | 5867136966166737283 | `811a491a6eec19b6` | eligible | 0 | 否 |
| 16 | `TRAIN_6` | P2 | TRAIN/opportunity | 2007274681249996974 | 8709423513222594460 | `9f4bdc44037df5f8` | eligible | 0 | 否 |
| 17 | `VAL_1` | P2 | VALIDATION | 4964940896226951351 | — | `ef02e2ae2987bb90` | **failed** | 0 | 否 |
| 18 | `VAL_2` | P2 | VALIDATION | 10046345032524705986 | — | `4e001af44bf621ad` | **failed** | 0 | 否 |
| 19 | `TRAIN_1` | P3 | TRAIN/opportunity | 14300510430257703506 | 6533227921728707381 | `49d8896056997215` | eligible | 0 | 否 |
| 20 | `TRAIN_2` | P3 | TRAIN/opportunity | 11803540824159096411 | — | `fac4a012ebe8828e` | **failed** | 0 | 否 |
| 21 | `TRAIN_3` | P3 | TRAIN/opportunity | 15095910801075510818 | 8214224796288978561 | `9cd8282dcd90a2aa` | eligible | 0 | 否 |
| 22 | `TRAIN_4` | P3 | TRAIN/opportunity | 1408316617229734659 | 8862752592133022981 | `2fea1ab7037f4e03` | eligible | 0 | 否 |
| 23 | `TRAIN_5` | P3 | TRAIN/opportunity | 6480175311113180951 | 3160886542338391251 | `bcd9c016924dbc58` | eligible | 0 | 否 |
| 24 | `TRAIN_6` | P3 | TRAIN/opportunity | 3449552447603342600 | 5721582391779123333 | `cbd5c9593b494282` | eligible | 0 | 否 |
| 25 | `VAL_1` | P3 | VALIDATION | 5560278581663723372 | 6545600431564083803 | `38ce9e07326de9e5` | eligible | 0 | 否 |
| 26 | `VAL_2` | P3 | VALIDATION | 10301972090181610039 | 5339759396693625412 | `dc6929bebc541cc8` | eligible | 0 | 否 |
| 27 | `VAL_3` | P3 | VALIDATION | 13196992175538331492 | 8103504990021122424 | `815d4f3818e62e7b` | eligible | 0 | 否 |
| 28 | `VAL_4` | P3 | VALIDATION | 5276681482089107995 | — | `1270c818775e155c` | **failed** | 0 | 否 |
| 29 | `VAL_5` | P3 | VALIDATION | 9216523893445883930 | 8921428058653875013 | `e189ee72af9f9d21` | eligible | 0 | 否 |
| 30 | `VAL_6` | P3 | VALIDATION | 18229936926937999770 | 8360826105648211745 | `e54a10c9b88c9c55` | eligible | 0 | 否 |
| 31 | `VAL_7` | P3 | VALIDATION | 16994972859832178032 | 1933609355281524465 | `921f84f90c39257c` | eligible | 0 | 否 |
| 32 | `VAL_8` | P3 | VALIDATION | 16124584929509702145 | 3836538395111743981 | `4a1ce4cc15fc82f4` | eligible | 0 | 否 |
| 33 | `calibration_1` | G3-1 | CALIBRATION | 10568376817971081221 | 2681003412216673716 | `dda615cad76ff175` | eligible | 10 | 否 |
| 34 | `calibration_2` | G3-1 | CALIBRATION | 16446809033092008304 | 4429980145609240498 | `249c177ee3fa7f61` | eligible | 10 | 否 |
| 35 | `calibration_3` | G3-1 | CALIBRATION | 11268862518202512688 | 5014745257682700171 | `aefa9affc249adba` | eligible | 10 | 否 |
| 36 | `calibration_4` | G3-1 | CALIBRATION | 13851859804781534736 | 4413690447069893544 | `aa8aebe916a1c597` | eligible | 10 | 否 |
| 37 | `calibration_5` | G3-2 | CALIBRATION | 10345901150499424863 | — | `c6b5f17ef1c1ec60` | **failed** | 5 | 否 |
| 38 | `calibration_6` | G3-2 | CALIBRATION | 14808566417892199153 | 6250957459381661906 | `348e4c704cc72e08` | eligible | 5 | 否 |
| 39 | `calibration_7` | G3-2 | CALIBRATION | 18136731138408547509 | 1875744519872662205 | `1bbdeab710d5a540` | eligible | 5 | 否 |
| 40 | `calibration_8` | G3-2 | CALIBRATION | 2384259282910847564 | — | `b21434f29bfb99af` | **failed** | 5 | 否 |

（完整哈希、namespace、`exclusion_source_role` 见 JSON 的 `identity_ledger_40`。）

- **16 opportunity** ＝ legacy 4 + P2 TRAIN 6 + P3 TRAIN 6。
- **24 calibration/validation** ＝ legacy 2 + calibration_four 4 + P2 VAL 2 + P3 VAL 8 + G3 8。
- 独立复算：全库 65 个 `generation.json` → 40 唯一 geometry、40 唯一 raw；partition 计数 `{calibration:13, validation:11, opportunity:16}`。
- **10 张锚点失败**（opportunity_1/3、legacy calibration_1、P2 TRAIN_3/VAL_1/VAL_2、P3 TRAIN_2/VAL_4、G3 calibration_5/8），与 `STATE.json#research_counts.total_unusable_anchors = 10` 相符；失败不退额度、不补图。

### 3.3 126 实际比较如何计

**【事实】** 唯一给出分族口径的是
`g24_weather_nfz/status_reconciliation_g3_20261105/ROUND_DECISION.md:17-18`：

```
研究累计：40 唯一新身份 = 16 opportunity + 24 calibration/validation；40 作者尝试；126 实际比较 = 旧 66 + 新 60。
比较族累计：36 RL、6 BC-only、84 非 RL；非 RL 含旧 24 + 新 60（导入失败也是真实调用）。
```

- 校验：36 + 6 + 84 = **126**；84 = 24 + **60**（新 G3）；旧 66 = 126 − 60。
- 新 60 逐包可核：第一批 40 次启动（27 交付 / 5 超时 / 8 导入失败）+ 第二批 20 次启动 = 60（`ROUND_DECISION.md:8,10`）。
- 旧 24 非RL：本地能逐行核对的只有 calibration_four 的 **16** 条已交付行（`calibration_four_execution_20261104/output/COMPARISONS.json`，4 图 × strict/annealed × 6s/12s）。
- P2 与 P3 的 VAL 调用均为 **0**（`STATE.json#ordinary_rl_attribution_pilot.new_validation_calls=0`、`#P3_fixed_population.actual_VAL_calls=0`）。
- 因此 16 + 60 + 36 + 6 = 118，**剩余 8 条旧非RL 行没有本地逐行键**：【假说】落在 weather v2/v3 的 opportunity_2 / opportunity_4 / validation_1 上，但无文件级证据（见 §9 G1）。

**三个分母不能合并**：40 = 唯一地图身份；40 = 作者尝试（1 图 1 次，上限 48）；126 = 方法×图的比较调用。三者口径不同。

---

## 4. Q3 — 24 校准验证的具体身份与「额度已满」依据

### 4.1 24 个身份（逐条，按包）

| # | 身份 | 包 | 锚点 | author_seed |
|---|---|---|---|---:|
| 1 | `calibration_1` | legacy6 | failed | 8061040517756394818 |
| 2 | `validation_1` | legacy6 | eligible | 6552377845290530962 |
| 3-6 | `calibration_1..4` | calibration_four slot1..4 | 全 eligible | 5416193097313746951 / 7050745614158280690 / 3882061849787976752 / 6883377457131737141 |
| 7-8 | `VAL_1..2` | P2 | 全 failed | — |
| 9-16 | `VAL_1..8` | P3 | 6 eligible + VAL_4 failed | 6545600431564083803 / 5339759396693625412 / 8103504990021122424 / — / 8921428058653875013 / 8360826105648211745 / 1933609355281524465 / 3836538395111743981 |
| 17-20 | `calibration_1..4` | G3 第一批 slot1..4 | 全 eligible | 2681003412216673716 / 4429980145609240498 / 5014745257682700171 / 4413690447069893544 |
| 21-24 | `calibration_5..8` | G3 第二批 slot1..4 | 6/7 eligible；5/8 failed | — / 6250957459381661906 / 1875744519872662205 / — |

派生规则（可复算）：40 图中 `partition ∈ {calibration, validation}` 的全部 = 2 + 4 + 2 + 8 + 8 = **24**；
`partition = opportunity` 的全部 = 4 + 6 + 6 = **16**。

### 4.2 「额度已满」的依据

1. `route_rl_research/20261103/return_makespan/STATE.json#resource_envelope`：
   `separate_nonRL_calibration_validation_maps_max = 24`、`separate_calibration_validation_identities_used = 24`、`calibration_validation_remaining = 0`。
2. `.../status_reconciliation_g3_20261105/ROUND_DECISION.md:19`：
   「24/24 calibration/validation 额度已用满；**不得将剩余 opportunity 额度改名挪用或失败额度退款**」。
3. 同一文件 `:21`：「48 作者尝试上限已用 40；仅有 8 次未分配作者额度，并不等于自动获准新校准」。
4. 退款禁令有字段支撑：`failed_reservations_refunded = false`、`quota_reallocation_authorized = false`。
5. 第二批 2/4 天气锚点不合格、第一批 strict「临时胜者」资格被撤回，均**不产生额度退回**（`ROUND_DECISION.md:10,13,19`）。

**作者尝试额度**：cap 48 / used 40 / remaining 8（`resource_envelope.author_attempt_cap|used|remaining`），同样不可退、不自动授权新校准。

---

## 5. Q4 — 各 WX pilot 的 TRAIN/EVAL 身份区间与 clustered/uniform 生成方式

### 5.1 区间（逐包，来自各自 driver 源码）

| 包 | TRAIN seed 区间 | EVAL seed 区间 | 评价行 | 终局 |
|---|---|---|---:|---|
| `20261112_wx_e`（toy，作废） | — | 100-103 | — | `INVALIDATED_ENGINEERING_ONLY` |
| `20261112_wx_e`（real pilot） | — | 0-3 | 64 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_real`（v2） | 200-203 | 300-307 | 128 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_forecast_v1` | 1200-1211 | 1100-1115 | 256 | `PILOT_CLOSED_NEGATIVE` |
| `20261112_wx_e_v3` | 100-111 | 300-315 | 256 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_v4` | 500-511 | 400-415 | 256 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_v5` | 700-711 | 600-615 | 256 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_v6` | **700-711** | **600-615** | 256 | `CLOSE_NO_FULL_RUN`（**与 v5 同场景**） |
| `20261112_wx_e_v7` | 1000-1011 | 900-915 | 256 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_v8` | 1200-1211 | 1100-1115 | 256 | `CLOSE_NO_FULL_RUN` |
| `20261112_wx_e_risk_v1` | **2000-2063** | **3100-3131** | 512 | `PILOT_CLOSED_NEGATIVE` |
| `20261112_wx_c_spatial_diag_v3` | — | clustered **4200-4231** / uniform **5200-5231** | 320 + 320 | `CLOSE_WX_C_CANDIDATE` |

证据：`wx_e_risk_driver.py:484-489`（2000-2063 / 3100-3131）、`wx_e_forecast_driver.py:474-475`、`wx_e_v3_driver.py:424-425`、`wx_e_v4_driver.py:426-427`、`wx_e_v5/v6_driver.py:426-427`、`wx_e_v7_driver.py:443-444`、`wx_e_v8_driver.py:444-445`、`wx_e_real_driver.py:342-344`、`wx_e_driver.py:44`（toy 100-103）、`wx_c_spatial_diag.py:315`。

### 5.2 clustered / uniform 的生成方式（以 risk_v1 为例，其它包同构）

`wx_e_risk_driver.py:83-141`：

- **底图固定**：单站 `Station(0,0,0)`；8 个 routine 任务坐标**写死在代码里**（`2200,900` … `6300,1300`），所有 seed 相同。
- **只有 emergency 任务随 seed 变**：16 个紧急任务，`burst = rng.choice((70,150,230))`，release 逐 5 s 抖动；
  - `clustered`：沿公开预报方向放置，中心距 = `{70:3400, 150:4700, 230:6000}` m，±450 纵向 / ±650 横向；
  - `uniform`：极坐标 `radius∈[2800,6500]`、`theta∈[-π,π]` 均匀撒点；
- **分割隔离**：`rng = random.Random(918271 + seed*53 + (1 if clustered else 2) + (0 if train else 1000000))`
  → clustered/uniform 用不同偏移（1/2），train/eval 用 1,000,000 偏移。
- **预报可信度**：`confidence = 0.92 if clustered else 0.55`，仅改公开预报向量长度。
- 其它包差异：v3/v4/v5/v6/v7/v8 共用 RNG 基址 `71011 + seed*37 + (1|2) + (0|100000)`（`sed -n '71,74p'` 逐包核对），只有 seed 区间和场景常数不同；forecast_v1 用 `93117 + seed*53` 且坐标流另开 `coord_rng`（`+7919/+15437`）。

**结论【事实】**：12 个 WX 包共用同一张底图（单站 + 固定 routine 任务），seed 只改变 emergency 任务几何与风轨；
clustered/uniform 是同一底图上的两种**放置律**，不是两张地图。因此 WX 包之间的「新身份」全部是同一设计人口的新抽样。

---

## 6. Q5 — 其它已暴露人口（同样不可用于新选模）

| 人口 | 图数 | 关键身份 | 暴露 | 证据 |
|---|---:|---|---|---|
| `joint_weather_emergency/20261105` | 32 | TRAIN `w5_35_0 … w8_80_23`；DEV `d5_35_1..4` + `d6_50_1..4`；日 550100-550103 | 32 作者 + 288 控制 + 384 模型 = 672 回放 | `.../server_snapshot<EXECUTION_PATH>` |
| `20261105_deep_revision` | 44 | TRAIN `w*` ordinal 24-55；VAL `d7_65_1..4`；DEV `d8_80_1..4`+`d10_110_1..4`；日 880000/881000-881001/882000-882003 | 9 训练 run、768 步、1184 评价 | `...<EXECUTION_PATH>` |
| `20261106_method_family_B` | 44 | 24 TRAIN + 8 VAL + 12 SELECT（`select0..11`）；日 970000/971100-971101/972100-972103 | 8256 意向（8112 DONE / 144 TIMEOUT） | `.../REGISTRATION_PLAN.json`、`results/EVALUATIONS.jsonl` |
| `20261106_sufficient_training_D` | 64 | 32 TRAIN + 8 VAL + 24 SELECT；日 991000/994100-994103/995100-995103 | 12/30 流完成审计；2880 VAL + 26880 SELECT **无 intent**；12.046 GB 超限 -9 | `.../DESIGN.json`、`20261106_server_recovery/D_TERMINAL_RECONCILIATION/RESULT.json` |
| GitHub 发布实例 | 620 | 600 `w*` + 20 `d*`；与官方 120 图 raw 哈希**交集 0** | 逐文件 sha256+git sha1 | `audit/20261104_github_execution/server_evidence/INSTANCE_PROVENANCE.json` |
| 旧 Stage A | 96 | 72 train（seed 1-6）+ 24 val（seed 7-8） | 720 任务；24 图回放、132 站点 | `stage_a_audit/MODIFIED_FILE.md` |

**禁入登记表**：`12,131` 条（官方 120 + pilot 几何提案 12,000 + v2 合成 4 + Windows 探针 6 + 合成烟测 1），
`calibration_1/generation.json` 的 `metadata.exclusion_record_count = 12131` 与 12120+4+6+1 自洽。
canonical 哈希对**平移、行序、节点 ID、空白不变**（`PROTOCOL.md`），因此「挪一下坐标原点再画一次」会被判重。

---

## 7. Q6 — 新人口可用性规则

### 7.1 必须先定义的三件事

1. **地图身份元组**：`(generator_version, protocol, family=[sites,targets], square_side_m, namespace, partition, ordinal, coordinate_seed_u64, target_id_seed_u64)` → `canonical_geometry_sha256` + `raw_sha256`。
2. **地图级单位**：一张唯一 canonical geometry 且不在 12,131 条排除表内的图。事件日、求解 seed、训练 seed **一律嵌套在图内**，不构成独立图。
3. **天气条件**：`(wind trace, NFZ polygon 集合, 预报发布序列)` 的内容哈希。固定合成风只算 **1** 个天气条件。

### 7.2 十条硬规则（机器可执行）

| ID | 规则 | 依据 |
|---|---|---|
| R1 | 新图先冻结身份元组并算双哈希，登记后才允许求解 | `generator_v2.derive_seed` 可完整复算 |
| R2 | 必须通过 12,131 条排除表的 canonical + raw 双查重 | 40 图即由该表保证不重复 |
| R3 | **只改 seed / 只改 namespace 后缀不算新人口**，只是同人口新抽样 | 40 图 = 6 namespace 下 40 次抽样 |
| R4 | 新人口必须覆盖 **≥3 个 family**，并冻结 family×slot 配额 | 40/40 单 family `[3,20]` 无规模泛化力 |
| R5 | 事件日须由新 day 命名空间产出，禁止与 550100-550103、880000+、881000-881001、882000-882003、970000/971100-971101/972100-972103、991000/994100-994103/995100-995103 重叠 | 旧 day 已被多包共用 |
| R6 | 天气必须独立登记内容哈希；同一 `fixed-global-square-and-wind-v1`（`25916a05…`）只算 1 个条件 | 40 图天气内容完全相同 |
| R7 | **同一底图换日/换求解 seed/换训练 seed 不计独立地图**；统计以图为 n | G5 合同：map 为主要独立单位 |
| R8 | 锚点失败不退款、不补图，失败图保留在册 | `replacement_on_failure=false` × 40 |
| R9 | 跑前必须登记 population_id、图数、day 区间、天气哈希、作者上限、CPU 核时、**输出字节上限** | D 包 12.046 GB 超限 -3 收据 |
| R10 | 已暴露集合永久退出选模（本文件即排除清单） | 120/40/620/96/32/44/44/64/12 包 |

### 7.3 不算独立的五种情形（明确写死）

1. 同一 canonical geometry 换求解 seed 或训练 seed；
2. 同一底图换事件日 id（除非 day 生成器与 seed 命名空间全新，且仍按 map 聚合）；
3. 同一 geometry 换 namespace 后缀（`:slot1/:slot2`）重画；
4. 40 图中不同 map_id 但同 family/同天气——它们是**同人口的独立图**，可作 map 级 n，但不构成新人口；
5. 同一 seed 数字在不同 RNG 基址下重画（forecast_v1 1100-1115 vs v8 1100-1115）——是不同图，但属同一设计人口。

### 7.4 验收清单（缺一不许开跑）

- [ ] 身份元组 + 双哈希已登记且不在排除表
- [ ] population_id 与 40 图人口实质不同（生成器版本 / family 组合 / 约束 / 天气条件至少一项）
- [ ] family 覆盖 ≥3 且配额冻结
- [ ] day id 全新、与所有旧区间不重叠
- [ ] 天气条件哈希已登记且 ≠ `25916a05…`
- [ ] 作者锚点逐一求解；失败保留、不补图、不退额度
- [ ] 资源与输出硬限已登记，含 VAL/SELECT 评价键的 intent 行
- [ ] TRAIN / VAL / DEV / Formal 四级隔离，Formal 冻结前不生成

---

## 8. 冲突清单（10 条）与采用值

| # | 冲突 | 采用值 | 理由 |
|---|---|---|---|
| C1 | `EXPOSURE_EXCLUSIONS_40.json` 的 `sources` 只列 5 组共 **36** 条，`record_count=40` | 采用 `records`（40 条）按其 `source_role` 分 6 组：6/4/8/14/4/4 | records 与 40 唯一双哈希自洽，且与 `research_counts.scope`（6+4+8+14+8）一致 |
| C2 | 「24」有两义：校准额度 24；Stage A 24 图回放 | 本文一律指**校准/验证额度 24**；另一处显式写「Stage A 24 图回放」 | 分母、对象、用途完全不同 |
| C3 | 交接表写 WX-E 首包 `V_cluster=-0.40625`、成本比 1.20743；包内为 `0.0`、`1.0863` | 采用包内 `0.0 / 0.3333 / 1.0863` | 包内是同期收据；-13/32 与 64 行结构不符 |
| C4 | `REPORT_V3_V8.md` 把 v5/v6 当两包；代码上 `_scenario()` 只差 id 前缀、区间同为 700-711/600-615 | v5/v6 记**同一组 24+32 场景**（仅 id 字符串不同） | 代码级 diff 逐字相同 |
| C5 | G3 第二批包名 `..._validation`、id `calibration_5..8`，但 `generation.json.partition=calibration` | 按 generator partition 计入 24 桶，保留源包名 | 额度桶是 calibration+validation 合计 |
| C6 | 126 只到分族合计，无逐图键 | 采用 126 = 66 + 60、84 = 24 + 60；8 条旧非RL 标 residual_unverified | 本地可核：16（cal4）+ 60（G3）+ 36 + 6 = 118 |
| C7 | `DESIGN.json` 写 `scientific_maps=0`，`STATE.json` 写 64 | 采用 64 个名额；但逐图身份未核验 | DESIGN 是预执行草稿 |
| C8 | 生成器预分配 12 family，实际 40 图全 `[3,20]` | 采用「40 图单 family」为事实，禁止当规模泛化证据 | 65 个 generation.json 去重只有 `[3,20]` |
| C9 | forecast_v1 与 v8 同 seed 区间 1100-1115 / 1200-1211 | 不判重复：RNG 基址与放置律不同 | 代码级比较 |
| C10 | B 包 `map_slots` 44 vs 报告「12 地图、4 日」 | 两者都对：44 是登记人口，12 是 SELECT 子集 | 不同层级分母 |

---

## 9. 缺口（6 条）

| # | 缺口 | 影响 | 补齐方式 |
|---|---|---|---|
| G1 | 40 图逐图 quality 行不可重建（126 只有分族合计） | 无法逐图复核旧胜负 | 从 <COMPUTE_HOST> 旧结果目录抽 COMPARISONS 行对账 |
| G2 | D 64 图、B 44 图的逐图 identity+hash 不在本地快照 | 只能按人口登记，不能按图核验 | 从服务器注册/物化文件拉取 |
| G3 | joint 20261105 的 TRAIN 日基址本地未写（只有 DEV 550100-550103） | TRAIN 事件日无法逐日核验 | 查服务器完整版 `REGISTRATION.json` |
| G4 | 620 发布实例只有 raw sha256，无 canonical 哈希 | 几何级重叠只能按 raw 判（已算交集 0，但格式差异可能掩盖同几何） | canonical 化后与 12,131 表比对 |
| G5 | WX 各包 scenario 几何哈希未落盘（只有 scenario_id） | v5/v6 重复性靠代码 diff 判定 | 哈希重放 `_scenario()`（不求解） |
| G6 | 24 校准身份「额度已满」只有 STATE 字段 + 裁决文档 | 争议时需回溯 | 用本文件 `calibration.identities` 作签收单 |

---

## 10. 五段式结论

### 10.1 已证实事实

1. 官方 Liu 120 图的权威 ID 清单是 `OFFICIAL_EXCLUSION_MANIFEST.json`，120 条、120 唯一 raw、120 唯一 canonical；与 `semfix_full_P1` 600 行的 `input_sha256` 一一相等。
2. 120 图已全部暴露（1200 次配对运行、0 失败、完整解归档），**不能**作新 Formal。
3. 40 新身份 = 16 opportunity + 24 calibration/validation，两份侧车 + 汇总件三处互证；40 唯一 geometry、40 唯一 raw、10 张锚点失败。
4. 40 图全部 `family=[3,20]`、14000 m 方、生成器 `2.0.0-engineering`、**同一套天气内容**（`25916a05…`）。
5. 24 校准额度已满（24/24、剩 0、不退款）；作者尝试 40/48，剩 8 不自动授权新校准。
6. 126 比较 = 36 RL + 6 BC-only + 84 非RL（旧 24 + 新 60），旧 66 = 126−60。
7. WX-E 各包身份区间已逐包取到；**v5 与 v6 是同一批场景**；risk_v1 为 2000-2063 / 3100-3131；WX-C v3 为 4200-4231 / 5200-5231。
8. WX 全部 12 包均 `CLOSE_*`，无训练扩展；WX-C 两模式 gap 同为 1/6，uniform-shrink 失败。
9. 排除登记表共 12,131 条几何，canonical 化对平移/行序/ID 不变。
10. 旧人口中「可用于新选模」的地图数 = **0**。

### 10.2 当前未证实假说

- H1：旧的 8 条未定位非RL 行落在 weather v2/v3 的 opportunity_2 / opportunity_4 / validation_1（无逐行证据）。
- H2：D 的 64 图与 B 的 44 图确实按登记 family 生成（本地无 generation.json，仅有登记草稿）。
- H3：620 发布实例与 40 图在**几何**上也不重叠（只能证明 raw sha256 交集 0）。

### 10.3 失败或关闭

- 官方 120 图作为「新 Formal」：**关闭**（永久禁入 Formal 分母）。
- 40 图作为「新人口」：**关闭**（同 generator/family/天气，只是抽样）。
- 24 校准/验证额度：**关闭**（24/24 满，不退款）。
- 48 作者额度：剩 8 但**不自动可用**。
- WX-E 12 包 + WX-C v3：**全部关闭**，不得以换 seed 救结果。
- D 包：`D_RESOURCE_TERMINATED_INCOMPLETE_RECONCILED`，不重启。

### 10.4 下一项有界工作

1. **B1（可立即做）**：写 `PREREG.md` 冻结新 `population_id`：生成器版本 + ≥3 family 配额 + 约束 + 天气条件哈希 + day 命名空间；day 避开所有旧区间。
2. **B2**：从 <COMPUTE_HOST> 拉 D 64 图、B 44 图的逐图 identity+hash，闭 G2。
3. **B3**：对 620 实例做 canonical 化并与 12,131 表比对，闭 G4。
4. **B4**：只做哈希重放（不求解）把 WX v5/v6 的 32+32 场景 geometry 哈希落盘，闭 G5。

每条上限：只读 + 文档 + 哈希，不跑求解/训练；产出写回本包目录。

### 10.5 是否需要用户决策

**不需要。** 本文件只做排除清单与规则冻结；新人口是否立项属 G0/G3 范畴，需先有非救结果的新机制与资源修订。
