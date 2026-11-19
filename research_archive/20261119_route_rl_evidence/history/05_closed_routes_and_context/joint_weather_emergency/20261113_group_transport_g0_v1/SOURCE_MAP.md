# 主源与实际读取范围

继续使用nature-academic-search的multi-source-search流程。学术MCP/AgentKey检索入口未挂载，使用内建web及主源HTTP；没有把搜索摘要当方法阅读。本包8+4条新查询及上轮4条搜索原件分别保存在evidence/portfolio_coupling_search*.json；第一轮相关性很低，未把无关结果计作进展。仅以下3份新主源读取了列明的方法范围，均HTTP200/有效PDF/pdftotext成功，字节/hash/headers见evidence/sources/HTTP_RECEIPTS.json。不是全文精读或文献穷尽证明。

|主源|实际读取范围|对本候选的约束|
|---|---|---|
|[CorrSynth, EMNLP2024](https://aclanthology.org/2024.emnlp-main.899/)|正文§3.1–3.2，式1–3；web PDF lines192–279|并行轨迹间的logit对比、相关生成已有先例。其式1–3改变单轨迹分布；不能把所有并行相关采样说成新颖，也不能声称本组tilt控制是其忠实复现。|
|[Cao等，Scalable Bi-causal OT，arXiv2605.17271v1](https://arxiv.org/html/2605.17271v1)|§2.1/一阶Markov核，式3–8；§4.1联合路径因子化与式29–31；web lines207–239/393–409|因果联合核、边际过程保持和联合路径score均属通用先例。本文使用KL松弛求一般过程耦合；本候选只是一种固定离散物理分组代价的组合，不主张新OT或一般policy-gradient定理。预印本身份保留，不冒称接收。|
|[Altschuler/Weed/Rigollet，NIPS2017，arXiv1705.09634v2](https://arxiv.org/html/1705.09634v2)|§2 Algorithm2全部六步、§3.1、§4 Lemma7；web lines96–133/271–279|固定迭代后round到边际可行点已有标准算法。12轮实现不是精确最优OT，浮点只按实测误差表述。|

旧PolyNet/MDAM/MARCO/PB-NCO/HBG、SBS/Gumbeldore以及固定风变换结论直接引用上包SOURCE_MAP，不重下载或重跑。ARMS/CARMS及普通antithetic不作为本项目原创；本包CDF控制只测试固定类别顺序的反相关，不冒称运行了CARMS梯度估计。

有限新增组合是：生成过程中基于已经不可撤销、且不受公共整趟重新分配影响的同/异趟承诺形成D，以边际约束联合核安排两个物理动作。相同D的无约束概率重加权同场比较。这个可执行差别允许有界工程筛查，并没有提前确立原创性、RL优势或G0/G3通过。
