# wx3_server_run：ES-RL（轨迹级约束进化策略）正式实验包

设计见 `wx_e/DESIGN_ZH.md`，预注册见 `wx_e/PREREG_v3.md`（正式运行前已提交），调研见 `wx_e/SURVEY_ZH.md`。
只用合成天气；纯 numpy/scipy，CPU 即可（无需 GPU）。

## 1. 获取代码（用你自己的 GitHub token，不要写进任何文件）
```bash
git clone https://github.com/arivercrabcanwalk/keyan001.git   # 私有仓库时按提示输入用户名 + 你自己的 token
cd keyan001/wx3_server_run
```

## 2. 安装 + 冒烟测试（几分钟）
```bash
bash setup.sh                      # 建 .venv，装 numpy/scipy（已有则跳过）
SMOKE=1 bash run_all.sh            # 极小规模走通全流程；看到 "ALL DONE" 即通过
rm -rf logs models3 wx_e/results results_final results_out.tar.gz PROGRESS_SERVER.md   # 清掉冒烟产物（只删本目录下这些生成物）
```

## 3. 正式运行（一条命令，后台）
```bash
nohup bash run_all.sh > run_all.log 2>&1 &
tail -f PROGRESS_SERVER.md         # 进度（JST 时间戳）
```
- 自动用「CPU 核数 − 2」个 worker（40 核 → 38）。可用 `NCPU=40` 覆盖。
- **断点续跑**：机器重启或进程被杀后，再执行同一条 nohup 命令即可；每个阶段有 `logs/*.official.done` 标记，每条评估结果逐行写入、已完成的跳过；ES 每轮原子保存状态。
- 预计时长（40 核）：ES 训练约 4.5–7.5 h（3 种子并行，每个 (种子, λ) 300 轮，单次上限 150 分钟）+ 评估约 1.5–2 h，**合计约 6.5–9.5 h**。

## 4. 产出
- `results_final/SUMMARY_ZH.md`：所有检验表（地图级 Wilcoxon+Holm、天聚类检验、交叉 bootstrap CI、「确认」列）。
- `results_final/ANALYSIS_V3.json`、各 `*_v3.jsonl` 原始逐日结果、`select_es_s*.json`（预注册选择记录）、`es_hist_*.jsonl`（训练曲线）。
- `results_out.tar.gz`：上面全部 + 最终模型 `models3/final_es_s*.npz` + 日志。把它发回来即可分析。
- 脚本**不会推送任何东西**到网络。

## 5. 目录
| 文件 | 作用 |
|---|---|
| `run_all.sh` | 单一入口（阶段 s1 N6 冻结 → s2 ES 训练+选择 → s3 Test-A → s4 Test-B/C → s5 P4/P3 → s6 WX-H → s7 分析打包） |
| `run_es.py` | ES-RL 训练（对偶扰动、共同随机数、中心化秩、Adam、断点续跑） |
| `select_es.py` | 预注册 dev 选择 |
| `run_jobs3.py` | 可续跑的评估器 |
| `analyze_v3.py` | 统计与汇总 |
| `wx2/` | 仿真器、天气、策略、公平 twin rollout（`twin.py`） |
| `run_api.py` | 试点中失败的 API/ExIt 学习器（保留供透明与消融，正式流程不运行） |
| `models/rl_s{0,1,2}_best_pomo_v2.npz` | v2 服务器训练的 pomo_v2 策略（ES 初始化 & 基线 POMO_s*） |
