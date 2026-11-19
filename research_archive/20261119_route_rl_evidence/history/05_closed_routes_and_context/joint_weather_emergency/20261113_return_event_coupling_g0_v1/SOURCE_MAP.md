# 先例与本次读取

沿用nature-academic-search的multi-source-search流程。学术MCP和AgentKey三工具未挂载，使用公开主源与内建web；不改客户端配置。WEB_SEARCH_LOG.json保存三轮九条定向发现查询及四个原文打开结果。只采用以下原文方法范围作机制判断，不把搜索结果当全文。

|原文|本次方法读取（本地txt行）|已有步骤及本候选边界|
|---|---|---|
|[An Analysis of Measure-Valued Derivatives for Policy Gradients](https://arxiv.org/pdf/2203.03917v1)|80–220；§2–3/Table1|分布导数写作两个期望之差；采样相关性影响方差，需计额外求值。此通用原理和局部差分梯度不是本项目原创。|
|[Coupled Gradient Estimators for Discrete Latent Variables](https://proceedings.neurips.cc/paper_files/paper/2021/file/cd0b43eac0392accf3624b7372dec36e-Paper.pdf)，NeurIPS2021|90–182；§2–3，Eq3及support要求|相关根类别一般需要修正，不能因保持边际就直接套iid LOO。本候选保持根动作独立，仅耦合条件续接，不套其factorial-discrete简化到整个路线。|
|[Weighted Automata Algorithms](https://www.cs.brandeis.edu/~cs136a/CS136a_docs/Mohri_WeightedAutomataAlgorithms_Handbook.pdf)，Mohri|1021–1085；§6.1/Eq28–29/Thm4及算法|加权ε闭包与等价消除已有。本候选RETURN不是物理无操作；只在训练模拟器把其概率和真实资源转移整合至下一服务事件，恢复路径仍保留RETURN。|
|[An Efficient Finite Difference Method for Parameter Sensitivities of Continuous Time Markov Chains](https://people.math.wisc.edu/~dfanderson/papers/AndersonCFD_SIAM.pdf)，Anderson2012|297–430；§3.1/Eq7|共享事件通道与剩余质量保边际，coupling收益与实现费用均需比较。其CTMC/有限差分不是本工程离散actor核，不能逐字等同或借用其方差阶结论。|

四次新HTTP均200、有效PDF且提取成功；原件、响应头、请求命令/退出码/hash见HTTP_RECEIPTS.json和sources/。只声称以上定向阅读，未声称全文精读或穷尽新颖性检索。

Cao的Event coupling and performance sensitivity analysis of generalized semi-Markov processes仅检索到出版页面/摘要；实际刊年1995，网页上线2016，未取全文，不作细节覆盖依据。搜索中的自动idea集合、博客、二手综述和专利页均未作方法证据。

旧MACSIM固定作者源、交错核对、SBS/Gumbeldore、前包共同H分解及全部删除/替换工程直接复用，未重新下载或重跑。当前候选的具体组合与旧微动作耦合/完整宏事件耦合有可执行差别；这种差别尚不等于论文级新颖性或训练收益。
