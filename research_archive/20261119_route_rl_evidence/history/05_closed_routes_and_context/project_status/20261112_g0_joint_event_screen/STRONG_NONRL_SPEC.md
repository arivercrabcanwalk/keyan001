# 最强同信息 non-RL 资格规格（尚未执行）

status: SPECIFICATION_ONLY_G3_NOT_PASSED
scientific_run_admitted: false

## 对象、输入和输出

比较单位是完整地图/完整事件日，非单次成功决策。所有方法得到相同公开 H_t、站点/机型/归属、累计 duty、公共预测模型、初始状态、合法候选和可用历史。输出都是合法物理 (slot,target)/(slot,RETURN)；non-RL 内部求解可使用搜索方法，RL 不输出搜索方法或预算。

本规格仅明确资格要求，不冻结新人口、不分配新资源、不启动求解或训练。当前 40 身份/126 实际比较与 24/24 校准验证占用保持原账本。

## 必须具备的对照

|对照|可验收实现和排除的替代物|
|---|---|
|Liu 原法作者锚点|静态研究逐图调用已复现的作者原实现，绑定参数/seed/输入/完整路线/独立 scorer 与 hash；不以 task.id/距离手写评分冒充|
|同目标车队规则/greedy|使用全车队状态和原全图目标、固定 tie-break，包含公平可用的 deadline、准备度和公共预测；不故意只用静态距离|
|同目标联合 beam/其他合适强优化器|共享合法候选，维护完整 incumbent；全流程截止后只交付截止前的完整解，partial/无交付/回退分别计数|
|公共准备度 non-RL|用公开未来需求与可用资源求下一窗口缺口/机会价值；Han 2026 是必须全文比较的线索，其改降/换站动作须按本项目合同固定，适配结果不冒充原作者完整算法|
|真正的因果 scenario rollout|对每个相同物理候选采样联合未来流，以同一冻结 μ 逐事件执行；未释放信息不公开；16/128 次随机分数扰动不算该控制|
|充分预算 scenario 对照|预先指定有限大诊断预算并完整计费，单列为计算上限参考；不把它列入同墙钟主比较，也不将有限预算称为真正无限|
|教师、BC initial、监督 value 与 RL|教师规则单列；BC 神经模型在任何 RL 更新前保存并独立评价；RL initial/selected/checkpoint 与 seed 原样保留|

当前 static M_return 研究沿用共同 R_Liu、逐图 epsilon=0/1e-7 cap、整图路线改善总 6s/12s。新动态天气任务如另行准入，需先冻结完整事件日预算及因果作者适配；不能把每个决策 6s 累加后与整图 6s 相比。WX-H 的 1/10/100ms 为另一项尚未准入的依赖试验，不与静态预算混用。

## 真实 rollout 的完整接口与伪码

输入：公共状态 H、全部合法物理候选 A、冻结联合抽样器 P_TRAIN、冻结因果续接 μ、完整 evaluator、同一外部截止。输出：截止前完整可验证路线 incumbent，或真实失败/无交付记录。

```text
start common external timer
initialize the same complete incumbent from the permitted causal anchor
for each candidate a in the frozen fair order while time remains:
    for each common-random-number sample while time remains:
        omega = public_model.sample_future(H)
        simulation = copy_public_state_and_sampled_future(H, omega)
        simulation.execute_physical(a)
        while not terminal and external time remains:
            publish only sampled events whose release <= simulation.time
            action = frozen_mu(simulation.public_history, common_mask)
            simulation.execute_physical(action)
        if terminal:
            score the full route independently; preserve failures
        else:
            record truncated sample; never score it as a complete success
    estimate candidate value with the frozen missing-sample rule
return only a complete incumbent delivered before the common deadline
```

计时包括方法所需加载、编码、特征、抽样、状态复制、所有模拟/搜索、候选生成、约束检查和交付验证；公共初始化及环境执行等共同成本另按冻结边界一致记录。不能把一方算出的候选/样本免费送给另一方后忽略生成成本。非 RL 若获得更多 rollout 或 RL 若多用专家标签，均计训练/开发资源总账。所有 timeout、异常、incomplete、不可行、零样本和序列化失败须先逐行持久化，再写终局汇总。

## 联合分布与原 uniform 重训的资格

“知道风暴关联”不能仅供 RL：完整 H、同一预测模型与训练标签来源必须公平开放给强 non-RL。联合抽样器至少同时输出未来风、预报发布时间、请求 release、坐标、priority、deadline、能量和服务时长；只逐点加分数噪声不兑现这个接口。

原 clustered/uniform 验收需要两套训练过程，至少三独立 seed，各自保存 BC initial 与 RL 模型；训练样本数、初始化规则、选择资源保持对称。配对生成时冻结 routine、release、deadline、priority、服务、能量、风和预报，只替换紧急任务坐标分布；使用独立 RNG 子流，避免 mode 分支改变后续风样本。

若另验联合相关性，须在事前定义保持条件边际及每批任务数的 null。一个可审查的标准对象为固定请求数 n 下的最大熵分布 P0(S|H,n) ∝ exp(sum_i λ_i 1{i∈S})，仅在相容边际可实现时拟合 λ。它是诊断分布，不是新 RL 算法；独立 Bernoulli 改变任务总数后不满足这个 null。当前没有拟合、生成或测试它。

## G3 验收和关闭

先完成全文差异与实现/模型资格，不在已暴露 DEV 上择优调参。随后才讨论新人口与资源修订；当前不使用已满的校准额度制造新资格。主比较器及其选择规则必须在独立校准上确定，后续确认集不得再用来挑最强对照/检查点。

同信息完整强 non-RL 缺任一关键控制、作者锚点不忠实、无真实 rollout、预算不对等或失败记录不完整，则 G3 未通过。即使工程接口全通过，也只证明实现完整性。只有 G0 与 G3 通过后，才允许按单独冻结方案启动至少三独立训练 seed 的 G4；全部方法/模型/数据/预算/统计族冻结后才进行全新 Formal。
