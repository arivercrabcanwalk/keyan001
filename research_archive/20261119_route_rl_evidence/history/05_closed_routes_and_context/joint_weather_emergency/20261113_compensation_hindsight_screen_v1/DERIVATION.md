# 补偿见证重标：对象、概率与关闭边界

这是本轮符号设计筛查，0数值/梯度/模型/求解运行。原共同H完整接线结果直接复用；不重跑4个新工程配置、旧16失败配置或旧科学人口。本文件不是作者错误证明，也不是RL不可能性证明。

## 1. 一轮候选到底做什么

对固定风A的一张TRAIN图，固定作者同风完整锚点Rw、站型/部署/target-station、公共T与完整scorer。当前尚无合格TRAIN人口或训练准入，以下仅算法定义。部署完整成本上限B=Cw(Rw)，绝对容差1e-7；本草案不增大B。公共H是学习/构造上下文，不是actor选择的算子或预算。

固定控制器按站和副本索引遍历。每个副本从空前缀执行(slot,target)/(slot,RETURN)，产生完整raw路线或失败，保存每个动作、状态、logp和实际生成上下文。全部副本先经相同T/完整scorer，再入公共bank；永久anchor不删除。组合器在完整全图cap内求最小M，得到完整交付见证W，失败副本仍保留。拟议下一步骤是用W的达成结果作为新目标，重放组成W的局部物理动作，训练同一个goal-conditioned actor。

这个版本的新增学习步骤只有“完整结果重标＋交叉熵”或“完整结果重标＋重要性加权策略梯度”。生成器仍是普通条件物理actor，T/bank组合已存在；没有新增构造运算。因此当前身份关闭为标准hindsight强控制，不能靠名称、H条件、补偿字段或首次在本项目使用来通过G0。

## 2. 同一局部路线的可用目标依赖远站见证

给站i的完整schedule r及其他站固定公开bank O，定义

    T_i(r;O) = min_{one row per other station from O}
                 M_return(complete map with r), subject to full original cap/physics.

无bank支持时定义+infinity，含义是NO_BANK_WITNESS，不是物理无解。H>=T_i(r;O)给出的训练标签是“r与当前O中的某组完整远站路线能够共同交付”；它不是“r对任意未来策略或任意远站路线都可行”。

已有两站补偿见证可直接说明O的重要性：本站新分趟单独超cap，远站省费用路线加入O后才有联合支持。该事实已有真实工程收据，不新建数值toy。局部轨迹自身(C_i,M_i)不能替代完整全图结果。若将O作为策略输入，须固定并完整公开其路线/代价及生成成本；若重组产生了不同全图状态，须重建相应全图物理历史并重算动作概率，不能只替换回报标签后沿用旧全图状态。

T_i与强制插入查询在既有replacement_values/policy_continuation工作中已有定义；共同H组合器亦已存在。本轮不把它们再次命名为新oracle或免费新步骤。

## 3. 重标后谁的概率必须进入更新

X表示固定数目的全部站/副本raw动作轨迹；失败路径也在X内。g为显式条件目标，物理mask只依赖真实物理状态；若额外以g改mask，需要另检查支持。条件独立生成时

    q_theta,g(X) = product over station/copy/path actions pi_theta(a|s,g).
    F_B(X) = full-cap shared-bank delivered makespan, including permanent anchor fallback.

对预先固定的目标分布mu(g)，可定义辅助目标

    J(theta) = sum_g mu(g) E_{X~q_theta,g}[ 1{F_B(X)<=H_g} ].

这只是学习辅助目标，不能替换原科学primary。普通on-policy likelihood-ratio给

    grad J = sum_g mu(g) E[ 1{F_B(X)<=H_g} * grad log q_theta,g(X) ].

若X是在另一个条件g0下生成，则在绝对连续与可计算概率的条件下，标准重要性采样形式为

    w_g(X) = q_theta,g(X) / q_behavior,g0(X)
    grad J = E_behavior[ sum_g mu(g) w_g(X) 1{F_B(X)<=H_g}
                         * grad log q_theta,g(X) ].

用于实现梯度估计时，w和回报作stop-gradient；若直接对w*q的重复乘积求导，会多计score。旧policy replay还需包含behavior/theta变化。H控制的物理前缀mask若产生零概率，不能无条件采用全支持公式。

全bank回报F_B依赖所有被采样副本；q也因此含全部这些动作的score。只乘最终选中路线的score，或只在已选中路线内计算重标概率比，通常不等于以上目标的梯度。共享theta或同一T不会消除未选中副本的分布作用。若改为条件于独立冻结O的单站目标，可只为该单站轨迹求导，但那是另一个明确的条件目标；若O来自同一当前theta批次而忽略其生成项，就不能仍称原全bank目标无偏。

g*若由同一X事后自选，不能把g*当作与X独立的mu抽样。可以显式采用监督/自训练目标；它无须假装是原J的无偏梯度。也可对已定义的目标分布求和/采样并正确记账，但这属于标准HPG路线。当前草案没有解决一个新的采样/共享计算步骤，不为一般恒等式追加有限梯度toy。

## 4. 监督版本的确切地位

可行的标准版本将W重建为完整物理动作序列tau_W，并用目标g_W和每步真实状态做

    L_BC = -sum_t log pi_theta(a_W,t | s_W,t, g_W).

标签可来自自身探索和公共组合，因而不一定需要外部专家；这仍是明确的自生成监督强控制。所有原raw/T后解、重组/回放/评分、数据生成、训练成本保留。相同teacher/组件也交BC、标准RL与无学习对照，强ALNS和共同H独立新生成保持原生能力。单纯从失败样本学到新目标不证明比最强控制更好。

## 5. 六项G0裁决

|项目|本版本实际内容与决定|
|---|---|
|输入/输出|固定风A、B/Rw、H、完整公开bank；从空前缀直接TARGET/RETURN；最终完整cap和M验收|
|新增操作|用公共组合见证的达成结果重标动作；更新只是已有CE或HPG，当前没有另外的构造/更新步骤|
|最近先例|PCN §4.1–4.3/Eq5已有达成回报重标与自生成监督；HPG §4–5/Eq6–12已有目标转换、概率比和加权估计，见SOURCE_MAP|
|可推翻判断|若有一个不能由既有重标/已完成T_i查询/普通联合score重述的实际操作，可据该具体区别重新评估；本简单版本没有给出|
|费用/强控制|全部raw构造、T、bank、重建状态/重算logp、组合/评分、teacher和训练均计账；非RL/BC/标准RL共享新组件；无免费donor或oracle|
|关闭范围|CLOSE_GENERIC_COMPENSATION_HINDSIGHT_AS_NOVELTY；0新数值toy/训练/人口。保留为必要标准hindsight控制，不否定其他新组合或RL本身|

G0/G3仍未通过。不会因该数学对象正确而启动多seed或Formal；原科学门槛、强基线、旧失败和两保护STATE保持。新路线生成操作仍未选定。
