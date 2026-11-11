# Liu/LRPHSD 路线 RL 上下文（中文）

## 研究问题

项目研究在 Liu/LRPHSD 多站点、异构无人机、多趟路线约束下，RL 是否能在每张地图成本不高于 Liu 作者锚点的条件下，直接构造更好的物理无人机路线。RL 的动作是下一目标或 RETURN；它不选择任何搜索算子。

固定边界包括部署/站点类型/目标归属（条件路线研究）、目标恰好一次服务、每趟返航、能量/时间约束和累计 duty 规则。若要声称端到端 TSALNS 胜出，必须另行冻结完整外层比较，不能把条件路线结果冒充系统结果。

## 已完成

Liu/SEMFiX 官方实现复现覆盖 120 张官方地图、5 个种子、P1/P2 和 1,200 次配对运行，全部可行并通过独立审计。精确数字与差异解释见 `analysis_docs/SEMFiX_FULL_RESULTS.md`。

工程上实现/验证了天气、NFZ、动态紧急任务、释放时间、期限、高优先级、异构机型、多趟路线、累计 duty、独立物理回放、关系编码器、LOO、SCST、PPO、A2C、离散 SAC、DQN、VFA、行为克隆、beam 和完整 rollout 对照。

## 当前负结果

最强登记非 RL `oldbeam` DEV 平均 `J=1169.612132`，SCST/LOO `J=1188.621808`，差 `+1.6253%`，8/8 DEV 地图落后。6 个 SCST/LOO actor seed 均选择 initial；DQN 个别 seed 胜自身 initial，但没有胜最强非 RL。多目标复核中完整非 RL 候选组合 HV 高于 RL 组合。

所以当前结论是“高保真基线复现 + 路线 RL 未证明优越/研究未完成”，而不是正向 RL 论文结果。

## G 阶段

G0 新机制原创性未通过；G1 工程契约通过；G2 只有有限机会诊断；G3 最强非 RL 资格未通过；G4 RL 优越性未通过；G5-G8 尚未完成。不得在这些门槛未过时扩写新的正向论文正文。

## 阅读路径

先读 `CURRENT_STATUS.md`、`RESULTS_SUMMARY.md`、`RESEARCH_PLAN.md` 和 `CODE_MAP.md`，再按需要读 `analysis_docs/` 中的完整状态/报告和 `source/` 中的源码。
