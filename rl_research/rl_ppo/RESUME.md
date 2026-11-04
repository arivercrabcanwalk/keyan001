# rl_ppo — PPO/A2C 动态算法配置（DAC）控制 ALNS：RL vs NoRL（RESUME）
目录 /workspace/rl_ppo（新目录，原项目只读）。Python=/workspace/rlproj/venv/bin/python。≤4 线程（rl_dyn 并行）。
## 代码
- ppo/dac.py  段级 DAC 引擎：同 rl_v3 search4 的算子/修复/评估器/冷温 SA/best-of-M；运行分 S=10 段，每段由控制器选
  cfg=(温度档 T, M=best-of-K, 算子族, 破坏强度, 重启到最优)。预算 = 确定性工作量单位 units=steps+evals（标定：步开销≈一次修复评估），控制器每次决策另计 2 单位。
- ppo/specs.py 规格串：norl:M（rl_v3 NoRL 复刻）、s:T,M,I 静态、p:A/B@f 两阶段、r: 反应式规则；units(sec,n)= sec*1e6/(45+0.7n)（标定 results/calib.json）
- ppo/grid.py OUT SPECS INSTSET LAMS SEEDS SECS [W]  可断点续跑
## 进度
- 11-04 05:3x（box 时钟）：stage1 静态网格诊断（38 个规格 × tune4 20 例 × λ{0,0.2,1} × 2 种子 × 0.3s/1s）
  nohup python ppo/grid.py results/stage1.jsonl "$(cat results/stage1_specs.txt)" tune4 0,0.2,1 0,1 0.3,1.0 4 > logs/stage1.log 2>&1 &
- stage1 完成（results/stage1.jsonl，9120 次）。CV 空间（ppo/headroom.py）：全局单一静态 −0.33%，按 λ 选 −0.71%，按 (λ,预算) −0.56%，按算例 −0.35%（相对所有配置均值）。
  λ=0 最好是热温 T=0.03+M=8；λ=0.2 最好是反应式 r:1,3,1（停滞→重启到最优+高强度）；λ=1 是 M=2 或 norl:1。→ 最优配置依赖 λ，且反应式控制有价值。
- stage2（两阶段/反应式 vs 静态，4 个新种子 2–5）：
  nohup python ppo/grid.py results/stage2.jsonl "$(cat results/stage2_specs.txt)" tune4 0,0.2,1 2,3,4,5 0.3,1.0 3 > logs/stage2.log 2>&1 &
- PPO 试训 ppo_p0（heads T,M,I,R；W=2；6h）：
  nohup python ppo/train.py --out models/ppo_p0 --algo ppo --heads T,M,I,R --ninst 12 --G 4 --W 2 --hours 6 --iters 2000 --seed 0 > logs/ppo_p0.log 2>&1 &
  续训加 --resume models/ppo_p0/last.pt
- 注意：box 时钟是 UTC（06:12 UTC = 22:12 PST）。stage2 与 ppo_p0 于 06:12 UTC 启动。
- 测试统计脚本 ppo/final.py SEC REF LABEL=file[:spec] ... [TS]（TS = rlproj s2_json_T0.3/T1 的 TSALNS_w，5 个 λ，种子 101）。
- grid.py 支持 spec "rl:/path/ckpt.pt"（贪心）或 "rl:/path:sample"。
## 里程碑（07:15 UTC）
- stage2 完成（11040）。动态（两阶段/反应式规则）相对按 (λ,预算) 选的最佳静态，CV 空间仅 −0.067%（p=0.055，ppo/dynhead.py）；
  按 λ 选 vs 全局单一配置：stage1 −0.38%，stage2 −0.13%。→ 低于 0.5% 门槛；RL 唯一现实空间是"λ/预算条件化 + 反应式"对单一全局静态。
- ppo_p0 已停（学太慢），改 ppo_p1（组内留一均值基线 + GAE，lr 1e-3）运行中（W=2，8h）。
- 07:15 UTC 启动：ppo_s1、a2c_s0、rf_s0（各 W=1，3h）。断了用 --resume models/X/last.pt 续：
  python ppo/train.py --out models/ppo_s1 --algo ppo --heads T,M,I,R --ninst 4 --G 8 --W 1 --lr 1e-3 --ent 0.003 --hours 3 --iters 3000 --seed 1
  （a2c_s0: --algo a2c --seed 0；rf_s0: --algo reinforce --seed 0）
## 07:40 UTC
- dev 快照（ppo_p1 ~it120，results/dev_snap1.jsonl）：RL 对 norl:4 −0.44%（p=7e-5），对 r:1,3,1 −0.22%（p=0.22），λ=0 时最明显（−0.76%/−0.45%）。
- 公平 NoRL："tuned" = 在 tune4（训练侧生成算例）上按 (λ组, 预算) 从 61 个人工配置（静态/两阶段/反应式）中选最好的，见 results/norl_tuned.json；全局单一最优 = r:1,2,1。
- 测试集 NoRL 运行（W=1）：nohup python ppo/grid.py results/test_norl.jsonl "tuned;r:1,2,1;norl:4" test 0,0.05,0.1,0.2,0.5,1,2 101,102,103 0.3,1.0 1 > logs/test_norl.log 2>&1 &
- 07:45 UTC 启动 ppo_s2（同 ppo_s1，--seed 2）
- F 节草稿：/workspace/rl_ppo/F_draft.md（最后合并进 PAPER_FINDINGS）
## 08:47 UTC 里程碑
- 训练全部停止（按用户要求减负）。最终检查点 models/final/{ppo_p1,ppo_s1,ppo_s2,a2c_s0,rf_s0}.pt
  样本量：ppo_p1 371 it×48=17.8k 回合；ppo_s1 174×32=5.6k；ppo_s2 138×32=4.4k；a2c_s0 175×32=5.6k；rf_s0 175×32=5.6k。
- 测试 RL：nohup python ppo/grid.py results/test_rl.jsonl "<5 个 rl:models/final/*.pt>" test 0,0.05,0.1,0.2,0.5,1,2 101,102,103 0.3,1.0 3 > logs/test_rl.log 2>&1 &
- test_norl 仍在跑（W=1）。完成后：python ppo/final.py 0.3 NoRL_tuned NoRL_tuned=results/test_norl.jsonl:tuned ... TS
- 09:08 UTC：开环蒸馏消融 results/distill_p1.json（ppo_p1 在 dev 上每段动作众数），测试 results/test_distill.jsonl
- 09:40 UTC：test_rl 完成（10500）、test_norl 完成（6300）
## 09:55 UTC 完成
- test_distill 完成（2100）。最终统计 results/final_{0.3,1.0}.txt（vs NoRL_tuned，Holm 102 项）、final_vsglob_*、final_vsv3_*。
- F 节已合并进 /workspace/rl_v3/PAPER_FINDINGS.md（F0–F5）。结论：弱 go（PPO 在 1s λ=0 成本、0.3s F(λ=1) 上 Holm 显著胜 NoRL_tuned；HV/MK@1% 不显著；收益可被开环蒸馏复现）。
