---
schema: rvc-change/v1
id: CHG-20260820-stage8a-unified-manual-ingestion
title: Stage 8A Unified Manual Ingestion Foundation
level: L3
status: ready_for_review
owner: AI coding agent
branch: feature/stage8a-unified-manual-ingestion
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas:
  - ingestion
  - provenance
  - postgres
  - debug-entrypoints
  - documentation
affected_paths:
  - changes/active/CHG-20260820-stage8a-unified-manual-ingestion/
  - backend/src/aima_ugc/modules/ingestion/
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/adapters/providers/imports_test/
  - backend/src/aima_ugc/adapters/providers/tikhub_test/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/contracts/provider/
  - backend/src/aima_ugc/database_schema.py
  - contracts/provider/
  - migrations/
  - scripts/quality/check_table_ownership.py
  - tests/
  - docs/blueprint/
  - docs/测试与调试说明.md
contracts:
  - ProviderRequestV1
data_changes:
  - processing_import_batches
  - provider_requests
---

# Stage 8A：Unified Manual Ingestion Foundation

## 1. 结果与当前机器事实

Stage 1—7 与临时 P1 已闭环。本 Change 只实现 Stage 8A，不进入 Stage 8B/8C，也不开发正式前端。

Stage 8A 已形成以下机器事实：

1. `processing_import_batches` 是 Excel File Import 的最小业务父事实，不复制 Content/Comment 业务字段。
2. `ProviderRequestV1/provider_requests` 恰好属于 Collection Scope 或 Processing Import Batch 之一；无父级和双父级关闭失败。
3. Excel File Import 不制造 Collection Run/Scope/Candidate；使用 Input Artifact + Processing Import Batch + import-parent Provider Request/non-billable Attempt，并把 Input Artifact 绑定为 Attempt 的真实来源证据。
4. TikHub 数据库模式继续使用正式 Collection 语义：manual Run/keyword Scope → Provider Request/Attempt → Raw → Candidate-before-Mapper → Canonical → fenced Ingestion。
5. `imports_test`、`tikhub_test` 默认仍为 file-only；只有显式开启数据库模式才装配 PostgreSQL Runtime。
6. Canonical 之后不新增 Excel/TikHub 私有 Writer，统一进入现有 Content Ingestion / Content Owner Repository。
7. PostgreSQL 继续以 `(platform, external_content_id)` 和评论稳定身份作为跨批次、跨来源业务收敛边界，并保留 Version/Metric/来源历史。

## 2. 已确认的上游决策与不变项

- Excel 是第一版主要人工数据入口，TikHub 是辅助来源。
- PostgreSQL 是唯一业务事实库；Excel/JSONL/XLSX 调试产物不是业务数据库。
- Provider 差异在 Canonical 前结束；Canonical 后只复用正式 Ingestion 和 Owner Repository。
- 禁止私有 DB Writer/Repository 和绕过 Owner 的 SQL。
- 两个调试入口永久保留，默认 file-only，数据库模式显式 opt-in。
- 数据库模式只连接已准备好的 PostgreSQL 18，不管理 Docker，不自动跑 Migration。
- DB/Schema 失败明确失败；已有文件不删除。
- Stage 8A 不新增 HTTP API、正式前端、Analysis 持久化、认证权限、预算系统或新基础设施。

## 3. 成功标准状态

1. File Import 不伪造 Collection 来源：已实现。
2. 两个调试入口默认不要求数据库：已实现。
3. 显式 DB 模式复用正式来源链和 Ingestion：已实现。
4. DB/Schema 不可用时关闭失败且不自动管理容器/Migration：已实现并有边界测试。
5. 重复 Excel 与 Excel/TikHub 跨来源只形成一个 Current：PG18 Integration 已验证。
6. 更晚合法 Observation 推进 Current/Version/Metric：PG18 Integration 已验证。
7. 数据库阶段失败后可重试且不制造第二 Current：PG18 Integration 已验证。
8. 最终合并仍必须以 PR 实际最新 head 的新鲜 CI 与 Review 为准。

## 4. 来源链方案

- 方案 A（Excel 制造 Collection Run/Scope）：污染 Collection 语义，不采用。
- 方案 B（Provider Request 双父级）：复用 Attempt/Artifact 与 Content 来源约束，不伪造 Collection，已采用。
- 方案 C（独立 FileAttempt/FileSource）：复制执行/来源体系、扩大 Content 来源模型，不采用。

## 5. Schema / Migration

Forward Revision：`20260820_0019`，Revises `20260818_0018`。

```text
processing_import_batches
  id                uuid PK
  input_artifact_id uuid NOT NULL FK artifacts(id)
  job_id            uuid NULL UNIQUE FK jobs(id)
  status            processing | succeeded | failed
  stats             jsonb NOT NULL default {}
  error_summary     text NULL
  created_at        timestamptz NOT NULL
  started_at        timestamptz NULL
  finished_at       timestamptz NULL

provider_requests
  scope_id        nullable
  import_batch_id nullable FK processing_import_batches(id)
  CHECK exactly one(scope_id, import_batch_id)
  UNIQUE(import_batch_id, request_fingerprint)
  INDEX(import_batch_id, created_at)
```

Provider Request 已有 Attempt 后来源身份继续不可修改。已有 File Import Request 时 downgrade 明确拒绝，防止丢失 provenance。

## 6. Excel File Import

```text
XLSX → Reader/Mapper → Canonical JSONL → filter → deduplicate
→ [显式 DB] Input Artifact → Import Batch → import-parent Request/Attempt
→ Canonical Source → ContentIngestionService → Content Owner → PostgreSQL
```

`imports_test`：`WRITE_TO_DATABASE=False`，支持 `run_all(..., write_to_database=False)` 与 `ingest_database(run_dir=...)`。DB 模式实际顺序为 `convert → filter → deduplicate → database_ingestion → AI → Excel`；DB 失败时已生成文件保留，后续阶段不自动继续。

## 7. TikHub 调试数据库模式

五个平台均支持：

```python
write_to_database: bool = False
provider_config_id: UUID | None = None
```

DB 模式验证正式 Provider Config/Secret 与本次 `.env` 一致，然后：

```text
manual Collection / Job Fencing
→ Provider Request / billable Attempt
→ ProviderDispatchService
→ 一次 Transport.send
→ 同一响应：本地 Raw 镜像 + 正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 Mapper / Canonical
→ fenced Ingestion
→ PostgreSQL
```

不会额外再发一次 TikHub 请求，也不从 JSONL/Excel 二次回灌。

## 8. TDD 证据

Red 提交 `cab003d9...`：Stage 5B 为 `267 passed / 1 failed`，唯一失败是 TikHub 公共入口尚无 `write_to_database`。

Green 后实现 Stage 8A；其后只按 CI 证据修正 Ruff/import-order/mypy。专属 PG18 验收加入后曾只因测试文件 Ruff format 失败，业务 PG18 断言已通过；格式化后重新取得全绿，未修改断言。

## 9. PostgreSQL 18 / CI 已有证据

核心实现检查点 `08f1d646058a0da447b658a257a3f6da61dc0c17` 的 12 个适用 workflow 全部 success。

Stage 5B run `32287548694` / job `96180559519`：

```text
postgres:18.4
268 passed in 4.85s
20260820_0019 (head)
alembic check: No new upgrade operations detected.
69 PostgreSQL integration passed in 11.94s
```

同一 job 成功完成 Architecture、Table Ownership、Secret、Docs、Contract generation/compatibility、base roundtrip 和 previous-revision roundtrip。

由于 README/导航/测试说明/Change 后续又产生文档提交，最终合并必须重新查询 PR 实际最新 head 的全部适用 workflow；上述证据不能替代最终 head 验证。

## 10. 文档同步

已同步：Blueprint 02、03、17、根 Blueprint README、`imports_test/README.md`、`tikhub_test/README.md`、`docs/测试与调试说明.md`。

不修改依据：

- Blueprint 04：无 HTTP Contract/Route/Client 变化，属于 8B。
- Blueprint 15：无 Analysis Contract/Prompt/taxonomy/persistence 变化。
- Blueprint 13：无 `UnifiedDataExcelV1` / Workbook / Exporter Contract 变化。
- Blueprint 06：开发流程和门禁未变化，Stage 8 子阶段由 17/根导航维护。

## 11. 兼容、依赖、部署、回滚

- 既有 Collection Request 继续使用 `scope_id`，旧数据不重写。
- 调试入口默认 file-only，已有调用兼容。
- 未新增/升级/降级依赖；PG 仍为 18 系列。
- 部署：备份 → `alembic upgrade head` → 部署代码 → 验证 Schema/来源链 → 再开启人工 DB 模式。
- 回滚：普通 Git revert；有 File Import 来源事实时 Migration 不允许直接 downgrade。

## 12. Review 与 Git

- 起始 `main`：`09ff597f6dc28d06c36017c3c9a8af062fe1e425`
- 分支：`feature/stage8a-unified-manual-ingestion`
- PR：#88
- Change：`ready_for_review`
- 最新 head 必须完成新鲜 CI + 两阶段 Review 后才可 Ready/合并。
- 合并后重新读取 main `AGENTS.md` 并验证 main；之后才可 `done` + archive。
- Stage 8A 闭环前不进入 Stage 8B。

## 13. 中断恢复

稳定导航：仓库 `dingyuwen777/AIMA_UGC`、分支 `feature/stage8a-unified-manual-ingestion`、PR #88、本 Active Change、Migration `20260820_0019`。恢复时重新读取目标分支 `AGENTS.md` → Skill → Change → PR 最新 head/CI；不把开发分支 SHA 当永久最新事实。
