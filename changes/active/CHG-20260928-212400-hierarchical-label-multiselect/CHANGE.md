---
schema: coding-change/v1
id: CHG-20260928-212400-hierarchical-label-multiselect
title: 统一工作台与声音广场的层级标签多选筛选
level: L2
status: ready_for_review
owner: codex
branch: feature/652-hierarchical-label-multiselect
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - workbench
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/src/features/workbench/
  - frontend/tests/
  - frontend/e2e/
  - tests/api/test_stage8d_contents.py
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
  - docs/product/02_当前产品能力与用户流程.md
contracts:
  - ContentFilterSnapshot primary_labels / secondary_labels
data_changes: []
---

# 变更摘要

统一工作台和声音广场的一级/二级标签筛选：两级均支持多选，二级候选只来自当前已选一级标签；父级取消后同步剔除失效二级标签。声音广场公共 Content Filter Contract 采用兼容式 plural 扩展，保留 legacy singular 输入并在 Contract 边界归一化。

# 背景、现状与问题

Requirement Source 为 Issue #652。工作台原本已经使用 `primary_labels / secondary_labels` 数组 Contract，但前端把所有一级标签的二级项平铺；声音广场仍使用 `primary_label / secondary_label` 单值 Contract 和单选控件；工作台到声音广场的深链也只能表达一个标签。若只改下拉控件，会留下列表/Count/Analysis/Export、读模型 fallback 或隐藏旧二级条件继续生效等语义漂移。

# 目标、成功标准与非目标

## 目标

- 两页一级、二级标签都可多选。
- 二级候选只来自已选一级标签，未选一级时不可选；父级取消时同步清理失效子项。
- 同一维度 OR，一级维度与二级维度 AND，并与工作台现有 PostgreSQL 语义一致。
- 声音广场列表、Count、query-scope Analysis/Export 复用同一 `ContentFilterSnapshot`。
- projection ready 热路径与 fallback 路径一致。
- 新前端只发 plural 字段；legacy singular HTTP/历史快照继续兼容。
- Workbench → Voice Plaza 支持多标签深链；legacy singular 深链可恢复。

## 非目标

- 不修改 active Taxonomy 内容、标签层级定义或 AI Prompt。
- 不新增数据库表、列或 Migration。
- 不升级依赖、不改变其它筛选维度。
- 不执行 Release、Deploy 或生产数据操作。
- 按用户最新指令，本任务只提交 PR，不合并 `main`。

# 事实与关键决策

| 事实 / 决策 | 当前结论 |
| --- | --- |
| 工作台服务端语义 | `primary_labels` 与 `secondary_labels` 各自使用独立 `EXISTS ... ANY(array)`，同维度 OR、两个维度 AND |
| 声音广场公共 Contract | 新增 plural 数组，保留 singular 输入；模型校验后统一写入 plural，并清空 singular |
| 历史快照 | Analysis Planner 恢复 query snapshot 时通过 `ContentFilterSnapshot.model_validate`；旧 singular JSON 无需 Migration |
| Export query scope | 直接消费 `ContentTargetSelection.filters: ContentFilterSnapshot` 并冻结同一查询 |
| 读路径 | projection JSONB 与 fallback AI/manual labels 分别按同一两个维度过滤 |
| 前端父子约束 | Store 层负责清理无效值，组件层负责限制候选与禁用状态；不能仅隐藏 UI |
| 深链 | 新版使用 repeated `primary_labels/secondary_labels`；页面仍识别旧 singular query |
| 交付边界 | 创建 PR 并取得 PR 状态证据；本任务不 merge |

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 工作台一级/二级标签均支持多选 | #652 / AC1 | satisfied | 既有数组 Store/Contract 保留；`WorkbenchFilters.vue` 二级继续使用 `WorkbenchMultiSelect`，Browser 用例验证多父级选择。 |
| R2 | 声音广场一级/二级标签均支持多选 | #652 / AC2 | satisfied | `VoicePlazaFilters.vue` 改为 plural 数组 + checkbox 多选；Frontend Unit 与 Browser 通过。 |
| R3 | 未选择一级时二级不可选并提示 | #652 / AC3 | satisfied | 两页均在无一级选择时禁用二级入口；Browser 直接验证 `请先选择一级标签` 与 disabled/aria-disabled。 |
| R4 | 二级候选只来自所选一级标签并取并集 | #652 / AC4 | satisfied | Workbench/Voice Plaza 均按 selected primary 过滤 Taxonomy；Unit + Browser 验证未选父级子项不可见。 |
| R5 | 取消一级后清理失效二级，不允许隐藏条件继续查询 | #652 / AC5 | satisfied | 两个 Store 均把父子关系作为状态不变量；声音广场 Browser 最终请求只含剩余合法 secondary。 |
| R6 | 同维度 OR、一级与二级维度 AND，保持工作台一致 | #652 / AC6 | satisfied | 已复核 Workbench SQL；Content projection/fallback 改为两个独立维度条件；PostgreSQL cross-pair 回归证明不要求同一 label pair。 |
| R7 | List/Count/query-scope Analysis/query-scope Export 共用多选 Filter Snapshot | #652 / AC7 | satisfied | Voice Plaza `filterSnapshot()` 是列表、Count、query export 的共同来源；后端 `ContentTargetSelection.filters` 同时供 Analysis freeze 与 Reporting freeze 使用。 |
| R8 | projection 与 fallback PostgreSQL 路径一致 | #652 / AC8 | satisfied | 实际 PostgreSQL 测试先走 ready projection，再把 projection state 置 pending 走 fallback，cross-pair 查询结果一致。 |
| R9 | plural Contract + legacy singular 兼容 | #652 / AC9 | satisfied | API 回归验证 repeated plural；同一测试验证 legacy singular 被归一化为 singleton plural；OpenAPI/Orval generation + compatibility clean。 |
| R10 | Workbench 多标签深链与 legacy singular 深链兼容 | #652 / AC10 | satisfied | Workbench 生成 repeated plural route；Voice Plaza 优先恢复 plural、回退 singular；Browser 心智钻取与页面恢复路径通过。 |
| R11 | 分层验证与 generated drift/compatibility 通过 | #652 / AC11 | satisfied | Temporary Validation run 36433340226：Backend、PostgreSQL、Frontend 三 Job 全部 success；详见完成证据。 |

# 修改方案与实际实现

1. **Contract 兼容扩展**：`ContentFilterSnapshot` 新增 `primary_labels/secondary_labels`，保留 singular 并统一归一化；不做破坏性删除。
2. **Query Read Model**：projection JSONB 与 fallback AI/manual label 查询都按两个多值维度独立过滤。
3. **声音广场状态**：草稿、已应用快照、Session 恢复、筛选目录刷新统一使用 plural；目录变化时清理无效父子值并刷新已应用结果。
4. **声音广场交互**：两级 checkbox 多选；二级未选父级时不可操作；多父级时展示其子项并集；展开层级菜单参与正常布局，避免覆盖查询操作。
5. **工作台交互**：保留既有一级/二级多选，二级只按当前所选父级生成；Store 再次执行父子清理，避免只靠组件隐藏。
6. **深链**：工作台普通“查看全部声音”携带完整 plural 数组；心智维度钻取只携带被点击一级，避免把不相关二级条件带入；声音广场兼容新旧 query。
7. **生成与文档**：使用仓库正式 Contract/Orval 生成命令更新 OpenAPI/Client；产品能力文档同步当前筛选语义。

# 验证矩阵

| 验证层 | 是否要求 | 实际证据 |
| --- | --- | --- |
| Frontend Unit | required | Voice Plaza + Workbench：2 files / 51 tests passed |
| Browser Mock Acceptance | required | Voice Plaza + Workbench：37 passed |
| API / Contract | required | Stage8D Content API：11 passed；repeated plural + legacy singular 回归 |
| PostgreSQL Integration | required | PG 18.4 + Alembic head/check；目标集成 1 passed，覆盖 projection/fallback |
| Generated Client | required | Contract generate、Orval generate、git diff clean、generate --check、compatibility 均成功 |
| Backend Static / Types | required | Ruff format/check 通过；mypy 413 source files 无问题 |
| Frontend Static / Build | required | lint、目标 Unit、typecheck/Vite build 均成功 |
| Migration | not_applicable | 无 Schema/Data Migration；历史 singular snapshot 由 Contract 解析兼容 |
| Provider Probe | not_applicable | 不涉及外部 Provider |
| Release / Deploy | not_applicable | 用户未授权且本任务不执行 |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 |
| --- | --- |
| 公共 Contract | additive：新增 plural，旧 singular 保留；新版前端不再发送 singular |
| 历史 Analysis/Export Snapshot | 旧 singular 可通过现有 Pydantic Contract 恢复，无需数据回填 |
| DB / Migration | 无变化 |
| 依赖 | 无变化 |
| 性能 | 标签值上限仍受 Contract 限制；未新增额外 HTTP 往返或逐行 SQL；projection 路径继续使用已有 JSONB Read Model |
| 回滚 | 回滚本 PR 即恢复旧筛选 UI/查询逻辑；无数据恢复步骤 |
| 已知交付边界 | PR 创建后不 merge；main-fresh、Archive、Issue Closure、分支 cleanup 均留待后续明确授权 |

# 完成审计

- [x] upstream_re_read：已重读 #652 最新 AC 与用户“只提交 PR、不合并 main”的后续指令，并重读 Workbench SQL、Content Filter Contract、Analysis/Export query-scope 冻结链和最终前端状态链。
- [x] change_coverage：AC1–AC11 均映射到实现与新鲜测试；没有用 UI 多选替代后端 Contract、Count、freeze target 或 fallback 语义。
- [x] reverse_audit：从用户勾选/取消一级 → 二级候选/清理 → applied snapshot → List/Count → Analysis/Export freeze → projection/fallback 反查；从 Workbench → Voice Plaza plural/legacy deep link 反查恢复。
- [x] unresolved_cleared：实现范围内无 `not_satisfied`；Review 发现的展开菜单遮挡查询按钮已按布局根因修复并由 Browser 复验。merge/main-fresh/archive/cleanup 因用户明确限定“只提交 PR”而不属于本任务交付范围。

# 完成证据与状态

## 新鲜证据

- **生成物**：仓库正式 `scripts/contracts/generate.py` + Orval 已生成并提交；最新专项 run 36433340226 再次执行 generation、generated diff、`--check` 与 compatibility，全部成功。
- **Backend**（run 36433340226 / job 108964860119）：Ruff format 4 files already formatted；Ruff check passed；mypy **413 source files** 无问题；`tests/api/test_stage8d_contents.py` **11 passed**。
- **PostgreSQL**（run 36433340226 / job 108964860335）：PostgreSQL **18.4**，`alembic upgrade head` + `alembic check` 成功；目标集成 **1 passed, 8 deselected**，覆盖 plural/cross-pair、projection ready 与 fallback pending。
- **Frontend**（run 36433340226 / job 108964859910）：generated contract clean；Voice Plaza + Workbench Unit **2 files / 51 tests passed**；lint/build 成功；两页 Browser Mock **37 passed**。
- **Review 第一阶段**：发现层级 `details` 沿用固定 40px 高度时展开选项会覆盖底部“查询”按钮；改为 tertiary 多选展开参与布局并限制可滚动高度。另修正 Browser locator 的精确标签语义。
- **Review 第二阶段**：重新核对 AC1–AC11、final diff、工作台 SQL 与 Content projection/fallback；未发现新的 blocking finding。
- **分支新鲜度**：删除临时验证 Workflow 后，任务分支相对 `main` 为 ahead、behind 0；最终 diff 不包含临时 Workflow。

## 交付状态

- implementation: complete
- targeted validation: complete / green
- completion audit: complete
- review: no blocking findings within current scope
- PR: pending creation
- merge: explicitly not authorized
- main-fresh / Change Archive / Issue Closure / cleanup: not part of this task per latest user instruction
