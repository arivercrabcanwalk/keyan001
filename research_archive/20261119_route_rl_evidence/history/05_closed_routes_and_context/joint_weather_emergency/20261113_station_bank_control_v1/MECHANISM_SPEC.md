# FEASIBLE_STATION_BANK_PAIRING：筛选及不立项理由

1. **输入输出。** 固定部署/站型/target-station、固定风简单能耗、完整成本cap、共同anchor。各站生成K个完整物理路线字符串，actor原样只做(slot,target)/(slot,RETURN)，不选算子/预算。推理在同bank选一站一schedule，输出完整物理动作与解；建池/验证/组合全部计入墙钟。当前没有actor实现或权重。

2. **数学对象。** bank B的概率为`qθ(B)=∏s,k pθ,s(Rsk)`。令`H(B)=min{M_return(Rω): ω∈bank组合, C(Rω)≤C_anchor+1e-7}`，共同anchor进入池以保证完整回退可表示。拟议学习目标是`E_B[H(B)]`，而非旧product平均`E[M(R)]`。其普通score梯度为`E[H(B)∑s,k ∇log pθ,s(Rsk)]`；只对被选路线的score求和通常不是此目标的完整score。这个变换仍是标准best-of-K终局目标加log-derivative，没有定义额外新信用步骤；本轮没有执行梯度/训练检验。

3. **最近先例。** Kuntz等product-form Eq4已覆盖旧独立bank平均；当前min而非平均确实不同，但不能以此重开旧估计器。CMSA-RL §3.2/3.3/3.5已有构造多解、路线池精确重组和按优质组合反馈学习；它的set-cover允许重叠、后续删重复，当前整站固定归属不需此修复，二者不完全同构。旧R7完整crew/整数主问题＋终局学习已经因无非直接新步骤关闭；本轮缩回固定站域不产生新颖性。两篇主来源仅复用已归档原文，不重新下载。

4. **可证伪预测。** 在固定站池内，给定τ，只要每站存在一条`m_sk≤τ`的schedule，最小总成本可逐站单调前缀选择。设`f_sk(x)=fl(fl(x+d_sk0)+d_sk1)`，它在x上单调，故`min路径operating`的下一步为`min_k f_sk(min前缀)`。固定费和time_cost相同且非负，所以原scorer完整cost最小也由此获得。阈值最早可行者就是有限池最小M。若枚举出现更优M/成本或独立validator不符，工程实现失败；不把数学命题预先写作实测。

5. **同信息最强对照。** exact-bank阈值控制应与未来学习共用相同父解池、全部建池成本/参数/候选/physics/anchor；不能给nonRL随机matching而把跨池重组收益算成RL贡献。池外强minmax ALNS仍保持原生联合搜索，不能被有限池替代。即使此控制最优，也只对给定站schedule池，不是全路线全局最优或G3科学资格。

6. **关闭及工程续接。** 本轮未找到超出best-of-bank/普通score/标准池重组的新构造或学习步骤，`NO_ADMITTED_NEW_G0_CANDIDATE`，不训练，不换seed复活旧product/R7。下一实际动作是补上述已有G3要求的可调用强控制，并用新手写工程fixture核验其完整物理/字面成本/回滚。工程通过不抬G0/G3。
