---
schema: coding-change/v1
id: CHG-20260903-issue-328-data-import-runtime
title: Data Import Campaign 运行中心与辅助补采闭环
level: L3
status: ready_for_review
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
| R1 | Campaign 在运行中心显示正确状态、阶段、进度和统计 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | Runtime UNION 投影 Campaign 父记录且允许 `job_id=null`；PostgreSQL 集成覆盖 succeeded/ready 状态、进度与统计，Browser Mock 和 CI Full-stack 均重读成功 |
| R2 | 运行中心 KPI 纳入 Campaign 且不重复计数 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | KPI 分别统计旧 `ingestion.import-excel.v1` Batch、Campaign 父记录和 Collection Run；Campaign Chunk Batch 被 Job type 过滤，PostgreSQL 测试断言完成数与入库数只计一次 |
| R3 | Campaign 可在辅助补采中选择，并提供资格查询 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | 新增 Campaign eligibility API；前端选择器优先展示终态 Campaign 并保留旧 Batch，Browser Mock 验证请求只提交对应来源字段 |
| R4 | Campaign 逐行账本中已关联 Content 的 `unchanged` 等终态具备补采资格 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | Target Reader 由 `processing_import_batch_items → historical_import_campaign_items → contents` 读取并去重；PostgreSQL 测试以 `unchanged` 行验证资格与 Scope 冻结 |
| R5 | 新 Run 持久化 Campaign 来源，旧 `import_batch_id` 行为继续兼容 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | Migration 0040 新增 nullable Campaign 外键、索引和来源互斥约束；Service/Repository/Worker 全链路消费，旧 Batch API、Run 与浏览器验收继续通过 |
| R6 | 管理员配置与运行中心默认 generated Client 请求通过 Contract 校验 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | OpenAPI/Orval 重新生成且 compatibility gate 通过；CI #3903 的 Repository Quality 与真实 Full-stack 管理员/运行中心请求全部成功 |
| R7 | 422 响应与安全日志可由同一 `request_id` 关联到字段和错误码 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | FastAPI handler 只记录 `field/code` 并复用响应 `request_id`；API 日志测试和前端 shared/import error 测试验证可定位且不回显拒绝值 |
| R8 | Contract、PostgreSQL、Browser Mock、Full-stack、构建和治理门禁通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/328 | satisfied | 本地缺陷矩阵 56 passed、Vitest 90 passed、Browser Mock 9 passed、build/mypy/gates 通过；远程 CI #3903、Runtime Acceptance #1024、Tooling #389 全部 success |

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
| Red | required | 首个治理提交冻结 Campaign eligibility 404、Campaign source Contract 拒绝和 422 无诊断三类预期失败；实现后全部转绿 |
| 行为 / Unit / Component | required | 本地目标后端矩阵 56 passed；前端 Vitest 19 files / 90 tests passed；mypy 287 source files 无问题 |
| 接口 / Contract | required | OpenAPI、API routes、generated Client 已同步；Contract generation 与 compatibility gate 成功 |
| 集成 / Persistence / Runtime Dependency | required | 隔离 PostgreSQL 18 验证 Runtime Query、Campaign ledger、Migration 0039→0040→0039 和 Collection Run 来源；CI #3903 PostgreSQL Integration 成功 |
| 用户 / Workflow Acceptance | required | `collection-runtime.spec.ts` 9 passed，覆盖导入后可见、Campaign/旧 Batch 补采和错误表达 |
| 跨组件 Golden Path | required | CI #3903 Real Full-stack Golden Path 成功，真实 API、Worker、PostgreSQL 与浏览器重读 Campaign Runtime/eligibility |
| 外部依赖 Probe | not_applicable | 不发送真实 TikHub/LLM 请求；使用现有 Fake Provider |
| Build / Package / Runtime | required | 前端 lint/typecheck/build、本地后端静态检查成功；CI #3903 Repository Quality 与 Runtime Acceptance #1024 成功 |
| Docs / Governance / Other | required | Docs/Fact/Architecture/Table Owner/Secret/Agent Governance 门禁成功；目标 Change Ready Check 待本证据提交触发最终复核 |

# 兼容、迁移与回滚

- `CollectionRunCreateRequest` 保留 `import_batch_id`，新增 Campaign 来源时两者互斥；历史请求和历史 Run 继续读取。
- `collection_runs` 只新增 nullable Campaign 外键和互斥约束；既有行无需回填。
- 回滚应用前应停止创建新的 Campaign 补采 Run；Migration downgrade 删除新增约束、索引和列，不修改 Campaign、Batch、Content 或 Job 历史事实。

# 实现与 Review 证据

2026-09-03 完成 L3 两阶段 Review。先按 Issue #328 的用户可见故障逐项复核，再从最终 diff 反查 Contract、Schema、Producer/Consumer、异步状态、前端入口和兼容路径。Review 期间发现并修复：

1. 补采 API 不能只依赖前端隐藏运行中 Campaign，后端 eligibility 与 Run create 共同增加终态门禁并返回 409；
2. `ready` Campaign 的公开状态为 queued，因此 KPI 也必须计入 processing；新增 PostgreSQL 回归后修正；
3. 最新 `main` 已把受管 Runtime 重命名为 `agent-skills.exe`，旧治理测试仍要求整个 Runtime 目录被忽略；最小同步为“旧文件名不跟踪、当前文件名已跟踪”。

最终结论：`NO_UNRESOLVED_FINDINGS_WITHIN_SCOPE`。原始请求提供的两个历史 `request_id` 未出现在当前保留日志中，无法追溯当次被拒字段；本修复确保今后同类 422 在响应与安全日志中保留同一 `request_id + field + code`。

# Pre-Merge 永久门禁

PR #329 首轮实现 HEAD `038d73e76f27a948c6002dbc5ef8be2ea4f07ca1`：

- CI #3903 / run `33745640755`：success，覆盖 Repository Quality、Linux Unit/Contract/API、PostgreSQL Integration、Real Full-stack Golden Path、Docs/Governance；
- Runtime Acceptance #1024 / run `33745640389`：success；
- Developer Tooling Compatibility #389 / run `33745640382`：success；
- Change Completion Gate #1768/#1769：因本 Change 按流程保持 `proposed` 等待上述证据而失败；本提交改为 `ready_for_review` 后重新触发最终 Gate，不把预期阶段失败写成通过。

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #328、相关 Blueprint/Appendix、最终 Contract/Schema、最新 `origin/main` 与 PR #329 最终业务 diff，并独立重建 R1–R8 完成定义。
- [x] change_coverage：Campaign Runtime/KPI、eligibility、逐行账本、Run 来源、旧 Batch 兼容、generated Client、422 诊断、Migration、测试与文档均有实现和新鲜证据。
- [x] reverse_audit：已从 Campaign 反查运行中心/补采/Worker，从页面选择与详情动作反查后端真实 API/持久化支持，并确认 Campaign Chunk 不重复统计、旧 Batch 路径仍可用。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`；外部付费 Probe 的不适用依据明确；Review 发现已修复，首轮 CI/Runtime/Tooling 无失败。
