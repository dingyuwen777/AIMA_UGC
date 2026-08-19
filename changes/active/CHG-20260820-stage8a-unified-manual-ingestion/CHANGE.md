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

Stage 8A 当前已经形成以下机器事实：

1. 新增 `processing_import_batches`，作为 Excel File Import 的最小业务父事实；它不复制 Content/Comment 业务字段。
2. `ProviderRequestV1/provider_requests` 从“只能属于 Collection Scope”一般化为“恰好属于 Collection Scope 或 Processing Import Batch 之一”。
3. 既有 Collection Request 仍通过 `scope_id` 工作；File Import 通过 `import_batch_id` 工作。无父级和双父级都关闭失败。
4. Excel File Import **不制造** Collection Run/Scope/Candidate。它使用真实 Input Artifact + Processing Import Batch + import-parent Provider Request/non-billable Attempt，并把该 Input Artifact 绑定为 Attempt 的真实来源证据。
5. TikHub 数据库模式仍保持正式 Collection 语义：manual Run/keyword Scope → Provider Request/Attempt → Raw → Candidate-before-Mapper → Canonical → fenced Ingestion。
6. `imports_test`、`tikhub_test` 默认仍为 file-only；只有显式开启数据库模式才装配 PostgreSQL Runtime。
7. Canonical 之后不新增 Excel/TikHub 私有 Writer，统一进入现有 Content Ingestion / Content Owner Repository。
8. PostgreSQL 继续以 `(platform, external_content_id)` 和评论稳定身份作为跨批次、跨来源最终业务收敛边界，并保留 Version/Metric/来源历史。

## 2. 已确认的上游决策与不变项

- Excel 是第一版主要人工数据入口，TikHub 是辅助发现、补漏和详情/评论补充来源。
- PostgreSQL 是唯一业务事实库；Excel/JSONL/XLSX 调试产物不是业务数据库。
- Provider 差异在 Canonical 前结束；Canonical 后只复用正式 Ingestion 和 Owner Repository。
- 禁止 `ExcelDatabaseWriter`、`TikHubDatabaseWriter`、调试目录私有 Repository 和绕过 Owner 的直接 SQL。
- `imports_test`、`tikhub_test` 永久保留；默认 file-only，数据库模式显式 opt-in。
- 数据库模式只连接开发者已经准备好的 PostgreSQL 18，不自动管理 Docker，不自动运行 Alembic Migration。
- 数据库/Schema 失败必须明确失败；已经生成的调试文件不因 DB 失败被删除。
- Stage 8A 不新增 HTTP API、正式 Vue/Figma 页面、Analysis 数据库存储、认证权限、预算系统或新基础设施。

## 3. 成功标准状态

1. File Import 不伪造 Collection 来源：已实现。
2. 两个调试入口默认不要求数据库：已实现。
3. 显式 DB 模式复用正式来源链和 Ingestion：已实现。
4. DB/Schema 不可用时关闭失败且不自动管理容器/Migration：已实现并有边界测试。
5. 重复 Excel 与 Excel/TikHub 跨来源只形成一个 Current：已由 PostgreSQL 18 Integration 验证。
6. 更晚合法 Observation 推进 Current/Version/Metric：已由 PostgreSQL 18 Integration 验证。
7. 数据库阶段失败后可重试且不制造第二 Current：已由 PostgreSQL 18 Integration 验证。
8. Migration/Contract/Unit/PG18/质量门禁：核心实现检查点已取得新鲜成功证据；最终合并仍必须以 PR 实际最新 head 的 CI 为准。

## 4. 来源链方案比较与最终选择

### 方案 A：Excel 制造 Collection Run/Scope

旧 Schema 改动少，但会把本地文件读取伪装成外部 Collection Scope，污染采集 Run、页面统计和审计语义。**不采用。**

### 方案 B：一般化 Provider Request 父级

新增 `processing_import_batches`；让 `provider_requests` 恰好属于 `scope_id` 或 `import_batch_id` 之一；继续复用 Provider Attempt、Artifact 和 Content 来源约束。

这样既不伪造 Collection，也不复制 Attempt/Artifact 体系；既有 Collection 数据兼容，File/HTTP 两种执行仍共享统一 Request/Attempt 执行事实。代价是 Provider Request Contract/Repository 一般化和 forward Migration。**已采用并实现。**

### 方案 C：独立 FileAttempt/FileSource 体系

文件语义独立，但会复制 Attempt/Artifact 概念，并迫使 Content Version/Metric/来源 FK、Contract 和 Repository 扩大为双来源模型。**不采用。**

## 5. Schema / Migration 实际结果

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
```

`provider_requests`：

```text
scope_id        → nullable
import_batch_id → nullable FK processing_import_batches(id)
CHECK exactly one(scope_id, import_batch_id)
UNIQUE(import_batch_id, request_fingerprint)
INDEX(import_batch_id, created_at)
```

Provider Request 已有 Attempt 后，`scope_id/import_batch_id/provider/operation` 继续受来源不可变 Trigger 保护。若已经存在 File Import Provider Request，Migration downgrade 明确拒绝，防止静默丢失 provenance。

## 6. Excel File Import 实际执行链

文件处理仍复用 P1 生产实现：

```text
XLSX
→ Excel Reader / Mapper
→ Canonical JSONL
→ keyword filter
→ stable identity deduplicate
→ UnifiedContentRecordV1 JSONL
```

显式数据库阶段：

```text
原始 XLSX
→ ArtifactService：Input Artifact
→ Processing Import Batch
→ import-parent Provider Request
→ non-billable Provider Attempt
→ Attempt.raw_artifact_id = Input Artifact
→ 读取 deduplicated JSONL 的 UnifiedContentRecordV1.content
→ 绑定真实 Request / Attempt / Artifact 到 Canonical Source
→ ContentIngestionService
→ PostgresCompleteContentRepository / PostgresContentRepository
→ PostgreSQL
```

`imports_test` 当前 API：

```python
WRITE_TO_DATABASE = False
run_all(..., write_to_database=False)
ingest_database(run_dir=...)
```

`run_all(write_to_database=True)` 的真实阶段顺序为：`convert → filter_keywords → deduplicate → database_ingestion → label_sentiment → export_labeled_excel`。数据库阶段失败时，它之前已经生成的文件保留；后续 AI/最终 labeled Excel 不会继续自动执行。

## 7. TikHub 调试数据库模式实际执行链

五个平台 `run_*()` 都保留：

```python
write_to_database: bool = False
provider_config_id: UUID | None = None
```

显式数据库模式要求稳定 `provider_config_id`，并校验 Provider Config 存在/启用/provider=tikhub、Base URL 与本次 `.env` 一致、正式 Secret 与本次 `.env` API Key 一致，以及 Stage 8A Schema 已部署。

执行链：

```text
manual Collection Run / keyword Scope / Job Fencing
→ formal Provider Request / billable Attempt
→ ProviderDispatchService
→ _MirroringTransport 只执行一次真实 Transport.send
→ 同一个响应写本地 tikhub_test Raw 镜像
→ 同一个响应进入 RawArtifactService，形成正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 TikHub Mapper / Canonical
→ 本地 Canonical / XLSX 继续保留
→ PostgresFencedCollectionIngestionWriter
→ Content Owner / PostgreSQL
```

数据库模式不会因为写库再发第二次 TikHub，也不会从已经导出的 JSONL/Excel 二次回灌。

## 8. TDD 与调试过程证据

Red 提交 `cab003d9...` 首先要求 TikHub 公共入口具备显式 `write_to_database`，当时 Stage 5B 为 `267 passed / 1 failed`，唯一失败是目标行为尚未实现。

Green 后实现 Processing Batch、Provider Request 双父级、Excel 正式 File Import、两个调试入口数据库模式和 TikHub 正式来源桥接；后续只按 CI 证据修正 Ruff 格式/import-order 与 mypy 类型边界，没有降低门禁。专属 PG18 验收加入后也曾因新测试文件 Ruff format 失败；业务 PG18 断言已成功，只格式化测试文件后重新取得全绿，未修改验收语义。

## 9. PostgreSQL 18 与 CI 证据

核心实现检查点 `08f1d646058a0da447b658a257a3f6da61dc0c17` 的 12 个适用 workflow 全部 success，包括 CI、Stage4、Stage5A—5D、Stage6、Stage7 Provider/Keyword/Scheduler/Snapshot 和 Stage1–7 Audit。

Stage 5B workflow run `32287548694`、job `96180559519` 完整日志确认：

```text
postgres:18.4
uv run pytest tests/unit/collection tests/contracts/test_provider_v1.py -q
→ 268 passed in 4.85s

uv run alembic upgrade head
uv run alembic current
→ 20260820_0019 (head)
uv run alembic check
→ No new upgrade operations detected.

uv run pytest tests/integration/collection -q
→ 69 passed in 11.94s
```

同一 job 还成功完成 Architecture、Table Ownership（含 `processing_import_batches:ingestion`）、Secret、Docs、Contract generation/compatibility、`head → base → head` 与 `head → previous revision → head`。

README、导航、测试说明和本 Change 收口后产生了新的文档提交，所以最终合并必须再读取 PR **实际最新 head** 的完整适用 CI；不能用上述历史检查点替代最终证据。

## 10. 文档同步

已同步：

- Blueprint 02：区分 Collection Candidate 链与 File Import 来源链。
- Blueprint 03：同步 `processing_import_batches`、Provider Request 双父级、Input Artifact/Attempt 与 Migration 0019。
- Blueprint 17：Stage 8A 目标态更新为机器事实，并保留 8B—8F 后续边界。
- Blueprint README：当前状态改为 Stage 8A Foundation 已实现，下一最小正式单元为 8B。
- `imports_test/README.md`：同步数据库开关、`ingest_database()`、真实顺序和失败边界。
- `tikhub_test/README.md`：同步 `provider_config_id`、配置/Secret 一致性、单次请求双 Raw 和 fenced Ingestion。
- `docs/测试与调试说明.md`：同步两个调试入口和 Stage 8A Unit/Contract/PG18 验收。

检查后不修改：

- Blueprint 04：没有新增/修改公开 HTTP Contract、FastAPI Route 或生成 Client；属于 Stage 8B。
- Blueprint 15：没有修改 Analysis Prompt、Taxonomy、Contract 或正式持久化。
- Blueprint 13：没有改变 `UnifiedDataExcelV1`、Workbook 格式或共享 Exporter Contract。
- Blueprint 06：开发流程/TDD/CI/Git 规则未改变；Stage 8 子阶段由 Blueprint 17 与根导航维护。

## 11. 兼容性、依赖、部署与回滚

兼容性：既有 Collection Request 继续使用 `scope_id`；旧数据无需重写。调试入口默认值仍 file-only；Content/Comment 身份、Canonical Content/Comment Contract 和 Content Owner 公共入口未改变。

依赖：未新增、升级或降级 Python/Node/数据库依赖；PostgreSQL 仍为 18 系列，CI 实际使用 18.4。

部署：停止/避免新 File Import DB 模式 → 备份并确认数据库 → 显式 `alembic upgrade head` → 部署兼容代码 → 验证 Schema/来源链 → 再允许人工开启数据库模式。

回滚：代码用普通 Git revert；Migration 只有在没有 File Import Provider Request 时才能 downgrade。一旦已有 `import_batch_id` 来源事实，必须先显式迁移/处理，不能直接丢失 provenance。

## 12. Review 与 Git 集成状态

- 起始 `main`：`09ff597f6dc28d06c36017c3c9a8af062fe1e425`
- 分支：`feature/stage8a-unified-manual-ingestion`
- PR：`#88 Stage 8A：统一手工数据入库基础`
- 当前 Change 状态：`ready_for_review`
- PR 必须在实际最新 head 取得新鲜 CI，并完成需求符合性/代码质量 Review后才可转 Ready/合并。
- 合并后必须重新读取 `main` 的 `AGENTS.md` 和合并事实，并验证 main 集成状态；只有此后才能将 Change 置为 `done` 并归档。
- Stage 8A 闭环前不进入 Stage 8B。

## 13. 中断恢复

稳定导航：仓库 `dingyuwen777/AIMA_UGC`，分支 `feature/stage8a-unified-manual-ingestion`，PR #88，本 Active Change，Migration baseline `20260820_0019`。

恢复时固定重新读取目标分支 `AGENTS.md` → Skill → 本 Change → PR 最新 head/CI；不把任何开发分支 SHA 当永久最新事实。
