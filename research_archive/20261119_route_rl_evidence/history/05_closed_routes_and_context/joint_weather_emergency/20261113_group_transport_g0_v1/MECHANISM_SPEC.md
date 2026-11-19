# 空路线成对分组传输：G0有界工程规格

本候选是标准模块的具体组合，原创性和RL质量均待证；G0/G3仍未通过。只启动下述工程，不启动训练、作者求解、ALNS质量批次或Formal。仅root，科研仅<REMOVED_ENDPOINT>。

1. **输入与物理输出。** 固定风A、简单能耗、固定站型/归属，两个从空路线出发的副本使用相同合法mask和固定几何proposal。每个副本只执行(slot,target)/(slot,RETURN)，可以产生旧bank之外的访问顺序及分趟；结束副本以内部吸收态补齐，不执行虚构物理等待。公共T重新分配完整trip，各控制均得到T。工程anchor为手写完整路线，明确不是作者Rw或新科学地图。未来科学仍逐图使用完整作者风适配Rw成本cap、完整Mw和6s/12s退出计时。

2. **一次新增组合操作。** 每个合法物理后继提取目标对中已经不可撤销的SAME/DIFFERENT位集；未访问目标仍可加入开放trip，不提前标成异趟。两个后继只对双方均已决定的目标对计算相反决定比例D。给两个原策略边际p/q，用exp(4D)进行固定12轮Sinkhorn、标准可行化round及0.1独立混合，得到联合动作Q；从Q抽取两个物理动作。不是对完成后路线加多样性奖励，也不是让actor挑分组约束或搜索算子。

3. **完整后果与更新。** 完整raw和T后路线分别调用冻结原scorer；超cap/死路仍计入固定身份和费用，以共同anchor回退计算best-of-two改进。若以后获准学习，目标是E[(Mw(anchor)-min(Mw(anchor),admissible Mw(T(x1)),admissible Mw(T(x2))))/Mw(anchor)]。更新必须用这个联合law的整条score：g=(U-b) sum_t grad_theta log Q_theta(a1_t,a2_t|s1_t,s2_t)，通过实际12轮/round/混合求导，禁止当独立轨迹相加或沿用旧LOO。分段min的边界不可微需另登记，未来验证不能用极限精确OT梯度替代实际程序。本包0参数更新/梯度实验。

4. **最近先例及实质比较。** 双因果耦合/边际约束、Sinkhorn/round、一般policy gradient均已有先例，不主张发明。PolyNet/MDAM/记忆构造也复用原查新。本组合待检验的区别是：在物理构造过程中，以对公共整趟重排不变的不可撤销同/异趟承诺，安排两个副本的联合动作，同时保留各自既有proposal边际。不是完整解等价类修正；同分组仍允许不同完整质量。与相同D直接重加权比较，防止只把增加信息归给transport；与token差异transport及CDF反相关比较，防止普通多样性或antithetic换名。

5. **固定输入、强控制、费用。** INPUT含4手写全新二维几何(5/6/7/8目标)、两固定风、每配置32个固定成对采样身份。控制iid/CDF反相关/token_transport/group_tilt，候选group_transport；同mask/policy/完整cap/T/scorer/固定身份，不挑更好seed。完整子进程退出时间含启动、构造、评分、T和结果写盘。工程不代表完整G3最强对照：共同H独立新生成、强minmax ALNS、公共bank、BC/标准RL、SBS/beam等仍是后续必须保留的科学控制，本包没有运行它们。

6. **证伪、上限、关闭。** 核误差<1e-10；完整路线原scorer逐份复算；T保留trip分组及内部顺序；从真实动作回放独立核SAME/DIFFERENT。候选继续的必要工程条件全部同时满足：8配置至少6有非恒定改进，候选相对每配置所列最强控制至少6/8胜，平均归一化改进额外至少0.01，完整候选/IID进程时间比<=1.5。32身份只作筛查，非统计优越/训练seed。未满足就关闭当前固定组合，不改坐标/强度/温度/采样身份追阳性。四phase串行，合计child CPU<=180s、wall<=240s、每进程地址空间<=1GiB。最多一次仅正确性修复，原失败保留；成功计时不重跑。

可复用接续指令：
```text
先读本包STATE、AUDIT/RESULTS与REPORT_ZH。仅root/<COMPUTE_HOST>；固定风A。
actor只输出物理slot-target/RETURN，保留强ALNS/共同H独立生成/公共T。
本候选从空路线成对生成，transport/round/联合score均为标准工具。
不把分组多样性当完整解质量，不把工程采样当RL训练或科学人口。
按事前条件关闭或继续，禁止在这4几何/2风/32身份上调参。
G0/G3未过，整体goal active，训练/Formal不自动放行。
```
