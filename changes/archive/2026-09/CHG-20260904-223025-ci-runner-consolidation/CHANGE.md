---
schema: coding-change/v1
id: CHG-20260904-223025-ci-runner-consolidation
title: 收敛 PR CI 证明责任并降低 Runner Job 成本
level: L3
status: done
owner: dingyuwen777
branch: infra/352-ci-runner-consolidation
created: 2026-09-04
updated: 2026-09-05
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

AIMA_UGC 原 PR 质量证明分散在 CI Scope、Docs/Governance、Repository Quality、Change Completion、Runtime fast-path 与总 Gate 等多个 Ubuntu runner Job。目标是在不降低 Requirement Source、Completion、Repository Quality、PostgreSQL、Real Full-stack、Compose Runtime 等现有证明责任的前提下，把可合并的同环境责任收敛，并让高成本独立层只在 changed scope 明确命中时启动。

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
| Requirement Traceability and Completion Audit | CI Core required job | required context 名称保持，Requirement Source / Change readiness / governance 命令保持 |
| Repository Quality | CI Core 条件 steps | 同一 runner 执行，质量命令保持；仅删除被完整 audit 覆盖的重复 prod-only npm audit |
| PostgreSQL Integration | 独立条件 Job | 保持真实 PostgreSQL |
| Real Full-stack Golden Path | 独立条件 reusable workflow | 保持真实 Golden Path |
| Compose Golden Path | 独立 Runtime Workflow | required context 与真实 Compose 证明保持；本轮不做不安全的顶层 path filter |
| CI Gate | 最终 fail-safe Job | `always()` + needs 汇总 scoped CI layers |
| Archived Change 历史仓库来源 | AIMA `check_change_completion.py` | 当前文件存在时仍走 installed validator；仅当 archive 的仓库相对来源后来消失时，用该 Change 最后写入 revision + `git cat-file -t` 证明当时确为 `blob` 文件；虚构历史来源、历史目录来源与 Active 当前缺失来源继续失败 |

# 需求追溯

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 日常普通代码 PR runner Job 数至少下降 50% | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | 旧普通 frontend-only PR #343：CI run `33860391786` 实际分配 4 个 runner（CI Scope、Docs and Governance、Repository Quality、CI Gate），Change Completion run `33860391545` 1 个 runner，Runtime run `33860391543` 1 个 runner，共 6。实现 merge 后专用且不合并的 backend-only 测量 PR #356：CI run `33895201545` 只有 Core job `101096093751` 与 CI Gate `101096895889` 获得 runner，PostgreSQL `101096897398` / Real Full-stack `101096896354` 均 `runner_id=null`；Runtime run `33895201397` 的 Compose Golden Path `101096093122` 为第 3 个 runner。因此真实 `6→3`，下降 50%；PR #356 已关闭未合并，测量探针没有进入 main。 |
| R2 | 独立高价值测试责任与 fail-closed scope 不下降 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | final implementation HEAD `298f6e930e86a64498639bcacaf7951364215bf7` 的 CI run `33893555159`：Core、PostgreSQL Integration、Real Full-stack Golden Path、CI Gate 全部真实成功；同 HEAD Runtime Acceptance `33893554789` required context success，因本 PR 未修改 Runtime 风险面合法走 fast-path。`runtime.yml` 本 PR无 diff；最近一次 runtime-risk PR #350 的 run `33864457072` 真实执行 canonical/Windows Compose startup、security、persistence、recovery 并全部 success。classifier 未放宽，Workflow/CI 自身变化继续 fail-closed 到 full。 |
| R3 | 三个 required context 保持并能阻塞失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | active Ruleset `main-quality-gate`（21909651）仍严格要求 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`，本 Change 未修改/绕过 Ruleset；final HEAD 的 CI `33893555159` 与 Runtime `33893554789` 均 success。实现期间多个 Red（governance wiring、历史 Source、Ruff、Architecture baseline）均真实阻止 `CI Gate`，证明失败不会被 scoped skip 静默转绿。 |
| R4 | 消除重复 runner 和重复 npm audit | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | Scope + Docs/Governance + Completion + Repository Quality 已收敛为一个 Ubuntu Core；独立 Completion Workflow 删除；前端只保留一次同阈值完整 `npm audit --audit-level=high`。 |
| R5 | Workflow 结构有永久回归并保持 fail-safe Gate | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | `tests/unit/test_ci_workflow_structure.py` 锁定 required context、旧独立 Job/Workflow 删除、edited metadata-only、audit 去重、高价值 Owner 与普通代码 PR runner 模型；现有 `test_ci_scope.py` 继续覆盖 docs/governance、frontend、backend、contract、persistence、fullstack、runtime、CI-self、unknown 等 fail-closed classifier。final CI `33893555159` 中这些回归包含在 820 个 Unit 测试内并成功。 |
| R6 | Review、merge、main fresh、archive、Closure | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | explicitly_deferred | 实现阶段已完成：PR #353 final HEAD `298f6e93...` required CI `33893555159` / Runtime `33893554789` success；L3 Deep Review `5115416240` = `NO_FINDINGS_WITHIN_SCOPE`；guarded merge → `9a3f0a2baeaa00daf190fcfc38e6701bb33f5859`；该 exact merge revision main-fresh CI `33894306597` 与 Runtime `33894306245` success；AC1 测量 PR #356 已完成并关闭。当前归档 PR、archive-main fresh 与 Issue #352 Closure Audit 仍是本归档提交之后的后置动作，不在归档文件中提前伪造。 |
| R7 | 删除旧 CI Owner 后不得改写历史 Change，也不能让 archive 历史来源或 Active 当前来源失真 | https://github.com/dingyuwen777/AIMA_UGC/issues/352 | satisfied | Red run `33886825990` 精确暴露历史 archive R5 的旧 Workflow 来源在当前 HEAD 消失；项目 wrapper 使用 archive revision `git log` + `git cat-file -t`，仅接受历史真实 `blob` 文件。回归覆盖“历史真实文件后续删除通过 / 历史从未存在失败 / 历史目录来源失败 / Active 当前缺失失败”。 |

# Validation Matrix

| Layer | Required | Evidence |
| --- | --- | --- |
| Unit / Component | required | final CI `33893555159`：820 Unit、104 Contract、53 API 全部 success；Workflow/Change historical-source 回归包含其中。 |
| Contract / Governance | required | final CI `33893555159`：Requirement Source、Change readiness、Secret/Docs、生成 Contract/Client、Architecture/Table Ownership 全部 success。 |
| PostgreSQL | required_when_scoped | final CI `33893555159`：Migration、Platform、Database、Jobs、Collection、Content、Ingestion PostgreSQL Integration 全部 success。 |
| Full-stack | required_when_scoped | final CI `33893555159`：Real Full-stack Browser Golden Path success。 |
| Runtime | required | final HEAD Runtime Acceptance `33893554789` required context fast-path success；本 PR不修改 `runtime.yml`。最近 runtime-risk PR #350 run `33864457072` 对未改动 Runtime Workflow 真实执行 canonical Compose 与 Windows overlay startup/security/persistence/recovery 并全部 success。 |
| Build / Frontend | required | final CI `33893555159`：Wheel build/install、Frontend lint/typecheck、22 Vitest files / 107 tests、production build、Playwright 60/60 success。 |
| GitHub PR / main | required | PR #353 final-head CI/Runtime success；Deep Review `5115416240` no findings；guarded merge `9a3f0a2b...`；exact merge revision main-fresh CI `33894306597` + Runtime `33894306245` success；PR #356 真实证明日常 backend-only runner `6→3`。 |

# 实施步骤

- [x] 建立并写后重读 Issue #352。
- [x] 恢复 main、Ruleset、现有 Workflow、classifier、测试和 CI 文档事实。
- [x] 完成 Evidence Preservation Mapping。
- [x] 将 Scope、Governance、Completion、Repository Quality 收敛为 required CI Core。
- [x] 删除失去独立 Owner 的 Change Completion Workflow，并消除重复 npm audit。
- [x] 增加 Workflow responsibility / runner budget 永久回归。
- [x] 用真实 Red `33886825990` 定位旧 Workflow 删除后历史 archive Source 的当前路径漂移，并在 AIMA carrier wrapper 增加历史 revision `blob` 验真，不改写归档正文。
- [x] exact final-head CI `33893555159` 与 Runtime `33893554789` success；独立 L3 Review `5115416240` = `NO_FINDINGS_WITHIN_SCOPE`。
- [x] PR #353 guarded merge 到 `9a3f0a2baeaa00daf190fcfc38e6701bb33f5859`；exact merge revision main-fresh CI `33894306597` 与 Runtime `33894306245` success。
- [x] PR #356 在新 main 上完成 backend-only 实际 Runner 计数：旧 6 → 新 3，下降 50%；测量 PR 已关闭且未合并。
- [ ] 本独立 archive PR required checks、Review、guarded merge、archive-main fresh 与 Issue #352 Closure Audit。

# 完成审计

- [x] upstream_re_read：归档前已重新读取 Issue #352、当前 main、active Ruleset、final implementation PR/Review/Actions、AC1 测量 PR #356、CI/Runtime/Completion Owner 与当前 Change；未发现目标或门禁漂移。
- [x] change_coverage：R1–R7 全部映射 #352；R1–R5/R7 已有当前直接 Evidence；R6 的 implementation/measurement 部分已经完成，只有归档 PR 自身、archive-main fresh 与 Issue Closure 按生命周期显式 deferred。
- [x] reverse_audit：从三个 required context 反查 CI Core、独立 Runtime、PostgreSQL、Real Full-stack 与最终 Gate；从 archive 缺失来源反查 archive revision/blob 与 Active 当前来源；从实际 #343/#356 runner_id 反查成本模型，未用 skipped job object 冒充 runner 消耗。
- [x] unresolved_cleared：没有 `not_satisfied`；仅归档 PR 后置生命周期保持 `explicitly_deferred`，有明确 Owner 和执行顺序。

# Red / Green 证据

- `33885551012`：旧 governance wiring 仍把独立 Completion Workflow 当唯一 Owner，Core 失败；Runtime `33885550801` success。
- `33886825990`：governance/Requirement Source 已通过，但历史 archive 的旧 Workflow Requirement Source 在当前 HEAD 消失，Change readiness 正确失败；高成本 Postgres/Full-stack 未继续启动。
- `33888070627` / `33888934097` / `33889320240`：依次暴露并修复纯 Ruff format/lint 问题，没有放宽规则。
- `33889779024`：Ruff/mypy、820 Unit、104 Contract、53 API success；Architecture checker 正确暴露长期 REQUIRED 中仍引用旧 Completion Workflow 的过期机器事实。
- `33893555159`：final implementation HEAD full-scope CI completed/success；Core、PostgreSQL、Real Full-stack、Wheel、Frontend/Browser、CI Gate 全绿。Runtime `33893554789` required context success。
- `33894306597` / `33894306245`：implementation merge revision `9a3f0a2b...` 的 main-fresh CI / Runtime success。
- `33895201545` / `33895201397`：不合并的 backend-only PR #356 仅 3 个实际 runner；PostgreSQL/Real Full-stack job object 为 skipped 且 `runner_id=null`。对照旧 #343 的 CI `33860391786` + Completion `33860391545` + Runtime `33860391543` 共 6 runner，真实下降 50%。

# 回滚

全部变化仅影响 CI/治理控制面；若 required context、scope、archive historical source 或 evidence 发生异常，回滚本 Change 的 Workflow/checker/test/architecture-baseline 提交即可。无数据迁移、生产部署或 Runtime 版本回滚要求。
