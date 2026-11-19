# 天气事件流数据可行性与实验设计

日期：2026-11-14。本包只完成来源核对、边界判断和下一阶段合同设计；没有下载天气/故障数据，也没有运行科研样本、求解器、训练或Formal。

## 结论

公开数据能支持“历史风暴身份、宏观风场、部分区域的高频雷达观测、区域停电聚合量”几类不同用途，但没有一份已核实来源同时提供本项目所需的**目标级资产坐标与类型、逐目标故障/告警起止、同场景天气暴露、运营预测发布时间戳**。因此当前 `p=0.2` 与 `delay~U[0,20]` 仍只是工程默认值；不能用相邻领域的fragility曲线或图像缺陷率代替项目故障率。

本地目标数据搜索命令统计到0个 `.nc/.grib/.grb/.grib2/.bufr/.parquet` 原始气象文件；文件名检索也未发现 IBTrACS、ERA5、TIGGE、NEXRAD、EAGLE-I 或停电事件源。此结果只表示当前工作区未发现这些常见原始文件，不表示全网没有适用数据。

## 来源审查

|来源|可支持的环节|不能支持的环节|当前判断|
|---|---|---|---|
|NOAA IBTrACS v04r01|全球热带气旋身份、轨迹与强度来源；适合作风暴先验/分层|轨迹大多按6小时报告、档案位置插值为3小时；弱系统位置不确定性约30–40 km，风速平均时长随机构不同；不能当5分钟目标尾缘观测或同一套全球一致风速|事件级先验，不是`t_exit`精确真值或目标故障率|
|Copernicus ERA5|全球0.25°、小时级10m/100m风U/V等再分析量；适合作宏观暴露协变量|再分析不是当时可见的as-issued forecast；小时/网格产品不能验证5分钟单体尾缘时刻|回顾性天气协变量，不能冒充实时预报发布流|
|ECMWF TIGGE|2006年以来多中心集合预报，典型集合成员12–51、时效10–15天；有可追溯预报初始化|官方数据说明时间分辨率为6小时，不能直接满足每60分钟一次独立新预报|可作历史as-issued forecast vintage基准，不满足当前原定小时发布频率|
|ECMWF HRES operational archive / Open Data|HRES四个UTC周期每日运行，小时lead steps可到144h；能保留forecast cycle与valid time|Open Data仅保留最近12个run（约2–3天）；长期历史archive另需服务协议/访问；四次初始化每天不等于每小时刷新一次预报|历史回测需核准档案访问；不得把lead step误当发布次数|
|NOAA NEXRAD Level II|美国覆盖区域的历史雷达反射率、径向速度等；单个volume文件通常含4/5/6/10分钟扫描|仅美国雷达网；雷达反射不等于地面资产故障，扫描/波束遮挡与storm-cell识别仍需质控；不能外推全球或直接估资产fragility|若研究区在覆盖域内，可用作对流单体观测与区间化退出时间候选|
|EAGLE-I county outages|美国县级用户停电估计，2014–2022、15分钟；2022覆盖面约92%|区域聚合、非线路/目标级元件故障；监测覆盖率随时间变化|可作区域需求/服务扰动的外部校准层，不能直接拟合每个Liu目标的失效概率|
|InsPLAD UAV输电线影像|17个真实资产、10,607张影像，图像级状态标签；含6个缺陷样本类别实例|不是资产运行事件日志；没有风暴时间、故障发生时间/暴露历程或概率分母|可支持视觉识别研究，不能校准天气触发故障到达律|

来源： [IBTrACS主页](https://www.ncei.noaa.gov/products/international-best-track-archive), [IBTrACS v04r01技术说明](https://www.ncei.noaa.gov/sites/g/files/anmtlf171/files/2025-04/IBTrACS_version4r01_Technical_Details.pdf), [ERA5数据说明](https://confluence.ecmwf.int/pages/viewpage.action?navigatingVersions=true&pageId=662510445), [TIGGE目录](https://ecds.ecmwf.int/datasets/tigge-forecasts), [ECMWF operational archive](https://www.ecmwf.int/en/forecasts/datasets/operational-archive), [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data), [NEXRAD档案说明](https://www.ncei.noaa.gov/products/radar/next-generation-weather-radar), [EAGLE-I数据描述](https://www.nature.com/articles/s41597-024-03095-5), [InsPLAD论文](https://arxiv.org/abs/2311.01619).

## 关键设计推论

1. **轨迹与风场分开。** IBTrACS定storm identity/粗轨迹，ERA5给回顾性大尺度风场；若要5分钟左右的`storm_exit`，需要覆盖目标区的雷达/地面观测或承认退出时间是区间删失。即使NEXRAD可用，4–10分钟扫描也不等于连续精确时刻，应保存`[last_inside, first_outside]`并在训练/压力分析中传播区间不确定性。
2. **预报发布时钟单独保存。** `issued_at`、`valid_at`、成员、变量、空间网格必须成为场景行的一部分；任何决策只可读`issued_at <= decision_time`的数据。ERA5不提供as-issued历史预测；TIGGE为6小时资料，HRES小时lead不是小时发布。原合同若坚持每60分钟独立更新，只能使用满足该条件的历史预报vintage，或另立“历史误差驱动的合成小时发布流”并明确其为合成。不得静默把6小时/小时lead解释成60分钟独立预报。
3. **目标故障率需要目标事件与暴露配对。** 至少需要稳定资产ID/类型与位置、故障发生或区间、正常观测/缺测区间、同一时期的天气暴露、检测/告警时间及恢复/服务标签。仅有缺陷照片、县级停电或跨领域fragility都不能识别项目目标级`lambda`。
4. **训练/校准按风暴分组。** 同一风暴的空间相关目标不能拆到TRAIN与VAL两侧；响应延迟分布从检测/告警时间差估计，不能继续默认均匀分布。若有效资产级样本不存在，事件概率和delay仅作为合成压力测试参数，不作实证风险结论。
5. **RL对比依赖不变的事件实例。** 所有方法共用天气轨迹、预报vintage、风暴/资产latent、故障随机数与延迟抽样；策略改变路线不能改变同一实例的故障事件释放时间。事件过程与策略效应分别报告。

## 当前准入状态

这项来源审查没有改变G0或G3。G0新机制未通过，强non-RL完整资格未通过；当前天气事件环境只是有限工程实现。它不授权RL训练、多seed、消融或Formal。下一项工程可在合成fixture上接入显式带时间戳的storm-track接口与interval-censored exit记录；目标区/资产型、可用事件账本和小时预报vintage没确定前，不启动数据校准或W科学批次。具体任务账本与实验对照见`EVENT_LAW_AND_JOB_LEDGER.md`。
