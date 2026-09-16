---
schema: coding-change/v1
id: CHG-20260916-historical-import-partial-preflight
title: 历史批量导入跳过空文件并隔离少量坏文件
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/506-historical-import-partial-preflight
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - historical-import
  - frontend
  - testing
affected_paths:
  - backend/src/aima_ugc/bootstrap/historical_import_worker.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - tests/integration/ingestion/test_historical_partial_preflight_postgres.py
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/DataImportDialog.vue
  - docs/product/02_当前产品能力与用户流程.md
  - docs/appendix/08_数据入口与统一入库实现.md
contracts: []
data_changes: []
---

# 背景与现状

Historical Import 原实现的 Source File 预检采用 all-or-nothing 收敛：合法但只有表头的 Excel 返回 `historical_source_empty` 并失败；任意 Source File 失败都会让整个 Campaign 进入 `failed`，从而阻止已经正常预检的文件进入既有 Batch/Chunk 导入链。导入阶段的 Chunk 已经支持 `partial_failed`，因此失败隔离在 Source File 预检层不一致。

Requirement Source：GitHub Issue #506；本轮用户明确确认采用最小方案实施并合并主分支。

# 目标

- 合法空 Excel 作为无数据来源成功跳过并保留警告事实，不阻塞 Campaign；
- 少量真正坏文件仍保留失败和技术原因，但只要存在正常文件就允许开始导入正常部分；
- 正常文件成功写入且存在预检坏文件时，最终 Campaign 为 `partial_failed`；
- 全部为空文件时无写入成功结束；全部为坏文件时保持 `failed`；
- 保持现有 Chunk 级失败、取消、重试、Brand/Vehicle Filter、Historical Fill-Only / Standard Observation 语义不变。

# 范围

Included：Historical Snapshot Worker、Campaign 预检/最终状态收敛、既有 HTTP `can_start` 所依赖的持久统计语义、必要用户提示、真实 PostgreSQL/API/Worker 回归。

Excluded：新增数据库表/状态枚举、修改 Excel Profile/Canonical/Content 身份、自动 AI、复杂预检分类体系、依赖/Runtime 升级、无关重构。

# 必须保持不变

- 正常 Source File 仍只通过 `ready` 进入 `prepare_campaign_start()`；
- 真正坏 Source File 不创建 Batch，不绕过预检错误；
- `stats.failed` 继续表示行/Chunk 处理失败，不把一个坏文件伪造成一条失败数据行；
- 现有 Chunk retry 只处理失败 Chunk，不对确定性坏 Source File 做无意义重试；
- 不改变 PostgreSQL Schema、主状态 CHECK、Content Owner、Artifact/Canonical 关系和写入策略。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正常文件 + 空文件时，空文件跳过且正常数据可导入，最终 succeeded | #506 / AC1 | satisfied | `historical_import_worker.py` 将空 Source 收敛为 `succeeded` warning；真实 PostgreSQL/API/Worker 回归在 PR run 35066151634 通过 |
| R2 | 正常文件 + 坏文件时，正常数据可导入，最终 partial_failed 且坏文件可追溯 | #506 / AC2 | satisfied | `finalize_preflight()` 允许存在 failed Source 时进入 `ready`；`refresh_batch_and_campaign()` 纳入 Source failed；真实 PostgreSQL 回归通过 |
| R3 | 全空无写入成功；全坏 failed 且不可开始 | #506 / AC3 | satisfied | `finalize_preflight()` 明确全空 `succeeded` / 全坏 `failed`；对应真实 PostgreSQL 回归通过 |
| R4 | 默认业务层使用用户语言，技术错误码只在技术详情追溯 | #506 / AC4 | satisfied | `DataImportDialog.vue` 显示“文件没有数据，已自动跳过。”和既有友好失败提示；技术详情保留 `relative_path · error_code`；前端 unit/build/Browser Mock 在 PR run 35066151634 通过 |
| R5 | 现有 Chunk partial failure、取消、重试、Filter 和两种写入策略保持不变 | #506 / AC5 | satisfied | 未改 Job type、Chunk retry、Filter Snapshot、Policy、Schema/Contract；Ruff/Mypy、Unit/Contract/API、架构/Owner、Wheel 与 PostgreSQL Integration 均通过。Full-stack 唯一失败是当前 main 同样存在的声音广场车型系列/类别基线断言，与本 Change 无改动路径 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 核心风险依赖真实 Job/Persistence 状态机，直接由 Integration 覆盖，不复制一套内存状态机测试 |
| 接口 / Contract | not_applicable | 未新增或修改 HTTP/OpenAPI 字段、状态枚举或 generated client |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL + API + Durable Job Worker：正常+空、正常+坏、全空、全坏四条链；PR run 35066151634 的 PostgreSQL Integration 已通过，最新 main 同层也为绿色 |
| 用户 / Workflow Acceptance | required | HTTP 创建/预检/start/final 状态由同一 Integration 覆盖；前端用户提示由生产组件实现并通过前端 unit/build/Browser Mock |
| 跨组件 Golden Path | required | 仓库路径矩阵触发 Excel Browser Full-stack；本 Change 对应 Stage12 历史导入链通过，唯一失败为当前 main 可重复的声音广场车型系列/类别断言，作为独立基线阻塞保留，不在本任务绕过 |
| 外部依赖 Probe | not_applicable | 不涉及 TikHub/LLM 等外部事实 |
| Build / Package / Runtime | required | Runtime Acceptance、Developer Tooling、Wheel build 已通过；最新 head 同步 main 后重新执行 current-head 门禁 |
| Docs / Governance / Other | required | Issue #506、当前 Change、产品流程文档同步；Appendix 08 与 Roadmap 03 已重新读取，既有“全量预检/共用 Campaign”描述不与文件级隔离冲突，不为此复制第二套状态说明 |

# 实施步骤

- [x] 建立并重新读取 Issue #506；确认最新 main 与当前生产调用链。
- [x] 从最新 main 创建任务分支和 Draft PR #511。
- [x] 建立四个真实 PostgreSQL/API/Worker 回归场景；早期 Red 运行被项目 Change Completion Gate 按 `in_progress` 正常阻断，未伪造未执行的失败测试证据。
- [x] Green：空文件成功跳过；预检部分失败仍可 start；最终状态纳入 Source File failed。
- [x] 收敛前端用户提示，不扩大 Schema/状态枚举/依赖。
- [x] 同步产品文档；重读 Appendix/Roadmap 后确认无需重复改写。
- [x] PR head `82fa268480f16a9cdb767271f8cd3d6b9903a1b3`：治理、Ruff/Mypy、Unit/Contract/API、架构/Owner、Wheel、前端 unit/build/Browser Mock、PostgreSQL Integration、Runtime Acceptance、Developer Tooling 均通过。
- [x] Full-stack 失败已与 current main `ccab9d50a17e3b8faab85eccf891fabfe36b63ce` 对照：两者均只在 `admin-product-capabilities.spec.ts` 的声音广场车型系列/类别断言失败，非本 Change 引入；不绕过 required gate。
- [x] 任务分支已非强制同步 current main，保留其 env 模板更新。
- [x] PR 描述已移除 `Closes #506` 并收敛为当前实现/证据；Issue 只在 merge 后 main-fresh 与 Change archive 完成后关闭。
- [ ] 当前提交触发最新同步 head 的完整 current-head CI；不再修改 PR 元数据，避免 metadata-only 取消该运行。
- [ ] current-head CI 后执行最终独立 Review。
- [ ] required checks 全部满足后 guarded merge；随后取得 main fresh、repository-native Change archive 和 Issue Closure Evidence。

# 当前新鲜证据

- Issue #506 仍为当前 Requirement Source，AC1–AC5 未被改写。
- 已确认根因：`historical_source_empty` 原路径把 0 数据行视为失败；`finalize_preflight()` 原先任意 Source failed/cancelled 都让 Campaign failed。
- 真实 Green：PR run 35066151634 的 PostgreSQL Integration job 104698171000 通过，直接覆盖正常+空、正常+坏、全空、全坏；同一 run 的前端、静态、Unit/API、架构与 Wheel 均通过。
- 基线隔离：current main CI run 35065984387 与 PR run 35066151634 在同一 Full-stack 用例 `admin-product-capabilities.spec.ts`、同一系列/类别文本断言失败；本 Change 未修改声音广场车型展示或该用例。
- task branch 已同步 current main `ccab9d50a17e3b8faab85eccf891fabfe36b63ce`，同步提交使用两个 parent 且非强制更新分支。
- Ruleset `main-quality-gate` 当前 required checks 为 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`；即使当前账号可 bypass，也禁止用 bypass 代替绿色 required checks。

# Completion Audit

- [x] upstream_re_read：Ready 前已重新读取 Issue #506、相关产品/Appendix/Roadmap、生产 Worker/Repository/前端调用链。
- [x] change_coverage：AC1–AC5 均映射到实现与直接 Integration/UI Evidence；Full-stack 基线失败单独保留，不把它伪装成本 Change 成功证据。
- [x] reverse_audit：已从导入入口反查 Campaign 预检、Source Item、start、Batch/Chunk、Content 写入、最终状态、用户提示与技术错误追溯；`prepare_campaign_start()` 仍只选 `ready` Source。
- [x] unresolved_cleared：本 Change 内无 `not_satisfied` Requirement；当前唯一外部阻塞为 main 自身 Full-stack 基线失败，是否阻断 merge 由现行 Ruleset/required check 判定，禁止绕过。

# 兼容、部署与回滚

不改 Schema/Migration、依赖、Runtime、部署拓扑、Content 身份或写入策略。回滚只恢复 Historical Snapshot/Repository 收敛逻辑及对应提示/测试；已按新语义成功写入的正常 Content 不应因代码回滚被删除，撤销仍使用现有可审计导入撤销能力。
