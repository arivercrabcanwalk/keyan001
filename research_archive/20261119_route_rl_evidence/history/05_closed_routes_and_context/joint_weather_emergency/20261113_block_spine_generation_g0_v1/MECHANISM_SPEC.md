# 服务集合分块同步的物理路线粒子生成：六项规格

执行前状态：`FROZEN_FOR_ONE_ENGINEERING_DIAGNOSTIC_ONLY`。G0/G3未过，不运行模型、求导、训练或Formal。仅root；所有物理/概率数值运行在<REMOVED_ENDPOINT>。本轮使用标准PGAS，并检验一个具体组合；不要求发明通用RL原语，不预先称组合原创。

## 1. 输入输出与实际路线构造

固定风向风速、简单能耗，A先行、应急后置。科学合同继续固定完整作者同风Rw的部署/站型/target-station，完整原cap绝对容差1e-7、含返站Mw、强ALNS、共同H独立新生成和公共T。本轮只有新手写工程输入；手写anchor不是作者Rw，工程耗时不是6s/12s科学资格。

输入是完整、可行的raw物理参考轨迹x_ref，公开固定块宽2及offset o∈{0,1}。o=0按2,2,…个TARGET分块；o=1按1,2,2,…分块。Z_o(x)是有序的无序目标集合序列。每段在指定数量的最后一个TARGET后立即结束，最后一段另包含所有终结RETURN。因此同一路径有唯一切段，不把RETURN任意移动到段的两侧。

每个粒子从空路线通过(slot,target)/(slot,RETURN)生成。当前段只允许本块未服务TARGET及原合法RETURN，结束一块后，各粒子服务集合相同，但slot、目标同趟关系、开放位置、电量、累计duty可以不同。最后关闭全部非空趟；没有WAIT、空RETURN、跨站动作。RETURN保留累计duty。动作数≤2n；未完成死路记录为失败，不重试。

P−1条普通粒子从上一段按权重抽祖先；一条保留粒子使用参考段。PG固定其祖先；PGAS在每个非首段开始前，从全部粒子前缀中重选保留祖先。对每个候选前缀，必须真正重放完整参考后缀，检查覆盖、typed、空RETURN、趟能量、累计duty、完整raw scorer、公共T及完整cap。只服务集合相同不构成可拼接证书。失败祖先权重0；未见证不表示物理无解。

所有已计算的完整splice，不论是否被选为祖先，交给相同公共bank。PG_COLLECT控制也计算、收集全部splice，但不改变保留祖先；这是必要强控制。最终工程交付在anchor+全部完整合格候选中取最小T后Mw。一个站的工程不验证多站bank接线；既有共同H接线直接复用。

## 2. 目标、辅助变量和真实抽样律

q0(x)是全局原合法动作集上逐动作均匀的θ无关基础law。分母包含块外目标；不把它偷换成块内均匀。γ(x)=q0(x) exp(βU(Tx)) 1{raw完整物理可行且T后完整cap合格}，U=(M_anchor−M(Tx))/M_anchor。T按原二进制64浮点和输入趟顺序执行，不假定幂等，不消除raw交错/纤维重数。

辅助law r(o,z|x)=ρ(o)1{Z_o(x)=z}，ρ(0)=ρ(1)=1/2。给定(o,z)，γ限制到兼容z的路径。先按r抽辅助、再运行条件不变kernel，可保持原γ；它不是任意状态依赖kernel混合。工程完整枚举小例检查此有限结论，不声称全物理可行域连通。

第b段之前的中间γ_b为q0(prefix)及兼容/合法指示，终段乘exp(βU)及原cap。qθ^z(segment|prefix)按实际块内合法动作归一化，失败保留走过动作概率。普通粒子增量权重为γ_b/(γ_{b−1}qθ^z)。保留祖先分布为

    A_b(i) ∝ W_{b−1}^i × γ(prefix_i ⊕ ref_suffix_b)/γ_{b−1}(prefix_i).

后缀q0及proposal概率都从候选真实资源状态重算；祖先公式使用γ比，不把proposal后缀logp误放进去。采样的保留段增量权重仍要除以实际qθ^z段概率。终局spine按W_B抽取。一次pass的law包含全部proposal、普通祖先、保留祖先和最终抽取概率；单spine的γ不等于实际公共bank交付law。

## 3. 一次学习更新（仅规格，本轮不执行）

未来若G0/G3准入，固定θ无关anchor和一次pass参考，Ξ记全部粒子森林及失败。pθ(Ξ|I,x_ref,o,z)包含上述全部随机选择；Jθ=E[U(delivery(bank(Ξ)))]。一次正确标准score更新为g=(U−b(I,x_ref))∇log pθ(Ξ)，b与本次Ξ独立。权重归一化、普通祖先、AS和末次抽取的θ依赖不能无据删掉；不能只乘最终赢家动作logp。多pass时保留此前pass对参考分布的信用。标准SCG梯度本身不当原创，也不把γ的终局tilt称为训练收益。

```python
# 可复用算法规格；本轮没有模型或参数更新。
def physical_block_iteration(theta, I, raw_anchor, fixed_offset, shared):
    blocks = shared.target_sets(raw_anchor, width=2, offset=fixed_offset)
    forest, loglaw = shared.pgas_physical_segments(
        theta, I, raw_anchor, blocks,
        global_base_law="all_original_legal_actions_uniform",
        replay_all_suffixes=True, collect_all_complete_splices=True)
    delivered = shared.original_score_T_cap_bank(raw_anchor, forest)
    loss = -stop_gradient(delivered.utility-shared.independent_baseline(I))*loglaw
    return loss, delivered, forest
```

## 4. 最近先例与特定增量

Lindsten/Jordan/Schön JMLR2014 §3.1–3.2 Eq3/Alg2已给PGAS和非Markov祖先权重；van de Meent等AISTATS2015 §3.3、§4.1–4.3已给prefix+suffix自洽重建、分支拒绝及概率重算。1505.06356本轮只读官方摘要，退化转移下的rejuvenation也已有先例，未声称完整方法精读。

待检验组合的具体差分是：以参考访问序列的无序目标块为辅助变量，使不同访问排列/分趟前缀在同服务集合处相遇，再以完整typed/累计duty/原cap验收换保留祖先，影响后续普通粒子构造。它不同于上包只给actor增加context，确实改变粒子转移。但通用PGAS可以表达它；当前未找到完全相同实现不等于证明原创。工程若成立，仍须进一步任务先例与学习增量论证。

TARGET时钟、未限制访问次序的PGAS只在偶然服务集合相同处可拼接；它是完整强控制，不能强行固定其访问顺序来削弱。PG_COLLECT拥有同样完整splice、T、cap与评分预算。AS若仅把已收集最优splice再选一次，没有产生后续价值，就不支持组合收益。

## 5. 唯一有界诊断与强控制

INPUT.json冻结3个新手写二维工程几何（SD/dual/typed），同一恒风(160,-100)，2个offset，8个固定工程replica。P=4，β=2，一次pass。baseline默认BLOCK_PG_COLLECT；modified默认BLOCK_PGAS，同时运行BLOCK_IID与UNRESTRICTED_TARGET_PGAS。192条pass记录；不是训练seed或科学地图。全部几何/参数/replica在运行前冻结，不挑有利结果。

另一个3目标单SD小例只用于有限路径/概率kernel检查：完整枚举raw路径，β=0及β=2分别检查条件PG/PGAS与offset辅助混合的不变性，并检查错误块内q0替换会改变目标。保留所有完整解、完整评分、动作law、祖先选择和失败；原scorer对象先JSON规范化键再比较。AUDIT独立重放每条完整记录，核覆盖、能量、累计duty、T、cap、祖先公式及段概率。negative controls包括非法slot、空RETURN、重复/遗漏目标。

全包CPU70s、完整进程wall75s、单进程512MiB；phases BASELINE15s、MODIFIED20s、AUDIT25s、ROLLBACK8s，串行。限额含解释器和失败，SSH传输另记。最多一次代码/验收修复，仅正确性错误可用，不为质量或速度补跑成功phase；所有原失败保留。阈值不后改。

继续条件：全部正确性通过；AS有真实不同祖先和后续新分组；相对每个fixture所列最好控制，至少2/3 fixture的平均交付utility严格提高（>1e−12）；完整modified候选worker退出wall不超过匹配PG_COLLECT的1.5倍。该小工程即使满足，也只准继续设计/查新，不使G0/G3或训练自动通过。若不满足，关闭当前固定均匀proposal配方，不调P/β/块宽/坐标/replica救结果，不推断所有learned组合失败。

## 6. 当前边界、停止规则与用户决策

本轮不调用作者solve/强ALNS、不创建科学身份、不导入模型、不训练、不跑Formal。旧192repack失败和其repair0、group_transport1280负结果、旧所有审计/实验直接复用。两保护STATE保持原字节，40身份/126比较及校准24/24不变。

<REMOVED_ENDPOINT>已经以专用key重连成功；仅root，当前无需用户操作或决策。可信突破、充分多seed/消融/全新Formal、CCF-B论文和G8仍未完成。
