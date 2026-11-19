# A方向接续裁决：全图工程已实现，原创机制尚未通过

日期：2026-11-03，Asia/Shanghai。用户审批依据为P2.1及“是的我允许 开始优化设计我们的rl吧”，随后要求continue。

## 1. 当前批准内容

固定站点、站型及target-to-station；允许站内slot归属和物理路线联合决定。RL动作只有slot-target与slot-RETURN。新问题为完整原可行约束下，C<=C_ref（主epsilon0、绝对工程容差1e-7），最小化全图最终返航M_return。D条件路线改进为主制度；E全流程另立协议，不混用。5%是待检验点估计目标，地图级95%CI下界须大于0，6s/12s均须满足。

第一审批包为G0–G3：最多48新机会/开发图、最多24隔离的非RL校准/验证图、16 CPU核小时科学调查上限。G4训练资源、Formal及消融仍须后续放行；本次没有训练许可被工程测试自动替代。V6/semfix与全部旧负结果复用，旧自动任务未恢复。

用户后续要求把Liu作者原法纳入明确胜出标准：新图上以作者完整可行输出`R_Liu`为共同锚点，逐图`C_candidate <= C_Liu + 1e-7`，在相同6s/12s路线改进墙钟下比较`M_return`。RL若未同时胜作者原输出和最强同目标非RL，就不称RL有独立作用。`M_return`与官方`Check.calculateLatestTime`同语义，不再称新指标；固定部署域仅能支持条件路线结论，系统级TSALNS结论须另过同预算E。

## 2. 已实际完成的工程

- scorer.py独立由原坐标计算原可行性、完整成本、每机累计多趟时间、目标完成前缀和全图M；不信任optimizer距离缓存。
- CostAnchor冻结实例/参数、完整见证、站型及目标站归属；候选可换同站slot，但不能换站、站型或超全图成本cap。
- global_env.py在原StationRouteEnv副本上增加FullMapRouteEnv。固定程序调度站点；不同机/站从t=0并行，同机多趟累计。原station_env及其cost reward未修改。
- 成功完整轨迹的gamma1奖励为-P增量，P=max(已闭合duty+当前trip elapsed)，终局return=-M_return。必要成本mask仅是下界，不保证后续可完成。
- delivery.py保存raw候选、独立评分、回退及其原因和验证结束/输出就绪时间；逾时验证不能追认为按时输出。回退并非免费，D输入锚点生成成本另列。
- 原始hash、副本差分、四件事务包和另一副本回滚均已实测。probe前后是同一路线，reward由-4改为-5，不是路线质量提高。

## 3. 测试与验收边界

事务运行实际exit0：37核心合成测试、15项独立作者scorer脚本的root修复复验、8旧站接口合成兼容检查，全部通过。独立反方此前的14通过/1错误及其自身首次导入错误均保留。发现的巨大整数cost输入OverflowError已修复；同一15项脚本最终root复验通过。

独立代理现已按冻结输入完成最终动态终验：9个动态测试及15项独立scorer测试通过，三份源码hash与冻结值一致，未修改被测源码。三项初次失败均为验收harness问题并保留。最终签认仅覆盖冻结的合成工程契约，不代表一般策略完成率、地图质量、创新或学习收益。命令、逐项字面输出和退出状态见transaction/VERIFICATION.txt、RUN_RECEIPTS.json及agents/final_acceptance/RESULTS.json。

## 4. 三方机制审查的结果

三角色先独立冻结INITIAL及hash，再读取彼此冻结文稿并交叉。具体对象为独立站完整路线bank的product-form成本门/max收益信用。有限16-bank数学核验通过：无偏/方差及合法LOO有条件成立，self-including baseline有偏，动态跨站条件策略有失效反例。

一手正式原文Kuntz、Crucinio、Johansen，Product-form estimators，Statistics and Computing32:12，DOI10.1007/s11222-021-10069-9，§2.1 Eq.(4)，令测试函数为G乘各站score之和即直接得到候选公式。故该对象作为独立新估计器贡献G0 NO_GO。保存为标准参考，不改K、reward或名称复活，不据此启动训练。原文PDF、逐式代入、初判/交叉hash和16-bank结果均保存。

全图动态预算mask会导致跨站条件依赖，不能配用要求站间独立的product估计。普通max奖励、pointer、pair动作、标准mask或共享anchor均不单独构成新机制。

## 5. 新阈值策略候选交叉裁决

独立机制代理冻结了一个cost-capped threshold-conditioned physical-route policy候选；机制代理、独立先例审计和G2/G3反方审查先后冻结初判、实际交换异议并收到逐点答复。三方一致NO-GO：它仍只输出(slot,target)/(slot,RETURN)，但标量阈值条件化没有超出通用goal-conditioned/constrained RL；Liu官方latest-time与M_return同构，作者已有loadBalanceInsertion，异构min-max route RL及多趟min-max无人机非RL也有近邻先例。阈值候选无G4新颖性准入，不换名、换阈值或改奖励复活。完整交叉见agents/new_route_mechanism/CROSS_RESPONSE.md、agents/g0_prior_art_audit/EXCHANGE.md及g23/nonrl_data_protocol/CROSS_RESPONSE_NEW_ROUTE_MECHANISM.md。该NO-GO只关闭该候选，不否定成本保护下优化作者已报告M_return的实证问题。

## 6. 下一阶段与明确未完成项

G0的问题定义已批准，但product-form与阈值条件候选均为交叉确认NO-GO，尚无新机制通过。G1通用实现、root动态测试/回滚及独立9项动态+15项scorer终验通过。G2/G3已有独立数据/基线协议审计，root尚未冻结实例生成、作者共同锚点、身份清单和基线实现；新地图、质量比较均0。G4新训练、G5新Formal、G6创新消融、G7新正文、G8完整研究验收均未开始。

按用户最新要求，每个新地图以Liu作者完整可行路线为共同锚点`R_Liu`，逐图要求`C_candidate<=C_Liu+1e-7`；RL和非RL共享6/12秒路线改善预算并报告`M_return`。固定部署/归属域只支持条件路线结论；系统级TSALNS优势另需E协议。先冻结透明constraint-reconstructed生成器、暴露身份排除、R_Liu配置/完整cost、失败计分和强同目标非RL实现；再执行唯一有界G2/G3包。新G0机制仍须具体、可证伪且有先例增量；G2/G3不产生RL训练许可。

本轮新科学地图/solver/训练/Formal调用均0；synthetic工程和数学测试单列。08:35:56UTC远端相关研究进程0；该系统Python未见torch、未见nvidia-smi或nvidia设备，尚不能据此判断其他环境/主机的训练可用性。未启动远端任务。

本轮工程交付不代表RL优越、创新、论文写作或项目完成。当前真实入口为本目录STATE.json；上轮cost状态和审批前提案状态作为历史保留。
