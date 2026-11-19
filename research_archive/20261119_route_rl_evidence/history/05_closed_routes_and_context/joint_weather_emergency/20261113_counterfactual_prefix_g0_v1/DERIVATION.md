# 全删除反事实包络下的物理前缀停止

这是一个明确可推翻的工程/学习计算候选；不是新颖性证书、训练结果或G0通过。固定风A/简单能耗/作者风适配完整cap/物理动作合同不变。新输入均为小型手写工程几何，不占旧科学地图/满额校准，也不冒充Liu作者锚点。

## 问题与具体步骤

每站保留永久完整anchor，固定K个独立采样身份；F(P)是从当前各站完整schedule池中各取一个，在原完整成本cap下最小化完整返站M的值。D_x(P)=F(P-x)。固定身份、round-robin站顺序、独立sample-ID随机流，不补抽失败/截断样本。

仅用当前H=F(P)剪掉LB>=H的候选，可以保持F，却不能保持D：单站anchor12、X5、Y8，丢Y前后F均5，但D_X由8变12。把截断池当IID完整池套普通LOO，缺乏正确性。

本候选在每个新候选开始前计算

    E(P)=max(F(P), max_{x为已完成非anchor副本} D_x(P)).

空副本集合使用F(anchor)。沿当前物理前缀取得对最终完整重排schedule均成立的下界LB。如果LB>=E(P)，就真正停止后续TARGET/RETURN生成，记录固定身份的PRUNED_CERTIFIED_NONIMPROVING；没有完整路线交付，也没有新候选补抽。完整失败同样留在原身份分母。

具体相对简单incumbent剪枝的增量是“保护全部单删除上下文的阈值”，相对固定anchor阈值的增量是随着有冗余完整可行见证出现，阈值可以单调降低。公共缓存F/D求值和全部重排也交给固定anchor剪枝控制，不能只对候选优化。普通B&B、LOO、零信用、score恒等式及阈值排序均不是原创主张。

## 等价证明及学习边界

对任一当前删除上下文P-x，已有完整可行见证值D_x<=E。被停候选y的每个完成都满足m_y>=LB>=E，因此任何包含y的组合，其max至少E，不能严格降低该上下文的值。原池同理。增加任意未来候选B后，旧可行见证仍存在，F((P+B)-x)<=D_x(P)<=E；因此y对所有旧删除上下文永久冗余。删除未来副本z时，当前P也仍存在，F((P+B)-z)<=F(P)<=E。删除y自己当然恢复同一个值。

逐个停止可以归纳得到最终F和每一个D都与全生成池相同。每个被停候选自己的最终D_y-F为零。完整保留候选的实际动作、概率和完整score与全生成相同；各sample-ID随机流隔离，跳过一个后缀不改变任何其他身份。因此对固定原IID潜在完整批次，

    g_full=sum_x (D_x-F) grad log pi(tau_x)
    g_stopped=g_full

逐样本成立，而不只是期望成立；估计器方差也保持相同。并不是声称自适应截断池本身仍IID。证明比较的是原完整池LOO随机变量；只有零贡献的后缀被省略。共享参数允许，动作/状态依赖的模型score允许，但不包含随策略变化而未纳入score的外部采样。当前代码用有限Bernoulli物理动作策略作精确核对，未导入模型或训练。

标量F/D/梯度等价不保证最终选中路线身份、成本tie-break或全部候选输出完全相同。返回的路线必须单独由原scorer验收。E由精确当前F/D得出，代码在不可能改变E的完整候选上不重复求解；这属于有证明的缓存跳过，不调整样本。

## 整趟重排后仍成立的字面浮点下界

原scorer每趟以sum(travel)+sum(service)求duration，再按slot按趟累计duty。环境自身的cumulative_duty分组不同，且公共整趟重排可把原slot负载移走；不能直接用当前slot累计值。

每条已闭合趟照原scorer计算duration；每条开放趟只计算已走过腿和已访问service，不含尚未走返航。CPython3.10/IEEE binary64下，这些非负有序和为最终同趟duration的下界。设已知这些duration的精确dyadic总和S、最大值A，每站N个目标、v个可用slot、u=2^-53、eta=2^-1074。每slot最多N非空趟，非负rounded累加满足

    duty_slot >= (1-N*u)*exact_sum_assigned - N*eta.
    M_after_reassignment >= max(A, (1-N*u)*S/v - N*eta).

第二项用Fraction精确构造并向下取binary64，第一项直接取已知duration最大值。输入限制N<2^52、资源有限非负，N趟数上界由每趟至少一个不同目标及不可重复访问保证。公共postprocessor枚举每条完整趟的typed slot分配、累计duty和合法电池，保持每趟及顺序，不修复/重排趟内弧。

这个界保护的是当前“直接构造＋整趟重分配＋原池选择”流程。允许事后改变已经构造的趟内弧（例如完整ALNS）会破坏前提；不能据此替代强ALNS主对照，也不能宣布整个G3已过。将来若接学习/额外后处理，须为那个真实映射另证有效界及全费用。

## 可证伪标准

任一新coupled样本的F/D/非零梯度不等，任一合法全动作完成的重排M低于LB，或原scorer不接受交付，即正确性失败。总wall或生成动作未优于固定anchor证书控制，即当前效率主张关闭。只降低查询次数、保正确、单次时间或有限工程阳性都不等于训练/论文突破。固定输入与概率不根据结果重调。

## 可复用接续提示

```text
仅root，数值仅<REMOVED_ENDPOINT>。先读本包STATE/REPORT_ZH/DERIVATION/PROTOCOL，按TERMINAL收据续接，勿重跑成功计时或旧8phase。
固定风A、原完整cap、物理TARGET/RETURN、强ALNS与成本中性重排保留。
先核对E保护全部单删除上下文的证明、typed重排后LB、逐sample-ID耦合和原完整池LOO路径一致性。
公共组件同交固定anchor剪枝/nonRL/BC/标准RL；不把B&B或LOO当原创。负结果保留，不以工程PASS解锁训练/Formal。
```
