# 本轮实际结果：完整路线分布查新与 normalizer 资格反证

2026-11-13。仅 root／<COMPUTE_HOST>。主对象 `PRETRAINED_FLOW_COMPOSITION_FOR_COMPLEMENTARY_ROUTES_V1` 未获 G0；项目 G0/G3 仍未通过，整体研究与 CCF-B／G8 目标未完成。原两科学 STATE、暴露人口与失败保留。

## 已证实事实

两份新直接全文 MOGFN 与 RBR 已覆盖 preference-conditioned TB、多模态候选及 reaching 混合；换 GFlowNet／偏好／温度没有我们新增的学习步骤。作者固定提交早于所读论文 v3，未认定为论文实验提交。完整证据位置与阅读范围见 PAPER_CODE_MODEL_MAP、READ_LEDGER。

此前“估计 normalizer 只造成全局缩放”的迁移前提，本轮有两个精确反例和两个不变对照。固定四个两终点数学 DAG，component law 和 reaching probability 准确，仅改变用于 component 混合的 Z 相对尺度：

|冻结输入|目标 law|修改后 law|精确 L1|原函数逐项最大误差|
|---|---|---|---|---|
|A_DIFFERENTIAL|1/2,1/2|19/30,11/30|4/15|2.220446049250313e-16|
|B_COMMON_SCALE|1/2,1/2|1/2,1/2|0|5.551115123125783e-17|
|C_UNEQUAL_TRUE_Z|5/7,2/7|19/24,5/24|13/84|1.1102230246251565e-16|
|D_IDENTICAL_LAWS|3/4,1/4|3/4,1/4|0|1.1102230246251565e-16|

<COMPUTE_HOST> BASELINE／MODIFIED／SOURCE／ROLLBACK 四阶段均 exit0。精确参考四例均 L1=0；作者原 `_scalarization` 的四组 float64 root 输入与修改后有理数一致。SOURCE runtime torch2.12.1+cpu、线程1，无模型或优化器。另副本回滚恢复 1/1 原 hash、BASELINE 逐字 stdout 与完整 JSON；修改主副本继续 `USE_ESTIMATED_Z=True`，备份保留。

受监督 child CPU 共 1.588938s，wall 共 1.662554s，峰值233244KiB。四次各限 CPU15s／wall20s／AS4GiB／每文件2MiB，未用预留的一次修复额度。传输、SSH、上层 supervisor 的开销不冒充 child CPU。原命令、输入、完整逐字输出与退出状态见 VERIFICATION.txt 与 server_evidence。

## 未证实假说

仍未证明完整物理路线分布学习能提供强 ALNS／同池精确控制之外的收益；没有新物理 headroom、训练充分性、6s/12s 性能或泛化证据。硬全图 cap 下的完整后缀条件化仍缺本项目的非直接、可计算新步骤。normalizer 反例不提供这一新步骤。

## 失败或关闭方向

关闭本次“迁移 MOGFN／RBR 即构成新路线机制”的切入，拒绝一般“各模型 Z 相对误差不影响混合目标”的资格前提。只改 Grid 缓存 zs 且保持 fs 不动不是本测试；完整 TB sampler 未执行。未否定准确 Z 的线性定理、论文性能、所有 GFN、RL 或天气路线方向。OpenAlex 两个 HTTP429 查询失败保留，未用它们证明无先例。

## 下一项有界工作

按 NEXT_BOUNDED_WORK 先核对一个完整后缀计算对象的具体新增运算及最近先例。普通条件概率／Doob 变换、已有 score／LOO、有限 station-bank 组合与 preference-conditioned TB 不重立。若写不出新增步骤，不生成另一套无判别力数学测试或训练。

本轮 0 新科学地图、0 作者求解／ALNS、0 物理质量评价、0 训练／checkpoint／Formal／子 agent。旧1200复现、48图、104环境矩阵、20交错、ECHO与完整进程工程未重跑；40身份／126比较、校准24/24满额不退款。

## 是否需要用户决策

没有新增问题。风域 cap A/B 已在前包 WIND_COMPARISON_PROTOCOL 提出且仍未答复；原 primary／两 STATE 不改，不重复提问，不默认批准依赖新 cap 的科学批次。该决策不阻止本轮查新和资格反证。固定风先行、应急后置；训练与 Formal 仍待 G0/G3、全新人口及资源准入。
