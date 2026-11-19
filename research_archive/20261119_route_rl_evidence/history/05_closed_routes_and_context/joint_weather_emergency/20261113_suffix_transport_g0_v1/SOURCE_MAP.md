# 两份直接主源及固定作者源

行号指本包提取文本／原样源码；保留原HTML、API响应和失败。元数据用于发现，不作为未读原文的定理证据。

|来源|原式／源行|实际结论与边界|
|---|---|---|
|Drakulic, Michel, Mai, Sors, Andreoli, [BQ-NCO: Bisimulation Quotienting for Efficient Neural Combinatorial Optimization](https://arxiv.org/html/2301.03313v3)，2023-09-28 v3|BQ_primary.txt 15–29，Eq1–2，Proposition1|direct constructive MDP与最优解对应；明文要求状态可扩成完整可行解，不能把局部battery mask当全局可扩展性证明。|
|同源 §3|30–46，Eq3，Proposition2|`(f*y)(x)=f(y∘x)`、`X*y={x:y∘x∈X}` 定义完整tail subproblem；不同前缀可归并的条件包含未来目标与可行集合，非只剩余目标ID。|
|同源 §4、Appendix A、E.3|47–59；130–143；170–171|子轨迹监督、origin／剩余容量、direct/via-depot输出和轨迹预处理已有；其公开实验为imitation，不当成已验证本项目RL增量。|
|Vidal, [Hybrid Genetic Search for the CVRP: Open-Source Implementation and SWAP* Neighborhood](https://arxiv.org/html/2012.10384v2)，2021-10-12 v2；2022 C&OR|HGS_primary.txt 16–33，尤27、29；35–49；52–60|片段OX＋Split、2-opt*、资源／插入信息缓存已有。SWAP*的专门新效率来自Theorem1的有限候选结构；不以“用缓存”概括或冒充它。|

BQ 论文给出的旧库 `ddrakulic/BQNCO` 在固定 commit `05fb8586bcad95b71b5b2b1625374cc2d0ed2743`、2023-11-09 只含 README；README 明确指向 `naver/bq-nco`。后者固定到 `b7f927faf1d87dca699361312471c10ecc8dd346`、2023-11-17，完整tree未截断。它晚于所读v3，未证明为论文实验提交。没有把旧空库当“作者没有代码”。

|BQ作者源码|读取范围|对象|
|---|---|---|
|BQ_dataset.py|全文116行；90–115核心|随机 begin_idx 截取后缀子问题，并取对应 remaining_capacity；不是未经资源记录的任意前缀配对。|
|BQ_decoding.py|全文287行；140–149、152–191、229–287核心|direct/via-depot动作，重排起点与剩余点，按via-depot重置容量；未包含本项目的两身份slot累计duty和全图成本cap。|

HGS当前作者库固定 HEAD `1a927955cd2861a29d978f0d359d6e647db9319c`、2025-03-26。其README明确指认 **v1.0.0** 为论文结果版本，API解析为 `35b32d8e9552074f52444d51ea1fe8aec9055467`。本轮因此另取该tag的 LocalSearch.cpp；作者的版本关联陈述保留，未在本机或<REMOVED_ENDPOINT>复现实验。

|HGS作者源码|读取范围|对象|
|---|---|---|
|HGS_PAPER_LocalSearch.cpp|395–451、630–678及局部相关范围|move9的tail交换使用cumulatedTime/cumulatedLoad评价，再更新route链；updateRouteData缓存累计资源。只读相关函数，不声称全文审计。|
|HGS_LocalSearch.cpp（2025 HEAD）|相关函数定位与少量摘读|保留发现路径；最终源行结论绑定paper-tag文件，两个版本未混用。|

2014 *A unified solution framework for multi-attribute vehicle routing problems* DOI `10.1016/j.ejor.2013.09.045` 及2024 *A note on...* DOI `10.1016/j.ejor.2023.11.037` 仅取得CrossRef元数据；未取得其全文，**不据此宣称原式已核对或某定理错误**。作者旧站握手超时，另一个候选主页404，均保留失败；之后改用已取得的HGS正文和指定版本源码，不盲重试这些主页。一次arXiv检索的truck-and-drone等无关项不作本项目先例证据。

核心原件SHA256：

```text
BQ_HTML.html e5dfdc0fd80d1d82917924a665318111c5d32e90155bbb43a5c3af37448ef04a
HGS_HTML.html 4ef9dd7e5381d5ae749ac6f499c0d39d4e58d4a45a87cd2e24084d1e79f5df2b
BQ_dataset.py 5d6d99b76966c7bd24cf9fb43ae9a5cda605c1e6c7b141d4ee8e6e5016b76cb8
BQ_decoding.py 77e9b2d0e5e5f990cd7a47784d1c685d9848f9443c46fb9b65c7b6c3d4dd2bd6
HGS_PAPER_LocalSearch.cpp 05a88b07fe8556a1918245baa7d43c97d49ced40c0c15d0e0b21fc1e7e757564
HGS_README.md 691038e55b1328658efc8def95c115c4d62f7ee1b36fb819148d5bb643cb7ff5
```
