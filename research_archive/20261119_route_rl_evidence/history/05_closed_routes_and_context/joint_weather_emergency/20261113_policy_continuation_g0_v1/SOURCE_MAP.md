# 本轮原式查新与实际阅读范围

沿用nature-academic-search的multi-source-search流程。当前tool catalog未暴露academic-search MCP或AgentKey find_tools/describe_tool/execute_tool；使用web发现、正式原文及系统curl正常TLS，不安装连接器，不将元数据命中数当全文精读数。原始web响应、失败和HTTP见sources。本轮3次curl均HTTP200、exit0；前两次来自接续前已保存记录，第三次为本轮PKPO。

| 原研究 | 原文/身份与实际阅读 | 对当前机制的约束 |
|---|---|---|
| UCPO，AAAI 2026，DOI 10.1609/aaai.v40i43.41017 | 正式[AAAI PDF](https://ojs.aaai.org/index.php/AAAI/article/download/41017/44978)，sources/UCPO_final.pdf；SHA f6ff6423ecf4b5c02339cfdce1dae897f17a1913fbec91d8af803a8206135924。接续前100–285行部分读取，本轮补260–335行，主要pp36902–36904式(1)–(3)、Alg1；未声称全文精读。 | 可行性分层及偏好loss不是新步骤；它按完整解排序，不直接给本站sample对跨站重组的删除值。 |
| LOLS，ICML 2015 | [PMLR PDF](https://proceedings.mlr.press/v37/changb15.pdf)，sources/LOLS.pdf；SHA 4f0886cb97a9af0609256adba348c2d29d36acf6f2f1f4c2592c0d0a6448d3d2。本轮105–150行，接续前120–225行，Alg1和式(2)已明确；未声称全文精读。 | learned roll-in/单步分支/混合rollout已知；不用其重命名G0。 |
| PKPO v5，Walder/Karkhanis，2026-06-10修订 | [arXiv v5](https://arxiv.org/abs/2505.15201v5)，sources/PKPO_v5.pdf；SHA 1a145105ca18a7d246d5eb0c20430c9aacdfcef9ba25399bbdcbaf3b42cfad57。本轮215–290、315–447行，§2.2/3.2/4.1–4.2，式(18)–(32)、定理4–6。 | 最大集合收益及低方差LOO、全部信用O(k+n log n)已有。当前预算耦合max+sum重组不等同独立标量max排序，但差别须落到共享sensitivity步骤，不把集合目标/恒等式当原创。 |
| RL-CMSA minmax mTSP，2602.23579v1 | [arXiv原文](https://arxiv.org/html/2602.23579v1)，复用../20261113_cap_conditioned_credit_v1/literature/cmsa_primary.txt。本轮130–185及185–207行，§3.2–3.6/部分§4，池去重、MILP、pair q值及age已核对。 | 已有路线池+精确重组+强化构造；其学习按入选解中的city-pair更新，不同于原hard-cap的全部采样副本删除扫描。不能因此说整个方案首创。 |
| Kuntz等product-form，2022卷/2021在线 | 复用../20261113_station_bank_control_v1/literature/productform_primary.txt，DOI 10.1007/s11222-021-10069-9；本轮只读开头1–65行及沿用既有包方法审查。 | 独立重组/乘积分布估计不是新贡献；当前是有限池最优而非product平均估计。 |
| Martello/Toth，EJOR 83(1995)621–638 | [出版商身份/摘要](https://www.sciencedirect.com/science/article/pii/0377221793E0271X)核对DOI 10.1016/0377-2217(93)E0271-X。新增[原论文OCR镜像](https://www.academia.edu/108860383/The_bottleneck_generalized_assignment_problem)，实际读网页L23–36，§2.2/§3、pp625–627。保存bmckp_author_mirror.json及bmckp_method_section.json；文件名author_mirror来自查询标签，不证明上传者身份。未取得PDF、未独立核印刷不等号/OCR。 | 原BMCKP已按value扫描并维护每组最低weight，排序后线性扫描；此组合器不是新算法。所读§3没有当前全部删除值/浮点两侧证书步骤，仍不据此作穷尽新颖性证明。 |

MECHANISM_SPEC是运行前冻结版本，其中“1995全文尚未取得”按PDF未取得仍成立；本表更新为已经读到原论文OCR方法范围，不能再记为完全没有读算法。其他新检索命中仅为发现，未阅读者不作排除先例的依据。没有运行任何外部作者源码或模型。

首个web发现调用结果未持久化为独立本地raw，本表只使用已保存的后续web响应作来源证据；下载receipt不补造web完整记录。本轮无穷尽检索或世界首次的结论。
