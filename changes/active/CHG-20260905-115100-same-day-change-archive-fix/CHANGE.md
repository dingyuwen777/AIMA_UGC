---
schema: coding-change/v1
id: CHG-20260905-115100-same-day-change-archive-fix
title: 修复 same-day Change Archive 冻结误判
level: L2
status: in_progress
owner: dingyuwen777
branch: fix/362-same-day-change-archive
created: 2026-09-05
updated: 2026-09-05
completion_gate: required
depends_on:
  - CHG-20260905-110300-actions-runner-optimization
affected_areas:
  - change-lifecycle
  - github-actions
  - ci-governance
affected_paths:
  - scripts/quality/archive_change_after_merge.py
  - tests/unit/test_change_archive_automation.py
contracts:
  - AIMA Repository-native Change Archive Contract
data_changes: []
---

# 目标

修复 Change `updated` 已经等于 merge 对应北京时间日期时，repository-native Change Archive 把合法冻结误判为失败的问题；保持现有 fail-closed 安全边界不变。

# 成功标准

- [ ] same-day：`updated == merged_date` 时冻结成功，最终 `status: done`、`updated` 保持 merge date，实际文本只需要改变 `status`。
- [ ] cross-day：`updated != merged_date` 时继续同时得到正确的 `status: done` 与 merge-date `updated`。
- [ ] 正文、非授权 frontmatter、缺失生命周期字段、非 `ready_for_review` 等非法输入继续失败关闭。
- [ ] 修复通过 targeted archive regression 与当前 CI。
- [ ] Fix 合并后通过 repository-native Archive 重跑 PR #361，旧 Change 自动归档；不手工移动旧 Change。

# 范围

- 修正 `archive_change_after_merge.py` 对“允许修改字段”与“必须实际产生 diff 的字段”的判断。
- 增加 same-day 永久回归，并保留 cross-day 与非法修改回归。

# 非目标

- 不修改 Change Archive GitHub App、Environment、Ruleset 或 Workflow 权限。
- 不修改业务 API、Schema、Migration 或产品功能。
- 不改写 PR #361 / merge 历史。
- 不手工归档 `CHG-20260905-110300-actions-runner-optimization`。

# 必须保持不变

- 归档最终状态只能是 `status: done`。
- 归档最终 `updated` 必须等于 merge 对应北京时间日期。
- 归档不得改变正文、行数或任何非 `status/updated` frontmatter 字段。
- merged revision、Change identity、active/archive 唯一性、main ancestry/drift 校验保持不变。

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | same-day 归档允许 updated 无文本 diff | #362 / AC1 | not_satisfied | 待新增回归与实现。 |
| R2 | cross-day 归档继续正确冻结两个字段 | #362 / AC2 | not_satisfied | 现有回归存在，修复后重新验证。 |
| R3 | fail-closed 安全边界不降低 | #362 / AC3 | not_satisfied | 待反向回归。 |
| R4 | targeted + current CI 通过 | #362 / AC4 | not_satisfied | 待验证。 |
| R5 | 修复合并后原生重跑 #361 并自动归档旧 Change | #362 / AC5 | not_satisfied | 需 Fix merge 后执行。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 | required | `freeze_lifecycle` same-day/cross-day 与非法输入回归。 |
| 接口 / 契约 | required | repository-native Archive 生命周期字段不变量。 |
| 集成 / 运行依赖 | required | GitHub Actions current-head CI；Fix merge 后真实 Change Archive 重跑 #361。 |
| 用户 / 工作流验收 | required | 原 PR #361 的 Active Change 自动进入 archive/status done。 |
| 业务跨组件 | not_applicable | 不改变业务代码或跨组件产品链。 |
| 外部 Provider | not_applicable | 不涉及第三方 Provider。 |
| 构建 / 发布 | not_applicable | 不改变产品构建/发布格式。 |
| 文档 / 治理 | required | Issue/Change/Archive 状态与真实平台结果一致。 |

# 完成审计

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 任务

- [x] 恢复 #361 Archive 失败原始日志并确认根因。
- [ ] 新增 same-day Red 回归。
- [ ] 最小修复生命周期 diff 验证。
- [ ] targeted regression + CI。
- [ ] A1/A2 Review 并进入 ready_for_review。
- [ ] Fix merge 后重跑原 PR #361 Archive，验证旧 Change 自动归档。

# 回滚

仅回滚 helper 与新增回归即可；不涉及数据 Migration、业务数据或生产配置。

# 交付

- Requirement Source：#362
- PR：待创建
- merge：未授权
