---
schema: coding-change/v1
id: CHG-20260909-203000-stage2-brand-vehicle-resolver
title: 搜索与品牌车型过滤 Stage 2 品牌车型管理与解析器
level: L3
status: active
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
| R1 | Brand CRUD 与 Brand Alias 管理 API，共用 Vehicle Catalog 版本 | #418 / AC1 | planned | Brand repository/service/routes + PostgreSQL/API tests |
| R2 | Vehicle 品牌归属可显式设置、读取并检查 readiness；不猜历史归属 | #418 / AC2 | planned | Vehicle brand assignment/readiness API + repository tests |
| R3 | 统一 Catalog Snapshot 同时冻结 Brand/Vehicle 及两类 Alias | #418 / AC3 | planned | `BrandVehicleCatalogSnapshot` + snapshot repository/API |
| R4 | 纯确定性 Resolver：车型别名优先派生品牌、品牌别名补充、字段优先且歧义 fail-safe | #418 / AC4 | planned | resolver 单元测试 |
| R5 | Brand Evidence/Review Lock 持久化且人工锁不被自动覆盖，Brand/Vehicle evidence 独立 | #418 / AC5 | planned | repository + PostgreSQL integration tests |
| R6 | 真实 PostgreSQL 覆盖 CRUD/Alias/readiness/lock | #418 / AC6 | explicitly_deferred | 当前 PR HEAD 正式 PostgreSQL 18.4 CI |
| R7 | Collection/Keyword Pack/Excel/TikHub/声音广场非目标保持不变 | #418 / AC7 | planned | reverse audit + regression CI |
| R8 | OpenAPI/生成 Client/事实文档同步；resolver 关键语义有测试 | #418 / AC8 | planned | generated contract gate + docs facts + unit tests |
| R9 | Completion Audit、独立 Review、PR HEAD CI、expected HEAD merge、main fresh CI、原生归档与 Roadmap 收口 | #418 / AC9 | explicitly_deferred | 生命周期后置门禁，不提前宣称完成 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | Resolver precedence、字段优先、Alias 歧义、人工锁优先、Brand/Vehicle evidence 独立 |
| Contract / Generated Client | required | OpenAPI 与 `frontend/src/generated/api/client.ts` 必须由正式 generator 同步 |
| API | required | Brand CRUD/Alias、Vehicle brand assignment、snapshot/readiness、权限与错误语义 |
| PostgreSQL Integration | required | Brand/Alias CRUD、Catalog version、assignment/readiness、Evidence/lock |
| Browser Mock | not_applicable | 本阶段无前端页面行为变化 |
| Real Full-stack | required | 新公开 API 接线进入正式 `api_main`，并验证既有主链路无回归 |
| External Provider Probe | not_applicable | 不改 TikHub/LLM Provider |
| Docs / Governance | required | Change/Issue/Completion Audit/Review/docs facts/CI Gate |

# 兼容与回滚

- 不新增 Migration；Stage 2 仅消费 `20260909_0044` 已存在结构。
- 既有 Vehicle CRUD/Collection snapshot 保持兼容；品牌归属通过独立显式管理 API 提供，不要求旧调用方立即传 Brand。
- active Vehicle 缺少 active Brand 时只标记为 unresolved/not-ready，并从统一自动解析 snapshot 中 fail-safe 排除；管理员可显式修复，禁止根据 Keyword Pack 或名称猜测回填。
- 回滚 Stage 2 代码不会删除 Stage 1 Schema 或历史数据。

# Completion Audit

- [ ] upstream_re_read：合并前重读 Stage 2/Exit/状态规则、Issue #418 AC1-AC9 与最终实现。
- [ ] change_coverage：R1-R9 全部具有实现/测试/后置证据或明确非目标。
- [ ] reverse_audit：按 API→service→repository→schema→generated contract→docs 与 Collection/Import 反向检查。
- [ ] unresolved_cleared：无未决阻断；正式 CI/Review/main fresh evidence 完成前不得合并或标 Stage 2 completed。
