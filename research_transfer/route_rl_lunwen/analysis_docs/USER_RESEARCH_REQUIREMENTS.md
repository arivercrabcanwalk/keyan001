## 2026-11-05 指标解释与路线RL先例复核

最新审查收据：`joint_weather_emergency/20261105_route_claim_audit/REPORT.md`。用户当前要求仍是RL直接选择无人机物理路线，不选择算子；本轮不创建子agent。现有开发结果中SCST/LOO在部分应急服务次指标和两个命名作者在线适配上有较好数值，但六个actor seed均选回initial，因此RL增量未证明。相对 `oldbeam` 完整J差1.6253%、平均成本高约2.40%、8/8 DEV地图落后。CEDA/DRLSA/Ulmer以及Ren/PADA资料已做有边界的先例核对；G0无通过的新机制，G3/G4未通过，G5–G8未完成。不得在已暴露DEV续调或重训；先提出可逐式对比、可证伪的物理路线机制，再冻结新开发集和强同信息baseline。详细数字/文献核验层级见审查报告。

## 2026-11-05 用户“查清瓶颈”执行结果

当前最新包joint_weather_emergency/20261105_bottleneck_diagnosis/REPORT.md。TRAIN-only受控8倍SCST训练/动作分支/拟合完成，已证弱先验修正与部分动作的±6硬限幅障碍；不等于已证明全部性能差由限幅造成。仅root/<EXPERIMENT_SERVER>/物理TARGET/RETURN，旧DEV/VAL/TEST不动；无新Formal，后续调整先验和信用须受控新协议。

## 2026-11-05 深度重构实际验收

用户目标“大幅领先”仍是研究验收条件，不是预设结论。joint_weather_emergency/20261105_deep_revision/REPORT.md的三算法九运行已完成且主优势未达；768优化器步/960训练轨迹/1184评价均已审计。六actor选回initial；DQN部分seed相对弱initial有学习但未胜最强登记nonRL。后续不在本轮DEV重复调参、不把作者弱适配或先验回退包装为RL成功。仅root、<EXPERIMENT_SERVER>、物理TARGET/RETURN，Formal/投稿另验。

## 2026-11-05 用户要求深度复盘与RL技术重构
用户明确要求深度复盘调整、RL不限PPO/A2C，研究目标为大幅领先非RL与作者方法。当前新包joint_weather_emergency/20261105_deep_revision/，先保存TRAIN诊断后冻结v2技术筛选；仅root、<EXPERIMENT_SERVER>、物理TARGET/RETURN，旧20261105包与Formal封存不变。5%主J降幅是设计目标不是承诺；成功必须实证。不得弱化基线、改任务或J寻找阳性；PPO/A2C不是必须沿用的技术限制。

## 2026-11-05 本轮用户新增联合任务
当前要求：加入天气和紧急任务，完善项目，在<EXPERIMENT_SERVER>比较RL、非RL和作者方法。有界联合开发入口joint_weather_emergency/20261105/PROTOCOL.md，独立数据/资源身份；不把历史两分支拼成联合结果、不恢复旧P3、不篡改旧门槛。新动态主J与旧严格成本cap/M_return分开验收。仅root执行，至少3seed；具体资源、实际进度和成功通知以新包冻结协议/STATE/服务器原收据为准。开发阳性与投稿就绪分开报告。

## 2026-11-05 最新执行覆盖
用户最新要求：继续完成所有任务不要再创建子agent 就用你自己的模型。当前仅root独立执行，不新建或恢复子agent，覆盖旧G4多agent调度；历史审计身份不变。实验在<EXPERIMENT_SERVER>，物理路线动作和失败保留/准入不变。40新身份/126实际比较，校准验证24/24额度满，状态以LATEST_STATUS和return_makespan/STATE.json为准，不按历史尚无新图/未训练字样重复执行。

# 用户研究要求：当前有效版本

日期：2026-11-03。来源：用户本对话最新直接指令。

> 记住你先充分记住 我们只要做rl选择无人机路线 而不要参与任何选择算子
> 调整完之后重新给我汇报我们的总规划

## 固定约束

1. 主研究是RL直接选择/构造无人机物理路线；默认基础动作是选择下一目标或返航，形成访问顺序和多趟划分。
2. RL不选择算法、搜索算子、destroy/repair、邻域、Location/Assignment/Routing/Joint标签、操作强度、子问题或repair计算预算；对这些选择换名称仍属于旧路线。
3. 站点与站型由既有非RL外层处理。路线研究先以固定站点及明确任务归属作为归因边界；是否扩展物理跨机/跨站路线决策须另定义、查新和冻结，非本次自动批准范围。
4. 用户原要求仍保留：RL须实际胜最强非RL；创新逐项实证；方法冻结后使用全新独立正式测试；之后才编写新论文正文。
5. V6/semfix复现不重做；保留所有旧负结果和已暴露数据身份；不通过换网络/参数/种子或将旧Stage A改名重跑来宣称新方向成功。
6. 后续最新用户指令已授权实际开始G0–G8，尤其G4设计必须多Agent协作、交叉讨论并以真实效果验收。旧两小时窗口已结束；本次为新授权窗口，未给新截止时间。旧定时器仍暂停。
7. G8按本轮约定解释为完整研究材料与投稿就绪验收；无公开/投稿授权。强于非RL是验收要求，实际阳性与否由冻结协议和全部数据决定。

## 用户后续确认的路线范围

2026-11-03 用户对“路线范围”回复：“允许站内联合分配与路线（推荐）”。固定站点、站型、目标到站归属；允许在站内直接决定LD/SD目标归属与物理路线，动作只为(slot,target)/(slot,RETURN)。这不是算子选择，也不自动构成创新或Stage B/C准入；新机制仍须独立验收。

## 接手入口

- 当前总规划：`RESEARCH_PLAN_ROUTE_RL.md`。
- 研究结果与调度：`LATEST_STATUS.md`。
- 历史证据：`stage_a_audit/MODIFIED_FILE.md`、`execution/20261102/ROUND_DECISION.md`、各轮封存裁决。

## 2026-11-03 最新目标审批：A方向
用户批准新指标规划后明确要求开始优化RL并continue。当前主问题更新为：固定站点/站型/target-station，RL仅直接构造物理路线；完整原成本不增加（共同可行anchor、epsilon0、绝对容差1e-7）下min全图最终返航M_return。D条件改进是本阶段主制度，6s/12s各检验平均5%目标及地图95%CI下界>0，不是已取得效果。
A第一包G0–G3按P2.1执行，最多48新机会/开发图+24隔离非RL校准/验证、16 CPU核小时；G4训练/新Formal及正文各依原准入，不恢复旧自动任务。当前 <LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/STATE.json 和 <LOCAL_PROJECT>/route_rl_research/20261103/return_makespan/EXECUTION_PLAN.md 优先于此前原成本目标文字；原模型evaluator与历史结果不修改。

## 2026-11-03 新增作者基线胜出要求

用户最新要求：成本与作者原算法相当时，RL路线方案在全图最终返航时间上领先作者原方法，并实际证明RL有作用。操作定义采用逐图严格成本非劣：共同锚点为新图上Liu作者原法的完整可行解 `R_Liu`，候选须满足 `C(candidate) <= C(R_Liu) + 1e-7`（epsilon=0）；不是跨图均值成本相抵。RL与所有非RL候选从同一作者锚点开始，在6s/12s相同墙钟下比较 `M_return`。RL只有同时优于作者锚点及同目标最强非RL，才支持RL独立贡献；失败/超时/不可行地图均保留。

当前 `M_return` 与作者官方 `Check.calculateLatestTime` 的定义相同（每架无人机累计多趟飞行、服务及返航时间，再取全局最大值），故不得称“首次提出新指标”。可检验主张是：成本不增加时改善作者已报告的完工时间指标。固定deployment/station type/target-station的实验只支持条件路线结论；若声称全流程系统胜过作者TSALNS，还需另行冻结同总墙钟端到端比较E，不得用条件路线D替代。

## 2026-11-04 最新执行偏好

用户明确：“实验都要放到服务器上去跑而不是windows”。最新模型要求：“注意所有子agent都不许用astra 强制使用sol ultra”，覆盖此前继承主模型的要求。

- 后续实验、训练、作者求解与质量评测统一在服务器<EXPERIMENT_SERVER>执行。Windows历史合成smoke和6图materialization仍按真实来源保留，不改写为服务器来源。
- 所有子agent强制Sol ultra：`model="gpt-6.1-sol"`、`reasoning_effort="ultra"`、`fork_turns="none"`；禁止Astra，不续用旧Astra代理。任务上下文须显式完整传递。
- 最新实际进度以LATEST_STATUS首段、return_makespan/STATE.json及<EXPERIMENT_SERVER>原始结果为准；此前“0地图/0训练”等为历史时点记录。

模型版本说明：用户指定Sol系列与ultra，未限定版本号；gpt-6-sol持续429后，使用工具列出的当前Sol版本gpt-6.1-sol，仍强制ultra，禁止Astra。
