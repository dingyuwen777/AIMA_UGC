---
schema: rvc-change/v1
id: "CHG-20260828-figma-skill"
title: "新增通用 Figma 原型审查与 Design-to-Code 基线 Skill"
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
contracts: []
data_changes: []
---

# 目标

新增一个跨项目通用的 `figma` Skill，把 Figma 原型审查、真实系统能力映射、页面美观与可用性、公共组件与业务逻辑复用、Prototype 隐藏状态、动态数据来源和 Design-to-Code Ready 门禁固化为可重复执行工作流。Skill 不能绑定 AIMA、采集策略、采集运行中心、某个后端模型或某一种技术栈；后续安装到其它项目也应能先识别项目形态，再按真实边界执行审查。

# 成功标准

- [x] 新增 `.agents/skills/figma/SKILL.md`，支持 `review-only`、`review-and-fix`、`baseline-ready`。
- [x] Skill 明确适用于 Web、Mobile、Desktop、Dashboard、Admin、Static Site、Design System 和 Design-only 等不同项目形态，不机械要求所有项目都有 API/数据库/Route。
- [x] Skill 区分设计事实、系统机器事实、运行时事实和代表性示例，禁止把示例数据当生产事实或由设计稿创造真实系统不存在的能力。
- [x] Skill 覆盖真实系统 Contract/API/SDK/CMS/Local State/Runtime 等能力映射，数据库数据必须通过项目正式架构进入客户端。
- [x] Skill 覆盖页面尺寸、Viewport、布局、间距、图片比例/裁切、图片/文字/按钮/标注不重叠、图表 Label、长文本、表格/表单、Overlay、滚动和用户任务顺序。
- [x] Skill 要求跨页面稳定视觉组件复用公共 Component，并要求可复用业务逻辑有唯一 Owner；同时避免把 Feature 逻辑机械提升成全局万能组件。
- [x] Skill 覆盖 Component Property、Token、Prototype Variable/Reaction/Flow、状态完整性、用户术语和 Design Context 审计。
- [x] Skill 与现有 Coding/Docs/Review 职责分层，不复制第二套研发、文档或代码 Review 规范。
- [x] 新增 README、OpenAI agent metadata 和 8 个 references，结构与现有 Skill 目录风格一致。
- [x] 通过标准 `.agents/skills/figma/` + `agents/openai.yaml` 提供可直接显式调用的 `$figma` Skill。
- [ ] PR 的 Change Completion Gate、总 CI 和适用治理检查通过后正常合并到 `main`。

# 范围

- 新增 `.agents/skills/figma/` 完整通用 Skill。
- `SKILL.md`：通用主流程、三种模式和 Ready 门禁。
- `README.md`：跨项目使用说明和调用示例。
- `agents/openai.yaml`：通用默认 Prompt。
- 8 个 references：项目形态、事实源、系统能力映射、组件/业务逻辑复用、Prototype、Design-to-Code、Findings、页面布局/真实可用性。
- 通过 PR/CI 完成正常集成。

# 非目标

- 不修改任何业务 Figma 文件本身。
- 不修改 Vue/React/Flutter/原生客户端、后端、数据库、Contract 或生产运行行为。
- 不把 AIMA 当前 Route、Provider、Scheduler、具体页面 Node、平台枚举或设计尺寸写成通用永久事实。
- 不修改现有 `AGENTS.md`、Figma Guide 或其它长期文档来复制新 Skill 的详细规则。
- 不替代宿主环境自己的 Figma MCP、插件、权限或工具调用规则。
- 不把 Coding、Docs、Review 的详细规则复制进新 Skill。

# 必须保持不变

- 当前仓库研发、Change、Git、CI、Review 和交付规则继续以 `AGENTS.md` + Coding Skill 为唯一研发规范源。
- 技术文档事实同步继续由 Docs Skill 负责。
- 代码 Review 和测试充分性继续由 Review Skill 负责。
- 宿主 Figma 工具前置技能、权限和调用规范仍由当前宿主负责。
- 通用 Skill 只定义“怎样审查”，项目本地 Design Guide/Design System/Product Spec/机器事实定义“这个项目具体应该是什么”。

# 关键决策

1. Skill 名称使用 `figma`，支持审查、修复和正式基线验收。
2. 先识别项目形态，再决定读取 Route/API/SDK/CMS/数据库/设备能力等哪些事实，不把 Full-stack Web 当默认世界模型。
3. 页面美观和真实可用性进入硬审查域：Frame/Viewport、布局、间距、图片/标注、长文本、滚动、表格/表单和用户任务路径都必须检查。
4. 公共复用包括视觉组件和业务逻辑，但必须落到正确层级：Shared UI、Feature Public、Shared Domain/Service 等唯一 Owner；Button/Input 等基础组件不承载业务规则。
5. 数据来源标注使用通用 `SYSTEM_DYNAMIC / RUNTIME_STATE / DESIGN_EXAMPLE / SYSTEM_FIXED` 等分类；数据最终在数据库并不意味着客户端直接访问数据库。
6. `baseline-ready` 只有在适用的静态结构、真实系统能力、动态数据来源、布局/可用性、Prototype、复用边界、Fresh Screenshot 和 Design Context/实现视角都有证据时才能给 READY。
7. Skill 通过标准目录 + agent metadata 直接调用，不为发现性再改现有 AGENTS/Guide。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 创建可直接复用的 Figma Skill，避免后续重复输入审查要求 | user:创建并推送FigmaSkill | satisfied | 已新增 `.agents/skills/figma/` 主文件、README、metadata 和 references |
| R2 | Skill 要固化 Figma 与真实系统能力、动态数据和 Design-to-Code 的审查 | user:结合近期Figma讨论 | satisfied | `SKILL.md` + refs 01/02/04/05 已覆盖事实源、真实系统映射、Prototype 与交付门禁 |
| R3 | Skill 必须跨项目通用，不能局限 AIMA、采集策略/运行中心或某种技术栈 | user:通用Skill | satisfied | 新增 ref 00 项目形态路由；主 Skill/README/metadata 已改为 Web/Mobile/Desktop/Static/Design-only 等通用模型；项目特定机器值未写死 |
| R4 | 页面审查要保证美观、符合使用习惯、尺寸合理、各区块位置合理，图片/标注不重叠且间距统一 | user:布局与美观规范 | satisfied | 新增 ref 07；主 Ready 门禁加入 Viewport、对齐、间距、图片/图表/标注、长文本、滚动和用户任务顺序 |
| R5 | 需要读取后端/数据库/其它系统数据时必须明确来源并保证设计能真正接入实现 | user:真实可用与数据来源 | satisfied | ref 02 泛化到 API/SDK/CMS/Local Store/Runtime/数据库正式链路；主 Skill 要求动态数据 Annotation 和真实系统动作映射 |
| R6 | 可复用视觉组件和可复用业务逻辑都要公共化并避免多页面复制 | user:公共组件与业务逻辑复用 | satisfied | ref 03 明确 Shared UI / Feature Public / Shared Domain 唯一 Owner；基础 Button/Input 不承载业务规则 |
| R7 | Skill 必须与仓库 Coding/Docs/Review 体系兼容，不制造第二套规范 | .agents/skills/review/SKILL.md | satisfied | Skill 显式服从项目研发规则并只定义 Figma 审查；现有 AGENTS/Guide 未修改 |
| R8 | 下次可以直接显式调用 Skill | user:下次可以直接用 | satisfied | `agents/openai.yaml` 定义 `$figma` 默认 prompt；README 提供三种模式通用示例 |
| R9 | 交付必须通过正常 PR/CI 合并 main | user:推送到仓库主分支 | satisfied | Draft PR #252 指向 `main`；只有 Ready Check/CI 通过才执行合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 复核 Skill frontmatter、项目形态路由、三种模式、8 refs、Ready 门禁和 metadata 是否形成完整可执行流程 |
| 接口 / Contract | not_applicable | 本任务不修改产品 API/Schema/SDK/CLI public contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、进程、设备、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | 用 Design-only、Web Full-stack、Mobile/Desktop、Dashboard 等典型请求反向检查 Skill 是否按项目形态选择规则，并覆盖布局、动态数据、复用和 Prototype |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Skill 通过标准 Skill 目录与 metadata 调用 |
| External Dependency / Provider Probe | not_applicable | 不需要真实外部服务验证 Skill 文本 |
| Build / Package / Runtime | not_applicable | 不修改生产构建/包；机器治理证据由 PR CI 提供 |
| Docs / Governance / Other | required | Skill 目录、8 refs、README、metadata、Change、独立 Review、PR Ready Check 和 CI |

# Completion Audit

- [ ] upstream_re_read：最终 Ready 前重新读取最新用户补充、项目规则、Coding/Docs/Review 和当前 Skill diff。
- [ ] change_coverage：独立检查通用性、页面美观/可用性、数据来源、系统可接入、公共组件和业务逻辑复用是否全部进入 Skill。
- [ ] reverse_audit：执行“多类项目请求 → Skill 路由”和“典型 Figma 缺陷 → Skill 检查项”双向审计。
- [ ] unresolved_cleared：Requirements 无未满足项，所有不适用层有事实依据。

# 任务

- [x] 恢复当前仓库规则和现有 Skill 结构。
- [x] 创建独立分支、gated Change 和 Draft PR #252。
- [x] 新增 Figma Skill 主文件、README、agent metadata。
- [x] 新增/泛化 8 个 references。
- [x] 从 Web/后端偏置改成跨项目形态路由。
- [x] 补页面尺寸、布局、美观、图片/标注、间距和真实可用性门禁。
- [x] 补公共视觉组件和可复用业务逻辑唯一 Owner 审计。
- [ ] 重新执行 targeted Docs re-review 和独立 Review。
- [ ] 完成 Completion Audit 并切回 `ready_for_review`。
- [ ] 由 PR Change Completion Gate 执行机器 Ready Check。
- [ ] 等待全部 CI 通过并合并 main。
- [ ] 独立归档 Change。

# 验证

## 计划

- 重新列举 `.agents/skills/figma/` 与 references，确认恰有 8 个通用 refs。
- 检查主 Skill/README/metadata 不依赖 AIMA、采集策略、采集运行中心、具体 Provider/平台/Route 或具体技术栈。
- 用至少四类典型任务做语义反向审计：Design-only 页面、Web Full-stack、Mobile/Desktop、Data Dashboard。
- 检查“页面尺寸/重叠/间距/图片/标注/长文本/滚动”是否都有 Ready 门禁。
- 检查“公共 Button 等视觉组件”和“可复用业务逻辑唯一 Owner”是否被明确区分。
- 使用 Review Skill 独立执行 A1/A2；使用 Docs Skill targeted re-review 判断是否形成第二套项目事实。
- PR Ready 后由 Change Completion Gate 执行 `ready_check.py --changed-since`。

## 新鲜证据

- Draft PR #252 已转回 Draft，以承载用户新增通用性/布局/复用要求，未在旧 Ready 结论上继续推进。
- 新增 `00_通用适用性与项目形态.md` 和 `07_页面布局与真实可用性审计.md`。
- 原 `02_业务能力与前后端映射.md` 已删除并替换为 `02_业务能力与真实系统映射.md`，避免默认 Web/后端模型。
- `SKILL.md`、README、metadata、refs 01/03/04/05/06 已泛化，不再把 AIMA/采集页面作为规则前提。
- `03_设计系统与组件复用审计.md` 已明确视觉组件和业务逻辑两类复用 Owner。
- 待重新 Review/CI 后继续补充。

# 文档影响

- 新增 `.agents/skills/figma/README.md` 作为通用 Skill 自身说明。
- 现有项目 AGENTS/Guide/Blueprint 没有需要同步的新系统事实，继续不修改，避免把通用 Skill 规则复制成项目本地第二套事实。

# 交付

- Branch：`docs/add-figma-skill`
- PR：#252 `文档：新增 Figma 原型审查 Skill`，当前 Draft。
- CI：待重新 Ready 后运行/确认。
- 发布：不适用。
- 归档：合并并确认 main CI 后执行独立归档 PR。
