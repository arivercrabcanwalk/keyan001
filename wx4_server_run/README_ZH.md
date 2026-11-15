# wx4_server_run：「先保证 100% 完成，再比较其他指标」的 ES-RL 正式实验包

预注册见 `wx_e/PREREG_v4.md`（**正式运行前已提交**；含 v3 reward hacking 的披露），试点见 `wx_e/PILOT_v4.md`，
v3 设计/调研见 `wx_e/DESIGN_ZH.md`、`wx_e/SURVEY_ZH.md`。只用合成天气；纯 numpy/scipy，CPU 即可（无需 GPU）。

## 0. v4 相对 v3 改了什么
1. **共享可行性层（所有方法完全相同）**：不放弃重试、多目标超能量拆分、最晚出发/强制出发掩码（时间余量 + 方向相关预报能量窗口）、
   duty 不足时移交给其他无人机、紧急请求超期 ≥30 min 时强制服务、收工后 8 h 完成窗口（t>H 无新警报、风场衰减，修复 v3 冻结假象）。
   试点：dev 400/400、诊断 150/150、Test-L 20/20 上**所有方法 100% 完成**。
2. **完成率是第一门槛**：任何方法 <100% 被标记，其他指标只作条件参考；J' = J + π·未完成 的 π 敏感性作为次要护栏。
3. **ES 重训**：在共享层内训练，目标含 1000×(未完成+漏紧急)；**固定 500 次迭代、无墙钟上限**；3 种子 × 2 组 λ（一组含 makespan 项）
   6 个运行并行、worker 相同 → 真正等算力；dev 选择要求 100% 完成且 makespan 对最强基线非劣。pomo_v2 在掩码下重新评估。
4. **rollout 截止在仿真内部检查**（超时立即中止该次模拟），删除退化的 10 ms 档；保留 100/1000 ms。
5. **测试天气**：每个测试集 100 个全新独立天气日（Test-A 7200–7299 等）；保留天聚类检验与地图×天交叉 bootstrap。
6. **新增**：权重敏感性（用记录分量重新计分）、较大实例集 Test-L（12×150、15×200）；保留 Test-A/B/C、P4a/b、时延分析。

## 1. 获取代码（用你自己的 GitHub token，不要写进任何文件）
```bash
git clone https://github.com/arivercrabcanwalk/keyan001.git   # 私有仓库时按提示输入用户名 + 你自己的 token
cd keyan001/wx4_server_run
```

## 2. 安装 + 冒烟测试（约 5–10 分钟）
```bash
bash setup.sh                      # 建 .venv，装 numpy/scipy（已有则跳过）
SMOKE=1 bash run_all.sh            # 极小规模走通全流程；看到 "ALL DONE" 即通过
rm -rf logs models4 wx_e/results results_final results_out.tar.gz PROGRESS_SERVER.md wx_e/N6_FREEZE.smoke.json data/days   # 清掉冒烟产物
mkdir -p logs
```

## 3. 正式运行（一条命令，后台）
```bash
nohup bash run_all.sh > run_all.log 2>&1 &
tail -f PROGRESS_SERVER.md         # 进度（JST 时间戳）
tail -f logs/es_train.log          # ES 训练曲线（每 10 轮一行，含 compl= 完成率）
```
- 自动用「CPU 核数 − 2」个 worker（40 核 → 38）。可用 `NCPU=40` 覆盖。
- **断点续跑**：机器重启或进程被杀后，再执行同一条 nohup 命令即可；每个阶段有 `logs/*.official.done` 标记，
  每条评估结果逐行写入、已完成的跳过；ES 每轮原子保存状态。
- **预计时长（40 核）**：ES 6 个运行并行（每个 6 worker，500 轮）约 2.5–3.5 h；Test-A（含 N4fd 100 ms rollout）约 0.7 h；
  N4fd 1000 ms（20 天子集）约 0.7 h；Test-B/C/L + P4a/b + P3 约 0.5 h；WX-H 时延（dev，含 1000 ms rollout）约 1–1.5 h；
  **合计约 6–7.5 h**（上限估计 ≤10 h）。

## 4. 产出
- `results_final/SUMMARY_ZH.md`：每个测试集先给**完成率门槛表**，再给 H1（J，对每个可实现基线，Holm）、H2（makespan 对最强基线非劣，δ=2%）、
  次要指标、π 敏感性、权重敏感性、逐种子结果；天聚类检验 + 交叉 bootstrap +「确认」列。
- `results_final/ANALYSIS_V4.json`、各 `*_v4.jsonl` 原始逐例结果、`select_es_s*.json`（预注册选择记录）、`es_hist_*.jsonl`（训练曲线）。
- `results_out.tar.gz`：上面全部 + 最终模型 `models4/final_es_s*.npz` + 日志。把它发回来即可分析。
- 脚本**不会推送任何东西**到网络。

## 5. 目录
| 文件 | 作用 |
|---|---|
| `run_all.sh` | 单一入口（s1 N6 冻结 → s2 ES 训练+选择 → s3 Test-A → s4 Test-B/C/L → s5 P4/P3 → s6 WX-H → s7 分析打包） |
| `run_es.py` | ES-RL 训练（对偶扰动、共同随机数、中心化秩、Adam、断点续跑；未完成惩罚；固定迭代） |
| `select_es.py` | 预注册 dev 选择（100% 完成 + makespan 对最强 dev 基线非劣 → 最小 J） |
| `run_jobs3.py` | 可续跑的评估器 |
| `analyze_v4.py` | 统计与汇总（完成率门槛优先；复用 `analyze_v3.py` 的检验函数） |
| `wx2/sim.py` `wx2/const.py` `wx2/weather.py` | 仿真器 + **共享可行性层**（COMPLETE 模式，参数在 const.py 末尾） |
| `wx2/twin.py` | 公平 twin rollout（仿真内截止） |
| `data/instances/large`, `data/plans/test_large.jsonl` | Test-L 较大实例（生成种子 2026） |
| `models/rl_s{0,1,2}_best_pomo_v2.npz` | v2 服务器训练的 pomo_v2 策略（ES 初始化 & 基线 POMO_s*） |
