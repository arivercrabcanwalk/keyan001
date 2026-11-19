# 本轮主源、读取范围与设计裁决

本轮沿用 nature-academic-search 多源检索及 PDF 原式/图示核对。学术 MCP 和 AgentKey 工具未挂载；未安装连接器或请求密钥。公开 HTTP 字节/hash 见 literature 各 *_RECEIPT.json；下载不等于全文逐页读完。

|来源|实际读取|对本项目的直接影响|
|---|---|---|
|C. Rego, Node Ejection Chains for the Vehicle Routing Problem: Sequential and Parallel Algorithms；2000-09-14 preprint，发表版 Parallel Computing 27(3),2001,201–222，DOI 10.1016/S0167-8191(00)00102-2|REGO2000.body；定点读 §2.1/2.2、§3.1 和 strategic oscillation；图像核对 PDF 页7/8/9，文本约683–720行|已有复合移位、增量 trial value、受控不可行中间状态与可行提交。该实现第一层要求可行是其具体限制，不由此声称所有 ejection-chain 均禁止首次不可行。|
|Sontrop, van der Horn, Uetz, Fast Ejection Chain Algorithms for Vehicle Routing with Time Windows，2005 METEOR RM013，DOI 10.26481/umamet.2005013|FAST_CHAIN.body；官方封面、§1、§2.1–2.3、§3.1；核对 PAGE-05 的 CDR 图|已有针对非对称性的 reference structure、S/E/T 转换、候选邻域、tabu/ILS。添加风/资源特征不使普通转换成为新步骤。|
|Gendreau, Guertin, Potvin, Séguin，Neighborhood search heuristics for a dynamic vehicle dispatching problem with pick-ups and deliveries，TRC14(3),2006,157–174，DOI 10.1016/j.trc.2006.03.002|两次直接 HTTP 均 TLS 超时；web 打开大学原站得到访问拒绝页、出版社403。仅读取大学原 PDF 被搜索引擎索引的 §3.1.2 段落和出版社元数据，未取得完整 PDF|该原段已有带层限制的 constrained shortest path、intra-layer 重排及已完成 pickup 限制、启发式 Floyd–Warshall；不把固定前缀或最短路本身申报为创新。|
|Luo等，Learning to Insert for Constructive Neural Vehicle Routing Solver，arXiv2505.13904v3，2025-10-30更新|Atom 核对版本；HTML 全文取得、文本提取；实际读 §2–3（TEXT125–191附近）、§4（655–675附近）、附录B.3/相关比较说明|它学习任意插入位置、采用 SL 标签及 local reconstruction；并非本项目直接执行后的物理前缀。区别是动作/约束，不自动产生新学习法。作者库由原文确认为 https://github.com/CIAM-Group/L2C_Insert；未取得或运行作者代码。|
|Falkner等，Large Neighborhood Search based on Neural Construction Heuristics，arXiv2205.00772v2，2022-05-10更新|Atom 核对版本；HTML 全文取得；实际读 TEXT34–125（NCH/JAMPR 动作、扩展、Alg1和repair）|已有(route,node)并行构造、RL训练、NCH repair、部分路线保持及 LNS。当前 HTML 正文渲染日期2026不是论文版本日期。作者库为原文明示 https://github.com/jokofa/JAMPR_plus；未运行模型。|
|已有本地 station-bank 与 nonbottleneck-credit 修复|本地 MECHANISM_SPEC/REPORT 及冻结原 scorer 源码直接复用|有限站池阈值组合和非瓶颈站降成本已经存在；本轮只补当前物理前缀/动作后尾部生成接口，不把静态池组合或之前的 M12→M7 当本轮新结果。|

主URL：

- https://neo.lcc.uma.es/vrp/wp-content<EXECUTION_PATH>
- https://cris.maastrichtuniversity.nl/ws/files/669165/guid-9f287323-4672-421b-9cef-fa9de04f5a91-ASSET1.0.pdf
- https://www-labs.iro.umontreal.ca/~potvin/trc.pdf
- https://www.sciencedirect.com/science/article/pii/S0968090X06000349
- https://arxiv.org/html/2505.13904v3
- https://arxiv.org/html/2205.00772v2

直接 HTTP 8次：6个200（2PDF、2Atom、2HTML），2次TLS超时，失败receipt保留。web检索另记，不能计作8次HTTP的成功下载。WEB_DISCOVERY_0/1/2/3是4批完整工具JSON；另外2批仅保留对话工具原记录与 evidence/WEB_TOOL_LOG.md 的调用/结果摘要，未声称有完整本地原始JSON。

本轮查新足够否定“普通补偿链本身就是新机制”，不构成穷尽新颖性证明。新工程的共享索引/阈值组合也作为公共标准组件，不因为手写例有效就重判G0。
