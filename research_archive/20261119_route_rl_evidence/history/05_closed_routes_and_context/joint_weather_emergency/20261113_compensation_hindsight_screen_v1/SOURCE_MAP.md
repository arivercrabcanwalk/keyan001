# 两份主来源的方法核对

沿用nature-academic-search的multi-source-search流程；本轮学术MCP与AgentKey的find_tools/describe_tool/execute_tool未挂载，使用内建web检索和主站HTTP读取，不安装/修改连接器。只以原文方法节支持以下结论，不以搜索摘要证明新颖性穷尽。

|主来源|已读范围|与本简单草案的关系|
|---|---|---|
|Mathieu Reymond, Eugenio Bargiacchi, Ann Nowé, *Pareto Conditioned Networks*, AAMAS2022；[arXiv2204.05036v1](https://arxiv.org/html/2204.05036v1)|§2.3、§4.1–4.3、Eq5；HTML同段|用达成回报重标各步，再以交叉熵训练单一条件策略；从自身轨迹形成数据。把return换成完整成本/完工时间仍不新增这一学习操作。未复现其实验，也未声称其处理本项目逐解cap。|
|Paulo Rauber, Avinash Ummadisingu, Filipe Mutz, Juergen Schmidhuber, *Hindsight policy gradients*, ICLR2019；[arXiv1711.06006v3](https://arxiv.org/html/1711.06006v3)|§2、§4–5，Eq1–2、6–12；Theorem4.1–4.4/5.1–5.2|目标改变时重新评价轨迹并用概率比校正；正文区分无偏估计和归一化加权估计。适用支持条件须逐项满足；局部路线的概率不自动等于公共组合后完整见证的分布。|

四个HTTP原件（两HTML、两PDF）均200且格式有效，字节与SHA见HTTP_RECEIPTS.json；仅主张以上HTML方法范围已读，不把下载等同全文精读/作者代码复现。PCN版本标注AAMAS2022，HPG版本标注ICLR2019；不将搜索引擎抓取日期当发表日期。

本轮曾误试PMLR的reymond22a地址，工具返回不可访问；该地址未用于证据或会议信息。少量本地路径猜测读取失败亦保留在READOUT_ISSUES.json；没有科研执行失败被改为通过。

原有定义直接引用：`20261113_policy_continuation_g0_v1/NEXT_MECHANISM_DERIVATION.md`中的T_i强制插入对象；`20261113_common_h_delivery_g3_engineering_v1`的两站完整费用补偿收据；本轮均未重跑。推导中全bank score和支持边界是本项目的符号适配，不主张为新一般定理。

补充检索发现Constraints Matrix Diffusion(arXiv2603.07568)和DEG(arXiv2610.39512)。它们当前仅有发现摘要，不承担方法差异或创新裁决；下一对象须实际读方法，不能根据标题把diffusion换名通过G0。
