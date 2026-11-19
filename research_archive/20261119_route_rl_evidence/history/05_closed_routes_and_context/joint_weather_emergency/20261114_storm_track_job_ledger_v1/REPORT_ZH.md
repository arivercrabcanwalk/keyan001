# 风暴轨迹区间与独立 job 账本工程验证

## 已证实事实

本包在已通过的风暴告警修改版上另建 `BASELINE/` 和 `MODIFIED_FILE/`。修改版新增时间戳足迹输入、目标退出区间删失记录、需显式保存抽样来源的区间解析、每 crossing 独立告警 job ID，以及从 dispatch/completion 回执独立重建普通任务和告警状态/分母。告警恰在服务完成时释放时，按冻结的 `(service_start, completion_time]` 语义先开放告警，再关闭服务；同一物理访问可以完成基础任务和告警，不重复增加 dispatch 或成本。

区间只表示观测边界。缺测保留为 unknown 并使区间变宽；版本/身份不连续会拒绝拼接；多次 crossing 保留独立 ID，但当前 engine 的单目标单 crossing v1 接口会 fail closed。缺少响应窗口来源时，ledger 显式阻断准时率/CVaR，不填便利常数。

<COMPUTE_HOST> 3.10.12 验收：BASELINE 新夹具 2/2 PASS，精确完成时点释放告警需对同一目标派发两次；MODIFIED 14/14 PASS，同一物理访问结算基础 job 与告警 job，目标派发 1 次、operating time 10 min。修改前后既有 T9/T11 分别 11/11 PASS。另将最终修改副本复制至 `ROLLBACK_COPY/` 验收 14/14 后执行 `ROLLBACK.sh`，`diff -qr` 与 BASELINE 无差异，恢复夹具 2/2 PASS、派发恢复为 2 次。远端与本地关键源码哈希相同；逐命令、输出、exit status 与 SHA256 见 `VERIFICATION.txt`。

## 未证实假说

未来可用带目标资产定位、风暴单体 footprint、观测覆盖与实际故障/告警的区域数据估计暴露风险和响应时窗；本工程没有验证该数据假说，也没有拟合事件律。

## 失败或关闭方向

真实 cell segmentation、经纬度变换、轨迹跨版本拼接、重复/相邻 cell 对同一目标的合并语义、真实响应时限和目标级故障率仍未解决。当前包不将均匀区间 draw、工程故障率、延迟或 fixture response window解释为校准参数；G0/G3 仍未过。

## 下一项有界工作

在适用区域/资产级故障数据和业务响应时窗来源到位后，另行冻结数据映射与风暴整场 TRAIN/VAL split；先核数据覆盖、轨迹版本和目标匹配率，不拟合 E2，直到事件样本单位与观测窗口可审计。无此数据前只保留合成工程输入，不启动策略质量批次。

## 用户决策

当前无需用户决策。后续真实校准需要指定适用区域/资产类别和可追溯目标级事件/响应记录来源。
