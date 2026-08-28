---
schema: rvc-change/v1
id: "CHG-20260828-migrate-figma-canvas-rules"
title: "将 Figma 画布可读性规则迁移到 Figma Skill"
level: L2
status: done
owner: "chatgpt"
branch: "docs/migrate-figma-canvas-rules-to-figma-skill"
created: 2026-08-28
updated: 2026-08-28
completion_gate: required
depends_on: []
affected_areas:
  - "coding-skill"
  - "figma-skill"
  - "tests"
affected_paths:
  - ".agents/skills/coding/references/02_跨项目研发任务路由.md"
  - ".agents/skills/coding/references/12_规则保留映射.md"
  - ".agents/skills/coding/references/13_Figma设计画布与可读性规则.md"
  - ".agents/skills/coding/tests/test_development_guidance.py"
  - ".agents/skills/figma/SKILL.md"
  - ".agents/skills/figma/references/07_页面布局与真实可用性审计.md"
contracts: []
data_changes: []
---

# 目标

把错误归属于 Coding Skill 的 Figma Canvas / Annotation / Spacing 详细设计规则迁移到 Figma Skill，使职责边界变为：

```text
Coding
→ 识别 Figma 任务并硬路由到 Figma Skill
→ 继续负责 Change / TDD / Review / CI / Git / 代码交付

Figma
→ 负责页面、Canvas、Frame、Section、Spacing、Annotation、Prototype、Design System 与 Design-to-Code 设计基线
```

迁移采用内容守恒：原 Coding `13_Figma设计画布与可读性规则.md` 的触发、fallback、Annotation、画板组织、Canvas-level Review、邻接修复边界、禁止事项和完成判定全部迁入 Figma Skill 的 canonical 规则，不保留第二套 Coding 正文。

# 成功标准

- [x] Coding `02_跨项目研发任务路由.md` 不再维护 Figma 设计细则或指向 Coding `13_`，同仓存在 Figma Skill 时硬路由到 `.agents/skills/figma/SKILL.md`。
- [x] 删除 `.agents/skills/coding/references/13_Figma设计画布与可读性规则.md`，消除 Coding/Figma 双事实源。
- [x] `figma/SKILL.md` 明确页面/Canvas 视觉修改和 `baseline-ready` 使用 Figma `07_页面布局与真实可用性审计.md`，Figma 写操作后执行 Canvas-level Review。
- [x] `figma/references/07_页面布局与真实可用性审计.md` 完整承载原 Coding `13_` 的 Canvas/Spacing/Annotation 可执行语义，并与既有页面布局、图片、标注、滚动和真实可用性规则合并。
- [x] `12_规则保留映射.md` 记录 Figma Skill/`07_` 为 canonical 位置，并明确 Coding 不得恢复第二套 Figma 设计规则。
- [x] Governance regression 验证 `Coding → Figma Skill → Figma 07` 可达、旧 `13_` 已删除、关键 fallback 与 Canvas Review 仍存在。
- [x] 不修改产品运行代码、HTTP Contract、数据库、Migration、generated client、依赖或 Figma 文件本身。
- [x] PR #269 在 Ready HEAD 永久门禁成功后正常 squash merge `main`；merge 后 `main@480e331fbdcf7b0b9f12407f52b8b406c5b1d403` 的 Change Gate #1223、CI #3377、Runtime Acceptance #498 全部成功。

# 范围与非目标

范围：Coding/Figma Skill 职责迁移、规则内容守恒、治理测试与本 Change。

非目标：不重新设计 Figma 产品规则；不改变 AIMA 产品页面或 Figma 文件；不新增设计工具、依赖、像素级视觉回归或项目专属 Spacing Token；不把 Coding 的 Change/TDD/Git/CI/Release 规则复制到 Figma Skill。

# 必须保持不变

- Coding 仍是 AIMA 仓库研发、Change、验证、Review、CI、Git 和交付统一入口。
- Figma Skill 不复制 Coding 的 Change/TDD/Git/CI/Release 规则；有仓库时继续遵守上位 `AGENTS.md` 和 Coding 工作流。
- 项目已有 Design System / Spacing Token / Grid / Layout Guideline 的优先级高于通用 fallback。
- Figma 示例与 Annotation 不能成为 API/数据库/Provider 的机器事实。
- 历史/废弃/备份 Figma 资产不能因 Canvas 整理被静默删除。
- 旧 Coding `13_` 的规则迁移必须内容守恒，不因“精简”丢失触发、例外、失败、验证或完成语义。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 将 Figma Canvas/注释/间距详细要求迁移到 Figma Skill，Coding 不再作为详细规则 Owner | user:2026-08-28-migrate-figma-skill | satisfied | Coding `02_` 已改为 Figma Skill hard route；旧 Coding `13_` 已删除；Figma `SKILL.md` + `07_` 成为 canonical 事实源；governance test 已验证 |
| R2 | Figma Skill 负责 Figma 页面尺寸、布局、间距、图片与标注、Prototype、Design-to-Code 设计工作流 | .agents/skills/figma/SKILL.md | satisfied | Figma Skill 已明确 Canvas/Spacing/Annotation 责任，并把视觉写操作与 baseline-ready 路由到 `07_页面布局与真实可用性审计.md` |
| R3 | Skill 重组必须内容守恒，移动规则不得丢失触发、例外、失败、验证和兼容语义 | .agents/skills/coding/SKILL.md | satisfied | Ready 前逐节对照 base `main@f3524b...` 的旧 Coding `13_` 与当前 Figma `07_`；Design System 优先、4px fallback、页面间距、24–32px Annotation、40–64/64–80/96–160px 画板、分区、Canvas-level Review、真实几何、邻接范围、禁止项和完成判定均保留；`12_` 固化映射 |
| R4 | Coding 只负责 Figma 任务的研发路由，不维护第二套 Figma 设计细则 | .agents/skills/coding/references/02_跨项目研发任务路由.md | satisfied | `02_` 明确同仓存在 Figma Skill 时必须进入 Figma Skill，并明确 Coding 不维护第二套 Figma 设计细则；治理回归测试通过 |
| R5 | 完成后不得绕过 Change/Review/CI/PR，正常合并 `main` | AGENTS.md | satisfied | PR #269 已 squash merge，merge SHA `480e331fbdcf7b0b9f12407f52b8b406c5b1d403`；merge 后 main push 的 Change Gate #1223、CI #3377、Runtime #498 全部 success |

# Validation Matrix

| Layer | Required | Actual Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | PR #269 治理回归：`python3 -m unittest discover .agents/skills/coding/tests -v` 共 42/42 passed；`test_figma_canvas_readability_guidance_is_owned_by_figma_skill` passed |
| 接口 / Contract | not_applicable | diff 仅 Skill/reference/test/Change，不修改 public API/ABI/HTTP/Schema/generated boundary |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件运行时、进程或外部依赖；CI scope 正常跳过 PostgreSQL/Repository Quality |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品用户工作流；本次改变 Agent 设计工作流的规则归属 |
| 跨组件 Golden Path | not_applicable | 无产品跨组件接线变化 |
| 外部依赖 Probe | not_applicable | 不需要访问 Figma API/Provider 来证明仓库规则迁移；未修改 Figma 文件 |
| Build / Package / Runtime | not_applicable | 不修改 Runtime、Manifest、lock 或 artifact；Runtime workflow 使用 unchanged-runtime fast-path |
| Docs / Governance / Other | required | Ready HEAD `301037a48ac51fdca962f03146617d44627a1c65` 的 Change Gate #1222、CI #3376、Runtime #497 全部 success；merge 后 `main@480e331f...` 的 Change Gate #1223、CI #3377、Runtime #498 全部 success |

# 实施与验证记录

1. 从 `main@f3524b679dfa3c9bfc65ebf1e3b7376935e07fa9` 重新读取 `AGENTS.md`、Coding/Figma Skill、旧 Coding `13_`、Figma `07_`、规则保留映射和治理测试。
2. Coding `02_` 改为同仓 Figma Skill 硬路由；同仓没有 Figma Skill 时退回项目设计 Guide/宿主 Figma 工具规则，不假设 Coding 内置视觉规范。
3. 原 Coding `13_` 的全部设计语义合并进 Figma `07_`，Figma `SKILL.md` 强化 review-and-fix、baseline-ready、Annotation 和写后 Canvas-level Review。
4. 删除 Coding `13_`；`12_规则保留映射.md` 记录当前 canonical 位置及内容守恒清单。
5. 更新治理测试，明确断言旧 `13_` 不存在、Coding 路由可达 Figma Skill、Figma `07_` 保留关键 fallback/Canvas Review/完成判定。
6. Draft PR #269 首轮：CI #3375 success；Coding governance 42/42 passed；Runtime #496 fast-path success；Change Gate #1221 的门禁测试成功，readiness 因 `in_progress` 按设计阻塞。
7. Ready 前重新读取当前分支 `AGENTS.md`、Coding `SKILL.md`、Figma `SKILL.md`/`07_`、迁移前 base 的旧 Coding `13_`、Review Skill/执行/Findings/测试专家规则，并读取 PR #269 实际 diff；完成 A1/A2 Review，结论 `NO_FINDINGS_WITHIN_SCOPE`。
8. Ready HEAD `301037a48ac51fdca962f03146617d44627a1c65` 的 Change Completion Gate #1222、CI #3376、Runtime Acceptance #497 全部 success；PR 随后转 Ready 并正常 squash merge。
9. PR #269 merge SHA 为 `480e331fbdcf7b0b9f12407f52b8b406c5b1d403`；merge 后 main push：Change Completion Gate #1223、CI #3377、Runtime Acceptance #498 全部 success。

# 文档影响

Docs Impact: targeted review completed，current product-guide update not_required。

`docs/guides/01_Figma与前端设计开发工作流.md` 继续作为 AIMA 项目级 Design System/Spacing/Design-to-Code Overlay；本次改变的是通用 Skill 规则 Owner，不改变 AIMA 产品或前后端事实。把跨项目 fallback 再复制进 Guide 会重新形成第二套项目间距正文，因此不增加重复文档 diff。

# Git / PR 状态

- base: `main@f3524b679dfa3c9bfc65ebf1e3b7376935e07fa9`
- branch: `docs/migrate-figma-canvas-rules-to-figma-skill`
- Ready HEAD: `301037a48ac51fdca962f03146617d44627a1c65`
- PR: #269 `文档：将 Figma 画布规则迁移到 Figma Skill`，已 squash merge
- implementation main SHA: `480e331fbdcf7b0b9f12407f52b8b406c5b1d403`
- merge 后 main push gates: Change #1223 / CI #3377 / Runtime #498，全部 success
- archive: 通过独立 docs-only PR 移入 `changes/archive/2026-08/`

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取当前分支 `AGENTS.md`、Coding Skill、Figma Skill/`07_`、Review Skill；并读取 base `main@f3524b...` 的旧 Coding `13_` 作为迁移前语义基线。独立重建完成定义为“详细规则归 Figma、Coding 只路由、内容不丢、正常 PR/CI/merge main”。
- [x] change_coverage：R1–R5 全部进入 Change。迁移/Owner/内容守恒/唯一事实源和主分支交付均已满足。
- [x] reverse_audit：正向验证 `Coding SKILL → Coding 02 → .agents/skills/figma/SKILL.md → Figma 07`；反向验证 Figma `07_` 的 Canvas/Spacing/Annotation 细则不再依赖 Coding `13_`，治理测试同时断言旧文件不存在。产品 API/DB/Runtime 反向审计不适用，因为本次无对应变化。
- [x] unresolved_cleared：治理测试、Docs/CI Gate、Ready Change Gate 和 merge 后 main push gates 全部成功；R1–R5 全部 satisfied，无未解决 BLOCKER/HIGH/MEDIUM Finding。

# Review

## A1 需求符合性

结论：`NO_FINDINGS_WITHIN_SCOPE`。

- 用户明确要求把上一轮规则迁移到 Figma Skill 并最终合并 main；详细设计规则已经从 Coding `13_` 移出，Coding 只保留 Figma Skill hard route。
- 迁移后的 Figma Skill 能独立承担页面、Canvas、Spacing、Annotation、Prototype 与 Design-to-Code 设计责任，不再依赖 Coding 中的隐藏视觉 reference。
- `12_规则保留映射.md` 明确 canonical 位置和不可恢复第二套 Coding 规则的约束，降低后续维护漂移风险。
- PR #269 已正常合并 main，并有 merge 后 main push 新鲜验证。

## A2 质量与测试充分性

结论：`NO_FINDINGS_WITHIN_SCOPE`。

逐项对照迁移前旧 Coding `13_` 与当前 Figma `07_`：

- Design System / Token / Grid / Layout 优先级与 4px fallback 保留；
- 页面内部 4–8、6–8、12–16、20–24、24–32、32–48px fallback 保留；
- Annotation 与正式 Frame 边界、24–32px fallback、长说明容器和内容增长后邻接复查保留；
- 连续状态稿 40–64、同组 64–80、跨组 96–160px fallback、对齐与阅读顺序保留；
- 正式/状态/探索/说明/组件 Demo/历史/废弃分区和“整理不等于删除历史”保留；
- 每次写操作后的 Frame/Section/相邻画板/Annotation/zoom-out Canvas-level Review、真实几何优先与截图精度限制保留；
- 当前修改直接造成的邻接问题属于最小修复范围，同时禁止无边界重排整个文件；
- 禁止随机间距、只看单 Node、只看局部、另造 spacing、静默删历史、把 Figma 示例当机器事实等失败边界保留；
- 页面内部正确但 Canvas 仍拥挤、贴边、遮挡或归属不清时不得声明完成的终止条件保留。

治理测试直接断言跨 Skill 路由、旧文件删除和关键语义；merge 后 main CI #3377 继续成功。没有产品代码、Contract、DB、依赖或 Figma 文件变化，因此 Browser/PostgreSQL/Full-stack/Provider Probe 对本任务没有独立证明价值。
