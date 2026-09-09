---
schema: coding-change/v1
id: CHG-20260909-204600-stage2-brand-vehicle-resolver
title: 搜索与品牌车型过滤 Stage 2 管理面与统一解析器
level: L3
status: active
owner: chatgpt
branch: feature/stage2-brand-vehicle-resolver
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on: []
affected_areas:
  - vehicles
  - administration
  - contracts
  - database
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/vehicles/
  - backend/src/aima_ugc/adapters/persistence/postgres/vehicles.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/modules/administration/http.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/bootstrap/api.py
  - tests/
  - docs/blueprint/
contracts:
  - Administration HTTP / OpenAPI
data_changes:
  - 仅通过已有 Stage 1 表结构写 Brand/Vehicle 主数据与证据；不猜测或批量反推历史品牌
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 2：在 Stage 1 Schema 基础上提供 Brand/Vehicle 管理、统一 Catalog Snapshot 与纯确定性 BrandVehicleResolver，为后续 Stage 3 自动过滤提供可测试基础。本 Change 不接入 Excel/TikHub Runtime、不改变 Collection Plan/Keyword Pack 业务语义、不修改声音广场 UI。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Brand CRUD/Alias 管理 API 与共享 catalog version | #418 / AC1 | in_progress | Brand domain/repository/contract/API + PG tests |
| R2 | Vehicle 显式 brand_id 管理与 active 品牌完整性；不从旧词包反推 | #418 / AC2 | in_progress | Vehicle contract/repository + integrity query/test |
| R3 | 统一 CatalogSnapshot，兼容既有 Vehicle snapshot | #418 / AC3 | in_progress | vehicles models/repository tests |
| R4 | 确定性 resolver：车型优先、字段优先级、冲突可观察 | #418 / AC4 | in_progress | BrandVehicleResolver unit tests |
| R5 | Brand evidence/review lock 与人工锁保护，Vehicle 锁语义不回退 | #418 / AC5 | in_progress | repository PG tests |
| R6 | 真实 PostgreSQL 覆盖 CRUD/Alias/完整性/锁 | #418 / AC6 | explicitly_deferred | PR HEAD PostgreSQL CI |
| R7 | Collection/Keyword Pack 与 Stage 3+ 行为不变 | #418 / AC7 | in_progress | 既有回归 + diff audit |
| R8 | OpenAPI/client/docs 与 resolver/contract tests 同步 | #418 / AC8 | in_progress | generated-contract gates + targeted docs |
| R9 | Completion Audit、独立 Review、PR/main CI、merge/archive/Roadmap 收口 | #418 / AC9 | explicitly_deferred | 合并生命周期后置门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | BrandVehicleResolver、字段优先级、冲突 |
| Contract/API | required | Brand/Vehicle 管理 OpenAPI 与 API tests |
| PostgreSQL Integration | required | CRUD、Alias、active Vehicle 品牌完整性、Brand evidence lock |
| Generated Client | required | OpenAPI/client 生成一致性 |
| Collection regression | required | 既有 Vehicle snapshot、Keyword Pack/Collection 语义不变 |
| Docs/Governance | required | Change、Issue AC、facts、Review、CI |

# 实施计划

1. 扩展 vehicles 领域对象/Repository：Brand、统一 Snapshot、active 品牌完整性与 Brand evidence/lock。
2. 新增纯确定性 BrandVehicleResolver，同时保留现有 Vehicle snapshot 给 Collection 调用。
3. 扩展 Administration Contract/Service/API；Vehicle `brand_id` 仅由显式管理写入，不做历史猜测。
4. 补 unit/Contract/API/真实 PostgreSQL 测试并同步 OpenAPI/client/事实文档。
5. Completion Audit + 独立 Review + PR HEAD CI 后 expected-head 合并；验证 main fresh CI 与原生 Change 归档；单独更新 Roadmap Stage 2 状态后停止。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 当前证据

- 开工基线 `main=ebecba7efaaab73ca0ecca30ce65b82bbc36bb4e`；Stage 1 completed，Stage 2 planned；开工时无 open PR、无 active Change。
- Stage 1 已提供 `vehicle_brands` / `vehicle_brand_aliases` / nullable `vehicle_models.brand_id` / `content_brand_evidence` / `content_brand_review_locks`，但当前管理 Contract/Repository 尚未消费这些表。
- 现有 Vehicle Repository 已具备人工 review lock 阻止自动证据写入、既有 Collection Vehicle snapshot 与车型管理；Stage 2 在其上增量扩展，不另建重复车型 API。
