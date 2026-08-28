---
schema: rvc-change/v1
id: "CHG-20260828-collection-runtime-figma-sync"
title: "采集运行中心同步正式 Figma 并复用公共组件"
level: L2
status: in_progress
owner: "chatgpt"
branch: "feature/collection-runtime-figma-sync"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "frontend"
  - "design-system"
  - "tests"
affected_paths:
  - "frontend/src/features/import-batches/pages/CollectionRuntimePage"
  - "frontend/src/shared/ui"
  - "frontend/tests"
  - "frontend/e2e"
contracts: []
data_changes: []
---

# 目标

把 Figma 文件 `YkXhqg39cnZxWLuEyPRKSO` 中 `225:5` 页面下的正式开发基线 `1252:766` 同步到仓库现有 `/collection-runtime` 页面。在不改变 Collection Runtime、Data Import Campaign、Collection Run、Provider Capability、Cursor 和 generated client Contract 的前提下，使页面主视觉、弹窗/抽屉、状态反馈与正式 Figma 一致，并复用“采集策略”已经使用的 AIMA 公共组件。

# 已确认事实与方案

- 当前目标路由实现位于 `frontend/src/features/import-batches/pages/CollectionRuntimePage/`。
- “采集策略”已复用 `AimaPageHeader`、`AimaButton`、`AimaFeedbackBanner`；“采集运行中心”仍有私有 Header/Button/Feedback 样式。本次优先复用现有共享组件，不新增无必要抽象。
- Figma 主画板为 1440×900；AppShell 已提供 180px Sidebar、60px TopBar 与 24px Workspace inset，因此不复制 Figma Shell。
- Figma 示例数字、文件名、ID、时间仅是展示数据态；生产值继续由 Store / generated client / API / Capability 注入。
- Provider/Platform/Search 参数继续由 `/api/v1/collection-capabilities` 驱动，不把 Figma 示例平台能力硬编码到前端。

# 成功标准

- [ ] `/collection-runtime` 的标题、动作、KPI、页签、筛选、运行表格与分页层级匹配正式 Figma。
- [ ] 页面标题区和主要/次要按钮复用与“采集策略”相同的 `AimaPageHeader` / `AimaButton`；通用 Info/Warning/Error 反馈优先复用 `AimaFeedbackBanner`。
- [ ] 主动作文本为“新建辅助补采”，页面说明为“统一查看数据导入与辅助补采运行”，KPI 使用“今日入库内容”。
- [ ] 筛选顺序为搜索 → 创建时间范围 → 状态 → 类型 → 阶段，辅助说明仅保留“时间按北京时间解释”，不把 Cursor 实现细节展示给普通用户。
- [ ] Data Import Modal、辅助补采 Drawer、Import/Run Detail Drawer 保持固定 Header/Footer、正文独立纵向滚动，并覆盖 Figma 中加载、空、失败、部分失败、完成、Provider 不可用等真实状态。
- [ ] 不改变现有 HTTP Contract、Store 业务语义、数据库、Migration、依赖版本、生成代码或路由边界。
- [ ] 新增最小回归测试证明 Figma 关键文案、布局语义和共享组件复用；现有 frontend unit/type/lint/build/browser acceptance 全绿。
- [ ] PR 永久 CI 全绿、两阶段 Review 无严重/重要 Finding 后合并 main，并对合并后的 main 获取新鲜验证证据。

# 范围与非目标

范围：采集运行中心页面及其现有子组件的视觉/展示结构、最小共享 UI 复用、对应前端测试和必要文档同步。

非目标：不改后端 API、Pydantic Contract、OpenAPI、Orval generated client、PostgreSQL Schema、Migration、Worker/Job 行为、TikHub 请求协议、采集策略业务逻辑；不因 Figma 中未来 IA 创建死链或假页面；不新增第三方依赖。

# 不变量与兼容边界

- `CollectionRuntimePage` 的 polling、refresh、select/open/copy/viewContents/createRun 调用链保持不变。
- `CollectionRuntimeFilters` 的 v-model 与 `search/reset` emits 保持不变。
- `DataImportDialog` 的来源选择、写入策略、.xlsx 校验、Campaign 创建/开始/取消/重试及 AI 不自动执行语义保持不变。
- `TikHubSupplementDrawer` 的 Capability 过滤、Discovery/Batch Supplement、平台参数、评论/二级回复依赖保持不变。
- 所有现有公共路由与 API 请求形状保持兼容。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 将指定 Figma 正式基线同步到“采集运行中心” | user:2026-08-28-figma-runtime-sync | in_progress | Figma `1252:766/1252:768` 已读取；待实现/验证 |
| R2 | 与“采集策略”复用适合的公共组件 | user:2026-08-28-shared-components | in_progress | 已确认 Strategy 使用 AimaPageHeader/AimaButton/AimaFeedbackBanner；待 Runtime 复用 |
| R3 | 不依据 Figma 示例伪造后端事实或第二套 Capability | AGENTS.md | in_progress | 当前 Contract/Store/Capability 已读取；实现阶段保持不变 |
| R4 | 验证通过后通过 PR 合并 main | user:2026-08-28-merge-main | in_progress | 待 CI/Review/merge/main 验证 |

# Validation Matrix

| Layer | Required | Planned Evidence |
| --- | --- | --- |
| Unit / Component | required | `npm --prefix frontend run test -- --run`，新增 runtime design 回归测试 |
| Type / Lint / Build | required | `npm --prefix frontend run lint`、`typecheck`、`build` |
| Browser Mock Acceptance | required | `npm --prefix frontend run test:e2e`，覆盖 runtime 主流程或现有相关场景 |
| Contract / Generated | required | 永久 CI generate + Orval + drift/compatibility；期望零差异 |
| PostgreSQL / Backend | required_by_repo_ci | 永久 CI 全量门禁；本次不修改后端语义 |
| External Provider Probe | not_applicable | 不改 Provider 协议/外部调用能力 |
| Docs / Governance | required | `check_docs.py`、Change completion gate |

# TDD / 实施计划

1. Red：新增 SSR 组件验收，表达共享 PageHeader/Button、Figma 正式文案、KPI 与筛选顺序/说明；在旧实现上确认失败。
2. Green：最小修改 Runtime 页面/KPI/Filters；复用现有共享 AIMA 组件。
3. Green：按 Figma 统一 Data Import、辅助补采与详情 Drawer 的尺寸、滚动、反馈和按钮层级，不改变业务逻辑。
4. Refactor：只删除本次被共享组件替代的重复私有样式，避免跨业务无关重构。
5. 验证：frontend unit/type/lint/build/e2e + 仓库永久 CI。
6. Review：A1 需求符合性、A2 代码质量/测试充分性；修复后 re-review。
7. PR 合并 main，读取 main 新 SHA 与 push CI 作为最终证据。

# 文档影响

当前 `docs/guides/01_Figma与前端设计开发工作流.md` 已定义公共组件优先与 Design-to-Code 规则，本次不改变架构/Contract。若实现形成新的长期公共组件或修改既有开发约束，再同步该文档；仅页面视觉同步本身不新增重复说明。

# Git / PR 状态

- base: `main@3484cebbe1ab94e689ddc774b92ae1db10b000e1`
- branch: `feature/collection-runtime-figma-sync`
- PR: pending
- merge: pending

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# Review

## A1 需求符合性

待实现后独立重建并审查。

## A2 代码质量与测试充分性

待实现后独立审查。
