# G0 / G4 独立交叉反驳记录

日期：2026-11-03。参与：route_independent_audit、route_failure_audit、route_mechanism_g4。三方先独立冻结 INITIAL，再作针对性问题与答复。本记录不改写各自初判，不含新solver/evaluator/训练或质量结果。

## 1. 反方对 Route-RL 失败归因初判的挑战

### 挑战

旧Stage A固定了站点、站型和每个目标的无人机归属。24张旧图的完整初解可拆成180个非空无人机目标集合：中位6个目标，最大17个，177组不超过12个、179组不超过16个。固定ownership下，固定费和service总和不随路线变化，电池和路线可行性按无人机分离。是否把按机subset/partition DP列为G2和进一步训练的阻塞性强基线？若不列，现有证据有什么资格支持完整目标仍有至少0.3%的可学headroom？另请确认`env.py`中`run_policy_task`调用`policy_step(..., generator=...)`的关键字错误是否实际进入720任务路径。

### route_failure_audit答复

接受把按机subset-DP列为G2和训练投资前的阻塞证据；现有结果不足以声称有0.3%可学机会。固定ownership下目标分解为固定费用、固定service和各无人机flight长度之和；各机可行约束彼此独立。对每机，在energy-feasible多趟路线集合中，最短总长度不大于已有可行初解；已知初解可行时，累计duty约束不会排除该最短最优解。duty仍需在构造前缀mask中检查，以避免进入不可完成前缀。尺寸统计不保证DP在任何给定时间内结束，也不证明无headroom。

`generator`关键字错误在死helper中；训练主路径调用`collect_episode -> policy_step(..., torch_generator=...)`，验证调用`run_task_deterministic -> policy_step`，720测试调用`evaluate.run_policy_budget -> policy_step(..., torch_generator=...)`。故该错误不是旧720失败原因。

## 2. 反方对 Route-RL G4机制初判的挑战

### 挑战

候选H-R声称利用“候选target与全部remaining targets的energy-feasible trip-completion关系”避免不可完成前缀。该查询若回答剩余集合是否存在能量可行的route/partition，是否就是标准subset/partition DP、ESPPRC标签延伸或beam lookahead的直接completion test？把此证书作为pointer特征，是否只是既有feasibility lookahead包装？G4拟用attention/集合关系、mask或训练策略时，如何区别于DPTARL已存在的动态动作裁剪、拓扑attention与路线策略？按机exact后若没有可度量headroom，继续固定ownership RL训练的研究价值是什么？

### route_mechanism_g4答复

接受反驳：若completion certificate只是等价于标准remaining-subset route/partition DP，它不是不可约增量；给policy添一个标签或布尔证书只是工程feature。当前没有证据表明attention/lookahead/关系摘要能胜按机DP；也没有相对DPTARL和标准completion算法的实质创新增量。因此固定ownership completion-aware pointer机制G0判为NO_GO，不据此开启G4训练。

若按机精确机会诊断后仍需研究，重新立G0必须提出超出标准DP/lookahead的、仍属物理路线的具体增量，并给出一手先例差异证据。不是更换网络、训练时长或对旧Stage A调参。

## 3. 交叉答复：反方对机制代理的回应

独立反方同意当前H-R定义为标准remaining-set完成性查询的直接特化；向策略输入该查询输出本身不足以证明方法创新或RL必要性。按机exact应先作为机会分析和强非RL参考。对于固定ownership下至多17目标的旧集合，是否有足够剩余收益尚待实际有界G2诊断。旧Stage A对route-only SA/ALNS的负结果仍有效，但它不识别失败的因果来源；源码中确有的死helper keyword bug不解释该结果。应将此轮冻结与结果视为**固定ownership候选NO_GO（机制未立项）**，不是全部路线RL不可能的结论。

## 4. G2诊断的预冻结验收要求（方案建议，未执行）

1. **范围固定。** 只读重用全部24张旧图、180个非空ownership组，按地图列出任务尺寸与资源紧度。不可事后删除较慢或结果不理想的组；这批图已经暴露，仅用于机会/算法诊断，不是新开发或正式测试。
2. **算法与正确性先冻结。** 明确Held–Karp式子集最短闭合trip、energy-feasible trip集合、trip partition以及跨组重组算法；记录代码/输入哈希、状态定义、精度、tie-break、时间和内存cap。超时组保留incumbent、下界和未解状态，不写成精确最优。
3. **浮点与可行谓词一致。** 原独立evaluator的battery与duty可行阈值为`1e-7`，既有DP路径有`1e-9`阈值；报告须选择并显式冻结要诊断的可行集合，统一distance计算、累加顺序、余量和边界重评分。若为安全采用更严格阈值，应标作保守可行参考，不能将其下界冒充原模型1e-7域的严格最优证书。所有返回路线用原独立evaluator重评分。
4. **独立小例对拍。** 预先选小到可穷举的集合，独立枚举station-closed序列及所有trip partitions，与DP逐实例比成本、可行性及边界解。这里是算法正确性验证，不挑高收益地图。
5. **最优性论证分层。** 对单机目标，说明固定service常数、闭合flight总长度和energy trip约束；证明/核验在已有可行初解条件下，最短energy-feasible多趟总长度不增，因此duty不排除最优route。该性质仅适用于fixed station/mode/ownership和同一物理/浮点判定；不得外推到共同分配、站型改变或所有LRPHSD实例。
6. **Oracle机会与同预算性能分开。** G2可额外报告按机精确参考的总生成/计算/验证耗时、每图cost gap及超过0.3% full-objective门槛的上界空间；这是机会诊断，不是solver优越性。任何后续G3/G4公平胜负必须把同一初始化、完整所有子任务、求解、组解和独立验证都纳入每图6s/12s总墙钟，另报模型冷/热加载口径。不可把“每无人机各有6秒”拼成每图6秒，也不可把oracle额外算力排除后称公平性能。
7. **停止解释。** 若精确/强非RL已在主要规模内消尽可用空间，或剩余可实现的完整目标收益低于冻结门槛，则关闭fixed-ownership候选；不得缩小分母、挑DP慢的图、增加地图规模或让RL独占昂贵reference。

## 5. 三方当前一致与未完成项

- 当前不批准新训练或旧720矩阵重跑。
- 固定ownership路线、completion-aware pointer本候选当前G0 NO_GO；这不是一条已证明原创的新机制。
- G2可以由root进一步冻结为有界旧数据机会诊断，需先确定公式、epsilon、memory/time cap、独立枚举例及比较预算。当前没有运行结果。
- 即便G2剩余空间为正，仍需新颖性G0、强非RL G3和真正RL额外收益G4；旧Stage A训练不是新G4证据。
- 旧CA-RL算子选择不恢复；物理路线动作约束继续生效。

## Evidence pointers

- 独立反方冻结稿：`route_rl_research/20261103/audit/INITIAL.md`（SHA256 `1a6b90c0553c544f1615d80e9a48ec4f5e39e11c2f8ab0ae7f63f47fa0667d87`）
- 失败归因冻结稿：`route_rl_research/20261103/failure/INITIAL.md`（SHA256 `a174c84d0dc9da09e7f2a53b4237624424271b1ca66516d69c134f089a3773d4`）
- 机制初判：`route_rl_research/20261103/mechanism/INITIAL.md`（SHA256 `af475caccc6d3b008a47b48f24c4bd279d5a5959b0248ff281ff1e6d25d0f229`）
- 旧Route-RL源码快照：`route_rl_research/20261103/source_snapshot/`
- 原RL独立结果审计：`stage_a_audit/MODIFIED_FILE.md`及`stage_a_audit/VERIFICATION.txt`
