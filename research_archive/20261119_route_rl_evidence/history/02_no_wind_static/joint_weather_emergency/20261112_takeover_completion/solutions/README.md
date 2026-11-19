# solutions/ — 完整解的实际位置

顶层 `solutions/` 故意留空；**完整解都随各自的方法行落盘**，位置如下：

| 内容 | 路径 |
|---|---|
| 作者锚点完整解（每图） | `results/g3_pop/author/<map>/solution.json` 与 `reference.json` |
| 非 RL 每行交付解（chosen + raw + 每候选证书） | `results/g3_pop/solutions/<map>__<method>__<budget>s.json` |
| 同上（确认集） | `results/g3_confirm/solutions/...` |
| 成本中性精确重排解 | `results/g3_pop/EXACT_REASSIGN_RESULTS.json` 的 `per_station[].assignment` |
| 全局精确最优解（6 图） | `results/exact_solutions/` 与 `results/EXACT_RESULTS.json` |

合计：开发集 33 个非 RL 解 + 确认集 108 个非 RL 解 + 47 个作者解 + 7 个精确解。
每个非 RL 解文件都带 `chosen_solution_sha256` 与 `candidate_certificates`，因此可以**从产物**复核，而不必重跑搜索。
