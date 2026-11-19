# 风、能耗与连续禁区审计（2026-11-19）

本记录审查 `c193b0d560dd128b252936e2c3edc025224dc760` 中的两个民用巡检包。两包的 `rlcore/phys.py` 与 `rlcore/weather.py` 保持相同字节。结论限于手写工程反例和该代码的数学定义；没有读取旧地图运行科学实验，没有训练、作者求解、真实气象回放或实际飞行。

## 1. 可支持的物理域

主研究域是公开已知、全场恒定的三个风向量：W00=(0,0)、W04E=(4,0)、W08N=(0,8)，单位 m/s。`FixedWeather` 使非零风与零风均可走同一物理执行接口，并明确使用 `energy_model=author_simple`：每个节点服务消耗该节点原始 energy，飞行消耗 P1 × 时间。它没有随机预报误差、雷暴或真实机型认证含义。原合成动态天气保留为隔离的工程压力场景，不能因这些测试通过而进入训练或解释为真实天气效果。

坐标与距离用 m，风速和空速用 m/s，时间用 min；名义空速固定为 15 m/s。设单位地面航向为 u，沿程风为 w_parallel=w·u，横风为 w_perp，则最大正向空速分支满足：

```
v_ground = w_parallel + sqrt(v_air**2 - w_perp**2)
v_air_vector = v_ground * u - w
norm(v_air_vector) = v_air
minutes = distance_m / (60 * v_ground)
energy = energy_per_minute * minutes
```

横风绝对值大于空速时没有该航向解；地速非正时没有正向进展。横风恰等于空速且有顺风时可以存在极限运动学解，代码不再把等号一概判成无解。`VG_MIN=4 m/s` 是额外操作规则，不是风三角的必然物理边界。低于它的航段返回 `(inf, inf, False)`，不再用 0.5 m/s 伪造有限飞行时间或能量。输入非有限值、非正巡航空速和非单位方向显式报错。

`W_LIMIT=12 m/s` 只是场景操作阈值，由环境使用。原文引用的 DJI 单机抗风规格不能证明作者两种无人机、不同载荷与整个模型都具有相同额定限制。

## 2. Zeng 公式实际起什么作用

保留旋翼机桨叶型阻、诱导功率和寄生阻力的形状，用两个系数强制匹配 `P(0)=0.020/min`、`P(15)=0.018/min`。当前计算 `ALPHA=0.00011870140661166834`、`BETA=1.4197380678031015`。诱导项改用等价倒数表达式，避免高速度下两个近似数相减。

两点匹配是标定约束。由此再检查相同两个点，或者发现离散网格最省能量/距离速度为 16.5 m/s，都不是独立实验验证。默认飞行空速从不变化，所以整个巡航能耗严格退化为 **P1 × 风致飞行时间**；Zeng 曲线在默认执行里只影响定点巡检的等效空速功率，另用于可选空速网格敏感性计算。没有可行空速时，网格函数现在显式报错，而不是把全 inf 的第一个位置当最优速度。

原合成动态天气中的巡检采用定点维持位置的近似 `P(|w|)`。该曲线可能使适中风下的悬停功率低于零风，例如 `P(8)=0.015549189329950117/min`。这来自所用前飞形状和两点标定，未受载荷、姿态或实飞数据验证，不能解释为已验证的节能效果；三个固定风的主研究模型不使用此悬停曲线。该模型不含起降、爬升、加速、转弯、飞控响应、垂直风、电池老化、载荷差异或湍流附加损耗。

电池单位是作者的归一化可用能量，LD=1、SD=0.81；`P1/P2` 不是 W，也不是 Wh。900 m 零风航段正好需 1 min、0.018 电池单位；10 min 零风巡检需 0.2 电池单位。相同名义参数可使这些基础量一致，**不等于** 在新增硬工时、失败终止或风场执行规则下，任意完整环境轨迹都与作者评估器完全相等。

## 3. 连续禁区与可见性修复

原 `nowcast_hits` 只检查 9 个等距点，路径在采样点之间穿越小禁区会漏报。新实现把无人机位置、预测中心和椭圆半轴写成分段仿射函数。旋转坐标后，消去正半轴分母，得到四次多项式：

```
q(s) = rx(s)**2 * b(s)**2 + ry(s)**2 * a(s)**2 - a(s)**2 * b(s)**2
contact iff min(q(s), s in [0,1]) <= 0
```

端点与导数在 [0,1] 内的根覆盖连续极值；用递归隔根与二分，避免全局伴随矩阵在近零轴增长下受极大根影响。接触和浮点容差以内的边界归为相交。原 `n` 参数仅保留调用兼容，不再决定采样数。`buf` 扩大两个半轴，是定义的椭圆缓冲，不能称作严格欧氏 Minkowski 等距安全带。

新增 `truth_segment_hits(x1,y1,x2,y2,t0,dur)`，按天气网格、单体生灭时间、活动阈值和重采样时刻切段，对真值线性中心/强度插值做同类连续检查。静止巡检可用相同起终坐标检查。检测覆盖的是这个分段插值的合成禁区，不是现实中任意未知雷暴。原单体出生前插值提前显示禁区的问题也已修正；`in_cell`、`nowcast`、真实出流风都不再通过该插值提前看到单体。

`WeatherDay` 的公开时域是 [0,900] min，越界显式报错，不再把天气冻结到最后一个状态无限延长。`FixedWeather` 在非负有限时刻定义相同常风。面积预报只返回已发布 issue 的误差与所设均值，不读隐藏阵风、湍流系数或尚未发布的误差；特征仍需由环境保证只在决策当前时刻调用观测接口。

## 4. 重采样不具备无后见偏差资格

原重采样在零 scale 时出现 0/0→NaN，并完全保留已生单体未来随机轨迹。现已修复；任意非网格切点的过去与当前观测保持原字节值，未来 OU/阵风创新和已生单体漂移重抽，单体索引按原出生次序显式映射。

但此接口仍条件于模拟器隐状态、日参数、已生单体真实形状与寿命，不是从公共可观测历史构造的 posterior/belief sampler。`public_future_sampler_verified=False` 是明确资格字段。该接口只能用作工程敏感性抽样；训练链必须阻断依赖“公共历史条件独立未来”的 RI 请求，不能把改过的接口称为已消除后见偏差。已知恒风的未来确定性也不自动为动态天气 RI 提供资格。

## 5. 工程证据与保留边界

`tests/test_review_weather.py` 为两包共用参数化手写反例。首次修复前运行 26 项：22 failed、4 passed、2 个零 scale NaN 警告，退出 1。扩大后包含风三角向量闭合、能量单位、静止/移动细禁区、切线、旋转、增长半轴、出生前可见性、活动阈值、非网格过去保持、未来分歧、单体乱序索引、空速无解、无效输入和时域边界；修改版最终运行共 36 项通过。首轮新增切线测试曾暴露全局多项式根算法精度问题，原失败不抹去。

同一扩大集在原版与独立回滚副本均为 32 failed、4 passed、2 warnings，退出 1；修改版退出 0。它们是预期的反例恢复，不是把失败收据说成测试全通过。

原始提交保留在 Git 历史；本版[可复验工程证据](../rlv3_review/ACCEPTANCE.md)包含物理反例与独立审核入口。结果只验证模拟器语义，不证明真实安全、100%完成或RL优势。

## 6. 外部完整同风作者锚的独立审计

新增 `rlcore/fixed_anchor.py` 与 `tests/test_review_anchor.py`，不调用 `phys`、`Env`、优化器或距离缓存。`audit_fixed_anchor(instance, solution, provenance=None, *, wind, map_path=None)` 返回严格 JSON 收据；`audit_anchor_file(anchor_path,map_path,wind)` 从外部 `{solution,provenance}` 文件读取并适用于 strict pilot 注册。支持三风 ID、对应场景名或精确风向量。

逐目标核查节点身份与一次完整覆盖、原始 node.energy、站半径、LD/SD 机位与每趟电池，逐机核查累计飞行+服务工时；按作者 vendor 合同的站型 duration 上限计。独立风三角逐边计算飞行分钟，总费用=固定成本+time_cost×总作业分钟，`M_return` 为各机闭趟串接后的最大返站时间。读取 map 原始字节 SHA 并逐字段比对 instance，不能只修改坐标或能量仍复用旧 SHA。

完整同风资格需要 `liu-full-same-wind-author-run-v1` provenance：同 map/solution/parameters hash、风 ID 与向量、author_node_energy_plus_flight_rate、TSALNS、完整运行且求解已使用该风、exit_status=0、完整预算≥1800 s、有限 wall≤budget、原外层 500/内层名义 5000（`outer_iterations=500, inner_iterations=5000, full_strength=true, downgraded=false`）、仓库/40 位 commit/源码 hash/命令/run_id，以及外部运行收据的路径和 SHA。外部收据还须逐字段绑定上述身份。1800 s 配弱化迭代数依然仅为工程。`run_receipt_path` 可以是绝对路径；从 anchor 文件读取时，相对路径以该 anchor 文件的目录为基准。该记录审计只验证所提供证据的一致性，不能仅凭元数据证明实际执行、作者源代码真实性或算法最优；root 仍应核验实际远端原始运行证据。

资源可行而缺少完整身份、只有 10 s 预算、或拿 W00 作者路线在非零风重评分时，结果为 `ENGINEERING_ONLY`、`scientific_eligible=False`；真实资源失败为 `RESOURCE_AUDIT_FAILED`。完整绑定得到 `FULL_SAME_WIND_AUTHOR_RECORDED`，`formal` 永远为 false。收据还包含每趟能量/余量、参数 hash、provenance hash 及自身 audit hash，可由注册器冻结。手写测试只建立这个审核器的行为，不生成任何真实作者解。

从 `rlv3_weather` 包目录执行的实际 CLI 形式如下，外部文件路径需替换为待审核文件：

```sh
python3 -m rlcore.fixed_anchor --anchor /absolute/path/anchor.json --map /absolute/path/Liu_instance.txt --wind W04E --output /absolute/path/anchor_audit.json
```

CLI 无论资源通过与否均写出可读收据；退出 0 表示完整同风身份已记录，2 表示仅工程，1 表示资源审计失败。输入文件本身损坏则直接报错，不产生可误认通过的收据。Python 可直接调用 `audit_anchor_file(anchor_path,map_path,"fixed_e4")`；strict pilot 应要求 `physical_feasible` 与 `full_same_wind_author` 同时为 true，并绑定 `anchor_file_sha256`、`audit_sha256` 及原始运行证据。

## 7. 同天气、禁入规则有无的配对工程接口

`rlcore/paired_weather.py` 新增 `make_paired_weather(seed,bbox,scale=1)`，从一个 `WeatherDay(mode="storm")` 抽样构造 `(clear,cells)` 两个窄接口。仅天气包注册 `weather_paired_clear`、`weather_paired_cells`，均标记 `engineering_only=True`；紧急包不增加跨包依赖。

两臂始终调用同一底层对象的 `truth_wind` 和 `forecast_wind`；均值、湍流、阵风、单体出流风、预报误差、发布时间和整个时域完全保留。`pair_world_sha256` 标识干预前同一个完整天气对象。独立按同 seed 构造两臂也重建相同对象；环境原有完整 input hash 则包含干预差别，应不同，不能为了“配对”抹去规则变更。

cells 臂保留原禁区检测和临近预报；clear 臂公开 `ncell=0`、`nowcast=[]`、`in_cell=False`、`truth_segment_hits=False`，不转发 `cells_meta/c_a/c_b/c_ang/c_cx/c_cy/_cell_list/storm` 等形态字段。没有通用 `__getattr__`。这限制的是受支持的策略观测接口；Python 任意对象内省不构成对抗性安全隔离。潜在未来重采样使用同一个 latent-only 抽样规则，并继续保留 RI 未获资格的字段。

在相同风环境中，只移除禁入规则及其对应显式禁区观测，可以研究该规则制度下的调度/可行性差异。由于源风场包含单体出流，不能称作“有雷暴天气 vs 无雷暴天气”，不能归因于移除实际风暴，也不能据两臂差异分离屏蔽的纯效果与禁区信息的纯价值。动态环境的预测误差与失败风险仍然保留，工程通过不开放科学训练。

手写工程单体是会移动的一个椭圆；没有读取科研地图。`engineering_check()` 比对 24 次真值风与 22 次预报查询，验证细区连续穿越 cells 命中/clear 不命中，确认两臂都保留非零单体出流、clear 不转发几何、同 seed 可重建和潜在未来重采样一致。`tests/test_review_pair.py` 另直接检查 pickle 往返及真实 `make_env` 注册，后者使用手写空站 fixture 并替换地图读取。连同先前物理与锚测试共 55 项通过。

实际工程命令（在仓库根目录运行）及其严格 JSON 收据：

```sh
python3 -m rlv3_weather.rlcore.paired_weather --engineering-check --output rlv3_weather/physics_audit_evidence/PAIRED_WEATHER_ENGINEERING.json
python3 -m pytest -q rlv3_weather/tests/test_review_pair.py tests/test_review_weather.py tests/test_review_anchor.py
```
