---
schema: coding-change/v1
id: CHG-20260902-change-carrier-gate
title: 修复顶层 Change carrier 完成门禁漏检
level: L3
status: done
owner: dingyuwen777
branch: fix/292-change-carrier-gate
created: 2026-09-02
updated: 2026-09-02
completion_gate: required
depends_on:
  - CHG-20260902-work-initialization-gate
affected_areas:
  - project-governance
  - ci
  - documentation
affected_paths:
  - scripts/quality/check_change_completion.py
  - scripts/quality/check_agent_governance.py
  - tests/unit/test_change_completion.py
  - tests/unit/test_agent_governance.py
  - .github/workflows/change-completion-gate.yml
  - AGENTS.md
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/archive/2026-09/
contracts: []
data_changes: []
---

# 背景与现状

AIMA 的项目 Change 由顶层 `changes/` 维护，其中既有当前 `coding-change/v1`，也有机制升级前归档的 `rvc-change/v1`。通用 resolver 为避免静默混用 schema，只有在整个 carrier 全部是当前 schema 时才选择顶层目录，因此当前 CI 回退到空的 `.agents/changes`，并输出 `gated=0, strict=0`。这会让顶层 Active Change 绕过机器完成门禁。

Agent_Skills #158 已明确 canonical 不提供 mixed legacy/current 兼容；历史策略必须由目标项目决定。本 Change 因而只在 AIMA 项目 Owner 内实现显式 carrier 适配，不修改受安装流程管理的 `.agents/skills`，也不创建替代 Skill。

# 目标

- 顶层 `changes/` 是 AIMA 唯一项目 Change carrier；
- 项目 checker 复用 installed ready-check 的当前 metadata、Requirement Traceability 与 Completion Audit 校验语义；
- 当前 `coding-change/v1` 在 Active/Archive 继续执行完整门禁；
- `rvc-change/v1` 和 schema 机制引入前的未版本化记录只允许作为不可变历史归档保留，不批量迁移；
- Workflow 日志明确输出 `carrier=changes`，且 `gated/strict` 非零；
- required check 名称、PR Requirement Source、Review、Ruleset 消费者与 main fresh 证据链保持不变。

# 范围

Included：AIMA 项目自有 checker、回归测试、Completion Gate 接线、静态治理自检、项目规则与开发 Blueprint；同时修正三份当前 schema 归档中已被后续仓库演进破坏的 Source/表头，使新门禁能真实检查全部当前记录。

Excluded：修改 Agent_Skills canonical 或本地 managed Skill、批量迁移 125 份 `rvc-change/v1` 与 3 份未版本化历史 Change、产品 Contract/Schema/Migration/依赖/运行时行为、Branch Protection 规则变更。

# 必须保持不变

- `.agents/` 仍是安装资产域，不成为 AIMA Change Owner；
- 通用 ready-check 的当前 schema 与文档校验语义不复制、不弱化；
- Workflow 名 `Change Completion Gate` 和 job/check 名 `Requirement Traceability and Completion Audit` 不变；
- 未改动的 legacy archive 保持可读，不因新门禁被批量重写；
- 删除、改名或移动不能成为规避当前 Change 门禁的手段。

# 方案比较

- 方案 A（采用）：项目自有 adapter 显式枚举顶层 carrier，并复用 installed validator；能表达 AIMA 的 legacy 政策，且不复制 Skill。
- 方案 B（不采用）：把 125 份 legacy 全量迁移为当前 schema；历史含义与证据不足，改写风险高且不属于本缺陷最小修复。
- 方案 C（不采用）：把当前 Change 移到 `.agents/changes`；会把项目事实写入安装资产域，破坏 Owner 与升级边界。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | PR 必须拦截新增或修改后仍为 in_progress 的顶层当前 Change | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | satisfied | 目标回归验证 changed-since 返回失败并包含 ready_for_review 诊断 |
| R2 | Ready 且追溯/审计完整的当前 Change 必须通过 | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | satisfied | 目标回归验证当前 Ready Change 与未改动 legacy 共存时通过 |
| R3 | rvc 与未版本化 legacy 仅允许未改动归档；修改、Active、未知 schema 与删除规避失败 | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | satisfied | Unit 覆盖 rvc/未版本化兼容、legacy 修改/Active、未知 schema、删除和合法归档移动 |
| R4 | main 输出 carrier=changes 且 gated/strict 非零 | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | satisfied | main fresh Change Completion Gate run 33597529998 在 merge commit `c2664f0c` 成功；PR/main CLI 均输出 `carrier=changes` 且 gated/strict 非零 |
| R5 | 保持 required check 身份及 Ruleset 消费者不变 | https://github.com/dingyuwen777/AIMA_UGC/issues/292 | satisfied | Workflow/job 名未变；Ruleset 21909651 于 Ready 前复核仍消费 `Requirement Traceability and Completion Audit`、`CI Gate`、`Compose Golden Path` |
| R6 | canonical 不提供 mixed carrier 兼容，AIMA 不修改 managed Skill 或创建替代 Skill | https://github.com/dingyuwen777/Agent_Skills/issues/158 | satisfied | 方案限定在项目自有 scripts/tests/workflow/docs |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit | required | current/legacy/unknown/delete/rename 与 changed-since/main 两种模式 |
| Contract / Generated | not_applicable | 不修改产品或公共 API Contract |
| Backend/API/PostgreSQL | not_applicable | 不修改后端业务或持久化 |
| Browser Mock Acceptance | not_applicable | 无用户页面行为 |
| Real Full-stack Golden Path | not_applicable | 无产品接线；CI Workflow 自身执行是本任务真实边界 |
| External Provider Probe | not_applicable | 不改变外部 Provider |
| Build / Runtime | required | Python 3.14 CLI、跨 Windows/Linux 路径与 CI 执行 |
| Docs / Governance / CI | required | governance checker、Docs、Workflow Responsibility Audit、Evidence Preservation Mapping、PR/current-head/main-fresh |

# Workflow Responsibility Audit

- 永久责任：顶层当前 Change 的 metadata、状态、需求追溯和完成审计必须被 PR/main 机器门禁检查；legacy 历史不得阻断未改动仓库，也不得被修改或移入 Active。
- 触发：保持 PR opened/synchronize/reopened/edited 与 push main；PR 使用 changed-since，main 使用 require-active-ready。
- required check：保持 `Requirement Traceability and Completion Audit` 名称，不修改 Ruleset required status check。
- 权限：保持 `contents: read` 与 `issues: read`，不新增 write 权限或 Secret。
- 失败可见性：checker 输出路径、原因、carrier、gated、strict、legacy；不得以 exit 0 隐藏问题。

# Evidence Preservation Mapping

| 原责任 | 新 Owner | 证明方式 | 当前状态 |
| --- | --- | --- | --- |
| 当前 schema/frontmatter 严格解析 | installed ready-check validator | adapter 动态加载并调用同一 metadata 解析 | Unit 已通过 |
| Requirement Traceability / Completion Audit | installed ready-check validator | adapter 调用同一文档校验函数 | Unit 已通过 |
| PR changed-since Active Ready | project checker + Completion Gate | Unit Red/Green + PR 真实日志 | PR run 33596440533 已证明 in_progress 失败；final-head run 33596647829 已证明 Ready 成功 |
| main 全 Active Ready 与 Archive done | project checker + Completion Gate | Unit + main fresh 日志 | merge commit `c2664f0c` 的 main fresh run 33597529998 成功；本归档 PR 再验证 archive done |
| legacy 历史兼容与不可变 | project checker | unchanged/modified/active/delete 回归 | Unit 已通过 |
| Branch Protection 消费 | 既有 Ruleset | check 名不变 + Ruleset/PR checks 复核 | Ruleset 21909651 已复核；required status 上下文未变 |

# 实施步骤

- [x] 更新 Issue #292，使范围与 Agent_Skills #158 当前决定一致。
- [x] Red：建立 carrier、状态、legacy、未知 schema 与删除绕过测试；沙箱外目标 pytest 为 `6 failed`，共同失败于项目 checker 尚不存在。
- [x] 首个本地提交后首次 push，并创建早期 PR；逻辑未就绪时禁止 merge。
- [x] Green：实现项目 checker、Workflow/治理静态接线和当前归档兼容修正。
- [x] 同步项目规则和 Blueprint，执行 targeted Docs review。
- [x] 运行目标回归与质量门禁，并取得 Workflow 真实失败证据。
- [x] 重新读取上游，完成 Completion Audit。
- [x] 完成独立 Review、PR current-head CI 与 Workflow 成功证据。
- [x] 获授权后受保护合并并执行 main fresh。
- [ ] 用独立归档 PR 收尾并关闭 Issue。

# 当前新鲜证据

- Red：项目 checker 不存在时，目标 pytest `6 failed`；每个失败均为 `FileNotFoundError` 指向预期生产入口。
- Green：`tests/unit/test_change_completion.py` 与 `tests/unit/test_agent_governance.py` 共 `21 passed`。
- 静态质量：变更集 Ruff format/check 和项目 checker Mypy 均 exit 0。
- 治理/文档/架构/表所有权/Secret 检查均 exit 0；首次沙箱执行只因用户级 uv 缓存拒绝访问而未进入测试，沙箱外相同命令形成上述真实结果。
- PR run 33596440533 在最新 main 基线 `cdb76a26` 上按预期失败，唯一诊断是当前 Change 为 `in_progress`；日志输出 `carrier=changes, gated=14, strict=13, legacy=128`。
- Ready 前重新读取 Issue #292、Agent_Skills #158、Workflow 与 Ruleset 21909651；后者仍要求 `CI Gate`、`Requirement Traceability and Completion Audit`、`Compose Golden Path`，未发生检查身份漂移。
- 实现分支 final head `3a1fb629` 的 PR run 33596647829、Runtime 33596625892 与完整 CI 33596626086 全部成功；两阶段独立 Review 无 findings。
- PR #299 已按用户对该 PR 的明确授权使用管理员权限合并；merge commit 为 `c2664f0c0e5e85506bedf36de6caa0e8a39c3b72`。
- merge commit 的 main fresh Change Completion Gate 33597529998、Runtime Acceptance 33597530035 与完整 CI 33597530173 全部成功；Repository Quality、PostgreSQL Integration、Real Full-stack、Docs/Governance 和 CI Gate 均实际执行并通过。
- 本归档 PR 只把已完成记录从 Active 移入 Archive，不改变产品、治理实现或 required check 身份。

# Completion Audit

- [x] upstream_re_read：Ready 前已重新读取 Issue #292、Agent_Skills #158、Ruleset 21909651、Workflow 与项目实现/测试事实。
- [x] change_coverage：R1–R6 均已映射到实现、目标回归、真实失败日志、main 模式 CLI 或 Ruleset 证据；PR 成功与 main fresh 作为后续交付门禁继续执行。
- [x] reverse_audit：从 Ruleset required status 反查到未改名的 Workflow job，再反查 project checker 的 changed-since/main 两种真实命令；没有丢失消费者。
- [x] unresolved_cleared：无 `not_satisfied` 需求；128 份 legacy 的不可变边界、3 份未版本化记录和合并后 main fresh 均已显式记录。

# 兼容、部署与回滚

不改产品 Contract、Schema、Migration、依赖或部署拓扑。回滚只需恢复原 Workflow/checker/docs；但原行为会重新漏检顶层 Change，因此只能在新门禁存在缺陷且有正式回滚决定时执行。legacy 记录不迁移、不删除，回滚不会产生数据恢复步骤。
