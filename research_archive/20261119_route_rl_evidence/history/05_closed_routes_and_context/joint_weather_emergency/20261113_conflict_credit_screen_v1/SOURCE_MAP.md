# 主来源与实际阅读范围

6份PDF由FETCH_SOURCES.py获取；HTTP均200、PDF magic有效、pdftotext均exit0。每份URL、响应头、字节和SHA见sources/*_HTTP.json和HTTP_RECEIPTS.json。以下是方法节定向阅读，不声称全文每页精读或复现实验。

|来源|版本/直接链接|本次读取的本地文本范围|支持的有限结论|
|---|---|---|---|
|P01 NeuOpt/GIRE|[NeurIPS 2023](https://papers.nips.cc/paper_files/paper/2023/file/9bae70d354793a95fa18751888cea07d-Paper-Conference.pdf)|P01_NeuOpt.txt 342–406；另读官方PDF §4.1动作定义|已有违约特征、可行/不可行探索统计和shaping；k-opt是改进动作，不直接采用为物理actor。|
|P02 Ortiz-Haro等|[ICRA 2023作者全文](https://quimortiz.github.io/assets/icra23_gnn.pdf)，DOI 10.1109/ICRA48891.2023.10160887|P02_FactoredConflict.txt 117–245；§III-A–D、式2–5、Alg1|已有最小不可行子图定义、变量分类、连通分量候选及Solve/Reduce复核；不是本项目路线cap实现。|
|P03 CaR|[arXiv 2602.16012v1](https://arxiv.org/abs/2602.16012v1)，PDF标Published at ICLR2026|P03_CaR.txt 303–405；§4.2、式3–5；官方HTML §2–3|已有构造/轻量改进联合训练和改进后伪标签监督。它的完整改进actor不符合本项目直接物理动作域。|
|P04 PIP/PIP-D|[arXiv 2410.21066v1](https://arxiv.org/abs/2410.21066v1)|P04_PIP.txt 237–390；§4.2–4.3；官方HTML §4.1|已有Lagrangian、one-step前瞻不可行mask、辅助decoder与加权BCE。精确全域mask不可算与该文采用近似前瞻是不同主张。|
|P05 Semantic Loss|[ICML2018正式全文](https://proceedings.mlr.press/v80/xu18h/xu18h.pdf)|P05_SemanticLoss.txt 105–151；§3.1 Definition1及§3.2开头|满足赋值概率的负log早已有原式；其独立Bernoulli输出形式不能不加说明地套到自回归访问上下文。|
|P06 PLPG|[IJCAI2023正式全文](https://www.ijcai.org/proceedings/2023/0637.pdf)|P06_LogicShield.txt 204–267；另读正式PDF §3–4式2–3|已有策略安全概率重权和满足概率loss与PG组合；本地正式版是§5式5–6，网页另一解析呈现§4式6–7，报告以本地PDF为准。|

OpenReview两次web读取出现browser challenge，未将验证页当论文。CaR改用作者arXiv公开稿；不推断2025 workshop稿与2026正式稿字节相同。本包不执行、修改或声称复现任何作者代码。

初轮发现时，arXiv2504.02383和IJCAI2024/0218只有摘要。随后已补取两份全文并定向读方法，原件/HTTP收据另存pricing_sources；范围和不应外推的结论见PRICING_FIRST_READ。它们不计入上表六份冲突信用来源，也不代表新方法已定义或G0通过。
