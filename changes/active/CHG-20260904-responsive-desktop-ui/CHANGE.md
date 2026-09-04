---
schema: coding-change/v1
id: CHG-20260904-responsive-desktop-ui
title: 桌面端响应式 Typography Density Layout 体系
level: L2
status: in_progress
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
5. 复用现有 Playwright，增加 1180/1280/1440/1600/1920/2560 代表性 viewport 的 overflow/reflow 回归；保留 1440 正式几何测试。
6. 同步 `frontend/README.md` 与 Figma/前端开发 Guide 的长期响应式规则。

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
| R1 | 1440 保持正式视觉锚点，同时建立桌面端统一响应式规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待实现与多 viewport Browser Evidence |
| R2 | 建立 Semantic Typography / Density / Layout Token，并由 AppShell/Shared UI 消费 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待代码与组件回归 |
| R3 | 1180/1280 不通过缩小字体解决空间问题，使用 reflow/wrap/local scroll；普通页面无非预期整页横滚 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待 Responsive Playwright Evidence |
| R4 | 1600/1920/2560 适度增加字号/留白并有最大值，超宽页面控制内容宽度 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待 computed style / geometry Evidence |
| R5 | 主要 9–10px 业务/操作文字提升到 semantic caption/body-small，Drawer/Dialog 不超 viewport | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待 Browser/Style Evidence |
| R6 | 无 Backend/Contract/Schema/Migration/generated/依赖变化，现有功能回归、Build、Docs/CI 完整通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | pending | 待 diff/CI/Review Evidence |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Shared UI 与现有前端单测回归；不复制视觉规则到业务逻辑测试 |
| 接口 / Contract | not_applicable | 本 Change 不改变 HTTP/OpenAPI/generated client/public data contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改变 Backend、PostgreSQL、Worker 或持久化语义 |
| 用户 / Workflow Acceptance | required | Playwright 覆盖当前正式路由在代表性 viewport 的 overflow/reflow/关键操作可见性 |
| 跨组件 Golden Path | not_applicable | CSS/Layout 不改变前后端真实接线；保留现有 Golden Path，不把 skipped 冒充通过 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub、LLM 或其他外部 Provider |
| Build / Package / Runtime | required | lint、typecheck、unit、production build、相关/全量 frontend e2e |
| Docs / Governance | required | frontend README、Figma/前端 Guide、Change/Requirement/Completion Gate 与 CI |

# User Journey / Black-box Matrix

| 场景 | 预期 | 证据 |
| --- | --- | --- |
| J1 小桌面 1180/1280 | 页面不靠缩小文字塞内容；筛选/工具栏可换行，普通页面无整页横滚 | 待 Playwright |
| J2 标准 1440 | 正式设计关键 geometry 与用户任务保持 | 现有 Figma geometry/design specs + 新回归 |
| J3 大屏 1920/2560 | Semantic 字号/留白适度增加且达到上限，内容不无限拉宽 | 待 computed style + Browser geometry |
| J4 表格/Overlay | 表格必要时局部横滚；Drawer/Dialog 宽度不超过 viewport safe margin | 待 Playwright |
| J5 功能回归 | Voice Plaza / Collection Strategy / Collection Runtime / Admin 功能与状态语义不变 | 现有 e2e + CI |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取 Issue #337 与当前 main。
- [ ] change_coverage：R1—R6 全部映射到实现与新鲜证据。
- [ ] reverse_audit：确认无 Backend/Contract/Schema/Migration/generated/依赖或无关重构进入 diff。
- [ ] unresolved_cleared：Review/Test Findings 已修复或明确不存在阻塞项。
