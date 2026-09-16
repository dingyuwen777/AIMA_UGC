---
schema: coding-change/v1
id: CHG-20260916-174631-voice-plaza-compact-overflow
title: 修复声音广场紧凑桌面溢出
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/voice-plaza-compact-overflow-515
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - voice-plaza
affected_paths:
  - frontend/src/app/layouts/AppShell.vue
  - frontend/src/features/voice-plaza/pages/VoicePlazaPage/components/VoicePlazaTable.vue
  - frontend/src/shared/styles/responsive.css
  - frontend/e2e/voice-plaza-design.spec.ts
  - frontend/e2e/responsive-layout.spec.ts
contracts: []
data_changes: []
---

# 背景与目标

Requirement Source 为 GitHub Issue #515 / AC1–AC4；旧 #501 验收的 1212px 局部横滚是历史基线，不是本轮目标。当前 AppShell 导航项固定宽度略大于侧栏内宽；声音广场表格在 1180/1280 仍强制 1212px，末列详情需横向滚动。本轮只调整紧凑桌面布局，保留宽屏与真实业务流程。

# 范围与不变项

- AppShell 导航填满而不撑出侧栏，仍可纵向滚动。
- 声音广场 1180–1439 使用表头/行一致的 952px 最小宽度；1440 及以上保留 1212px 基线；极窄窗口保留表格局部横滚。
- 保留七列、字号、筛选/排序/Cursor/详情/AI/导出、现有 Vue/Pinia/生成 Client；不改后端 Contract、Schema、依赖或 Figma 文件。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 1180/1280 七列和详情无需横滚，极窄窗口局部滚动兜底 | #515 / AC1 | not_satisfied | 待实施并运行浏览器几何/交互回归 |
| R2 | 公共侧栏导航不横向溢出且交互保持 | #515 / AC2 | not_satisfied | 待实施并运行跨窗口回归 |
| R3 | 1440/1920 列宽基线、表头/行对齐和业务行为保持 | #515 / AC3 | not_satisfied | 待运行现有及新增回归 |
| R4 | 前端检查、PR CI、合并后 main CI 和设计一致性 | #515 / AC4 | not_satisfied | 待逐项取得新鲜证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 既有前端单元回归，确保交互行为不变 |
| 接口 / Contract | not_applicable | 本次只改 CSS 和浏览器断言，不改 API/生成 Client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不改后端、持久化或外部运行依赖 |
| 用户 / Workflow Acceptance | required | Playwright 覆盖 1180/1280/1440/1920 与窄窗口侧栏、详情可达性 |
| 跨组件 Golden Path | not_applicable | 不改前后端接线；现有浏览器层直接验证此处可观察布局和点击 |
| 外部依赖 Probe | not_applicable | 不改 Provider 或付费服务边界 |
| Build / Package / Runtime | required | 前端 lint/typecheck/unit/build 和项目 required CI |
| Docs / Governance / Other | required | 同步响应式说明、检查文档事实、Change/PR/Review/主分支证据 |

# 实施计划

- [ ] 补浏览器几何与详情可达性断言，确认旧实现因目标行为失败。
- [ ] 最小修改 AppShell 与声音广场表格 CSS；同步受影响的响应式说明。
- [ ] 目标及前端回归通过，完成设计一致性核对。
- [ ] 重新读取 #515 做完成审计、独立复核，取得 current-head CI 后按规则合并。

# Completion Audit

- [ ] upstream_re_read：合并前重读 #515、正式 Figma Compact 节点和当前项目事实。
- [ ] change_coverage：AC1–AC4 与实现、测试、文档逐项对应。
- [ ] reverse_audit：侧栏公共消费者、声音广场表头/行/详情和真实业务链无回归；验证层级适当。
- [ ] unresolved_cleared：Ready 前所有 R 行有直接证据或正式处置。

# 兼容与回滚

纯前端布局变更，无依赖、配置、Contract、Schema/Migration 或生产部署变化。若验证发现回归，可回滚本次前端提交，不需数据操作。
