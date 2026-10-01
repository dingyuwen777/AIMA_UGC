---
schema: coding-change/v1
id: CHG-20261001-163121-brand-first-resolver
title: 数据库目录驱动的品牌先行多品牌多车型识别
level: L3
status: ready_for_review
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
  - .github/workflows/ci.yml
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
| E3 | Replay 在未命中时跳过；已命中的既有内容在主批次已有自动证据收敛，但解析未传入人工品牌范围 | bootstrap/canonical_replay_worker.py 的 _ingest_batch | 补齐负向路径与人工品牌范围，不重复已有收敛机制 |
| E4 | 既有 Evidence 多对多、声音广场集合投影及持久 Job 可复用 | vehicles/content persistence 与 Replay | 不建平行机制或物理删除事实 |

以上 E1–E4 描述开工基线。当前实现已沿正式 Owner 补齐负向贡献账本、实际 Current 分类、人工锁继承、较新来源保护与断链撤回；真实 PostgreSQL 场景见本 Change 的 LOCAL_VALIDATION.md。运行库配置不直接用于破坏性验证，所有测试在本任务隔离资源执行。

# 目标、成功标准与非目标

成功标准来自 [Issue #685](https://github.com/dingyuwen777/AIMA_UGC/issues/685) 的 AC1–AC20。用户最新明确“品牌与车型在数据库配置好了，从配置中选择”，沿用现有 Repository 的冻结目录，不维护硬编码业务清单。非目标为模型识别、新队列、内容身份重建、管理员阈值配置、物理删除 Raw/Canonical、依赖升级、生产部署及运行库迁移。

# 约束与意图决策

算法语义由冻结目录 snapshot 持有：历史缺字段默认为 field_priority_v1，生产新建目录显式 brand_scoped_vehicle_v2；统一过滤和重分类快照均复用同一字段，避免两个版本 Owner。v2 的 automatic_evidence_vehicle_ids 同时冻结 selected 清理身份，包含停用与合并旧源，不在执行时重新读取车型归属。API/Job 名称及 Payload Version 保持，新增 JSON 字段进入持久摘要与幂等身份。现有 JSONB 可以保存该内部快照，不需要实体 Schema Migration；生成公共 Contract 检查已通过。

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
| R1 | 全字段完整品牌扫描 | #685 / AC1 | satisfied | 1753 后端回归：全字段/跨字段/transcript；Resolver 及 codec 专项；LOCAL_VALIDATION/EVIDENCE.json |
| R2 | 多品牌全部有效证据 | #685 / AC2 | satisfied | 完整品牌证据单元；真实 PG 多品牌投影查询场景；LOCAL_VALIDATION/EVIDENCE.json |
| R3 | 仅确认品牌下车型 | #685 / AC3 | satisfied | 确认品牌内索引及无品牌负例；普通/历史/Collection 完整 PG；LOCAL_VALIDATION/EVIDENCE.json |
| R4 | 无品牌不自动车型反推 | #685 / AC4 | satisfied | 纯车型无品牌负例；真实 frozen legacy→v2 重筛对照；LOCAL_VALIDATION/EVIDENCE.json |
| R5 | 单字车型局部安全关联 | #685 / AC5 | satisfied | 单字车型正反例、12 原始字符间隔/空白/换行/ASCII 边界；LOCAL_VALIDATION/EVIDENCE.json |
| R6 | 共享别名单次命中消歧 | #685 / AC6 | satisfied | 同一次共享别名命中唯一归属/歧义保守场景；LOCAL_VALIDATION/EVIDENCE.json |
| R7 | 同内容多品牌多车型 | #685 / AC7 | satisfied | 真实 PG 数据库品牌/车型→完整投影→各实体查询；LOCAL_VALIDATION/EVIDENCE.json |
| R8 | 去重与稳定证据 | #685 / AC8 | satisfied | 实体去重与字段/长别名/位置/身份稳定代表证据单元；LOCAL_VALIDATION/EVIDENCE.json |
| R9 | 人工锁优先 | #685 / AC9 | satisfied | 人工空锁/双锁；真实新版本审核继承、重筛及重分类 PG；LOCAL_VALIDATION/EVIDENCE.json |
| R10 | 投影完整多对多集合 | #685 / AC10 | satisfied | test_database_configured_multi_brand_models_project_and_filter_as_complete_sets；LOCAL_VALIDATION/EVIDENCE.json |
| R11 | 品牌 OR 查询 | #685 / AC11 | satisfied | 真实生产 ContentListQuery brand_ids OR 查询各品牌返回同一内容；LOCAL_VALIDATION/EVIDENCE.json |
| R12 | 车型 OR 查询 | #685 / AC12 | satisfied | 真实生产 ContentListQuery vehicle_model_ids OR 查询各车型返回同一内容；LOCAL_VALIDATION/EVIDENCE.json |
| R13 | 自有及竞品归类 mixed | #685 / AC13 | satisfied | 真实投影 competition_scope=mixed，纯竞品查询不误包含；LOCAL_VALIDATION/EVIDENCE.json |
| R14 | 含竞品筛选保持仅竞品语义 | #685 / AC14 | satisfied | 45 浏览器 Mock：含竞品组合和仅竞品保持；真实 PG 查询组合；LOCAL_VALIDATION/EVIDENCE.json |
| R15 | 现有管理员全历史重筛 | #685 / AC15 | satisfied | 完整 ingestion 111 项，管理员创建父请求→正式 Planner/Worker；未调用运行库；LOCAL_VALIDATION/EVIDENCE.json |
| R16 | 旧自动证据负向收敛 | #685 / AC16 | satisfied | 负向、四类旧 import 文本字段/NULL事实、撤回、较新写入与断链 PG；LOCAL_VALIDATION/EVIDENCE.json |
| R17 | 历史未入库 Canonical 幂等入库 | #685 / AC17 | satisfied | 完整 Canonical Replay 正向/幂等/历史未入库回归；LOCAL_VALIDATION/EVIDENCE.json |
| R18 | v1 旧任务/v2 新任务冻结 | #685 / AC18 | satisfied | 旧/新 codec、真实旧任务 retry/Worker、新 v2收敛；selected 冻结2个PG场景；LOCAL_VALIDATION/EVIDENCE.json |
| R19 | 版本纳入任务摘要与幂等身份 | #685 / AC19 | satisfied | 旧字节/选择摘要单元及实际幂等任务；新冻结车型清理身份进入JSON；LOCAL_VALIDATION/EVIDENCE.json |
| R20 | 批次预编译与品牌内索引复用 | #685 / AC20 | satisfied | 100条编译复用/语义变化重编译单元；Collection 实例复用；复杂度范围见验证记录；LOCAL_VALIDATION/EVIDENCE.json |

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

- [x] upstream_re_read：重新读取 Issue #685、引用会话已确认方案及用户数据库配置决定。
- [x] change_coverage：按 AC1–AC20 重建当前实现单元，AC21 保留交付阶段责任。
- [x] reverse_audit：PG 管理员/Worker/Evidence/projection/查询与16项真实浏览器全栈均已覆盖；其中目录配置→品牌明确命中→车型→详情实际alias_match→查询/导出形成闭环。
- [x] unresolved_cleared：当前实现要求的 not_satisfied 清零，无伪造延期或 N/A。

# 完成证据与状态

新实例已通过当前canonical实例Contract校验。原基线15dd366、实现36f0f7f5的缺陷Red/Green和完整分套证据保持；本批已同步报告原生归档后的当前main `dd821ca86a64951d4f7add4d39b6129368aac18d`，组合实现检查点 `143f5a0bca6b5be72d4f574367fe358c69db0c7c`。18个品牌生产Git blob与原证据一致。当前组合1782项后端/16既有skip/12subtests、96项CI精确PG目标、24项品牌专项、报告PG9项/1 opt-in skip、16项真实全栈、前端274项与构建以及静态/Contract/文档检查通过。

独立组合Repair复核RV-BRAND-01–09 closed，确认报告版本化Evidence消费者边界。首个冻结head4b4e6b84的PG目标96项通过后，CI空库迁移probe因顺序问题失败，RV-BRAND-10为blocking并退Draft修复。原顺序真实数据库Red和新增顺序回归Red均已复现；仅移动完整迁移probe到数据测试之前，取得14个checkpoint/base回0078及紧接96targets的真实Green、相关79项回归Green。未修改生产Migration或降低断言，18个品牌生产文件保持。Final必须绑定新head/current-base及完整required CI，通过之前不允许merge。详细命令、环境、原始失败、生产源码与XML摘要见LOCAL_VALIDATION.md和EVIDENCE.json。仅当前开发目录与自有测试资源可写，运行目录和既有容器未操作。

## 交付阶段与 Issue AC21

独立Repair已复核迁移顺序源码、Red/Green及真实新序列96项XML，RV-BRAND-01–10全部closed，没有新的blocking；当前进入ready_for_review，仍等待新冻结head的Final与完整CI。

#685 / AC21保持未勾选：第一批报告PR #688已正常squash合并，原生Archive、main-fresh和Issue #684 Closure已完成；旧PR #686关闭为superseded，其分支/Change身份及失败记录保留。第二批PR #687按当前组合Ready门禁继续交付。Delivery Agent持有最终Review/CI、expected-head merge、main-fresh、Closure与cleanup，原生automation持有同ID Change归档。当前第二批delivery、main_fresh、change_archive、requirement_closure、end_to_end仍incomplete，不伪造已执行状态。当前Change的Ready准备不等价于整个Issue完成。
