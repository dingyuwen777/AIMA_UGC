---
schema: rvc-change/v1
id: CHG-20260825-docs-skill
title: 新增 Docs 文档审查 Skill
level: L2
status: in_progress
owner: aima
branch: feature/docs-skill
created: 2026-08-25
updated: 2026-08-25
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - documentation-governance
  - testing-governance
affected_paths:
  - AGENTS.md
  - .agents/skills/docs/
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/agents/openai.yaml
  - .agents/skills/coding/tests/test_docs_skill.py
  - changes/active/CHG-20260825-docs-skill/CHANGE.md
contracts: []
data_changes: []
---

# 目标

新增一个通用、轻量的 `docs` Skill，用于技术文档编写、更新和审查。它要保证文档与当前真实实现同步，并让基础较弱的读者能够从“为什么存在、解决什么问题、数据怎么流、代码在哪实现”开始理解技术方案和实现逻辑，而不是靠术语堆砌获得表面专业感。

同时让现有 `coding` Skill 在不丢失、不概括、不改写任何既有规则的前提下建立可靠的双向协作：Coding 先做轻量 Docs Impact；有影响时必须加载 Docs；Docs 如果发现实现缺陷，必须切回 Coding 的完整研发规则后才能修改实现，再由 Docs 做 targeted re-review。

# 成功标准

- [x] `.agents/skills/docs/SKILL.md` 成为独立可直接使用的 Docs Skill，覆盖文档 Review、编写和更新。
- [x] Docs Skill 明确从第一性原理组织技术说明：先解释为什么存在、解决什么问题、输入输出/数据或调用如何流动、当前代码在哪实现，再解释必要术语。
- [x] Docs Skill 要求术语首次出现时用白话解释；最小例子只在能明显降低理解成本时使用；禁止为了显得专业而堆概念。
- [x] Docs Skill 明确代码路径、表名、类名、函数名等只有在帮助理解/定位且不会制造第二套事实时才引用；精确机器事实继续由代码、Contract、Schema/Migration、generated、tests、locks 等维护。
- [x] Docs Skill 不机械让文档追随当前代码；发生冲突时先判断实现缺陷、文档过期、已批准但未实现设计或新的上游决定，再修正确的一方。
- [ ] `AGENTS.md` 明确文档任务和 Coding Docs Impact 的 Docs 加载条件，避免只依赖 Agent metadata。
- [ ] `coding/SKILL.md` 在保留 4.12 原文全部语义的前提下，只追加最小 Docs 硬路由：`not_applicable` 给依据并跳过；有影响必须读取 `.agents/skills/docs/SKILL.md`，由 Docs 决定 targeted/full。
- [ ] Docs 发现 `code_issue_detected` 时，如果同仓存在 `.agents/skills/coding/SKILL.md`，必须先读取并切回 Coding 后才能修改实现；Coding 不可用时只报告实现问题，不由 Docs 越权修代码。
- [x] 常规开发不会因 Docs Skill 变成全仓文档扫描：支持 `not_applicable / targeted / full`，其中 `targeted` 是有影响时默认模式，`full` 也只覆盖完整受影响文档域。
- [x] Blueprint 06 已重新核对；其现有文档门禁、第一性原理和第二套事实约束与新 Docs 机制一致，因此不制造无意义 Blueprint diff。
- [ ] 自动化回归同时保护 Coding 现有关键规则，并验证 Coding → Docs 与 Docs → Coding 两个方向的硬路由存在。

# 范围

- 维护 `.agents/skills/docs/` 主规则、agent metadata 和四份 reference。
- 在 `AGENTS.md` 增加项目级最小 Docs 路由入口。
- 在 `.agents/skills/coding/SKILL.md` 现有 4.12 末尾追加双向协作所需的最小前向路由；不删除、不重写、不搬移现有内容。
- 在 Docs 主规则/协作 reference 中把“返回 Coding”收紧为实际读取 Coding Skill 后再修改实现。
- 在现有 Coding Skill 测试目录维护 Docs / 双向路由回归，直接复用 Change Completion Gate。

# 非目标

- 不总结、精简、重排、拆分、合并、重写或删除 Coding Skill 的任何既有规则。
- 不把 Docs Skill 变成 Markdown linter、固定模板生成器或每次开发都执行的全仓扫描器。
- 不要求任何代码变化都必须产生文档 diff；`not_applicable` 有事实依据即可结束文档分支。
- 不规定所有仓库必须采用 AIMA 的 Blueprint/Appendix/Change 目录结构；项目本地规则仍是 Overlay。
- 不复制完整代码、完整 Schema、完整 API 字段、依赖精确版本等机器事实到文档中。
- 不修改产品代码、HTTP Contract、数据库 Schema/Migration、依赖、Runtime、部署或 CI workflow。
- 不创建 Docs CLI；本任务不需要新的可执行编排器。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 当前已有规则全部继续有效；现有 4.12 全文和“未同步不得 Ready/完成”规则不得被删减、替换或总结。
- Coding 的四维任务路由、L1-L3、Change、Requirement Traceability、Completion Audit、TDD、根因调试、Validation Matrix、Review、Git、安全、时间、日志、注释、协作和交付规则保持不变。
- `.agents/skills/coding/references/`、`coding.py`、`ready_check.py`、CHANGE schema 与现有 CI workflow 不因本任务改变。
- AIMA 当前正式事实优先级和文档分层继续以 `AGENTS.md`、Blueprint 及机器事实为准。

# 关键决策

- Skill 正式名称使用 `docs`，目录为 `.agents/skills/docs/`。
- `docs` 同时支持 Review Only、Review + Fix、Write / Update；是否允许写文件仍由当前任务授权决定。
- Coding 只负责先判断 Docs Impact；没有影响记录 `not_applicable` 依据，有影响则必须读取 Docs。Docs 决定真正需要检查/修改哪些文档以及 `targeted/full`。
- 仅靠 `coding/agents/openai.yaml` 的默认提示不够可靠；AIMA 项目入口、Coding Skill 正文和回归测试都必须包含路由，避免宿主没有消费 agent metadata 时丢失 Docs 调用。
- 为保护 Coding，只允许在现有 4.12 之后追加路由规则；原 4.12 和其他章节逐字保留，不做结构重写。
- Docs 发现实现缺陷后不得自己在 Docs 模式下修代码；同仓 Coding 存在时先读取 Coding Skill 并按它的需求、调试/TDD、验证、Git 和完成门禁执行。Coding 不可用时只报告阻塞。
- Docs Impact 使用三档：`not_applicable`、默认 `targeted`、必要时 `full`；`full` 也只覆盖完整受影响文档域。
- 文档一致性不是“代码永远正确”。先确定正确事实，再决定修实现还是修文档。
- 是否引用代码路径、表名、类名、函数名、接口名、配置项，以“能否帮助理解/定位且不会制造第二套事实”为判断标准。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增名为 `docs` 的独立文档审查 Skill，保证代码和文档同步 | user:current-request | satisfied | `.agents/skills/docs/` 已实现，既有 Green 回归通过 |
| R2 | 文档从第一性原理解释为什么存在、解决什么问题、数据怎么流、代码在哪实现 | user:current-request | satisfied | Docs 主规则和 `02_第一性原理技术写作.md` 已固化 |
| R3 | 面向基础较弱读者，术语白话解释，必要时给最小例子，不堆高大上名词 | user:current-request | satisfied | Docs 固定原则和写作 reference 已固化 |
| R4 | 是否引用代码/表/类等由理解价值与第二套事实风险决定 | user:current-request | satisfied | Docs 固定原则与事实源 reference 已固化 |
| R5 | Coding 能按需调用 Docs，但执行不应变重：无影响跳过、有影响默认 targeted | user:conversation-decision | not_satisfied | 当前只有 Coding agent metadata 明确路由；需要补 AGENTS + Coding Skill 正文硬入口 |
| R6 | 不过分总结 Coding，不丢任何既有内容，不影响 Coding 使用效果 | user:latest-clarification | not_satisfied | 后续只允许在 4.12 末尾追加；完成后用 diff 和原有回归证明无删改 |
| R7 | Docs 发现实现问题时必须可靠返回 Coding，再由 Coding 修复，Docs 复核 | user:latest-clarification | not_satisfied | 当前只写“返回 Coding”，需要收紧为读取 `.agents/skills/coding/SKILL.md` 后才能改实现 |
| R8 | 双向路由不能只依赖某个宿主是否消费 `agents/openai.yaml` | user:current-follow-up | not_satisfied | 将用 AGENTS + 两个 Skill 正文 + CI 回归形成静态多层入口 |
| R9 | 长期开发文档与 Docs 治理机制一致 | docs/blueprint/06_开发约束与分阶段实施.md | satisfied | 已 targeted 复核，现有原则一致，无需修改 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 先扩展回归使当前缺少双向硬路由的状态失败，再补路由使全套 Coding/Docs tests 通过 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/CLI/Schema/序列化格式 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、业务持久化、队列或运行时依赖 |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品工作流；Agent 路由由仓库规则和 Skill 回归约束 |
| 跨组件 Golden Path | not_applicable | 不涉及产品组件接线 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建、包或运行入口 |
| Docs / Governance / Other | required | 复核 AGENTS、Coding 4.12、Docs 协作、Change、PR diff；执行 Skill tests、Ready Check 与 PR 永久门禁 |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户新增的“双向可靠路由”要求、AGENTS、Coding 4.12、Docs 主规则和协作 reference。
- [ ] change_coverage：确认前向和反向路由均不依赖单一 metadata，并保持轻量 targeted 策略。
- [ ] reverse_audit：验证 Coding → Docs → code_issue_detected → Coding → Docs targeted re-review 的完整链路；Coding 不可用时 Docs 不越权修改实现。
- [ ] unresolved_cleared：R5—R8 重新清零后才能回到 `ready_for_review`。

# 两阶段 Review

当前因用户新增了“是否能确保每次正确使用 Docs，包括 Docs 路由回 Coding”的要求，Change 已从 `ready_for_review` 回到 `in_progress`。此前 Review/CI 证据保留为历史过程证据，但不能替代新 HEAD 的双向路由验证。

# 任务

- [x] 实现 Docs 主规则、四份 reference 与 agent metadata。
- [x] 建立原始 Docs Red/Green 回归并通过第一轮永久 CI。
- [x] 复核 Blueprint 06，确认无需无意义修改。
- [ ] 扩展回归，先证明当前缺少 AGENTS/Coding 正文前向硬路由和 Docs→Coding 实际读取门禁。
- [ ] 最小追加 AGENTS、Coding 4.12、Docs 主规则/协作 reference 的双向硬路由。
- [ ] 确认 Coding 原有正文只有追加、没有删除或改写。
- [ ] 重新执行 Skill tests、Ready Check、Completion Audit、两阶段 Review 和 PR 最新 HEAD CI。

# 验证

## 计划

- Red/Green：`python -m unittest discover .agents/skills/coding/tests -v`
- Coding 门禁：`python .agents/skills/coding/scripts/ready_check.py --root . --changed-since <PR-base>`
- Diff Review：核对 Coding 4.12 原文仍完整，新增内容只位于其末尾。
- PR CI：以 PR #237 最新 HEAD 的永久 workflow 为最终证据。

## 已有证据

- 第一轮 Red：HEAD `e75b261e` 的 Change Completion Gate 证明 Docs 缺失会失败。
- 第一轮 Green：HEAD `2ae8b764` Skill tests 22/22 通过。
- 第一轮 Ready HEAD `f573ebcb`：Change Completion Gate、CI、Runtime Acceptance、Full-stack Acceptance 均 success。
- 上述证据在新增双向路由要求后不作为最终 Ready 证据；必须重新取得最新 HEAD 结果。

# 文档影响

- `AGENTS.md`：需要增加项目级 Docs 按需加载/反向 Coding 路由入口。
- `docs/blueprint/06_开发约束与分阶段实施.md`：现有原则已足够，不需要复制双向 Skill 路由细节形成第二套规范。
- 其他产品文档：不涉及产品事实变化，不修改。

# 交付

- Branch：`feature/docs-skill`。
- PR：#237，当前要求变化后继续在同一 PR 开发；完成新门禁前不合并。
- 发布：not_applicable。
