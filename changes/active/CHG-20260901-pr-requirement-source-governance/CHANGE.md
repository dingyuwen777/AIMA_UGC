---
schema: coding-change/v1
id: CHG-20260901-pr-requirement-source-governance
title: 补齐 PR 需求追溯与轻量协作治理
level: L3
status: ready_for_review
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
  - tests/unit/test_agent_governance.py
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/active/CHG-20260901-pr-requirement-source-governance/CHANGE.md
contracts: []
data_changes: []
---

# 目标

补齐 AIMA_UGC 多人协作的最小需求追溯闭环：真实 PR 必须指向可验证的 Requirement Source；普通 L2 使用最小充分任务契约而不是一律创建持久 Change；Issue chooser 增加技术变更入口。

# 成功标准

- [x] `Requirement Traceability and Completion Audit` 保持现有 Required Check 名称和原治理/Ready Check 责任，并新增真实 PR Requirement Source 校验。
- [x] PR 缺少来源、存在占位来源、来源无法解析或不可访问时 fail closed；合法 Issue 或仓库正式路径通过。
- [x] 一个 PR 可以声明多个 Requirement Source，机器只校验追溯事实，不判断自然语言需求完整性或实现符合性。
- [x] 新增技术变更 Issue Form，覆盖工程变更所需的最小充分字段。
- [x] AIMA Blueprint 不再把所有普通 L2 强制升级为 Active Change；持久 gated L2/L3 的 Change/Completion 责任保持不变。
- [ ] 最终 PR revision 完成 Deep Review、Required Checks、正常合并与 main fresh CI 后归档。

# 范围

- 新增项目自有 PR Requirement Source parser/validator 与 Unit 回归。
- 在现有 Change Completion Gate 中调用该校验，并赋予最小 `issues: read` 权限。
- 更新 PR 模板，公开机器支持的来源格式和失败边界。
- 扩展 AIMA governance checker，防止技术变更表单与 PR traceability 接线漂移。
- 新增技术变更 Issue Form。
- 定向修正 Blueprint 06 的 L2 / persistent Change 语义。

# 非目标

- 不新增第二个 Required Check 或独立 traceability Workflow。
- 不修改 Ruleset check 名称、业务 API、Contract、Schema/Migration、数据库、Provider、前端功能或部署拓扑。
- 不升级 Python、uv、依赖或 GitHub Actions。
- 不让 CI 判断自然语言需求质量、需求覆盖或实现是否满足需求。
- 不强制所有 L1/L2 创建 Issue 或持久 Change。

# 必须保持不变

- Required Check `Requirement Traceability and Completion Audit` 名称保持不变。
- `scripts/quality/check_agent_governance.py` 与 `.agents/skills/coding/scripts/ready_check.py` 继续在现有 Completion Gate 中执行。
- PR 来源校验失败必须给出可操作诊断；GitHub API 无法确认来源时不得乐观通过。
- 产品 Runtime、依赖、API、数据和部署行为保持不变。

# 关键决策

1. **在现有 Completion Gate 内新增项目自有 Python 校验**：采用。保持 Required Check identity 和单一治理 Owner，脚本可单元测试，失败诊断清晰。
2. **新增独立 Requirement Source Workflow/Required Check**：不采用。会新增 Ruleset 消费者和重复 checkout/setup，第一版协作闭环没有独立收益。
3. **只用 Workflow shell/正则直接解析 PR body**：不采用。Issue/路径存在性、错误处理和多来源规则难以稳定测试，长期维护成本更高。
4. **让机器判断 Issue 需求是否完整或 PR 是否满足需求**：不采用。机器只验证稳定追溯事实；语义完整性继续由 Completion Audit / Agent Review 承担。

# Requirement Traceability

| 编号 | 要求 | 来源 | 状态 | 证据 |
| --- | --- | --- | --- | --- |
| R1 | 真正校验每个 PR 的 `Requirement-Source` | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | `scripts/quality/check_pr_requirement_source.py` + Unit；真实 PR #287 的 Completion Gate `33514375840` 中 `Verify PR Requirement Source` 成功确认 `#286` |
| R2 | 修正 AIMA 文档中“所有 L2 必须 Active Change”的过重规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | `docs/blueprint/06_开发约束与分阶段实施.md` 明确普通 L2 使用最小充分任务契约，只有有持久价值时升级 Change；Docs and Governance 在 CI `33514376272` 通过 |
| R3 | 增加“技术变更” Issue 模板 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | `.github/ISSUE_TEMPLATE/03-technical-change.yml` + `check_agent_governance.py` / Unit 接线回归；Docs and Governance 在 CI `33514376272` 通过 |
| R4 | 不新增平行 Workflow/Required Check，不改变产品接口、数据或依赖 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | 继续使用现有 Change Completion Gate 与相同 job 名；compare 仅涉及治理/测试/文档文件，无产品 Contract/Schema/lock 变更 |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required / green | 有效 Red：CI `33512788064` / Repository Quality `99872369242` 在格式、ruff、mypy通过后，Unit collection 因 checker 尚不存在而 exit 2；Green：CI `33514376272` 的 Unit/Contract/API 阶段成功 |
| 接口 / Contract | not_applicable | 不修改产品 public API/ABI/HTTP/Schema/generated Contract；同一 Green CI 的 generated contract/client drift check 也通过 |
| 集成 / Persistence / Runtime Dependency | required / green | PR #287 的真实 GitHub Actions event + `GITHUB_TOKEN` + Issues API：Completion run `33514375840` / job `99877574319` 的 `Verify PR Requirement Source` 成功 |
| 用户 / Workflow Acceptance | required / green | 当前实现 PR #287 使用 `Requirement-Source: #286`，新 Required Completion Check 在真实 PR 中通过，而不是只靠 Mock/Unit |
| 跨组件 Golden Path | not_applicable / control-plane regression green | 不修改产品跨组件接线；因 CI-self 变更按保守分类执行，CI `33514376272` 的 Real Full-stack Golden Path 仍成功 |
| 外部依赖 Probe | not_applicable | GitHub Issues API 的真实 CI 调用已作为交付依赖证据；无业务 Provider 现时事实变化，不执行额外付费/外部 Probe |
| Build / Package / Runtime | not_applicable / regression green | 不修改产品 build/package/runtime；CI `33514376272` 的 Wheel、前端 build 与 Runtime Acceptance `33514375870` 成功 |
| Docs / Governance / Other | required / green | Docs and Governance、AIMA governance wiring、PR Requirement Source、changed PR Ready Check 均在当前 HEAD 的 Required/CI 流程中成功 |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| AIMA 项目治理接线 | Change Completion Gate / `check_agent_governance.py` | 原位置不变 | 保持并已实跑 | run `33514375840` step `Verify AIMA project governance wiring` success |
| gated Change Ready | Change Completion Gate / `ready_check.py` | 原位置不变 | 保持并已实跑 | run `33514375840` step `Enforce changed PR Change readiness` success |
| Required Check identity | `Requirement Traceability and Completion Audit` | 原名称不变 | 保持 | run `33514375840` job 仍名为 `Requirement Traceability and Completion Audit` |
| 真实 PR Requirement Source | 当前无永久证明责任 | Change Completion Gate / `check_pr_requirement_source.py` | 新增并已实跑 | run `33514375840` step `Verify PR Requirement Source` success |

# Completion Audit

- [x] upstream_re_read：Ready 前已重新读取 Issue #286、PR #287 的 Requirement Source、当前 base/head、main Ruleset 与受影响项目事实。
- [x] change_coverage：Issue #286 的三项用户目标分别映射到 checker/Workflow、Blueprint 06、技术变更 Issue Form，不以 Change checklist 代替上游要求。
- [x] reverse_audit：从 run `33514375840` 反向确认 governance checker、PR source validator、Ready Check 都实际执行；PR 模板和技术变更 Issue Form 已把协作者需要知道的规则放在正式入口。
- [ ] unresolved_cleared：待最终 revision-bound Deep Review 证明无 blocker，并确认最终 HEAD Required Checks 后再进入合并。

# 任务

- [x] 建立 Issue #286 与 L3 Change
- [x] 建立 PR Requirement Source Red 回归
- [x] 实现 parser/validator 和 GitHub Issue/仓库路径验证
- [x] 接入 Change Completion Gate 并保持稳定 check identity
- [x] 扩展 governance checker 与回归
- [x] 新增技术变更 Issue Form
- [x] 修正 Blueprint 06 的普通 L2 / persistent Change 规则
- [x] 完成 targeted docs/governance 验证
- [ ] 完成最终 revision-bound Deep Review、最终 HEAD Required Checks、merge 与 main fresh CI
- [ ] 归档 Change 并清理分支

# 验证证据

## Red

- 非目标 Red：CI `33512373583` 曾因新测试自身 Ruff format 失败；仅修测试格式后重跑，因此不把该结果当行为 Red。
- 有效 Red：CI `33512788064` / Repository Quality job `99872369242`。format、ruff、mypy 已通过，随后 Unit collection 因 `scripts/quality/check_pr_requirement_source.py` 尚不存在触发 `FileNotFoundError`，exit code 2。

## Green（实现 HEAD `1c676fcbd33eb64cc11d59be096c49e51d3f60e7`）

- CI `33514376272`：success；Repository Quality、Docs and Governance、PostgreSQL Integration、Real Full-stack Golden Path 与最终 `CI Gate` 全部成功。
- Change Completion Gate `33514375840`：success；job `99877574319` 中 governance wiring、`Verify PR Requirement Source`、changed PR Ready Check 全部成功。
- Runtime Acceptance `33514375870`：success。
- CI-self 变更按保守策略执行了完整产品回归，不依赖轻量路径自证。

# 文档同步

Docs Impact: targeted。只修改承担开发流程长期事实的 `docs/blueprint/06_开发约束与分阶段实施.md` 与直接面向 PR 作者的模板说明；未修改无关业务 Blueprint/Appendix。

# Git / 交付

- Requirement Source：Issue #286。
- 基线 main：`70b1c0fae6c6a8274ec6d03259b0dff57d06ca01`。
- 实现分支：`chore/pr-requirement-source-governance`。
- 实现 PR：#287 `治理：补齐 PR 需求追溯与轻量协作规则`。
- 当前已验证实现 HEAD：`1c676fcbd33eb64cc11d59be096c49e51d3f60e7`；本文件证据更新后 HEAD 会变化，最终 Review / merge 必须绑定更新后的实际 SHA，不能复用旧 HEAD Green 结论。
- Merge / main fresh CI / archive：待最终 Review 与最终 HEAD Required Checks 后执行。
