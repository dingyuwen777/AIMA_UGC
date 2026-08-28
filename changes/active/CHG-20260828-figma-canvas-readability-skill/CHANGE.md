---
schema: rvc-change/v1
id: "CHG-20260828-figma-canvas-readability-skill"
title: "Coding Skill 增加 Figma 画布可读性与间距规则"
level: L2
status: in_progress
owner: "chatgpt"
branch: "docs/figma-canvas-readability-skill"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "coding-skill"
  - "tests"
affected_paths:
  - ".agents/skills/coding/references/02_跨项目研发任务路由.md"
  - ".agents/skills/coding/references/13_Figma设计画布与可读性规则.md"
  - ".agents/skills/coding/tests/test_development_guidance.py"
contracts: []
data_changes: []
---

# 目标

把“修改 Figma 原型/设计稿时，不能只保证单个 Frame 内部正确，还必须保持整个 Canvas 中画板、注释、开发说明、状态稿和辅助标记具有合理间距、明确归属和良好可读性”的要求固化到 Coding Skill。

采用“主 `SKILL.md` 固定要求每个任务先读取四维路由 → `02_跨项目研发任务路由.md` 对 Figma 任务触发专项 reference → 独立 Figma reference 保存完整可执行细则”的结构。这样无需把几十条 Figma 细则塞进主文件，也能确保命中 Figma 创建/修改/整理/Design-to-Code 时被强制加载。

规则优先使用当前项目已有 Design System / Spacing Token；只有项目没有明确间距规范时才使用通用缺省值，避免 Skill 反向建立第二套设计系统。

# 成功标准

- [x] Coding 的强制四维路由新增 Figma 触发：创建、修改、整理、模板化、状态稿维护或 Design-to-Code 时必须读取专门的 Figma 画布规则。
- [x] 新增独立 reference，定义项目 Design System 优先、页面内部语义间距、注释/开发说明与正式画板间距、画板组间距、正式/历史/废弃/说明分区、zoom-out Canvas Review、禁止事项和完成判定。
- [x] 缺省数值采用可解释的 4px 网格参考，并明确它们只是无项目规范时的 fallback，不覆盖项目已有 Token/Grid/Layout Guideline。
- [x] AIMA 当前 Figma Guide 已有 `Spacing` Design Token 与视觉“间距”核对规则；本次不复制第二份项目级间距表，专项 reference 明确项目 Overlay 优先。
- [x] Coding 规则回归测试覆盖 Figma 路由、reference 关键 Canvas Review/间距规则，并确认 AIMA Guide 仍提供项目级 Spacing/视觉核对入口。
- [x] 不修改产品运行代码、HTTP Contract、数据库、Migration、generated client、依赖或当前 Figma 文件本身。
- [ ] PR 的适用 Docs/Governance/Completion Gate/CI 全绿，经 Review 后正常合并 `main`，并验证 merge 后 `main`。

# 范围与非目标

范围：Coding Skill 的 Figma 专项规则、强制路由、最小治理回归测试与本 Change。

非目标：不修改任何 Vue/Python 生产实现；不修改 Figma 文件；不建立像素级视觉回归框架；不规定所有项目必须使用同一固定数值；不新增设计工具或第三方依赖；不重排既有 01—12 references；不把相同 Canvas 间距表重复写入 AIMA Guide。

# 必须保持不变

- 当前 Coding Skill 的四维路由、Change、Completion Gate、Review、Git 与验证规则保持不变。
- `references/` 继续按触发条件最小读取，不要求每个编码任务机械加载 Figma 规则。
- 项目已有 Design System / Spacing Token / Grid / Layout Guideline 的优先级高于 Skill fallback 数值。
- Figma 负责视觉/交互事实，HTTP/数据库/Provider 等机器事实仍由当前 Contract/代码/测试维护。
- 历史/废弃 Figma 资产不能因为画布整理而静默删除；只允许按现有设计治理做明确分区或归档。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Figma 页面内画板、注释说明等必须保持合理间距，保证画布美观与可读性，并把该要求写入 Skill | user:2026-08-28-figma-canvas-spacing | satisfied | 新增 `13_Figma设计画布与可读性规则.md`，覆盖页面、注释、画板组、分区和 Canvas-level Review；`02_跨项目研发任务路由.md` 已把 Figma 任务硬路由到该 reference |
| R2 | Figma 页面/公共组件优先遵循当前项目已有 Design System/Spacing，而不是另造第二套规则 | docs/guides/01_Figma与前端设计开发工作流.md | satisfied | 新 reference 明确“项目 Design System/Token/Grid/Layout → 当前稳定模式 → fallback”的优先级；AIMA Guide 已有 Spacing Design Token 与视觉间距核对，不复制第二份固定数值表 |
| R3 | Detailed reference 只有命中触发条件时才加载，主 Skill 保持路由入口而不堆叠全部细则 | .agents/skills/coding/SKILL.md | satisfied | 主 Skill 已强制所有任务先读取 `02_跨项目研发任务路由.md`；本次只在该路由增加 Figma 命中条件，并把详细规则放入独立 `13_` reference |
| R4 | 完成后正常推送并合并主分支，不绕过仓库门禁 | user:2026-08-28-push-main | explicitly_deferred | 按 AGENTS/Coding 的 Ready→CI/Review→merge→main 验证顺序，在实现验证完成后执行 |

# Validation Matrix

| Layer | Required | Planned Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | `.agents/skills/coding/tests/test_development_guidance.py` 断言 Figma 路由、reference 关键规则和 AIMA Guide Overlay 入口 |
| 接口 / Contract | not_applicable | 不修改 public API/ABI/HTTP/Schema/format/generated boundary |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件运行时、进程或外部依赖 |
| 用户 / Workflow Acceptance | not_applicable | 本次是开发治理规则，不改变产品用户工作流；规则可执行性由内容审查与治理测试证明 |
| 跨组件 Golden Path | not_applicable | 无产品跨组件接线变化 |
| 外部依赖 Probe | not_applicable | 不需要访问 Figma API 或其他外部服务来证明规则文本 |
| Build / Package / Runtime | not_applicable | 不修改可执行包、Runtime 或依赖 |
| Docs / Governance / Other | required | Coding governance tests、`check_docs.py`、Change Completion Gate、PR CI 与 A1/A2 Review |

# 实施记录

1. 读取当前 `AGENTS.md`、Coding Skill/路由/Change/Validation/Review 规则、AIMA Figma Guide 和 Coding governance tests。
2. 新增 `.agents/skills/coding/references/13_Figma设计画布与可读性规则.md`，完整表达可执行规则。
3. 在强制读取的 `02_跨项目研发任务路由.md` 增加 Figma 创建/修改/整理/模板化/状态稿/Design-to-Code 触发，保证命中时加载 `13_` reference。
4. 更新 `test_development_guidance.py`，固定路由链、Design System 优先、24–32px 注释 fallback、64–80px 同组画板 fallback、Canvas-level Review、zoom-out 和完成判定。
5. 本任务属于文档/治理规则变更，按 Coding 的 docs/config TDD 例外使用内容/引用/治理检查，不伪造产品行为 Red。
6. 待完成 Requirement Traceability/Completion Audit、A1/A2 Review、Ready Check 与永久 CI；全绿后合并 main 并取得 main 新鲜验证。

# 文档影响

Docs Impact: targeted review completed，current docs update not_required。

`docs/guides/01_Figma与前端设计开发工作流.md` 已明确：Design Token 包含 `Spacing`、Figma 文件设计规范包含“间距”、正式页面视觉核对包含“间距”。新 Skill reference 进一步规定跨项目 Canvas hygiene，并明确项目已有 Design System/Guide 优先。因此继续修改 Guide 复制 24–32/64–80/96–160 等 fallback 会制造第二套需要同步的项目事实，本次不做重复文档 diff。

Blueprint 不承担具体 Figma 画布实施细则，本次不修改核心 Blueprint。

# Git / PR 状态

- base: `main@dacdaf93824bcc36d96081f287b4a3f1fc440b4d`
- branch: `docs/figma-canvas-readability-skill`
- PR: pending
- merge: pending

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# Review

## A1 需求符合性

待验证后重新从用户要求、当前 Skill 路由和 AIMA Figma Guide 重建完成定义。

## A2 代码质量与测试充分性

待验证后检查规则是否可执行、是否避免固定值覆盖项目 Design System、是否没有无关流程膨胀，以及治理测试是否覆盖关键入口。
