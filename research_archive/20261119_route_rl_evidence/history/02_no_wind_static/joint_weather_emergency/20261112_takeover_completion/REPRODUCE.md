# REPRODUCE — 干净环境入口与真实复现收据

本文只写**本轮实际跑过并留下收据**的路径。所有计算在 <COMPUTE_HOST> 上完成；本地只做文档、静态审查、哈希与统计复算（统计也在 <COMPUTE_HOST> 复算过一次）。

## 0. 前置

- 远端根：`<EXECUTION_PATH>`
<CONNECTION_COMMAND_REMOVED>
  （本地已封装为 `<EXECUTION_PATH>`）
- 远端 Python 3.10.12（**仅标准库**；无 pip、无 numpy）
- 隔离 JDK：`runtime/jdk17`（Corretto 17.0.21，tarball SHA256 `8f9a2ddb131ec5317419f2b0769240fe22ce27f8a0ae43f5346d53e1c8aec6a0`）
- 源码快照：`code/`（31 文件，本地↔远端 SHA256 31/31 一致）

## 1. 从零复现 G3（约 6 分钟墙钟）

```bash
R=<EXECUTION_PATH>
GEN=$R/code/route_rl_research/20261103/return_makespan/g23<EXECUTION_PATH>

# 1) 开发集（ordinal 1，12 图）
python3 $R/harness/gen_maps.py --namespace takeover-20261112-g3-v1 \
  --partition opportunity --out $R/g3_pop --ordinals 1 --generator-dir $GEN

# 2) 作者锚点（J1b，隔离编译 + 每图单 seed）
python3 $R/harness/02_run_author.py --out $R/g3_pop --timeout 1800

# 3) 同目标非 RL（LPT + joint_minmax，6s/12s）
python3 $R/harness/03_run_nonrl.py --out $R/g3_pop --budgets 6,12

# 4) 成本中性类精确最优 + 独立复核
python3 $R/harness/04_exact_reassign.py --out $R/g3_pop

# 5) 确认集（ordinal 2-4，36 图；脚本先写 PREREG_CONFIRM.json）
bash $R/harness/20_confirm_pop.sh
```

## 2. 统计（B=10000，seed=20261112，单位=地图）

```bash
# 在包根目录执行；期望读 results/g3_pop 与 results/g3_confirm
python3 analysis/compute_stats_full.py     # -> stats/STATS.json
python3 analysis/emit_final_tables.py      # -> FINAL_TABLES.md
```

本轮实际收据：本地与 <COMPUTE_HOST> 各跑一次，**所有点估计逐位相同**，5 个比较的 95% CI 端点差 1–2 ulp（求和顺序）。
服务器原始输出见 `receipts/SERVER_STATS.txt`。

## 3. 精确最优（6 图）

```bash
python3 $R/harness/exact_minmax.py        # -> g3_pop/EXACT_RESULTS.json（12 图总墙钟 8.3 s）
```

5 重独立检查（RGS 穷举对照 n≤8 的 12 个站、Pareto 点复算、9,845 个随机配置支配性抽样、validate_candidate、独立进程重跑）
的结论见 `EXACT_MINMAX_REFERENCE.md` §4/§11。

## 4. 期望的关键数字（用于比对）

|量|值|
|---|---|
|开发集 exact cost-neutral vs anchor|−12.919%，CI [−18.788, −6.696]，7/4/0（n=11）|
|确认集同量|−10.951%，CI [−14.852, −7.354]，20/16/0（n=36）|
|合并|−11.412%，CI [−14.796, −8.179]，27/20/0（n=47）|
|LPT vs exact（合并）|+0.100%，CI [−0.000, +0.270]，0/45/2|
|joint 12s vs exact（valid-only）|−0.310%，CI [−0.636, −0.063]，7/27/1（n=35）|
|joint 12s vs exact（ITT）|+3.607%，CI [+1.250, +6.407]，7/31/9（n=47）|
|6 图精确最优与 LPT 的差|0.0（6/6）|

## 5. 已知的不可复现项（必须如实披露）

- **joint_minmax 不是位级可复现**：`candidate_validation_calls` 随墙钟切点浮动（独立复核实测 ±31，0.4%），
  但交付值可复现。这是墙钟预算的固有性质，不是缺陷。
- **4x20_o1 的作者记录不可用**：Java 打印与 `reference.json` 的 slot 归属互换，cost 相同、M_return 不同（86.5649 vs 79.4749）。
- **arXiv/出版社入口**：Han 在线 SI 文章页 403、CDN 11 个 URL 404；Zhao 独立 SI 走 `ars.els-cdn.com` 取得（HTTP 200）。
  这两个状态只代表本轮探测，不代表永久状态。

## 6. 环境限制

- 远端 `/` overlay 仅约 9.6 GB 可用；本包全部产物合计 < 20 MB（gzip 后 < 2 MB）。若扩规模，输出必须落 `<EXECUTION_PATH>`（独立 49G 卷）。
- 无 GPU；本轮所有计算均为 CPU 串行，总 CPU 消耗 < 0.1 核小时。
