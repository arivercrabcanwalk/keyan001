# 固定风 A：同站多机联合路线训练入口

从本版起，固定风研究优先使用联合路线，而不是直接把 Grok 旧配置长训。固定站型、机队与目标所属站，策略对所有合法的（站、同站机位、下一目标或真实 RETURN）一起打分。每趟必须保留返航电量，机位累计工时不随返站清零；任务只服务一次。终局用独立固定风审计再验成本和最后返站时间。对构造失败不补作者路线。此模型不选搜索算子，不负责选址，也不处理动态天气与应急单。

## 可以立即运行的工程验收（不需要科研票）

在单个干净仓库副本进入本页所在目录。已有可用的 Python ≥3.10 且能导入 torch、numpy、scipy、pytest 时，将 PY 指向该解释器绝对路径；否则用 setup.sh 建立包内环境。Linux CPU 也能验收。工程 smoke 固定两张内嵌手写图，没有导入科研地图的选项。它确实做优化器更新，不将其作为模型性能证据。

~~~bash
cd rlv3_weather
# 如果没有可用环境：bash setup.sh
# 如果已有环境：export PY=/绝对路径/bin/python
MODE=check bash run_all.sh
OUT="$(mktemp -d)/joint-smoke" MODE=joint-smoke bash run_all.sh
~~~

## 新开发小训（仅 hn01；不是 pilot、Formal 或通用长训）

先取得真实有效的开发票据、G0/G3 收据、按原人口规则封存的地图、完整同风作者原件与成本清单。每票一个风、一个预先登记的 seed、一次启动；另外两个风或其它 seed 不是自动授权。模板、仓库暴露图、历史 HZ01 输入及演示收据都不是新训练票。不要用 GPU 票在 CPU 上运行；没有可见 CUDA 时 CUDA 票应当预检失败，由用户决定另行安排机器或批准 CPU 预算。新机制未经科学验证，不预设 RL 胜出。

~~~bash
# 在本包内，显式设置环境里的真实 TICKET 绝对路径、可写的 JOB 根目录：
: "${TICKET:?须指向本次真实票据}" "${JOB:?须指定绝对作业目录}"
export TICKET
MODE=joint-preflight OUT="$JOB/preflight" bash run_all.sh &&
MODE=joint-train PREFLIGHT="$JOB/preflight" OUT="$JOB/train" bash run_all.sh
~~~

预检冻结源码、依赖版本、文件 SHA 和配置；训练启动重新核验。登记的总墙钟包含真实准入、两种结构、优化、验证及序列化；监督进程在超时杀掉单一 worker。超时/崩溃保留已写日志，不自动续跑、不得改输出路径复用同一票。全机用户锁与旧驱动共用。启动记录在本用户的 ~/.local/state/rlv3/joint_ticket_attempts/；不要删除它来重试。默认无参数入口只做工程检查。

### 训练实际上比较什么

1. **联合结构与固定机位消融**使用同一网络、物理特征、合法动作和采样预算。联合 actor 选机位和目标；消融先由固定循环选当前机位，再由 actor 选目标/RETURN。后者是严格的表示对照，**不是**原 Grok 事件驱动控制器。
2. 每种结构各拟合一份 BC（行为克隆）；其冻结副本与两个从完全相同权重启动的 PG 端点分别验证。两种 PG 都优化真实物理动作：一组沿用费用/失败代理 J，另一组在全服务、全返站、物理且成本合规时最小化 M_return。每种结构另有使用同候选的非学习贪心。训练时保留未完成和超 cap；不刷步数挑最佳验证 checkpoint，不在本入口打开末次诊断或 Formal。
3. **不是全流程性能胜出比较。** 原 Grok 审修版的事件驱动 trainer 及基线保留（标签为 legacy-preflight / legacy-pilot，需其单独有效票）；本轮 joint-train 不冒充已经跑过该原始对手。原生 min-max ALNS、共同 H 和独立新图确认仍是进一步作科学结论的必要对照。开发验证结果不能自动入论文。

### 输出怎么读

- SUPERVISOR.json 的 exit_status 必须为 0，RESULT.json 必须齐全。这只表示工程执行结束，不代表 RL 更好。超时或不完整端点查看 FAILURE.json、子目录 receipts.jsonl，不认作成功训练。
- 每种结构子目录中保存 initial/bc/frozen_bc/pg_j/pg_m 的 checkpoint、输入合同、实际更新数、权重 SHA 和包含失败的 validation.jsonl。没有候选、未返站、超支或回退均不算合规。
- PAIRED_VALIDATION.json 保留每张验证图每个方法的双方状态；只有 joint 与 serial 两方均合规才报告返站时间差。先报告全部登记图的合规数，再看双合规差值。一次小训不输出“达到全项目 G0/G3”或自动开始长训。

### 提供票据给驱动

原基础格式是 ticket.example.json；附加 joint_training 的**准确字段**、三类外部收据及几何排除集要求见 rlcore/joint_inputs.py 顶部文档，示意数字不是批准。G0/G3 收据必须一并、逐项批准该块。代码审定后，在包根的同一环境执行以下只读命令取得实际源码指纹：

~~~bash
"${PY:-.venv/bin/python}" -c 'from rlcore.joint_inputs import implementation_fingerprint; print(implementation_fingerprint())'
~~~

单票全轮最大 BC 更新=2×bc_epochs；PG 更新=4×pg_steps；训练采样轨迹=4×pg_steps×rollouts。科学入口要求 bc_epochs≥1、rollouts≥2。不提供把旧图、失败收据或公开仓库模板提升为批准文件的生成命令。
