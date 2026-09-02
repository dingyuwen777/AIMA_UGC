---
schema: coding-change/v1
id: CHG-20260902-collection-runtime-figma-sync
title: 同步采集运行中心 Figma 与真实后端契约
level: L2
status: done
owner: dingyuwen777
branch: fix/302-collection-runtime-figma-sync
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma-design-to-code
  - testing
affected_paths:
  - frontend/src/features/import-batches/pages/CollectionRuntimePage/
  - frontend/tests/collection-runtime-design.spec.ts
  - frontend/e2e/collection-runtime.spec.ts
  - frontend/e2e/excel-import-submit-state.spec.ts
  - frontend/e2e/historical-migration.spec.ts
  - changes/active/CHG-20260902-collection-runtime-figma-sync/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

正式 Figma `release / 采集运行中心`（node `3500:2023`）已经以当前后端 Contract 为事实源收敛：采集运行主表固定 7 列，“关联对象”不单独占列；Data Import Campaign 只在后端 `can_start=true` 时提供“开始导入”；辅助补采产品文案保持 Provider-neutral。当前 Vue 页面原先存在 8 列表格、非 Ready Campaign 的禁用“开始导入”占位动作，以及少量 TikHub / Worker / Job 技术文案，本 Change 以现有后端 Contract 为边界完成最小差异同步。

# 目标

- 采集运行主表与正式 Figma 一致，仅保留 7 个产品列；关联批次、平台等详情继续通过任务辅助信息或详情 Drawer 获取。
- Data Import Campaign 仅在后端 `HistoricalCampaignResponse.can_start=true` 时渲染“开始导入”；取消、重试、查看内容继续使用当前服务端状态/资格判断。
- 页面与辅助补采可访问文案保持 Provider-neutral，不把 TikHub、Worker、Job 作为产品层文案。
- 保持现有 cursor 分页、北京时间过滤、Runtime Summary、Capability/Eligibility、条件轮询和后台任务语义不变。
- Figma 与代码采用同一真实 Contract，并保留自动化设计同步后的人工复核门禁。

# 范围与非目标

Included：`CollectionRuntimePage`、`CollectionRuntimeTable`、`DataImportDialog`、`TikHubSupplementDrawer` 的最小差异修正，相关前端 Unit/Browser Mock 回归，以及正式 Figma 状态/注释同步与一致性复核。

Excluded：后端 API/Contract/Schema/Migration、generated Client、数据库、Provider 执行逻辑、路由、依赖版本、部署拓扑、无关页面重构或内部文件无必要改名。

# 必须保持不变

- Pydantic → FastAPI → OpenAPI → Orval → `frontend/src/generated/api` 的 Contract 链不变，generated Client 不手工修改。
- `GET /api/v1/collection-runtime/runs` 的 cursor + limit 与 `next_cursor + has_more` 分页语义不变。
- `GET /api/v1/collection-runtime/summary` 的 KPI 及后端 `Asia/Shanghai` 自然日口径不变。
- 活跃任务仅在页面可见时约每 5 秒静默刷新；Data Import Dialog 使用同一约 5 秒前台轮询节奏，显式取消动作立即刷新一次状态，后台持久任务模型不变。
- Batch Supplement 平台资格继续以后端 Eligibility 为最终事实，不在前端写死平台资格。
- 不升级 Vue、Vite、Pinia、TypeScript、Vitest、Playwright 或任何依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 主表固定 7 列，不单独展示“关联对象” | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | satisfied | `CollectionRuntimeTable.vue` 固定 7 列；`collection-runtime-design.spec.ts` 直接断言 7 个表头且无“关联对象”；PR #304 CI #3687 与 main CI #3688 通过 |
| R2 | Campaign 只有 `can_start=true` 才渲染“开始导入” | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | satisfied | `DataImportDialog.vue` 以 `v-if="store.selectedHistoricalCampaign.can_start"` 控制动作；PR #304 Unit/Browser Mock 与 main fresh CI 通过 |
| R3 | 辅助补采产品/可访问文案保持 Provider-neutral | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | satisfied | Drawer aria-label 与创建成功提示已去除 TikHub/Worker/Job 产品文案；`collection-runtime-design.spec.ts` 与 `collection-runtime.spec.ts` 在 PR #304 / main fresh CI 通过 |
| R4 | cursor、北京时间 KPI、Capability/Eligibility 和约 5 秒条件轮询语义保持一致 | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | satisfied | 原 Store/API Owner 未修改；Data Import Dialog 使用 `campaignPollIntervalMs = 5_000`；取消状态覆盖 `cancelling → cancelled`；PR #304 CI #3687 与 main CI #3688 均通过 |
| R5 | 正式 Figma 与真实后端状态/动作一致且无已知几何重叠 | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | satisfied | Figma key state `3500:3648` 的最新 Design Context/1440×900 截图确认固定 7 列、running 仅“取消任务 + 关闭”、无“开始导入”，Footer 无已知重叠；自动化状态为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW` |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `collection-runtime-design.spec.ts` + 现有 Collection Runtime/Store Unit；PR #304 CI #3687：16 files / 71 tests passed；main CI #3688 success |
| 接口 / Contract | not_applicable | 本 Change 不修改后端 API、Schema、generated Client 或公共数据 Contract；Consumer 继续走现有 generated/API Owner |
| Backend/API/PostgreSQL | not_applicable | 不修改后端业务、事务、数据库或持久化；changed-scope 正确跳过 PostgreSQL Integration |
| Browser Mock Acceptance | required | 用户可见 7 列、Campaign 动作、Provider-neutral 文案、取消轮询；PR #304 CI #3687：43 passed，无 retry/flaky；main CI #3688 success |
| Real Full-stack Golden Path | not_applicable | 不改变前后端机器接口、路由、Persistence 或跨组件接线；changed-scope 正确跳过该层 |
| External Provider Probe | not_applicable | 不改变 TikHub/外部 Provider 请求、字段、分页或真实能力，不需要当前外部 Probe |
| Build / Runtime | required | npm locked install、lint、typecheck、Vite production build；PR #304 CI #3687 success；Runtime #808 success；main CI #3688 / Runtime #809 success |
| Docs / Governance / Figma | required | Requirement-Source #302 已解析；Figma `3500:3648` 最新 Design Context/截图完成一致性复核；Completion Audit、Standard Review、PR Completion #1541 与 main Completion #1542 均通过 |

# 实施步骤

- [x] 重新读取目标项目规则、当前实现、真实后端 Contract 与 Agent_Skills canonical Source Mode 规则。
- [x] 审查并修正 Figma 的 Provider-neutral 命名、Campaign 动作矩阵、KPI/轮询注释和几何重叠。
- [x] Red/Green：增加 7 列、Campaign Start 条件、Provider-neutral 文案和取消状态回归，并实施最小前端差异。
- [x] 将 Data Import Dialog 的周期轮询收敛为约 5 秒，同时让显式取消立即刷新一次，再由下一次周期轮询取得最终取消态。
- [x] 执行前端 lint、typecheck、Unit、production build、Browser Mock Acceptance 与 Runtime Acceptance；最终 PR fresh CI 无 flaky/retry。
- [x] 重新读取上游，完成 Completion Audit、Figma/实现一致性复核与两阶段 Standard Review。
- [x] 因宿主 Draft→Ready GraphQL 返回查询错误且重读后 #303 仍为 Draft，按零人工交付规则关闭 #303，以相同 head/base 创建普通 PR #304；#304 重新取得 fresh required checks 与 Review 后 guarded merge。
- [x] PR #304 使用 `expected_head_sha=3e0491eee986eda5e553536343eead61b1f1bf7b` guarded merge；真实 merge commit `4e8495fee68029ad9fd73dd1ae0751308398f9a7`。
- [x] merge 后 main fresh CI：CI #3688、Runtime #809、Change Completion #1542 全部 success。
- [x] Change 进入独立归档流程；Issue #302 Closure Audit 与任务分支清理在归档合并后执行。

# 当前新鲜证据

- Requirement Source：Issue #302 = resolved。
- 最终 Review snapshot：`reviewed_base_sha/current_base_sha = 8b785317c917d5cbca18ce6c3df418f4a0130f0e`，`reviewed_head_sha = 3e0491eee986eda5e553536343eead61b1f1bf7b`；merge 前 main 未漂移。
- PR #304 fresh checks：CI #3687（33629410683）success；Change Completion #1541（33629410460）success；Runtime Acceptance #808（33629410438）success。
- PR #304 CI #3687 实际执行：npm audit 0 vulnerabilities；lint/typecheck success；Vitest 16 files / 71 tests passed；Vite production build success；Playwright 43 passed，无 retry/flaky；CI Gate success。
- PR #304 Standard Review 锚定 `3e0491eee986eda5e553536343eead61b1f1bf7b`，最终无 BLOCKER/HIGH/重要 MEDIUM finding；review thread 为空。
- guarded merge 成功：PR #304 → main，merge commit `4e8495fee68029ad9fd73dd1ae0751308398f9a7`。
- main fresh：CI #3688（33629778404）success；Runtime Acceptance #809（33629778038）success；Change Completion #1542（33629777985）success；三条均为 `event=push` 且 `head_sha=4e8495fee68029ad9fd73dd1ae0751308398f9a7`。
- Figma `3500:3648` 最新 Design Context 与 1440×900 截图确认：运行记录表头固定 7 列；KPI 注释绑定 Runtime Summary / Asia/Shanghai；running/queued/uploading/cancelling 只提供“取消任务 + 关闭”，不显示“开始导入”；当前截图未发现 Footer 重叠或操作越界。
- Figma 自动化同步状态保持 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`；机器一致性复核完成，但不伪造 `HUMAN_VERIFIED`。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #302、merge 前当前 `main`、PR current head、正式 Figma 关键运行态及受影响实现，独立重建目标、非目标、成功标准与不变项。
- [x] change_coverage：Issue #302 的 7 列、`can_start` 动作、Provider-neutral、cursor/北京时间/Capability/Eligibility/5 秒轮询及 Figma 同步要求均已映射到 R1—R5 和对应实现/测试/Figma 证据，没有发现 requirement omission。
- [x] reverse_audit：从 7 列表格、导入 Campaign 按钮、取消状态、辅助补采文案反查现有 Store/generated Client/后端 Contract；未新增虚构 API、前端自造资格、假总页数、浏览器本地“今日”聚合或 Provider 专属产品语义。
- [x] unresolved_cleared：R1—R5 均为 `satisfied`；Backend/Persistence、Real Full-stack、External Provider 对本次纯前端/设计差异有事实依据为 `not_applicable`；Figma 人工最终视觉确认明确保留为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW` 状态，不被伪装成自动化完成项。

# 两阶段 Review

- Review A1（上游 → Change）：Issue #302 与正式 Figma/后端事实已逐项重建，未发现遗漏或范围静默扩大。
- Review A2（Change → 实现/测试/设计）：R1—R5 均有当前实现与匹配证据；用户可见行为由 Browser Mock 覆盖，Build/Runtime 有正式 CI；未用 Mock 冒充未运行的 Backend/PostgreSQL/Provider 边界。
- 代码质量 Review：已修复 Review 中发现的“取消”/“取消任务”设计文案差异和 5 秒轮询测试竞态；最终 reviewed head 未发现 BLOCKER/HIGH/重要 MEDIUM finding。

# Post-Merge Finalization

- implementation PR：#304，已 merge；原 Draft #303 因宿主 Ready mutation 能力缺陷关闭未合并，保留为历史证据。
- merge revision：`4e8495fee68029ad9fd73dd1ae0751308398f9a7`，已确认是 `main` 当前实现合入 revision。
- main fresh CI：CI #3688、Runtime #809、Change Completion #1542 均在该 revision 上 success。
- archive：本文件由独立 governance-only 归档分支移动至 `changes/archive/2026-09/` 并设置 `status: done`。
- Requirement Source：Issue #302 保持 open，待归档 PR 合入并取得其 main fresh 治理验证后执行 Closure Audit，再显式 close；没有使用 closing keyword 绕过 post-merge evidence。

# 文档影响

当前长期文档已经要求真实后端 Contract、cursor 分页、北京时间和 Provider-neutral 能力边界；本 Change 没有改变长期架构、API、Schema、部署、配置或用户操作流程定义，因此不机械改写 Blueprint/README。需求原因、实现取舍、验证与 Figma 同步状态由本 Change 和 Issue #302 承载。

# 兼容、部署与回滚

不改变公共 Contract、Schema、Migration、依赖、路由或部署拓扑，不需要数据迁移，也没有生产 Provider 写操作。回滚只需恢复本 Change 的前端模板/样式/测试；后端和历史数据不受影响。Figma 已按真实后端语义修正，若代码回滚则必须重新标记设计/代码差异，不能让两侧静默漂移。
