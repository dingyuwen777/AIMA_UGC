---
schema: rvc-change/v1
id: "CHG-20260828-figma-skill"
title: "新增 Figma 原型审查与 Design-to-Code 基线 Skill"
level: L2
status: in_progress
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
  - "AGENTS.md"
  - "docs/guides/01_Figma与前端设计开发工作流.md"
contracts: []
data_changes: []
---

# 目标

新增仓库级 `figma` Skill，把近期 Figma 原型审查中反复出现的事实源恢复、后端能力映射、公共组件复用、Prototype 隐藏状态、产品术语和 Design-to-Code Ready 门禁固化为可重复执行的工作流。后续用户只需显式调用 `figma` Skill，即可按当前仓库事实审查或修复 Figma，而无需重复输入同一组约束。

# 成功标准

- [ ] 新增 `.agents/skills/figma/SKILL.md`，支持 `review-only`、`review-and-fix`、`baseline-ready` 三种模式。
- [ ] Skill 明确区分 Figma 设计事实、业务机器事实和服务器运行事实，禁止把示例数据当生产事实或由设计稿创造后端不存在的能力。
- [ ] Skill 覆盖后端 Contract/Capability/调度/Provider 映射、设计系统复用、Component Property、Prototype Variable/Reaction/Flow、状态覆盖、产品术语和 Codex Design Context 审计。
- [ ] Skill 与现有 Coding/Docs/Review 职责分层，不复制第二套研发、文档或代码 Review 规范。
- [ ] 新增 README、OpenAI agent metadata 和 6 个 references，职责与现有 Skill 目录风格一致。
- [ ] `AGENTS.md` 与 Figma Guide 增加 `figma` Skill 导航和使用边界。
- [ ] PR 的 Change Completion Gate、总 CI 和适用治理检查通过后正常合并到 `main`。

# 范围

- 新增 `.agents/skills/figma/` 完整 Skill 目录。
- 更新 `AGENTS.md` 的 Figma / Design-to-Code 导航。
- 更新 `docs/guides/01_Figma与前端设计开发工作流.md`，说明何时调用 Figma Skill，以及 Skill 与 Guide/Coding/Docs 的关系。
- 通过 PR/CI 完成正常集成。

# 非目标

- 不修改任何 Figma 文件本身。
- 不修改 Vue、Store、generated client、FastAPI、数据库、Contract 或生产运行行为。
- 不把 AIMA 当前 Route、Provider Registry、Scheduler 周期或具体 Figma Node ID 写死成 Skill 永久事实。
- 不替代 Figma MCP 自身的 `figma-use`、`figma-design-to-code` 等工具技能。
- 不把 Coding、Docs、Review 的详细规则复制进新 Skill。

# 必须保持不变

- 仓库研发、Change、Git、CI、Review 和交付规则继续以 `AGENTS.md` + Coding Skill 为唯一研发规范源。
- 技术文档事实同步继续由 Docs Skill 负责；Figma Skill 只判断 docs impact 并路由。
- 代码 Review 和测试充分性继续由 Review Skill 负责；Figma Skill 只负责设计/Prototype/Design-to-Code 审查。
- Figma Guide 仍是 AIMA 当前 Design-to-Code 长期项目说明，Figma Skill 不复制其易失项目事实。

# 关键决策

1. Skill 名称使用 `figma`，而不是仅限审查的 `figma-review`，因为需要同时支持只读审查、审查并修复、正式开发基线验收。
2. Skill 保持通用方法论：要求读取当前仓库的 Route/Contract/Capability/Provider/Scheduler 等事实，但不把 AIMA 当前具体枚举和值写死。
3. `SKILL.md` 保留主流程和硬门禁，细节拆到 6 个 references，沿用现有 Coding/Docs/Review 的导航式结构。
4. 用户可见产品术语按用户认知审查，不采用“所有英文都翻译”的机械规则；版本号、型号等确有产品价值的表达可以保留。
5. `baseline-ready` 只有在静态结构、Prototype、动态数据来源、公共组件复用、状态完整性、Fresh Screenshot 和 Design Context 都有证据时才能给 READY。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 创建可直接复用的 Figma Skill，避免后续重复输入审查要求 | user:创建并推送FigmaSkill | not_satisfied | 待新增 `.agents/skills/figma/` |
| R2 | Skill 应固化近期关于 Figma 与仓库真实前后端事实联动的审查方法 | user:结合近期Figma讨论 | not_satisfied | 待在 SKILL/references 固化事实源、能力映射、Prototype、组件和 Ready 门禁 |
| R3 | Skill 必须与当前仓库已有 Coding/Docs/Review 体系兼容，不制造第二套规范 | `.agents/skills/coding/SKILL.md`; `.agents/skills/docs/SKILL.md`; `.agents/skills/review/SKILL.md` | not_satisfied | 待建立显式路由和职责边界 |
| R4 | 后续能从 AGENTS/Figma Guide 找到并正确调用该 Skill | `AGENTS.md`; `docs/guides/01_Figma与前端设计开发工作流.md` | not_satisfied | 待更新导航和使用说明 |
| R5 | 通过仓库正常 PR/CI 门禁集成到 main | user:推送到主分支 | not_satisfied | 待完成 Review、PR、CI 与合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 复核 Skill frontmatter、工作模式、硬门禁、references 导航和 agent default prompt 是否构成完整可执行流程 |
| 接口 / Contract | not_applicable | 不修改任何产品 API/Schema/CLI/public contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、运行进程、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | 以典型调用语句验证 Skill 能覆盖 review-only、review-and-fix、baseline-ready，并能从仓库事实路由到 Figma 审查 |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Skill 的宿主调用由 metadata + 文档导航提供 |
| External Dependency / Provider Probe | not_applicable | 不需要调用真实 Provider 或 Figma 在线数据验证 Skill 文本本身 |
| Build / Package / Runtime | not_applicable | 不修改生产构建、依赖或包产物 |
| Docs / Governance / Other | required | 新 Skill 目录、AGENTS 导航、Figma Guide、Change 结构、Ready Check 和 PR CI |

# Completion Audit

- [ ] upstream_re_read：Ready 前重新读取用户目标、AGENTS、Coding/Docs/Review 与 Figma Guide。
- [ ] change_coverage：独立比较上游要求与 Skill/导航实现，检查是否遗漏近期高频审查失败模式。
- [ ] reverse_audit：执行“Skill 规则 → 典型 Figma 审查任务”和“典型 Figma 问题 → Skill 是否有对应检查”的双向审计。
- [ ] unresolved_cleared：Requirement Traceability 无 `not_satisfied`，所有不适用层有事实依据。

# 任务

- [x] 恢复当前仓库规则、现有 Skill 结构和 Figma Guide 事实。
- [x] 建立四维任务路由：Documentation/Configuration + Agent Workflow / Requirement-Design-Implementation / Markdown+YAML / L2。
- [x] 创建独立分支和 gated Change。
- [ ] 新增 Figma Skill 主文件、README、agent metadata 和 references。
- [ ] 更新 AGENTS 与 Figma Guide。
- [ ] 执行 targeted Docs re-review 和独立 Review。
- [ ] 完成 Requirement Traceability、Validation Matrix、Completion Audit 和 Ready Check。
- [ ] 创建 PR，等待全部 CI 通过并合并 main。
- [ ] 独立归档 Change 并完成归档 PR。

# 验证

## 计划

- 逐文件重新读取新增 Skill，检查 frontmatter、内部链接、目录职责和无占位符。
- 搜索 `.agents/skills/figma` 的 reference 链接和 AGENTS/Guide 导航，确认路径真实存在。
- 以三类典型请求做语义审计：只读审查、审查并修复、Codex 正式基线判断。
- 使用 Review Skill 独立执行 A1/A2 与治理质量复核。
- 由 PR `Change Completion Gate` 执行 `ready_check.py --changed-since <base sha>`；合并后由 main push gate 验证 `--require-active-ready`。

## 新鲜证据

- 待实现后补充。

# 文档影响

- `AGENTS.md`：新增 Figma 原型审查/Design-to-Code Ready 的 Skill 导航。
- `docs/guides/01_Figma与前端设计开发工作流.md`：新增 Figma Skill 的使用入口和与现有 Guide/Coding/Docs 的职责边界。

# 交付

- Branch：`docs/add-figma-skill`
- Commit：待完成。
- PR：待创建。
- CI：待运行。
- 发布：不适用。
- 归档：合并并确认 main CI 后执行独立归档 PR。
