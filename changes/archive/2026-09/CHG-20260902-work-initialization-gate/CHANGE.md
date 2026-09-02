---
schema: coding-change/v1
id: CHG-20260902-work-initialization-gate
title: 建立本地分支优先的研发开工门禁
level: L2
status: done
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
contracts: []
data_changes: []
---

# 目标

把 AIMA_UGC 的正式研发开工顺序固化为项目 Overlay：需要持久 Change/PR 的开发任务先同步 `main` 并创建本地任务分支，在本地建立 Change 与首个治理/失败测试提交，首次 push 时才创建远程分支，随后尽早创建带 Requirement Source 的 PR；禁止直接在 `main` 上开始正式实现。

Requirement Source：https://github.com/dingyuwen777/AIMA_UGC/issues/290

# 成功标准

- [x] AIMA 项目规则明确区分本地分支、远程分支和早期 PR 的正确时序。
- [x] L1 快速路径继续保留；只读分析/方案/Review 不因本门禁获得写权限。
- [x] 持久 gated L2 和 L3 在生产代码前建立 Issue/正式 Requirement Source、Change 与本地任务分支。
- [x] 首个本地治理/失败测试提交完成后，首次 push 创建远程跟踪分支，再建立早期 PR。
- [x] 早期 PR 未达到 Ready 时保持 Draft；宿主无法可靠转 Ready 时使用普通 PR 并明确逻辑未就绪。
- [x] Issue、Change、branch、PR 保持稳定可追溯；项目机器门禁缺口已由 Issue #292 独立承载，不在本 PR 手改受管 Skill 或扩大 CI 基线修复。
- [x] 不新增平行 Workflow，不改变产品 Contract、Schema、依赖、Runtime 或部署。

# 范围

- 更新根 `AGENTS.md` 与 Blueprint 06 的项目开工/交付规则。
- 按当前 Branch Protection、Requirement Source、Completion、Review 和 CI 流程交付。

# 非目标

- 不把所有 L1、只读分析、方案或 Review 机械升级为 Issue/Change/PR。
- 不在远端先创建空分支。
- 不新增 GitHub Workflow、Required Check、Issue 状态机或 Project Board。
- 不在本 PR 修复 mixed legacy Change carrier；由 Issue #292 与 Agent_Skills Issue #158 独立处理。
- 不把 U1–U5 的 Python 格式和 Migration/MetaData 漂移混入治理 PR；由 Issue #293 独立处理。
- 不改变业务代码、API、Contract、Schema/Migration、依赖、Runtime、Figma 或部署拓扑。
- 不授予 merge、Release、部署、Issue 关闭或分支删除权限。

# 必须保持不变

- 现有 Requirement Source validator、Completion Gate、CI、Runtime、Full-stack 和 Review 门禁保持原语义。
- 当前未完成的 U1–U5 与声音广场 Change 状态不因本治理任务改变。
- AIMA 只维护项目 Overlay；通用规则仍由 `dingyuwen777/Agent_Skills` canonical Owner 维护。
- 提交消息继续使用中文，禁止绕过 Branch Protection/Ruleset/CI。

# 关键决策

- 方案 A（采用）：在现有项目规则与 Blueprint 中补充开工顺序；canonical Skill 由 Agent_Skills PR #157 维护，不在 AIMA 创建替代 Skill。
- 方案 B（拒绝）：只依赖全局指令。无法给项目协作者和 CI 留下稳定事实。
- 方案 C（拒绝）：由远端空分支或 PR 先行。本地尚无可审查提交，且把远程对象误当成本地开发起点。
- 不涉及数据 Migration、部署或 Release；回滚为撤销本次治理文本与回归。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 任务开始时建立 Issue、Change、分支与早期 PR 的可追溯流程 | https://github.com/dingyuwen777/AIMA_UGC/issues/290 | satisfied | Issue #290、当前 Change、本地分支 `chore/290-work-initialization-gate` 与 PR #291 已形成追溯链；`AGENTS.md` 与 Blueprint 06 固化顺序 |
| R2 | 本地开发先创建本地分支，不能先创建远程分支 | user:local-branch-first | satisfied | 首次 push 前已创建本地分支与提交 `1b3f3a5b`；`AGENTS.md` 与 Blueprint 06 明确禁止远程空分支先行 |
| R3 | Skill Mutation 只改 canonical Agent_Skills，不在 AIMA 新建替代 Skill | user:canonical-skill-owner | satisfied | AIMA diff 未新增 Skill；通用修改由 Agent_Skills Issue #156、Change 和 PR #157 独立承载 |
| R4 | 不改变现有产品能力与未完成 U1–U5 状态 | AGENTS.md | satisfied | 最终 diff 仅覆盖项目治理文档与当前 Change；Contract、Schema、依赖、Runtime 和既有 Active Change 状态未修改 |
| R5 | AIMA 项目机器门禁必须真实检查顶层当前 Change | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | explicitly_deferred | CI 已证明现有 Runtime 回退到 `carrier=.agents/changes, gated=0`；需先由 Agent_Skills #158 提供显式 carrier，再通过正式升级接入，禁止手改安装副本 |

# Validation Matrix

| 验证层 | 状态 | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | not_applicable | 最终 diff 只修改项目规则和 Change；AIMA 机器门禁正式延期至 Issue #292 |
| 接口 / Contract | not_applicable | 不修改产品 public Contract、OpenAPI 或 generated client |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改 PostgreSQL、文件、Worker 或 Runtime 依赖 |
| 用户 / Workflow Acceptance | required | 当前任务以本地分支、首次 push、早期 PR 的真实顺序完成一次闭环 |
| 跨组件 Golden Path | not_applicable | 不修改产品跨组件接线 |
| External Dependency / Provider Probe | not_applicable | 不改变 Provider/TikHub 边界 |
| Build / Package / Runtime | not_applicable | 不改变构建、包、镜像或启动行为 |
| Docs / Governance / Other | required | 项目治理与文档检查、当前 Change 语义校验、独立 Review、PR CI；main fresh 仅在获授权合并后执行 |

# Completion Audit

- [x] upstream_re_read：已重新读取 Issue #290、用户决定、项目 AGENTS/Blueprint、PR #291 与当前 CI 事实。
- [x] change_coverage：项目 Overlay 覆盖本地分支、首次 push、远程跟踪分支、早期 PR、追溯链和授权边界；机器 carrier 明确延期至 #292。
- [x] reverse_audit：已反查直接在 main 开工、远程空分支先行、无 Requirement Source PR、把 AIMA 本地 Skill 当 canonical 等错误路径。
- [x] unresolved_cleared：所有 `not_satisfied` 已清零；R5 按 #292 正式 `explicitly_deferred`，其余 Required 证据新鲜完整。

# 任务

- [x] 创建并关联 Issue #290
- [x] 从最新 `main` 创建本地分支 `chore/290-work-initialization-gate`
- [x] 建立本 Change
- [x] 提交本 Change，首次 push 创建远程分支并创建早期 PR #291
- [x] 更新项目规则与 Blueprint
- [x] 调查 Completion Gate carrier 与 U1–U5 CI 基线，分别建立 Issue #292、#293 和 Agent_Skills #158
- [x] 撤回与本 PR 目标无关的 checker/单测改动，避免把既有产品基线修复混入治理规则 PR
- [x] 运行项目治理、文档、架构、Owner 与 Secret 门禁
- [x] 对当前顶层 Change 运行同一 ready_check metadata/traceability/completion 语义校验；正式 carrier CI 延期至 #292
- [x] 执行独立 Standard Review 与 re-review，最终 diff 无剩余 Finding
- [x] 取得 PR #291 当前规则-only HEAD CI
- [x] PR #291 已合并，并在后续 `main` 提交上取得 Completion Gate、产品 CI 与 Runtime Acceptance 新鲜成功证据

# 验证

## 计划

- 目标检查：`git diff --check origin/main...HEAD`、人工核对 `AGENTS.md` 与 Blueprint 06 的顺序一致性
- 项目门禁：`uv run python scripts/quality/check_agent_governance.py`
- 就绪检查：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- `check_agent_governance.py`、`check_architecture.py`、`check_table_ownership.py`、`scan_secrets.py`、`check_docs.py` 均 exit 0。
- 真实工作流：本地分支与首个本地提交 `1b3f3a5b` 先于首次 push；随后创建远程跟踪分支和早期 PR #291。
- 托管调查：PR #291 Completion Gate 错误报告 `carrier=.agents/changes, gated=0`；AIMA #292 / Agent_Skills #158 已记录修复边界。
- 基线调查：当前 PR 触发 backend full 后发现 U1–U5 Ruff 与 Alembic drift；AIMA #293 独立承载，不跳过、不在本治理 PR 顺手格式化产品代码。
- Standard Review：最终范围仅为 `AGENTS.md`、Blueprint 06 与当前 Change；两处规则顺序一致，未改变产品 Contract/Schema/Runtime。早期发现的标点问题已由 `1c0affed` 修复，re-review 无剩余 Finding。
- PR CI：head `3e2448ba` 共 5 项成功，Repository Quality、PostgreSQL、Full-stack 3 项按 governance-only scope 跳过；这不作为 #292 或 #293 已完成的证据。
- Change 语义：直接调用正式 `ready_check.py` 的 `_metadata` 与 `_validate_ready_document` 校验顶层当前 Change → `status=ready_for_review; errors=0`；正式 carrier 自动选择仍由 #292 延期处理。
- 合并与 main fresh：PR #291 已合并为 `309aa9ced2d645971f2ab5d08e260764b8895b5a`；后续当前 `main` 提交 `f60f598c84e0696873cc01fc30f4d817ed51ae52` 的 Change Completion Gate run #33589659411、CI run #33589659720 和 Runtime Acceptance run #33589659537 均成功。

# 文档影响

- 更新项目长期研发流程；不更新产品 Blueprint、API、数据库或 Roadmap。

# 交付

- 提交：`1b3f3a5b`（Change）、`f23f1f38`（规则初稿）、`1c0affed`（Review 修复）
- 拉取请求：https://github.com/dingyuwen777/AIMA_UGC/pull/291（Requirement-Source: #290）
- 发布：不适用
