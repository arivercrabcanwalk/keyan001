# A已落实；相近研究实验设计调研

用户已选择A：后续固定风主比较使用同风作者完整解的成本上限 `Cw(Rw)+1e-7`，目标为完整返站 `Mw`。原无风S0和原数值C0跨风稳健性结果保留。当前无需用户再作决定。

本轮实际进行了20组发现检索，取得208条元数据，按DOI或规范化标题合并为189组；这不是189篇全文精读。选取21份可获取全文的实验/评测章节：16份新取得，5份复用已有主源；另登记1条只有元数据的弧巡检论文。P03/P16属同一研究线；AM-E用的是作者博士论文相关章。全部HTTP/版本/哈希/读取位置与失败保存，没有运行论文代码，也没有新科研评价。

## 已证实事实

**最相近的实验模板有三类，可组合使用。**

1. [多站多趟无人机研究](https://arxiv.org/html/2207.06155v1)采用10–200目标、每规模20随机实例，先小图精确MIP，再大图matheuristic，并改变续航、服务时间与站/机数。正文§3把“total completion time”明确定义为各机累计趟时间的最大值，确实接近我们的makespan；不能仅按标题理解为总和。它未含我们的风与全成本cap，且会预删不可达目标，我们不沿用该删图规则。
2. [Li HCVRP](https://arxiv.org/html/2110.02629v2)、[DPN](https://arxiv.org/html/2405.17272v2)、[Equity-Transformer](https://arxiv.org/html/2306.02689v3)、ECHO分别提供直接选车/节点、min-max分配和规模泛化的对照结构。Li每规模同一1,280测试图配对所有方法，并保留强SISR；DPN/ET有fine-tune、采样和增强，这些都应计计算并和zero-shot分开。
3. [Routing Arena](https://arxiv.org/html/2310.04140v1)同时比较固定时间质量与anytime轨迹，纳入HGS/FILO/LKH等强OR。这比“神经模型一次forward很快”更接近我们需要回答的6/12s交付问题。其跨硬件PassMark近似不替代<REMOVED_ENDPOINT>实测。

**对RL增量最有用的消融已经有先例。** [KERL](https://arxiv.org/html/2605.14416v1)比较训练时使用DP反馈与仅事后DP；[GaS](https://arxiv.org/html/2508.17087v1)比较最优split与RL直接RETURN。这支持我们保留“同组件无学习/BC/标准RL/新机制”四组，不支持把普通RL＋Split当新颖性。原始actor与共享后处理结果均应报告。

**泛化与随机性必须拆开。** [RRNCO](https://arxiv.org/html/2503.16159v2)区分已见城市新实例、未见城市、cluster；对我们意味着按基础地图隔离，而不是仅换风seed。[统计评测论文](https://arxiv.org/html/2108.13264v4)强调区间估计和运行间变异。[MixRoute](https://arxiv.org/html/2611.11977v1)附录明确四次独立重训、只在六个代表分布报告；这是近期预印本，不是所有实验都有多seed的证据。测试图数、解码采样数、训练seed三者不可互换。

## 未证实假说

固定风有向能耗、异构多趟与累计duty的联合结构，可能使跨实例学习在6/12s内产生超越强ALNS的路线；当前没有这样的证据。十个独立训练seed是本方案的建议目标，也不保证有足够功效或保证RL获胜。G0新步骤和完整G3资格仍需补齐。

## 失败、限制与关闭方向

旧完整模板索引未显示加速、ECHO迁移、普通joint-split等关闭结论保留；本轮未重跑旧审计、1200复现、48图、104环境、20交错或训练。

文献中存在我们不应照搬的比较：在线RL对离线无风/固定margin方法、只用弱神经对手、跨论文不同测试图比均值、用预测准确率替代完整路线、将fine-tune写作zero-shot、仅报告成功子集。Weather-Aware Transformer主要是A*/Dijkstra标签监督与next-node分类，并非全路线RL优越证据。相关原文未充分披露的训练seed/划分字段均记NR，不推断作者一定没做。

38次HTTP：35次200、1次429、1次403、1次TLS证书错误；失败完整留存。P15出版社阻挡页不当全文。两个相近风研究版本不当独立实证。一次本地复用文件的相对路径错误已纠正，未运行科研代码。

## 下一项有界工作

已交付[正式A合同](S_CONST_APPROVED_CONTRACT.md)、[逐源对照表](EXPERIMENT_DESIGN_COMPARISON.md)和[具体实验矩阵](EXPERIMENT_MATRIX_DRAFT.md)。矩阵保留作者风适配、成本中性重排、强ALNS；统一完整6/12s；共享组件的无学习/BC/标准RL控制；建议主方法10独立重训、240新底图×3风条件的Formal草案，按底图聚类且全失败入账。样本/seed/预算数字尚未冻结或执行，不占旧满额人口。

接下来回到一个实质G0对象：无需完整模板枚举的双向部分资源标签，明确相对普通逐删除DP/普通join少做了什么，并给出反例和包含生成/边界/恢复的完整成本。如果只是已有算法换名就关闭；有具体新步骤才另冻<REMOVED_ENDPOINT>验证。G0/G3通过、新人口与预算冻结后，才执行充分多seed、消融和一次全新Formal。

## 是否需要用户决策

目前不需要。A已生效；当前继续工作所需的信息和权限齐备。整体研究/G8尚未完成，G0/G3没有因本次调研而被提升。

审计入口：SOURCE_LEDGER.json、READ_LEDGER.json、SEARCH_SUMMARY.json、NETWORK_LEDGER.json、STATE.json、GATE_DECISIONS.json、VERIFICATION.txt。所有“作者结果”均为原文报告，不冒称本项目复现。
