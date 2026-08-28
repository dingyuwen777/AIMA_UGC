---
schema: rvc-change/v1
id: "CHG-20260828-collection-runtime-figma-sync"
title: "采集运行中心同步正式 Figma 并复用公共组件"
level: L2
status: ready_for_review
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
- “采集策略”已复用 `AimaPageHeader`、`AimaButton`、`AimaFeedbackBanner`；本次让“采集运行中心”复用同一批已存在的共享组件，没有为单页新增平行设计系统。
- Figma 正式开发基线 `1252:766` 已重新读取；其中 `1252:768` 为主页面，`1252:771/772` 为本地/服务器导入，`1252:773/774` 为辅助补采，`1252:775/776` 为详情，`1279:1734`、`1294:2110/2337/2567/2802/3034`、`1296:2563/2806` 覆盖 Ready、Discovering、Running、Partial Failure、Completed、Provider 不可用、上传中和创建失败等状态。
- Figma 主画板为 1440×900；AppShell 已提供 180px Sidebar、60px TopBar 与工作区 inset，因此页面实现不复制第二套 Shell。
- Figma 示例数字、文件名、ID、时间仅是展示数据态；生产值继续由 Store / generated client / API / Capability 注入。
- Provider/Platform/Search 参数继续由 `/api/v1/collection-capabilities` 驱动，不把 Figma 示例平台能力硬编码到前端。

# 成功标准

- [x] `/collection-runtime` 的标题、动作、KPI、页签、筛选、运行表格与分页层级匹配正式 Figma 的结构和业务层级。
- [x] 页面标题区和主要/次要按钮复用与“采集策略”相同的 `AimaPageHeader` / `AimaButton`；通用 Info/Warning/Error 反馈复用 `AimaFeedbackBanner`。
- [x] 主动作文本为“新建辅助补采”，页面说明为“统一查看数据导入与辅助补采运行”，KPI 使用“今日入库内容”。
- [x] 筛选顺序为搜索 → 创建时间范围 → 状态 → 类型 → 阶段，辅助说明仅保留“时间按北京时间解释”，不把 Cursor 实现细节展示给普通用户。
- [x] Data Import Modal、辅助补采 Drawer、Import/Run Detail Drawer 保持固定 Header/Footer、正文独立纵向滚动，并覆盖加载、空、失败、部分失败、完成、Provider 不可用等真实状态；历史 Campaign 在重新打开导入入口后仍可进入继续处理。
- [x] 不改变现有 HTTP Contract、Store 业务语义、数据库、Migration、依赖版本、生成代码或路由边界。
- [x] 已新增最小设计回归测试，并以本轮永久 CI 验证 frontend unit/type/lint/build/browser acceptance、Contract、PostgreSQL 和 Full-stack 全绿。
- [ ] PR #265 在 Completion Gate 通过并转为 Ready 后正常合并 `main`，再对合并后的 `main` 获取新鲜验证证据；这是本 Change Ready 之后的交付动作，不在门禁之前提前执行。

# 范围与非目标

范围：采集运行中心页面及其现有子组件的视觉/展示结构、最小共享 UI 复用、对应前端测试和必要文档同步。

非目标：不改后端 API、Pydantic Contract、OpenAPI、Orval generated client、PostgreSQL Schema、Migration、Worker/Job 行为、TikHub 请求协议、采集策略业务逻辑；不因 Figma 中未来 IA 创建死链或假页面；不新增第三方依赖。

# 不变量与兼容边界

- `CollectionRuntimePage` 的 polling、refresh、select/open/copy/viewContents/createRun 调用链保持不变。
- `CollectionRuntimeFilters` 的 v-model 与 `search/reset` emits 保持不变。
- `DataImportDialog` 的来源选择、写入策略、.xlsx 校验、Campaign 创建/开始/取消/重试及 AI 不自动执行语义保持不变；创建按钮、历史 Campaign 入口和既有可访问名称继续保持可观察兼容。
- `TikHubSupplementDrawer` 的 Capability 过滤、Discovery/Batch Supplement、平台参数、评论/二级回复依赖保持不变。
- 所有现有公共路由与 API 请求形状保持兼容。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 将指定 Figma 正式基线同步到“采集运行中心” | user:2026-08-28-figma-runtime-sync | satisfied | 已重新读取 Figma `1252:766` 及主页面/弹窗/抽屉/状态帧；实现覆盖 Page Header、KPI、筛选、表格、导入、辅助补采和详情结构，`frontend/tests/collection-runtime-design.spec.ts` 与 31 条 Browser Mock 验证关键可观察行为。 |
| R2 | 与“采集策略”复用适合的公共组件 | user:2026-08-28-shared-components | satisfied | Runtime 已复用 `AimaPageHeader`、`AimaButton`、`AimaFeedbackBanner`、`AimaIcon`，没有新增第三方依赖或另一套跨页面 UI 抽象。 |
| R3 | 不依据 Figma 示例伪造后端事实或第二套 Capability | AGENTS.md | satisfied | PR 未修改后端 Contract/Migration/generated client；永久 CI 的 generate + Orval + drift/compatibility 通过，Provider/Platform/Search 仍由现有 Store/API/Capability 驱动。 |
| R4 | 验证通过后通过 PR 合并 main | user:2026-08-28-merge-main | explicitly_deferred | `AGENTS.md` 强制执行 Ready → Completion Gate/永久 CI/Review → merge → main 新鲜验证；当前实现 HEAD 已通过 CI/Runtime/Full-stack，合并动作按该正式门禁顺序延后到本 Change Ready 检查通过后立即执行，不是取消或弱化用户要求。 |

# Validation Matrix

| Layer | Required | Actual Evidence |
| --- | --- | --- |
| Unit / Component | required | CI #3365：Vitest 12 files / 53 tests passed，包含 `collection-runtime-design.spec.ts`。 |
| Type / Lint / Build | required | CI #3365：ESLint、TS native typecheck、`vue-tsc`、Vite build 全部成功。 |
| Browser Mock Acceptance | required | CI #3365：Playwright 31/31 passed；覆盖导入创建/取消/重试、历史 Campaign 重开、递归发现、indeterminate progress、辅助补采和详情错误状态。 |
| Contract / Generated | required | CI #3365：Contract generate、Orval、`git diff --exit-code`、Schema drift/compatibility 全部通过。 |
| Python / API | required_by_repo_ci | CI #3365：Ruff format/lint、mypy；unit 705 passed、contracts 92 passed、API 38 passed。 |
| PostgreSQL Integration | required_by_repo_ci | CI #3365：Migration、Platform/Database/Job/Collection/Content/Ingestion PostgreSQL integration 全部通过。 |
| Runtime Acceptance | required_by_repo_ci | Runtime Acceptance #486 success；本次未触及 Compose/Runtime 风险路径，因此按仓库 fast-path 验证成功。 |
| Real Full-stack Golden Path | required | Full-stack Acceptance #442：真实 API + Worker + PostgreSQL + 浏览器 6/6 passed。 |
| External Provider Probe | not_applicable | 本次不改 Provider 协议、路由或真实外部请求能力；不为视觉同步引入付费/外部探测。 |
| Docs / Governance | required | CI #3365：Secret scan 与 `check_docs.py` 通过；现有 Figma 工作流文档已覆盖本次规则，未形成新的长期架构约束。 |

# TDD / 实施记录

1. 设计回归测试固定正式业务文案、KPI、筛选顺序和共享组件复用。
2. 最小调整 Runtime 页面、KPI、Filters、Table 和三个 Dialog/Drawer 的展示结构；Store/API/Contract 调用链保持不变。
3. 永久 CI 首轮暴露视觉重构造成的可观察行为回归后，按失败证据逐项修复：创建按钮兼容、源 Excel 保留期文案、历史 Campaign 重新进入能力。
4. 修复后重新运行完整永久门禁；当前实现 HEAD `c0a165e8a681fc1caf1d058513c6c241cc93c150` 已取得 CI、Runtime Acceptance、Full-stack Acceptance 全绿证据。
5. 完成 A1 需求符合性与 A2 代码质量/测试充分性复核；未发现未解决的 BLOCKER/HIGH/MEDIUM Finding。
6. 本 Change 更新为 Ready 后重新跑 Completion Gate 和全部永久 CI；全绿后转 PR Ready、正常合并并验证 `main`。

# 文档影响

`docs/guides/01_Figma与前端设计开发工作流.md` 已规定 Figma 只负责视觉/交互、公共组件优先、后端真实能力以 Contract/Store/API 为准。本次没有新增长期架构、公共 Contract 或新的设计系统规则，因此不重复修改 Blueprint/Guide；施工事实、验证证据和交付状态由本 Change 维护。

# Git / PR 状态

- base: `main@3484cebbe1ab94e689ddc774b92ae1db10b000e1`
- branch: `feature/collection-runtime-figma-sync`
- implementation HEAD before Ready document update: `c0a165e8a681fc1caf1d058513c6c241cc93c150`
- PR: `#265`（当前 Draft；Completion Gate 全绿后转 Ready）
- merge: pending；仅在永久门禁全绿后执行

# Completion Audit

- [x] upstream_re_read: 已重新读取 `AGENTS.md`、Coding/Review Skill、Blueprint 技术门禁、Figma 工作流 Guide，并重新读取 Figma 正式开发基线 `1252:766` 及关键状态帧；未从历史对话替代当前事实。
- [x] change_coverage: 逐条重建 R1–R4；R1–R3 已由当前实现和本轮永久 CI 证明，R4 仅按仓库正式 PR 顺序延期到 Ready/Completion Gate 之后执行，没有遗漏或静默缩小范围。
- [x] reverse_audit: 已执行“后端能力 → 前端入口 / 前端动作 → 后端真实支持”反向审计；导入 Campaign 创建/开始/取消/重试/历史重开、辅助补采 Capability/平台/搜索参数均继续走既有 Store/generated client/API，未发现孤儿能力或虚假 UI 动作。
- [x] unresolved_cleared: 先前 CI 暴露的创建按钮、源文件保留期文案、历史 Campaign 入口回归均已修复并由最新 31 条 Browser Mock 与 6 条真实 Full-stack 验证；当前无未解决 BLOCKER/HIGH/MEDIUM Finding。

# Review

## A1 需求符合性

结论：通过，当前实现没有未解决的需求符合性 Finding。

- 正式 Figma 基线已重新核对，页面主结构、Modal/Drawer 尺寸与固定 Header/Footer + Body Scroll 结构、Ready/Running/Partial Failure/Completed/Provider 不可用等状态均有对应实现路径。
- 用户要求的业务文案和共享组件复用已经落地；Figma 示例数据未进入业务真相层。
- 首轮 Review/CI 发现的可观察行为回归均已根因修复，而不是修改/删除失败测试规避：`.create-button` 与既有 aria 契约恢复、源 Excel 保留提示恢复、历史 Campaign 在创建态恢复可进入。
- R4 的合并只因正式仓库门禁顺序尚未执行，已显式记录为交付阶段延期；Completion Gate 全绿后继续执行，不作为已完成事实提前宣称。

## A2 代码质量与测试充分性

结论：通过，未发现未解决的 BLOCKER/HIGH/MEDIUM Finding。

- 修改集中在现有 `CollectionRuntimePage` 及其子组件，没有改 Contract、Migration、依赖、后端接口或 generated client。
- 共享 UI 复用基于仓库已有 `AimaPageHeader` / `AimaButton` / `AimaFeedbackBanner` / `AimaIcon`，未创建无证据的新抽象层。
- 当前 permanent CI 已覆盖 lint/type/build、53 条 frontend unit/component、31 条 Browser Mock、Python unit/contracts/API、PostgreSQL integration；真实 Full-stack 6/6 passed。
- External Provider probe 不适用：本次没有改变 Provider 请求协议、Operation 选择或外部响应映射。
- 剩余视觉风险边界：本轮以 Figma 正式节点结构核对、组件级设计测试和浏览器行为验收为证据，没有建立像素级 screenshot diff，因此不把“逐像素完全一致”作为已验证结论；该限制不影响本 Change 已定义的结构、交互和业务兼容验收。
