# 补偿性后续路线：六项裁决及有界工程规格

本轮先完成查新裁决，再补一个可以共享给所有方法的公共组件。普通ejection-chain、受约束最短路、固定已服务部分、追加资源标签、RL下一目标接现成repair均不单独构成新机制。**TARGET_COMPENSATING_CHAIN_AS_INNOVATION_V1关闭；G0/G3均不因此通过。** 本包不训练，也不生成科学人口。

## 1. 输入、动作和边界

采用已批准固定风A、原simple linear energy、原LD/SD容量/累计duty/返本站/完整覆盖/target-station/全图成本语义。每slot分为固定已返站航次D、已服务但尚未返站的前缀P、当前未执行后缀T、其他尚未执行航次F。完整路线为D+(P+T)+F。actor仍仅输出(station,slot,target/RETURN)，station只是slot的固定索引，不是新增动作。

TARGET从本所属站尚未执行部分删除目标后接在P末尾，并将这个新TARGET也锁入前缀；RETURN把P闭合并保留余下T/F。所有后续规划只改未执行部分，不能取消真实/本次指定的TARGET或RETURN。禁止跨站转移目标。工程输入4个全新手写二维fixture；cap=C(W)，不是作者Rw，不充作科学A锚点。

## 2. 实际新增工程步骤及查新边界

缺口是现有单移位见证会拒绝可由另一站降成本补偿的下一动作；旧station-bank只有完整父解接口，没有真实物理前缀/动作后续接接口。补齐下列**常规组合组件**，不以缓存或组合命名为创新：

1. 固定本次物理动作后，枚举本动作站的一次尚未执行目标relocate（含不改）；本次前缀不动，中间强制动作可暂时不可行，最后必须完整合法。
2. 若动作站候选与其他站原见证已满足阈值H和全图cap，直接交付；若尚有费用债或远站H违规，则生成其他站同样的一次relocate邻域。
3. 每个远站在M_s<=H下选择最低运行时间schedule。共享实现对完整站前缀和见证字节建立身份，首次需要时生成，并建立按M_s排序的最小费用前缀表。相同前缀下后续物理动作/阈值可共用；前缀改变就不共用。
4. 原站/slot顺序重算完整成本，最后交付整图路线；费用不足、物理违规、没有完整解均返回不支持，不偷偷执行其他物理动作。

这是一个有限邻域的公共可行续接器。它产生原完整父解池之外的尾部，但不提供池外全局最优证书。它与完整静态station-bank的输入/生成域不同；有限邻域组合和缓存本身仍是常规算法步骤。其价值先以漏掉的动作支持和完整计算成本检验，不能冒充RL增量。

## 3. 物理递推及全图融资

对有向匀风leg t_w(i,j)，trip时间T=sum legs+sum target services，energy E=.018*sum legs+sum target energies。每个trip单独比较slot电池；slot duty=sum各trip T，RETURN不清零；C=C_fixed+.5*按原站/slot次序累加duty，M=max各slot duty。背景站同样入C和M。

对目标a插入边(p,q)且从边(u,a),(a,v)移走，闭合路线的时间差为[t(p,a)+s_a+t(a,q)-t(p,q)]+[t(u,v)-t(u,a)-s_a-t(a,v)]。若同一段相交、删除空trip或新建trip，不能直接叠加独立边差，必须重算具体route string。电池差含目标能耗；费用融资只能用完整最后差额，不能用逐站cap或重复计算已删除边。实现将所有候选完整重算，避免依赖错误的可加近似。

## 4. 可证伪预测和强对照

BASELINE为每动作独立生成同一远站邻域，MODIFIED为按完整站前缀共用邻域及阈值前缀表；两者相同输入/物理动作/局部候选/阈值/排序/回退，全部查询结果和最终完整路线必须一致。另记single-shift和只有动作站relocate的支持，不将它们当最强对照。

核验所有交付解的target-station、原前缀及本次物理动作，并用冻结wind_scorer独立重算；小例再用独立实现的route-string邻域和完整远站Cartesian product核对动作支持。负控制至少包含不允许跨站融资、遗忘真实RETURN、清零累计duty、错误SD容量、忽略全图cap。支持增加不是质量或学习优势。

完整成本含本地强制动作/候选构造、全部远站枚举/打分、索引建立/查询、最后整图重算；不只报query lookup。若没有费用补偿恢复动作，或共享全进程未快于独立实现，不申报当前效率主张。4例全部保留，不改fixture/阈值挑阳性。

## 5. 后续公平性和实际研究状态

本组件开放给nonRL/BC/标准RL/任何未来新机制，强ALNS仍保留原生搜索域，不被本一次relocate邻域取代。未来科学6s/12s须包含全部候选生成和完整验收；本包不是G3科学资格或训练放行。数学/工程通过也不会把已经关闭的普通链修复改判为G0创新。

## 6. 冻结、预算及终止

运行前冻结本规格、INPUT.json和validation源码hash；只在<REMOVED_ENDPOINT>串行执行BASELINE、MODIFIED、AUDIT、ROLLBACK、RESULT五phase，每phase CPU60s/wall75s/2GiB，总硬额300CPU秒。最多一次不改输入的实现错误修复，额外60CPU秒；总额360CPU秒。上一TERMINAL必须exit0且结果complete后才开下一phase。每fixture查询上限120、每站一次relocate候选上限4000；触限记失败，不换输入。另副本回滚恢复baseline分支及完整answers/stdout，主MODIFIED_FILE保持修改。保护STATE/旧额度/旧DEV与失败不动。
