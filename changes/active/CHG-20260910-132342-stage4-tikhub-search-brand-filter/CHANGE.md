---
schema: coding-change/v1
id: CHG-20260910-132342-stage4-tikhub-search-brand-filter
title: 搜索与品牌车型过滤 Stage 4 TikHub 搜索过滤解耦
level: L3
status: ready_for_review
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
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_plan_lifecycle.py
  - backend/src/aima_ugc/adapters/persistence/postgres/collection_content.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/bootstrap/collection_scope.py
  - backend/src/aima_ugc/bootstrap/collection_strategy_http.py
  - backend/src/aima_ugc/bootstrap/resource_lifecycle_http.py
  - backend/src/aima_ugc/bootstrap/scheduler.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/contracts/resource_lifecycle.py
  - backend/src/aima_ugc/database_schema.py
  - migrations/versions
  - contracts/openapi/openapi.json
  - frontend/src/features/collection-strategy
  - frontend/src/features/import-batches
  - frontend/src/generated/api/client.ts
  - tests/unit/collection
  - tests/api
  - tests/contracts
  - tests/integration/collection
  - tests/integration/database
  - docs/blueprint
  - docs/collection
  - backend/src/aima_ugc/modules/collection/README.md
  - backend/src/aima_ugc/modules/system/README.md
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
| R1 | Keyword Pack 每词独立产生 `platform × keyword` Scope，不再组合 Vehicle Alias | #426 / AC1 | satisfied | `resource_selection.py` 只返回 `build_scheduled_scope_snapshot` 的逐词 Scope；确定性测试约束两个词只产生两个 Scope，且函数不再接收 Vehicle Snapshot。创建入口还拒绝任一目标平台没有适用 Search Term，避免静默少跑平台。 |
| R2 | Run/Plan/Scheduler 冻结 Search Snapshot 与 all_active/selected Brand Filter Snapshot | #426 / AC3 | satisfied | 一次性 Run 与 Scheduler 均创建 `collection-run-config.v2`，分别保存 `search_snapshot` 和 `brand_vehicle_filter`；0045 新增 `collection_plan_brands`，Create/Update/Copy/Archive 与 Response 全链持久化。兼容 `vehicle_model_ids` 在目录共享锁下转换为 active Brand，Run Response 返回实际冻结 Brand UUID。 |
| R3 | Search match、Search miss→Detail match、Detail miss→filtered 复用统一 Resolver | #426 / AC4 | satisfied | `collection_scope.py` 在 Search Canonical 后调用 Stage 2 Resolver；Search 未命中时复用受控 Detail，Detail 仍未命中则把 Search/Detail Candidate 记为 filtered。Unit 覆盖三条分支；PostgreSQL Worker Fixture 覆盖 v2 Snapshot、Search 命中、Detail 复用、同事务 Content/Brand Evidence。 |
| R4 | 新 Run 停止 Global Keyword Relevance 入库过滤，AI/人工 relevance 与旧表/API 保留 | #426 / AC5 | satisfied | HTTP/Scheduler 新 Run 不再读取或保存 `global_relevance_config`；Worker 仅对 `collection-run-config.v1` 构造 legacy `RelevanceService`，v2 缺失/错误 Filter Snapshot 时 fail closed。Global Relevance API/UI 兼容入口、AI 与人工 relevance 未删除，界面说明已同步为 legacy。 |
| R5 | Batch Supplement 不搜索且不重新过滤既有 Content | #426 / AC6 | satisfied | enrichment 分支在 discovery filter 解析前返回，删除旧 Relevance 判断；Contract 拒绝补采提交 Keyword Pack/Brand/Vehicle/Search Config，现有 PostgreSQL Fixture 约束只发 Detail 且继续更新既有 Content。 |
| R6 | Provider Request/Attempt、Raw/Candidate、计费、重试与 Fence 边界不变 | #426 / AC7 | satisfied | Stage 4 复用现有 Provider Dispatch、Raw Artifact、Candidate、Decision、Fenced Ingestion 与 Job Runtime。生产 Worker PostgreSQL 测试直接断言 Search/Detail 两组 Request/Attempt、Raw、attempt_no、dispatch/billing 状态和 Brand Evidence；既有恢复/重试测试继续进入 PR 全量 CI。 |
| R7 | Contract、Migration、生成物和长期文档同步，不越界 Stage 5-7 | #426 / AC8 | satisfied | Pydantic Run/Plan/Create/Update/Response 增加 `brand_ids` 与互斥/必选约束；0045 是 Expand-only 单 head；OpenAPI 与 TypeScript Client 已按 generator 同步。Blueprint、API、环境、测试、Appendix、Collection/System README 与当前 Vue 兼容文案已同步；未实现 Stage 5 查询/导出、Stage 6 Brand UI 或 Stage 7 清理。 |
| R8 | Completion Audit、独立 Review、PR HEAD CI、expected-head merge、main fresh CI、原生归档、Roadmap 与 Issue 收口 | #426 / AC8 | explicitly_deferred | 上游重读、Completion Audit 与两阶段实现 Review 已完成；最终 PR HEAD CI、expected-head merge、main fresh CI、仓库原生 Change Archive、Roadmap 状态提交和 Issue #426 关闭属于合并生命周期后置门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Component | required | Red 提交 `1f734a74` 的目标命令为 2 failed / 12 passed；最终 Stage 4 Unit/Contract/API 目标集 50 passed，覆盖逐词 Scope、v1/v2 选择、Resolver 三分支、Plan 互斥与补采例外。 |
| Contract / Generated Client | required | OpenAPI generate `--check` 与兼容校验均成功；Run/Plan `brand_ids`、兼容字段约束和 Lifecycle OpenAPI 有直接测试，Orval Client 已重新生成。 |
| PostgreSQL Integration | required | 新增/更新测试覆盖 Plan Brand 关系及删除保护、Scheduler v2 Snapshot、无词平台拒绝、旧车型失效隔离、Worker Content/Brand Evidence 与 filtered Candidate。当前 Windows 没有可用 PostgreSQL Secret/Engine；PR CI 首轮 PostgreSQL 18 执行发现新增 Plan Brand 子表未纳入两个旧 Fixture 清理顺序，并发现 Worker 断言未限定当前 Content Version，现已按外键顺序和当前版本范围修正，等待最终 PR HEAD 复核。 |
| Provider trace / retry | required | 正式 Worker Fixture 直接断言 Search/Detail Request/Attempt、Raw、Candidate、计费与 Evidence；现有 Retry/Recovery/Fence 套件由最终 PR HEAD CI 全量复核。未调用真实付费 TikHub。 |
| Browser Mock Acceptance | required | Vitest 23 files / 135 tests passed；PR CI 首轮发现一个旧 Playwright 旅程仍尝试 vehicle-only Discovery，修复后定向 Playwright 1 passed。兼容页面现在要求 Keyword Pack，不再受 Global Relevance 可用性阻断，车型只转换为 Brand Scope；最终 PR HEAD 重新执行 105 项 Browser Mock。 |
| Real Full-stack Golden Path | required | 前端生产构建成功；涉及 PostgreSQL/浏览器服务的现有 Golden Path 由最终 PR HEAD CI 执行。 |
| Build / Static / Governance | required | 变更 Python Ruff success；mypy 324 source files success；Alembic 单 head 为 `20260910_0045`；ESLint、TypeScript/Vue typecheck、Vite build、Contract compatibility、docs facts 与 `git diff --check` 均成功。完整 Linux CI 仍是合并门禁。 |
| External Provider Probe | not_applicable | Stage 4 行为由冻结 Fixture/正式 Adapter 调用链证明，不需要付费 TikHub 实时可用性。 |
| Docs / Delivery | required | Blueprint/API/环境/测试/Appendix/模块 README 和当前 Vue 兼容文案已同步；PR/main CI、原生归档、Roadmap 状态与 Issue Closure 按合并生命周期继续执行。 |

# 兼容、迁移、部署与回滚

- Migration 0045 仅新增 Plan→Brand 关联，不删除或回填旧表；新代码先兼容旧数据。
- 旧 queued/running `collection-run-config.v1` 继续用旧 Relevance Snapshot；v2 Worker fail closed 要求 discovery Filter Snapshot。
- 旧 Plan 的 `vehicle_model_ids` 在 Scheduler 创建 v2 Run 时显式解析到 Brand Scope；无法解析或没有 Keyword Search Terms 时拒绝调度并记录错误，不把车型别名继续当 Search Terms。
- 回滚旧应用前必须确认不存在 v2 queued/running Collection Run；Expand 表可保留，必要时在确认无新 Plan Brand 数据后 downgrade 0045。
- 不升级依赖、不执行生产 Migration/部署、不调用真实付费 Provider。

# Completion Audit

- [x] upstream_re_read：重新核对 Roadmap Stage 4/Exit Criteria、Issue #426、Stage 2 Resolver/Snapshot/Evidence、Stage 3 Import 过滤和当前 Collection Run/Plan/Scheduler/Worker/Batch 事实；未把 Stage 5 查询导出、Stage 6 Vue 产品化或 Stage 7 清理提前实现。
- [x] change_coverage：R1-R7 均有实现、测试、生成物或文档证据；R8 只保留必须发生在最终 PR HEAD/合并后的交付生命周期证据并明确 `explicitly_deferred`。
- [x] reverse_audit：按 Run/Plan 输入→Search/Filter Snapshot→Scheduler/Scope→Provider Request/Attempt/Raw/Candidate→Mapper/Canonical→Resolver→Decision/Ingestion/Evidence 反查，并核对 Batch Supplement、legacy v1、新 Contract、Plan Lifecycle、Brand 删除保护、Run 可观测字段和 Stage 6 前前端兼容入口。
- [x] two_stage_review：A1 从 #426/Roadmap 独立重建 AC1-AC8 并检查搜索复杂度、冻结语义、三条 Resolver 分支、事务、兼容与分层测试；A2 以最终候选 diff 反向检查每个生产者/消费者和文档。Review 发现并修复目录转换并发漂移、目标平台 Search Term 静默缺失、Scheduler 单 Plan 异常中断、双 Scope 脏数据、Run 冻结 Brand 不可见、Plan→Brand 删除保护缺失及旧前端文案漂移；PR CI 另发现并修复一个仍提交 vehicle-only Discovery 的 Browser Mock 资产，以及新增 Plan Brand 子表造成的 PostgreSQL Fixture 清理和 Evidence 当前版本断言问题。
- [x] unresolved_cleared：R1-R7 无 `not_satisfied`，当前无已知 P0/P1/P2 实现 Finding；本地 PostgreSQL 不可用由最终 PR HEAD PostgreSQL 18/Full-stack CI 补齐。R8 的 PR/main/归档/Roadmap/Issue 动作是交付生命周期，不属于未解决实现缺陷。
