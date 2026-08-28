---
schema: rvc-change/v1
id: "CHG-20260828-figma-intent-routing"
title: "补强 Figma Skill 高频意图自动路由与 Design-to-Code 实施入口"
level: L2
status: in_progress
owner: "chatgpt"
branch: "docs/figma-intent-routing"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "agent-workflow"
  - "docs"
  - "frontend-design"
affected_paths:
  - ".agents/skills/figma/SKILL.md"
  - ".agents/skills/figma/README.md"
  - ".agents/skills/figma/agents/openai.yaml"
  - ".agents/skills/figma/references/05_Design-to-Code交付门禁.md"
contracts: []
data_changes: []
---

# 目标

在不复制现有审查规则、不制造第二套 Coding 工作流的前提下，为通用 `figma` Skill 增加高频自然语言意图自动路由，使用户以后只需要给出 Figma 链接和简短目标，就能自动进入正确的审查、修复或 Design-to-Code 实施流程。

# 成功标准

- [ ] `figma` Skill 能从常见自然语言自动识别“全面检查”“检查并修复”“按 Figma 替换现有页面”等高频意图，不要求用户记住模式名。
- [ ] 有仓库的“全面检查”默认进入 `baseline-ready`；纯设计/无实现仓库的检查默认进入 `review-only`。
- [ ] “检查并修复”进入 `review-and-fix`，修复后必须自动 re-review 并给出 Readiness。
- [ ] “按 Figma 替换/实现现有页面”先做 `baseline-ready`，设计 Ready 后明确 handoff 到项目 Coding 工作流，定位真实 Route/Page/State/API/Contract/Shared Owner 后实施。
- [ ] Figma Skill 不复制 Change/TDD/CI/Git/PR 等 Coding 细则，只负责路由和 Design-to-Code handoff 边界。
- [ ] README 和 OpenAI agent metadata 提供足够短的调用方式，用户后续可直接说“全面检查这个 Figma：<link>”或“按这个 Figma 替换当前页面：<link>”。
- [ ] 保持 Skill 跨项目通用，不写死 AIMA、Vue、Provider、具体 Route、Figma Node 或业务页面。
- [ ] 独立 Review、Change Completion Gate、Runtime Acceptance 和总 CI 通过后正常合并到 `main`，随后完成 Change 归档。

# 范围

- 更新 `.agents/skills/figma/SKILL.md`：新增高频用户意图自动路由。
- 更新 `.agents/skills/figma/references/05_Design-to-Code交付门禁.md`：新增“Figma → 现有页面/代码实现”的正式 handoff 流程与责任边界。
- 更新 `.agents/skills/figma/README.md`：将长提示词收敛成短调用入口，并解释自动路由。
- 更新 `.agents/skills/figma/agents/openai.yaml`：让默认 Prompt 能按自然语言意图选择模式并在 Design-to-Code 场景切回 Coding 工作流。
- 正常 PR/CI/合并/归档。

# 非目标

- 不修改业务 Figma 文件。
- 不修改前端、后端、数据库、API Contract、Schema 或生产运行行为。
- 不把用户之前的两段长提示词原样复制进 Skill。
- 不新增第二套 Coding、Docs 或 Review 规范。
- 不要求所有项目都有仓库、Route、API、数据库或 Design-to-Code 实现层。

# 必须保持不变

- 当前仓库的研发、Change、TDD、Review、CI、Git 和交付规则继续由 `AGENTS.md` + Coding Skill 负责。
- Figma Skill 继续保持跨项目通用，只定义 Figma 审查、修复、Ready 与实现 handoff 方法。
- `review-only`、`review-and-fix`、`baseline-ready` 三种既有模式语义保持兼容。
- 没有明确写入授权时，Figma Skill 不自动修改 Figma；没有生产代码授权时，不自动修改代码。
- 真实系统能力继续以目标项目当前机器事实为准，不能由 Figma 或 Skill 示例反向创造。

# 关键决策

1. 不新增第四种核心 Figma 模式；自然语言意图只路由到既有三种模式或“baseline-ready → Coding handoff”组合流程。
2. 高频意图路由写在 `SKILL.md` 主文件，确保用户只说短句时即可触发；详细 Design-to-Code handoff 继续放在既有 ref 05，避免主文件膨胀。
3. “全面检查”有仓库时默认 `baseline-ready`，因为用户通常同时要求视觉、可用性与当前实现一致；无实现仓库时默认 `review-only`，不得伪造系统事实。
4. “检查并修复”只有在用户明确授权修改 Figma 时进入 `review-and-fix`；修复后自动执行 Fresh Screenshot / Prototype / Machine Audit / Design Context 的适用 re-review。
5. “按 Figma 替换现有页面”不由 Figma Skill直接承担生产实现：先验证设计 Ready，再 handoff 到项目 Coding Skill，由 Coding 负责当前仓库事实恢复、实现、测试、Review、CI 和 Git 交付。
6. README 只保留短提示词示例，详细规则继续单一维护在 Skill/references 中，避免提示词和规范重复漂移。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 把“全面检查 Figma 是否美观、好用、符合用户习惯和当前仓库实现”内化为短句可触发的流程 | user:内化全面检查提问 | not_satisfied | 待更新 `SKILL.md` 高频意图路由 |
| R2 | 把“用指定 Figma 替换当前仓库对应页面”内化为短句可触发的 Design-to-Code 流程 | user:内化页面替换提问 | not_satisfied | 待更新 `SKILL.md` + ref 05 handoff |
| R3 | 内化时避免冗余，不复制两段长提示词和第二套 Coding 规范 | user:避免Skill冗余 | not_satisfied | 待通过差异和独立 Review 验证 |
| R4 | 用户后续只需简单表达意图和给 Figma 链接即可使用 | user:后续简单说即可 | not_satisfied | 待更新 README / agent metadata |
| R5 | Skill 继续跨项目通用，不局限 AIMA 或某种技术栈 | .agents/skills/figma/SKILL.md | not_satisfied | 待对最终文本执行项目特定术语反向审计 |
| R6 | 通过正常门禁推送并合并到 main | user:推送主分支 | not_satisfied | 待 PR / CI / merge / archive |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 复核意图短句 → 正确模式/工作流的路由语义，确保既有三模式兼容 |
| 接口 / Contract | not_applicable | 不修改产品 API/Schema/SDK/CLI public contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、进程、设备、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | 用“全面检查”“检查并修复”“按 Figma 替换现有页面”三类短提示词反向走查，验证无需重复长约束即可得到完整流程 |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Design-to-Code 只定义 Figma → Coding handoff |
| External Dependency / Provider Probe | not_applicable | 无真实外部服务事实需要验证 |
| Build / Package / Runtime | not_applicable | 不修改生产构建/包；仓库 CI 仅作为治理/解析门禁证据 |
| Docs / Governance / Other | required | Skill frontmatter、README、agent metadata、references、Change Ready/CI/Review 均需验证 |

# Completion Audit

- [ ] upstream_re_read：完成前重新读取本轮用户要求、当前 `figma` Skill 与 Coding/Figma Design-to-Code 上游规则。
- [ ] change_coverage：独立检查“检查 / 检查并修复 / 替换现有页面”三类高频意图是否均被覆盖且没有复制长提示词。
- [ ] reverse_audit：执行“短用户意图 → 模式/流程”与“既有模式/Design-to-Code handoff → 是否有自然语言入口”的双向审计，并复核 Figma/Coding 责任边界。
- [ ] unresolved_cleared：Requirement Traceability 无 `not_satisfied`，不适用层均有事实依据，独立 Review 无阻塞 Finding。

# 任务

- [x] 恢复当前 `main` 的 AGENTS、Coding、Blueprint 和现有 Figma Skill 事实。
- [x] 确认当前无 Active Change 冲突并创建独立分支/Change。
- [ ] 更新 `SKILL.md` 高频意图自动路由。
- [ ] 更新 ref 05 Design-to-Code 实施 handoff。
- [ ] 更新 README 短调用入口。
- [ ] 更新 OpenAI agent metadata 默认路由提示。
- [ ] 执行内容/链接/通用性/职责边界验证。
- [ ] 执行独立 Review 与 Completion Audit。
- [ ] PR CI 全绿后合并 `main`。
- [ ] 合并后校验 main 并创建独立归档 PR。

# 验证

## 计划证据

- `SKILL.md`：检查新增路由不会重复已有审查清单。
- ref 05：检查 Design-to-Code handoff 只引用 Coding 工作流，不复制 TDD/CI/Git 规则。
- README：检查短提示词能覆盖三类高频意图。
- `agents/openai.yaml`：检查默认 Prompt 与主 Skill 语义一致。
- Git diff：只允许上述 Skill 文件与当前 Change。
- PR / main：按仓库现有 Change Completion Gate、Runtime Acceptance、总 CI 作为治理证据。

# 文档影响

- `figma` Skill 自身文档需要同步（SKILL/README/ref 05/agent metadata）。
- `AGENTS.md`、Blueprint、Figma Guide 没有新的产品/系统事实变化，不复制本次意图路由，避免形成第二套规则。

# 交付

- 开发分支：`docs/figma-intent-routing`
- PR：待创建
- Merge：待完成
- Change 归档：待完成
