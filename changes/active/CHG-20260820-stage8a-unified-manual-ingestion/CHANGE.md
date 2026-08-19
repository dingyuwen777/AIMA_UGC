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
affected_areas: [ingestion, provenance, postgres, debug-entrypoints, documentation]
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
contracts: [ProviderRequestV1]
data_changes: [processing_import_batches, provider_requests]
---

# Stage 8A：Unified Manual Ingestion Foundation

## 结果

Stage 8A 只建立统一手工入库 Foundation，不进入 Stage 8B/8C，不开发正式前端。

机器事实：

- `processing_import_batches` 是 Excel File Import 的最小业务父事实。
- `ProviderRequestV1/provider_requests` 恰好属于 Collection Scope 或 Import Batch 之一；无父级/双父级关闭失败。
- Excel 不伪造 Collection Run/Scope/Candidate：Input Artifact → Import Batch → import-parent Request/non-billable Attempt → Canonical Source →正式 Content Ingestion。
- TikHub DB 模式继续使用 manual Collection → Request/Attempt → Raw → Candidate-before-Mapper → Canonical → fenced Ingestion。
- `imports_test` / `tikhub_test` 默认 file-only，显式 opt-in 才连接 PostgreSQL。
- Canonical 后没有 Excel/TikHub 私有 Writer；跨来源最终仍由 Content Owner 以业务稳定身份收敛 Current，并保留历史。

## 方案

- A：Excel 制造 Collection Run/Scope——语义错误，不采用。
- B：Provider Request 增加 Import Batch 父级——复用 Attempt/Artifact 与 Content 来源约束，已采用。
- C：新建 FileAttempt/FileSource——复制来源体系、扩大 Content 来源模型，不采用。

## Schema / Migration

Forward Revision `20260820_0019`（down `20260818_0018`）：

```text
processing_import_batches
  id uuid PK
  input_artifact_id uuid NOT NULL FK artifacts
  job_id uuid NULL UNIQUE FK jobs
  status processing|succeeded|failed
  stats jsonb
  error_summary text NULL
  created_at/started_at/finished_at

provider_requests
  scope_id nullable
  import_batch_id nullable FK processing_import_batches
  CHECK exactly one(scope_id, import_batch_id)
  UNIQUE(import_batch_id, request_fingerprint)
  INDEX(import_batch_id, created_at)
```

已有 Attempt 后来源父级/provider/operation 不可修改。存在 File Import Request 时 downgrade 明确拒绝，避免丢失 provenance。

## Excel DB 链

```text
XLSX → Reader/Mapper → Canonical JSONL → filter → deduplicate
→ [显式 DB] Input Artifact → Import Batch → import-parent Request/Attempt
→ Canonical Source → ContentIngestionService → Content Owner → PostgreSQL
```

`imports_test` 默认 `WRITE_TO_DATABASE=False`；支持 `run_all(..., write_to_database=False)` 和 `ingest_database(run_dir=...)`。DB 模式顺序为 `convert → filter → deduplicate → database_ingestion → AI → Excel`；DB 失败时之前文件保留，后续阶段不自动继续。

## TikHub DB 链

五个平台 `run_*()` 均支持：

```python
write_to_database: bool = False
provider_config_id: UUID | None = None
```

DB 模式要求正式 Provider Config/Secret 与本次 `.env` 一致，然后：

```text
manual Collection / Job Fencing
→ Provider Request / billable Attempt
→ ProviderDispatchService
→ 一次 Transport.send
→ 同一响应：本地 Raw 镜像 + 正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 Mapper / Canonical
→ fenced Ingestion → PostgreSQL
```

不会因为写库额外发送第二次 TikHub，也不从 JSONL/Excel 二次回灌。

## TDD / 验证

Red `cab003d9...`：Stage 5B `267 passed / 1 failed`，唯一失败为缺少目标 `write_to_database` 行为。

核心实现检查点 `08f1d646058a0da447b658a257a3f6da61dc0c17` 的 12 个适用 workflow 全部 success。

Stage 5B run `32287548694` / job `96180559519`：

```text
postgres:18.4
268 Unit/Contract passed
20260820_0019 (head)
alembic check: no drift
69 PostgreSQL Collection Integration passed
```

同一 job 还成功完成 Architecture、Table Ownership、Secret、Docs、Contract compatibility、base roundtrip 和 previous-revision roundtrip。

专属 PG18 覆盖：TikHub DB 模式单次 Fake Transport、重复 Excel、Excel→TikHub 跨来源收敛、较新 Observation 推进 Version/Metric、DB 失败后幂等重试。

后续 README/导航/测试说明/Change 产生了新文档提交，所以**最终合并必须以 PR 实际最新 head 的新鲜 CI 为准**，不能拿历史绿灯替代。

## 文档

已同步：Blueprint 02/03/17、Blueprint README、`imports_test/README.md`、`tikhub_test/README.md`、`docs/测试与调试说明.md`。

不修改：

- Blueprint 04：无 HTTP Contract/Route/Client 变化，属于 8B。
- Blueprint 15：无 Analysis Contract/Prompt/taxonomy/persistence 变化。
- Blueprint 13：无 UnifiedDataExcel/Workbook/Exporter Contract 变化。
- Blueprint 06：开发流程/TDD/CI/Git 门禁未变化；Stage 8 子阶段由 17/根导航维护。

## 兼容 / 部署 / 回滚

- 既有 Collection Request 继续使用 `scope_id`，旧数据不重写。
- 调试入口默认 file-only，已有调用兼容。
- 无新增/升级/降级依赖；PostgreSQL 仍为 18 系列。
- 部署：备份 → `alembic upgrade head` → 部署代码 → 验证 Schema/来源链 → 再显式开启 DB 模式。
- 回滚：普通 Git revert；已有 File Import provenance 时 Migration 不允许直接 downgrade。

## Git / Review

- 起始 `main`: `09ff597f6dc28d06c36017c3c9a8af062fe1e425`
- branch: `feature/stage8a-unified-manual-ingestion`
- PR: #88
- Change: `ready_for_review`
- 最新 head 必须新鲜 CI + 两阶段 Review 后才可 Ready/merge。
- merge 后重新读取 main `AGENTS.md` 并验证 main，之后才可 `done` + archive。
- Stage 8A 闭环前不进入 8B。

## 中断恢复

稳定导航：repo `dingyuwen777/AIMA_UGC`，上述 branch，PR #88，本 Active Change，Migration `20260820_0019`。恢复时重新读取目标分支 `AGENTS.md` → Skill → Change → PR 最新 head/CI；不在 Change 中维护动态分支 SHA。
