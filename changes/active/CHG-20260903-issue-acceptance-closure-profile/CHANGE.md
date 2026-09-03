---
schema: coding-change/v1
id: CHG-20260903-issue-acceptance-closure-profile
title: 统一 AIMA Issue 标题、验收与关闭 Profile
level: L2
status: in_progress
owner: dingyuwen777
branch: chore/issue-acceptance-closure-profile
created: 2026-09-03
updated: 2026-09-03
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - github-collaboration
  - issue-profile
  - requirement-traceability
  - tests
affected_paths:
  - .github/ISSUE_TEMPLATE/01-requirement.yml
  - .github/ISSUE_TEMPLATE/02-bug.yml
  - .github/ISSUE_TEMPLATE/03-technical-change.yml
  - .github/PULL_REQUEST_TEMPLATE.md
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_agent_governance.py
  - tests/unit/test_issue_acceptance_profile.py
  - changes/active/CHG-20260903-issue-acceptance-closure-profile/CHANGE.md
contracts:
  - AIMA GitHub Issue Profile
  - AIMA Requirement Closure Profile
data_changes: []
---

# 目标

让 AIMA_UGC 的 GitHub 项目 Profile 与当前 Agent_Skills canonical Issue Acceptance / Closure Contract 达到同样效果：三类 Issue 使用统一 chooser/title 语义、稳定 `AC1/AC2/...` 验收项和公共 `validation_requirements`；PR 在需要 post-merge evidence 时不提前 auto-close Requirement Source；AIMA 自有 governance checker/test 永久保护项目 Profile 的结构。通用 Evidence Sufficiency、逐项 `[ ] → [x]`、写后重读、close 后再次确认仍由 Agent_Skills canonical Owner 承担，不在 AIMA 复制第二套通用规则正文。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/319

关联 canonical Requirement：https://github.com/dingyuwen777/Agent_Skills/issues/184

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三类 chooser/title 使用统一项目 Profile | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC1 | not_satisfied | Red/Green Profile regression |
| R2 | 三类 acceptance_criteria 统一 label、AC1 checklist 与 required | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC2 | not_satisfied | Issue Form regression + checker |
| R3 | 三类统一 validation_requirements / 验证要求 / required | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC3 | not_satisfied | Issue Form regression + checker |
| R4 | 公共结构与 Agent_Skills 当前 Profile 对齐，同时保留 AIMA 专项字段与项目 Owner | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC4 | not_satisfied | Diff reverse audit |
| R5 | PR post-merge evidence 场景禁止 closing keyword 抢先关闭 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC5 | not_satisfied | PR Template regression |
| R6 | governance checker/unit 永久保护标题、AC、validation、post-merge closure 结构 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC6 | not_satisfied | targeted + full CI |
| R7 | 产品业务/Contract/Schema/Runtime/Full-stack/Release 行为不变 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC7 | not_satisfied | changed-files + existing CI |
| R8 | PR/CI/Review/guarded merge/main-fresh/Change archive 闭环 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC8 | not_satisfied | lifecycle evidence |
| R9 | Issue #319 关闭前逐项充分 Evidence、实际 `[x]` 回写、重读、close、再读 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC9 | not_satisfied | final Closure Audit |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| Red | pending | 新 Profile regression 在旧模板/checker 上应失败 |
| 行为 / Unit / Component | required | governance checker + unit/profile regressions |
| 接口 / Contract | not_applicable | 不修改产品 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改产品 Runtime/Persistence |
| 用户 / Workflow Acceptance | required | GitHub Issue chooser/Form + PR Template 项目 Profile |
| 跨组件 Golden Path | not_applicable | 不修改产品调用链 |
| 外部依赖 Probe | not_applicable | 不涉及外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建/Runtime |
| Docs / Governance / Other | required | Change Completion Gate + AIMA permanent CI + Agent_Skills Review |

# Completion Audit

- [ ] upstream_re_read：重新读取 Issue #319、Agent_Skills #184、AIMA `AGENTS.md`、现有 Issue Forms/PR Template/checker 与最终 diff。
- [ ] change_coverage：AC1–AC9 均有直接实现或生命周期 Evidence。
- [ ] reverse_audit：从最终 diff 反查没有复制通用 canonical 正文、没有删除 AIMA 类型专项字段、没有修改产品行为。
- [ ] unresolved_cleared：无 blocker、CI failure、未验证适用 AC 或未同步 Requirement Source 状态。
