---
schema: coding-change/v1
id: CHG-20260916-134600-collection-runtime-release2-sync
title: 采集运行中心对齐 release-2 Figma 正式设计
level: L2
status: done
owner: dingyuwen777
branch: feature/503-collection-runtime-release2-sync
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma-design-to-code
  - testing
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/
  - frontend/src/shared/ui/
  - frontend/src/features/import-batches/store.ts
  - frontend/tests/collection-runtime-design.spec.ts
  - frontend/tests/collection-runtime-release2.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
  - changes/active/CHG-20260916-134600-collection-runtime-release2-sync/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

正式 Figma `release-2 / 采集运行中心`（Page/Canvas `3500:2023`）是本次 Design-to-Code 的上游视觉事实源。`/collection-runtime` 原实现已经具备真实运行列表、KPI、Cursor 分页、Data Import Campaign、辅助补采、Capability/Eligibility、详情、撤销和条件轮询能力，本次只做 Existing Implementation Delta：保留 generated Client、Pinia Store、后端 Contract、Job/Provider 语义，将主页面、状态表达、复杂 Modal/Drawer Shell 与响应式几何收敛到当前 release-2，不回写 Figma。

# 目标

- `/collection-runtime` 主页面、状态、复杂 Modal/Drawer 与 release-2 当前设计一致。
- 默认筛选只展示搜索、北京时间日期范围、状态和类型，不暴露内部 Stage。
- 运行记录使用 Figma 的 7 列产品表格与状态徽标/百分比/状态色进度表达。
- Loading / Empty / Error / Retry 形成完整产品状态。
- 把真实跨场景复用的 Drawer、复杂 Modal、Empty State 外壳提升到 `shared/ui`，业务状态与 API 继续由 Feature Owner 持有。
- 保持所有现有真实数据导入、辅助补采、Capability、Cursor、轮询、撤销和详情行为。

# 范围与非目标

Included：`CollectionRuntimePage` 及其 Filters/KPI/Table/状态组件、Data Import Modal、Import/Run Detail Drawer、Supplement Drawer、必要 Shared UI Shell、相关 Store 产品错误边界与前端 Unit/Browser Mock 回归。

Excluded：Figma 写入、后端 API/Contract/Schema/Migration、generated Client、数据库、Provider 执行逻辑、依赖/Runtime 升级、无关页面重构。

# 必须保持不变

- Pydantic → FastAPI → OpenAPI → Orval → `frontend/src/generated/api` 事实链不变，generated 文件不手改。
- `GET /api/v1/collection-runtime/runs` 继续使用 cursor + limit / `next_cursor + has_more`。
- `GET /api/v1/collection-runtime/summary` 与后端 `Asia/Shanghai` “今日”口径不变。
- 只有活跃任务且页面可见时约每 5 秒静默刷新，已加载 Cursor Window 不因静默刷新丢失。
- Data Import local/server、预检、开始、取消、重试、撤销和冲突详情继续由服务端状态/资格决定。
- 辅助补采 Provider/Platform/Search Config/评论能力继续由 Capability/Eligibility 驱动，不写死 Figma 示例。
- 技术 ID、原始错误码与内部工程事实继续只在技术详情/诊断层出现；默认产品列表错误态不暴露 `request_id`。
- 不升级 Vue、Pinia、Vue Router、Vite、Element Plus、Node、npm 或其它依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 主页面 Geometry、KPI、Tabs、筛选、7 列表格和 Cursor 与当前 release-2 对齐，默认不展示 Stage | #503 / AC1 | satisfied | `CollectionRuntimePage.vue`、`CollectionRuntimeFilters.vue`、`CollectionRuntimeKpiCards.vue`、`CollectionRuntimeTable.vue`；当前 Figma `3500:2025`、`4742:2404`、`4742:2603` 已重读；Browser Mock 覆盖 1100/1180/1200/1280/1440/1920。 |
| R2 | 状态与进度使用状态徽标、百分比和状态色进度条，列表保持产品可读 | #503 / AC2 | satisfied | 新增 `CollectionRuntimeStatusProgress.vue`；主表固定七列且默认层不展示 Run/Job/Batch 身份；`collection-runtime-design.spec.ts` 与 Browser 回归覆盖状态和详情入口。 |
| R3 | Loading/Empty/Error/Retry 与 Figma 状态规格一致，失败不无谓清空已有数据 | #503 / AC3 | satisfied | `CollectionRuntimeTable.vue` 使用 AIMA Feedback + 3 Skeleton、`AimaEmptyState`、产品级 Error/Retry；已有列表刷新失败保留 rows；当前 Figma `3500:5609` 已重读；E2E 验证技术 request_id 不进入产品列表错误态。 |
| R4 | Data Import Modal、Import Detail、Supplement 与 Run Detail Overlay 对齐 Figma 且真实行为不退化 | #503 / AC4 | satisfied | `DataImportDialog.vue` 使用 840×800 Shared Modal；`ImportBatchDetailDrawer.vue` 450px、四页签；Supplement/Run Detail 510px Shared Drawer；现有 local/server/preflight/start/cancel/retry/revoke/conflict/Capability 行为由 Browser Mock 全量回归。 |
| R5 | 仅对真实复用的 Drawer/Modal/Empty Shell 建立 Shared Owner，Feature 业务逻辑不进入 Shared | #503 / AC5 | satisfied | 新增 `shared/ui/AimaDrawer.vue`、`AimaModalContainer.vue`、`AimaEmptyState.vue`；Shared 只持有遮罩、尺寸、滚动边界、slot 与关闭交互，Feature Store/API/资格条件仍在 import-batches Feature。 |
| R6 | 1180/1440/1920 设计锚点及 1100/1200/1280 回归宽度保持可达，只有表格局部横向滚动 | #503 / AC6 | satisfied | Figma Compact/Wide 已重读；`collection-runtime.spec.ts` 对 1100/1180/1200/1280/1440/1920 检查筛选无溢出、TableViewport 局部 `overflow-x:auto`、操作列可达；全局 responsive suite 同时通过。 |
| R7 | 既有导入/补采/Capability/Cursor/轮询等业务回归与正式 CI 全部通过 | #503 / AC7 | satisfied | 与实现代码树一致的 validation PR #505 `75cc57d663d0f3c77d6005ae3b0b681fbf29f35d`：CI run `35067199872` success、Runtime Acceptance `35067199740` success；lint success、audit 0 vulnerabilities、Vitest 28 files/157 tests、typecheck/build success、Playwright 107/107。最新 main 仅额外修改 env 模板且已无冲突同步进实现分支。 |
| R8 | 实现完成后执行 Implementation ↔ Figma Conformance；本需求不修改 Figma | #503 / AC8 | satisfied | 当前重新读取 `3500:2025`、`3500:5609`、`3500:2875`、`3500:4257`、`3500:4557`、`4742:2404`、`4742:2603`，逐项对照现有 Vue Owner/Contract；结论 `NO_FIGMA_CHANGE_REQUIRED`。未对 Figma 执行写操作。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `collection-runtime-design.spec.ts`、`collection-runtime-release2.spec.ts` 与既有 Store/API tests；validation CI 中 Vitest 28 files / 157 tests passed。 |
| 接口 / Contract | not_applicable | 未修改 HTTP Contract、generated Client、数据格式或公共机器接口。 |
| Backend/API/PostgreSQL | not_applicable | 未修改后端服务、事务、数据库或 Persistence。 |
| Browser Mock Acceptance | required | validation CI Playwright 107/107 passed，覆盖 `/collection-runtime` 主页面、状态、Overlay、筛选、响应式和既有工作流。 |
| Real Full-stack Golden Path | not_applicable | CI scope classifier 判定本次为 `frontend_only`；required workflow job 已按仓库规则评估并 skipped，没有伪造执行结果。 |
| External Provider Probe | not_applicable | 未修改 Provider endpoint、字段、分页或外部真实能力，不需要付费 Probe。 |
| Build / Runtime | required | Node 24.19.0 / npm 11.17.0；lint、audit、typecheck、Vite production build、Runtime Acceptance 均在 validation GitHub Runner 新鲜通过。 |
| Docs / Governance / Figma | required | Issue #503、当前 Change Completion Audit、Figma Conformance `NO_FIGMA_CHANGE_REQUIRED`；长期 Guide/Blueprint 未新增规则，因此不机械修改。 |

# 实施步骤

- [x] 重新读取目标仓库规则、当前 main、相关前端调用链、正式 Figma release-2 与 Agent_Skills canonical Source Mode。
- [x] 创建并回读 Requirement Source Issue #503，确认范围、AC、不变项与验证要求。
- [x] Red：更新 Design/Browser 回归，使 Stage、状态进度、Loading/Empty/Error、Overlay Shell 和 Geometry 差异可观察。
- [x] Green：按现有 Vue/Pinia/generated Client 架构实施最小 UI Delta，并抽取真实复用 Shared Shell。
- [x] 在 validation GitHub Runner 执行 lint、audit、Unit、typecheck、production build、107 项 Browser Mock 与 Runtime Acceptance，修复唯一定位器歧义后取得全绿证据。
- [x] 完成 Implementation ↔ Figma Conformance 与 Completion Audit；结论 `NO_FIGMA_CHANGE_REQUIRED`。
- [ ] 在本 Change 进入 Ready 后，由 PR #504 当前 HEAD 重新取得 required CI，并完成最终 Standard Review。
- [ ] guarded merge 到最新 main；merge 后读取真实 merge revision、main fresh CI 与 repository-native Change Archive 结果。
- [ ] Closure Audit 后回写 Issue #503 Acceptance 状态并关闭 Requirement Source；清理任务分支与 validation 分支。

# 当前新鲜证据

- 最新 `main`：`ccab9d50a17e3b8faab85eccf891fabfe36b63ce`；相对最初实施基线只包含 `env.local.example` / `env.production.example` 更新，已以双父 merge 同步到实现分支，无前端代码冲突。
- Requirement Source：Issue #503 已重新读取，AC1—AC8 未变化且当前仍 open。
- validation 代码树：`75cc57d663d0f3c77d6005ae3b0b681fbf29f35d`；CI `35067199872` success、Runtime Acceptance `35067199740` success。
- validation CI 明细：`npm ci` 391 packages、audit 0 vulnerabilities；ESLint success；Vitest 28 files / 157 tests；TS native + `vue-tsc` success；Vite 8.2.1 build success；Playwright 107/107。
- Figma：当前 `3500:2025` 已确认只包含搜索、北京时间日期、状态、类型四个默认筛选；`3500:5609`、`3500:2875`、`3500:4257`、`3500:4557`、`4742:2404`、`4742:2603` 已重新取得当前 Design Context，本任务没有 Figma 写入。

# Completion Audit

- [x] upstream_re_read：Ready 前已重新读取 Issue #503、正式 Figma 主页面/状态/Modal/Drawer/1180/1920、PR #504 HEAD 和最新 main；Stage 设计冲突已不存在。
- [x] change_coverage：逐项核对 AC1—AC8 / R1—R8；主页面、三态、复杂 Overlay、Shared Owner、响应式、业务回归和 Figma Conformance 均有代码与 Runner 证据。
- [x] reverse_audit：从 UI 动作反查 Store/API/generated Client；Cursor、5 秒条件轮询、Campaign `can_start`、Provider/Platform Capability、评论/二级回复和撤销资格均继续使用原真实 Contract，没有虚构接口或 Figma 示例常量。
- [x] unresolved_cleared：R1—R8 均为 satisfied；Backend/Schema/generated/dependency/Provider Probe/Full-stack 执行层均有明确 N/A 或 frontend-only 依据，没有残留 `not_satisfied`。

# 文档影响

当前长期架构与 Figma 工作流文档已经规定 App/Shared/Feature/Page 分层、真实 Contract 优先、复杂公共组件只在真实复用时抽取。本 Change 没有改变 API、Schema、部署或新的长期治理规则，因此不机械修改 Blueprint/Guide；变更范围、事实和验收证据由 Issue #503、Change 与 PR #504 承载。

# 兼容、部署与回滚

- 公共 HTTP Contract、Schema/Migration、数据语义、Provider 请求与配置不变。
- 不新增依赖，不改变 Runtime/package manager/lock。
- 最新 main 的 env 模板变更已同步保留，本 Change 未覆盖或回退其它人的修改。
- 部署方式、Docker/Release 产物结构不变，仅前端 bundle 内容变化。
- 回滚为 revert 本 Implementation PR；不需要数据库或数据迁移回滚。
