# 新窗口必须先读的当前上下文

日期：2026-11-12，Asia/Shanghai。此文件与 NEW_WINDOW_TAKEOVER_PROMPT.md 开头相同，用作独立快速入口。本次交接只读现有材料并制作文档，没有连接 <COMPUTE_HOST>、运行科研、启动训练或创建子 agent。

## 0.1 你接手的任务

你是全新窗口的项目主执行者，默认对过去一无所知。用户要求你接续 Liu/LRPHSD 多无人机路线 RL 的全部剩余研究：**沿原规划的天气驱动外生事件流／应急巡检方向，补齐真正的模型与强对照，提出实质新机制，获准后做充分的多 seed 实验、优化、review、消融和全新 Formal，争取可信突破。**

仅 root 独立执行；不新建、恢复或联系子 agent。最新接手完成包记载过另一个窗口的并行线程，这是历史执行来源，不是本窗口创建线程的指令。保留其来源和审计身份，勿冒充自己独立重现。

读完后直接接续实质工作，不要重复提问“是否开始读／写规格”。已有工作不要重做，最新 source/hash/index 要核对。前置 gate 和资源满足时持续执行；当前无合格新机制就不训练。不要把用户希望突破解释成保证阳性或无限算力。

## 0.2 入口、时点和阅读顺序

工作区：`<LOCAL_PATH>`。

本次完整 prompt：`<LOCAL_PATH>`。

本次重点索引：`<LOCAL_PATH>`。

本次历史发现索引：`<LOCAL_PATH>`。

完整 prompt 后半保留原研究全史、论文、代码、服务器和 G0–G8 操作规范，并已合并重要更新；本节是最新优先入口。旧的 `<LOCAL_PATH>` 是之前时点的交接记录，不是当前文件／人口／服务器状态快照。

**阅读优先级：**

1. 完整读本节、AGENTS、USER_RESEARCH_REQUIREMENTS、RESEARCH_PLAN_ROUTE_RL、最新 LATEST_STATUS 和原两份主科学 STATE。
2. 完整读最新包 `<LOCAL_PATH>` 中 `STATE.json`、`GATE_DECISIONS.json`、`REPORT_ZH.md`、`STRONG_NONRL_REPORT.md`、`RUN_LOG.md`、`G0_DECISION.md`，再追其数据／manifest。该包 INDEX 和部分报告仍有旧计数／“尚未实现”的段落，按具体收据时间和代码解释，勿把第一个命中当最新版。
3. 读同包的 `PUBLIC_ROLLOUT_CONTRACT.md`、`public_rollout/DOCS_IMPLEMENTATION.md`、当前源码、`public_rollout_receipts/receipts/SUMMARY.json`／`MUTATION.json`／T1–T11、`SERVER_INVENTORY.md`、`PRIOR_ART_EQUATION_AUDIT.md`、`WX_PILOT_RECEIPTS.md`、`SPLITS_AND_EXCLUSIONS.json` 和 `RESOURCE_LEDGER.jsonl`。
4. 读 `<LOCAL_PATH>` 的原审计三文件及新增四规格，结合下面已指出的错误修订；不要把当时 pending-user 的文字当当前硬阻塞。
5. 沿后半16节和 HISTORY_INDEX 阅读各阶段 canonical 裁决，重要主张追到原文页／式、源码、完整解与真实命令。无需把同哈希的几千份快照都当独立研究重读。

原两份主科学 STATE 保留旧字节，**不能因为没有写入最新包的新数字，就认为新包没有执行**；也不能因最新包“最强 baseline 已建立”标签而自动提升整个 G3。冲突要逐项绑定时点、比较域、统计分母、budget 与实际收据。新窗口开工前先核实是否另有窗口仍在写当前包／运行服务器任务，避免并发覆盖；不要停掉不明任务。

## 0.3 当前科学状态与最新真实进展

**项目整体未完成；RL 仍未证明优于最强 non-RL 或 Liu 作者方法。**

- Liu/SEMFiX 120地图×5seed×P1/P2=1200配对复现已经完成，不重跑。
- 旧联合 DEV：oldbeam J=1169.612132，SCST/LOO J=1188.621808，高约1.6253%，8/8图落后；六actor选 initial。历史训练真实存在。
- 新 `20261112_takeover_completion` 包记录**本包0次训练、0个checkpoint、0条RL评价**；这不是全项目从未训练。它实际新增了作者锚点／非RL／精确参考和公共环境工程。
- G0：现有登记候选仍 `NO_NEW_DISTINCT_MECHANISM_NO_TRAINING`，静态 S 的本轮候选未过。不能外推为“确定性问题中RL／近似DP／信用分配在理论上必然无用”，也不能把它解释成未定义的所有未来 S 候选永久禁止。
- G1：有限工程通过；公共环境 `ENGINEERING_READY_WITHIN_IMPLEMENTED_SCOPE`，不是完整原WX合同或科学验证通过。
- G2：有新增 headroom 分解。
- G3：仍未通过完整资格，但已有实测强 min-max nonRL，不再笼统写成从未实现任何强控制。G3应核对强对照本身的域／正确性／预算／数据资格，不把尚未做G4的RL和G5的Formal反向列为G3先决条件；端到端TSALNS比较按独立主张另冻。
- G4未过，本包未开始；G5/G6/G7未完成；G8只部分材料，没有论文／投稿就绪证书。历史工程／开发包的完成不等于项目完成。

### 新静态机会／baseline结果：都已有证据，别重新跑一遍接手

来源是最新包的 STATE、G3_REPORT、STRONG_NONRL_REPORT、results、stats 与各收据；本交接仅静态核对这些文件，没有重新求解或独立确认全部统计。

|对象|该包记录|必须保留的限制|
|---|---|---|
|新人口|namespace `takeover-20261112-g3-v1`，12 family×4 ordinal=48图；作者锚点47合格；开发11合格、确认36图|48图现在都已暴露；确认集是预登记nonRL复核，不是G5 Formal；旧人口额度另记，不据新包自动退款|
|整趟站内slot重分配|47图相对作者锚点M_return均值约−11.412%，95%CI[−14.796,−8.179]，27胜20平0负；确认36图约−10.951%|保持已有趟路线，只改站内slot分配；标准非RL收益，不是RL或新机制；成本数学恒等，浮点差≤约2.3e−13|
|LPT／精确参考|LPT达到整趟精确重排值45/47；6张可精确求解图上等于更广域全局精确值|只对这6张及其冻结域成立；不宣称所有大图无空间|
|强min-max ALNS|开发交付10图＋确认36图=46；相对重排地板均值−3.041%，22胜0负；已交付46/46 admissible，0回退|开发10x110_o1未交付，不能静默剔除后声称全注册人口100%成功；同预算、ITT和完整分母需再核资格|
|8x80_o1|锚点M240.788→重排199.712→ALNS159.628，成本692.529→689.432；包称等于已证下界|核对精确证书与适用域后再引用“最优”；这些是nonRL、不是RL突破|
|早期joint_minmax|仅交付子集相对地板改善约0.310%；ITT回锚点则差约3.607%|保留超时、失败、完整解和不同分母；不得只报交付子集|
|失败锚点4x20_o1|Java latest-time86.5649与记录解scorer79.4749不一致、成本一致；runner拒绝|按原规则不补图，不改写为合格；保持原完整收据|
|精确扩展|6x50/7x65在max-n-exact16时返回UNKNOWN_NONEXACT_STATION|单站18–20等更多目标，不能把“未知”写成无空间／全局最优或擅自放大cutoff|

36确认图强基线先因2026-11-12 08:28Z服务器拒连中断，后来同seed重跑72行；两次成本和中断都记账。包还披露曾有线程读取confirm log尾部及早期intent后补，不能改写成完全盲验／从未中断。不要自动恢复这些旧脚本。

“相对作者锚点改善5%”已可由标准nonRL实现，这说明门槛不足以单独支持RL贡献，**不自动废除原合同或授权改门槛**。RL原本就要同时胜最强nonRL。若新主张要改变比较基准／primary estimand，先书面明确协议修订，不事后换分母。

## 0.4 论文与审计修订：不要重复旧误解和旧确认问题

**Zhao独立SI已取得**，不再写“未获得”：

```text
<LOCAL_PATH>
SHA256 6b9a7dd41f03d9567c9df8736dd823aa7420484ad4d38c7965200e2c757bb0ea
5页，138559字节
```

读最新包 `PRIOR_ART_EQUATION_AUDIT.md`：SI包含符号与RE算例，不含作者代码／完整实验数据；特征VS、参数是否含截距等与正文有差别。Han在线SI存在性仍未核实。正文＋SI范围此前已授权，不再询问用户是否一起下载。

**t_f：** Java／scorer每目标一次一致；印刷式(1)(8)统一常数对全部弧求和，不能仅靠站节点service_time=0证明与代码字面等价；每个非空返站航次会多一次t_f。作者MILP实际实现仍未知，不推断必然错误。原 `AUDIT_CLARIFICATIONS.md` 某些“差值被消除”句子仍不精确。

**边界判定：** Java `if(consumed > capacity) return false` 在精确相等时接受；不能沿用澄清表中“等于也拒绝”的错误中文解释。Java `checkPathEnergy` 用严格`<`，相等拒绝；scorer允许相应物理容差。搜索辅助与最终验收分层、调用链分开。以后按真实函数做边界工程例，不改老evaluator；成本与能量的容差单位也不混用。

**delta_pot：** 全图potential差奖励早在G1底座实现；未在某轮训练使用不使标准shaping变成新机制。不要再让用户裁定“没训练过是否算原创”。该候选的实质新步骤不成立就保留NO-GO；以后若有新的具体算法步骤，再完整六项查新。

**确定性不是RL不可能性定理：** 给定动作的转移确定，不意味着随机策略／探索／不同候选／训练抽样的方差为零，也不证明函数近似或跨实例学习不可能胜。确定性中重复同一动作续接无需重采，这个有限结论与“任何估计／信用信息增益恒零”不同。保留原候选NO-GO，但不要把过强理由当定理继续引用。

**历史WX数字已经修订：** 旧首包−0.40625与成本比1.20743出自作废toy；真实64行记录V_cluster=0.0、成本比1.086307，仍关闭。v6的+0.0208333是单个最好seed；该包3seed pooled约−0.012153。逐包读 `WX_PILOT_RECEIPTS.md`；其13包／14次有结果运行／3520行含作废及本地来源，不等于全部都是合格<REMOVED_ENDPOINT>科学行。旧40“新身份”也不等于40独立人口；新包指出它们来自同family／共同天气块，需以manifest重建相关性和统计单位。

## 0.5 公共环境最新进展及必须先核对的实质缺口

新实现：

```text
<LOCAL_PATH>
<LOCAL_PATH>
```

已有<REMOVED_ENDPOINT>工程收据：T1–T11，各n字段相加72条，均PASS；8个注入变异体被对应测试抓到。包括版本预报、隐藏phase、固定事件序／reservation、中途snapshot、RETURN、独立episode复算、背景请求、NFZ、告警、W指标与单episode driver的实现。后半提到的旧18概率例是更早隔离模块，**不应把新能力仍写成完全没有实现**。

这些检查证明有限工程覆盖，不能证明完全满足原WX环境、无信息泄漏、最强N4或科学优越。已知缺N4／beam／joint_minmax策略接线、合格科学批次driver及参数来源；有些文档计数和“未实现”段落没有同步，按真实代码与最新收据列明已完成／未完成，不盲信READY布尔值。

**从当前源码可直接定位的三项优先问题，交接未运行它们：**

1. `public_rollout/env/causal_engine.py` 在`SERVICE_END`分支以`t_done + delay`安排告警，T11也把“首次完成”作为起点。原WX-E需要**移动风暴单体离开目标后0–20min**产生告警。episode前预抽故障／延迟，不能消除触发时刻随服务策略变化的依赖。当前实现不可宣称兑现原天气驱动外生流。先区分storm crossing、物理巡检完成和告警job实例，再用同一完整风暴轨迹对不同动作序列核对事件release不变。
2. `exogenous_stream.py::MovingNFZ.blocks_leg`在若干离散空间点用同一个`t0`调用contains；12点采样并不构成连续航段无碰撞的保守证明，也没沿航行时刻推进移动单体。先明确静态近似／时变碰撞的适用范围，再做真正保守界或连续检查；不以“保守采样”注释当安全证书。
3. `metrics_w.py::evaluate`按`static.target_ids`、静态deadlines和receipt的`served`评分，而告警二次服务记录在`ALARM_SERVICED`分支。应核对**每个应急job实例的release／deadline／完成记录是否独立计入分母**，避免初次巡检时间替代后续告警响应。未服务∞的存储／bootstrap、CVaR最差10%的ceil近似也须明确；不能因手写三个值的例子通过就说全部W统计成立。

先做一次有界的“原WX场景合同↔最新实现↔真实测试”差异表和修正规格，优先修外生release语义，再做有判别力的<REMOVED_ENDPOINT>工程验收。保留原失败、旧源码和版本。工程修复和标准条件Bayes不自动产生G0创新；新科学运行仍由准入／人口／预算管理。

## 0.6 <REMOVED_ENDPOINT>最新可用连接：优先密钥，不让用户重复建连接

已存在本机私钥路径 `<LOCAL_PATH>`。最新环境包记录该密钥认证成功；本交接只核实文件存在，没登录也没读取／复制密钥内容。新窗口先做一次只读连接验证：

```bash
<CONNECTION_COMMAND_REMOVED>
    -i "$HOME<REMOVED_SSH_PATH>" -o IdentitiesOnly=yes \
    -p <CONNECTION_PORT> root@<COMPUTE_ENDPOINT> 'hostname'
```

临时wrapper `<EXECUTION_PATH>`目前在本机存在，内容／有效性仍需核对；可直接使用上述明确命令，不依赖临时脚本。alias默认`id_ed25519`失败与新专用key成功不是矛盾。不要再默认只有密码，也不要求用户先建已不存在的`cm-<COMPUTE_HOST>`socket。若key失效，再按真实错误采用既有密码／交互路径，不在日志／命令行／项目存凭据。

最新包记录的环境是**历史观测，开始任务时重新只读核实**：hostname <COMPUTE_HOST>；系统Python3.10.12；104逻辑CPU、371GiB内存；当时无可用NVIDIA设备；runtime Python3.13.18、torch CPU可import但scipy缺失；conda另有依赖。分列挂载：`/`约9.9–11G剩余、`<EXECUTION_PATH>`约42G、`<EXECUTION_PATH>`约611G但持久性未证。不能把全机nproc/free当cgroup可用额度，需核对实际quota。新大结果优先已核实持久卷，先看可用量与新目录不覆盖；不删除历史数据换空间。

远端现有最新包：

```text
<EXECUTION_PATH>
<EXECUTION_PATH>
<EXECUTION_PATH>
<EXECUTION_PATH>
<EXECUTION_PATH>
<EXECUTION_PATH>
```

别把07:52Z“无作业”当成当前状态。按实际进程、开始时间、intent和终局核对，不根据旧PID重启／终止任务。所有新物理工程、作者求解、训练、质量评价只在<REMOVED_ENDPOINT>；Mac仅文档／静态／哈希／传输／查看既有数据，不本地重算科研结果。

## 0.7 接下来具体做什么

1. 本地核对最新包和只读服务器现状，补一个短的接续差异记录；不要重做1200复现、48图作者锚点、旧DEV／confirm统计或旧9项F问题的完整审计。
2. 以原WX-E外生天气—故障模型为准，完成上述三项工程／指标差异规格及必要修正，在<REMOVED_ENDPOINT>做新的有界工程验证。明确模型参数来源、公共条件分布和隐藏阶段；不为获得RL优势追调天气强度或请求率。
3. 一边补环境，一边针对该动态决策困难筛查**一个有实质新构造／估计／学习步骤的G0候选**，六项合同齐全；不把“此前没训练”“已有shaping”“标准rollout”当创新，不靠修改网络或seed重开旧身份。
4. 将已实现强min-max baseline、真正公共因果N4、共享容量准备度、BC／监督／VFA／API-only公平对照纳入当前任务域的G3资格，分开S与W；不能只胜LPT／Greedy或弱LIU_ADAPTER就放行。
5. 有实质G0与合格G3后，独立冻结新TRAIN／VAL／一次DEV／Formal人口和资源，登记充分实验矩阵：至少3独立训练seed、训练充分性、RL增量、同信息同候选同预算、uniform独立重训、机制消融、鲁棒性及新Formal。新包48图与所有旧已暴露人口都排除出Formal。
6. 主动开展依赖满足、预算已登记的工作，不每步要用户重批。单纯创建文档／新隔离工程目录不是额外审批理由。确需新增动作WAIT／DIVERT、改变原primary合同、超过明确已有硬资源额或外发／投稿时，才提出具体用户决策。此交接请求本身不批准这些变更。

最新STATE称下一项P1h为参数物理来源／独立TRAIN校准，P2仍待决策；新窗口应把它与以上更基础的release／指标语义一起排依赖，不能只给默认参数加引文就宣布原W模型已合格。也不要把某旧文档“仅能写两份规格”当作永久停止命令。

每次向用户汇报中文五项：**已证实事实／未证实假说／失败或关闭／下一项有界可验收工作／是否需要用户决策**。数字注明来源时点和完整分母；本次未独立复现就标既有收据。项目当前仍G0 NO-GO、G3/G4未过、Formal／正文／G8未完成。完整完成标准是科学证据和可复核交付，不能靠计划、代码行数、PASS计数或训练日志宣称完成。
