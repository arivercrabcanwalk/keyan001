# 完整作者固定风调用：已执行结果

仅root/<COMPUTE_HOST>；本包7phase已终局，6成功/1原传输失败。实际child CPU63.357717s，phase墙钟合计55.932087s；剩余phase/repair均0。没有重跑旧1200/48/科学DEV，训练/模型导入/checkpoint/新科学人口/Formal均0。

## 已证实事实

完整Main确实执行：BASELINE 3行、MODIFIED 3行、DELIVERY 2行、独立回滚3行，共11次，其中5次Main实际返回、4次工程交付合格。含同输入与回滚重复，不是11张独立科学地图，也不是可靠性泛化样本。

|注册手写输入|原J1b完整调用|风适配完整调用|
|---|---|---|
|dual_station_2d|QUALIFIED；0.939914s进程；source M36.083924/C91.541978，风重评分M38.397390/C93.456103|QUALIFIED；1.778569s进程；最终打印/Recorder/源Java/独立heading scorer均M38.397390/C93.456103|
|large_station_2d|15.019312s超时，已保存完整初解，无最终Main|15.019048s超时，已保存完整初解，无最终Main|
|init_stall_2d|1.015895s超时，无Recorder|0.066975s进程，exit1，WIND_INIT_NO_PROGRESS，无Recorder|

时间是单次工程观测，含参数分支差异，不能外推运行速度、路线质量或训练收益。完整参数500/100/5000及温度原值、guard与物理不变；恒风(540,0)是工程值。

正常短budget调用实际合格；故意Main后等待2000ms的完整解已保存且Main返回，但进程在1s被kill，资格拒绝。新增final latest-time+1与最终路线不一致两变异均被抓到。该晚退控制是显式工程wrapper，不暗改作者预算。

回滚另副本恢复driver字段original_j1b及原SHA；两可终止/超时见证的原始Recorder、Final Main存在性/内容、源评分、资格JSON逐字一致，stall继续拒绝；BASELINE字面stdout也一致，主修改保留。

## 未证实假说

单站large超时有具体源码解释：LocationOperator在站数1时用nextInt(1)抽两个不同站，进入此分支后必无限循环；本次未采当时线程栈，不冒称实际栈定位。修复是否令完整作者链交付，须新隔离修复包验证。工程成功不表示完整G3、科学共同锚点或6s/12s方法比较已获资格。

## 失败或关闭

两profile全部原超时/初始化失败留在注册分母，不补图、不延时，不用早存初解虚填交付。首次BUILD因68个AppleDouble sidecar污染源码glob而exit1；实际作者30源hash无变化，原builds/sidecar及收据在TRANSFER_V0_PRESERVED，唯一预留修复禁用元数据并BUILD_REPAIR1成功。另一次只读SSH诊断在Mac shell因引用错误退出，未远端执行，记录在OPERATION_ERRORS.json。

当前l2o前缀投影已按L2O_DECISION.md关闭独立创新身份。条件score证明只保证对完整l2o保均值/方差不增；手算27倍方差反例表明它不普遍支配l1o。不为标准组合追加toy或训练。

## 下一有界工作

`20261113_author_single_station_fix_v1/INTENT.md`已另冻最小cardinality修复：单站/零站返回clone，两站保持原随机流；作者身份另命名，原失败不覆盖。实际工程回归后再明确科学锚点源/同风完整cap/整图计时资格。G0新机制仍需具体不同的物理路线学习步骤；完成G0后才进入矩阵的新科学G3人口。

## 是否需要用户决策

当前没有。A已批准；固定风和简单能耗先行、强ALNS/成本中性重排保留，仅root/<COMPUTE_HOST>。G0/G3未过；整体研究、CCF-B目标及G8未完成，两保护STATE和旧40/126/24额度不改。
