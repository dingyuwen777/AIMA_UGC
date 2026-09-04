---
schema: coding-change/v1
id: CHG-20260904-223025-ci-runner-consolidation
title: 收敛 PR CI 证明责任并降低 Runner Job 成本
level: L3
status: ready_for_review
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
  - tests/unit/test_ci_workflow_structure.py
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

Included：CI DAG、required context ownership、对应永久回归与当前 Change 生命周期。

Excluded：产品 API/Schema/Migration/业务行为、依赖或 Runtime 版本升级、Ruleset 放宽、正式 Release/Deploy。当前 GitHub 连接不提供 Ruleset 写接口，因此 `Compose Golden Path` 本轮保持独立 Workflow；Release/Runtime 构建共享与 Runtime required context 迁移属于后续 P1，不冒险用 path-filtered required Workflow 制造 Pending。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` required check identity 保持；
- PostgreSQL Integration、Real Full-stack Golden Path、Compose Runtime Acceptance 的真实证明责任不删除；
- unknown path、CI/Workflow 自身变化继续由现有 classifier fail-closed；
- 不降低 secret/docs/governance、Requirement Source、Change readiness、lint/type/unit/contract/API/build/browser mock 等现有门禁；
- 不升级 Python、Node、npm、uv、Docker、Compose、Action 或业务依赖。

# Evidence Preservation Mapping

| 原责任 | 新 Owner | 证据变化 |
| --- | --- | --- |
| CI Scope | CI Core / 现有 classifier | 合并 runner，分类语义保持 |
| Docs and Governance | CI Core | 同一 checkout/Python runner 内执行，命令保持 |
| Requirement Traceability and Completion Audit | CI Core required job | required context 名称保持，命令保持 |
| Repository Quality | CI Core 条件 steps | 同一 runner 执行，质量命令保持；仅删除被完整 audit 覆盖的重复 prod-only npm audit |
| PostgreSQL Integration | 独立条件 Job | 保持真实 PostgreSQL |
| Real Full-stack Golden Path | 独立条件 reusable workflow | 保持真实 Golden Path |
| Compose Golden Path | 独立 Runtime Workflow | required context 与真实 Compose 证明保持；本轮不做不安全的顶层 path filter |
| CI Gate | 最终 fail-safe Job | always + needs 汇总 scoped CI layers |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 日常普通代码 PR runner Job 数至少下降 50% | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 新 DAG 的普通 frontend/backend 路径静态上界为 CI Core + CI Gate + Runtime fast-path = 3，对比原 6；最终必须由真实 PR Actions 统计回填。 |
| R2 | 独立高价值测试责任与 fail-closed scope 不下降 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | PostgreSQL、Real Full-stack、Runtime Workflow 均保留原 Owner；classifier 未放宽，Workflow 自身变化仍走 full；结构回归反查高价值 Owner。 |
| R3 | 三个 required context 保持并能阻塞失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | `Requirement Traceability and Completion Audit` 迁入 CI Core，`CI Gate` 与独立 `Compose Golden Path` 保持；Ruleset 未修改，最终以 final-head check-runs 验证。 |
| R4 | 消除重复 runner 和重复 npm audit | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | Scope + Docs/Governance + Completion + Repository Quality 已收敛为一个 Ubuntu Core；独立 Completion Workflow 删除；前端只保留一次同阈值完整 `npm audit --audit-level=high`。 |
| R5 | Workflow 结构有永久回归并保持 fail-safe Gate | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | 新 `tests/unit/test_ci_workflow_structure.py` 锁定 required context、旧 Job/Workflow 删除、audit 去重、高价值 Owner 与 6→3 普通代码 PR runner 模型；现有 `test_ci_scope.py` 继续覆盖 fail-closed classifier。 |
| R6 | Review、merge、main fresh、archive、Closure | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 这些属于 final-head CI 后的 L3/Post-Merge 生命周期，按仓库顺序执行，不提前伪造完成。 |

# Validation Matrix

| Layer | Required | Planned Evidence |
| --- | --- | --- |
| Unit / Component | required | `tests/unit/test_ci_scope.py` + `test_ci_workflow_structure.py` + Repository Quality 全套 |
| Contract / Governance | required | required check identity、Requirement Source、Change readiness、docs/secret gates |
| PostgreSQL | required_when_scoped | 现有 PostgreSQL Integration |
| Full-stack | required_when_scoped | 现有 Real Full-stack Golden Path |
| Runtime | required | 现有 Runtime Workflow；本 CI-self PR 会真实运行 full Compose Acceptance |
| GitHub PR / main | required | final-head CI、L3 Review、guarded merge、main fresh |

# 实施步骤

- [x] 建立并写后重读 Issue #352。
- [x] 恢复 main、Ruleset、现有 Workflow、classifier、测试和 CI 文档事实。
- [x] 完成 Evidence Preservation Mapping。
- [x] 将 Scope、Governance、Completion、Repository Quality 收敛为 required CI Core。
- [x] 删除失去独立 Owner 的 Change Completion Workflow，并消除重复 npm audit。
- [x] 增加 Workflow responsibility / runner budget 永久回归。
- [ ] final-head CI、独立 L3 Review、Completion Audit。
- [ ] guarded merge、main fresh、独立 archive PR、Issue Closure Audit 与分支清理。

# 完成审计

- [x] upstream_re_read：写入前已重新读取 Issue #352、当前 main、Ruleset、CI/Runtime/Completion Workflow、classifier、测试与 Blueprint CI 事实，未发现目标或门禁漂移。
- [x] change_coverage：R1–R6 全部映射 #352；R2/R4/R5 已有机器实现/回归，依赖真实 GitHub final-head 的 R1/R3 与后置 R6 保持显式 deferred。
- [x] reverse_audit：从三个 required context 反查 CI Core、独立 Runtime、PostgreSQL、Real Full-stack 与最终 Gate；没有删除独立证明责任，也没有使用 workflow-level path filter 跳过 required check。
- [x] unresolved_cleared：没有 `not_satisfied`；尚需 Actions/Review/merge/main-fresh/archive/Closure 的项均有明确后续 Owner，因此只标 `explicitly_deferred`。

# 回滚

全部变化仅影响 CI 控制面；若 required context、scope 或 evidence 发生异常，回滚本 Change 的 Workflow/test 提交即可。无数据迁移、生产部署或 Runtime 版本回滚要求。
