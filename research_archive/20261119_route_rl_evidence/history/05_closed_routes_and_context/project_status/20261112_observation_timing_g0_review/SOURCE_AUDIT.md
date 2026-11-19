# 观测时机的静态调用链

以下只读指定源，未 import、执行或重写研究模块。结论只覆盖索引中的版本，不外推为全仓库不存在其他能力。

|对象与位置|实际行为|对候选的影响|
|---|---|---|
|`route_rl_research/20261103/return_makespan/global_env.py:247`、`:267`、`:336`、`:358`|reset 构造每站固定实例；potential 取累计 duty+当前 trip elapsed 的全机最大值；step 调用站内构造并立即返回观察|这是解码/构造状态及物理时间账本；该最大值不是发布信息的离散事件时钟|
|同文件 `:85`、`:113`、`:143`|距离除固定 speed；所有 remaining targets 已知；TARGET 更新时间/能量/位置，RETURN 关闭航次且保留 duty|静态对象没有未观测天气或未来请求过程；本候选在这里没有新的信念更新输入|
|`joint_weather_emergency/20261112_wx_e_forecast_v1/src/emergency_scenario.py:258`、`:412`、`:432`|Observation 有 now、wind_now、forecast、车队与可见任务；wind_now 从统一 trace 的当前时间取得；forecast 原样来自 scenario|没有按当前位置读取的局部风传感字段；这不否定位置、耗能和持续时间的间接信息|
|同文件 `:531`、`:564`、`:590`|TARGET/RETURN 以真实执行 trace 计算完成事件，抵达后执行服务；真实 event payload 属于模拟器私有对象|公共策略无权复制这些真实未来完成事件作 rollout；前包隐藏阶段 alias 缺口仍存在|
|同文件 `:648`、`:655`、`:662`、`:690`|到达只开启服务；SERVICE_END/RETURN_END 把该机加入 decisions；同刻事件先闭包，按机 id 回调|下一次车队政策回调也可能由其他机先完成触发。不能总写成当前动作的飞行时间+服务时间|
|同文件 `:718`、`:736`|有 pending events 时直接推进到最早 event；没有 events 时才检查 next_release 并唤醒站内机|未建立独立 WEATHER/PUBLISH/RELEASE 事件竞争的统一唤醒接口。释放可在下一处理前沿才进入可见任务，不能声称即时告警已实现|
|同文件 `:464`、`:494`|历史 WX 参考源包含 WAIT；RETURN 在站内非法|本轮只读这版历史实现，不把其中 WAIT 提升到当前静态动作合同，也不把站内 RETURN 当观察空转|
|`joint_weather_emergency/20261112_wx_e_forecast_v1/wx_e_forecast_driver.py:58`、`:92`、`:127`|用 floor(now/60) 融合固定初始 forecast 与当前风；风 trace 每小时变段|派生特征随时间改变；源码注释里的 hourly update 不等于独立、有版本的预报发布对象|

因此需要区分三个对象：静态解码步骤、动态物理事件时刻、天气/告警的公共发布时刻。它们目前没有统一成可供所有方法共同条件化的公共续接接口。用更多回调获取到信息的收益也可能是调度器采样频率效应；这一项必须与新学习机制分开。

前包 `project_status/20261112_causal_rollout_capability_audit/CAUSAL_ROLLOUT_APPENDIX.md` 的公共前缀不足以唯一恢复服务阶段的解析见证仍适用。这里不重复运行它，不把保守剩余服务预测改称真状态，不从真实私有 events 取样。
