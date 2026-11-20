# keyan001

## 跑 Grok 的两部分实验

- **A 有风、无紧急任务**：常规巡检。固定东风/北风测联合机位路线与返站时间；另用原天气模拟器训练在线策略，在动态风、雷暴条件下测试。
- **B 有紧急复检、无风**：常规任务照做，紧急单仅在发布时可见；比较响应时效、常规任务完成、返站和成本。

在 hn01 的仓库根目录运行（已有安装 torch、numpy、scipy 的 Python；否则先执行 `bash rlv3_weather/setup.sh`）：

```bash
bash run_experiments.sh
```

默认顺序运行 A、B 和 3 个训练 seed。两套实验不共享权重。新生成的训练/测试图与仓库原图的冻结模型评估分开报告。普通探索实验不用填写票据；不是 Formal。
可用 `--part A` 或 `--part B` 单跑一部分，`--profile quick` 做快速全流程检查。直接看输出目录的 **SCORES.csv**（逐 seed、数据来源、风况/紧急负荷、方法）；**RESULTS.json** 列退出状态和缺项。[实验方法、对照和口径](rlv3_review/TWO_EXPERIMENTS_ZH.md)。

当前审后实验入口：[论文 A 天气](rlv3_weather/README_ZH.md) · [论文 B 紧急复检](rlv3_emergency/README_ZH.md) · [审查与实验协议](rlv3_review/REVIEW_ZH.md) · [工程验收](rlv3_review/ACCEPTANCE.md) · [来源与适用边界](rlv3_review/SOURCES_ZH.md)。

下列历史快照只读，不是本版运行入口。

## rl_project_pack.tar.gz

- size: 39 MiB, 56,600 files
- md5: `ee334a3fdd7529bce18ed6f8cd3871fb`

Contents: `ca_rl_completion_v5_a6_no_runtime_reward_20261101/` source tree,
`training_runs_v5_a6_no_runtime_reward_20261101/PPO_seed{11,23,37}/best.pt`,
120 Liu instances, `sol_rl/`, `bench_rl_12s/`, result CSVs, `lrphsd_eval.py`,
`export_sol.py`, and `pack/{ENV.txt,MANIFEST.txt,requirements_freeze.txt}`.

See `pack/ENV.txt` inside the archive for the entry command and environment.

```bash
md5sum -c <<< "ee334a3fdd7529bce18ed6f8cd3871fb  rl_project_pack.tar.gz"
tar xzf rl_project_pack.tar.gz
```
