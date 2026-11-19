# 最近先例定向核验与证据边界

本次使用 nature-academic-search 的多源发现/身份核验流程。当前学术检索和 AgentKey MCP 工具未挂载，已用出版社公开索引和 CrossRef 官方 API 定向核验两篇，不计作完成“99 篇全文”或原始七篇摘要缺口。未获取付费正文或补充材料。

## 两篇身份与可支持的结论

|论文|核验与证据范围|对本项目的直接影响|
|---|---|---|
|Shan Zhao, Jian Zhang, Leandro C. Coelho. Dynamic truck-drone collaborative routing with stochastic requests under changing weather conditions. TR-E 214 (2026), 105074. DOI 10.1016/j.tre.2026.105074|CrossRef HTTP200 确认题名、作者、卷、文章号与 2026-10 卷期；出版社预览描述随机请求、变化风况、route-based MDP、VFA/ADP。完整公式、附录和所有基线未读。|不能把“天气+随机请求+未来价值”作为空白；精确联合依赖与本项目动作/约束差异仍待全文逐式核对。|
|Linghui Han, Yue Wu, Chengjuan Zhu, Huijun Sun. Rolling-horizon UAV dispatch for urban traffic incidents with preparedness-aware repositioning. TR-E 215 (2026), 105100. DOI 10.1016/j.tre.2026.105100|CrossRef HTTP200 确认题名、作者、卷、文章号与 2026-11 卷期；出版社预览描述当前响应、下一窗口准备度、异构可用状态及 non-RL ALNS/MILP 两阶段。模型全式、附录未读。|强对照需包括使用未来需求/准备度的 non-RL；其中改降和返航站重归属不属于当前物理合同，适配须披露。|

一手链接：[Zhao 出版社页](https://www.sciencedirect.com/science/article/pii/S1366554526004138)、[Zhao CrossRef](https://api.crossref.org/works/10.1016/j.tre.2026.105074)、[Han 出版社页](https://www.sciencedirect.com/science/article/pii/S1366554526004382)、[Han CrossRef](https://api.crossref.org/works/10.1016/j.tre.2026.105100)。

两篇 CrossRef 原响应及 HTTP/哈希收据位于 evidence/。网页直接 open 收到 403，搜索索引提供出版社预览；403 不表示文章没有全文，也不表示所有机构无权限。未用搜索未命中断言不存在作者稿。未引用第三方代传文件或二手新闻来补成算法全文。

## 已有全文复用和仍存缺口

Joe & Lau 2020（10.1609/icaps.v30i1.6685）已有归档全文，270–285 行涉及学习 postdecision value 与路线搜索，330–347/363–368 行涉及真实请求场景和路线计算。其框架与本次联合场景估计的主要步骤相近；不声称该文已经证明本文件的精确反例或完整 Liu 约束域。

本地 ADP_SPEC.md 已写固定因果 μ、共同未来样本、MC/TD VFA 与同信息 rollout；其数学接口没有要求未来流逐点独立。本次将 P_TRAIN 明确成联合分布，不产生新的更新公式。

Ren（10.1016/j.cor.2025.107141）和 PADA（10.1016/j.comnet.2026.112607）的旧全文获取缺口继续保留，本次没有重复失败下载。它们的摘要不承担精确算法差异证明。

“99 篇已核实、其中 7 篇摘要级”是目标说明中的历史陈述。本次定位到的材料未提供与该计数逐项对应的完整清单或三份独立原始 prompt，所以没有新登记 99/99 或 7/7 验收。当前目录中的 WX 协议是已执行包的协议，不能补称为用户最初的三份 prompt。

## 全文下一步与当前决定

已异步询问本批 Zhao/Han 是否同时获取 SI；依据 nature-downloader/SKILL.md 的明文要求："Before downloading any PDF, CAJ, HTML, XML, archive, or attachment, ask whether the user wants Supporting Information." SI 范围未确认期间，仅做身份/元数据核验及使用已归档全文的独立工作；不把等待回复当作同意。

后续全文核对须回答：Zhao 的 postdecision state、联合请求/天气过程、价值逼近与前瞻基线具体是什么；Han 的 preparedness 函数、跨机竞争、可用状态与动作域如何定义。若全文差异只剩站点/机型/多趟/指标组合或输入分布变化，本候选继续 G0 NO-GO，不启动训练。当前已足以确认“候选尚未建立新算法”，不把全文未知当成创新支持。
