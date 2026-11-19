# 多无人机巡检物理路线研究：原始证据迁移（2026-11-19）
本目录与 WX6 / E2E v3 是不同研究合同。优先保存已完成固定风 F3 的原件。三个同风条件、24 张独立底图、72 个作者锚点；2 种强非学习对照 × 2 个全进程预算 × 10 个求解种子，共 2,880 份原始输出。没有固定风 RL 胜出的结论。
   
- server_originals/F3_RAW_RESULTS.tar.gz：从实验服务器只读取得的全部 2,880 个 RAW_RESULT.json，未重写 JSON。
- server_originals/RAW_SHA256.tsv：每个注册行的相对路径与 SHA‑256，逐件与先前独立完工收据、DECISION 核对。
- server_originals/RESOURCE_LEDGER.jsonl：该票据服务器账簿原字节，不是实验剩余额度授权。

## 建议从这里读
1. [F3 中文终局判定](fixed_wind/MODIFIED_FILE/performance_g3_analysis_v1/G3_ADJUDICATION_ZH.md)及[完整汇总表](fixed_wind/MODIFIED_FILE/performance_g3_analysis_v1/results/)：严格同风作者成本上限、含返航的最后一架完工时间、全进程 6/12 秒；强 ALNS 相对共同锚点分别改善 15.726630% / 15.727271%。这是非学习精修；独立 n=24，推断参数事后确定。
2. [历史取舍与来源](history/README_ZH.md)：作者复现、无风整趟负载平衡、旧 RL 失败、AIR2 工程及已关闭方向。无风 47 个合格锚点平均 11.412%，事前登记的 36 图子集为 10.951%；不要与 F3 数字相减，不要称固定风 RL 突破。
3. [F3 验收记录](fixed_wind/ARCHIVE_VERIFICATION.json)：19,459 条所选源记录，18,821 项既有终局清单的原始哈希已对上。物理 scorer、强 ALNS、共同 H、driver、统计代码、输入身份、作者原失败和恢复证据都保留。科学证据目录内少量含基础设施标识的文件作了脱敏；具体原始字节与归档字节哈希见 [映射](fixed_wind/SOURCE_TO_ARCHIVE.json)。该目录早期验证中的 raw_result_bodies=0 指紧凑包；本次另在 server_originals 补入了真实本体。
4. [服务器原件](server_originals/)：除 F3 外，还保留无风 465 个 JSON/输入原件及逐件 SHA。包括 7 张小图的精确解及验证记录；[12 个补件索引](server_originals/NO_WIND_EXACT_RECOVERED.json)补齐 history 里因本地占位缺读的这部分。另附 SEMFiX 服务器矩阵 11,407 个 JSON/压缩解成员（P1/P2、J0/J1/J1b/J2/J2b），并非 11,407 个独立比较。原工作区已暴露实例、复现表和旧训练都保持原实验身份；其余未取的旧材料详见 history 的缺读清单。此清单描述的是本地精编阶段，不等于服务器补件后的总损失。
5. **如何核验**：从本目录运行 `python3 verify_public.py`，只读核对全部发布文件和三个服务器原件包的逐件 SHA；不运行求解。每个 tar 内均为相对路径。论文全文、登录配置、凭据、完整系统/运行时和未筛选的服务器日志未在此公开。本目录不是服务器全盘镜像。旧转交资料仍在仓库原位置。
