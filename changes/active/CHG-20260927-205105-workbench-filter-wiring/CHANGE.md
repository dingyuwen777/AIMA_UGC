---
schema: coding-change/v1
id: CHG-20260927-205105-workbench-filter-wiring
title: 修复工作台筛选交互与三模块查询联动
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/634-workbench-filters
created: 2026-09-27
updated: 2026-09-27
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - workbench
  - shared-ui
affected_paths:
  - frontend/src/features/workbench/
  - frontend/src/shared/ui/AimaDateRange.vue
  - frontend/e2e/workbench.spec.ts
contracts: []
data_changes: []
---

# 目标与现状

Issue #634：工作台三个模块已有真实后端接口及 PostgreSQL 筛选查询，但声音流内的多选面板位于横向滚动容器内，可能被裁切；日期范围分两次写入父级筛选快照，可能丢失首次写入。修复用户可操作性与日期查询联动。

# 范围与不变项

- 修复声音流的多选弹层显示和键盘/关闭行为，并保留横向滚动的窄卡片布局。
- 日期确认时一次性写入起止日期，三个工作台模块收到同一筛选快照；筛选和重置均触发真实接口刷新。
- 保持 active Taxonomy、品牌车型目录、布局编辑、声音广场深链及现有生成 Client/后端 Contract 不变。
- 不变更 Schema、Migration、依赖、部署或生产数据。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 声音流筛选项可点击并能看到可选项 | https://github.com/dingyuwen777/AIMA_UGC/issues/634 | not_satisfied | 待浏览器回归与修复。 |
| R2 | 日期确认后起止日期完整进入声音流、心智和趋势请求 | https://github.com/dingyuwen777/AIMA_UGC/issues/634 | not_satisfied | 待浏览器请求断言与修复。 |
| R3 | 多选、重置和三模块呈现与当前后端数据口径保持一致 | docs/product/02_当前产品能力与用户流程.md | not_satisfied | 待前端回归与后端现有测试复核。 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 工作台 Store 与共享日期组件既有回归及新增日期快照行为。 |
| 接口 / Contract | required | 核对生成参数与现有 WorkbenchQuery，不修改公共 Contract。 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 后端 SQL/Schema 未修改；用已有后端集成覆盖筛选口径核查。 |
| 用户 / Workflow Acceptance | required | Browser Mock 从点击、选择、确认到三个 HTTP 请求参数与显示状态。 |
| 跨组件 Golden Path | required | 验证工作台三个 generated-client 请求共用同一筛选参数；如可运行，执行现有 fullstack 关键链。 |
| External Dependency / Provider Probe | not_applicable | 不改 TikHub/LLM 外部调用。 |
| Build / Package / Runtime | required | 前端 lint、typecheck、build。 |
| Docs / Governance | required | 产品文档现有口径核对，Change Completion 检查。 |

# 实施步骤

1. 在现有 Browser 测试复现弹层裁切和日期丢失，核对三个模块请求。
2. 修复筛选弹层承载和日期原子提交；保持其他页面日期组件兼容。
3. 运行前端目标测试、受影响质量检查和后端筛选回归，核对文档事实。

# Completion Audit

- [ ] upstream_re_read：交付前重读 Issue #634 与产品工作台能力。
- [ ] change_coverage：逐条检查 R1-R3 无遗漏。
- [ ] reverse_audit：前端动作到真实 API、后端筛选到前端入口双向核对。
- [ ] unresolved_cleared：全部需求满足且 required 验证有新鲜证据。

# 交付状态

当前为早期施工记录；实现、Review、CI、PR Ready 均待完成。
