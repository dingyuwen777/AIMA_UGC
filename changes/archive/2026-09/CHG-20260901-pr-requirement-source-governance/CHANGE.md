---
schema: coding-change/v1
id: CHG-20260901-pr-requirement-source-governance
title: 补齐 PR 需求追溯与轻量协作治理
level: L3
status: done
owner: dingyuwen777
branch: chore/pr-requirement-source-governance
created: 2026-09-01
updated: 2026-09-01
completion_gate: required
depends_on: []
affected_areas:
  - ci
  - project-governance
  - issue-pr-traceability
  - documentation
affected_paths:
  - .github/workflows/change-completion-gate.yml
  - .github/PULL_REQUEST_TEMPLATE.md
  - .github/ISSUE_TEMPLATE/03-technical-change.yml
  - scripts/quality/check_pr_requirement_source.py
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_pr_requirement_source.py
  - tests/unit/test_change_completion_gate.py
  - tests/unit/test_agent_governance.py
  - docs/blueprint/06_开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 目标

补齐 AIMA_UGC 多人协作的最小需求追溯闭环：真实 PR 必须指向可验证的 Requirement Source；普通 L2 使用最小充分任务契约而不是一律创建持久 Change；Issue chooser 增加技术变更入口。

# 最终结果

- [x] `Requirement Traceability and Completion Audit` 保持原 Required Check 名称和原 governance / Ready Check 责任，并新增真实 PR Requirement Source 校验。
- [x] PR 缺少来源、使用占位值、来源不可解析或不可访问时 fail closed；合法同仓 Issue 或仓库正式路径通过。
- [x] 支持一个 PR 声明多个真实 Requirement Source；机器只校验追溯事实，不判断自然语言需求质量或实现符合性。
- [x] PR 正文被编辑后会重新执行 Requirement Source 校验，不能复用编辑前的绿色结果。
- [x] 新增“技术变更” Issue Form。
- [x] AIMA Blueprint 不再把普通 L2 一律要求为 Active Change；只有跨 Owner/跨 PR/长期审计/正式 Completion Gate 等有持久治理价值的 L2 才升级为持久 Change，L3 继续保留完整门禁。
- [x] PR #287 已按最终 head 正常合并到 `main`，实现 merge 后的 main fresh CI / Completion / Runtime 全部通过。

# 范围与实现

## PR Requirement Source 机器校验

新增 `scripts/quality/check_pr_requirement_source.py`：

- 从真实 PR body 提取一个或多个 `Requirement-Source:`；
- 支持同仓 `#<Issue编号>`；
- 支持仓库内安全、真实存在的相对正式文件路径；
- 拒绝缺失、空值、模板占位、TODO/TBD、自由文本未定义标识；
- GitHub `/issues` 返回对象若实际是 Pull Request，则拒绝作为 Issue Requirement Source；
- 拒绝不存在 Issue、路径逃逸、绝对路径和不存在路径；
- GitHub API 无法确认来源时 fail closed 并输出可操作诊断；
- 只使用最小 `issues: read` 权限，不引入新依赖。

## Completion Gate 接线

现有 `.github/workflows/change-completion-gate.yml` 保持：

- Workflow / Required Check identity 不变；
- `scripts/quality/check_agent_governance.py` 继续执行；
- `.agents/skills/coding/scripts/ready_check.py` 继续执行；

并新增：

- `Verify PR Requirement Source`；
- `issues: read`；
- `pull_request.types` 显式覆盖 `opened / synchronize / reopened / edited`。

因此 PR 代码更新和 PR 正文编辑都会重新检查 Requirement Source。

## 协作入口与项目规则

- `.github/PULL_REQUEST_TEMPLATE.md` 明确机器支持的 Requirement Source 格式及关闭关键字与追溯关系的区别；
- `.github/ISSUE_TEMPLATE/03-technical-change.yml` 增加工程治理类 Issue 入口；
- `scripts/quality/check_agent_governance.py` 与对应 Unit 回归保护上述永久接线；
- `docs/blueprint/06_开发约束与分阶段实施.md` 修正普通 L2 与持久 Change 的关系。

# 非目标与兼容性

本 Change 未修改：

- 业务 API / HTTP Contract；
- Canonical / Schema / Migration；
- 数据库业务语义；
- Provider / TikHub；
- 前端业务功能；
- Python / Node / uv / npm / PostgreSQL / GitHub Actions 版本；
- 业务依赖或 lock；
- 部署拓扑、Release 或生产环境。

没有执行生产部署或 Release，也没有业务 Provider Probe；这些边界对本次治理改动不适用。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 真正校验每个 PR 的 `Requirement-Source` | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | checker + Unit + PR #287 真实 Completion Gate；PR body `edited` 后 Completion `33517313888` 再次执行 `Verify PR Requirement Source` 并成功 |
| R2 | 修正 AIMA 文档中过重的 L2 规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | Blueprint 06 已改为普通 L2 最小充分任务契约，持久 gated L2/L3 保持完整治理；Docs/Governance CI 通过 |
| R3 | 增加“技术变更” Issue 模板 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | `.github/ISSUE_TEMPLATE/03-technical-change.yml` + governance checker / Unit 回归 |
| R4 | 不新增平行 Workflow/Required Check，不改变产品接口、数据或依赖 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | 复用原 Completion Gate；产品 Contract/Schema/lock 未变化；PR 与 main fresh CI 均通过 |

# Validation Matrix

| 验证层 | 最终状态 | 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required / passed | 初始有效 Red：CI `33512788064` 在 format/ruff/mypy Green 后因 checker 尚不存在而 Unit collection exit 2；Review finding Red：CI `33515205023` 仅 `edited` 重验回归失败，`736 passed / 1 failed`；Green：最终实现与 PR head CI Unit / Contract / API 全部成功 |
| 接口 / Contract | not_applicable | 不修改产品 public Contract；生成 Contract/client drift check 仍通过 |
| 集成 / Runtime Dependency | required / passed | 真实 GitHub PR event + `GITHUB_TOKEN` + Issues API 在 Completion Gate 中确认 Issue #286 |
| 用户 / Workflow Acceptance | required / passed | PR #287 使用 `Requirement-Source: #286`；PR body 编辑后 run `33517313888` 真实重新触发并通过来源校验 |
| 跨组件 Golden Path | product risk not_applicable / control-plane regression passed | CI-self 改动按 fail-closed 分类执行 Real Full-stack，PR 与 implementation merge main fresh 均通过 |
| 外部依赖 Probe | not_applicable | 无业务 Provider 当前事实变化；GitHub Issues API 已由真实 CI 覆盖 |
| Build / Package / Runtime | product risk not_applicable / regression passed | Wheel、frontend build、Runtime Acceptance 均通过 |
| Docs / Governance / Other | required / passed | Docs/Governance、governance wiring、Requirement Source、Change Ready、Issue Form、PR 模板均有机器证据 |

# Evidence Preservation Mapping

| 证明责任 | 结果 |
| --- | --- |
| AIMA 项目治理接线 | `check_agent_governance.py` 原位置保留，并在 Completion Gate 中持续执行 |
| gated Change Ready | `ready_check.py` 原位置保留，并在 Completion Gate 中持续执行 |
| Required Check identity | `Requirement Traceability and Completion Audit` 名称未改变 |
| 真实 PR Requirement Source | 新增到同一 Completion Gate，而非另建 Required Check |
| PR body 编辑后重新校验 | `pull_request.types: edited` + 永久回归测试保护 |

# Red / Green 与 Review

## Red

- 初始行为 Red：CI `33512788064` / Repository Quality `99872369242`，在 format/ruff/mypy通过后，Unit collection 因 `check_pr_requirement_source.py` 尚不存在而 exit 2。
- Review finding Red：CI `33515205023` / Repository Quality `99880446718`，format/ruff/mypy通过，Unit 结果 `1 failed, 736 passed`，唯一失败是 PR body 编辑后未重验 Requirement Source。

## Green

实现 revision `681526687fe3261c6ce61504efbd45d5d0fd6563`：

- CI `33515853617` success；
- Change Completion Gate `33515853402` success；
- Runtime Acceptance `33515853247` success；
- Unit `738 passed`；
- Contract `92 passed`；
- API `38 passed`；
- Frontend Unit `56 passed`；
- Browser Mock Acceptance `39 passed`；
- Wheel build/install/import、frontend production build、PostgreSQL Integration、Real Full-stack Golden Path success。

最终 PR head `295a001090a908e2f325474887a17d9580dc1dd9`：

- CI `33517305505` success，最终 `CI Gate` success；
- Runtime Acceptance `33517304894` success；
- Completion Gate `33517304782` success；
- PR body 编辑后额外 Completion Gate `33517313888` success，证明 `edited` 重验真实生效；
- `681526... → 295a001...` 的后续 diff 仅为 Active Change 证据文本，无实现代码漂移。

## Deep Review

- PR #287 L3 Deep Review submission：`5078944214`；
- 结论：`NO_FINDINGS_WITHIN_SCOPE`；
- Review 中发现 `edited` 事件缺口后已按 Red → Green 修复并 re-review；
- 合并前 review threads 为空。

# Git / 交付事实

- Requirement Source：Issue #286。
- 实现分支：`chore/pr-requirement-source-governance`。
- 实现 PR：#287 `治理：补齐 PR 需求追溯与轻量协作规则`。
- 最终 PR head：`295a001090a908e2f325474887a17d9580dc1dd9`。
- PR #287 使用 REST merge + `expected_head_sha=295a001090a908e2f325474887a17d9580dc1dd9` 正常合并。
- 实现 merge commit：`7c806bf434fc80b45e4c3651dd2665f865da4d0c`。
- merge 后 `main` 已确认指向 `7c806bf434fc80b45e4c3651dd2665f865da4d0c`。

## Implementation merge 后 main fresh evidence

- CI `33517778296`：success；Repository Quality、PostgreSQL Integration、Docs and Governance、Real Full-stack Golden Path、最终 `CI Gate` 全部 success。
- Runtime Acceptance `33517778009`：success。
- Change Completion Gate `33517778014`：success。

因此满足“实现 merge + main fresh CI 后再归档”的前置条件。

# Completion Audit

- [x] upstream_re_read：重新读取 Issue #286、PR #287、最终 base/head、main Ruleset 和受影响项目事实。
- [x] change_coverage：三项用户目标全部落到实现、文档或协作入口，不以 Change 自身作为需求全集。
- [x] reverse_audit：从真实 Completion Gate 反向确认 governance checker、Requirement Source validator、Ready Check 均执行；PR 模板和 Issue Form 对协作者公开规则。
- [x] unresolved_cleared：无 `not_satisfied`；Deep Review 无 blocker；PR 与 merge 后 main fresh 必需证据全部 Green。

# 归档

本文件在实现 PR #287 合并且 `main` fresh CI / Completion / Runtime 全部成功后，从 `changes/active/` 移入 `changes/archive/2026-09/` 并标记 `done`。归档 PR 只承担历史状态收口，不改变产品或已合并治理行为。
