---
schema: coding-change/v1
id: CHG-20261001-163121-brand-first-resolver
title: 数据库目录驱动的品牌先行多品牌多车型识别
level: L3
status: proposed
owner: Codex
branch: feature/brand-first-resolver
created: 2026-10-01
updated: 2026-10-01
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - ingestion
  - content
affected_paths:
  - backend/src/aima_ugc/modules/vehicles
  - backend/src/aima_ugc/modules/ingestion
  - backend/src/aima_ugc/adapters/persistence/postgres
  - backend/src/aima_ugc/bootstrap
  - frontend/src/features/voice-plaza
  - tests
  - docs
contracts:
  - frozen BrandVehicleCatalogSnapshot JSON
data_changes:
  - automatic evidence convergence through existing owners
---

# 变更摘要

使用用户在数据库配置的品牌、车型及别名，完整扫描所有文本字段中的品牌，再匹配已确认品牌下面的车型。单字车型要求局部品牌关联，共享别名歧义不猜测。新任务冻结新算法，旧快照继续旧算法；历史重筛收敛无效自动证据并保留人工事实。

# 背景、现状与问题

当前 Resolver 的品牌和车型扫描在首个命中字段结束；无品牌锚点时仍扫描全局车型，可遗漏跨字段品牌并误把单字母当车型。CanonicalReplay、统一入库和旧内容重分类共用该 Resolver，必须切断同一机制且冻结任务行为，不能只修页面查询或只补新入库。

# 事实与证据

| 编号 | 已确认事实 | 来源 | 约束 |
| --- | --- | --- | --- |
| E1 | 当前数据库目录 snapshot 包含有效品牌、对应车型及两类别名 | adapters/persistence/postgres/brand_vehicle.py 的 snapshot | 数据库配置是唯一识别目录 |
| E2 | 旧 Resolver 首字段优先且允许车型反推品牌 | modules/vehicles/brand_vehicle.py | 新语义必须版本化，旧任务不能漂移 |
| E3 | Replay 在未命中时跳过，已存在内容处理追加而非替换自动证据 | bootstrap/canonical_replay_worker.py | 需要负向收敛和人工锁审计 |
| E4 | 既有 Evidence 多对多、声音广场集合投影及持久 Job 可复用 | vehicles/content persistence 与 Replay | 不建平行机制或物理删除事实 |

推断与待确认：具体负向贡献账本和可见性边界需在生产修改前沿现有 Owner 进一步核对；不能把静态发现写成已执行测试。运行库配置不直接用于破坏性验证，所有测试在本任务隔离资源执行。

# 目标、成功标准与非目标

成功标准来自 [Issue #685](https://github.com/dingyuwen777/AIMA_UGC/issues/685) 的 AC1–AC20。用户最新明确“品牌与车型在数据库配置好了，从配置中选择”，沿用现有 Repository 的冻结目录，不维护硬编码业务清单。非目标为模型识别、新队列、内容身份重建、管理员阈值配置、物理删除 Raw/Canonical、依赖升级、生产部署及运行库迁移。

# 约束与意图决策

算法语义由冻结目录 snapshot 持有：历史缺字段默认为 field_priority_v1，生产新建目录显式 brand_scoped_vehicle_v2；统一过滤和重分类快照均复用同一字段，避免两个版本 Owner。API/Job 名称及 Payload Version 保持，新增 JSON 字段进入持久摘要与幂等身份。若机器事实显示需数据库 Migration 或破坏性公共 Contract，先恢复边界再决定，不猜测。

短车型固定局部最大间隔 12，要求同字段、同片段、ASCII token 边界及无其他确认品牌介入；多品牌共享别名一次命中只归属唯一品牌。人工品牌限定自动车型范围，人工车型保持并可关联其品牌；两者都锁定时尊重既有人工事实。

# 修改方案与决策依据

1. 新语义场景及旧/新快照测试 → 复现全字段遗漏、无品牌反推、短字母及歧义 → 验证 Red，再实现 Green。
2. AC 提供命中位置、预编译品牌内车型索引；Resolver 保留 v1 分支，新增 v2 品牌先行完整扫描 → 单元验证结果、证据代表与索引复用。
3. 数据库 snapshot 显式冻结 v2，JSON 恢复缺字段为 v1，验证摘要和旧任务行为 → codec/Contract 回归。
4. 统一 Replay 与重分类收敛自动证据、保护人工与现有贡献账本 → 真实隔离 PostgreSQL 验证负向和正向历史路径。
5. 声音广场全量投影及 OR 筛选、mixed 与“含竞品”语义 → 真实查询与管理员重筛关键路径，按变化补前端。
6. 同步直接文档并独立重建完成定义 → Completion Audit、两阶段 Review、当前 head/base required CI。

## 备选方案与取舍

只取消首字段 return 无法解决纯字母误命中和历史证据残留；新增模糊/AI 推断会扩大错误与运行成本，且不是用户确认方案。保留无品牌车型反推与本轮精确率优先决定冲突；旧行为只服务已冻结 v1 任务。

# 需求追溯

本表是当前实现单元合并前的要求；AC21 的完整交付阶段在末尾单独持有，Issue 未关闭，不提前满足合并后动作。

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 全字段完整品牌扫描 | #685 / AC1 | not_satisfied | 待 Red/Green |
| R2 | 多品牌全部有效证据 | #685 / AC2 | not_satisfied | 待验证 |
| R3 | 仅确认品牌下车型 | #685 / AC3 | not_satisfied | 待验证 |
| R4 | 无品牌不自动车型反推 | #685 / AC4 | not_satisfied | 待验证 |
| R5 | 单字车型局部安全关联 | #685 / AC5 | not_satisfied | 待验证 |
| R6 | 共享别名单次命中消歧 | #685 / AC6 | not_satisfied | 待验证 |
| R7 | 同内容多品牌多车型 | #685 / AC7 | not_satisfied | 待验证 |
| R8 | 去重与稳定证据 | #685 / AC8 | not_satisfied | 待验证 |
| R9 | 人工锁优先 | #685 / AC9 | not_satisfied | 待验证 |
| R10 | 投影完整多对多集合 | #685 / AC10 | not_satisfied | 待 PG 验证 |
| R11 | 品牌 OR 查询 | #685 / AC11 | not_satisfied | 待 PG 验证 |
| R12 | 车型 OR 查询 | #685 / AC12 | not_satisfied | 待 PG 验证 |
| R13 | 自有及竞品归类 mixed | #685 / AC13 | not_satisfied | 待 PG 验证 |
| R14 | 含竞品筛选保持仅竞品语义 | #685 / AC14 | not_satisfied | 待消费者调查与验证 |
| R15 | 现有管理员全历史重筛 | #685 / AC15 | not_satisfied | 待工作流验证 |
| R16 | 旧自动证据负向收敛 | #685 / AC16 | not_satisfied | 待 PG 验证 |
| R17 | 历史未入库 Canonical 幂等入库 | #685 / AC17 | not_satisfied | 待 PG 验证 |
| R18 | v1 旧任务/v2 新任务冻结 | #685 / AC18 | not_satisfied | 待 codec/PG 验证 |
| R19 | 版本纳入任务摘要与幂等身份 | #685 / AC19 | not_satisfied | 待身份验证 |
| R20 | 批次预编译与品牌内索引复用 | #685 / AC20 | not_satisfied | 待机制验证 |

# 计划改动

| 模块 / 资产 | 改动 | 对应要求 |
| --- | --- | --- |
| modules/vehicles/brand_vehicle.py | 算法语义、位置命中、两阶段解析及稳定证据 | R1–R9、R18、R20 |
| postgres/brand_vehicle.py 与快照 codec | 新目录冻结语义和兼容编码/摘要 | R18–R19 |
| canonical_replay_worker、重分类 Worker 与 Evidence Owner | 正负向收敛和人工保护 | R9、R15–R17 |
| 声音广场消费者与现有测试 | 集合查询、角色筛选及真实用户路径 | R10–R14 |
| 直接模块 README、相关 Appendix/Blueprint | 数据库配置目录、两阶段规则和任务冻结排障 | 全部 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| 行为 / 单元 / 组件 | required | 多字段/品牌/车型、局部消歧、锁、预编译 |
| 接口 / 契约 | required | snapshot JSON 恢复及摘要、公共消费者兼容 |
| 集成 / 持久化 / 运行依赖 | required | 隔离 PG 中 Evidence/贡献账本/projection/查询 |
| 用户 / 工作流验收 | required | 管理员重筛→Job→声音广场结果 |
| 跨组件关键路径 | required | 生产 Repository/HTTP/Worker/查询实际装配 |
| 外部依赖 / 供应方探测 | not_applicable | 不改变 Provider 操作，复用持久 Canonical，不调用真实模型/TikHub |
| 构建 / 打包 / 运行 | required | Python 静态检查及受影响前端构建 |
| 文档 / 治理 / 其他 | required | 当前事实文档、Secret/Owner/Change、PR CI |

# 风险、兼容性、迁移与回滚

无品牌纯车型不再自动命中是已批准精确率取舍。只追加冻结 JSON 语义，旧缺字段恢复 v1，保留原解析路径；不改现有实体 Schema 或删除历史。历史重筛只通过现有 Owner/贡献账本更新自动证据与可见性；人工证据保留。回滚新代码不能把已有 v2 快照误当 v1，需停用新增 v2 任务并保留版本识别边界；本轮不部署或执行运行库重筛。

# 文档、依赖、部署与发布影响

定向同步车辆目录、统一入库/重筛与声音广场事实的既有 Owner；不增加平行说明书。依赖和运行启动方式保持。无新增 Secret，不记录内容正文或敏感值；必要日志只记录语义、数量、任务身份与冲突摘要。生产部署/迁移不在授权内，远程主分支合并由交付阶段负责。

# 完成审计

- [ ] upstream_re_read：重新读取 Issue #685、引用会话已确认方案及用户数据库配置决定。
- [ ] change_coverage：按 AC1–AC20 重建当前实现单元，AC21 保留交付阶段责任。
- [ ] reverse_audit：管理员重筛入口、Worker、Evidence/projection 与查询消费者均实际覆盖。
- [ ] unresolved_cleared：当前实现要求的 not_satisfied 清零，无伪造延期或 N/A。

# 完成证据与状态

新实例已按当前秒级 ID 创建，并通过当前 canonical 新实例 Contract 校验，完成代码前不声明 Ready。基线为 15dd366db6e1632535fadc615513636a4b22c639。执行 `.venv/Scripts/python.exe -m pytest tests/unit/test_brand_first_resolver.py -q -p no:cacheprovider --junitxml=.runtime/brand-resolver-red.xml`，取得 10 failed/8 passed：实际复现跨字段品牌遗漏、无品牌车型反推、跨字段/跨片段/远距离单字车型误命中、共享别名遗漏及人工品牌范围失效。当前测试先使用原目录对象复现旧机制；新语义字段实现后，将 fixture 显式选择 v2，保持验收断言，既有 v1 回归保留。其他验证与 Review 待执行，正式 PR 为早期追溯入口。仅本开发目录与自有测试资源可写；运行目录和既有容器未操作。

## 交付阶段与 Issue AC21

#685 / AC21 保持未勾选：两批本地验证完成后，依次合并报告 PR #686、品牌识别 PR；第二批针对包含报告的最新 main 重新验证和审查。Delivery Agent 持有 merge/main-fresh/Closure，原生 automation 持有同 ID Change 归档。当前 delivery、main_fresh、change_archive、requirement_closure、end_to_end 均 incomplete，不伪造已执行状态。当前 Change 的 Ready 只证明实现单元，不等价于整个 Issue 完成。
