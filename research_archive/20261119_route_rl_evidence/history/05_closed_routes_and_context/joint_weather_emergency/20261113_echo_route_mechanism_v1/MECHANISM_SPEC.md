# ECHO迁移切入：六项G0及限定关闭

身份：`ECHO_TRANSFER_AS_NEW_MECHANISM`。日期2026-11-13，仅root。只裁决本对象；不把它解释成固定风路线RL的总体不可能性。

1. **输入/输出。** 输入是固定部署、站型、target-station、slot状态、剩余目标、固定风和简单能耗、逐图完整成本cap及公开路线历史。拟议输出仍为`(slot,target)/(slot,RETURN)`。本轮只执行公开提交decoder的三个固定数学张量例、原环境的两目标trace；没有Liu域神经adapter、学得权重、训练或质量批次。作者源三个文件固定提交`a97011c942184d2abc54ce066390173a0581f7ad`；没有证明它是论文实验提交。

2. **拟议改变及数学对象。** 直接复用ECHO的边编码、联合vehicle-node选择和上一vehicle信息，再适配本项目物理约束。源码PFCA可精确化简为`Nhat_j=N_j+M_last(s)`；clip前的pair logit为`z_ij=M_i·N_j/sqrt(d)+M_i·M_last(s)/sqrt(d)`。softmax最后轴长度1，所以attention权重路径导数为0；residual和最终概率梯度仍非零。这个化简属于源码语义结论，不是本项目的新学习算法。

3. **最近先例差异。** ECHO正文§3.2.2/式2–3/23–25和作者`attention_model.py:224–281`、`hcvrp.py:139–174`已包含异构车辆、联合物理动作、返站重置容量、累计时间保留与终局补返站。新增多站home、服务能耗、风/energy/duty/cap需要实现，但约束或特征迁移没有建立新的构造/估计/学习步骤。源码从当前embedding按last-ID重新索引，与正文保存过去embedding的表述分列。详细映射见PAPER_CODE_MODEL_MAP。

4. **可证伪预测。** 对公开decoder和显式广播残差，全部概率、选中动作及q/k真实autograd应一致；固定vehicle下合法node的greedy排序应不变；联合vehicle选择可以变化。若任一等价断言失败，则推导或提取过程失败，不能按预设结论通过。<REMOVED_ENDPOINT>三例均满足，概率和梯度最大误差均0.0；两例含last-ID，第三例无context。节点维softmax与保存旧embedding是非等价控制，实际概率L1差分别0.895484023439818/1.9782182019231889。

5. **最强non-RL与归因。** 若将来把ECHO用作强神经控制，必须与同信息/候选/物理/完整成本cap/6s和12s的强minmax ALNS、适用精确参考、监督/BC/API-only和普通RL比较。作者原文的SISR/GPU sampling预算不替代本项目比较，不能只与Greedy或弱作者适配比较。本轮没有这些性能结果；工程语义不提升G3。

6. **关闭规则与结果。** 若剩余差别仅为约束适配、网络/维度修正、last-ID记忆或标准化简，则关闭创新切入，不训练。本轮命中此条件，裁决`CLOSE_ECHO_TRANSFER_NO_DISTINCT_NEW_STEP`。三个原作者文件未改；3节点topk越界原样保留。没有用修改softmax维度/补小输入/换seed重新打开本身份，也不重开旧交错边缘score候选。G0/G3总体仍未通过。
