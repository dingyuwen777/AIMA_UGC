---
schema: coding-change/v1
id: CHG-20260901-requirement-issue-flow
title: 建立 AIMA 多人协作 Issue 到 PR 需求追溯入口
level: L2
status: done
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
  - changes/archive/2026-09/CHG-20260901-requirement-issue-flow/CHANGE.md
contracts: []
data_changes: []
---

# 目标

为 AIMA_UGC 建立最小可运行的多人协作需求追溯入口：功能与缺陷通过结构化 Issue 形成团队可访问的 Requirement Source，PR 使用稳定的 `Requirement-Source:` 指向上游需求，Agent_Skills Review 据此独立重建目标、验收和不变项；Requirement Source 不可访问、不完整或已漂移时，整体需求符合/可合并结论继续由 Agent_Skills canonical Review 规则 fail closed。

# 成功标准

- [x] GitHub 新建 Issue 时提供“需求 / 功能”和“缺陷 / Bug”两个结构化入口。
- [x] 需求表单要求目标、范围、非目标、验收标准、必须保持不变和相关事实源。
- [x] Bug 表单要求实际行为、期望行为、复现、证据、影响范围、回归范围、修复验收标准和相关事实源。
- [x] PR 模板显式要求 `Requirement-Source:`，并把关闭关键字与需求追溯关系分开。
- [x] AIMA 项目治理 checker 持续保护两个 Issue Form、blank issue 关闭状态和 PR 追溯字段不被误删。
- [x] 通用 Requirement Source 解析、PR revision 绑定和 Review fail-closed 继续由 Agent_Skills canonical 单一维护，不复制进 AIMA 项目 Overlay。
- [x] 不引入 GitHub Project 状态机、标签自动化、独立 Agent Review 服务或自然语言需求解析 CI。
- [x] 不修改业务代码、Contract、Schema/Migration、依赖、Runtime、Provider、Figma 或部署拓扑。
- [x] 功能 PR 已合并，AIMA `main` fresh CI/Runtime/Full-stack/Completion 全绿，并生成独立归档记录。

# 范围

- 新增 AIMA 项目级 GitHub Issue Forms：需求、Bug。
- 关闭 blank issue 普通入口。
- 更新 PR Template 的 Requirement Source 区域。
- 扩展 AIMA 自有 governance checker 和单元回归，保护项目 Profile 的最小结构。
- 复用 Agent_Skills canonical 已存在的需求来源 / Issue / PR / Review 治理规则，不复制其通用正文到 AIMA。

# 非目标

- 不修改 Agent_Skills canonical；当前 main 已具备完整的需求来源、Issue Form、PR revision 绑定与 Review fail-closed 规则。
- 不在本 Change 启用或重构 GitHub Ruleset / Branch Protection。
- 不强制所有 L1 机械修改必须新建 Issue。
- 不增加 Ready for Development 状态机、GitHub Project Board、标签自动化、独立 Agent Review 服务或自然语言 Acceptance Criteria 解析器。
- 不新增独立 Issue Skill。

# 必须保持不变

- 当前 AIMA Change / Completion Gate / CI / Runtime / Full-stack / Tooling 门禁保持原语义。
- `.github/CODEOWNERS` 不变。
- Contract、Schema/Migration、Figma、测试和代码仍是各自事实 Owner；Issue 是需求入口，不替代机器事实。
- Source Mode 的通用治理语义仍来自 Agent_Skills canonical；AIMA 本地安装资产不反向成为 canonical。

# 关键决策

1. **新建独立 Issue Skill**：不采用。Issue 是 Coding/Review 的上游需求载体。
2. **复制 Agent_Skills 三套完整 Issue Forms**：不采用。AIMA 第一阶段仅保留需求和 Bug 两类。
3. **把 Review fail-closed 通用正文复制到 AIMA `AGENTS.md`**：不采用。Agent_Skills canonical 保持唯一通用规则 Owner。
4. **首期增加复杂机器语义门禁**：不采用。机器只保护项目 Profile 的关键结构；Acceptance Criteria 的质量和需求符合性由 Agent_Skills 语义 Review 判断。
5. **Requirement Source 与 `Closes/Fixes/Resolves` 分离**：采用。前者用于审查追溯，后者只在 PR 真正完成整个 Issue 时关闭事项。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 先跑通 Issue → PR → Agent_Skills Review 的最小流程，不做复杂 | user:current-request | satisfied | 两个 Issue Form、chooser config、PR `Requirement-Source:`、checker/回归均已合入 main；PR #280 |
| R2 | Issue 给 Review 提供明确需求和验收依据 | user:current-request | satisfied | Requirement Form 与 Bug Form 均固定必要的需求/验收/证据字段 |
| R3 | 通用能力由 Agent_Skills 提供，项目只落项目级模板/接线 | user:previous-request | satisfied | Agent_Skills main `e5a147f08fb4d501e1e28a71c35bf7a100bc7057` 已提供 Requirement Source / PR revision / Review fail-closed；AIMA 未复制通用规则 |
| R4 | 不重复修改已经满足要求的 Agent_Skills canonical | current-repository-fact | satisfied | 本任务 Agent_Skills diff 为 0 |
| R5 | 功能 PR 合并、main fresh CI 与独立 Change 归档 | project-delivery | satisfied | PR #280 merge `bd0c6c25e121f02efb1bcfefa28cfdee9eda94f2`；main CI `33476510999`、Completion `33476511019`、Runtime `33476510993`、Full-stack `33476510996` 全部 success；本记录进入独立 archive PR |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | Red `33474958230`：706 Unit 中仅新增追溯回归失败；Green/final PR CI 全绿 |
| 接口 / Contract | not_applicable | 不修改产品 Contract；生成/兼容检查仍全绿 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改 Runtime/持久化；完整 PostgreSQL Integration 作为额外回归证据成功 |
| 用户 / Workflow Acceptance | required | Issue chooser Profile + PR Template + Agent_Skills Review 链路 |
| 跨组件 Golden Path | not_applicable | 不修改产品调用链；Full-stack 作为额外回归证据成功 |
| 外部依赖 Probe | not_applicable | 不依赖外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建/Runtime；Wheel、Frontend Browser Mock、Runtime 均成功 |
| Docs / Governance / Other | required | governance checker、Completion Gate、CI Gate、独立 Agent_Skills Review |

# Completion Audit

- [x] upstream_re_read：重新读取用户“先跑起流程、不要太复杂”的要求、Agent_Skills canonical requirement/PR 规则和 AIMA 项目事实。
- [x] change_coverage：正式实现只包含两个 Issue Form、chooser、PR Template、项目 checker/测试；无临时 Workflow 或 AGENTS 规则复制。
- [x] reverse_audit：PR 可通过 `Requirement-Source:` 找到 Issue/正式需求；来源解析与 revision fail-closed 由 Agent_Skills canonical 承担。
- [x] unresolved_cleared：R1–R5 均有真实实现、Review、PR/main fresh CI 或归档证据。

# 任务

- [x] 新增需求 Issue Form
- [x] 新增 Bug Issue Form
- [x] 新增 Issue chooser config
- [x] 更新 PR Template
- [x] 强化项目 governance checker 与回归
- [x] Red → Green 并运行永久 PR CI
- [x] 独立 Review / final-head re-review
- [x] 功能 PR 合并并验证 main fresh CI
- [x] 生成独立 Change 归档记录

# 验证

## Red

- CI `33474958230`：706 个 Unit 中仅新增 `test_checker_requires_issue_and_pr_requirement_traceability` 失败，其余 705 个通过，证明旧 checker 缺少 Issue/PR 追溯结构门禁。

## Green / PR

- 实现 Green CI `33475508841` success；Runtime `33475508838`、Full-stack `33475508835`、Completion `33475508861` success。
- 最终 feature head：`d1c8beb908b09e2dda7870278f0fb8070898ce3a`。
- 非 Draft PR #280 自身 fresh CI `33476154176`、Completion `33476154228`、Runtime `33476154196`、Full-stack `33476154247` 全部 success。
- Agent_Skills Review #5074547483 锚定 PR #280 / exact head `d1c8beb908b09e2dda7870278f0fb8070898ce3a`，结论 `NO_FINDINGS_WITHIN_SCOPE`。
- PR #280 合并 commit：`bd0c6c25e121f02efb1bcfefa28cfdee9eda94f2`。
- 早期 Draft #279 仅因连接器无法执行 Mark Ready 而关闭，最终实现与 head 未因此改变；正式交付 PR 为 #280。

## Main fresh validation

- `main@bd0c6c25e121f02efb1bcfefa28cfdee9eda94f2`。
- CI `33476510999`：success，包含 706 Unit、Contract/API、Architecture/Owner、Secret/docs/governance、Wheel、Frontend unit/build/Browser Mock 和完整 PostgreSQL Integration。
- Change Completion Gate `33476511019`：success。
- Runtime Acceptance `33476510993`：success。
- Full-stack Acceptance `33476510996`：success。

# 最终结论

AIMA 已具备第一阶段可运行的多人协作需求入口：先用需求/Bug Issue Form 固化 Requirement Source，PR 通过 `Requirement-Source:` 关联上游，Agent_Skills 使用 canonical 规则按真实 PR revision 独立 Review。机器门禁只保护结构，不尝试替代语义 Review；复杂协作自动化留待后续真实需要再增加。
