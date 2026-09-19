---
schema: coding-change/v1
id: CHG-20260919-114700-figma-code-final-sync
title: 四页 Figma 与前端交互最终同步
level: L2
status: in_progress
owner: dingyuwen777
branch: feature/figma-code-final-sync
created: 2026-09-19
updated: 2026-09-19
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - figma
  - testing
affected_paths:
  - frontend/src/features/voice-plaza/
  - frontend/src/features/admin-configuration/
  - frontend/tests/
  - frontend/e2e/
contracts:
  - Voice Plaza user-visible interaction
  - Administrator configuration user-visible interaction
data_changes: []
---

# 变更摘要

- **要解决的问题**：当前正式 Figma 已包含声音广场详情四段快捷导航和管理员未保存修改确认，但最新 `main` 尚未消费这两项交互，导致设计与实现再次漂移。
- **拟议修改**：保持 API、Schema、generated client、依赖和现有业务规则不变，只在真实页面/Feature Owner 内补导航与未保存草稿保护，并对四页 Prototype/Owner 链做最终机器审计。
- **预期结果**：Figma 在演示模式下可完成代表性交互，Vue 在真实页面具有同等用户语义；报告策略后端继续明确延期，不出现假任务或假飞书结果。

# 背景、现状与问题

Requirement Source 为 Issue #543。上一轮本地 `feature/figma-owner-code-sync` 停止于 ready_for_review 且未形成远程交付；当前远端仅保留 `main`。

## 已确认事实

1. Figma 声音广场 Detail Drawer `4627:8510` 已有“内容 / AI 信息 / 人工确认 / 评论”四个有效 `SCROLL_TO` Reaction。
2. Figma 管理员配置已有 `7907:14019` 未保存修改确认状态，标题为“放弃未保存的修改？”。
3. 当前 `ContentDetailDrawer.vue` 没有详情快捷导航。
4. 当前 `AdminConfigurationPage.vue` Tab 点击直接赋值，没有页面级 dirty guard。
5. Provider 与 Analysis Scheme 子 Owner 已有各自 `hasUnsavedChanges` 计算；应上送状态而不是复制业务校验。
6. 报告策略只有本地前端准备能力，正式后端 Job/API/飞书同步未接入，本次继续延期。

# 目标与非目标

## 目标

- 声音广场详情按正式 Figma 提供四段快捷导航。
- 管理员配置五个可编辑 Tab 的未保存输入在离开前得到统一确认。
- 保持操作记录只读。
- 完成四页 Prototype 与代码一致性复核，并端到端交付到 `main`。

## 非目标

- 不实现报告策略后端。
- 不改变 HTTP Contract、数据库 Schema/Migration、generated client。
- 不升级依赖/Runtime，不重构无关页面。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 当前证据 |
| --- | --- | --- | --- | --- |
| R1 | 详情四段导航与 Figma Prototype 一致 | #543 AC1 | not_satisfied | Figma 有四个 SCROLL_TO；main 缺实现 |
| R2 | 五个可编辑管理员 Tab 离开 dirty 草稿前确认 | #543 AC2 | not_satisfied | Figma 有代表性确认态；main 直接切换 |
| R3 | 操作记录只读且不制造 dirty | #543 AC3 | not_satisfied | 待实现后 Browser 验收 |
| R4 | 报告策略后端继续延期且不伪造成功 | #543 AC4 | satisfied | ReportStrategyPanel 当前明确 backend-unavailable |
| R5 | 四页 Prototype 无失效目标/重复触发并保持 Owner 链 | #543 AC5 | not_satisfied | 待本轮最终机器审计 |
| R6 | 不改变 Contract/Schema/dependency/runtime | #543 AC6 | satisfied | 计划仅前端交互与测试 |
| R7 | 当前 PR head 新鲜 Unit/Browser/lint/typecheck/build/CI | #543 AC7 | not_satisfied | 待执行 |
| R8 | Review→merge→main-fresh→archive→closure→cleanup | #543 AC8 | not_satisfied | 待交付 |

# 最小实施计划

1. 建立 Red：固定详情导航和管理员 dirty Tab 行为。
2. Figma Owner/Prototype 审计；只修真实设计缺口。
3. 代码最小实现：Voice Page-private 导航；Admin Page Owner dirty guard；子 Feature 只上送已存在的 dirty 事实。
4. 目标 Green → 前端相关回归 → Browser/Playwright → lint/typecheck/build。
5. Completion Audit、独立 Review、Implementation ↔ Figma 六域复核。
6. current-head CI → guarded merge → main-fresh → repository-native archive → Issue/PR/branch 清理。

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Behavior / Component | required | 新增两项回归；各子 Panel dirty 投影 |
| Contract / Consumer | not_applicable | 公共 HTTP/generated Contract 不变 |
| Integration / Persistence | not_applicable | 不改后端/数据库/持久化 |
| User / Workflow Acceptance | required | 管理员继续编辑/放弃切换；详情四段导航 |
| Real Cross-component Golden Path | not_applicable | 本次仅客户端局部交互，无新的服务器接线 |
| External Provider Probe | not_applicable | 不涉及 Provider 协议事实 |
| Build / Runtime | required | lint、typecheck、production build |
| Figma | required | Prototype destination/duplicate reaction/Owner/Canvas/Fresh Screenshot/Design Context targeted review |
| Governance / CI | required | Change completion、Review、PR current-head、main-fresh |

# 风险、兼容与回滚

- **主要风险**：dirty 状态上送遗漏某个可编辑 Tab，或确认后旧草稿状态残留；通过 Component + Browser Journey 覆盖。
- **兼容性**：不改变 API、数据库和持久数据；只是阻止意外丢弃未保存的客户端输入。
- **依赖 / Runtime**：无变化。
- **Migration**：不适用。
- **部署 / Release**：本次不部署、不发布。
- **回滚**：revert Implementation PR 即可，无数据恢复动作。

# 完成审计

- [ ] upstream_re_read：Ready 前重新读取 #543、正式 Figma 与当前实现。
- [ ] change_coverage：R1—R8 无 `not_satisfied`。
- [ ] reverse_audit：Figma → Vue 与 Vue → Figma 六域双向复核完成。
- [ ] review：无 BLOCKER/HIGH/重要 MEDIUM。
- [ ] current_head_ci：最终 PR head required CI 新鲜通过。
- [ ] post_merge：main-fresh、archive/closure/cleanup 完成。
