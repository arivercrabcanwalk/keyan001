# 学习链审修：开发工程资格，未训练

审计原点为 `c193b0d560dd128b252936e2c3edc025224dc760`，两包原五个学习文件逐字相同。此次只运行手写合成观测、完整有限概率枚举、冻结权重前向和 score 有限差分；没有科研地图、求解、优化器 step、参数训练、性能胜出或 Formal 资格。

## 模型实际决策

`Policy` 每次重新编码当前候选任务及 RETURN、WAIT 两类 token，输出这些物理动作的 logits。模型没有输出搜索算子、修复预算或启发式编号。当前布局、站型、目标所属站、作者解和共享预测 shield 仍由外部固定；这不是端到端选址/站型/跨站分配模型。mask 限制预测合法性，不能保证未知天气下实际成功。

默认 `base=teacher` 会实际运行 shadow heuristic，把其本步物理动作标在第32列。BC 的该标记和 label 相同，因此带提示的 BC 准确率很容易升高；它只能解释为学习使用在线提示，不能作为脱离 teacher 的路线能力。`--no_base` 仅去掉此标记；作者计划的下一点/原序号/原机归属仍在21:24列，需 `--feat_ablate noplan` 才移除。`nophys` 只移除 eta/xi 和显式风信息；能耗、mask、几何和风影响的预测成本仍存在，不能称“无物理”。`nophys_noplan` 合并这两组列消融。

## 训练目标与主指标

PG 默认目标为 `E[-J/reward_scale]`，默认固定尺度1000。`J` 是工程代理：实际运行费用、事件/迟到项及环境新增的每未服务项1000、每失败机1000；超时、无可行继续、失败轨迹均保留。所有外生应急请求含未覆盖项都进入未服务分母。此有限惩罚不构成“任何失败都严格劣于任何成功”的词典序定理；没有通过调小样本分母消失失败。

A 三格已知固定风（含无风）以同风作者实际方案的逐图费用为 cap。所有验证地图物理可行、常规服务完成、全机回站且各自费用不超 cap+1e-7，才按平均 `M_return` 最短选模型与教师；每张图仅评一次。A 的动态风开发选择仍以严格完成后的 J 为代理；两类 A 和 B 的 PG 奖励均为 J 代理，而非主指标的无偏替代。B 的模型、教师与调参按所有发布高优请求的合并准时到场且完成率选择，要求常规任务全完成及物理实返；遗漏急单保留为 0/N，无高优为 N/A。B 的费用在独立 pilot 用逐格登记的运营预算检查，不以 J 替代。

## PG 概率链及原缺陷

同一组中的 rollout 共享外生场景，但策略抽样使用相互独立的 `SeedSequence([run_seed, iteration, group, ...])` 和 rollout 子流。没有强行首步；这是 IID 多 rollout REINFORCE，不是 POMO 不同起点协议。

令同组成本为 `C_i`、轨迹为 `tau_i`、组大小 `N>=2`，留一基线 `b_-i=sum_(j!=i) C_j/(N-1)`。用于最小化的 loss 为

`-1/(G*N) * sum_(g,i) [-(C_i-b_-i)/s] * sum_t log pi_theta(a_it|o_it)`。

在给定共同场景后，其他 rollout 的策略抽样独立于本轨迹；因此留一基线对应的 score 期望为零。各动作 score 求和后按 episode 平均，无动作 episode 也计入 `G*N`。原版共享均值含本样本，且按本组样本标准差和总决策数再归一，会改变所声明梯度。默认熵系数改为0；非零 `--ent` 是额外局部熵 surrogate 消融，不声称仍为纯 J 梯度。

原版 rollout 使用 `logits/temp` 抽样，反传却使用原 logits；且 worker 将 tok 压成 float16，replay 时输入改变。现同用 `action_log_probs` 的 float64 temperature-softmax、完全相同 float32观测，mask位置概率严格0。冻结模型有限差分验证温度导数；有限可变长度轨迹枚举验证完整期望 score。全部 reward/advantage 对参数停止梯度。

## BC、REOPT 与反事实标签

Recorder 以实际 `acts.index(teacher_action)` 建 label，对 mask不合法动作明确报错。自动 teacher 仅在 TRAIN 的 A1/GREEDY/REOPT候选探测里按上述A/B合格标准与开发选择指标决定，不能称所有标准强方法中的最强。显式 `--teacher REOPT` 或 `--teacher REOPT@0.1`、`--teacher REOPT-W8@0.2` 可用；可直接使用 tuner 的非空 `overall`。REOPT有墙钟搜索，固定随机 seed也不保证完全相同标签；必须保存实际费用和评估票据。

原 RI 将天气隐藏 latent 的条件续采样误称为公共观测 posterior，并允许 `ri_R=0` 使用真实未来。现 `ri_hours` 默认0，发布启动统一 `--no_ri`；所有 `ri_hours>0` 入口明确终止，内部还要求独立验证的 `public_future_sampler_verified=True` 且 `R>=1`。潜在 RI 内部已将 teacher 当前调用后的状态快照一次、各候选相同 future seeds、重采样后当前公开特征/mask不变检查连好，但它仍是未准入代码。已知恒风或齐次泊松独立增量可另行证明窄域公共采样；本轮没有据此自动开启、没有RI收益证据。

## 控制组与命名

以下开关附加到远端注册的共同 plans、dev_plans、scen、seed 和相同预算；不是本机开训指令。

| 控制 | 独立开关 | 含义 |
|---|---|---|
| 纯标准PG | `--no_bc --no_base --no_ri --feat_ablate noplan --shaping none --ent 0` | 无在线teacher提示/无作者序列列，仍条件于作者布局与共享shield |
| BC-only | `--rl_iters 0 --no_ri` | 监督初始化控制；提示是否保留需与主臂一致 |
| BC+标准PG | `--no_ri --shaping none --ent 0` | 监督初始化后普通REINFORCE |
| 去在线提示 | `--no_base --no_ri` | 作者计划列仍在；不混称无teacher历史 |
| 特征消融 | `--feat_ablate nophys` / `noplan` / `nophys_noplan` | 精确按上述列说明 |
| 奖励消融 | `--shaping eta` | 非势函数 shaping，改变目标，独立命名 |

A1 是作者顺序的在线执行，完整同风作者原件另记。原生强 ALNS 和独立共同 H 不等于 REOPT；没有这些对照和资格不得宣称全面胜出。tuner 仅在预定参数格中按独立验证数据选教师；不合格的算法族不补选。

## Checkpoint、预算、复现

`bc.pt` 只在BC启用时生成；`--no_bc` 初始随机权重保存 `init.pt`。`last.pt` 保存最近评估，包括BC-only；`best.pt` 只保存满足上述A/B开发准入且选择指标最好的快照，无合格项则 exit3。每个开发评估、teacher/BC episode与PG rollout都输出实际结果和身份行。`state.pt` 保存每次PG迭代的模型/Adam、stage、总step、完整主进程Python/NumPy/Torch/CUDA RNG和冻结契约。契约包含全部学习参数、两个plan文件SHA、所有rlcore源码SHA；更换输入/消融/目标/源码拒绝同目录续跑，旧无schema checkpoint明确拒绝。worker/cache联合文件身份，不再仅以迭代ver判断。阶段切换加载另一个best权重时重置Adam moments。

`--total_hours` 覆盖teacher探测、BC、开发选择、rollout和PG；`--rl_hours` 是PG阶段上限。批次等待按剩余时间超时并清理worker。外部 cold end-to-end driver仍必须实施硬进程期限、CPU/GPU实际计量及失败票据，内部墙钟不是核时账簿，也不是硬实时保证。worker退出异常不生成 `done.json`；不能把旧best当作本次完成。

训练时限按连续 PG 阶段墙钟计；耗尽时取消未完成批次，跨界提交的参数/Adam 回滚，保留已完成更新。独立记录 `pg_optimizer_steps` 与 `best_source`（BC、初始化、PG 等）；最佳快照如果来自 BC，不能把它的成绩归为 PG 增益。总期限或子进程异常仍是失败。可复核手写反例和进程冒烟，见[本版验收](../rlv3_review/ACCEPTANCE.md)。
