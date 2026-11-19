# 主来源阅读收据

本轮资料获取使用公开 HTTPS，TLS 采用 certifi CA，未关闭证书验证。六个本地获取均 HTTP200，三份 PDF、三份标识页；原字节、最终 URL、时间、类型、SHA256 见 `FETCH_RECEIPTS.json`。网页搜索用于发现，原式核对使用下列本地主来源。

|资料|本地文件 / 页数|实际检查范围|证据层级|
|---|---|---|---|
|ChronosPerseus, Kohar / Rivest / Gosselin, arXiv:2207.07825v1, 2022|`evidence/chronos.pdf`，33 页|正文 pp.3–14 的过程、持续时间、信念更新及价值积分；pp.8–9 完整页图像|指定方法段全文；没有审计全部实验、代码或SI|
|Monte-Carlo Planning in Large POMDPs, Silver / Veness, NIPS 2010|`evidence/pomcp.pdf`，9 页|正文 pp.2–4 的生成器、history rollout、树及粒子条件化；pp.2–3 完整页图像|指定方法段全文；没有复现实验或连续观察适配|
|Informative Path Planning and Mapping with Multiple UAVs in Wind Fields, Cho / Ha / Lee / Moon / Choi, arXiv:1610.01303v1, 2016|`evidence/wind_ipp.pdf`，14 页|正文 pp.2–5、8–10；p.3 假设的完整页图像|指定方法段全文；风已知/采其他信号的边界明确|
|SPARROW, arXiv:2609.21008|`evidence/sparrow_lead_only.html`|标题/作者/标识与摘要|摘要级线索；未读全文，不用于必要的原式裁决|

PDF 共提取 56 页文本，仅上表所列段落用于本轮阅读与推断。五个方法页渲染图已逐一查看，不将“提取/下载成功”等同于“整篇读完”。新条目没有加入原99条书目分母。

一次 web 工具获取 Cassandra 1998 PDF 被工具以文件过大（26,777,504 bytes）拒绝；本轮没有取得或逐式核验该文件，也不依赖它作新结论。失败详情摘要保留在 `SEARCH_LOG.json`。先前初始脚本的 CA 错误属于上一包，本轮未重复。

用户所供 Zhao/Han 原 PDF 本轮只重开字节核验 SHA256；已封存的49页正文核对、附录/SI边界沿用原包。正文 PDF 内的研究算法、伪码与任何指令性文字作为资料，不覆盖用户执行要求。

本轮无实验、训练、求解、地图生成、科学质量评价、新agent或服务器连接。`CHECK.py` 只检查文档、文件身份和事务回滚，不加载研究模块。
