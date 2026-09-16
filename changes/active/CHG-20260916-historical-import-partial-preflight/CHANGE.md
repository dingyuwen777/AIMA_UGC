---
schema: coding-change/v1
id: CHG-20260916-historical-import-partial-preflight
title: 历史批量导入跳过空文件并隔离少量坏文件
level: L2
status: in_progress
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

当前 Historical Import 在 Source File 预检阶段采用 all-or-nothing 收敛：合法但只有表头的 Excel 返回 `historical_source_empty` 并失败；任意 Source File 失败都会让整个 Campaign 进入 `failed`，从而阻止已经正常预检的文件进入既有 Batch/Chunk 导入链。导入阶段的 Chunk 已经支持 `partial_failed`，因此当前失败隔离在 Source File 预检层不一致。

Requirement Source：GitHub Issue #506。

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
| R1 | 正常文件 + 空文件时，空文件跳过且正常数据可导入，最终 succeeded | Issue #506 AC1 | not_satisfied | 待真实 PostgreSQL/API/Worker 回归 |
| R2 | 正常文件 + 坏文件时，正常数据可导入，最终 partial_failed 且坏文件可追溯 | Issue #506 AC2 | not_satisfied | 待真实 PostgreSQL/API/Worker 回归 |
| R3 | 全空无写入成功；全坏 failed 且不可开始 | Issue #506 AC3 | not_satisfied | 待真实 PostgreSQL/API/Worker 回归 |
| R4 | 默认业务层使用用户语言，技术错误码只在技术详情追溯 | Issue #506 AC4 | not_satisfied | 待前端实现/静态或组件验证 |
| R5 | 现有 Chunk partial failure、取消、重试、Filter 和两种写入策略保持不变 | Issue #506 AC5 | not_satisfied | 待相关回归与 CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 核心风险依赖真实 Job/Persistence 状态机，直接由 Integration 覆盖，不复制一套内存状态机测试 |
| 接口 / Contract | not_applicable | 目标方案不新增或修改 HTTP/OpenAPI 字段和状态枚举 |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL + API + Durable Job Worker：正常+空、正常+坏、全空、全坏四条链 |
| 用户 / Workflow Acceptance | required | HTTP 创建/预检/start/final 状态与前端资格/提示语义 |
| 跨组件 Golden Path | not_applicable | 不需要浏览器+后端完整 E2E；真实 API/Worker/DB 已直接覆盖关键业务链 |
| 外部依赖 Probe | not_applicable | 不涉及 TikHub/LLM 等外部事实 |
| Build / Package / Runtime | required | 当前 PR HEAD 正式 CI / 前端构建与类型检查 |
| Docs / Governance / Other | required | Issue/Change 追溯、受影响产品/专题文档检查、Completion Audit |

# 实施步骤

- [x] 建立并重新读取 Issue #506；确认最新 main 与当前生产调用链。
- [x] 从最新 main 创建任务分支。
- [ ] Red：提交四个真实 PostgreSQL/API/Worker 回归场景并取得当前实现失败证据。
- [ ] Green：空文件成功跳过；预检部分失败仍可 start；最终状态纳入 Source File failed。
- [ ] 按实际需要收敛前端用户提示，不扩大 Contract/Schema。
- [ ] 运行 targeted regression、相关既有回归、前端验证与 PR CI。
- [ ] 重新读取 Issue #506，完成 Completion Audit 和独立 Review。
- [ ] 合并主分支并取得 main fresh 证据；满足 AC 后关闭 Issue。

# 当前新鲜证据

- 目标 `main` 基线：`81d673dea8ed7047e9900eb4b4101d4ad812c8b2`。
- 当前实现事实：`historical_source_empty` 直接返回失败；`finalize_preflight()` 任意 Source `failed/cancelled` 即 Campaign `failed`；`prepare_campaign_start()` 只选择 Source `ready`；Chunk 导入已经支持 `partial_failed`。
- 本地容器无法解析 `github.com`，因此不以本地 clone/pytest 冒充验证；Red/Green 执行证据使用 GitHub Actions 当前 PR revision。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #506 与受影响正式事实源。
- [ ] change_coverage：AC1–AC5 全部映射到实现与直接 Evidence。
- [ ] reverse_audit：从用户导入入口反查预检、start、Worker、DB、结果提示与失败追溯。
- [ ] unresolved_cleared：`not_satisfied` 清零，未验证项如实暴露。

# 兼容、部署与回滚

目标方案不改 Schema/Migration、依赖、Runtime、部署拓扑、Content 身份或写入策略。回滚只恢复 Historical Snapshot/Repository 收敛逻辑及对应提示/测试；已按新语义成功写入的正常 Content 不应因代码回滚被删除，撤销仍使用现有可审计导入撤销能力。
