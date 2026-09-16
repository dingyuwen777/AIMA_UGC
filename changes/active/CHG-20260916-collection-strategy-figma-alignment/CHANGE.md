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
  - changes/active/CHG-20260916-collection-strategy-figma-alignment/CHANGE.md
contracts: []
data_changes: []
---

# 目标

以 Figma `qmZEFvPrB8u9JX5fyqc93S` 的采集策略 Page `4627:13214` 当前有效节点为视觉与交互基线，收敛 `/collection-strategy` 的 Header、KPI、关键词包工作区、计划筛选、计划列表、Modal/Drawer 与详情信息层级，同时保留当前真实 Keyword Pack、Brand Scope、Capability、Provider Search Config、归档恢复和计划资格逻辑。

# 成功标准

- [ ] 页面标题说明、三张 KPI 卡、双 Tab 与当前有效 Figma 一致，不恢复 Legacy“全局相关性”。
- [ ] 关键词包列表/详情使用内容驱动换行；1180 宽度下详情自然落到列表下方，1440 下保持 823 + 373 的正式布局。
- [ ] 计划筛选成为 Feature Owner；1180/1440/1920 下关键筛选和查询动作可达，页面不产生水平溢出。
- [ ] 计划列表普通用户层只展示平台名称，不暴露 Provider 显示名；范围摘要只使用当前 Contract 可证明的数据，不发明 scope_count。
- [ ] 新建/编辑计划与计划详情复用共享 Drawer；关键词包与关联资源复杂弹窗复用共享 Modal，并保留 Escape、焦点返回和单一滚动容器。
- [ ] Provider/Capability/Search Config、Brand Scope、Eligibility、归档恢复与历史运行冻结语义保持不变。
- [ ] frontend lint、typecheck、Vitest、build、相关 Playwright Browser Mock 与 PR CI 取得新鲜 GREEN；合并后 main 再取得新鲜验证。

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

- 用户本轮明确要求：按前序方案参考 Figma 采集策略页面修改 `dingyuwen777/AIMA_UGC` 并合并 `main`。
- 设计事实源：Figma `qmZEFvPrB8u9JX5fyqc93S` / Page `4627:13214`。
- 当前机器事实：`main` 的 Pydantic/OpenAPI/generated client、Collection Strategy Store/API/Eligibility 与 Blueprint 08。

# 关键决策

- Figma 视觉/交互与当前机器 Contract 冲突时，以当前正式 Contract 为机器事实；Legacy Global Relevance 不回写生产代码。
- 计划列表第二行不使用未定义的“采集范围”数量，改为 API 可直接证明的“关键词包数 · 平台数”。
- 普通列表和默认详情不展示 Provider 身份；Provider Display Name/ID 仅留技术详情，Capability 表单仍动态使用 Provider。
- 已存在 `AimaDrawer` / `AimaModalContainer` 是共享 Owner，本次增强焦点进入/返回后由采集策略复用，不继续用 `AimaDialog + CSS` 模拟 Drawer/复杂 Modal。
- Browser Mock 用于覆盖视觉/交互状态；不把 Mock 结果冒充 Backend/PostgreSQL 证明。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | Header、三张 KPI 卡和双 Tab 收敛到当前有效 Figma，并排除 Legacy 全局相关性 | `user:2026-09-16采集策略Figma对齐 / AC1` | satisfied | `CollectionStrategyPage.vue` 与 `StrategyKpiCards.vue` 已按当前有效主画板实现；Tabs 仍只有 `keywords/plans` |
| R2 | 关键词包工作区在 1440 保持列表+详情同行，在 1180 由内容宽度自然换行 | `user:2026-09-16采集策略Figma对齐 / AC2` | satisfied | `KeywordPackPanel.vue` 使用 `flex-wrap`、列表 `flex-basis:640px`、详情 373px；新增 Browser Mock 回归覆盖 1180 |
| R3 | 计划筛选形成 Feature Owner，并保持搜索、状态、平台、重置、查询可达 | `user:2026-09-16采集策略Figma对齐 / AC3` | satisfied | 新增 `PlanFilterBar.vue`，Page 只接 Store 状态与事件；组件包含 1180/1440/1920 自适应布局 |
| R4 | 计划普通列表只展示用户需要的平台和真实范围摘要，不暴露 Provider 技术信息 | `user:2026-09-16采集策略Figma对齐 / AC4` | satisfied | `PlanPanel.vue` 改为平台业务投影；第二行使用 Contract 可证明的关键词包数与平台数；Browser Mock 断言 Provider 不在列表出现 |
| R5 | Plan Create/Detail 复用共享 Drawer，Keyword/Resource 复杂弹窗复用共享 Modal，并保持键盘焦点行为 | `user:2026-09-16采集策略Figma对齐 / AC5` | satisfied | `PlanCreateDrawer.vue`、`PlanDetailDrawer.vue` 使用 `AimaDrawer`；两个复杂弹窗使用 `AimaModalContainer`；Shared Owner 增加焦点进入/返回与 Escape |
| R6 | 保留 Capability/Search Config、Brand Scope、Eligibility、资源生命周期和历史冻结语义，不改后端 Contract/generated/依赖 | `user:2026-09-16采集策略Figma对齐 / AC6` | satisfied | 最终实现范围仅前端组件、Shared Overlay、Browser Mock 与 Change；现有 `store.ts`/`api.ts`/`eligibility.ts` 与 generated/backend 未修改 |

# 验证矩阵

| 验证层 | 是否要求 | 计划证据 |
| --- | --- | --- |
| 静态检查 | required | GitHub Actions 锁定环境执行 frontend lint 与 typecheck |
| 单元/组件 | required | GitHub Actions 执行现有 Vitest 回归 |
| 构建 | required | GitHub Actions 执行 Vite build |
| Browser Mock | required | 既有 `collection-strategy-figma-geometry.spec.ts` + 新增 `collection-strategy-figma-projection.spec.ts` |
| Contract | required | fresh generated client / Feature API / eligibility 对照；最终 diff 不改 generated/backend |
| 持久化 | not_applicable | 本次不改数据库或数据语义 |
| 外部 Provider Probe | not_applicable | 本次不改 TikHub Provider 行为 |
| Figma Conformance | required | 当前有效主页面、Modal/Drawer、1180/1920 节点 targeted re-read/screenshot |
| Git/PR/CI | required | feature branch → PR → CI → guarded merge → main fresh CI |

# 完成审计

- [x] upstream_re_read: 已重新读取用户本轮要求、当前有效 Figma 主页面/Modal/Drawer、当前 generated Contract、Collection Strategy API/Store/Eligibility 与项目 Blueprint；Legacy Global Relevance 明确排除。
- [x] change_coverage: R1-R6 均有对应生产实现路径和回归测试入口；本 Change 只进入当前审计确认的前端视觉、交互与共享 Overlay 边界。
- [x] reverse_audit: 从 Page/Component 反查 Store、Feature API、generated client 与 Capability/Eligibility Owner，没有新增 endpoint、机器字段、持久化或第二套业务规则。
- [x] unresolved_cleared: 当前实现审计未发现 `not_satisfied` 产品要求；PR 自动验证仍是合并前强制证据，未取得 GREEN 前不宣称可合并或完成。

# 验证证据

- 实现基线：branch `feature/collection-strategy-figma-sync` 基于 task-start `main` SHA `171aad848dd6cb8c570a700d8ea7c5dce9a64a17`。
- 第一次 PR CI 仅因 Requirement-Source 元数据写成 Figma 文本而在验证入口失败；未运行实现测试。PR 已改为引用本 Change。
- 第二次 PR CI 通过 Requirement Source 与项目治理入口后，仅因 Change status 使用不受支持的 `active` 而在 Ready Check 停止；未运行 frontend 测试。当前已按门禁切换为 `ready_for_review` 并补齐稳定 Acceptance 追溯。
- 实现、测试、构建与 Browser Mock 的强完成结论只在后续 GitHub Actions 新鲜 GREEN 后回填，不用上述治理失败冒充功能验证。
