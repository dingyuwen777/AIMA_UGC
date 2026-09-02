---
schema: coding-change/v1
id: CHG-20260903-frontend-fullstack-reliability
title: 完善前端全栈可靠性与功能性黑盒验收
level: L3
status: in_progress
owner: dingyuwen777
branch: fix/314-frontend-fullstack-reliability
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - backend
  - public-contract
  - postgresql
  - testing
  - documentation
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/contracts/administration.py
  - backend/src/aima_ugc/bootstrap/api.py
  - backend/src/aima_ugc/bootstrap/import_http.py
  - backend/src/aima_ugc/bootstrap/administration_http.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/system.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/identity/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/import-batches/
  - frontend/src/features/admin-configuration/
  - frontend/src/shared/VehicleMultiSelect.vue
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - tests/
  - docs/blueprint/04_后端任务API与前端.md
  - frontend/README.md
  - changes/active/CHG-20260903-frontend-fullstack-reliability/
contracts:
  - KeywordPackCreateRequest
  - AuditEventListQuery
  - AuditEventListResponse
  - HistoricalCampaignResponse
data_changes: []
---

# 背景与现状

当前已实现前端页面的主业务交互均通过 generated Client 接入 FastAPI 与真实 PostgreSQL/Job 链路，但全面审计仍确认若干最终用户可见的可靠性缺口：全局身份/通知失败态被误显示为正常状态、共享车型目录失败后无法就地恢复、词包创建由多个 HTTP 写请求拼成非原子动作、管理员配置资源读取互相连坐、审计历史只能读取最近记录、Historical Campaign Retry 资格由截断明细推算、表单存在静默无效点击，以及 Browser Mock 允许未声明 API 请求失败仍保持绿色。

用户已经明确批准本 Change 继续使用固定 Development Identity，并明确排除付费采集预算/限额/熔断；这些边界不得借本 Change 静默扩张。

# 目标

- 让当前用户可见错误状态明确、可恢复，不把请求失败伪装成业务空状态或普通用户状态；
- 让“新建关键词包”成为一个 HTTP 请求、一个 PostgreSQL transaction 的原子动作，同时保持既有空词包创建和单条追加兼容；
- 让管理员配置各资源独立加载/失败/重试；
- 让审计历史可分页读取全部记录，不引入任意 JSON 正文搜索；
- 让 Historical Campaign 的 Retry 资格由完整 PostgreSQL 事实返回；
- 让 Browser Mock 对未声明 `/api/v1/**` 请求 fail-closed，并增加功能性黑盒与真实 Full-stack 证明；
- 保持数据库 Schema、Migration、固定开发身份、AI selected ≤1000 边界和 Provider 行为不变。

# 范围

Included：Identity/Notification 错误恢复、VehicleMultiSelect 重试、Keyword Pack 原子创建、Admin 独立资源状态、Audit 分页、Historical Campaign Retry capability、表单校验、Browser Mock fail-closed、相关 Contract/generated Client、Backend/API/PostgreSQL/Full-stack 测试及必要长期文档同步。

Excluded：飞书/真实身份认证、采集预算/限额/熔断、AI query-scope Run、Provider endpoint/参数/字段/价格、Schema/Migration、依赖/Runtime 升级、无关页面视觉重构。

# 必须保持不变

- `DevelopmentIdentityResolver` 继续作为当前默认身份；本 Change 不新增认证 Provider 或真实用户模型；
- Vue/FastAPI/PostgreSQL/Python/Node 与直接依赖版本不升级；
- generated Client 只能由 OpenAPI + Orval 重新生成，不手改；
- PostgreSQL 18 仍是唯一业务事实库；表 Owner 不变化；
- Historical Item 明细继续保持有界返回，Retry 资格改为独立聚合事实而不是解除明细上限；
- Existing Keyword Pack API 调用仍兼容不传初始关键词；单条 `add keyword` API 保留；
- 不修改 TikHub/Provider 实际协议，不执行真实付费 Provider Probe。

# 方案比较

- Keyword Pack 方案 A（采用）：给既有 `KeywordPackCreateRequest` 增加可选初始关键词集合，既有 POST 在同一事务完成 Pack/Keyword/Item/Audit。兼容旧调用、无新 Route、事务边界最清楚。
- Keyword Pack 方案 B（不采用）：新增 `/keyword-packs/bulk`。语义也正确，但会产生第二个创建入口并增加长期 API 面。
- Keyword Pack 方案 C（不采用）：前端失败后自动回滚/删除。无法保证跨 HTTP 原子性，且删除半成品本身可能失败。

- Audit 方案 A（采用）：原 `GET /api/v1/audit-events` 增加 `offset/limit` Query，Response 增加 `total/offset/limit`，按现有稳定倒序翻页。
- Audit 方案 B（不采用）：Cursor。审计列表规模和当前管理员 UI 只需要稳定历史翻页，Offset 更简单且与车型/词包管理目录一致。
- Audit 方案 C（不采用）：只把 limit 从 100 调大。仍然有静默截断，不能解决长期历史访问。

- Campaign Retry 方案 A（采用）：Repository 聚合失败 Chunk 数，`HistoricalCampaignResponse` 返回完整 retry capability；前端只消费该事实。
- Campaign Retry 方案 B（不采用）：把 Item 明细上限无限增大。会破坏大 Campaign 有界读取目标且仍让 UI 依赖明细实现。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 保留固定开发身份，但身份/通知失败必须显式且可重试 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待前端 unit + Browser Mock |
| R2 | VehicleMultiSelect 失败后可就地重试 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待前端 unit/Browser Mock |
| R3 | Keyword Pack + 初始关键词原子创建且旧调用兼容 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待 Contract/API/PostgreSQL/Full-stack |
| R4 | Admin 四类资源独立加载与错误恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待前端 unit/Browser Mock |
| R5 | Audit 支持完整历史分页 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待 Contract/PostgreSQL/Browser Full-stack |
| R6 | Campaign Retry 资格来自完整失败 Chunk 聚合 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待 PostgreSQL/API/Browser Full-stack |
| R7 | 管理员车型必填字段无静默点击 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待前端 unit/Browser Mock |
| R8 | Browser Mock 未声明 API fail-closed | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待测试门禁回归 |
| R9 | 增加高价值功能黑盒与真实 Full-stack 证据并完成 main 交付 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | in_progress | 待 CI/Review/PR/main fresh |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Frontend Unit | required | Identity/Notification error state、Vehicle retry、Admin partial failure、表单校验、Store Contract 调用 |
| Browser Mock Acceptance | required | fail-closed 基线 + 页面错误/重试/Audit 翻页/原子词包请求/Campaign Retry UI |
| Backend/API/PostgreSQL Integration | required | Keyword Pack transaction rollback/成功、Audit offset/total、failed chunk 聚合 |
| Contract / Generated Client | required | OpenAPI 与 Orval generated client 新鲜生成且 drift 为零 |
| Real Full-stack Golden Path | required | Browser → real API → PostgreSQL/Worker 覆盖原子词包、Audit 翻页、Campaign Retry capability 的用户路径 |
| Real Provider Probe | not_applicable | 不改变 Provider endpoint、参数、分页、字段或价格事实 |
| Build / Runtime / Security | required | lint、typecheck、unit、build、npm audit、Python quality、Runtime Acceptance |
| Docs / Governance / Review | required | Blueprint/Frontend README 事实同步、Completion Audit、两阶段 Review、PR/main fresh |

# 实施步骤

- [x] 恢复 main、目标项目规则、Agent_Skills canonical Source Mode 与相关 Blueprint/Contract/Owner 事实。
- [x] 创建 Requirement Issue #314、L3 分支与本 Active Change。
- [ ] Red：为八类缺陷建立可失败的前端/后端/黑盒回归，证明旧实现确实不满足。
- [ ] Green：实现最小兼容 Contract、Service/Repository 与前端恢复行为。
- [ ] 重新生成 OpenAPI/generated Client；禁止手工编辑 generated。
- [ ] 增加/调整 Browser Mock fail-closed 基线和真实 Full-stack specs。
- [ ] 运行目标测试、相关回归、PostgreSQL Integration、Contract drift、Real Full-stack、Build/Runtime/Security。
- [ ] 同步长期文档并执行 Completion Audit。
- [ ] 读取 canonical Review 规则，执行两阶段独立 Review；修复 Finding 后重新验证。
- [ ] 创建 PR，等待 current-head required checks 全绿后受保护合并。
- [ ] main fresh CI/Runtime 成功后用独立归档 PR 移入 `changes/archive/2026-09/`，关闭 Issue #314 并清理已合并分支。

# Completion Audit

- [ ] upstream_re_read：Ready/merge 前重新读取 Issue、main、相关 Contract/Owner、当前 Active Change 与 required checks。
- [ ] change_coverage：R1–R9 均有实现与对应验证证据，无未解释缺口。
- [ ] reverse_audit：从页面交互反查 generated Client/FastAPI/Service/PostgreSQL/Job，并从新增 Contract 反查全部消费者与测试。
- [ ] unresolved_cleared：所有 required Validation Matrix 项均有新鲜结果；not_applicable 具有事实依据。

# 兼容、部署与回滚

本 Change 只做向后兼容 HTTP 字段扩展和前端行为修复，不做 Schema/Migration、依赖升级或部署拓扑变化。旧客户端不提交 `keywords` 仍可创建空词包；新增 Response 字段不改变现有字段含义。回滚可恢复旧 Contract/Service/Frontend，不需要数据库迁移回滚，但会重新引入半成品词包、审计截断和 Retry 资格推断等已知缺陷，因此只应在新实现出现阻塞缺陷时通过正式回滚决定执行。
