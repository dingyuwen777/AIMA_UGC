---
schema: coding-change/v1
id: CHG-20260928-144700-usage-review-guidance
title: 同步 USAGE Code Review 双模式指令
level: L2
status: ready_for_review
owner: dingyuwen777
branch: docs/646-usage-review-guidance
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on: []
affected_areas:
  - docs
  - review-guidance
  - governance
affected_paths:
  - USAGE.md
contracts:
  - Code Review user guidance
  - Review-only / Review-and-deliver prompt semantics
data_changes: []
---

# 变更摘要

把用户最终确认的“只审核”和“审核并合并”两套 Code Review 指令同步到根 `USAGE.md`，并保留现有“Review 后直接修复”为第三种独立模式。只修改人类使用说明，不改变 Review/Coding/Router 的 canonical 执行规则。

# 背景、现状与问题

Requirement Source：GitHub Issue #646。当前 Code Review 使用说明缺少完整“审核并合并”模板，且两个仓库的 Section 10 已经出现文案差异。用户明确要求两仓同步并交付到 main。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 影响 |
| --- | --- | --- | --- |
| E1 | 当前 `USAGE.md` 已有 Code Review 章节 | current main | 采用 targeted update，不新建文档 |
| E2 | 用户已确认“只审核 / 审核并合并”两套完整文本 | #646 | 作为本次文案 Requirement |
| E3 | canonical Review/Delivery 规则已经定义 blocking Finding、current-head CI、guarded merge、post-merge finalization | Agent_Skills current canonical Source | USAGE 只做入口，不成为第二套治理 Owner |

# 目标、成功标准与非目标

## 目标 / 成功标准

- AC1：Section 10 包含完整“只审核”模板。
- AC2：Section 10 包含完整“审核并合并”模板。
- AC3：继续保留“Review 后直接修复”为第三种模式。
- AC4：双模板不降低 Review、CI、Branch Protection、merge guard 或 post-merge closure 门禁。
- AC5：Section 18 快捷指令同步对应“只审核 / 审核并合并 / Review 并修复”入口。
- AC6：当前 HEAD 的 Review/CI 通过并完成 main-fresh、Change Archive、Issue Closure 与 cleanup。

## 非目标

- 不修改生产代码、Runtime、Router、Review/Coding canonical 规则、CI、模板、依赖或 Schema/Migration。
- 不创建 Release/Deploy。
- 不把 `USAGE.md` 变成机器治理事实源。

# 约束与意图决策

| 决策 | 结论 | 依据 |
| --- | --- | --- |
| 文档 Owner | 更新现有 `USAGE.md` | 已有唯一使用说明入口 |
| 双模板一致性 | 两仓 Section 10 核心正文保持一致 | 用户明确要求同步 |
| canonical Ownership | 规则仍由 Agent_Skills Review/Coding/Router 拥有 | 避免第二套事实 |
| Scope | 只改 Code Review 相关段落和快捷入口 | targeted Docs Impact |

# 修改方案与决策依据

1. 把 Section 10 重构为：10.1 只审核、10.2 审核并合并、10.3 Review 后直接修复。
2. 10.1/10.2 使用用户最终确认文本，不缩短关键门禁。
3. Section 18 增加/同步两条短指令，并保留 Review 并修复。
4. 验证最终两仓 Section 10 逐字一致；其余文档内容不机械同步。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 完整只审核模板 | #646 / AC1 | satisfied | Section 10.1 已按用户最终文本写入 |
| R2 | 完整审核并合并模板 | #646 / AC2 | satisfied | Section 10.2 已按用户最终文本写入 |
| R3 | 保留 Review 后直接修复 | #646 / AC3 | satisfied | Section 10.3 保留原独立修复模式 |
| R4 | 不降低治理门禁 | #646 / AC4 | satisfied | 双模板保留 blocking Finding、current HEAD、required CI、权限、Branch Protection 与 post-merge finalization |
| R5 | 快捷指令同步 | #646 / AC5 | satisfied | Section 18 已同步只审核 / 审核并合并 / Review 并修复 |
| R6 | 端到端交付 | #646 / AC6 | explicitly_deferred | post-merge lifecycle |

# 计划改动

| 文件 | 修改 | 对应要求 |
| --- | --- | --- |
| `USAGE.md` | Section 10 双模板 + 第三模式；Section 18 快捷入口 | R1-R5 |

# 验证矩阵

| 验证层 | 是否要求 | Evidence |
| --- | --- | --- |
| 文档结构 | required | Section 10/18 定向读取 |
| 跨仓一致性 | required | 两仓 Section 10 核心正文比较 |
| canonical 语义 | required | Review/Delivery Source 对照 |
| CI / Review | required | current-head repository gates |
| Runtime / Schema / Provider | not_applicable | 无对应变更 |

# 验证计划

- 定向检查 Section 10/18 标题和完整模板。
- 比较两个仓库最终 Section 10 文本。
- 独立 Review 对照 Requirement Source 与 canonical Review/Delivery 门禁。
- PR current-head CI；merge 后 main-fresh、Change Archive（适用时）与 Issue Closure。

# 风险、兼容性、迁移与回滚

主要风险：遗漏关键门禁、两仓文案漂移、误把 Review-and-deliver 写成自动修复。
兼容性：仅人类使用说明，现有工程行为不变。
数据 / Schema / Migration：不适用。
回滚：revert 对应文档 PR；无数据或部署状态恢复。

# 文档、依赖、部署与发布影响

- 文档：仅 `USAGE.md` targeted update。
- 依赖 / Contract / Schema / Migration：无。
- 部署 / Release：不适用。

# 完成审计

- [x] upstream_re_read
- [x] change_coverage
- [x] reverse_audit
- [x] unresolved_cleared

# 完成证据与状态

## 新鲜证据

- Requirement Source #646 已重读；AC1-AC5 与用户最终双模板一致。
- USAGE 文档提交：`54665a0725c26a35a136f2e0e0e05c1fee5088b7`。
- 两仓 Section 10 已定向读取并确认逐字一致。
- Section 18 已确认存在“只审核 / 审核并合并 / Review 并修复”快捷入口。
- canonical Ownership 审计：未修改 Review/Coding/Router 规则，USAGE 仅做人类入口。

## 未验证内容与剩余风险

- current-head CI 与 independent Review 尚未在 ready revision 上完成。
- merge/main-fresh/Change Archive/Issue Closure/cleanup 尚未完成。

## 交付状态

- implementation: complete
- delivery: PR ready candidate
- validation: document-level checks complete; current-head CI pending
- main_fresh: not_applicable before merge
- change_archive: not_applicable before merge
- requirement_closure: #646 open
- cleanup: pending
- end_to_end: incomplete
