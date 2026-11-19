# 原式／固定源码／适用条件

本轮新增两份直接主源全文；元数据发现列表不等于精读。arXiv 两个查询与 CrossRef 查询原响应／收据均保留；CrossRef 的 A-star 文字检索返回天文学等无关结果，没有引用其排名证明任何机制。改用已核实的 arXiv ID 取得 A* Sampling 正文。

## 1. GeLaTo

[Tractable Control for Autoregressive Language Generation](https://arxiv.org/html/2304.07438v4)，Honghua Zhang、Meihua Dang、Nanyun Peng、Guy Van den Broeck，arXiv2304.07438v4，2023-11-15。原 HTML SHA256：`ad9e2d46a34b2c206e0f775c625f9361cb5a4a8dceadeb09d62e40725cc15d48`。

已读正文 §1–3、Algorithm1 与附录 A 递推推导；未声称独立复现其 §4 效果。§2 中先从基础 AR 模型蒸馏一个可推断概率模型 q，然后使用 q 的完整后缀约束概率指导 π。无监督 Eq(1) 是 `p(a|prefix,α)∝q(α|prefix+a)π(a|prefix)`；监督 Eq(2) 是 q 的条件动作分布与 π 的加权几何平均。正文明确讨论 quality β 与约束 α 的条件独立假设，不能把其替代模型的 h 当任意 actor 的精确 h。

§3 Eq(3) 使用 HMM 的 Markov 性。Algorithm1 预缓存约束子集／关键词后缀／位置／隐状态上的条件概率，再在每一步候选 token 上查询。文中粗略复杂度 `O(2^|α| n m)` 把词表及隐状态数视为常数；本问题的未服务集合、各 slot 的资源和连续累计费用尚未由此获得常数规模。不能用“支持 DP”宣称物理路线编译能在 6s/12s 完成。

作者库 [UCLA-StarAI/GeLaTo](https://github.com/UCLA-StarAI/GeLaTo/tree/b6e824eeb63723935049ff6c6b66672040648a59)，固定 commit `b6e824eeb63723935049ff6c6b66672040648a59`，2023-06-12T21:41:55Z，早于所读 v4，未证实为论文实验提交。完整 tree 非 truncated。

|原文件与本地原字节|已读对应|SHA256|
|---|---|---|
|src/hmm_model.py → literature/GELATO_hmm_model.py|全文；108行 initialize_cache，164–175行枚举约束子集，230行起 compute_logits 返回约束／无约束 logits|ae89f8b2a2fcd6aed11a61772fd7e86a3d37630756d389d10b71a85f54b35c84|
|src/decode.py → literature/GELATO_decode.py|全文；30行调用 compute_logits，57行监督几何混合，59行无监督 logit 校正，237行初始化缓存|7a7b42ba95e925047247927d35542844f2dbf149a9e8511e4a114cbe7155a05b|

`decode.py:240` 该入口实际 `do_sample=False`，配合 beam；不能因论文 Algorithm1 写 sample 就声称这个默认命令产生了其随机样本。源码本轮只读和 AST 检查，未导入／执行 torch、未加载模型／训练，不对作者效果、约束边界或实现的全面正确性作验收。

## 2. A* Sampling

[A* Sampling](https://arxiv.org/abs/1411.0030v2)，Chris J. Maddison、Daniel Tarlow、Tom Minka，v2 2015-01-26（首次提交2014-10-31）。原 PDF SHA256：`859d58c8b4b1d761db255f10e6c764b55e5e4e87c17d000a1430a84bf52fee83`。已读正文 §1–5、附录 Termination/Global-Bound 部分；不声称所有附录证明或实验均精读。pdftotext 只作本地原文提取。

§2 Eq(1–2) 给有限类别的 Gumbel-max；§3 Algorithm1 给 top-down 构造；§4 Algorithm2 以已知可采样基准 ν 和有上界的 log-density 差 o 搜索扰动最大值。正式 §4 方法明确为连续版，路线动作 DAG 的区域划分／mass／界需要另行定义，不能把本文当成现成 route solver。

§4 在完成 `incumbent lower bound ≥ 所有未展开区域 upper bound` 后，才证成返回样本的精确性。§5 与附录 Global-Bound 给常数全局界时迭代数的几何分布参数 `ρ=μ(Ω)/(exp(M)ν(Ω))`；这是概率一终止及其假设内的结论，不给任意实例在固定6s/12s内的交付保证。细化界能有实际收益，但必须证明本问题的界并计全部计算成本。

## 3. 仅发现、未精读的元数据

`ARXIV_CONSTRAINED_ITEMS.json` 含 Hidden Biases in Conditioning Autoregressive Models（2604.07855v1）等条目；`ARXIV_DIAGRAM_ITEMS.json` 含 weighted BDD／AOMDD／credal diagrams 等条目。本轮没有取得这些全文，不把摘要中的 hardness／tractability 当独立核实的定理。它们提示下一次专门原文核对，而非替代当前两主源。

没有论文投稿场次／影响力排名推断，没有穷尽查新主张。所有 HTTP status／URL／时间／字节与 hash 见 literature 中原收据。作者代码字节保持未改。
