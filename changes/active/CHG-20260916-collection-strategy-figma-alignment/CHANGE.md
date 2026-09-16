---
schema: coding-change/v1
id: CHG-20260916-collection-strategy-figma-alignment
title: 收敛采集策略前端到当前有效 Figma 基线
level: L2
status: ready_for_review
owner: dingyuwen777
branch: feature/collection-strategy-figma-sync
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma-sync
  - tests
affected_paths:
  - frontend/src/features/collection-strategy/
  - frontend/src/shared/ui/AimaDrawer.vue
  - frontend/src/shared/ui/AimaModalContainer.vue
  - frontend/e2e/collection-strategy-figma-projection.spec.ts
  - frontend/e2e/collection-strategy.spec.ts
  - frontend/tests/collection-strategy-design.spec.ts
  - frontend/tests/stage6-brand-productization.spec.ts
  - changes/active/CHG-20260916-collection-strategy-figma-alignment/CHANGE.md
contracts: []
data_changes: []
---

# 目标

以 Figma `qmZEFvPrB8u9JX5fyqc93S` 的采集策略 Page `4627:13214` 当前有效节点为视觉与交互基线，收敛 `/collection-strategy` 的 Header、KPI、关键词包工作区、计划筛选、计划列表、Modal/Drawer 与详情信息层级，同时保留当前真实 Keyword Pack、Brand Scope、Capability、Provider Search Config、归档恢复和计划资格逻辑。

# 成功标准

- [x] 页面标题说明、三张 KPI 卡、双 Tab 与当前有效 Figma 一致，不恢复 Legacy“全局相关性”。
- [x] 关键词包列表/详情使用内容驱动换行；1180 宽度下详情自然落到列表下方，1440 下保持 823 + 373 的正式布局。
- [x] 计划筛选成为 Feature Owner；1180/1440/1920 下关键筛选和查询动作可达，页面不产生水平溢出。
- [x] 计划列表普通用户层只展示平台名称，不暴露 Provider 显示名；范围摘要只使用当前 Contract 可证明的数据，不发明 scope_count。
- [x] 新建/编辑计划与计划详情复用共享 Drawer；关键词包与关联资源复杂弹窗复用共享 Modal，并保留 Escape、焦点返回和单一滚动容器。
- [x] Provider/Capability/Search Config、Brand Scope、Eligibility、归档恢复与历史运行冻结语义保持不变。
- [x] frontend lint、typecheck、Vitest、build、相关 Playwright Browser Mock 与 PR current-head CI 已取得新鲜 GREEN；按 Requirement #518 AC6，merge 后 main fresh validation 继续由 Closure Audit 取得后才允许关闭需求。

# 范围

- Collection Strategy Page 与页面私有/Feature 组件。
- Shared Drawer / Modal 的焦点进入与返回能力。
- Collection Strategy Figma 投影 Browser Mock 回归。
- 本 Change 追溯与完成审计。

# 非目标

- 不新增或修改后端 endpoint、Pydantic/OpenAPI Contract、generated client、Schema/Migration 或 PostgreSQL 数据。
- 不升级 Vue、Vite、Pinia、Element Plus、Orval、Node/npm 或其它依赖。
- 不实现 Figma 历史 Stage 中的 `/api/v1/relevance-config`、Global Relevance Tab、`vehicle_model_ids` Plan Contract 或 `/api/v1/platforms`。
- 不删除当前真实的复制、归档、恢复、受限永久删除等生命周期能力。

# 必须保持不变

- `CollectionPlanCreateRequest` 当前 Keyword Pack Search + Brand Scope 语义。
- `GET /api/v1/collection-capabilities` → generated client → Feature/Field 的动态 Provider/Search Config 链。
- `planExecutionReason` 当前资格 Owner 与后端最终校验。
- `Asia/Shanghai`、批准 Cron 机器值、历史运行冻结配置、资源生命周期语义。

# 需求来源

- Requirement Source：GitHub Issue #518 `[需求] 采集策略页面对齐当前 Figma 基线`，AC1–AC6 为当前验收 Owner。
- 用户本轮明确要求：按前序方案参考 Figma 采集策略页面修改 `dingyuwen777/AIMA_UGC` 并合并 `main`。
- 设计事实源：Figma `qmZEFvPrB8u9JX5fyqc93S` / Page `4627:13214`。
- 当前机器事实：`main` 的 Pydantic/OpenAPI/generated client、Collection Strategy Store/API/Eligibility 与 Blueprint 08。

# 关键决策

- Figma 视觉/交互与当前机器 Contract 冲突时，以当前正式 Contract 为机器事实；Legacy Global Relevance 不回写生产代码。
- 计划列表第二行不使用未定义的“采集范围”数量，改为 API 可直接证明的“关键词包数 · 平台数”。
- 普通列表和默认详情不展示 Provider 身份；Provider Display Name/ID 仅留技术详情，Capability 表单仍动态使用 Provider。
- 已存在 `AimaDrawer` / `AimaModalContainer` 是共享 Owner，本次增强焦点进入/返回和嵌套 Escape 层级后由采集策略复用，不继续用 `AimaDialog + CSS` 模拟 Drawer/复杂 Modal。
- Browser Mock 用于覆盖视觉/交互状态；不把 Mock 结果冒充 Backend/PostgreSQL 证明。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Header、三张 KPI 卡和双 Tab 收敛到当前有效 Figma，并排除 Legacy 全局相关性 | `#518 / AC1` | satisfied | `CollectionStrategyPage.vue` 与 `StrategyKpiCards.vue` 已按当前有效主画板实现；Tabs 只有 `keywords/plans`；Figma 当前主 Section 只含关键词包与采集计划正式 Frame |
| R2 | 关键词包工作区在 1440 保持列表+详情同行，在 1180 由内容宽度自然换行且无页面横向溢出 | `#518 / AC2` | satisfied | `KeywordPackPanel.vue` 使用内容驱动布局；Figma geometry、projection 与 responsive Browser Mock 在 PR CI #5119 当前 head 全部通过 |
| R3 | 计划筛选、计划表与普通用户信息投影对齐当前 Figma，不泄露 Provider 技术身份 | `#518 / AC3` | satisfied | `PlanFilterBar.vue` 成为 Feature Owner；`PlanPanel.vue` 只展示平台业务名和 Contract 可证明的范围摘要；projection Browser Mock 验证 Provider 不出现在普通列表/默认详情 |
| R4 | 新建/编辑计划继续由真实 Keyword Pack、Brand Scope、Capability/Search Config 和 Eligibility 驱动，不猜测机器接口 | `#518 / AC4` | satisfied | `PlanCreateDrawer.vue` 继续复用 Store/Capability/`planExecutionReason`；Browser Mock 验证分页 active Brand、Search Config 与创建 payload，且无 `vehicle_model_ids` 等旧字段 |
| R5 | Shared Drawer/Modal 承载计划与复杂资源弹层，并保持 Escape、嵌套层级、焦点返回与单一滚动边界 | `#518 / AC5` | satisfied | `AimaDrawer.vue` / `AimaModalContainer.vue` 统一 Owner；PR CI #5119 中采集策略 geometry 的嵌套资源详情与全部 Escape/焦点回归均通过 |
| R6 | frontend current-head lint/typecheck/Vitest/build/Browser Mock 与 PR CI 通过 | `#518 / AC6` | satisfied | head `64c4650fe0c8add9554d2dba28cf0bec1a771f20`：CI #5119 success，Runtime Acceptance #2167 success；Vitest 28 files / 157 tests passed，Vite build success，Playwright 110 passed + 1 unrelated flaky case recovered on retry，最终 exit 0 |
| R7 | merge 后 main fresh validation 后才能关闭 Requirement #518 | `#518 / AC6` | explicitly_deferred | 该证据按 AC6 定义只能在 guarded merge 后取得；由 Requirement Closure Audit 继续持有，未取得前 Issue #518 保持 open |

# 验证矩阵

| 验证层 | 是否要求 | Scope / Evidence |
| --- | --- | --- |
| 静态检查 | required | PR CI #5119 / frontend step：`eslint . --max-warnings=0`、TS7 typecheck、`vue-tsc --noEmit` 全部 exit 0 |
| 单元/组件 | required | PR CI #5119：Vitest 28 files / 157 tests passed，0 failed |
| 构建 | required | PR CI #5119：Vite 8.2.1，191 modules transformed，production build exit 0 |
| Browser Mock | required | PR CI #5119：采集策略现有 geometry、功能与新增 projection/1180 wrap 回归全部通过；全套 Playwright 最终 110 passed + 1 unrelated voice-plaza carousel flaky recovered on retry，exit 0 |
| Contract | required | fresh 对照当前 generated client、Feature API/Store/Eligibility；最终 PR diff 不改 backend/generated/OpenAPI，Browser Mock payload 继续断言当前 Plan Contract |
| 持久化 | not_applicable | 本次不改数据库、Schema/Migration 或数据语义 |
| 外部 Provider Probe | not_applicable | 本次不改 TikHub Provider 协议或当前外部事实；真实 Provider Probe 不增加本次前端对齐证明价值 |
| Figma Conformance | required | fresh 读取当前 Figma Page metadata 与采集计划正式 Node `4627:13336` Design Context，并对照关键词包、Modal/Drawer、1180/1440/1920 既有设计基线；未发现需要回写 Figma 的正式 Drift |
| Git/PR/CI | required | PR #517 current head `64c4650f…`：CI #5119 success、Runtime Acceptance #2167 success；guarded merge 与 main fresh validation 由交付阶段继续执行 |

# 完成审计

- [x] upstream_re_read: 已重新读取 Issue #518 AC1–AC6、用户本轮要求、当前有效 Figma Page/主计划 Node、当前机器 Contract 与目标实现；Legacy Global Relevance 只存在于隐藏 Legacy/历史设计区域，不作为生产事实。
- [x] change_coverage: AC1–AC5 已映射到生产实现与 current-head 直接证据；AC6 的 PR 侧证据已 GREEN，merge 后 main fresh 部分明确留给 Closure Audit，没有把未发生的 post-merge 事实写成已完成。
- [x] reverse_audit: 从 Page/Component 反查 Store、Feature API、generated client 与 Capability/Eligibility Owner，没有新增 endpoint、机器字段、持久化或第二套业务规则；嵌套 Modal → Drawer Escape 与焦点返回有直接 Browser Mock 回归。
- [x] unresolved_cleared: 当前 Implementation PR 范围无 `not_satisfied`；唯一生命周期待办是 #518 AC6 明确定义的 post-merge main fresh validation，已由 R7 指向 Requirement Closure Owner。

# 验证证据

- 实现基线：branch `feature/collection-strategy-figma-sync` 基于 task-start `main` SHA `171aad848dd6cb8c570a700d8ea7c5dce9a64a17`。
- 治理 Red：初始 PR CI 因 Requirement-Source 写成 Figma 文本停止；已建立正式 Requirement #518 并修正 PR 追溯，后续门禁通过。
- 行为 Red：head `3a0553024aa22a2c449f2a5bedf8d284da5358c0` 的 CI #5118 复现“嵌套资源 Modal 关闭后底层计划 Drawer 被连带关闭/焦点无法返回”的 Browser Mock 失败；根因是通用 Escape 层级按 DOM dialog 顺序判断，无法表达 Modal z-index 高于 Drawer。
- Green：head `64c4650fe0c8add9554d2dba28cf0bec1a771f20` 将 Escape ownership 收敛到 `Modal > Drawer` 层级后，CI #5119 success；相关嵌套资源详情与全策略 Overlay Escape/焦点用例均通过。
- PR current-head CI #5119：Requirement Source、项目治理、Ready Check、Secret/docs gates、Node 24.19.0 / npm 11.17.0、dependency audit、frontend lint、typecheck、Vitest、Vite build、Playwright 与 CI Gate 全部完成；PostgreSQL / Real Full-stack 按本次 frontend-only profile 正确 skipped。
- Vitest：28 files / 157 tests passed。
- Playwright：采集策略相关测试全部首轮通过；全套结果为 110 passed，另 1 个与本 PR 无关的 `voice-plaza-media-carousel` 首轮 flaky、retry 通过，Playwright 最终 exit 0。该 flake 未由本次采集策略变更触发，不在本 Change 内无关重构。
- Runtime Acceptance #2167：success。
- npm audit：0 vulnerabilities；本 Change 未修改依赖。
- Figma Sync：`NO_FIGMA_CHANGE_REQUIRED`；本轮以当前有效 Figma 为正式设计输入，代码差异已收敛到其当前主页面/弹层/响应式语义，没有证据支持把历史 Legacy 注释或当前代码实现反写为新设计事实。
