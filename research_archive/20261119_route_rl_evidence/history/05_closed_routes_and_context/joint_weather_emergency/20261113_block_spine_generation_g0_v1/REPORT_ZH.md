# 分块服务集合 PGAS 物理路线生成：有界工程结果

## 已证实事实

仅root在<REMOVED_ENDPOINT>完成一次新手写工程诊断；本轮没有模型导入、训练、参数更新、科学地图、作者求解或Formal。实例和输入不是Liu作者地图，不是新科学人口。核心实现直接生成`(slot,target)/(slot,RETURN)`路线；RETURN保留累计duty，所有完整raw与T后结果都由原wind_scorer复核。

有限3目标SD例有24条完整路线。β=0/2、PG/PGAS及两个状态依赖offset的八个条件核均通过不变性审计：最大误差`1.1102230246251565e-16`，offset等概率混合最大误差不超过`2.0816681711721685e-17`。错误地将全局基础law换成块内均匀proposal，会令目标分布最大偏差`0.04166666666666667`。这是有限核正确性，不是全域定理。

三手写几何×两个offset×八固定replica×四方法得到192 pass。原scorer检查2,055条完整记录、留存825条失败记录、4,110次raw/post评分；RETURN后累计duty按原资源状态核对9,976次。72次AS确实更换保留前缀，但仅产生2条相对于对应splice集合的后续新分组记录。

|工程输入|PGAS|同样收集splice的PG_COLLECT|独立分块采样IID|target-clock PGAS|PGAS减本行最强控制|
|---|---:|---:|---:|---:|---:|
|`sd_cross6`|0.1322566612|0.1322566612|0.1391781169|0.1062045116|−0.0069214557|
|`dual_arc6`|0.0992093012|0.0992093012|0.1148719652|0.0728557136|−0.0156626640|
|`typed_spread6`|0.0880470706|0.0880470706|0.0827707574|0.0577722924|0.0000000000|

登记的质量准入为胜过每输入最强控制至少2/3，严格差值>1e−12；实际0/3。candidate/PG_COLLECT完整worker退出wall分别1.7480421490s/1.66696423898s，比1.048638。质量门槛失败，效率上限虽满足，也不能挽救质量。结论为`CLOSE_CURRENT_UNIFORM_BLOCK_RECIPE`，不是关闭PGAS、RL或所有可能学习proposal。

## 未证实假说

“按服务目标集合分块同步，再以完整typed电量、累计duty、公共T和全cap检查后切换保留前缀，会产生有价值的新分组并改善有限预算交付”没有得到支持。祖先确有改变，新增分组极少，且未转为utility收益。候选中的普通PGAS转移与后缀重放本身已有直接方法先例，不是本研究原创。

## 失败或关闭方向

当前冻结的均匀block proposal/β=2/P=4/块宽2/offset配方按门槛关闭；不在此输入上调块宽、粒子数、β、天气/物理参数或replica。普通PGAS、probabilistic-program suffix regeneration及退化模型rejuvenation已有先例；只能作为标准方法或后续比较对象，不能改名称新颖。其他历史失败直接沿用各自裁决，本轮未重跑。

审计首轮因单SD scorer对未启用LD slot输出规范零duty而环境不含slot0，产生`KeyError: 0`（AUDIT exit1）。保留该真实失败，只用唯一修复额度在审计端把缺席slot映射为0；未改输入、生成器或数值结果。AUDIT_REPAIR1对全部数据通过。独立ROLLBACK将另一副本恢复到原PG_COLLECT SHA，并复跑第一条完整pass，与原baseline完整JSON逐字相等；主PGAS修改保留。

## 下一项有界工作

当前候选不进入训练、Formal或暴露DEV。下一项重新筛选一个会实质改变银行外typed路线生成及后续交付的具体步骤，并在冻新输入前先做最近先例与真实law/一次更新差分；不得复活本配方或重复PGAS小例。固定风简单能耗优先，强minmax ALNS、共同H独立新生成、公共bank、完整作者同风cap、原浮点公共T保持。G0/G3仍未过。

## 是否需要用户决策

否。<REMOVED_ENDPOINT>已重连；root独立执行；A路线优先顺序不变。当前均匀配方已封闭，不需用户操作。

## 方法来源边界

- [Lindsten, Jordan & Schön (2014), Particle Gibbs with Ancestor Sampling](https://jmlr.org/papers/volume15/lindsten14a/lindsten14a.pdf)：§3.1–3.2、Eq.3、Algorithm 2已给PGAS与祖先权重。本地读至这些方法段及相关web段，非全文逐页精读。
- [van de Meent et al. (2015), Particle Gibbs with Ancestor Sampling for Probabilistic Programs](https://proceedings.mlr.press/v38/vandemeent15.pdf)：prefix+suffix重建、自洽性拒绝和概率重算均已有。本地/网页读取对应§3.3、§4.1–4.3，非全文逐页精读。
- [Lindsten et al. (2015), Particle ancestor sampling for near-degenerate or intractable state transition models](https://arxiv.org/abs/1505.06356)：本轮仅读arXiv官方元数据与摘要；不据此宣称已核全文。
