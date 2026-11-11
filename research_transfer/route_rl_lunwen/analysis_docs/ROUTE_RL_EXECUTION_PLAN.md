# 2026-11-05 当前覆盖
下方保留早期计划。当前40新身份/40作者尝试/126实际比较；校准验证24/24满，预约7.5/16科学核小时。G0无创新，G3未过，G4无完整RL候选、P3关闭，G5–G8未过。仅root不创建子agent；新科学协议须有非救结果假说及明确数据资源修订，不重复旧计划未生成/未训练任务。剩余见REMAINING_TASKS.md，工程不自动放行科学。

# 已批准A方向的执行计划

## 当前唯一目标

固定部署/站型/目标所属站，直接构造站内无人机路线；主目标min全图最终返航M，原硬约束和完整全图成本cap C<=C_ref不变。RL不输出算子、算法、子问题或计算预算。主epsilon0、绝对对账容差1e-7；D条件改进6s/12s、平均M降幅目标5%、地图95%CI下界>0。目标不是已实现结论。

P2.1原提案及历史cost协议不改写。当前执行状态以本目录STATE.json为准。

## 最新比较要求

逐张新图以Liu作者原法的完整可行输出`R_Liu`作为共同路线锚点。每个候选必须单图满足`C <= C_Liu + 1e-7`（epsilon=0），并在相同6s/12s路线改进墙钟下比较`M_return`。最终要支持RL贡献，RL还须优于冻结的最强同目标非RL；只胜作者cost目标的原始输出不够。`M_return`与官方`Check.calculateLatestTime`同定义，不称新指标首创。固定部署与目标归属实验仅支持条件路线主张；若要声称整个TSALNS系统端到端领先，需独立同总墙钟E协议。

|Gate|本轮状态|后续验收|
|---|---|---|
|G0|A问题获批；product信用与阈值条件策略均经独立交叉审查NO-GO，尚无新机制|继续筛查一个具体、可证伪且不被最近先例覆盖的物理路线机制|
|G1|独立scorer/global物理env/deadline交付已实现；37+15+8及独立9动态+15 scorer测试、隔离回滚通过|合成工程契约已通过；一般策略失败率、真实地图质量及批处理性能仍未知|
|G2|独立数据协议审计完成；root尚未冻结；新图未生成|使用公开描述的constraint-reconstructed生成器，明确几何和spacing规则、暴露身份清单、作者锚点及失败分母，冻结48机会图|
|G3|对照族已审计，代码实现与质量运行未做|作者loadBalance、cheap平衡、同目标joint minmax、threshold可行性、适用matheuristic；从同一个R_Liu出发、同预算同cost cap|
|G4|未开始|另审训练包；至少3独立seed；普通同目标RL及学习/非学习强控制；全部seed、失败、开销及双预算门槛|
|G5|未开始|方法/模型/所有确认对照/数据生成器/预算/统计族全冻后才开放新Formal|
|G6|未开始|预登记机制消融、RL额外贡献、无后处理/公平后处理及独立完整解复核|
|G7|未开始|通过新颖性、RL胜强非RL、Formal和消融后才写正文|
|G8|未开始|干净环境完整研究包与投稿就绪验收；不含公开或投稿|

## 数据与资源

第一包48新机会/开发+最多24隔离非RL校准/验证图、科学非RL总16 CPU核小时。旧24图、旧Stage A、作者1200保存运行始终为已暴露历史；本轮未把任何旧图改称新开发或Formal。G4训练预算另审，旧30分钟自动任务仍暂停。

## G4设计底座与待决事项

- 物理actor对(slot,target)及(slot,RETURN)打分，输入remaining、位置、trip能量/时长、累计duty、全图成本余额/必要下界和当前全图时钟；station调度由固定程序完成。attention/slot-node decoder只是标准底座。
- 当前新代码仅完成环境与评价，不是新模型或新训练器。旧source_snapshot/route_rl/train.py仍优化旧cost/旧任务域，不能直接当A方案训练成果。
- 成功完整轨迹reward与全图M对账；deadend/超cap/超时的部分回报不能当成功终局。训练前另冻失败终止/惩罚、合法mask、归一化和checkpoint选择规则。
- 动态跨站预算策略与独立站product采样是不同分布；后者公式不得用于前者。product估计器作为新算法已关闭。
- 普通同目标RL、BC/beam、同池阈值组合器均要公平获得同信息、mask、初始化及候选生成/校验资源；所有训练失败也计总预算。
- 未通过G0–G3、未登记对称训练资源前，不启动72小时等训练矩阵。至少3seed是最低复本要求，不是稳定性或必胜保证。

## 复用接手提示

```text
先读AGENTS、USER_RESEARCH_REQUIREMENTS、LATEST_STATUS，再读return_makespan/STATE.json、ROUND_DECISION.md和EVIDENCE_INDEX.json。
当前用户已批准A第一包；固定部署/站型/target-station，RL只输出物理slot-target/RETURN。
主目标全图返航M、完整成本epsilon0、D条件6s/12s，5%是待检验目标。
复用V6/semfix及历史失败；新global_env/scorer/delivery有60项执行检查和隔离回滚证据。
product信用已被通用原式直接覆盖，保留参考但不改名复活。G1独立最终动态签认已通过（9项动态+15项scorer）。G0阈值机制经三方交叉NO-GO；G2/G3独立协议审计已出，root冻结前不开质量地图。新图标为constraint-reconstructed，不称精确复现；逐图作者锚点成本cap与同目标强非RL比较按本计划执行。
G4训练另审，Formal全冻结后才生成。
不把工程、oracle、候选组合、旧图或回退后的可行性冒充RL优势。
```
