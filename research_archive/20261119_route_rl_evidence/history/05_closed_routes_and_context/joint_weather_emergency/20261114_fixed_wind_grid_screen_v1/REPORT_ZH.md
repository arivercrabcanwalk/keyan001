# 恒风速度/方向网格冻结与物理验收

## 已证实事实

- 本轮只做恒风方案设计及<REMOVED_ENDPOINT>上的有限物理/G1验收；没有新科学地图、作者求解、ALNS求解、策略运行、训练、checkpoint或Formal。
- 阅读本地 Sensors 2020 论文：其风向量在单个weather time window内固定，且给出固定空速下风影响地速/航向关系；但它自身的功率公式含非线性和载荷项，不能说它采用本项目的简单线性能耗。本项目简单模型继续继承LRPHSD合同：飞行能耗=飞行时间×固定能耗率，加静态服务能耗。
- 定向查到并读了 Luo et al. 2018 steady-wind全文实验段。其模拟比较四个基准风向，并在east风下扫描1--8 m/s，图18示例为2/4/6/8 m/s。该研究使用固定翼Dubins、最小时间与GA，所以只作为风强/风向情景设计先例，绝不冒充本项目算法或能耗基线。
- 在隔离矩阵副本冻结S_const的配对网格：风速 `{0,2,4,6,8} m/s` × 流向 `{E,N,W,S}`。零风四方向同为零向量，只计一个不同条件，因此每张地图共17个独立风向量。坐标约定x向东、y向北；风向定义为**气流流向**，E/N/W/S分别为(+x,+y,-x,-y)。先每个非零风速内方向等权，再五个风速层等权；底图内17行是配对重复测量，不是17张独立地图。
- <REMOVED_ENDPOINT>当前作者速度900 m/min，风速换算为m/min后最大风速/空速比8/15=0.5333，17组均满足闭合支持`|w|<a`。
- <REMOVED_ENDPOINT>既有恒风测试24/24通过；新增17场有限闭合航次检查17/17通过。变换度量与逐边物理飞行时间的最大差为`8.88e-16 min`，闭合路线反转的最大差为`1.78e-15 min`。简单线性能耗在同一路线/风条件下保持同一静态服务能耗和飞行时间线性分解。
- 单独回滚副本恢复到原始矩阵SHA并与BASELINE_COPY逐文件一致；MODIFIED_FILE保持修订。
- 现有资源帐仍是作者尝试40/48（余8），校准/验证24/24已满。17风场全因子超过剩余额度，因此该矩阵不是科学质量运行授权。

## 未证实假说

- 在固定恒风简单能耗下，RL直接选择物理target/RETURN路线能否在逐图作者同风成本cap内降低完整返航`M_return`并胜过强min-max ALNS，仍完全未证实。
- 2--8 m/s情景借鉴文献，但对LRPHSD当前参数体系的工程/真实飞行代表性仍未标定；速度矩阵只确认运动学域和实现一致性，不证明现实外部效度。
- 所列方向/强度对各几何难度的敏感性与主效应尚无科学地图数据。

## 失败或关闭方向

- 本轮尝试用`/usr/bin/time`和shell `time`包装服务器命令均返回127（环境无该工具），未进入Python；失败原样记账。随后使用无包装SSH命令完成两个必要检查，没有以失败包装结果代替测试结果。
- 关闭将 Sensors 2020 的非线性载荷功率模型说成本项目简单能耗来源的表述；本项目简单能耗明确来自LRPHSD继承合同。
- 关闭把“东风/西风”等气象来源口语直接当作向量方向的做法；协议用明示的flow-to笛卡尔向量，避免论文角度约定和中文风名歧义。
- 既有G0候选的NO-GO和G3未通过状态全部保持；本轮物理正确性结果不抬升新颖性、G3、RL效果或论文结论。

## 下一项有界工作

先完成一个与已关闭路线排序/信用机制不同、具备明确新增物理路线生成或参数更新步骤的G0候选及最近先例对照。与此同时须另冻结G3人口、锚点、强ALNS、作者尝试额度及计算资源修订，逐失败计入分母。只有G0/G3与新资源方案明确通过后，才按本17风场网格进行恒风科学评价及足量多seed、消融、全新Formal；恒风科学研究完成后才进入紧急任务分支。不得在暴露DEV调参，不弱化作者同风cap或强基线。

## 是否需要用户决策

当前不需要。研究仍在G0/G3前置闸门；若后续研究设计需要新增科学计算资源，届时提交具体额度和方案供用户确认。目标继续进行，当前没有证据支持“突破”或CCF-B以上投稿结论。

## 文献与实现依据

- Luo et al., “Integrated optimization of unmanned aerial vehicle task allocation and path planning under steady wind,” PLOS ONE (2018), DOI: 10.1371/journal.pone.0194690. 实验范围来自原文§6及图18。
- Thibbotuwawa et al., “UAV Mission Planning Resistant to Weather Uncertainty,” Sensors 20 (2020), 515, DOI: 10.3390/s20020515. 本地原PDF阅读记录及模型差异见`joint_weather_emergency/20261112_constant_wind_v1/MODEL_AND_SOURCES.md`。
- 恒风实现与线性能耗合同见`joint_weather_emergency/20261112_constant_wind_v1/MODIFIED_FILE/env/constant_wind.py`、`baselines/problem.py`及本包服务器收据。

可重开的原始结果：`server_evidence/BASELINE_CONSTANT_WIND.json`、`server_evidence/WIND_GRID.json`。完整命令、输入、逐字摘要、退出码与回滚状态见`VERIFICATION.txt`。
