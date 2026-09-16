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
| R1 | 正常文件 + 空文件时，空文件跳过且正常数据可导入，最终 succeeded | #506 / AC1 | satisfied | `historical_import_worker.py` 将空 Source 收敛为 `succeeded` warning；对应真实 DB/API/Worker 回归已提交，current-head PostgreSQL Integration 在 PR Ready 后执行 |
| R2 | 正常文件 + 坏文件时，正常数据可导入，最终 partial_failed 且坏文件可追溯 | #506 / AC2 | satisfied | `finalize_preflight()` 允许存在 failed Source 时进入 `ready`；`refresh_batch_and_campaign()` 纳入 Source failed；对应真实回归已提交 |
| R3 | 全空无写入成功；全坏 failed 且不可开始 | #506 / AC3 | satisfied | `finalize_preflight()` 明确全空 `succeeded` / 全坏 `failed`；对应真实回归已提交 |
| R4 | 默认业务层使用用户语言，技术错误码只在技术详情追溯 | #506 / AC4 | satisfied | `DataImportDialog.vue` 显示“文件没有数据，已自动跳过。”和既有友好失败提示；技术详情保留 `relative_path · error_code` |
| R5 | 现有 Chunk partial failure、取消、重试、Filter 和两种写入策略保持不变 | #506 / AC5 | satisfied | 未改 Job type、Chunk retry、Filter Snapshot、Policy、Schema/Contract；PR current-head 全套 CI 作为最终回归门禁 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 核心风险依赖真实 Job/Persistence 状态机，直接由 Integration 覆盖，不复制一套内存状态机测试 |
| 接口 / Contract | not_applicable | 未新增或修改 HTTP/OpenAPI 字段、状态枚举或 generated client |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL + API + Durable Job Worker：正常+空、正常+坏、全空、全坏四条链；PR Ready 后由 `PostgreSQL Integration` current-head gate 执行 |
| 用户 / Workflow Acceptance | required | HTTP 创建/预检/start/final 状态由同一 Integration 覆盖；前端用户提示由生产组件实现并由前端 CI build/type/browser gates 检查 |
| 跨组件 Golden Path | not_applicable | 本改动没有新增组件接线；真实 API/Worker/PostgreSQL 已直接覆盖关键业务链，既有 Full-stack gate 按仓库路径规则决定是否运行 |
| 外部依赖 Probe | not_applicable | 不涉及 TikHub/LLM 等外部事实 |
| Build / Package / Runtime | required | 当前 PR HEAD 正式 CI / 前端构建与类型检查；Runtime Acceptance 按路径风险矩阵执行 |
| Docs / Governance / Other | required | Issue #506、当前 Change、产品流程文档同步；Appendix 08 与 Roadmap 03 已重新读取，既有“全量预检/共用 Campaign”描述不与文件级隔离冲突，不为此复制第二套状态说明 |

# 实施步骤

- [x] 建立并重新读取 Issue #506；确认最新 main 与当前生产调用链。
- [x] 从最新 main 创建任务分支和 Draft PR #511。
- [x] 建立四个真实 PostgreSQL/API/Worker 回归场景。Red 运行尝试被仓库 Completion Gate 在 Change `in_progress` 阶段提前截断，PostgreSQL Integration 被跳过；未绕过门禁，也不伪造 Red 执行结果。
- [x] Green 实现：空文件成功跳过；预检部分失败仍可 start；最终状态纳入 Source File failed。
- [x] 前端只增加必要用户提示，不扩大 Contract/Schema。
- [x] 同步 `docs/product/02_当前产品能力与用户流程.md`；重新读取 Appendix 08 / Roadmap 03，未发现需要额外改写的矛盾事实。
- [ ] PR Ready 后运行 current-head PostgreSQL Integration、前端 gates、静态/类型/现有回归和 CI Gate。
- [ ] 完成独立 Review；如有 Finding 返回修复并重跑对应证据。
- [ ] 合并主分支并取得 main fresh 证据；满足 AC 后关闭 Issue #506。

# 当前新鲜证据

- 目标 `main` 基线：`81d673dea8ed7047e9900eb4b4101d4ad812c8b2`。
- 当前分支基于该基线且无 behind；实现 diff 限定在 Historical Worker/Repository、3 行前端提示、回归测试、产品文档与 Change。
- Red CI 尝试：Actions run `35064515979`；`Requirement Traceability and Completion Audit` 因当时 Change=`in_progress` 失败，后续 `PostgreSQL Integration`/产品 CI 被仓库门禁跳过，因此没有把“未执行测试”冒充失败测试证据。
- Runtime Acceptance run `35064515732`：Compose Golden Path fast-path success；Runtime 风险路径未变化。
- 本地容器再次尝试通过 raw GitHub 拉取分支文件做 `py_compile`，因 DNS `Temporary failure in name resolution` 无法取得源码；该环境缺口不替代 PR CI。
- PR Ready run `35065702165`：Requirement Source 与项目治理接线通过；Change Source `Issue #506 AC*` 被解析为仓库路径，Ready Check 失败。
- PR Ready run `35065790019`：Requirement Source 与项目治理接线继续通过；Ready Check 明确要求 Source 使用稳定 Acceptance（例如 `#123 / AC1`）。本提交已改为 `#506 / AC1`～`AC5`；两次均为治理载体格式失败，产品/Integration jobs 按门禁未执行。

# Completion Audit

- [x] upstream_re_read：2026-09-16 重新读取 Issue #506、产品流程、Appendix 08、Roadmap 03 和当前生产实现。
- [x] change_coverage：AC1–AC5 均有实现路径和直接回归目标，没有新增复杂预检体系。
- [x] reverse_audit：用户创建 Campaign → Source Snapshot → 预检收敛 → `can_start` → `prepare_campaign_start()` 仅选择 `ready` Source → Chunk/DB → Campaign 终态 → 前端明细/技术详情已反向核对。
- [x] unresolved_cleared：设计与实现范围没有待决策语义；current-head CI / Review 是交付门禁而非未实现 Requirement，执行失败将退回 `in_progress` 修复。

# 兼容、部署与回滚

无 Schema/Migration、依赖、Runtime、部署拓扑、Content 身份、Canonical Contract 或写入策略变化。部署沿现有 Release；无需数据迁移。回滚只恢复 Historical Snapshot/Repository 收敛逻辑及对应提示/测试；已按新语义成功写入的正常 Content 不因代码回滚删除，撤销仍使用现有可审计导入撤销能力。
