---
schema: rvc-change/v1
id: $change_id
title: $title
level: $level
status: proposed
owner: $owner
branch: $branch
created: $created
updated: $updated
completion_gate: required
$depends_on
$affected_areas
$affected_paths
$contracts
$data_changes
---

# 目标

描述用户或系统最终获得的结果。

# 成功标准

- [ ] 使用可观察行为描述验收结果。

# 范围

- 列出本次允许修改的内容。

# 非目标

- 列出本次明确不做的内容。

# 必须保持不变

- 列出需要兼容的接口、数据、配置和既有合法行为。

# 关键决策

记录已经确认的取舍、依据和影响；L3 变更还应覆盖迁移、部署与回滚。

# Requirement Traceability

从用户已确认决定、正式 Roadmap/Spec/Stage 完成定义或其他上游事实源独立提取要求。**当前 Change 不能把自身作为 Requirement Source，也不能把本表当作上游需求全集。**

状态只允许：

- `satisfied`：已有实现/验证证据；
- `explicitly_deferred`：已有正式批准的延期依据；
- `not_applicable`：有明确事实证明不适用；
- `not_satisfied`：尚未满足，进入 `ready_for_review` 前必须清零。

`Source` 优先写仓库相对事实源路径；本轮用户明确决定可写 `user:<简短标识>`。`Evidence` 必须写实际实现、测试、运行或正式延期/不适用依据，Ready 时不得保留占位内容。

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 写明第一条上游要求 | user:current-request | not_satisfied | 尚未验证 |

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。按当前任务实际边界执行正向和反向审计；例如前后端任务应检查“后端能力 → 前端入口”和“前端动作 → 后端能力”，异步任务应检查状态、错误和结果闭环。

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [ ] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 目标测试：
- 相关测试：
- 静态检查/构建：
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 尚未执行。

# 文档影响

- 待确认。

# 交付

- Commit：
- PR：
- 发布：
