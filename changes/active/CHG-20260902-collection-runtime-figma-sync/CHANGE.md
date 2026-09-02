---
schema: coding-change/v1
id: CHG-20260902-collection-runtime-figma-sync
title: 同步采集运行中心 Figma 与真实后端契约
level: L2
status: in_progress
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
  - changes/active/CHG-20260902-collection-runtime-figma-sync/CHANGE.md
contracts: []
data_changes: []
---

# 背景与现状

正式 Figma `release / 采集运行中心`（node `3500:2023`）已经以当前后端 Contract 为事实源收敛：采集运行主表固定 7 列，“关联对象”不单独占列；Data Import Campaign 只在后端 `can_start=true` 时提供“开始导入”；辅助补采产品文案保持 Provider-neutral。当前 Vue 页面仍存在 8 列表格、非 Ready Campaign 的禁用“开始导入”占位动作，以及少量 TikHub / Worker / Job 技术文案，因此需要做现有实现的最小差异同步。

# 目标

- 采集运行主表与正式 Figma 一致，仅保留 7 个产品列；关联批次、平台等详情继续通过任务辅助信息或详情 Drawer 获取。
- Data Import Campaign 仅在后端 `HistoricalCampaignResponse.can_start=true` 时渲染“开始导入”；取消、重试、查看内容继续使用当前服务端状态/资格判断。
- 页面与辅助补采可访问文案保持 Provider-neutral，不把 TikHub、Worker、Job 作为产品层文案。
- 保持现有 cursor 分页、北京时间过滤、Runtime Summary、Capability/Eligibility、条件轮询和后台任务语义不变。
- Figma 与代码采用同一真实 Contract，并保留自动化设计同步后的人工复核门禁。

# 范围与非目标

Included：`CollectionRuntimePage`、`CollectionRuntimeTable`、`DataImportDialog`、`TikHubSupplementDrawer` 的最小差异修正，相关前端回归测试，以及已完成的正式 Figma 状态/注释同步。

Excluded：后端 API/Contract/Schema/Migration、generated Client、数据库、Provider 执行逻辑、路由、依赖版本、部署拓扑、无关页面重构或内部文件无必要改名。

# 必须保持不变

- Pydantic → FastAPI → OpenAPI → Orval → `frontend/src/generated/api` 的 Contract 链不变，generated Client 不手工修改。
- `GET /api/v1/collection-runtime/runs` 的 cursor + limit 与 `next_cursor + has_more` 分页语义不变。
- `GET /api/v1/collection-runtime/summary` 的 KPI 及后端 `Asia/Shanghai` 自然日口径不变。
- 活跃任务仅在页面可见时约每 5 秒静默刷新，不改轮询频率或后台执行模型。
- Batch Supplement 平台资格继续以后端 Eligibility 为最终事实，不在前端写死平台资格。
- 不升级 Vue、Vite、Pinia、TypeScript、Vitest、Playwright 或任何依赖。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 主表固定 7 列，不单独展示“关联对象” | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | not_satisfied | Red/Green 回归直接渲染表头并检查正式 7 列 |
| R2 | Campaign 只有 `can_start=true` 才渲染“开始导入” | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | not_satisfied | 回归检查 DataImportDialog 模板条件与禁用占位逻辑 |
| R3 | 辅助补采产品/可访问文案保持 Provider-neutral | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | not_satisfied | 回归检查 Drawer aria-label 与页面创建成功提示 |
| R4 | cursor、北京时间 KPI、Capability/Eligibility 和条件轮询语义保持不变 | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | not_satisfied | 既有 Store/API/设计基线回归及完整前端验证 |
| R5 | 正式 Figma 与真实后端状态/动作一致且无已知几何重叠 | https://github.com/dingyuwen777/AIMA_UGC/issues/302 | not_satisfied | Figma 结构、几何、状态与 Design Context 复核 |

# Validation Matrix

| 验证层 | 要求 | 计划证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | `collection-runtime-design.spec.ts` Red/Green 与现有 Collection Runtime Unit |
| Contract / Generated | regression | 不修改 Contract/generated；现有 generated-client delegation 回归 |
| Backend/API/PostgreSQL | not_applicable | 不修改后端业务或持久化，真实后端仅作为事实源读取 |
| Browser Mock Acceptance | targeted | 现有页面行为若永久 CI 覆盖则作为回归证据；本 Change 不扩展业务路径 |
| Real Full-stack Golden Path | regression | 不新增全栈能力；永久 CI 现有 Golden Path 不得回归 |
| External Provider Probe | not_applicable | 不改变 TikHub/外部 Provider 请求与数据结构 |
| Build / Runtime | required | Frontend lint、typecheck、unit、build 与永久 CI |
| Docs / Governance / Figma | required | Change Completion、独立 Review、Figma 结构/几何/状态复核 |

# 实施步骤

- [x] 重新读取目标项目规则、当前实现、真实后端 Contract 与 Agent_Skills canonical Source Mode 规则。
- [x] 审查并修正 Figma 的 Provider-neutral 命名、Campaign 动作矩阵、KPI/轮询注释和几何重叠。
- [x] Red：增加 7 列、Campaign Start 条件和 Provider-neutral 文案回归；首轮 CI 新增 7 列测试按预期暴露断言脆弱性，其他新增断言通过。
- [x] Green：最小修改现有 Vue 页面/组件，不重写 Store/API，不升级依赖。
- [ ] 执行前端目标测试、lint、typecheck、build 与永久 CI。
- [ ] 重新读取上游，完成 Completion Audit 与两阶段独立 Review。
- [ ] Ready 后受保护合并，执行 main fresh 验证并独立归档本 Change。

# 当前新鲜证据

- 后端 Runtime Summary 已确认按 `Asia/Shanghai` 自然日返回 `processing_count / completed_today_count / contents_ingested_today / as_of`。
- 当前 Store 已确认使用 `limit=20` cursor 分页，并仅在存在活跃任务且文档可见时按 5000ms 静默刷新。
- Batch Supplement 已确认先筛选成功且有入库数据的批次，再以后端 eligibility 返回的平台作为最终资格。
- Figma 已移除 discovering/running/partial_failed/succeeded 状态中的“开始导入”占位；修复 partial_failed/succeeded Footer 重叠与双操作行越界；关键帧重新取得 Design Context/1440×900 截图证据。
- Figma 自动化同步当前状态为 `SYNCHRONIZED_PENDING_HUMAN_REVIEW`，不替代最终人工视觉确认。
- PR #303 首轮 CI 的 Frontend step 已完成 lint/typecheck 并运行 70 条 Unit；仅新增 7 列 SSR 断言因 Vue scoped attribute 导致定位过严而失败，69 条通过；断言已改为 scope-attribute tolerant 匹配，等待新一轮 CI。
- PR #303 首轮 Runtime Acceptance 已成功；Change Completion Gate 首轮失败原因是 PR body 缺少机器要求的 `Requirement-Source`，待 PR metadata 修正。

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #302、最新 main、正式 Figma 与受影响实现。
- [ ] change_coverage：R1—R5 均映射到实现、测试或 Figma/CI 证据。
- [ ] reverse_audit：从用户可见表格、Campaign 动作、辅助补采文案反查真实 Contract/Store，确认无 Future/虚构能力进入生产。
- [ ] unresolved_cleared：无 `not_satisfied` Required 项，未验证边界和剩余风险已显式记录。

# 文档影响

当前长期文档已要求真实后端 Contract、cursor 分页、北京时间和 Provider-neutral 能力边界；本 Change 暂未发现需要改写长期 Blueprint/README 的语义。若实现调查发现长期文档与代码事实冲突，再在同一 Change 内定向同步，禁止机械扫描或无关重写。

# 兼容、部署与回滚

不改变公共 Contract、Schema、Migration、依赖或部署拓扑，不需要数据迁移。回滚只需恢复本 Change 的前端模板/样式与测试；后端和历史数据不受影响。Figma 已按真实后端语义修正，若代码回滚则必须重新标记设计/代码差异，不能让两侧静默漂移。
