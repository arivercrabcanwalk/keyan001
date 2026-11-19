# 本轮来源与逐式对照

通过已加载的nature-academic-search多源工作流，读取本地既有证据，并用公开arXiv HTTP检索。学术搜索MCP和AgentKey查询工具未挂载；未安装或配置服务。5组发现请求得到46条元数据记录（未宣称去重后46篇），4份HTML原文下载，合计9次HTTP均200；另有2条查询的一次web搜索，结果保存在NEXT_DIRECTION_WEB_DISCOVERY.json，不混入9次下载账。

“取得HTML”与“实际读完全文”分开。以下仅主张定点读取列出的正文和证明/实验片段；未运行、下载或声称复现作者代码。

|来源|本地文本行/原文位置|本轮结论与边界|
|---|---|---|
|[The Mirage of Action-Dependent Baselines in Reinforcement Learning](https://arxiv.org/html/1802.10031v3)|MIRAGE_TEXT.txt 74–148，§2.2式(2)、§3式(3)、§4开头|动作相关控制变量必须加回对动作求期望的梯度。其方差分解区分尾部、动作与状态来源；作者在所测任务的负结果不是所有路线问题无效的定理。本轮必须比强状态baseline，不能只比无baseline。|
|[From Importance Sampling to Doubly Robust Policy Gradient](https://arxiv.org/html/1910.09066v3)|DRPG_TEXT.txt 220–303，§5.1 Theorem3式(8)、stop-gradient特例式(11)、§5.2 Theorem6式(12)|普通纠偏action-CV及轨迹相关修正均已有先例；其广义估计还利用Q梯度。当前独立probe是自己的固定策略组合，不等同实现作者完整DR-PG，不把DR-PG排除在后续强学习对照外。|
|[Policy Gradient with Active Importance Sampling](https://arxiv.org/html/2405.05630v1)|ACTIVE_IS_TEXT.txt 106–146，Theorem1式(9–12)、§3.2式(13–15)；182附近defensive mixture；267–280总样本与biased重用；834–888证明片段|向量PG的最优轨迹采样密度按梯度范数重权，defensive混合与行为策略拟合已有先例。本包的区间宽度只最小化残差二阶矩上界，未证明实际方差最优；不把作者实用biased版本当严格无偏。|
|[Dynamic Model Predictive Shielding for Provably Safe Reinforcement Learning](https://arxiv.org/html/2405.13863v2)|DMPS_TEXT.txt 128–160恢复策略；161–250 §5式(1–3)/Algorithm1；694规划开销；1306–1338代码披露|动态备用规划、恢复可行性与神经策略互相学习已有先例。其规划渐近条件/折扣regret不直接证明本项目γ=1有限路线6/12s质量；本包逐次见证M不增的归纳单独写出。正文仅说明代码随补充提交与计划开放，本轮未取得固定作者commit。|

其余发现条目，包括2605.07094、2609.33543 OSCC、2206.05165、2206.06827，仅元数据/摘要；不据此断言已掌握其原式或完全覆盖本包。9个body/receipt及46条记录在literature/，错误或阴性结果不得由下一包覆盖。

## 新组合与先例的边界

单独的midpoint、score-function、控制变量纠偏、重要性采样和备用见证都不是新发明。本包实际新增并检验的组合是：动作后对完整物理见证作前缀保留改写，以后每步保证见证M不增，从而让[L,U]逐条约束同一策略的实际尾部；由区间生成独立probe分配，并在零宽时消除尾部模拟。主轨迹仍按π，避免只乘局部π/r的状态占用错误。

这是有限正确性的组合检验，没有穷尽新颖性证书，也没有训练效果。效率结果失败，故本实现已关闭，不以“原文未逐字出现”作为继续训练理由。

## 接续检索已发现的直接障碍

一次web发现检索指向[Node Ejection Chains for the Vehicle Routing Problem](https://neo.lcc.uma.es/vrp/wp-content<EXECUTION_PATH>)：检索摘要已描述受控不可行中间移位组成可行复合链。因此下一项若只是“移走另一个目标再修复”，仍是普通ejection-chain，不能换名立项。当前仅发现该PDF，尚未下载/精读，不使用搜索引擎显示的近期日期作为原论文年份。

同一次检索发现[动态VRP策略比较](https://doi.org/10.1016/j.cie.2024.110747)的完整路线重算/偏离策略；当前仅网页检索片段，不能把其结果移植至本项目。下一项先确认真实前缀、typed battery、全图融资和完整cap如何共同改变算法步骤，再决定是否值得新工程运行。
