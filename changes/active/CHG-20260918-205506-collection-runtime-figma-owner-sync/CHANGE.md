---
schema: coding-change/v1
id: CHG-20260918-205506-collection-runtime-figma-owner-sync
title: 采集运行中心同步 Figma 四层 Owner 与紧凑布局
level: L2
status: active
owner: dingyuwen777
branch: feature/539-collection-runtime-figma-owner-sync
created: 2026-09-18
updated: 2026-09-18
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - documentation
  - figma-design-to-code
  - testing
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/components/CollectionRuntimeFilters.vue
  - frontend/tests/collection-runtime-release2.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
  - docs/guides/01_Figma与前端设计开发工作流.md
  - docs/guides/README.md
  - docs/guides/07_采集运行中心Figma开发基线.md
  - changes/active/CHG-20260918-205506-collection-runtime-figma-owner-sync/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

正式 Figma 文件 `qmZEFvPrB8u9JX5fyqc93S` 的“采集运行中心”（Page `3500:2023`）已经建立“设计规范/公共组件 → 页面模板 → 页面公共组件/Feature Owner → 正式页面实例”四层 Owner 链路。当前 `/collection-runtime` 已经对齐主要页面、状态、Modal/Drawer 和真实业务流程，但 Figma 开发规范 `7099:27523` 要求视口不大于 1120px 时筛选区稳定切换为两列，当前实现仍只依赖 Flex 自然换行；仓库长期文档也尚未记录新 Owner 链路和完整正式节点。

# 目标

- 以 Figma 正式页、Compact/Wide 和 Owner Governance 为当前视觉与交互事实源。
- 保持大于 1120px 的单行优先筛选，在不大于 1120px 时稳定切换为两列，并为更窄窗口提供单列兜底。
- 保持 1212px 七列表格仅在列表区域横向滚动，操作列始终可达。
- 建立 Figma 四层 Owner 到现有 Vue/App/Shared/Feature/Page Owner 的长期映射。
- 保留既有 Data Import Campaign、Excel Import、辅助补采、Capability、Cursor、条件轮询、详情和撤销行为。

# 范围与非目标

Included：采集运行筛选区响应式样式、正式 Figma Owner/节点文档、源码结构与 Browser Mock 回归、Change/Issue/PR 交付证据。

Excluded：后端 API、Contract、Schema/Migration、generated client、Pinia Store 业务规则、Provider/Job/Worker 逻辑、依赖升级、其他页面重构、Figma 再写入。

# 必须保持不变

- Route 继续为 `/collection-runtime`。
- Page → Store/local state → Feature API → generated client → HTTP 调用链不变，generated 文件不手改。
- `GET /api/v1/collection-runtime/runs` 的 cursor + limit、`GET /summary` 的 `Asia/Shanghai` 今日口径不变。
- 只有活跃任务且页面可见时约每 5 秒静默刷新。
- Modal/Drawer/Empty/Feedback/Button/PageHeader/DateRange 继续复用 Shared Owner，业务状态留在 Feature。
- Figma 示例任务、数量、时间、状态不写入生产默认值。
- 不升级 Vue、Pinia、Vue Router、Vite、Element Plus、Node、npm 或其他依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 保持正式页的标题操作、三 KPI、三 Tab、五项筛选、七列表格和三态表达 | #539 / AC1 | pending | 待执行源码结构、Unit 与 Browser Mock 回归。 |
| R2 | `>1120px` 单行优先，`≤1120px` 两列，更窄窗口可达且无页面级横向溢出 | #539 / AC2 | pending | Red 回归先锁定 1120px 两列规则，再实施最小 CSS Delta。 |
| R3 | 1212px 表格只在列表区域横向滚动，六组目标宽度下操作列可达 | #539 / AC3 | pending | 待扩展并执行 Playwright 响应式验收。 |
| R4 | Shared Overlay Shell 与真实 API/Store/Capability/Cursor/轮询行为不变 | #539 / AC4 | pending | 待执行既有 Unit/Browser 回归和反向审计。 |
| R5 | 长期文档记录四层 Figma Owner、正式节点、响应式规则和代码 Owner | #539 / AC5 | pending | 待新增采集运行中心专门基线并更新 Guide 导航。 |
| R6 | 所有必需门禁通过且无 Contract、依赖、数据库、Migration 变化 | #539 / AC6 | pending | 待记录本地与 current-head CI 新鲜证据。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `collection-runtime-design.spec.ts`、`collection-runtime-release2.spec.ts` 及现有 Import Store/API 回归。 |
| 接口 / Contract | not_applicable | 计划不修改 HTTP Contract、generated client、公共数据格式。 |
| Backend/API/PostgreSQL | not_applicable | 计划不修改后端 Service、事务、数据库或 Persistence。 |
| Browser Mock Acceptance | required | `/collection-runtime` 主页面、1100/1180/1200/1280/1440/1920 响应式与已有 Overlay/流程。 |
| Real Full-stack Golden Path | not_applicable | 纯前端布局、测试与文档 Delta；不改变前后端接线或真实持久化流程。 |
| External Provider Probe | not_applicable | 不修改 Provider endpoint、字段、分页或真实外部能力。 |
| Build / Runtime | required | Frontend lint、typecheck、Unit、production build 和仓库 CI。 |
| Docs / Governance / Figma | required | Issue #539、正式 Figma Design Context、四层 Owner 映射、Completion Audit。 |

# 实施步骤

- [x] 读取 canonical Agent_Skills、仓库规则、当前实现与相关历史 Change。
- [x] 检查开放 Issue/PR 重叠并建立 Requirement Source Issue #539。
- [x] 读取当前 Figma 主页面、Page Metadata 与 Compact 1180 Design Context。
- [ ] Red：用源码结构与浏览器回归锁定 1120px 两列和现有正式结构。
- [ ] Green：实施最小筛选响应式 Delta，不改业务调用链。
- [ ] 同步长期 Figma/代码 Owner 文档。
- [ ] 执行 Unit、lint、typecheck、build、Playwright、Change Completion 和 Standard Review。
- [ ] 将 Change 更新为 `ready_for_review`，取得 current-head CI 后 guarded merge。
- [ ] 读取 main fresh CI、自动归档结果，完成 Issue Acceptance 回写与关闭。

# 当前新鲜证据

- 实施基线：`main` / `origin/main` = `0549d28726d2b132c7605fd019f4dde3b7c4e619`，任务开始时工作树 clean。
- Requirement Source：Issue #539，2026-09-18 创建并回读；创建前确认无开放同类 Issue/PR。
- Figma：已读取主页面 `3500:2025`、Page `3500:2023` Metadata、Compact `4742:2404` Design Context；规范明确 1212px 七列表格局部滚动和 `≤1120px` 筛选两列。
- 现有实现：主页面、KPI、Tab、五项筛选、七列表格、Shared Overlay 和真实 Store/API 链路已存在；当前缺口集中在确定性紧凑断点和长期 Owner 文档。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #539、目标 Figma 节点、当前 PR HEAD 与最新 main。
- [ ] change_coverage：逐项核对 AC1—AC6 / R1—R6，所有必需项有当前 revision 直接证据。
- [ ] reverse_audit：从用户动作反查 Page/Store/API/generated client；确认没有 Figma 示例或新平行状态机进入生产实现。
- [ ] unresolved_cleared：所有 required 行为与门禁满足；未验证风险、N/A 理由和回滚边界明确。

# 文档影响

本 Change 会新增采集运行中心专门 Figma 开发基线，并更新现有 Figma 工作流与 Guide 导航。Blueprint、API、Operations、Product 文档不受影响，因为本次不改变业务能力、接口、数据、部署或运行语义。

# 兼容、部署与回滚

- 公共 HTTP Contract、Schema/Migration、数据语义、Provider 请求和配置不变。
- 不新增依赖，不改变 Runtime/package manager/lock。
- 部署方式、Docker/Release 产物结构不变；合并后按现有流程重新构建前端 bundle。
- 回滚为 revert 本 Implementation PR；不需要数据库、数据或配置迁移回滚。
