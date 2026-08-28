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

`/voice-plaza` 当前业务链路已经具备 Content 查询、Cursor、Detail、Analysis Run、人工相关性复核和 Excel Export，但页面视觉仍早于已经验收 READY 的正式 Figma 基线。正式设计文件为 `EAPm8KVarUe7BFTSnzvOpT`，开发 Section `3079:328`，Normal/Data 起点 `169:10`。

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
- 实现完成后的 `frontend/README.md` 与 Figma Guide targeted 文档同步。

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

| ID | 上游要求 / 事实源 | 当前状态 | 实现 Owner / 证据 |
| --- | --- | --- | --- |
| R1 | 用户明确要求以正式 Figma 替换 `/voice-plaza` 页面表现 | not_satisfied | `169:10` + VoicePlazaPage/components |
| R2 | Figma `169:10`：复用 App Shell、Page Header、Actions、11 个筛选、Run、表格、Cursor | not_satisfied | AppShell / Shared UI / Voice Plaza Feature |
| R3 | Figma `3083:134/351/568`：Loading/Empty/Error | not_satisfied | VoicePlazaTable/Page + Browser Mock |
| R4 | Figma `3085:654`：Runtime 未配置时 Warning + AI disabled，列表仍可用 | not_satisfied | Store capability + Page |
| R5 | Figma `3084:311`：610px Detail Drawer，同时保留真实 supplement/媒体/评论能力 | not_satisfied | ContentDetailDrawer |
| R6 | Figma `3084:568`：selected-only Analysis Preview/Create，动态 Preview 数据 | not_satisfied | AnalysisSubmitDialog + current Store/API |
| R7 | Figma `3084:770`：selected/page/query Export、进度、下载、7天保留 | not_satisfied | DataExportDialog + TaskProgressBar + artifactRetention |
| R8 | Figma/Guide：公共组件按真实 Owner 复用，不机械创建第二套组件库 | not_satisfied | AppShell/shared/ui + Review |
| R9 | 当前 Contract/Feature：不改变 Cursor、Analysis、Review、Export、Detail 业务语义 | not_satisfied | existing unit/E2E + generated diff zero |
| R10 | 用户要求实现后 targeted visual review、Review、CI、正常合并 main | not_satisfied | Fresh screenshots + PR/CI/main evidence |

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

| 维度 | 级别 | 计划 |
| --- | --- | --- |
| Voice Plaza unit/component | required | Vitest：现有行为 + Design-to-Code 结构/状态回归 |
| Shared UI regression | required if modified | 相关 Vitest / App Shell 回归 |
| Lint / Typecheck / Build | required | 当前 `frontend/package.json` 脚本 |
| Browser Mock Acceptance | required | Playwright：Normal、Runtime unavailable、Detail、Analysis、Export；补 Loading/Empty/Error 视觉状态 |
| 1440×900 Fresh Figma visual review | required | Fresh Figma Screenshot ↔ Playwright capture/结构尺寸证据 |
| Contract/generated | required | generated 目录无手工 diff；仓库 CI Contract gate |
| Backend/API/PostgreSQL | regression-by-CI | 本 Change 不改接口/后端；执行仓库永久 CI，不能由 Browser Mock 冒充 |
| Real Full-stack | targeted regression | wiring 未变时复用现有 Golden Path/仓库门禁；若 wiring 改动则运行相关 fullstack spec |
| External Provider probe | not_applicable | 页面视觉同步不调用 TikHub/LLM Provider |
| Docs/Governance | required | Docs targeted review + Completion Audit + Ready Check |

# 实施步骤

- [x] 恢复最新 `main`、AGENTS/Coding/Figma Skill、目标 Feature、正式 Figma Design Context。
- [x] 建立 Design-to-Code 回归测试并取得正确 Red 证据。
- [ ] 最小修改 Shared/Page/Feature Owner，使 Normal 与状态稿对齐。
- [ ] 补齐 Browser Mock 状态覆盖和 1440×900 验收证据。
- [ ] targeted 同步 Frontend README / Figma Guide。
- [ ] 重新读取上游事实，完成 Completion Audit。
- [ ] 执行两阶段 Review，修复所有阻塞 Finding。
- [ ] Ready Check + 永久 CI 全绿，PR 合并 main。
- [ ] 合并后 main 再验证并归档 Change。

# Red 证据

2026-08-29 在 PR #272 首个 Head `5888d815de5558c5c0d0240e54849844d36605a5` 上，GitHub Actions CI run `33201933092` / Repository Quality job `98953507650` 实际执行前端完整门禁：

- 原有 `frontend/tests/voice-plaza.spec.ts`：11/11 通过；
- 新增 `frontend/tests/voice-plaza-design.spec.ts`：3/3 因正式 Figma 差距失败；
- 失败点分别为未复用 `AimaPageHeader`、缺筛选事实源说明、缺正式 Empty/Error 状态；
- 总计 53 passed / 3 failed，exit code 1。

因此 Red 失败来自当前页面与正式设计基线的已确认差距，不是现有 Voice Plaza 业务行为基线损坏。

# Completion Audit

- [ ] A1：重新读取用户目标、正式 Figma、当前 Contract/Feature，重建完成定义。
- [ ] A1：检查“上游要求 → Change”无遗漏，`not_satisfied` 清零。
- [ ] A2：逐项检查“Change → 实现 / 测试 / 文档 / 运行证据”。
- [ ] 反向能力审计：当前 Voice Plaza 后端/Store 能力仍有正确前端入口。
- [ ] 反向动作审计：页面每个可执行动作都有真实系统支持。
- [ ] Figma DESIGN_EXAMPLE 未进入 production constant。
- [ ] generated Client 无手工修改，依赖/Schema/API 无无关变化。
- [ ] Fresh Figma 与实际页面 targeted review 无阻塞偏差。

# Git / 交付

用户已明确授权本任务建立开发分支、中文提交、创建 PR、处理 CI/Review、正常合并 `main`、合并后验证与分支清理。不得绕过仓库现有质量门禁。实现 Change 合并后按仓库惯例通过独立归档 PR 移入 `changes/archive/2026-08/`。
