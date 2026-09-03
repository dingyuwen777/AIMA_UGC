---
schema: coding-change/v1
id: CHG-20260903-183812-global-task-center
title: 全局任务中心与声音广场任务信息架构收口
level: L2
status: ready_for_review
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

- `AppShell` 是跨业务页面稳定存在的全局 UI Owner，任务中心入口放在其右上角并使用右侧 Drawer。
- 任务中心只聚合既有 Analysis Run、Collection Runtime、Data Export read model；没有新增统一 Job 表、Task API 或第二套状态机。
- Collection Runtime 当前正式类型包括 `excel_import`、`data_import_campaign`、`tikhub_discovery`、`tikhub_batch_supplement`；任务中心将它们转换为用户可读标签。
- Collection Runtime 列表 Contract 是 cursor 分页。任务中心先读取最近 100 条；只有存在更早历史时，才按 `queued` / `running` 状态继续翻页并合并去重，保证较早但仍活动的采集任务不会从全局活动数量中漏失。
- 声音广场只保留 `queued/running/cancelling` Analysis Run 的紧凑活动状态，终态 Run 不再长期占据正文。
- Collection Runtime 继续承担完整运行管理，Notification Inbox 继续承担通知，任务中心只负责状态聚合和快速跳转。
- 本 Change 不修改 Analysis Run 数据库保留期，不修改 Schema/Migration/API Contract/generated client，不升级依赖或 Runtime。

# 范围

1. 在 `AppShell` 右上角新增全局任务中心入口、活动任务数量和右侧 Drawer。
2. 通过现有 generated client 聚合 Analysis Run、Collection Runtime、Data Export，只读展示活动任务与最近终态。
3. 对 Collection Runtime 的既有 cursor 分页做前端消费：常见单页场景保持单请求，历史超过单页时补齐全部活动状态页。
4. 声音广场移除完整历史 Run 大卡片，仅保留活动 Analysis Run 紧凑状态条并提供任务中心入口。
5. 保持声音广场的 Analysis 创建/取消 Owner、Collection Runtime 专业运行管理 Owner 和 Notification Inbox 通知 Owner 不变。
6. 补齐 Store/API、Component、Browser 用户旅程、正式 build、文档和治理证据。

# 非目标

- 不决定或实现 Analysis Run 自动清理/数据库保留周期。
- 不新增或迁移数据库表、Migration、Job Runtime 或统一后台 Task Contract。
- 不重做采集运行中心，不合并消息通知与任务状态。
- 不引入新 Router、API Client、UI/Test Framework 或依赖升级。
- 不做与本需求无关的视觉重构、Release 或 Deploy。

# 必须保持不变

- 现有 Analysis Run、Collection Runtime、Data Export API 语义与 generated client 事实源。
- Voice Plaza 的 AI 打标创建、取消、内容刷新和导出业务 Owner。
- Collection Runtime 的完整运行列表、筛选、详情与管理能力。
- 当前 Vue/Pinia/Vue Router/Element Plus/npm/Node 版本与前端构建测试体系。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | AC1：AppShell 全局任务中心入口、活动数和右侧 Drawer | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | `AppShell.vue` + `TaskCenter.vue`；`frontend/tests/app-shell.spec.ts`；`task-center-api.spec.ts` 验证 Collection Runtime 历史超过一页时仍补齐深页活动任务；CI #3931。 |
| R2 | AC2：复用既有 Analysis / Collection Runtime / Export read model 统一聚合，不复制后台任务系统 | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | `task-center/api.ts` 仅调用 generated client；`store.ts` 统一 ViewModel、活动/终态排序、单源失败保留上次成功快照；`task-center.spec.ts` 覆盖三类任务与 `data_import_campaign`；`task-center-api.spec.ts` 覆盖 cursor 活动任务分页；Browser 同 Drawer 验证三类活动任务。 |
| R3 | AC3：声音广场移除完整历史 Run，只显示活动 Run 紧凑状态 | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | `VoicePlazaPage.vue` 仅过滤 `queued/running/cancelling`；`voice-plaza-design.spec.ts` 与 Browser 回归验证终态不占正文、活动 Run 可取消且终态转入任务中心。 |
| R4 | AC4：Collection Runtime、Notification、Task Center 职责保持独立 | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | 任务中心仅提供状态/跳转；Collection 仍链接 `/collection-runtime`；Browser 场景分别打开任务中心与“站内通知”，验证两个面板独立。 |
| R5 | AC5：无 Schema/Migration/Job/API/依赖/保留策略变化 | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | `main@3de5c431...` → implementation HEAD `a2fa3d3d...` 为 19 个预期前端/测试/文档/Change 文件，behind=0；无 backend、contracts、generated client、Migration、manifest/lock 变化。 |
| R6 | AC6：目标测试、用户可见回归、文档、required CI 和完成前复核 | https://github.com/dingyuwen777/AIMA_UGC/issues/330 | satisfied | CI #3931 / run `33770691945`：Docs/Governance、Repository Quality、CI Gate 全绿；Vitest 21 files / 99 tests；Vite production build 成功；Playwright 51/51；Runtime Acceptance #1052 与 Change Completion Gate #1800 成功；Blueprint 与 frontend README 已同步；独立 A1/A2 re-review 无剩余阻塞 Finding。 |

# Validation Matrix

| Layer | Required | Result / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | PASS：CI #3931 `npm --prefix frontend run test -- --run`，21 files / 99 tests；新增 Collection Runtime 深页活动任务分页与单页不额外请求回归。 |
| 接口 / Contract | not_applicable | 本 Change 未修改 backend Contract/OpenAPI/generated client；任务中心只消费既有 cursor/list Contract。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 未修改后端、数据库、Worker、Artifact 或持久化语义。 |
| 用户 / Workflow Acceptance | required | PASS：CI #3931 `npm --prefix frontend run test:e2e`，Playwright 51/51；覆盖三类任务同 Drawer、通知独立、终态降噪、Analysis 创建/取消/终态迁移。 |
| 跨组件 Golden Path | not_applicable | CI Scope 对当前业务 diff 判定 `profile=frontend_only`、`backend=False`、`contract=False`、`postgres=False`、`fullstack=False`；Real Full-stack Golden Path 因机器范围判定跳过，不把 skipped 伪称为通过。 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub、LLM 或其他 Provider 边界。 |
| Build / Package / Runtime | required | PASS：CI #3931 lint、TS native typecheck、`vue-tsc --noEmit`、`npm --prefix frontend run build` 均成功；Vite 8.2.1 production build，150 modules transformed。 |
| Docs / Governance | required | PASS：CI #3931 Docs and Governance / CI Gate 成功；Runtime Acceptance #1052 fast-path 成功；Change Completion Gate #1800 成功；Requirement-Source 指向 #330。 |

# User Journey / Black-box Matrix

| 场景 | 结果 | 证据 |
| --- | --- | --- |
| J1 全局查看任务 | PASS：右上角显示活动任务数；Drawer 同时展示 Analysis、Collection、Export 并提供业务页跳转；Collection 历史超过首屏时仍补齐深页活动任务 | `frontend/e2e/task-center.spec.ts` + `frontend/tests/task-center-api.spec.ts`，CI #3931 |
| J2 声音广场聚焦内容 | PASS：终态 Analysis Run 不再显示为正文历史大块 | `voice-plaza-design.spec.ts`，CI #3931 |
| J3 活动 AI 任务 | PASS：活动 Run 显示紧凑状态；创建/运行/取消后正文消失且终态在任务中心可追溯 | `voice-plaza.spec.ts` / `voice-plaza-review-regressions.spec.ts`，CI #3931 |
| J4 专业运行管理 | PASS：Collection 任务只跳转 `/collection-runtime`，未搬走专业列表/详情 Owner | Task Center ViewModel + Browser 回归 |
| J5 通知职责独立 | PASS：任务中心关闭后可独立打开“站内通知”，任务 Drawer 不与消息中心共用 | `frontend/e2e/task-center.spec.ts`，CI #3931 |

# Completion Audit

- [x] upstream_re_read: 2026-09-03 在 implementation HEAD `a2fa3d3d...` 完成前重新读取 GitHub Issue #330；AC1—AC6 和非目标未发生变化，`main` 为 `3de5c431b1df405e88efd71db164852176f47161`。
- [x] change_coverage: AC1—AC6 已逐条映射到实现、API/Store/组件测试、Browser 用户工作流、文档和 CI #3931 证据；机器 CI Scope 明确把后端/PostgreSQL/Full-stack 判定为不适用。
- [x] reverse_audit: `main@3de5c431...` 到 implementation HEAD `a2fa3d3d...` 为 19 个预期前端/测试/文档/Change 文件，behind=0；未发现 backend、Contract、generated client、Migration、依赖或无关视觉重构进入范围。
- [x] unresolved_cleared: 独立 Review 发现的 `data_import_campaign` 用户可读映射缺口、两处 Playwright strict locator 缺陷、以及 Collection Runtime 固定首 50 条导致深页活动任务可能漏算的问题均已修复并有目标回归；CI #3931 最终 99/99 Vitest、51/51 Browser 通过，A1/A2 re-review 后当前范围无未解决阻塞 Finding（NO_FINDINGS_WITHIN_SCOPE）。

# Evidence Ledger

- Red：初始 AppShell / Voice Plaza 目标测试在旧实现上 3 条按预期失败，证明缺少全局任务中心且终态历史仍占正文；不是环境失败。
- Main concurrency：开发期间 `main` 前进后，以 `main@3de5c431...` 为基底完成非 force 主线同步；最终 compare `behind=0`，保留 #329/#333 的 Data Import Campaign/辅助补采/归档事实。
- Review Finding 1：最新主线新增正式 `data_import_campaign` record type，任务中心初版缺少中文映射；已补 `数据导入` 映射及 `320 行入库` 单测。
- CI #3927/#3928：生产 lint/typecheck/unit/build 已通过，Browser 各 50/51；失败均为 Playwright strict selector 同时命中相近文案。修复 locator 后后续 Browser 51/51。
- Review Finding 2：Collection Runtime 正式 List Contract 支持 cursor 分页且单页上限 100，初版固定 `limit: 50` 不跟 `has_more`，会让更早但仍 `queued/running` 的任务从全局活动数中漏失。实现改为“最近 100 条首屏 + 仅在 `has_more` 时按活动状态翻页并合并去重”，并新增 `task-center-api.spec.ts` 2 条回归。
- Final implementation CI #3931（run `33770691945`，HEAD `a2fa3d3d785e03ef920937a4222671efe16a47db`）：
  - `npm audit --omit=dev --audit-level=high`：0 vulnerabilities；完整 audit：0 vulnerabilities。
  - `npm --prefix frontend run lint`：PASS。
  - `npm --prefix frontend run typecheck`：PASS（TS native + `vue-tsc --noEmit`）。
  - `npm --prefix frontend run test -- --run`：PASS，21 files / 99 tests；`task-center-api.spec.ts` 2/2。
  - `npm --prefix frontend run build`：PASS，Vite 8.2.1，150 modules transformed。
  - `npm --prefix frontend run test:e2e`：PASS，Playwright 51/51。
  - Docs and Governance：PASS；Repository Quality：PASS；CI Gate：PASS。
  - PostgreSQL Integration / Real Full-stack Golden Path：SKIPPED by `frontend_only` CI Scope，明确记为 not_applicable，不作为通过证据。
- Change Completion Gate #1800：PASS。
- Runtime Acceptance #1052：PASS fast-path；本 Change 未修改 runtime-owned path，因此仅证明运行时范围门禁没有被触发，不冒充真实 Full-stack。
- Docs：`frontend/README.md` 与 `docs/blueprint/04_后端任务API与前端.md` 已同步任务中心 Owner/职责和 Voice Plaza 活动 Run 语义。

# Git / Delivery 状态

- Requirement Source: https://github.com/dingyuwen777/AIMA_UGC/issues/330
- Current Base: `main@3de5c431b1df405e88efd71db164852176f47161`
- Branch: `feature/330-global-task-center`
- Implementation PR: #332，Ready；实现 HEAD `a2fa3d3d785e03ef920937a4222671efe16a47db` 已完成独立 re-review 与 required pre-merge CI。
- Merge: pending；只允许在本 Change 最终证据提交后的新 HEAD required CI 继续全绿、compare `behind=0` 且 PR 无阻塞 Review 后执行 `expected_head_sha` guarded merge。
- Post-merge: pending；合并后必须对真实 main merge SHA 执行 fresh CI、Change 独立归档、Issue acceptance/closure 和任务分支清理。
- Release/Deploy: not_applicable；本次授权不包含发布或生产部署。
