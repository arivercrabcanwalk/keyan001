# 恒风前缀对偶证书候选：G0 静态筛查

日期：2026-11-14。执行：root。对象：在 S_const 固定风和简单线性能耗下，学习一个 typed 多趟路线前缀的可行对偶证书，并以证书下界安全过滤 `(slot,target)/(slot,RETURN)` 动作。

## 已证实事实

- 既定 A 合同不变：每张新图均须 `C_w(candidate) <= C_w(R_w)+1e-7`，`epsilon=0`；主质量指标为完整返航 `M_return`。RL 只能输出物理路线动作。固定风场每图17个，恒风矩阵 G3/VAL/DEV/Formal 规划行数408/1020/1020/4080；这些是配对风场行，不是独立地图数，也不是已批准预算或运行授权。
- 既有源码 `global_env.py::necessary_cost_lower_bound` 已在动作级计算已发生工作、剩余服务和已承诺返航成本，并用于 cap mask；既有 G0 的 M08 已把一般 LB/branch-and-bound 剪枝归为标准工程工具。
- 一手先例直接覆盖候选的核心构件：CP 2024 的 TSP 方法用 GNN 预测 Held–Karp 乘子并过滤 branch-and-bound 边；Bessa 等人用学习乘子形成有效拉格朗日界并剪枝；Neural Certificate Pricing 在 ESPP-NC 中学习价格、执行结构恢复和路径解码；2026 的 L-PDDOIs 已在 CVRP/VRPTW 学习对偶不等式并给出恢复基线界的证书流程；Dual Lagrangian Learning 使用投影/补全保证对偶可行。[CP 2024 原文](https://doi.org/10.4230/LIPIcs.CP.2024.22) [Bessa et al.](https://arxiv.org/abs/2408.12695) [Neural Certificate Pricing](https://arxiv.org/abs/2607.01185) [L-PDDOIs](https://arxiv.org/abs/2607.13373) [DLL](https://arxiv.org/abs/2402.03086)
- 本轮是文献与源码静态核对；未独立运行 <COMPUTE_HOST>，未调用作者/ALNS 求解器，未生成科研地图、模型或 checkpoint，也未训练或开启 Formal。

## 未证实假说

对未服务目标—槽—趟次建立物理松弛问题，让网络预测对偶乘子，再用确定性可行化取得 `LB(prefix, action)`，可能比当前必要成本界更紧。若证书对所有物理 completion 有效，只屏蔽 `LB > C_w(R_w)+1e-7` 的动作即可保持安全。仍未证实此界在原始路线模型中足够紧、其完整推理开销能降低误搜索，或 RL 能从中获得对非学习解算器没有的质量增益。

## 失败或关闭方向

`G0_NO_GO_AS_DISTINCT_MECHANISM`。候选的差别目前只是把已知学习型拉格朗日/对偶界迁移到本站多趟路线前缀和 cap mask；没有新证书构造、可行化、动作生成或参数更新步骤。通用连续松弛、对偶可行投影、下界剪枝只能作为工程基线/对照，不能据此申报新机制。没有启动 toy fixture、solver 或训练；不触碰旧暴露 DEV，也不调整基线、人口或阈值。

关闭仅针对该候选。确定性 S_const 不构成 RL 不可能性证明；其他新构造候选仍可独立六项筛查。若将来作为工程或标准强控制评估，至少须证明证书在原始物理 completion 集上有效、边界计算保守、不会误屏蔽有 cap 内完整续接的动作，并把模型/证书生成/验证/后处理全部计入预算；对照须含当前下界、同一松弛的非学习对偶优化、精确适用域小图参考及强 min-max ALNS。

## 下一项有界工作

回到固定风阶段，只筛一个仍未关闭、实质改变 bank 外物理路线构造或学习更新的具体操作。先写完整输入/输出、一次更新、最近原文逐步差异、可证伪预测、最强同信息 non-RL 和关闭条件；没有差异则公式阶段关闭，不做 fixture。G0 与 G3 资格及新资源/人口冻结通过前，不开展新科学比较、多 seed、消融或 Formal。

## 是否需要用户决策

科学方向当前无需决策。<COMPUTE_HOST> 的 `<COMPUTE_ENDPOINT>` 本轮专用密钥连接仍为 TCP `Connection refused`；实例运行状态已由用户确认，但端点尚未恢复。若控制台显示的 SSH host/port 已变化，只需提供当前 host 与 port，之后继续远端只读检查；本轮不转到本地做科研运行。
