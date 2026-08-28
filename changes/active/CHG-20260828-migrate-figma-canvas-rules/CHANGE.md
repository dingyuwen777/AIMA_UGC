---
schema: rvc-change/v1
id: "CHG-20260828-migrate-figma-canvas-rules"
title: "将 Figma 画布可读性规则迁移到 Figma Skill"
level: L2
status: in_progress
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

把当前错误归属于 Coding Skill 的 Figma Canvas / Annotation / Spacing 详细设计规则迁移到 Figma Skill，使职责边界变为：

```text
Coding
→ 识别 Figma 任务并硬路由到 Figma Skill
→ 继续负责 Change / TDD / Review / CI / Git / 代码交付

Figma
→ 负责页面、Canvas、Frame、Section、Spacing、Annotation、Prototype、Design System 与 Design-to-Code 设计基线
```

迁移必须内容守恒：上一版 `13_Figma设计画布与可读性规则.md` 中已经固化的 Design System 优先、4px fallback、页面语义间距、注释安全距离、画板组间距、正式/历史/废弃分区、Canvas-level Review、zoom-out、邻接修复边界、禁止事项和完成判定不能因重组而丢失。

# 成功标准

- [ ] Coding `02_跨项目研发任务路由.md` 不再维护 Figma 设计细则或指向 Coding `13_`，而是在同仓存在 Figma Skill 时硬路由到 `.agents/skills/figma/SKILL.md`。
- [ ] 删除 `.agents/skills/coding/references/13_Figma设计画布与可读性规则.md`，避免 Coding 与 Figma 形成两套设计规范事实源。
- [ ] `figma/SKILL.md` 明确：涉及 Figma 页面/Canvas 的创建、修改、整理、审查或 baseline-ready 时，必须读取 `07_页面布局与真实可用性审计.md`，写操作后必须执行 Canvas-level Review。
- [ ] `figma/references/07_页面布局与真实可用性审计.md` 完整承载原 Coding `13_` 的全部可执行 Canvas/Spacing/Annotation 语义，并与既有页面布局、图片、标注、滚动、真实可用性规则自然合并。
- [ ] `12_规则保留映射.md` 记录旧 Coding `13_` → Figma Skill/`07_` 的 canonical 迁移关系，明确不得恢复第二套 Coding Figma 细则。
- [ ] Governance regression 验证 `Coding → Figma Skill → Figma 07` 的可达路由、旧 `13_` 已删除、关键 fallback 与 Canvas Review 语义仍存在。
- [ ] 不修改产品运行代码、HTTP Contract、数据库、Migration、generated client、依赖或 Figma 文件本身。
- [ ] PR 适用 Change Gate / Docs & Governance / CI / Runtime fast-path 全绿，经 Review 后正常 squash merge `main`，再验证 merge 后 `main` 并独立归档 Change。

# 范围与非目标

范围：Coding/Figma Skill 职责迁移、规则内容守恒、治理测试与当前 Change。

非目标：不重新设计 Figma 规则；不改变 AIMA 产品页面；不修改 Figma 文件；不新增新的设计工具、依赖、像素级视觉回归或项目专属 Spacing Token；不把 Figma 的 Git/CI/代码研发规则复制到 Figma Skill。

# 必须保持不变

- Coding 仍是 AIMA 仓库研发、Change、验证、Review、CI、Git 和交付的统一入口。
- Figma Skill 不复制 Coding 的 Change/TDD/Git/CI/Release 规则；有仓库时继续遵守上位 `AGENTS.md` 和 Coding 工作流。
- 项目已有 Design System / Spacing Token / Grid / Layout Guideline 的优先级始终高于通用 fallback 数值。
- Figma 示例与 Annotation 不能成为 API/数据库/Provider 的机器事实。
- 历史/废弃 Figma 资产不能因 Canvas 整理被静默删除。
- 旧 Coding `13_` 的规则语义迁移后必须全部可追溯，不能为了精简删掉触发条件、例外、失败行为或完成判定。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 将 Figma Canvas/注释/间距要求从 Coding Skill 迁移到 Figma Skill，并推送合并主分支 | user:2026-08-28-migrate-figma-skill | not_satisfied | 待完成跨 Skill 迁移、PR/CI/Review/merge/main 验证 |
| R2 | Figma Skill 是 Figma 页面尺寸、布局、间距、图片与标注、Prototype、Design-to-Code 的设计工作流 Owner | .agents/skills/figma/SKILL.md | not_satisfied | 当前 Skill 已声明该职责；待把 Canvas 详细规则合并到其 `07_` reference 并补完成门禁 |
| R3 | Skill 重组必须内容守恒，移动规则时不得丢失触发、例外、失败、验证和兼容语义 | .agents/skills/coding/SKILL.md | not_satisfied | 待按 `12_规则保留映射.md` 逐项迁移旧 Coding `13_` 语义 |
| R4 | Coding 只负责 Figma 任务的研发路由，不维护第二套 Figma 设计细则 | .agents/skills/coding/references/02_跨项目研发任务路由.md | not_satisfied | 待将当前 `13_` 路由改为 Figma Skill hard route |
| R5 | 完成后不得绕过 Change/Review/CI/PR，正常合并 `main` | AGENTS.md | explicitly_deferred | 实现和 Ready 门禁完成后按 PR → CI/Review → squash merge → main push 验证顺序执行 |

# Validation Matrix

| Layer | Required | Planned Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 更新 Coding governance test，断言 `Coding → Figma Skill → Figma 07` 路由、旧 `13_` 不存在及关键规则内容守恒 |
| 接口 / Contract | not_applicable | 不修改 public API/ABI/HTTP/Schema/生成物 |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不修改数据库、文件运行时、进程或外部依赖 |
| 用户 / Workflow Acceptance | not_applicable | 不改变 AIMA 产品用户工作流；本次是 Agent 设计工作流治理迁移 |
| 跨组件 Golden Path | not_applicable | 无产品跨组件接线变化 |
| 外部依赖 Probe | not_applicable | 不需要调用 Figma API/Provider 来证明仓库规则迁移 |
| Build / Package / Runtime | not_applicable | 不修改 Runtime、Manifest、锁文件或可执行 Artifact；Runtime workflow 仅按仓库 scope fast-path 判定 |
| Docs / Governance / Other | required | Secret/docs gate、Coding governance tests、Change Completion Gate、CI Gate、A1/A2 Review、PR/main push evidence |

# 实施计划

1. 从当前 `main` 重新读取 `AGENTS.md`、Coding/Figma Skill、旧 Coding `13_`、Figma `07_`、规则保留映射和治理测试。
2. 修改 Coding `02_`：Figma 创建/修改/整理/审查/Design-to-Code 在同仓存在 Figma Skill 时硬路由到 Figma Skill；删除 Coding 设计细则入口。
3. 合并旧 Coding `13_` 的完整语义到 Figma `07_`，并在 Figma `SKILL.md` 强化写后 Canvas-level Review / baseline-ready 门禁。
4. 删除 Coding `13_`，同步 `12_规则保留映射.md` 记录 canonical 迁移。
5. 更新治理测试，证明新路由和规则内容守恒；本任务为规则迁移，采用文档/治理 TDD 例外，不伪造产品行为 Red。
6. 完成 Completion Audit、A1/A2 Review、Ready Check 与永久 CI；全绿后合并 `main`，验证 merge 后 main，再通过独立 docs-only PR 归档 Change。

# 文档影响

Docs Impact: targeted，范围限 Skill 自身及规则保留映射。`docs/guides/01_Figma与前端设计开发工作流.md` 已维护 AIMA 项目级 Design System/Spacing/Design-to-Code Overlay，本次不改变项目级产品事实，不需要复制跨项目 Canvas 细则。

# Git / PR 状态

- base: `main@f3524b679dfa3c9bfc65ebf1e3b7376935e07fa9`
- branch: `docs/migrate-figma-canvas-rules-to-figma-skill`
- PR: pending
- merge: pending

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# Review

## A1 需求符合性

待实现完成后，重新从本轮用户要求、当前 Coding/Figma Skill 职责和规则保留门禁独立重建完成定义。

## A2 质量与测试充分性

待实现完成后，逐项核对旧 Coding `13_` 的规则是否全部迁移、是否真正消除第二事实源、治理测试是否验证新 canonical 路由，且没有把 Coding Git/CI 规则复制进 Figma Skill。
