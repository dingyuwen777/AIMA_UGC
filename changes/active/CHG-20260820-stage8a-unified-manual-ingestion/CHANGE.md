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

以下决定继承 Blueprint 17 与用户已批准方案：

- Excel 是第一版主要人工数据入口，TikHub 是辅助发现、补漏和详情/评论补充来源。
- PostgreSQL 是唯一业务事实库；Excel/JSONL/XLSX 调试产物不是业务数据库。
- Provider 差异在 Canonical 前结束；Canonical 后只复用正式 Ingestion 和 Owner Repository。
- 禁止 `ExcelDatabaseWriter`、`TikHubDatabaseWriter`、调试目录私有 Repository 和绕过 Owner 的直接 SQL。
- `imports_test`、`tikhub_test` 永久保留；默认 file-only，数据库模式显式 opt-in。
- 数据库模式只连接开发者已经准备好的 PostgreSQL 18，不自动管理 Docker，不自动运行 Alembic Migration。
- 数据库/Schema 失败必须明确失败；已经生成的调试文件不因 DB 失败被删除。
- Stage 8A 不新增 HTTP API、正式 Vue/Figma 页面、Analysis 数据库存储、认证权限、预算系统或新基础设施。

## 3. 成功标准状态

1. **File Import 不伪造 Collection 来源：已实现。** Excel 使用 Input Artifact → Import Batch → import-parent Request/Attempt；不创建 Collection Run/Scope/Candidate。
2. **两个调试入口默认不要求数据库：已实现。** 默认参数分别为 `WRITE_TO_DATABASE=False` / `write_to_database=False`，数据库装配使用延迟导入/显式分支。
3. **显式 DB 模式复用正式来源链和 Ingestion：已实现。**
4. **DB/Schema 不可用时关闭失败且不自动管理容器/Migration：已实现并有边界测试。**
5. **重复 Excel 与 Excel/TikHub 跨来源只形成一个 Current：已由 PostgreSQL 18 Integration 验证。**
6. **更晚合法 Observation 推进 Current/Version/Metric：已由 PostgreSQL 18 Integration 验证。**
7. **数据库阶段失败后可重试且不制造第二 Current：已由 PostgreSQL 18 Integration 验证。**
8. **Migration/Contract/Unit/PG18/质量门禁：核心实现检查点已取得新鲜成功证据；最终文档 head 仍需再次取得完整 CI 后才允许合并。**

## 4. 来源链方案比较与最终选择

### 方案 A：Excel 制造 Collection Run/Scope

优点：旧 Schema 改动少。

缺点：把本地文件读取伪装成外部 Collection Scope，污染采集 Run、页面统计和审计语义。

**结论：不采用。**

### 方案 B：一般化 Provider Request 父级

做法：新增 `processing_import_batches`；让 `provider_requests` 恰好属于 `scope_id` 或 `import_batch_id` 之一；继续复用 Provider Attempt、Artifact 和 Content 来源约束。

优点：

- 不伪造 Collection；
- 不复制 Attempt/Artifact 体系；
- Content 历史来源约束无需放松；
- 既有 Collection 数据和调用链兼容；
- File/HTTP 两种执行仍共享统一 Request/Attempt 执行事实。

代价：需要 Provider Request Contract/Repository 一般化和 forward Migration。

**结论：采用并已实现。**

### 方案 C：独立 FileAttempt/FileSource 体系

优点：文件执行概念完全独立。

缺点：复制 Attempt/Artifact 概念，并迫使 Content Version/Metric/来源 FK、Contract 和 Repository 扩大为双来源模型，显著增加迁移和维护成本。

**结论：不采用。**

## 5. Schema / Migration 实际结果

Forward Revision：

```text
20260820_0019
Revises: 20260818_0018
```

实际变化：

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

Provider Request 已有 Attempt 后，`scope_id/import_batch_id/provider/operation` 继续受来源不可变 Trigger 保护。

Downgrade 不会静默删除已经存在的 File Import 来源事实：如果 `provider_requests.import_batch_id IS NOT NULL` 的记录仍存在，Revision 明确拒绝 downgrade，并要求先显式迁移/处理这些事实。

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

`run_all(write_to_database=True)` 的真实阶段顺序：

```text
convert
→ filter_keywords
→ deduplicate
→ database_ingestion
→ label_sentiment
→ export_labeled_excel
```

数据库阶段失败时，它之前已经生成的 Canonical/filtered/deduplicated 文件保留；后续 AI/最终 labeled Excel 不会继续自动执行。修复数据库/Schema/输入后，可以在同一 `run_dir` 继续调用需要的单步函数。

## 7. TikHub 调试数据库模式实际执行链

五个平台 `run_*()` 都保留：

```python
write_to_database: bool = False
provider_config_id: UUID | None = None
```

显式数据库模式要求：

- `provider_config_id` 必填；
- Provider Config 存在、启用、`provider=tikhub`；
- 正式 Provider Config 的 Base URL 与本次 `tikhub_test/.env` Base URL 一致；
- 正式 Secret 与本次 `.env` API Key 一致；
- PostgreSQL 已升级到当前 Stage 8A Schema。

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

因此数据库模式不会为了“还要写库”再调用第二次 TikHub，也不会从已经导出的 JSONL/Excel 二次回灌。

## 8. TDD 与调试过程证据

### Red

测试提交 `cab003d9...` 首先要求 TikHub 公共入口具备显式 `write_to_database`，当时 Stage 5B 结果为：

```text
267 passed / 1 failed
```

唯一失败是目标行为尚未实现，而不是旧基线回归。

### Green / 修正

后续实现了 Processing Batch、Provider Request 双父级、Excel 正式 File Import、两个调试入口数据库模式和 TikHub 正式来源桥接；随后依次修正 Ruff 格式/import-order 与 mypy 类型边界，没有降低门禁或绕过测试。

专属 Stage 8A PG18 验收加入后，曾因新测试文件 Ruff format 失败；业务 PG18 断言当时已经通过。只格式化测试文件后重新取得全绿，不修改验收语义。

## 9. PostgreSQL 18 与 CI 新鲜证据

核心实现检查点：

```text
08f1d646058a0da447b658a257a3f6da61dc0c17
```

该 commit 的 12 个适用 workflow 全部 `success`：

- CI — run `32287548675`
- Stage 4 Job Runtime — `32287548667`
- Stage 5A Provider Raw — `32287548738`
- Stage 5B Collection Execution — `32287548694`
- Stage 5C Provider Persistence — `32287548672`
- Stage 5D Provider Dispatch — `32287548677`
- Stage 6 XHS Vertical Slice — `32287548666`
- Stage 7 Provider Config Routing — `32287548700`
- Stage 7 Keyword Packs — `32287548706`
- Stage 7 Scheduler Runtime — `32287548674`
- Stage 7 Plan Occurrence Run Snapshot — `32287548725`
- Stage 1–7 Audit Correctness — `32287548760`

Stage 5B job `96180559519` 的完整日志确认：

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

同一 job 还实际完成：

- Stage 8A 所在 Collection PostgreSQL Integration；
- Architecture Check；
- Table Ownership（含 `processing_import_batches:ingestion`）；
- Secret Scan；
- Docs link check；
- Contract generation/check/compatibility；
- `head → base → head`；
- `head → previous revision → head`。

文档/Change 收口后的最终验证候选 head 为：

```text
d599c275fb510544972b76727c61684c6a54d08f
```

本文件本身随后又产生一个只记录验证锚点的文档 commit，因此**最终合并必须以 PR 实际最新 head 为准重新查询 workflow**，不得直接拿 `08f1d646` 或 `d599c275` 的旧结果冒充最终证据。

## 10. 文档同步

已同步：

- `docs/blueprint/02-采集系统与数据标准化.md`：区分 Collection Candidate 链与 File Import 来源链，删除“所有来源都必须 Candidate”的错误泛化。
- `docs/blueprint/03-数据库与文件存储.md`：同步 `processing_import_batches`、Provider Request 双父级、Input Artifact/Attempt 与 Migration 0019。
- `docs/blueprint/17-Stage8数据入口统一入库与业务前端实施.md`：Stage 8A 目标态更新为当前机器事实，并保留 8B—8F 后续边界。
- `docs/blueprint/README.md`：当前状态更新为 Stage 8A Foundation 已实现、下一最小正式单元为 Stage 8B。
- `backend/.../imports_test/README.md`：同步 `WRITE_TO_DATABASE=False`、`ingest_database()`、真实执行顺序和失败恢复边界。
- `backend/.../tikhub_test/README.md`：同步 `write_to_database/provider_config_id`、Provider Config/Secret 一致性、单次请求双 Raw 和 fenced Ingestion。
- `docs/测试与调试说明.md`：同步两个调试入口、Stage 8A Unit/Contract/PG18 验证方式和成功判据。

检查后不修改：

- Blueprint 04：Stage 8A 没有新增/修改公开 HTTP Contract、FastAPI Route 或生成 Client；HTTP 产品化属于 Stage 8B。
- Blueprint 15：Stage 8A 没有修改 Analysis Prompt、Taxonomy、Analysis Contract 或正式 Analysis 持久化。
- Blueprint 13：Stage 8A 没有改变 `UnifiedDataExcelV1`、Workbook 格式或共享 Exporter Contract；数据库模式只增加显式副作用，TikHub 也不从 Excel 回灌。
- Blueprint 06：开发流程/TDD/CI/Git 规则未改变；Stage 8 的详细子阶段顺序由 Blueprint 17 与根 Blueprint 导航维护。

## 11. 兼容性、依赖、部署与回滚

兼容性：

- 既有 Collection Request 继续使用 `scope_id`；旧数据无需重写。
- 调试入口默认值保持 file-only；已有调用不传新参数时行为不要求数据库。
- Content/Comment 公共业务身份、Canonical Content/Comment Contract 与 Content Owner 公共入口未改变。

依赖：

- 未新增、升级或降级 Python/Node/数据库依赖。
- PostgreSQL 仍为 18 系列；CI 实际使用 18.4。

部署：

```text
停止/避免新 File Import DB 模式
→ 备份并确认数据库
→ 显式 alembic upgrade head
→ 部署兼容代码
→ 验证 Schema / Provider 来源链
→ 才允许人工开启数据库模式
```

回滚：

- 代码使用普通 Git revert；不重写历史。
- Migration downgrade 只在没有 File Import Provider Request 时允许；一旦已有 `import_batch_id` 来源事实，必须先显式迁移/处理，不能直接丢失 provenance。

## 12. Review 与 Git 集成状态

- 起始 `main`：`09ff597f6dc28d06c36017c3c9a8af062fe1e425`
- 分支：`feature/stage8a-unified-manual-ingestion`
- PR：`#88 Stage 8A：统一手工数据入库基础`
- PR 当前仍需在**实际最新 head**取得新鲜 CI，并完成需求符合性/代码质量 Review。
- 在最终 CI 与 Review 完成前，Change 保持 `ready_for_review`，不得标记 `done`，不得归档。
- 合并后必须重新读取 `main` 的 `AGENTS.md` 和合并事实，确认 main 集成状态/CI；只有这一步也成立后，才能把 Change 标记 `done` 并移动到 `changes/archive/2026-08/`。
- Stage 8A 闭环前不进入 Stage 8B。

## 13. 中断恢复检查点

如果对话/推理再次中断，新会话从以下事实恢复，而不是依赖聊天记忆：

```text
repo: dingyuwen777/AIMA_UGC
branch: feature/stage8a-unified-manual-ingestion
PR: #88
Change: changes/active/CHG-20260820-stage8a-unified-manual-ingestion/CHANGE.md
code/migration baseline: 20260820_0019
last fully green core checkpoint: 08f1d646058a0da447b658a257a3f6da61dc0c17
last pre-validation documentation checkpoint: d599c275fb510544972b76727c61684c6a54d08f
```

恢复顺序：先读目标分支 `AGENTS.md` → Skill → 本 Change → PR 最新 head/CI。若最新 head 比上述 checkpoint 更新，必须以 GitHub 最新事实为准重新验证，不能退回旧 commit。
