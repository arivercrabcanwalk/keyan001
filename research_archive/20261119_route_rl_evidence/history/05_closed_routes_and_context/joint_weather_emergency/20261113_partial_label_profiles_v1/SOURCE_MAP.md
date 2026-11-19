# 本轮定点先例核对

本轮沿用 nature-academic-search 的多源检索流程。AgentKey/academic-search MCP 未挂载，使用公开 Crossref、arXiv 和 OpenAlex HTTP；没有安装服务或修改用户配置。以下结论只覆盖实际阅读的段落，不把搜索未命中当作原创证明。

|来源|本轮实际阅读|已有操作与本候选的关系|
|---|---|---|
|[Range, 2013, Discussion Papers on Business and Economics 17/2013](https://www.sdu.dk/-/media/files/om_sdu/institutter/ivoe/disc_papers/disc_2013/dpbe17_2013.pdf)，[DOI](https://doi.org/10.2139/ssrn.2340997)|新取得大学原站24页PDF。阅读摘要/引言、§4.1、§5.2和Algorithms 3–4、§6.3的报告方法、§7及小状态数开销讨论。PDF第6–7页视觉复核；未逐页精读全部实验表。正文作者名Troels Martin Range；Crossref缩写为Troels Range。|先比较成本/资源，再要求不可达节点集包含关系；trie加速subset/superset检查，删除整个被支配状态。本文的集合是“未来不可达节点”，本候选是“某个删除查询仍由此模式支持”。该源已覆盖集合条件支配和数据结构加速，所读算法未给出本候选的跨查询支持位部分相减。有限区别不等于本候选已获新颖性。|
|[Resource Constrained Pathfinding with Enhanced Bidirectional A* Search, arXiv:2412.13888v1](https://arxiv.org/abs/2412.13888v1)|复用上一包原文，重点重读本包 RCSP_TEXT.txt 112–140行。|多资源双向join、支配、界剪枝已有；截断资源向量的支配不保证标签可从所有join中删除，作者保留第二列表。本候选用完整所需资源和同首目标组，不能直接套用截断支配。|
|[Replacement Paths via Row Minima of Concise Matrices, arXiv:1310.8062v1](https://arxiv.org/abs/1310.8062v1)|复用上一包已核的prefix/bridge/suffix与区间支持证据，未重做整篇审计。|区间支持、多个删除查询共享路径结构已有；本候选的删除会重接物理弧并改变能耗，不能直接引用固定图replacement-path的复杂度作为本问题复杂度。|
|[Enhanced Multi-Objective A* Using Balanced Binary Search Trees, arXiv:2202.08992v3](https://arxiv.org/abs/2202.08992v3)|复用上一包维度/支配数据结构核对，不重新跑作者代码。|多维支配和树结构已有；不能把任意维查询无条件写成log复杂度。|

Range的原文定位：`literature/RANGE_TEXT.txt` 237–290行定义资源/elementary dominance；439–456行介绍subset/superset trie；648–785行Algorithms 3–4；939–951行说明C++ -O3、两小时限额、超时阶段与存活状态数；1121–1146行讨论小状态数时数据结构开销可能超过减少比较次数的收益。本文给本轮的启示是记录实际总耗时和状态数，不能只报减少了多少检查。

来源获取链：Crossref Q01/Q03定位DOI → SSRN返回403 → OpenAlex DOI记录给出大学公开PDF链接 → SDU原站200成功。SSRN错误页面和所有失败收据保留，没有越过登录/访问控制。Q01/Q02第一次因本地Python证书链错误失败；改用已安装certifi根证书后另标签重抓成功，没有禁用TLS。

本轮共8次HTTP：5次200、1次403、2次TLS失败；原始body/receipt位于literature/。3组发现检索不是3份全文，本轮只新增1份原文。Range未执行作者代码，实验加速倍数只属于该文自己的实验，不能移植为本项目结果。

查新裁决：Pareto、双向join、集合条件支配与trie不是新原语。本候选在实现中确有“生成时只删除重叠动作支持”这一步；尚无证据证明其组合是独立研究贡献。当前总效率实测失败，G0仍未通过。
