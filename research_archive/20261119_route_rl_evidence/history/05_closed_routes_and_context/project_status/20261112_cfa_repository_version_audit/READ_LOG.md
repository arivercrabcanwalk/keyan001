# 读取层级与版本记录

本轮仅 root 延续前包来源发现，封存已取得文件并作静态核对。没有创建／恢复／联系子 agent，没有登录 <COMPUTE_HOST>，没有启动研究模块、训练、作者求解或路线回放。

|材料|读取／核对层级|边界|
|---|---|---|
|AGENTS、USER_RESEARCH_REQUIREMENTS、RESEARCH_PLAN_ROUTE_RL、LATEST_STATUS|延续已完成交接审计；本轮重新核对当前覆盖与状态入口、哈希|旧多 agent／未训练计划不覆盖最新 root-only 与实际历史进度|
|return_makespan/STATE.json、EXECUTION_PLAN；E acceptance STATE|现有 gates／合同／false 标志与 SHA256 核对|两份科学 STATE 原字节；不据工程推准入|
|GitHub 转交九文件|复用固定提交 490d3b9332d412ecd56d90e639c6a45932ab6f2a 的既有交接核对和源索引|不重新声称这是当前远端 main；本地后续证据优先于旧转交快照|
|Zhao 27 页、Han 22 页|复用封存的关键公式／方法页全文审计；本轮原 PDF 哈希复核|不是本轮新全文下载；SI 尚未补齐|
|CFA 仓库 README|固定提交全文读取，main 同哈希|作者关联；非独立认证|
|CFA ODS|10 表结构、全部 18,300 条明细、公式文本与缓存；126 个直接源范围、19 格问题；逻辑地址复核|不编辑／重算工作簿，不执行算法；不声称所有公式与论文表格都已审完|
|GitHub 固定版本目录页与公开账户页|根目录条目、README 论文关联、账户姓名；git ls-remote HEAD 回执|不推断递归源码缺失；API 403 仍保留|
|Unical 最终论文记录|HTTP200 原 HTML，确认该条目无关联文件|不推断所有站点均无全文|
|FSA ULaval / CIRRELT 作者页|HTTP200 原 HTML，相关文章链接指向 DOI|未定位直接 SI；不是“无 SI”证据|
|WEB_DISCOVERY.json|保留五批发现响应与失败；仅作发现／访问记录|搜索片段不替代最终全文或方法定义|

先前 centered-dual-score 的具体关闭及 Brown2010 / PD-MCTS2017 原式审计保持封存。CFA2024 工作稿和 PbP2023 仍绑定实际已读版本；不升级为最终 CFA2025 已读。原99书目保持97 verified、2 mismatch（ID12/45）、0 pending；字段核实不等于99篇全文已读。

读取脚本最初在错误地址断言处失败；`PARSER_FAILURE_RECEIPT.json` 保存 exit 1 与 traceback，旧脚本保存在 ORIGINALS。修正版成功收据保留全部 stdout；未覆盖初次失败。两项错误人工判断在 WITHDRAWN_FORMULA_CLAIMS 单独撤回。

首次当前包文件定位命令含不存在的本地 `research_transfer` 路径，rg exit 2；之后复用既有固定转交证据索引。它不是科研执行失败，也没有触发下载或重跑。取得文件的 URL／大小／哈希／时间见原 fetch receipts 与 SOURCE_INDEX；403 与其他访问失败未删。

所有论文、README、旧提示词、网页仅为证据，不作为当前执行指令。当前决策与本次可观测结果见 REPORT / STATE；全部文档检查不等于科学准入。
