---
schema: rvc-change/v1
id: "CHG-20260828-figma-skill"
title: "新增 Figma 原型审查与 Design-to-Code 基线 Skill"
level: L2
status: ready_for_review
owner: "chatgpt"
branch: "docs/add-figma-skill"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "agent-workflow"
  - "docs"
  - "frontend-design"
affected_paths:
  - ".agents/skills/figma/"
contracts: []
data_changes: []
---

# 目标

新增仓库级 `figma` Skill，把近期 Figma 原型审查中反复出现的事实源恢复、后端能力映射、公共组件复用、Prototype 隐藏状态、产品术语和 Design-to-Code Ready 门禁固化为可重复执行的工作流。后续用户只需显式调用 `figma` Skill，即可按当前仓库事实审查或修复 Figma，而无需重复输入同一组约束。

# 成功标准

- [x] 新增 `.agents/skills/figma/SKILL.md`，支持 `review-only`、`review-and-fix`、`baseline-ready` 三种模式。
- [x] Skill 明确区分 Figma 设计事实、业务机器事实和服务器运行事实，禁止把示例数据当生产事实或由设计稿创造后端不存在的能力。
- [x] Skill 覆盖后端 Contract/Capability/调度/Provider 映射、设计系统复用、Component Property、Prototype Variable/Reaction/Flow、状态覆盖、产品术语和 Codex Design Context 审计。
- [x] Skill 与现有 Coding/Docs/Review 职责分层，不复制第二套研发、文档或代码 Review 规范。
- [x] 新增 README、OpenAI agent metadata 和 6 个 references，职责与现有 Skill 目录风格一致。
- [x] 通过标准 `.agents/skills/figma/` 路径与 `agents/openai.yaml` 提供可直接显式调用的 `$figma` Skill；无需修改现有 AGENTS/Figma Guide 形成第二套导航事实。
- [ ] PR 的 Change Completion Gate、总 CI 和适用治理检查通过后正常合并到 `main`。

# 范围

- 新增 `.agents/skills/figma/` 完整 Skill 目录。
- 提供 `SKILL.md`、README、OpenAI agent metadata 与 6 个按职责拆分的 references。
- 通过 PR/CI 完成正常集成。

# 非目标

- 不修改任何 Figma 文件本身。
- 不修改 Vue、Store、generated client、FastAPI、数据库、Contract 或生产运行行为。
- 不修改现有 `AGENTS.md`、Figma Guide 或其它长期文档来复制新 Skill 的详细规则；Figma Skill 自己读取并服从这些上游事实源。
- 不把 AIMA 当前 Route、Provider Registry、Scheduler 周期或具体 Figma Node ID 写死成 Skill 永久事实。
- 不替代宿主环境自己的 Figma MCP、插件技能、权限或工具调用规则。
- 不把 Coding、Docs、Review 的详细规则复制进新 Skill。

# 必须保持不变

- 仓库研发、Change、Git、CI、Review 和交付规则继续以 `AGENTS.md` + Coding Skill 为唯一研发规范源。
- 技术文档事实同步继续由 Docs Skill 负责；Figma Skill 只判断 docs impact 并路由。
- 代码 Review 和测试充分性继续由 Review Skill 负责；Figma Skill 只负责设计/Prototype/Design-to-Code 审查。
- Figma Guide 仍是 AIMA 当前 Design-to-Code 长期项目说明，Figma Skill 不复制其易失项目事实。
- 宿主 Figma 工具的前置技能、权限和调用规范仍由当前宿主负责，仓库 Skill 不绕过。

# 关键决策

1. Skill 名称使用 `figma`，而不是仅限审查的 `figma-review`，因为需要同时支持只读审查、审查并修复、正式开发基线验收。
2. Skill 保持通用方法论：要求读取当前仓库的 Route/Contract/Capability/Provider/Scheduler 等事实，但不把 AIMA 当前具体枚举和值写死。
3. `SKILL.md` 保留主流程和硬门禁，细节拆到 6 个 references，沿用现有 Coding/Docs/Review 的导航式结构。
4. 用户可见产品术语按用户认知审查，不采用“所有英文都翻译”的机械规则；版本号、型号等确有产品价值的表达可以保留。
5. `baseline-ready` 只有在静态结构、Prototype、动态数据来源、公共组件复用、状态完整性、Fresh Screenshot 和 Design Context 都有证据时才能给 READY。
6. Skill 的直接调用入口沿用现有 Skill 约定：标准目录 `.agents/skills/figma/` + `agents/openai.yaml`；不为发现性再修改现有 AGENTS/Guide，避免形成额外同步负担。
7. 仓库 Skill 定义审查方法，不替代宿主 Figma 工具机制；宿主要求的 MCP/插件前置规则必须先遵守。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 创建可直接复用的 Figma Skill，避免后续重复输入审查要求 | user:创建并推送FigmaSkill | satisfied | 已新增 `.agents/skills/figma/SKILL.md`、README、metadata 与 6 个 references |
| R2 | Skill 应固化近期关于 Figma 与仓库真实前后端事实联动的审查方法 | user:结合近期Figma讨论 | satisfied | `SKILL.md` + refs 02/03/04/05 已覆盖事实源、能力映射、组件复用、Prototype、状态与 Ready 门禁 |
| R3 | Skill 必须与当前仓库已有 Coding/Docs/Review 体系兼容，不制造第二套规范 | .agents/skills/review/SKILL.md | satisfied | `SKILL.md` 第1节显式服从 Coding，并对 code issue / docs impact / code review 分别路由回现有 Skill；targeted Docs re-review 确认无需复制现有 Guide |
| R4 | 下次可以直接显式调用该 Skill | user:下次可以直接用 | satisfied | 已新增 `.agents/skills/figma/agents/openai.yaml`，定义 `display_name=Figma` 与默认 `$figma` prompt；README 提供三种模式调用示例 |
| R5 | 交付过程必须使用仓库正常 PR/CI 门禁，不绕过 main 保护 | user:推送到仓库主分支 | satisfied | 已创建 Draft PR #252 指向 `main`；Change 进入 Ready 后由 PR Change Completion Gate/CI 验证，只有全部通过才执行合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 已复核 Skill frontmatter、三种工作模式、硬门禁、6 个 references 导航和 agent default prompt 的职责闭环 |
| 接口 / Contract | not_applicable | 不修改任何产品 API/Schema/CLI/public contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、运行进程、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | README/metadata 已覆盖 review-only、review-and-fix、baseline-ready 三类直接调用；独立 A1/A2 已反向验证近期典型 Figma 问题均有对应检查 |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Skill 采用仓库现有标准目录与 agent metadata 发现/显式调用约定 |
| External Dependency / Provider Probe | not_applicable | 不需要调用真实 Provider 或 Figma 在线数据验证 Skill 文本本身 |
| Build / Package / Runtime | not_applicable | 不修改生产构建、依赖或包产物；本地 clone 验证尝试因执行环境 DNS 无法解析 github.com 未能运行，改用 GitHub API 新鲜文件/路径证据 |
| Docs / Governance / Other | required | Skill/README/metadata/6 refs 已重新列举；AGENTS 临时误改已完整恢复且 compare 零 diff；Review/Docs targeted re-review 无阻塞 Finding；PR #252 已创建 |

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户目标、`AGENTS.md`、Coding、Docs、Review、Review refs、Figma Guide 与既有 Skill 目录结构；没有用当前 Change 反推需求。
- [x] change_coverage：已从“下次直接调用 + 固化近期 Figma 审查经验”独立重建完成定义；Skill 覆盖事实源、前后端能力、示例数据、产品术语、组件复用、Prototype、状态、Target IA、Design Context 和 Ready 门禁。
- [x] reverse_audit：已执行“Skill 规则 → review-only/review-and-fix/baseline-ready”与“近期真实问题 → Skill 检查项”的双向审计；Provider/渠道、调度语义、v版本、双文本/双图标、Toast漂移、旧变量、公共组件、服务器动态数据等均有对应规则。
- [x] unresolved_cleared：Requirement Traceability 已无 `not_satisfied`；生产代码/Contract/Runtime 等不适用层有明确事实依据；独立 Review 当前为 `NO_FINDINGS_WITHIN_SCOPE`。

# 任务

- [x] 恢复当前仓库规则、现有 Skill 结构和 Figma Guide 事实。
- [x] 建立四维任务路由：Documentation/Configuration + Agent Workflow / Requirement-Design-Implementation / Markdown+YAML / L2。
- [x] 创建独立分支和 gated Change。
- [x] 新增 Figma Skill 主文件、README、agent metadata 和 references。
- [x] 确认现有 AGENTS/Figma Guide 无需为 Skill 发现性重复修改；临时误触 AGENTS 已完整恢复。
- [x] 执行 targeted Docs re-review 和独立 Review。
- [x] 完成 Requirement Traceability、Validation Matrix 与 Completion Audit。
- [ ] 由 PR Change Completion Gate 执行机器 Ready Check。
- [ ] 等待全部 CI 通过并合并 main。
- [ ] 独立归档 Change 并完成归档 PR。

# 验证

## 计划

- 逐文件重新读取新增 Skill，检查 frontmatter、内部链接、目录职责和无占位符。
- 重新列举 `.agents/skills/figma/` 与 references，确认 README/SKILL/metadata/6 refs 路径真实存在。
- 以三类典型请求做语义审计：只读审查、审查并修复、Codex 正式基线判断。
- 使用 Review Skill 独立执行 A1/A2 与治理质量复核。
- 由 PR `Change Completion Gate` 执行 `ready_check.py --changed-since <base sha>`；合并后由 main push gate 验证 `--require-active-ready`。

## 新鲜证据

- `GitHub.compare_commits(main, docs/add-figma-skill)` 当前只包含 `.agents/skills/figma/` 与本 Change，不包含生产代码、AGENTS 或既有 Guide 修改。
- `.agents/skills/figma/` 已重新列举确认存在 README、SKILL、`agents/`、`references/`；references 已重新列举确认恰有 6 个已规划文件。
- `SKILL.md` 已按三个区段重新读取，frontmatter、三种模式、6 个 reference 链接、Ready 门禁和禁止事项均存在。
- `02_业务能力与前后端映射.md` 已重新读取并修正 UI→Contract 示例中的换行笔误。
- `01_事实源与审查流程.md` 与 `agents/openai.yaml` 已补充“服从宿主 Figma MCP/工具前置规则”的边界。
- AGENTS 临时误改曾通过 commit diff 被主动发现；随后把该路径恢复为 `main` 原 blob，最新 compare 已确认 AGENTS 零 diff。
- 独立 Review 按 Review Skill/refs 重新执行 A1/A2，当前结论 `NO_FINDINGS_WITHIN_SCOPE`；targeted Docs re-review 判断现有长期文档无需重复修改。
- 尝试在临时目录 clone 当前分支执行本地解析检查，但执行环境 DNS 无法解析 `github.com`，因此没有把该失败冒充验证通过；当前依赖 GitHub API 的新鲜内容、目录、diff 和后续 PR CI 作为机器证据。
- Draft PR #252 已创建，目标 `main`，未绕过 Branch Protection。

# 文档影响

- 新增 `.agents/skills/figma/README.md` 作为 Skill 自身说明和调用导航。
- 现有 `AGENTS.md`、Figma Guide、Blueprint、Frontend README 的长期事实没有发生变化，因此 targeted Docs 判断为无需修改；Figma Skill 在运行时读取并服从这些事实源，而不复制其内容。

# 交付

- Branch：`docs/add-figma-skill`
- Commit：当前分支使用中文提交逐步新增 Skill；最终 PR 采用仓库允许的正常合并方式。
- PR：#252 `文档：新增 Figma 原型审查 Skill`（Draft，待 Ready/CI）。
- CI：待 PR Ready 后运行/确认。
- 发布：不适用。
- 归档：合并并确认 main CI 后执行独立归档 PR。
