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
  - .agents/skills/docs/
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/tests/test_docs_skill.py
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/active/CHG-20260825-docs-skill/CHANGE.md
contracts: []
data_changes: []
---

# 目标

新增一个通用、轻量的 `docs` Skill，用于技术文档编写、更新和审查。它要保证文档与当前真实实现同步，并让基础较弱的读者能够从“为什么存在、解决什么问题、数据怎么流、代码在哪实现”开始理解技术方案和实现逻辑，而不是靠术语堆砌获得表面专业感。

同时让现有 `coding` Skill 在不丢失、不概括、不改写任何既有规则的前提下，仅增加最小 Docs Impact 路由：没有文档影响时说明依据并跳过；有影响时再读取 `docs` Skill，默认只做针对性审查，只有架构/主数据流/部署等广泛变化才做全量审查。

# 成功标准

- [ ] `.agents/skills/docs/SKILL.md` 成为独立可直接使用的 Docs Skill，覆盖文档 Review、编写和更新。
- [ ] Docs Skill 明确从第一性原理组织技术说明：先解释为什么存在、解决什么问题、输入输出/数据或调用如何流动、当前代码在哪实现，再解释必要术语。
- [ ] Docs Skill 要求术语首次出现时用白话解释；最小例子只在能明显降低理解成本时使用；禁止为了显得专业而堆概念。
- [ ] Docs Skill 明确代码路径、表名、类名、函数名等只有在帮助理解/定位且不会制造第二套事实时才引用；精确机器事实继续由代码、Contract、Schema/Migration、generated、tests、locks 等维护。
- [ ] Docs Skill 不机械让文档追随当前代码；发生冲突时先判断实现缺陷、文档过期、已批准但未实现设计或新的上游决定，再修正确的一方。
- [ ] `coding` 保留现有全部规则语义、顺序、触发条件、例外、失败处理、验证责任、安全/兼容边界，只在现有“同步当前事实和文档”规则处增加轻量 Docs Impact → `docs` 路由。
- [ ] 常规开发不会因 Docs Skill 变成全仓文档扫描：支持 `not_applicable / targeted / full`，其中 `targeted` 是有影响时默认模式。
- [ ] `docs/blueprint/06_开发约束与分阶段实施.md` 与新的长期文档治理流程同步，但不复制 Skill 的全部规则形成第二套规范。
- [ ] 自动化回归能证明 Docs Skill 核心规则存在、Coding 路由生效，并继续保护 Coding 现有关键规则。

# 范围

- 新增 `.agents/skills/docs/`：Skill 主文件、OpenAI agent metadata 和最少充分 reference。
- 在 `.agents/skills/coding/SKILL.md` 的现有文档同步章节追加最小协作路由，不重组其他内容。
- 在现有 Coding Skill 测试目录新增 Docs Skill / 路由回归，以复用当前 Change Completion Gate。
- 对 `docs/blueprint/06_开发约束与分阶段实施.md` 做最小长期治理同步。

# 非目标

- 不总结、精简、重排、拆分、合并、重写或删除 Coding Skill 的任何既有规则。
- 不把 Docs Skill 变成 Markdown linter、固定模板生成器或每次开发都执行的全仓扫描器。
- 不规定所有仓库必须采用 AIMA 的 Blueprint/Appendix/Change 目录结构；项目本地规则仍是 Overlay。
- 不复制完整代码、完整 Schema、完整 API 字段、依赖精确版本等机器事实到文档中。
- 不修改产品代码、HTTP Contract、数据库 Schema/Migration、依赖、Runtime、部署或 CI workflow。
- 不创建 Docs CLI；当前需求不需要额外脚本或依赖。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 当前已有规则全部继续有效；新增 Docs 路由只能叠加，不能替代现有 `4.12 同步当前事实和文档` 的任何内容。
- Coding 的四维任务路由、L1-L3、Change、Requirement Traceability、Completion Audit、TDD、根因调试、Validation Matrix、Review、Git、安全、时间、日志、注释、协作和交付规则保持不变。
- `.agents/skills/coding/references/`、`coding.py`、`ready_check.py`、CHANGE schema 与现有 CI workflow 不因本任务改变。
- AIMA 当前正式事实优先级和文档分层继续以 `AGENTS.md`、Blueprint 及机器事实为准。

# 关键决策

- Skill 正式名称使用 `docs`，目录为 `.agents/skills/docs/`。
- `docs` 同时支持 Review Only、Review + Fix、Write / Update；是否允许写文件仍由当前任务授权决定，Review 默认不等于授权修改。
- Coding 只负责 Docs Impact 判断与路由，不复制 Docs 的第一性原理写作和审查规则；Docs 负责决定真正需要检查/修改哪些文档。
- Docs Impact 使用三档：`not_applicable`（无事实影响，给出依据）、`targeted`（默认，只读取受影响事实源和文档）、`full`（仅长期架构、主数据流、广泛部署/运行边界等确实广泛变化时使用）。
- 文档一致性不是“代码永远正确”。Docs 必须先确定当前正确事实，再决定修代码、修文档、保留待实现设计或提请上游决策。
- 是否引用代码路径、表名、类名、函数名、接口名、配置项，以“能否帮助理解/定位且不会制造第二套事实”为判断标准。
- 历史 Change/Git/Release 负责“为什么变”；当前 README/Blueprint/Guide/Appendix 负责“现在为什么这样、怎么工作”；精确机器事实不在 Markdown 里完整复制。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增名为 `docs` 的独立文档审查 Skill，保证代码和文档同步 | user:current-request | not_satisfied | 尚未实现 |
| R2 | 文档从第一性原理解释为什么存在、解决什么问题、数据怎么流、代码在哪实现 | user:current-request | not_satisfied | 尚未实现 |
| R3 | 面向基础较弱读者，术语白话解释，必要时给最小例子，不堆高大上名词 | user:current-request | not_satisfied | 尚未实现 |
| R4 | 是否引用代码/表/类等由理解价值与第二套事实风险决定 | user:current-request | not_satisfied | 尚未实现 |
| R5 | Coding 能按需调用 Docs，但执行不应变重：无影响跳过、有影响默认 targeted | user:conversation-decision | not_satisfied | 尚未实现 |
| R6 | 不过分总结 Coding，不丢任何既有内容，不影响 Coding 使用效果 | user:latest-clarification | not_satisfied | 尚未实现 |
| R7 | 长期开发文档与新的 Docs 治理机制一致 | docs/blueprint/06_开发约束与分阶段实施.md | not_satisfied | 尚未同步 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 新增纯 Python 回归读取 Skill/Blueprint，验证 Docs 核心原则、三档路由、Coding 最小接线和现有关键规则仍存在 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/CLI/Schema/序列化格式；Docs Skill 本身通过 Markdown/YAML 规则文件暴露，不新增机器 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、文件业务持久化、队列或运行时依赖 |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品用户工作流；Agent 研发治理由 Skill 回归和人工语义 Review 验证 |
| 跨组件 Golden Path | not_applicable | 不涉及产品组件真实接线 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider 当前事实 |
| Build / Package / Runtime | not_applicable | 不修改构建、打包、镜像或运行入口 |
| Docs / Governance / Other | required | 对照用户当前要求、Coding 4.12、Blueprint 06 做事实/内容守恒 Review，并执行 Ready Check 与 PR Change Gate（进入 Ready 后） |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户当前要求、`AGENTS.md`、Coding Skill 现有文档同步规则和 Blueprint 06。
- [ ] change_coverage：确认 Docs Skill 覆盖同步、第一性原理、白话术语、最小例子、第二套事实防护和轻量路由，且没有把本 Change 当需求全集。
- [ ] reverse_audit：从 Coding → Docs、直接 Docs 任务 → Docs、Docs 发现代码问题 → Coding 三个方向复核边界；确认不产生无限循环或全仓强制扫描。
- [ ] unresolved_cleared：所有 `not_satisfied` 清零，required 验证均有新鲜证据。

# 任务

- [x] 恢复当前 AGENTS、Coding Skill、Blueprint 06、Change/CI 事实。
- [x] 确认任务为 L2，当前无 Active Change 冲突，仓库无 `openspec/`。
- [ ] 先新增会因 Docs Skill 缺失而失败的回归测试。
- [ ] 实现 `.agents/skills/docs/`。
- [ ] 对 Coding 4.12 做最小、内容守恒的 Docs 路由接线。
- [ ] 最小同步 Blueprint 06。
- [ ] 执行 Skill 回归与 Ready Check。
- [ ] 完成 Requirement Traceability、Completion Audit 和两阶段 Review。

# 验证

## 计划

- Red/Green：`python -m unittest discover .agents/skills/coding/tests -v`
- Coding 门禁：`python .agents/skills/coding/scripts/ready_check.py --root . --require-active-ready`（Change 进入 Ready 后）
- Diff Review：确认 Coding `SKILL.md` 只有 Docs 路由增量，没有删除/改写原规则。
- PR CI：如进入 PR 交付，再以 PR 最新 HEAD 的 Change Completion Gate/相关 CI 作为新鲜证据。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/blueprint/06_开发约束与分阶段实施.md`：需要最小同步新的 Docs Impact → Docs Skill 长期流程和第一性原理写作要求。
- 其他产品 Blueprint/Appendix/README：不涉及产品架构、接口或运行行为，不需要修改。

# 交付

- Commit：待实现。
- PR：未创建。
- 发布：不适用。
