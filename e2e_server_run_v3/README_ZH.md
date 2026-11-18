# e2e_server_run_v3 —— 纯端到端 RL（论文二）v3 服务器包

设计：`DESIGN_E2E_V3_ZH.md`；预注册：`PREREG_E2E_V3.md` + `gates_v3.json`。RL 方法内部不使用作者 ALNS。

## 1. 安装（RTX 3090 + ~40 核 + Java）
```bash
git clone https://github.com/arivercrabcanwalk/keyan001 && cd keyan001/e2e_server_run_v3
sudo apt-get install -y openjdk-17-jdk-headless      # 若无 javac
bash setup.sh            # .venv + torch(CUDA) + numpy/scipy；克隆作者仓库到 third_party 并编译打补丁的 TSALNS
# 或手动：LRPHSD_DIR=/path/to/LRPHSD bash baselines/tsalns_java/build.sh
```

## 2. 冒烟测试（CPU 即可，约 20–40 分钟）
```bash
SMOKE=1 bash run_all.sh && cat results/analysis_v3/ANALYSIS_V3.md | head -40
```

## 3. 全量运行（可断点续跑：重跑同一命令即跳过 *.done 阶段）
```bash
nohup bash run_all.sh > logs/run_all.log 2>&1 &
tail -f PROGRESS_SERVER.md
```
时间旋钮（环境变量）：`SEEDS="0 1 2 3 4" ROUTE_H=3 ROUTE_PAR=5 EXIT_ROUNDS=3 EXIT_DAYS=600 ES_ITERS=300 ES_H=3 J5_H=1.5 SITE_H=0.75 BUDGETS="1 3 10 30 60" TS_REPS=3 W=<核数-2>`；
可选 `ROUTE_INIT=<v2 runs/route/best.pt>`（暖启动，会记录在 state，论文需披露；默认不用）。

| 阶段 | 内容 | 资源 | 预计 |
|---|---|---|---|
| S0/S1 | G0、作者臂 TS-FIX/TS-CC/TS-CR/PAD（Java，各预算） | CPU | 与 S2 并行 ~1 h |
| S2 | π_route 5 seeds 并行 | GPU | ~3–4 h |
| S3 | 训练/开发图上的我们的计划 | GPU | ~0.3 h |
| S4 | π_exec 5 seeds（ExIt→ES）+ 2 消融；同时 S5 测试计划（GPU） | CPU | ~12–14 h |
| S6 | π_route-J5 5 seeds + 计划 | CPU+GPU | ~8 h |
| S7 | π_site 5 seeds + SimOpt（大图） | CPU | ~5 h |
| S8 | 动态评估（全部臂） | CPU | ~4 h |
| S9 | 分析/门槛/CSV/打包 | — | 分钟 |
| **合计** | | | **≈ 35–40 h** |

## 4. 结果回传
运行结束生成 `results/e2e_v3_results_<host>_<time>.tgz`（含 ANALYSIS_V3.md、raw_per_instance.csv、G0、全部 dyn jsonl、计划、曲线、最终 ckpt）。把 tgz 与 `PROGRESS_SERVER.md` 发回（或提交到 keyan001 的 `e2e_server_run_v3/results_server/`）。

## 5. 主要文件
`e2e/coverage.py`(CFL) · `e2e/verify_coverage.py`(G0) · `e2e/author_adapt.py`(TS-CR/PAD) · `baselines/tsalns_java/`(TS-CC/TS-FIX 补丁) ·
`e2e/route_train.py` · `e2e/plan_v3.py` · `e2e/lns.py:improve_v3` · `e2e/route_j5.py` · `e2e/site_v3.py` · `e2e/exec_v3.py` · `e2e/exec_train_v3.py` · `e2e/dyn_eval.py` · `e2e/analyze_v3.py`
