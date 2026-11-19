# 本轮先例核对与真实读取范围

沿用nature-academic-search的multi-source-search工作流。当前工具目录没有AgentKey的find_tools/describe_tool/execute_tool，也没有academic MCP；未安装连接器或请求凭据。使用web发现、官方原文及本地curl文本提取。错误路径references/workflows/multi-source-search.md曾返回不存在，按manifest改读wf1-multi-source-search.md；非科研失败，无数值phase。

|来源|核对范围|与本候选关系|
|---|---|---|
|[ARMS, ICML 2021](https://proceedings.mlr.press/v139/dimitriev21a/dimitriev21a.pdf)|正文§2.1、§3，特别式(4)/(6)，本地ARMS.txt与web全文检索定位；不是整篇精读|两独立样本的Product of Differences已经是标准无偏估计，不把本候选的对称更新称原创；本文相关Bernoulli耦合扩展不是本轮路线策略已实现能力|
|[COMA v3](https://arxiv.org/html/1705.08926v3)|§4.2式(4)、Appendix A baseline零均值段；HTML+文本抽取|固定其他动作的条件baseline已有先例；本轮没有训练central critic，也不冒称COMA为静态站池hard-cap精确solver|
|Martello/Toth 1995 BMCKP|复用上包SOURCE_MAP和已读§2.2/3 pp625–627的OCR原论文镜像范围；本轮没有取得出版商PDF|按H维护组内最低成本的单目标扫描已有；增量只能是全部外来强制候选同时求解，不是基础BMCKP|
|PKPO v5、UCPO、LOLS、CMSA-RL|读取范围沿evidence/PREVIOUS_SOURCE_MAP.md，不重新跑旧矩阵|集合收益、LOO信用、局部rollout和池组合不改名作创新|

本轮新增2个原文下载，均curl exit0/HTTP200；ARMS.pdf SHA256=0b320e210dc4fa8f1503a5d576abbf2c89e8dda36036dd181bd2d7d578cade24，COMA.html SHA256=0de68fe0ce86a5259a44b7997b6d808889f789858538559428ea6eab0693b870。原始HTTP收据见evidence/sources/HTTP_RECEIPTS.json。

有界发现查询包含bottleneck multiple-choice sensitivity/min-marginal/all forced choices及two-sample REINFORCE。完整web结果见evidence/replacement_discovery2.json、replacement_sources3.json、replacement_primary_read.json；二手页面只作发现线索，未作为技术判据。上一窗口replacement_discovery1未落盘，summary给出的元数据不是本包新增全文证据。OSCC、Difference rewards新搜索条目未读，不依赖其主张。

没有查到恰同双层堆不能证明新颖；当前只支持一项具体可复核的计算候选。任何G0通过仍须绑定明确算法差异、适用域及实际学习价值，不由下载数/通过数推出。
