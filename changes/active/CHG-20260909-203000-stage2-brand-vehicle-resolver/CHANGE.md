---
schema: coding-change/v1
id: CHG-20260909-203000-stage2-brand-vehicle-resolver
title: 搜索与品牌车型过滤 Stage 2 品牌车型管理与解析器
level: L3
status: ready_for_review
owner: chatgpt
branch: feature/stage2-brand-vehicle-management-resolver
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on:
  - CHG-20260909-185000-brand-vehicle-foundation
affected_areas:
  - vehicles
  - administration
  - api
  - contracts
  - database
affected_paths:
  - backend/src/aima_ugc/modules/vehicles
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/brand_vehicle_http.py
  - backend/src/aima_ugc/contracts/brand_vehicle.py
  - backend/src/aima_ugc/entrypoints/api_main.py
  - tests/unit
  - tests/integration
  - tests/api
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - docs/blueprint/03_数据库与文件存储.md
contracts:
  - Brand / Brand Alias 管理 HTTP API
  - Vehicle Brand Assignment / Catalog Snapshot HTTP API
data_changes:
  - 使用 Stage 1 已有 Schema；不新增 Migration，不猜测或回填历史 Vehicle 品牌归属
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 2。Stage 1 已建立 Brand、Brand Alias、Vehicle 可空 `brand_id`、Brand Evidence 与 Review Lock Schema；本阶段把这些结构接入正式管理与解析能力，并继续复用唯一 `vehicle_catalog_versions`。

范围严格限制为 Brand/Vehicle 主数据管理、统一 Catalog Snapshot、确定性 `BrandVehicleResolver`、Brand Evidence/Review Lock 持久化与 active Vehicle 品牌完整性可观察/可修复路径。不切换 Excel/TikHub Runtime，不改变 Collection Plan/Keyword Pack 既有行为，不修改声音广场 UI，不进入 Stage 3。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Brand CRUD 与 Brand Alias 管理 API，共用 Vehicle Catalog 版本 | #418 / AC1 | satisfied | `PostgresBrandVehicleRepository` + `PostgresBrandVehicleHttpService`；Brand/Alias 变更推进同一 `vehicle_catalog_versions`；Stage2 Review Fixes PostgreSQL 18.4 回归通过。 |
| R2 | Vehicle 品牌归属可显式设置、读取并检查 readiness；不猜历史归属 | #418 / AC2 | satisfied | Vehicle Create/Update/Response 暴露 `brand_id`；正式新建 active Vehicle 强制 active Brand；readiness 暴露遗留悬空 Vehicle，显式 assignment 修复；PostgreSQL 回归覆盖。 |
| R3 | 统一 Catalog Snapshot 同时冻结 Brand/Vehicle、两类 Alias、Catalog Version 与歧义上下文 | #418 / AC3 | satisfied | `BrandVehicleCatalogSnapshot` 支持 `all_active/selected`；selected Brand 自动纳入全部 active Vehicle；冻结全局 active Alias 歧义集，避免 selected 隐藏跨实体冲突；既有 Collection `VehicleCatalogSnapshot` 未修改。 |
| R4 | 纯确定性 Resolver：车型别名派生品牌、品牌别名补充、字段优先且歧义 fail-safe | #418 / AC4 | satisfied | `BrandVehicleResolver` 无 LLM/Embedding/网络依赖；title→raw_text→transcript；多实体保留、歧义不猜；独立 Review 后 Resolver 6 tests passed。 |
| R5 | Brand Evidence/Review Lock 持久化且人工锁不被自动覆盖，Brand/Vehicle evidence 独立 | #418 / AC5 | satisfied | Brand automatic/manual evidence 持久化；人工 Brand Lock 阻止自动覆盖；Vehicle Lock 不受影响；证据保留 `matched_text/source_field/derived_vehicle_model_id/catalog_version`；真实 PostgreSQL 回归通过。 |
| R6 | 真实 PostgreSQL 覆盖 CRUD/Alias/readiness/lock | #418 / AC6 | satisfied | Stage2 Review Fixes 使用 PostgreSQL 18.4：Stage2 repository 2 passed、existing administration 3 passed；`alembic upgrade head/check` 成功且无新 upgrade operations。 |
| R7 | Collection/Keyword Pack/Excel/TikHub/声音广场非目标保持不变 | #418 / AC7 | satisfied | 反向审计当前 diff：未修改 Collection Runtime/Keyword Pack/Excel/TikHub/Voice Plaza；仅 Vehicle 管理契约、正式 API 接线、生成物、测试与事实文档变化。 |
| R8 | OpenAPI/生成 Client/事实文档同步；resolver 关键语义有测试 | #418 / AC8 | satisfied | `scripts/contracts/generate.py` + Orval 成功；`contracts/openapi/openapi.json`、`frontend/src/generated/api/client.ts`、数据库事实文档同步；Unit/API Contract 回归通过。 |
| R9 | Completion Audit、独立 Review、PR HEAD CI、expected HEAD merge、main fresh CI、原生归档与 Roadmap 收口 | #418 / AC9 | explicitly_deferred | Completion Audit 与独立实现 Review 已完成且两项发现已修复；最终 PR HEAD 全量 CI、最终 Review 提交、expected-head merge、main fresh CI、原生归档与 Roadmap 状态收口属于合并生命周期后置门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | Resolver precedence、字段优先、Alias 歧义、selected 跨 Scope 歧义、人工锁优先、Brand/Vehicle evidence 独立；定向 6 passed。 |
| Contract / Generated Client | required | OpenAPI 与 `frontend/src/generated/api/client.ts` 已由正式 generator 同步；正式 PR HEAD CI 再验证无 drift。 |
| API | required | Brand CRUD/Alias、Vehicle brand assignment、snapshot/readiness、权限与错误语义；定向 API Contract 2 passed。 |
| PostgreSQL Integration | required | Brand/Alias CRUD、共享 Catalog Version、assignment/readiness、selected snapshot、Evidence/lock；PostgreSQL 18.4 定向 Stage2 2 passed + existing administration 3 passed。 |
| Browser Mock | not_applicable | 本阶段无前端页面行为变化；正式 CI 仍按变更分类执行生成 Client 相关前端门禁。 |
| Real Full-stack | required | 新公开 API 接线进入正式 `api_main`，正式 PR HEAD CI 验证既有主链路无回归。 |
| External Provider Probe | not_applicable | 不改 TikHub/LLM Provider。 |
| Docs / Governance | required | Issue #418 AC1-AC9、Change Completion Audit、数据库事实文档、独立 Review 与正式 CI Gate。 |

# 兼容、迁移与回滚

- 不新增 Migration；Stage 2 只消费 Alembic `20260909_0044` 已有结构，`alembic check` 无 drift。
- 既有 Collection Vehicle snapshot、Pack/Plan 关系和 Excel/TikHub Runtime 保持不变；Stage 2 新增独立 Brand/Vehicle Snapshot，不替换 Collection Contract。
- Stage 2 正式管理 API 对**新建 active Vehicle** 收紧为必须显式绑定有效 active Brand；这是路线要求的有意契约变化。Stage 1 前遗留的 nullable Brand Vehicle 不自动猜测回填，由 readiness 暴露并通过管理员显式修复。
- Brand 停用与 Vehicle 新建/归属修改对 Brand 行串行化；仍有 active Vehicle 时 Brand 停用 fail-closed。
- selected Snapshot 冻结全局 active Brand/Vehicle Alias 歧义集合，避免因 Scope 裁剪产生假唯一命中。
- 回滚 Stage 2 代码不会删除 Stage 1 Schema 或历史数据；若回滚应用代码，新增 Brand/Vehicle 数据仍保留于 Stage 1 已存在表中。
- 无依赖升级、无部署环境变量新增、无生产数据批量回填。

# Completion Audit

- [x] upstream_re_read：已重新读取 Stage 2、Exit Criteria、Non-goals、阶段状态规则和 Issue #418 AC1-AC9，并按最新实现复核；未提前实施 Stage 3/4 Runtime 切换。
- [x] change_coverage：R1-R8 均有实现与定向测试/生成证据；R9 仅保留必须发生在最终 PR HEAD/合并后的生命周期证据，明确 `explicitly_deferred`。
- [x] reverse_audit：已按 API→service→repository→Stage 1 schema→generated OpenAPI/client→facts docs 反查，并对 Collection/Keyword Pack/Excel/TikHub/Voice Plaza 做非目标反向核对；独立 Review 额外发现 selected Scope 隐藏全局 Alias 歧义及 Brand lifecycle 并发窗口，两项均已修复并回归。
- [x] unresolved_cleared：当前实现 Review 无已知 P0/P1/P2 阻断；剩余正式 PR HEAD CI、Review 提交、expected-head merge、main fresh CI、原生归档与 Roadmap 收口均为 R9 交付生命周期门禁，不属于未解决实现缺陷。
