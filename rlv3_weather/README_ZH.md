# rlv3_weather · 审后版

[研究设计与主指标](DESIGN_ZH.md) · [完整审计、实验与服务器入口](../rlv3_review/REVIEW_ZH.md) · [学习实现边界](LEARNING_AUDIT_ZH.md)。原始 c193b0d 为历史基线，其 13 项检查与结果不继承为本版科学证据。

从当前包目录运行：

```bash
bash setup.sh
MODE=check bash run_all.sh
```

**下一步请读[联合路线方案与训练命令](JOINT_TRAINING_ZH.md)。** `joint-smoke` 为固定人工数据的最小训练验收；`joint-preflight`、`joint-train` 为需真实票据的新开发入口。旧的顺序式控制实验需显式选用 `legacy-preflight`/`legacy-pilot`，不再把旧 `MODE=pilot` 当作新版训练。
