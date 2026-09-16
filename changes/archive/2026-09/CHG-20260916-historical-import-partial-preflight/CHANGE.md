---
schema: coding-change/v1
id: CHG-20260916-historical-import-partial-preflight
title: 历史批量导入跳过空文件并隔离少量坏文件
level: L2
status: done
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
contracts: []
data_changes: []
---

# 背景与现状

Historical Import 原实现的 Source File 预检采用 all-or-nothing 收敛：合法但只有表头的 Excel 返回 `historical_source_empty` 并失败；任意 Source File 失败都会让整个 Campaign 进入 `failed`，从而阻止已经正常预检的文件进入既有 Batch/Chunk 导入链。导入阶段的 Chunk 已经支持 `partial_failed`，因此失败隔离在 Source File 预检层不一致。

Requirement Source：GitHub Issue #506。用户确认采用最小方案实施并合并主分支。

# 目标

- 合法空 Excel 作为无数据来源成功跳过并保留警告事实，不阻塞 Campaign；
- 少量真正坏文件仍保留失败和技术原因，但只要存在正常文件就允许开始导入正常部分；
- 正常文件成功写入且存在预检坏文件时，最终 Campaign 为 `partial_failed`；
- 全部为空文件时无写入成功结束；全部为坏文件时保持 `failed`；
- 保持现有 Chunk 级失败、取消、重试、Brand/Vehicle Filter、Historical Fill-Only / Standard Observation 语义不变；
- 不新增数据库表、状态枚举、HTTP/OpenAPI 字段、依赖或复杂预检体系。

# 实现结果

1. `historical_import_worker.py`
   - `rows_seen == 0 / chunks == 0` 不再返回 fatal `historical_source_empty`；
   - 空 Source 以 `succeeded` 收敛，`stats.warning_code` 与 `error_code` 继续保留 `historical_source_empty` 供技术追溯；
   - 空 Source 不创建后续 Batch/Chunk。
2. `historical_import.py`
   - `finalize_preflight()` 等待所有 Source File 进入预检终态；存在正常 `ready` Source 时允许 Campaign 进入 `ready`；
   - 真正坏 Source 保持 `failed`，但不阻塞正常 Source；
   - 全空直接 `succeeded`，全坏仍 `failed`；
   - 最终 Campaign 收敛同时考虑 Source 与 Chunk，正常部分成功且存在真实失败时为 `partial_failed`；
   - `stats.failed` 继续只表达行/Chunk 失败，不把坏文件伪造成失败数据行。
3. `DataImportDialog.vue`
   - 空文件显示“文件没有数据，已自动跳过。”；
   - 真正失败继续使用业务层提示；技术详情保留 `relative_path · error_code`。
4. 保持 `prepare_campaign_start()` 只选择 `status == ready` 的正常 Source，因此空 Source 与坏 Source 都不会误创建 Batch。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正常文件 + 空文件时，空文件跳过且正常数据可导入，最终 succeeded | #506 / AC1 | satisfied | `test_historical_partial_preflight_postgres.py`；PR #511 current-head PostgreSQL Integration 成功 |
| R2 | 正常文件 + 坏文件时，正常数据可导入，最终 partial_failed 且坏文件可追溯 | #506 / AC2 | satisfied | 同一真实 PostgreSQL/API/Worker 回归；最终收敛纳入 Source failed |
| R3 | 全空无写入成功；全坏 failed 且不可开始 | #506 / AC3 | satisfied | 全空 / 全坏两条真实 PostgreSQL 回归通过 |
| R4 | 默认业务层使用用户语言，技术错误码仅在技术详情追溯 | #506 / AC4 | satisfied | `DataImportDialog.vue`；Frontend unit/build/Browser Mock 与 Real Full-stack 均通过 |
| R5 | 现有 Chunk partial failure、取消、重试、Filter 与两种写入策略保持不变 | #506 / AC5 | satisfied | 未改 Job type、Chunk retry、Filter Snapshot、Policy、Schema/Contract；全套 CI 与 Full-stack 通过 |

# Validation Matrix

| Layer | Required | Final Evidence |
| --- | --- | --- |
| Static / Type | required | PR head `ef65197b7c88b1e9456fbc5c7c9de18e251c5837` Ruff / Mypy 成功 |
| Unit / Contract / API | required | CI run `35073266748` 成功 |
| Architecture / Owner | required | CI run `35073266748` 成功 |
| Build / Frontend | required | Wheel、Frontend unit/build/Browser Mock 成功 |
| PostgreSQL Integration | required | CI run `35073266748` 成功，直接覆盖正常+空、正常+坏、全空、全坏 |
| Real Full-stack | required | CI run `35073266748` Excel Browser Full-stack 成功 |
| Runtime / Compose | required | Runtime Acceptance run `35073266514` / Compose Golden Path 成功 |
| Tooling | required | Developer Tooling Compatibility run `35073266511` 成功 |
| Governance | required | Requirement Traceability and Completion Audit、CI Gate 成功；最终 Review 无阻断发现 |

# Completion Audit

- [x] upstream_re_read：读取 Issue #506、项目 AGENTS、相关产品/Appendix/Roadmap、生产 Worker/Repository/前端调用链以及 Agent_Skills Source Mode 规则。
- [x] change_coverage：AC1–AC5 均有实现与直接测试证据。
- [x] reverse_audit：从创建 Campaign、Source 预检、start、Batch/Chunk、Content 写入、最终状态、用户提示到技术错误追溯均已反查；`prepare_campaign_start()` 仍只选择 `ready` Source。
- [x] failure_isolation：空文件不会建 Batch；坏文件不会建 Batch；正常文件继续处理；系统级错误语义未被吞掉。
- [x] current_head_ci：PR head `ef65197b7c88b1e9456fbc5c7c9de18e251c5837` 的 CI / Runtime / Tooling 全部成功。
- [x] final_review：PR #511 最终独立 Review 无阻断问题、无未解决 Review Thread。
- [x] guarded_merge：PR #511 使用 expected head SHA 合并，没有使用 Ruleset bypass。
- [x] main_fresh：业务 merge SHA `c622a7e2ca97208334e119a79f1b53f0c8f67c4e` 已成为 `main`。

# 交付结果

- PR：#511 `修复历史批量导入预检的部分失败隔离`
- PR head：`ef65197b7c88b1e9456fbc5c7c9de18e251c5837`
- Merge SHA：`c622a7e2ca97208334e119a79f1b53f0c8f67c4e`
- CI：`35073266748` 全绿；`CI Gate`、`Requirement Traceability and Completion Audit` 成功。
- Runtime：`35073266514` 全绿，包含 required `Compose Golden Path`。
- Tooling：`35073266511` 全绿。
- Schema / Migration：无。
- HTTP/OpenAPI / 主状态枚举：无新增或删除。

# 兼容、部署与回滚

不改 Schema/Migration、依赖、Runtime、部署拓扑、Content 身份或写入策略。回滚只恢复 Historical Snapshot/Repository 收敛逻辑及对应提示/测试；已按新语义成功写入的正常 Content 不应因代码回滚被删除，撤销仍使用现有可审计导入撤销能力。
