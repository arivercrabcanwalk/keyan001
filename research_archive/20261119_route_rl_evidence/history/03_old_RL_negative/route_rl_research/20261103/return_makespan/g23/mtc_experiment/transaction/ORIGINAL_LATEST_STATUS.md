# 最新研究状态
## 2026-11-03 当前执行更新（优先于以下历史条目）
执行入口仍为 `<LOCAL_PATH>`；用户要求尽快推进，但结果必须由实验决定，不能预设RL领先。当前候选 `M_return` 与Liu官方latest-completion指标同定义，不得称新指标；平均目标完成时间正由多Agent审查是否作为本研究新增报告的主要指标（并非学术领域首创）。

作者端点已做真实Linux验收：<REMOVED_ENDPOINT>现有Corretto JDK17将哈希锁定J1b/J2b各编译为20个class，逐class哈希复核一致。J1b在手工合成3站/10目标夹具上的一次端到端smoke exit 0，两套独立评分器及作者最新完成时间/成本完全对账；该夹具已永久排除，非质量证据。17项runner、13项生成器、7项非RL基线合成测试均通过。原作者/V6/semfix文件未修改。

几何拒绝率pilot一次12,000张整图提案，67通过、11,933拒绝；(3,20)和(10,110)各0/1000，旧v1全图重采生成器不适合当前全家族配额。官方120图和pilot全部12,000身份已并入永久排除清单；smoke夹具单独排除。新v2逐点条件proposal sampler在连续概率模型下经独立复核为有条件GO，只能叫 `constraint-reconstructed sequential conditional-uniform-proposal`，不能说复现作者生成器，也不能无条件声称落点IID均匀。53-bit离散网格attempt-cap上界仍待独立计算，故尚未生成任何开发地图。

Residual-budget dual-price physical-route actor经哈希冻结初审与交叉审计仍为G0 NO-GO（普通RL control需等G2/G3后另审）；反方代理已披露初审为NON-BLIND，报告中标注。未训练，也未改名复活旧候选。当前新研究地图0、作者研究图求解0、nonRL质量调用0、RL训练0、Formal0。G4关闭；当前下一步是metric endpoint独立审查与v2有限网格审计，随后冻结完整方案才进入G2/G3。

## 2026-11-03 A方向已批准：全图返航目标工程接续
用户已回复“是的我允许 开始优化设计我们的rl吧”并要求continue。当前真实执行入口：<LOCAL_PATH>
批准A第一包G0–G3：固定站点/站型/target-station，RL只做物理slot-target/RETURN；完整成本epsilon0（绝对容差1e-7）下min全图最终返航M。D条件改进为主、6s/12s、5%为待检验目标而非成绩；48新机会/开发+最多24隔离非RL校准/验证、16 CPU核小时科学上限。G4训练包和Formal仍另行准入。
新增scorer、FullMapRouteEnv及deadline/raw/fallback记账已实现；37核心+15独立作者scorer脚本root复验+8旧接口合成检查通过，隔离回滚恢复原hash与cost reward。独立代理又完成9项冻结动态场景及15项scorer终验，源码hash匹配且未改源码。原station_env/V6/semfix未改，未重跑复现。工程通过不代表路线质量。
product站轨迹信用与cost-capped threshold-conditioned physical-route policy均经独立交叉审查NO-GO；后者只是通用goal-conditioned/constrained RL应用，无独立机制增量，不得训练或改名复活。三方实际交叉材料已封存。G1独立工程终验通过：9动态+15 scorer测试，未改源码。
用户最新要求已落实为逐图作者比较：新图的Liu原法完整解`R_Liu`是共同锚点，候选成本需`C<=C_Liu+1e-7`，RL/非RL以相同6/12秒改善预算比较作者已有的`M_return`指标；RL还须胜同目标最强非RL。`M_return`并非新指标首创。G2/G3独立协议审计已完成，建议明确标注constraint-reconstructed新图；root仍需冻结并实现基线。新地图/质量调用/训练/Formal仍0，RL效果与创新未证明。
下一步是root冻结新数据身份、约束重建生成规则、`R_Liu`配置及强非RL实现，随后在48+24上限和16 CPU核小时内执行一次有界G2/G3；G4必须等有新机制、机会证据及单独训练资源包。

## 2026-11-03 新指标深度调研与待审批规划（最新用户任务入口）
用户要求结合现有代码研究成本以外的有效评价维度，形成具体规划供审批。本轮调研/规划已完成；**不表示新方向获批，原研究goal保持paused，旧自动任务不恢复。** 现行科学协议与route_rl_research/20261103/STATE.json保留原历史状态；当前规划状态见project_status/20261103/metric_replan/STATE.json，优先级高于下方历史“ACTIVE”字样。
最终提案project_status/20261103/metric_replan/PROPOSED_RESEARCH_PLAN.md（P2.1，SHA256 c63276a49b669ff311386bd4a2ca40c5d4b10cdf4aef3a73fa182d991a78f34c）。推荐固定站点/站型/目标站归属，RL只做物理slot-target/RETURN，在共同完整成本不增加下min全图返航makespan；平均目标完成及anytime为预定次维度。Liu已有makespan与balance，新增指标本身不是创新；总距离/总工时/总确定性能耗在固定域与cost仿射等价。
三Agent独立推导/初判hash冻结后实际交叉、P1具体异议、P2差分审查及P2.1包含关系修正均留档。规划可审批不等于G0机制、G4效果或项目通过。直接复用V6/semfix，不重跑复现。
本轮72旧G2完整解及1200旧作者J1b/J2b完整解只读描述性计量，对账异常0；未变路线/排序、未生成新方案。旧G2 joint相对Greedy成本均降3.1397%、raw M均升14.2150%、平均目标完成均升17.7820%，不是RL效果/Pareto必然代价。旧作者固定trip重派改善上界均10.2299%/9.9182%，287/297各600运行已等该有限域下界；上界可能不可达，非已实现收益/新图保证。全部暴露身份保留。
推荐只先批G0–G3：48新机会/开发+最多24非RL校准/验证图、16 CPU核小时总上限；主epsilon0，D条件路线改进为主，若声称全流程胜作者，E须独立预算/验收。5%是待批实用门槛。关键基线含cheap controls启用版、同目标joint/threshold强非RL、最近多趟minmax适配；G4同训练资源至少3seed及消融另审，之后全冻结新Formal。当前新增solver/evaluator/训练/地图/完整解均0，论文正文/公开/投稿仍无准入。
接续：等待用户审批目标、成本保护、效应与第一包资源；未获审批不更新科学协议、不启动新矩阵/训练。完整证据索引project_status/20261103/metric_replan/EVIDENCE_INDEX.json。

## 2026-11-03 站内联合路线G2已完成（当前入口）
用户授权固定站点/站型/目标站归属下，站内联合SD/LD分配和物理路线；RL不选算子。V6/semfix直接复用。
一次预冻结的24旧暴露图数值诊断完成exit0：132站/98非空，11图两种参照完整、13图partial；72个parent/fixed/joint完整解均独立evaluator可行，144份历史ALNS完整解逐份复核通过。相对Greedy，fixed-owner平均改善0.933169%，joint平均3.139719%；完整11图fixed→joint额外差3.586871%。历史ALNS best-of3→joint平均约1.53%（16赢8输），其partial13图反而平均落后约0.20%。旧ALNS固定owner而新参照放开owner，不能据此称胜同域强非RL或RL优势；partial不封剩余空间上界。执行core78.600s，2图实际超过12s调度阈值，全部保留。
独立结果审计0项对账错误。报告 route_rl_research/20261103/joint_route_env/G2_REPORT.md；审计 route_rl_research/20261103/audit/G2_POSTRUN_INDEPENDENT_AUDIT.md；冻结FINAL2、所有完整解/未解站/原始日志保留。第一次仅preflight因并行fake-test变更被hash guard拒绝，未求解；原始科学代码协议未改后重冻执行唯一一轮。16DP合成+9driver假对象测试通过；隔离回滚已验。
服务器已用原既有liu2026_repro_ed25519密钥连接<REMOVED_ENDPOINT>成功，05:38:07UTC相关研究进程0；未新启动远端实验。
下一步G0依据trip/battery组合收益设计具体新对象；查新已命中SED2AM（多趟累计工时）、PIP/LMask（预防/回溯mask）、2503.10421v1/v2（constraint-oriented hypergraph route RL）。这些是具体先例，不能换名网络创新。当前G0仍开放、G4新训练未启动、Formal/论文正文准入false。接手先读 route_rl_research/20261103/STATE.json。

## 2026-11-03 站级G2诊断接续（尚未执行旧图DP）
用户已确认允许固定站点/站型/目标到站归属下，站内联合LD/SD归属和物理路线；禁止RL选择算子。G0新机制仍未通过，G4训练未启动。
站级DP合成16项通过，已修正原草稿缩进/预算异常捕获与coverage/energy字面谓词；fixed-owner与joint参照分别实现。历史24图×6/12s×3求解seed的144对ALNS完整解/meta身份与固定owner域核验通过，未重跑ALNS。driver合成错误路径及三方终审收口后，冻结一次24旧图数值机会诊断；未解域保留，部分可行改进不作剩余机会的上界。
工程差分与隔离回滚见 route_rl_research/20261103/joint_route_env/g2_transaction/VERIFICATION.txt。服务器liu-gpu连接拒绝、<REMOVED_ENDPOINT>非交互公钥认证未过，实际远端进程状态尚未观察；未新开远端任务。本阶段完整输入和历史解已在本地，不依赖远端重求解。当前入口仍为 route_rl_research/20261103/STATE.json。

## 2026-11-03 新执行窗口（当前进度优先于下方历史记录）
用户已要求开始G0–G8，重点G4采用多Agent协作。RL只直接决策物理路线；旧Stage A与全部历史负结果保留。旧V6/semfix复现不重跑。

**当前G0仍未通过，G4新训练尚未启动。** 已封存的 `fixed-ownership completion-aware pointer`、`joint station slot-target serialization` 和 RSCC route-slot counterfactual credit 均为G0 NO-GO：前者等价标准剩余子集RCSP/partition DP；第二个在固定站/站型/目标站归属、无跨机同步资源时可双向化为LD/SD目标分区及各自路线，且已在旧Stage B草案出现；第三个的修订因子化信用公式在适当score分解下可成立，但属于COMA式信用分配与Li vehicle-node route decoder的应用组合，未建立独立增量。RSCC初版flat-pair action-dependent baseline保留为失败工件，不可直接用。多Agent实际交换见 `mechanism/joint_physical/EXCHANGE.md` 与 `CROSS_EXAM.md`。

旧按机G2复核发现其不覆盖DABS站内重新分派；旧0.156895%是177组×6旧单元的暴露路线组统计，不能代表完整地图目标门槛；`C6-C120`不是剩余机会的上界，同seed也不保证搜索轨迹嵌套。上述校正均未重跑solver。站级split-DP可作为固定站域机会/强非RL参照，但完整冻结协议和执行均未完成。root统一控制服务器实验；本地/服务器当前无新Route-RL训练或质量矩阵。

**本轮新完成的工程验收**：`joint_route_env/station_env.py`实现站内物理路线构造，不含算子动作；8项合成检查通过，包括故意过早RETURN产生死路时显式报告、不伪装成完整解。旧 Stage A 暴露验证集按 frozen input hash 回放24/24张图、132个站点，其中98个非空路线池；原 Greedy route witnesses 全部通过独立 evaluator，完整目标值逐图相同，reward 对账误差0。另冻结seed `20261103`在相同24图各站跑一次均匀合法动作，24/24完整图可行、98个站无死路、无回退；这只是一次工程stress pass，不代表一般失败率或质量。G1工程集成通过但总体仍部分通过。记录见 `route_rl_research/20261103/joint_route_env/G1_ACCEPTANCE.md`、`G1_STAGEA_REPLAY.json`、`G1_RANDOM_FEASIBILITY.json`。

当前修订计划 `RESEARCH_PLAN_ROUTE_RL.md` 覆盖G0–G8，G8为完整研究包与投稿就绪验收，不含公开/投稿授权。项目未完成、RL优势未证明、创新未实证、论文正文准入为false。

## 2026-11-03 用户方向修订（当前优先入口）
用户明确：“我们只要做rl选择无人机路线 而不要参与任何选择算子”。RL只直接决策下一目标/返航/分趟等物理路线，旧宏控制PPO/算子选择不再是研究主线。当前要求见 USER_RESEARCH_REQUIREMENTS.md；修订后的完整G0–G7见 RESEARCH_PLAN_ROUTE_RL.md；后续代理先读 AGENTS.md。
本次已完成记忆与规划调整，未启动新实验/训练/自动任务。复现、旧负结果、完整原模型、同资源比较、至少3训练seed、双预算0.3%、新Formal与正文准入保留。旧契约中算子控制及“先创新非RL算子再学选择”的依赖由新规划替代；具体新路线机制尚未通过G0，旧Stage A及R2–R7封存不变。下文保留上一工作窗口的事实与暂停回执，不当作当前路线方案。

日期：2026-11-03（Asia/Shanghai）。本轮三项有界证据/数学任务均已封存；已按用户两小时截止暂停，总体研究未完成。

## 用户本轮截止（优先）
开始00:15:16，截止2026-11-03 02:15:16。每次接续先运行 <LOCAL_PATH>)。旧30分钟定时器PAUSED；一次性截止任务lrphsd已设，不自动明天恢复，不关闭服务器/电脑、不停止来源未明进程。

## 最新有界阶段（已于01:29前收口）
<LOCAL_PATH>
<LOCAL_PATH>
结论G0 NO_GO原样商化：在存在证书覆盖mixed可行分槽的同C纤维中，原normal operator9请求域不相容；不是postguard核/收益/可达性实测。旧3_10_1解析锚点保留原trip实数可行前提，不把float标志当形式证明。静态LD定理不变，一般可action-remap的homomorphism亦未全否定。三方先独立冻结后实际双向交叉；31工件、13 JSON、103路径/hash引用重开PASS，初始状态历史引用1处、未解0。3篇primary全文及章节已留档，新科学执行0。禁止原样压缩分支改动作/换名/preimage复活。
裁决：<LOCAL_PATH>
证据：<LOCAL_PATH>

## 最新完成：现成10小图DP声明审计
- 父26件、30完整baseline解/30metadata及57匹配源码字节已补齐。独立30/30 task身份/结构/字段，源aggregate匹配全部30meta；原始字段和全失败记录保留。
- 原历史CLEAN同完整域DP重求解复验exit0可复用；V6/semfix与审稿包验收不变，不重跑复现，也不新开数值形式证明阻塞。
- 192工件、65 JSON、389路径/hash引用重开PASS，历史版本依赖1处显式解析，未解0。近似最优参考是工程用语，严格实数/全部生产IEEE最优与零headroom不由此自动证明；没有判参考值错误。
- 10图best-of3请求3×6s，不是单次6s；保存meta时间不是diag必fresh或全进程wall。n_trips含空trip，3图非空计数纠偏存sidecar，原文件不改。
- 这是非RL旧小图的证据审计，不是创新/RL优越性/新Formal。本阶段新增solver/evaluator/geometry/quality/training/Formal均0；远端当前相关研究进程0（01:07:52前后只读观测）。
裁决：<LOCAL_PATH>
证据：<LOCAL_PATH>
剩余：<LOCAL_PATH>

## 已封存结构结论
LD适用范围：官方102/120、旧dev8/12图所有非空站满足条件，若原实数可行/最优解存在，各DABS的SD完整trips可转LD保mode/ownership/trip/费用得到等价代表。其余18/4图只部分覆盖，不证明双机必要。SABS/站型/覆盖/分配/每趟电池/分趟/trip内部路序仍非平凡，纯trip列表排列不是额外物理耦合。该基础消维不是创新/性能/RL优势，未用于生产IEEE剪枝。
<LOCAL_PATH>
<LOCAL_PATH>

## 不变总体门槛
V6/semfix复现已验收直接复用；R2–R7已封存，不换参数/种子/名称复活。新G0算法未通过；创新实证、RL胜最强非RL、全冻结后新Formal、论文许可全部false。继续原G0–G7、6s/12s双预算0.3%筛选、地图级CI、完整比较族和全成本，不保证阳性。无新具体可执行对象时不重复求解或写同一无进展日志。
原契约：<LOCAL_PATH>
原门槛：<LOCAL_PATH>

## 截止前检查点
<LOCAL_PATH>
当前无通过G0的新算法、无本轮新启动研究求解或训练，全部代理阶段已收口。不为填满时间启动无假说实验，也不重写相同无进展日志；保持截止安排，02:15:16暂停，明天等待用户恢复。

## 实际暂停回执（当前调度真值）
Goal实际返回status=paused；回执时间UTC 2026-11-02T18:17:05+00:00。三个所属代理均completed，无活动代理需中断。一次性lrphsd与旧lrphsd-agent均PAUSED；未新设恢复、不关闭电脑/服务器、不停止未知进程。截止后只做保存与暂停，无新研究。
<LOCAL_PATH>
<LOCAL_PATH>
用户明确要求继续后才开始新工作窗口；整体创新/RL/Formal/写作门槛仍未完成。
