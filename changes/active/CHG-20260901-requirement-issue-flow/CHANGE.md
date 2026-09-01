---
schema: coding-change/v1
id: CHG-20260901-requirement-issue-flow
title: 建立 AIMA 多人协作 Issue 到 PR 需求追溯入口
level: L2
status: in_progress
owner: dingyuwen777
branch: chore/requirement-issue-flow
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - github-collaboration
  - docs
  - ci
affected_paths:
  - .github/ISSUE_TEMPLATE/01-requirement.yml
  - .github/ISSUE_TEMPLATE/02-bug.yml
  - .github/ISSUE_TEMPLATE/config.yml
  - .github/PULL_REQUEST_TEMPLATE.md
  - AGENTS.md
contracts: []
data_changes: []
---

# 目标

为 AIMA_UGC 建立最小可运行的多人协作需求追溯入口：功能与缺陷先通过结构化 Issue 形成团队可访问的 Requirement Source，PR 使用稳定的 `Requirement-Source:` 关系指向上游需求，Agent_Skills Review 能据此独立重建目标、验收和不变项；找不到可验证来源时不得把 PR 判定为整体需求符合或可合并。

# 成功标准

- [ ] GitHub 新建 Issue 时至少提供“需求 / 功能”和“缺陷 / Bug”两个结构化入口。
- [ ] 需求表单要求目标、范围、非目标、验收标准、必须保持不变和相关事实源。
- [ ] Bug 表单要求实际行为、期望行为、复现、证据、影响范围、回归范围和修复验收标准。
- [ ] PR 模板显式要求 `Requirement-Source:`；关闭关键字与需求追溯关系分开表达。
- [ ] AIMA 项目规则明确：多人协作 PR 的 Requirement Source 不可访问或不足时，可以继续局部代码质量 Review，但不得声明整体需求符合或可合并。
- [ ] 不引入 GitHub Project 状态机、标签自动化、独立 Agent Review 服务或自然语言需求解析 CI。
- [ ] 不修改业务代码、Contract、Schema/Migration、依赖、Runtime、Provider、Figma 或部署拓扑。

# 范围

- 新增 AIMA 项目级 GitHub Issue Forms：需求、Bug。
- 关闭 blank issue，减少绕过结构化入口的普通路径。
- 更新现有 PR Template 的 Requirement Source 区域。
- 在 AIMA 项目 Overlay 中增加最小多人协作追溯规则。
- 复用当前 Agent_Skills canonical 已存在的需求来源 / Issue / PR / Review 治理规则，不复制其通用正文到 AIMA。

# 非目标

- 不修改 Agent_Skills canonical：当前 main 已存在完整的需求来源、Issue Form、PR revision 绑定与 Review fail-closed 规则。
- 不在本轮启用或重构 GitHub Ruleset / Branch Protection；平台合并权限另按仓库设置执行。
- 不强制所有 L1 机械修改必须新建 Issue；是否需要独立 Requirement Source 继续按项目和 Agent_Skills 当前风险规则判断。
- 不增加“Ready for Development”状态机或 GitHub Project Board。
- 不让 CI 解析自然语言 Acceptance Criteria 的语义质量。

# 必须保持不变

- 当前 AIMA Change / Completion Gate / CI / Runtime / Full-stack / Tooling 门禁保持原语义。
- `.github/CODEOWNERS` 继续由当前仓库 Owner 维护，不在本 Change 改写。
- 项目真实 Contract、Schema/Migration、测试和代码仍是实现事实；Issue 是需求入口，不替代机器事实 Owner。
- Agent_Skills Source Mode 仍从 canonical Agent_Skills main 获取通用治理语义；AIMA 本地安装资产不反向成为 canonical。

# 关键决策

1. 新建独立 Issue Skill：不采用。Issue 是 Coding/Review 的上游需求载体，不值得增加新的专业 Skill。
2. 复制 Agent_Skills 三套完整 Issue Forms：不采用。AIMA 第一阶段只保留需求和 Bug 两类，减少填写与维护成本。
3. 首期增加复杂机器语义门禁：不采用。先通过 required Issue Form + PR Template + Agent Review fail-closed 跑通链路。
4. Requirement Source 与 `Closes/Fixes` 分离：采用。前者说明为什么审查，后者只在当前 PR 真正完成整个 Issue 时关闭事项。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 先能跑通 Issue → PR → Agent_Skills Review 的最小流程，不做得太复杂 | user:current-request | not_satisfied | 待实现 |
| R2 | Issue 必须给 Review 提供明确需求与验收依据 | user:current-request | not_satisfied | 待实现 |
| R3 | 通用能力应由 Agent_Skills 提供，项目只落项目级模板/规则 | user:previous-request | satisfied | Agent_Skills main 已存在需求来源与 PR 追溯治理 Reference、Issue Forms 和回归测试 |
| R4 | 不重复修改已经满足要求的 Agent_Skills canonical | current-repository-fact | satisfied | Agent_Skills main 已覆盖 Requirement Source resolved/partial/unavailable 与 PR revision fail-closed |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | 检查 Issue Form YAML 和 PR/AGENTS 项目规则的最小回归或治理检查 |
| 接口 / Contract | not_applicable | 不修改产品 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改运行时或持久化 |
| 用户 / Workflow Acceptance | required | 验证 GitHub Issue chooser / PR 模板结构可作为协作入口 |
| 跨组件 Golden Path | not_applicable | 不修改产品调用链 |
| 外部依赖 Probe | not_applicable | 不依赖外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建或 Runtime |
| Docs / Governance / Other | required | AIMA governance checker、Change Ready、CI 与 Review |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取用户要求、当前 Agent_Skills requirement/PR 规则和 AIMA 项目规则。
- [ ] change_coverage：确认 Issue Forms、PR Template 和项目追溯边界覆盖最小流程。
- [ ] reverse_audit：从 PR Review 反向确认能找到 Requirement Source；来源缺失时 fail closed。
- [ ] unresolved_cleared：R1/R2 在 Ready 前必须变为 satisfied。

# 任务

- [ ] 新增需求 Issue Form
- [ ] 新增 Bug Issue Form
- [ ] 新增 Issue chooser config
- [ ] 更新 PR Template
- [ ] 更新 AIMA 项目 Overlay
- [ ] 运行治理/文档/CI 验证
- [ ] 独立 Review
- [ ] PR 合并、main fresh CI、Change 归档

# 验证

待本轮实现后补充当前 HEAD 的新鲜证据。
