# 固定风 G3 与后续实验：下一次可运行协议

日期：2026-11-14。状态：静态协议；没有新科学运行。本文只供 root 冻结下一份 intent，不修改两份科学 STATE、不扩科学人口、不代替新增资源授权。科研、训练、作者求解与质量评价均只在 <COMPUTE_HOST>；root 独占调度。当前多 Agent 模型覆盖为 GPT-6.1-Sol / xhigh。

## 1. 先给执行结论

1. **眼下有一个真实、局部且值得立即修的 G3 工程缺口：共同 H 生成器没有消费全图剩余 deadline。** 外层正确 kill 晚退进程，只能证明失败被诚实记录，不能证明该强控制在完整 6/12s 下有效利用预算。下一 intent 只补这条时间线，复用已有物理与交付验收，不重跑旧首尾小例或旧失败批。
2. **G3 的后继才是 RL 训练/开发胜出和 Formal。** G3 要建立新风域作者锚点、强 nonRL、完整交付/失败分母及可冻结的公平比较协议；不要求先出现 RL 胜出、创新消融阳性或新 Formal。G0 是研究新算法的独立立项门，当前项目合同仍要求 G0 与 G3 都满足才开新科学训练；不要把 G4/G5 倒置成 G3 资格。
3. **现有边界内没有可直接开跑的科学 TRAIN 包。** 原账为作者 40/48（余 8）、校准/验证 24/24、科学 nonRL 16 核时（7.5 已预约、8.5 未分配），且 `quota_reallocation_authorized=false`、G4 训练另审。新 TRAIN/VAL、把 8 次改名 G3 或 TRAIN、给校准另起名称，均不能自动绕过该账。现在可做新工程和 TRAIN-ready 静态冻结；不做 optimizer 更新、模型导入、checkpoint 或质量调用。
4. **24 底图 ×17 风只是尚未冻结的草案，并非用户硬性指定的人口。** 原建议“先1底图×17风”核心上界9.01h，却只有1个独立地图cluster，主要是耗时探针，信息效率不适合作为首选科学G3。建议在生成新图前提交一份明确的比较域修订：12 family×2全新底图×预定3风（0、4m/s向E、8m/s向N），两强控制各3个运行seed，完整作者1800s强度保持，核心38.16h、独立新票据42h；完整17风改列后续鲁棒性。该方案须审查/冻结后才执行，不改旧人口、额度、门槛或历史结果。

## 2. 已有证据复用与真正剩余资格

|事项|目前事实|仍需什么，不能混为已通过|
|---|---|---|
|原强 min-max ALNS|20261112 已在旧开发/确认图建立真实新趟划分与完整成本 cap 的强控制；旧结果与中断/缺行保留|旧 48 底图全暴露；不能称新 DEV、G3 新人口或 Formal|
|恒风感知|`ConstantWindCtx`/heading scorer 接线已核；闭趟对称有效长度与原逐边风 scorer 一致|无需重做风格点正确性测试，更不能以“ALNS 不懂风”偷换弱基线|
|实际作者 → 强 ALNS|20261113 两份真实完整作者输出已接修后 43 文件包，2/2 admissible；0.6s 工程预算|不是完整 6/12s 科学质量或新风域一般资格；不重跑两例|
|共同 H +全图 cap|两新手写几何、174 条 bank 记录及补偿/typed/晚退工程已通|原控制没有全图 deadline 传递；科学规模效率与完整 H 调度尚未资格|
|作者完整性|完整 Main/最终 recorder 修复已有单独证据|新 map-wind 上仍需实际完整原强度 Rw、独立 scorer、失败全入分母|
|G3 新风域|未过|冻结全新底图身份、完整作者/强 nonRL 和同组件协议；按时退出+独立验收；冻结部署基线选择；所有尝试/失败/原始输出/完整费用入账|
|G0 新算法|未过，旧候选关闭|一个具体、可证伪的物理路线构造/学习更新差分；不能用普通 deadline 接线修复充算法新意|

G3 资格判定只检查其本阶段注册的条件：共同作者锚点完整合格；强基线搜索域保留；在完整同墙钟下真实交付；域、信息、成本、人口和失败分母一致；新人口上获得可解释的 nonRL 机会与可靠性记录。若完全没有相对强 nonRL 的剩余空间，应如实缩限/关闭该研究假说，不以降低基线强度制造空间。**不把“新机制 RL 已经胜出”列作 G3 通过条件，也不强制先发明一个新 nonRL 算子。**

## 3. 下一次立即可运行 intent：共同 H 的全图 deadline

### 精确接点（都先复制到 root 新事务目录，不改旧证据）

基目录：`<LOCAL_PATH>`。

|文件 / 函数|原代码观察|最小所需变化|
|---|---|---|
|`MODIFIED_FILE/independent_h.py::generate`|逐站调用 `search_station`，末尾才 `combine_at_H`；没有全图时钟参数|接收同一次 launcher 的 `started_at` 与全图 `budget_s`，只派生一个绝对搜索截止时刻；各站共用，不能每站重置|
|`MODIFIED_FILE/independent_h.py::search_station`|当前显式 `alns.Budget(perf_counter(), 600.0, perf_counter)`|删除每站 600s 新时钟；复用全图剩余搜索时间，既有 makers/ruin 仍按原物理搜索域工作；站间结束、长循环边界查剩余时间|
|`MODIFIED_FILE/independent_h.py::combine_at_H`|组合全 bank 后完整评分；成本补偿允许局部超 anchor|在原全图 cap/typed/覆盖/累计 duty/公共 T 不变下，保证最终完整组合、原 scorer、序列化有预留；过期不能声称 ONTIME|
|`validation/worker.py::main`|从 `ROUTE_DELIVERY_STARTED` 只写 ready 时间，`generate` 并未接收；worker 现无 `--budget`|将 launcher 起点与明确的总 budget 传给 generate；不能在 import/解析后另起钟；保留 payload/身份/原始输出|
|`validation/run.py::delivery_checks` 与后续科学 driver 的 command_factory|当前 worker 命令仅 bundle/result/延迟；实际 `route_delivery.run(...method='common_h', command_factory=...)`|命令明确传 budget；复用已有外层观察器；全图 budget 起点仍在 `route_delivery.run` 入口|
|`frozen/route_delivery.py::run`|已有输入、启动、真正退出、独立二次验收全计时，失败 ITT anchor|原则上复用，不扩大改动；读取其实际 `process_wall_s`、`admission_wall_s` 与 exit，不能仅看 saved 输出|

重要区别：`frozen/route_method.py` 的 CLI `--method strong_bank` 是 ALNS 后接 station-bank，不等于这里的独立共同 H 控制；不要把它更名当共同 H。共同 H 目前必须经已验证的 `command_factory` 调用 `validation/worker.py`。已有强 ALNS `constant_wind_adapter.solve(..., budget_s, started_at=t0, seed=...)` 可作同一绝对时间线接线的参考，但不改其算法或借给它缩减搜索域。

### 只测新增时间线的必要反例

1. **多站重置反例：**一份新手写多站 fixture，让首站已消耗绝大部分搜索时间，后站仍有候选。修改版各站看到同一绝对截止；总搜索时间不能变成 `站数×budget`，旧每站 600s 行为被明确识别。候选、H、seed、站序不按结果调整。
2. **启动计时反例：**将固定消耗放在 worker 解析/导入/生成前；剩余时间必须相应减少。不能以进入 generate 的时刻洗掉启动成本。
3. **最终化反例：**搜索刚接近截止时仍需完整组合、原 scorer 与 durable 输出。过晚原始有效路线保留，但拒绝 ONTIME，并按已有规则记 ITT anchor；不以“在 deadline 前发现了好解”替代退出与验收。
4. **终止反例：**剩余≤0、closed 站、空候选/无 H 见证、内部异常都及时返回诚实状态；无见证保持 `UNKNOWN/NO_BANK_WITNESS`，不改为物理 UNSAT。银行已有完整 anchor 可回退，策略生成失败仍保留。
5. **公平与不变性：**不改 makers、ruin、typed 资格、公共 T、浮点 cap、H、轮数或评估上限以“变快”；用新有限 trace 核对相同 deadline 前已做调用顺序，完整最终路线继续由原 scorer 验收。时间预留是实现参数，在科学人口开放前冻结；不是从科学效果反推。

本轮 root 已指定 **30 CPU 秒 / 60 墙钟秒的纯假钟单元验证**；它覆盖上面新增时间线控制流，绝不等同实际6/12s物理/质量资格。按该决定，intent骨架为：

```json
{
  "purpose": "COMMON_H_WHOLE_MAP_DEADLINE_FAKE_CLOCK_UNIT_ONLY",
  "host": "<COMPUTE_HOST>",
  "owner": "root",
  "phases": ["BASELINE", "MODIFIED", "AUDIT", "ROLLBACK_OTHER_COPY"],
  "new_handwritten_fixtures_max": 0,
  "clock": "injected deterministic fake clock",
  "simulated_budget_values_seconds": [6, 12],
  "real_6_12s_physical_runs": 0,
  "new_scientific_maps": 0,
  "author_calls": 0,
  "full_ALNS_quality_calls": 0,
  "training_updates": 0,
  "checkpoint_writes": 0,
  "cpu_threads": 1,
  "child_cpu_seconds_hard_cap": 30,
  "whole_intent_wall_seconds_hard_cap": 60,
  "successful_timing_reruns": 0,
  "source_repair_cap": 0,
  "unexpected_failure": "retain originals and stop; do not reopen old failed batch",
  "pass_scope": "fake-clock deadline propagation/control-flow only; not actual 6/12s physical qualification, G0, or G3 scientific pass"
}
```

30/60s 是本轮新intent的硬上限，不挪用旧工程包已耗完的phase/repair，也不授予训练预算。本轮仅用假时钟确定性trace验证跨站共享截止、启动收费、终止与最终化；不做实际物理求解、不运行6/12s科学配置。实际全图物理6/12s资格仍待后续独立冻结的科学/必要接线验证证据，不能把假钟推进6或12个单位称作真实秒数性能。不复跑旧17风物理矩阵、旧共同H八配置、旧晚退或作者首尾验收。

H 的科学调度（例如共同 H 阈值列表及搜索顺序）须另外在新人口开放前冻结；此次只传递全图 deadline，不把新的 H 网格搜索扩入本工程，不把单个手写 `anchor_M×0.9`直接当全域最强 H 配置。

## 4. 原边界内的 TRAIN-ready 工作与准入顺序

可以立即交付而不启动新科学训练的内容：新候选的六项 G0 规格/最近先例差分；同组件标准 RL、BC、无学习与核心消融的精确接口；TRAIN/VAL/一次 DEV/Formal 的 namespace 和暴露排除规则；优化器/归一化/完整终局奖励/失败罚则/teacher 成本/checkpoint 选择规则；学习曲线与训练充分性停止规则；driver 的静态入口/参数/hash 检查。它们是资格准备，不记作训练成果。

依赖链是：

```text
当前假钟 deadline 单元 ──> 共同 H 时间线控制流有限资格（非实际6/12s物理资格）
G0 具体新算法立项 ──────> 新候选实现/同组件控制规格
新 G3 人口与资源冻结 ──> 完整作者 + 强 ALNS + 共同 H 的资格/机会
上述 G0、G3 + 新训练资源冻结 ──> ≥3独立seed 的 TRAIN/VAL
模型/解码/统计全冻结 ──> 一次 DEV ──> 全新 Formal 与最终消融
```

G0 可以和只读 G3 协议工作并行；共同 H 的工程正确性不依赖 RL。按当前项目合同，不以普通 RL 试训绕 G0/G3，不把没有训练的标准 RL 代码存在当 G4 通过。新 Formal 不参与 baseline、checkpoint 或阈值选择。

## 5. 资源复核：24独立底图优先，17风可移至后续鲁棒性

### 5.1 两个事前方案的比较域与门槛

24底图（12既定family×2全新底图）与17风网格都是**未冻结实验草案**；现有用户批准的是固定风A、完整同风作者成本cap与物理动作/预算边界，没有把24×17指定为不可修订的硬人口。17风源包的情景定义和资源算术保留为原版本；本节提出可供用户审查的替代新协议，不能直接覆盖旧冻结记录或在看新数据后修改风层。

|方案|预先固定情景|估计目标与权重|G3门槛保持|科学结论边界|
|---|---|---|---|---|
|F17：24底图×完整17风|0；2/4/6/8m/s各E/N/W/S|每底图先四方向等权，再五风速等级等权|完整作者/同风cap、强ALNS及共同H原生能力、完整6/12s退出验收、全部ITT；不要求先RL或Formal|可做登记17场风域的资格/机会描述；n仍为24底图，不是408|
|F3：24底图×预定3风|`w=(0,0)`、`w=(240,0)`、`w=(0,480)` m/min，即0、4m/s向E、8m/s向N|每底图三情景各1/3，再family等权；各情景独立完整报告|完全相同的物理/强度/预算/失败门槛；仅比较域事前缩限，绝不降作者或ALNS强度|只对这三个固定场景及原几何分布资格；不能外推任意方向/全17风，也不能分离风速、方向主效应或交互|

F3不是F17总体均值的无偏抽样近似，而是**不同、明确更窄的estimand**。三风不是按新实验结果选出的有利子集：必须在生成24底图前把上述向量、权重、全部方法和统计族一并冻结。零风是同域控制，中/强风是预定物理压力；不能把4E或8N事后换成RL更好的方向。全17风若后续用于鲁棒性，应另立全新底图或清楚标成已暴露G3底图的补充描述，不能因此把同一24底图改称新Formal。

三风与17风下，作者仍 `outer_iterations=500`、`alns_iterations=5000`、每map-wind完整1800s timeout；强ALNS和共同H仍完整独立6/12s调用，不把12s中间值充6s，不以压缩候选池/每站预算弱化对手。确定性作者/整趟重排B2不为凑seed重跑。每行cap仍是其自身完整同风作者 `Cw(Rw)+1e-7`，不是旧零风数值。

### 5.2 核心预算：完整作者不变，仅改变预定风域/运行复本数

以下是单线程进程时间上界换算，不是实际CPU使用、价格、已批资源或已测耗时。两控制固定为强min-max ALNS和独立共同H；作者一行只需一次完整锚点。

|人口/运行复本|作者行及上界|两控制调用数（含两个deadline）|两控制核心小时|合计核心小时|
|---|---:|---:|---:|---:|
|旧建议：1底图×17风，各3seed|17行；8.5h|204|0.51h|9.01h；独立底图仅1，不作主G3推荐|
|F17：24×17，各3seed|408行；204h|4896|12.24h|**216.24h**|
|F17：24×17，各10seed|408行；204h|16320|40.8h|**244.8h**|
|F3：24×3，各3seed|72行；36h|864|2.16h|**38.16h**|
|F3：24×3，各10seed|72行；36h|2880|7.2h|**43.20h**|

公式：作者=`24×风数×1800/3600`；两控制=`24×风数×seed数×2方法×(6+12)/3600`。同运行seed数下，F3是F17核心上界的3/17，减少82.35%，而独立地图cluster仍为24。与1底图×17风相比，F3各3seed核心多29.15h，却能覆盖全部12family、获得24个独立几何cluster，适合G3资格的跨图信息目标。这个信息效率判断针对地图异质性；不表示三风覆盖了全风域。

3与10个是**nonRL运行seed**，不是RL独立训练seed；3seed只降低随机求解噪声估计的精度，不降低每次作者/ALNS搜索强度。10seed原本也是建议而非用户硬性指定，不能将其伪装成不可调整门槛。F3若事前选3seed，后续不得看效果再挑追加seed来救结果；要扩至10，必须在新结果前登记固定追加7seed或明确仅为精度复核且保留全体。

### 5.3 推荐用户审查的最小完整G3票据：F3 / 42h

```json
{
  "status": "PROPOSED_FOR_REVIEW_NOT_AUTHORIZED",
  "domain": "S_const_three_prespecified_winds_only",
  "base_maps": 24,
  "family_count": 12,
  "new_maps_per_family": 2,
  "wind_vectors_m_per_min": [[0, 0], [240, 0], [0, 480]],
  "within_map_wind_weights": [0.3333333333333333, 0.3333333333333333, 0.3333333333333333],
  "map_wind_identities": 72,
  "author": {"attempt_cap_new_pool": 72, "outer_iterations": 500, "alns_iterations": 5000, "timeout_seconds_each": 1800},
  "nonrl_methods": ["strong_minmax_ALNS", "common_H_independent_generation"],
  "nonrl_run_seeds_each": 3,
  "whole_process_deadlines_seconds": [6, 12],
  "nonrl_launches_registered": 864,
  "core_single_thread_process_hours_upper_bound": 38.16,
  "preparation_and_independent_audit_hours_reserve": 3.84,
  "new_ticket_total_hours_hard_cap": 42,
  "legacy_author_40_of_48_and_calibration_24_of_24": "unchanged",
  "legacy_7_5_reserved_and_8_5_unallocated_hours": "unchanged",
  "new_RL_training_or_checkpoint": 0,
  "new_Formal": 0,
  "unexpected_failure": "retain all registered rows and stop when hard cap/implementation failure requires; no replacement maps, no seed rescue"
}
```

这是**独立新增72作者尝试/24底图/42h票据**，保留旧48人口/作者额度、余8次、原7.5h预约及8.5h未分配余额；不改旧满额校准身份。所有失败消耗相应尝试与实际时间，不退款。3.84h储备用于准备、整趟重排记录、完整解独立复核与收据，不是免费重跑成功时限/隐藏搜索；若储备不足，停止并按实收据申请，不能偷支旧余额。42h只覆盖这份G3最小资格票据，不覆盖训练、teacher、BC/RL、VAL、DEV、Formal、额外新基线或存储无限增长。

该票据的执行前提是新比较域/人口/暴露排除/配置与账务修订获准、项目合同所需G0条件满足、共同H时间线的新单元与必要实际接线准备完成、<REMOVED_ENDPOINT>当前cgroup/进程/持久卷核查；不要求RL、消融或Formal先通过。本轮纯假钟PASS不能填成864行实际6/12s资格PASS。若希望一开始保留10个nonRL运行seed，票据改为核心43.2h+4.8h储备=**48h**；这是比最小票据多6h的明确选择，不得事后无记录追加。

AACO若在冻结前被独立审查纳入，F3三seed另加 `72×3×18/3600=1.08h`（10seed为3.6h）；F17十seed另加20.4h，总265.2h。候选组件无学习B4若不等价共同H，也必须单列，不能藏在“两控制”费用里。是否纳入须在新人口开放前确定，不能用Formal或暴露G3排名挑对手。

### 5.4 科学精度与停止口径

F3的72行只有24个独立底图；各family只有2底图，不能支持可靠的family内细分效应/复杂交互推断。三个固定风不是独立几何样本，3个搜索seed也不能把n从24放大。24底图适合建立G3完整作者/强nonRL资格、地图级机会和方差估计，**不事先承诺5%或0.3%效应的检验功效，也不等于Formal样本量充分**。一次单底图17风连跨地图方差都无法估计，因此取消它作为优先科学阶段的推荐，保留其9.01h算术仅作备选耗时探针。

G3按预登记全部72作者锚点、864强控制调用与独立可行/真实交付状态报告；完整可靠性要求与失败处理不因三风缩限降低。有缺锚点或未按时交付，保留ITT/原始输出，不删失败后宣布完整资格；不把某个nonRL平均改善需达5%强塞为新的G3门槛。RL双预算效应、作者/强nonRL优越、充分训练、机制消融和全新Formal是后继独立门槛。若F3仅支持“这三场景资格成立”，G3结论只写该范围；完整17风的一般化主张仍未通过。

资源上界仍以完整1800s作者计，真实耗时低于上界只形成结余收据，不能自动放大人口或启动后续训练。若需要新增付费，票据必须补机型/单价/账户余额/金额封顶后获确认；当前只提出核时与尝试上限，不推定任意付费授权。

## 6. 训练与效果协议：充分性不等于只跑三个 seed

**必需训练组：**候选机制 RL、同组件标准直接 route-RL、同组件 BC、去掉唯一新步骤的核心消融。若核心消融与标准 RL 数学及实现完全相同，事前声明同一组，复用而不重复跑。另保留候选组件＋无学习 B4；它有在线搜索成本，没有假训练 seed。主强 ALNS 仍保留其完整原生搜索域，不强迫它采用 RL 的受限候选池。

每个学习组至少 **3 个从头独立训练 seed**，包括初始化、TRAIN采样和优化随机性；全部模型入账，不选幸运 seed。clustered 主域与 **uniform 独立重训**各自建立独立 TRAIN/VAL namespace；完整四组时最低是 `4×3×2=24` 次训练，而不是一个 checkpoint 换均匀测试集就叫 uniform 训练。zero-shot 跨分布另表，fine-tune 另namespace/预算，均不混入主Formal。

训练票据按组/分布/seed明确：最大环境 transition、完整轨迹、optimizer更新、CPU/GPU墙钟、教师求解和数据生成、VAL次数、存储、失败预算。现在没有实测每步代价，所以不捏造“足够训练只需若干GPU小时”。先在**获准的新 TRAIN**做一次固定的资源剖面/短学习曲线，再用预冻结规则确定完整上限；不能在旧 DEV 上调。候选与标准 RL 对齐网络/特征/mask/数据、实际训练计算及在线解码；BC 教师只来自 TRAIN且费用计入。更新数、轨迹数与实际时间三者同时报告，不把更贵完成器藏在相同步数里。

充分性至少同时检查：完整终局可行率；TRAIN与VAL目标曲线/预定末窗变化；对BC初始化与标准RL的增量；全部seed的波动；预算耗尽时是否仍显著改善。若到硬上限仍在快速学习，结论是预算下未收敛，不能宣称“RL无效”；但不因结果不好自动加训。若需扩预算，按事前TRAIN/VAL规则申请一次具体增量，所有前失败保留。DEV/Formal永不用于延长训练或选checkpoint。

raw actor 与公共后处理两列都保存。相同新组件/完成器/公共 T/候选生成/独立验收交给BC、标准RL、无学习和核心消融；所有在线费用计入6/12s。若新机制只改训练估计，则部署decoder与后处理保持同一；若改变完成器，增加仅事后用完成器的对照。强ALNS不因这些配对受限。

## 7. 完整 ITT、统计与全新 Formal

注册单元是底图×风×方法×真实运行seed×deadline；推断底图cluster与独立训练seed，绝不按风行或测试输出数膨胀n。F17每底图先对四个非零方向等权，再五个风速等级等权，零风只一次；F3按预定三情景各1/3。二者不能混用或称同一个总体。按family预定等权/既定权重汇总，保留同图全部风；训练seed作为整列移动。科学分析只在<REMOVED_ENDPOINT>进行，bootstrap次数、seed、CI及多重比较族在开放数据前冻结。

所有作者失败、anchor不可用、启动异常、超时/OOM、漏目标、cap/energy/duty违规、晚退、fallback全部入注册分母。已有 `route_delivery` 对未按时交付的方法记录ITT anchor，是**虚拟无改进编码**，不能据此说方法真实按时交付；按时合法原始策略、按时真实fallback和虚拟anchor三项分列。共同作者anchor失败时，保留整块失败率和未定义的配对质量，不悄悄删行后宣称全批合格；不更换地图补齐好样本。

比较主项同时包括作者Rw、成本中性重排B2、冻结部署最强nonRL、同组件BC/标准RL/无学习/核心消融。最强nonRL可在G3资格阶段按注册聚合规则选，进入DEV前冻结；不能在Formal逐图取最优再把oracle称部署方法。报告相对每一强控制的全部配对效应，不能只报有利一个。

既有作者5%目标、完整双预算要求保持；原G4完整目标0.3%门槛与新A方案阈值的适用关系须root在新意图冻结时逐项写清，**本协议不悄悄改掉任何既有门槛**。同时要求相对冻结强nonRL的有效增量、独立95%CI/预定校正、完整可靠性。valid-only只是补充；小图平局保留；不得按新效果挑大图或风层。

Formal 仍用全新底图，旧48、旧1200、已暴露DEV、任何工程fixture与新TRAIN/VAL/G3全部排除。候选240底图×17风=4080行是原草案，人口/风域都尚未冻结；不能误称4080独立地图，也不能由本G3票据直接锁定Formal。最终数量与主风域须在新DEV后、开放Formal前用注册效应/方差与功效或精度标准决定并留版本；若预算不够，缩限实际主张并重新事前评审，不能只减样本后宣称原检验仍充分。若采用F3为主，17风另列鲁棒性，二者预定报告且不互相充当新Formal。作者/强nonRL、全部训练seed与核心消融、uniform独立重训的评价费用逐项列，Formal费用另审。

## 8. 给 root 的下一步清单与完成口径

最先做：复制共同H最小源范围 → 冻结全图deadline的新intent → <COMPUTE_HOST> **30CPU/60wall纯假钟单元验证** → 留原失败/差分/独立副本回滚证据。这个修复不扩大科学人口，也不需要RL或Formal先过；完成口径只写控制流有限资格，不写完整6/12s物理资格。

然后做：完成仍未获准的具体G0差分，与G3冻结工作并行；提交F3与F17的事前范围/精度/资源比较，推荐**24全新底图×3预定风、72新作者身份、两强控制各3seed、42h独立新增票据**供用户审查，旧人口/额度不动。获准并冻结后才生成/运行该人口；无需先有RL或Formal。不能把本协议或假钟工程PASS写成G3科学PASS。后续训练只有在G0/G3与独立新资源完成后开；至少3独立训练seed、同组件、uniform重训、完整ITT及全新Formal是后续实质工作，不是已完成状态。

### 核对来源（本地只读）

- `AGENTS.md` 当前2026-11-14覆盖；`LATEST_STATUS.md` 前80行。
- `USER_RESEARCH_REQUIREMENTS.md`、`RESEARCH_PLAN_ROUTE_RL.md`，特别是G0–G8原条款与A固定风覆盖。
- `route_rl_research/20261103/return_makespan/EXECUTION_PLAN.md`、`STATE.json`（作者40/48、24/24、quota_reallocation=false、训练另审）。
- `joint_weather_emergency/20261114_fixed_wind_matrix_resource_v2/REPORT_ZH.md`、`RESOURCE_ESTIMATE.json`、`MODIFIED_FILE/EXPERIMENT_MATRIX_DRAFT.md`。
- `joint_weather_emergency/20261112_takeover_completion/STRONG_NONRL_REPORT.md`。
- `joint_weather_emergency/20261113_author_strong_chain_v1/REPORT_ZH.md`、`NEXT_BOUNDED_WORK.md`。
- `joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/REPORT_ZH.md`、`MODIFIED_FILE/independent_h.py`、`validation/worker.py`、`validation/run.py`、`frozen/route_delivery.py`、`frozen/route_method.py`。

本次及本次资源复核仅编辑本协议文件；没有生成/运行地图、远端实验、科学评分、代码修改、旧数据重评或STATE变更。第5节为供审查的新方案，不是已冻结事实或授权。
