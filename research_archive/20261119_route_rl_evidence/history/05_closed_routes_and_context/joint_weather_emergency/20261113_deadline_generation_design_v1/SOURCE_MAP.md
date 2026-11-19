# 原文、版本与实际读取范围

本表记录本包已经发生的定向方法阅读；下载不等于全文精读。所有HTTP原始响应、响应头和逐请求收据留在sources/。ALL_HTTP_RECEIPTS_INDEX.json是七请求总索引；HTTP_RECEIPTS.json只包含首批五请求，不是总分母。

|ID／原稿|实际读取范围（提取文本行）|支持的判断与边界|
|---|---|---|
|P01：[Heuristic Rectangle Splitting](https://arxiv.org/pdf/1705.10174v1)，Matl/Hartl/Vidal，v1|175–245、304–433、504–559；ε-约束、Alg.1、热启动和solution harvesting|阈值子问题及跨阈值搜索复用已有先例。其平衡目标是route-length range，不能冒称我们的typed minmax硬cap求解器。|
|P02：[Pareto Set Learning for Neural Multi-Objective Combinatorial Optimization](https://arxiv.org/pdf/2203.15386v1)，Lin/Yang/Zhang，ICLR2022版本|180–225、265–321、364–429；scalarization、条件decoder、REINFORCE|偏好条件化和多偏好训练已有先例；文中使用Tchebycheff，线性加权和反例不能否定该方法。|
|P03：[Stochastic Beams and Where to Find Them](https://proceedings.mlr.press/v97/kool19a/kool19a.pdf)，Kool/van Hoof/Welling，ICML2019|121–285；§2.3–2.4、§3.1|Gumbel Top-k、条件top-down树和无放回序列采样。没有声称本文实现我们的deadline分组。|
|P04b：[List-Level Distribution Coupling with Applications to Speculative Decoding and Lossy Compression](https://arxiv.org/pdf/2506.05632v1)，Rowan/Phan/Khisti，v1|开头及§3/Alg.1，约124–193；部分工具输出截断|共享指数噪声耦合分类分布。归档v1标题与后续Gumbel-max List Sampling标题区分，不混称同字节版本；不声称精读全部证明。|
|P05：[Self-Improvement for Neural Combinatorial Optimization: Sample without Replacement, but Improvement](https://arxiv.org/pdf/2403.15180v1)，Pirnay/Grimm，v1|281–317、328–376；§4.1–4.2|增量trie、分轮SBS、样本优势反馈已有。普通前缀缓存不能单独作为新增机制。|
|P06：[MACSIM](https://arxiv.org/pdf/2510.12273v1)，同v1重复获取|本轮方法网页再读；完整方法与固定源码核对直接复用旧interleaving包|重复下载不计新增研究进展，不重做loss/梯度或20交错。旧源码commit为b08a608ea487933a3afd332d36b92d5d8d55325e。|

POMO-CG 2504.02383v1和NCG的原文与首读复用上一包PRICING_FIRST_READ.md及pricing_sources/；本轮未再下载。POMO-CG已直接逐节点生成池外列、多起点生成多列，不能将这两点单独视为增量。经典LP pricing可保留暂时不改善整数解的新列。

Reiter/Gutjahr 2012，DOI 10.1007/s10100-010-0158-3，只取得出版元数据/摘要，DOI打开失败；不作为已读全文依据。

七次原文请求：六份有效PDF且提取成功，一份HTTP403 HTML。P04_GumbelList.pdf实际是403响应，pdf_magic=false，原样保留；不能用它支持论文内容。P04b为其后单独获取的有效v1，不覆写403原件。六份有效PDF中P06为重复，因而不是六份新读论文。精确PDF/text SHA以各_RECEIPT.json及总索引为准。

本包先前另有OpenAlex HTTP429及web打开失败；不把搜索摘要作为方法全文。SSH成功后的store(undefined)编排报错不是SSH失败；这些会话级事实来自接续记录，未伪造新的逐请求收据。学术MCP/AgentKey未挂载，使用内建web和公开HTTP；没有重试OpenAlex或重启已完成搜索。
