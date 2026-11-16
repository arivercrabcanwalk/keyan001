# WX5 正式结果（完整）

- 代码：wx5_server_run，commit `6363655`
- 运行：服务器 A（40 核 cgroup），`NCPU=40`，`W=38`
- 时间：2026-11-16 03:21:09 → 12:54:53 UTC，`ALL DONE`
- 结论：**8 个场景全部 100% 完成，H1（J5 对所有可实现基线）全部确认，H2（加班非劣 N6_best，δ=+5%）全部通过**

## 文件

- `SUMMARY_ZH.md`：完整汇总（2036 行，门槛表 / H1 / H2 / 次要指标 / 消融 / 敏感性 / makespan 附录）
- `ANALYSIS_V5.json`：机器可读统计
- `PROGRESS_SERVER.md`：A 上正式进度（含 ALL DONE）
- `select_es5*.json`：12 个训练变体的预注册 dev 选择记录
- `es_hist_es5*.jsonl`：12 条训练曲线
- `dev_n6grid_v5.jsonl`：N6 冻结网格
- `../models5/final_es5*.npz`：12 个最终模型（main 3 seed + nf/ne/uc 消融各 3）
- `../results_out.tar.xz.part-00..03`：全部原始逐例 jsonl、日志、模型（xz 155MB，切 4 片）

## 重建归档

```bash
cat results_out.tar.xz.part-00 results_out.tar.xz.part-01 results_out.tar.xz.part-02 results_out.tar.xz.part-03 > results_out.tar.xz
xz -t results_out.tar.xz
tar -xJf results_out.tar.xz
```

哈希：

```text
SUMMARY_ZH.md          764b406391a3736b4ec725fb7f3c1952c699fd3c9dd2cb09cd8b193e927ac2a2
ANALYSIS_V5.json       5575ec6d63736b7ab8b60b052b073192f55848f9b61f964ca66b2414b68e34af
results_out.tar.xz     68224fc8c23687641c1d80223885a1e9da34ce03bcd2cefa154f5000a3576857
part-00                ed4d3a60d94dcb025448859f3caeb6df3cfed75831f8a112256b1ff9ed788921
part-01                e7c0e50b9f498f292c4894a9e817218bed5cf42adba92e8013b002ac620dfb47
part-02                898a0a7849c306948e1bbc8757cf16e8dc330547632daf7aea2460770d444be8
part-03                79622ddda495a0eb201aab93f627a6639ea626599c6e9c49673d66732e9de8d8
```

## 核心结果

- **Test-A（主测试，112,000 行）**：全部方法完成率 100%；RL5 J5 **6143**，对 N6_best **−10.68%**、对最强基线 R_N6best **−9.65%**；加班 113.7 vs N6 140.8（**−19.2%**，H2 通过）；fails 6.65 vs 8.72（−23.8%）；**makespan 423.8 vs 492.9（−14.0%，v4 的 +19.7% 已消除）**。
- **Test-B（作者 TSALNS 计划）**：J5 7536 vs N6 8144（−7.46%），加班 174.3 vs 216.9（−19.6%），H2 通过；完成率 100%（v4 的 99.9% 缺口已修复）。
- **Test-C（压力）**：J5 1.279e4 vs 1.441e4（−11.25%），H2 −8.7%。
- **Test-L（大图 12×150 / 15×200）**：J5 1.778e4 vs 1.93e4（−7.87%），H2 −3.9%（CI 上界 +3.1% < +5%）。
- **P4a（σ×1.5）**：−7.68%；**P4b（临近预报偏差）**：−10.69%；**P3（均匀故障）**：−8.31%（最强基线为 POMO_mean）。
- **窗口敏感性**：H+180 −12.25%；H+300 −12.10%；两档完成率 100%、H2 均通过。
- **消融**：去掉天气特征 +7.27%（显著变差）；去掉紧急特征 −3.70%（该消融反而略好，如实报告）；去掉加班约束 −1.22%（但加班升到 195.7，验证约束的作用）；不用 ES（POMO）+11.03%；不用 RL（A1）+17.81%。

## 备注

- 合成天气；未改动代码、参数或随机种子。
- 全部方法统一排除 0.25/天物理不可达紧急请求（预注册口径）。
- makespan / J_v4 只在附录报告，不进入主指标。
- 原始大包在仓库中为 4 个分片，避免 GitHub 100MB 单文件限制。
