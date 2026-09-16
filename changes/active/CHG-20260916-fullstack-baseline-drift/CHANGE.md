---
schema: coding-change/v1
id: CHG-20260916-fullstack-baseline-drift
title: 修复 release2 后 Full-stack 验收断言漂移
level: L2
status: ready_for_review
owner: dingyuwen777
branch: fix/512-fullstack-baseline-drift
created: 2026-09-16
updated: 2026-09-16
completion_gate: required
depends_on: []
affected_areas:
  - testing
  - ci
affected_paths:
  - frontend/e2e-fullstack/excel-import.spec.ts
  - frontend/e2e-fullstack/stage12-historical-analysis.spec.ts
  - frontend/e2e-fullstack/admin-product-capabilities.spec.ts
contracts: []
data_changes: []
---

# 背景与现状

release2 合并后，当前 `main` 的 Excel Browser Full-stack required gate 存在稳定断言漂移：Data Import 弹窗正式说明文案已更新，但两处 Full-stack 仍匹配旧文案；声音广场主列表已经按 Figma 两行摘要展示，系列/类别保留在车型单元格 `title` 与详情，但验收仍要求主列表正文直接出现“系列 · 类别”。

Requirement Source：GitHub Issue #512。

# 目标

只同步 Full-stack 验收断言到当前正式产品行为，使 required Full-stack suite 重新验证真实语义；不修改任何生产代码、API、Schema、数据或业务规则。

# 必须保持不变

- 不回退 release2 当前 Data Import 文案；
- 不改变声音广场 Figma 两行摘要设计；
- 车型系列/类别仍必须从正式 API 创建、筛选器使用，并在主列表 `vehicle-cell` 的技术完整信息中可验证；
- 不跳过、删除或弱化 Full-stack 用例，只修正过期观察点。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 本地 Excel Full-stack 使用 release2 当前说明文案 | #512 / AC1 | satisfied | `excel-import.spec.ts` 改为当前正式文案，仍通过真实浏览器/API/Worker/PostgreSQL 链 |
| R2 | Stage12 历史补空 Full-stack 使用 release2 当前说明文案 | #512 / AC2 | satisfied | `stage12-historical-analysis.spec.ts` 只替换过期文案断言 |
| R3 | 声音广场验证系列/类别未丢失但不要求正文直接展示 | #512 / AC3 | satisfied | `admin-product-capabilities.spec.ts` 改为断言 `.vehicle-cell` `title` 包含 `全栈系列 · 电动两轮车` |
| R4 | required Full-stack suite 恢复绿色且生产代码零改动 | #512 / AC4 | not_satisfied | 待 PR current-head Full-stack 与 CI Gate 新鲜证据 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Behavior / Unit | not_applicable | 不改变生产行为，只修正现有 Full-stack 验收观察点 |
| Contract | not_applicable | 不改 HTTP/OpenAPI/generated client |
| Integration / Persistence | not_applicable | 不改后端/Persistence；本修复由真实 Full-stack 直接验证 |
| User / Workflow Acceptance | required | 当前 14 条 Excel Browser Full-stack suite |
| Real Cross-component Golden Path | required | `Excel Browser Full-stack` 必须全绿 |
| Build / Runtime | required | 前端类型/build 与 PR current-head CI |
| Docs / Governance | required | Issue #512、Change、PR 追溯；不改产品文档，因为产品行为本身不变 |

# 已确认 Red 证据

- PR #511 run `35069843385`：PostgreSQL Integration 成功，但 Excel Browser Full-stack 4 个断言失败。
- 其中 3 个失败都匹配 release2 之前的旧 Data Import 文案；当前生产组件已明确使用新文案。
- 另 1 个失败要求声音广场主列表正文直接显示“全栈系列 · 电动两轮车”；当前 `VoicePlazaTable.vue` 明确按 Figma 两行摘要展示，并把系列/类别保留在 `.vehicle-cell` 的 `title` / 详情。
- 当前 `main` 已复现同一声音广场旧断言失败，因此不是 #511 引入。

# Completion Audit

- [x] upstream_re_read：已读取 Issue #512、当前 release2 `DataImportDialog.vue`、`VoicePlazaTable.vue` 与三个失败 spec。
- [x] change_coverage：AC1–AC3 已映射到最小测试断言修正；AC4 等待 current-head CI。
- [x] reverse_audit：没有生产文件变更；每个新断言都验证当前生产组件真实可观察语义，而不是降低断言强度。
- [ ] unresolved_cleared：等待 Full-stack/CI Gate 全绿后清零 AC4。

# 兼容、部署与回滚

无生产代码、Contract、Schema、Migration、依赖、部署或数据变化。回滚只会恢复已经确认过期的测试断言，并重新导致 required Full-stack 基线失败。
