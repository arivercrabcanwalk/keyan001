# RSCC候选修订稿：factorized route-slot counterfactual credit

日期：2026-11-03。独立机制代理的公式自查修订。不是G0通过、训练授权、创新结论或预注册。原G4_CANDIDATE.md保持冻结原样，保留其梯度问题。

## 结论

原候选对一个flat joint policy `pi(d,i|s)` 使用依赖所选target `i` 的baseline `b(s,i)`。对target动作score而言该baseline随动作变化，因此一般不满足policy-gradient baseline的action-independent条件；原公式可能有偏。原冻结候选不能直接进入训练。

可以通过自回归物理动作修正梯度，但修正后就是已有的vehicle-then-node/two-decoder路线策略加标准条件反事实critic，**没有识别新的算法增量，故G0仍NO_GO**。以下仅作为若未来执行普通应用比较时正确的G4对照候选。

## 精确状态、factorized physical action与转移

输入固定station/mode及每站target集合。station state包含所有尚未服务targets、每个合法drone slot的current endpoint、open-trip energy/physical time、closed-trip route/duty摘要、剩余累计duty、电池、eligibility和station/type特征。

每个决策先从物理事件候选`u`选择：

- `visit(i)`，其中i是本站尚未服务的一个真实inspection target；
- `RETURN`，表示本站某架机关闭一个已打开的物理sortie。

然后从该事件的合法slot集合`D(u,s)`选择无人机d：

- `D(visit(i),s)`包含所有可由该slot/该station mode服务i，且追加i后直接返站仍满足coverage、单趟battery、该机累计duty的slot；
- `D(RETURN,s)`包含有非空open trip、返站合法的slot。

最终物理动作是`a=(u,d)`，即`(d,i)`或`(d,RETURN)`。不产生算法/搜索算子动作。visit把i从共享剩余集删除并追加给d的route；RETURN将d的open trip闭合、重置trip energy/current endpoint但累加duty，不改变其他slot。最后target后的自动返航或显式RETURN只选其一并冻结。

station/mode/target-to-station ownership固定；DABS的SD/LD target ownership由每次合法visit事件逐步形成。无同步/共享charger/makespan，不能借factorization引入新物理约束。

## 合法条件反事实学习信号

定义集中式state-action critic `Q(s,u,d)` 为从当前prefix开始遵从政策完成站内完整路线时负的原始运行总费用期望。route reward为负精确operating-cost增量、terminal含全部返航；评估仍使用完整evaluator/original objective。

策略分解为`pi_U(u|s) pi_D(d|s,u)`。两个决策头的score term分开，使用不同baseline：

    Qbar_U(s,u) = sum_{d in D(u,s)} pi_D(d|s,u) Q(s,u,d)
    b_U(s)      = sum_{u'} pi_U(u'|s) Qbar_U(s,u')
    A_U(s,u)    = Qbar_U(s,u) - b_U(s)
    b_D(s,u)    = sum_{d' in D(u,s)} pi_D(d'|s,u) Q(s,u,d')
    A_D(s,u,d)  = Q(s,u,d) - b_D(s,u)

更新为`-A_U*grad log pi_U(u|s) - A_D*grad log pi_D(d|s,u)`的策略损失（critic目标使用冻结的完整episode原费用returns/有正确估值的GAE）。`b_U`只依赖s，不依赖当前u；`b_D`可依赖u，因为它仅作为条件slot policy对d的baseline，且不进入event-policy score。实现共享参数时仍保持这两个合法score项分开，做有限MDP exact expectation梯度对拍。

Critic反事实action values可以由on-policy completed returns拟合；若使用paired counterfactual rollouts生成label，其全部分支时间必须计训练/查询开销，且不得把DP teacher只给RL。部署时如需对所有u/d枚举critic logits，计入策略推理时长；无需在线执行环境分支仿真。

## 相对先例及原创性边界

- Li et al. arXiv2110.02629v2已有异构vehicle-node two-decoder，逐step明确联合vehicle/customer选择并考虑各partial route状态与返depot。因此上述因子动作、slot-target和full fleet context全部已有近邻。
- COMA counterfactual multi-agent policy gradient已有条件于其他选择的action-conditional baseline概念；本修订正是标准条件反事实信用形式，不主张新的credit算法。
- PARCO arXiv2409.03811v3已有多agent route communication、竞争客户和pointer conflict handling。DPTARL已有inspection target/return/energy pruning/long-horizon RL。
- 本题将coverage、SD/LD、trip flight+target energy与累计duty放进动作可行集，是LRPHSD应用约束；尚未找到超出模型适配、可证明或可测的非直接算法增量。

## 预测、资源与拒绝标准

如root之后决定把它作为基线性G4候选而非创新稿，比较同一station inputs、同一因子动作域、same masks、same encoder/parameter budget、same training maps/updates/total compute：

1. standard factorized PPO/GAE；
2. factorized PPO + RSCC conditional credit；
3. Li-style two-head vehicle-target PPO复现/适配，区别训练信号；
4. route-safe greedy/best insertion、strong station ALNS/SISR；
5. 完整station partition-DP或有界DP/branch-and-bound作为G2/G3强非RL；同资源beam与BC/监督控制。

至少3个独立training seeds，3个selected models全部评测；新开发地图，不用旧24图作阳性开发或Formal。完整objective在6s和12s均需平均改善≥0.3%、map-bootstrap95%下界>0、地图胜负平衡、独立可行100%、受控overrun；credit计算、训练、模型加载、critic查询/推理、paired rollout及所有失败均如实入账。

可推翻预测：若RSCC相对同架构standard PPO无稳定提升，或提升仅来自额外compute/paired rollout，学习-credit假说失败；若station exact/同资源partition-DP相当或更优，RL相对最强非RL失败；若效果不落在LD/SD竞争且route remainder确实改变的station strata，所谓slot-credit作用机制被否证。失败全部保留，不补训练seed救阳性。

## 独立自审的最终决定

这是一个数学上可修正、实验上可证伪的G4训练信号消融候选，但它是COMA-style baseline在已有heterogeneous vehicle-node autoregressive route policy上的适配，不是G0的新方法。不能因为formula正确、种子多或性能有收益，就把它升级成算法原创。当前结论：保留为可选G4实验条件；**不通过G0，不开始该训练**。若目标只要求一篇特定问题应用的RL实证研究，主张也须依最终全文查新和Formal结果严格缩窄。
