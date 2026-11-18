# e2e_server_run_v2 服务器结果（bdb6506）

## 运行

- GPU 机 E：RTX 3090 24GB / 20 核 cgroup；route、small route、site、exec、site-J5
- CPU 机：40 核 cgroup / 200GB；动态测试、large maps、分析
- 迁移：v1 的 `runs/route` 检查点（1.18h）续训；route 12h 完成 10,363 iter
- 3090 适配：route 阶段 `--chunk 8`；batch/N/aug/seed 未改
- v2 修复：`run_tsalns.py` 补回缺失的 `--reserve` 参数
- dev 选出的主基线：**TS_RfcP**

## 总体结论

**J5、G2b、G5、G6 全部通过；G1 静态通过；但 G3（严格完成率）在 5 个主场景全部 FAIL，G4（失败数）在 sigma15/stress 等场景 FAIL。因此不能声称“所有 pre-registered gates 通过”。**

### 静态 G1

- **PASS**：`OURS_full_10s` 平均 gap **−0.98%**（门槛 ≤ +1.0%）
- CPU-only 10s 臂也存在，按实际 wall 报告

### 动态主结果（J5，相对主基线 TS_RfcP）

| 场景 | OURS J5（3 seed） | TS_RfcP | ΔJ5 | completion（OURS / TS） | 门槛 |
|---|---|---|---|---|---|
| base | 4521.7 / 4522.8 / 4539.7 | 6820.0 | **−33.7%** | 0.979–0.990 / 0.847 | G2/G4/G2b/G5/G6 PASS；**G3 FAIL** |
| sigma15 | 6763.3 / 6781.4 / 6852.6 | 9846.7 | **−31.3%** | 0.978–0.987 / 0.849 | **G3/G4 FAIL**；其余 PASS |
| ncbias | 5214.3 / 5227.7 / 5316.2 | 7923.4 | **−34.2%** | 0.978–0.987 / 0.849 | **G3 FAIL**；其余 PASS |
| stress | 8201.2 / 8217.8 / 8673.6 | 13686.9 | **−40.1%** | 0.982–0.989 / 0.847 | **G3/G4 FAIL**；其余 PASS |
| uniform | 5070.4 / 5108.2 / 5146.0 | 7414.9 | **−31.6%** | 0.978–0.987 / 0.849 | **G3 FAIL**；G4 部分 seed FAIL |
| large | 11523.8 / 11649.6 / 12454.7 | — | — | 0.998–1.000 | s0/s2 G3 PASS，s1 G3 FAIL；G4 FAIL；G2/G5/G6 PASS |

所有场景 OURS 的 J5 都显著低于 TS_RfcP；p99 决策延迟 1.0–2.0 ms。  
但 **G3 要求所有图×天 100%**，严格口径下 OURS 是 97.8–99.0%，不是 100%；TS 基线更低（84.7%）。这是真实结论，不能写成“100% 完成”。

## 关键消融（base）

| 消融 | ΔJ5 vs full | 解读 |
|---|---|---|
| ABL_scratch（不从 RL5 热启动） | **+25.1%** | 热启动影响很大，F4 的隐患成立 |
| ABL_heurRepack（用启发式替代 RL 适配） | **+6.5%** | RL 的早晨路线适配有独立贡献 |
| ABL_Rfc | +15.3% | 只有静态计划 + 基线执行，明显变差 |
| ABL_N6 | +18.9% | 同上 |
| ABL_RL5 | +1.9% | 只换回 RL5 执行，损失较小 |
| ABL_noRR | −0.0% | 学到的 REROUTE 动作几乎没被用上 |
| ABL_B_online | +13.1% | 在线重建不如学习执行 |
| ABLP_full_static / pure / noeas | +38.2% / +36.9% / +40.0% | 计划本身贡献很大 |

## 结论与限制

- **可以主张**：在严格完成率口径下，J5 相对最强非 RL 基线仍大幅领先（−31% 到 −40%）；加班、延迟、G2b 都过；消融支持“计划/路线适配/热启动”有贡献。
- **必须披露**：G3 未过（严格完成率 97.8–99.0%，不是 100%）；G4 在 sigma15/stress 等场景未过；large 的 s1 G3 也未过；所以“所有 gate 通过”不成立。
- 3090 24GB 约束下使用了 `chunk 8`；训练硬件与 CPU 评估机分离，已记录在 `PATCHES_APPLIED.md`。
- 原始 `dyn_test_*.jsonl`（base 221MB + 4×约 110MB + large）未放进仓库；服务器上保留，本目录只放汇总 md/json/tgz。

## 文件

- `dyn_test_{base,sigma15,ncbias,stress,uniform}.md`：逐场景主表、门槛、Holm/bootstrap、消融
- `dyn_large.md`：大图
- `static_*.md/json`：G1 静态表
- `dev_select.jsonl` / `primary_baseline.txt`：dev 选主基线过程（**TS_RfcP**）
- `PROGRESS_SERVER.md`：运行进度
- `PATCHES_APPLIED.md`：迁移与 3090 适配记录
- `e2e_results_*.tgz`：所有 md/json/txt/plans/日志的打包
