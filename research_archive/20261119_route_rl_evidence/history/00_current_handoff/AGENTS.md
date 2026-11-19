## 2026-11-14 当前用户覆盖：恢复多 Agent，统一 GPT-6.1-Sol / xhigh

用户最新明确要求创建多agent高效工作，agent模型必须为6.1solxhigh。本轮允许root协调新建子agent，统一显式使用 `model="gpt-6.1-sol"`、`reasoning_effort="xhigh"`、`fork_turns="none"`；覆盖下文2026-11-05的root-only与2026-11-04的ultra要求。科研/训练/求解/质量评价仍仅<REMOVED_ENDPOINT>；不重跑旧实验，不在暴露DEV调参，物理动作、G0/G3、成本cap、强对照和失败保留规则不变。root统一分配远端运行，避免并发实验与资源重复。

## 2026-11-05 最新执行覆盖
用户最新要求：继续完成所有任务不要再创建子agent 就用你自己的模型。当前仅root独立执行，不新建或恢复子agent，覆盖旧G4多agent调度；历史审计身份不变。实验在<REMOVED_ENDPOINT>，物理路线动作和失败保留/准入不变。40新身份/126实际比较，校准验证24/24额度满，状态以LATEST_STATUS和return_makespan/STATE.json为准，不按历史尚无新图/未训练字样重复执行。

# 项目当前用户要求

先读 `USER_RESEARCH_REQUIREMENTS.md`、`RESEARCH_PLAN_ROUTE_RL.md` 和 `LATEST_STATUS.md`。

2026-11-03 用户明确纠正研究方向：**“我们只要做rl选择无人机路线 而不要参与任何选择算子”。**

- RL只直接决策物理无人机路线，例如下一目标、返航和分趟；不得输出搜索算子、邻域、算法家族、算子强度或修复预算。
- 旧CA-RL宏控制器/算子选择器仅作历史负结果，后续不得作为主线恢复。
- 当前计划以 `RESEARCH_PLAN_ROUTE_RL.md` 为准；旧契约的算子控制与“先做一个创新非RL算子再训练选择器”的依赖已被本次方向修订替代。历史结果、协议、锁文件保持原样。
- V6/semfix及审稿包直接复用。旧Route-RL Stage A负结果保留；本次改方向不是其重跑许可，也不是Stage B/C自动准入。
- 2026-11-03 用户已明确要求开始执行G0–G8，重点G4必须多Agent协作。当前窗口已获执行授权；旧两小时截止只约束历史窗口，不作为本次新工作的截止。旧定时器仍暂停，不自动恢复。
- 当前进度先读 `route_rl_research/20261103/STATE.json`。G8为完整研究包和投稿就绪最终验收，不包含公开/投稿授权。新机制、训练、Formal或创新通过只能据新证据记录。

## 2026-11-04 用户模型与执行地点要求

- 用户最新要求覆盖此前模型继承规则：所有子agent强制使用 **Sol + ultra**。创建时显式传入 `model="gpt-6.1-sol"`、`reasoning_effort="ultra"`、`fork_turns="none"`，并提供完整任务上下文；禁止使用Astra。不续用历史Astra代理，未结束工作交由Sol ultra新代理续接。
- 所有新实验、训练、作者求解与质量评测必须在服务器执行，当前使用<REMOVED_ENDPOINT>；不再在Windows运行。历史Windows合成诊断和地图生成来源记录原样保留。

模型版本说明：用户指定Sol系列与ultra，未限定版本号；gpt-6-sol持续429后，使用工具列出的当前Sol版本gpt-6.1-sol，仍强制ultra，禁止Astra。
