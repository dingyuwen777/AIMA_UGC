---
schema: coding-change/v1
id: CHG-20260909-235500-stage3-excel-brand-vehicle-filter
title: 搜索与品牌车型过滤 Stage 3 Excel 统一过滤
level: L3
status: done
owner: chatgpt
branch: feature/stage3-excel-brand-vehicle-filter
created: 2026-09-09
updated: 2026-09-10
completion_gate: required
depends_on:
  - CHG-20260909-203000-stage2-brand-vehicle-resolver
affected_areas:
  - ingestion
  - vehicles
  - api
  - contracts
  - jobs
  - frontend
  - tests
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/ingestion
  - backend/src/aima_ugc/adapters/providers/imports/historical_chunk.py
  - backend/src/aima_ugc/adapters/persistence/postgres/brand_vehicle.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/system/README.md
  - contracts/openapi/openapi.json
  - frontend/src/features/import-batches
  - frontend/src/generated/api/client.ts
  - frontend/e2e
  - frontend/e2e-fullstack
  - scripts/performance/benchmark_stage12_historical.py
  - tests/api
  - tests/contracts
  - tests/integration/collection/test_collection_worker_runtime.py
  - tests/integration/content
  - tests/integration/ingestion
  - tests/fullstack/seed_stage8f_manual_relevance_review.py
  - tests/unit/test_brand_vehicle_resolver.py
  - docs/03_API接口说明.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - docs/blueprint/01_总体架构与技术选型.md
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/blueprint/04_后端任务API与前端.md
contracts:
  - Excel Import Brand/Vehicle Filter Scope
  - Historical/Data Import Brand/Vehicle Filter Scope
  - ingestion.import-excel.v1/v2 Job compatibility
data_changes:
  - 复用既有 Historical keyword_pack_snapshot JSONB 列承载版本化 BrandVehicle Filter Snapshot；不新增 Migration
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 3：单文件 Excel Import 与 Historical/Data Import Campaign 的新任务统一冻结 `BrandVehicleFilterSnapshot`，过滤统一调用 Stage 2 `BrandVehicleResolver`。旧 `ingestion.import-excel.v1` 与 legacy Historical Campaign 保持显式兼容，不进入 Stage 4 TikHub 或 Stage 6 完整前端产品化。

Requirement Source：#422。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新单文件 Import 与 Historical/Data Import 创建冻结 Brand/Vehicle Filter Snapshot；Excel Search 为 not applicable | #422 / AC1 | satisfied | `contracts/http.py`、`modules/ingestion/brand_vehicle_filter.py`、两条 HTTP service 与持久 Job/Campaign；Contract/API/Browser Mock 直接约束 `brand_ids`、`all_active`、`search_semantics=not_applicable`，旧 `keyword_pack_ids/vehicle_model_ids` 被拒绝。 |
| R2 | 两条 Excel 链使用统一 Resolver，保持 mapping→filtering→dedup→ingestion，并覆盖 Brand/Vehicle/multi/unmatched | #422 / AC2 | satisfied | `modules/ingestion/brand_vehicle_filter.py` 是唯一 Stage 3 Filter，单文件 Worker与 Historical converter 均调用 Stage 2 `BrandVehicleResolver`；Unit 新增 Snapshot round-trip 与 JSONL Filter 生产调用覆盖，既有 Resolver 覆盖品牌别名、车型派生品牌、多实体、歧义与 unmatched；PostgreSQL 单文件回归覆盖两个选中 Brand 的并集与 unmatched。 |
| R3 | Content 与 Brand/Vehicle Evidence 使用同一冻结 Snapshot 在现有事务边界协调写入，人工锁不被绕过 | #422 / AC3 | satisfied | `manual_ingestion.py` 与 `historical_import_worker.py` 在 Content 写事务内写入两类 Evidence；Brand/Vehicle 人工锁沿用现有 Owner。最终 Review 发现 Brand Evidence 原先会用 live 目录复核冻结结果，现由 Stage 3 调用显式传入冻结 Catalog Snapshot，并在 Repository 内校验 catalog version、Brand 和 Vehicle→Brand 归属；回归把 live 车型 alias 与品牌归属同时改写后仍要求按旧 Snapshot 成功写入。 |
| R4 | 新旧 Job/Campaign 显式版本兼容，升级前 queued/running 工作不被错读 | #422 / AC4 | satisfied | `ingestion.import-excel.v1/v2` 双注册；同一 `PostgresImportJobExecutor` 保留 legacy v1 与 v2 分支；Historical 按 Snapshot schema 和 `historical-canonical-row.v1/v2` 配对解释；Worker Registry 测试同时约束 v1/v2。 |
| R5 | retry/replay 幂等，任务创建后目录变化不改变冻结解释 | #422 / AC5 | satisfied | v2 Worker 始终从 Batch/Campaign 读取冻结 Snapshot；单文件覆盖 Lease fencing/retry、目录 alias/车型归属漂移、重复内容与人工锁；Historical 覆盖 source-change fail-closed、技术 retry、跨 chunk duplicate、取消和 lease takeover。 |
| R6 | imports_test/debug 继续复用生产能力，不复制 Resolver，不增加 Provider Probe | #422 / AC6 | satisfied | 本变更未新增 TikHub/LLM Probe，也未在调试目录复制 Resolver；`imports_test` 保留现有离线清洗用途，正式 Excel 创建、转换、Canonical、Ingestion 能力继续来自生产模块。 |
| R7 | Contract、生成物和事实文档同步，不越界 Stage 4/6，不升级依赖 | #422 / AC7 | satisfied | 公共请求 Contract 在既有 `contracts/http.py` 单点维护，OpenAPI/TypeScript Client 由正式 generator 同步；Blueprint、API、Appendix 与模块 README 已改为 `brand_ids/all_active`、Search N/A、v2/legacy 和 Evidence 事实。取消、撤销、多范围、容量基准和真实全栈资产已从旧 `keyword_pack_ids/vehicle_model_ids` 迁移到真实 Brand Catalog + `brand_ids`；关键词包只保留相关性配置与既有产品关系验收。无 Manifest/lock/Migration/Provider Search 改动；前端只完成当前入口兼容接线并说明 Stage 6 才提供品牌范围选择 UI；最终候选没有 `.github` workflow 修改。 |
| R8 | Completion Audit、两阶段 Review、PR HEAD CI、expected-head merge、main fresh CI、原生归档与 Roadmap/Issue 收口 | #422 / AC8 | explicitly_deferred | 上游重读、Completion Audit 与两阶段实现 Review 已完成，发现的重复 Contract、错误 409 表达、测试辅助重复及冻结证据 live 校验均已修复。最终 PR HEAD 全量 CI、expected-head merge、main fresh CI、Change Archive、Roadmap 状态提交与 Issue #422 关闭属于合并生命周期后置门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit | required | `tests/unit/test_brand_vehicle_resolver.py`：8 passed；覆盖 Resolver 原有语义、Filter Snapshot JSON round-trip、JSONL 生产 Filter。 |
| Contract / API / Generated Client | required | 本轮 `tests/contracts` 107 passed、`tests/api` 59 passed；Stage 3 定向 Contract/API 33 passed；OpenAPI generate/check 和 compatibility 均成功，Orval Client 已重新生成。 |
| PostgreSQL Integration | required | 前序正式 GitHub runner `34383852063`：Resolver 6/6、Historical Worker 11/11；Run `34425486728`：Content PostgreSQL 58/58。PR Run `34433881961` 提供迁移前 Red：21 passed / 7 failed；修复旧请求资产后，Run `34435514442` 的 PostgreSQL Integration 已成功。当前 Windows 缺少 `.runtime/secrets/postgres_password`，本地 PostgreSQL 套件只到收集 41 tests；最终 PR HEAD 仍需重新通过 PostgreSQL 18 门禁。 |
| Frontend static / unit / build | required | 本轮 ESLint success、Vue/TypeScript + Vite build success、Vitest 23 files / 134 tests passed。 |
| Browser Mock Acceptance | required | 本轮 `collection-runtime`、`excel-import-submit-state`、`historical-migration` 共 26 passed；请求断言覆盖 `brand_ids`、旧字段不存在及 Stage 4 Collection Discovery 既有语义保持。 |
| Real Full-stack | required | PR Run `34435514442` 提供迁移前 Red：8 passed / 6 failed，失败定位为四个 Playwright 文件仍提交 `keyword_pack_ids/vehicle_model_ids` 或选择已移除的关键词包控件。当前候选已统一改为 Brand Catalog + `brand_ids/all_active`，并以共享 helper 建立真实品牌前置；本轮 ESLint 与 14 个 Full-stack 用例发现成功，最终 PR HEAD `Real Full-stack Golden Path` 必须提供新鲜 Green。 |
| Static / Architecture / Governance | required | Ruff、mypy 324 source files、architecture、table ownership、Secret scan、docs facts/navigation、Change/Issue/PR governance 均成功；完整 Unit 为 909 passed / 8 skipped，另 3 个 Linux host-preparation 用例因 Windows 无 `os.geteuid/os.chown` 失败，交由 Linux PR CI 验证。 |
| External Provider Probe | not_applicable | Stage 3 不调用 TikHub、LLM 或 Embedding；真实 Provider 不是本 Stage 验收条件。 |
| Docs / Delivery | required | Blueprint/API/Appendix/模块 README、#422、Completion Audit、PR/main CI、expected-head merge、原生 Change 归档与合并后 Roadmap 状态收口。 |

# 兼容、迁移与回滚

- 新单文件 Import 使用 `ingestion.import-excel.v2`；`v1` 继续注册并由同一正式 Worker 的 legacy 分支解释升级前 queued/running Job。
- Historical/Data Import 通过持久 Snapshot `schema_version` 与 Chunk v1/v2 分流；旧 Campaign 继续由同一正式 Worker 的 legacy 分支处理。
- 新公共 Excel 请求仅接受 `brand_ids`；旧 `keyword_pack_ids/vehicle_model_ids` 显式拒绝，避免接受后静默忽略。
- Stage 6 才完成 Brand 范围选择产品化；本 Stage 把现有入口切到新 Contract，并明确当前默认在创建时冻结全部 active Brand。
- 兼容期复用既有 `keyword_pack_snapshot` JSONB 列承载版本化 Filter Snapshot；不新增 Migration，Stage 7 再统一清理历史载体。
- Stage 3 自动 Brand Evidence 可按任务冻结 Snapshot 校验；未提供 Snapshot 的既有 Repository 调用仍按 live 目录校验，不改变 Stage 2 管理语义。
- 不升级依赖、不调用真实 Provider、不回填生产数据。回滚到旧 Worker 前必须确认不存在 v2 queued/running Job/Campaign；legacy 数据仍可由旧版本解释。

# Completion Audit

- [x] upstream_re_read：重新核对 Roadmap Stage 3/Exit Criteria、Blueprint、Issue #422 与 Stage 2 Resolver/Snapshot/Evidence 事实源；未改变 Stage 4/6 边界。
- [x] change_coverage：R1-R7 均有实现、测试或生成证据；R8 只保留必须发生在最终 PR HEAD/合并后的交付生命周期证据并明确 `explicitly_deferred`。
- [x] reverse_audit：按 HTTP→Filter Snapshot→Job/Campaign→mapping→Resolver filtering→dedup→ingestion→Brand/Vehicle Evidence 反查，并核对 legacy v1/v2、前端入口、Full-stack seed、事实文档和无 Provider Probe 边界。Review 发现并修复公共 Contract 重复、无效品牌错误映射、Content 集成辅助代码重复，以及冻结过滤结果被 live 车型归属校验拒绝的问题。
- [x] two_stage_review：A1 从 #422/Roadmap 独立重建 AC1-AC8 并检查实现、Contract、兼容、事务与测试；A2 以最终候选 diff 反向检查公共输入、冻结边界、Evidence、前端、文档和非目标。已发现的实现问题及 CI 暴露的四组旧请求资产均已修复，当前无已知 P0/P1/P2 实现 Finding；最终 PR HEAD CI 与 GitHub review 状态仍作为合并门禁。
- [x] unresolved_cleared：R1-R7 无 `not_satisfied`；required 分层均有本轮本地证据、已有正式 PostgreSQL 证据或明确的最终 PR HEAD 验证入口。Windows 缺 PostgreSQL Secret 与 Linux-only host 用例属于已说明的本机环境限制；R8 的 PR/main/归档/Roadmap/Issue 动作是交付生命周期，不属于未解决实现缺陷。
