# 状态投影、规范见证与成本边界

闭趟pool为P=(p1,…,pk)，每趟内目标和顺序冻结，合法slot由完整返站energy决定。开放趟O0/O1固定在原slot；actor只给a=(slot,target/RETURN)。令A(P)为全部typed分配，L_s(σ)按pool创建次序、逐slot以原binary64加法累加完整duration。B_s(L_s,O_s,a)同时取原动作合法性表达式、执行该动作后的即时RETURN表达式、原scorer完整返站表达式的最大值。候选mask为

`legal(a) = physical_target_or_return_checks(a) AND exists σ∈A(P): max_s B_s≤min(H,duty_limit)+EPS`。

它是当前动作的可行分配投影，不是剩余全部目标可完成的证书。固定前缀只检查一个σ；eager先按当前O选σ再查a；conditional按a选σ，故eager可能拒绝conditional允许的a。该差异发生在同一登记规划前缀，不表示原完整物理schedule域更大。一个从空开始的full-support原actor可直接生成条件规划器交付的最终路线。

规范见证key为`(max(B0,B1),L0,L1,assignment)`。当前load点q被p弱支配时，p经过同一非负追加表达式的B不大于q；若B相同，原load字典序或同load的最早assignment使p不劣。因此当前查询可只看l0递增/l1严格递减frontier。二分找到满足H的区间与两曲线交点，再找达到最小max值的最左点，即同规范见证。当前前缀不用永久丢弃其他不同load点：未来浮点加法可能压平差别而使其assignment重新在tie中获胜。实现因此持有全部不同load对，仅合并完全相等点并保留最早assignment；相等状态追加同后缀后仍相等，字典序也保持。

label数最坏2^k，新增闭趟的扩展/排序最坏仍指数；不是一般多项式求解器。单次action查询在已建frontier上作O(log F)load比较，另有开放趟资源重算；逐动作直接强控制重建全部2^k assignment。运行只验证k≤5工程输入，旧14趟硬上限保持。

物化只改闭趟slot/routes/cumulative_duty，开放趟target顺序、位置、能量、elapsed保持。规划采样中的重分配事件不是实际执行日志。完整结果必须在冻结原StationRouteEnv从空逐最终slot重放，且原完整scorer可行、固定域、C≤工程anchor.C+1e-7、M_return≤H+1e-7。当前query只作局部约束传播，不替代该终局验收，也不声称完全处理所有极端float边界。

同一固定趟pool的真实算术总operating与slot分配无关；原scorer按slot分组的binary64总费用可有末位差，仍逐解验收。公共final T保持，其时间与独立评分/回放全计入对应mode pipeline；不免除已有bank、强ALNS或作者同风完整cap合同。

标准REINFORCE未来若采用此规划状态，其动作score按实际生成动作law；确定性物化不另增随机score项，既有旧轨迹不能直接当新law数据。当前没有模型、梯度或RL实验，本文只给接线边界，不把上述投影或标准更新当独立创新。
