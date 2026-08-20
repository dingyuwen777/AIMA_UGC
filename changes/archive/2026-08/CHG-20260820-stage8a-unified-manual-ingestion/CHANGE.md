---
schema: rvc-change/v1
id: CHG-20260820-stage8a-unified-manual-ingestion
title: Stage 8A Unified Manual Ingestion Foundation
level: L3
status: done
owner: AI coding agent
branch: feature/stage8a-unified-manual-ingestion
created: 2026-08-20
updated: 2026-08-20
depends_on: []
affected_areas: [ingestion, provenance, postgres, debug-entrypoints, documentation]
affected_paths:
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

# 完成结论

Stage 8A 已完成实现、TDD、PostgreSQL 18 验证、两阶段 Review、实现 PR 合并和合并后完整门禁验证；本 Change 已进入 `done` 并归档。下一正式最小单元只能是 Stage 8B，本 Change 未开始 Stage 8B/8C 或正式前端。

```text
开始 main:
09ff597f6dc28d06c36017c3c9a8af062fe1e425

实现分支:
feature/stage8a-unified-manual-ingestion

实现最终 head:
5fede03a6b442b0a5f178fe218a2238ad7c13925

实现 PR:
#88 Stage 8A：统一手工数据入库基础

PR #88 merge / 合并后 main:
f933f9c193d9416169f8ac796248611cefcffd1d

归档 PR:
#89 归档 Stage 8A Unified Manual Ingestion Change
```

PR #88 使用固定 `expected_head_sha=5fede03a...` 正常 merge，未 force push、未绕过 Branch Protection、未降低 CI/测试门禁。

# 方案选择

来源链比较后的最终选择：

- A：Excel 制造 Collection Run/Scope —— 会污染 Collection 业务语义，不采用；
- B：最小一般化 Provider Request，使其恰好属于 Collection Scope 或 Processing / Import Batch —— **采用**；
- C：新增独立 FileAttempt/FileSource 体系 —— 会复制 Attempt/Artifact/Content 来源模型，不采用。

因此 File Import 与 HTTP Provider 继续共享 Request/Attempt/Artifact/Content 来源约束，但不强迫 Excel 伪装成 Collection Candidate。

# Processing / Import Batch 机器结构

Forward Migration `20260820_0019`（down `20260818_0018`）建立：

```text
processing_import_batches
  id uuid primary key
  input_artifact_id uuid not null references artifacts
  job_id uuid null unique references jobs
  status processing | succeeded | failed
  stats jsonb
  error_summary text null
  created_at timestamptz
  started_at timestamptz null
  finished_at timestamptz null
```

它只保存一次文件处理/导入的父事实，不复制 `contents/comments` 业务字段。Owner 为 `ingestion`。

# Provider Request 双父级

`ProviderRequestV1/provider_requests` 最终保持恰好一个来源父级：

```text
Collection Request:
run_id + scope_id
import_batch_id = null

File Import Request:
import_batch_id
run_id = null
scope_id = null
```

数据库增加：

```text
scope_id nullable FK collection_scopes
import_batch_id nullable FK processing_import_batches
CHECK exactly_one(scope_id, import_batch_id)
UNIQUE(scope_id, request_fingerprint)
UNIQUE(import_batch_id, request_fingerprint)
INDEX(import_batch_id, created_at)
```

已有 Attempt 后来源身份不可修改。Stage 8A `0019` 的 lineage trigger 最终保护：

```text
scope_id
import_batch_id
provider_config_id
provider
operation
```

其 downgrade 恢复 Stage 7 已有：

```text
scope_id
provider_config_id
provider
operation
```

存在 File Import Request 时 `0019` downgrade 明确拒绝，避免删除合法 provenance。

# Excel 正式数据库来源链

文件处理继续复用 P1 正式实现：

```text
XLSX
→ Excel Reader
→ Excel Mapper
→ CanonicalContentV1
→ 关键词相关性清洗
→ 稳定身份批次去重
→ UnifiedContentRecordV1 JSONL
```

显式数据库阶段：

```text
原始 XLSX
→ ArtifactService(kind=file-import.raw)
→ ProcessingImportBatch
→ import-parent Provider Request
→ non-billable Provider Attempt
→ Attempt.raw_artifact_id = Input Artifact
→ 读取 UnifiedContentRecordV1.content
→ 绑定真实 Request / Attempt / Artifact 到 Canonical Source
→ ContentIngestionService
→ PostgresCompleteContentRepository
→ PostgresContentRepository
→ PostgreSQL
```

Excel 不创建虚假的 Collection Run/Scope/Candidate，不伪造 `provider_attempt_id/raw_artifact_id`，也没有 Excel 私有 Content Repository/Writer。

Import Batch 建立后，Input Artifact 的 `stored → linked` 也纳入统一失败收敛边界；该步骤失败时 Batch 终结为 `failed`，不会遗留 `processing` 僵尸批次。

# imports_test 两种模式

默认：

```python
WRITE_TO_DATABASE = False
run_all(write_to_database=False)
```

- 不装配数据库 Runtime；
- 不要求 PostgreSQL；
- 原 Canonical / 过滤 / 去重 / Analysis / Excel / run summary 文件行为保持；
- 不管理 Docker，不运行 Alembic。

显式：

```python
run_all(write_to_database=True)
# 或对同一 run 显式执行
ingest_database(run_dir=...)
```

实际顺序：

```text
convert → filter → deduplicate → database_ingestion → AI → Excel
```

DB/Schema 不可用时明确失败；已生成文件不删除，失败不静默降级为 file-only success。

# tikhub_test 两种模式

五个平台公共入口默认：

```python
write_to_database = False
provider_config_id = None
```

保持原本本地 Raw / Canonical / Excel / state / run summary，不装配数据库 Runtime。

显式数据库模式：

```python
write_to_database = True
provider_config_id = <正式 provider_configs.id>
```

先验证 PostgreSQL 18 / Stage 8A Schema，以及正式 Provider Config 的启用状态、`provider=tikhub`、Base URL 和 Secret 与本次调试配置一致。随后：

```text
manual Collection Run / Job Fencing
→ Provider Request / billable Attempt
→ ProviderDispatchService
→ 一次 Transport.send
→ 同一响应同时：本地调试 Raw 镜像 + 正式 Raw Artifact
→ Candidate-before-Mapper
→ 正式 TikHub Mapper / Canonical
→ 本地 Canonical / Excel 保留
→ fenced Content Ingestion
→ PostgreSQL
```

不会因为写库再发送第二次 TikHub 请求，也不从已导出的 JSONL/Excel 建平行回灌 Writer。

# 去重、历史与失败重试

最终业务身份继续由 Content Owner 约束：

```text
Content: (platform, external_content_id)
Comment: (content_id, external_comment_id)
```

真实 PostgreSQL 18 验收覆盖：

- 同一个 Excel 重复执行：一个 Current Content；
- Excel 后 TikHub 观察同身份：仍一个 Current；
- 较新合法 TikHub Observation：更新 Current，并形成新 Version/Metric；
- 不同来源 Attempt/Artifact/Version/Metric 历史保留；
- DB 阶段中途失败后重新执行：不产生第二条业务 Current；
- Artifact link 失败：Batch 记 `failed`，不产生 Content，可后续重试。

# TDD / Review Red → Green

## TikHub DB opt-in

初始 Red `cab003d9...`：Stage 5B `267 passed / 1 failed`，唯一失败是公共入口尚无 `write_to_database` 行为；随后接入正式 Collection/Provider/Raw/Candidate/Ingestion 链转 Green。

## Artifact link 失败终态

Review 新增 PG18 回归，先证明 `ArtifactService.link()` 失败会遗留 `processing` Batch，再把该步骤纳入统一失败收敛路径。Green 后 Batch 为 `failed` 且 Content 数为 0。

## provider_config_id 来源冻结

Review 发现 Stage 8A `0019` 替换 Stage 7 lineage trigger 时漏掉 `provider_config_id`：

- Red：Stage 5B run `32317588483`，PostgreSQL Integration `70 passed / 1 failed`；唯一失败 `test_stage8a_keeps_provider_config_immutable_after_attempt`，表现为合法 Config A → Config B 改绑没有触发 `IntegrityError`；
- Green：修复当前尚未发布的 `0019` trigger，恢复 Stage 7 不可变语义并加入 `import_batch_id`；
- Green run `32317773858`：268 Unit/Contract、71 PostgreSQL Integration 通过，Migration/质量门禁通过。

## 代码质量 Review

- 删除 Stage 8A 首次引入、没有真实历史消费者需要的 `modules.manual_ingestion` 兼容壳；
- `RawArtifactService` 明确保留 Collection-only `RawEnvelopeV1` 边界，File Import 不伪造 HTTP RawEnvelope；
- 撤回 Blueprint 02/03/17 的无关压缩式重写，恢复仍有效的 Stage 1–7 长期设计，只保留 Stage 8A 必需增量；
- Blueprint 17 原有 Stage 8B → 8C → 8D → 8E → 8F 顺序保持不变。

# 实现 PR 最终验证

PR #88 最终 head：

```text
5fede03a6b442b0a5f178fe218a2238ad7c13925
```

该 head 取得 **12 / 12** 适用 PR workflows success：

- CI；
- Stage 4 Job Runtime；
- Stage 5A Provider Raw；
- Stage 5B Collection Execution；
- Stage 5C Provider Persistence；
- Stage 5D Provider Dispatch；
- Stage 6 XHS Vertical Slice；
- Stage 7 Provider Config Routing；
- Stage 7 Keyword Packs；
- Stage 7 Scheduler Runtime；
- Stage 7 Plan Occurrence Run Snapshot；
- Stage 1-7 Audit Correctness。

最终主 CI run `32318006788` 成功，包含锁定环境、生成 Contract/Client、Ruff、mypy、381 Unit、38 Contract、3 API、Architecture、Table Ownership、Secret、Docs、wheel、Frontend lint/typecheck/test/build、Windows bootstrap 和 PostgreSQL 阶段。

最终 Stage 5B 使用 PostgreSQL 18.4，包含最新 Stage 8A 来源/幂等回归，并完成 `alembic check`、base→head、previous→head、downgrade/re-upgrade。

# 合并后 main 验证

PR #88 已正常 merge：

```text
main = f933f9c193d9416169f8ac796248611cefcffd1d
```

当前 GitHub 连接器的 `fetch_commit_workflow_runs` 只暴露 pull-request-triggered runs，因此不能据此读取/声称该 merge commit 的 push workflow 数量。本 Change 使用两层可验证证据：

1. 最终成功 PR merge-ref `3e5d790dee5700a0dffa5403d272e3028dc28790` 与实际 main merge commit `f933f9c1...` 具有相同父提交，且 **tree SHA 均为 `ed6f7c1790a83b63d56a074cd069485843e6b611`**；因此 PR 最终 12/12 验证覆盖了当前 main 的精确仓库树。
2. 按仓库 P1 归档 PR #72 的既有模式，从 `main@f933f9c1...` 创建 `chore/archive-stage8a-unified-manual-ingestion`，临时加入 Migration / Collection / Change 三个无业务语义 `.txt` marker。post-merge 验证候选：

```text
fc57f5d748d796d5f051f8ee28de604f8a9fe75e
```

该候选实际触发并取得 **12 / 12 success**，包括 CI、Stage1–7 Audit、Stage4、Stage5A/5B/5C/5D、Stage6、Stage7 Keyword/Plan/Provider/Scheduler。Scheduler PostgreSQL 的 upgrade、previous revision、base roundtrip 也全部成功。

三个 marker 在归档前已全部删除，不进入最终 main。

# 文档同步

Stage 8A 实现同步了真正受影响的 Blueprint/README/测试说明；Review 期间已撤回无关大规模文档压缩。

最终未改：

- Blueprint 04：Stage 8A 没有 HTTP Contract；
- Blueprint 15：没有 Analysis Contract/Prompt/taxonomy 变化；
- Blueprint 13：没有 Unified Excel Export Contract 变化；
- Blueprint 06：开发流程/门禁未变化。

归档 PR 只做 Change 生命周期和必要的“Stage 8A 已闭环、下一正式单元为 Stage 8B”导航同步，不修改业务代码、Contract、Migration、依赖或测试行为。

# 真实 Provider Probe

本 Stage 没有发真实 TikHub 付费请求。TikHub DB 自动化使用现有 Fake Transport / Fixture；这足以验证单次请求、正式 Request/Attempt/Raw/Candidate/Ingestion 和 PostgreSQL 18 来源链，不用付费请求替代可重复自动化，也没有泄露 Secret。

# 兼容 / 部署 / 回滚

- 既有 Collection Request 继续使用 `scope_id`；旧历史不重写；
- `provider_config_id` 在已有 Attempt 后继续保持 Stage 7 数据库不可变语义；
- `imports_test` / `tikhub_test` 默认 file-only 兼容；
- 无新增/升级/降级依赖；
- PostgreSQL 仍为 18 系列；
- 部署：备份 → 显式 `alembic upgrade head` → 部署代码 → 验证 Schema/来源链 → 再显式开启 DB 模式；
- 回滚：普通 Git revert；已有 File Import provenance 时 `0019` 不允许直接 downgrade，必须先显式处理来源数据；
- 不自动管理 Docker、不自动 Migration。

# 最终验收

- [x] Processing / Import Batch 最小父事实落地；
- [x] File Import 合法 Artifact/Request/Attempt 来源链；
- [x] Excel 正式数据库摄取复用 Content Ingestion / Content Owner；
- [x] imports_test 默认 file-only + 可选 DB；
- [x] tikhub_test 默认 file-only + 可选 DB；
- [x] 不存在 Excel/TikHub 平行 Content Writer；
- [x] PostgreSQL 18 跨来源去重、历史与失败重试验证；
- [x] Migration 0019 forward / downgrade / roundtrip / alembic check；
- [x] Provider Config 来源不可变兼容性回归修复；
- [x] Artifact link 失败终态回归修复；
- [x] 两阶段 Review 完成，无未解决严重/重要问题；
- [x] PR #88 最终 head 12/12 success；
- [x] PR #88 正常合入 main；
- [x] 合并后 main 精确 tree-equivalence 已确认；
- [x] 从合并后 main 建立的 post-merge 候选 12/12 success；
- [x] 临时验证 marker 已删除；
- [x] Change 更新为 `done` 并进入归档流程；
- [x] Stage 8B 未开始。

本归档 PR 最终只保留 Change 生命周期与必要阶段导航同步；其适用 CI/Review 成功后再正常合入 main。
