---
schema: coding-change/v1
id: CHG-20260907-admin-config-business-view
title: 管理员配置业务化展示与技术详情收敛
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feat/admin-config-business-view
created: 2026-09-07
updated: 2026-09-07
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - tests
affected_paths:
  - frontend/src/features/admin-configuration/
  - frontend/tests/
  - frontend/e2e/
  - changes/active/CHG-20260907-admin-config-business-view/CHANGE.md
contracts: []
data_changes: []
---

# 变更摘要

- **要解决的问题**：管理员配置与操作记录把 `event_type`、内部对象 ID、`request_id`、revision、JSON、并发/RPS 等实现细节放在默认阅读路径，影响非研发管理员理解和操作。
- **修改方式**：调整为“默认业务视图 + 按需高级设置/技术详情”；保留所有原始审计事实、Secret 保存语义、高级参数与现有编辑能力。
- **边界**：只修改前端展示、展示辅助逻辑和相关测试；不修改后端、数据库、OpenAPI、generated client、Provider/Analysis Scheme 保存语义或依赖版本。

# 背景、现状与问题

Issue #378 明确要求管理员界面面向实际使用者，而不是把后端字段和运行实现当成主信息。当前操作记录直接展示原始审计 token/ID/JSON；模型服务与 AI 分析规则又默认突出 revision、请求参数、Hash、Prompt 等信息。它们对排障和追溯仍有价值，因此正确边界不是删除，而是把技术事实移入按需展开区域。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑的决策 |
| --- | --- | --- | --- |
| E1 | Audit API 返回 `event_type`、`object_type/object_id`、`actor_ref`、`safe_detail`、`request_id`、`created_at` | generated `AuditEventResponse` 与现有页面调用 | 默认业务视图可做展示映射，但原始字段必须保留 |
| E2 | Provider 表单仍需要服务地址、密钥、模型、超时、重试、并发和 RPS 等现有配置能力 | `ProviderConfigurationPanel.vue` | 产品化只能重排层级，不能删除配置能力 |
| E3 | Analysis Scheme 仍需要业务状态、Prompt/JSON 与版本信息 | `AdminConfigurationPage.vue` | 默认突出业务状态，Prompt/版本进入高级区域 |
| E4 | Issue #378 明确禁止修改 backend、DB、OpenAPI、generated client 与依赖 | #378 | 本 Change 限定为前端展示和测试 |

# 目标、成功标准与非目标

## 目标

让管理员默认看到“这是什么、当前状态、做了什么、影响什么”，只有排障或深度配置时才展开实现细节。

## 成功标准

- [x] 操作记录默认显示时间、操作人、业务动作、影响对象和说明；原始审计事实可从“技术详情”查看。
- [x] AI 模型/TikHub 默认显示常用配置；超时、重试、并发、RPS 进入“高级设置”，内部 ID/revision 进入“技术信息”。
- [x] AI 分析规则默认突出业务状态，Prompt/JSON/版本等进入按需高级区域；能力不删除。
- [x] 未识别审计 token 使用保守业务兜底，不根据 `safe_detail` 猜测语义，原始 token 仍可追溯。
- [x] 生产实现没有 backend、Contract、generated client、Schema/Migration 或依赖版本变化。

## 非目标

- 不重新设计整个后台或引入新 UI 框架。
- 不修改审计写入语义、Provider 保存 Contract 或 Analysis Scheme 保存语义。
- 不隐藏或删除排障所需原始事实；只改变默认信息层级。
- 不触碰独立施工线 PR #382。

# 修改方案与决策依据

1. 新增纯展示映射层 `presentation.ts`，只把已知状态/审计 token 翻译为业务文案；未知 token 一律使用保守兜底。
2. `AdminConfigurationPage.vue` 把审计表重排为业务列，把原始字段和 JSON 收入每行“技术详情”；把 AI 分析规则的 Prompt/JSON/版本信息移入按需高级区域。
3. `ProviderConfigurationPanel.vue` 把地址、模型、密钥等常用字段留在主界面，把超时/重试/并发/RPS 放入“高级设置”，内部 ID/revision 放入“技术信息”。
4. 用 Vitest 覆盖业务映射、未知值兜底和设计回归；用 Playwright Browser Mock 覆盖操作记录技术详情、分页和多 viewport 管理员界面。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 操作记录默认业务化，原始审计事实仍可在技术详情查看，未知事件不丢原始事实 | #378 / AC1 | satisfied | `presentation.ts` 保守映射；`AdminConfigurationPage.vue` 默认业务列 + 折叠技术详情；`frontend-reliability.spec.ts` 验证未知事件默认不暴露 raw token、展开后可查看并可翻页 |
| R2 | AI 服务不默认突出请求参数/revision，同时保持读取、编辑、保存语义 | #378 / AC2 | satisfied | `ProviderConfigurationPanel.vue` 常用字段主视图 + 高级设置 + 技术信息；现有 store/API 未改；相关设计/并发配置测试与 Browser Mock 覆盖 |
| R3 | AI 分析规则默认突出业务状态，Hash/Run/Shard/Prompt/Taxonomy 等实现信息按需展示且能力不删除 | #378 / AC3 | satisfied | `AdminConfigurationPage.vue` 业务状态卡 + 高级规则编辑；展示映射统一为“AI 分析规则”；相关设计回归测试覆盖 |
| R4 | 后端、OpenAPI、generated client 和依赖无变更，前端质量与用户场景验证通过 | #378 / AC4 | satisfied | PR diff 限于前端、测试与本 Change；此前同分支 lint、113 个 Vitest、TypeScript/Vue build 已通过；最终同-SHA GitHub CI 与 Runtime Acceptance 保留为合并硬门禁 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 展示逻辑 / 单元 | required | `admin-configuration-presentation.spec.ts`、设计与回归 tests |
| 类型与构建 | required | CI 执行 `npm --prefix frontend run build`，包含当前 TypeScript/Vue 与 Vite 构建门禁 |
| 用户 / 工作流验收 | required | `frontend-reliability.spec.ts` 验证操作记录默认视图、技术详情与分页；`responsive-layout.spec.ts` 验证多 viewport 业务化界面与高级设置可读性 |
| 接口 / 契约 | not_applicable | 不修改 backend/OpenAPI/generated client；PR diff 审计确认 |
| 数据 / Migration | not_applicable | 不修改数据库、持久化结构或迁移 |
| 外部 Provider 探测 | not_applicable | 不改变 TikHub/LLM 外部调用语义，不执行付费 Probe |
| 治理 / Review | required | Issue #378、当前 Change、两阶段 Review、同 SHA PR CI |

## 验证命令

- `npm --prefix frontend run lint`
- `npm --prefix frontend run test -- --run`
- `npm --prefix frontend run build`
- `npm --prefix frontend run test:e2e`
- `python3 scripts/quality/check_change_completion.py --root . --require-active-ready`

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理方式 |
| --- | --- | --- |
| 主要风险 | 业务文案映射错误或技术事实被误隐藏 | 已知 token 显式映射；未知值保守兜底；raw 字段始终保留在技术详情 |
| 兼容性 | 保持 | Store、generated API、保存 payload 与 Secret 行为不改 |
| 数据 / Migration | 不适用 | 无 Schema/Migration/数据转换 |
| 依赖 / Runtime | 不变 | 不升级或新增 npm/runtime 依赖 |
| 部署 | 仅需既有前端发布流程 | 无配置、Compose、后端或数据库部署变化 |
| 回滚 | 可直接回退本 PR | 没有不可逆数据或迁移副作用 |

# 文档影响

正式 Blueprint/Contract/部署说明不需要修改：本次不改变业务能力、接口、数据模型、部署或开发入口。用户可见信息层级由代码、Issue #378、本 Change 和验收测试承载，避免为纯展示措辞制造长期文档双写。

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #378、项目 AGENTS/前端规则、相关 Blueprint、当前管理员实现、generated Audit 类型、CI 与 Agent_Skills Review 规则，完成定义来自上游需求而不是当前实现。
- [x] change_coverage：已逐项把 AC1-AC4 反查到展示层、两个页面组件、单元/设计测试与 Browser Mock，未把技术信息从系统中删除。
- [x] reverse_audit：已从审计 raw 字段、Provider 高级参数、Analysis Scheme 高级字段反向检查默认视图和展开路径；backend/generated/DB/依赖均保持边界外。
- [x] unresolved_cleared：实现范围内未保留已知功能缺口；最新改动将以最终同-SHA Runtime Acceptance 与完整 CI 作为正常合并硬门禁。

# 两阶段 Review

- **阶段 1：需求与风险重建**：以 #378 AC1-AC4 为唯一完成定义，重点风险是删除能力、误译未知事件、泄漏 Secret/Prompt、破坏保存语义或让技术信息不可追溯。
- **阶段 2：证据对照**：逐文件检查展示映射、Provider 表单、管理员页面和测试。未知事件仍保留 raw token；高级参数/Prompt/JSON/revision 仍可访问；Store/API/generated client 未改。最终同-SHA CI 通过后才允许合并。

# 已取得的测试证据

- 分支中间 HEAD 的前端门禁已实际跑到：ESLint 通过、Vitest 23 files / 113 tests 通过、TypeScript/Vue 类型检查与 Vite production build 通过。
- Browser Mock 的中间失败均定位为测试仍引用旧文案/旧展开前提；对应断言已改为“操作记录”“词包关联”以及先展开“高级设置”后验证辅助文字，不通过恢复旧工程术语规避测试。
- Runtime Acceptance 在最近多个实现 HEAD 上成功；最终证据必须重新覆盖本 Change 与最后一次术语/Browser Mock 修正后的同一 HEAD。
