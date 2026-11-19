# 2026-11-14 固定风物理路线RL：本轮真实完成与剩余工作

## 已证实事实

本轮三个新设计agent均为GPT-6.1-Sol / xhigh：物理路线构造、旧RL失败/学习更新、G3对照/预算。三份独立报告已落盘，物理与失败组实际交换并修订了具体反驳。root统一进行所有<REMOVED_ENDPOINT>运行。没有恢复历史agent、重跑旧科学人口或修改三份保护科学STATE。

**共同H计时接线已在副本修正。** `deadline_control/MODIFIED_FILE.py::generate/search_station`接收同一绝对deadline，按剩余活跃站分配剩余搜索时间，固定预留最终化；`WORKER_MODIFIED.py`从原launcher时间戳派生截止时刻，显式接收总budget。原makers/ruin、物理scorer、完整cap未改。无deadline的历史API保留；科学driver需显式使用新入口。

<REMOVED_ENDPOINT>假时钟单元：原版0/7满足新增deadline合同，修改版7/7，独立副本回滚恢复原hash和全部原case/循环/worker结果。原版/回滚exit0表示诚实记录预期缺口。另一个新手写8目标/2站几何，完整6s与12s两个真实worker进程均`ONTIME_VALID`、原scorer admissible，独立验收总时间分别0.16799402236938477s、0.168241610750556s。它们是小型接线工程，**不是科学规模、性能优势或G3全通过**。没有重跑旧17风矩阵/作者首尾/8配置。

**专用见证边界推进已验证。** 新`boundary_advance/MODIFIED_FILE.py::advance_next_token`只把已确定的下一TARGET从suffix首位移入prefix；不提前提升下一趟。下一token是RETURN时仅在suffix空时闭合真实prefix，然后规范化。七个有限API/完整路线守恒检查原任意动作force为4/7、新adapter为7/7；两个非下一token请求新adapter均拒绝；独立副本恢复原hash、4/7及全部原数组。该包没有运行AIR2枚举、地图、scorer或训练。它修正新适配的API误用，**不宣称旧force对其原本任意强制动作语义有普遍缺陷**。

逐命令、输入、literal stdout/stderr、退出码、CPU/wall、源hash、独立副本回滚均已取回并写入三个子包`VERIFICATION.txt`。主修改副本保留。

## 未证实假说与唯一候选

具体候选是：动作前的两条有效计划航次，在当前条件域内至多8目标，固定内核生成至多两条替代航次的新分组/顺序；候选按下一物理TARGET/RETURN建共享表，完整跨站费用组合后只执行一个物理动作。`air2_kernel/MODIFIED_FILE.py`已写入`compile_pair_rows/next_tokens`，但本轮其修改版枚举phase尚未执行。

所有已算候选必须交给COLLECT。首次完整表带来的即时收益属于固定内核；RL只能通过选动作改变后续物理前缀/公开见证，使后续表发现首次表以外的更好分组/次序。这是待检验假说，不是已证学习优势。保存`F(B0)/F(Bfinal)`、新分组首次发现步骤/来源pair/费用。影子COLLECT仅做归因审计；科学控制使用自己前缀、同kernel、同deadline独立运行，不能免费读取RL未来候选。

同context、kernel、动作law和PG的“标准RL”就是该候选RL本身，不虚设独立对照。margin辅助更新暂不进入无模型工程；今后与PG-only、margin-only、无更新同信息比较。新组合不胜margin-only时不称RL增益。

## 失败或关闭方向

**AIR2首次工程批次关闭失败。** BASELINE在`routes(post)==routes(pre)`断言中止，exit1；MODIFIED/AUDIT未启动。原冻结repair0，不补跑成功计时，不将该批改PASS。原因是新设计错误地把现成`force`当作不改完整路线的下一token推进：对singleton当前趟，remove+norm会提前提升future首趟并与当前目标合并。此失败说明适配假设不成立，并没有实际评价AIR2表的新分组、融资或质量。

另副本回滚恢复原source SHA并复现相同AssertionError/exit1；主附加kernel副本保留。之后只对专用边界adapter做独立七状态代数验证；其7/7不恢复原失败六配置批，也不构成AIR2通过。完整失败、旧稿错误断言与后续纠正均保留。

旧动态J的±6残差上界和16状态/178分支/256步诊断均已有结果，直接复用。本轮核对发现固定风可复用actor已有无界输出头，故不把旧硬界当当前固定风实证根因。旧Stage A、SCST/LOO、WX-E各失败配方均不重开。

## 下一项有界工作

先完成使用专用边界adapter的两趟候选完整链资格，明确与原失败批的不可复用结果及准入；核验真实前缀、typed电池、完整覆盖、跨站cap和共享表/逐动作域一致。未取得这些证据不宣布G0通过。公共H科学调度、实际规模6/12s交付与完整科学driver仍须冻结/验收，不把0.168s小例外推。

科学主线保持固定风、简单能耗、完整作者同风cap、强ALNS及共同H；应急后置。G0/G3、新人口与具体资源满足后，才有新TRAIN/VAL和至少3个独立训练seed、充分训练曲线、同组件监督/无学习及学习消融，之后一次DEV、全冻结全新Formal。不存在本轮新模型、checkpoint或RL优势。

## 是否需要用户决策

只需新增科学资源票据选择，已发出异步问题，**截至本报告落盘未收到答复**。推荐：24张全新底图（12family×2）×预定零风/4m/s向E/8m/s向N，72次完整同风作者尝试，两个强对照各10个运行seed、完整6/12s，新增48 CPU核小时上限（43.2h核心＋4.8h准备/复核）。较小选项为3运行seed/42h。旧余额不动、不新购或升级实例；训练和Formal另列。详见`RESOURCE_TICKET.md`。

三风是较窄比较域，不是17风总体替代；n=24地图，不是72独立样本。比较域/权重/种子在新人口生成前冻结，原完整作者1800s强度和ALNS搜索域保留。资源许可也不替代root的G0/G3技术判断。

**本轮整体：G0/G3未通过，0新科学人口/作者尝试/模型/训练/checkpoint/Formal；完成两项隔离工程修正，保留一项新工程失败。**
