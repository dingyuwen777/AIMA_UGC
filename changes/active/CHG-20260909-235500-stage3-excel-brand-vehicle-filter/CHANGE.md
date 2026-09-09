---
schema: coding-change/v1
id: CHG-20260909-235500-stage3-excel-brand-vehicle-filter
title: 搜索与品牌车型过滤 Stage 3 Excel 统一过滤
level: L3
status: ready_for_review
owner: chatgpt
branch: feature/stage3-excel-brand-vehicle-filter
created: 2026-09-09
updated: 2026-09-09
completion_gate: required
depends_on:
  - CHG-20260909-203000-stage2-brand-vehicle-resolver
affected_areas:
  - ingestion
  - vehicles
  - api
  - contracts
  - jobs
  - docs
affected_paths:
  - backend/src/aima_ugc/modules/ingestion
  - backend/src/aima_ugc/adapters/providers/imports/historical_chunk.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - backend/src/aima_ugc/contracts/stage3_import.py
  - tests/contracts
  - tests/integration/ingestion
  - docs/roadmap/04_搜索与品牌车型过滤实施路线.md
contracts:
  - Excel Import Brand/Vehicle Filter Scope
  - Historical/Data Import Brand/Vehicle Filter Scope
  - ingestion.import-excel.v1/v2 Job compatibility
data_changes:
  - 复用既有 Historical keyword_pack_snapshot JSONB 列承载版本化 BrandVehicle Filter Snapshot；不新增 Migration
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 3：单文件 Excel Import 与 Historical/Data Import Campaign 的新任务统一冻结 `BrandVehicleFilterSnapshot`，过滤统一调用 Stage 2 `BrandVehicleResolver`。旧 `ingestion.import-excel.v1` 与 legacy Historical Campaign 保持显式兼容，不进入 Stage 4 TikHub 或 Stage 6 前端产品化。

Requirement Source：#422。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新单文件 Import 与 Historical/Data Import 创建冻结 Brand/Vehicle Filter Snapshot；Excel Search 为 not applicable | #422 / AC1 | satisfied | `contracts/stage3_import.py`、`bootstrap/api.py`、`bootstrap/import_http.py`、`bootstrap/historical_import_http.py`；Contract 测试直接约束 `brand_ids` 与旧字段移除。 |
| R2 | 两条 Excel 链使用统一 Resolver，保留 mapping→filtering→dedup→ingestion，并覆盖 Brand/Vehicle/multi/unmatched | #422 / AC2 | satisfied | `modules/ingestion/brand_vehicle_filter.py` 作为唯一 Stage 3 Filter；单文件 Worker 与 Historical converter 均调用该模块，旧 `offline_content` 仅留给 legacy v1。 |
| R3 | Content 与 Brand/Vehicle Evidence 使用同一冻结 Snapshot 在现有事务边界协调写入，人工锁不被绕过 | #422 / AC3 | satisfied | `bootstrap/manual_ingestion.py` 与 `bootstrap/historical_import_worker.py` 在 Content 写事务内调用现有 Brand/Vehicle Repository；Repository 原有 Review Lock 仍是裁决点。 |
| R4 | 新旧 Job/Campaign 显式版本兼容，升级前 queued/running 工作不被错读 | #422 / AC4 | satisfied | `ingestion.import-excel.v1/v2` 双注册；Historical Snapshot schema + `historical-canonical-row.v1/v2` 强配对；legacy Worker 路径委托冻结 base。 |
| R5 | retry/replay 幂等、Snapshot 不漂移 | #422 / AC5 | satisfied | v2 Worker 每次从 Batch/Campaign 读取冻结 Snapshot，单文件 PostgreSQL 回归覆盖 Lease fencing、retry 后 Content 不重复；最终 CI 继续验证全量回归。 |
| R6 | imports_test/debug 复用生产能力，无 TikHub Probe | #422 / AC6 | satisfied | 本变更未新增 Provider Probe、未复制 Resolver；调试导入继续从生产 converter/ingestion 模块进入，后续反向审计不允许新增第二套过滤器。 |
| R7 | Contract/文档同步且不越界 Stage 4/6、不升级依赖 | #422 / AC7 | satisfied | 变更集中于 Excel/Historical 创建与执行链；无 Manifest/lock/Migration/Provider Search 改动；Stage 6 前端部署窗口在本 Change 明示。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Contract | required | Stage 3 创建 Contract、v1/v2 Job 注册、Snapshot schema 与显式 legacy/new 分支；PR CI 作为新鲜执行证据。 |
| PostgreSQL Integration | required | 单文件 Import v2 已迁移现有 PostgreSQL 行为回归，覆盖成功、Artifact 失败、retry/fencing；Historical 全量回归由 PR CI 验证。 |
| Existing Regression | required | Import/Historical 取消、错误、容量、supplement 等既有测试在 PR CI 全量执行。 |
| External Provider Probe | not_applicable | Stage 3 不依赖真实 TikHub/LLM/Embedding，禁止用外部 Probe 作为验收条件。 |
| Docs / Governance | required | #422、Roadmap Stage 3、Completion Audit、两阶段 Review、PR/main CI 与原生 Change 归档。 |

# 兼容、迁移与回滚

- 新单文件 Import 使用 `ingestion.import-excel.v2`；`v1` 继续注册并由 frozen base Worker 解释升级前 queued/running Job。
- Historical/Data Import 通过持久 Snapshot `schema_version` 与 Chunk v1/v2 分流；旧 Campaign 继续 legacy 分支。
- 新公共 Excel 请求仅接受 `brand_ids`；旧 `keyword_pack_ids/vehicle_model_ids` 会被显式拒绝，不存在接受后静默忽略。
- Stage 6 才完成正式前端切换，因此 Stage 3 是后端先行兼容窗口：不能把本 Stage 单独部署到仍提交旧 Import 参数的生产前端。
- 兼容期复用既有 `keyword_pack_snapshot` JSONB 列承载版本化 Filter Snapshot，避免只因字段名迁移引入无收益 Migration；Stage 7 再统一清理历史兼容载体。
- 不升级依赖、不调用真实 Provider、不做生产数据回填。回滚到旧 Worker 前必须确认不存在 v2 queued/running Job/Campaign；legacy 数据本身仍可由旧版本解释。

# Completion Audit

- [x] upstream_re_read：已重新核对 Roadmap Stage 3/Exit Criteria、Blueprint、Issue #422 与 Stage 2 Resolver/Snapshot/Evidence 事实源；本轮未改变 Stage 4/6 边界。
- [x] change_coverage：R1-R7 均存在直接实现路径与对应 Contract/PostgreSQL 验证入口；合并后 CI/归档/Issue 关闭属于 PR 交付生命周期，不伪写进预合并 Requirement 结果。
- [x] reverse_audit：已从 HTTP→Filter Snapshot→Job/Campaign→mapping→Resolver filtering→dedup→ingestion→Brand/Vehicle Evidence 反查；legacy v1 与新 v2 路径显式隔离。
- [x] unresolved_cleared：当前静态审计无待决实现项或架构决策；下一步进入独立 PR CI/Review，若发现缺陷立即退回 Draft/active 修复，不以 ready_for_review 代替测试通过结论。
