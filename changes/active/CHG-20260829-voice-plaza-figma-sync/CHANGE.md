---
schema: rvc-change/v1
id: "CHG-20260829-voice-plaza-figma-sync"
title: "声音广场正式 Figma 基线同步"
level: L2
status: in_progress
owner: "chatgpt"
branch: "feature/voice-plaza-figma-sync"
created: 2026-08-29
updated: 2026-08-29
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma-design-to-code
  - documentation
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/shared/
  - frontend/tests/
  - frontend/e2e/
  - frontend/README.md
  - docs/guides/01_Figma与前端设计开发工作流.md
contracts: []
data_changes: []
---

# 背景与现状

`/voice-plaza` 业务链路已经具备 Content 查询、Cursor、Detail、Analysis Run、人工相关性复核和 Excel Export，但本 Change 开始时页面视觉仍早于已经验收 READY 的正式 Figma 基线。正式设计文件为 `EAPm8KVarUe7BFTSnzvOpT`，开发 Section `3079:328`，Normal/Data 起点 `169:10`。

本 Change 只同步页面视觉、状态表达和交互组合，不重做后端业务能力，不改变 Pydantic/OpenAPI/generated client、数据库 Schema 或 Analysis/Export 业务语义。

# 目标

- 让 `/voice-plaza` 的 Normal、Loading、Empty、Error、AI Runtime 未配置、Detail Drawer、AI Analysis Preview、Export Dialog 与正式 Figma 基线一致。
- 继续复用现有 App Shell、Shared UI、TaskProgressBar、Artifact retention 和 Voice Plaza Feature Owner。
- 保持当前真实 API/Store/人工复核/Analysis/Export/Cursor 行为不变。
- 使用 Browser Mock 覆盖用户可见状态，并在 1440×900 参考 Viewport 做 Fresh Figma 对照。

# 范围

## Included

- `VoicePlazaPage` 页面组合与样式。
- `VoicePlazaFilters`、`VoicePlazaTable`、`ContentDetailDrawer`、`AnalysisSubmitDialog`、`DataExportDialog` 的 Figma 对齐。
- 仅在真实公共 Owner 存在缺口时最小扩展 Shared UI，例如语义图标。
- Voice Plaza Design-to-Code 回归测试、相关 Browser Mock E2E。
- 实现完成后的 `frontend/README.md` 与 Figma Guide targeted 文档复核/同步。

## Excluded

- 新后端 API、Schema/Migration、Analysis taxonomy、Export 格式变化。
- Query Scope Analysis Run。
- 车型/车系筛选、假总页数、内容存档、传播记录、自定义导出字段、消息中心、未来 Route。
- React、Tailwind、第二套 UI Library/Store/Router/API Client。
- 全站字体迁移；Figma 的 Noto Sans SC 作为设计标准，本 Change 不静默改变全局字体交付。

# 必须保持不变

- Vue 3 + TypeScript + Vite + Pinia + Vue Router 与当前锁定依赖。
- Pydantic → OpenAPI → Orval → `frontend/src/generated/api/` 唯一 Contract 链，generated 文件禁止手改。
- Content Cursor 查询和真实筛选语义。
- AI Runtime `configured` 安全能力投影。
- 显式选择 1—1000 条 → Preview → Create Analysis Run → Run History/Progress/Cancel。
- `relevant / irrelevant / inherit_ai` 人工相关性复核及 AI 原判保留。
- Excel Export 的 selected/page/query、后台 Job、下载和 7 天 Artifact retention。
- Detail 的媒体、完整标签、互动、评论 Coverage 和 supplement 状态。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 以正式 Figma 替换 `/voice-plaza` 的页面视觉与交互组合 | user:声音广场正式Figma同步任务 | satisfied | `frontend/src/features/voice-plaza/pages/VoicePlazaPage/`；Fresh Figma ↔ 1440×900 Browser Visual Evidence |
| R2 | Normal/Data 复用 App Shell、Page Header、Actions、11 个筛选、Run、表格和 Cursor | external:Figma-EAPm8KVarUe7BFTSnzvOpT-169:10 | satisfied | `VoicePlazaPage.vue`、`VoicePlazaFilters.vue`、`VoicePlazaTable.vue`；`frontend/e2e/voice-plaza-design.spec.ts` Normal 场景 |
| R3 | Loading / Empty / Error 使用正式状态稿，状态卡不保留数据表头或虚构分页 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3083:134-351-568 | satisfied | `VoicePlazaTable.vue`；Browser Mock 状态验收；Empty 菱形图标 Red→Green |
| R4 | AI Runtime 未配置时展示 Warning、禁用 AI 打标，同时列表和非 AI 操作仍可用 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3085:654 | satisfied | `VoicePlazaPage.vue`；`frontend/e2e/voice-plaza-design.spec.ts` Runtime unavailable；现有 Voice Plaza E2E |
| R5 | Detail 使用 610px Drawer，同时保留 supplement、媒体、评论等真实能力 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3084:311 | satisfied | `ContentDetailDrawer.vue`；1440×900 geometry + Browser Mock；既有 detail/supplement 单测 |
| R6 | Analysis 使用 selected-only Preview/Create，并显示当前真实 Preview 数据 | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3084:568 | satisfied | `AnalysisSubmitDialog.vue` + existing Store/API；540×446 geometry + Browser Mock |
| R7 | Export 保留 selected/page/query、进度、下载和 7 天 Artifact retention | external:Figma-EAPm8KVarUe7BFTSnzvOpT-3084:770 | satisfied | `DataExportDialog.vue` + `TaskProgressBar.vue` + `artifactRetention.ts`；650×690 Browser Mock；既有 retention E2E |
| R8 | 公共部分复用真实 Shared Owner，不机械建立第二套组件库 | external:Figma-Design-to-Code-owner-mapping | satisfied | `AimaPageHeader`、`AimaButton`、`AimaFeedbackBanner`、`AimaIcon` 复用；Feature 私有组件仍留 Page Owner |
| R9 | 不改变 Cursor、Analysis、人工复核、Export、Detail、Contract/generated 业务语义 | repo:frontend/src/features/voice-plaza | satisfied | Store/API 无本 Change 语义改写；CI generated drift gate 通过；Runtime/Full-stack/PostgreSQL 回归通过 |
| R10 | targeted visual review、正式 Review、永久 CI 后再进入 Ready 并正常合并 main | user:本任务Git与交付授权 | pending_review | Visual Evidence 与永久 CI 已完成；正式独立 Review、Ready、merge/main 验证仍按 Git/交付步骤执行 |

# Design-to-Code 映射

| Figma | 代码 Owner | 动作 |
| --- | --- | --- |
| AIMA/侧边栏 + 顶部栏 | `app/layouts/AppShell.vue` | reuse |
| AIMA/页面标题区 | `shared/ui/AimaPageHeader.vue` | reuse |
| AIMA/按钮 | `shared/ui/AimaButton.vue` | reuse |
| Feedback | `shared/ui/AimaFeedbackBanner.vue` | reuse |
| 语义图标 | `shared/ui/AimaIcon.vue` | reuse / 仅缺失时最小扩展 |
| Analysis/Export progress | `shared/TaskProgressBar.vue` | reuse |
| Artifact 7天语义 | `shared/artifactRetention.ts` | reuse |
| Filter/Table/Run | Voice Plaza Page/Feature | modify, keep feature-private |
| Detail/Analysis/Export overlays | Voice Plaza Page components | modify, keep feature-private |

# Validation Matrix

| 维度 | 级别 | 当前证据 |
| --- | --- | --- |
| Voice Plaza unit/component | required | `frontend/tests/voice-plaza.spec.ts` + `voice-plaza-design.spec.ts`；当前 CI Vitest 门禁通过 |
| Shared UI regression | required if modified | App Shell / shared UI 相关 Vitest 与完整前端测试门禁通过 |
| Lint / Typecheck / Build | required | CI Repository Quality 通过 |
| Browser Mock Acceptance | required | Playwright 覆盖 Normal、Loading、Empty、Error、Runtime unavailable、Detail、Analysis、Export；当前 CI 通过 |
| 1440×900 Fresh Figma visual review | required | Visual Evidence run `33225606958`，8 张 1440×900 截图；Fresh Figma targeted 对照无阻塞差异 |
| Contract/generated | required | CI 重新生成 Contract/Orval 后 `git diff --exit-code` 与 compatibility gate 通过 |
| Backend/API/PostgreSQL | regression-by-CI | CI PostgreSQL Integration 通过；本 Change 无后端 diff |
| Real Full-stack | targeted regression | Full-stack Acceptance run `33225609693` 通过，真实 Browser/API/Worker/PostgreSQL 链路未回归 |
| External Provider probe | not_applicable | 页面视觉同步不调用 TikHub/LLM Provider |
| Docs/Governance | required | `frontend/README.md` targeted 复核后无需修改；Figma Guide 新增 7.2 正式基线；最终 Ready 前再跑文档/Completion Gate |

# 实施步骤

- [x] 恢复最新 `main`、AGENTS/Coding/Figma Skill、目标 Feature、正式 Figma Design Context。
- [x] 建立 Design-to-Code 回归测试并取得正确 Red 证据。
- [x] 最小修改 Shared/Page/Feature Owner，使 Normal 与状态稿对齐。
- [x] 补齐 Browser Mock 状态覆盖和 1440×900 验收证据。
- [x] targeted 复核 Frontend README，并同步 Figma Guide。
- [x] 重新读取上游事实，完成实现侧 Completion Audit。
- [ ] 执行两阶段 Review，修复所有阻塞 Finding。
- [ ] 删除临时视觉 Workflow，在无临时验证文件的最终 HEAD 上完成 Ready Check + 永久 CI 全绿。
- [ ] PR 转 Ready 并正常合并 `main`，合并后验证。
- [ ] 通过独立归档 PR 移入 `changes/archive/2026-08/` 并清理分支。

# Red / Green 证据

## 首轮 Design-to-Code Red

2026-08-29 在 PR #272 首个 Head `5888d815de5558c5c0d0240e54849844d36605a5` 上，GitHub Actions CI run `33201933092` / Repository Quality job `98953507650` 实际执行前端完整门禁：

- 原有 `frontend/tests/voice-plaza.spec.ts`：11/11 通过；
- 新增 `frontend/tests/voice-plaza-design.spec.ts`：3/3 因正式 Figma 差距失败；
- 失败点分别为未复用 `AimaPageHeader`、缺筛选事实源说明、缺正式 Empty/Error 状态；
- 总计 53 passed / 3 failed，exit code 1。

因此 Red 失败来自当前页面与正式设计基线的已确认差距，不是现有 Voice Plaza 业务行为基线损坏。

## Empty 图标 targeted Red → Green

Fresh Figma targeted review 发现 Empty 状态正式稿使用灰色圆形中的菱形语义图标，而实现仍使用 `voice` 波形图标。

- Red commit `81e26433dcc9bc1c07b88d6051b2416733d4d741` 增加 `data-aima-icon="empty"` 断言；CI run `33225185083` 精确因实际仍为 `voice` 失败，55 passed / 1 failed。
- Green commits `ae5c364b0926155a97f39f03441f388bae9d296d`、`83b1498bbc5298170820b1e0cfd68058c0c0fc89` 只新增 Shared `empty` 图标并替换 Empty 状态引用。
- Green CI run `33225387299`：Vitest 56/56、Build、Browser Mock 35/35、PostgreSQL Integration 全部通过。

# 最终视觉证据

Head `9b35d01951d5242a144a7f77a32d88d35590fe7c` 的 Visual Evidence run `33225606958` 成功生成并上传 Artifact `9706738712`：

- Artifact digest：`sha256:c765777a4863e8738ebb1622f19cf330ceabf7689e8172e2d26d6c8c2b8da6fc`；
- 实际检查 8/8 PNG，全部为 1440×900；
- 覆盖 Normal/Data、Loading、Empty、Error、Runtime unavailable、Detail、Analysis、Export；
- Fresh Figma 重新渲染 `169:10`、`3083:351`、`3085:654` 等高风险节点并与实际浏览器截图 targeted 对照；Empty 菱形已对齐，Normal/Runtime 结构和状态表达无阻塞差异；
- Figma 的帖子、Run 状态、选择数量等静态示例不作为服务器事实；浏览器原生 date 控件 Chrome 的平台差异不作为生产缺陷。

# 当前永久验证证据

Head `9b35d01951d5242a144a7f77a32d88d35590fe7c`：

- CI run `33225609695`：success；Repository Quality、PostgreSQL Integration、CI Gate 均 success；
- Runtime Acceptance run `33225609715`：success；
- Full-stack Acceptance run `33225609693`：success；
- Change Completion Gate 当前仍失败是预期状态：本文件仍为 `in_progress`，尚未完成正式 Review/Ready，不将此门禁绕过或误报为产品回归。

# 文档同步判断

- `frontend/README.md` 已 targeted 复核：现有文本已经准确描述 `/voice-plaza` 的 Page → Store → Feature API → generated client 边界、筛选/Cursor/Detail/Analysis/人工复核/Export 能力及 Shared UI 复用原则，本 Change 未新增 Route、Contract 或长期架构，因此不重复写第二份节点清单。
- `docs/guides/01_Figma与前端设计开发工作流.md` 已新增 `7.2 声音广场正式 Figma 基线`，固化正式节点、Owner 边界、1440×900 参考 Viewport、原生控件差异和分层验收规则。

# Completion Audit

- [x] upstream_re_read: 已重新读取用户目标、当前 AGENTS/Coding/Figma/Docs 规则、正式 Figma 节点、Voice Plaza Store/API/Page/Shared Owner 与当前生成 Contract 边界。
- [x] change_coverage: R1—R9 已逐项映射到实现、Browser Mock、Fresh Figma、Contract/CI/Full-stack 和文档证据；未把 Figma 示例数据扩成后端或生产常量。
- [x] reverse_audit: 已从页面所有可执行入口反向核对刷新、查询、Cursor、Detail、AI Preview/Create/Cancel、人工相关性复核、Export/Download 与 Runtime capability 均由现有真实系统能力支持。
- [ ] unresolved_cleared: 正式独立 Review、临时视觉 Workflow 清理、最终无临时文件 HEAD 的永久门禁、PR Ready/merge/main 验证和独立 Change 归档仍待执行。

# Git / 交付

用户已明确授权本任务建立开发分支、中文提交、创建 PR、处理 CI/Review、正常合并 `main`、合并后验证与分支清理。不得绕过仓库现有质量门禁。实现 Change 合并后按仓库惯例通过独立归档 PR 移入 `changes/archive/2026-08/`。
