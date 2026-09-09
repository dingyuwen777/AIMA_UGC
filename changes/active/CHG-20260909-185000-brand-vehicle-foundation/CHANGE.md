---
schema: coding-change/v1
id: CHG-20260909-185000-brand-vehicle-foundation
title: 搜索与品牌车型过滤 Stage 1 数据模型基础
level: L3
status: ready_for_review
owner: chatgpt
branch: migration/stage1-brand-vehicle-foundation
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - database
affected_paths:
  - backend/src/aima_ugc/modules/vehicles/tables.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions/20260909_0044_brand_vehicle_filter_foundation.py
  - tests/integration/database/test_brand_vehicle_foundation_schema.py
  - scripts/quality/check_table_ownership.py
  - docs/blueprint/03_数据库与文件存储.md
contracts: []
data_changes:
  - Expand-only PostgreSQL Schema；新增品牌目录、可空车型品牌归属与品牌证据，不回填历史数据
---

# 背景与目标

上游为 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` 的 Stage 1。当前系统已有
`vehicle_models`、车型别名、内容车型证据与车型人工锁，但没有独立品牌实体，也无法在同一内容上
以可审计证据表达品牌归属。Stage 1 只建立后续搜索、品牌/车型过滤所需的 PostgreSQL 数据模型
基础，不改变现有 Excel/TikHub 导入、Collection Plan、API、前端或在线业务行为。

本次采用 Expand-only Migration：复用 `vehicle_catalog_versions` 作为品牌与车型共享目录版本；
新增品牌目录/别名；给车型增加可空 `brand_id`；新增内容品牌证据和人工锁。历史车型不猜测品牌、
不回填 `brand_id`，旧 `keyword_pack_vehicle_models`、`collection_plan_vehicle_models` 和
`global_relevance_config` 保持不变。

# 方案与兼容边界

品牌稳定身份使用 UUID `id` 与唯一 `code`；`display_name` 只用于展示。品牌别名只在同一品牌内
唯一，允许不同品牌共享同一 `normalized_text`，避免把歧义文本强制映射为单一品牌。车型
`brand_id` 保持 nullable，并提供 `brand_id + status` 索引，支持后续“品牌 → active 车型”读取。

`content_brand_evidence` 与现有车型证据保持追加式设计。`vehicle_match` 证据必须携带
`derived_vehicle_model_id`，其余来源不得携带该字段。PostgreSQL 普通 UniqueConstraint 对 NULL
不去重，因此采用两条 partial unique index：一条约束直接品牌证据，一条约束车型推导证据；
这样既阻止相同证据重复写入，又允许同一品牌由不同车型分别产生可审计证据。有效证据分别按
Content 与 Brand 提供 partial index。

`content_brand_evidence` / `content_brand_review_locks` 与既有 `content_vehicle_*` 同属 Vehicles
Domain 的内容匹配证据边界。由于表名使用稳定 `content_*` 前缀，Table Owner 门禁需要像既有
`content_vehicle_*` 一样在 `_VEHICLE_TABLES` 中显式登记，防止被通用 Content 前缀规则误判。
该登记只声明唯一写 Owner，不放宽未知表或其他 `content_*` 的默认 Content Owner 规则。

不新增第二套 catalog version 表，不向 `contents` 写品牌/车型标量，不新增 Provider 调用，不做
历史品牌猜测或海量回填。Migration 可逆：downgrade 只删除本次新增结构并移除 `brand_id`，
不会改写旧 Migration。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 复用 `vehicle_catalog_versions`，新增 `vehicle_brands` 稳定身份、角色、生命周期和版本字段 | #416 / AC1 | satisfied | `vehicles/tables.py` 与 0044 Migration 共用现有 catalog FK；未新增品牌版本表 |
| R2 | 新增品牌别名，别名仅在品牌内部唯一，不做全局唯一 | #416 / AC2 | satisfied | `vehicle_brand_aliases` 使用 `(brand_id, normalized_text)` 唯一约束；真实 PostgreSQL 语义由 R7 验证 |
| R3 | `vehicle_models.brand_id` 必须可空、FK 品牌且不回填，并具备品牌到 active 车型读取索引 | #416 / AC3 | satisfied | 0044 只 ADD nullable FK/Index，无 UPDATE/backfill；SQLAlchemy metadata 同步 |
| R4 | 建立品牌追加式证据，来源/车型推导/置信度/锁定/active/查询索引与 NULL 幂等语义完整 | #416 / AC4 | satisfied | `content_brand_evidence` 字段、Check、两条 partial unique index 与 Content/Brand active index 已实现；真实 PostgreSQL 语义由 R7 验证 |
| R5 | 新增按 content version 生效的品牌人工锁 | #416 / AC5 | satisfied | `content_brand_review_locks` 复用车型锁的复合主键与 actor/time 结构 |
| R6 | 保持既有 legacy 关系及 Excel/TikHub/Collection Plan/API/前端业务语义不变，不做历史猜测 | #416 / AC6 | satisfied | Implementation diff 仅限 vehicles Schema 注册、0044 Migration、数据库集成测试、Table Owner 清单、Blueprint 同步与本 Change |
| R7 | 真实 PostgreSQL upgrade/downgrade、metadata drift、FK/Check/Unique/Index/Owner 与既有回归必须通过 | #416 / AC7 | explicitly_deferred | 当前宿主无本地 PostgreSQL runner；由当前 PR HEAD 的正式 PostgreSQL 18.4 CI 运行，不豁免 |
| R8 | L3 Completion Audit、独立两阶段 Review 与当前 PR HEAD CI 必须完成 | #416 / AC8 | explicitly_deferred | Implementation 完成后执行独立 Review；正式 CI 由 push/PR 触发，合并前必须成功 |
| R9 | 合并 main 后完成 fresh main CI、repository-native Change 归档，并把 Stage 1 标 completed / Stage 2 保持 planned | #416 / AC9 | explicitly_deferred | 必须在 Implementation PR 合并后执行；不得在本 PR 提前修改 Roadmap 完成状态或手工归档 Change |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | 正式 backend Unit/Contract/API 回归证明现有 Python 运行行为未被 Schema 注册破坏 |
| Contract / Generated Client | not_applicable | 本次不改 HTTP/OpenAPI/导出文件 Contract，也不改生成 Client |
| Backend/API/PostgreSQL Integration | required | PostgreSQL 18.4 空库 upgrade/current/check、历史 downgrade→head compatibility、数据库 suite 与新增品牌 Schema/NULL 唯一语义测试 |
| Browser Mock Acceptance | not_applicable | 无前端/UI 行为变化 |
| Real Full-stack Golden Path | not_applicable | Stage 1 不改变跨组件业务接线；若仓库 CI 因 migration fail-closed 额外运行，只作为附加回归证据 |
| External Provider Probe | not_applicable | 不改 TikHub/LLM 等外部 Provider 协议或当前事实 |
| Build / Package / Runtime | required | Python format/lint/mypy、正式 Wheel build/install/import 以及 Migration head 可装载 |
| Docs / Governance | required | Requirement Source、Change readiness、架构/Table Owner、Secret/docs gates、Completion Audit、Review 与 CI Gate |

# 实施计划

1. 在 `vehicles` Owner 内建立品牌目录/别名，并以 nullable FK 扩展车型；Migration 只做 Expand。
2. 建立品牌证据与版本锁，用 PostgreSQL partial unique index 固化直接/车型推导两类幂等语义。
3. 增加真实 PostgreSQL Schema/约束测试，并复用现有 migration compatibility、metadata drift、
   ownership 与 backend 回归门禁。
4. 完成 A1/A2 + 代码质量 Review 和 PR HEAD CI 后合并；再验证 main fresh CI、原生 Change
   归档，最后单独同步 Roadmap 阶段状态，不进入 Stage 2 实现。

# Completion Audit

- [x] upstream_re_read：已重读 Roadmap Stage 1/Exit/阶段状态规则、Issue #416 AC1-AC9、项目数据库/Owner/Migration 规则与当前 0043 head。
- [x] change_coverage：品牌目录、别名、nullable 车型品牌 FK、品牌证据、品牌锁、真实 PostgreSQL 语义、Table Owner 稳定表族、Blueprint 当前事实同步与非目标均已映射到 R1-R9 / AC1-AC9。
- [x] reverse_audit：按 writer/schema/reader/历史兼容路径反查；Brand Evidence 与既有 Vehicle Evidence 平行并继续由 Vehicles Domain 唯一写；Stage 1 没有新 API/前端消费者，因此只要求真实 PostgreSQL/metadata/owner 与现有运行回归。
- [x] unresolved_cleared：当前设计无未决 Schema 决策；R7-R9 是受正式 PR/合并时序约束的生命周期后置门禁，未豁免且阻止提前宣称 Stage 完成。

# 当前证据

- `main` 基线为 `5e3bd0e2f0ff21e5cfca2e3271f7da2f842c3ab3`，开工时 Alembic head 为 `20260908_0043`，未发现开放 PR 或 Active Change。
- 已核对 `vehicles/tables.py`、`database_schema.py`、0031/0032/0043 Migration、PostgreSQL integration 测试与 CI 分类器；品牌目录/车型及其内容匹配证据继续归 `vehicles` Owner。
- 新增 PostgreSQL 测试直接覆盖：品牌别名“品牌内唯一/跨品牌可重复”、车型 `brand_id` nullable、两类 brand evidence partial unique index 的 NULL 幂等语义、`vehicle_match` 派生车型一致性、FK/Check/Index 注册；Table Owner 由正式 ownership gate 直接验证。
- 当前宿主没有本地仓库 runner，真实 PostgreSQL 18.4、Alembic downgrade→head、全部既有回归、Wheel 与正式 CI 证据由当前 PR HEAD 执行；这些结果未取得前不得合并或宣称 Stage 1 完成。
- PR #415 首次 CI 在 Change readiness 阶段发现 Source 包含章节说明而被误作仓库路径；第二次 CI 明确要求稳定 Acceptance 绑定。已建立 Issue #416，以 Roadmap Stage 1 原要求定义 AC1-AC9，并将本 Change 逐条绑定到真实 `#416 / ACn`，未改变生产 Schema/测试或 Roadmap 阶段状态。
- 后续 full CI 的 `check_docs_facts.py` 发现 Blueprint 缺少四张新增 Schema 表；已按 Docs targeted 规则同步 `docs/blueprint/03_数据库与文件存储.md` 的 Owner/Vehicle Catalog 当前事实，不复制完整 DDL。
- `53473fe5` full CI 已取得：Requirement/Change/Secret/docs/Contract/format/lint/mypy 全部成功，Unit 914/Contract 104/API 55 全通过；Architecture 骨架检查通过。唯一失败为 ownership checker 尚未把新增 `content_brand_*` 登记为与 `content_vehicle_*` 同域的 Vehicles 例外，导致 PostgreSQL job 被前置门禁阻断；已在当前分支补充 `_VEHICLE_TABLES` 精确两项登记，不改变其他表族默认 Owner 规则。
