# 研究材料本地迁移精简包（2026-11-19）

此包来自既有工作区的静态读取与脱敏复制。没有执行实验、求解、训练或联网操作，没有改动或删除源文件。

## 阅读顺序

1. `00_current_handoff/`：当前需求、研究方案、LATEST_STATUS 与 11月19日新窗口提示词。状态文件按最新在前的顺序阅读，历史段落不覆盖最新判定。
2. `02_no_wind_static/`：11月12日无风静态接手验收、协议、独立统计、逐图结果与精确见证。
3. `01_author_reproduction/`：V6/semfix作者复现源码、表格比较、独立审核与已读取逐次结果JSONL。
4. `04_AIR2_G0/`：AIR2首批完整路线守恒失败、next-token隔离修复、G0设计和冻结源码。F3内的最新AIR2完整链及F3科学数据由主迁移包负责，本子包不重复。
5. `03_old_RL_negative/` 与 `05_closed_routes_and_context/`：旧RL/CA-RL负结果、当前关闭候选、失败、边界及保留强控制。

## 结果与限制

RL只直接决策物理目标/返航/分趟，不选择搜索算子。无风静态包曾发现许多M_return收益来自公共重标/后处理；该结论有特定合同范围，不能推广为所有RL无效。AIR2即时枚举收益属于公共kernel，现有证据没有确立学习增量。G0仍未通过；最新限定F3 G3资格与结果由主迁移包单独保存，不能读旧条目回退状态。旧DEV暴露、失败、24/24校准与关闭身份不得重开或抹除。

已读取的逐次作者复现JSON保存在`01_author_reproduction/COMPACT_RESULTS/*.jsonl`；每行含原相对路径、原SHA256与脱敏结果。无风强控制最终解保存在`02_no_wind_static/COMPACT_FINAL_SOLUTIONS/*.jsonl`；完整最终路线/分值保留，候选逐步certificate大列表只保留数量/状态直方图与原文件SHA，详见每行说明。本地缺读源文件详列`LOCAL_UNREADABLE_SOURCES.json`，不能将其视为不存在或结果为0；作者复现逐次raw并非全量。逐组完整性见`RESULT_COMPLETENESS.json`。无风g3_confirm与g3_pop的141个最终解全部保留；小规模exact_solutions尚有12个本地缺读证书，EXACT_RESULTS汇总已保留。大型训练清单、模型二进制、运行时、重复快照、压缩日志与系统库存未复制。

## 来源与脱敏

`SOURCE_MAP.json`逐项记录源相对路径、目标相对路径、原SHA256、复制类型和既有GitHub快照状态。`existing_GitHub_transfer_same_sha256`表示旧交接已存在完全相同内容；`existing_GitHub_transfer_source_path_content_differs_or_was_sanitized`表示旧迁移清单已列同一源相对路径、但内容不同或旧件已经脱敏；`not_found_in_inspected_existing_GitHub_transfer`只表示在所核快照中未找到，不证明是新内容或从未上传。源哈希对应脱敏前字节，目标哈希对应脱敏后字节，不应混用。

密码、令牌、身份凭据、连接命令、具体主机/端口/IP、用户邮箱及本地/远端绝对执行路径已替换为占位符。脱敏源码保留研究逻辑，若原脚本依赖执行路径，迁移后需在新环境配置路径；此包没有承诺直接运行。程序与研究结果未在本地执行。

主包可按相对路径合并。此包不含GitHub review材料，不含重复F3归档，也未包含任何新实验。
