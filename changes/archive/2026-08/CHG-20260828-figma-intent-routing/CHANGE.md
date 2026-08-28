---
schema: rvc-change/v1
id: "CHG-20260828-figma-intent-routing"
title: "补强 Figma Skill 高频意图自动路由与 Design-to-Code 实施入口"
level: L2
status: done
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

- [x] `figma` Skill 能从常见自然语言自动识别“全面检查”“检查并修复”“按 Figma 替换现有页面”等高频意图，不要求用户记住模式名。
- [x] 有仓库的“全面检查”默认进入 `baseline-ready`；纯设计/无实现仓库的检查默认进入 `review-only`。
- [x] “检查并修复”进入 `review-and-fix`，修复后必须自动 re-review 并给出 Readiness。
- [x] “按 Figma 替换/实现现有页面”先做 `baseline-ready`，设计 Ready 后明确 handoff 到项目 Coding 工作流，定位真实 Route/Screen、Page/View、State、API/SDK、Contract/Schema、Shared Owner 等适用实现入口后实施。
- [x] Figma Skill 不复制 Change/TDD/CI/Git/PR 等 Coding 细则，只负责路由和 Design-to-Code handoff 边界。
- [x] README 和 OpenAI agent metadata 提供足够短的调用方式，用户后续可直接说“全面检查这个 Figma：<link>”或“按这个 Figma 替换当前页面：<link>”。
- [x] 保持 Skill 跨项目通用，不写死 AIMA、Vue、Provider、具体 Route、Figma Node 或业务页面。
- [x] PR #261 的 Change Completion Gate、Runtime Acceptance 和总 CI 全部通过后正常合并到 `main`；合并后的 `main` 三项 push 门禁再次全部通过，并通过独立归档 PR 移入归档目录。

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
- `review-only`、`review-and-fix`、`baseline-ready` 三种既有模式保持；不新增第四种核心模式。
- 模式目标与写入权限分开判断：只读不自动降级正式基线验收；实现页面不自动扩大 commit/PR/merge/release 权限。
- 真实系统能力继续以目标项目当前机器事实为准，不能由 Figma 或 Skill 示例反向创造。

# 关键决策

1. 不新增第四种核心 Figma 模式；自然语言意图只路由到既有三种模式或“baseline-ready → Coding handoff”组合流程。
2. 高频意图路由写在 `SKILL.md` 主文件，确保用户只说短句时即可触发；详细 Design-to-Code handoff 继续放在既有 ref 05，避免主文件重复完整审查规则。
3. “全面检查”有目标实现仓库时默认 `baseline-ready`，因为需要同时检查视觉、可用性与真实系统一致性；无实现仓库时默认 `review-only`，不得伪造系统事实。
4. “检查并修复”明确提供本轮 Figma 写授权时进入 `review-and-fix`；修复后自动执行 Fresh Screenshot / Prototype / Machine Audit / Design Context 的适用 re-review。
5. “按 Figma 替换现有页面”先验证设计 Ready，再 handoff 到项目 Coding Skill；Coding 负责生产实现、测试、Review、CI 和 Git 交付，Figma Skill 不维护第二套研发规则。
6. “只检查、不修改”是写权限限制，不覆盖显式 `baseline-ready` 目标；“替换/实现页面”授权修改目标实现，但不自动授权 commit、PR、merge、release。
7. README 只保留短提示词入口；agent metadata 收敛成路由提示；详细规则继续单一维护在 Skill/references 中，避免规则副本漂移。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 把“全面检查 Figma 是否美观、好用、符合用户习惯和当前仓库实现”内化为短句可触发的流程 | user:内化全面检查提问 | satisfied | `SKILL.md` 3.1A：有目标实现时默认 `baseline-ready`，Design-only 时默认 `review-only`；既有章节继续承担视觉、可用性、Prototype、系统映射和 Design Context 门禁 |
| R2 | 把“用指定 Figma 替换当前仓库对应页面”内化为短句可触发的 Design-to-Code 流程 | user:内化页面替换提问 | satisfied | `SKILL.md` 3.1C + `references/05_Design-to-Code交付门禁.md` 13.1：baseline-ready → 必要修复/re-review → Coding handoff → 实现后 targeted re-review |
| R3 | 内化时避免冗余，不复制两段长提示词和第二套 Coding 规范 | user:避免Skill冗余 | satisfied | 主 Skill 只增加意图路由；ref 05 只定义设计事实交接；`agents/openai.yaml` 收敛为路由入口并明确以 `$figma` Skill/references 为唯一审查方法源 |
| R4 | 用户后续只需简单表达意图和给 Figma 链接即可使用 | user:后续简单说即可 | satisfied | README“最短使用方式”与 SKILL 3.1D 固化四类短句；目标仓库/分支/Git 只有无法从上下文确定且影响执行边界时再补 |
| R5 | Skill 继续跨项目通用，不局限 AIMA 或某种技术栈 | .agents/skills/figma/SKILL.md | satisfied | 新增路由使用 Route/Screen、Page/View、API/SDK/CMS/Local Store、Shared/Feature 等条件式通用模型；最终 diff 未新增项目专用机器事实 |
| R6 | 交付必须走正常 PR/CI 路径，不直推 `main` 或绕过门禁 | user:推送主分支 | satisfied | PR #261 三项门禁全部成功并正常 squash merge 到 `main`，merge commit `36d973197da63e5ebb4745b23339fe6f7f9f7e94`；合并后 main 三项 push 门禁全部成功 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 已逐项走查短意图路由：有仓库全面检查→`baseline-ready`；Design-only检查→`review-only`；明确修复→`review-and-fix`→re-review；替换/实现→`baseline-ready`→Coding handoff。模式与写权限已分离，既有三模式未被第四模式替换 |
| 接口 / Contract | not_applicable | 不修改产品 API/Schema/SDK/CLI public contract；修改只涉及 Agent Skill 文本与治理元数据 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、进程、设备、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | README 和 SKILL 均可直接使用四类短句；独立反向审计确认短句无需重贴页面尺寸、组件复用、Prototype、动态数据和后端接线清单即可进入已有完整规则 |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Design-to-Code 只定义 Figma Ready 事实到目标项目 Coding 的 handoff 边界 |
| External Dependency / Provider Probe | not_applicable | 本任务没有需要确认的第三方服务、硬件或远端运行事实 |
| Build / Package / Runtime | not_applicable | 不修改生产构建/包/runtime；YAML metadata 通过仓库 CI 与当前解析验证 |
| Docs / Governance / Other | required | PR #261：Change Completion Gate #1174、Runtime Acceptance #449、CI #3328 均成功；merge 后 main：Change Completion Gate #1175、Runtime Acceptance #450、CI #3329 均成功 |

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户“把两类高频提问内化、后续只简单说、避免冗余、推送主分支”的要求，以及当前 `AGENTS.md`、Coding、Figma Skill、ref 05、Review/Docs 协作规则。
- [x] change_coverage：独立比较“全面检查 / 检查并修复 / 按 Figma 替换现有页面”三类用户目标与最终 Skill；三类都有短句入口，且没有把两段长提示词原样复制进主 Skill、README 或 metadata。
- [x] reverse_audit：已执行“短用户意图 → 模式/流程”和“既有 review-only/review-and-fix/baseline-ready/Design-to-Code handoff → 自然语言入口”的双向审计；同时复核模式与写权限、Figma 与 Coding 责任边界，并修正 `review-only` 默认语义和“只读=模式”两处潜在歧义。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`；Contract、Persistence、Golden Path、External Probe、Build 等不适用层均有事实依据；独立 A1/A2 与 targeted Docs re-review 无剩余阻塞 Finding。

# 任务

- [x] 恢复当前 `main` 的 AGENTS、Coding、Blueprint 和现有 Figma Skill 事实。
- [x] 确认当前无 Active Change 冲突并创建独立分支/Change。
- [x] 更新 `SKILL.md` 高频意图自动路由。
- [x] 更新 ref 05 Design-to-Code 实施 handoff。
- [x] 更新 README 短调用入口。
- [x] 更新 OpenAI agent metadata 默认路由提示并消除规则重复。
- [x] 执行内容、通用性、权限边界、职责边界和 YAML 解析验证。
- [x] 执行独立 Review、targeted Docs re-review 与 Completion Audit。
- [x] 创建 PR #261 并将 Change 切到 `ready_for_review`。
- [x] PR #261 三项 CI 门禁全绿并正常 squash merge 到 `main`。
- [x] 合并后 `main` 三项 push 门禁成功。
- [x] 创建独立归档分支并将本 Change 标记 `done`、移入 `changes/archive/2026-08/`。

# 验证

## 新鲜证据

- 开发分支：`docs/figma-intent-routing`，基于原 `main` SHA `ec13305e721b0010d65d1687c58f375751b8032e`。
- 最终开发 diff 仅包含 `.agents/skills/figma/{SKILL.md,README.md,agents/openai.yaml,references/05_Design-to-Code交付门禁.md}` 与当前 Change；没有生产代码、API Contract、Schema、数据库、业务 Figma 或 AGENTS/Blueprint 变化。
- `agents/openai.yaml` 已按标准 YAML 结构解析；仓库 CI 亦通过。
- 独立路由走查：`全面检查`、`全面检查并修好`、`对照当前仓库全面验收`、`按这个 Figma 替换当前对应页面` 四类短句均有唯一、可解释的默认流程。
- 权限审计：只读限制不会把明确 `baseline-ready` 降级；Figma 修复需明确写授权；页面实现不自动扩大 commit/PR/merge/release 权限。
- 规则冗余审计：详细视觉/Prototype/数据/组件审查清单仍只由既有 Skill/references 维护；metadata 已缩成入口路由，不复制第三套审查规范。
- 通用性审计：新增文本没有绑定 AIMA、具体页面、具体 Provider、具体技术栈或 Figma Node。
- PR #261：Change Completion Gate #1174、Runtime Acceptance #449、CI #3328 均为 `success`。
- PR #261 已通过 squash merge 合入 `main`，merge commit：`36d973197da63e5ebb4745b23339fe6f7f9f7e94`。
- `main` merge commit：Change Completion Gate #1175、Runtime Acceptance #450、CI #3329 均为 `success`。

# 文档影响

- targeted：只同步 `figma` Skill 自身的 `SKILL.md`、README、ref 05 和 agent metadata。
- `AGENTS.md`、Blueprint、Figma Guide 没有新的产品/系统事实变化，因此未重复加入意图路由，避免形成第二套规则。

# 交付

- 开发分支：`docs/figma-intent-routing`
- PR：#261 `文档：补强 Figma Skill 高频意图自动路由`，已 squash merge。
- Merge commit：`36d973197da63e5ebb4745b23339fe6f7f9f7e94`。
- CI：PR 与合并后 `main` 的 Change Completion Gate、Runtime Acceptance、总 CI 均成功。
- 发布：不适用。
- 归档：本记录通过独立归档 PR 从 `changes/active/` 移至 `changes/archive/2026-08/`。