# 作者调用点与风适配身份

官方锁：LRPHSD `d86f5549ebc9c05d65fce16f61b6df4f7cb73158` 的 `code/TSALNS`，10 文件。实际起点是历史仪器化/guard 后的 J1b，15 文件；见 evidence_sources 的两份原 manifest。ORIGINAL_FILE 的 Java 15/15 与 J1b manifest 相符。Python 最小依赖 5 文件来自上一修复包；没有重跑其强 ALNS。原20文件哈希在 ORIGINAL_HASHES.json。

`SOURCE_CALL_MAP.json` 列出原/改每个相关行号与原文；`SOURCE_EDITS.json` 记录逐段替换；`DIFF_FILE` 为完整差分。Main、ALNSSolver、LocationOperator、ReplayRandom、ReferenceRecorder、Node 等原字节保留。

|调用|原含义|修改后的含义|
|---|---|---|
|Calculator.calculateDistance；Init 覆盖/归属；LocationOperator；RoutingOperator 各 coverage 条件；Round4Guard coverage|原坐标欧氏几何|保留原式及半径，未整体替换|
|Check.calculatePathTime/cost/energy/droneTime；时间/能源验收；Init 目标/返航 reserve|distance/speed|有向 track-holding 时间，包含返航；全成本仍 fixed + 0.5×operating|
|Check.calculatePathLength|物理米|保留；原以该值除 speed 估能量的两个调用改用独立命名 calculateFlightTime|
|RoutingOperator 2-opt四边；removal/insertion delta；新趟 baseCost|欧氏距离启发式|闭合航次精确对称有效米；原比较结构/系数保留。baseCost 原本单边的排序约定也保留，没有借适配偷偷改算法|
|Init 最近目标/距离排序；RoutingOperator similarity|欧氏启发式|保留欧氏排序；可行性已按有向风时间检查|
|Init 无可行目标|可能无进展循环|明确 WIND_INIT_NO_PROGRESS；异常/失败保留，不修复为成功|
|Round4Guard|硬编码官方900/0.018/1/.81/600/480/5000/4000|常数不变，仅飞行分钟改有向。EPS1e-7 沿用；Python独立能量容差1e-12仍更严，最终还须独立复核|

令 D=a²−||w||²、δ=b−a、q=√(D||δ||²+(w·δ)²)。有向时间 `(q−w·δ)/D`；顺风时使用等价稳定表达式 `||δ||²/(q+w·δ)`。闭合航次的势差求和为零，因此搜索度量是 `a*q/D`；有向服务前缀不能使用该对称值。该数学等价已属标准构造，本包没有 G0 创新主张。

边界：checkPathEnergy 严格 `<`；最终 checkStationPathsEnergy 用 `>` 拒绝，等于接受。工程 boundary 例 flight0/serviceEnergy1 的结果为 helper=false、final=true、guard=true。旧 checkEnergyConstraints 跨趟相加的辅助语义未重写，不据名称混成最终验收。正 ID、站服务0、官方参数适用范围写入合同；未测试任意参数或坏 ID 的整个 Java 搜索。

本包编译全部 J1b 源，调用真实 Check/Init/RoutingOperator/Round4Guard/ReferenceRecorder；探针使用明确手写完整路线，**没有调用 Main/ALNS 搜索**。因此风适配代码存在并通过有限工程验收，但还没有完整作者算法的同墙钟资格证书。
