---
schema: rvc-change/v1
id: CHG-20260826-sync-current-docs
title: 同步当前架构与数据入口文档事实
level: L2
status: in_progress
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

- [ ] `docs/blueprint/01_总体架构与技术选型.md` 正确描述 Internal V1-A 已实现的 Docker/Compose/Windows storage-only override，并继续明确完整 Production Go-Live 尚未闭环。
- [ ] Collection 与 Excel Import 的 Rule Relevance 选择语义被清楚拆开：Collection 继续使用全局 Relevance Snapshot；Excel Import 使用用户显式选择的 1—20 个词包并冻结 `ImportKeywordSelectionSnapshot`。
- [ ] 当前 README/Appendix 不再声称 Excel Import 依赖全局 Relevance，也不再声称当前 Import Job 兼容已不存在的旧 `relevance` Payload。
- [ ] `system` / `ingestion` 当前 README 移除与当前说明无关的 Stage 8B/8F 施工叙述，只保留当前职责、限制和真实实现入口。
- [ ] 人工相关性复核的表、Repository、前端入口和 PostgreSQL 排障路径能从当前导航文档定位到，但不复制第二套完整 Schema/业务规则。
- [ ] `frontend/README.md` 的永久 Real Full-stack Workflow 路径与当前 `.github/workflows/fullstack.yml` 一致。
- [ ] 不修改业务代码、Contract、Schema/Migration、依赖、Prompt、Workflow 或 Roadmap；已发现的 Import 错误提示语义问题保持为已知未修实现问题。
- [ ] Docs targeted re-review、独立 Review 和适用文档/治理门禁取得本轮新鲜证据，无阻塞 Finding 后才进入 Ready/合并。

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
| R1 | 按 Docs `full` 要求修复已审计确认的受影响文档域，不机械扫描全部 Markdown | user:current-request | not_satisfied | 本 Change 范围 + 待完成文档 diff / targeted re-review |
| R2 | Blueprint 01 与当前 Docker/Compose/Internal V1-A 机器事实一致，同时不误写完整 Production 已完成 | `Dockerfile`; `compose.yaml`; `compose.windows.yaml`; `env.production.example`; `docs/roadmap/02_生产上线实施路线.md` | not_satisfied | 待完成 `docs/blueprint/01_总体架构与技术选型.md` |
| R3 | Excel Import 文档反映当前显式多词包选择与冻结语义；Collection 保留全局 Relevance | `backend/src/aima_ugc/bootstrap/import_http.py`; `backend/src/aima_ugc/modules/ingestion/import_job.py`; `backend/src/aima_ugc/bootstrap/import_worker.py`; `backend/src/aima_ugc/bootstrap/collection_scope.py` | not_satisfied | 待完成 Blueprint 02 / Appendix 08 / System README / Ingestion README |
| R4 | 人工相关性复核在开发导航、数据库排障和前端 README 中可定位，但不复制第二套 Schema | `backend/src/aima_ugc/modules/analysis/relevance_review_tables.py`; `backend/src/aima_ugc/database_schema.py`; `frontend/src/features/voice-plaza/api.ts` | not_satisfied | 待完成 `docs/01_代码结构与修改导航.md` / PostgreSQL Appendix / `frontend/README.md` |
| R5 | Full-stack Workflow 路径使用当前实际 `.github/workflows/fullstack.yml` | `.github/workflows/fullstack.yml` | not_satisfied | 待完成 `frontend/README.md` |
| R6 | 本轮只修文档并提交到 main，不静默修代码或扩大范围 | user:current-request; `.agents/skills/docs/SKILL.md` | not_satisfied | 待完成 diff / Review / Git 合并证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本 Change 不改变机器业务行为 |
| 接口 / Contract | not_applicable | 不修改 Pydantic/OpenAPI/generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库或运行时实现 |
| 用户 / Workflow Acceptance | not_applicable | 不改变用户可见产品行为；只同步说明 |
| 跨组件 Golden Path | not_applicable | 不改变组件接线 |
| External Dependency / Provider Probe | not_applicable | 不修改或验证外部 Provider 行为 |
| Build / Package / Runtime | not_applicable | 不修改构建、镜像、配置或 Runtime 文件 |
| Docs / Governance / Other | required | `scripts/quality/check_docs.py`、适用 Secret/Change 门禁、Docs targeted re-review、Review re-review、最终 Git/CI 状态 |

# 分步任务

- [ ] 修正 Blueprint 01 的当前容器/Production 边界。
- [ ] 修正 Blueprint 02 与 Appendix 08 的 Collection/Import Rule Relevance 分层。
- [ ] 修正 System/Ingestion README 的当前职责与 Import Payload 说明。
- [ ] 补齐人工 Relevance Review 的导航和 PostgreSQL 排障入口。
- [ ] 修正 Frontend README 的人工复核能力摘要与 Full-stack Workflow 路径。
- [ ] 对照机器事实执行 Docs targeted re-review，确认没有把未来能力写成当前能力。
- [ ] 执行独立 Review，处理所有阻塞 Finding。
- [ ] 运行适用文档/治理门禁并记录本轮新鲜证据。
- [ ] 更新 Requirement Traceability、Validation Matrix 和 Completion Audit，进入 `ready_for_review`。
- [ ] 通过仓库正常 PR/CI 流程合入 `main`，合并后再归档 Change。

# 验证计划与本轮证据

当前仅完成审计与事实源恢复。文档修改、Review、CI/Docs 门禁证据待本 Change 实施后记录；进入 `ready_for_review` 前不得保留未满足 Requirement。

# Docs Impact

`full`：本任务本身就是跨核心架构、主数据入口、模块 README、开发导航与运维事实的文档一致性整改；`full` 仅覆盖审计已界定的受影响文档域，不等于读取/修改仓库全部 Markdown。

# Completion Audit

- [ ] upstream_re_read：修改完成后重新读取本轮用户要求、Docs/Coding/Review 规则和关键机器事实。
- [ ] change_coverage：逐项确认 R1-R6 均有文档 diff 或明确非目标证据。
- [ ] reverse_audit：从文档关键断言反查 Docker/Compose、Import/Collection、Analysis Review、Workflow 真实入口，并从这些机器能力反查相关当前文档没有遗漏/冲突。
- [ ] unresolved_cleared：`not_satisfied` 清零，所有 required 验证有新鲜证据，无未说明阻塞。

# Git / PR / 发布状态

- branch: `docs/sync-current-docs`
- base main: `be35c195d5ef03282410a90a28048361f8bc4881`
- commit: Active Change 初始化提交待本次写入产生
- PR: 未创建
- CI: 未运行
- main merge: 未完成
- archive: 未完成
