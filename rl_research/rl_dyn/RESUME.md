# rl_dyn — 场景 E：LRPHSD + 在线紧急任务（RL vs TSALNS vs NoRL）— RESUME
Python: /workspace/rlproj/venv/bin/python，运行时 `cd /workspace/rl_dyn && export PYTHONPATH=/workspace/rl_dyn`
engine/、rlv3/ 是 rl_v3 的副本（只读使用）。不改原项目。CPU ≤4 线程。

## 场景（dyn/sim.py）
静态 LRPHSD 计划（我们的 ALNS lam=0.5 1s / TSALNS 10s cost-only）+ 白天在线紧急请求（Poisson，H=240min，期望 nt/3 个；
70% 的天有隐藏热点（60% 请求来自热点）；40% 高优先级 deadline 15min，其余 30min）。紧急请求由开站的无人机单独往返，
优先于计划航次（飞行中不可打断）。决策：无人机回站时"发下一计划航次"或"待命 5 分钟"（hold）。
J = 固定+0.5·忙碌时间 + 0.5·计划 makespan + 30·高优先迟到 + 10·普通迟到（无站覆盖=迟到）。

## 文件
- dyn/plan.py：计划 → plans/{train,dev,test}_ours.jsonl（lam=0.5,1s）、{dev,test}_ts.jsonl（TSALNS 10s）
- dyn/pol.py：myopic / static(T)（CFA 式保留，Beraldi 2024）/ adaptive / slack / rollout(M)（已知生成模型+精确后验）/ clairvoyant
- dyn/simts.py：TS-insert = 作者算法在线化（成本最小插入，无优先级）
- dyn/headroom.py, summ.py：诊断（results/hr1.jsonl, hr2.jsonl）
- dyn/feat.py, rl.py, train.py：RL（MLP 22 维特征，REINFORCE + POMO 式共享基线 K=8，BC 预热到 static120 标签平滑）
- dyn/evaluate.py, stats.py：评估与 Wilcoxon+Holm
## 进度
- 2026-11-03 21:00 PST：诊断完成（见 PAPER_FINDINGS E 节），go。训练 models/pg_s0（nohup，log results/train_pg_s0.log）
- 21:10 PST：API（优势回归，models/api_s0）it0 dev 比 static120 差 0.53%，it1 太慢已停（负结果，作消融）。
- PG s0（models/pg_s0, it360）test：J 比 dev 选出的 static240 低 1.79%（46/4, p_holm 6e-12），makespan −30%；但准时率低 2.7 点。
  比 test 上事后最好的 slack240 低 1.2% J，准时率 +4.4 点，高优先 +6.8 点。结果：results/test_main.jsonl、test_pgs0.jsonl
- 21:12 PST：启动 3 个独立种子 PG（models/pg_r10/11/12，同 pg_s0 配置，选 dev 最好 best.pt），日志 results/train_pg_r*.log
- 待办：test 评估 3 种子；rollout M=1/2/8/32 test 参考（roll32 只跑 3 个种子）；写 E3+。
- 21:45 PST：3 种子 PG test 完成（results/test_main.jsonl）；rollout test 运行中 results/test_roll.jsonl（roll1/2/8 10 种子，roll32 3 种子）；fine-tune models/pg_r11ft、pg_r12ft 运行中。dev 30 种子调参（results/dev_norl30.jsonl）选出 static30 为公平 NoRL
- 22:10 PST：rollout 基策略改为 dev 最优 static30（rollb30_M），results/test_rollb30.jsonl；旧 roll*（static120 基）在 test_roll.jsonl（roll32 只完成 133/150 天）。ppo.py：PPO/A2C(GAE)、PPO-POMO(共享基线)、attn 编码、api 初始化；运行 models/pp_mlp, pp_attn, pp_api
- 22:55 PST：PPO-POMO 三个已完成；启动 GAE 消融 models/ppo_gae, a2c_gae, ppo_gae_attn（λ=1，0.5h）
- 23:20 PST：dev 上全部 RL 变体都优于 static30（results/dev_rl.jsonl）；最终 RL 选 REINFORCE-POMO MLP 3 种子(pg_r10/11/12)；test30 消融评估运行中 (results/test30.jsonl, log test30b.log)
- 23:50 PST：全部完成。结果：results/final_E_main.txt、final_E_rollout.txt、final_E_ablation.txt；PAPER_FINDINGS E3–E7 已写。
- 11-03 23:07 PST：新增作者基线 (A3) TS-reopt：dyn/simreopt.py（TSALNS 路由层滚动重优化，冻结站点/在飞航次/就绪时刻；sec=0 时与 A2 完全一致=自检通过）、dyn/eval_reopt.py。
  命名：A1=ts_myo（TSALNS 计划+最早到达/空闲机派单，计划不变）；A2=ts_ins（TS-insert）；A3=reopt_ev_1 / reopt_ev_3 / reopt_p10_1。
  nohup 运行：results/test_reopt.jsonl（log test_reopt.log），test 50 算例 × 3 事件天（seed 5000–5002，=150 天子集，算力限制），3 workers。
  完成后：python dyn/e8.py 生成 results/final_E8.txt，写 PAPER_FINDINGS E8。
- 11-04 00:05 PST：test_reopt 完成（450/450）。results/final_E8.txt（dyn/e8.py 5000-5002）。PAPER_FINDINGS E8 已写。
  结论：作者组最强为 A1；RL3 对 A1/A2/A3 在 J、准时、高优先、响应上均显著胜出；对 static30 在 150 天子集上不显著（J +0.46%，p_H=1），需引用 E4 的 30 天结果。
  可选后续：把 reopt_ev_1 扩到种子 5003–5029（约 1 h × 9 / 3 worker），得到 30 天全量 A3。
- 11-04 00:05 PST：nohup 扩展 reopt_ev_1 到种子 5003–5029 → results/test_reopt30.jsonl（log test_reopt30.log，1350 任务，3 worker，可断点续跑：重跑同命令即跳过已完成）。ts_myo 已有 30 天。完成后 python dyn/e8.py 5000-5029 > results/final_E8_30d.txt
- 11-04 01:55 PST：A3-1s 30 天完成（test_reopt30.jsonl 1350/1350）。dyn/e8.py 改为按共有 (算例,天) 配对；results/final_E8_30d.txt；PAPER_FINDINGS E8（续）30 天主表已写。A1(ts_myo) 本来就有 30 天。E 线全部完成。
