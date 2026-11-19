# 预训练概率流组合迁移：六项 G0 对象与裁决

对象 `PRETRAINED_FLOW_COMPOSITION_FOR_COMPLEMENTARY_ROUTES_V1`。2026-11-13，仅 root；固定风＋简单能耗先行，应急后置。本轮是单对象查新和精确资格反证，不是已实现的路线策略。

1. **输入／输出。** 拟议输入为固定部署、站型、target-station、公开固定风、完整原成本 cap，以及分别学习不同成本—时间偏好的完整物理路线分布。拟议部署动作仍为 `(slot,target)/(slot,RETURN)`；不输出搜索算子、模型家族或预算。隐藏天气／未来应急不进入当前对象。最终须输出完整可重放解和失败状态，全部加载、采样、验证及交付计入原 6s/12s。当前只有四个两终点数学 DAG 的诊断，无路线策略、模型或新科学人口。

2. **数学对象／具体步骤。** 被筛选的步骤是按各 component 的 reaching probability 混合物理动作概率，以复用不同完整路线偏好。对 β=1、准确 `p_i(x)=R_i(x)/Z_i`，RBR 已给 `v_i=ω_i Z_i/Σω_j Z_j`、`p_M(a|s)=Σ_i v_i u_i(s)p_i(a|s)/Σ_i v_i u_i(s)`。这本身没有我们新增的运算。本轮单独检验其 Remark(ii) 的估计 Z 不变性：保持 component law 与 reaching probability 准确、把混合系数的 Z 换为 Zhat，实际 `qhat(x)=Σ_i ω_i(Zhat_i/Z_i)R_i(x)/Σ_i ω_i Zhat_i`。四例与作者原函数核对确认不同相对误差可改变目标。

3. **最近先例逐式差异。** MOGFN §3.1 Eq(2) 已有 preference/reward-conditioned trajectory balance 与 conditional logZ；§2.1、§6 已有非凸前沿用 scalarization、多模态、多温度与不同偏好分布。PSL 的既有核对继续有效。RBR §4 Eq(4–8)、附录 A.1 Eq(10–16) 已有预训练分布的 reaching 混合。把分子 reward 换成路线成本—返航时间、把生成动作换为 TARGET/RETURN，属于迁移；尚无非直接的构造／估计／学习步骤。RBR 不是无人机路线论文，其标题的 Routing 指概率流。当前也没有把硬全图 cap 的完整后缀条件化计算解决掉。两份新主源不构成穷尽检索。

4. **可证伪预测及实际检验。** 执行前冻结 A/C 的 L1 分别 `4/15`、`13/84`，B 共同缩放和 D 相同 component law 的 L1 为 0。<COMPUTE_HOST> 四阶段 exit0，全部符合；作者 `_scalarization` 四组固定 float64 root tensor 与精确有理数的最大逐项误差 `2.220446049250313e-16`。这是一般“不变”表述的有限反例；不是作者训练误差分布、性能或我们物理 headroom 的估计。

5. **最强 non-RL／学习对照。** 未来若有实质新步骤，仍须对已接线强 min-max ALNS（含非瓶颈节省成本融资）、完整 station-bank 精确控制、忠实风适配作者、同信息 BC／监督／无更新控制比较。共享 bank 时生成成本和候选完全共享，non-RL 保持其原生联合搜索域。准确 normalizer、显式偏好条件策略以及普通条件采样均属必要简单替代，不能只比错误 Z 的混合或弱贪心。当前未跑任何新物理质量比较，不发 G3 资格。

6. **关闭条件与终局。** 若新增步骤仍只是 MOGFN conditional TB、RBR mixing 或普通 cap 过滤，则不立项；若一般 normalizer 不变性被反例否证，不再以该不变性为迁移依据。本轮两项均命中：`CLOSE_TRANSFER_NO_DISTINCT_STEP_AND_REJECT_GENERAL_Z_INVARIANCE`。只关闭该迁移主张与该资格前提，不关闭所有 GFlowNet、RL 或天气路线研究；准确 Z 的 RBR 线性定理未被推翻。G0/G3 总体仍未通过，不训练、不 Formal，不重开旧 product/条件 score/交错等身份。
