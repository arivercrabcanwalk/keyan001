> **已被 G3_REPORT.md 取代。** 本文件只含 12 张开发图（ordinal 1），写在 36 张确认图存在之前；数字与 G3_REPORT.md 的开发集部分一致。保留作为时间线证据，不作为最终结论入口。

# G3 开发集报告：M_return 缺口主要是"换标签"，不是路线问题

日期：2026-11-12（Asia/Shanghai）。全部计算在 <COMPUTE_HOST>（`<COMPUTE_HOST>`）执行，Python 3.10.12，Corretto JDK 17.0.21，单进程串行。
本报告是本包**唯一新增的实证科学结果**。它不是 Formal，不是 RL 优势证据，不改变 G0 的 NO-GO 以及 G4/G5/G6 的未通过状态。

## 0. 一句话结论

在 Liu 原目标、固定部署/站型/target-station、逐图 `C <= C_Liu + 1e-7`、epsilon=0 的合同下，
**"新图上的 M_return 改善"有 99.3% 来自一个不改变任何路线、不改变任何成本的 slot 换标签操作**：
把作者解里已经存在的整趟重新分配到站内合法 slot，总运行分钟逐位不变，因此成本约束恒满足。
精确成本中性重排使 11 张新图的 M_return 平均下降 **12.919%**（中位 17.059%，地图级 bootstrap 95% CI [-18.788%, -6.696%]，7 胜 / 4 平 / 0 负）；
一个 **1 毫秒**的 LPT 启发式在 10/11 图上取到与精确最优完全相同的值。路线级搜索在成本中性最优之上只再降 **0.599%**（n=8，CI [-1.651%, -0.000%]）。

因此本包把既有"平均改善 5%"门槛重新定性为**平凡基线可达**，而不是方法贡献。这一点是后续 G0 裁决的直接输入。

## 1. 人口与身份（冻结）

|项目|值|
|---|---|
|生成器|v2 `2.0.0-engineering`，协议 `constraint-reconstructed-sequential-conditional-uniform-proposal`，RNG SplitMix64（reference variant v1）|
|namespace|`takeover-20261112-g3-v1`（全新，未在任何历史 manifest 出现）|
|partition|opportunity，ordinal=1|
|family|12 个已发表 family：(3,10)…(10,110)|
|图数|12 生成成功；11 张锚点合格|
|身份|每图 raw_sha256 + canonical_geometry_sha256，见 `results/g3_pop/population_index.json`|
|排除|120 官方（全部已暴露）+ 12,000 pilot 提案 + 合成烟测 + Windows 探针；共 12,131 条排除记录，生成时强制校验（`generator_v2.ExclusionIndex.require_research_ready`）|
|本人口性质|**新身份**，但属 G3 **开发集**（opportunity），不是 Formal；且 12 图均为单张 ordinal，不得事后扩 ordinal 追结果|

这不是 40 旧身份的重跑：旧 40 身份全部为 family=[3,20]、同一套天气、同一 namespace 抽样；本人口覆盖 12 个 family。

## 2. 作者锚点

- 实现：作者 Java（J1b profile，`reference/java/J1b_source`，逐文件 SHA256 与 `J1b_build_manifest.json` 一致）。
- 参数：outer 500，名义 ALNS 5000 次（**实际 270 次**，因 `temperature > finalTemp` 提前终止；见 PAPER_EQUATION_COMPARISON.md §4）。
- seed：`sha256("takeover-20261112-g3-author-seed-v1:" + input_sha256)[:8]`，事前冻结、不按成本或 M 选 seed。
- 每图单次运行，wall 1.4–8.7 s。
- 收据：`results/g3_pop/author/<map>/RUN.json` 含 `anchor_eligible`、源码/字节码/build/DEP 哈希、完整 stdout/stderr、独立审计与 `return_score.json`。
- 结果：**11/12 anchor_eligible**。

### 2.1 唯一失败：4x20_o1（记为 ANCHOR_NOT_ELIGIBLE，不补图）

作者 Java 自报 `latest completion time = 86.56491551657447`，独立 scorer 对该 recorded solution 算得 `M_return = 79.47485804779748`。
逐项核对后定位到**记录端**而非求解端：

- 两者 cost 完全一致（`249.41126588643058`，Δ=0），20/20 目标服务，无 issue；
- 差异恰好等于 `45.11378648015091 + 41.45112903642357 = 86.56491551657448`；
- 即 station#2 的 `[6,7,16]`（45.114）与 `[3,19,17]`（41.451）在 `reference.json` 的 slot 归属与 Java 打印的 large/small drone 归属**互换**；
- 两种归属都可行、成本相同，但 M_return 从 86.565 变为 79.475。

作者 runner 的"stdout latest-time 与 scorer M_return 逐解对账"因此正确地拒绝该锚点。
按"固定分配、失败不补图"的登记规则，该 slot 保持空置并在此记录，**未计入任何汇总**。

## 3. 主结果：成本中性重排

### 3.1 为什么它是"免费的"

把锚点解中的每一趟（一个闭合巡回 `station→perm→station`）整体分配给该站另一个合法 slot，**不改变任何一趟的内容、顺序、能量或时长**。因此：

- 每站总运行分钟 `operating_s` 不变 ⇒ 全局 `operating` 不变 ⇒ `cost = fixed + 0.5·operating` **逐位不变** ⇒ `C <= C_Liu + 1e-7` 恒满足；
- `M_return = max_s max_slot (slot duty)` 会因分配而改变；
- 于是"在成本中性类内最小化 M_return"是一个**纯 min-max 负载均衡**问题，与路线内容无关。

该类的精确最优可用每站穷举求得（每站 trip 数 ≤ 15，2 个 slot ⇒ ≤ 2^15 种分配；实测最大 32768）。这就是 `harness/04_exact_reassign.py`。

### 3.2 逐图结果

| map | anchor | exact cost-neutral | vs anchor | LPT 6s | vs anchor | best route search | vs anchor | LPT gap to exact |
|---|---|---|---|---|---|---|---|---|
| 3x10_o1 | 56.098 | 44.611 | -20.48% | 44.611 | -20.48% | 44.611 | -20.48% | +0.00% |
| 3x20_o1 | 66.824 | 66.824 | +0.00% | 66.824 | +0.00% | 66.824 | +0.00% | +0.00% |
| 3x15_o1 | 106.981 | 92.715 | -13.34% | 92.715 | -13.34% | 92.715 | -13.34% | +0.00% |
| 4x25_o1 | 120.942 | 120.942 | +0.00% | 120.942 | -0.00% | 120.942 | -0.00% | -0.00% |
| 4x30_o1 | 130.685 | 96.926 | -25.83% | 96.926 | -25.83% | 96.926 | -25.83% | +0.00% |
| 5x35_o1 | 177.083 | 136.815 | -22.74% | 136.815 | -22.74% | 136.815 | -22.74% | +0.00% |
| 6x50_o1 | 182.002 | 140.544 | -22.78% | 142.460 | -21.73% | 134.629 | -26.03% | +1.36% |
| 7x65_o1 | 229.586 | 229.586 | +0.00% | 229.586 | +0.00% | 228.245 | -0.58% | +0.00% |
| 8x80_o1 | 240.788 | 199.712 | -17.06% | 199.712 | -17.06% | TIMEOUT | — | +0.00% |
| 9x95_o1 | 247.678 | 247.678 | +0.00% | 247.678 | +0.00% | TIMEOUT | — | +0.00% |
| 10x110_o1 | 318.737 | 255.354 | -19.89% | 255.354 | -19.89% | TIMEOUT | — | +0.00% |

"best route search" = `joint_minmax` 在 6s/12s 中取得的最好值（确定性路线级下降，`g23/nonrl_baseline/baseline.py`）。TIMEOUT 表示该预算内无法产出有效输出（`NO_ONTIME_VALID_OUTPUT`），不是 0 改善。

### 3.3 统计推断（配对，单位=地图，B=10000，seed=20261112）

|比较|n|平均差|中位|95% CI（平均%）|W/T/L|
|---|---|---|---|---|---|
|exact cost-neutral vs anchor|11|**-12.919%**|-17.059%|[-18.788, -6.696]|7/4/0|
|LPT 6s vs anchor|11|-12.823%|-17.059%|[-18.656, -6.662]|7/4/0|
|LPT 6s vs exact cost-neutral|11|+0.124%|0.000%|[-0.000, +0.372]|0/10/1|
|joint_minmax 6s vs anchor|7|-15.488%|-20.477%|[-22.750, -7.381]|5/2/0|
|joint_minmax 6s vs exact cost-neutral|7|-0.601%|0.000%|[-1.804, +0.000]|1/6/0|
|joint_minmax 12s vs anchor|8|-13.625%|-16.906%|[-21.210, -5.904]|6/2/0|
|joint_minmax 12s vs exact cost-neutral|8|-0.599%|0.000%|[-1.651, -0.000]|2/6/0|

要点：

1. 成本中性重排的增益**显著**（CI 完全位于 0 以下），且与"5% 目标"相比是 **2.6 倍**。
2. LPT 与精确最优之间只差 0.124%（且只发生在 1 张图）；10/11 图逐位相同 ⇒ **1ms 的启发式已经吃满了这一类空间**。
3. 路线级下降在成本中性最优之上只再降 0.599%，n=8，CI 上界触及 0，且 **3 张大图完全超时**。

## 4. 这意味着什么

### 4.1 对"5% 目标"的重新定性

既有规划里的"A 方向目标：平均改善 5% 且地图级 95% CI 下界 > 0"被本轮直接证否其**判别力**：
一个零学习、零路线改变、零成本的换标签操作就能达到 12.9%，并越过 5% 门槛。
因此：

- 任何"我们比作者锚点改善 X%"的主张，**不能**作为方法有效性的证据；
- 反过来，任何 RL 主张必须先打赢 `exact_cost_neutral_reassign`（一个可精确计算的下界门槛），而不是打赢作者锚点；
- 这也解释了历史上一系列"改善 5% 但 RL 并未胜出"的张力：改善本来就属于目标错配的可回收部分，与学习无关。

### 4.2 对 G0 的含义

作者锚点只优化成本（Liu 原目标），在成本最优解族内 slot 归属是任意的，因此 M_return 天然不平衡。
把这个不平衡回收掉不需要任何新机制。**这直接削弱了"用 M_return 作为新机制载体"的可行性**：
机制若要在 S 上成立，必须解释它如何胜过成本中性最优，而后者是一个可在毫秒级求到的组合下界。

### 4.3 对 G3 的含义（唯一实质性推进）

G3 的"最强合格 non-RL"现在有了一个**可证明的地板**：
`exact_cost_neutral_reassign`（成本中性类精确最优，11/11 admissible，Δcost=0）＋ 路线级下降（`joint_minmax` 或更强的 min-max ALNS）。
该地板高于作者锚点 12.9%，且可靠、可复现、无超时（精确重排本身是纯枚举，11 图全部 < 1 s）。

### 4.4 没有证明的东西

- 未证明"任何 RL 都不可能有效"。本轮只证明目标错配部分是平凡的。
- 未证明路线级 headroom 为零：6x50_o1 上路线搜索比成本中性最优再降 4.2%，说明**换趟/换路线**仍有空间；全规模精确最优（允许改变趟划分）正在另行计算（`EBD949`/exact-minmax 线程），本报告不引用其结果。
- 未触及 W 合同；不改变 WX 各 pilot 的关闭状态。

## 5. 失败、超时与保留

|事项|处置|
|---|---|
|4x20_o1 锚点不合格（记录端 slot 归属互换）|保留在 `results/g3_pop/author/4x20_o1`，标 ANCHOR_NOT_ELIGIBLE，不进汇总，不补图|
|`joint_minmax` 在 8x80/9x95/10x110 的 6s 与 12s 均 NO_ONTIME_VALID_OUTPUT|保留原行（status 已写入），作为"该实现不构成大图强基线"的证据，不重跑找阳性|
|`joint_minmax` 6s 在 7x65 超时、12s 成功|保留两行|
|作者 ALNS 名义 5000 次实际 270 次|在锚点收据中记录，不据此重跑|
|本人口只看了 opportunity ordinal 1|不得事后加 ordinal/换 namespace 追结果|

## 6. 复现

```bash
# 0) 环境（已在本轮完成，隔离 JDK）
ssh <COMPUTE_HOST> 'ls <EXECUTION_PATH>'

# 1) 生成人口（12 图，固定 namespace/partition/ordinal）
python3 harness/10_gen_pop.sh          # -> g3_pop/population_index.json

# 2) 作者锚点（每图一次，seed 由输入哈希派生）
python3 harness/02_run_author.py --out <pop> --timeout 1800

# 3) 同目标非 RL
python3 harness/03_run_nonrl.py --out <pop> --budgets 6,12

# 4) 成本中性精确最优 + 独立复核
python3 harness/04_exact_reassign.py --out <pop>

# 5) 统计（本地，B=10000）
python3 analysis/compute_stats.py
```

所有数字可由 `results/g3_pop/*.json` 与 `stats/STATS.json` 独立重算。