# stats/ 说明（哪个是权威）

最终一次运行：`analysis/compute_stats_full.py`，输入为**落盘了完整解之后**重跑的结果文件；
重跑前后点估计**逐位相同**（这是对结果稳定性的直接检验）。`RESULTS_MANIFEST.json` 冻结了全部文件的 SHA256。

| 文件 | 内容 | 分母 | 权威性 |
|---|---|---|---|
| `STATS.json` | 本包主统计：开发集 + 确认集 + 合并；含 ITT 与 valid-only 双口径、failures_by_method、replication | **47 图** | **权威入口** |
| `STATS_server.json` | 同脚本在 <COMPUTE_HOST> 上的副本 | 47 图 | 溯源；与 `STATS.json` 点估计逐位相同，5 个 CI 端点差 1–2 ulp |
| `STATS_local.json` | 更早一次本机运行的副本 | 47 图 | 溯源 |
| `STATS_INDEPENDENT_AUDIT.json` | 独立复核线程自己的重算（**只覆盖 12 图开发集**，自有 schema） | 11 图 | 独立佐证；**不是**主统计，不覆盖 36 图确认集 |

`G3_INDEPENDENT_AUDIT.md` 声明它未审 36 图确认集、不背书 −10.95%——这是正确的边界，
不代表确认集无效：确认集由 `G3_REPORT.md` §3.1 与上面的 `STATS.json` 承载。
