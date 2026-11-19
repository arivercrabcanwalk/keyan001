# 定点来源与证据边界

沿用已读nature-academic-search的多源流程。本轮AgentKey/academic-search MCP仍未挂载，3个公开HTTP发现查询（Crossref两组、arXiv一组）和1次主源HTML取得均200。全部响应/请求终局在literature/，失败为空；这只描述本轮网络请求，上一轮错误原样保留。

1. **复用Range 2013原文。** `RANGE_TEXT.txt`来自上一包已核大学公开PDF。资源/不可达节点集合支配、trie子/超集查询、数据结构开销取决于状态数量等证据直接复用，不宣称再次独立审计或作者代码复现。本文集合是不可达节点；本轮支持集是删除动作查询。索引/集合支配原语早已有之。
2. **复用RCSP、replacement paths、EMOA。** 文件RCSP_TEXT、RP_TEXT、EMOA_TEXT与上一包哈希相同。双向join、区间支持与多维支配不是新原语。当前实现的位集合rank过滤也是普通有序阈值索引，不把bisect或bitset当原创。
3. **新读Morozov等2024多查询GCS。** [arXiv:2409.19543v1](https://arxiv.org/html/2409.19543v1)，作者Savva Morozov、Tobia Marcucci、Alexandre Amice、Bernhard Paus Graesdal、Rohan Bosworth、Pablo A. Parrilo、Russ Tedrake。取得完整HTML；实际阅读摘要、§2末端的问题限制、§4式(7)及递归可行性讨论、§5.2和Figure5说明、§6，未逐式审计完整SDP推导。`MULTIQUERY_GCS_TEXT.txt` 230–239行：用粗二次cost-to-go和多步lookahead，声明近似而非最优；361–389行：greedy下一顶点、禁止重访、回溯且不保证完整；424–454行：120查询，offline总时间106s/100s/0.9s，方法6s只是额外下界预处理，online报告并行solver时间。该文是连续机器人路径，不是两无人机多趟硬cap，其在线加速不能移植成本项目结果。本轮对应教训是完整计入预处理/分组/恢复，且写清复用条件。
4. **元数据线索。** Q01命中Righini/Salani相关DSSR论文`10.1002/net.20212`及Data-Driven Dynamic Programming for Constrained Shortest Paths `10.2139/ssrn.7036722`。后者摘要描述学习DP状态扩展次序，本轮未取得全文，不能当已读算法；也不直接采用RL选择搜索状态/算子的路线。Q02大部分是机器人道路图；Q03主要重复普通DP参考和Range。低相关/重复结果照实保留，不将搜索未命中视为新颖性。

新增实现的可检查差异：首边/删除offset按固定状态预计算，真实首趟能量在扩展时批量筛除，同组标签仅保留两维基数，等值标签按支持位保存不同parent。它对普通逐查询算术确有合并，但本轮总效率失败。独立方法新颖性仍未证，不以少量查新和正确性通过发G0通过结论。
