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
  - backend/src/aima_ugc/modules/vehicles/models.py
  - backend/src/aima_ugc/modules/vehicles/resolver.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_routes.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - tests/unit/vehicles/test_brand_vehicle_resolver.py
  - tests/integration/database/test_brand_vehicle_stage2.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - docs/blueprint/03_数据库与文件存储.md
contracts:
  - Administration HTTP / OpenAPI
data_changes:
  - 仅通过已有 Stage 1 表结构写 Brand/Vehicle 主数据与证据；不猜测或批量反推历史品牌
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 2：在 Stage 1 Schema 基础上提供 Brand/Vehicle 管理、统一 Catalog Snapshot 与纯确定性 BrandVehicleResolver，为 Stage 3 自动过滤提供可测试基础。本 Change 不接入 Excel/TikHub Runtime、不改变 Collection Plan/Keyword Pack 业务语义、不修改声音广场 UI。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Brand CRUD/Alias 管理 API 与共享 catalog version | #418 / AC1 | satisfied | `brand_vehicle.py` + `brand_vehicle_http.py` + 扩展路由 |
| R2 | Vehicle 显式 brand_id 管理与 active 品牌完整性；不从旧词包反推 | #418 / AC2 | satisfied | 显式 assignment API + integrity endpoint；无自动 backfill |
| R3 | 统一 CatalogSnapshot，兼容既有 Vehicle snapshot | #418 / AC3 | satisfied | 新 `CatalogSnapshot` 与 `catalog_snapshot()`；旧 `VehicleCatalogSnapshot` 保留 |
| R4 | 确定性 resolver：车型优先、字段优先级、冲突可观察 | #418 / AC4 | satisfied | `BrandVehicleResolver` + unit tests |
| R5 | Brand evidence/review lock 与人工锁保护，Vehicle 锁语义不回退 | #418 / AC5 | satisfied | 自动 Brand/Vehicle replace 均先检查对应 review lock；PG test |
| R6 | 真实 PostgreSQL 覆盖 CRUD/Alias/完整性/锁 | #418 / AC6 | explicitly_deferred | 当前 PR HEAD PostgreSQL CI，不豁免 |
| R7 | Collection/Keyword Pack 与 Stage 3+ 行为不变 | #418 / AC7 | satisfied | 旧 Vehicle snapshot/Pack/Plan API 未改；既有回归作为验证 |
| R8 | OpenAPI/client/docs 与 resolver/contract tests 同步 | #418 / AC8 | in_progress | 由 generated-contract gate 与 targeted docs 收口 |
| R9 | Completion Audit、独立 Review、PR/main CI、merge/archive/Roadmap 收口 | #418 / AC9 | explicitly_deferred | 合并生命周期后置门禁，不豁免 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | BrandVehicleResolver、字段优先级、冲突 |
| Contract/API | required | Brand/Vehicle 管理 OpenAPI 与 API 回归 |
| PostgreSQL Integration | required | CRUD、Alias、active Vehicle 品牌完整性、Brand/Vehicle evidence lock |
| Generated Client | required | OpenAPI/client 生成一致性 |
| Collection regression | required | 既有 Vehicle snapshot、Keyword Pack/Collection 语义不变 |
| Docs/Governance | required | Change、Issue AC、facts、Review、CI |

# 实施计划

1. 建立 Brand 管理、显式车型 Brand 归属、统一 Snapshot 与证据写入。
2. 建立纯确定性 Resolver，并保留既有 Collection Vehicle Snapshot。
3. 通过现有 `entrypoints/api_main.py` 扩展路由安装机制暴露公共管理 API。
4. 补 unit/PG 回归，同步 OpenAPI/client/事实文档。
5. 独立 Review + PR HEAD CI 后 expected-head 合并；验证 main fresh CI/原生归档；单独收口 Roadmap 后停止。

# Completion Audit

- [x] upstream_re_read：已重读最新 main、Roadmap Stage 2/Exit、Stage 1 Schema、当前 Vehicle Repository/Administration/API assembly 与最新 Agent_Skills Source Mode 规则。
- [x] change_coverage：AC1-AC9 已映射到管理、归属、快照、Resolver、证据锁、PG、兼容、Contract/docs、交付生命周期。
- [x] reverse_audit：按写 Owner、公共 API、Collection 旧快照、证据锁和未来 Stage 3 reader 反查；没有新增第二套 catalog version 或从旧词包推断品牌。
- [x] unresolved_cleared：实现决策已收敛；R6/R9 仅受正式 CI/Review/合并时序约束，R8 等待生成 Contract 与文档门禁，不视为豁免。

# 当前证据

- 开工基线 `main=ebecba7efaaab73ca0ecca30ce65b82bbc36bb4e`；Stage 1 completed，Stage 2 planned；开工时无 open PR、无 active Change。
- Stage 1 表结构足以完成 Stage 2，因此本阶段无新 Migration；nullable `vehicle_models.brand_id` 继续承担显式修复窗口，不做历史猜测。
- Resolver 已固定 Vehicle-first、`title -> raw_text -> transcript_text` 和歧义不猜规则。
- 新 PG 回归覆盖 active Vehicle 缺 Brand 可观察→显式修复→完整性归零，以及 Brand/Vehicle 人工锁阻止自动替换。
- 当前 Draft PR #419 用于迭代；只有 R8 完成、独立 Review 与当前 HEAD 全量 CI 成功后才允许合并。
