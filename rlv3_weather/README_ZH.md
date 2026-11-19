# rlv3_weather · 审后版

[研究设计与主指标](DESIGN_ZH.md) · [完整审计、实验与服务器入口](../rlv3_review/REVIEW_ZH.md) · [学习实现边界](LEARNING_AUDIT_ZH.md)。原始 c193b0d 为历史基线，其 13 项检查与结果不继承为本版科学证据。

从当前包目录运行：

```bash
bash setup.sh
MODE=check bash run_all.sh
```

在 hn01 开发实验前，先用相同票据、输出目录及 W 执行 `MODE=preflight TICKET=/absolute/ticket.json OUT=/absolute/new-run W=4 bash run_all.sh`。预检会核对真实输入并写冻结清单，不训练。[票据模板](ticket.example.json)是格式样例，不是获批数据。

默认也是 check：只运行手写工程反例和端到端小例，不求解历史科研图。开发比较必须用新的地图、已核 G0/G3 票据和登记预算，在 hn01 单包运行 `MODE=pilot TICKET=/absolute/ticket.json OUT=/absolute/new-run W=4 bash run_all.sh`。同机不要并跑两套抢同一张 GPU。正式评测单独冻结；本版本的 `MODE=formal` 预期退出 2。
