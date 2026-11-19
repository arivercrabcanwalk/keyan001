# 主源与实际阅读边界

沿用已读nature-academic-search multi-source-search工作流；学术MCP与AgentKey发现工具未挂载，本轮继续使用内建web及arXiv原站HTTP，不安装连接器。只以原文方法/附录支持判断。

1. Ni Zhang等，DEG: Diffusion-Enhanced GFlowNet for Solving Vehicle Routing Problems，arXiv:2610.39512v1，2026-10-29。https://arxiv.org/html/2610.39512v1 。已读§3、§4.1至4.2开头、Eq2–9，及Appendix B.1–B.4/Eq23–25。逐edge clean reward平均/zscore/CDF、Gaussian noise/clamp、有限population target与CVRP K偏置原文明确；不是新发现，不指责作者。未读完全文/未跑作者代码，原文的TSP/CVRP结论不直接当本typed无人机结果。
2. Zhenwei Wang等，Constraints Matrix Diffusion based Generative Neural Solver for Vehicle Routing Problems，arXiv:2603.07568v1，2026-03-08。https://arxiv.org/html/2603.07568v1 。已读§III-B、§IV-A/B、§IV-C/D/Eq17–26与训练步骤：同趟矩阵标签、HGS监督diffusion、freeze后REINFORCE actor。仅同趟矩阵/条件actor已有先例；本包不重现其科学实验。

HTTP HTML/PDF原件和SHA见HTTP_RECEIPTS.json；下载不等于全文精读。前一hindsight筛查的PCN/HPG原件与推导直接引用，不重跑。此前SOURCE_MAP中“只发现摘要”是较早时点；本文件记录后续已读方法范围。
