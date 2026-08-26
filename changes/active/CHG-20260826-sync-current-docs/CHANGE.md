---
schema: rvc-change/v1
id: CHG-20260826-sync-current-docs
title: 同步当前架构与数据入口文档事实
level: L2
status: ready_for_review
owner: dingyuwen777
branch: docs/sync-current-docs
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - documentation
  - architecture
  - ingestion
  - analysis
  - operations
affected_paths:
  - docs/blueprint/01_总体架构与技术选型.md
  - docs/blueprint/02_采集系统与数据标准化.md
  - docs/appendix/08_数据入口与统一入库实现.md
  - backend/src/aima_ugc/modules/system/README.md
  - backend/src/aima_ugc/modules/ingestion/README.md
  - docs/01_代码结构与修改导航.md
  - docs/appendix/01_PostgreSQL查询与调试实战.md
  - frontend/README.md
contracts: []
data_changes: []
---

# 目标

基于本轮 Docs `full` 文档审计已经确认的机器事实，修复核心架构、Excel Import Rule Relevance、人工相关性复核导航和 Full-stack Workflow 路径的文档漂移，使当前技术文档重新与 `main` 真实实现一致。

本 Change 只同步文档，不通过修改文档把已发现的代码问题合法化，也不扩大到与审计结论无关的 Markdown。

# 成功标准

- [x] `docs/blueprint/01_总体架构与技术选型.md` 正确描述 Internal V1-A 已实现的 Docker/Compose/Windows storage-only override，并继续明确完整 Production Go-Live 尚未闭环。
- [x] Collection 与 Excel Import 的 Rule Relevance 选择语义被清楚拆开：Collection 继续使用全局 Relevance Snapshot；Excel Import 使用用户显式选择的 1—20 个词包并冻结 `ImportKeywordSelectionSnapshot`。
- [x] 当前 README/Appendix 不再声称 Excel Import 依赖全局 Relevance，也不再声称当前 Import Job 兼容已不存在的旧 `relevance` Payload。
- [x] `system` / `ingestion` 当前 README 移除与当前说明无关的 Stage 8B/8F 施工叙述，只保留当前职责、限制和真实实现入口。
- [x] 人工相关性复核的表、Repository、前端入口和 PostgreSQL 排障路径能从当前导航文档定位到，但不复制第二套完整 Schema/业务规则。
- [x] `frontend/README.md` 的永久 Real Full-stack Workflow 路径与当前 `.github/workflows/fullstack.yml` 一致。
- [x] 不修改业务代码、Contract、Schema/Migration、依赖、Prompt、Workflow 或 Roadmap；已发现的 Import 错误提示语义问题保持为已知未修实现问题。
- [x] Docs targeted re-review、独立 Review 和适用文档/治理门禁取得本轮证据；进入 `ready_for_review` 前未发现阻塞 Finding。

# 范围

只修改本 Change `affected_paths` 中的当前技术说明，以及本 Change 自身的状态/证据。

# 非目标

- 不修改 `backend/src/aima_ugc/bootstrap/api.py` 的 `RelevanceConfigurationError` 错误文案或异常类型；该实现问题另行进入 Coding Change。
- 不修改 Excel Import、Collection、Analysis、Docker/Compose、Release 的实际运行行为。
- 不修改 HTTP Contract、OpenAPI/generated client、数据库表或 Migration。
- 不机械扫描、重写或格式化所有 Markdown。
- 不重排 Blueprint/Appendix 编号，不迁移或删除历史 Change。

# 必须保持不变

- Collection 当前全局 `global_relevance_config → RelevanceSnapshotV1 → Run` 语义。
- Excel Import 当前 `keyword_pack_ids → ImportKeywordSelectionSnapshot → Batch + Job → Worker` 语义。
- Rule Relevance 与 AI Semantic Relevance 的领域分离。
- Internal V1-A 已实现、完整 Production Go-Live 仍 No-Go 的部署边界。
- `analysis_content_results` 保留模型原判；人工复核追加写 `analysis_content_relevance_reviews`。
- 生成物、Contract、Schema、测试和代码继续作为精确机器事实源。

# 已确认关键决策

1. Docs 模式为 `full`，但只完整覆盖本轮已界定的受影响文档域，不扩成全仓 Markdown 扫描。
2. 修复 Import 文档时不删除 `global_relevance_config`：它仍是当前 Collection 的正式全局 Relevance 选择事实。
3. 文档只解释 Import 的多词包选择/冻结语义，精确请求和 Snapshot 字段继续指向 Pydantic/代码，不复制第二套 Contract。
4. 已确认代码错误不能通过文档迎合；本 Change 只记录其为非目标，不修改实现。
5. 当前文档中的历史 Stage 施工语句若不再承担长期事实说明，应改写为当前职责/限制，而不是把历史过程继续留在模块 README。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 按 Docs `full` 要求修复已审计确认的受影响文档域，不机械扫描全部 Markdown | user:current-request; `.agents/skills/docs/SKILL.md` | satisfied | PR #248 diff 只有 8 份审计目标文档 + 本 Change；`main...docs/sync-current-docs` compare 未出现无关 Markdown/代码 |
| R2 | Blueprint 01 与当前 Docker/Compose/Internal V1-A 机器事实一致，同时不误写完整 Production 已完成 | `Dockerfile`; `compose.yaml`; `compose.windows.yaml`; `env.production.example`; `docs/roadmap/02_生产上线实施路线.md` | satisfied | `docs/blueprint/01_总体架构与技术选型.md` 已同时写明 Internal V1-A 当前事实与完整 Production No-Go 边界 |
| R3 | Excel Import 文档反映当前显式多词包选择与冻结语义；Collection 保留全局 Relevance | `backend/src/aima_ugc/bootstrap/import_http.py`; `backend/src/aima_ugc/modules/ingestion/import_job.py`; `backend/src/aima_ugc/bootstrap/import_worker.py`; `backend/src/aima_ugc/bootstrap/collection_scope.py` | satisfied | Blueprint 02 / Appendix 08 / System README / Ingestion README 已区分 `RelevanceSnapshotV1` 与 `ImportKeywordSelectionSnapshot`；targeted re-review 再次核对 `ImportJobPayload.extra=forbid`、`keyword_selection` 与 `_read_import_keyword_selection()` |
| R4 | 人工相关性复核在开发导航、数据库排障和前端 README 中可定位，但不复制第二套 Schema | `backend/src/aima_ugc/modules/analysis/relevance_review_tables.py`; `backend/src/aima_ugc/database_schema.py`; `frontend/src/features/voice-plaza/api.ts`; `frontend/src/features/voice-plaza/store.ts` | satisfied | `docs/01_代码结构与修改导航.md`、PostgreSQL Appendix、`frontend/README.md` 已补当前表/Repository/API/排障导航；精确 Schema 继续指向机器事实 |
| R5 | Full-stack Workflow 路径使用当前实际 `.github/workflows/fullstack.yml` | `.github/workflows/fullstack.yml` | satisfied | `frontend/README.md` 两处旧 `stage8f-fullstack.yml` 已改为当前永久 Workflow；targeted re-review 确认文件存在且 docs/README-only 变更由其 `paths-ignore` 排除 |
| R6 | 本轮只同步文档事实，不静默修改代码、Contract、Schema、依赖、Workflow 或 Roadmap | user:current-request; `.agents/skills/docs/SKILL.md` | satisfied | PR #248 实际 changed files 仅 8 份目标文档 + 本 Change；已知 `bootstrap/api.py` 错误提示问题明确留作非目标 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本 Change 不改变机器业务行为 |
| 接口 / Contract | not_applicable | 不修改 Pydantic/OpenAPI/generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库或运行时实现 |
| 用户 / Workflow Acceptance | not_applicable | 不改变用户可见产品行为；只同步说明 |
| 跨组件 Golden Path | not_applicable | 不改变组件接线；`.github/workflows/fullstack.yml` 对 docs/README-only 变更明确 `paths-ignore` |
| External Dependency / Provider Probe | not_applicable | 不修改或验证外部 Provider 行为 |
| Build / Package / Runtime | not_applicable | 不修改构建、镜像、配置或 Runtime 文件 |
| Docs / Governance / Other | required | PR #248 HEAD `89849c3895763cbbd02345f58aa48b956110d077`：`Docs and Governance` success、`CI Scope` success、`CI Gate` success；本次 Change 切到 Ready 后由新 HEAD 再执行 `Requirement Traceability and Completion Audit` 与最终 docs/governance 门禁 |

# 分步任务

- [x] 修正 Blueprint 01 的当前容器/Production 边界。
- [x] 修正 Blueprint 02 与 Appendix 08 的 Collection/Import Rule Relevance 分层。
- [x] 修正 System/Ingestion README 的当前职责与 Import Payload 说明。
- [x] 补齐人工 Relevance Review 的导航和 PostgreSQL 排障入口。
- [x] 修正 Frontend README 的人工复核能力摘要与 Full-stack Workflow 路径。
- [x] 对照机器事实执行 Docs targeted re-review，确认没有把未来能力写成当前能力。
- [x] 执行独立 Review；结论为 `NO_FINDINGS_WITHIN_SCOPE`，已知 Import HTTP 错误提示问题属于本 Change 明确非目标，未通过文档掩盖。
- [x] 取得首轮 `Docs and Governance` / `CI Gate` 文档治理证据；Ready 状态提交后继续要求新 HEAD 最终门禁全绿。
- [x] 更新 Requirement Traceability、Validation Matrix 和 Completion Audit，进入 `ready_for_review`。
- [ ] 通过仓库正常 PR/CI 流程合入 `main`，合并后再归档 Change。

# 验证计划与本轮证据

## Docs targeted re-review

重新从 PR #248 实际 diff 反查机器事实，而不是让修改后的 Markdown 互相证明：

- `ImportJobPayload` 当前只有 `keyword_selection`，`ConfigDict(extra="forbid")`，不存在旧 `relevance` Payload 兼容字段；
- `PostgresImportHttpService.create_import()` 先读取显式 `keyword_pack_ids` 形成 `ImportKeywordSelectionSnapshot`，验证 XLSX 后保存 Input Artifact，并把同一 `keyword_selection` 写入 Batch stats 与 Job Payload；
- `_read_import_keyword_selection()` 限制 1—20 个不重复 Pack，冻结 Pack ID/Version，并通过 `RelevanceService` 形成 `effective_keywords`；
- Voice Plaza Store 当前真实调用 `submitContentRelevanceReview()` 并根据返回结果刷新列表/详情；
- `.github/workflows/fullstack.yml` 是当前永久 Real Full-stack Workflow；该 Workflow 对 `docs/**`、`changes/**`、`**/README.md` 等文档-only 变化明确 `paths-ignore`；
- Docker/Compose 当前事实继续由根 `Dockerfile`、`compose.yaml`、`compose.windows.yaml` 与 Roadmap/Release Appendix 交叉验证。

结果：没有发现修改后的目标文档与上述机器事实之间的新冲突；没有发现为了同步而复制完整 Contract/Schema 的第二事实源。

## Independent Review

Review Target：`main@be35c195d5ef03282410a90a28048361f8bc4881 ... docs/sync-current-docs` / PR #248。

独立重建 R1-R6 后检查实际 diff：9 个 changed files = 8 份目标文档 + 本 Change，无生产代码、Contract、Schema/Migration、依赖、Prompt、Workflow、Roadmap 差异。对 Fact Correctness、Coverage、Source-of-truth Safety、知识保留与范围控制逐项复核，结论：`NO_FINDINGS_WITHIN_SCOPE`。

已知实现问题：`bootstrap/api.py` 仍可能把 Import 显式词包错误描述成“全局 Relevance 未配置”。这是审计发现的代码问题，不由本次文档 Change 修复，也没有被修改后的文档合法化。

## GitHub Actions 首轮证据

PR #248 HEAD `89849c3895763cbbd02345f58aa48b956110d077`：

```text
CI Scope                           success
Docs and Governance               success
CI Gate                            success
Linux Local Development Tooling   success
Windows Development and Compose Tooling success
Repository Quality                skipped（docs-only scope）
PostgreSQL Integration            skipped（docs-only scope）
```

该 HEAD 的 `Requirement Traceability and Completion Audit` 在 Change 仍为 `in_progress` 时按设计失败；本提交已将 Change 收口为 `ready_for_review`，最终结论只接受新 HEAD 的重新执行结果。

# Docs Impact

`full`：本任务本身就是跨核心架构、主数据入口、模块 README、开发导航与运维事实的文档一致性整改；`full` 仅覆盖审计已界定的受影响文档域，不等于读取/修改仓库全部 Markdown。

# Completion Audit

- [x] upstream_re_read：修改完成后重新读取本轮用户要求、Docs/Coding/Review 规则，并重新核对 Import Job/API、Voice Plaza relevance review、Full-stack Workflow 与容器关键机器事实。
- [x] change_coverage：R1-R6 均有对应文档 diff 或明确非目标证据；实际 PR diff 未发现范围外变化。
- [x] reverse_audit：已从文档关键断言反查 Docker/Compose、Import/Collection、Analysis Review、Workflow 真实入口，并从这些机器能力反查相关当前文档是否遗漏关键导航；未发现新的阻塞缺口。
- [x] unresolved_cleared：Requirement 状态已无 `not_satisfied`；required 文档治理验证已有首轮成功证据，Ready 提交后的新 HEAD 仍必须全绿后才允许合并。

# Git / PR / 发布状态

- branch: `docs/sync-current-docs`
- base main: `be35c195d5ef03282410a90a28048361f8bc4881`
- PR: `#248`（当前 Draft；本 Change Ready 提交后转 Ready for Review）
- 首轮 reviewed head: `89849c3895763cbbd02345f58aa48b956110d077`
- 首轮 CI: Docs/Governance 与 CI Gate 成功；Completion Gate 因 Change 当时仍 `in_progress` 按设计失败
- final CI: 待本次 `ready_for_review` 提交的新 HEAD 重新执行并确认
- main merge: 未完成
- archive: 未完成；只在 main 集成确认后执行
