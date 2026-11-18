# PREREG E2E v3（在看到任何 v3 测试结果前冻结；机器可读版本 = gates_v3.json）

## 数据
* 测试图：data/instances/test（50，论文同规模）、fresh（50）、large+fresh_large（25，12–20 站）。
* 测试天气：base 21700-21799（主）、子集 21700-21719（昂贵臂：RLR、OURS+S）、stress 22700-22749、sigma15/ncbias/uniform 22700-22719、large 23700-23749。dev 26000-26019（仅检查点选择）。训练天气 ≥5e6。
* 主指标 J5 = cost + ot + 30·late_h + 10·late_n + 100·fails；前提：complete_strict=1。

## 门槛
* **G0**：每个作者臂（TS-CR、PAD、TS-CC、TS-FIX 各预算）在 base/stress 测试日的严格完成上界 = 1.0（verify_coverage.py；失败则 run_all 停止）。
* **G3**：所有臂、所有场景严格完成率 = 100 %（违例逐臂列出）。
* **G1（静态，同预算同选址 S\*）**：v3_b vs TS-FIX(S\*)_b，b∈{1,3,10,30,60}，另 fresh 10/60、large 10/60；Holm 家族内校正，单侧 Wilcoxon（逐图配对，seed 均值），≥4/5 seeds 同向。
* **G2（主结论）**：OURS 全栈（π_route-J5 计划 + π_exec）vs 每一个作者非 RL 强组合（TS-FIX|N6、TS-FIX|Rfc、TS-FIX|RfcP、TS-CC|Rfc、TS-CR|Rfc、PAD|Rfc；stress 下 TS-FIX|N6/Rfc），Holm。
* **G4（vs v5）**：相同计划 TS-FIX 上 π_exec vs RL5；我们计划上 π_exec vs RL5；全栈 vs TS-FIX|RL5、PAD|RL5；stress。**G4b**：OURS+S vs RLR（同 100 ms）。
* **G5（加班非劣）**：ot 相对 TS-FIX|RL5 上 95 % CI < +10 %。
* **G6（时延）**：OURS 决策 p99 ≤ 20 ms（表中 p99 列）。
* **G7（层贡献）**：路由层（v3_10|OURS vs TS-FIX|OURS）、J5 感知（v3j5 vs v3_10）、OFFLOAD（OURS vs nooff）、计划对 RL5 的增益。
* **G8（选址，大图）**：π_site vs MinCov、vs TS-CC（superiority），vs SimOpt-J5（非劣 1 %）；同时报告固定成本、#DABS。

## 统计
逐图平均（跨天、跨 seed）后单侧 Wilcoxon；Holm 在每个家族内；95 % CI = 图×天两级 bootstrap（5000 次）的相对差。所有原始逐实例行：results/analysis_v3/raw_per_instance.csv。

## 结果解释规则
未通过的门槛如实报告，不更换测试日/指标；不在测试日上调参。若 G4 失败，论文主张仅限 G1/G2/G7/G8 通过部分。
