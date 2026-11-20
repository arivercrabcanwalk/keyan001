# 两包场景静态审核（2026-11-20）

证据类型为源码静态审核。审核对象为 keyan001 当前工作副本；本记录不建立实验准入或方法性能结论。

## 结论

未发现需要立即修改两套实验共享物理源的已确认新缺陷。下列合同在已读代码中一致。尚未执行路径的正确性不据此保证；现有物理/事件反例证据继续按原验收记录解释。

## B：事件可见性、结束及指标

1. `rlv3_emergency/rlcore/env.py:131` 的候选集合仅含当前已发布、未完成、未claim且有站资格的任务；`feat.py:107` 的urgent上下文同样按release过滤。`policies.py:123` 的REOPT从该候选集合构造问题。完整未来流保存在模拟器中供外生发布调度和最终全发布分母使用，不是当前actor特征。
2. `env.py:272` 在精确发布时间唤醒站内空闲机；`env.py:285` 在同一公共时钟先推进全部在途/服务机，再开放节点决策。当前合同是节点决策，飞行与服务不可抢占，不能写成发布瞬间允许全部飞机改向。
3. 无可行续接或600分钟日界均可结束；没有skip不推出全部完成。`env.py:369` 保留全部冻结高/普通优先请求作为分母；到场不晚于deadline且随后服务成功才计准时。零高优先请求的比例为null/N/A。
4. `train.py:146` 对B的检查允许紧急请求未完成，但要求常规任务全部完成、无失败和实际返站；这与以全发布时效为主指标相容。报告不能把B的checkpoint资格写成全紧急任务完成资格。

## A：固定风、任务职责及动作

1. `rlv3_weather/rlcore/joint_route.py:67` 从已审核锚固定部署与每个常规目标的站归属；`:115`拒绝跨站常规任务。动作只选择物理站/机槽/目标或RETURN；机槽内目标归属、分趟和次序可以改变。
2. `joint_route.py:132` 的RETURN实际增加返程工时并换电，累计duty不清零。每趟的node.energy沿用原作者字段；固定风仅通过风三角改变飞行时间/能量。最终`:317`独立调用fixed_anchor，检查完整路线、实际闭趟与同风成本cap。
3. `joint_learning.py:143`的serial是同一个JointActor在固定机槽循环顺序与动作子集下的表示消融，不是传统独立agent，也不是对旧Grok串行控制器的复现。应明确命名，避免把结构限制的结果当作多agent对比。
4. `joint_route.py:155`的mask只提供必要可行性检查，合法动作仍可能导致dead_end。所有失败轨迹和验证分母必须保留，不应称mask为完整可行性oracle。
5. A的JointRoute和旧通用Env是不同执行接口；涉及最终同风cap与精确电池边界时以JointRoute的独立终局审计为准，不把旧Env通用physically_feasible字段当作完整作者锚证明。

## 两负责人的执行建议

- A负责人：预先固定评估人口/种子/端点；joint与serial应保留相同初始化、计算预算和失败分母；最终质量只比较eligible完整闭趟解，分别展示完成率、cap合规和M_return。
- B负责人：全发布高优先分母、常规完成率、实际返站与物理失败并列报告；不要因零高请求或不可服务请求重抽日期；节点响应与到场SLA的含义需保持一致。
- root：REOPT源码定义为自写insertion+relocate+2-opt+merge，不是作者TSALNS/ALNS或已认证最强非RL；固定风科学场景不要与动态天气/禁区配对工程场景混写。

## 共享源码身份

{
  "rlcore/env.py": {
    "rlv3_weather": "1271d252e4a848367aa186d564b27ff1aafa2112cae19a4e7ec8083a72e49057",
    "rlv3_emergency": "1271d252e4a848367aa186d564b27ff1aafa2112cae19a4e7ec8083a72e49057"
  },
  "rlcore/phys.py": {
    "rlv3_weather": "616f8c2fa9477ab22dcff2b2b1d0e986d80b95808d18413674a29bce2284fdae",
    "rlv3_emergency": "616f8c2fa9477ab22dcff2b2b1d0e986d80b95808d18413674a29bce2284fdae"
  },
  "rlcore/weather.py": {
    "rlv3_weather": "dc691d39ef7690c94fb2e4f85509404bfc2e96a7f76c3b2730841af6e49584d1",
    "rlv3_emergency": "dc691d39ef7690c94fb2e4f85509404bfc2e96a7f76c3b2730841af6e49584d1"
  }
}

三组文件在两包间逐字相同。审核仅新增本记录，未修改源码。
