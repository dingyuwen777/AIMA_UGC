---
schema: coding-change/v1
id: CHG-20260904-223025-ci-runner-consolidation
title: 收敛 PR CI 证明责任并降低 Runner Job 成本
level: L3
status: in_progress
owner: dingyuwen777
branch: infra/352-ci-runner-consolidation
created: 2026-09-04
updated: 2026-09-04
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - testing
  - governance
  - runtime
  - documentation
affected_paths:
  - .github/workflows/ci.yml
  - .github/workflows/runtime.yml
  - .github/workflows/change-completion-gate.yml
  - scripts/quality/classify_ci_scope.py
  - tests/unit/test_ci_scope.py
  - tests/unit/test_ci_workflow_structure.py
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/active/CHG-20260904-223025-ci-runner-consolidation/CHANGE.md
contracts:
  - CI Required Check Identity
  - CI Evidence Preservation
  - CI Scope Fail-Closed Contract
data_changes: []
---

# 背景与目标

Requirement Source：Issue #352。

当前 AIMA_UGC 的 PR 质量证明分散在 CI Scope、Docs/Governance、Repository Quality、Change Completion、Runtime fast-path 与总 Gate 等多个 Ubuntu runner Job。目标是在不降低 Requirement Source、Completion、Repository Quality、PostgreSQL、Real Full-stack、Compose Runtime 等现有证明责任的前提下，把可合并的同环境责任收敛，并让高成本独立层只在 changed scope 明确命中时启动。

# 范围 / 非目标

Included：CI DAG、changed-scope classifier、required context ownership、相关回归与当前 CI 开发说明。

Excluded：产品 API/Schema/Migration/业务行为、依赖或 Runtime 版本升级、Ruleset 放宽、正式 Release/Deploy。Release/Runtime 构建共享属于后续 P1，不作为本 Change 的完成条件。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` required check identity 保持；
- PostgreSQL Integration、Real Full-stack Golden Path、Compose Runtime Acceptance 的真实证明责任不删除；
- unknown path、CI/Workflow 自身变化继续 fail-closed；
- 不降低 secret/docs/governance、Requirement Source、Change readiness、lint/type/unit/contract/API/build/browser mock 等现有门禁；
- 不升级 Python、Node、npm、uv、Docker、Compose、Action 或业务依赖。

# Evidence Preservation Mapping

| 原责任 | 新 Owner | 证据变化 |
| --- | --- | --- |
| CI Scope | CI Core / classifier | 合并 runner，分类语义保持并扩展 Runtime responsibility |
| Docs and Governance | CI Core | 同一 checkout/Python runner 内执行，命令保持 |
| Requirement Traceability and Completion Audit | CI Core required job | required context 名称保持，命令保持 |
| Repository Quality | CI Core 条件 steps | 同一 runner 执行，质量命令保持；只去掉被完整 audit 覆盖的重复 prod-only npm audit |
| PostgreSQL Integration | 独立条件 Job | 保持真实 PostgreSQL |
| Real Full-stack Golden Path | 独立条件 reusable workflow | 保持真实 Golden Path |
| Compose Golden Path | CI 内独立条件 Job | 只在 classifier 命中 Runtime 时启动；job-level skip 保持 required check success 语义 |
| CI Gate | 最终 fail-safe Job | always + needs 汇总所有 required/not-applicable 结果 |

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 日常 PR runner Job 数至少下降 50% | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | in_progress | 待真实 PR Actions 统计 |
| R2 | 独立高价值测试责任与 fail-closed scope 不下降 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | in_progress | 待 classifier/workflow 回归与真实 CI |
| R3 | 三个 required context 保持并能阻塞失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | in_progress | 待 Ruleset + PR check-runs 复核 |
| R4 | 消除重复 runner 和重复 npm audit | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | in_progress | 待 diff / CI 证据 |
| R5 | 自动回归覆盖 scope 与 DAG fail-safe | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | in_progress | 待测试 |
| R6 | Review、merge、main fresh、archive、Closure | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 实现后按顺序完成 |

# Validation Matrix

| Layer | Required | Planned Evidence |
| --- | --- | --- |
| Unit / Component | required | `tests/unit/test_ci_scope.py`、Workflow 结构回归 |
| Contract / Governance | required | required check identity、Requirement Source、Change readiness |
| PostgreSQL | required_when_scoped | 现有 PostgreSQL Integration |
| Full-stack | required_when_scoped | 现有 Real Full-stack Golden Path |
| Runtime | required_when_scoped | 现有 Compose acceptance 原命令迁入条件 Job |
| Docs | required | CI Blueprint 当前事实同步 |
| GitHub PR / main | required | final-head CI、Review、guarded merge、main fresh |

# 实施步骤

- [x] 建立并写后重读 Issue #352。
- [x] 恢复 main、Ruleset、现有 Workflow、classifier、测试和 CI 文档事实。
- [x] 完成 Evidence Preservation Mapping。
- [ ] 修改 classifier 与 Red/Green 回归。
- [ ] 收敛 CI Workflow，并删除失去独立 Owner 的旧 Workflow。
- [ ] 更新当前 CI 文档。
- [ ] 完成 final-head CI、独立 L3 Review、Completion Audit。
- [ ] guarded merge、main fresh、独立 archive PR、Issue Closure Audit 与分支清理。

# 回滚

全部变化仅影响 CI 控制面；若 required context、scope 或 evidence 发生异常，回滚本 Change 的 Workflow/classifier/test/doc 提交即可。无数据迁移、生产部署或 Runtime 版本回滚要求。
