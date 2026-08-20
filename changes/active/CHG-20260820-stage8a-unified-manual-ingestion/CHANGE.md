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

## 当前结果

Stage 8A 只建立统一手工入库 Foundation，不进入 Stage 8B/8C，不开发正式前端。

- `processing_import_batches` 是 Excel File Import 的最小业务父事实。
- `ProviderRequestV1/provider_requests` 恰好属于 Collection Scope 或 Import Batch 之一。
- Excel 不制造 Collection Run/Scope/Candidate：Input Artifact → Import Batch → import-parent Request/non-billable Attempt → Canonical Source → Content Ingestion。
- TikHub DB 模式走 manual Collection → Request/Attempt → Raw → Candidate-before-Mapper → Canonical → fenced Ingestion。
- `imports_test` / `tikhub_test` 默认 file-only，显式 opt-in 才访问 PostgreSQL。
- Canonical 后没有 Excel/TikHub 私有 Writer；跨来源最终由 Content Owner 收敛 Current 并保留历史。

非目标：HTTP API、正式前端、Analysis 数据库存储、认证权限、预算系统和新基础设施。

## 方案选择

- A：Excel 制造 Collection Run/Scope——污染 Collection 语义，不采用。
- B：Provider Request 增加 Import Batch 父级——复用 Attempt/Artifact 与 Content 来源约束，已采用。
- C：独立 FileAttempt/FileSource——复制来源体系并扩大 Content 来源模型，不采用。

## Migration

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

已有 Attempt 后来源身份不可修改。Stage 8A 扩展 lineage trigger 时继续保留 Stage 7 已有的 `provider_config_id` 不可变语义，并新增 `import_batch_id` 到同一数据库约束；downgrade 也恢复 Stage 7 的原保护范围。存在 File Import Request 时 downgrade 明确拒绝，避免丢失 provenance。

## Excel DB 链

```text
XLSX → Reader/Mapper → Canonical JSONL → filter → deduplicate
→ [显式 DB] Input Artifact → Import Batch → import-parent Request/Attempt
→ Canonical Source → ContentIngestionService → Content Owner → PostgreSQL
```

`imports_test` 默认 `WRITE_TO_DATABASE=False`；支持 `run_all(..., write_to_database=False)` 与 `ingest_database(run_dir=...)`。DB 模式顺序为 `convert → filter → deduplicate → database_ingestion → AI → Excel`；DB 失败时已生成文件保留，后续阶段不自动继续。

Import Batch 创建后，Input Artifact 的 `stored → linked` 也位于统一失败收敛边界内；该步骤失败时 Batch 必须终结为 `failed`，不能永久停留在 `processing`。

## TikHub DB 链

五个平台 `run_*()` 均支持：

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
→ fenced Ingestion → PostgreSQL
```

不会因写库额外发送第二次 TikHub，也不从 JSONL/Excel 二次回灌。

## TDD / PostgreSQL 18 证据

初始 TikHub DB opt-in Red `cab003d9...`：Stage 5B `267 passed / 1 failed`，唯一失败为缺少目标 `write_to_database` 行为。

跨来源/重试验收随后落地，覆盖重复 Excel、Excel→TikHub 同身份 Current 收敛、较新 Observation 推进 Version/Metric、DB 失败后幂等重试以及 TikHub DB 单次 Fake Transport。

Review 中又建立两条缺陷回归：

1. Artifact `stored → linked` 在 Batch 创建后失败：Red 证明 Batch 会遗留 `processing`；Green 将 `Artifact.link()` 纳入统一失败收敛路径，PG18 验证后 Batch 正确变为 `failed` 且不产生 Content。
2. Stage 8A `0019` 替换 Provider Request lineage trigger 时遗漏 Stage 7 已有 `provider_config_id` 保护：
   - Red：Stage 5B run `32317588483` / PostgreSQL Integration `70 passed / 1 failed`，唯一失败 `test_stage8a_keeps_provider_config_immutable_after_attempt`，实际表现为合法 Config A → Config B 改绑没有触发 `IntegrityError`；
   - Green：修正当前未合并 Revision `0019`，升级态保护 `scope_id/import_batch_id/provider_config_id/provider/operation`，downgrade 态恢复 `scope_id/provider_config_id/provider/operation`。

最新 Green 的 Stage 5B run `32317773858` / job `96273610074`：

```text
postgres:18.4
268 Unit/Contract passed
20260820_0019 (head)
alembic check: No new upgrade operations detected.
71 PostgreSQL Collection Integration passed
```

同一 job 成功完成 Architecture、Table Ownership、Secret、Docs、Contract compatibility、base → head 与 previous-revision → head / downgrade-re-upgrade 门禁；日志也明确显示已有 Attempt 后修改 `provider_config_id` 被数据库 trigger 拒绝。

历史候选 head 曾取得 12 个适用 workflow 全部 success；由于 Review 修复和文档范围收口产生了新的分支 head，**最终合并仍必须以 PR 实际最新 head 的新鲜完整 CI 为准**，历史绿灯不能替代最终验证。

## Review 收口

需求符合性与代码质量 Review 已处理以下问题：

- 删除 Stage 8A 首次引入且没有真实历史消费者需要的 `modules.manual_ingestion` 兼容壳，正式依赖统一指向 `modules.ingestion` Owner；
- 修复 Import Batch 在 Artifact link 失败时的僵尸 `processing` 终态；
- 修复 `0019` 对 Stage 7 `provider_config_id` 来源不可变约束的兼容性回归；
- 撤回 Blueprint 02/03/17 的无关压缩式重写，恢复任务开始时仍有效的 Stage 1–7 长期设计，只保留 Stage 8A 必需增量；
- Blueprint 17 保留原有 Stage 8B → 8C → 8D → 8E → 8F 顺序，仅把 8A 从计划态更新为当前机器事实。

## 文档

已同步：Blueprint 02/03/17、Blueprint README、`imports_test/README.md`、`tikhub_test/README.md`、`docs/测试与调试说明.md`。

不修改：Blueprint 04（无 HTTP 变化）、15（无 Analysis 变化）、13（无 Excel Export Contract 变化）、06（开发流程/门禁未变化）。

## 兼容 / 部署 / 回滚

- 既有 Collection Request 继续使用 `scope_id`；旧数据不重写。
- `provider_config_id` 在已有 Attempt 后继续保持 Stage 7 的数据库不可变语义。
- 调试入口默认 file-only；已有调用兼容。
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

稳定导航：repo `dingyuwen777/AIMA_UGC`，上述 branch，PR #88，本 Active Change，Migration `20260820_0019`。恢复时重新读取目标分支 `AGENTS.md` → Skill → Change → PR 最新 head/CI；不维护动态分支 SHA。
