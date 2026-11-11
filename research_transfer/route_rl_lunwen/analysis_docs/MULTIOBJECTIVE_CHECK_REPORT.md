# GitHub多目标研究：来源核对与<EXPERIMENT_SERVER>实测复核

结论：GitHub确有多目标研究，但它没有证明“换成多目标后RL稳定胜过强非RL”。本次<EXPERIMENT_SERVER>对联合天气＋紧急任务B原始完整数据做独立多目标重评价，也未观察到这种整体反转。此次没有重新训练多目标策略或生成新路线，不能据此否定尚未测试的偏好条件化RL。

## 1. 查到的原始说法

在线GitHub API核实仓库arivercrabcanwalk/keyan001，main最新commit f6bbc81bdfa4f563969c8f4adfe4d59e423807dc，提交时间2026-11-04T10:16:26Z。7份原文/源代码/摘要输出已在线下载，逐SHA见GITHUB_MANIFEST.json。

- [PAPER_FINDINGS A4/A5/A8](https://github.com/arivercrabcanwalk/keyan001/blob/f6bbc81bdfa4f563969c8f4adfe4d59e423807dc/rl_research/PAPER_FINDINGS.md#L32)：7个lambda的成本—完工前沿，作者HV0.0869，RL0.0900，NoRL0.0920；成本允许+1%时RL归一完工0.698、NoRL0.678。A8已明确非RL更好。这里“多目标框架胜作者”与“RL胜同框架非RL”是两种主张。
- [D14及原表](https://github.com/arivercrabcanwalk/keyan001/blob/f6bbc81bdfa4f563969c8f4adfe4d59e423807dc/rl_research/rl_wind/results/pareto_strong.txt)：成本—天气失败前沿，固定类型余量NoRL HV0.7857，RL五seed均值0.70028276、标准差0.09314073。报告称等成本下RL相对无学习凸包差约−0.52%，34/70点在凸包下；该数字所需hr_*原表及5个模型未进入当前GitHub树，本轮未制造原人口复现。
- [F3及PPO摘要](https://github.com/arivercrabcanwalk/keyan001/blob/f6bbc81bdfa4f563969c8f4adfe4d59e423807dc/rl_research/rl_ppo/results/final_1.0.txt)：PPO部分加权标量目标有改善，但报告自己写HV和MK@1%未显著。其RL动作是旧算法参数控制，与当前物理TARGET/RETURN研究不同；本轮未恢复该旧RL分支。

A4/A5原step*.txt对应的逐lambda完整结果也未见于公开树。文档数值属于历史报告陈述，不能把重读摘要当独立重现p值。公开代码的HV5与HV7点数不同，不能直接比较；MK@1%没有候选时应明确保留缺失，而不能只汇总有候选地图。

## 2. 已实际执行的实验

实验前PLAN_BEFORE_EXECUTION.md冻结：四平面、参考点(1.10,1.50)、成本容忍0/1%/4%、12地图独立单位、10000次地图bootstrap描述区间，保留所有失败、不调参、原J不改。全部计算<EXPERIMENT_SERVER> CPU103，原D处TRAINING，原85冻结源前后不变。

第一项：逐字抽取GitHub原hv函数，与独立矩形并集/枚举、非支配点、凸包及缺候选成本约束进行7个合同测试，全部通过。原HV在这些有效输入上与独立实现一致；新增工具接口在baseline不存在造成预期ImportError，不代表GitHub原HV有计算错误。

第二项：对已完成B全部8256意向重新评估，其中8112DONE/144TIMEOUT。完整68个method-stage-budget单元，62完整、6含失败保留且不产生均值/前沿点；绝不按DONE行临时构造期望人口。12地图、4日、3训练seed在地图内平均，seed不是独立n；6s和12s在本数据的下列表现相同，不能算两份独立证据。selected的pairedES及所有initial归无学习对照，12个RL selected归RL。

第三项：另一次独立脚本从原EVALUATIONS.jsonl重新核对单元、地图均值和成本约束，4334项算术检查通过。未重新模拟或训练，原数据SHA不变。完整模型/物理合法性复用之前已完成独立审计及服务回放，不冒充本轮重新验证所有旧模型。

## 3. 多目标结果（12s；6s相同）

HV越大表示该固定归一化矩形内覆盖更大。归一化对每图采用动态author_dispatch成本，以及max(1,作者该第二轴)。各平面的HV尺度不同，不能跨行比较。

|目标平面|完整无学习/非RL候选组合HV|完整RL候选组合HV|RL组合覆盖更好的地图|
|---|---:|---:|---:|
|成本—日历返航makespan|0.054164|0.048132|3/12|
|成本—迟到罚分|0.151586|0.115263|2/12|
|成本—应急迟到任务数|0.155546|0.137607|3/12|
|成本—响应|0.056842|0.049723|2/12|

这是看过结果后候选集合的描述性前沿：非RL19个完整候选、RL12个完整候选，候选数和生成成本不同；部分登记强控制有超时，all_registered_controls_complete=false。因此不把它当公平同算力算法排名、完整最强baseline证明或确认性显著结论。它能回答的限定问题是：当前已完成候选集合在这些固定评估口径下，没有出现RL整体领先的迹象。

## 4. 相同成本条件下看返航

参考为dynamic author_dispatch；先按地图在事件日及seed内平均成本，再施加epsilon，不等于旧静态R_Liu逐case严格costcap，也不把日历返航称累计duty M_return。候选组合按地图事后选最低makespan，是描述性上界而非真实可部署选择器。

|允许平均成本增加|RL组合有合格候选的地图|无学习组合有合格候选的地图|
|---|---:|---:|
|0%|4/12|12/12|
|1%|7/12|12/12|
|4%|12/12|12/12|

0%和1%不删除RL无候选地图、不产生全图配对均值。4%时RL组合日历返航平均高0.071073分钟，地图bootstrap描述95%区间[−0.092579,+0.247232]分钟；1胜/5平/6负。没有支持“成本最多多1%，RL就能在当前联合场景普遍显著缩短完工”的证据。原A5的约31%来自另一静态问题、另一参考及权重扫描，不能迁移到本联合问题。

等成本凸包比较也已落表；大量点不在无学习凸包成本支持范围，明确null、不外推。例如成本—返航144个RL地图点中29个处支持范围、其中5个在凸包下；这个条件子集不是144独立地图，也不能用它推断整体收益。

## 5. 对研究路线的含义

多目标评价值得保留，它能区分“服务提升来自额外成本”与“同成本下路线更有效”；现有数据尚未证明RL把可达到的前沿向外推。当前RL主要按固定完整J训练，没有偏好参数输入；对固定J模型做重新打分不等于训练了真正的偏好条件化多目标RL。本轮完成的是对当前结果和历史说法的核查，未开展该类新训练，也不是新Formal。

若继续研究多目标训练，应明确“同时生成成本—服务Pareto解集”的新技术假说，让物理TARGET/RETURN策略接收预先定义偏好，同时给非RL同样的权重扫描、点数与总预算，检查同成本凸包差和原完整J；新人口/冻结/多seed/确认须另行完整执行。不得恢复旧算子选择，也不从暴露B结果挑权重宣告成功。

## 6. 执行与工件

父CPU0.028460876秒，子CPU1.407091秒，独立算术复核另计原容器。37服务器原件已SHA重开，archive SHA9677c05bab37a42ed7508383367798e076113ed54dd109c2ba6e11353a5c0a6c；随后独立审计另有INDEPENDENT_AUDIT_REOPEN.json，不改前一archive身份。精确命令/输入/逐字输出/退出和实际回滚如下。修改副本保留。

```text
Changed branch: retain exact GitHub hv; add independent finite 2D HV, nondominance, lower convex hull and cost-cap missing=null for old-data multiobjective experiment.
PATH <SERVER_PATH>
PATH <SERVER_PATH>
PATH <SERVER_PATH>
PATH <SERVER_PATH>
BASELINE {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "", "stderr": "Traceback (most recent call last):\n  File \"<SERVER_PATH>", line 1, in <module>\n    from multiobjective import hypervolume, best_with_cap\nImportError: cannot import name 'hypervolume' from 'multiobjective' (<SERVER_PATH>", "exit_status": 1}
MODIFIED {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "", "stderr": "test_cost_cap_missing_is_null (__main__.Tests.test_cost_cap_missing_is_null) ... ok\ntest_dominated_duplicate_permutation_invariant (__main__.Tests.test_dominated_duplicate_permutation_invariant) ... ok\ntest_equal_cost_randomized_hull (__main__.Tests.test_equal_cost_randomized_hull) ... ok\ntest_hv7_is_not_hv5_protocol (__main__.Tests.test_hv7_is_not_hv5_protocol) ... ok\ntest_independent_grid_union (__main__.Tests.test_independent_grid_union) ... ok\ntest_manual_hv_matches_github (__main__.Tests.test_manual_hv_matches_github) ... ok\ntest_reference_and_nonfinite (__main__.Tests.test_reference_and_nonfinite) ... ok\n\n----------------------------------------------------------------------\nRan 7 tests in 0.001s\n\nOK\n", "exit_status": 0}
MODIFIED_CONTRACT {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "PASS_HV_AND_MISSING_COSTCAP_CONTRACT\n", "stderr": "", "exit_status": 0}
ROLLBACK {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "RESTORED_EXTRACTED_GITHUB_HV_SHA\n", "stderr": "", "exit_status": 0}
RESTORED {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "", "stderr": "Traceback (most recent call last):\n  File \"<SERVER_PATH>", line 1, in <module>\n    from multiobjective import hypervolume, best_with_cap\nImportError: cannot import name 'hypervolume' from 'multiobjective' (<SERVER_PATH>", "exit_status": 1}
EXPERIMENT {"command": ["<SERVER_PATH>", "<SERVER_PATH>"], "environment": {"IMPL_DIR": "<SERVER_PATH>", "PYTHONPATH": "<SERVER_PATH>", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}, "input": "See frozen PLAN_BEFORE_EXECUTION.md; seven deterministic HV/hull/cap contracts; original B8256 full-intent data for EXPERIMENT.", "stdout": "{\"status\": \"PASS_POSTHOC_MULTI_OBJECTIVE_REEVALUATION\", \"all_intents\": 8256, \"statuses\": {\"DONE\": 8112, \"TIMEOUT\": 144}, \"cells\": 68, \"complete_cells\": 62, \"failed_or_infeasible_cells\": 6, \"maps\": 12, \"hull_summary\": [{\"budget\": 12, \"metric\": \"makespan\", \"all_RL_map_points\": 144, \"supported_points\": 29, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": 0.0007761977565792987, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 12, \"metric\": \"miss_penalty\", \"all_RL_map_points\": 144, \"supported_points\": 12, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": 1.2392883983746918, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 12, \"metric\": \"emergency_late\", \"all_RL_map_points\": 144, \"supported_points\": 12, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": -0.06672183786099145, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 12, \"metric\": \"response\", \"all_RL_map_points\": 144, \"supported_points\": 39, \"below_nonRL_hull\": 9, \"mean_normalized_gap\": 0.007578814236506204, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 6, \"metric\": \"makespan\", \"all_RL_map_points\": 144, \"supported_points\": 29, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": 0.0007761977565792987, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 6, \"metric\": \"miss_penalty\", \"all_RL_map_points\": 144, \"supported_points\": 12, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": 1.2392883983746918, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 6, \"metric\": \"emergency_late\", \"all_RL_map_points\": 144, \"supported_points\": 12, \"below_nonRL_hull\": 5, \"mean_normalized_gap\": -0.06672183786099145, \"support_conditional_not_full_population_effect\": true}, {\"budget\": 6, \"metric\": \"response\", \"all_RL_map_points\": 144, \"supported_points\": 39, \"below_nonRL_hull\": 9, \"mean_normalized_gap\": 0.007578814236506204, \"support_conditional_not_full_population_effect\": true}], \"cpu_s\": 1.1069125290000001, \"wall_s\": 1.1066803499124944, \"source_unchanged\": true, \"new_policy_rollouts\": 0, \"new_training_runs\": 0, \"rl_superiority_claim\": false, \"publication_ready\": false, \"not_historical_A4_A5_D14_replication\": true}\n", "stderr": "", "exit_status": 0}
Restored: isolated multiobjective.py SHA exactly equals extracted original GitHub HV; missing new entrypoint ImportError exit1 returns; original hv remains available; modified copy retained.
```
