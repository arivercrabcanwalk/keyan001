# rl_v3 进度与续跑命令（最近更新：11-03 05:20 PST）

目录：/workspace/rl_v3。原项目只读；引擎副本在 engine/（MAXSLOT=5）。$P = /workspace/rlproj/venv/bin/python
注意：AwaitShell 期间读到的文件行数可能是旧的，以 shell 里 sleep 之后再 wc 的结果为准。

## 状态
- **闸门 1：** 通过（PAPER_FINDINGS B1）。
- **闸门 2：** 未通过（B2–B4）。
  - 候选过滤、目标级 BC 策略、RL 微调（组内基线 PPO，不用 critic），都没能稳定超过冷温 NoRL 的 best-of-4 或 best-of-8。
  - 开发集结果都在 results/dev/。对比命令：$P rlv3/cmp_dev.py BASE.jsonl OTHER.jsonl
- **后台（已重启）：** run_m1_baselines.sh 在测试集（Liu 50 个算例）上跑 norl:8、norl_m4、norl_m1，覆盖 7 个 λ 和 10% 余量，3 个种子。
  - 输出 results/base_*.jsonl，完成后生成 results/base.done（约 1.5 小时）。
  - 断点续跑：nohup ./run_m1_baselines.sh > results/run_m1.log 2>&1 &

## 可选的下一步（等用户决定）
- **A. 写成"学习增强框架"（写法 A）：** 用 base_norl_8 加余量，和 TSALNS_w 对比 HV、MK@1%、λ=1/2、短预算、余量成本。还需要补跑 0.3s/1s 短预算：
  $P rlv3/bench.py norl:8 results/short_norl8_T0.3.jsonl 0,0.05,0.1,0.2,0.5,1,2 0 101,102,103 0.3 8
  TSALNS_w 的结果在 /workspace/rlproj/results/tsw_s10{1,2,3}、tsrsv_*、s2tsw_* 下，可直接复用。
- **B. 继续找 RL 的突破口（未做）：**
  - F2：λ>0 时用 RL 决定停滞重启；
  - 自适应 K：每步修复几个候选由 RL 决定；
  - 站点级选择（钩 _wchoice）。
  - 注意：C 的诊断提示，这几项都可能被静态调参追平。
- **训练和评估命令（备用）：**
  - $P rlv3/train_tp.py --seed S --iters 60 --bc-iters 4 --out models/tp/sS [--algo a2c|ppo_critic] [--nocond] [--bc-iters 0]
  - $P rlv3/bench.py tp:models/tp/sS/last.json[:M8] OUT.jsonl LAMS 0 SEEDS 6 8   （测试集；加 SET=dev 则跑开发集）
