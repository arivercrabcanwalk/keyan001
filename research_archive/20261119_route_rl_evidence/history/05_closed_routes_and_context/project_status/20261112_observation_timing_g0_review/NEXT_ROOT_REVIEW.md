# 下一项有界证据工作

下面是可复用的研究接续 prompt。保存文件不会创建任务、派遣代理或运行代码。

```text
只由root继续Liu/LRPHSD，先读LATEST_STATUS和本包REPORT。
本轮只核对原99条书目中15个manual_needed，不实验、不训练、不求解、不质量评价。
读取20261112_original_prompts_cfa_audit/BIBLIOGRAPHY_AUDIT.json与原REPORT_ZH，
冻结这15条的标识与原字段后，对每条最多访问一个正式出版社/会议主来源和一个对应官方入口。
第10条查Banaszak/Zbigniew姓名字段；其余14条查arXiv与正式会议的作者、题名、年、卷页关系。
不同版本分列，不把预印本作者字段或网页发布日期直接当正式会议年份。
输出逐字段证据URL/时间/原响应hash、verified/mismatch/manual_needed和保留原因。
不要把新发现文献插入原99条改变分母；原封存包不改，只在新包追加纠正。
完整全文阅读、元数据核实、摘要线索三个证据层级分别记录。
正文与SI范围已获确认，现有Zhao SI/Han在线SI/CFA最终版定义缺口保留，不重复询问。
这项工作不放行G0/G3/G4，静态动作与逐图Liu cap/M_return和6s/12s合同保持。
回报分开：事实、假说、关闭方向、下一有界验收、用户决策。
```
