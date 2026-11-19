# 主源、版本与实际阅读范围

机器可读hash/路径/边界为本包`SOURCE_MAP.json`；本包没有复现任何作者实验。

|主源|实际核对|用途与限制|
|---|---|---|
|[FK steering v1](https://arxiv.org/html/2501.06848v1)|§3.1–3.3、Eq1–7、Alg1及interval/many-sample/learned reward|普通粒子/势/重采样/guide先例；没有声称全文精读|
|[LGS v2](https://arxiv.org/pdf/2506.03672v2)|§3.2–3.3、§4.1–4.3、Eq1–5、Alg1、§5.1假设1–2/Theorem5.2|当前主方法MCMC+SA；有正性/对称proposal等假设，不直接证明本项目hard-cap/T|
|[LGS作者代码固定提交](https://github.com/SobihanSurendran/LGS/tree/ef75b5a900725b5e407c7d1d15cee87bc04a0183)|README、CVRP/test.py和train.py全文；model encode/forward/decoder和env资源mask相关片段；4文件AST|静态代码读取，不导入模型；commit早于论文版本，未证为实验提交|
|[作者出版列表](https://sobihansurendran.github.io/publications/)|两个LGS条目及各自链接|明确ICML论文与ICLR workshop是两个入口，不能仅凭同一代码链接混同方法|
|[workshop独立PDF](https://openreview.net/pdf?id=0ljRxP9y5W)|本轮403 HTML；原response保存|方法全文未取得；不作为已读方法或新颖性支持|
|[FIVO2017](https://proceedings.neurips.cc/paper/2017/file/fa84632d742f2729dc32ce8cb5d49733-Paper.pdf)|复用同hash原件，§4.1 Eq8|重采样梯度已有先例；FIVO目标与本项目人口交付效用分开|

LGS的abs明确v1=2025-06-04、v2=2026-06-09；本次PDF固定v2。代码commit为2025-05-26；只记录时间差，不据此断言作者结果有误。FK固定v1，不将最新v5元数据当已读方法版本。

本项目原代码定位直接复用：

- `route_rl_research/20261103/source_snapshot/route_rl/policy.py`的`PointerActorCritic`/`policy_step`：已有全支持TARGET/RETURN底座；旧失败身份不重训。
- `joint_weather_emergency/20261106_D_C2_engineering_v2/MODIFIED_FILE/route_learning_candidate.py`的`RouteLearningCandidate`及E包`PreferenceActor`：已有神经物理actor，不重造toy模型。
- `joint_weather_emergency/20261113_common_h_delivery_g3_engineering_v1/MODIFIED_FILE/independent_h.py`：共同H下独立生成/费用目标已实现，复用已通过的有限工程收据，不重跑。
- `joint_weather_emergency/20261113_multitrip_iteration_design_v1/MODIFIED_FILE/PHYSICAL_ROUTE_ITERATION.md`：完整TARGET/RETURN到公共T/bank/完整C/M/标准更新规格已存在。

上列旧底座仅作为已读源码定位与继承证据；本包没有新模型执行或独立复现其历史结果。学术MCP/AgentKey三发现工具未挂载，沿已授权内建web和主站HTTP读取；没有安装连接器或要求用户补凭据。
