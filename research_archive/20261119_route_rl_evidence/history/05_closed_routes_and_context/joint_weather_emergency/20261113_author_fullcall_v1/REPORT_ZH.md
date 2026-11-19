# 完整固定风作者调用与强nonRL闭环

**已证实事实**：仅root/<COMPUTE_HOST>。两份冻结手写三站九目标输入完整运行真实Main/ALNS，独立heading scorer核对最终cost/latest、保存完整解及source guard。6s例从父进程起计到runner真实退出 2.067810477s，M=22.491325002669335、cost=117.136987504004；12s例 3.340444280s，M=26.67181731250836、cost=193.70772596876256。风分别(540,0)/(0,540)，airspeed900、简单线性能耗.018/min；官方电池/duty/覆盖/固定费不改。原零风J1b启动修复后完整解合格；未把原runner的native0伪称原生6/12预算。

首次强链生成脚本SyntaxError、换行修复后env.causal_engine缺失都保留，均未调用solver。最终另包20261113_author_strong_chain_v1按原完整43依赖闭包装包，复用两份实际作者解，强minmax ALNS真实2调用、各0.6s工程budget，2/2 admissible、无fallback、站型/归属/epsilon0且全成本cap保持；M均与作者锚点持平，无改善。该结果是接线验证，不是科学效果估计。

**未证实假说**：完整风作者/强nonRL在新人口、统一整图科学协议的资格和RL增量仍未成立。工程两例没改善不推断大域无空间。G0无合格新机制，G3未通过，未启动训练、checkpoint或Formal。本包有真实作者完整调用，不能再记为0作者求解；总6次Java启动尝试，1次在Main前内存启动失败，5次真正进入Main，3个完整合格输出（1零风+2风），另1预设不可行初始化、1drop-wind变异被独立验收拒绝。科学地图为0。

**失败或关闭方向**：初次旧JVM元空间预留失败，保留hs_err/stdout/stderr；仅补共同native内存预留参数后原输入/源码/seed再调用成功，不改算法。超时后早存best、最终print与保存解不一致、实际exit0但6.05s晚交付均被拒绝。两项中间链路工程失败不是ALNS算法质量失败。标准风度量/条件score/LOO等已关闭对象不重开。

**资源与回滚**：主8模块、换行修复3模块、完整依赖3模块，共14，child CPU 25.542525s（主24.447822、换行.237273、依赖.857430），2个模块exit1，加上各模块内部真实失败全保留。每包均执行baseline/modified/独立副本rollback：主21/21恢复旧command_for native0/无wind（原Java15同hash）；换行1/1恢复SyntaxError；依赖10/10恢复原import failure。主22文件修改与最终43依赖保留。原两科学STATE、旧Java/前包受保护源共38文件原字节保持；40身份/126比较、24/24校准不变。旧LATEST_STATUS正文保留。

**下一项有界工作**：风域比较协议与具体G0，见NEXT_BOUNDED_WORK.md。工程链已通，复用本包，不重复probe/全call。原C_Liu不默换，新风reference/原解风下不可行ITT/共同anchor/整图费用需要明示；兼容项自主推进，必须改变primary时才提交具体修订供用户决定。G0及域内G3后才全新TRAIN/VAL/一次DEV/Formal与充分≥3seed/消融。

**是否需要用户决策**：当前无新增。整体研究/CCF-B/G8未完成，goal保持active；风先应急后。完整路径、逐字stdout、输入、命令、退出码、每项计时和回滚见VERIFICATION.txt及server_evidence。
