# public_rollout

公共因果环境 + 真实 rollout 的工程实现（合同见 `../PUBLIC_ROLLOUT_CONTRACT.md`）。

- `env/core.py` 对象与不变量 · `env/forecast_book.py` 版本化预报 · `env/latent_phase.py` 隐藏过去/阶段采样
- `env/causal_engine.py` 事件闭包/固定顺序/reservation/中途分叉 · `env/exogenous_stream.py` 移动 NFZ + 背景 Poisson 释放 · `env/episode_audit.py` 独立全 episode 复算 · `env/snapshot.py` 导出前缀
- `policies/mu.py` 确定性非学习基策略 · `fixtures/build.py` 手写夹具
- `env/metrics_w.py` W 三指标 · `drivers/run_episode.py` intent→run→fsync 行 · `tests/run_all.py` T1–T11 · `tests/mutation_check.py` 变异检验（8 个变异体）

**先读 `DOCS_IMPLEMENTATION.md`**：它列出与合同的 6 处偏差和 7 条弱断言，是本包结论的边界。

状态：T1–T11 全过（72 条断言），8/8 变异体被抓；物理已改为两阶段（FLYING→SERVING），W 三指标可算。仍**不是**合同全部断言的通过证书（告警参数是工程默认值而非拟合值，见 DOCS §3 H-3）。