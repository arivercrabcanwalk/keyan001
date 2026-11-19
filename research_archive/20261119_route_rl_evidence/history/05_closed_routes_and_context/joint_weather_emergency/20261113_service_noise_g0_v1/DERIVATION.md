# 明确的有限诊断对象

令Ω为四个既有工程bank之一的带标签站组合积。本站选项重复或slot/trip排列不同会有不同标签；不先去重，不把Ω说成全物理轨迹域。每条记录经原完整wind_scorer；A={x∈Ω:原物理/部署/target-station/全图cap合格}。所有Ω失败保留，不因A条件化而删分母。永久anchor属于A。科学cap仍C≤C_anchor+1e-7。

令u(x)=(M_anchor-min(M_anchor,M_return(x)))/M_anchor，R(x)=exp(u(x))。这是诊断reward，不替换科学primary。A中记录的每条有向边按(station,slot,from,to)标记。对含边e的带标签A记录平均R，跨不同边做population zscore，再normal CDF并clamp[δ,1]得到p_e；所有边reward相同时p=.5。端到端来源仍含原bank生成费用。此prior使用同池全图标签，明确in-sample/oracle信息，所有控制共享。

每图服务目标n、非空趟K、航段L=n+K。独立noise变量g_α(p)=log clamp(sqrt(α)p+sqrt(1-α)ε,δ,1)，ε∼N(0,1)。记m_α(p)=E g，v_α(p)=Var g，c_α=m_α(.5)。按u=log y∈[logδ,0]做Simpson512积分并加下端原子；1024独立精度复核。alpha1直接logp/0方差，不做有奇点的数值积分。

各law为P_mode,α(x)∝R(x)exp(μ_mode,α(x))，在A上logsumexp归一；这只是固定prior/full-support有限TB population target的适配，不是训练收敛或作者完整实现。μ与ν如下：

- all_leg：Σ_e m(p_e)，Σ_e v(p_e)。
- length_centered：Σm−(L−n)c；ν同all_leg。
- mean_variance_matched：n c+sqrt(n/L)(Σm−L c)；ν=(n/L)Σv。
- target_only：仅n条入TARGET边的Σm/Σv；返站仍物理存在，但不入noise。
- service_event_return_bundle：每TARGET一个prior。非末为p_in，末目标为sqrt(p_in p_return)。对这些n prior逐项求Σm/Σv。
- terminal_half_log：最简同信息强控制。非末TARGET入边权1，末TARGET入边和return各权.5；μ=Σw_e m(p_e)，ν=Σw_e² v(p_e)。它先corrupt原边再平均log；候选先平均clean log再corrupt。区别仅是这两个步骤的顺序，不把均值或长度校正本身当原创。

alpha0下m恒等c，候选、target_only、terminal_half_log及两校正μ均n c，所以P=p∝R。原all_leg保留exp(cK)，原文早已说明。alpha1下log sqrt(p_in p_return)=.5(log p_in+log p_return)，候选与terminal_half_log law精确相等；不能要求此四格严格战胜同一个对象。故执行前补强控制并记录未执行sketch修订，主要必要继续条件落在alpha=.25四格，完整分母4、不换输入。端点用于恒等核验，非新增优势。

这不是完整GFlowNet的normalized backward probability证明，也未解决raw→公共T的轨迹重数问题；这里只定义有限带标签目标，原文weight同样需与normalized PB区分。本包不以有限law直接替代真实物理actor的训练目标或创新证明。即使必要继续条件通过，仍待实际新构造/更新、支持、G0查新和完整G3；失败则只关闭当前固定noise配方，不否定RL/diffusion/GFN。
