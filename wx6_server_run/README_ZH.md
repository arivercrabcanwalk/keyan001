# wx6_server_run — WX-E6 / RL6（论文 1：v5 升级版，扩展 Liu et al. EJOR 2026）

文档：`DESIGN_V6_ZH.md`（调研 + 设计 + 整改）、`PREREG_v6.md`（预注册）、`docs/PROTOCOL_FAIR_V6_ZH.md`（公平协议）。

## 服务器运行（RTX 3090 不需要；用 CPU，约 40 核）
```bash
git clone https://github.com/arivercrabcanwalk/keyan001 && cd keyan001/wx6_server_run
bash setup.sh                       # venv(numpy, scipy) + openjdk-17 检查/安装 + 克隆作者 LRPHSD + 编译 TSALNS-Cov
SMOKE=1 bash run_all.sh             # 可选：端到端冒烟（约 15–25 min），结果不正式
rm -rf logs models6 results results_final teacher data/plans6 PROGRESS_SERVER.md   # 冒烟后清理
nohup bash run_all.sh > run_all.log 2>&1 &     # 正式运行；中断后重复同一命令即可续跑
tail -f PROGRESS_SERVER.md                      # 进度（每阶段 START/DONE，带时间）
PUSH=1 bash run_all.sh                          # 全部完成后（或正式运行时就加 PUSH=1）把结果推回 wx6_server_run/results_server/
```
没有 sudo 装 Java 时：自行安装 JDK 17 后 `export JAVA=/path/bin/java JAVAC=/path/bin/javac`；已有作者仓库可 `export LRPHSD_DIR=/path/LRPHSD`。

## 旋钮（环境变量）
| 变量 | 默认 | 含义 |
|---|---|---|
| NCPU | 自动 | 工作进程 = NCPU − 2 |
| SEEDS_MAIN / SEEDS_ABL | "0 1 2 3 4" / "0 1 2" | 主模型 / 消融种子 |
| SHIELD | 1 | 班次护盾（ns 变体为无护盾消融） |
| TEACHER_BASE | RL5 | 第 0 轮 rollout 基策略 |
| T0_H / T1_H | 2.5 / 2.5 | 两轮老师墙钟预算（小时） |
| T_M / T_P | 8 / 0.5 | 老师孪生未来数 / 标签概率 |
| ES_ITERS / ES_POP / ES_BATCH | 250 / 20 / 16 | 约束 ES（预注册值，改动需另行声明） |
| PSECS / PSECS_L | 10 / 30 | TSALNS(-Cov) 每实例秒数 |
| PUSH | 0 | 1 = 结束后推送结果 |

## ETA（40 核）
计划 ≈ 0.2 h · dev 冻结 ≈ 0.5 h · 老师 ≤ 5 h · 蒸馏 ≈ 0.5 h · ES ≈ 8–9 h · 选择 ≈ 0.7 h · 测试 ≈ 2–3 h → **合计 ≈ 18–20 h**（上限 24 h）。

## 产出
`results_final/SUMMARY_ZH.md`（门槛表、H1/H2、逐种子、消融、泛化/稳健/选址/时延）、`ANALYSIS_V6.json`、`raw_compact.csv.gz`
（每行 map, day, method, seed, J5, cost, ot, late_h, late_n, fails, complete_strict, n_dabs, fixed_cost, latency…）、冻结文件、最终模型、`results_out.tar.gz`。
