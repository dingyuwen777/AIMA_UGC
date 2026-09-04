---
schema: coding-change/v1
id: CHG-20260904-responsive-desktop-ui
title: 桌面端响应式 Typography Density Layout 体系
level: L2
status: done
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

- 原全局 `tokens.css` 已有 Color/Spacing/Layout Token，但没有 Semantic Typography / Responsive Density Token。
- 原 `AppShell.vue` 存在 `min-width: 1180px`，Sidebar/Topbar/Workspace 大量使用固定 px。
- Voice Plaza、Admin Configuration 等存在 9–10px 的辅助或操作文本；主要页面只有零散 layout breakpoint，没有统一字体缩放策略。
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
| R1 | #337 验收标准 1：1440×900 正式关键页面与已批准几何基线继续成立 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | Implementation PR #338 保留既有 1440 Figma geometry/design tests；PR final-head 与 `main@c67b08d224caa5b8c516c528db864efa558f3efe` 的 Browser 回归均通过。 |
| R2 | #337 验收标准 2：六个指定桌面 viewport 下正式页面无非预期整页横向溢出、关键操作遮挡或文字裁切 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `responsive-layout.spec.ts` 在 1180/1280/1440/1600/1920/2560 逐页检查 AppShell/workspace/document overflow、Filter reflow、表格局部滚动与 Admin/Provider 布局；PR 与 main-fresh CI 均通过。 |
| R3 | #337 验收标准 3：Page title / section title / body / control / caption 等统一通过 semantic token 表达 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `tokens.css` 建立 semantic typography/density/layout token；`AppShell.vue`、`AimaPageHeader.vue`、`AimaButton.vue`、`AimaFeedbackBanner.vue` 与 `responsive.css` 统一消费；lint/typecheck/unit/build 全绿。 |
| R4 | #337 验收标准 4：Voice Plaza、Admin、Collection Strategy、Collection Runtime 的主要 9–10px 业务文本提升到可读 semantic scale | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | Browser computed-style 断言覆盖 Voice Plaza 告警、Admin 词包/Provider 辅助文本；Playwright 59/59 通过。 |
| R5 | #337 验收标准 5：Drawer/Dialog 有 viewport 上限，窄桌面 filter/toolbars 正确 wrap/reflow，表格在自身容器滚动 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `.table-wrap overflow-x:auto`、1180 Admin/Provider 单列、filters reflow 与 560px 真实关键词包 Dialog safe-margin 均有 Browser 直接断言并通过。 |
| R6 | #337 验收标准 6：lint、typecheck、unit、相关 Playwright、production build 新鲜通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | PR final-head CI #4044 与 main-fresh CI #4045 均通过；main-fresh run `33836926044` 同一 commit 重跑后 npm audit、Repository Quality、Browser/Build 与 CI Gate 全部 success。 |
| R7 | #337 验收标准 7：Backend Contract/OpenAPI/generated client/Schema/Migration/依赖无变化 | https://github.com/dingyuwen777/AIMA_UGC/issues/337 | satisfied | `cb8ef5645eed38036bdaabd56b9229c1d45f2e03...c67b08d224caa5b8c516c528db864efa558f3efe` 仅 10 个预期 Change/Frontend 文件；无 backend、contracts/openapi、frontend/generated、Schema/Migration、manifest 或 lockfile 变化。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | PR 与 main-fresh CI：Vitest `22 files / 100 tests passed`；Shared UI 与现有 Feature 行为回归未失败。 |
| 接口 / Contract | not_applicable | 本 Change 不改变 HTTP/OpenAPI/generated client/public data contract；最终 compare 未包含对应路径。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改变 Backend、PostgreSQL、Worker 或持久化语义；CI 按 frontend-only 正确跳过 PostgreSQL Integration。Runtime Acceptance 仅作为运行时非回归证据。 |
| 用户 / Workflow Acceptance | required | Playwright `59 passed`，其中六档 viewport + 560px Dialog + typography bounds 八个响应式用例全部通过。Browser Mock 只证明 UI/请求边界，不宣称真实 Backend/DB。 |
| 跨组件 Golden Path | not_applicable | CSS/Layout 不改变前后端真实接线；Real Full-stack Golden Path 在 frontend-only scope 正确跳过。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub、LLM 或其他外部 Provider；未执行 Provider Probe。 |
| Build / Package / Runtime | required | npm audit `0 vulnerabilities`；lint、TS7/vue-tsc、production build 全部成功；Node 24.19.0 / npm 11.17.0 保持仓库锁定事实。 |
| Docs / Governance | required | `frontend/src/shared/styles/README.md` 成为精确规则 Owner；frontend README/Figma Guide targeted re-review 后保持现有职责；PR 与 main-fresh Docs/Governance、Completion Gate、CI Gate 均通过。 |

# User Journey / Black-box Matrix

| 场景 | 预期 | 证据 |
| --- | --- | --- |
| J1 小桌面 1180/1280 | 页面不靠缩小文字塞内容；筛选/工具栏可换行，普通页面无整页横滚 | `compact-1180` / `compact-1280` Browser 用例通过。 |
| J2 标准 1440 | 正式设计关键 geometry 与用户任务保持 | 既有 Collection Strategy/Voice Plaza Figma geometry/design specs 与 `baseline-1440` 同时通过。 |
| J3 大屏 1920/2560 | Semantic 字号/留白适度增加且达到上限，内容不无限拉宽 | `wide-1920` / `wide-2560` 与 typography bounds 用例通过。 |
| J4 表格/Overlay | 表格必要时局部横滚；Drawer/Dialog 宽度不超过 viewport safe margin | 表格 `overflow-x:auto` 与 560px Dialog safe-margin 用例通过。 |
| J5 功能回归 | Voice Plaza / Collection Strategy / Collection Runtime / Admin 功能与状态语义不变 | Vitest `100 passed`、Playwright `59 passed`、production build 成功。 |

# Docs Impact

Docs Impact：targeted。

- `frontend/src/shared/styles/README.md` 是响应式代码规则 Owner，解释 token、viewport 档位、reflow/overflow/Overlay 与验证责任。
- `frontend/README.md` 当前仍正确描述 Page/Store/API/generated client 和前端修改导航，不复制第二套字号或 breakpoint 数值。
- `docs/guides/01_Figma与前端设计开发工作流.md` 已明确 Shared Styles/Shared UI 的视觉 Owner，以及 `1440×900` 只是桌面参考 Viewport、生产代码不得写死页面宽高；本次没有改变该职责边界，因此 targeted re-review 后无需为了产生文档 diff 重写现有 Guide。

# Review / CI Evidence

- Requirement Source：GitHub Issue #337；merge 前重新读取，7 条验收标准语义未漂移。
- Implementation PR：#338，squash merge commit `c67b08d224caa5b8c516c528db864efa558f3efe`。
- reviewed_base_sha：`cb8ef5645eed38036bdaabd56b9229c1d45f2e03`。
- reviewed_head_sha：`b9293a0ec1917494b403381328479a1faeac64bd`；Targeted re-review 结论 `NO_FINDINGS_WITHIN_SCOPE`。
- PR final-head Completion Gate：#1922 / run `33835839686` success。
- PR final-head Runtime Acceptance：#1165 / run `33835839680` success。
- PR final-head CI：#4044 / run `33835839887`，Repository Quality、Docs and Governance、CI Gate 全部 success。
- main-fresh Completion Gate：#1923 / run `33836925810` success。
- main-fresh Runtime Acceptance：#1166 / run `33836925707` success。
- main-fresh CI：#4045 / run `33836926044`；首轮 Repository Quality 因 npm Registry advisories endpoint network timeout 失败，未修改代码/依赖/lockfile/CI；同一 `main@c67b08d224caa5b8c516c528db864efa558f3efe` 重跑 job `100912732195` 后 npm audit、Repository Quality、Browser/Build 全部 success，CI Gate job `100913993982` success。
- Unit/Component：Vitest `22 files / 100 tests passed`。
- Browser Mock Acceptance：Playwright `59 passed`；本 Change 八个 responsive/browser 用例全部通过。
- Build：lint、TS7/vue-tsc、Vite production build 成功。
- Security audit：成功运行报告 `0 vulnerabilities`；历史失败只来自 npm Registry 503/network timeout，未通过修改依赖、lockfile 或降低门禁换取绿色。
- Standard Review A1：从 #337 独立重建七条验收标准，与 R1—R7 一一对应，无 requirement omission。
- Standard Review A2 / Code Quality：最终 10-file diff 无 Backend/Contract/Schema/Migration/依赖变化；前序 scoped specificity、Admin reflow、table local scroll、1440 small-button geometry、Provider 小字号与 Browser fixture/locator Findings 均已修复；当前无 BLOCKER/HIGH/重要 MEDIUM Finding。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #337、最终 PR #338、当前 `main@c67b08d224caa5b8c516c528db864efa558f3efe` 与 main-fresh workflow evidence，独立重建完成定义。
- [x] change_coverage：#337 七条验收标准一一映射为 R1—R7，并由 PR final-head 与 main-fresh Browser/Unit/Build/diff Evidence 支撑。
- [x] reverse_audit：`cb8ef564…` → `c67b08d…` 仅 10 个预期 frontend/Change 文件；Backend/Contract/OpenAPI/generated/Schema/Migration/依赖未进入 diff，Browser Mock 未冒充真实 Backend/DB。
- [x] unresolved_cleared：所有 Review/Testing Findings 已修复并在实现 PR 与 main 上回归；Standard/Targeted re-review 均无阻塞 Finding、无 `not_satisfied` Requirement；实现已合并并完成 main-fresh 绿色验证。
