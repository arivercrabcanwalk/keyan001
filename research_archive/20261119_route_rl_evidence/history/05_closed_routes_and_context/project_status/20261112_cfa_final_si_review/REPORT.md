# 信息惩罚评分的静态审查与全文缺口

本轮取得三份公开原文，核对了信息松弛的基本对偶公式，并关闭一个明确的评分候选：在当前静态全信息构造模型中，下一状态价值减其正确条件均值恒为零；动态版本的基本运算已有先例。裁决为`G0_NO_GO_CENTERED_DUAL_SCORE_STANDARD_AND_STATIC_ZERO`。这是原式与源码支持的静态准入判断，不是新的RL负实验或所有静态学习无效的结论。

## 已证实事实

|证据|实际取得与阅读层级|
|---|---|
|[Brown、Smith、Sun 2010](https://people.duke.edu/~psun/bio/785.pdf)，Operations Research58:785–801，DOI10.1287/opre.1090.0796|作者Duke站点公开PDF17页；重点读取PDF3/5/6（印刷787/789/790）的弱对偶、居中惩罚及有条件无偏嵌套估计；PDF3/5/6已渲染目视核对|
|[同文online appendices](https://people.duke.edu/~psun/bio/Information_Relaxations_and_Duality_in_Stochastic_Dynamic_Programs_ECompanion.pdf)|作者Duke站点公开PDF15页，含封面；读取并目视核对PDF2–3（附录印刷1–2）的条件化/可测性证明。补充材料实际取得，与主文下载器bare-PDF路由的`si.not_found`自动提示分开|
|[Jiang、Al-Kanj、Powell arXiv1704.05963v1](https://arxiv.org/abs/1704.05963v1)|33页，2017版，题名没有最终版的Optimistic；重点读取PDF9–11、式(4)–(8)，近似价值惩罚与状态动作对偶界已有。未取得2020期刊最终版，不替换版本|
|当前global_env.py|只读reset/observation/step、距离/速度/服务/电量/duty及终局验证；固定实例与动作确定下一构造状态。没有导入或执行研究模块|

完整输入输出、公式推导、先例差异、反证预测、共享信息/候选/预算对照及关闭条件见`MECHANISM_SPEC.md`。`ORACLE_QUALIFICATION.md`补齐信息界、限时启发式和可部署rollout的资格区别，包含一个纯符号算例；它不计作Liu严格cap机会证据。

本包明确区分无学习non-RL、监督/BC学习式non-RL和真正RL更新。监督引导规划仍有资格进入最强non-RL，不因含学习而被剔除；只有与其等信息、等候选、等预算的比较才支持RL独立增量。两篇用户正文的逐式结论见`../20261112_zhao_han_fulltext_audit/EQUATION_AUDIT.md`：Zhao已经有VFA、真实rollout与RE，Han已经有共享区域容量约束。论文原有方法收益未转记为本项目结果。

原99书目仍为97字段核实/2原作者错误/0待核；本轮新先例单独附录，不插入原99条或改分母。Liu复现、oldbeam与SCST/LOO等既有科研结论未变化。

## 当前未证实假说与取得缺口

CFA2025最终版（DOI10.1016/j.trb.2025.103335）CrossRef正式版本许可证已确认为CC BY 4.0，但本轮公开API默认响应只有coredata，FULL视图401，浏览器停在出版社验证页；下载器未定位文件。PFA/oracle的最终定义仍未读，不能由2024工作稿或最终摘要替代。未把access failure说成无OA。

Zhao/Han用户PDF的所有外部链接已静态提取，未发现直接SI资产链接；Zhao正文已声明独立SI，Han在线SI存在性仍未核实。没有猜测mmc文件名并将404解释为无SI。两篇正文及既有关键公式审计继续有效。

居中惩罚在任何获准动态模型中的有效估计、公共历史充分性、模型误差、实际完整路线质量及同墙钟优势均未知。近似价值函数本身或监督规划可能有工程作用，本轮没有相应科学证据。

## 失败或关闭方向

关闭上述具体评分提案的创新/静态信息增量主张，不复活既有观测时机、whole-station exact、partial-trip、R3、energy-duty projection、R5、旧WX-E/WX-C等失败身份。没有将PD-MCTS树展开选择作为RL动作，没有启动WX-H。

当前静态合同仅(slot,target)/(slot,RETURN)、固定部署/站型/目标所属站、累计duty、逐图C<=C_Liu+1e-7、epsilon0、同整图6s/12s改善M_return；MTC辅助。WX WAIT/均值1%成本协议不替代它。

## 下一项有界、可验收工作

对尚未有明确独立运算的候选不再写泛化的“未来价值”提案。下次仅当出现具体新构造/估计步骤或取得会改变差异判断的最终原式时，逐项核对数学增量和同信息强对照；否则维持G0 NO-GO。CFA最终正文与Zhao SI缺口保留为待取得证据，不循环请求同一受阻入口。

G0/G3/G4未通过，G1有限工程，G5–G8未完成；整体goal保持active。本轮实验、训练、作者求解、科学质量评价、新地图、<REMOVED_ENDPOINT>连接和子agent均0。

## 是否需要用户决策

当前不需要；正文+SI已授权，无需重复确认。验证页未操作，未要求你处理；本轮静态推导与关闭裁决已独立完成。没有申请新训练、动作扩展或数据额度。

完整文件事务和隔离副本回滚见`VERIFICATION.txt`。该验证只核对文档、哈希与恢复状态，不是科研实验或科学准入。
