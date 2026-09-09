---
schema: coding-change/v1
id: CHG-20260909-235500-stage3-excel-brand-vehicle-filter
title: 搜索与品牌车型过滤 Stage 3 Excel 统一过滤
level: L3
status: active
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
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/bootstrap/manual_ingestion.py
  - backend/src/aima_ugc/contracts/http.py
  - tests/unit
  - tests/contracts
  - tests/integration/ingestion
  - docs/roadmap/04_搜索与品牌车型过滤实施路线.md
contracts:
  - Excel Import Brand/Vehicle Filter Scope
  - Historical/Data Import Brand/Vehicle Filter Scope
  - ingestion.import-excel.v1/v2 Job compatibility
data_changes:
  - 优先复用既有 JSON Snapshot 持久字段作为版本化兼容载体；不计划新增 Migration
---

# 背景与目标

实施 `docs/roadmap/04_搜索与品牌车型过滤实施路线.md` Stage 3。当前单文件 Excel Import 与 Historical/Data Import Campaign 仍把 Keyword Pack 和 Vehicle Alias 作为入库过滤条件；Stage 2 已提供冻结 `BrandVehicleCatalogSnapshot`、确定性 `BrandVehicleResolver`、Brand Evidence/Review Lock 与 Vehicle Evidence 持久化能力。本 Change 只把两条 Excel 生产导入链迁移到统一 Brand/Vehicle Filter，不进入 Stage 4 TikHub 或 Stage 6 前端产品化。

Requirement Source：#422。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新单文件 Import 与 Historical/Data Import 创建冻结 Brand/Vehicle Filter Snapshot；Excel Search 为 not applicable | #422 / AC1 | pending | 待实现与 API/Contract 证据。 |
| R2 | 两条 Excel 链使用统一 Resolver，保留 mapping→filtering→dedup→ingestion，并覆盖 Brand/Vehicle/multi/unmatched | #422 / AC2 | pending | 待实现与行为测试。 |
| R3 | Content 与 Brand/Vehicle Evidence 使用同一冻结 Snapshot 在现有事务边界协调写入，人工锁不被绕过 | #422 / AC3 | pending | 待 PostgreSQL 集成证据。 |
| R4 | 新旧 Job/Campaign 显式版本兼容，升级前 queued/running 工作不被错读 | #422 / AC4 | pending | 待 legacy/new compatibility tests。 |
| R5 | retry/replay 幂等、Snapshot 不漂移 | #422 / AC5 | pending | 待 PostgreSQL/job 证据。 |
| R6 | imports_test/debug 复用生产能力，无 TikHub Probe | #422 / AC6 | pending | 待反向审计。 |
| R7 | Contract/文档同步且不越界 Stage 4/6、不升级依赖 | #422 / AC7 | pending | 待 docs/reverse audit。 |
| R8 | Completion Audit、两阶段 Review、PR/main CI、归档与 Issue 关闭 | #422 / AC8 | pending | 合并生命周期后置门禁。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Unit / Contract | required | Filter Snapshot schema、v1/v2 Job 注册、Excel/Historical 新请求参数、legacy 显式分支。 |
| PostgreSQL Integration | required | 单文件与 Historical Content + Brand/Vehicle Evidence、manual locks、retry、Snapshot frozen。 |
| Existing Regression | required | Import/Historical 取消、错误、容量、supplement 相关受影响回归。 |
| External Provider Probe | not_applicable | Stage 3 明确不依赖真实 TikHub/LLM/Embedding。 |
| Docs / Governance | required | #422、Roadmap Stage 3、Change Completion Audit、Review、PR/main CI。 |

# 兼容、迁移与回滚

- 单文件 Import 新任务使用新的版本化 Job Type/Payload；`ingestion.import-excel.v1` 保持注册并按旧 Snapshot 继续消费升级前 queued/running Job。
- Historical/Data Import 使用持久 Snapshot `schema_version` 区分 Stage 3 与 legacy Campaign；旧 Campaign 继续旧分支，新 Campaign 只使用 Brand/Vehicle Filter Snapshot。
- 新 Excel 请求不再把 Keyword Pack/单车型当 Filter；不能通过继续接受并静默忽略旧参数伪装兼容。
- Stage 6 才完成正式前端切换，因此本 Stage 是后端先行兼容窗口：Stage 3 代码不能单独部署到仍提交旧 Import 参数的生产前端。旧持久任务兼容与新请求契约是两个不同问题。
- 不升级依赖、不调用真实 Provider、不做生产数据回填。回滚应用代码前必须确认没有 Stage 3 新格式 queued/running Job/Campaign，否则旧 Worker 无法识别新格式；旧格式任务本身可继续保留。

# Completion Audit

- [ ] upstream_re_read：合并前重新读取 Stage 3、Exit Criteria、Issue #422 与最终 diff。
- [ ] change_coverage：R1-R7 均有直接实现/测试/文档证据；R8 仅保留真实合并后事件。
- [ ] reverse_audit：从 HTTP→Snapshot→Job/Campaign→mapping/filtering→dedup→ingestion→Evidence 反查，并核对 imports_test、Stage 4/6 非目标。
- [ ] validation_matrix：required 层均有本轮新鲜证据；不使用真实 TikHub Probe。
- [ ] compatibility：v1/v2 Job、legacy/new Campaign、前端部署窗口与回滚边界已验证并文档化。
- [ ] cleanup：无调试副本、无重复 Resolver、无无关依赖/配置/Schema 改动。
- [ ] independent_review：L3 两阶段 Review 完成，P0/P1=0。
- [ ] ci_and_delivery：PR HEAD CI、expected-head merge、main fresh CI、原生 Change 归档、Issue #422 回写关闭、分支清理均完成或有证据说明宿主限制。
