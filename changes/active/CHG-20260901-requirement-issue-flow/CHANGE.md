---
schema: coding-change/v1
id: CHG-20260901-requirement-issue-flow
title: 建立 AIMA 多人协作 Issue 到 PR 需求追溯入口
level: L2
status: ready_for_review
owner: dingyuwen777
branch: chore/requirement-issue-flow
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - github-collaboration
  - ci
  - tests
affected_paths:
  - .github/ISSUE_TEMPLATE/01-requirement.yml
  - .github/ISSUE_TEMPLATE/02-bug.yml
  - .github/ISSUE_TEMPLATE/config.yml
  - .github/PULL_REQUEST_TEMPLATE.md
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_agent_governance.py
  - changes/active/CHG-20260901-requirement-issue-flow/CHANGE.md
contracts: []
data_changes: []
---

# 目标

为 AIMA_UGC 建立最小可运行的多人协作需求追溯入口：功能与缺陷先通过结构化 Issue 形成团队可访问的 Requirement Source，PR 使用稳定的 `Requirement-Source:` 关系指向上游需求，Agent_Skills Review 能据此独立重建目标、验收和不变项；Requirement Source 不可访问、不完整或已漂移时，是否允许给出整体需求符合/可合并结论继续由当前 Agent_Skills canonical Review 规则 fail closed。

# 成功标准

- [x] GitHub 新建 Issue 时提供“需求 / 功能”和“缺陷 / Bug”两个结构化入口。
- [x] 需求表单要求目标、范围、非目标、验收标准、必须保持不变和相关事实源。
- [x] Bug 表单要求实际行为、期望行为、复现、证据、影响范围、回归范围、修复验收标准和相关事实源。
- [x] PR 模板显式要求 `Requirement-Source:`；关闭关键字与需求追溯关系分开表达。
- [x] AIMA 项目治理 checker 持续保护两个 Issue Form、blank issue 关闭状态和 PR 追溯字段不被误删。
- [x] 通用 Requirement Source 解析、PR revision 绑定和 Review fail-closed 继续由 Agent_Skills canonical 单一维护，不复制进 AIMA 项目 Overlay。
- [x] 不引入 GitHub Project 状态机、标签自动化、独立 Agent Review 服务或自然语言需求解析 CI。
- [x] 不修改业务代码、Contract、Schema/Migration、依赖、Runtime、Provider、Figma 或部署拓扑。
- [ ] PR 合并后取得 AIMA `main` fresh CI，随后独立归档本 Change 并验证归档后的最终 `main`。

# 范围

- 新增 AIMA 项目级 GitHub Issue Forms：需求、Bug。
- 关闭 blank issue，减少绕过结构化入口的普通路径。
- 更新现有 PR Template 的 Requirement Source 区域。
- 扩展 AIMA 自有 governance checker 和单元回归，保护项目 Profile 的最小结构。
- 复用当前 Agent_Skills canonical 已存在的需求来源 / Issue / PR / Review 治理规则，不复制其通用正文到 AIMA。

# 非目标

- 不修改 Agent_Skills canonical：当前 main 已存在完整的需求来源、Issue Form、PR revision 绑定与 Review fail-closed 规则。
- 不在本轮启用或重构 GitHub Ruleset / Branch Protection；平台合并权限另按仓库设置执行。
- 不强制所有 L1 机械修改必须新建 Issue；是否需要独立 Requirement Source 继续按项目和 Agent_Skills 当前风险规则判断。
- 不增加“Ready for Development”状态机或 GitHub Project Board。
- 不让 CI 解析自然语言 Acceptance Criteria 的语义质量。
- 不新增独立 Issue Skill；Issue 继续作为 Coding / Review 的上游需求载体。

# 必须保持不变

- 当前 AIMA Change / Completion Gate / CI / Runtime / Full-stack / Tooling 门禁保持原语义。
- `.github/CODEOWNERS` 继续由当前仓库 Owner 维护，不在本 Change 改写。
- 项目真实 Contract、Schema/Migration、Figma、测试和代码仍是各自事实 Owner；Issue 是需求入口，不替代机器事实。
- Agent_Skills Source Mode 仍从 canonical Agent_Skills main 获取通用治理语义；AIMA 本地安装资产不反向成为 canonical。

# 关键决策

1. **新建独立 Issue Skill**：不采用。Issue 是 Coding/Review 的上游需求载体，不值得增加新的专业 Skill。
2. **复制 Agent_Skills 三套完整 Issue Forms**：不采用。AIMA 第一阶段只保留需求和 Bug 两类，减少填写与维护成本。
3. **把 Review fail-closed 通用正文复制到 AIMA `AGENTS.md`**：不采用。Review 语义已经由 Agent_Skills canonical 单一维护；AIMA 只保存项目 Profile，避免双 Owner 漂移。
4. **首期增加复杂机器语义门禁**：不采用。机器只检查项目 Profile 的关键结构是否存在；Acceptance Criteria 的质量和需求符合性仍由 Agent_Skills 语义 Review 判断。
5. **Requirement Source 与 `Closes/Fixes/Resolves` 分离**：采用。前者说明为什么审查，后者只在当前 PR 真正完成整个 Issue 时关闭事项。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 先能跑通 Issue → PR → Agent_Skills Review 的最小流程，不做得太复杂 | user:current-request | satisfied | 两个 Issue Form + chooser config + PR `Requirement-Source:` 已落地；治理 checker/回归已 Green；CI `33475508841` success |
| R2 | Issue 必须给 Review 提供明确需求与验收依据 | user:current-request | satisfied | 需求 Form 固定目标/范围/非目标/AC/不变项/事实源；Bug Form 固定 actual/expected/impact/repro/evidence/regression/AC/事实源 |
| R3 | 通用能力应由 Agent_Skills 提供，项目只落项目级模板/接线 | user:previous-request | satisfied | Agent_Skills main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057` 已存在需求来源与 PR 追溯治理 Reference、Issue Forms 和回归测试；AIMA 未复制通用 Review 规则 |
| R4 | 不重复修改已经满足要求的 Agent_Skills canonical | current-repository-fact | satisfied | 当前 canonical 已覆盖 Requirement Source `resolved/partial/unavailable` 与 PR base/head revision fail-closed；本任务 Agent_Skills diff 为 0 |
| R5 | 功能 PR 合并、main fresh CI 与独立 Change 归档 | project-delivery | explicitly_deferred | 必须在 PR #279 合并后产生真实 main 证据；归档前不得把该责任写成已完成 |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Red `33474958230`：706 个 Unit 中仅新增追溯回归失败；Green `33475508841`：Unit/Contract/API 全绿 |
| 接口 / Contract | not_applicable | 不修改产品 Contract；完整 CI 的生成/兼容检查仍通过 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 本任务不修改运行时/持久化；完整 PostgreSQL Integration 作为额外回归证据全绿 |
| 用户 / Workflow Acceptance | required | GitHub Issue chooser Profile + PR Template 作为协作入口；checker 防止关键结构被删除 |
| 跨组件 Golden Path | not_applicable | 不修改产品调用链；Full-stack `33475508835` 作为额外回归证据 success |
| 外部依赖 Probe | not_applicable | 不依赖外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建/Runtime；Wheel、Frontend build/Browser Mock、Runtime `33475508838` 均作为额外回归证据成功 |
| Docs / Governance / Other | required | `check_agent_governance.py`、Secret/docs facts、Change Completion Gate `33475508861` 与 CI Gate 均成功 |

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户“先能跑起流程、不要太复杂”的要求、当前 Agent_Skills requirement/PR 规则和 AIMA 项目 Profile/CI 事实。
- [x] change_coverage：当前正式 diff 只包含 Issue Forms、chooser、PR Template、项目 checker/测试和本 Change；未遗留临时 Workflow 或 AGENTS 计划改动。
- [x] reverse_audit：从 Review 反向确认 PR 可通过 `Requirement-Source:` 找到 Issue/正式需求；来源解析和 revision fail-closed 由 canonical Agent_Skills 承担，AIMA 不维护第二套语义。
- [x] unresolved_cleared：R1–R4 已有当前 HEAD 证据；R5 明确只延后到 merge 后交付阶段，不降低完成责任。

# 任务

- [x] 新增需求 Issue Form
- [x] 新增 Bug Issue Form
- [x] 新增 Issue chooser config
- [x] 更新 PR Template
- [x] 强化项目 governance checker 与回归
- [x] Red → Green 并运行永久 PR CI
- [ ] 独立 Review / final-head re-review
- [ ] PR 合并、main fresh CI、Change 归档

# 验证

## Red

- CI `33474958230`：Repository Quality 在 Unit 阶段按预期失败；706 个 Unit 中仅 `test_checker_requires_issue_and_pr_requirement_traceability` 失败，其余 705 个通过。失败原因是旧 checker 尚无 GOV012/013/014 追溯检查，证明新增回归有效。

## Green

- 实现候选 `3aa56ea6b057efc0ffbdc6719b7e1b04f5989a04`。
- CI `33475508841`：success；Python format/lint/type、706 Unit、Contract/API、Architecture/Owner、Secret/docs/governance、Wheel、Frontend unit/build/Browser Mock、PostgreSQL Integration 全部成功。
- Runtime Acceptance `33475508838`：success。
- Full-stack Acceptance `33475508835`：success。
- Change Completion Gate `33475508861`：success。

## Review 前结论

- 实现 diff 未修改 AIMA `AGENTS.md`、业务代码、Contract、Schema/Migration、依赖或 Runtime。
- 早期计划中的“把通用 Review fail-closed 写入 AIMA Overlay”已在实现审查中撤销；canonical Agent_Skills 保持唯一通用规则 Owner。
- 当前 Change 进入 `ready_for_review`；正式可合并结论必须绑定本次 Change-only 更新后的 final HEAD、fresh CI 和独立 Review。
