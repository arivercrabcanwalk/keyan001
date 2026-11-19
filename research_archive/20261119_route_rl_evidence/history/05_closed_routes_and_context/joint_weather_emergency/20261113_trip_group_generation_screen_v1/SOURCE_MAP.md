# 主源与实际读取范围

本次沿用nature-academic-search多源检索流程。学术MCP/AgentKey检索工具未挂载，使用内建web发现与主源HTTP。WEB_DISCOVERY.json保留上一轮已发现结果，未重搜同一轮；ADDITIONAL_DISCOVERY仅保存部分后续发现，不冒称完整浏览日志。以下“读”指所列方法段，不声称全文精读。

|ID|主源/版本|实际读取|本项目含义|
|---|---|---|---|
|P01|[PolyNet, ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/c7b9810b2e27bccdc8d605a3a54c8cd6-Paper-Conference.pdf)|§3.2–3.5；本地txt216–310附近|单decoder条件码、best-only更新与独立多策略采样已有先例。|
|P02|[MDAM, AAAI2021](https://cdn.aaai.org/ojs/17430/17430-13-20924-1-2-20210518.pdf)|多decoder/beam与合并/Training；txt146–265|多策略、KL与beam内支配合并不能换名作新操作。|
|P03|[UDC, NeurIPS2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/0b8e4c8468273ee3bafb288229c0acbc-Paper-Conference.pdf)|§3.2 DCR；txt300–345及后续公式|分解后重构边界、联合训练已有先例；未迁移为本项目算子选择。|
|P04|[ASAP, ICML2026](https://proceedings.mlr.press/v306/fang26t.html)|§4.1–4.2与两阶段训练/适应；txt230–375|物理候选提议再选择、条件化/快速适应已有先例；不把其论文性能外推到本域。|
|P05|[MARCO, IJCAI2024](https://ijcai.org/proceedings/2024/0766.pdf)|§3–3.1、Algorithm1–2、Constructive methods范围；txt120–225|历史解检索、共享记忆及质量/新颖性权衡已用于构造。|
|P06|[Population-based architectures, arXiv2601.08696v1](https://arxiv.org/html/2601.08696v1)|§III、IV-B及相邻IV-C；txt431–495|参考解集合+探索权重+质量/距离奖励的条件构造直接覆盖当前简化草案。是预印本，不冒称已正式接收。|
|P07|[AGFN, ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/b210c387381713a14a4f5a607aff3520-Paper-Conference.pdf)|§3.1正反向/TB、§3.2判别器及AppendixA解释|GFN路线生成、标准TB和质量反馈不是新原语；本文未运行其代码。|
|P08b|[HBG, NeurIPS2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/1898054a9392207250ad9cfde5286b2c-Paper-Conference.pdf)|§3.2.2，定义1/式4–7、§3.2.3 depot-guided推理；本地txt300–400及web原文|多趟顺序/方向反向计数与TB/DB组合已有直接先例。单序列计数不能未经推导套给双slot。|
|P09|[EVRP with multiple technologies, TRC2023](https://doi.org/10.1016/j.trc.2023.104374)|web返回出版社§5 Branching完整相关段；本地作者稿HTTP403，未读到PDF|Ryan–Foster目标对同趟/异趟、open-node资源和join检查已有先例。|

共10次本地HTTP下载：8份有效PDF、2份403 HTML（OpenReview与P09作者稿），失败正文和headers原样保存，见HTTP_AND_TEXT_RECEIPTS。HBG OpenReview受阻后用正式会议主源成功取得，不把两者计作两篇。ASAP web解析器报unsupported content-type，curl取得有效PDF且pdftotext通过；未把web失败写为读成功。

已有GaS/KERL/ECHO/POMO-CG/NCG/P-MOCO/MACSIM/PKPO/SBS/Gumbeldore/PIP/PLPG历史表直接复用，本次未重新开展其整套审计。恒风闭合度量/变换是已完成结果，本次查到旧C07–C09/C23记录后立即复用，不计新发现。

有限阅读没有证明全领域不存在相同组合。关闭的仅是MECHANISM_SPEC中明确的简化草案；剩余q问题也不因没有发现同文献就自动取得原创身份。

