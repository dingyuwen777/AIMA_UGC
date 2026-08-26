---
schema: rvc-change/v1
id: CHG-20260826-sync-current-docs
title: 同步当前架构与数据入口文档事实
level: L2
status: done
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

基于 Docs `full` 文档审计已经确认的机器事实，修复核心架构、Excel Import Rule Relevance、人工相关性复核导航和 Full-stack Workflow 路径的文档漂移，使当前技术文档重新与真实实现一致。

本 Change 只同步文档，不通过修改文档把已发现的代码问题合法化，也不扩大到与审计结论无关的 Markdown。

# 成功标准

- [x] `docs/blueprint/01_总体架构与技术选型.md` 正确描述 Internal V1-A 已实现的 Docker/Compose/Windows storage-only override，并继续明确完整 Production Go-Live 尚未闭环。
- [x] Collection 与 Excel Import 的 Rule Relevance 选择语义被清楚拆开：Collection 继续使用全局 Relevance Snapshot；Excel Import 使用用户显式选择的 1—20 个词包并冻结 `ImportKeywordSelectionSnapshot`。
- [x] 当前 README/Appendix 不再声称 Excel Import 依赖全局 Relevance，也不再声称当前 Import Job 兼容已不存在的旧 `relevance` Payload。
- [x] `system` / `ingestion` 当前 README 移除与当前说明无关的 Stage 8B/8F 施工叙述，只保留当前职责、限制和真实实现入口。
- [x] 人工相关性复核的表、Repository、前端入口和 PostgreSQL 排障路径能从当前导航文档定位到，但不复制第二套完整 Schema/业务规则。
- [x] `frontend/README.md` 的永久 Real Full-stack Workflow 路径与当前 `.github/workflows/fullstack.yml` 一致。
- [x] 不修改业务代码、Contract、Schema/Migration、依赖、Prompt、Workflow 或 Roadmap；已发现的 Import 错误提示语义问题保持为已知未修实现问题。
- [x] Docs targeted re-review、独立 Review、PR 门禁和合并后 `main` 验证全部取得新鲜成功证据。

# 范围

只修改本 Change `affected_paths` 中的当前技术说明，以及本 Change 自身的生命周期状态/证据。

# 非目标

- 不修改 `backend/src/aima_ugc/bootstrap/api.py` 的 `RelevanceConfigurationError` 错误文案或异常类型；该实现问题另行进入 Coding Change。
- 不修改 Excel Import、Collection、Analysis、Docker/Compose、Release 的实际运行行为。
- 不修改 HTTP Contract、OpenAPI/generated client、数据库表或 Migration。
- 不机械扫描、重写或格式化所有 Markdown。
- 不重排 Blueprint/Appendix 编号，不改写历史 Change。

# 必须保持不变

- Collection 当前全局 `global_relevance_config → RelevanceSnapshotV1 → Run` 语义。
- Excel Import 当前 `keyword_pack_ids → ImportKeywordSelectionSnapshot → Batch + Job → Worker` 语义。
- Rule Relevance 与 AI Semantic Relevance 的领域分离。
- Internal V1-A 已实现、完整 Production Go-Live 仍 No-Go 的部署边界。
- `analysis_content_results` 保留模型原判；人工复核追加写 `analysis_content_relevance_reviews`。
- 生成物、Contract、Schema、测试和代码继续作为精确机器事实源。

# 已确认关键决策

1. Docs 模式为 `full`，但只完整覆盖已界定的受影响文档域，不扩成全仓 Markdown 扫描。
2. 修复 Import 文档时不删除 `global_relevance_config`：它仍是当前 Collection 的正式全局 Relevance 选择事实。
3. 文档只解释 Import 的多词包选择/冻结语义，精确请求和 Snapshot 字段继续指向 Pydantic/代码，不复制第二套 Contract。
4. 已确认代码错误不能通过文档迎合；本 Change 只记录其为非目标，不修改实现。
5. 当前文档中的历史 Stage 施工语句若不再承担长期事实说明，应改写为当前职责/限制，而不是把历史过程继续留在模块 README。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 按 Docs `full` 要求修复已审计确认的受影响文档域，不机械扫描全部 Markdown | user:current-request | satisfied | PR #248 实际 diff 只有 8 份审计目标文档 + 本 Change，无无关 Markdown/代码 |
| R2 | Blueprint 01 与当前 Docker/Compose/Internal V1-A 机器事实一致，同时不误写完整 Production 已完成 | `compose.yaml` | satisfied | Blueprint 01 已与根 Dockerfile、canonical Compose、Windows storage-only override 及 Roadmap 的 Production No-Go 边界交叉核对 |
| R3 | Excel Import 文档反映当前显式多词包选择与冻结语义 | `backend/src/aima_ugc/modules/ingestion/import_job.py` | satisfied | Blueprint 02 / Appendix 08 / System README / Ingestion README 已反映 `ImportKeywordSelectionSnapshot`；targeted re-review 核对 `ImportJobPayload.extra=forbid`、`keyword_selection` 与 Import API/Worker 冻结校验 |
| R4 | Collection 继续保留全局 Rule Relevance，并与 Import 每批词包选择区分 | `backend/src/aima_ugc/bootstrap/collection_scope.py` | satisfied | Blueprint 02 / Appendix 08 / System README 明确 Collection 使用 Run 冻结 `RelevanceSnapshotV1`；没有因修 Import 文档删除 `global_relevance_config` |
| R5 | 人工相关性复核在开发导航、数据库排障和前端 README 中可定位，但不复制第二套 Schema | `backend/src/aima_ugc/modules/analysis/relevance_review_tables.py` | satisfied | 代码导航、PostgreSQL Appendix、Frontend README 已补当前表/Repository/API/排障导航；Voice Plaza Store 的 `reviewRelevance()` 验证前端真实接线 |
| R6 | Full-stack Workflow 路径使用当前实际 `.github/workflows/fullstack.yml` | `.github/workflows/fullstack.yml` | satisfied | Frontend README 两处旧 `stage8f-fullstack.yml` 已改为当前永久 Workflow，并确认 docs/README-only 变更由该 Workflow `paths-ignore` 排除 |
| R7 | 本轮只同步文档事实，不静默修改代码、Contract、Schema、依赖、Workflow 或 Roadmap | user:current-request | satisfied | PR #248 changed files 仅 8 份目标文档 + 本 Change；已知 `bootstrap/api.py` 错误提示问题明确留作非目标 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本 Change 不改变机器业务行为 |
| 接口 / Contract | not_applicable | 不修改 Pydantic/OpenAPI/generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库或运行时实现 |
| 用户 / Workflow Acceptance | not_applicable | 不改变用户可见产品行为；只同步说明 |
| 跨组件 Golden Path | not_applicable | 不改变组件接线；Full-stack Workflow 对 docs/README-only 变更按既有规则处理 |
| External Dependency / Provider Probe | not_applicable | 不修改或验证外部 Provider 行为 |
| Build / Package / Runtime | not_applicable | 不修改构建、镜像、配置或 Runtime 文件 |
| Docs / Governance / Other | required | PR #248 最终候选 HEAD `1d231430ed1ec8ba07cba151c415a6e5380a8bf6` 的 Completion Gate、CI、Developer Tooling、Runtime Acceptance 全部 success；合并后的 `main@44c274ce9d4a0df71d36ecdb05f304c61470c854` 对应 CI #3189、Completion Gate #1035、Developer Tooling #60、Runtime Acceptance #310 也全部 success |

# 分步任务

- [x] 修正 Blueprint 01 的当前容器/Production 边界。
- [x] 修正 Blueprint 02 与 Appendix 08 的 Collection/Import Rule Relevance 分层。
- [x] 修正 System/Ingestion README 的当前职责与 Import Payload 说明。
- [x] 补齐人工 Relevance Review 的导航和 PostgreSQL 排障入口。
- [x] 修正 Frontend README 的人工复核能力摘要与 Full-stack Workflow 路径。
- [x] 对照机器事实执行 Docs targeted re-review，确认没有把未来能力写成当前能力。
- [x] 执行独立 Review；文档 diff 结论为 `NO_FINDINGS_WITHIN_SCOPE`。
- [x] 运行文档/治理门禁并按失败证据修正 Change Source 格式，没有修改门禁或降低要求。
- [x] 更新 Requirement Traceability、Validation Matrix 和 Completion Audit。
- [x] 通过仓库正常 PR/CI 流程合入 `main`，并完成合并后主分支新鲜验证。
- [x] 在主分支验证成功后进入独立 Change 归档流程。

# 验证与证据

## Docs targeted re-review

重新从 PR #248 实际 diff 反查机器事实，而不是让修改后的 Markdown 互相证明：

- `ImportJobPayload` 当前只有 `keyword_selection`，`ConfigDict(extra="forbid")`，不存在旧 `relevance` Payload 兼容字段；
- `PostgresImportHttpService.create_import()` 先读取显式 `keyword_pack_ids` 形成 `ImportKeywordSelectionSnapshot`，验证 XLSX 后保存 Input Artifact，并把同一 `keyword_selection` 写入 Batch stats 与 Job Payload；
- `_read_import_keyword_selection()` 限制 1—20 个不重复 Pack，冻结 Pack ID/Version，并通过 `RelevanceService` 形成 `effective_keywords`；
- Voice Plaza Store 当前真实调用 `submitContentRelevanceReview()` 并根据返回结果刷新列表/详情；
- `.github/workflows/fullstack.yml` 是当前永久 Real Full-stack Workflow；
- Docker/Compose 当前事实由根 `Dockerfile`、`compose.yaml`、`compose.windows.yaml` 与 Roadmap/Release Appendix 交叉验证。

结果：没有发现修改后的目标文档与机器事实之间的新冲突；没有发现为了同步而复制完整 Contract/Schema 的第二事实源。

## Independent Review

Review Target：`main@be35c195d5ef03282410a90a28048361f8bc4881 ... docs/sync-current-docs` / PR #248。

独立重建 R1-R7 后检查实际 diff：8 份目标文档 + 本 Change，无生产代码、Contract、Schema/Migration、依赖、Prompt、Workflow、Roadmap 差异。对 Fact Correctness、Coverage、Source-of-truth Safety、知识保留与范围控制逐项复核，结论：`NO_FINDINGS_WITHIN_SCOPE`。

已知实现问题：`bootstrap/api.py` 仍可能把 Import 显式词包错误描述成“全局 Relevance 未配置”。这是审计发现的代码问题，不由本次文档 Change 修复，也没有被修改后的文档合法化。

## Completion Gate 调试证据

Change 首次切到 Ready 后，Completion Gate 的 Coding tests 成功，但 `Enforce changed PR Change readiness` 失败。对照 `ready_check.py` 确认根因是 Requirement Source 单元格放入多个路径，而门禁要求每条 Requirement 对应一个安全仓库相对路径或显式 `user:/external:` Source。随后把 Requirement 拆分/收敛为 R1-R7，每个 Source 只保留一个合法事实源；没有修改门禁实现。

## PR #248 最终候选证据

最终候选 HEAD：`1d231430ed1ec8ba07cba151c415a6e5380a8bf6`。

```text
Change Completion Gate             success
CI                                 success
  CI Scope                         success
  Docs and Governance              success
  CI Gate                          success
  Repository Quality               skipped（docs-only scope）
  PostgreSQL Integration           skipped（docs-only scope）
Developer Tooling Compatibility    success
Runtime Acceptance                 success
```

Runtime Acceptance 实际执行并成功验证 canonical Compose、repository-relative Host Root 和 Windows storage overlay；并非以“文档任务”为由静默跳过已经触发的 Runtime 验证。

## `main` 合并后证据

PR #248 以 squash 正常合并，生成：

```text
main commit
44c274ce9d4a0df71d36ecdb05f304c61470c854
```

合并后重新核对主分支，`main` 精确指向该 SHA，并重新执行 push workflows：

```text
CI #3189                          success
Change Completion Gate #1035     success
Developer Tooling #60            success
Runtime Acceptance #310          success
```

Runtime #310 的 `Compose Golden Path` 成功，包含：

```text
Validate canonical Compose topology                       success
Canonical Compose startup, security, persistence, recovery success
Repository-relative host root smoke                       success
Validate Windows overlay storage model                    success
Windows overlay startup/permissions/persistence           success
```

因此本 Change 的实现和合并后主分支均有本轮新鲜证据。

# Docs Impact

`full`：本任务本身就是跨核心架构、主数据入口、模块 README、开发导航与运维事实的文档一致性整改；`full` 仅覆盖审计已界定的受影响文档域，不等于读取/修改仓库全部 Markdown。

# Completion Audit

- [x] upstream_re_read：修改完成后重新读取用户要求、Docs/Coding/Review 规则，并重新核对 Import Job/API、Voice Plaza relevance review、Full-stack Workflow 与容器关键机器事实。
- [x] change_coverage：R1-R7 均有对应文档 diff 或明确非目标证据；实际 PR diff 未发现范围外变化。
- [x] reverse_audit：已从文档关键断言反查 Docker/Compose、Import/Collection、Analysis Review、Workflow 真实入口，并从机器能力反查相关当前文档是否遗漏关键导航。
- [x] unresolved_cleared：Requirement 状态无 `not_satisfied`；PR 最终候选和合并后主分支的适用门禁均成功，无未说明阻塞。

# Git / PR / 发布状态

- implementation branch: `docs/sync-current-docs`
- initial base main: `be35c195d5ef03282410a90a28048361f8bc4881`
- implementation PR: `#248`
- final candidate head: `1d231430ed1ec8ba07cba151c415a6e5380a8bf6`
- merge method: squash
- merged main commit: `44c274ce9d4a0df71d36ecdb05f304c61470c854`
- PR final CI: Completion Gate / CI / Tooling / Runtime 全部 success
- post-merge main CI: CI #3189 / Completion Gate #1035 / Tooling #60 / Runtime #310 全部 success
- archive: 当前文件由独立治理分支移动至 `changes/archive/2026-08/`；归档 PR/合并结果由该治理 PR 记录在 Git 历史中
