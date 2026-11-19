# 同池强non-RL控制补齐：有限站schedule精确组合

## 已证实事实

仅root在<REMOVED_ENDPOINT>完成5个预登记模块，全部exit0，child CPU0.688247秒、wall合计0.7222886583767831秒、最大rss18304KiB。新可调用`station_bank.solve`对完整物理父解建立每站完整两slot多趟schedule池；固定阈值下按原站/slot累加顺序最小化全图成本，再用独立完整validator验收。它没有将全局cap误改为逐站cap，也没有删掉全图超cap但局部有用的父解schedule。

3固定风×3手写anchor共9输入，阈值方法与每输入27组合的完整穷举在M和完整成本上9/9完全一致，9/9独立TARGET/RETURN物理复算。原始anchor、父解及输出完整保留。东风手写例anchor M12、父解1 M8，同池nonRL得到M7/cost145.2；此数值是三站六目标新工程fixture，非旧四目标复跑、非Liu作者或科学地图效果。

9项错误身份/固定域/参数/不完整/重复/能量/duty/篡改anchor拒绝，2个字面加法/忽略全局cap变异被抓。单slot两趟duty14不清零。单独1e16标量边界证明重结合浮点求和可能错失原字面cap可行组合；它不是物理地图、不是创新或有意义的质量headroom。

另一副本1/1原hash、原九行完整JSON和stdout恢复，修改前备份保留，主`MODE=threshold_monotone`保留。五依赖与两保护科学STATE原字节、旧40身份/126比较/24校准额度不变。未重跑1200/48/104/20交错/ECHO五模块。

## 未证实假说

候选`FEASIBLE_STATION_BANK_PAIRING`把旧bank期望平均改为可行组合最小M的best-of-bank目标，确实是不同目标对象；但目前只剩标准终局收益log-derivative和池重组，没有非直接新步骤，不训练。没有证明此控制在新科学人口和6s/12s端到端胜出，也未解决任何新RL的G0/G3准入。固定风路线RL仍未证明胜最强nonRL/作者，CCF-B目标/G8未完成。

## 失败或关闭方向

本轮没有进程失败/超时/修复重跑；9拒绝和2变异都是预登记负控制，不称新科研负结果。`FEASIBLE_STATION_BANK_PAIRING`未立项为新机制；旧product平均信用、条件score、R7 crew、ECHO迁移不复活。CMSA-RL已有池组合学习，Kuntz已有product估计器；约束差别和更换终局目标不能代替具体新步骤。

本组件仅最优于给定有限站schedule池，无法作池外全路线最优性或动态事件流证书；池外强ALNS保留其原生搜索。原科学cap未变，手写anchor不冒充作者锚点。工程父监督不替代科学driver端到端deadline。

## 下一项有界工作

固定风与简单能耗先行。下一G0对象尚未选定；优先针对物理slot分配/访问次序/RETURN分趟的新增构造或学习步骤，不再以标准池组合器、best-of-K、阈值、score或网络特征重立。只接受六项规格、原式差异与可证伪完整路线见证；有新步骤才另登记<REMOVED_ENDPOINT>检验。G0/G3后再开展足量独立训练seed/消融/新Formal。

## 是否需要用户决策

无新增问题。原WIND_COMPARISON_PROTOCOL的A/B仍待既有答复，不重复询问、不默认新cap批准；本轮工作独立于此决定。已有goal active，整体研究仍未完成。
