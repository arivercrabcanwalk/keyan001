# PREFIX_OFFSET_SUPPORT_DP_V1：六项运行前规格

固定风A、简单飞行时间线性能耗、物理TARGET/RETURN范围保持。仅root。上轮实测关闭PARTIAL_LABEL_PROFILES_V1加速实现，本轮不调其四个输入；此处定义一个不同的共享转移操作，再用新二维工程输入验证。

## 1. 输入与输出

给定双slot真实前缀、剩余顺序σ、完整总duty上限L、完整makespan上限H和背景站。每个下一动作(q,a)真实服务a，再求删a后连续分趟/带身份双slot分配家族的最优完整(M,sum duty)和见证。只覆盖这个受限顺序家族；不是全排列最优或actor概率保持。

计算核的mode表示已开放趟继续或先RETURN，输出仍可还原为物理路线。本包尚未实现完整RL策略和独立的下一RETURN查询入口。未来新组件须向无学习、BC、标准RL开放。

## 2. 新的压缩形式

固定q和两个开放趟mode，令a为删除位置。A_q(a)是已执行真实动作后的累计duty（若mode=RETURN则包括立即返站）；另一个slot的历史duty/立即返站是常数，计入基数。

若slot q继续开放首趟且未来首目标为f，定义 G_f(a)=t(a,f)-t(home,f)。若删除在一段内部，其原邻点为u,v，定义 Δt(a)=t(u,v)-t(u,a)-t(a,v)-service(a)，Δe(a)=flight_rate×[同一flight delta]-energy(a)。这些表只依赖本状态/物理信息；不依赖部分分割标签。

标签状态为 `(i, used_mask, f_q, b, D0,D1,S,parents)`。i是扫描层；b是内部删除所在slot，或者None（删除尚未遇到/以间隙跳过）；f_q只有继续q开放首趟时才需要；另一个slot的首边修正是常数，已并入D。对于支持位a，真实累计duty是

`d_k(a) = D_k + 1[k=q]×(A_q(a)+G_f(a)) + 1[k=b]×Δt(a)`，未指定f时G=0。

两slot的首趟电池均在首次区间转移时按真实前缀核完；后续都是独立闭合趟。因此长期标签不再保留首趟能量，也不再用五维通用模板作末端连接。

## 3. 转移、批量过滤和见证

每个连续区间[i,j)和slot k只计算一次名义趟时间/能量。一个标签扩展区间时分两类支持：a在区间外，保持b；a严格在区间内部，设b=k并应用Δ。a等于区间端点的情况不在这里删除，统一以i=a处的单点skip边处理，这样覆盖删除后的航次边界且不在同一物理解上反复插删端点。

q的开放首趟能量可写成 `E_trip + E_after_q(a) + flight_rate×G_f(a) + optional Δe(a)`。另一个slot的开放首趟修正为常数。每种剖面预先排序其a相关值，保存各rank的累计bitset。电池可行支持由一次上界rank查找给出；d0、d1和d0+d1的必要界同样各用一次rank查找与bitset交。位集合运算成本按其宽度计，不宣称无限宽O(1)。

同一(used_mask,f_q,b)组内，D逐坐标支配会在所有重叠动作上保持支配，因为动作offset相同。只从劣标签删除被覆盖支持位。D完全相等时合并支持并保留按支持位选择的parent分支，不能为所有查询盲用同一个见证。终点对未使用但有开放趟的slot补真实RETURN及电池检查。

```text
precompute physical interval costs and action offset rank masks
for each query slot and open-trip mode:
    scan the original order once using labels with two base duties and query support
    split support into interval-outside and interval-interior cases
    intersect precomputed energy and duty rank masks
    subtract only the supported queries dominated at the same compressed state
    preserve a per-query parent branch when equal bases merge
recover complete physical witnesses only for improving final answers
```

## 4. 正确性与计算代价预测

任一删除后分割在删除点处要么有趟边界（skip），要么有唯一跨删除点的航次（内部delta）；覆盖不要求生成全部完整模板。归纳证明：初始标签的真实duty由A和历史常数给出；每次转移只新增闭合航次并在首次时换真实首边，内部删除只出现一次，所以压缩式保持。电池约束在闭合该趟时核，已闭合趟不依赖后续。因此同组D支配与部分支持相减安全。该论证对一般有向航段时间表成立，不借用一维风方向或低秩距离假设。

预测可被推翻：192动作阈值最优值须与独立DP一致；两个小例须与完整枚举一致；小例所有保留终局标签的每个支持位须与完整见证重放的两slot duty一致。任何不一致均是实现/证明待修，不以总最优相同掩盖内部错误。

动作表预处理至少O(n²)数值和排序开销；缓存每个rank bitset额外包含字宽因素。标签数可指数，组数和最终支持扫描仍可能抵消收益。真正被减少的是每个转移对全部a重新做Fraction资源算术：本实现改为按组一次基数更新、少量rank查找和位集合交；只在初始化/建表/最终输出枚举a。比较计数和完整进程墙钟分别报告。

## 5. 最近先例与同预算对照

已有Range集合条件支配/trie、RCSP双向join、replacement paths区间支持、EMOA多维支配全部承认。rank bitset本身也是标准索引。当前待评估的具体组合是“真实首边offset分组＋已闭合趟的能量支持提前筛除＋两维基数共享扩展＋按支持恢复见证”。本轮检索/源映射单列，未获得穷尽新颖性证书。

BASELINE直接复用上轮带几何缓存和两维剪枝的逐动作DP；换同一个新二维物理接口，不降低它的剪枝或精度。MODIFIED和BASELINE都精确运算同一份由binary64物理航时转成Fraction的表，算表和序列化成本全计；冻结原风scorer另用航向三角函数复算原二维坐标。表值精确不等于实数物理完全无误差，独立物理验收仍按原绝对容差。

## 6. 预算、停止条件和准入

预登记4个全新工程fixture，n=5/7/9/11，三组阈值；n5/n7完整oracle，小n5额外逐终局模式校验。不是科学图、DEV或Rw作者锚点评价。BASELINE40 CPU秒、MODIFIED40、AUDIT50、另副本ROLLBACK40，wall各55s、2GiB；总child CPU上限170s。最多一轮不改输入的源错误修复，额外最多80s，硬总额250s；成功计时不重跑挑快。

正确性未修复则不通过；总时间未胜则关闭当前加速实现。即使工程加速成立，G0科学创新、G3强基线资格、RL贡献仍单列，不自动启动训练/Formal。下一步由完整结果而非局部速度或用户期望决定。旧失败/额度/两份科学STATE/暴露DEV原样保留。
