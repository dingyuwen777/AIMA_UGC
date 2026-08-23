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

# Validation Matrix

按当前任务真实边界选择验证层。每层只使用 `required` 或 `not_applicable`：`required` 写明本次要证明的 Scope，并在完成前补当前 Evidence；`not_applicable` 必须说明为什么该层没有独立证明价值。不要机械要求所有任务执行全部层，也不要用 Browser Mock 冒充 Real Full-stack。

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 无用户界面时说明依据；有用户可见行为时通常用于广覆盖状态、请求和错误表达 |
| Backend/API/PostgreSQL Integration | not_applicable | 无服务器/数据库行为变化时说明依据；否则验证业务规则、事务、持久化、Job/Worker |
| Contract / Generated Client | not_applicable | 无公共 Contract/生成客户端影响时说明依据；否则验证 Pydantic/OpenAPI/generated client 一致性 |
| Real Full-stack Golden Path | not_applicable | 无跨组件关键链时说明依据；否则用少量 Golden Path 证明真实组件接通 |
| Real Provider Probe | not_applicable | 无外部 Provider 当前事实变化时说明依据；需要时必须有界、可审计、默认不进普通 CI |
| Docs / Governance / Other | not_applicable | 纯文档、配置、生成物或其他专项验证在这里记录替代证据 |

详细分层规则见 `.agents/skills/reliable-vibe-coding/references/testing-strategy.md`。

# Completion Audit

进入 `ready_for_review` 前必须**重新读取上游事实源**，不要从当前 Change 的 checklist 反推需求。按当前任务实际边界执行正向和反向审计；例如前后端任务应检查“后端能力 → 前端入口”和“前端动作 → 后端能力”，异步任务应检查状态、错误和结果闭环，同时复核 Validation Matrix：每个 `required` 层都有足够的新鲜证据，每个 `not_applicable` 都有真实依据。

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计，并复核 Validation Matrix；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [ ] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [ ] 建立并维护 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- Validation Matrix：按 `.agents/skills/reliable-vibe-coding/references/testing-strategy.md` 选择适用层
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