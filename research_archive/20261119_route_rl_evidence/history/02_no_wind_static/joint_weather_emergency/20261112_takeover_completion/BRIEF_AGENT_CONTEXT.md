# SHARED BRIEF — 2026-11-12 接手完成包（DeepSeek Harness）

本文件是所有工作线程的共享上下文。先读完本文件，再执行你的任务。

## 工作位置
- 项目根：`<LOCAL_PATH>`
- 本包目录：`<LOCAL_PATH>`
- 接手指令全文：`<LOCAL_PATH>`（627 行，必读相关章节）
- 索引：`.../20261112_claude_handoff/SOURCE_INDEX.json`、`HISTORY_INDEX.json`

## 服务器（所有实验必须在这台）
- SSH wrapper 已就绪：`<EXECUTION_PATH> '<远程命令>'`（key 认证已验证可用）
- 远端：hostname `<COMPUTE_HOST>`，Python 3.10.12，104 核，371 GB RAM，**磁盘仅剩约 11 GB**，无 GPU，时区 UTC（= Asia/Shanghai - 8h）
- 远端历史目录：`<EXECUTION_PATH>`、`<EXECUTION_PATH>`、`<EXECUTION_PATH>`
- Mac 只做文档/静态审查/传输/哈希；**不得在 Mac 跑科研计算**

## 不可违反的研究合同
1. 动作只有 `(slot, target)` 与 `(slot, RETURN)`。不得引入搜索算子/邻域/算法选择/修复预算。RETURN 回所属站换电池但**不清零累计 duty**。
2. 静态主合同 S：逐图 `C(candidate) <= C(R_Liu) + 1e-7`（epsilon=0），在整图 6s/12s 墙钟下 `min M_return`；M_return == 官方 `Check.calculateLatestTime`；禁止跨图均值抵消超 cap；MTC 仅辅助。目标 5% 平均改善 + 地图级 95% CI 下界 > 0 是**目标**，不是已实现结果。
3. W（天气/应急）与 S 分列注册、分列结果。W 有成本比 bootstrap 95% CI 上界 <= 1.01、CVaR90 等；不得把 W 包装成 S 已通过。
4. 当前科学状态：**G0 = NO-GO（无获准新机制）；G3/G4 未通过；G5–G8 未完成。** 不得在 G0/G3 未过时启动新训练。不得重开已关闭身份（WX-E/WX-C 各 pilot、reserve v5、centered-dual-score、observation-timing/POSMDP、joint-event-screen 等）。
5. 失败/超时/不可行/NaN 必须落盘保留；不得剔除失败日算均值。
6. 不修改历史文件原字节；新产物只写在本包目录或你被指定的新目录、以及远端新目录。不 push、不公开、不投稿。

## 输出纪律
- 所有产出写到本包目录下你被指定的文件名，中文正文 + 英文术语。
- 每个数字必须带：协议/分母/地图身份/原始证据路径。
- 必须显式区分：已证实事实 / 未证实假说 / 失败或关闭 / 下一项有界工作。
- 报告回给我时用简洁结构（<=120 行），列出：产物绝对路径、关键发现 5–10 条、冲突与采用版本、未解决缺口、你建议的下一项有界工作。
- 不要说"我可以"或给空泛计划；要么交付文件，要么给出具体阻塞与证据。

## 已核实的服务器实收据（2026-11-12 15:52 CST）
见本包 `ENVIRONMENT_AND_SSH.md`（由环境线程维护；若尚未生成，以本文件下列事实为准）：
hostname=<COMPUTE_HOST>；python3=3.10.12 (/usr/bin/python3)；nproc=104（Xeon Platinum 8269CY, 2×26×2）；Mem 371 GB，空闲 95 GB；`/` overlay 30G，已用 20G，**可用 11G**；无 nvidia-smi；uptime 41 天；无用户作业在跑；`/root` 26G。
