# e2e_server_run_v2 运行时补丁记录（E, RTX 3090）

代码基线：commit `bdb6506`（`e2e_server_run_v2`）。

## 迁移
- 从 v1 `e2e_server_run/runs/route/` 复制 `last.pt`, `best.pt`, `curve.jsonl`（训练到 `it=1533`, `elapsed=1.18h`）。
- v2 s2a 从该检查点续训，日志确认：`[route_train] resumed it=1533 elapsed=1.18h`。
- 未改 route 模型结构、奖励、数据或课程。

## 必须的运行时修复

### P1 `baselines/tsalns_java/run_tsalns.py`：补 `--reserve`
- 上游 v2 把 `ap.add_argument("--reserve", ...)` 误写进了注释，导致 s1 的 dev 预留阶段 `AttributeError: 'Namespace' object has no attribute 'reserve'`。
- 修复：真正添加 `ap.add_argument("--reserve", type=float, default=0.0)`。
- 不改 TSALNS 算法；只让 `--reserve 0.1/0.2` 生效。

### P2 `run_all.sh` 的 s2a/s2b：加 `--chunk 8`
- 3090 只有 24GB；v2 默认 route 在 n=50/80 时峰值约 23.5GB，v1 曾在同样位置 OOM。
- 在 s2a/s2b 的 `route_train.py` 调用中追加 `--chunk 8`。
- `B/N/aug/seed/学习率/奖励/课程/预注册门槛` 全部未改；v2 自己的 `B=32*(50/n)` 自动 batch 仍生效（n=80→B20，n=110→B14，n=150→B10）。
- 这是显存适配，不是实验参数改动。

### P3 环境变量
- `PYTORCH_ALLOC_CONF=expandable_segments:True`，降低碎片导致的 OOM。
- `NCPU=20 W=18`（E 的 cgroup 是 20 核；`nproc` 报 256，必须显式限制）。

## 未改
- PREREG、seed（0/1/2）、reward、J5 权重、场景、天数、门槛、TSALNS 预算。
- 旧 `e2e_server_run/` 保持不动；所有 v2 结果在 `e2e_server_run_v2/`。
