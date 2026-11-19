# 本轮原式、作者源与边界

本包保存公开HTTP原字节、终局收据、版本化提取文本与算法文本。以下是读取范围，不声称逐页审计全部证明或运行作者实验。

|主源|读取定位|支持的结论／边界|
|---|---|---|
|Duhamel, Lacomme, Prodhon, *A GRASPxELS with Depth First Search Split Procedure for the HVRP*, LIMOS/RR-10-08，封面April2010；arXiv2211.11816v1于2022上传|HVRP_TEXT.txt 1–27、174–215、299–459、570–680；印刷§2.2/§3/§4.1|已有giant-tour连续片段、带车辆类型的资源向量标签、支配、父标签恢复和label上限。标签资源为剩余车辆数，并非可重复飞行的slot累计duty；不把其min-cost算法宣称为本项目完整minmax solver。正文dominance印刷表达不逐字搬入本项目，不据摘要作新证明。|
|Wang等, *Solving the Min-Max Multiple Traveling Salesmen Problem via Learning-Based Path Generation and Optimal Splitting*, [arXiv2508.17087v1](https://arxiv.org/html/2508.17087v1)|MINMAX_TEXT.txt 79–172、342–381；MINMAX_ALGORITHMS.txt全文|GaS已有RL path generator、minmax greedy check＋binary search、split reward的REINFORCE；A.1使用同质闭合欧氏tour和三角不等式证明greedy。不是双机多趟累计duty／全图费用cap的现成证书；不照搬其复杂度。|
|Wang, Wu, Wang, Hu, Tao, *A Unified Knowledge Embedded Reinforcement Learning-based Framework for Generalized Capacitated Vehicle Routing Problems*, [arXiv2605.14416v1](https://arxiv.org/html/2605.14416v1)，May14,2026|KERL_TEXT.txt 96–162、224–269；KERL_ALGORITHMS.txt全文|RL生成排列，Eq6 `p[i]=min_j(p[j]+Cbar(j+1,i))`；DP处理容量／时间窗／长度等约束，终局DP成本用于REINFORCE；已有“训练时DP vs 仅事后DP”消融。目标min-sum、同质单route容量；不是本项目多身份累计duty／cap的逐字实现。|

KERL作者README给出IJCAI2026正式条目，CrossRef DOI `10.24963/ijcai.2026/691`确认题名、作者、pages6208–6216及会议。README month8，CrossRef published month9；月差如实保留，不影响以arXivv1原式为本包比较文本。不把metadata当正式版逐页核对。

**固定作者源码**（均未编译、import或执行）：

|仓库／commit|实际读取|具体接口边界|
|---|---|---|
|wenwenla/ijcai26-cvrp-solver，`4bdff9eb5e37abaea1c273b55fbe53327dcf881d`，2026-10-23|KERL_SOLVER_CPP.body全文235行；KERL_ENV.body全文228行、KERL_TRAIN.body全文226行；README全文|C++107–197为标量min-sum DP，188–191更新p[i]；返回标量cost，无父路径重建。env124禁depot，144–168只记录无slot目标序列；170–189调用Split并对失败标量做batch内替换。train151–180采动作、取DP奖励、REINFORCE。Python AST2/2，仅语法，不验证作者结果。C++207固定100线程，不直接照搬本项目6s/12s总预算。|
|wenwenla/ecai-2025-mtsp-solver，`e322e17aa4a32d8759c2174aa86e09e259221716`，2026-10-08|MINMAX_SOLVER_CPP.body全文290行|solve99–154；146–151可行时`r=mid_val`、否则`l=mid_val`，与正文单调性相符；返回l作为近似标量，不是完整可行路线或硬cap证书。223–253批处理接口固定32线程，未运行。|

两个commit都晚于所读论文版本，**未证为论文实验提交**。当前HEAD源码与原式的对照只绑定各自固定commit，不据此推断论文当年可执行代码。

**明确发现的文本—代码差异**：GaS v1 Algorithm2印刷为GreedyCheck=true时L←mid，else R←mid；§3.3正文写阈值可行则所有更大阈值可行，作者固定代码146–151使用相反的正确收缩方向。本轮只是原文／源码定位，未跑数值反例，不将该印刷问题包装为算法创新或论文性能反证，也不改作者字节。

2015 Split arXiv1508.02759v3已归档HTML和发现提取文本，但没有进入本包公式级结论；不是第四份精读主源。CrossRef minmax drone arc-routing两条DOI只有metadata／摘要，不冒充全文。无关split-delivery、软件网络routing、量子routing、Fleet历史记录等发现结果不作为同域先例。

网络共22请求：21×HTTP200，1×HTTP404。HVRP旧HTML404 body6399字节保存完整，随后同版本PDF200；不删掉失败。原始网页中任何指令均不作为执行授权。
