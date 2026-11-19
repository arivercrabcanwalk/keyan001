# 目标证据独立审计

**日期：** 2026-11-04（Asia/Shanghai）  
**性质：** 只读证据审计；未新增检索、地图、求解、训练、远端作业或代码修改。  
**审计基线：** 已读取项目有效要求、主计划、最新状态、`return_makespan/STATE.json`、G23 协议/作者 runner、G24 协议/文献和实现审计、现有 smoke 结果与 Windows 复核。

## 结论

当前最能服务于目标的场景选择是**已预报、预先公布的日内临时禁飞区（可同时带已知分段风）**，而不是紧急到达任务或周期任务。这个选择保持策略的物理动作为 `(slot, target)` / `(slot, RETURN)`，不改变固定站点、站型和 target-station 归属；它是受限环境扩展，**不是**新颖性主张。

现有 G24 已有多站固定外层、LD/SD 槽、`M_return`、物理 mask、双 weather replay 及 PPO/A2C 工程烟雾的实现证据，但没有任何作者地图比较、注册质量运行、强非 RL 对照或 Windows 执行结果。它不能支持“RL 优于作者”“PPO 优于 A2C”“天气不确定性有效”或投稿级结论。

## 用户目标逐项审计

| 用户要求 | 已证事实 | 缺失或矛盾 | 最直接的下一动作 |
|---|---|---|---|
| 充分阅读本地相关论文并大量线上论文 | 工作区有 **42 份内容唯一 PDF**。G24 的逐篇审计明确核验了 Liu 正文/补充、DPTARL、风能耗 CVaR、无人机多趟能耗等；在线一手来源审计已读取天气时间窗、定时 NFZ、NFZ 路由和 PPO/A2C 原始来源。 | 这不是“本地全部决策相关论文均已完成变量级阅读”。`related_work/fulltext_comparison_20261102.md` 仍把 Cai 2025、ESWA 2026、RESS 2026、TRE 2026、RLHEA 2024、Q-HGALNS 2026 等列为 F2（题名/摘要级，缺全文）。现有 42 篇中没有一篇构成“LRPHSD + 已知风 + 临时 NFZ + 直接路线 RL + 作者级比较”的直接先例或完整对照。 | 在任何新颖性或论文主张前，建立版本/哈希、问题变量、动作、信息、约束、目标、对照和实验域的全文矩阵。F2 项只能保留正面题名/摘要事实，不能用缺失正文推断其没有某机制。 |
| 选择天气/风速场景适配 | `weather_full_map.py` 对固定外层的 LD/SD 并行槽构造物理 `(station, slot, target|RETURN)`；风为已知时间分段向量，航段跨 knot 精确积分。`weather_replay.py` 另有积分、几何和路径枚举实现。 | 代码不是随机天气、预报误差、空间风场、阵风、风致功率、实机能耗或风险约束。若称“weather uncertainty”，当前 mask 使用完整真实日程而 observation/信息协议必须先冻结，否则信息口径不一致。 | 把 V1 明确冻结为 `deterministic full forecast`。所有策略、非 RL 和 validator 读取同一 forecast hash；真实扰动/POMDP 仅作为后续独立分支。 |
| 在紧急/周期/临时禁飞区中选择合适扩展 | 临时 NFZ 只改变现有腿在当前出发时刻的可行性/时耗，能进入同一 `target/RETURN` mask 和公共 oracle。Liu 已将风/NFZ列为可扩展限制；已有定时 NFZ 文献也表明该类建模并非空白。 | 紧急到达改变 target 集、release time、优先级、截止期、取消/抢占、在线信息和分母；周期任务引入跨日频率、任务重现与每日 sortie 语义。DPTARL 的周期固定巢模型不能替代本问题。三类不能合并为一个实验因子并归因给路线 RL。 | 只冻结临时 NFZ V1：一个调用方缓冲的严格凸区、半开活跃窗、无 WAIT、全部任务 `t=0` 已知。紧急和周期分别登记为新问题，至少需专用状态、目标、强非 RL rolling 控制和独立 evaluator。 |
| 对比 PPO/A2C 等直接物理路线 RL | G24 的 PPO/A2C 共用 pointer backbone、固定 forecast state、物理 action 列表和合法 mask；旧 Route-RL PPO Stage A 的负结果已保留。 | 现有 G24 仅五目标 synthetic smoke。严格 V3 report 的 PPO `M_return` 为 6.682738/7.045658/6.727936 min，A2C 为同组三值；report scope 明确是 synthetic engineering fixture，而非作者图、注册或 Formal。没有公平墙钟、checkpoint 规则、地图样本或强非 RL。 | G4 前将 PPO 与 A2C 都列为普通 direct-route 控制，不预选赢家：相同模型/信息/mask/训练分布，至少 3 训练 seed，预注册 checkpoint 聚合，全部失败和训练/推理成本入账。 |
| 最后在 Windows 跑实验对照作者 | 已有 Windows runbook；本机 synthetic tests 与 smoke 已留环境/source manifest，作者 J1b/J2b Java profile 已各编译 20 classes，J1b 在永久排除的合成夹具端到端 smoke 通过双 scorer 对账。 | Windows reverse tunnel 被拒、LAN mDNS 不可解析，Windows Python/PyTorch/CUDA/项目树均未核验。当前 smoke 没有 Liu map、作者输出或强 non-RL。Windows 不是当前新图为零的唯一原因，但它是用户所要求的最终平台复验缺口。 | 连接恢复后，先执行冻结 CPU 环境的完整单元测试和 synthetic smoke，留存 stdout/stderr、6 checkpoints、环境/源码 manifest 和严格 reload；之后才在已冻结的真实新图协议上执行作者和所有对照。 |

## 本地与线上文献完整性

### 已有可用证据

1. `audit/papers/Liu2026.pdf` 与 supplement 说明基础 LRPHSD 的静态弧时间、站点/站型/归属、多趟、返航、能量和 duty；`M_return` 同作者 `Check.calculateLatestTime` 语义一致，故不是新指标。
2. `audit/papers/DPTARL.pdf` 是直接 `target/RETURN`、可行性剪枝、A2C 的近邻先例；其周期固定巢、单域目标和实验数字均不可移作 LRPHSD 结果。
3. G24 既有在线一手来源记录已支持以下保守事实：预报风时间窗、定时 NFZ 绕行、NFZ UAV routing、周期巡检直接 RL、紧急 UAV rolling scheduling 都已有先例。它们排除了将动作、mask、PPO/A2C、风或 NFZ本身称作新颖性。

### 未完成的证据工作

1. 42 份本地 PDF 是内容清点，不等于 42 份均与当前问题等相关，也不等于每一篇均有可复核的变量级阅读记录。当前 G24 本地文献表只直接列入其中一部分；其余组合优化、MDP abstraction、LNS 和机制论文不能替代动态 UAV 域的完整比较。
2. 既有路线/LRP 近邻中多篇仍为 F2。尤其与固定巢混合巡检、可靠 nest location、分布式 RL dock-patrol、latency LRP 和 ALNS 相关的全文变量/动作比较没有关闭。
3. 对天气/空域分支，现有在线审计虽已足以否定“无人做过”，却没有生成“所有天气、NFZ、紧急和周期 UAV 文献”的穷尽性系统综述。当前工程不能把该审计包装成完整领域查新。

## 当前实现与主研究契约的对齐

### 已对齐

- RL 的可学习选择是物理路线动作；没有 operator、neighborhood、repair budget 或算法 ID。
- 多站 V1 固定 author anchor 的 station、station type 与 target owner；跨 station 的 action interleaving 不改变每个物理 slot 从 `t=0` 独立运行的含义。
- 完整候选通过原 LRPHSD scorer 及独立 weather replay。天气/几何 detour 是公共确定性 oracle 输出，不是 policy 选择路径搜索算法。
- 当前 V1 reward 以 `M_return` 势差对账，MTC 是次级报告；历史单站 `-MTC` smoke 已隔离，不能迁移成主目标结果。

### 仍与主目标不一致或未冻结

1. G24 strict smoke 的 reference 是五目标 `synthetic static-route anchor`，不是新开发图上的 `R_Liu`；不得称 author anchor。主研究要求逐图 `C(candidate) <= C_Liu + 1e-7`，并在相同 6s/12s route-improvement 预算下比较作者和最强同目标非 RL。
2. G24 另有 `weather_cost_cap`。主 D 研究的原始成本 cap 与天气域 cap 的关系尚未冻结。若作者静态路线在 scenario 下不 weather-feasible，直接将其写为 weather baseline 是无效的。必须预先二选一并如实限制主张：
   - `R_Liu^F`：将已保存 Liu 路线用公共 weather oracle 重放，只有可行者作为 no-op author comparator；或
   - `R_ref^F`：以 weather-aware 非学习可行参考定义天气条件比较。
   后者可支持受限 weather-domain 条件比较，不能声称未扩展 Liu 原算法端到端胜负。
3. 现有 V1 只支持完全已知、均匀分段风、一个严格凸 NFZ、无 WAIT。NFZ 解除后等待可飞的路线会被模型视作无合法动作，这是已声明模型边界，不是可以在 oracle 内暗中修复的细节。
4. `station_idx` 必须在最终 action/log schema 声明为 fixed target-owner/slot-state key，不能在图注或报告中称为 learned station selection。

## 为什么作者地图比较目前仍只有 synthetic

这不是作者实现完全不可用。`g23/author_baseline/author_runner.py` 已能用冻结 J1b/J2b profile 对单输入运行、记录 seed、完整 raw output、独立 evaluator 和 `M_return` scorer；Linux 上也已有编译与一个永久排除的合成夹具 smoke。

但研究级 author-map 对比尚未开始，原因按因果顺序为：

1. 主 `STATE.json` 记录 `new_development_maps=0`、`new_training_calls=0`、`new_formal_maps=0`，当前 gate 是 G2 V2 finite-grid audit/metric freeze pending。
2. 官方 120 个输入是已暴露预生成文件，作者 generator/seed 未获得。第一版整图拒绝采样在 `(3,20)` 与 `(10,110)` 家族不可执行；V2 sequential conditional sampler 虽获条件性审查，但 53-bit attempt-cap、失败分母、输出身份与 exclusion manifest 未冻结。因此没有合法的新研发图可送入作者 runner。
3. 对每张新图尚未冻结 author profile/seed namespace、`R_Liu` 保存格式、timeout 和 anchor witness；也尚未冻结同目标 joint min-max non-RL、threshold control、cheap controls 的实现与参数。
4. 6s/12s 的冷启动全开销 ledger、失败/fallback 规则、成对 map bootstrap 和比较族尚未成为 root freeze receipt。没有这些即使运行作者代码，也只能是未注册试运行。
5. Windows 当前不可达、依赖锁和项目部署封装不完备；这阻塞用户要求的 Windows 最终复现，但不应被误写为上面 G2/G3 数据与比较冻结尚未完成的替代原因。

## 优先执行序列

1. **冻结数据与估计量。** 完成 V2 sampler 的 finite-grid/attempt-cap 审计；冻结新 map/scenario identities、120 张官方图和旧 24 张图的 exclusion identity、失败分母、weather V1 schema、信息 hash，以及 `R_Liu^F` 或 `R_ref^F` 的唯一口径。
2. **冻结作者锚点与非 RL 对照。** 用已验证的 J1b runner 定义每张新图的 seed、profile、timeout、完整 witness 和 `C_Liu/M_return` receipt；实现并在不看 RL 结果前锁定 Liu-faithful load-balance、cheap physical controls、beam，以及 station-joint same-objective weather-aware non-RL。所有路线从同一 anchor 开始，计全部 construction/oracle/validation/fallback 开销。
3. **只做受限 G2/G3。** 在 48 新机会图和最多 24 隔离校准/验证图、16 CPU-core-hour 上限内，先确定该受限 temporary-NFZ 域是否仍有 `M_return` headroom，且逐图严格原始成本不劣。无 headroom 则关闭该分支，不以改变种子、参数或扩大旧图 cutoff 追求阳性。
4. **再决定是否进入 G4。** 只有有新机制、G2/G3 opportunity 和另行冻结的多 Agent 训练包时，运行 PPO/A2C 及 direct-route controls 的至少三 seed 比较。RL 必须同时击败 author/no-op anchor 与预先冻结的 strongest same-objective non-RL；任何 smoke 数值均不得进入该结论。
5. **完成 Windows 复验与 Formal。** Windows 恢复后按 runbook 做严格环境、源码、checkpoint 重载与 synthetic smoke 验证；方法、模型、统计和所有对照随后全冻结，才生成此前未暴露的 Formal 图。Windows smoke 本身不替代作者地图实验。

## 当前状态

用户已授权 G0--G8 的执行；本审计没有发现还需要由本地流程另行补发的用户授权。尚未通过的是可复核的科学门槛，而不是授权门槛：新机制未批准，G2/G3 未执行，G4 未启动，RL 优越性/创新/Formal/论文正文均为 false。

## 证据入口

- `USER_RESEARCH_REQUIREMENTS.md`
- `RESEARCH_PLAN_ROUTE_RL.md`
- `LATEST_STATUS.md`
- `route_rl_research/20261103/return_makespan/STATE.json`
- `route_rl_research/20261103/return_makespan/g23/nonrl_data_protocol/G23_PROTOCOL_AUDIT.md`
- `route_rl_research/20261103/return_makespan/g23/author_baseline/author_runner.py`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/DESIGN_AND_LITERATURE_AUDIT.md`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/LOCAL_LITERATURE_AUDIT.md`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/EXPERIMENT_PROTOCOL.md`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/POSTIMPLEMENTATION_SCIENCE_REVIEW.md`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/FULL_MAP_SMOKE_RESULTS_20261104.md`
- `route_rl_research/20261103/return_makespan/g24_weather_nfz/POSTIMPLEMENTATION_WINDOWS_REVIEW.md`
- `related_work/fulltext_comparison_20261102.md`
- `related_work/fulltext_retrieval_log_20261102.md`

