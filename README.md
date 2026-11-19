# keyan001

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
