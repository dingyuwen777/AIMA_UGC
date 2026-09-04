---
schema: coding-change/v1
id: CHG-20260904-responsive-desktop-ui
title: 桌面端响应式 Typography Density Layout 体系
level: L2
status: ready_for_review
owner: chatgpt
branch: feature/337-responsive-desktop-ui
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - app-shell
  - shared-ui
  - voice-plaza
  - collection-strategy
  - collection-runtime
  - admin-configuration
  - documentation
affected_paths:
  - frontend/src/shared/styles/
  - frontend/src/shared/ui/
  - frontend/src/app/layouts/AppShell.vue
  - frontend/src/features/voice-plaza/
  - frontend/src/features/collection-strategy/
  - frontend/src/features/import-batches/
  - frontend/src/features/admin-configuration/
  - frontend/e2e/
  - frontend/README.md
  - docs/guides/01_Figma与前端设计开发工作流.md
contracts: []
data_changes: []
---

# 目标

在保持 AIMA_UGC 当前 Vue/Pinia/Element Plus/OpenAPI generated client 与全部后端业务行为不变的前提下，建立以 1440×900 为正式视觉锚点的桌面端响应式设计体系，使小桌面通过 reflow/wrap/local scroll 保持可读性，大屏通过有边界的字体、留白和内容宽度调整提升信息层级，而不是整页等比例缩放。

本 Change 的 Requirement Source 为 GitHub Issue #337；本文件只承担施工、验证和完成门禁。

# 当前事实与已确认决定

- 当前全局 `tokens.css` 已有 Color/Spacing/Layout Token，但没有 Semantic Typography / Responsive Density Token。
- `AppShell.vue` 当前存在 `min-width: 1180px`，Sidebar/Topbar/Workspace 大量使用固定 px。
- Voice Plaza、Admin Configuration 等当前存在 9–10px 的辅助或操作文本；主要页面只存在零散 layout breakpoint，没有统一字体缩放策略。
- Voice Plaza 与 Collection Strategy 已有 1440×900 正式 Figma/Playwright 几何基线；1440 继续作为视觉锚点，生产实现不能写死整页宽高。
- 本 Change 只做桌面端自适应，不扩展成完整 Mobile 重构。
- 不修改 Backend、PostgreSQL、Schema/Migration、HTTP Contract、OpenAPI/generated client、业务 Store/API 语义，不升级或新增前端依赖。

# 范围

1. 在 `shared/styles` 建立 Semantic Typography、Density、Responsive Layout Token，并提供统一桌面响应式规则。
2. AppShell 去除强制整页最小宽度，改为可收缩 Workspace、受控内容最大宽度、窄桌面 reflow 与大屏有界留白。
3. AimaPageHeader、AimaButton、AimaFeedbackBanner 等 Shared UI 消费 Semantic Token。
4. 当前正式页面的主要 9–10px 文本、Filter/Toolbar、Table 容器、Drawer/Dialog 通过统一规则收口，不创建第二套页面级响应式体系。
5. 复用现有 Playwright，增加 1180/1280/1440/1600/1920/2560 代表性 viewport 的 overflow/reflow 回归；保留 1440 正式几何测试，并对 Voice Plaza、Collection Runtime、Admin Configuration 做 Compact Desktop 黑盒回归。
6. 由 `frontend/src/shared/styles/README.md` 维护精确响应式代码规则；对 `frontend/README.md` 与 `docs/guides/01_Figma与前端设计开发工作流.md` 做 targeted re-review，只有当前说明与实现冲突时才修改，避免复制第二套 breakpoint/字号事实。

# 非目标

- 不做完整手机/平板信息架构与导航重构。
- 不修改页面业务流程、Store、Feature API、generated client 或服务端行为。
- 不引入 Tailwind、CSS-in-JS、Cypress、视觉测试 SaaS、JS 缩放库等新技术体系。
- 不升级 Vue、Vite、Element Plus、Playwright、Node/npm。
- 不因为本次响应式改造重写现有 Figma 页面业务结构或创建伪路由/伪数据。

# 必须保持不变

- 1440×900 正式页面关键几何关系和当前用户任务入口。
- 当前路由、AppShell 导航身份与权限语义。
- Page → Store/local state → Feature api.ts → generated client → FastAPI 调用链。
- Loading / Empty / Error / Disabled / Drawer / Dialog 等已批准状态语义。
- 现有 Backend/Contract/Schema/Migration/Provider/Analysis/Collection 业务规则。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 1440 保持正式视觉锚点，同时建立桌面端统一响应式规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | PR #338 当前实现保留既有 1440 Figma geometry/design tests；CI run 33832938209 的 Repository Quality job 100901820665 中相关 1440 geometry 与新 baseline-1440 Browser 回归均通过。 |
| R2 | 建立 Semantic Typography / Density / Layout Token，并由 AppShell/Shared UI 消费 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `tokens.css` 新增 semantic typography/density/layout tokens，`AppShell.vue`、`AimaPageHeader.vue`、`AimaButton.vue`、`AimaFeedbackBanner.vue` 与 `responsive.css` 统一消费；同一 CI 的 lint/typecheck/unit/build 全部通过。 |
| R3 | 1180/1280 不通过缩小字体解决空间问题，使用 reflow/wrap/local scroll；普通页面无非预期整页横滚 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `responsive-layout.spec.ts` 的 compact-1180 与 compact-1280 用例在四个正式页面检查 AppShell/workspace/整页 overflow、Filter reflow、表格局部滚动与 Admin 单列；CI run 33832938209 通过。 |
| R4 | 1600/1920/2560 适度增加字号/留白并有最大值，超宽页面控制内容宽度 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | large-1600、wide-1920、wide-2560 Browser 回归通过；独立 typography 用例验证 1440 标题锚点、1920 增长、2560 上限及超宽 workspace 约束。 |
| R5 | 主要 9–10px 业务/操作文字提升到 semantic caption/body-small，Drawer/Dialog 不超 viewport | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | Browser computed-style 断言覆盖 Voice Plaza 告警、Admin 词包/Provider 辅助文本；真实关键词包 Dialog 在 560px 窄窗口验证 viewport safe margin；CI run 33832938209 全部通过。 |
| R6 | 无 Backend/Contract/Schema/Migration/generated/依赖变化，现有功能回归、Build、Docs/CI 完整通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `main@cb8ef5645eed38036bdaabd56b9229c1d45f2e03...427533449b3986f877c175d34a50134d00c684ee` 反向 diff 仅包含 10 个 Change/Frontend 文件；Runtime Acceptance run 33832937916 成功；CI run 33832938209 中 Docs/Governance、npm audit、lint、typecheck、22 files/100 Vitest、production build、59/59 Playwright 与 CI Gate 全部通过。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | CI run 33832938209：22 个 Vitest 文件、100 个测试全部通过；Shared UI 与现有 Feature 行为回归未失败。 |
| 接口 / Contract | not_applicable | 本 Change 不改变 HTTP/OpenAPI/generated client/public data contract；反向 diff 未包含对应路径。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改变 Backend、PostgreSQL、Worker 或持久化语义；CI 按 frontend-only 正确跳过 PostgreSQL Integration。 |
| 用户 / Workflow Acceptance | required | CI run 33832938209：59/59 Playwright 通过，新增六档 viewport、四正式页面、局部滚动、Admin reflow、Dialog safe margin、Typography computed-style 回归。 |
| 跨组件 Golden Path | not_applicable | CSS/Layout 不改变前后端真实接线；Real Full-stack Golden Path 在 frontend-only scope 正确跳过，不把 skipped 冒充通过。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub、LLM 或其他外部 Provider；未执行 Provider Probe。 |
| Build / Package / Runtime | required | npm audit 0 vulnerabilities；lint、typecheck、production build、Playwright 在 CI run 33832938209 当前实现 HEAD 上新鲜通过；Runtime Acceptance run 33832937916 成功。 |
| Docs / Governance | required | `frontend/src/shared/styles/README.md` 成为精确规则 Owner；frontend README/Figma Guide targeted re-review 后保持现有职责；Docs/Governance 与 CI Gate 均通过。 |

# User Journey / Black-box Matrix

| 场景 | 预期 | 证据 |
| --- | --- | --- |
| J1 小桌面 1180/1280 | 页面不靠缩小文字塞内容；筛选/工具栏可换行，普通页面无整页横滚 | `responsive-layout.spec.ts` compact-1180/compact-1280 在 CI run 33832938209 通过。 |
| J2 标准 1440 | 正式设计关键 geometry 与用户任务保持 | 既有 Collection Strategy/Voice Plaza Figma geometry/design specs 与新 baseline-1440 回归同时通过。 |
| J3 大屏 1920/2560 | Semantic 字号/留白适度增加且达到上限，内容不无限拉宽 | wide-1920/wide-2560 与 typography bounds 用例通过。 |
| J4 表格/Overlay | 表格必要时局部横滚；Drawer/Dialog 宽度不超过 viewport safe margin | 表格 `overflow-x:auto` 断言与 560px 真实 Dialog safe-margin 用例通过。 |
| J5 功能回归 | Voice Plaza / Collection Strategy / Collection Runtime / Admin 功能与状态语义不变 | 全量 59/59 Playwright、100/100 Vitest、production build 通过；现有 1440 设计测试保持绿色。 |

# Docs Impact

Docs Impact：targeted。

- `frontend/src/shared/styles/README.md` 是本次新增的响应式代码规则 Owner，解释 token、viewport 档位、reflow/overflow/Overlay 与验证责任。
- `frontend/README.md` 当前仍正确描述 Page/Store/API/generated client 和前端修改导航，不应复制第二套字号或 breakpoint 数值。
- `docs/guides/01_Figma与前端设计开发工作流.md` 已明确 Shared Styles/Shared UI 的视觉 Owner，以及 `1440×900` 只是桌面参考 Viewport、生产代码不得写死页面宽高；本次没有改变该职责边界，因此 targeted re-review 后无需为了产生文档 diff 重写现有 Guide。

# Completion Audit

- [x] upstream_re_read：完成前重新读取 Issue #337，并确认当前 `main` 仍为 `cb8ef5645eed38036bdaabd56b9229c1d45f2e03`。
- [x] change_coverage：R1—R6 已全部映射到当前实现与 CI run 33832938209 / Runtime Acceptance run 33832937916 的新鲜证据。
- [x] reverse_audit：确认 `main@cb8ef5645eed38036bdaabd56b9229c1d45f2e03...427533449b3986f877c175d34a50134d00c684ee` 仅含 10 个 Change/Frontend 文件，无 Backend/Contract/Schema/Migration/generated/依赖或无关重构进入 diff。
- [x] unresolved_cleared：已修复 scoped CSS specificity、Admin reflow、table overflow、small-button 1440 baseline、Provider 新增小字号与响应式测试夹具问题；最终 Standard re-review 在当前范围内无 BLOCKER/HIGH/重要 MEDIUM Finding。