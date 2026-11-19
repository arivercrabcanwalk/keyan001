# 原文与候选边界

沿用nature-academic-search的multi-source-search流程；当前工具目录中AgentKey find_tools/academic MCP均未暴露，未安装连接器，使用web发现/官方原文curl。仅原论文支持技术判断；发现的二手/自动综述不作为先例排除证据。sources保留原文、文本、HTTP成功/失败和搜索原始结果。

|原文|本轮实际读取位置|与当前候选的关系|
|---|---|---|
|[Abbas et al., Bottleneck Potentials in Markov Random Fields, ICCV2019](https://openaccess.thecvf.com/content_ICCV_2019/papers/Abbas_Bottleneck_Potentials_in_Markov_Random_Fields_ICCV_2019_paper.pdf)|标题/摘要/相关工作、§3.2/§4.1、unary bottleneck算法、Prop1；本地BMRF_main.txt约210–245行|明确阈值排序、最低线性费用、完整profile及多次改变线性势时复用排序。关闭“仅统一排序复用足以创新”的原下一步理由；未证明它覆盖上包每个hard-cap双层堆细节。|
|[同文SI](https://openaccess.thecvf.com/content_ICCV_2019/supplemental/Abbas_Bottleneck_Potentials_in_ICCV_2019_supplemental.pdf)|§6.2和完整Min Marginals BMRF算法，BMRF_SI.txt约106–187行|已明确有固定标签min-marginal、阈值流、前后向最短路及受影响节点更新；不再说批量min-marginal没有先例。|
|[Fast Best-of-N Decoding via Speculative Rejection, NeurIPS2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/3950f6bf5c2eb7435ecf58eaa85cc8c2-Paper-Conference.pdf)|§2、§4.1、§4.2/Algorithm1与式3–6，本地约119–194、245–379行|用partial/full reward相关性和分位数拒绝率alpha保留高分候选。支持“提前停止已有”，不支持逐随机种子F/D/LOO梯度严格等价。并未完整精读全部实验/附录。|
|[Kool et al., Stochastic Beams and Where to Find Them, ICML2019](https://proceedings.mlr.press/v97/kool19a/kool19a.pdf)|§3的Gumbel树递推/上下界剪枝、Algorithm1与摘要/页信息，Kool2019.txt约165–295行|已有保留精确top-k的上下界剪枝，产生without-replacement序列。不能把“精确剪枝生成”本身当原创；本文目标是原IID潜在批次全部单删除值和LOO估计器的路径保留。|
|[Minimal Witness Reinforcement Learning, arXiv:2610.07226v3](https://arxiv.org/abs/2610.07226v3)|官网版本/作者/摘要；§3.2–§3.4、式6、Prop3、leave-two-out讨论，MWRL.txt约230–414行|普通组删除信用、重复/冗余候选零信用已有明确先例。该阅读范围未见本任务的物理前缀LB和保护所有未来单删除上下文的在线包络构造；这不是穷尽新颖性证明。其l2o信用依赖双删除，本候选只保证l1o，不能外推到l2o。|

MWRL的发现来自二手页面，以上技术结论已改追arXiv官方v3全文。新HTTP Kool2019与MWRL均200、pdftotext exit0；此前CVF web 403、猜测arXiv页面404及curl成功收据保留其原时点。文件下载不等于全文精读。

本候选与这些原式有具体可检验差异：不是按H剪枝，而是用全部D的包络来保留原强LOO随机变量；不是更换动作/分布/比较对象。其独立发表价值、完整查新和大图费用均未证。此次只做新有界工程核对，不抬G0/G3。
