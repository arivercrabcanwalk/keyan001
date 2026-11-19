# rlv3_weather —— 原论文场景 + 天气（风场物理能耗 + 移动雷暴禁飞区）

rlv3 系列（以后修改依次叫 rlv4、rlv5…）。本文件夹**完全自包含**：作者的 TSALNS 源码（含官方读取/评估器）、地图、测试/dev 方案、模拟器、所有基线、RL、单元测试、分析脚本。
设计说明见 `DESIGN_ZH.md`。另一篇论文的包是 `rlv3_emergency/`，两者互不依赖。

## 1. 安装（一次）
```bash
cd rlv3_weather
bash setup.sh                      # 建 .venv，装 torch(默认 cu128，适配 3090/4090/5090) + numpy/scipy/pytest，检查 javac
# 其他 CUDA：TORCH_INDEX=https://download.pytorch.org/whl/cu121 bash setup.sh
# 纯 CPU：  TORCH_INDEX=https://download.pytorch.org/whl/cpu bash setup.sh
```
需要：Python ≥3.9、Java JDK ≥11（`javac`，用于编译作者 TSALNS；Ubuntu: `sudo apt install openjdk-17-jdk-headless`）。

## 2. 运行
```bash
SMOKE=1 bash run_all.sh            # 先跑冒烟（本地 8 核 CPU 约 7–10 分钟），必须看到 ALL DONE
bash run_all.sh                    # 正式实验（可断点续跑：中断后重跑同一命令即可，已完成阶段自动跳过）
```
常用环境变量：`W`（CPU 进程数，默认 核数-2）、`DEVICE`（cuda/cpu，默认自动）、`SEEDS`（默认 "0 1 2"）、
`RI_H`（每个种子的滚动改进阶段小时数，默认 2）、`RL_H`（每个种子策略梯度小时数，默认 1）、`ABL_H`（每个消融的 RI 小时数，默认 1，另加 0.5 h PG）、`TS_SECS`（训练图 TSALNS 每图秒数，默认 10）。
同一台机器同时跑两篇论文：`W=14 bash run_all.sh` 在两个文件夹里各起一个（把核数对半分）。
进度：`PROGRESS_SERVER.md`（每阶段开始/结束/失败），日志：`logs/`。

## 3. 阶段
| 阶段 | 内容 |
|---|---|
| s0 | 环境检查；编译作者 TSALNS |
| s1 | 单元测试：零风能耗与作者完全一致（解析 + 积分 + 70 张图官方评估器逐图相等）、屏蔽永不导致不可行、所有方法 100 % 完成、无额外开站、可复现 |
| s2 | 作者 TSALNS 求解 200 张训练图 + 50 张 fresh 图（测试/dev 方案已随包提供，即作者 10 s 方案） |
| s3 | 在 dev 上为每个非 RL 基线调参（风险余量/等待阈值），自动选出最强非 RL = 教师 |
| s4 | RL：行为克隆 → 滚动改进（近似策略迭代 + DAgger）→ 多 rollout 策略梯度；3 个种子 + 消融 |
| s5 | 测试：50 张作者测试图 × 100 天（主场景）+ 附加场景 + fresh 新图，全部方法配对 |
| s6 | 分析：`results_full/report_*/REPORT.md`、`table.tex`、`gates.json`、`per_episode.csv`，并打包 `rlv3_weather_full_results.tar.gz` |

## 4. 时间估计（正式实验）
RL 各阶段按 **墙钟时间预算** 运行（不因机器快慢而变长），机器越强，同样时间内训练越多。
| 阶段 | 32 核 CPU + 3090/5090（估计） | 说明 |
|---|---|---|
| s0–s3 | 约 15–30 min | TSALNS 250 图 × 10 s / W；调参 20 图 × 20 天 |
| s4 每个主种子 | 约 3.3 h（BC 采样+训练 ~15 min，RI 2 h，PG 1 h） | 3 个种子串行 ≈ 10 h |
| s4 消融 | 每个约 1.7 h | 3 个：ABL_nophys / ABL_eta / ABL_nobase ≈ 5 h |
| s5–s6 | 约 0.5–1 h | |
| **合计** | **约 16 h** | 5090 与 3090 墙钟时间基本相同（时间预算制；模拟器在 CPU 上），5090 在同样时间内完成更多梯度步 |
纯 CPU（无 GPU）也能跑：BC 训练会慢（可设 `DEVICE=cpu`，预计 BC 多 1–2 h），其余不变。核数少于 16 时建议 `RI_H=3`。
以上为根据本地 8 核 CPU 试跑速度外推的估计，不是实测。

## 5. 公平性与诚实性
* 所有方法使用作者方案的同一组站点、机队与计划分配 → 固定成本逐图相同（闸门 G1 自动检查）；不存在“多开站”获益。
* 严格 100 % 完成：没有跳过/拒单动作，episode 只在全部任务完成后结束（G0）。
* 测试种子与训练/dev 完全分开；非 RL 基线也在 dev 上调参；RL 的检查点只用 dev 选择。
* 报告里所有数字都来自 `results_full/`；若 G2/G3 未通过，按原样报告。
