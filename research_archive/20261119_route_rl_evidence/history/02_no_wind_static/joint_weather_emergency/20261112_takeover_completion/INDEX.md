# 20261112_takeover_completion — 包索引

接手 Liu/LRPHSD 物理路线 RL 项目的完成包。**先读 `REPORT_ZH.md`**，技术细节按需进入下表。

## 一句话结论

在静态 S 合同内，**只做 slot 换标签**（不改路线、不改成本、1 毫秒）就能让 M_return 下降 **11.412%**（47 图，未见 36 图复现 −10.951%），
因此既有的"平均 5% 改善"门槛失去判别力；但换标签**不是天花板**：允许改趟划分后，一个非学习的 min-max ALNS 在 46 图上相对地板 **22 胜 0 负**（8x80 从 240.788 降到 159.628，−33.7%，等于精确下界）。
G0 裁决 `NO_NEW_DISTINCT_MECHANISM_NO_TRAINING`，**本轮 0 次训练**。G3 仍未通过，G4–G7 未启动，整体研究未完成。

## 交付清单（对应接手指令 §16）

| §16 要求 | 本包文件 | 状态 |
|---|---|---|
| TAKEOVER_AUDIT.md | `TAKEOVER_AUDIT.md`（497 行，19 阶段 × 11 列，K1–K15 冲突） | 完成 |
| PAPER_EQUATION_COMPARISON.md | `PAPER_EQUATION_COMPARISON.md`（533 行，逐式 + 行号） | 完成 |
| MECHANISM_SPEC.md | `MECHANISM_SPEC.md` + `G0_DECISION.md`（10 候选 × 六项 + T1–T6 定理） | 完成（裁决 NO-GO） |
| GATE_DECISIONS.json | `GATE_DECISIONS.json` | 完成 |
| ENVIRONMENT_AND_SSH.md | `ENVIRONMENT_AND_SSH.md` + `SERVER_INVENTORY.md` + `SERVER_MANIFEST.json` | 完成 |
| PUBLIC_ROLLOUT_CONTRACT.md | `PUBLIC_ROLLOUT_CONTRACT.md`（1,269 行，T1–T7 可执行测试） | 完成（规格，未实现） |
| BASELINE_QUALIFICATION.md | `BASELINE_QUALIFICATION.md` + `BASELINE_REGISTRY.json` | 完成（规格） |
| PREREG.md | `PREREG.md`（首段自陈非盲验） | 完成 |
| SPLITS_AND_EXCLUSIONS.json | `SPLITS_AND_EXCLUSIONS.json`（含本轮新人口登记） | 完成 |
| EXPERIMENT_MATRIX.csv | `EXPERIMENT_MATRIX.csv`（19 行 × 14 列，8 族） | 完成 |
| RESOURCE_LEDGER.jsonl | `RESOURCE_LEDGER.jsonl`（31 事件） | 完成 |
| RUN_LOG.md / STATE.json | `RUN_LOG.md` + `STATE.json` | 完成 |
| results/ / solutions/ | `results/`（含每行完整解与证书） | 完成 |
| models/ / receipts/ | `models/README.md`（0 模型，说明原因）+ `receipts/` | 完成（无模型是真实状态） |
| FINAL_TABLES.md / STATS.json | `FINAL_TABLES.md` + `stats/STATS.json` | 完成 |
| CLAIM_EVIDENCE_MATRIX.md | `CLAIM_EVIDENCE_MATRIX.md`（17 条主张 + 6 条不支持） | 完成 |
| REPORT_ZH.md | `REPORT_ZH.md` | 完成 |
| REPRODUCE.md | `REPRODUCE.md` | 完成 |

## 额外交付（§16 未列但本轮需要）

| 文件 | 作用 |
|---|---|
| `G3_REPORT.md` | 主实验报告（开发 + 确认 + 精确最优 + 强基线 + C04 定位） |
| `G3_INDEPENDENT_AUDIT.md` | 独立逐位复核（13 条不符全列） |
| `EXACT_MINMAX_REFERENCE.md` | 6 图全局精确最优证书（5 重检查） |
| `STRONG_NONRL_REPORT.md` | 强 min-max 非 RL 基线：46 图 22 胜 0 负（8x80 −33.7%，等于精确下界） |
| `public_rollout/` | 公共因果环境与真实 rollout 工程：T1–T7 全过 52 条断言、4/4 变异体被抓、独立 episode 复算；边界见其 `public_rollout/DOCS_IMPLEMENTATION.md` |
| `CLOSED_DIRECTIONS.md` | 33 条关闭方向 + 重开条件 |
| `CODE_MAP.md` | 代码地图与 evaluator 精确合同 |
| `PRIOR_ART_EQUATION_AUDIT.md` | Zhao/Han 逐式（含 Zhao SI 已取得） |
| `WX_PILOT_RECEIPTS.md` | 13 包 3,520 行逐行复算 |
| `RESULTS_MANIFEST.json` | 477 个文件的 SHA256 冻结 |
| `harness/` | 全部可复现脚本（生成/锚点/非RL/精确） |

## 读法建议

1. 想知道"发现了什么" → `REPORT_ZH.md` §1。
2. 想核对数字 → `FINAL_TABLES.md` 与 `stats/STATS.json`，再追 `results/`。
3. 想知道为什么不能训练 → `G0_DECISION.md`。
4. 想复现 → `REPRODUCE.md`。
5. 想知道哪些历史数字是错的 → `REPORT_ZH.md` §1.6 与 `CLAIM_EVIDENCE_MATRIX.md`。