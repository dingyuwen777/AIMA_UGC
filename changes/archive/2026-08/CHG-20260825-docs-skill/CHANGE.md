---
schema: rvc-change/v1
id: CHG-20260825-docs-skill
title: 新增 Docs 文档审查 Skill
level: L2
status: done
owner: aima
branch: feature/docs-skill
created: 2026-08-25
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - documentation-governance
  - testing-governance
affected_paths:
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

同时让现有 `coding` Skill 在不丢失、不概括、不改写任何既有规则的前提下建立可靠双向协作：Coding 先做轻量 Docs Impact；有影响时必须加载 Docs；Docs 如果发现实现缺陷，必须切回 Coding 的完整研发规则后才能修改实现，再由 Docs 做 targeted re-review。

# 成功标准

- [x] `.agents/skills/docs/SKILL.md` 成为独立可直接使用的 Docs Skill，覆盖 Review Only、Review + Fix、Write / Update。
- [x] Docs 从第一性原理组织技术说明：先解释为什么存在、解决什么问题、输入输出/数据或调用如何流动、当前代码在哪实现，再解释必要术语。
- [x] 术语首次出现时用白话解释；最小例子只在能明显降低理解成本时使用；不为了显得专业而堆概念。
- [x] 代码路径、表名、类名、函数名等只有在帮助理解/定位且不会制造第二套事实时才引用；机器事实继续由代码、Contract、Schema/Migration、generated、tests、locks 等维护。
- [x] Docs 不机械让文档追随当前代码；发生冲突时先判断实现缺陷、文档过期、已批准但未实现设计或新的上游决定，再修正确的一方。
- [x] `coding/SKILL.md` 保留全部原规则，只在现有 4.12 末尾追加最小 Docs 硬路由：`not_applicable` 给依据并跳过；有影响或任务本身是技术文档 Review/编写/更新时必须读取 `.agents/skills/docs/SKILL.md`，由 Docs 决定 targeted/full。
- [x] Docs 发现 `code_issue_detected` 时，如果同仓存在 `.agents/skills/coding/SKILL.md`，任何实现修改前必须读取并切回 Coding；Coding 不可用或无代码授权时只报告，不由 Docs 越权改实现。
- [x] 常规开发不会因 Docs Skill 变成全仓文档扫描：支持 `not_applicable / targeted / full`，有影响时默认 `targeted`，`full` 也只覆盖完整受影响文档域。
- [x] Blueprint 06 已 targeted 复核；现有“文档是交付门禁”“不是每次代码变化都全量重写”“正式文档写作标准”“不复制第二套 Schema/Contract”已经与 Docs 机制一致，因此不制造无意义 Blueprint diff。
- [x] 自动化回归同时保护 Coding 现有关键规则，并验证 Coding → Docs 与 Docs → Coding 两个方向的硬路由存在。

# 范围

- 新增并维护 `.agents/skills/docs/` 主规则、agent metadata 与四份最少充分 reference。
- 在 `.agents/skills/coding/SKILL.md` 现有 4.12 末尾追加 Docs 按需硬路由；不删除、不重排、不概括原有内容。
- 对齐 `.agents/skills/coding/agents/openai.yaml` 的额外提示，但不把 metadata 当唯一调用入口。
- 在现有 Coding Skill 测试目录维护 Docs 核心原则、双向路由和 Coding 内容守恒回归，直接复用 Change Completion Gate。

# 非目标

- 不总结、精简、重排、拆分、合并、重写或删除 Coding Skill 的任何既有规则。
- 不把 Docs Skill 变成 Markdown linter、固定模板生成器或每次开发都执行的全仓扫描器。
- 不要求任何代码变化都必须产生文档 diff；`not_applicable` 有事实依据即可结束文档分支。
- 不规定所有仓库必须采用 AIMA 的 Blueprint/Appendix/Change 目录结构；项目本地规则仍是 Overlay。
- 不复制完整代码、完整 Schema、完整 API 字段、依赖精确版本等机器事实到文档中。
- 不修改产品代码、HTTP Contract、数据库 Schema/Migration、依赖、Runtime、部署或 CI workflow。
- 不创建 Docs CLI；本任务不需要新的可执行编排器。

# 必须保持不变

- `.agents/skills/coding/SKILL.md` 原有 4.12 全文和其他所有规则、触发条件、例外、失败处理、验证责任、安全/兼容边界保持原样；Docs 仅追加新规则。
- Coding 的四维任务路由、L1-L3、Change、Requirement Traceability、Completion Audit、TDD、根因调试、Validation Matrix、Review、Git、安全、时间、日志、注释、协作和交付规则保持不变。
- `.agents/skills/coding/references/`、`coding.py`、`ready_check.py`、CHANGE schema 与现有 CI workflow 不因本任务改变。
- AIMA 当前正式事实优先级和文档分层继续以 `AGENTS.md`、Blueprint 及机器事实为准。

# 关键决策

- Skill 正式名称使用 `docs`，目录为 `.agents/skills/docs/`。
- `docs` 同时支持 Review Only、Review + Fix、Write / Update；Review 默认不代表修改授权。
- Coding 只负责 Docs Impact 判断和前向路由：无影响记录 `not_applicable`，有影响则必须读取 Docs；Docs 负责选择真正相关文档和 `targeted/full`。
- AIMA 根 `AGENTS.md` 已强制所有研发任务先读取 Coding，因此不再在 AGENTS 复制第二套 Docs 路由；可靠链路是 `AGENTS → Coding 4.12 → Docs`。
- 仅靠 `coding/agents/openai.yaml` 不够；正式前向路由写入 Coding Skill 正文。Agent metadata 只是额外提示。
- 为保护 Coding，只在现有 4.12 末尾追加子节；PR patch 已证明原文没有删除或近似改写。一次人工回写曾把“强制其他序列化形式”误写为“强制其他格式”，已经在 Ready 前恢复原文，并新增回归阻止类似漂移。
- Docs 发现实现缺陷后不得自己在 Docs 模式下修代码；同仓 Coding 存在时先读取 Coding Skill 并按完整研发门禁执行，之后 Docs 只做 targeted re-review。
- Docs Impact 使用 `not_applicable / targeted / full`；`full` 表示完整覆盖受影响文档域，不等于全仓扫描。
- 文档一致性不是“代码永远正确”。先确定正确事实，再决定修实现还是修文档。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增名为 `docs` 的独立文档审查 Skill，保证代码和文档同步 | user:current-request | satisfied | `.agents/skills/docs/SKILL.md`、agent metadata 和 4 个 references 已实现 |
| R2 | 文档从第一性原理解释为什么存在、解决什么问题、数据怎么流、代码在哪实现 | user:current-request | satisfied | Docs 主规则与 `02_第一性原理技术写作.md` 固化问题→流动→实现→术语顺序 |
| R3 | 面向基础较弱读者，术语白话解释，必要时给最小例子，不堆高大上名词 | user:current-request | satisfied | Docs 固定原则 4/5 与写作 reference 已固化，回归覆盖核心文本 |
| R4 | 是否引用代码/表/类等由理解价值与第二套事实风险决定 | user:current-request | satisfied | Docs 固定原则 6/7 与事实源 reference 明确双判断 |
| R5 | Coding 能按需调用 Docs，但执行不应变重：无影响跳过、有影响默认 targeted | user:conversation-decision | satisfied | Coding 4.12 新增 `Docs Impact` 硬路由；无影响不加载 Docs，有影响必须读取 Docs，Docs 默认 targeted |
| R6 | 不过分总结 Coding，不丢任何既有内容，不影响 Coding 使用效果 | user:latest-clarification | satisfied | PR Coding patch 只有 4.12 末尾新增子节；原规则近似改写已恢复，内容守恒回归锁定“强制其他序列化形式”等既有规则 |
| R7 | Docs 发现实现问题时必须可靠返回 Coding，再由 Coding 修复，Docs 复核 | user:latest-clarification | satisfied | Docs `6.1 code_issue_detected 反向硬路由`、协作 reference 与 agent metadata 均要求任何实现修改前读取 `.agents/skills/coding/SKILL.md`，之后 targeted re-review |
| R8 | 双向路由不能只依赖某个宿主是否消费 `agents/openai.yaml` | user:current-follow-up | satisfied | 前向规则位于 Coding Skill 正文；反向规则位于 Docs Skill 正文；metadata 仅额外提示；CI 回归同时验证两端 |
| R9 | 长期开发文档与 Docs 治理机制一致 | docs/blueprint/06_开发约束与分阶段实施.md | satisfied | targeted 复核确认 Blueprint 06 已符合，不需要复制 Skill 路由形成第二套规范 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 第二轮 Red HEAD `58a8e604` 的 Change Gate `32865678112` 在双向硬路由尚未实现时 Skill tests 失败；Green HEAD `7f4b9aeb` 的 Skill tests 23/23 通过；Ready HEAD `07bf67a2` 的 Change Completion Gate `32866954840` 中 Skill tests 与 PR Ready Check 均 success |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/CLI/Schema/序列化格式 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、业务持久化、队列或运行时依赖 |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品工作流；Agent 路由由仓库规则、Skill 正文和 CI 回归约束 |
| 跨组件 Golden Path | not_applicable | 不涉及产品组件接线 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改构建、包或运行入口；`main` 合并提交 `aa6159f4` 的 Runtime Acceptance `32870375575` 与 Full-stack Acceptance `32870375683` 均 success，作为无回归补充证据 |
| Docs / Governance / Other | required | PR #237 已正常合并为 `main` 提交 `aa6159f408e70548c60039141c6846d0f6d3dfb5`；main push 的 Change Completion Gate `32870375661`、CI `32870375696`、Runtime Acceptance `32870375575`、Full-stack Acceptance `32870375683` 均 success；CI 内 Repository Quality、PostgreSQL Integration、Secret/docs gate、Build、Frontend unit/build/Browser Mock 与 CI Gate 全部成功 |

# Completion Audit

- [x] upstream_re_read：重新读取用户“每次正确使用 Docs，包括 Docs 路由回 Coding”的新增要求，并重新读取当前 AGENTS、Coding 4.12、Coding metadata、Docs 主规则、Docs metadata 和协作 reference。
- [x] change_coverage：前向路由不再只靠 metadata；Coding 正文明确 not_applicable/必须读取 Docs；反向路由明确 code_issue_detected 后必须读取 Coding 才能改实现；保持默认 targeted，不引入全仓扫描。
- [x] reverse_audit：链路为 `AGENTS → Coding → Docs → code_issue_detected → Coding → Docs targeted re-review`。Coding 不可用或无代码授权时 Docs 停止实现修改；第二次复核若范围扩大则回到上游决策，不无限循环。
- [x] unresolved_cleared：R1—R9 全部 satisfied；第二轮 Red/Green、Coding patch 内容守恒检查、双向规则复核和 main 集成证据均已闭环。

# 两阶段 Review

## Review A1：上游要求 → Change

重新独立核对用户全部要求：独立 Docs Skill、第一性原理、基础读者可理解、术语白话、最小例子、第二套事实防护、Coding 按需调用且不变重、不损伤 Coding、Docs 能可靠回到 Coding。R1—R9 全部覆盖，没有静默延期。

## Review A2：Change → 实现 / 测试 / 文档

- Coding 4.12：只新增 Docs Skill 按需路由；最终 patch 没有修改原有规则。
- Coding metadata：与正文一致，覆盖技术文档任务、变化后的 Docs Impact 和 code_issue_detected 回交。
- Docs 主规则：新增 `6.1 code_issue_detected 反向硬路由`，Coding 不可用/无授权时明确禁止改实现。
- Docs 协作 reference：同样固定真实 Coding Skill 路径、必须读取条件、targeted re-review 和防循环边界。
- Docs metadata：明确反向切回 Coding，不再只是抽象“return to Coding”。
- 测试：第二轮 Red 能失败；Green/Ready 回归通过；同时继续保护 Coding 原有内容，并专门锁定曾被误改的原始日志规则文本和 Docs 缺失时的原流程回退。
- Blueprint 06：已有长期原则足够，不复制具体 Skill 协作协议形成第二套规范。

未发现需要阻止进入评审的严重或重要问题。

# 任务

- [x] 实现 Docs 主规则、四份 reference 与 agent metadata。
- [x] 建立第一轮 Docs Red/Green 和永久 CI。
- [x] 根据用户新增要求把 Change 从 Ready 返回 in_progress。
- [x] 扩展回归并取得第二轮 Red，证明只靠 metadata 的路由不足。
- [x] 在 Coding 4.12 末尾追加前向硬路由；未改写其他规则。
- [x] 在 Docs 主规则、协作 reference、metadata 中实现 code_issue_detected → Coding 反向硬路由。
- [x] 增强 Coding 内容守恒回归，并恢复人工回写产生的唯一近似文字变化。
- [x] 完成 Requirement Traceability、Completion Audit 和两阶段 Review。
- [x] 取得 Skill tests + Ready Check + 永久 CI 全绿证据。
- [x] PR #237 正常合并到 main，并取得 main push 永久 CI 全绿证据。

# 验证

## 计划

- `python -m unittest discover .agents/skills/coding/tests -v`
- `python .agents/skills/coding/scripts/ready_check.py --root . --changed-since <PR-base>`
- PR patch：Coding 除 4.12 追加外无其他修改。
- PR CI：Change Completion Gate、CI、Runtime Acceptance、Full-stack Acceptance。
- main push：再次确认同四个永久 workflow。

## 新鲜证据

- 第一轮 Docs Red/Green 和 Ready CI 已完成，作为基础实现历史过程证据。
- 第二轮 Red：HEAD `58a8e604`，Change Completion Gate `32865678112` 的 Skill tests 失败，证明双向硬路由缺失被回归捕获。
- 第二轮 Green：HEAD `7f4b9aeb`，Change Completion Gate `32866557360` 的 Skill tests 23/23 通过；当时 Ready Check 唯一失败为 Change 仍是 `in_progress`。
- Ready 候选 HEAD `07bf67a2`：Change Completion Gate `32866954840`、CI `32866954584`、Runtime Acceptance `32866954535`、Full-stack Acceptance `32866954383` 全部 success。
- 证据提交 `90976d31`：Change Completion Gate `32867814870` success，Skill tests 与 PR Ready Check 均通过；CI `32867814925` success，其中 PostgreSQL Integration、Repository Quality、Secret/docs gate、Build、Frontend unit/build/Browser Mock 和 CI Gate 全部 success；Runtime Acceptance `32867814973` success；Full-stack Acceptance `32867815281` success。
- PR 最终 HEAD `9fd66441`：Change Completion Gate `32869096582`、CI `32869094648`、Runtime Acceptance `32869094297`、Full-stack Acceptance `32869094284` 全部 success。
- main 合并提交 `aa6159f408e70548c60039141c6846d0f6d3dfb5`：Change Completion Gate `32870375661`、CI `32870375696`、Runtime Acceptance `32870375575`、Full-stack Acceptance `32870375683` 全部 success。
- Coding patch：PR 对 `.agents/skills/coding/SKILL.md` 的 diff 只有 4.12 末尾新增 Docs 路由；原日志规则已恢复为“强制其他序列化形式”。

# 文档影响

- `docs/blueprint/06_开发约束与分阶段实施.md`：实际 targeted 复核后无需修改；其现有文档交付门禁、第一性原理写作和第二套事实防护已经承载长期原则。
- `AGENTS.md`：不修改。它已经强制所有仓库研发任务先读取 Coding；具体 Docs 路由由 Coding 自己维护，避免重复两套路由。
- 其他产品 Blueprint/Appendix/README：本任务不改变产品架构、接口、数据、部署或用户行为，没有文档事实变化。

# 交付

- Branch：`feature/docs-skill`。
- PR：#237 已正常合并到 `main`。
- main merge commit：`aa6159f408e70548c60039141c6846d0f6d3dfb5`。
- main push 永久 CI：Change Completion Gate `32870375661`、CI `32870375696`、Runtime Acceptance `32870375575`、Full-stack Acceptance `32870375683` 均 success。
- Change：`done`，归档到 `changes/archive/2026-08/CHG-20260825-docs-skill/CHANGE.md`。
- 发布：not_applicable。
