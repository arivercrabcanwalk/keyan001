# WX4 主结果（N4big 待补）

生成时间：2026-11-16 04:23 JST（服务器 `run_all` Stage7）。
本目录是 A/B/C 三机并行完成六组 ES 训练后，由 A 单机跑完主测试得到的**主结果**。
N4big（`N4f_M32/N4p_M32`，Test-A 7200–7203）仍在补跑，完成后会更新本目录和归档。

## 文件

- `SUMMARY_ZH.md`：完整中文汇总（完成率门槛优先；H1/H2、次要指标、敏感性、逐种子）
- `ANALYSIS_V4.json`：机器可读统计
- `PROGRESS_SERVER.md`：A 上正式运行/测试进度
- `select_es_s{0,1,2}.json`：预注册 dev 选择记录（三 seed 均为 `1:10:0`，`feasible=false`：100% 完成但 mk 未满足 ≤1.02×N1）
- `es_hist_es_s*.jsonl`：六组训练曲线
- `dev_n6grid_v4.jsonl`：N6 冻结网格
- `../models4/final_es_s{0,1,2}.npz`：三个最终策略
- `../results_out_main.tar.xz`：全部原始逐例 jsonl、日志和 final 模型（压缩后约 70MB）

## 归档校验

```bash
shasum -a 256 results_out_main.tar.xz
# 1103190bcf48a858f66f50fe21f460c6ba28de866a24c9a1f8b07f986407e8a0
tar -xJf results_out_main.tar.xz
# 得到 results_final/、models4/、logs/、wx_e/results/
```

## 关键结论（详见 SUMMARY_ZH.md）

- Test-A：全部方法 100% 完成；RL4 J 5120 vs N1 6588（−22.28%）、vs N6 6389（−19.85%），H1 通过；H2 makespan +19.65% vs N6，**未通过**。
- Test-C、P4a/P4b、P3、WX-H：完成率 100%，H1 均确认；H2 均未通过（mk +7.7%～+36.8%）。
- Test-B、Test-L：所有方法完成率约 99.7%–99.9%，**门槛未过**，H1 只能作条件参考；mk 仍更差。
- 结论：v4 的完成率门槛修复了 v3 的“少做事”问题；J/成本/失败/时延全面改善，但 **makespan 非劣（H2）没有成立**，必须如实报告。

## 备注

- 合成天气；未改动 v4 代码、实验参数或随机种子。
- N4big 结果不在本主归档中；见 `N4BIG_PENDING.md`。
