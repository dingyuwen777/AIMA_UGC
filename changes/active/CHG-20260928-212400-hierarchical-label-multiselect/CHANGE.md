---
schema: coding-change/v1
id: CHG-20260928-212400-hierarchical-label-multiselect
title: 统一工作台与声音广场的层级标签多选筛选
level: L2
status: in_progress
owner: codex
branch: feature/652-hierarchical-label-multiselect
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - frontend
  - content
  - workbench
affected_paths:
  - backend/src/aima_ugc/contracts/http.py
  - backend/src/aima_ugc/adapters/persistence/postgres/content_queries.py
  - contracts/openapi/openapi.json
  - frontend/src/generated/api/client.ts
  - frontend/src/features/voice-plaza/
  - frontend/src/features/workbench/
  - frontend/tests/
  - frontend/e2e/
  - tests/api/test_stage8d_contents.py
  - tests/integration/content/test_stage8d_voice_plaza_runtime.py
  - docs/product/02_当前产品能力与用户流程.md
contracts:
  - ContentFilterSnapshot primary_labels / secondary_labels
data_changes: []
---

# 变更摘要

统一工作台和声音广场的一级/二级标签筛选：两级均支持多选，二级候选只来自当前已选一级标签；父级取消后同步剔除失效二级标签。声音广场公共 Content Filter Contract 采用兼容式 plural 扩展，保留 legacy singular 输入。

# 背景、现状与问题

Requirement Source：Issue #652。工作台已有数组 Contract，但二级候选平铺全部 Taxonomy；声音广场仍使用单值标签筛选，工作台深链也只能携带单个标签。

# 目标、成功标准与非目标

目标与 AC1–AC11 以 #652 为唯一 Requirement Source。本 Change 不改 Taxonomy 内容、不新增 Migration、不升级依赖、不执行 Release/Deploy。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 两页一级/二级标签均支持多选 | #652 / AC1 | not_satisfied | 实现中 |
| R2 | 二级候选只来自已选一级且父级取消清理失效子项 | #652 / AC3 | not_satisfied | 实现中 |
| R3 | 同维度 OR、跨一级/二级维度 AND | #652 / AC6 | not_satisfied | 实现中 |
| R4 | List/Count/Analysis/Export 共享 plural Filter Snapshot | #652 / AC7 | not_satisfied | 实现中 |
| R5 | Projection/Fallback PostgreSQL 语义一致 | #652 / AC8 | not_satisfied | 实现中 |
| R6 | plural Contract + legacy singular 兼容 | #652 / AC9 | not_satisfied | 实现中 |
| R7 | Workbench → Voice Plaza 多标签深链与旧深链兼容 | #652 / AC10 | not_satisfied | 实现中 |
| R8 | 分层测试、生成与兼容门禁通过 | #652 / AC11 | not_satisfied | 实现中 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 |
| --- | --- | --- |
| Frontend Unit | required | Workbench / Voice Plaza 状态与组件 |
| Browser Mock | required | 两页真实多选、联动、深链 |
| API / Contract | required | repeated plural query + legacy singular |
| PostgreSQL Integration | required | projection/fallback、多值语义 |
| Generated Client | required | OpenAPI/Orval clean + compatibility |
| Build / Governance | required | lint/typecheck/build/Change/Review/CI |

# 风险、兼容性、迁移与回滚

公共 Contract 仅做 additive plural 扩展，并保留 legacy singular 输入归一化；无 Schema/Migration。回滚本 PR 即恢复旧 UI/筛选行为，不涉及数据恢复。

# 完成审计

- [ ] upstream_re_read：实现后重读 #652 与最终 diff。
- [ ] change_coverage：实现后逐项绑定 AC。
- [ ] reverse_audit：实现后从用户动作反查 List/Count/Analysis/Export/深链。
- [ ] unresolved_cleared：实现、Review、CI 后确认。

# 完成证据与状态

当前处于实现阶段，尚未进入 ready_for_review。
