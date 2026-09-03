---
schema: coding-change/v1
id: CHG-20260903-issue-acceptance-closure-profile
title: 统一 AIMA Issue 标题、验收与关闭 Profile
level: L2
status: ready_for_review
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

实现 PR：https://github.com/dingyuwen777/AIMA_UGC/pull/320

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 三类 chooser/title 使用统一项目 Profile | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC1 | satisfied | `test_current_issue_profiles_share_title_acceptance_and_validation_contract` + final diff：chooser `需求/缺陷/技术变更`、title prefix `[需求]/[缺陷]/[技术变更]` |
| R2 | 三类 acceptance_criteria 统一 label、AC1 checklist 与 required | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC2 | satisfied | 三类 Form diff + Profile regression；冻结 Red `9ebd0883...` 在 run `33727975944` 明确 EXPECTED_RED，Green targeted run `33727888585` 通过 |
| R3 | 三类统一 validation_requirements / 验证要求 / required | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC3 | satisfied | 三类 Form + `REQUIREMENT_FORM_FIELDS/BUG_FORM_FIELDS/TECHNICAL_CHANGE_FORM_FIELDS` 均使用 `validation_requirements`，Green targeted run `33727888585` 通过 |
| R4 | 公共结构与 Agent_Skills 当前 Profile 对齐，同时保留 AIMA 专项字段与项目 Owner | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC4 | satisfied | A1/A2 reverse audit：只统一 chooser/title/Acceptance/Validation/PR Closure，Requirement/Bug/Technical Change 专项字段继续保留，未复制 Agent_Skills canonical 正文 |
| R5 | PR post-merge evidence 场景禁止 closing keyword 抢先关闭 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC5 | satisfied | PR Template 新增 `需要 post-merge evidence` + `不得使用 Closes/Fixes/Resolves` + Closure Audit；冻结 Red/Green targeted 均覆盖 |
| R6 | governance checker/unit 永久保护标题、AC、validation、post-merge closure 结构 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC6 | explicitly_deferred | checker 与永久回归已实现且 targeted Green `33727888585` 通过；PR final-head 完整永久 CI/Completion Gate 由本 PR Ready 生命周期取得后再升级为 satisfied |
| R7 | 产品业务/Contract/Schema/Runtime/Full-stack/Release 行为不变 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC7 | satisfied | PR changed-files 仅 3 个 Issue Form、PR Template、governance checker、profile test、Change；当前 HEAD Runtime Acceptance #997 / run `33728051743` success |
| R8 | PR/CI/Review/guarded merge/main-fresh/Change archive 闭环 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC8 | explicitly_deferred | 独立 A1/A2 Review 当前 `NO_FINDINGS_WITHIN_SCOPE`；final-head CI、guarded merge、main-fresh、archive 只能在后续生命周期取得 |
| R9 | Issue #319 关闭前逐项充分 Evidence、实际 `[x]` 回写、重读、close、再读 | https://github.com/dingyuwen777/AIMA_UGC/issues/319#AC9 | explicitly_deferred | 必须在 implementation main-fresh 与 Change archive 完成后执行最终 Closure Audit，当前禁止提前勾选/关闭 |

# Red 与 Green 证据

冻结 Red revision：`9ebd0883d5efb5ba1a71bfbaa1de424f87330c63`。最早 CI #3859 在进入语义测试前被新增测试文件的 ruff format 门禁拦截，因此不把该失败冒充语义 Red。随后 Temporary Frozen Issue Profile Red Evidence run `33727975944` 明确 checkout 此 revision，并确认以下两项均输出 `EXPECTED_RED`：

- 旧三类 Issue Profile 不满足统一 chooser/title、AC1 与 validation contract；
- 旧 PR Template 不满足 post-merge evidence Closure 时序。

Green 实现后，Temporary Issue Profile Green V2 run `33727888585` 使用标准库直接运行四个项目 Profile/Checker 回归并执行 `check_agent_governance.py`，全部成功后才提交 checker/test 变更。临时迁移/Red workflows 均已从最终分支删除。

# 独立 Review

A1：从 Issue #319 AC1–AC9 反查当前实现，AC1–AC5、AC7 均有直接实现与 targeted Evidence；AC6 的永久 CI、AC8/AC9 的 merge 后生命周期保持显式 deferred，没有被 CI Green 或作者声明提前满足。

A2：从 PR #320 final implementation diff 反查，仅修改 GitHub Issue/PR Profile、静态 governance checker、永久 Profile regression 与 Change；checker 只验证结构，不尝试判断自然语言 AC 是否满足；未修改产品业务、Contract、Schema/Migration、数据库、Runtime、Figma、部署或 Release。

Review 结论：`NO_FINDINGS_WITHIN_SCOPE`。未发现 blocker/high/medium；未验证项仅为按生命周期尚未产生的 final-head/main/archive/Closure 证据。

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| Red | satisfied | frozen Red run `33727975944` 对旧 revision 两项核心 Contract 均得到 EXPECTED_RED |
| 行为 / Unit / Component | satisfied | targeted Green run `33727888585`：Profile + Checker 回归和真实 `check_agent_governance.py` 全部通过 |
| 接口 / Contract | not_applicable | 不修改产品 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改产品 Runtime/Persistence |
| 用户 / Workflow Acceptance | satisfied | 三类 GitHub Issue chooser/Form + PR Template 结构由真实文件和 checker 验证 |
| 跨组件 Golden Path | not_applicable | 不修改产品调用链 |
| 外部依赖 Probe | not_applicable | 不涉及外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建/Runtime；Runtime Acceptance #997 仍为 success，作为非回归旁证 |
| Docs / Governance / Other | explicitly_deferred | Ready HEAD 的永久 CI / Change Completion Gate 需在本次 Change 更新后重新取得 |

# 完成审计

- [x] upstream_re_read：已重新读取 Issue #319、Agent_Skills #184、AIMA `AGENTS.md`、现有三类 Issue Forms、PR Template、checker、冻结 Red 和最终 diff。
- [x] change_coverage：AC1–AC5、AC7 已由直接 Evidence 覆盖；AC6、AC8、AC9 的 final-head/main/archive/Closure 部分显式 deferred 到对应正式生命周期，不伪造未来证据。
- [x] reverse_audit：已从最终 diff 反查没有复制通用 canonical 正文、没有删除 AIMA 类型专项字段、checker 没有越权推断自然语言完成状态、没有修改产品行为。
- [x] unresolved_cleared：当前实现/Review 无未解决 blocker；仅剩明确登记的 final-head CI、merge/main-fresh、archive 与 Issue Closure 生命周期事项。
