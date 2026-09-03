---
schema: coding-change/v1
id: CHG-20260903-issue-328-data-import-runtime
title: Data Import Campaign 运行中心与辅助补采闭环
level: L3
status: proposed
owner: codex
branch: fix/issue-328-data-import-runtime
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - ingestion
  - collection
  - runtime
  - api
  - frontend
  - database
  - observability
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/modules/collection/
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/adapters/persistence/postgres/
  - backend/src/aima_ugc/modules/ingestion/
  - migrations/versions/
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/import-batches/
  - tests/
  - docs/
contracts:
  - Collection Runtime HTTP API
  - Data Import Campaign Supplement Eligibility API
  - Collection Run HTTP API
data_changes:
  - collection_runs.data_import_campaign_id
---

# 背景与现状

当前页面“导入数据”已经使用 `/api/v1/data-import-*` Campaign，但采集运行中心、运行汇总和“基于已有批次补采”仍只读取兼容 `/api/v1/import-batches`。因此新导入成功后不会出现在运行中心，Campaign 内容也无法作为补采来源；前端遇到 422 时只显示通用 Contract 校验提示和 `request_id`，缺少安全、可定位的字段级信息。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/328

# 目标

把 Data Import Campaign 接入既有统一运行中心和 Batch Supplement 能力，同时保持旧 `import_batch_id` Contract 与历史数据兼容，并让 422 响应和日志能够通过同一 `request_id` 定位失败字段与错误码。

# 范围

1. Campaign 作为运行中心一等只读记录，进入列表、筛选、搜索和 KPI 汇总。
2. Campaign 提供补采资格查询，并可作为新建 `batch_supplement` Run 的来源。
3. Collection Run 持久化 Campaign 来源，Worker 从 Campaign 逐行账本解析目标，覆盖 `unchanged` 等已关联 Content 的终态。
4. 前端补采选择器、详情入口和错误表达改用 Campaign 主入口，同时保留旧 Batch 兼容展示。
5. 422 日志与响应使用同一 `request_id`，只记录字段位置和错误码，不记录请求值、Secret 或正文。

# 非目标

- 不改变 Excel Mapper、Canonical、Content Owner 或导入写入策略。
- 不自动调用真实 TikHub 或 LLM，不改变 Provider 费用与重试语义。
- 不删除 `/api/v1/import-batches`、`import_batch_id` 或历史 Batch 补采能力。
- 不升级依赖，不重构无关页面或运行时查询。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Campaign 在运行中心显示正确状态、阶段、进度和统计 | Issue #328 AC1 | not_satisfied | 待实现与验证 |
| R2 | 运行中心 KPI 纳入 Campaign 且不重复计数 | Issue #328 AC2 | not_satisfied | 待实现与验证 |
| R3 | Campaign 可在辅助补采中选择，并提供资格查询 | Issue #328 AC3 | not_satisfied | 待实现与验证 |
| R4 | Campaign 逐行账本中已关联 Content 的 `unchanged` 等终态具备补采资格 | Issue #328 AC4 | not_satisfied | 待实现与验证 |
| R5 | 新 Run 持久化 Campaign 来源，旧 `import_batch_id` 行为继续兼容 | Issue #328 AC5 | not_satisfied | 待实现与验证 |
| R6 | 管理员配置与运行中心默认 generated Client 请求通过 Contract 校验 | Issue #328 AC6 | not_satisfied | 待实现与验证 |
| R7 | 422 响应与安全日志可由同一 `request_id` 关联到字段和错误码 | Issue #328 AC7 | not_satisfied | 待实现与验证 |
| R8 | Contract、PostgreSQL、Browser Mock、Full-stack、构建和治理门禁通过 | Issue #328 AC8 | not_satisfied | 待实现与验证 |

# 实施计划

1. [冻结缺陷行为]
   → 修改范围：Contract、API、PostgreSQL 与前端回归测试
   → 预期结果：测试分别证明 Campaign 缺失、补采来源缺失和 422 诊断不足
   → 验证方式：目标测试在修复前按预期失败
2. [接入 Campaign 运行投影]
   → 修改范围：Runtime Contract、Cursor、Query Repository、HTTP 映射
   → 预期结果：Campaign 进入统一列表/KPI，旧 Batch 和 Collection Run 不变
   → 验证方式：Contract + PostgreSQL Integration
3. [接入 Campaign 补采]
   → 修改范围：Collection Run Contract/Schema/Migration、Target Reader、Run/Worker
   → 预期结果：Campaign 可冻结为 Run 来源，`unchanged` 等已关联 Content 可执行补采
   → 验证方式：API + PostgreSQL Integration + Worker workflow
4. [前端与诊断闭环]
   → 修改范围：generated Client、Store/API/Drawer/Runtime 页面、422 handler
   → 预期结果：页面可选择 Campaign、打开详情，并显示可行动的 Contract 错误
   → 验证方式：Vitest Browser Mock + Playwright Full-stack + backend API log test
5. [文档、审计与交付]
   → 修改范围：对应 Blueprint/Appendix、Change、PR
   → 预期结果：当前架构说明与机器事实一致，完成两阶段 Review 与 Completion Audit
   → 验证方式：Docs/Governance、完整 CI、Runtime Acceptance、main-fresh evidence

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| Red | required | Campaign runtime/eligibility/source persistence/422/frontend workflow 回归 |
| 行为 / Unit / Component | required | Contract validator、Cursor、前端 Store/组件 |
| 接口 / Contract | required | OpenAPI、API routes、generated Client |
| 集成 / Persistence / Runtime Dependency | required | PostgreSQL Runtime Query、Campaign ledger、Migration、Collection Worker |
| 用户 / Workflow Acceptance | required | 浏览器 Mock：导入后可见、可选 Campaign 补采、错误表达 |
| 跨组件 Golden Path | required | 真实 API + PostgreSQL + 浏览器 Full-stack |
| 外部依赖 Probe | not_applicable | 不发送真实 TikHub/LLM 请求；使用现有 Fake Provider |
| Build / Package / Runtime | required | Backend quality、Frontend lint/typecheck/test/build、Compose Runtime |
| Docs / Governance / Other | required | Change Completion、Docs/Governance、两阶段 Review、PR/main fresh CI |

# 兼容、迁移与回滚

- `CollectionRunCreateRequest` 保留 `import_batch_id`，新增 Campaign 来源时两者互斥；历史请求和历史 Run 继续读取。
- `collection_runs` 只新增 nullable Campaign 外键和互斥约束；既有行无需回填。
- 回滚应用前应停止创建新的 Campaign 补采 Run；Migration downgrade 删除新增约束、索引和列，不修改 Campaign、Batch、Content 或 Job 历史事实。

# Completion Audit

- [ ] upstream_re_read：实现完成后重新读取 Issue #328、相关 Blueprint/Appendix、最终 Contract/Schema 与 diff。
- [ ] change_coverage：逐项核对 R1–R8 的实现、测试、文档和运行证据。
- [ ] reverse_audit：从 Campaign 反查运行中心/补采/Worker，从页面动作反查后端真实支持，并从最终 diff 反查无越权改动。
- [ ] unresolved_cleared：清零未满足需求、未解决 Review 发现、失败门禁和兼容风险。
