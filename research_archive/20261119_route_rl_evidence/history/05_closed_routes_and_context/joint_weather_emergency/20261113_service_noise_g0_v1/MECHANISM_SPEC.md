# 服务事件噪声：六项有界规格

本包仅检验有限、已暴露工程bank上的目标分布；不是新科学人口、RL训练、DEG复现或G0/G3通过。复用共同H四行，不重新执行任何站搜索、作者求解、ALNS solve或旧审计。原合成anchor不冒充作者Rw。固定风A/简单能耗先行，应急后置；仅root，所有数值只在<REMOVED_ENDPOINT>。

1. **输入和输出**：两既有手写二维几何×两固定风，四组站bank。每站选一条的全部带标签Cartesian组合，保存每条完整解、原scorer结果、费用/物理失败及分母。仅在完整cap合格子域定义诊断law；这是条件于已知可行池的分布，不是在线物理actor分布。输出三alpha下每条概率、期望归一化M改善、趟数和log-noise矩，不输出科学优越结论。
2. **实际新增操作**：每个TARGET建立一个噪声事件。非末TARGET使用入边clean prior；该趟末TARGET将入边与真实返站边clean prior几何平均，再做一次相同Gaussian corruption/clamp。每图始终n事件。RETURN保留为原物理动作；只改噪声归属。无PAD/WAIT/选择算子。未来若准入，空前缀actor仍只输出(slot,target)/(slot,RETURN)，TB目标需包含该事件weight；本包不实现或训练此actor。
3. **最近先例与区别**：DEG §4.1、Appendix B已明确逐航段乘积、CVRP n+K与高噪声少趟偏置，此事实不是我们的发现或作者错误。新候选仅是将返站先并入末目标prior再corrupt的具体适配。长度/矩校正、目标only及直接terminal_half_log全部强控制。Constraints Matrix Diffusion已有同趟矩阵+条件actor，不能独立作为创新。无穷尽新颖性主张。
4. **可证伪条件**：alpha0候选及固定n/长度校正端点恢复p∝R；alpha1候选必须与terminal_half_log完全一致。alpha=.25的四配置为主要判别域，至少3格informative、至少3/4严格胜每格五强控制中最优者，四格平均额外utility≥.002，才仅建议继续G0研究。失败关闭本固定配方，不改alpha/delta/prior/几何/池或追加样本追阳性。端点相等不当胜利。新strong control及修订原因在执行前单独记录，原未执行sketch原字节保留。
5. **费用和公平性**：全部方法用同一完整池、同R与edge prior、原scorer和cap。构池与先验用本池标签，是in-sample有限诊断；不是泛化、在线可得、神经学习或免费oracle。源bank生成CPU/wall直接引用前包账本，不计为免费候选。新组合评分/审计另计。log-noise方差不称神经梯度方差，也不据其宣称训练加速。完整进程退出后才计完成。
6. **预算与终止**：BASELINE/MODIFIED/AUDIT/ROLLBACK严格串行各一次；总child CPU≤90s、完整wall≤120s、每phase≤30s、地址空间≤1GiB。最多1次纯验收修复，保留原失败/原validator/原manifest并另名，不改算法/输入或重跑成功计时；不自动使用。失败停止依赖phase。无模型导入、参数更新、训练seed、checkpoint、新科学图、Formal。另副本回滚恢复原mode/hash及首配置完整law；主候选保持修改。两个主科学STATE原字节、旧40/126与校准24满额保留。
