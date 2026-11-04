# rl_rt — 构造式 RL（毫秒级实时重规划）RESUME
更新：2026-11-03 06:20 PST（06:25 再更新）

## 规则
只在 /workspace/rl_rt 新目录工作；不改原项目/检查点；文件里不写密码；rl_v3 基线保持运行
（重启：`cd /workspace/rl_v3 && nohup ./run_m1_baselines.sh > results/run_m1.log 2>&1 &`，结束时写 results/base.done）。
Python：/workspace/rlproj/venv/bin/python；numba 装在 /workspace/rl_rt/pylib（--target，没动 venv），rt/fast.py 自动加入 sys.path。无 GPU。

## 代码
- rt/inst.py  Liu 参数常量、生成器 gen(n,ns,rng)、from_lrphsd
- rt/env.py   批量构造环境（torch）。掩码：覆盖半径、含返航电量（容量/(1+r)）、累计工作时长、SABS/DABS 互斥、SABS 不得孤立仅本站 5km 可覆盖的目标
- rt/model.py 异构注意力编解码（目标 + 站×机型 token），FiLM 条件化 κ、r；rollout()
- rt/train.py --algo pomo（多样本共享基线 REINFORCE）| a2c（critic 基线消融）；--nocond 消融
- rt/fast.py  毫秒推理：torch 编码 + numba 解码；rt/check_fast.py 验证与 torch 动作完全一致
- rt/infer.py torch 推理（greedy / sample:N / aug8 / aug8s:N）
- rt/solution.py 动作序列 → 官方解格式；rt/check.py 用官方 evaluator 验证（成本误差 <2e-4，全部可行）
- rt/make_dev.py 生成 20 个留出 dev 算例 instances/dev/d{ns}_{n}_{1..4}.txt（seed 777）
- rt/ref_alns.py dev 参考：`ref` 阶段 = norl_8 10s ×2 种子（λ=0,0.5）+ Python TSALNS 30s；`budget` 阶段 = norl_m1/m4 在 0.01–1s
Liu 50 个测试算例只用于最终测试，不用于选模型。

## 运行中
- 训练：pomo_s0 (B=16, 05:24–05:48 PST, 400 it) → 续训 `nohup python rt/train.py --out models/pomo_s0b --resume models/pomo_s0/last.pt --B 64 --lr 5e-4 --hours 3 --threads 4 > models/pomo_s0b.log &`（05:49 PST 起）
  断了就续：加 `--resume models/pomo_s0/last.pt`
- 参考：`nohup python rt/ref_alns.py results/dev_ref.jsonl 2 ref > results/dev_ref.log &`（可断点续跑）

- rt/search_ws.py = rl_v3 search4 的副本，加了 init_sol（warm start）和 mk_w_override
- rt/gonogo.py CKPT OUT：RL 各模式 + warm start（RL aug8 → ALNS m1，总预算 50/100/300ms）；rt/report.py 汇总差距
- rt/dynamic.py CKPT dev|test OUT：场景 2（能耗突增 10/20%、新增 10% 目标、站点故障），ONLY=name 只跑单个算例
- 已有结果：results/dev_ref.jsonl（参考）、results/dev_budget.jsonl（ALNS 0.01–1s）、results/gonogo_s0b_it100.jsonl（早期检查点）

## 06:25 PST 状态
- rl_v3 基线已全部完成（results/base.done 存在），无需重启；dev_ref / dev_budget 也已完成（.done）。
- pomo_s0b 训练仍在跑（pid 见 `pgrep -af train.py`），纯 RL 学得很慢（≈400 it 后 dev 贪心 F 基本持平）。诊断：策略熵很低（每步约 0.1–0.2 nat），同一批算例反复训练 60 it 也只降 2.5%。
- 新增 BC 预热（行为克隆 ALNS 1s 解，然后 POMO 微调）：
  - 示范生成：`nohup python rt/gen_demo.py data/demo.jsonl 0 6000 4 > data/demo.log &`（可续跑，完成写 data/demo.jsonl.done）
  - 示范在 env 掩码下 150/150 合法，env 目标值与 ALNS 目标值误差 3.6e-7
  - BC 训练（06:37 PST 起，示范快照 data/demo_snap1.jsonl 6.7k 条）：`DEMO=data/demo_snap1.jsonl nohup python rt/train_bc.py models/bc0 9 4 > models/bc0.log &`；纯 RL pomo_s0b 已在 06:24 PST 停止（平台期，作消融）
  - 然后 RL 微调：`python rt/train.py --out models/bcrl0 --resume models/bc0/best.pt --B 64 --lr 2e-4 --hours 1.5 --threads 4`

## 06:55 PST 状态
- 普通 BC（固定顺序，models/bc0）失败：每步 NLL 1.7，贪心解比纯 RL 还差，原因是顺序歧义。
- 改用顺序不变 BC（rt/train_bc2.py，对与示范一致的动作集合取 logsumexp），每步 NLL 仍有 1.38。
- 诊断（/tmp/diag.py）：连"行程内下一个目标"都预测不好（NLL 1.8，约 24 个候选）。说明模型缺少显式距离信息。
- 已加入距离感知偏置（DAR 思路）：model.wa/wl × [d(last,j), d(站,j), d(last,token站)]/5000。fast.py 已同步，check_fast 动作一致。
- 旧检查点用 rt.model.load_policy() 加载（wa=wl=0，行为与原来完全一样）。
- 运行中：
  - `DEMO=data/demo_snap2.jsonl nohup python rt/train_bc2.py models/bc3 12 4 > models/bc3.log &`
  - `nohup python rt/train.py --out models/pomo_d --B 64 --lr 5e-4 --hours 2 --threads 3 > models/pomo_d.log &`（纯 RL + 距离偏置）
- 示范已生成完：data/demo.jsonl 6000 条 + demo2.jsonl 约 2.4k 条 = data/demo_snap2.jsonl
- BC3 结束后：`nohup python rt/train.py --out models/bcrl3 --resume models/bc3/best.pt --B 64 --lr 2e-4 --hours 1.5 --threads 4 > models/bcrl3.log &`

## 07:09 PST
- bc3 已完成：val NLL 0.996（加距离偏置前为 1.38），dev 贪心 F 与纯 RL 相近。
- bcrl3 已启动：`nohup python rt/train.py --out models/bcrl3 --resume models/bc3/best.pt --B 64 --lr 2e-4 --hours 1.0 --threads 4 > models/bcrl3.log &`，约 08:10 PST 结束。
- pomo_d 计划到 08:54 PST，约 08:10 PST 时用它的 best.pt 一起评估。
- 评估：`python rt/gonogo.py models/X/best.pt results/gonogo_X.jsonl && python rt/report.py results/dev_ref.jsonl results/dev_budget.jsonl results/gonogo_X.jsonl`

## 07:42 PST 第一次 go/no-go 已完成（见 PAPER_FINDINGS C5）
- 结果：单独 RL 为 no-go（差距 8–14%，ALNS 在 50–300 ms 时只有 1–4%）；warm start 小幅改善，但大多不显著。
- bcrl3（到约 08:10 PST）和 pomo_d（到约 08:54 PST）仍在后台训练；结束后可以对 best.pt 重跑 gonogo。
- 待用户决定方向后再做 Liu-50 测试 / 动态事件（rt/dynamic.py 已就绪）/ A2C 消融。

## 下一步
1. 训练完：`python rt/gonogo.py models/pomo_s0b/best.pt results/gonogo_s0b.jsonl && python rt/report.py results/dev_ref.jsonl results/dev_budget.jsonl results/gonogo_s0b.jsonl`
3. 汇报 go/no-go；然后做 Liu-50 测试、预算曲线、动态事件、warm start、A2C 消融
- 08:13 PST：bcrl3 已训完（models/bcrl3/best.pt、last.pt）；pomo_d 在 it≈1850 时主动停止（平台期，models/pomo_d/best.pt、last.pt）。转入 rl_wind 阶段。
