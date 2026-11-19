# 单站终止修复：有限通过，最终解记录失败保留

仅root/<COMPUTE_HOST>。5phase全部exit0，child CPU18.657599s，phase墙钟合计9.532927s；无修复额度，未重跑成功计时。两工程输入复用前包已定位失败/回归，未生成科学人口或训练。

已证实：直接调用原randomSwapStationTypes([2])在打印ENTER后超时；length1时两个nextInt(1)只能相等，死循环原因明确。唯一Java改动在clone之后对length<2返回clone。0/1站返回独立副本、原数组不变；2站的返回值及后续RNG输出逐字与旧版相同。14个其余Java文件hash不变。

完整双站Main的Recorder、最终打印完整解和源评分与前包风适配逐字一致，合格。原15s超时的单站large完整Main现在2.832188s退出，Main500/routing100/ALNS5000、全部guard/物理参数保留；新身份AUTHOR_ALGORITHM_WIND_ADAPTED_TERMINATION_FIXED。该行最终仍REJECTED，不把恢复退出当合格交付。

具体失败：Recorder存LD[3,1,4]/SD[2]、C90.29552921338332；最终Main打印LD[2]/SD[3,1,4]、C90.2955292133833。两者M均62.5158681618782，但typed slot完整路线不同，资格按原规则拒绝。费用差远小于Recorder的1e-12增量保存阈值；Main按严格浮点更小更新best，存在两套选择标准。这不是靠放宽1e-7成本容差可以修掉的路线身份问题。

独立副本已恢复原LocationOperator SHA `0f813461e336e435feb0d05a7c3b5d9c0677e3dce87dbbd7899f441e90e79a54`，重编译后单站超时、零站异常、两站返回/RNG字面输出全部恢复，主修复hash `3f56fdcaf0452216938fb941b4311e4327c638ee07d3f530d669a541deafbc5d` 保留。工程收据exit0只表示测试正确捕获/保留上述结果，不表示两行都交付合格。

下一项另包 `20261113_author_final_recorder_fix_v1/`：只给最终best增加强制完整记录，不改优化、guard、物理或旧增量save；三种cost变化的记录探针＋原两工程完整Main回归，继续逐字核最终算法行为。已冻结，执行状态以该包STATE/真实终局为准。

G0/G3未通过，0模型导入/训练/checkpoint/科学地图/Formal/子agent；旧两科学STATE、40身份126比较、24/24校准和失败不改。当前无新增研究决策；服务器连通性变化另记，不混同论文准入。
