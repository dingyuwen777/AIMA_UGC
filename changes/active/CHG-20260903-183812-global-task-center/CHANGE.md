---
schema: coding-change/v1
id: CHG-20260903-183812-global-task-center
title: 全局任务中心与声音广场任务信息架构收口
level: L2
status: in_progress
owner: chatgpt
branch: feature/330-global-task-center
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - voice-plaza
  - collection-runtime
  - reporting
  - documentation
affected_paths:
  - frontend/src/app/layouts/AppShell.vue
  - frontend/src/features/task-center/
  - frontend/src/features/voice-plaza/
  - frontend/src/shared/ui/AimaIcon.vue
  - frontend/tests/
  - frontend/e2e/
  - frontend/README.md
  - docs/blueprint/04_后端任务API与前端.md
contracts: []
data_changes: []
---

# 目标

把后台任务状态从各业务页面的长期大块展示中收口为统一的全局任务入口，同时保持各业务 Owner、现有 generated client/API Contract 和专业运行页面职责不变。

本 Change 的上游 Requirement Source 是 GitHub Issue #330；本文件只承担施工、验证和完成门禁，不创建第二套成功标准。

# 当前事实与已确认决定

- `AppShell` 当前右上角已经承载消息中心、用户信息和头像，是跨业务页面稳定存在的全局 UI Owner。
- 声音广场当前在筛选区和“声音记录”之间逐条渲染完整 `AI Analysis Run 历史`，终态 Run 会持续占据正文空间。
- Analysis Run、Collection Runtime、Data Export 已分别存在正式 read API/generated client；Collection Runtime 本身已经统一投影 Excel Import 与 Collection Run，但不改变它们的物理业务 Owner。
- 用户已确认采用“全局任务中心固定入口 + 页面仅显示与当前页面直接相关的活动任务”的信息架构。
- 本 Change 不修改 Analysis Run 数据库保留期；不新增统一 Job 表或统一后端 Task API；不修改 Schema/Migration；不升级依赖或 Runtime。

# 范围

1. 在 `AppShell` 右上角新增全局任务中心入口与右侧 Drawer。
2. 任务中心通过现有 generated client 聚合 Analysis Run、Collection Runtime、Data Export 的只读状态，区分活动任务与最近完成任务。
3. 声音广场移除完整历史 Run 大卡片，只保留 `queued/running/cancelling` Analysis Run 的紧凑状态条，并可打开任务中心。
4. 保持采集运行中心作为 Collection Runtime 完整筛选、详情和业务管理页面。
5. 保持消息中心负责通知，任务中心只负责后台任务状态、进度与快速跳转。
6. 补齐目标组件/Store、Browser 用户工作流、构建和治理验证，并同步当前架构/前端说明。

# 非目标

- 不决定或实现 Analysis Run 自动清理/数据库保留周期。
- 不新增或迁移数据库表、Migration、Job Runtime 或统一后台 Task Contract。
- 不重做采集运行中心。
- 不把消息通知与任务状态合并。
- 不引入第二套 Router、State、UI Library、API Client 或测试框架。
- 不做与本需求无关的页面视觉重构。

# 必须保持不变

- 现有 Analysis Run、Collection Runtime、Data Export API 语义与 generated client 事实源保持不变。
- Voice Plaza 的 AI 打标创建、取消、内容刷新、导出和其他业务能力保持现有 Owner。
- Collection Runtime 的完整运行列表、筛选、详情入口保持可用。
- 当前 Vue/Pinia/Vue Router/Element Plus/npm/Node 版本和前端构建测试体系保持不变。
- 任何新增/修改函数继续提供与复杂度匹配的中文函数级说明。

# Requirement Traceability

| Requirement | Source | Status | Evidence / 依据 |
| --- | --- | --- | --- |
| AC1 全局入口 | GitHub Issue #330 / AC1 | not_satisfied | 待实现 AppShell 全局入口、活动数量与右侧 Drawer，并由组件/Browser 验证。 |
| AC2 统一聚合 | GitHub Issue #330 / AC2 | not_satisfied | 待复用三个现有 generated-client read model，验证活动/最近完成、进度、摘要、时间和业务跳转。 |
| AC3 声音广场降噪 | GitHub Issue #330 / AC3 | not_satisfied | 待删除正文历史 Run 区，只保留活动 Analysis Run 紧凑状态。 |
| AC4 职责保持 | GitHub Issue #330 / AC4 | not_satisfied | 待验证 Collection Runtime 仍是专业管理页、消息中心仍独立。 |
| AC5 兼容边界 | GitHub Issue #330 / AC5 | not_satisfied | 待确认 diff 无 Schema/Migration/API Contract/依赖版本变化，并执行生成物/架构相关回归。 |
| AC6 验证与文档 | GitHub Issue #330 / AC6 | not_satisfied | 待完成测试、build、docs、Completion Audit、Review、PR CI 与合并后验证。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Task Center 聚合/排序/状态映射/活动计数；Voice Plaza 仅渲染活动 Run；AppShell 固定入口。 |
| 接口 / Contract | not_applicable | 本 Change 不改变公共 API/Schema/generated client；完成前检查 generated client 未被手改且现有 Contract 回归保持。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改变后端、数据库、Worker、Artifact 或持久化语义；任务中心只消费现有只读接口。 |
| 用户 / Workflow Acceptance | required | Browser Mock：任意业务页可打开任务中心；可看到 Analysis/Collection/Export；Voice Plaza 不再展示终态历史大块；活动 Run 可查看/取消。 |
| 跨组件 Golden Path | required | 使用仓库现有 Full-stack 运行链验证至少一个真实页面可通过真实前后端读取既有任务接口，不扩大为状态穷举。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub、LLM 或其他外部 Provider 边界，不需要真实付费/外网 Probe。 |
| Build / Package / Runtime | required | 前端 lint/typecheck/test/build；仓库现有受影响 CI/Browser/full-stack 门禁。 |
| Docs / Governance / Other | required | CHANGE Ready、Issue/PR Traceability、Blueprint/frontend README 同步、架构/Secret/生成物等当前仓库门禁。 |

# User Journey / Black-box Matrix

| 场景 | 用户目标 | 初始状态 | 操作 | 预期结果 | 证据层 |
| --- | --- | --- | --- | --- | --- |
| J1 全局查看任务 | 从任意业务页查看后台任务 | 同时存在活动 Analysis/Collection/Export | 点击右上角任务中心 | Drawer 打开；活动数正确；三类任务按统一信息层级显示，可跳转对应业务页 | Browser Mock |
| J2 声音广场聚焦内容 | 浏览声音记录而不被历史任务挤占 | 存在终态 Analysis Run | 进入声音广场 | 不出现完整 `AI Analysis Run 历史`；终态 Run 不占正文 | Component + Browser Mock |
| J3 活动 AI 任务 | 观察正在打标的进度并处理取消 | 存在 queued/running/cancelling Run | 进入声音广场/点击任务中心 | 正文只出现紧凑活动状态；任务中心显示完整摘要；可取消允许取消的 Run | Component + Browser Mock |
| J4 专业运行管理 | 查看采集运行完整信息 | 存在 Collection Runtime 记录 | 从任务中心进入采集运行中心 | 专业页面仍提供原有完整列表/详情，不被任务中心替代 | Browser/Regression |
| J5 通知职责独立 | 查看消息与任务状态 | 同时存在通知和活动任务 | 分别打开消息中心、任务中心 | 两个入口和面板独立，语义不混用 | Component + Browser Mock |

# 实施步骤

1. 先补目标测试和 Browser 断言，验证当前代码缺少全局任务中心且声音广场仍展示历史 Run（Red）。
2. 新建 `task-center` Feature，直接复用 generated client，把三个既有 read model 规范化为前端只读 ViewModel；不复制后端业务状态机。
3. 在 `AppShell` 接入全局入口/Drawer；在共享图标体系补任务图标。
4. 将 Voice Plaza 历史 Run 卡片替换为活动 Run 紧凑状态条，并复用任务中心打开能力；不搬走 Voice Plaza 自己的创建/取消/轮询业务 Owner。
5. 更新 Browser Mock 场景与受影响文档。
6. 运行目标测试、前端全量测试、lint/typecheck/build、必要 full-stack/CI；修复真实回归。
7. 重新读取 #330，执行 Completion Audit、独立 Review、Ready gate、PR CI；仅在证据充分且 `main` 基线仍满足交付门禁时合并。

# Completion Audit

- upstream_re_read: pending
- change_coverage: pending
- reverse_audit: pending
- unresolved_cleared: pending

# Evidence Ledger

当前仅建立需求、范围和验证计划；实现与验证证据将在本轮执行后更新，不以计划替代执行结果。

# Git / Delivery 状态

- Requirement Source: GitHub Issue #330
- Base: `main@727eade486e32329d8d1c40cd9a15168ec121de0`
- Branch: `feature/330-global-task-center`
- PR: 未创建
- Merge: 未执行
- Release/Deploy: 不属于本 Change
