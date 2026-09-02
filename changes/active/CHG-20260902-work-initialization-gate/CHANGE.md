---
schema: coding-change/v1
id: CHG-20260902-work-initialization-gate
title: 建立本地分支优先的研发开工门禁
level: L2
status: in_progress
owner: dingyuwen777
branch: chore/290-work-initialization-gate
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on: []
affected_areas:
  - project-governance
  - issue-pr-traceability
  - git-delivery
affected_paths:
  - AGENTS.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_agent_governance.py
contracts: []
data_changes: []
---

# 目标

把 AIMA_UGC 的正式研发开工顺序固化为项目 Overlay 和机器回归：需要持久 Change/PR 的开发任务先同步 `main` 并创建本地任务分支，在本地建立 Change 与首个治理/失败测试提交，首次 push 时才创建远程分支，随后尽早创建带 Requirement Source 的 PR；禁止直接在 `main` 上开始正式实现。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/290

# 成功标准

- [ ] AIMA 项目规则明确区分本地分支、远程分支和早期 PR 的正确时序。
- [ ] L1 快速路径继续保留；只读分析/方案/Review 不因本门禁获得写权限。
- [ ] 持久 gated L2 和 L3 在生产代码前建立 Issue/正式 Requirement Source、Change 与本地任务分支。
- [ ] 首个本地治理/失败测试提交完成后，首次 push 创建远程跟踪分支，再建立早期 PR。
- [ ] 早期 PR 未达到 Ready 时保持 Draft；宿主无法可靠转 Ready 时使用普通 PR 并明确逻辑未就绪。
- [ ] Issue、Change、branch、PR 保持稳定可追溯，机器回归防止规则被误删。
- [ ] 不新增平行 Workflow，不改变产品 Contract、Schema、依赖、Runtime 或部署。

# 范围

- 更新根 `AGENTS.md` 与 Blueprint 06 的项目开工/交付规则。
- 扩展现有 governance checker 和单元回归。
- 按当前 Branch Protection、Requirement Source、Completion、Review 和 CI 流程交付。

# 非目标

- 不把所有 L1、只读分析、方案或 Review 机械升级为 Issue/Change/PR。
- 不在远端先创建空分支。
- 不新增 GitHub Workflow、Required Check、Issue 状态机或 Project Board。
- 不改变业务代码、API、Contract、Schema/Migration、依赖、Runtime、Figma 或部署拓扑。
- 不授予 merge、Release、部署、Issue 关闭或分支删除权限。

# 必须保持不变

- 现有 Requirement Source validator、Completion Gate、CI、Runtime、Full-stack 和 Review 门禁保持原语义。
- 当前未完成的 U1–U5 与声音广场 Change 状态不因本治理任务改变。
- AIMA 只维护项目 Overlay；通用规则仍由 `dingyuwen777/Agent_Skills` canonical Owner 维护。
- 提交消息继续使用中文，禁止绕过 Branch Protection/Ruleset/CI。

# 关键决策

- 方案 A（采用）：在现有项目规则、Blueprint 与 governance checker 中补充开工顺序。复用现有 CI 入口，不增加平行 Workflow。
- 方案 B（拒绝）：只依赖全局指令。无法给项目协作者和 CI 留下稳定事实。
- 方案 C（拒绝）：由远端空分支或 PR 先行。本地尚无可审查提交，且把远程对象误当成本地开发起点。
- 不涉及数据 Migration、部署或 Release；回滚为撤销本次治理文本与回归。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 任务开始时建立 Issue、Change、分支与早期 PR 的可追溯流程 | https://github.com/dingyuwen777/AIMA_UGC/issues/290 | not_satisfied | 尚未实现 |
| R2 | 本地开发先创建本地分支，不能先创建远程分支 | user:local-branch-first | not_satisfied | 尚未实现 |
| R3 | Skill Mutation 只改 canonical Agent_Skills，不在 AIMA 新建替代 Skill | user:canonical-skill-owner | not_satisfied | Agent_Skills Issue #156/独立 Change 正在实施；AIMA 本 Change 不新增 Skill |
| R4 | 不改变现有产品能力与未完成 U1–U5 状态 | AGENTS.md；当前 Active Changes | not_satisfied | 待通过 diff 和回归证明 |

# Validation Matrix

| 验证层 | 状态 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 扩展 `test_agent_governance.py`，先证明开工顺序门禁缺失，再验证 checker |
| 接口 / Contract | not_applicable | 不修改产品 public Contract、OpenAPI 或 generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改 PostgreSQL、文件、Worker 或 Runtime 依赖 |
| 用户 / Workflow Acceptance | required | 当前任务以本地分支、首次 push、早期 PR 的真实顺序完成一次闭环 |
| 跨组件 Golden Path | not_applicable | 不修改产品跨组件接线 |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider/TikHub 边界 |
| Build / Package / Runtime | not_applicable | 不改变构建、包、镜像或启动行为 |
| Docs / Governance / Other | required | governance checker、Ready Check、独立 Review、PR CI 与 main fresh CI |

# Completion Audit

- [ ] upstream_re_read：重新读取 Issue #290、用户决定、项目 AGENTS/Blueprint 及当前 Git/CI 事实。
- [ ] change_coverage：确认项目 Overlay 与机器回归覆盖本地优先顺序、追溯链和授权边界。
- [ ] reverse_audit：反查直接在 main 开工、远程空分支先行、无 Requirement Source PR、把 AIMA 本地 Skill 当 canonical 等错误路径。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，Required Evidence 新鲜且完整。

# 任务

- [x] 创建并关联 Issue #290
- [x] 从最新 `main` 创建本地分支 `chore/290-work-initialization-gate`
- [x] 建立本 Change
- [ ] 提交本 Change，首次 push 创建远程分支并创建早期 PR
- [ ] 先扩展失败回归并取得 Red
- [ ] 更新项目规则、Blueprint 和 governance checker
- [ ] 运行目标测试、项目质量门禁与 Ready Check
- [ ] 执行独立 Review、PR CI、merge 授权检查和 main fresh 验证

# 验证

## 计划

- 目标测试：`uv run pytest tests/unit/test_agent_governance.py -q`
- 项目门禁：`uv run python scripts/quality/check_agent_governance.py`
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 尚未执行。

# 文档影响

- 更新项目长期研发流程；不更新产品 Blueprint、API、数据库或 Roadmap。

# 交付

- 提交：待创建
- 拉取请求：首次 push 后创建，Requirement-Source: #290
- 发布：不适用
