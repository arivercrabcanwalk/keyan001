# e2e_server_run — 全强化学习端到端（设计 A，GPU 优先）

**目标**：完全不用作者 ALNS，由强化学习生成全部决策（选址 + 路线 + 动态执行），在 100% 完成率前提下，用 J5 等评价指标与作者 TSALNS（同算力）对比。
预注册见 `PREREG_E2E.md`（门槛 G1–G6、测试集、天数、统计方法、2 h 早停规则），**正式运行前已写好，不得事后修改**。

## 1. 三层设计（全部是 RL 策略；RL 内部没有任何 ALNS）
| 层 | 方法 | 代码 |
|---|---|---|
| π_site 选址 | 自回归 Transformer 集合策略 + 覆盖掩码；REINFORCE + POMO 式共享基线 + 专家迭代；再以仿真 J5 为奖励微调（每 seed） | `e2e/site_model.py` `site_train.py` `site_search.py` |
| π_route 路线 | LEHD/BQ 重解码器（6 层编码 + 2 层重解码器，top-k 可行候选）、POMO 多起点、Sym-NCO ×8 增强、EAS-Emb；GPU bf16 大批训练，课程 35→150 | `e2e/route_*.py` |
| π_exec 执行 | RL5 + 学习的 REROUTE 动作（小路由器重建站内剩余路线）；PPO + GAE + 熵退火 + KL 早停 + 加班 Lagrangian（ot ≤ N6） | `e2e/exec_policy.py` `exec_ppo.py` |
- **RL 自有搜索（明确声明）**：站集邻域搜索（用 π_route 打分）、EAS（测试时梯度自适应）、j5 模式 top-k 站集用仿真 J5 重排。同时报告**纯策略**结果（`OURS_pure` / `OURS_sample` / `OURS_noEAS`）。
- 消融：`ABL_N6`、`ABL_RL5`、`ABL_noRR`（不用 REROUTE）、`ABL_B_online`（PARCO 式每次起飞在线重建）、`OURS_full_lns`（后备 C：学习修复 LNS）、`ABLP_*`（不同计划 + 我们的执行层）。
- 作者 TSALNS 只作基线：`baselines/tsalns_java`（作者原始 Java 代码 + 仅加时间预算/电量预留参数的补丁），预算 1/3/10/30 s 与我们同算力对比。

## 2. 运行
```bash
cd e2e_server_run
bash setup.sh                       # 建 .venv；有 nvidia-smi 自动装对应 CUDA 版 PyTorch；自动 clone 作者仓库并编译 TSALNS（需 javac：apt install openjdk-17-jdk-headless）
SMOKE=1 bash run_all.sh             # 冒烟测试（CPU 也可，约 15 分钟），检查环境；完成后删掉 runs_smoke/ logs/ results/ PROGRESS_SERVER.md 再正式跑
rm -rf runs_smoke logs results PROGRESS_SERVER.md runs/markers
nohup bash run_all.sh > run_all.out 2>&1 &   # 正式运行（可断点续跑：再次执行同一命令即可，已完成阶段自动跳过）
tail -f PROGRESS_SERVER.md          # 进度
```
- 可调参数（环境变量）：`ROUTE_H=12 GATE_H=2 SITE_H=3 SITEJ5_H=2 SMALL_H=1.5 EXEC_H=2 PPO_ITERS=400 SEEDS="0 1 2" W=<CPU 核数-2> PLAN_B=10 BUDGETS="1 3 10 30"`。
- 指定 GPU：`CUDA_VISIBLE_DEVICES=0`；强制 CPU：`E2E_DEVICE=cpu`。Java 不在 PATH 时：`JAVA=/path/java JAVAC=/path/javac`。作者仓库已在别处：`LRPHSD_DIR=/path/LRPHSD`。
- **2 h 早停门**：π_route 训练 2 h 后 `gate.py` 外推 12 h 的路线 gap；若 > +1.0%（相对 TSALNS 路线）或无改善，流程以 exit 10 停止并写入 `results/gate_route.json`——请把这个结果推回来，我们再调整。
- 每阶段都有检查点（last.pt / best.pt）与完成标记（`runs/markers/*.done`），中断后重跑同一命令即可续跑。

## 3. 预计时间（1 张 GPU + 40 CPU 核）
| 阶段 | 资源 | 时间 |
|---|---|---|
| s1 作者 TSALNS 基线（100 图 × 44 s + 大图 + 电量预留） | CPU | ~0.3 h |
| s2 π_route（含 2 h 门）+ 小路由器 | GPU | 12 h + 1.5 h |
| s3 π_site | GPU | 3 h |
| s4 计划生成 | GPU | ~0.7 h |
| s5/s6 π_exec PPO + π_site-J5 微调 × 3 seed | CPU 为主 | (≤2 h + 2 h) × 3 ≈ 10–12 h |
| s7–s9 测试计划 + 动态评估（5 场景 + 大图） | CPU+GPU | ~3–4 h |
| **合计** | | **约 27–32 h**（若 2 h 门停止，则只需约 2.5 h） |

## 4. 需要推回的结果
跑完（或门停止）后，把以下文件放进仓库 `e2e_server_run/results_server/` 再推送（或直接发给我）：
- `results/e2e_results_*.tgz`（自动打包：所有表格、曲线、计划、日志）
- `results/*.md`、`results/*.json`、`PROGRESS_SERVER.md`
- 若门停止：`results/gate_route.json` + `runs/route/curve.jsonl`
```bash
mkdir -p results_server && cp results/*.md results/*.json results/*.tgz PROGRESS_SERVER.md results_server/ 2>/dev/null
git add results_server && git commit -m "e2e server results" && git push
```

## 5. 主要结果表
- `results/static_test_vs_ts.md`、`static_test_matched_{b}.md`、`static_fresh_matched_{b}.md`：静态成本 vs 作者 TSALNS（G1）。
- `results/dyn_test_{base,sigma15,ncbias,stress,uniform}.md`、`dyn_large.md`：J5、失败、加班、完成率、延迟、Wilcoxon+Holm、bootstrap CI、G2–G6、消融。

## 6. 目录
`e2e/` 代码 · `wx2/` 动态仿真（WX5 规则）· `vendor/lrphsd` 官方评估器 · `data/instances/{train,dev,test,large,fresh,fresh_large}` · `data/plans/{dev_ts,test_ts}.jsonl`（作者 TSALNS 10 s 计划）· `models_init/es_best_p5r_s0.npz`（RL5 热启动）· `baselines/tsalns_java` · `SMOKE_LOCAL.md`（本地 CPU 冒烟结果）。
