---
schema: coding-change/v1
id: CHG-20260901-pr-requirement-source-governance
title: 补齐 PR 需求追溯与轻量协作治理
level: L3
status: in_progress
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

- [ ] `Requirement Traceability and Completion Audit` 保持现有 Required Check 名称和原治理/Ready Check 责任，并新增真实 PR Requirement Source 校验。
- [ ] PR 缺少来源、存在占位来源、来源无法解析或不可访问时 fail closed；合法 Issue 或仓库正式路径通过。
- [ ] 一个 PR 可以声明多个 Requirement Source，机器只校验追溯事实，不判断自然语言需求完整性或实现符合性。
- [ ] 新增技术变更 Issue Form，覆盖工程变更所需的最小充分字段。
- [ ] AIMA Blueprint 不再把所有普通 L2 强制升级为 Active Change；持久 gated L2/L3 的 Change/Completion 责任保持不变。
- [ ] 新增行为先取得 Red，再完成 Green；最终 PR revision 完成 Deep Review 和 Required Checks 后合并，并取得 main fresh CI。

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
| R1 | 真正校验每个 PR 的 `Requirement-Source` | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | not_satisfied | 待实现并在真实 PR Completion Gate 验证 |
| R2 | 修正 AIMA 文档中“所有 L2 必须 Active Change”的过重规则 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | not_satisfied | 待定向修改 Blueprint 06 并执行 docs/governance 验证 |
| R3 | 增加“技术变更” Issue 模板 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | not_satisfied | 待新增表单并加入项目 governance checker 回归 |
| R4 | 不新增平行 Workflow/Required Check，不改变产品接口、数据或依赖 | https://github.com/dingyuwen777/AIMA_UGC/issues/286 | satisfied | 当前方案保持现有 Completion Check identity，affected_paths 不含产品/依赖事实源 |

# Validation Matrix

| 验证层 | 状态 | 范围 / 证据 |
| --- | --- | --- |
| 行为 / Unit / Component | required | PR body 来源解析、占位/多来源/Issue/路径/错误边界；先取得 Red，再 Green |
| 接口 / Contract | not_applicable | 不修改产品 public API/ABI/HTTP/Schema/generated Contract；PR 文本契约属于治理维度 |
| 集成 / Persistence / Runtime Dependency | required | 真实 GitHub Actions PR event + `GITHUB_TOKEN` + Issues API 在 Completion Gate 中验证 Issue #286 |
| 用户 / Workflow Acceptance | required | 当前实现 PR 作为真实协作者工作流，必须用 `Requirement-Source: #286` 通过 Required Completion Check |
| 跨组件 Golden Path | not_applicable | 不修改产品跨组件接线；CI-self 路径若仓库分类器保守触发 fullstack，只作为控制面回归证据，不改变本任务语义 |
| 外部依赖 Probe | not_applicable | GitHub API 的真实 CI 调用已归入交付/运行依赖证据，不额外建立外部 Probe |
| Build / Package / Runtime | not_applicable | 不修改产品 build/package/runtime；Workflow YAML 与 Python 脚本由 CI/治理验证 |
| Docs / Governance / Other | required | governance checker、docs check、Issue Form/PR 模板、稳定 Required Check identity、Change Ready 与最终 Review |

# Evidence Preservation Mapping

| 原证明责任 | 原位置 | 新位置 | 证据等级 | 依据 |
| --- | --- | --- | --- | --- |
| AIMA 项目治理接线 | Change Completion Gate / `check_agent_governance.py` | 原位置不变 | 保持 | 不删除、不迁移原步骤 |
| gated Change Ready | Change Completion Gate / `ready_check.py` | 原位置不变 | 保持 | 不删除、不迁移原步骤 |
| Required Check identity | `Requirement Traceability and Completion Audit` | 原名称不变 | 保持 | 仅在同一 Job 增加 PR 来源验证步骤 |
| 真实 PR Requirement Source | 当前无永久证明责任 | Change Completion Gate / 新项目脚本 | 新增 | 机器校验 PR body、来源语法和可访问性 |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取 Issue #286、最终 PR body/base/head、当前 Ruleset 与受影响项目事实。
- [ ] change_coverage：逐项比较 Issue #286 三项要求与最终实现/文档/表单，不以当前 Change 自身作为需求全集。
- [ ] reverse_audit：从 Required Completion Check 反向确认 governance checker、PR source validator、Ready Check 都实际执行；从 PR 模板/Issue Form 反向确认机器规则对协作者可见。
- [ ] unresolved_cleared：所有 not_satisfied 清零，Required Evidence 新鲜，Deep Review 无 blocker。

# 任务

- [x] 建立 Issue #286 与 L3 Change
- [ ] 建立 PR Requirement Source Red 回归
- [ ] 实现 parser/validator 和 GitHub Issue/仓库路径验证
- [ ] 接入 Change Completion Gate 并保持稳定 check identity
- [ ] 扩展 governance checker 与回归
- [ ] 新增技术变更 Issue Form
- [ ] 修正 Blueprint 06 的普通 L2 / persistent Change 规则
- [ ] 完成 targeted docs/governance 验证
- [ ] 完成最终 Deep Review、PR Required Checks、merge 与 main fresh CI
- [ ] 归档 Change 并清理分支

# 验证计划

1. Red：新增 PR Requirement Source 单元回归，在实现脚本不存在/行为缺失时确认失败原因正确。
2. Green：运行目标 Unit 与 `test_agent_governance.py`，确认解析、Issue/路径、Form/Workflow wiring 回归通过。
3. 运行 `python scripts/quality/check_agent_governance.py` 与项目 docs/secret/静态治理检查。
4. 在真实 PR 当前 HEAD 读取 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path` 结果；新的 Completion Gate 必须实际确认 Issue #286。
5. 对最终 base/head 执行 L3 Deep Review；合并前重新确认 current base/head、Ruleset 与 Required Checks。
6. REST merge 绑定 expected head；合并后读取 main fresh CI。实现 merge + main fresh 通过后再归档本 Change。

# 文档同步

Docs Impact: targeted。只修改承担开发流程长期事实的 `docs/blueprint/06_开发约束与分阶段实施.md` 与直接面向 PR 作者的模板说明；不扫描或改写无关业务 Blueprint/Appendix。

# Git / 交付

- Requirement Source：Issue #286。
- 基线 main：`70b1c0fae6c6a8274ec6d03259b0dff57d06ca01`。
- 实现分支：`chore/pr-requirement-source-governance`。
- PR / CI / merge / archive：待本轮实际完成后更新。
