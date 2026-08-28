---
schema: rvc-change/v1
id: "CHG-20260828-figma-skill"
title: "新增通用 Figma 原型审查与 Design-to-Code 基线 Skill"
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

新增一个跨项目通用的 `figma` Skill，把 Figma 原型审查、真实系统能力映射、页面美观与可用性、公共组件与业务逻辑复用、Prototype 隐藏状态、动态数据来源和 Design-to-Code Ready 门禁固化为可重复执行工作流。Skill 不绑定 AIMA、具体业务页面、某个后端模型或某一种技术栈；安装到其它项目后应先识别项目形态，再按真实边界执行审查。

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
| R3 | Skill 必须跨项目通用，不能局限 AIMA、具体页面或某种技术栈 | user:通用Skill | satisfied | ref 00 提供项目形态路由；主 Skill/README/metadata 已改为 Web/Mobile/Desktop/Static/Design-only 通用模型；项目特定机器值未写死 |
| R4 | 页面审查要保证美观、符合使用习惯、尺寸合理、各区块位置合理，图片/标注不重叠且间距统一 | user:布局与美观规范 | satisfied | ref 07 + 主 Ready 门禁覆盖 Viewport、对齐、间距、图片/图表/标注、长文本、滚动和用户任务顺序 |
| R5 | 需要读取后端/数据库/其它系统数据时必须明确来源并保证设计能真正接入实现 | user:真实可用与数据来源 | satisfied | ref 02 泛化到 API/SDK/CMS/Local Store/Runtime/数据库正式链路；主 Skill 要求动态数据 Annotation 和真实系统动作映射 |
| R6 | 可复用视觉组件和可复用业务逻辑都要公共化并避免多页面复制 | user:公共组件与业务逻辑复用 | satisfied | ref 03 明确 Shared UI / Feature Public / Shared Domain 唯一 Owner；基础 Button/Input 不承载业务规则 |
| R7 | Skill 必须与仓库 Coding/Docs/Review 体系兼容，不制造第二套规范 | .agents/skills/review/SKILL.md | satisfied | Skill 显式服从项目研发规则并只定义 Figma 审查；现有 AGENTS/Guide 未修改 |
| R8 | 下次可以直接显式调用 Skill | user:下次可以直接用 | satisfied | `agents/openai.yaml` 定义 `$figma` 默认 prompt；README 提供通用调用示例 |
| R9 | 交付必须通过正常 PR/CI 合并 main | user:推送到仓库主分支 | satisfied | Draft PR #252 指向 `main`；Ready 后由 Change Completion Gate/CI 验证，全部通过才合并 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 已复核 Skill frontmatter、项目形态路由、三种模式、8 refs、Ready 门禁和 metadata 的职责闭环 |
| 接口 / Contract | not_applicable | 本任务不修改产品 API/Schema/SDK/CLI public contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、进程、设备、文件存储或第三方运行依赖 |
| 用户 / Workflow Acceptance | required | 已用 Design-only、Web Full-stack、Mobile/Desktop、Dashboard 四类典型任务反向审计 Skill；各自只加载真实边界并覆盖布局、数据来源、复用和 Prototype |
| 跨组件 Golden Path | not_applicable | 不修改生产组件链；Skill 通过标准 Skill 目录与 metadata 调用 |
| External Dependency / Provider Probe | not_applicable | 不需要真实外部服务验证 Skill 文本 |
| Build / Package / Runtime | not_applicable | 不修改生产构建/包；机器治理证据由 PR CI 提供 |
| Docs / Governance / Other | required | Skill 目录、8 refs、README、metadata、Change、独立 Review、PR Ready Check 和 CI |

# Completion Audit

- [x] upstream_re_read：已重新读取本轮用户最初目标及后续“真实可用、布局尺寸、图片/标注、业务逻辑复用、跨项目通用”补充，并重新核对项目规则、Coding/Docs/Review 与当前 diff。
- [x] change_coverage：已独立比较全部用户要求与 Skill：通用项目形态、页面美观/可用性、系统数据来源、真实接线、公共视觉组件、业务逻辑唯一 Owner、Prototype 和 Design-to-Code 都有明确章节/reference/Ready 门禁。
- [x] reverse_audit：已执行“Design-only / Web Full-stack / Mobile-Desktop / Dashboard → Skill 路由”以及“尺寸错位、图片/标注重叠、长文本、动态数据来源、伪能力、重复组件、重复业务逻辑、旧 Prototype 状态 → Skill 检查项”的双向审计，未发现新的阻塞缺口。
- [x] unresolved_cleared：Requirement Traceability 无 `not_satisfied`；产品 Contract/Runtime 未变更等不适用层均有事实依据；独立 Review 当前结论 `NO_FINDINGS_WITHIN_SCOPE`。

# 任务

- [x] 恢复当前仓库规则和现有 Skill 结构。
- [x] 创建独立分支、gated Change 和 Draft PR #252。
- [x] 新增通用 Figma Skill 主文件、README、agent metadata。
- [x] 新增/泛化 8 个 references。
- [x] 从 Web/后端偏置改成跨项目形态路由。
- [x] 补页面尺寸、布局、美观、图片/标注、间距和真实可用性门禁。
- [x] 补公共视觉组件和可复用业务逻辑唯一 Owner 审计。
- [x] 重新执行 targeted Docs re-review 和独立 A1/A2 Review。
- [x] 完成 Completion Audit 并切回 `ready_for_review`。
- [ ] 由 PR Change Completion Gate 执行机器 Ready Check。
- [ ] 等待全部 CI 通过并合并 main。
- [ ] 独立归档 Change。

# 验证

## 计划

- PR Ready 后由 Change Completion Gate 执行 `ready_check.py --changed-since`。
- 等待 Runtime Acceptance 和总 CI，全部成功后才合并。
- 合并后确认 main 的相同门禁通过，再独立归档 Change。

## 新鲜证据

- `GitHub.compare_commits(main, docs/add-figma-skill)` 只包含 `.agents/skills/figma/` 与本 Change，没有生产代码或现有 AGENTS/Guide 修改。
- `.agents/skills/figma/references/` 已重新列举，当前使用 00–07 共 8 个通用 reference；旧“前后端映射”文件已删除，替换为“真实系统映射”。
- `SKILL.md` frontmatter 明确“面向任意项目”，并按项目形态选择 API/SDK/CMS/Local Store/Device/Runtime 等边界。
- README 明确可安装到任意项目，并列出 Web/Mobile/Desktop/Dashboard/Admin/Static/Design System/Design-only 场景。
- `agents/openai.yaml` 默认 prompt 明确 `Do not assume every project is a web/full-stack application`，并包含 Viewport、图片/标注重叠、真实长数据、业务逻辑 Owner 和系统能力映射检查。
- ref 07 已把页面尺寸、浏览器/设备、间距、图片/图表/标注、表格/表单、Overlay/Scroll、动态数据 Annotation 和真实系统调用链纳入硬门禁。
- ref 03 已把公共视觉组件与可复用业务逻辑分离，并要求跨页面相同业务规则只有一个 Owner。
- 独立 A1/A2 Review 重新以最新用户要求为上游完成定义，当前 `NO_FINDINGS_WITHIN_SCOPE`；targeted Docs re-review 判断现有项目长期文档无需复制通用 Skill 规则。
- PR #252 当前保持 Draft，未绕过 Branch Protection；下一步仅在本 Change Ready 后转 Ready。

# 文档影响

- 新增 `.agents/skills/figma/README.md` 作为通用 Skill 自身说明。
- 现有项目 AGENTS/Guide/Blueprint 没有发生新的产品/系统事实变化，继续不修改，避免把通用 Skill 复制成项目本地第二套事实。

# 交付

- Branch：`docs/add-figma-skill`
- PR：#252 `文档：新增通用 Figma 原型审查 Skill`，当前 Draft，待转 Ready。
- CI：待 PR Ready 后运行/确认。
- 发布：不适用。
- 归档：合并并确认 main CI 后执行独立归档 PR。
