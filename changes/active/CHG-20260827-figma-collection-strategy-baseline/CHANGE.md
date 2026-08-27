---
schema: rvc-change/v1
id: "CHG-20260827-figma-collection-strategy-baseline"
title: "采集策略 Figma 开发基线与 Design-to-Code 边界"
level: L2
status: in_progress
owner: "chatgpt"
branch: "docs/figma-collection-strategy-baseline"
created: 2026-08-27
updated: 2026-08-27
completion_gate: required
depends_on: []
affected_areas:
  - "docs"
  - "frontend-design"
affected_paths:
  - "docs/guides/01_Figma与前端设计开发工作流.md"
contracts: []
data_changes: []
---

# 目标

固化当前 AIMA Figma 与 Vue/后端事实源之间的开发边界，使后续 Codex 能以正式 Figma 原型替换现有“采集策略”页面，同时把真正跨页面稳定的视觉组件沉淀为公共组件，而不把 Figma 示例数据、未来信息架构或 MCP 示例代码误当成当前后端 Contract 和已实现路由。

# 成功标准

- [x] Figma “采集策略”三个主视图、词包弹窗、Plan 新建/详情抽屉已经按当前后端能力收敛，并通过截图与 Design Context 复查。
- [x] Figma 公共 Sidebar 保留目标产品的长期信息架构，同时明确当前 Vue 只能接通真实存在的 Route，未来入口不得生成死链、伪页面或伪路由。
- [x] Figma 中 Plan、Keyword Pack、Global Relevance、Provider Config、Capability、KPI、时间和状态等示例值均被定义为展示样例；生产实现必须从 Store / generated client / API 获取真实数据。
- [x] AIMA 公共 Input、Select、Page Header 等组件通过 Component Property 表达实例文字，避免 Codex 生成“公共组件 + 覆盖文字”的重复 DOM。
- [x] 采集计划列表只保留当前有信息增量的六列；固定排序、固定采集策略和误放的 schedule_version 不再作为列表字段。
- [x] 仓库 Figma 工作流 Guide 已同步上述长期边界并重新读取验证。

# 范围

- 更新 `docs/guides/01_Figma与前端设计开发工作流.md` 的 Figma 事实源、目标 IA、动态数据和 Design-to-Code 规则。
- 记录当前采集策略 Figma 基线如何与后端 Contract/Capability、Store/API、公共组件和 Feature 组件对应。
- 保留当前代码真实路由与后端业务实现不变。

# 非目标

- 不修改 `frontend/src/features/collection-strategy/`。
- 不修改 `frontend/src/app/layouts/AppShell.vue` 或 `frontend/src/app/routes.ts`。
- 不修改 Pydantic Contract、OpenAPI、generated client、数据库或后端 Service。
- 不在本轮直接让 Codex 实施 Figma → Vue 页面替换。
- 不为未来 Sidebar 菜单提前创建代码路由、空页面或 disabled 占位导航。
- 不引入 Tailwind、React、第二套 API SDK 或新的 UI 技术栈。

# 必须保持不变

- 当前 Vue 真实路由仍以 `frontend/src/app/routes.ts` 为唯一机器事实源。
- HTTP 数据语义仍由 Pydantic → OpenAPI → Orval generated client 维护。
- Provider/Platform 的可配置 Search 字段仍由 `GET /api/v1/collection-capabilities` 动态驱动；前端继续复用当前 `CollectionSearchConfigFields.vue`，不得按 Figma 示例硬编码五平台参数。
- Figma 负责视觉、布局、状态和交互意图，不成为数据库/API Schema 的第二事实源。

# 关键决策

1. 用户明确要求保留 Figma 当前完整公共 Sidebar，作为未来产品开发方向。因此不以当前代码缺少路由为理由删除未来信息架构。
2. “Figma 目标 IA”与“当前可运行 Route”分层：设计可以先行，代码只能为当前真实 Route 接通导航；未来 Feature 真正落地后再同步 Page → Route → Sidebar。
3. Figma 中可见的词包数量、Plan 数量、Provider 名称、时间、状态、版本等均用于表达数据态布局，不能在前端写死；Codex 实施时必须重新读取当前仓库和后端 Contract。
4. 公共组件只抽稳定跨页面模式；采集策略 KPI、Plan Table、Plan Form、Keyword Pack Workspace、Relevance Config 等保持 Feature 级，不制造万能组件。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Figma 原型应可作为后续 Codex 替换现有采集策略页的视觉/交互基线 | user:当前任务 | satisfied | Figma `284:112`、`284:313`、`284:561`、`284:411`、`476:92`、`928:1320` 已修改并截图复查；`284:561` 已重新读取 Design Context |
| R2 | Figma 完整公共 Sidebar 作为未来开发方向保留 | user:保留完整Sidebar | satisfied | `AIMA/侧边栏` 未删除未来入口，组件说明已写明目标 IA 与当前 Route 分层 |
| R3 | 动态数据必须来自后端代码/API/服务器事实，不能把原型示例硬编码 | user:注意后端或服务器数据 | satisfied | KPI、Plan 行、Relevance、Provider/Capability 等 Figma 说明已标记 API 动态；当前 Contract/Service/Store 已交叉核验 |
| R4 | 后续页面应复用稳定公共组件，但业务组件不强制全局化 | user:后续页面复用公共组件 | satisfied | Input/Select/Page Header/Button/Sidebar/TopBar 等公共组件已收敛；采集策略 KPI 和业务 Pattern 保持 Feature 边界 |
| R5 | 仓库正式 Figma 开发工作流同步上述边界 | user:可以更新文档 | satisfied | `docs/guides/01_Figma与前端设计开发工作流.md` 已更新并在目标分支重新读取，确认包含目标 IA/Route、动态数据、采集策略基线与公共组件边界 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 本轮不修改生产组件代码；Figma Component Property 和 Prototype 行为通过 Figma 工具直接复查 |
| 接口 / Contract | not_applicable | 不变更 HTTP Contract；仅读取当前 Pydantic/Service/Store 作为设计约束事实源 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、运行时或第三方依赖 |
| 用户 / Workflow Acceptance | required | Figma 三个主 Tab、Modal、两个 Drawer 均已重新截图；Prototype Reaction/滚动/动态状态已审计 |
| 跨组件 Golden Path | not_applicable | 本轮不修改真实 Vue ↔ API 接线；正式 Figma → Vue 实施由后续独立开发 Change 验证 |
| External Dependency / Provider Probe | not_applicable | 不需要确认 TikHub 当前在线事实，不调用真实 Provider |
| Build / Package / Runtime | not_applicable | 不修改生产代码、依赖或构建产物 |
| Docs / Governance / Other | required | Figma Guide 已更新并按目标分支重新读取；内容与当前 routes/Contract/Frontend Guide 边界一致 |

# Completion Audit

- [x] upstream_re_read：已重新读取 `AGENTS.md`、Coding Skill、Blueprint README/04/07、Figma Guide、当前 routes/AppShell、采集策略前后端实现和 Contract。
- [x] change_coverage：已从用户目标与仓库当前事实独立重建本轮设计完成定义，未从 Change checklist 反推需求。
- [x] reverse_audit：已执行“后端能力 → Figma 字段/状态”和“Figma 交互 → 后端真实支持”审计；确认本轮不需要新增 Contract。
- [x] unresolved_cleared：Requirement Traceability 已无 `not_satisfied`；本轮不适用项均有事实依据。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立四维任务路由：Full-stack / Requirement-Design / Vue+Python / L2
- [x] 说明测试例外：本轮不改生产代码，不建立代码级 Red/Green；以 Figma 结构、Design Context、截图和文档一致性作为验证
- [x] 建立并维护 Validation Matrix
- [x] 完成 Figma 设计基线收敛
- [x] 同步受影响文档
- [x] 取得文档新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- Figma：重新截图三个主 Tab、词包 Modal、新建/详情 Drawer。
- Figma：对当前采集策略页执行旧测试字符串/旧字段零残留扫描。
- Design-to-Code：重新读取 `284:561` Design Context，确认六列表格、公共 Input/Select、动态数据 Annotation 和 Sidebar 目标 IA 说明均可被 Codex读取。
- Docs：更新后重新读取 Guide 与 Change。
- Ready Check：本轮通过 GitHub 连接器进行 Figma + 文档同步，没有本地仓库执行环境；不在未实际运行 `ready_check.py` 的情况下声称 Ready。

## 新鲜证据

- Figma 主页面与弹窗/抽屉截图均已在本轮重新生成并人工检查，无明显错位、裁切或测试 Provider 回退。
- Figma 旧字符串/旧字段扫描最终返回空结果。
- `284:561` 最新 Design Context 已确认公共 Input/Select Component Property、六列 Plan Table、动态 API 注解和完整 Sidebar 边界说明。
- Guide 已在 `docs/figma-collection-strategy-baseline` 分支重新读取：目标 IA 与真实 Route 分层、动态数据事实源、采集策略正式 Figma 基线、公共/Feature 组件边界和 Codex 固定流程均已落文档。
- 本轮未修改任何 Vue、Store、Feature API、generated client、Pydantic Contract、数据库或后端 Service。

# 文档影响

- `docs/guides/01_Figma与前端设计开发工作流.md`：已补充目标 IA 与真实 Route 分层、动态数据事实源、采集策略正式 Figma 基线和 Codex 实施规则。

# 交付

- Commit：独立文档分支已产生中文提交；不包含生产业务代码。
- PR：本轮未授权创建。
- 发布：不适用。
- 状态说明：所有设计/文档要求已经完成，但未实际运行仓库 `ready_check.py`，因此 Change 保持 `in_progress`，不伪称 `ready_for_review`。
