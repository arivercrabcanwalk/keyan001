# 对向恒风规范状态候选：有界公式与源码复核

日期：2026-11-14。执行身份：root。范围：接续既有恒风矩阵草案，复核对向风前缀规范状态的公式、源码合同和最近先例。未运行科研数值、地图、作者/ALNS求解、模型、训练或Formal。

## 已证实事实

- 恒风风下leg时间可写为`T_w(x,y)=S_w(y-x)-[Phi_w(y-s)-Phi_w(x-s)]`。反转风向保持`S`、翻转`Phi`符号。沿完整闭趟，势差望远镜求和为零；同一给定物理路线的全趟时间、时间线性能耗、逐槽完整duty、`M_return`和成本不随`w`翻转。
- 对同一槽逐步构造的前缀，可用`tau_bar=tau+Phi_w(x-s)`与`E_bar=E+flight_energy*Phi_w(x-s)`表达剩余leg/return mask所需的静态资源；返站时势为零。该结论需要固定未完成目标集合/站归属并匹配相同逐槽物理前缀。
- 静态`wind_scorer.py`不把`target_completion`/`M_service`作为可行性或主目标阈值；completion仅为逐目标时间诊断。完整成本由固定成本和线性operating分钟组成，`M_return`按完整slot duty取最大。
- `physics_sha256`含方向向量；同路线跨对向风可有相同物理分数，但锚点hash身份不同，必须按每个风身份重建。
- `CausalEngine`按飞行到达、服务完成和`busy_until`创建事件frontier。对向风虽保持每个闭趟时长，趟内服务完成时间可能不同，多槽事件排序和在线策略观察不自动等价。
- 一个公式手算的双槽边界例（仅证明说明，未在<REMOVED_ENDPOINT>运行）取`a=100 m/min`、东西/北两目标距站1000m、服务1min、`w=(±60,0)`：正风下东槽7.25min先完成，反风下北槽13.5min先于东槽26min；但东西闭趟完工时间始终32.25min，北向始终26min。这直接展示闭趟主量不变与异步frontier翻转可同时发生。
- 最近先例包括Randers/Zermelo导航时间度量、potential-based reward shaping、MDP homomorphism/群对称策略网络；它们支持新颖性边界，不替代本模型的同一前缀物理验证。

## 未证实假说

若将恒风研究改为9个等价类，可能节省重复路线子问题运行；仍未证明原17场协议应缩减、在线多机策略可共享权重/轨迹、或减少风场行不损害风向鲁棒性评估。当前17场保留，资源数字不变。

## 失败或关闭

候选裁定仍为`G0_NO_GO_AS_DISTINCT_MECHANISM`：它是已知Minkowski/Randers势差、MDP同态和PBRS在固定风路线前缀上的具体应用，没有新路线构造、更新、估计器或证书步骤。仅有的证明范围为静态逐槽前缀与完整闭趟；不主张完整异步车队MDP商。此前恒风规范坐标候选也保持关闭，不重跑其物理检查或反转轨道梯度诊断。

## 下一项有界工作

若<REMOVED_ENDPOINT>连接恢复且后续G1排期进入此项，则用已冻结静态scorer/风引擎对同一完整路线、同一槽TARGET/RETURN前缀、双槽到达次序改变反例执行一次有限成对回归；新增测试放隔离副本，原17场协议不改。验收同时检查heading复算、完整成本/`M_return`/cap、每步mask和gauge转移，并确认双槽事件frontier不可预设相等。失败原样保留；通过也只属于G1正确性，不提升G0/G3。

## 是否需要用户决策

科学方向不需要决策。<REMOVED_ENDPOINT>实例运行已由用户确认；重试时DNS将`<COMPUTE_ENDPOINT>`解析为`<NETWORK_ADDRESS>`，但端口`<CONNECTION_PORT>`仍返回TCP `Connection refused`（ssh退出码255，未进入认证或执行远程命令）。控制台现行SSH host/port是唯一待用户提供信息；在收到前只继续本地静态文档与来源整理，不做任何本地科研运行。

## 一手来源

- Bao & Robles, *Ricci and Flag Curvatures in Finsler Geometry*, §3.1 Zermelo navigation: <https://library.slmath.org/books/Book50/files/06BR.pdf>.
- Ng, Harada & Russell, *Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping* (ICML 1999): <https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/NgHaradaRussell-shaping-ICML1999.pdf>.
- van der Pol et al., *MDP Homomorphic Networks: Group Symmetries in Reinforcement Learning* (NeurIPS 2020): <https://proceedings.neurips.cc/paper/2020/hash/2be5f9c2e3620eb73c2972d7552b6cb5-Abstract.html>.
