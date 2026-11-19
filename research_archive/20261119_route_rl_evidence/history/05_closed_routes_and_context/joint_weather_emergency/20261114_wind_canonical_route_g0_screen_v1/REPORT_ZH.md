# 恒风规范坐标候选：G0公式筛查

## 已证实事实

- 固定风下的航时可以写成`T_w(d)=S_w(d)-phi_w(d)`，其中`S_w`是对称正定范数项，`phi_w`是线性势差。闭合趟满足`sum d=0`，势差和消失；逐前缀的leg和返航可行性仍方向相关，必须沿用原动作mask和原scorer。
- 本地`ConstantWind.edge_decomposition`已有对称项/potential差实现；2026-11-14路线反转候选已验证该闭趟恒等式在有限fixture中的scorer表现。
- Zermelo/Randers稳态风几何已经把航时表示为Riemannian部分与线性项。Sym-NCO对正交输入变换/旋转不变表示及对称解REINFORCE已有通用方案；POMO和DPN覆盖多最优解/车辆置换等路线对称性训练。
- 因此，“把地图旋到风规范坐标＋把edge拆成对称目标通道与方向可行通道”目前是同一物理问题的输入特征重表达。它没有增加物理路线动作、完整解目标、梯度/信用估计、可行性更新或bank外路线构造步骤，裁决为`G0_NO_GO_AS_DISTINCT_MECHANISM`。

## 未证实假说

规范输入可能改善未见风向/风强度上的表示样本效率；没有在TRAIN/VAL或新底图上验证。即使未来验证有效，它首先是实用特征/对称性控制，不能自动称为独立新算法或RL独立增益。

## 失败或关闭方向

- 关闭“闭趟对称edge度量本身是新机制”的候选身份；该恒等式和分解已有于当前项目实现。
- 关闭“单做规范坐标变换足以通过G0”的主张；其最强对照包括相同网络与物理mask、旋转增强/Sym-NCO式不变表示、同信息确定性控制、完整作者锚点、成本中性整趟重排及强min-max ALNS。
- 不把闭趟时间相消扩张到前缀mask、动态天气或告警时效；方向性即时可行性仍需精确检查。
- <REMOVED_ENDPOINT>专用密钥连接多次在TCP阶段返回`Connection refused`；本轮没有远端命令执行、工程测试或科研运行。用户反馈实例仍运行已记录，当前需要控制台提供现行SSH主机/端口后继续重连。

## 下一项有界工作

<REMOVED_ENDPOINT>恢复后先只读核验真实实例主机、端口、运行进程和配额；不恢复不明作业。随后继续筛一个确有不同物理路线生成或学习更新步骤的G0候选。恒风17场网格保留待用，须等G0/G3、全新人口和资源协议冻结后才启动科学比较。固定风、作者逐图完整成本cap、6/12秒、强ALNS、root-only和旧失败保留不变。

## 是否需要用户决策

需要提供当前实例控制台显示的SSH连接主机与端口；无需提供密码、私钥内容或其他凭据。资源、动作合同和研究指标不需决策。

## 来源

- Dušek, “Zermelo Navigation Problem in Geometry” (2018): https://hrcak.srce.hr/file/304716
- Bao & Robles, “Randers Metrics Through Zermelo Navigation”: https://library.slmath.org/books/Book50/files/06BR.pdf
- Sym-NCO: https://arxiv.org/abs/2205.13209
- POMO: https://arxiv.org/abs/2010.16011
- DPN: https://proceedings.mlr.press/v235/zheng24m.html
- 本地先例：[恒风实现](<LOCAL_PATH>)、[闭趟反转筛查](<LOCAL_PATH>)。
