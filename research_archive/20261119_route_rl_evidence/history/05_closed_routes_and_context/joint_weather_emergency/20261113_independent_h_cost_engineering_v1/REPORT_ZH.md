# 共同H接线：失败已关闭

已证实：既有ALNS已有m_cap费用模式，真实新wrapper按站生成完整schedule、公共T与bank/cap组合。第一次BASELINE在搜索前因缺physics_sha256被原scorer拒绝；一次预留修复只补身份与JSON验收边界。BASELINE_REPAIR1和MODIFIED随后均在gen_ruin越界，均exit1，没有完整配置结果。四记录含一次失败行为回滚，child CPU0.429255s、wall0.5634795101359487s；实际评分调用未计数，不能写0评分。

明确失败：原AUDIT/原完整行为ROLLBACK没有执行；source repair已1/1、剩余0。本批CLOSED_FAILED，不重开16配置、不补跑成功计时、不据另一修复包改写其终局。另副本回滚仅恢复原SHA和相同IndexError，main独立h_cost字段保留。

根因：gen_ruin将(slot,trip,pos,target)规范化成(slot,trip,target)后读e[3]。旧完整minmax solve使用的ruin_step从原四元entry读e[3]正确；新失败不作废旧强ALNS结果。隔离一行修复与helper回归在相邻20261113_gen_ruin_key_fix_v1；这个新对象不恢复本批repair额度或质量运行。

未证实：独立H费用生成的强度、完整G3资格及RL收益均未完成。本包训练/作者/完整ALNS solve/新科学图/Formal/子agent均0；不是0ALNS内部操作。G0/G3未过，整体研究/G8未完成。

下一项：保留本批失败，复用隔离修正的helper前另冻有界端到端控制协议；不调暴露DEV或输入阈值。当前无需用户操作/决策。原始stdout/stderr/收据见server_evidence，四件套见VERIFICATION.txt。
