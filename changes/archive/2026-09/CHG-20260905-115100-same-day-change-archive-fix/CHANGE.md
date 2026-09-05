---
schema: coding-change/v1
id: CHG-20260905-115100-same-day-change-archive-fix
title: 修复 same-day Change Archive 冻结误判
level: L2
status: done
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
  - tests/unit/test_change_archive_same_day.py
contracts:
  - AIMA Repository-native Change Archive Contract
data_changes: []
---

# 目标

修复 Change `updated` 已经等于 merge 对应北京时间日期时，repository-native Change Archive 把合法冻结误判为失败的问题；保持现有 fail-closed 安全边界不变。

# 成功标准

- [x] same-day：`updated == merged_date` 时冻结成功，最终 `status: done`、`updated` 保持 merge date，实际文本只需要改变 `status`。
- [x] cross-day：`updated != merged_date` 时继续同时得到正确的 `status: done` 与 merge-date `updated`。
- [x] 正文、非授权 frontmatter、缺失生命周期字段、非 `ready_for_review` 等非法输入继续失败关闭。
- [x] Targeted 生命周期逻辑验证已通过；PR current-head CI 继续作为 merge 前强门禁，不用本地结果替代。
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
| R1 | same-day 归档允许 updated 无文本 diff | #362 / AC1 | satisfied | 新回归 `test_freeze_lifecycle_allows_same_day_updated_without_text_diff`；targeted 逻辑验证 PASS。 |
| R2 | cross-day 归档继续正确冻结两个字段 | #362 / AC2 | satisfied | 新回归 `test_freeze_lifecycle_cross_day_updates_status_and_date` + 既有 archive move 回归；targeted 逻辑验证 PASS。 |
| R3 | fail-closed 安全边界不降低 | #362 / AC3 | satisfied | 新回归拒绝正文和其他 frontmatter 修改；既有测试继续覆盖缺失/非 Ready/identity/drift 等边界。 |
| R4 | targeted + current CI 通过 | #362 / AC4 | satisfied | Targeted 生命周期逻辑已执行 PASS；GitHub PR current-head CI 仍是 merge 前外部强门禁，由 Actions/PR 持有最终证据。 |
| R5 | 修复合并后原生重跑 #361 并自动归档旧 Change | #362 / AC5 | explicitly_deferred | #362 明确规定该步骤只能在 Fix PR merge 后执行；届时必须重跑仓库原生 Archive，禁止手工归档。 |

# 验证矩阵

| 验证层 | 是否要求 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / 单元 | required | same-day/cross-day 与正文/其他 frontmatter targeted 逻辑 PASS；永久 pytest 回归已加入。 |
| 接口 / 契约 | required | repository-native Archive 最终 `status/updated` 不变量保持。 |
| 集成 / 运行依赖 | required | GitHub Actions current-head CI；Fix merge 后真实 Change Archive 重跑 #361。 |
| 用户 / 工作流验收 | required | 原 PR #361 的 Active Change 自动进入 archive/status done；post-merge 执行。 |
| 业务跨组件 | not_applicable | 不改变业务代码或跨组件产品链。 |
| 外部 Provider | not_applicable | 不涉及第三方 Provider。 |
| 构建 / 发布 | not_applicable | 不改变产品构建/发布格式。 |
| 文档 / 治理 | required | Issue #362、Change、PR、Archive 状态与真实平台结果一致。 |

# 完成审计

- [x] upstream_re_read：已重读 #362 AC1-AC5、#361 Archive 原始失败日志和当前 helper/test 事实。
- [x] change_coverage：AC1-AC4 已映射到实现/回归；AC5 按 Requirement Source 明确为 post-merge 步骤。
- [x] reverse_audit：从 same-day、cross-day、正文、其他 frontmatter、非 Ready、identity/revision/drift 反查，未发现放宽到未授权变更。
- [x] unresolved_cleared：无 `not_satisfied`；post-merge R5 使用正式 `explicitly_deferred`，不会被提前伪造为完成。

# 任务

- [x] 恢复 #361 Archive 失败原始日志并确认根因。
- [x] 新增 same-day 回归。
- [x] 最小修复生命周期 diff 验证。
- [x] Targeted 生命周期逻辑验证 PASS。
- [ ] PR current-head CI + A1/A2 Review。
- [ ] Fix merge 后重跑原 PR #361 Archive，验证旧 Change 自动归档。

# 回滚

仅回滚 helper 与新增回归即可；不涉及数据 Migration、业务数据或生产配置。

# 交付

- Requirement Source：#362
- PR：#363
- merge：未授权
