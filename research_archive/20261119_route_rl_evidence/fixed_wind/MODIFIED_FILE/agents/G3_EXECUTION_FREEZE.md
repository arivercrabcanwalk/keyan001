# F3-G3 可执行冻结设计：48 CPU核时、10运行seed

日期2026-11-14；状态 **STATIC_DESIGN_WITH_EXPLICIT_LAUNCH_BLOCKERS**。本文件冻结可事前确定的分配、比较域、种子、调度、强度、计时及停止规则；不宣称 driver 已能执行完整科研批次。仅编写本文件及同目录 `g3_driver.py`，没有生成地图、数值求解、远端运行或模型调用。当前 root 正在做全新 AIR2 完整链资格；原失败批保持原状态。G0/G3仍待实际证据。

本文工作区绝对前缀为 `/Users/USER/Documents/ChatGPT/lunwen/`；下述“相对路径”均明确相对该前缀。拟议远端新目录为 `/root/rivermind-data/lunwen_engineering/20261114_f3_g3_authorized_v1/`，创建/复用前须root在hn01核实，不沿用旧包运行目录。所有科学运行仅hn01、root串行调度。

## 1. 已有授权与本设计的边界

权威授权为 `joint_weather_emergency/20261114_f3_g3_authorized_v1/AUTHORIZATION.json`，SHA256 `0bc963d17f599835f8b740b315c43c20759a8cca517d4cca8100346c3c04efe8`，用户原话“批准新增 48 核时、10 个运行 seed（推荐）”。新池：24全新底图、12family各2图、每底图3固定风、72次完整作者尝试、两强控制各10运行seed/6与12秒，共2880控制行。CPU总量硬cap **172800秒**，核心工作155520秒（43.2h）、准备/独立复核储备17280秒（4.8h）。这不是任意新付费实例、训练、checkpoint、消融、Formal或旧额度重分配授权。

同风完整作者Rw定义每个单元的 `Cw(R)<=Cw(Rw)+1e-7`、epsilon0；目标 `min M_return`。共同station type/target-station均由该Rw确定并冻结，后续只允许物理 `(slot,target)/(slot,RETURN)`。完整覆盖、逐趟含返航电量、RETURN不清累计duty、机型与闭站资格全部保持。三风是本新G3的明确比较域，不改旧17风草案/历史结果，不外推全风域。

## 2. 24个分配ID与确定的元数据种子

namespace严格为 `f3-g3-20261114-authorized-v1`，partition使用现成generator合法值 `opportunity`，ordinal仅1、2。完整地图ID是 `namespace:opportunity:<sites>x<targets>:o<ordinal>`，如 `f3-g3-20261114-authorized-v1:opportunity:3x10:o1`；表内短ID仅作文件名。任何失败保留原slot，不换ordinal/namespace/seed或增补地图。

现成生成器：`route_rl_research/20261103/return_makespan/g23/data/generator_v2/generator_v2.py`，SHA256 `7a5f2e5c06acf7c70cccc55b20a1f8f1d30c481f73b14390b2b66b77894781e8`。直接复用 `generate_allocated_instance(sites,targets,namespace=...,partition='opportunity',ordinal=...,exclusions=...)`，不得重写坐标/标签生成器。版本2.0.0-engineering，SplitMix64/2015-02-16-reference-variant-v1，顺序条件均匀proposal、站间距>2000m、目标间距≥200m、距至少一站≤5000m；不称IID均匀地图或作者原生成器精确复现。

coordinate/target-ID seed逐字采用源码 `derive_seed`：对 `{schema:'route_rl_sequential_v2_seed_v1',namespace,family:[s,n],partition:'opportunity',ordinal,stream}` 做sort_keys、逗号冒号紧凑、ensure_ascii的JSON，SHA256前8字节big-endian uint64。作者seed为同样JSON约定下 `{schema:'f3_g3_author_seed_v1',namespace,map_id}` 的SHA前8字节与`(2^63-1)`按位与；**同底图三风共用同一作者seed**，不按风或质量重选。以下只计算字符串hash分配，未加载生成器、未抽坐标。

|短ID|coordinate seed u64|target-ID seed u64|作者 seed i63（三风共用）|
|---|---:|---:|---:|
|3x10_o1|2278710160775828834|1104186754301176309|881829287228501809|
|3x10_o2|7865733312478489808|17569006827134228642|3622741760507062823|
|3x15_o1|17436304524350099751|6548377777984729179|8910393318147477903|
|3x15_o2|12371900282963443624|1744564186529987095|3357412846445822686|
|3x20_o1|348518514818311379|17535357047866298785|1272393838018944287|
|3x20_o2|4144619728009712496|8781652315415603432|2931046392044710168|
|4x20_o1|3185841988599718495|4219290064782189605|797388913655063409|
|4x20_o2|5460632087710452987|1676344940185349095|9135636480183473717|
|4x25_o1|328393483588936178|14941219649315292963|655438540443935395|
|4x25_o2|15529397985997657619|17863014084985907487|8555298306099884333|
|4x30_o1|2622117846302733169|8436578473766011492|7208374650067882869|
|4x30_o2|681171166731885265|2634230863782943530|7396441661912560024|
|5x35_o1|15675876368531106336|16193013149516883731|1565460842238776923|
|5x35_o2|5945144976479834327|3291095359159399884|719621172487458068|
|6x50_o1|11252776006261006279|4871820690556908079|5762048607571234403|
|6x50_o2|4733514557098994849|673668851671797822|4682110155554336059|
|7x65_o1|14111561395772621243|2022268605970835512|12990659068818372|
|7x65_o2|9516724730319714133|5404523334055880052|6789172501807331675|
|8x80_o1|4527684052822239044|2317526801073763678|8380291290577372993|
|8x80_o2|9513950818257010830|6173515734255888997|5137284773595035418|
|9x95_o1|10217027527111199067|11048485215191667457|1684893639685561860|
|9x95_o2|11401316354066946098|7940300160991664017|1225593389843453229|
|10x110_o1|3110795177231077106|5784090767054364064|4373964262876733809|
|10x110_o2|16774433598109253979|15906925852327689779|7388980268678223173|

种子在跨语言manifest以**十进制字符串**保存，再由Python `int`/Java `Long`解析，避免JavaScript/Excel把>2^53整数四舍五入；不能从历史汇总中已被浮点化的作者seed恢复本分配。

## 3. 新图排除与生成失败协议

现成 `load_required_exclusions()` 只加载四个早期manifest，不能独自保证最新暴露排除。必须先冻结“源路径、源SHA、每源record数、实际unique raw与canonical数”的完整union，并将这四份原required源及补充记录一起传入原 `ExclusionIndex`；`require_research_ready()`保持原校验，不能绕开。至少包括：

|源相对路径|当前已读记录数/用途|
|---|---|
|`route_rl_research/20261103/return_makespan/g23/data/generator_reconstruction/PERMANENT_EXCLUSION_MANIFEST.json`|12120 official+pilot；保持原required校验|
|同目录 `SYNTHETIC_SMOKE_EXCLUSION.json`|1；required|
|`route_rl_research/20261103/return_makespan/g23/data/generator_v2/SYNTHETIC_EXCLUSION_MANIFEST.json`|4；required|
|同目录 `WINDOWS_DEVELOPMENT_PROBE_EXCLUSION.json`|6；required|
|`route_rl_research/20261103/return_makespan/g24_weather_nfz/status_reconciliation_g3_20261105/EXPOSURE_EXCLUSIONS_40.json`|40旧科学身份，以records数组为准|
|`joint_weather_emergency/20261106_control_qualification_C/exclusions/JOINT_EXPOSED.json`|120旧joint/deep等身份；不冒称覆盖所有以后暴露|
|`joint_weather_emergency/20261112_takeover_completion/results/g3_pop/population_index.json`|12旧暴露底图|
|同包 `results/g3_confirm/population_index.json`|36旧暴露底图；合计48全部排除|
|`joint_weather_emergency/20261112_takeover_completion/SPLITS_AND_EXCLUSIONS.json`|暴露源导航/审计证据，不直接当无遗漏geometry union|

**尚缺完整union**：11月06后B44/D64/发布620及其canonical核对、后续WX/新工程fixture和截至生成前新AIR2/截止接线等暴露，必须从其保存实例/manifest取原字节/规范几何身份合并；只列包名/新namespace或“碰撞概率很小”不算排除。现有 `SPLITS_AND_EXCLUSIONS.md` 也记录了B/D/canonical覆盖缺口；本次不重评旧质量，不重跑旧实验，可以在hn01准备预算内只读旧artifact补identity。raw/canonical任一撞已暴露或同批已生成图，原slot标 `GENERATION_FAILED_EXPOSURE_COLLISION`，不补图。

生成发生在root解除全部launch阻塞后；每slot保存完整 `generate_allocated_instance` 返回的元数据、proposal trace、完整/部分原始文本、raw/canonical SHA及失败原因。现成 `harness/gen_maps.py` 能作为薄调用样例，却只保存简化index且默认四源排除、失败不保存完整trace，不能原样拿它宣称本次完整生成冻结。无需重造生成器，只补保存与新union输入。生成后24slot无论成功失败都保留；成功图的三风只复用同一份原始底图字节。

## 4. 完整同风作者：复用修后Main，补薄CLI而非重写适配器

复用包 `joint_weather_emergency/20261113_author_final_recorder_fix_v1/`：

- Java源码为 `frozen/wind_adapted_fixed/`，其 `Main.MAX_ITERATIONS=500`、`ALNSSolver.maxIterations=5000`；保留全部现有算法参数、single-station guard与最终recorder修复。
- 使用 `validation/java/FullSolveEntry.java`（只调用`Main.main`并输出`FULL_MAIN_RETURNED=true`），不是probe/greedy/截短本地搜索。
- 原build身份 `J1b_constant_wind_final_record_v1`；`SOURCE_LOCK.json` SHA `924edf85366c30b4b242e2d69b0d41ad409ec71e5393822e787b1e7ddcaf475f`；已存 `builds/wind_adapted_fixed/BUILD_MANIFEST.json` SHA `edbb6795ca7d04b47b2f50f25a0b753c398e2184d209f3567d6daa099979856d`。跨目录复制后按source/class/JDK逐项核验，不仅信任路径和身份字符串。
- 复用 `validation/fullsolve_driver.py::final_main`、`compare_final`、`verify_build` 的逻辑及 `frozen/baselines/author_anchor.py::qualify_output`；它们已处理最终recorder与Main路线一致、Java独立WitnessAudit、原heading scorer及source身份。当前 `run_row` 写死`INPUTS.json`、ROOT与工程role，**还没有接新24图/3风的CLI**。只需把输入实例/风/seed/out/timeout显式参数化；保留原解析/验证函数，不另造风作者。

必须实现的薄接口形状（当前是待补接口，不冒称已有CLI）：

```text
full_author_cli.py --instance NEW_MAP --wind WX WY --seed FROZEN_AUTHOR_SEED
  --build VERIFIED_FIXED_BUILD --out UNUSED_ROW_DIR --timeout 1800
  --expected-input-sha256 RAW_SHA --expected-source-manifest-sha256 SOURCE_SHA
```

内部实际JVM命令沿原已验证结构：

```text
JAVA -XX:ActiveProcessorCount=1 -XX:+UseSerialGC -Xms16m -Xmx256m
  -XX:ReservedCodeCacheSize=64m -XX:CompressedClassSpaceSize=64m
  -XX:MaxMetaspaceSize=128m -Xss512k
  -Drepro.instance=NEW_MAP -Drepro.seed=FROZEN_AUTHOR_SEED
  -Drepro.seconds=0 -Drepro.wind.x=WX -Drepro.wind.y=WY
  -Drepro.guard=true -Drepro.output=ROW/reference.json
  -Dengineering.postMainDelayMillis=0 -cp VERIFIED_CLASSES test1.FullSolveEntry
```

**`repro.seconds=0`让原500/5000完整搜索，不以6/12s或1800内部早停替代完整作者；外部JVM timeout1800s。** 若1800s未返回则TIMEOUT，无完整作者锚点；即使早有raw也保留原字节并拒绝锚点。最终Main输出、recorder typed完整路线、source WitnessAudit、独立风scorer一致且guard合格才发Rw。全流程、审计及编译均计48h，锚点生成费用单列T_anchor；不能把它混入两控制各6/12s，也不能假称端到端TSALNS同预算领先。

不直接复用旧 `20261112_takeover_completion/harness/02_run_author.py`：其J1b/路径为旧零风批处理。不直接复用 `20261113_author_fullcall_v1/MODIFIED_FILE/author_runner.py::run_one`：该函数只接受6/12s并设置内部native截时，身份也早于最终recorder修复。它们可作进程记录样例，不能替代本完整作者定义。

## 5. 两强控制、H调度与公共组件

### 原生强ALNS

使用 `joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/frozen/baselines/` 的修后完整闭包：`minmax_alns.py` SHA `e43521f0f6284ddd45e3ce76890adb0f97cefaf3f87964e1ce016e27122e3e60`，`constant_wind_adapter.py` SHA `6deb20c25ca286c091b51fb63b3eaa04ea03a845ce7137c3eb6220494d19c119`。复用 `constant_wind_adapter.solve(instance,anchor,budget_s,started_at=t0,seed=...)`，完整原生harvest/rebalance/destroy-repair/new-trip/order能力保持；不给它RL候选池、单H、逐站静态owner或减迭代限制。风感知坐标与原heading scorer复核已有接线证据，不重造适配器。

现成科学入口可经 `frozen/route_delivery.py::run(bundle,out,budget_s=D,method='strong',seed=S)` 启动 `route_method`；其总时钟含input/import、搜索、后处理、durable输出、真正退出和独立二次验收。条件D下共享Rw在预算外生成但单独收费；不能预先免费跑ALNS/公共T再塞给它。

### 独立共同H：预定三阈值、全图时间线、跨H bank联合

源码底座为 `joint_weather_emergency/20261114_solxhigh_research_round_v1/deadline_control/MODIFIED_FILE.py`（SHA `4685e959232a2f8350cd91b028c54913def89b20308d0ae296f9675246b9b3bb`）与 `WORKER_MODIFIED.py`（SHA `6b051b69687dab509713249cf2ffed0ffa6cc94c4eeefe6f8b2e9bc075b38347`）。它们已经有全图绝对deadline及新worker `--budget/--reserve-s`入口；本次实际读取STATE另有单个新手写几何2次6/12s CLI有限接线结果，仍非新G3/科学规模资格，不重复该例。

本次事前H调度固定为：`H_j = rho_j × 原始同风作者M_return`，`rho=(1,9/10,4/5)`，按该次序；不根据新图效果/风/seed改阈值。每个6或12s调用从同一Rw开始，只有一次launcher时钟`t0`；总截止`t0+D`，最终化预留0.25s。三pass各占初始可用搜索时间1/3，绝对pass截止按`t_search_start + j*(t0+D-0.25-t_search_start)/3`确定；提前完成可转交后pass，不能延长最终截止或每H重新给D秒。每pass内复用当前deadline版本的active站剩余时间公平分配，闭站不占活跃站份额。

每H调用原 `generate/search_station`；operator_order固定 `rebalance,merge,relocate,swap,move_trip,split` 全部保留。工程 `rounds=4,max_evaluations_per_station=160`不得冒充科学充分搜索；科学时设上限为`2^31-1`，**实际只由全图deadline停止**，仍保留真实候选穷尽/无改进自然停止。每pass seed由 `{schema:'f3_g3_common_h_pass_seed_v1',namespace,run_seed,pass_index}` SHA前8字节得到，避免三个H硬复用同随机前缀；该规则不选算子，RL也不参与调度。

各pass所有合法站bank合并：每站anchor只保留一份，非anchor ID加 `H<j>:`前缀避免 `COPY_ID_MUST_BE_UNIQUE`；重复几何记录可按规范routes hash稳定去重，按首次出现保序。不删除局部超作者成本但物理合格的候选，保留跨站成本补偿。最终复用现有 `schedule_credit.Context.solve()` 从合并bank找最小可行H，再按原 `combine_at_H`/原scorer交付完整解；不是只交付最后H的局部费用最优。无bank见证仍UNKNOWN，不称物理UNSAT。

**实际阻塞：当前WORKER_MODIFIED只接单`bundle['common_H']`，没有上述三H调度/合并/最终Context.solve薄封装。** 需root在新包实现这一个薄worker，复用原求解器/Context/route_delivery.command_factory，不重写搜索。强ALNS不受该三H限制；共同H自身调度费用全部在自己的6/12s内。

### 公共T的14趟规模阻塞及现成替代

当前共同H `projected_slots()`导入的 `frozen/prefix_sampler.py::rebalance` 有 `assert len(trips)<=14`并做无deadline `product(slots,repeat=len(trips))`；大规模新图不能保证≤14趟。这是科学启动阻塞，不是可被忽略的工程注释；不能删断言直接无限指数枚举，也不能把大图失败删掉。

应复用同一强ALNS已有 `lpt_plan`（typed合法、失败回原排程）与 `gen_rebalance(ctx,plan,si,budget)`（k≤15且每64mask查budget）；以原方案为永久合法回退，按原scorer/字面cap取合格候选。k>15或deadline耗尽时用合法LPT/原方案，记录`APPROXIMATE_OR_TIMEOUT`，不称exact重排。不要调用旧无风 `harness/04_exact_reassign.py`充恒风通用T。该薄公共T接口须在科学前冻结、有限接线；未来BC/标准RL/候选RL/无学习获得完全同一T，原生强ALNS继续其原完整能力。公共T产生的收益单列；不记AIR2或RL创新。

## 6. 风、10运行seed与2880行顺序

固定风：`W00=(0,0)`、`W04E=(240,0)`、`W08N=(0,480)` m/min，风为**流向**；每底图三情景权重各1/3，family等权。10个运行seed固定为 `2026111401,2026111402,2026111403,2026111404,2026111405,2026111406,2026111407,2026111408,2026111409,2026111410`，两控制与两deadline共用这些seed索引，不假设算法随机流相同。

预注册一次总intent，24底图/72作者行/2880控制行在首次生成前列全。执行顺序为ordinal-major：先12family的o1，再12family的o2；family顺序严格沿generator的PUBLISHED_FAMILIES。第i底图的三风按`[W00,W04E,W08N]`循环左移`i mod3`，均完整保留；每风先完整作者与独立资格，再seed顺序1…10、deadline6后12。两控制先后按 `(map_index+wind_index_in_rotated_order+seed_index+D//6) mod2`交替，0时ALNS先、1时共同H先；这个调度只平衡运行顺序，不按表现选方法。

作者失败则同风40个控制行全部注册为`SKIPPED_ANCHOR_INELIGIBLE`（不真启动、不计作真实控制调用），保留72作者与2880注册分母。生成失败则该底图3作者机会和120控制行均保留为相应未启动状态；不更换图。调用数上限是启动数上限，跳过不等于失败额度退款。

## 7. CPU 172800秒的严格停止与恢复

CPU cap是本新ticket内**全部进程树user+system CPU之和**，不是墙钟、不是仅成功求解器rusage、也不是只把timeout相加。生成/编译/导入/driver/序列化/独立验证/失败/kill等待/收据均入账；老包消耗只读引用，不扣本新池也不退款。本轮本地静态编辑不是科学消耗，hn01准备开始时开新ledger零点。

必须有一个root独占运行锁、一个新ticket进程cgroup与一个外层预算监督器：采集单调`cpu.stat usage_usec`（含全部子孙线程）并按命令保存起止；对子进程另设`RLIMIT_CPU`/实际wall deadline、进程组kill，所有BLAS/OMP1线程、JVM ActiveProcessorCount1、CPU集固定且不并发科研。`cpu.max=1core`只是速率限制，**不是172800累计上限**；单次`RLIMIT_CPU`也不能代替整批累计。若机器没有可用的累计控制/进程树核账，保持launch blocked，不用事后总和冒称严格保护。

启动前按最坏剩余可支出预算预留本行full cap+审计/kill余量；不足则不启动任何下一个求解，余行标`BUDGET_NOT_STARTED`，既有失败/输出保留。总监督器必须在172800前留出可证明足够的检测/终止/最终收据CPU余量，并在工作CPU达到其保守停止线时立即停止整组；最终实际累计必须≤172800，否则整个ticket记录预算违反、不能PASS。禁止只在每行结束后才断言总和，从而容许末行超支。

建议实现时将已批17280秒储备中的至少3600秒不可用于搜索，专为driver、独立审计和终止；另将真实监督延迟/单进程hard-limit粒度作为明确guard计入预留。作者核心129600秒、控制核心25920秒之和155520秒保持；不能因预留而减少作者500/5000、替作者早停当完整解。搜索实际提前结束形成结余，不能自动增seed/图/方法或开训练。储备不足即停止并报告未完成，不借旧8.5h。

**当前还没有该ticket的累计CPU guard/一次性总driver。** 旧 `run_stage.py` 只做局部模块限额；旧deadline run.py只在phase后汇总，因此它们可复用收据字段/进程组约束做薄管理器，但原样不满足本段严格总上限。该项是实际启动阻塞，不能在本静态稿写成已验证。

每行先写durable INTENT+唯一rowID+输入/source/配置hash，再写RUNNING并启动；TERMINAL含真实argv/cwd/env、单调起止、exit、timeout/kill、CPU、raw stdout/stderr hash。已存在终局永不重跑。崩溃后的RUNNING没有终局，标`INTERRUPTED_UNCERTAIN`并按已预留attempt/预算保守占账，先只读恢复原进程/文件/收据，不能当没跑过重新启动相同seed。没有成功计时重跑或隐含repair额度；若实现缺陷触发停止，保留该次注册并另行冻结修订，不复活旧失败批。

## 8. 完整输出、ITT、统计与源闭包

每map保存原生成器完整返回（含失败），每author保存原reference JSON/stdout/stderr/final Main/Java source score/原wind scorer/guard/build/source/JDK身份、输入hash、wind/parameter hash、最终typed routes及对应Rw。每control保存bundle原字节、原raw完整路线/全bank或其可复核成员、同风独立scorer、route_delivery DECISION及真实最终exit/admission；晚退有效raw照留，但不进入ONTIME_VALID。cap/覆盖/机型/energy/duty任一失败均保留实际诊断。

未按时合格交付时原观察器的`itt_M_return=anchor.M`是**虚拟无改进编码**，与按时真实fallback分列；不能说算法已交付anchor。anchor不存在时配对质量未定义、保留可靠性失败与skip；不填零/均值或只做valid-only。策略生成失败、fallback、虚拟ITT、超时/OOM/启动/序列化异常分别计数。注册72作者、2880控制行总分母固定；actual launched/eligible/accepted另列。

每底图三风各1/3、再12family等权，三风是配对重复测量，独立地图n=24、family内n=2；10个nonRL运行seed不是独立训练seed或额外地图。完整报告每风/每family/6与12秒全部seed、胜平负、ITT与valid-only。G3只建立这三个固定场景下的完整资格、强nonRL和机会/方差，不预先声称5%/0.3%效应功效，不要求先RL/Formal阳性。冻结最强nonRL部署选择规则后才能进入DEV；不逐图取事后最好方法充部署基线。

source closure必须在科学前记录所有实际import的文件，不限于几个主文件：problem、wind_scorer、original_scorer、constant_wind_adapter、修后minmax/upstream、global_env/env依赖、公共T、schedule_credit、delivery/worker/driver/预算监督器、Java全部source/class/JDK、generator/exclusion源/新union、author解析/验证器及本分配。`g3_driver.py::SOURCE_PINS`只保存本次已读关键文件的确切SHA，**不是完整可启动闭包**；新增薄接口/完整union的hash未落盘前ready必须false。Python禁写pyc并冻结3.10语义；源变化则新版本意图，不覆盖原source manifest。

输出目录一律新建且不可覆盖，建议结构 `population/<shortID>/generation.json|instance.txt`，`authors/<shortID>/<wind>/...`，`controls/<shortID>/<wind>/<method>/seed_<S>/budget_<D>/...`；manifest中同时存完整ID，避免短名与旧o1/o2混淆。存储/文件数同样须在hn01实际可用盘上预留硬上限并由driver观察；不得删除失败/中间证据来腾空间。全图与统计实际数值仅hn01执行。

## 9. 交付的静态helper与明确阻塞表

同目录 `g3_driver.py` 只使用标准库，提供24ID/string-hash种子、72/2880注册计划、顺序及关键source pin验证的**元数据构建**；不import generator/physics/model，不生成地图，不提供scientific execute选项。它的输出始终 `execution_supported=false, ready_to_launch=false`，防止把静态计划当成果。后续root可在hn01准备记账时用它生成待冻结元数据，不需要重造现成适配器。

|阻塞|最小完成动作|解除证据，当前不能宣称|
|---|---|---|
|G0/AIR2实际技术准入|root完成当前新完整链并据实裁决|本文件不提前写PASS，不重开旧失败批|
|最新完整暴露union缺失|只读既有artifact补raw/canonical身份并冻结union|不是只换namespace即新图|
|完整风作者新人口CLI缺失|复用final_recorder_fix解析/验证/Java的薄参数入口|不是旧零风02_run_author或6/12截短author_runner|
|共同H三阈值/跨H bank封装缺失|复用现有generate/Context/route_delivery做薄worker|不是只跑单手写0.9H就叫充分强控制|
|公共T硬14趟域|复用原生LPT+bounded gen_rebalance+原解回退，完整typed/字面cap验收|不是删断言无界指数运行；不称大图exact|
|48h累计CPU硬保护缺失|新ticket进程树监测+预留+hard stop+完整账|不是timeout算术或行后assert|
|最终源码闭包/hash未冻|把上述新薄层及所有实际依赖纳入manifest|本helper SOURCE_PINS不是完整闭包|

以上是具体可完成接线，不是要求新发明nonRL算法，不以RL或Formal反向作G3前提。若root决定按本设计实施，在第一张新图生成前冻结最终配置/源/排除/driver/hash与技术准入；有阻塞时保持新科学人口生成与启动为0。用户48h授权仍有效，旧余额、训练与Formal始终不动。
