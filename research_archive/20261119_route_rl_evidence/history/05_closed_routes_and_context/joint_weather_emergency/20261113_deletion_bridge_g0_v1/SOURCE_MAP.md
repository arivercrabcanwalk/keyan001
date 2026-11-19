# 来源—步骤对应与证据边界

三份直接主源的已读范围如下；未声明逐页完整审计。搜索未命中某个字段组合，不当作新颖性证据。

| 主源及固定版本 | 实际源行 | 支持的事实与对本项目的含义 |
|---|---|---|
| Ahmadi等，Resource Constrained Pathfinding with Enhanced Bidirectional A* Search，arXiv2412.13888v1，2024-12-18 | RCSP_TEXT.txt 34–56、57–91、112–139、190–231；RCSP_ALGORITHMS.txt 353起Alg5全文 | 多维非负可加资源；forward/backward vector join已存在；g(x)+g(y)≤bounds与父节点对恢复均已有。截断支配标签仍可能须保留给join。它不是只有单资源，也不是自动涵盖本项目删目标后的新飞行边。 |
| Lee/Lu，Replacement Paths via Row Minima of Concise Matrices，arXiv1310.8062v1，2013-10-30 | RP_TEXT.txt 16–49、69–104、306–427；Eq1–3 | 固定图边/点失效；prefix+bridge+suffix、区间列支持和2-concise结构已有。其标量图上结果与本项目多资源、物理删目标改边权问题不等同，不能照搬线性复杂度。§3全部线性算法证明未精审。 |
| Ren等，Enhanced Multi-Objective A* Using Balanced Binary Search Trees，arXiv2202.08992v3，v1=2022-02-18，v3=2022-05-28 | EMOA_TEXT.txt 193–367；定义2/3、Alg2/3、Table1 | K维逐坐标dominance查询及AVL加速已有；一般维度Alg2/3最坏仍线性扫描数量级，只有特定二维投影Check可log。不能把平衡树高度log当任意高维查询log。 |

RCSP_TEXT第254行给出作者Bitbucket链接`https://bitbucket.org/s-ahmadi/multiobj`；EMOA_TEXT第395行给出`https://github.com/wonderren/public_emoa`。本轮定位了链接，未固定这些库commit或读取执行作者实现；先前“尚未找到RCSP代码链接”的阅读记录已纠正，不能表述成作者没有代码。

CrossRef返回的2018 online/2019 volume RCBDA论文、Righini/Salani2006、2017动态half-way等只读metadata；没有使用其未取得原式。HAR/联邦学习等错误匹配排除，不作先例。AX_RANGE_JOIN的空条目不证明新颖性。

本项目已写的首边分组、五个物理资源阈值和删除区间映射在上述已读段落中未定位到同一实现，但资源join/支配索引均为标准步骤。即使映射正确，也还须证明组合有实际计算或学习增量；本轮全模板实现没有显示效率优势。符号单点插回证明还指出边界枚举已覆盖整个受限家族。

原始HTTP字节、版本时间与失败见literature/*_RECEIPT.json；12次请求=11×200+1×429，429 body为0字节、exit1原样保留。无作者代码或模型执行。
