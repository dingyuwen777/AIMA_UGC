---
schema: rvc-change/v1
id: CHG-20260824-multi-keyword-pack-entrypoints
title: Excel 与 TikHub 手工发现统一多词包选择
level: L3
status: ready_for_review
owner: aima
branch: feature/multi-keyword-pack-entrypoints
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - frontend
  - contracts
affected_paths:
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/import_worker.py
  - backend/src/aima_ugc/bootstrap/collection_http.py
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/ingestion/import_job.py
  - frontend/src/features/import-batches/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
contracts:
  - HTTP OpenAPI
data_changes: []
---

# 目标

统一主动按关键词处理内容的入口：Excel Import、TikHub Manual Discovery、Collection Plan 均从 Keyword Pack 选择一个或多个词包，按所选词包有效关键词并集去重后执行 OR 匹配/搜索；Batch Supplement 保持针对既有 Batch 内容补采，不引入关键词搜索。

# 成功标准

- [x] Excel 上传必须选择 1—20 个启用词包，并冻结所选 pack id/version 与 effective_keywords。
- [x] Excel 过滤继续只检查 Canonical title/text，任一有效关键词命中即可保留。
- [x] TikHub Manual Discovery 改为选择 1—20 个启用词包，不再手工提交自由关键词，并冻结本次 Run 的有效关键词。
- [x] Collection Plan 既有多词包语义保持不变。
- [x] Batch Supplement 不接收词包或关键词。
- [x] OpenAPI/generated client/前端交互与后端 Contract 一致。
- [x] 按用户 2026-08-24 最终决定，不保留旧 `relevance` Import Job Payload 兼容；新 Import Job 只接受 `keyword_selection`。

# 范围

- Excel Import multipart Contract、快照、Worker 校验和前端上传弹窗。
- TikHub Manual Discovery Contract、后端词包解析和前端创建抽屉。
- Import Job Payload 从旧 `relevance` 快照切换为 `keyword_selection`，不提供旧 Payload 兼容路径。
- 受影响测试、OpenAPI/generated client、数据入口文档。

# 非目标

- 不改变 Content 去重、Current/Version/Metric、AI Semantic Relevance。
- 不改变 Batch Supplement 的详情/评论补采语义。
- 不改变全局 Relevance 配置或周期 Collection Plan 的既有模型。
- 不新增数据库表或 Migration。

# 必须保持不变

- Content 稳定身份 `(platform, external_content_id)`。
- Rule Relevance 仍为 title/text 任意关键词 OR 匹配。
- PostgreSQL Job Runtime、Artifact、来源追溯与事务边界。
- generated client 必须由 OpenAPI 生成，不手工维护第二套类型。

# 关键决策

1. 不把共享 `RelevanceSnapshotV1` 直接改成多词包，避免扩大 Collection 全局 Relevance 影响面；Excel 使用独立版本化 Import Keyword Pack Snapshot。
2. Manual Discovery 的公共输入改为 `keyword_pack_ids`；后端在创建 Run 时读取并冻结有效关键词，Provider 执行仍消费已有 Run keywords，不改变下游采集执行器。
3. 多词包语义为并集去重 + OR；同一规范化匹配身份只保留一次。
4. 用户于 2026-08-24 明确批准不保留旧 `relevance` Payload 兼容，因此 `ImportJobPayload` 只保留必填 `keyword_selection`；部署时若仍存在由旧版本创建且尚未执行的 Excel Import Job，不保证新 Worker 可继续执行，部署前应清空/完成这类旧任务。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Excel 上传可多选词包并按并集 OR 过滤 | user:2026-08-24-current-request | satisfied | `ImportUploadDialog.vue` + `PostgresImportHttpService._read_import_keyword_selection()` + PostgreSQL ingestion tests |
| R2 | TikHub Manual Discovery 从词包选择且支持多选 | user:2026-08-24-current-request | satisfied | `TikHubSupplementDrawer.vue` + `CollectionRunCreateRequest.keyword_pack_ids` + `PostgresCollectionHttpService._build_scopes()` |
| R3 | Batch Supplement 保持不按关键词搜索 | user:2026-08-24-current-request | satisfied | Contract 拒绝 Batch Supplement 携带 Keyword Pack；Browser/API 回归覆盖 |
| R4 | Collection Plan 既有多词包语义保持 | backend/src/aima_ugc/modules/collection/scheduled_scopes.py | satisfied | Manual Discovery 复用 `build_scheduled_scope_snapshot()`，未修改 Plan Contract/持久化模型 |
| R5 | 不保留旧 relevance Import Job Payload 兼容 | user:2026-08-24-current-request | satisfied | `ImportJobPayload` 仅保留必填 `keyword_selection`；Worker 删除旧 Relevance 分支，Integration 断言持久 Payload 不含 `relevance` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `frontend/e2e/collection-runtime.spec.ts` 已改为多词包选择并断言 `keyword_pack_ids`；最终 PR CI 复验 |
| Backend/API/PostgreSQL Integration | required | Runner 已验证 Stage 8B/8E 与 ingestion；移除兼容后的最终 PR CI Stage 3A 复验 |
| Contract / Generated Client | required | Runner 成功执行 Pydantic → OpenAPI → Orval → drift check；最终 CI 再检查 |
| Real Full-stack Golden Path | required | `frontend/e2e-fullstack/excel-import.spec.ts` 已改为真实创建并选择词包；Stage 8F PR CI 复验 |
| Real Provider Probe | not_applicable | 本次不改变 TikHub endpoint/响应映射，无需真实收费请求 |
| Docs / Governance / Other | required | Appendix 08、Ingestion README 已同步；Completion Gate/永久 CI 作为最终门禁 |

# Completion Audit

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [x] unresolved_cleared

审计结论：已重新读取当前分支 `AGENTS.md`、Reliable Vibe Coding 规则和相关实现；用户最终决定已纳入 R5。前端上传/Manual Discovery 到后端 Contract、Job/Run 冻结链路双向一致；Batch Supplement 没有被扩展为关键词搜索；没有发现仍需用户决策的范围内事项。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败/回归测试并读取实际失败证据
- [x] 建立并维护 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得目标 Runner 新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 已执行证据

- Dev Multi Keyword Pack Runner：Contract 生成、Orval 生成、Ruff、mypy（235 source files）、前端 lint/typecheck、Alembic upgrade、目标 API/PostgreSQL ingestion、前端 Vitest 均执行成功后提交正式实现。
- 移除旧 Payload 兼容后的第一次 Stage 3A Integration 正确暴露一个过期测试断言：业务 Job 已 succeeded，但测试仍访问已删除的 `payload.relevance`，结果 `1 failed, 4 passed`；随后将断言改为确认 `relevance` 不存在。最终永久 CI 必须在当前 HEAD 重新通过后方可合并。
- Completion Gate 的 RVC 自测 14/14 通过；前两次 Gate 分别发现 Change frontmatter 缺 `depends_on`、`data_changes` 类型不合法，均按机器门禁修正；等待当前 HEAD 复验。

## 最终门禁

- PR 永久 CI 全绿，包括 Stage 3A Database、Stage 8F Full-stack Acceptance、Stage 7 Keyword Packs/Plan/Scheduler/Provider、Stage 6、Local Dev、Windows Compose、Internal V1-A、Change Completion Gate。
- 合并后重新检查 `main` 的永久 CI，不以 PR 结果替代 main 结果。

# 文档影响

- `docs/appendix/08_数据入口与统一入库实现.md`：同步 Excel/Manual Discovery 多词包选择与冻结语义。
- `backend/src/aima_ugc/modules/ingestion/README.md`：删除 Excel 自动读取全局单词包的旧说明，改为上传时选择并冻结多词包。

# 兼容、部署与回滚

- 无数据库 Schema/Migration 变化，无依赖升级。
- HTTP Excel Import 与 Manual Discovery Contract 为行为变更，前端/generated client 同 PR 同步。
- 按用户明确决定，旧 `relevance` Import Job Payload 不兼容新 Worker；部署前若存在旧版本创建且未终结的 Excel Import Job，应先完成或清理，避免升级后由新 Worker 解析旧 Payload。
- 回滚应整体回滚本 PR 的前后端/Contract，不应只回滚单侧。

# 交付

- 分支：`feature/multi-keyword-pack-entrypoints`
- PR：#185 `统一 Excel 与 TikHub 手工发现多词包选择`
- 合并：待最终永久 CI 全绿后执行正常 PR 合并。
