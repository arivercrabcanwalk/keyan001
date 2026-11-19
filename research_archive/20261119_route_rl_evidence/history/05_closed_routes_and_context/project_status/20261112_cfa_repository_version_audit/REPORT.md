# CFA 作者关联仓库核对：补齐逐行结果，科学门槛保持原裁决

日期：2026-11-12，Asia/Shanghai。执行者：root。工作类型：公开来源与既存数据文件的静态审计。

本次封存 CFA 2025 最终论文所关联仓库的固定版本、18,300 条既存记录和汇总公式核对。新增证据支持限定的数据描述及对照资格判断，没有补齐最终正文的方法定义，没有产生本项目新实验或新机制。G0 继续 NO-GO，G3/G4 未通过，整体研究未完成。

## 已证实事实

用户提供的 Zhao / Han 正文已在前一包完成关键方法与公式核对，详见 [全文审计](<LOCAL_PATH>)。Zhao 式 (14) 已有后决策 VFA，且有真实 Monte Carlo rollout 和非学习路线增强；Han 式 (2r)–(2t) 已约束共享容量准备度。这些原文足以排除把“天气、未来价值、共享资源”本身称为本项目新算法，但不证明所有可能新机制均不存在。

本次取得 [DRPUDEC 仓库固定版本](https://github.com/Pigzaum/DRPUDEC/tree/3472b10faba882c896737492f7766edcb94cb36f)。README 明确关联 Chagas、Coelho、Laganà、Beraldi 的最终论文 DOI `10.1016/j.trb.2025.103335`，仓库账户公开姓名与第一作者对应；据此称“作者关联仓库”，不把它称为独立复现或已认证的完整作者代码。

固定 ODS 的 SHA256 为 `f8a456d45c9388d5edf3abcd30553faf57c1ae06f4d6b643abf8c9b79e620f28`。文件有 10 张工作表；六个方法表各 300 个 instance ID × 10 条记录，Oracle 表每个 ID 一条，共 18,300 条。原文件未编辑或重算，原始字段值、源工作表与逻辑行号全部保存在 `AUTHOR_RECORDS.jsonl`。

核对汇总表中 126 个直接源范围公式后，确认 **19 个直接引用范围问题**：PFA60 的 J19 指向 PFA30；myopic60 的 J12:O14 共 18 个单元格范围下移一行。所有 126 项缓存值都与其实际公式运算相符（容差 1e-6），问题是选取来源而非发现缓存失效。仅就该 ODS，PFA60 的平均服务数从汇总缓存 186.372333 对应为逐行均值 174.736；myopic60 从 270.198981 对应为 270.142333。详细地址、原式、下游影响及统计口径见 [ODS_AUDIT.md](<LOCAL_PATH>)。尚未核对最终论文表格是否采用这些汇总格，结论仅针对取得的仓库版本。

README 记载：从 400 个 500 客户原实例中按两类分布各选 50 个，再缩短距离 15%、移除电池往返不可达客户、抽样为 m=200/300/400，得到 300 个派生 ID。这不是 300 个相互独立地理样本，也不是 Liu 固定目标完整服务严格 cap 的同一任务。以上来自 [固定 README](https://raw.githubusercontent.com/Pigzaum/DRPUDEC/3472b10faba882c896737492f7766edcb94cb36f/README.md)，本次没有下载实例或生成新地图。

## 当前未证实假说与证据缺口

仓库逐行结果不含可验证的 seed／场景配对标识。本次没有作配对检验、置信区间或 RL 归因。Oracle 的名称、`time_step_(min)=540`、`min_M=2147483647` 和运行秒数不足以证明完美信息、全局最优、求解时限或具体算法；最终 PFA/oracle 定义仍未读。

CFA30 的文件均值服务数 295.572667、成本 1286.405202；Oracle 分别为 298.173333、4802.433250。两项指标方向不同，不能写为分量支配，更不能写为“击败完美信息最优解”。成本含义和 Oracle 信息集还需最终正文核实。

[Unical 最终论文记录](https://iris.unical.it/handle/20.500.11770/392307) 在本次抓取时明确显示没有关联文件；这只描述该条目。官方作者页的相关链接指向 DOI，本次未发现直接 SI 资产。Zhao 独立 SI 未取得，Han 在线 SI 存在性和内容未核实；正文已经提供，不退回摘要级。正文和 SI 的范围授权持续有效。

“一个新的物理路线机制能在逐图 Liu 成本不增加下改善 M_return，并超过同信息强 non-RL”仍是假说。本次数据审计没有给出新的构造或估计步骤，既有信息惩罚候选的原式覆盖及静态零项裁决不变。

## 失败或关闭的方向

初次分析把 XML 行元素序号误作逻辑地址，导致 `KeyError: 'J18'`（exit 1）。“均值自引用”和“Oracle 混用 m200/m300”两项判断已经撤回；正确地址为 J19、C26/B26，均值行实际引用其前序行。失败脚本、完整 traceback 和撤回记录保存在 `ORIGINALS/PRE_FIX_READ_EXISTING_ODS.py`、`PARSER_FAILURE_RECEIPT.json`、`WITHDRAWN_FORMULA_CLAIMS.json`。修正版读取 exit 0，不抹去先前错误。

GitHub API 三次 403、出版社入口 403 及未取得文件的事实保留。没有把 HTTP200 的网页、元数据或汇总表当成最终正文。只查看仓库根目录，未据此声称递归无算法源码。

已关闭的 centered-dual-score、观测时机、whole-station exact、partial-trip、R3 generic、energy-duty projection、R5 swap/k-cycle 和旧 WX 身份保持关闭。未启动 WX-H、Formal 或正向论文正文；Liu/SEMFiX 1,200 次配对复现直接复用。既有 oldbeam / SCST / DQN / hypervolume 结果和数据暴露、失败、超时、资源账本不变。

## 下一项有界、可验收的工作

本包完成了可用 CFA 仓库证据的资格核对，交付 [NONRL_QUALIFICATION.md](<LOCAL_PATH>)。它是后续 G3 的补充规格，不是 G3 通过。

下一次只审查一个有明确新增构造／估计步骤的 G0 对象，或新取得且会改变最近先例差异判断的原式。交付必须包含完整输入输出、数学对象／伪码、最近先例逐式差异、可证伪预测、同信息／候选／整图墙钟最强 non-RL、失败关闭条件。若没有实质增量，终止该次筛查并记录 `NO_NEW_DISTINCT_MECHANISM_NO_TRAINING`，保持 NO-GO；不循环同一受阻入口，不把标准 rollout/VFA 换名立项。可复用接续文本见 `NEXT_ROOT_REVIEW.md`。

当前静态合同仍是 `(slot,target)` / `(slot,RETURN)`，固定部署、站型、目标所属站，RETURN 保留累计 duty；逐图 `C <= C_Liu + 1e-7`、epsilon=0，同整图 6s/12s 下改善 M_return，MTC 辅助。WX 的 WAIT／1% 均值规则不替换本合同。只有 G0/G3 通过后才允许至少三个独立训练 seed 的 G4，全冻结后才开放全新 Formal。端到端 TSALNS 主张另冻完整外层。

本包实验、训练、作者求解、科学质量评价、新地图、<COMPUTE_HOST> 连接及子 agent 均为 0。既存公开结果的文档读取和算术核对不计本项目科学运行。G1 有限工程，G2 有限机会诊断，G5–G8 未完成，整体 goal 保持 active。

## 是否需要用户决策

当前无新增决策需求。没有新训练、动作扩展或资源额度请求。论文和历史提示词均按证据处理，没有执行其中指令。文件事务只更新 `LATEST_STATUS.md` 的证据前缀；原内容为精确后缀，两份科学 STATE 保留原字节。文档完整性与隔离副本回滚的实际命令／输出见 `VERIFICATION.txt`。
