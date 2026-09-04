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
  - .github/workflows/change-completion-gate.yml
  - scripts/quality/check_agent_governance.py
  - scripts/quality/check_architecture.py
  - scripts/quality/check_change_completion.py
  - tests/unit/test_agent_governance.py
  - tests/unit/test_change_completion.py
  - tests/unit/test_change_completion_gate.py
  - tests/unit/test_ci_workflow_structure.py
  - changes/active/CHG-20260904-223025-ci-runner-consolidation/CHANGE.md
contracts:
  - CI Required Check Identity
  - CI Evidence Preservation
  - CI Scope Fail-Closed Contract
  - Archived Change Historical Source Contract
data_changes: []
---

# 背景与目标

Requirement Source：Issue #352。

当前 AIMA_UGC 的 PR 质量证明分散在 CI Scope、Docs/Governance、Repository Quality、Change Completion、Runtime fast-path 与总 Gate 等多个 Ubuntu runner Job。目标是在不降低 Requirement Source、Completion、Repository Quality、PostgreSQL、Real Full-stack、Compose Runtime 等现有证明责任的前提下，把可合并的同环境责任收敛，并让高成本独立层只在 changed scope 明确命中时启动。

实现过程中真实 CI 又暴露出一个历史生命周期边界：当前 `coding-change/v1` archive 会持续重验 Requirement Source，而历史 Change 可能引用后来正常删除/重命名的仓库文件。删除旧 Completion Workflow 后，2026-09-01 的已归档 Change 因该历史路径在当前 HEAD 不再存在而失败。该问题必须在不改写历史 Change、不放宽 Active Change 当前来源校验的前提下解决。

# 范围 / 非目标

Included：CI DAG、required context ownership、对应永久回归、AIMA 顶层 Change 对历史 archive Source 的 Git-revision 验真，以及当前 Change 生命周期。

Excluded：产品 API/Schema/Migration/业务行为、依赖或 Runtime 版本升级、Ruleset 放宽、正式 Release/Deploy。`Compose Golden Path` 本轮保持独立 Workflow；Release/Runtime 构建共享与 Runtime required context 迁移属于后续 P1，不冒险用 path-filtered required Workflow 制造 Pending。

# 必须保持不变

- `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` required check identity 保持；
- PostgreSQL Integration、Real Full-stack Golden Path、Compose Runtime Acceptance 的真实证明责任不删除；
- unknown path、CI/Workflow 自身变化继续由现有 classifier fail-closed；
- 不降低 secret/docs/governance、Requirement Source、Change readiness、lint/type/unit/contract/API/build/browser mock 等现有门禁；
- Active Change 的仓库相对 Requirement Source 必须继续在当前 HEAD 真实存在；只有已归档 Change 才允许在当前路径消失后回到该 archive 最后一次写入的 Git revision 验真，而且历史对象必须仍是 `blob` 文件，目录/tree 不能冒充文件；
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
| Archived Change 历史仓库来源 | AIMA `check_change_completion.py` | 当前文件存在时仍走 installed validator；仅当 archive 的仓库相对来源后来消失时，用该 Change 最后写入 revision + `git cat-file -t` 证明当时确为 `blob` 文件；虚构历史来源、历史目录来源与 Active 当前缺失来源继续失败 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 日常普通代码 PR runner Job 数至少下降 50% | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 新 DAG 的普通 frontend/backend 路径静态上界为 CI Core + CI Gate + Runtime fast-path = 3，对比原 6；最终必须由实现 merge 后的真实 backend-only PR Actions 统计回填。 |
| R2 | 独立高价值测试责任与 fail-closed scope 不下降 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | CI-self pre-review head `52e00918a957f2e0eb5dd77db65e9b210ae8729b` 的 run `33890912145` completed/success：Core、PostgreSQL Integration、Real Full-stack Golden Path、CI Gate 全部真实成功；同 HEAD Runtime Acceptance `33890911933` required context success，但因本 PR 未修改 Runtime 风险面而走 fast-path。`runtime.yml` 本 PR 无 diff；最近一次 runtime-risk PR #350 的 run `33864457072` 真实执行 canonical/Windows Compose startup、security、persistence、recovery 并全部 success。classifier 未放宽，Workflow 自身变化仍走 full。 |
| R3 | 三个 required context 保持并能阻塞失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | `Requirement Traceability and Completion Audit` 迁入 CI Core，`CI Gate` 与独立 `Compose Golden Path` 保持；Ruleset 未修改。`52e00918...` 已证明三个 required context 正常成功，最终仍以本治理收口后的 exact final-head required checks 作为 Review/merge 证据。 |
| R4 | 消除重复 runner 和重复 npm audit | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | Scope + Docs/Governance + Completion + Repository Quality 已收敛为一个 Ubuntu Core；独立 Completion Workflow 删除；前端只保留一次同阈值完整 `npm audit --audit-level=high`。 |
| R5 | Workflow 结构有永久回归并保持 fail-safe Gate | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | `tests/unit/test_ci_workflow_structure.py` 锁定 required context、旧独立 Job/Workflow 删除、edited metadata-only、audit 去重、高价值 Owner 与 6→3 普通代码 PR runner 模型；现有 `test_ci_scope.py` 继续覆盖 fail-closed classifier。`33890912145` 中这些回归包含在 820 个 Unit 测试内并成功。 |
| R6 | Review、merge、main fresh、archive、Closure | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 这些属于 exact final-head CI 后的 L3/Post-Merge 生命周期，按仓库顺序执行，不提前伪造完成。 |
| R7 | 删除旧 CI Owner 后不得改写历史 Change，也不能让 archive 历史来源或 Active 当前来源失真 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | Red run `33886825990` 精确暴露历史 archive R5 的旧 Workflow 来源在当前 HEAD 消失；项目 wrapper 使用 archive revision `git log` + `git cat-file -t`，仅接受历史真实 `blob` 文件。回归覆盖“历史真实文件后续删除通过 / 历史从未存在失败 / 历史目录来源失败 / Active 当前缺失失败”。 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| Unit / Component | required | `33890912145`：820 Unit、104 Contract、53 API 全部 success；Workflow/Change historical-source 回归包含其中。 |
| Contract / Governance | required | `33890912145`：Requirement Source、Change readiness、Secret/Docs、生成 Contract/Client、Architecture/Table Ownership 全部 success。 |
| PostgreSQL | required_when_scoped | `33890912145`：Migration、Platform、Database、Jobs、Collection、Content、Ingestion PostgreSQL Integration 全部 success。 |
| Full-stack | required_when_scoped | `33890912145`：Real Full-stack browser acceptance success。 |
| Runtime | required | 本 PR 未修改 `runtime.yml` 或 Runtime 风险面；同 HEAD Runtime Acceptance `33890911933` required context 走 fast-path 并 success。最近一次 runtime-risk PR #350 的 run `33864457072` 真实执行 canonical Compose 与 Windows overlay 的 startup/security/persistence/recovery，全步骤 success。 |
| Build / Frontend | required | `33890912145`：Wheel、Frontend lint/type/unit/build、Browser Mock Acceptance 全部 success。 |
| GitHub PR / main | required | exact final-head required checks、L3 Review、guarded merge、main fresh 尚按顺序执行。 |

# 实施步骤

- [x] 建立并写后重读 Issue #352。
- [x] 恢复 main、Ruleset、现有 Workflow、classifier、测试和 CI 文档事实。
- [x] 完成 Evidence Preservation Mapping。
- [x] 将 Scope、Governance、Completion、Repository Quality 收敛为 required CI Core。
- [x] 删除失去独立 Owner 的 Change Completion Workflow，并消除重复 npm audit。
- [x] 增加 Workflow responsibility / runner budget 永久回归。
- [x] 用真实 Red `33886825990` 定位旧 Workflow 删除后历史 archive Source 的当前路径漂移，并在 AIMA carrier wrapper 增加历史 revision `blob` 验真，不改写归档正文。
- [x] 用 `33890912145` 取得 CI full-scope pre-review Green，证明 Core、PostgreSQL、Real Full-stack 责任保留；同 HEAD Runtime `33890911933` required context fast-path success，真实 Runtime 全量责任由未改动的 `runtime.yml` 与最近 runtime-risk run `33864457072` 交叉证明。
- [ ] 当前治理记录/测试说明收口后的 exact final-head CI、独立 L3 Review、Completion Audit。
- [ ] guarded merge、main fresh、独立 backend-only 测量/归档 PR、Issue Closure Audit 与分支清理。

# 完成审计

- [x] upstream_re_read：收口前已重新读取 Issue #352、当前 main、active Ruleset、CI/Runtime/Completion 责任、classifier、AIMA Change wrapper、失败 archive、Architecture baseline 与相关测试；未发现目标或门禁漂移。
- [x] change_coverage：R1–R7 全部映射 #352；R2/R4/R5/R7 已由真实实现与 fresh full-scope evidence 闭合；R1/R3/R6 依赖 exact final-head、merge 后测量与生命周期，保持显式 deferred。
- [x] reverse_audit：从三个 required context 反查 CI Core、独立 Runtime、PostgreSQL、Real Full-stack 与最终 Gate；从 archive 缺失来源反查 archive revision/blob 与 Active 当前来源；从 Architecture Red 反查长期 REQUIRED Owner，未引入“缺文件即放行”或恢复重复 Workflow。
- [x] unresolved_cleared：没有 `not_satisfied`；尚需 exact final-head Actions/Review/merge/main-fresh/backend-only measurement/archive/Closure 的项均有明确后续 Owner，因此只标 `explicitly_deferred`。

# Red / Green 证据

- `33885551012`：旧 governance wiring 仍把独立 Completion Workflow 当唯一 Owner，Core 失败；Runtime `33885550801` success。
- `33886825990`：governance/Requirement Source 已通过，但历史 archive 的旧 Workflow Requirement Source 在当前 HEAD 消失，Change readiness 正确失败；高成本 Postgres/Full-stack 未继续启动。
- `33888070627` / `33888934097` / `33889320240`：依次暴露并修复纯 Ruff format/lint 问题，没有放宽规则。
- `33889779024`：Ruff/mypy、820 Unit、104 Contract、53 API success；Architecture checker正确暴露长期 REQUIRED 中仍引用旧 Completion Workflow 的过期机器事实。
- `33890912145`：同步 Architecture Owner 后 CI full-scope completed/success；Core、PostgreSQL、Real Full-stack、CI Gate 全绿。Runtime Acceptance `33890911933` 同 HEAD required context fast-path success；真实 Compose 全量基线为未改动 Runtime Workflow 的最近 runtime-risk run `33864457072`。

# 回滚

全部变化仅影响 CI/治理控制面；若 required context、scope、archive historical source 或 evidence 发生异常，回滚本 Change 的 Workflow/checker/test/architecture-baseline 提交即可。无数据迁移、生产部署或 Runtime 版本回滚要求。
