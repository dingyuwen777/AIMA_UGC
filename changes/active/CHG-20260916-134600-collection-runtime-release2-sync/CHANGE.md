---
schema: coding-change/v1
id: CHG-20260916-134600-collection-runtime-release2-sync
title: 采集运行中心对齐 release-2 Figma 正式设计
level: L2
status: in_progress
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
  - frontend/e2e/collection-runtime.spec.ts
  - changes/active/CHG-20260916-134600-collection-runtime-release2-sync/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

正式 Figma `release-2 / 采集运行中心`（Page/Canvas `3500:2023`）已经是本次 Design-to-Code 的上游视觉事实源。当前 `/collection-runtime` 已具备真实的运行列表、KPI、Cursor 分页、Data Import Campaign、辅助补采、Capability/Eligibility、详情、撤销和条件轮询能力，但主页面筛选、运行状态表达、Loading/Empty/Error、复杂 Modal/Drawer Shell 与响应式几何仍未完全对齐当前 release-2。

本 Change 使用 Existing Implementation Delta：保留现有 generated Client、Pinia Store、后端 Contract、Job/Provider 语义，只修改真实 UI Owner 和有充分复用证据的 Shared Shell，不回写 Figma。

# 目标

- `/collection-runtime` 主页面、状态、复杂 Modal/Drawer 与 release-2 当前设计一致。
- 默认筛选只展示搜索、北京时间日期范围、状态和类型，不暴露内部 Stage。
- 运行记录使用 Figma 的 7 列产品表格与状态徽标/百分比/状态色进度表达。
- Loading / Empty / Error / Retry 形成完整产品状态。
- 把真实跨场景复用的 Drawer、复杂 Modal、Empty State 外壳提升到 `shared/ui`，业务状态与 API 继续由 Feature Owner 持有。
- 保持所有现有真实数据导入、辅助补采、Capability、Cursor、轮询、撤销和详情行为。

# 范围与非目标

Included：`CollectionRuntimePage` 及其 Filters/KPI/Table/状态组件、Data Import Modal、Import/Run Detail Drawer、Supplement Drawer、必要 Shared UI Shell、相关 Store 错误边界与前端 Unit/Browser Mock 回归。

Excluded：Figma 写入、后端 API/Contract/Schema/Migration、generated Client、数据库、Provider 执行逻辑、依赖/Runtime 升级、无关页面重构。

# 必须保持不变

- Pydantic → FastAPI → OpenAPI → Orval → `frontend/src/generated/api` 事实链不变，generated 文件不手改。
- `GET /api/v1/collection-runtime/runs` 继续使用 cursor + limit / `next_cursor + has_more`。
- `GET /api/v1/collection-runtime/summary` 与后端 `Asia/Shanghai` “今日”口径不变。
- 只有活跃任务且页面可见时约每 5 秒静默刷新，已加载 Cursor Window 不因静默刷新丢失。
- Data Import local/server、预检、开始、取消、重试、撤销和冲突详情继续由服务端状态/资格决定。
- 辅助补采 Provider/Platform/Search Config/评论能力继续由 Capability/Eligibility 驱动，不写死 Figma 示例。
- 技术 ID、原始错误码与内部工程事实继续只在技术详情/诊断层出现。
- 不升级 Vue、Pinia、Vue Router、Vite、Element Plus、Node、npm 或其它依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 主页面 Geometry、KPI、Tabs、筛选、7 列表格和 Cursor 与当前 release-2 对齐，默认不展示 Stage | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；当前实现仍展示 Stage，完成后补代码与 Browser Evidence |
| R2 | 状态与进度使用状态徽标、百分比和状态色进度条，列表保持产品可读 | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补组件与 Browser Evidence |
| R3 | Loading/Empty/Error/Retry 与 Figma 状态规格一致，失败不无谓清空已有数据 | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补状态回归 Evidence |
| R4 | Data Import Modal、Import Detail、Supplement 与 Run Detail Overlay 对齐 Figma 且真实行为不退化 | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补 Unit/Browser Evidence |
| R5 | 仅对真实复用的 Drawer/Modal/Empty Shell 建立 Shared Owner，Feature 业务逻辑不进入 Shared | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补结构审计 Evidence |
| R6 | 1180/1440/1920 设计锚点及 1100/1200/1280 回归宽度保持可达，只有表格局部横向滚动 | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补 Playwright Geometry Evidence |
| R7 | 既有导入/补采/Capability/Cursor/轮询等业务回归与正式 CI 全部通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；完成后补 PR HEAD required CI Evidence |
| R8 | 实现完成后执行 Implementation ↔ Figma Conformance；本需求不修改 Figma | https://github.com/dingyuwen777/AIMA_UGC/issues/503 | not_satisfied | 开发中；最终记录 `NO_FIGMA_CHANGE_REQUIRED` 与人工/机器复核边界 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Filters、7 列表格、状态进度、Shared Shell、既有复杂 Overlay 行为；复用并更新 `collection-runtime-design.spec.ts` |
| 接口 / Contract | not_applicable | 不修改 HTTP Contract、generated Client、数据格式或公共机器接口 |
| Backend/API/PostgreSQL | not_applicable | 不修改后端服务、事务、数据库或 Persistence |
| Browser Mock Acceptance | required | `/collection-runtime` 主页面、状态、Overlay、筛选、响应式与既有工作流 |
| Real Full-stack Golden Path | required | 仓库 main Ruleset 要求 `Compose Golden Path`；按正式 required check 取得当前 PR HEAD 证据 |
| External Provider Probe | not_applicable | 不修改 Provider endpoint、字段、分页或外部真实能力，不需要付费 Probe |
| Build / Runtime | required | lint、typecheck、Vitest、Vite production build 及仓库 CI/Runtime 适用门禁 |
| Docs / Governance / Figma | required | Issue #503、Completion Audit、Standard Review、Figma Conformance、PR/Change/main fresh 状态 |

# 实施步骤

- [x] 重新读取目标仓库规则、当前 main、相关前端调用链、正式 Figma release-2 与 Agent_Skills canonical Source Mode。
- [x] 创建并回读 Requirement Source Issue #503，确认范围、AC、不变项与验证要求。
- [ ] Red：更新已有 Design/Browser 回归，使 Stage、状态进度、Loading/Empty/Error、Overlay Shell 和 Geometry 差异可观察失败。
- [ ] Green：按现有 Vue/Pinia/generated Client 架构实施最小 UI Delta，并抽取真实复用 Shared Shell。
- [ ] 执行目标 Unit/Browser、lint、typecheck、production build 与 required CI，修复根因直到当前 PR HEAD 绿色。
- [ ] 完成 Implementation ↔ Figma Conformance、Completion Audit 与两阶段 Standard Review。
- [ ] guarded merge 到最新 main；merge 后读取真实 merge revision、main fresh CI 与 repository-native Change Archive 结果。
- [ ] Closure Audit 后回写 Issue #503 Acceptance 状态并关闭 Requirement Source；清理任务分支。

# 当前新鲜证据

- 当前实施基线：`main@81d673dea8ed7047e9900eb4b4101d4ad812c8b2`。
- Requirement Source：Issue #503 已创建并通过 live readback；当前状态 open。
- Figma：当前 `3500:2025` 已确认只包含搜索、北京时间日期、状态、类型四个默认筛选；原 Stage 冲突已由设计侧修正。
- Figma：`3500:2875` Data Import、`3500:4257` Supplement、`3500:4557` Batch Detail 已重新取得当前 Design Context；本任务明确不回写 Figma。
- Main Ruleset：`CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 为 required checks，strict up-to-date 开启。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #503、当前 Figma 关键状态、PR head 和最新 main。
- [ ] change_coverage：逐项比对 AC1—AC8 与 R1—R8，确认无 Requirement omission。
- [ ] reverse_audit：从前端动作/状态反查 Store/generated Client/后端真实能力，确认无虚构 API/资格/状态。
- [ ] unresolved_cleared：Ready 前 `not_satisfied` 清零；所有 required Evidence 与 N/A 依据完整。

# 文档影响

当前长期架构与 Figma 工作流文档已经规定 App/Shared/Feature/Page 分层、真实 Contract 优先、复杂公共组件只在真实复用时抽取。本 Change 不改变 API、Schema、部署或长期业务语义；若实现未引入新的长期规则，则不机械修改 Blueprint/Guide，变更原因与证据由 Issue/Change/PR 承载。

# 兼容、部署与回滚

- 公共 HTTP Contract、Schema/Migration、数据语义、Provider 请求与配置不变。
- 不新增依赖，不改变 Runtime/package manager/lock。
- 部署方式、Docker/Release 产物结构不变，仅前端 bundle 内容变化。
- 回滚为 revert 本 Implementation PR；不需要数据库或数据迁移回滚。
