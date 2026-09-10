---
schema: coding-change/v1
id: CHG-20260909-235500-stage3-excel-brand-vehicle-filter
title: 搜索与品牌车型过滤 Stage 3 Excel 统一过滤
level: L3
status: ready_for_review
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
  - ci
  - docs
affected_paths:
  - .github/workflows/ci.yml
  - backend/src/aima_ugc/modules/ingestion
  - backend/src/aima_ugc/adapters/providers/imports/historical_chunk.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - backend/src/aima_ugc/contracts/stage3_import.py
  - contracts/openapi/openapi.json
  - frontend/src/features/import-batches
  - frontend/src/generated/api/client.ts
  - frontend/e2e
  - tests/api
  - tests/contracts
  - tests/integration/collection/test_collection_worker_runtime.py
  - tests/integration/content
  - tests/integration/ingestion
  - tests/fullstack/seed_stage8f_manual_relevance_review.py
  - docs/blueprint/01_总体架构与技术选型.md
  - docs/roadmap/04_搜索与品牌车型过滤实施路线.md
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
| R1 | 新单文件 Import 与 Historical/Data Import 创建冻结 Brand/Vehicle Filter Snapshot；Excel Search 为 not applicable | #422 / AC1 | satisfied | `contracts/stage3_import.py`、`bootstrap/api.py`、`bootstrap/import_http.py`、`bootstrap/historical_import_http.py`；Contract/API 测试直接约束 `brand_ids` 与旧字段拒绝；Browser Mock 直接断言新请求不再携带 `keyword_pack_ids/vehicle_model_ids`。 |
| R2 | 两条 Excel 链使用统一 Resolver，保留 mapping→filtering→dedup→ingestion，并覆盖 Brand/Vehicle/multi/unmatched | #422 / AC2 | satisfied | `modules/ingestion/brand_vehicle_filter.py` 是唯一 Stage 3 Filter；单文件 Worker 与 Historical converter 均调用该模块，旧 `offline_content` 仅由 legacy v1 路径消费。补充验收 Run `34383852063`：Stage 2 Resolver `6/6`、Historical PostgreSQL Worker `11/11`、目标 Browser Mock `26/26`。 |
| R3 | Content 与 Brand/Vehicle Evidence 使用同一冻结 Snapshot 在现有事务边界协调写入，人工锁不被绕过 | #422 / AC3 | satisfied | `bootstrap/manual_ingestion.py` 与 `bootstrap/historical_import_worker.py` 在 Content 写事务内调用现有 Brand/Vehicle Repository；Brand 自动 Evidence 受 `review_lock` 拦截，Vehicle Evidence 受人工 Review Lock 约束；同一冻结 Snapshot 在过滤后再次解析并写 Evidence。 |
| R4 | 新旧 Job/Campaign 显式版本兼容，升级前 queued/running 工作不被错读 | #422 / AC4 | satisfied | `ingestion.import-excel.v1/v2` 双注册；`PostgresImportJobExecutor` 在同一正式模块内保留 `_execute_v1` 与 v2 分支；Historical 在同一正式 Worker 内按 Snapshot schema + `historical-canonical-row.v1/v2` 强配对；`test_collection_worker_runtime.py` 直接约束生产 Worker Registry 同时暴露 v1/v2，不保留镜像 base/第二套 Worker。 |
| R5 | retry/replay 幂等、Snapshot 不漂移 | #422 / AC5 | satisfied | v2 Worker 每次从 Batch/Campaign 读取冻结 Snapshot；单文件回归覆盖 Lease fencing/retry 后 Content 不重复；Historical `11/11` 集成套件继续覆盖 source-change fail-closed、技术 retry、跨 chunk duplicate、取消、lease takeover 等原有任务级语义。 |
| R6 | imports_test/debug 复用生产能力，无 TikHub Probe | #422 / AC6 | satisfied | 本变更未新增 Provider Probe、未复制 Resolver；调试导入继续从生产 converter/ingestion 模块进入，反向审计未发现第二套 Stage 3 Filter/Resolver。 |
| R7 | Contract/文档同步且不越界 Stage 4/6、不升级依赖 | #422 / AC7 | satisfied | 变更集中于 Excel/Historical 创建与执行链；无 Manifest/lock/Migration/Provider Search 改动；前端只做新 Contract 的兼容接线，完整 Brand 范围产品化仍留 Stage 6。正式 CI 因 GitHub hosted runner 自带、与项目无关的 Chrome APT 源连续三次 `Hash Sum mismatch`，仅在字体安装 job 内隔离该第三方源并保留 `fonts-noto-cjk` 强制安装及失败阻断，不改变产品依赖或测试门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Static / Contract | required | 一次性 GitHub runner `34379511703`：Ruff 全绿、mypy 325 source files 全绿、正式 OpenAPI generator 无漂移、Stage 3 Contract tests 通过；最终 PR HEAD 永久 CI 仍是合并门禁。 |
| Resolver / PostgreSQL | required | 补充验收 Run `34383852063`：`tests/unit/test_brand_vehicle_resolver.py` `6/6`；PostgreSQL 18.4 + Alembic head `20260909_0044` / `alembic check` 无新操作；`test_stage12_historical_campaign_worker.py` `11/11`。针对旧 Content seed 的迁移 Run `34425486728` 在 PostgreSQL 18.4 上执行 `tests/integration/content -q`，结果 `58 passed / 0 failed`，并在 Green 后才提交 7 个正式测试资产。最终 PR HEAD PostgreSQL 全量门禁仍必须再次通过。 |
| Browser Mock Acceptance | required | Run `34383852063`：`collection-runtime`、`excel-import-submit-state`、`historical-migration` 共 `26/26`；请求级断言覆盖 `brand_ids`、旧字段不存在，且同页 TikHub Discovery 的既有 Keyword/Vehicle 语义未被 Stage 3 越界修改。 |
| Real Full-stack | required | 既有 Stage 8F 人工相关性复核 seed 已迁移为真实 Stage 2 Brand Catalog + Stage 3 `brand_ids` 导入，不再直接调用已移除的 `keyword_pack_ids`；最终 PR HEAD `Real Full-stack Golden Path` 必须通过后方可合并。 |
| Existing Regression | required | API/Contract 与 Import/Historical 原有取消、错误、容量、supplement 等套件保留；Run `34425486728` 已补证整个 Content PostgreSQL 套件 `58/58`；最终 PR HEAD 永久 CI 仍执行全量回归。 |
| CI Infrastructure | required | `ci.yml` 的 CJK 字体步骤只临时禁用 hosted runner 的 `dl.google.com/linux/chrome-stable/deb` 第三方源并为官方 APT 源增加有限重试；字体仍安装，后续所有质量/测试层仍必须成功。 |
| External Provider Probe | not_applicable | Stage 3 不依赖真实 TikHub/LLM/Embedding，禁止用外部 Probe 作为验收条件。 |
| Docs / Governance | required | #422、Roadmap Stage 3、Completion Audit、L3 Deep Review、PR/main CI、expected-head merge 与原生 Change 归档。 |

# 兼容、迁移与回滚

- 新单文件 Import 使用 `ingestion.import-excel.v2`；`v1` 继续注册并由同一正式 Worker 内的 legacy 分支解释升级前 queued/running Job。
- Historical/Data Import 通过持久 Snapshot `schema_version` 与 Chunk v1/v2 分流；旧 Campaign 继续同一正式 Worker 的 legacy 分支。
- 新公共 Excel 请求仅接受 `brand_ids`；旧 `keyword_pack_ids/vehicle_model_ids` 会被显式拒绝，不存在接受后静默忽略。
- Stage 6 才完成完整 Brand 范围选择产品化；本 Stage 已把现有前端调用切到新 Contract，并明确提示当前按创建时全部 active Brand 冻结，不伪造尚未实现的范围选择 UI。
- 兼容期复用既有 `keyword_pack_snapshot` JSONB 列承载版本化 Filter Snapshot，避免只因字段名迁移引入无收益 Migration；Stage 7 再统一清理历史兼容载体。
- 不升级依赖、不调用真实 Provider、不做生产数据回填。回滚到旧 Worker 前必须确认不存在 v2 queued/running Job/Campaign；legacy 数据本身仍可由旧版本解释。
- CI 字体安装健壮化仅影响 GitHub hosted runner 单个 job 的 APT source 视图；不修改镜像、Runtime、生产部署或依赖锁，回滚即恢复原两条 `apt-get` 命令。

# Completion Audit

- [x] upstream_re_read：已重新核对 Roadmap Stage 3/Exit Criteria、Blueprint、Issue #422 与 Stage 2 Resolver/Snapshot/Evidence 事实源；本轮未改变 Stage 4/6 边界。
- [x] change_coverage：R1-R7 均存在直接实现路径与 Contract/PostgreSQL/Browser/Full-stack 验证入口；本轮新增发现的 Content 集成回归资产已纳入 `affected_paths`，合并后 main CI、归档与 Issue 关闭属于 PR 交付生命周期，不伪写进预合并 Requirement 结果。
- [x] reverse_audit：已从 HTTP→Filter Snapshot→Job/Campaign→mapping→Resolver filtering→dedup→ingestion→Brand/Vehicle Evidence 反查；legacy v1 与新 v2 在同一正式模块内显式分流；旧 Content seed 已迁移到正式 Brand Catalog + `brand_ids`，Stage8D 的 Global Relevance Keyword Pack 职责保持不变；任务临时迁移 workflow 已从最终候选 diff 清理。
- [ ] two_stage_review：先前 Review 之后又新增了 Worker Registry 与 7 个 Content 集成测试修复；因此旧 Review 不作为最终 candidate 结论，必须在最终稳定 HEAD 上重新执行 L3 Deep Review。
- [ ] unresolved_cleared：Stage 3 定向 PostgreSQL Content 回归现为 `58/58`，但最终候选 HEAD 的永久 CI、Runtime Acceptance、Developer Tooling、Real Full-stack、expected-head merge、main fresh CI、原生 Change 归档与 Issue #422 关闭仍待新鲜证据；这些门禁完成前不声明端到端完成。
