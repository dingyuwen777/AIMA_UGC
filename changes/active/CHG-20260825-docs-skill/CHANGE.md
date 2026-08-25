---
schema: rvc-change/v1
id: CHG-20260825-docs-skill
title: 新增 Docs 文档审查 Skill
level: L2
status: ready_for_review
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
  - .agents/skills/coding/agents/openai.yaml
  - .agents/skills/coding/tests/test_docs_skill.py
  - changes/active/CHG-20260825-docs-skill/CHANGE.md
contracts: []
data_changes: []
---

# 目标

新增一个通用、轻量的 `docs` Skill，用于技术文档编写、更新和审查。它要保证文档与当前真实实现同步，并让基础较弱的读者能够从“为什么存在、解决什么问题、数据怎么流、代码在哪实现”开始理解技术方案和实现逻辑，而不是靠术语堆砌获得表面专业感。

同时让现有 `coding` Skill 在不丢失、不概括、不改写任何既有规则的前提下，以最小方式增加 Docs Impact 路由：没有文档影响时说明依据并跳过；有影响时再读取 `docs` Skill，默认只做针对性审查，只有架构、主数据流、部署等广泛变化才做完整受影响域审查。

# 成功标准

- [x] `.agents/skills/docs/SKILL.md` 成为独立可直接使用的 Docs Skill，覆盖文档 Review、编写和更新。
- [x] Docs Skill 明确从第一性原理组织技术说明：先解释为什么存在、解决什么问题、输入输出/数据或调用如何流动、当前代码在哪实现，再解释必要术语。
- [x] Docs Skill 要求术语首次出现时用白话解释；最小例子只在能明显降低理解成本时使用；禁止为了显得专业而堆概念。
- [x] Docs Skill 明确代码路径、表名、类名、函数名等只有在帮助理解/定位且不会制造第二套事实时才引用；精确机器事实继续由代码、Contract、Schema/Migration、generated、tests、locks 等维护。
- [x] Docs Skill 不机械让文档追随当前代码；发生冲突时先判断实现缺陷、文档过期、已批准但未实现设计或新的上游决定，再修正确的一方。
- [x] `coding/SKILL.md` 正文零改动；现有全部规则语义、顺序、触发条件、例外、失败处理、验证责任、安全/兼容边界保持原样，只在小型 `coding/agents/openai.yaml` 默认提示中增加 Docs Impact → `docs` 路由。
- [x] 常规开发不会因 Docs Skill 变成全仓文档扫描：支持 `not_applicable / targeted / full`，其中 `targeted` 是有影响时默认模式，`full` 也只覆盖完整受影响文档域。
- [x] `docs/blueprint/06_开发约束与分阶段实施.md` 已重新核对；其现有“文档是交付门禁”“不是每次改代码都全部重写”“正式文档写作标准”“不复制第二套 Schema/Contract”与新 Docs 机制一致，因此不制造无意义 Blueprint diff。
- [x] 自动化回归能证明 Docs Skill 核心规则存在、Coding 路由生效，并继续保护 Coding 现有关键规则。

# 范围

- 新增 `.agents/skills/docs/`：Skill 主文件、OpenAI agent metadata 和四份最少充分 reference。
- 保持 `.agents/skills/coding/SKILL.md` 原样，只在 `.agents/skills/coding/agents/openai.yaml` 增加轻量 Docs Impact 路由。
- 在现有 Coding Skill 测试目录新增 Docs Skill / 路由回归，以直接复用当前 Change Completion Gate。
- 复核 Blueprint 06 的长期文档治理语义；已一致时记录无需修改的依据。

# 非目标

- 不总结、精简、重排、拆分、合并、重写或删除 Coding Skill 的任何既有规则。
- 不把 Docs Skill 变成 Markdown linter、固定模板生成器或每次开发都执行的全仓扫描器。
- 不规定所有仓库必须采用 AIMA 的 Blueprint/Appendix/Change 目录结构；项目本地规则仍是 Overlay。
- 不复制完整代码、完整 Schema、完整 API 字段、依赖精确版本等机器事实到文档中。
- 不修改产品代码、HTTP Contract、数据库 Schema/Migration、依赖、Runtime、部署或 CI workflow。
- 不创建 Docs CLI；当前需求没有独立脚本或依赖必要性。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 当前已有规则全部继续有效；现有 `4.12 同步当前事实和文档` 及“未同步不得 Ready/完成”规则不被替代。
- Coding 的四维任务路由、L1-L3、Change、Requirement Traceability、Completion Audit、TDD、根因调试、Validation Matrix、Review、Git、安全、时间、日志、注释、协作和交付规则保持不变。
- `.agents/skills/coding/references/`、`coding.py`、`ready_check.py`、CHANGE schema 与现有 CI workflow 不因本任务改变。
- AIMA 当前正式事实优先级和文档分层继续以 `AGENTS.md`、Blueprint 及机器事实为准。

# 关键决策

- Skill 正式名称使用 `docs`，目录为 `.agents/skills/docs/`。
- `docs` 同时支持 Review Only、Review + Fix、Write / Update；是否允许写文件仍由当前任务授权决定，Review 默认不等于授权修改。
- Coding 只负责 Docs Impact 判断与路由，不复制 Docs 的第一性原理写作和审查规则；Docs 负责决定真正需要检查/修改哪些文档。
- 为最大限度保护 Coding，本次不改 `coding/SKILL.md` 正文；它原有 `4.12` 已完整规定文档同步和 Ready 门禁，只在 `coding/agents/openai.yaml` 的默认执行提示中追加“Docs Impact → 读取 `.agents/skills/docs/SKILL.md`”。
- Docs Impact 使用三档：`not_applicable`（无事实影响，给出依据）、`targeted`（默认，只读取受影响事实源和文档）、`full`（仅长期架构、主数据流、广泛部署/运行边界等确实广泛变化时使用）。
- 文档一致性不是“代码永远正确”。Docs 必须先确定当前正确事实，再决定修代码、修文档、保留待实现设计或提请上游决策。
- 是否引用代码路径、表名、类名、函数名、接口名、配置项，以“能否帮助理解/定位且不会制造第二套事实”为判断标准。
- 历史 Change/Git/Release 负责“为什么变”；当前 README/Blueprint/Guide/Appendix 负责“现在为什么这样、怎么工作”；精确机器事实不在 Markdown 里完整复制。
- Blueprint 06 当前已经表达相同长期原则；按 Docs 自身“已正确则不改”的规则，不为体现同步而产生第二份或无意义 diff。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增名为 `docs` 的独立文档审查 Skill，保证代码和文档同步 | user:current-request | satisfied | `.agents/skills/docs/SKILL.md`、`agents/openai.yaml` 和 4 个 references 已实现；Docs 核心回归在 Green HEAD `2ae8b764` 通过 |
| R2 | 文档从第一性原理解释为什么存在、解决什么问题、数据怎么流、代码在哪实现 | user:current-request | satisfied | Docs 主规则第 1/4 节与 `02_第一性原理技术写作.md` 固化问题→流动→实现→术语顺序；自动回归检查核心文本 |
| R3 | 面向基础较弱读者，术语白话解释，必要时给最小例子，不堆高大上名词 | user:current-request | satisfied | Docs 固定原则 4/5、写作 reference 的“术语后置”“最小例子”与反例/正例均已固化；回归通过 |
| R4 | 是否引用代码/表/类等由理解价值与第二套事实风险决定 | user:current-request | satisfied | Docs 固定原则 6/7 与 `01_事实源与同步判断.md` 明确“帮助理解/定位 + 不制造第二套事实”双判断 |
| R5 | Coding 能按需调用 Docs，但执行不应变重：无影响跳过、有影响默认 targeted | user:conversation-decision | satisfied | `coding/agents/openai.yaml` 增加轻量 Docs Impact 路由；`04_与Coding协作.md` 固化 not_applicable/targeted/full 与 candidate docs 只是导航 |
| R6 | 不过分总结 Coding，不丢任何既有内容，不影响 Coding 使用效果 | user:latest-clarification | satisfied | PR changed files 不含 `.agents/skills/coding/SKILL.md`；Coding 只修改 1 行 agent default_prompt；原有 Coding 回归与新增保护断言在 Green HEAD 共 22/22 通过 |
| R7 | 长期开发文档与新的 Docs 治理机制一致 | docs/blueprint/06_开发约束与分阶段实施.md | satisfied | 重新读取 Blueprint 06 第 16—18 节，已有“文档门禁/不全量重写/为什么需要/不复制第二套 Schema/Contract”原则；无需修改即可保持一致 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Red HEAD `e75b261e` 的 Change Gate `32862993933` 在 Docs 尚未实现时 Skill 测试失败；Green HEAD `2ae8b764` 的 Change Gate `32863754209` 中 `python -m unittest discover .agents/skills/coding/tests -v` 22/22 通过 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/CLI/Schema/序列化格式；Docs Skill 通过 Markdown/YAML 规则暴露，不新增产品机器 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、文件业务持久化、队列或运行时依赖 |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品用户工作流；Agent 研发治理由 Skill 回归和语义 Review 验证 |
| 跨组件 Golden Path | not_applicable | 不涉及产品组件真实接线 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider 当前事实 |
| Build / Package / Runtime | not_applicable | 不修改构建、打包、镜像或运行入口；Green HEAD Runtime Acceptance `32863754212` success 作为无回归补充证据 |
| Docs / Governance / Other | required | 对照用户要求、Coding 4.12、Blueprint 06 和 PR diff 完成语义/内容守恒 Review；Green HEAD 的 Skill 测试全部通过，Ready Check 当时仅因 Change 仍为 `in_progress` 被门禁阻止，现已按审计结果进入 `ready_for_review` |

# Completion Audit

- [x] upstream_re_read：重新读取用户当前要求与“不要过分总结 Coding”最新补充，并重新读取当前 `AGENTS.md`、Coding Skill 4.12、Coding agent metadata、Blueprint 06 第 16—18 节。
- [x] change_coverage：Docs Skill 已覆盖同步、第一性原理、白话术语、最小例子、第二套事实防护、冲突归因和轻量三档路由；没有把当前 Change 当需求全集。
- [x] reverse_audit：从 Coding → Docs、直接 Docs 任务 → Docs、Docs 发现代码问题 → Coding 三个方向复核；默认 targeted，code issue 最多一次明确回交后 targeted re-review，避免无限循环和无边界 full review。
- [x] unresolved_cleared：R1—R7 全部 satisfied；required 验证已有 Red/Green、PR diff、Blueprint 复核与 Runtime 新鲜证据。

# 两阶段 Review

## Review A1：上游要求 → Change

重新从用户当前要求独立核对：

- 必须新增 `docs` Skill；
- 文档必须从第一性原理解释为什么、问题、流动和代码实现；
- 面向基础较弱读者，术语白话、必要时用最小例子；
- 不堆概念；
- 代码/表/类等引用由理解价值和第二套事实风险决定；
- Coding 必须能按需调用 Docs，但流程不能变成每次全量文档审查；
- 不能为了接入 Docs 总结、删减或削弱 Coding。

R1—R7 已覆盖这些要求，没有遗漏或静默延期。

## Review A2：Change → 实现 / 测试 / 文档

- `docs/SKILL.md`：主入口、固定原则、三档 Docs Impact、三种工作模式、第一性原理结构、六维 Review、Coding 协作和完成检查完整。
- `docs/references/01`：事实源、实现/设计/历史分离、代码并非永远正确、第二套事实防护和三档影响判断完整。
- `docs/references/02`：先讲问题、真实流动、术语后置、最小例子、代码定位、不同文档读者任务和历史分离完整。
- `docs/references/03`：Review Only / Review + Fix / Write / Update、targeted/full 读取范围和实际验证边界完整。
- `docs/references/04`：Coding 轻量 Docs Impact、candidate docs 不是必改清单、code issue 返回 Coding、targeted re-review 和防循环完整。
- `coding/SKILL.md`：PR diff 中零改动；现有 4.12 和其余规则保持原样。
- `coding/agents/openai.yaml`：只在原 default_prompt 中追加 Docs Impact 路由，其余既有默认要求保留。
- Blueprint 06：现有规则已匹配，不为了“同步”制造无意义修改。
- 自动化：Red 能失败；Green 22/22 通过；原 Coding migration/readiness/development-guidance 测试继续通过。

未发现需要阻止进入评审的严重或重要问题。

# 任务

- [x] 恢复当前 AGENTS、Coding Skill、Blueprint 06、Change/CI 事实。
- [x] 确认任务为 L2，开始时无 Active Change 冲突，仓库无 `openspec/`。
- [x] 先新增会因 Docs Skill 缺失而失败的回归测试并取得 Red CI 证据。
- [x] 实现 `.agents/skills/docs/`。
- [x] 以不改 Coding Skill 正文的方式增加轻量 Docs Impact 路由。
- [x] 重新核对 Blueprint 06；确认已有长期规则一致，因此无需产生文档 diff。
- [x] 执行 Skill Green 回归并取得 GitHub Actions 新鲜证据。
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段 Review。

# 验证

## 计划

- Red/Green：`python -m unittest discover .agents/skills/coding/tests -v`
- Coding 门禁：`python .agents/skills/coding/scripts/ready_check.py --root . --changed-since <PR-base>`
- Diff Review：确认 `.agents/skills/coding/SKILL.md` 不在 diff；Coding agent metadata 仅追加 Docs 路由。
- PR CI：以 PR #237 最新 HEAD 的 Change Completion Gate 和相关永久 workflow 作为最终集成证据。

## 新鲜证据

- Red：HEAD `e75b261e`，Change Completion Gate run `32862993933` 的 `Run Coding completion-gate tests` 失败，证明 Docs 缺失能被门禁捕获。
- Green：HEAD `2ae8b764`，Change Completion Gate run `32863754209` 的 Skill tests 22/22 通过；同一次 Ready Check 唯一问题是 Change 当时仍为 `in_progress`，没有其他结构/语义占位错误。
- Runtime：HEAD `2ae8b764` 的 Runtime Acceptance run `32863754212` success。
- Diff：`main 51eb5973 → 2ae8b764` 只有 9 个变更文件；`.agents/skills/coding/SKILL.md` 不在变更列表，Coding agent metadata 为 1 行替换式增量。

# 文档影响

- `docs/blueprint/06_开发约束与分阶段实施.md`：实际 targeted 复核后判定无需修改。它已经说明文档是交付门禁、不是每次代码变化都全量重写、正式文档要回答为什么/调用链/代码位置，并禁止复制精确 Schema/Contract 形成第二套文档。
- 其他产品 Blueprint/Appendix/README：本任务不改变产品架构、接口、数据、部署或用户行为，没有文档事实变化，不修改。

# 交付

- Branch：`feature/docs-skill`。
- PR：#237，Draft；当前 Change 已进入 `ready_for_review`，由最新 HEAD 重新执行门禁。
- 发布：not_applicable。
