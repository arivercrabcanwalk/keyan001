# 原式、作者源码与结论范围

本包仅两份新主源全文。下列行号指本包保存的 `literature/*_primary.txt` 或原样 `.py`，HTML 是对应原字节；不是网页视觉行号。获取失败亦保留。摘要用于发现，以下裁决基于正文／源码。

|原始来源|直接证据|本项目可得结论／边界|
|---|---|---|
|N. Carrara, E. Leurent, R. Laroche, T. Urvoy, O.-A. Maillard, O. Pietquin, *Budgeted Reinforcement Learning in Continuous State Space*, [1903.01004v3](https://arxiv.org/html/1903.01004v3), 2019-05-27|BMDP_primary.txt 99–104，Eq(1)|收益最大化、费用约束都是期望；不能当每条完整物理路线的 hard cap。|
|同源 §2|106–174，Eq(2)–(12)、Theorem1–2|预算同时进入 state/action；vector Q 的 budgeted optimality 已有。Theorem1 是最优 Q 的固定点关系；Theorem2 明确最优控制算子一般不收缩，不能引用为一般 BFTQ 收敛证明。|
|同源 §3–4|175–238，Algorithm2–3|sample target＋regression、双值共享网络、凸包上相邻两点的随机混合已有。|
|同源 Appendix E.3.3|1133–1148，Listing1|明确给出 eleurent/rl-agents 安装线索；不是精确实验 commit 的证明。|
|H. Wiltzer, J. Farebrother, A. Gretton, M. Rowland, *Foundations of Multivariate Distributional Reinforcement Learning*, [2409.00328v1](https://arxiv.org/html/2409.00328v1), 2024-08-31|MVDRL_primary.txt 70–122，Eq(1)、Theorem2|固定 π 的联合 law 和 pushforward Bellman 已有；bounded cumulants、γ∈[0,1)。|
|同源 §4|123–200，Eq(3)–(6)、Theorem3|joint particle MMD TD 已被前作提出；本文给 BootProj 随机 DP 和高概率界。不能把全部粒子 TD 都说成有本文收敛保证。|
|同源 §5|201–308，Eq(7)、Algorithm1、Lemma1–2、Corollary2|QP 同时要求 p≥0、sum p=1；此处是真正的概率分布，不能把整篇方法一概叫负质量。|
|同源 §6|309–370，Eq(10)–(13)、Lemma5、Theorem5–6|signed mass-1 松弛使投影仿射；Theorem5 已包含回投概率单纯形的误差界。单纯发现 signed 值或添加 simplex 回投不是新切入。|
|同源 Appendix F|1377–1390|已有图像状态的神经 signed categorical target 拟合，target QP 不反传。是示例评价，不是 hard-cap 路线控制实验。|

作者源码固定到 `eleurent/rl-agents` commit **84df15ea977271e6a4d015f10f9f355f7e866890**，提交日期 **2024-01-13**。它晚于 BMDP v3；只声称来自文内明确作者库的固定版本，**未证为论文实验版本**。完整 tree 未截断。三个文件全读，只做 AST 解析，未 import／执行其依赖、网络、优化器或环境。

|源码|关键源行|已核内容|
|---|---|---|
|BMDP_bftq.py|129–148；150–188；252–305|收益／费用 target；对 hull mixture 的概率加权期望；两个 scalar loss 的加权和，不能称 joint law。代码另有 gamma_c 配置，本包不把它无条件等同论文单 γ 定理。|
|BMDP_greedy_policy.py|16–36；39–103；106–123|optimal_mixture 明言 expected cost；regular mixture 概率、not_solvable 状态、凸包 frontier 与预算输入已有。未运行边界或断言整个库无缺陷。|
|BMDP_models.py|6–57|预算 encoder 与 2*n_actions 输出已有；这不是联合分布估计器。|

本轮未为 MVDRL 固定作者代码；其正文公式已足以否定“联合 law／投影本身为新增操作”的主张。没有把缺代码当不存在实现的证据，也没有宣称完整证明附录或所有相关文献已逐行审完。

原件 SHA256：

```text
BMDP_arxiv.html 9a16be38f72a13bf025f0c9cada8f97ae4fcbe114bc3085999c4ae5fc4b555e2
MVDRL_arxiv.html 865e0abcfa6d4c29c379ff985de46df5219069b3c167a3649b0c66054f96d80b
BMDP_bftq.py e0df1479b30c3674f57bbb4ea7e062ee85ef568d143c81a0089072d008ae92b0
BMDP_greedy_policy.py 995de1b7cbd960bdbc47be2538a42d492f58bacbcf1da015b44a68adbab01cd1
BMDP_models.py 4e02991899fc5594e697ad055cab946b258908b94be59cd3b3d0c25e427682b6
```
