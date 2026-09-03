---
schema: coding-change/v1
id: CHG-20260903-frontend-fullstack-reliability
title: 完善前端全栈可靠性与功能性黑盒验收
level: L3
status: ready_for_review
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
  - backend/src/aima_ugc/bootstrap/content_http.py
  - backend/src/aima_ugc/modules/analysis/
  - backend/src/aima_ugc/adapters/persistence/postgres/system.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - backend/src/aima_ugc/adapters/persistence/postgres/analysis.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/
  - frontend/src/features/identity/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/import-batches/
  - frontend/src/features/admin-configuration/
  - frontend/src/features/voice-plaza/
  - frontend/src/shared/VehicleMultiSelect.vue
  - frontend/e2e/
  - frontend/e2e-fullstack/
  - tests/
  - docs/blueprint/04_后端任务API与前端.md
  - docs/appendix/07_AI舆情打标与分析实现.md
  - frontend/README.md
  - changes/active/CHG-20260903-frontend-fullstack-reliability/
contracts:
  - KeywordPackCreateRequest
  - AuditEventListQuery
  - AuditEventListResponse
  - HistoricalCampaignResponse
  - AnalysisRunTargetSelection
  - AnalysisContentRunPreviewRequest
  - AnalysisContentRunCreateRequest
data_changes: []
---

# 背景与现状

当前已实现前端页面的主业务交互均通过 generated Client 接入 FastAPI 与真实 PostgreSQL/Job 链路，但全面审计仍确认若干最终用户可见的可靠性缺口：全局身份/通知失败态被误显示为正常状态、共享车型目录失败后无法就地恢复、词包创建由多个 HTTP 写请求拼成非原子动作、管理员配置资源读取互相连坐、审计历史只能读取最近记录、Historical Campaign Retry 资格由截断明细推算、表单存在静默无效点击，以及 Browser Mock 允许未声明 API 请求失败仍保持绿色。

用户已经明确批准本 Change 继续使用固定 Development Identity，并明确排除付费采集预算/限额/熔断。用户随后明确要求：AI 批量打标不能只开放 `selected <= 1000`，必须支持对当前系统中的全部数据发起正式打标 Run。该决定覆盖旧文档中“query/all scope 暂不开放”的限制。

# 目标

- 让当前用户可见错误状态明确、可恢复，不把请求失败伪装成业务空状态或普通用户状态；
- 让“新建关键词包”成为一个 HTTP 请求、一个 PostgreSQL transaction 的原子动作，同时保持既有空词包创建和单条追加兼容；
- 让管理员配置各资源独立加载/失败/重试；
- 让审计历史可分页读取全部记录，不引入任意 JSON 正文搜索；
- 让 Historical Campaign 的 Retry 资格由完整 PostgreSQL 事实返回；
- 让 AI Analysis Run 同时支持“选中数据”与“全部数据”两种正式 Scope；全部数据由数据库侧计数和 Planner 分批冻结/分片，不把全量 ID 放进 HTTP Payload 或浏览器内存；
- 让 Browser Mock 对未声明 `/api/v1/**` 请求 fail-closed，并增加功能性黑盒与真实 Full-stack 证明；
- 保持数据库 Schema、Migration、固定开发身份和 Provider 行为不变。

# 范围

Included：Identity/Notification 错误恢复、VehicleMultiSelect 重试、Keyword Pack 原子创建、Admin 独立资源状态、Audit 分页、Historical Campaign Retry capability、AI selected/all Run Scope、表单校验、Browser Mock fail-closed、相关 Contract/generated Client、Backend/API/PostgreSQL/Full-stack 测试及必要长期文档同步。

Excluded：飞书/真实身份认证、采集预算/限额/熔断、任意复杂筛选/query-expression Run、Provider endpoint/参数/字段/价格、Schema/Migration、依赖/Runtime 升级、无关页面视觉重构。

# 必须保持不变

- `DevelopmentIdentityResolver` 继续作为当前默认身份；本 Change 不新增认证 Provider 或真实用户模型；
- Vue/FastAPI/PostgreSQL/Python/Node 与直接依赖版本不升级；
- generated Client 只能由 OpenAPI + Orval 重新生成，不手改；
- PostgreSQL 18 仍是唯一业务事实库；表 Owner 不变化；
- Historical Item 明细继续保持有界返回，Retry 资格改为独立聚合事实而不是解除明细上限；
- Existing Keyword Pack API 调用仍兼容不传初始关键词；单条 `add keyword` API 保留；
- AI `selected` 模式保留现有最多 1000 个显式 ID 的防护；新增 `all` 模式不传 ID，由后端对当前全部 Content Current 事实计数并在 Planner 内有界冻结/分片；
- 全量打标不在 HTTP 请求内同步执行，不创建一个包含全部 Content ID 的超大 Payload，也不绕过现有 PostgreSQL durable Job Runtime；
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

- AI 全量打标方案 A（采用）：`AnalysisRunTargetSelection` 增加显式 `scope=selected|all`。`selected` 保持 1—1000 个 `content_ids`；`all` 禁止提交 `content_ids`。Preview 对 `all` 使用数据库 `COUNT`，Create 只保存 Run 头 + Planner Job；Planner 按数据库稳定顺序分批冻结 `content_id + current_version` 并维持现有有界 Shard Job 窗口。
- AI 全量打标方案 B（不采用）：前端先翻页拿到全部 ID 再调用 selected。会放大浏览器内存、HTTP Payload 和竞态窗口，无法支撑大数据量。
- AI 全量打标方案 C（不采用）：一个 Job 直接扫描并调用 LLM 直到完成。会绕过现有 Planner/Sharding、取消/进度/重试边界，不利于大数据量长期演进。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 保留固定开发身份，但身份/通知失败必须显式且可重试 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | Identity Store 拆分 principal/notification error；AppShell 与 NotificationInbox 显式错误/重试；CI #3811 Frontend Unit 18 files/87 tests 与 Browser Mock 48/48 通过 |
| R2 | VehicleMultiSelect 失败后可就地重试 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | 共享 VehicleMultiSelect 增加 Error + Retry 状态；CI #3811 Frontend Unit 与 Browser Mock 通过 |
| R3 | Keyword Pack + 初始关键词原子创建且旧调用兼容 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | `KeywordPackCreateRequest.keywords` 向后兼容扩展；同一 PostgreSQL transaction 创建 Pack/Keyword/Item/Audit；事务后重读版本；CI #3811 Contract/API/PostgreSQL/Real Full-stack 全部通过 |
| R4 | Admin 四类资源独立加载与错误恢复 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | Admin 车型/词包/Scheme/Audit 独立状态和重试，不再 Promise.all 连坐；Browser Mock `frontend-reliability` 通过 |
| R5 | Audit 支持完整历史分页 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | Audit `offset/limit` + `total/offset/limit` Contract 与 UI 翻页已接通；CI #3811 Contract/PostgreSQL/Browser/Real Full-stack 通过 |
| R6 | Campaign Retry 资格来自完整失败 Chunk 聚合 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | `HistoricalCampaignResponse` 返回完整失败 Chunk/retry capability；Browser Mock 已证明即使前 200 明细不含失败 Chunk 仍可正确 Retry；PostgreSQL/Real Full-stack 通过 |
| R7 | 管理员车型必填字段无静默点击 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | 必填字段禁用/校验反馈已落地；Frontend Unit/Browser Mock 通过 |
| R8 | Browser Mock 未声明 API fail-closed | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | 全局 `/api/v1/**` 未声明请求改为测试失败；补齐 Shell/通知等基础 Mock 并修正通知真实 PUT 契约；CI #3811 Browser Mock 48/48 通过 |
| R9 | AI 批量打标支持全部数据，同时保留 selected 模式 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | satisfied | `selected` 1—1000 保持兼容；`all` 无 ID Payload，数据库 COUNT、10,000 条批次冻结、Shard 调度、目标漂移 fail-closed；覆盖 irrelevant；历史空 query 保持 query；异常路径不做海量 DELETE；CI #3811 Unit/Contract/API/PostgreSQL/Browser/Real Full-stack 全部通过 |
| R10 | 增加高价值功能黑盒与真实 Full-stack 证据并完成 main 交付 | https://github.com/dingyuwen777/AIMA_UGC/issues/314 | explicitly_deferred | PR current-head `2eb6bcb61ae700f8d3db8439949820dfd6b20a24` 的 CI #3811、Runtime Acceptance #932、Developer Tooling #325 已通过；PR merge、main fresh CI/Runtime、Change 归档、Issue 关闭和分支清理必须在 Ready/merge 生命周期后执行，将在独立归档 PR 中补为 satisfied |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Frontend Unit | required | CI #3811：Vitest 18 files / 87 tests passed；覆盖 Identity/Notification error、Vehicle retry、Admin partial failure、AI selected/all、表单/Store Contract |
| Browser Mock Acceptance | required | CI #3811：Playwright 48/48 passed；unexpected `/api/v1/**` fail-closed；覆盖错误/重试/Audit 翻页/Campaign Retry/AI all；采集策略 Figma 几何在正式 CJK 字体环境通过 |
| Backend/API/PostgreSQL Integration | required | CI #3811：Unit 765、Contract 101、API 51 全通过；PostgreSQL Integration job 全部步骤成功，覆盖原子词包、Audit、Retry capability、all count/freeze/sharding 与 Review 回归 |
| Contract / Generated Client | required | CI #3811 重新生成 OpenAPI + Orval 后 `git diff --exit-code` 为零，兼容检查通过 |
| Real Full-stack Golden Path | required | CI #3811 `Real Full-stack Golden Path / Excel Browser Full-stack` job success；Browser → real API → PostgreSQL/Worker 覆盖本 Change 高价值链路 |
| Real Provider Probe | not_applicable | Provider endpoint、参数、分页、字段、价格语义均未修改，不执行真实付费 Probe |
| Build / Runtime / Security | required | CI #3811 lint/typecheck/build/Wheel/npm audit 0 vulnerabilities；Runtime Acceptance #932 success；Developer Tooling #325 success |
| Docs / Governance / Review | required | CI #3811 Docs and Governance success；Blueprint/AI Appendix/Frontend README 已同步；两阶段 L3 Review Finding 已修复并完成 re-review |

# 实施步骤

- [x] 恢复 main、目标项目规则、Agent_Skills canonical Source Mode 与相关 Blueprint/Contract/Owner 事实。
- [x] 创建 Requirement Issue #314、L3 分支与本 Active Change。
- [x] 用户追加批准 AI “全部数据”批量打标，更新 Scope、Contract 方案与验收矩阵。
- [x] Red：为审计缺陷和新增能力建立可失败的前端/后端/黑盒回归，确认旧实现缺口；Review 新增 Finding 也先取得行为 Red。
- [x] Green：实现最小兼容 Contract、Service/Repository/Planner 与前端恢复行为。
- [x] 重新生成 OpenAPI/generated Client；generated drift 为零。
- [x] 增加/调整 Browser Mock fail-closed 基线和真实 Full-stack specs。
- [x] 运行目标测试、相关回归、PostgreSQL Integration、Contract drift、Real Full-stack、Build/Runtime/Security；current-head `2eb6bcb61ae700f8d3db8439949820dfd6b20a24` 已取得新鲜成功证据。
- [x] 同步长期文档并执行 Completion Audit。
- [x] 读取 canonical Review 规则，执行两阶段独立 Review；Finding 修复后重新验证。
- [ ] PR current-head Completion Gate 通过后按用户既有授权转 Ready 并受保护合并。
- [ ] main fresh CI/Runtime 成功后用独立归档 PR 移入 `changes/archive/2026-09/`，关闭 Issue #314 并清理已合并分支。

# 两阶段 Review 结论

第一阶段 L3 Review 发现并修复：`all` Scope 不能复用声音广场默认相关性过滤；历史空 `query` 快照不能被重解释为 `all`；全量 Planner 不能回退到一次事务全量冻结；Keyword Pack 创建/追加后的响应与审计版本必须读取事务后真实版本；Browser Mock 通知读状态必须匹配真实 PUT Contract。对应永久回归已进入仓库，并由 PostgreSQL/Browser CI 重新证明。

第二阶段 re-review 发现并修复：`all` 目标漂移/取消异常路径不能用一次大 `DELETE` 清理已经分批冻结的海量 Run Target；现在终态 Run 保留已提交的 Run-local Target 且不创建 Shard，Run 统计仍按 `target_count - 已调度 items` 收敛。另定位跨前后端 CI 安装 Noto CJK 后导致采集策略 2—6px 几何漂移，改为显式 line-height；同一 3 条 Figma 几何测试已在“无额外 Noto CJK”和“安装 Noto CJK”两种环境均 3/3 通过，正式 CI #3811 的 48 条 Browser Mock 也全部通过。

最终 re-review 未发现仍需阻断 Ready 的功能性 Finding。已知证据边界：`all` Planner 的单 Attempt timeout 仍为 1800 秒，当前验证证明了批次事务、恢复点、目标一致性和真实小规模 Full-stack 行为，但**没有执行 4000 万级数据量性能/时延压测**，因此本 Change 不宣称已验证该规模下的 Planner 吞吐或 30 分钟内完成目标冻结；这属于容量验证边界，不改变本轮公开 API 与功能正确性结论。

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取 Issue #314、main `118181c5e5ba0b31f3827d6ae5443c631d89ac40`、PR #315/current head `2eb6bcb61ae700f8d3db8439949820dfd6b20a24`、相关 Contract/Repository/Job Runtime、当前 Active Change 与 required Workflow 结果；Requirement Source 未漂移。
- [x] change_coverage：R1–R9 均有实现和新鲜验证证据；R10 只把必须发生在 Ready/merge 之后的 main fresh/归档生命周期显式 deferred，不存在隐藏的未满足功能项；固定 Development Identity 与付费采集预算边界按用户明确决定保持不变。
- [x] reverse_audit：从 Identity/通知、车型选择、关键词包、Admin/Audit、Historical Campaign、声音广场 AI all 交互反查 generated Client → FastAPI Contract/Bootstrap → Service/Repository → PostgreSQL/Job；并从新增/扩展 Contract 反查 generated consumer、Frontend Store/UI、Unit/Browser/PostgreSQL/Full-stack 测试。L3 Review 发现的 all 语义、版本一致性、Mock 契约和异常路径有界性均已修复。
- [x] unresolved_cleared：required Validation Matrix 已由 current-head CI #3811、Runtime Acceptance #932、Developer Tooling #325 新鲜通过；Real Provider Probe 因 Provider 契约未变化为 not_applicable。4000 万级性能压测未执行且未被宣称为已验证；其容量边界已显式记录，不作为功能正确性证据。

# 兼容、部署与回滚

本 Change 只做向后兼容 HTTP 字段扩展和前端/Planner 行为修复，不做 Schema/Migration、依赖升级或部署拓扑变化。旧客户端不提交 `keywords` 仍可创建空词包；AI selected 调用保持原上限和语义；新增 `all` scope 是显式新能力。新增 Response 字段不改变现有字段含义。回滚可恢复旧 Contract/Service/Frontend/Planner，不需要数据库迁移回滚，但会重新引入半成品词包、审计截断、Retry 资格推断和无法全量打标等已知缺陷，因此只应在新实现出现阻塞缺陷时通过正式回滚决定执行。