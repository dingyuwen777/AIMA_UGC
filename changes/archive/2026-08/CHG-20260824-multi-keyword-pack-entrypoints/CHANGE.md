---
schema: rvc-change/v1
id: CHG-20260824-multi-keyword-pack-entrypoints
title: Excel 与 TikHub 手工发现统一多词包选择
level: L3
status: done
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
| Browser Mock Acceptance | required | `frontend/e2e/collection-runtime.spec.ts` 覆盖多词包选择并断言 `keyword_pack_ids`；PR #185 最终 CI 通过。 |
| Backend/API/PostgreSQL Integration | required | PR #185 最终 CI 全绿，包含相关 Stage/Integration 验证。 |
| Contract / Generated Client | required | PR #185 最终 CI 全绿，Contract/Generated drift gate 通过。 |
| Real Full-stack Golden Path | required | Stage 8F Full-stack Acceptance run `32675727914` 成功。 |
| Real Provider Probe | not_applicable | 该 Change 未改变 TikHub endpoint/响应映射，无需真实收费请求。 |
| Docs / Governance / Other | required | Change Completion Gate run `32675727870` 成功；相关文档已随实现同步。 |

# Completion Audit

- [x] upstream_re_read：已重新读取当前分支 `AGENTS.md`、Reliable Vibe Coding 规则和本次相关正式事实源，并独立重建完成定义。
- [x] change_coverage：已确认 Excel Import、Manual Discovery、多词包 OR、Batch Supplement 不变、Collection Plan 保持和移除旧 Payload 兼容均进入当前 Change。
- [x] reverse_audit：已从前端入口反查后端 Contract/冻结链路，并从后端能力反查前端入口；Batch Supplement 未被扩展为关键词搜索，Validation Matrix 各层与实际边界一致。
- [x] unresolved_cleared：R1—R5 均为 satisfied；没有范围内未决事项、延期项或无依据的不适用项。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败/回归测试并读取实际失败证据
- [x] 建立并维护 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得目标 Runner 新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

PR #185 最终 HEAD `4986dbc58a5d24ffdcdd7284bc24b6a8e286344c` 的 16 个 PR 工作流全部成功，包括 CI `32675727872`、Stage 8F Full-stack Acceptance `32675727914`、Change Completion Gate `32675727870`，以及 Stage 5/6/7、Local Dev、Windows Compose、Internal V1-A 等永久门禁。

# 文档影响

- `docs/appendix/08_数据入口与统一入库实现.md`：同步 Excel/Manual Discovery 多词包选择与冻结语义。
- `backend/src/aima_ugc/modules/ingestion/README.md`：Excel 导入改为上传时选择并冻结多词包。

# 兼容、部署与回滚

- 无数据库 Schema/Migration 变化，无依赖升级。
- HTTP Excel Import 与 Manual Discovery Contract 为行为变更，前端/generated client 同 PR 同步。
- 按用户明确决定，旧 `relevance` Import Job Payload 不兼容新 Worker；升级前若存在旧版本未终结 Excel Import Job，应先完成或清理。
- 回滚应整体回滚该实现的前后端/Contract，不应只回滚单侧。

# 交付

- 实现分支：`feature/multi-keyword-pack-entrypoints`
- PR：#185 `统一 Excel 与 TikHub 手工发现多词包选择`
- PR 合并时间：2026-08-24T00:17:46Z
- 合并提交：`e26c9eac8827efa42a02206d9fc829590e2db0ee`
- 状态：done，已归档。
