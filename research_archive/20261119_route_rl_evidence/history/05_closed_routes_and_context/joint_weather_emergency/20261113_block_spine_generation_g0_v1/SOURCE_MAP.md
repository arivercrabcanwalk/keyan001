# 本轮来源和读取边界

继续使用nature-academic-search的multi-source-search流程。academic MCP/AgentKey find_tools在本会话可见工具目录为空；没有安装连接器或请求新凭据。使用内建web和主源HTTP。发现查询及已存读取响应见evidence/PARTIAL_WEB_DISCOVERY.json；它不是全部HTTP/web日志。

|来源|主链接/版本|实际读取|对本机制的约束|
|---|---|---|---|
|S01 Lindsten, Jordan, Schön. Particle Gibbs with Ancestor Sampling. JMLR15,2145–2184,2014|https://jmlr.org/papers/volume15/lindsten14a/lindsten14a.pdf|本地txt200–368，§3.1–3.2、Eq3、Alg2；web另定位§6.1/6.2相关段，未全文逐页精读|PGAS、γT/γt祖先权重、一般非Markov路径均已有；完整suffix成本不可直接叫O(NT)|
|S02 van de Meent, Yang, Mansinghka, Wood. Particle Gibbs with Ancestor Sampling for Probabilistic Programs. AISTATS2015 pp986–994|https://proceedings.mlr.press/v38/vandemeent15.pdf|本地txt280–475及web §3.3、§4.1–4.3相关段；不是全篇逐页精读|prefix+suffix自洽重建、分支失配拒绝、重算概率/避免重算均已有|
|S03 Lindsten, Bunch, Singh, Schön. Particle ancestor sampling for near-degenerate or intractable state transition models. arXiv1505.06356v1,2015|https://arxiv.org/abs/1505.06356|本轮仅官方元数据和摘要，未下载/读全文|退化转移下的rejuvenation有先例；不将“退化问题”或其通用解法当原创|

S01本地PDF SHA256: `0e6852b82dfa02c1e5164c0c27d7734942e10d11a3e394c616e13052e55b0935`。
S02本地PDF SHA256: `021e110c8545828943a300799d8944d9f4c9dc198d0d5e40f9720b30189cfae3`。
既有两次主源HTTP均200、PDF有效、pdftotext exit0，原收据在sources/HTTP_RECEIPTS.json。

本轮三组针对性检索：particle Gibbs+traveling salesman；ancestor sampling+permutation/combinatorial；particle Gibbs+degenerate/rejuvenation。未找到完全相同实现，不构成穷尽查新或新颖性通过。普通PGAS/trace regeneration不原创；服务集合辅助分块＋完整typed/cap拼接只是有明确可消融操作的组合假说。有限工程只检查正确性与当前配方，不替代论文级新颖性或科学实验。

复用源码来自20261113_group_transport_g0_v1/frozen，字节未改；使用现global_env、原wind_scorer、constant_audit和prefix_sampler.rebalance。旧T纤维、transport1280、repack192及旧信用实验不重跑。完整作者风cap/共同H独立新生成/强ALNS/公共T直接沿用；本轮手写1站几何不冒充作者地图或全图强基线。
