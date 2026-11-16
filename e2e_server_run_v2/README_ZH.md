# e2e_server_run_v2 — 全强化学习端到端（设计 A，GPU 优先）· 审查修复版

> 本目录 = `e2e_server_run/` + 审稿式自查后的修复（详见 `REVIEW_E2E_ZH.md`，偏离记录见 `PREREG_E2E.md` 末尾 D1）。
> **正式实验请用本目录**；旧目录 `e2e_server_run/` 保持不变，只用来拷出已经训练了 1 h 的路线模型检查点。

## 0. v2 相对 v1 的主要变化（全部在正式测试结果之前）
- RL 方法的早晨计划适配改由 π_route 完成（`e2e/rl_adapt.py`），启发式 repack 只当安全网并统计改动（F1）。
- 完成率改为与选址无关的 `complete_strict`；缺行或出错算未完成（F2）。
- 主基线在 dev 上从 TSALNS（预留 0/10/20%）× {A1, N6, Rfc, RfcP} 中选最强；新增 G2b（赢过所有非 RL 基线）；新增信息对等基线 TSj5（F3）。
- 新增不用 RL5 热启动的 PPO 消融 `ABL_scratch`（F4）；完整 2×2 析因，3 个 seed（F5）；静态评估不再丢掉失败的图，并报告最长用时（F6）。
- TSALNS 的 JVM 参数修复并记录 CPU 秒；没有 Java TSALNS 时正式运行直接退出；新增纯 CPU 静态臂；4.8 h 之后的路线课程加入 Liu 式 20 km 地图；修复 σ×1.5 场景；续训时 best.pt 不会被更差的模型覆盖。

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
**前置**：`sudo apt install -y openjdk-17-jdk-headless`（作者 TSALNS 基线必需；v2 正式运行检测不到 Java TSALNS 会直接退出）。

### 2.1 迁移已训练 1 h 的路线模型（不浪费已训的 1 h）
1 h 训练命令结束后再拷贝（`last.pt` 是原子写入的，也可以在训练中途拷，但最好等它结束）。如果旧目录里已经在跑 `run_all.sh`，先停掉它（`pkill -f run_all.sh; pkill -f route_train.py`），再拷贝。
```bash
cd keyan001 && git pull                       # 拿到 e2e_server_run_v2/
mkdir -p e2e_server_run_v2/runs/route
cp e2e_server_run/runs/route/last.pt e2e_server_run/runs/route/best.pt e2e_server_run/runs/route/curve.jsonl e2e_server_run_v2/runs/route/
# 可选：把 1 h 的训练日志一并带上
cp e2e_server_run/logs_route_1h.log e2e_server_run_v2/runs/route/ 2>/dev/null || true
```
- 不要拷 `DONE`、`final.pt`；也不要拷旧目录的 `data/plans/test_ts*.jsonl`，v2 会用新的 JVM 参数重跑 TSALNS，只要几分钟。
- `run_all.sh` 的 s2a 阶段发现 `runs/route/last.pt` 后会从 1 h 接着训到 2 h 门，学习率和课程仍按 12 h 总长来排。

### 2.2 安装与正式运行
```bash
cd e2e_server_run_v2
bash setup.sh                       # 建 .venv；有 nvidia-smi 自动装对应 CUDA 版 PyTorch；自动 clone 作者仓库并编译 TSALNS（需 javac：apt install openjdk-17-jdk-headless）
SMOKE=1 bash run_all.sh             # 冒烟测试（CPU 也可，约 15 分钟），检查环境；完成后删掉 runs_smoke/ logs/ results/ PROGRESS_SERVER.md 再正式跑
rm -rf runs_smoke logs results PROGRESS_SERVER.md runs/markers   # 注意：不要删 runs/route（迁移来的检查点）
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
| s1 作者 TSALNS 基线（100 图 × 44 s + 大图 + 电量预留 + dev 预留 0/10/20%） | CPU | ~0.4 h |
| s2 π_route（含 2 h 门）+ 小路由器 | GPU | 12 h + 1.5 h（迁移 1 h 检查点后还剩约 11 h + 1.5 h） |
| s3 π_site | GPU | 3 h |
| s4 计划生成 | GPU | ~0.7 h |
| s5/s6 π_exec PPO + π_site-J5 微调 × 3 seed，加 scratch PPO 1 个 | CPU 为主 | ≈ 12–14 h |
| s8b/s8c dev 选主基线 + TSj5 | CPU | ~0.5 h |
| s7–s9 测试计划 + 动态评估（5 场景 + 大图；v2 多约 12 个析因/基线臂） | CPU+GPU | ~6–9 h |
| **合计** | | **约 33–40 h**；迁移 1 h 检查点后剩余约 **32–39 h**（若 2 h 门停止，约 1.5–2 h 就结束）。这是按 40 核估算，没有实测；CPU 核数少会更久 |

## 4. 需要推回的结果
跑完（或门停止）后，把以下文件放进仓库 `e2e_server_run_v2/results_server/` 再推送（或直接发给我）：
- `results/e2e_results_*.tgz`（自动打包：所有表格、曲线、计划、日志）
- `results/*.md`、`results/*.json`、`PROGRESS_SERVER.md`
- 若门停止：`results/gate_route.json` + `runs/route/curve.jsonl`
- v2 新增：`results/primary_baseline.txt`/`.json`（dev 选出的主基线）、`results/dev_select.jsonl`
```bash
cd e2e_server_run_v2
mkdir -p results_server && cp results/*.md results/*.json results/*.txt results/*.tgz PROGRESS_SERVER.md results_server/ 2>/dev/null
cp runs/route/curve.jsonl results_server/route_curve.jsonl 2>/dev/null
git add results_server && git commit -m "e2e server results" && git push
```

## 5. 主要结果表
- `results/static_test_vs_ts.md`、`static_test_matched_{b}.md`、`static_fresh_matched_{b}.md`：静态成本 vs 作者 TSALNS（G1）。
- `results/dyn_test_{base,sigma15,ncbias,stress,uniform}.md`、`dyn_large.md`：J5、失败、加班、完成率、延迟、Wilcoxon+Holm、bootstrap CI、G2–G6、消融。

## 6. 目录
`e2e/` 代码 · `wx2/` 动态仿真（WX5 规则）· `vendor/lrphsd` 官方评估器 · `data/instances/{train,dev,test,large,fresh,fresh_large}` · `data/plans/{dev_ts,test_ts}.jsonl`（作者 TSALNS 10 s 计划）· `models_init/es_best_p5r_s0.npz`（RL5 热启动）· `baselines/tsalns_java` · `SMOKE_LOCAL.md`（v1 本地 CPU 冒烟结果）· `REVIEW_E2E_ZH.md`（审稿式自查与修复说明）· v2 新增 `e2e/rl_adapt.py` `e2e/dev_select.py` `e2e/ts_j5select.py`。
