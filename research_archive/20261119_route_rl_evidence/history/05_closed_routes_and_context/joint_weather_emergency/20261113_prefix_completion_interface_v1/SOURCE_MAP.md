# 本轮新增来源与阅读范围

应用nature-academic-search的multi-source-search流程；当前工具目录未暴露academic-search MCP及AgentKey的find/describe/execute工具。本轮使用官方论文站、arXiv、PMLR及其下载链接，不安装或更改连接器。

|来源|实际取得与读取|用于什么；边界|
|---|---|---|
|APO2CS, arXiv2611.11792v1|官方HTML，SHA2092ef6aec3e325f84d2a053392fcd72798157612e532ba11b96ea6a29879a06；提取文本约125–324行的方法、另5.1评测段|Eq4–33，尤其局部片段成本标签Eq28/组合Eq33；未读作者代码、未验其表中优势；是预印本，不采模板DOI/会议占位符|
|BOPO, PMLR267 liao25a|官方链接PDF，SHA3e729984f097e34af3a1c77e42dba904673cfa4483d5a5cb7353f9e55af387d3；提取文本194–263行及前后的§3.2/4.1|混合rollout、uniform filtering、best-anchored pairing、Eq1–4/Algorithm1；未复现实验/作者模型|
|CoPro, PMLR306 li26ga|官方链接PDF，SHAb36a098f98021688df3ee037f179ee43ba3ea803c5a54507fbeb747202521e56；提取文本237–371行§4|组内矩投影/正权重/anchor及策略投影；未读完附录证明和代码，不把样本anchor质量当每条路线cap保证|
|BQ-NCO、Safe Policy Iteration、SIL|本轮web打开选段；BQ已有前包原文/代码证据|仅作最近先例线索，不称本轮全篇复审|
|UCPO（AAAI26）/LOLS|发现题名、出版页/原文入口|下一项定向阅读；同名UCPO有不同论文，必须按题名/作者/年份区分|

3次Python urllib请求均TLS证书错误；随后系统curl正常TLS验证取得3份原文，HTTP200、exit0。未关闭证书验证。错误和成功都保留在HTTP_RECEIPTS.json。web打开旧式BOPO PDF路径失败；实际改用PMLR页面给出的raw.githubusercontent链接成功。WEB_READS.json保留本轮搜索和打开结果，不将搜索条目数当精读数量。

原文已取不代表新机制已通过。原研究A完整cap、强ALNS、nonRL/BC/标准RL控制和独立多seed/全新Formal要求均保持。
