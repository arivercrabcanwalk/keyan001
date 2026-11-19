# 从真实失败到下一次物理路线更新

日期：2026-11-14。状态：`DESIGN_ONLY / NOVELTY_UNESTABLISHED / G0_G3_UNPASSED`。

本文件只交付源码定位、可证伪假说和一份待登记的 TRAIN-only 小诊断/一次学习步骤。本轮没有运行模型、梯度、评分、地图生成、作者求解、ALNS 或远端科研；没有重算旧统计。Mac 只做现存材料阅读与本文件写入。root 统一安排 <COMPUTE_HOST>；本稿不授权新人口、训练、G4 或 Formal。

## 1. 最重要的判断

旧动态 J 的主要可定位失败是“学到的动作差分没有跨过部署 argmax”，其中一部分还存在确定的函数类硬障碍。它不是“没有 optimizer”。但**当前固定风 A 不能直接沿用旧 ±6 限幅根因**：可复用网络已有无硬限幅输出头，固定风新循环仍是未执行规格。本轮应检验的是：在同一新 TRAIN 物理前缀上，是否存在一条 T 后、全图 cap 合格且更好的 TARGET/RETURN 分支；若存在，学习后是否真的把部署排序翻过去，并从空路线产生新的同趟关系或访问次序。

下一次最小学习步骤建议为：**冻结同一后续策略，用成对物理分支得到真实交付差，再做一次条件策略梯度和最小部署 margin 修正。** 它不是 best-of-K 改名，不要求精确 T 纤维 q，不通过改网络名字获得创新资格。分支续接、成本敏感分类、偏好学习和最小范数 margin 更新各有先例；待检验的具体组合必须同时与同信息 margin-only、普通条件 PG、终局 PG 及无学习控制对照。组合是否有新算法增量和跨图收益保持开放，不能因组件常见就一概否定，也不能因组合名称新就立为原创。

## 2. 已有证据直接复用：不再做一轮旧 J 诊断

|事实|现成证据|它允许/不允许的推断|
|---|---|---|
|SCST/LOO 各 3 seed 全选 initial；768 更新、960 保存轨迹、1184 eval|`20261105_deep_revision/REPORT.md` §3、§5|所选结果无 actor 学习收益；不说明所有 route-RL 无效|
|192 条 actor-last eval 中 148 条物理动作序列等于 initial；192 条 SCST TRAIN 采样中 151 差、41 好|同报告 §7；`results/SAVED_SUPPLEMENT.json`|参数变动与部署路线改变分开；采样差不是探索无效定理|
|旧 32 步模型在监测轨迹 2022 个多候选 callback 只改选 7 次；典型网络动作差分远小于 prior margin|`20261105_bottleneck_diagnosis/REPORT.md:21–33`|已有直接的排序通道证据；本轮无需重读权重再算一遍|
|旧 3 seed × 256 SCST、16 state/178 分支、bounded/unbounded 拟合均已完成|同报告 §1、§3–4、§8|“延长旧训练”“去限幅后能否拟合旧 16 状态”已经有答案，不重跑|
|两个 DDQN seed 胜弱零 Q initial、仍输 oldbeam；旧有限动作参考排序弱|`20261105_deep_revision/REPORT.md` §5、§7；bottleneck 报告 §5|TD loss、权重改变、胜弱初始化均不能代替强基线与真实排序|
|旧结果是动态联合 J，不是目前固定风同风作者 cap 下的 M_return|`20261105_route_claim_audit/REPORT.md` 的 metric boundary|旧结果不能证明当前 cost-cap 或公共 T 是失败原因|

本轮只引用上述保存结论，不生成旧曲线、不重新评价旧地图、不补旧 seed、不恢复关闭配方。

## 3. 当前固定风 actor 到底有没有旧硬界

以下行号来自本轮实际读取的本地原文件。路径以工作区 `<LOCAL_PATH>` 为根。

|代码对象|实际 scoring 分支|确定结论|
|---|---|---|
|`joint_weather_emergency/20261105_deep_revision/MODIFIED_FILE/route_v2.py:42–51`|`prior + 6*tanh(r/6)`；末 head 零初始化|旧动态 J 的 bounded actor。两个动作残差差严格小于 12；若 prior 第一比 b 高至少 12，b 永远不能严格成为第一|
|同包 `joint_core.py:35–42`|紧急任务 prior 可接近 30；RETURN prior 为 −1|旧硬界能锁住本来物理合法的动作；不是 mask 或电池不可行|
|`route_rl_research/20261103/source_snapshot/route_rl/policy.py:18–38,60–76`|target/RETURN 的可训练线性末 head；hidden 有 tanh，最终 logit 没有固定 ±6 外界，也没有外加固定 prior|可复用全支持神经底座；不能从 hidden tanh 推出固定的跨参数 logit 上限。它是历史 schema，不能未经适配声称已是新固定风 joint-slot 生产 actor|
|`route_rl_research/20261103/return_makespan/g24_weather_nfz/weather_policy.py:26–42`|query/key + 可训练 score_bias；合法 logits 未限幅|另一个无旧 ±6 硬界的可复用物理 actor；不代表本轮有其新固定风训练结果|
|`joint_weather_emergency/20261106_D_C2_engineering_v2/MODIFIED_FILE/route_learning_candidate.py:45–72,75–89,131–133`|`bounded_reference` 才用旧式；默认 `mode='unbounded'`，为 `lambda*prior+r`；`anneal_only` 是无学习控制|项目已经实现拆开的 scoring 分支，不能重复把“去限幅”包装成新机制。保存部署 metadata 是必要条件，state_dict 本身不含该分支|
|`joint_weather_emergency/20261106_E_learning_label_audit_v2/MODIFIED_FILE/preference_route_trainer.py:108–141`|无界末 head + `lambda*prior`，无旧 ±6|后续 engineering actor 也不能自动归为 bounded；该文件仍是旧动态 J/多目标工程来源，不直接搬其目标进入固定风 A|
|`joint_weather_emergency/20261113_service_clock_particle_screen_v1/SOURCE_MAP.md:16–21`|明确指向以上复用网络|证明继承链，不证明当前已冻结一个新固定风 learner|
|`joint_weather_emergency/20261113_multitrip_iteration_design_v1/MODIFIED_FILE/PHYSICAL_ROUTE_ITERATION.md:3,51–89`|完整物理循环/PG 仍为未执行规格|本轮材料未建立“固定风 A 沿用 bounded residual”的事实；执行前必须冻结具体 adapter、action schema、head、mode、prior_lambda 和源码 hash|

因此根因分两层记录：`LEGACY_HARD_BOUND_CONFIRMED` 只属于旧 J；`CURRENT_FIXED_WIND_REACHABILITY_UNMEASURED` 属于新域。无硬界不等于任一动作在冻结 encoder 的线性 head 下都可成为第一，更不等于有限更新能学会它。

## 4. 可复用的最小 reachability 诊断

该诊断在新 TRAIN 前缀上完成，不恢复旧 checkpoint 或旧 16state 训练。root 先冻结实际 actor，并从完整 greedy 轨迹按下文确定规则取前缀。

对每个合法动作 a 保存实际 logit `z(s,a)`、prior、mask、动作身份及末 head 的特征 `phi(s,a)`。冻结 encoder 后，把可训练末 head 写成

\[
z_w(s,a)=c(s,a)+w^T\phi(s,a).
\]

target/RETURN 分开的末 head 可写成参数和特征的 direct sum；c 包含冻结的 prior 和其它冻结分支。只对真实 adapter 的末层成立，不把整个非线性网络假称线性。

对一个已证更好交付的动作 b：

1. **旧式解析界**：只有当前冻结分支确为 bounded 时，才用 `p(a)-p(b)>=12` 记录硬障碍。无界分支不调用这条判定。
2. **特征混同**：若 `phi_b==phi_a` 且 `c_b<c_a`，冻结末 head 无法翻转这对动作，记 `EXACT_HEAD_FEATURE_ALIAS`。这不是整个网络不可表示的证明。
3. **最小末 head 可达性**：解下面的最小范数问题，并用实际 forward 逐动作验证：

\[
\delta_b^*=\arg\min_\delta\tfrac12\|\delta\|_2^2,
\quad z_w(s,b)-z_w(s,a)+\delta^T(\phi_b-\phi_a)\ge m\ \forall a\ne b.
\]

冻结 `m=0.1` logit。返回可行见证、全部实际 margin、最大 logit 变化、求解时间；数值求解未找到解只记 `NUMERIC_UNKNOWN`，除非另有线性不可行证书。没有固定 encoder/head 可行性证据时，不从 optimizer loss 猜函数类根因。
4. **更新是否真正跨 margin**：在同一个保存前缀，比较 `argmax(z_before)`、`argmax(z_after)` 和最小 b-vs-other margin；随后分别做“固定前缀后自由续接”和“从空路线自由构造”。局部翻序却从空路线不再访问该状态，单列 `PREFIX_DISTRIBUTION_SHIFT`。

仅一个 pair 时，忽略其它竞争动作的解析步为

\[
\delta=\frac{[z_a-z_b+m]_+}{\|\phi_b-\phi_a\|^2}(\phi_b-\phi_a).
\]

它只保证 b 超过 a，不保证 b 超过全部动作，所以实际更新使用上面的多类约束或明确报告局部 pair 结果，不能把 pair 翻转冒充部署 argmax 翻转。

## 5. 新的物理采样步骤：TARGET/RETURN 成对续接

### 5.1 不变的输入、输出和完整目标

输入为一张新登记 TRAIN 图 I、公开固定风 w、完整作者同风解 R_w、固定站型/部署/target-station、原 typed 环境、既有公共 T/bank/完整 scorer，以及冻结 actor `theta0`。RL 仅输出 `(slot,target)` 或 `(slot,RETURN)`；站顺序固定；电池逐趟，RETURN 不清零累计 duty。局部合法 mask 不等于余下全图可完成。

每条完整 raw schedule x 都保存原 scorer 结果，再经未改 T 得 y，重做完整 scorer。对同一固定输入定义实际交付效用

\[
U(y)=\begin{cases}
[M(R_w)-\min\{M(R_w),M(y)\}]/M(R_w),& y\text{完整、物理可行且 }C(y)\le C(R_w)+10^{-7},\ M(R_w)>0,\\
0,&\text{其它情况}.
\end{cases}
\]

失败、超 cap、超时和未完成都保留原始结果与固定 ID，交付回到 anchor；不对合格子样本重归一化。`M(R_w)=0` 时 U=0。失败的不同原因作为诊断字段保留，不靠临时 penalty 改合同。

### 5.2 每图两个确定前缀

从 theta0 的完整 greedy 轨迹按动作索引选：

- P_RETURN：最早一个同一 slot 上同时存在合法 TARGET 和 RETURN 的前缀；必须已有非空开放趟。
- P_ORDER：P_RETURN 之后最早一个至少三个合法 TARGET 的前缀；没有 P_RETURN 时从初始动作起找。它和 P_RETURN 不是同一 state。

不存在者记 `NO_ELIGIBLE_PREFIX`，不换图、不追加前缀、不按分支质量挑 state。候选顺序按实际稳定 action ID，不通过 target ID 伪造可交换性。

设 a0 为该前缀的当前 greedy 动作。P_RETURN 处构造 boundary 动作 b_boundary：a0 若为 TARGET(d,j)，取同 slot RETURN；a0 若为 RETURN(d)，在同 slot 合法 TARGET 中均匀取一个。若该规则无合法 boundary，则相应质量保留但用下述 uniform 部分；记录真实 q。抽一个非 greedy 动作 b：

\[
q_s(b)=\tfrac12 q_{boundary}(b)+\tfrac12\operatorname{Unif}(A(s)\setminus\{a0\})
\]

有 boundary 时使用上式，无 boundary 或 P_ORDER 时使用全部非 greedy 合法动作的 uniform。q 对每个非 greedy 合法动作为正；它不同于已关闭工程 sampler 的合法排序首尾二选一。后者不能当全项目 actor 缺乏 full support 的证据。

分别强制首步 a0 和 b，随后立即回到同一冻结 theta0 的实际物理 policy，执行到完整结束/真实失败。两分支均覆盖剩余全部站与目标，不能只评分局部趟或把其它站免费换成事后最优。每个 pair 用两组独立后缀随机流 u1/u2。

### 5.3 共随机数必须保留正确边际

使用 action-addressed Gumbel：由 `(input_hash, seed, prefix_ID, replicate, relative_step, stable_action_ID)` 生成每个合法动作的独立标准 Gumbel，选择 `argmax_a(log pi_theta0(a|state)+G_a)`。pair 两臂共用同地址随机场；不同 state 的合法集合仍用各自真实 mask。每臂单独的边际仍是 theta0 的 categorical law，共随机数只配对方差；不能把两条路线强行对齐到相同后续动作，不能在动作数变化后复用“第 j 个随机动作索引”。

这次物理操作能改变当前趟的终止位置，继而改变目标同趟关系和后续访问顺序；它是否真的改变这些对象必须由保存的完整路线证明。分支不保证更好，不补抽失败，不以几何距离更近替代完整 M/cap。

## 6. 四种失败机制分开观测

每个 pair 保存 `raw_action_hash`、带 typed slot 的 raw 完整 schedule、目标同趟关系与有向趟内弧、T 后完整 schedule、raw/post 的原 scorer C/M、cap slack、原始失败/退出原因、动作 logit/margin、q 和后续随机场身份。最终交付前的 bank/master 结果另存，不能把 bank 未选中等同 T 合并。

|机制|支持它的最小对照观察|可推翻它的观察|
|---|---|---|
|探索不足|强制 b 的两次后续均出现 T 后 cap 合格改进；同量普通 on-policy 从空样本没有访问相应动作/新分组；q 与 pi 说明该分支质量有真实覆盖缺口|普通样本已频繁产生同类合格改进，而部署未改：转查排序/信用。4 样本的未访问只是该预算下未覆盖，不能声称概率为零|
|动作排序没有改变|更好、可达 b 已进入训练信息；更新后在完全相同 state 的 b-vs-top margin 仍≤0；权重或 loss 变化不能替代这条记录|同 state 已翻序，仍无完整收益：转查续接分布/目标平坦，不再称单纯 argmax 问题|
|cap 拒绝|完整物理分支 T 后 M 更小、但原字面 `cost_within_cap` 拒绝；保留完整 C 和预算差值；还需有跨站补偿机会的独立标准控制，不能只做单站立即接受|合格改进已存在却学不到；或大量超 cap 路线本来 M 就更差。不能把“超 cap 比例高”本身当主要因果解释|
|公共 T 抹平|x0!=xb，但原 T 输出完整 y0==yb，或“raw M 的差异在 T 后消失”且两端 T 后完整结果均已记录|T 后仍有不同目标分组/趟内次序和可交付优势。只比较 M 相同不构成精确纤维合并证据|

四类标签可重叠，报告联合交叉表和全部 pair 分母，不用优先级强塞成四个互斥百分比。另保留 `PHYSICAL_DEAD_END`、`OBJECTIVE_TIE_NONBOTTLENECK`、`ANCHOR_FLOOR_TIE`、`BANK_REDUNDANCY`、`TIMEOUT`、`PREFIX_DISTRIBUTION_SHIFT`。这些情况不能误归于 T。

公共 T 的本项目代码边界很具体：`20261113_action_conditioned_repack_g0_v1/frozen/prefix_sampler.py:71–99` 的 rebalance 仅把完整趟分给 typed slot，保留目标分组及趟内顺序；`PHYSICAL_ROUTE_ITERATION.md:45–49` 同样明确这一点。纯 slot 负载变化可能被 T 吃掉；T 不会直接把新目标分组改回旧分组。该工程 T 有 14 趟限制，正式实现不得偷偷承接这个工程上限；执行必须绑定 root 已冻结的共同 T 身份。也不假设 binary64 下 T 幂等或成本字面完全相同。

`20261113_reward_pushforward_orderstat_screen_v1/DERIVATION.md` 已证明普通 on-policy `E[R(T(x))*grad log p]` 仍正确。T 合并只说明信息/效用可能平坦，不是 PG 有偏；本诊断不重新引入精确纤维 q 作为普通 RL 门槛。

## 7. 一次确实面向部署翻序的学习步骤

### 7.1 条件动作差分 PG：准确写明目标和抽样 law

冻结 roll-in、全部 suffix policy 和 encoder 为 theta0，只更新实际神经网络末 head w。对一个 pair 定义

\[
\widehat{\Delta Q}_s(b)=\tfrac12\sum_{r=1}^2[U(Y(s,b,u_r;\theta_0))-U(Y(s,a0,u_r;\theta_0))].
\]

它是冻结后续策略的一步偏离参考，不是真实最优 Q。在 q 抽取 b、后续流独立于 b 的条件下，

\[
\widehat g_s=\frac{\pi_{w_0}(b|s)}{q_s(b)}\widehat{\Delta Q}_s(b)\nabla_w\log\pi_{w_0}(b|s)
\]

是局部目标 `sum_a pi_w(a|s) Q_theta0(s,a)` 在 w0 的无偏 score 估计；基线 Q(a0) 对动作 a 的求和恒等式为零，a0 的差本来为零，所以无需把 b 当作 on-policy 样本。两个后续共享随机数不改变各臂均值。把 4 个 FIT 前缀槽位取均值后，以预冻结 `eta=1e-3` 做一次普通 SGD，得到 w_bar；缺前缀槽位贡献零，不把分母缩成幸存 state 数。无 importance clipping，不用赢家才反传，不把 forced action 冒充来自 pi。

这是冻结 roll-in/suffix 的条件策略改进目标，**不是**对完整 theta 的无偏整轨迹 PG；后缀与前缀的导数没有被包含。该边界写进日志。普通 full-trajectory PG 是独立控制，不因本式而被替代。

### 7.2 部署 margin 修正：只对已观察可交付分歧施加约束

仅在同一 FIT pair 的两次 replicate 都满足以下条件时，将 b 加入约束集 W：

1. b 分支完整、原 scorer 物理可行、T 后全图 cap 合格；
2. `U_b > U_a0` 且相对 M 改进至少 `10^-4`；该门槛只抑制数值/微小噪声，不改 cost tolerance；
3. T 后完整路线不同，且至少一个目标同趟关系或有向趟内访问弧发生变化；单纯 slot 标签重排不算路线构造证据。

在 w_bar 周围解一次共享末 head 最小修正：

\[
\min_\delta\tfrac12\|\delta\|^2,\quad
z_{w_{bar}}(s,b)-z_{w_{bar}}(s,a)+\delta^T(\phi_b-\phi_a)\ge0.1
\quad\forall(s,b)\in W,\ a\ne b.
\]

两次 replicate 都正只是本次固定筛选代理，不是总体 `Q_theta0(s,b)>Q_theta0(s,a0)` 的已确证结论，也不是两次抽样足以消除选择偏差的声明。W 是看过回报后的筛选集；§7.1 的无偏性质只属于筛选前那一个条件 score 估计，**不延伸到 margin QP、筛选后的更新或其最终组合**。因此必须独立验自由路线与锁定 READOUT，并保留同数据 margin-only 强控制。

所有 W 一起解，不能删冲突标签只留下好拟合状态。无 W 时保存 `NO_ROBUST_DELIVERABLE_PAIR`，不声称做了有效 margin 更新。若不可行/数值未知，保留 w_bar 并记录全部约束；不调 margin、不补 prefix。若见证可行但任一 FIT 合法动作 logit 绝对变化超过冻结的 2.0，则记录 `HEAD_SHIFT_OVER_LIMIT`，也保留 w_bar；该 2.0 是本次保守更新准入界，不是网络函数类硬界。最后必须由真实 forward 确认所有拟施加动作 margin≥0.05；未达到者为验收失败。

该步骤确实把“更好分支是否成为实际 greedy 动作”变为可验证事件，而不是希望 terminal loss 降一点会自然翻序。它没有把 T、cap 或 scorer 改成可微近似，也没有输出算子。冻结 encoder 的本次诊断不解决跨实例表示学习；若只在 FIT state 翻序、从空路线及锁定 READOUT 不改善，只得到局部可达性结果。

### 7.3 采样到更新的可复用伪代码

```python
def one_registered_step(actor0, new_train_inputs, common):
    # 全部模型/物理/评分调用仅在 <COMPUTE_HOST>；只有 root 冻结准入后运行。
    ledger = collect_greedy_and_ordinary_samples(actor0, new_train_inputs)
    prefixes = first_return_and_later_order_prefixes(ledger.greedy)
    pairs = []
    for prefix in prefixes:  # 缺前缀/死路保留固定 ID，不替换
        a0 = actor0.greedy(prefix)
        b, q = draw_registered_non_greedy_action(prefix, a0)
        pair = paired_full_map_suffixes(actor0, prefix, a0, b,
                                        common_action_addressed_gumbels=True,
                                        replicates=2)
        pairs.append(common.score_raw_T_cap_and_delivery(pair))
    save_all_attempts_before_any_update(ledger, pairs)
    # READOUT 标签封存；只有 2 张 FIT 图的最多 4 个前缀进入学习。
    fit = select_registered_fit_ids(pairs)
    w_bar = one_exact_conditional_pg_step(actor0.frozen_encoder, fit,
                                         importance_pi_over_q=True, eta=1e-3)
    constraints = robust_post_T_physical_divergences(fit)
    w_new, status = one_verified_minimum_head_margin_projection(
        w_bar, constraints, margin=0.1, max_logit_shift=2.0)
    # 学后从空路线生成；不回放 forced b 冒充 actor 自主决策。
    return evaluate_from_empty_with_shared_T_cap_deadline(w_new), status
```

此代码是完整步骤规格，没有在本轮运行。所有随机 law、失败 ID、日志与 numerical solver 版本需进入 root 的实际登记。

## 8. 最小登记矩阵与同计算量控制

### 8.1 人口与取样

建议的最小新登记人口为 4 张全新 TRAIN 图、每图 1 个公开固定风；2 FIT、2 锁定 READOUT，分割由生成 seed/ID 决定，见任何 solver/route 结果前冻结。READOUT 仍属于 TRAIN 机制诊断，既不是 DEV，也不是确认性泛化样本。每图最多 2 活跃站、每站最多 12 目标；站型/异构电池/简单能耗沿冻结参数，完整同风作者 R_w 每图一个。身份不得复用 40/126、旧 24/24 校准、旧动态 J 四图/16state、旧关闭工程几何或暴露 DEV。若当前没有新增人口资源准入，就只保留本设计，不挪用旧额度执行。

三个独立新诊断 seed：`260141/260142/260143`；它们是本提案的待登记名称，不是已创建运行。每 seed 的上限：

- 4 greedy 从空完整尝试；每图 4 条普通 on-policy 从空尝试，共 16。
- 8 个预定前缀 × 2 分支 × 2 后缀 replicate，至多 32 个完整续接尝试。
- 合计至多 52 次 raw 完整构造尝试；缺 prefix/失败计入固定 ID，不补抽。全 3 seed 至多 156 次。

每份 raw 与 T 后解各一次原 scorer 和一次独立复核，至多 624 次 pre-update 原 scorer 调用。此为调用上界，失败无法形成完整解时留 sentinel；不把空 scorer 次数当成功率。

### 8.2 必须同场的五个学习控制

|arm|拿到的信息和物理组件|更新职责|
|---|---|---|
|C0 无学习|同一完整 TRAIN 数据生成成本、同 inference sampling/公共 T/bank/cap/deadline|参数冻结；部署可把完整预算用于自己的新路线生成，不承担虚构等待|
|C1 普通终局 PG|同网络、同 initial；只用两张 FIT 图的 8 条普通 on-policy 轨迹及其独立 greedy baseline，READOUT 的另 8 条封存|按真实终局 U 做一次标准 SCST；forced 分支不能无权重混作 on-policy|
|C2 条件 PG|与 M 完全相同的强制 pair、q、后缀 law、post-T/full-cap 标签|只做 §7.1 的一次 PG，测其是否跨部署 margin|
|C3 margin-only / 成本敏感监督|与 M 相同的 pair、W、encoder、margin QP 和头部位移界|从 w0 直接做 §7.2，完全没有 PG；这是强监督-only控制，不能用一个难以翻序的弱 CE 步替代|
|M 条件 PG + margin|相同数据和物理组件|一次 §7.1，再一次 §7.2；本候选的唯一组合差异|

所有 arm 使用同一 FIT/READOUT 分割、相同 actor schema/encoder initial/hash、信息、prefix/后缀数据、失败分母、T、bank、scorer；只变更新。theta0 来自新冻结的实际 actor 初始化和声明的公共 prior，不加载旧 J 权重；若有 prior_lambda，本次固定不退火，数值写进 freeze。C1/C2/M 的 PG 都冻结 encoder、同为一次 `eta=1e-3` SGD、无 entropy 项；C1 的目标梯度为 8 个 FIT 轨迹的 `(U-U_greedy)*sum_t grad log pi(a_t|s_t)` 的固定分母均值。C3 使用同一 W 和 QP 参数，从 w0 而非 w_bar 起步。READOUT 的所有分支/普通轨迹标签均在更新前封存，不进入任何梯度、W 或模型选择。

数据可物理缓存共享，但各方法的资源账均收取完整共同采集费用，不能给 M 免费 oracle。每 arm/seed 优化硬上限 10s，solver/梯度/导入/验证均计；报告真实用时和操作数。相同上限不等于已证明实际等计算量，故部署比较必须另按完整 6s/12s 计时。C0 资源更省本身是结果，不给学习方法补加预算。

五个 arm 均在 4 张 TRAIN 图上从空路线做 6s/12s，3 seed 合计 120 次完整部署调用。root 的强 minmax ALNS、共同 H 内独立新生成控制各在相同输入、相同完整预算、对应 seed 上运行，合计 48 次；两者保持原生跨 slot/分趟/访问顺序、跨站完整费用补偿能力，不降为 fixed-owner、仅单站立即接受或旧 bank 重组。比较规则预冻结，不能每图挑有利对手。共同 H 的 deadline 接线正确性仅是工程资格，不作为科学增益，也不自动通过 G3。

若只是 M 优于 C2、但不优于 C3，则解释为 margin/监督改进，没有 RL 独立增益；若只是所有学习 arm 的 raw 路线更好而 T 后无差，则没有最终交付增益；若 C0/强 nonRL 同预算更好，候选仍失败。普通 best-of-K/OrderGrad 可在后续已准入完整比较中作标准强控制，本诊断不能以“新增 top-1 loss”替代 C2/C3 或获得创新身份。

### 8.3 资源上界与停止条件

全部串行 <COMPUTE_HOST>，CPU 1 线程，单进程内存 2GiB，GPU 不需要。root 冻结一次总预算，建议不超过 3600 CPU 秒和 3600 墙钟秒，包括：

- 新 4 个作者风 anchor 每个≤120s，共≤480s；不是免费预处理，T_anchor 单列。
- 每 seed 的 greedy/on-policy/fork 采集≤120s，共≤360s。
- 四个更新 arm × 3 seed × 10s≤120s。
- 5 arm × 4 图 × (6+12)s × 3 seed=1080s 部署额度；进程清理/验收额外预留计入总额。
- 两个强 nonRL × 4 图 × (6+12)s × 3 seed=432s。
- 其余审计/独立 scorer/序列化/进程启动/退出/证书预算合计≤1128s；这些不是可挪给额外实验的空白额度。到总上限就停止，记录所有未执行 ID。

任一源码/协议修正必须先冻结并保留首失败；最多一次只修验收映射的 repair，不改物理输入、cap、目标、m、步长、位移界、图或 seed；不重跑成功 timing。出现以下任一项停止本配方，不扩 K/epochs/地图救结果：

1. action/schema/随机边际/完整物理回放/原 scorer 不一致，或 root 的 deadline 工程资格未满足。
2. 四个 FIT 前缀没有一个两 replicate 都存在 T 后 cap 合格、真实分组/顺序改善的 pair：记 `NO_SIGNAL_IN_REGISTERED_BUDGET`；不宣称路线空间无机会。
3. 受约束 head 更新没有可验证翻序，或只改 slot 标签、不改变完整物理分组/次序：当前更新配方没有实现目标。
4. 翻序仅出现在保存 FIT state，从空路线或两张锁定 READOUT 没有改善：记录局部可达、自由策略未改进；不延训。
5. M 在三 seed 的 READOUT 全图可交付 U 上没有比 C0/C2/C3 中最强者严格正的平均配对差，或新学结果仍不及强 nonRL：关闭本配方的学习/效率主张。4 图小诊断不报告确认性 p、论文 CI 或“5%达标”。

通过这些门槛最多支持“有一个值得进一步冻结研究的机制组合”，不是 G0 原创证明、G3 全通过、RL 胜强 ALNS、G4 自动准入或 Formal。

## 9. 主源近邻：按实际操作逐步比较

本轮主要复用已保存主源文本，没有把摘要缺口当创新。已尝试再次打开 LOLS 主站 PDF；工具没有返回正文，本次方法依据仍为已归档主源 `sources/LOLS.txt` 的 Algorithm 1/式(2)，不记录一次新的全文精读。

|最近来源/现成实现|相同的实际步骤|本稿特定差异；必须承担的比较|
|---|---|---|
|LOLS，ICML 2015，Algorithm 1/式(2)；本地 `20261113_policy_continuation_g0_v1/sources/LOLS.txt:136–225`|learned roll-in、单步动作偏离、完整 rollout、按终局 cost 训练成本敏感 learner|本稿只取两个确定物理前缀、q 抽非 greedy 动作且写 pi/q；suffix 是冻结 actor，共 action-addressed Gumbel；末 head 先条件 PG 再强制交付有效动作跨 margin。LOLS 的一般 learner 框架可以容纳许多本稿组件，不能据应用名宣称超越它。C3 同数据/同约束的成本敏感 learner 是直接强控制；若与 C3 实际同更新，独立增量为零|
|UCPO，AAAI 2026，DOI 10.1609/aaai.v40i43.41017，式(1)–(3)/Algorithm 1；同包 `sources/UCPO_final.txt:190–335`|完整候选可行优先排序、目标改善偏好、神经策略参数更新|本稿保留原物理 mask 与 literal cap，不用其 mask-free/拉格朗日次序替代；作用在同前缀物理动作的实际部署 margin，不是完整 trajectory log-likelihood 偏好。可行性分类/偏好本身不是新贡献。后续完整研究应有同 pair 的 UCPO/BOPO 风格控制，不能只比弱 CE|
|OrderGrad，arXiv:2606.06096v1；`20261113_reward_pushforward_orderstat_screen_v1/SOURCE_MAP.md`|有限 K/order-statistic likelihood-ratio，top-1/best-of-K|本稿不声称新的 top-1 估计器；局部 frozen-suffix 条件目标与 head 翻序是不同检验对象。后续若改 best-of-K，按其标准控制计完整实际预算|
|本项目 `20261105_bottleneck_diagnosis` 与 D_C2 unbounded candidate|旧 bounded 可达性检查、强制一步续接、去限幅/退火、原 J 一致信用|本稿没有重开旧 16state/178branch/256update，也没有再把去限幅算创新；新对象是固定风 full-map cap/T 下的可交付 TARGET↔RETURN 分歧和一次确实翻序的更新|
|本项目 `20261113_policy_continuation_g0_v1`、`20261114_route_column_feedback_screen_v1`|公共 bank/master 下终局/删除信用、完整路线生成与普通 REINFORCE|本稿不把 master marginal 当新奖励，也不重跑其饱和池；直接在物理前缀分支检验排序/生成改变。bank 未选中单列冗余，不冒充 T 合并|

来源身份与原读范围以既有 SOURCE_MAP 为准。本稿没有穷尽文献，不能断言该组合世界首创；也没有依据“LOLS 足够通用可表达”就证明该组合无价值。合理的 next step 是先用这份最小矩阵回答一次实际物理学习问题，若 C3 已完全解释效果，就把它如实留为标准策略改进控制。

## 10. root 可复用的接续指令

```text
先核定固定风 A 的具体 actor/adapter/hash/mode，不把旧 J ±6 硬界当新域事实。
旧 bottleneck 报告已有 256步、16state178分支和bounded/unbounded拟合，直接复用。
root 统一 <COMPUTE_HOST>；本稿是设计，不批准新人口或训练；旧40/126、校准24/24、DEV和失败不动。
若 G0/G3及新资源合同允许小诊断，冻结4张全新TRAIN图（2FIT/2READOUT）与完整同风作者anchor。
按确定前缀做TARGET/RETURN与访问次序成对物理续接，记录raw/T/cap/margin，不补抽失败。
同一批数据比较无学习、终局PG、条件PG、margin-only、条件PG+margin；强ALNS/共同H完整预算保留。
分别判断函数类障碍、探索、未跨排序、cap、T、非瓶颈max、anchor floor与bank冗余。
任何局部翻序必须再验证从空路线的完整交付；共同H deadline工程只证明接线，不作科学增益。
候选若不胜同数据margin-only或强nonRL，不延训/调参；保留失败，G0/G3/Formal状态不自动改变。
```

写入者任务范围仅此文件；其它项目源码、状态、报告与运行锁均为只读。本文件的公式/计数是未执行登记草案，不是新的数值结果。

## 11. 对 AIR2 的唯一一次交叉反驳与归因边界

2026-11-14 接续附记。已只读交叉文件：`<LOCAL_PATH>`。对方已明确 pre-action 表到 post-force commit 的转换、两个完整原趟合计≤8含真实前缀、≤2替代趟不覆盖早 RETURN 后需3趟、旧域 union、局部 row 不提前按 anchor 单替换 cap 筛除及 prefix 不调用不受限 T。本次不重复这些已修边界；只反驳学习信号与方法身份。

### 11.1 共享全表会先吃掉什么：一个确定的等式

在同一公开状态 `z=(I,h,W,B)`，设 G(z) 为本次已经实际编译和组合完成的全部、与 h 相容的完整 cap 可行候选。令 `G_a(z)` 是与下一物理动作 a 相容的子域；每个未终止完整候选至少具有一个 enabled slot 的下一动作，因此须有

\[
G(z)=\bigcup_a G_a(z).
\]

如果 `W_a` 确实是每个 bucket 的最低 **raw M** 完整见证，则

\[
\min_a M_{raw}(W_a)=\min_{y\in G(z)}M_{raw}(y).
\]

这不需要模型或新数值。COLLECT 若拿到全部 `W_a`，已经拿到**该次已计算候选域的即时 raw 最优收益**。只有 bucket 的优化目标本身是完整 T 后交付值，或已经另证 T 不改变本域排序时，才可把 raw 等式直接改写成全域 T 后最优等式；本项目不能默认这条。若每 bucket 只返回 raw 最好的一条，另一个 raw 次优候选可能经 T 更好，不能据此宣称完整 T 后 G 域也被精确覆盖。

但更弱、且足以做归因的结论无须上述排序假设：把**所有实际返回的** `W_a` 经共同 T/scorer/完整 cap 付费验收并计入 B 后，`F(B union {W_a})` 已在 actor 选择 a 前确定；actor 选择本身不能再提高这个已收集集合的交付值，后续收益必须来自新状态产生的新候选。`first_compile_best` 只计实际完成共同验收和时限准入的候选；尚未支付 T/scorer 成本的 raw 表行不能记成已交付。若 G 只是 deadline 前的部分表，等式只对已经完成的 bucket/组合域成立，不能扩成未计算有限域的最优定理。若组合器只返回各 bucket 的一个有效而非最优见证，则也只保留上述已返回集合结论。

AIR2 本身只覆盖两个源趟、有限重闭合和固定插入规则，不覆盖完整后续域，故该等式**不证明整条轨迹以后没有学习机会**。可能仍有如下具体通路：选择 a 改变真实 h 与下一公开 W，下一张两趟表因而发现初表没有的三趟以上间接重组、与别的旧趟交互或新的兼容访问顺序。也可能固定 witness-follow 已全部发现它们；这是待测事实，不预设 RL 会有正收益。

应把首次编译后、首个 actor 动作之前的 bank 固定为 B0，终局 bank 为 BT，分开记

\[
\text{kernel-first gain}=M(R_w)-F(B0),\qquad
\text{post-first-table gain}=F(B0)-F(BT),
\]

其中 F 是实际公共交付器按原 T、完整 cap 和真实完成时点给出的值。第一项完全在首个学习动作之前产生，不能归给 RL。第二项仍不是天然 RL 收益，必须与同 kernel 的独立 COLLECT/witness-follow/贪心/初始策略/监督策略在相同预算下比较；区别只能来自访问了不同的后续 h/W 及其新表，而不能来自 actor 未选动作的 `W_a` 被偷偷扣给控制。

最小保留字段应为 `first_compile_best`、每轮 `new_full_route_ids`、首次新目标分组/次序的轮次、对应 parent h/W、累计原 scorer/组合调用与真实费用、`final_best`。若全部赢家已在 B0 中，或后续新增候选没有提高最终交付值，本配方在该输入预算下没有可识别的后续学习信号。记录真实零增量，不用 entropy、margin 或更长训练人为制造“RL 改进”。本段只补记录/解释要求，不新增候选或数值批次。

### 11.2 COLLECT 必须分成两种用途

**影子 COLLECT** 在 RL 实际访问的每个状态接收同一组 `W_a`，最后对同一 bank 调同一交付器。它与该 RL 轨迹的交付最好值相等是定义上的结果，可用来证明收益来自“已得到的候选”而非最终动作编号；它不是一个独立、不收费却有未来 RL 状态的科学竞争算法。

**独立 COLLECT/witness-follow** 从同一 anchor 出发，在自己按冻结规则形成的 h/W 上，调用相同 kernel、得到自己状态下的全部 `W_a`，使用同 6s/12s 完整预算；它不免费读取 RL 的未来状态及其表。后者才回答学习是否让有限计算访问到更有价值的后续物理路线域。公平性是“相同信息规则与 kernel、各自完整资源”，不是强迫不同策略在同一个未来表序列中行走。把 RL 未来表免费送给独立 COLLECT 再以平局关闭路径学习主张，同样会失去可识别性。

相反，在每个共享当前状态，所有已算 `W_a` 必须全部给各控制，不能只给 RL 或只给其选中项。两条规则同时成立：当前表无信息优惠；未来访问须由各自算法用预算产生。

### 11.3 AIR2 与普通同 kernel RL 是否不同

按对方 §2.3，策略看到相同 `(I,h,W,WA)`，输出同物理动作，使用普通 softmax 抽样和相同终局联合 score PG。若所谓“普通同 kernel flat RL”也获得相同状态、动作支持、表编译/commit、完整 reward、网络及预算，则它与该 AIR2-RL **就是同一个算法**，不应作两条独立优劣行，也不能从两者相同得分推导“新估计器无效”。flat/hierarchical若只是精确概率分解，也不能自动成为不同学习机制。

AIR2 的可指认差分是公开的行动索引两趟精确重闭合 kernel；研究身份应如实写为“AIR2 公共构造 + 普通物理 RL”。可分开估计：

- kernel 作用：同一无学习/初始动作规则，旧 identity/1reloc 与 AIR2 kernel 的完整预算差分；不能归 RL。
- 学习作用：**固定 AIR2 kernel**，学习后策略对无学习/initial、独立 COLLECT、贪心、同数据监督的配对完整交付差分。

这承认一个可能有价值的结构组合，不先要求再发明通用 PG 公式；同时保留 kernel 查新与 RL 效果是两项独立职责。root 本轮先做无模型内核工程，恰好只回答第一层的有限正确性/支持/费用问题，不会验证第二层。

### 11.4 本稿 margin 辅助项何时独立评估

不把 margin 混入 AIR2 无模型首批工程，避免 kernel 支持、表效率、策略表示、辅助监督四个变化同时发生。只有 kernel/完整 deadline 正确性、G0/G3 和新科学资源合同分别满足后，才按本稿既定矩阵另评；本次不再加新候选。

margin 的独立问题是：在**完全相同的 AIR2 kernel 或冻结 suffix kernel**、相同回报数据、相同 encoder/head、相同参数初始化和预算下，普通 PG 是否未跨部署 margin，而 margin-only 是否已经解释全部自由路线改进。比较 `PG-only / margin-only / PG+margin / no-update` 才有归因；`PG+margin` 只胜 PG、却与 margin-only 打平，不称 RL 的独立增益。若 margin-only胜，则它是成本敏感监督/约束辅助方法的效果。若 PG+margin同时胜两者且完整 cap/T/deadline/readout均通过，才得到该组合值得后续研究的证据，不自动成为原创或 Formal 结论。

再次限定：两个 replicate 都正只是冻结筛选代理；margin QP 之后的 actor 不受 §7.1 条件无偏梯度性质担保，且在 AIR2 中若把 W_a 当前 M 直接当 Q 标签，监督器只是在学习当前表已经算出的贪心选择。要识别超越 COLLECT 的学习，标签/自由执行必须涉及所选 a 引出的后续真实表发现，而不是重复奖励已收入 B0 的见证。

root 已向用户提交 `48h/10seed` 或 `42h/3seed` 的资源选择，尚未收到答复。该选择不由本文件替用户作出；在答复及准入前没有新科学人口/训练运行。本次附记只有静态逻辑交叉，所有科研数值为零。
