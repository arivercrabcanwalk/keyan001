# WX4 主结果 + N4big 参照（完整）

生成时间：2026-11-16 07:39 JST（Stage7 + N4big 完成后重跑分析）。
本目录是 A/B/C 三机并行完成六组 ES 训练后，由 A 单机跑完 Test-A/B/C/L、P4/P3、WX-H，
随后补跑 N4big（M32）并重跑分析的最终结果。

## 文件

- `SUMMARY_ZH.md`：完整中文汇总，已包含 N4big；Test-A 61,400 行
- `ANALYSIS_V4.json`：机器可读统计
- `PROGRESS_SERVER.md`：A 上正式运行/测试进度
- `select_es_s{0,1,2}.json`：预注册 dev 选择记录（三 seed 均为 `1:10:0`，`feasible=false`：100% 完成但 mk 未满足 ≤1.02×N1）
- `es_hist_es_s*.jsonl`：六组训练曲线
- `dev_n6grid_v4.jsonl`：N6 冻结网格
- `testA_n4big_M32.jsonl`：400 行 N4big 原始结果
- `N4BIG_DONE.md`：N4big 结果与参照对比
- `../models4/final_es_s{0,1,2}.npz`：三个最终策略
- `../results_out_main.tar.xz`：主测试全部原始逐例 jsonl、日志和 final 模型（61,000 行 Test-A）
- `../results_out_n4big.tar.xz`：N4big 增量（400 行 + 更新后的 summary/analysis + 日志）

## 完整重建

```bash
tar -xJf results_out_main.tar.xz
tar -xJf results_out_n4big.tar.xz
# 主 testA_v4.jsonl (61,000 行) + testA_n4big_M32.jsonl (400 行) = 完整 61,400 行
# 两者方法不重叠，直接 cat 即可；M32 行只覆盖 7200-7203 的 200 图 x 2 方法
```

## 校验

```text
SUMMARY_ZH.md               039440b5b5c4b0e9677363f65ae9764c6c3072f3cc2b7e52ef61df42e1c44a30
ANALYSIS_V4.json            6633ff08b240a32f7fbcd2e52942238d35385d1c657560c759fcf10b82b04203
results_out_main.tar.xz     1103190bcf48a858f66f50fe21f460c6ba28de866a24c9a1f8b07f986407e8a0
results_out_n4big.tar.xz    2950f1f3f76939b1f3eeee00f0e6250617ed02214aea2665742dc421c636e9e2
testA_n4big_M32.jsonl       99ea87fec513b13503f158b8adfdde99172892efd35d345880b1df485b7082a7
```

## 关键结论（详见 SUMMARY_ZH.md）

- Test-A：全部方法 100% 完成；RL4 J 5120 vs N1 6588（−22.28%）、vs N6 6389（−19.85%），H1 通过；H2 makespan +19.65% vs N6，**未通过**。
- Test-C、P4a/P4b、P3、WX-H：完成率 100%，H1 均确认；H2 均未通过（mk +7.7%～+36.8%）。
- Test-B、Test-L：所有方法完成率约 99.7%–99.9%，**门槛未过**，H1 只能作条件参考；mk 仍更差。
- N4big：N4f J 5131、N4p J 4247，均 100% 完成；RL 对 N4f J −3.98%（p=0.194，不显著），对 N4p J +16.01%（更差）。N4p 是参照/上界，不是 H1 基线。
- 结论：v4 的完成率门槛修复了 v3 的“少做事”问题；J/成本/失败/时延改善，但 **makespan 非劣（H2）没有成立**。

## 备注

- 合成天气；未改动 v4 代码、实验参数或随机种子。
- N4big 的 400 行只在 7200–7203 的 4 个天气日上，不改变主测试的 100 天统计。
