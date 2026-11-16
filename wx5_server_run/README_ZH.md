# wx5_server_run：v5 约束 ES-RL 正式实验包（100% 完成 + 12 h 作业窗口 + 加班预算）

- 设计：`wx_e/DESIGN_v5_ZH.md`；预注册（正式运行前提交）：`wx_e/PREREG_v5.md`；调研：`wx_e/SURVEY_v5_ZH.md`；试点：`wx_e/PILOT_v5.md`。
- 只用合成天气；纯 numpy/scipy，CPU 即可（无需 GPU）。

## 1. 获取代码（用你自己的 GitHub token，不要写进任何文件）
```bash
git clone https://github.com/arivercrabcanwalk/keyan001.git   # 私有仓库时按提示输入用户名 + 你自己的 token
cd keyan001/wx5_server_run
```

## 2. 安装 + 冒烟测试（约 5–10 分钟）
```bash
bash setup.sh
SMOKE=1 bash run_all.sh            # 看到 "ALL DONE" 即通过
rm -rf logs models5 wx_e/results results_final results_out.tar.gz PROGRESS_SERVER.md wx_e/N6_FREEZE.smoke.json data/days
```

## 3. 正式运行（一条命令，后台）
```bash
nohup bash run_all.sh > run_all.log 2>&1 &
tail -f PROGRESS_SERVER.md         # 进度（JST 时间戳）
```
- 自动用「CPU 核数 − 2」个 worker（40 核 → 38），可用 `NCPU=40` 覆盖。
- **断点续跑**：重启/被杀后再执行同一条 nohup 命令即可。阶段有 `logs/*.official.done`；评估逐行写入；ES 每轮原子保存，
  **未达到 250 轮的 ES 运行会被自动续跑补齐（最多 5 次），选择脚本拒绝使用未跑满的运行**（等算力）。
- 预计时长（40 核）：ES 12 个运行（4 变体 × 3 种子）并行约 4.5–5 h + 评估约 2.5–3 h，**合计约 7.5–8 h（上限 10 h）**。

## 4. 产出
- `results_final/SUMMARY_ZH.md`：门槛表、H1（J5，Holm）、H2（加班预算）、次要、消融、权重敏感性、附录（makespan / J_v4）。
- `results_final/ANALYSIS_V5.json`、各 `*_v5.jsonl` 逐日结果、`select_*.json`、`es_hist_*.jsonl`、`DONE_*`（迭代数证明）。
- `results_out.tar.gz`：上述全部 + `models5/final_*.npz` + 日志（发回即可分析）。脚本**不会推送任何东西**。

## 5. 目录
| 文件 | 作用 |
|---|---|
| `run_all.sh` | s1 N6 冻结 → s2 约束 ES（main/nf/ne/uc × 3 种子）+ 选择 → s3 Test-A（+ rollout 子集）→ s4 B/C/L → s5 P4a/P4b/P3 → s6 窗口敏感性 → s7 分析打包 |
| `run_es5.py` | 约束 ES（J5 + λ_V·违规 + λ_OT·加班，对偶上升；特征屏蔽消融） |
| `select_es5.py` | 预注册 dev 选择（complete=100% 且加班 ≤ 预算） |
| `analyze_v5.py` | 统计与汇总 |
| `run_jobs3.py` | 可续跑评估器 |
| `wx2/` | 仿真器（共享可行性层：备用机兜底、时间再平衡、作业窗口）、天气、特征、策略、`reopt.py`（全量重优化基线） |
| `run_es.py`、`select_es.py`、`analyze_v4.py` | v4 版本，保留供对照，正式流程不运行 |
| `models/rl_s{0,1,2}_best_pomo_v2.npz` | pomo_v2 策略（ES 初始化 & POMO 基线） |
