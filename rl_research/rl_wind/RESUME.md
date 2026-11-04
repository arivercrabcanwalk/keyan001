# rl_wind — 风场 LRPHSD：RL vs TSALNS vs NoRL — RESUME
更新：2026-11-03 10:20 PST

## 规则
新目录 /workspace/rl_wind；不改原项目和检查点（engine 是从 rl_v3/engine 拷贝后打的补丁）；文件里不写密码。
Python：/workspace/rlproj/venv/bin/python，运行时加 PYTHONPATH=/workspace/rl_wind。

## 代码
- engine/：rl_v3 engine 的副本，打了风补丁（gdist 覆盖、非对称 2-opt），libcakernel.so 已重新编译
- rlv3/：rl_v3/rlv3 的副本（__init__ 指向 rl_wind/engine）
- wind/model.py：风物理、等效距离、make_planning_instance、情境采样、蒙特卡洛 simulate（不修正）
- wind/regress.py：回归测试（风=0 时结果一致）
- wind/cases.py：dev = rl_rt dev 20 个算例 × 2 个风情境；test = Liu 50 个算例 × 2 个风情境（固定种子）
- wind/headroom.py + analyze_hr.py：D2 诊断（results/hr_dev.jsonl）
- wind/online.py：在线按航次修正仿真；策略 none / margin / oracle / lookahead
- wind/hr_online.py：D3 诊断（results/hr_online.jsonl、hr_online_la.jsonl）

## 发现
见 /workspace/rl_v3/PAPER_FINDINGS.md 的 D 节

## 09:45–10:20 PST 进展
- 已完成的诊断：D2（余量 ≤0.5%）、D3/D4（按航次修正 0.02–0.16%）、D5（隐藏阵风状态 ≤0.08%）、D6（RL 未超过 margin 规则）
- 规划文件：results/plans_{train,dev,test,test_ts_nowind,test_ts_fc,dev_ts_nowind}.jsonl
- dev 调参：results/dev_norl.jsonl（margin/look/oracle/none）、dev_rl_f20.jsonl；用法 `python wind/tune.py P files...`
- RL 模型：models/pomo_f20/last.pt（wind/train_rl.py，20 维特征）；pomo_s0 是 18 维特征的旧版，与当前特征不兼容
- test 评估（10:15 PST 启动，nohup）：results/test_eval.jsonl、test_eval_ts_nowind.jsonl、test_eval_ts_fc.jsonl，日志 results/test_eval.log
  - 中断后重跑同一命令即可续跑（已完成的行会跳过）

## 原计划（设计 a）
1. 训练规划：生成算例 × 风情境，用 ALNS 在 r∈{0,0.05,0.1} 下规划
2. wind/rlpol.py：以 P 为条件的按航次修正策略，POMO 式共享基线 REINFORCE
3. NoRL：在 dev 上调 (r, m)；TSALNS：Python 版，按无风/预报风规划，不修正，也提供加 margin 修正的版本
4. test：Liu 50 × 2 个情境，配对 Wilcoxon + Holm 校正

## 09:40 PST（11-03）进展
- 设计 a 的 test 已跑完：结果在 results/final_tables_design_a.txt，见 PAPER_FINDINGS 的 D7
  - RL 远胜 TSALNS，但不胜 NoRL → 设计 a 判为 no-go
- 新设计 b'：强风区间（W 6–10 m/s，σ 1–3，gust 0.05–0.3）+ RL 自适应余量（上下文 bandit）
  - wind/model.py 中 STRONG 开关由环境变量 STRONG=1 控制
  - dev 上 oracle 余量空间：独立种子下 P=50 时 1.3%，P=100 时 2.1%（wind/an_strong.py，wind/resim.py）
- nohup 流水线（results/strong_pipe.log）依次运行：
  - hr_test_strong、hr_train_strong（ALNS，9 个余量档）
  - strong_dev_ts_fc、strong_test_ts_fc（TSALNS 10s，9 个余量档）
  - strong_test_ts_nowind
- 设计 c'（锋面过境 / 时变风，调整航次顺序）：wind/hr_front.py
  - 预知锋面时间的 oracle 重排比计划原顺序好 2.2%；比按预报时间（±30 分钟）重排好 1.9%
- RL 训练脚本：wind/rl_reserve.py

## 09:55 PST
- results/hr_train_strong.jsonl：训练集 600 个案例 × 9 档余量，已完成
- RL 模型：models/reserve/n600_s0.pt（rl_reserve.py，6000 次迭代，weight_decay）
  - dev（种子 B）上与 dev 内调的固定余量相比：P=25 +1.1%，P=50 +0.2%，P=100 −0.3%，P=200 +1.1%（正数表示 RL 更差）
  - 训练集内也只好 0.05–0.9%：oracle 的空间大多是规划噪声，从情境学不到
- 运行中（nohup）：
  - strong_pipe2：TSALNS 的 dev/test 预报风规划（10s），以及 test 无风规划
  - b011：test 上每档 0.111s 的规划，用于同等计算量下的 sim-select 对比
- 全部完成后：
  - 对 strong_dev_ts_fc、strong_test_ts_fc、strong_test_ts_nowind 跑 resim → *_rs.jsonl
  - 然后运行 wind/final_strong.py models/reserve/n600_s0.pt

## 10:20 PST
- b' 流水线（strong_pipe2，nohup）仍在跑：TSALNS 的 test 预报风规划，之后是无风规划
- 设计 c'：
  - 代码：wind/front.py（环境 + NoRL 规则：plan / static_fc / saa16 / ratioβ / rollout / rsaa，以及 oracle）
  - 诊断：wind/hr_front2.py → results/front_dev.jsonl，分析用 wind/an_front.py
  - dev 结果（J 相对计划原顺序）：

| 策略 | 相对计划原顺序 |
|---|---|
| static_fc | −0.62% |
| saa16 | −0.99% |
| ratio1 | −0.61% |
| rollout | −0.90% |
| rsaa | −0.98% |
| oracle | −1.64% |

  - RL 相对最佳 NoRL 的上界只有 0.65%
  - 成本含服务时间，与 model.simulate 一致
  - RL：wind/front_rl.py，模型 models/front/s{0,1}.pt（nohup 训练 1500 次迭代，日志 results/front_rl_s*.log）

## 10:50 PST
- b' 测试完成：results/final_tables_design_b.txt，见 PAPER_FINDINGS 的 D10（弱 go，仅 P=100 时成立）
- c' 测试（nohup，脚本 results/front_test.sh，日志 results/front_test.log）
  - 产出 results/front_test_{tsnw,tsfc,ours}.jsonl，以及 final_tables_design_c.txt
  - RL 用 models/front/s1.pt
- c' 的 dev 结果：RL 与 ratio 规则持平（均为 −0.61%）；saa16 为 −0.99%（更好）→ 预计 no-go

## 20:20 PST：b' 完整化
- c' 判为 no-go，见 PAPER_FINDINGS 的 D11
- 新增按机型分开的余量 (r_small, r_large)，6×6 网格
  - wind/model.py 中 make_planning_instance 已支持传入元组；headroom.py 用环境变量 TYPEGRID=1 开启
- dev 上（种子 B）的空间：
  - 最佳固定组合比最佳统一 r 好 1.5–2.6%，NoRL 同样能拿到
  - oracle 组合比最佳固定组合再好 1.5–4.2%
- nohup 流水线 type_pipe（日志 results/type_pipe.log）：hr_test_type → resim → hr_train_type（600 例）
- 20:45 PST：流水线已改为 results/type_pipe2.sh
  - test 用 36 个组合
  - 训练集 400 例，用 TYPEGRID=2 的 20 个组合，rs∈{.1,.2,.3,.4,.5}，rl∈{.05,.1,.2,.3}
- 新代码：
  - wind/rl_type.py：丰富特征 + 期望策略梯度 + P 条件化；环境变量 H/WD/ENT
  - wind/cv_type.py：在训练集上做交叉验证
  - wind/dev_type.py
  - wind/final_type.py：表格 + 多种子 + Holm
  - wind/pareto.py：生成 Pareto 图和 HV
- 统一 r 的 5 折交叉验证（训练集上）：RL 相对固定 r 在 +0.4% 到 −0.46% 之间 → 统一 r 下可学的空间约为 0
- 注意：box 上还有别的 agent 在跑 dyn/headroom.py，CPU 比较紧

## 21:50 PST：b' v2 完成，结论为 no-go（见 PAPER_FINDINGS 的 D12–D14）
- 模型：models/reserve/type_s{0..4}.pt
- 表格：results/final_tables_design_b2.txt
- 图：results/figs/pareto_strong_test.png；HV 在 results/pareto_strong.txt
- 数据：results/hr_{train,dev,test}_type*.jsonl
- 当前没有在跑的任务
