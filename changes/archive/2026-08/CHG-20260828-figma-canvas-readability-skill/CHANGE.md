---
schema: rvc-change/v1
id: "CHG-20260828-figma-canvas-readability-skill"
title: "Coding Skill 增加 Figma 画布可读性与间距规则"
level: L2
status: done
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
- [x] PR #267 在 Ready HEAD 永久门禁全绿后转 Ready 并正常 squash merge `main`；merge 后 `main@b9902002f5be8528acc9b25f165ed3d500e283bd` 再次通过 Change Gate、CI 与 Runtime push 验证。

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
| R1 | Figma 页面内画板、注释说明等必须保持合理间距，保证画布美观与可读性，并把该要求写入 Skill | user:2026-08-28-figma-canvas-spacing | satisfied | 新增 `13_Figma设计画布与可读性规则.md`，覆盖页面、注释、画板组、分区和 Canvas-level Review；`02_跨项目研发任务路由.md` 把 Figma 任务硬路由到该 reference；Ready CI #3371 与 merge 后 main CI #3372 的 Coding governance 均通过 |
| R2 | Figma 页面/公共组件优先遵循当前项目已有 Design System/Spacing，而不是另造第二套规则 | docs/guides/01_Figma与前端设计开发工作流.md | satisfied | 新 reference 明确“项目 Design System/Token/Grid/Layout → 当前稳定模式 → fallback”的优先级；AIMA Guide 已有 Spacing Design Token 与视觉间距核对，不复制第二份固定数值表；docs check 在 Ready/main CI 均通过 |
| R3 | Detailed reference 只有命中触发条件时才加载，主 Skill 保持路由入口而不堆叠全部细则 | .agents/skills/coding/SKILL.md | satisfied | 主 Skill 强制每个任务先读取 `02_跨项目研发任务路由.md`；Figma 命中条件位于该强制路由，详细规则独立放在 `13_` reference；Coding governance 42/42 通过 |
| R4 | 完成后正常推送并合并主分支，不绕过仓库门禁 | user:2026-08-28-push-main | satisfied | PR #267 最终 Ready HEAD `ca8ecdaae9dee9a9d5b1397306672029df36afd7` 的 Change Gate #1217、CI #3371、Runtime #492 全部 success 后转 Ready并 squash merge；merge/main SHA `b9902002f5be8528acc9b25f165ed3d500e283bd`；main push Change Gate #1218、CI #3372、Runtime #493 全部 success |

# Validation Matrix

| Layer | Required | Actual Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Ready CI #3371：Coding governance 42/42 passed，包含 `test_figma_canvas_readability_guidance_is_routed_and_actionable`；merge 后 main CI #3372 再次通过同一治理回归层 |
| 接口 / Contract | not_applicable | 实现 diff 仅 Coding references/test/Change，不修改 public API/ABI/HTTP/Schema/format/generated boundary |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件运行时、进程或外部依赖；docs/governance scope 正常跳过 PostgreSQL/Repository Quality |
| 用户 / Workflow Acceptance | not_applicable | 本次改变开发治理规则而非产品用户工作流；规则路由和可执行内容由 Coding governance tests 直接验证 |
| 跨组件 Golden Path | not_applicable | 无产品跨组件接线变化 |
| 外部依赖 Probe | not_applicable | 不修改或验证 Figma API/Provider 外部协议；规则文本不需要付费或远端 Probe |
| Build / Package / Runtime | not_applicable | 不修改可执行包、Runtime、Manifest、锁文件或依赖；Ready Runtime #492 与 main Runtime #493 均按 unchanged-runtime fast-path success |
| Docs / Governance / Other | required | Ready：Change Gate #1217、CI #3371、Runtime #492 success；merge 后 main：Change Gate #1218、CI #3372、Runtime #493 success；Secret scan、`check_docs.py`、Coding governance、CI Gate 均通过 |

# 实施与验证记录

1. 读取当前 `AGENTS.md`、Coding Skill/路由/Change/Validation/Review 规则、AIMA Figma Guide 和 Coding governance tests。
2. 新增 `.agents/skills/coding/references/13_Figma设计画布与可读性规则.md`，完整表达可执行规则。
3. 在强制读取的 `02_跨项目研发任务路由.md` 增加 Figma 创建/修改/整理/模板化/状态稿/Design-to-Code 触发，保证命中时加载 `13_` reference。
4. 更新 `test_development_guidance.py`，固定路由链、Design System 优先、24–32px 注释 fallback、64–80px 同组画板 fallback、Canvas-level Review、zoom-out 和完成判定。
5. 本任务属于文档/治理规则变更，按 Coding 的 docs/config TDD 例外使用内容/引用/治理检查，不伪造产品行为 Red。
6. Draft PR #267 首轮 CI #3370：Secret/docs、Coding governance 42/42、CI Gate success；Runtime #491 fast-path success；Change Gate #1216 仅因当时 Change=`in_progress` 的 readiness 规则按设计阻塞。
7. Ready 前重新读取 `AGENTS.md`、`SKILL.md`、AIMA Figma Guide、Review Skill 与 Review references，重新审查 branch diff；没有 BLOCKER/HIGH/MEDIUM Finding。
8. 最终 Ready HEAD `ca8ecdaae9dee9a9d5b1397306672029df36afd7`：Change Completion Gate #1217、CI #3371、Runtime #492 全部 success；PR Review 记录为 NO_FINDINGS_WITHIN_SCOPE。
9. PR #267 按 expected HEAD 正常 squash merge，生成 `main@b9902002f5be8528acc9b25f165ed3d500e283bd`。
10. merge 后 main push：Change Completion Gate #1218、CI #3372、Runtime #493 全部 success；实现交付闭环完成。

# 文档影响

Docs Impact: targeted review completed，current docs update not_required。

`docs/guides/01_Figma与前端设计开发工作流.md` 已明确：Design Token 包含 `Spacing`、Figma 文件设计规范包含“间距”、正式页面视觉核对包含“间距”。新 Skill reference 进一步规定跨项目 Canvas hygiene，并明确项目已有 Design System/Guide 优先。因此继续修改 Guide 复制 24–32/64–80/96–160 等 fallback 会制造第二套需要同步的项目事实，本次不做重复文档 diff。

Blueprint 不承担具体 Figma 画布实施细则，本次不修改核心 Blueprint。

# Git / PR 状态

- implementation base: `main@dacdaf93824bcc36d96081f287b4a3f1fc440b4d`
- implementation branch: `docs/figma-canvas-readability-skill`
- final Ready HEAD: `ca8ecdaae9dee9a9d5b1397306672029df36afd7`
- implementation PR: #267 `文档：增加 Figma 画布可读性与间距规则`
- squash merge / main SHA: `b9902002f5be8528acc9b25f165ed3d500e283bd`
- production deployment: not_performed；本任务只修改研发治理 Skill，不执行生产部署

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取当前分支 `AGENTS.md`、Coding `SKILL.md`、AIMA Figma Guide、Review Skill/相关 references；独立确认用户要求是“Figma 页面内图/注释说明保持合理间距和整体美观可读，并写入 Skill”，现有 Guide 已有项目级 Spacing/视觉核对但缺少 Canvas hygiene 细则。
- [x] change_coverage：R1–R4 均已取得规则实现、治理测试、Review、Ready、merge 与 main push 证据；`not_satisfied` 与 `explicitly_deferred` 均已清零。
- [x] reverse_audit：执行 `SKILL.md → 02 强制路由 → Figma 触发 → 13 专项规则 → governance test` 反向可发现性审计，同时从 `13 → 项目 Overlay/Design System → AIMA Figma Guide` 检查优先级；规则可达且没有建立第二套项目 Spacing 事实。产品 API/DB/Runtime 反向审计不适用，因为本次没有对应边界变化。
- [x] unresolved_cleared：PR #267 无未解决 inline review thread；两阶段 Review 为 NO_FINDINGS_WITHIN_SCOPE；Ready/main CI 无规则实现失败，R1–R4 均处于 `satisfied`。

# Review

## A1 需求符合性

结论：通过，当前范围没有未解决的需求符合性 Finding。

- 用户要求的核心不是“固定一个数字”，而是每次 Figma 修改后保证页面、图、注释说明和相邻画板具有合理间距与可读性；新 `13_` reference 已把这一点写成完成门禁。
- 规则不仅覆盖注释与正式 Frame，还覆盖同组/跨组画板、历史稿/正式稿分区、内容扩展后的邻接复查、Canvas-level Review 与 zoom-out 检查，能够处理“单张图正确但整个画布很乱”的原问题类型。
- 固定数值被限定为项目无规范时的 fallback；项目已有 Design System/Spacing 时必须优先遵守，符合 Coding 的项目 Overlay 原则。
- `SKILL.md` 已强制所有任务先走 `02_跨项目研发任务路由.md`，因此把 Figma 触发写在 `02_` 并把细则放 `13_` 是实际可达的 Skill 路径，不需要在主文件复制同一规则。
- AIMA Guide 已经维护项目级 Spacing/视觉核对；不复制 fallback 数字避免第二套事实，没有文档漏同步。

## A2 代码质量与测试充分性

结论：通过，当前范围没有未解决的 BLOCKER/HIGH/MEDIUM Finding。

- 实现只修改 Coding 路由、新 Figma reference、Coding governance test 与当前 Change；没有生产代码、Contract、Migration、generated client、依赖或 Figma 资产变化。
- 新规则采用“项目 Design System 优先 + 通用 fallback”的条件结构，避免把 AIMA 当前数值或个人审美硬编码为跨项目强规则。
- 规则明确最小范围：修复当前修改直接造成的邻接问题，但禁止借 Canvas 整理扩大到无关全文件重排或擅自删除历史资产。
- Ready CI #3371 和 main CI #3372 都真实执行 Coding governance，42/42 passed；Secret scan、docs check、CI Gate 同样通过。
- 产品 E2E、PostgreSQL、Contract 或真实 Figma API Probe 对本次纯治理规则没有独立证明价值，因此按实际范围不适用。
- 容器环境此前无法解析 GitHub 域名，没有把本地未运行验证冒充通过；最终结论使用 GitHub Runner 的新鲜证据。

# 最终合并与主分支证据

- 实现 PR：#267 `文档：增加 Figma 画布可读性与间距规则`。
- 最终 Ready HEAD：`ca8ecdaae9dee9a9d5b1397306672029df36afd7`。
- Ready HEAD：Change Completion Gate `33169608249`（#1217）、CI `33169608239`（#3371）、Runtime Acceptance `33169608300`（#492），全部 completed/success。
- squash merge / main SHA：`b9902002f5be8528acc9b25f165ed3d500e283bd`。
- merge 后 main push：Change Completion Gate `33169705763`（#1218）、CI `33169705799`（#3372）、Runtime Acceptance `33169705753`（#493），全部 completed/success。
- 本任务未修改或执行生产部署、数据库迁移、依赖升级、Figma 文件写操作或真实外部 Provider Probe。
