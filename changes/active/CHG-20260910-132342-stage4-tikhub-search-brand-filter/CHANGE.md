---
schema: coding-change/v1
id: CHG-20260910-132342-stage4-tikhub-search-brand-filter
title: 搜索与品牌车型过滤 Stage 4 TikHub 搜索过滤解耦
level: L3
status: in_progress
owner: chatgpt
branch: feature/stage4-tikhub-search-brand-filter
created: 2026-09-10
updated: 2026-09-10
completion_gate: required
depends_on:
  - CHG-20260909-203000-stage2-brand-vehicle-resolver
  - CHG-20260909-235500-stage3-excel-brand-vehicle-filter
affected_areas:
  - collection
  - vehicles
  - api
  - contracts
  - jobs
  - persistence
  - frontend-generated-client
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/collection
  - backend/src/aima_ugc/modules/ingestion/brand_vehicle_filter.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/bootstrap/collection_strategy_http.py
  - backend/src/aima_ugc/bootstrap/scheduler.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - tests/unit/collection
  - tests/api
  - tests/contracts
  - tests/integration/collection
  - tests/integration/database
  - docs/blueprint
  - docs/collection
  - backend/src/aima_ugc/modules/collection/README.md
contracts:
  - Collection Run/Plan Search Terms 与 Brand Filter Scope
  - collection-run-config.v1/v2 Job compatibility
  - Collection Plan Brand 关联持久化
data_changes:
  - 新增 collection_plan_brands Expand 表；保留 collection_plan_vehicle_models 与 global_relevance_config 到 Stage 7
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 4：TikHub Discovery 只按 Keyword Pack 实际词建立 `platform × keyword` Scope，并在 Canonical 后使用任务创建时冻结的 Brand/Vehicle Filter Snapshot。旧 `collection-run-config.v1` 继续按原关键词 Relevance 解释；新任务使用 v2，Batch Supplement 不重新过滤既有 Content。

Requirement Source：#426。

# 范围与非目标

- 范围：一次性 Run、周期 Plan/Scheduler、Collection Worker、Plan Brand Expand Schema、公共 Contract/生成 Client、测试与长期事实文档。
- 非目标：不实施 Stage 5 查询/导出、不实施 Stage 6 Vue 品牌选择产品化、不执行 Stage 7 旧表删除或历史内容回填、不新增 Provider fallback/AI/Embedding。
- 必须保持：Provider Request/Attempt、Raw/Candidate、计费/重试/Lease/Fence、Mapper 纯映射、Content Owner、AI/人工 relevance、Stage 3 Excel/Historical Filter。

# 已确认方案

1. 推荐并采用 Expand-first：新增 `collection_plan_brands` 保存稳定 Brand Scope；旧 `collection_plan_vehicle_models` 保留到 Stage 7。
2. 新 Run 使用 `collection-run-config.v2`，冻结 Search Snapshot 与 `BrandVehicleFilterSnapshot(search_semantics=keyword_pack)`；v1 queued/running Run 继续走旧 Relevance 解释。
3. 公共 Run/Plan 增加 `brand_ids`。兼容期保留 `vehicle_model_ids`，显式转换为所属 Brand Scope；与 `brand_ids` 同时提交时拒绝，只有车型且没有 Keyword Pack 的 Discovery/Plan 拒绝，避免静默忽略或继续车型搜索。
4. 新 Discovery 在 Search Canonical 未命中时只复用现有受控 Detail 请求；不增加搜索组合。Batch Supplement 不执行该过滤。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Keyword Pack 每词独立产生 `platform × keyword` Scope，不再组合 Vehicle Alias | #426 / AC1-AC2 | not_satisfied | 计划修改 `resource_selection.py` 并补确定性 Red/Green 测试。 |
| R2 | Run/Plan/Scheduler 冻结 Search Snapshot 与 all_active/selected Brand Filter Snapshot | #426 / AC3 | not_satisfied | 计划新增 Plan Brand Expand 表并升级 Run Snapshot v2。 |
| R3 | Search match、Search miss→Detail match、Detail miss→filtered 复用统一 Resolver | #426 / AC4 | not_satisfied | 计划改 `collection_scope.py` 并补 Fixture/PostgreSQL 集成证据。 |
| R4 | 新 Run 停止 Global Keyword Relevance 入库过滤，AI/人工 relevance 与旧表/API 保留 | #426 / AC5 | not_satisfied | 计划从新 Run/Scheduler/Worker 路径移除旧依赖，保留 v1 兼容分支。 |
| R5 | Batch Supplement 不搜索且不重新过滤既有 Content | #426 / AC6 | not_satisfied | 计划删除 enrichment 的旧 Relevance 判断并补回归。 |
| R6 | Provider Request/Attempt、Raw/Candidate、计费、重试与 Fence 边界不变 | #426 / AC7 | not_satisfied | 计划复用现有调用链并执行恢复/计费回归。 |
| R7 | Contract、Migration、生成物和长期文档同步，不越界 Stage 5-7 | #426 / AC8 | not_satisfied | 计划执行 OpenAPI/Client、Migration、Schema、Docs 同步与校验。 |
| R8 | Completion Audit、独立 Review、PR HEAD CI、expected-head merge、main fresh CI、原生归档、Roadmap 与 Issue 收口 | user:stage4-end-to-end-delivery | not_satisfied | 交付生命周期完成后回填。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | Scope 独立展开、v1/v2 Snapshot 解析、Resolver 三分支、补采例外。 |
| Contract / Generated Client | required | Run/Plan `brand_ids`、兼容字段约束、OpenAPI/Orval 漂移。 |
| PostgreSQL Integration | required | Plan Brand 关系、Scheduler v2 Snapshot、Worker Evidence 与 filtered Candidate。 |
| Provider trace / retry | required | 现有 TikHub Fixture 下 Request/Attempt/Raw、计费、Retry/Fence 回归。 |
| Browser Mock Acceptance | required | 现有 Stage 6 前 UI 仍可经兼容字段提交，生成 Contract 不破坏当前构建。 |
| Real Full-stack Golden Path | required | 现有 Collection 关键路径在 PR CI 保持接通。 |
| Build / Static / Governance | required | Ruff、mypy、backend/frontend build、Migration/Schema、Change Ready、CI。 |
| External Provider Probe | not_applicable | Stage 4 行为由冻结 Fixture/正式 Adapter 调用链证明，不需要付费 TikHub 实时可用性。 |
| Docs / Delivery | required | Blueprint/模块 README、PR/main CI、原生归档、Roadmap 和 Issue Closure。 |

# 兼容、迁移、部署与回滚

- Migration 0045 仅新增 Plan→Brand 关联，不删除或回填旧表；新代码先兼容旧数据。
- 旧 queued/running `collection-run-config.v1` 继续用旧 Relevance Snapshot；v2 Worker fail closed 要求 discovery Filter Snapshot。
- 旧 Plan 的 `vehicle_model_ids` 在 Scheduler 创建 v2 Run 时显式解析到 Brand Scope；无法解析或没有 Keyword Search Terms 时拒绝调度并记录错误，不把车型别名继续当 Search Terms。
- 回滚旧应用前必须确认不存在 v2 queued/running Collection Run；Expand 表可保留，必要时在确认无新 Plan Brand 数据后 downgrade 0045。
- 不升级依赖、不执行生产 Migration/部署、不调用真实付费 Provider。

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] two_stage_review
- [ ] unresolved_cleared

