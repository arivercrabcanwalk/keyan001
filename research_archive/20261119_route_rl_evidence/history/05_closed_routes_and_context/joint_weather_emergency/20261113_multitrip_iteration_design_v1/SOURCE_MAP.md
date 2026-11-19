# 本轮方法证据与实际阅读边界

沿用已启用的nature-academic-search多源工作流。其学术MCP及AgentKey查询工具当前未挂载；未修改客户端配置，继续用已有原件与内建web。未调用子agent。

|源|本轮实际阅读|结论与边界|
|---|---|---|
|[DPN v2](https://arxiv.org/html/2405.17272v2)|复用`../20261113_fixed_wind_A_experiment_survey/literature/P04_DPN_TEXT.txt`，lines45–76，§3.1–3.3、式9–19；阅读由本轮接续前半完成|分区/导航编码、APS构造顺序baseline与位置编码已有；不把typed物理身份交换当对称。不重新下载或计成新论文|
|[SED2AM v1](https://arxiv.org/html/2503.04085v1)|本轮3次web open相同主源；方法累计覆盖§3与§4.1–4.4、式1–37；新补读重点§4.2–4.4|fleet/routing state、车辆/节点解码、mask、完整trip构造与greedy-baseline REINFORCE已有。其目标与场景不自动等于本项目cap/minmax/typed模型|

旧`route_rl_research/20261103/mechanism/trip_hypergraph/evidence/route_g0_primary_open.json`标题曾提到§§3–4，但保存内容仅到原文L155附近，未完整保存§4架构与训练。此次补读真实扩展方法证据，不计为首次发现SED2AM或新的独立论文。

`evidence/SED2AM_OPEN_1.txt`、`_2.txt`、`_3.txt`是实际返回的带行号web文本，有重叠。合并覆盖范围L0–400，只有§3–4与紧邻上下文作为本轮方法依据；没有据此声称读完全文或实验复现。网页工具未提供显式HTTP状态码，不臆造200。版本严格绑定v1与DOI10.1145/3721983。

`evidence/PRIOR_TURN_DISCOVERY.txt`是接续前半已执行的一批4查询的现存原始返回，本轮只落盘，没有重搜。IET分层多趟方法等仅为发现/摘要，未当作方法精读、包含关系或新颖性证据。本轮最多两份最近方法范围：DPN、SED2AM。P10旧多趟资料仅做题名定位，不新增方法读取。

既有Wang约束hypergraph、PIP/LMask/PLPG、GFN/Sinkhorn/coupling及GaS/KERL的原审计与调研直接复用，不再查新、补跑或宣称新读；没有从通用先例推出未来一切组合都无效。

物理规格只静态对照现有`../20261113_group_transport_g0_v1/frozen/global_env.py`与`frozen/baselines/wind_scorer.py`的TARGET/RETURN和完整C/M字段，未重做环境审计或执行评分。局部mask不保证余下全完成；公共T后H与raw-slot H不同，规格明确保留支持差别。

本包的概率链式分解证明是一般条件概率恒等式，不是原创RL理论，也不验证有限网络训练效果。当前原始文献阅读没有给出trip层架构的独立新操作，故关闭该有限新颖性主张；不据此关闭未来有实际增量的路线算法。
