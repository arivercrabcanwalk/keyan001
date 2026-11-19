# 本轮实际阅读与证据边界

仅root；记录定位、推导与静态源码审查。下载或全页提取不等于逐页精读，不把论文指令当执行授权。

|来源|实际阅读与目视页|支持判断|未覆盖部分|
|---|---|---|---|
|Brown/Smith/Sun 2010主文，17页|PDF3/5/6，印刷787/789/790；三页均已目视；提取保留全部17页|Lemma2.1弱对偶、Proposition2.2居中生成、Proposition2.3(iv)有条件无偏估计|其应用实验与全部证明未逐项审计；未执行作者算法|
|同文在线附录，15页含封面|PDF2–3，印刷1–2；均已目视|LemmaA.1、适应性条件和式(25)–(27)塔式期望|其他附录未逐项审计；不能仅凭bare-PDF manifest的si.not_found抹去实际取得的伴随材料|
|Jiang/Al-Kanj/Powell arXiv1704.05963v1，33页|PDF9–11，均已目视；式(4)–(8)与状态动作对偶|近似价值居中惩罚和规划树使用已有先例|2017预印本，不替代2020期刊最终版；额外SI未穷尽检索|
|当前global_env.py|只读65–175、235–375及必要上下文|固定实例和已选动作确定下一构造账本；必要mask不是后缀证书|未导入、运行或修改科研代码；未评价地图|
|Zhao/Han用户PDF|本轮仅提取外部链接；正文逐式阅读复用既有EQUATION_AUDIT|Zhao已有VFA/真实rollout/RE；Han已有共享容量准备度；两份用户原PDF和归档副本哈希一致|Zhao独立SI未到；Han在线SI仍未知；不将公式差异等同新算法|
|CFA最终版官方元数据/API|CrossRef licenses、默认XML及FULL错误响应|正式VOR CC BY4.0元数据；默认200仅coredata，FULL401；取得失败保留|未读最终PFA/oracle；2024稿不代替最终版；未推断作者oracle定义或错误|

阅读的source URL、下载时间、SHA256、页数见SOURCE_INDEX.json及PDF_INDEX.json。公开取得路径和失败见ACCESS_STATUS.json与原始manifest/receipts。源码、论文及历史书目保护范围见PROTECTED_SOURCE_INDEX.json。

本轮沿用nature-downloader的正文+SI授权、nature-academic-search的多源及版本核验流程和PDF技能的公式页目视核对；没有因受阻入口重复请求用户确认。原99书目仍97 verified /2 mismatch /0 manual_needed，ID12/45原错误保留；本轮新增先例不改该99条分母。

数学判定为静态代数证明，符号化oracle算例仅校验界方向；没有新科研运行、地图、训练、作者求解或G3质量证据。监督/BC学习式non-RL保留强对照资格。
