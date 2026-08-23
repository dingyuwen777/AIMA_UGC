---
schema: rvc-change/v1
id: CHG-20260823-skill-comments-observability
title: 固化内部函数注释与关键日志开发规则
level: L2
status: in_progress
owner: chatgpt
branch: chore/skill-comments-observability
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - development-governance
  - documentation
  - observability
affected_paths:
  - .agents/skills/reliable-vibe-coding/SKILL.md
  - .agents/skills/reliable-vibe-coding/references/development-workflows.md
  - .agents/skills/reliable-vibe-coding/references/verification-review.md
  - .agents/skills/reliable-vibe-coding/tests/
  - docs/blueprint/05-日志安全部署与运维.md
  - docs/blueprint/06-开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 目标

把两条后续开发默认规则固化到仓库的 Reliable Vibe Coding Skill：对非显然的内部/private/helper 函数提供有维护价值的注释或 docstring；对已有日志基础设施且重要、需要调试或运维排障的功能主动设计并增加必要的结构化日志。规则必须能被后续开发流程读取、在 Review 时复核，并避免机械注释和日志噪声。

# 成功标准

- [ ] `SKILL.md` 直接写明内部函数注释规则，不只覆盖 public/exported API。
- [ ] 注释规则要求解释意图、约束、为什么、状态转换或副作用边界；简单自解释 helper 不强制写无意义注释，也不允许逐行翻译代码。
- [ ] `SKILL.md` 直接写明重要功能的日志/可观测性规则：仓库已有日志能力且该功能对调试、异步运行、外部调用或后期排障有价值时，默认评估并补必要日志。
- [ ] 日志规则要求复用仓库现有 logging/event 体系，选择正确级别和稳定事件名，记录已有业务/关联 ID 与阶段结果，避免 INFO 级逐条高频噪声。
- [ ] 日志不得泄露 Secret、Token、密码、原始敏感 Payload/PII，不得用日志替代 PostgreSQL/业务事实，也不创建第二套 FileHandler/日志框架。
- [ ] `development-workflows.md` 给出可执行的注释与日志设计细则；`verification-review.md` 在完成前 Review 检查两类要求。
- [ ] AIMA Blueprint 05/06 与 Skill 新规则保持一致，不形成两套相互冲突的开发/日志规范。
- [ ] 新增 Skill 自测试，防止核心规则、实施细则或 Review 门禁以后被误删；现有 Completion Gate 与全量 CI 不回归。

# 范围

- Reliable Vibe Coding Skill 的主规则、开发工作流和 Review 规则。
- 针对规则存在性的轻量自测试。
- AIMA 开发约束与日志运维 Blueprint 的必要同步。

# 非目标

- 不批量给现有所有内部函数补注释。
- 不批量给现有所有业务代码新增日志。
- 不要求每个内部函数都必须有 docstring，也不要求每个函数都打印日志。
- 不修改产品业务逻辑、HTTP Contract、Schema、Migration、依赖或日志 Formatter 实现。
- 不引入新的日志库、Tracing 平台或外部 Observability 服务。

# 必须保持不变

- 仍坚持最小、精准、兼容，不为形式上的“注释完整率”制造冗余文字。
- 仍使用仓库已有 logging/log_event/Formatter/Secret 脱敏边界；业务模块不创建第二套 FileHandler。
- DEBUG/INFO/WARNING/ERROR 的现有级别语义保持不变。
- 日志只能辅助解释“为什么/在哪一步失败”，不能替代数据库持久事实、Health 或业务状态。

# 关键决策

- 注释采取“有认知价值才写”的规则：内部函数只要包含非显然业务规则、关键不变量、状态机、算法取舍、副作用边界、容错/兼容原因，就应有简短 docstring 或定点 inline comment；简单 getter/wrapper/自解释 helper 可以不写。
- 日志采取“按排障价值选择观测点”的规则：重要生命周期、外部 I/O、异步任务阶段、重试/部分失败/终态等优先记录；高频正常细节放 DEBUG 或不记，避免日志洪泛。
- 规则同时进入 Skill 主文、实施 reference 和 Review reference，并用自测试保护，确保不是只写一篇普通说明文档。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 后续 Skill 写代码时，内部函数也应有适量、有维护价值的注释 | user:internal-function-comments | not_satisfied | 待固化到 Skill 主规则、开发细则和 Review |
| R2 | 重要且有调试/排障价值的功能，在仓库已有日志能力时应主动增加必要日志 | user:important-feature-logging | not_satisfied | 待固化到 Skill 主规则、开发细则和 Review |
| R3 | 新日志必须遵守现有日志级别、脱敏、安全和“不用日志替代业务事实”的边界 | docs/blueprint/05-日志安全部署与运维.md | not_satisfied | 待同步细则并由 Skill 自测试/文档检查保护 |
| R4 | 开发治理规则应保持最小、精准，不机械制造注释、日志或新基础设施 | .agents/skills/reliable-vibe-coding/SKILL.md | not_satisfied | 待在新规则中显式保留例外和反模式 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本任务不改变用户界面或浏览器行为。 |
| Backend/API/PostgreSQL Integration | not_applicable | 本任务不改变产品后端、数据库或运行时行为。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract 或 generated client。 |
| Real Full-stack Golden Path | not_applicable | 不改变产品跨组件接线；现有永久 CI 仅作为仓库回归。 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider 当前事实或付费调用。 |
| Docs / Governance / Other | required | Skill 主规则、两个 reference、Blueprint 05/06 与新增 unittest；Change Completion Gate + 主 CI/永久回归。 |

# Completion Audit

- [ ] upstream_re_read：进入 Ready 前重新读取用户两条要求、AGENTS、Skill、开发/Review reference 与 Blueprint 05/06。
- [ ] change_coverage：确认“主规则 → 实施细则 → Review → 自测试 → AIMA 文档”完整消费链覆盖两条上游要求。
- [ ] reverse_audit：从后续开发执行反查能否读到规则，从完成 Review 反查能否发现缺失注释/日志或日志过度；无前后端反向审计边界。
- [ ] unresolved_cleared：R1—R4 全部满足，无未解释延期或占位。

# 任务

- [x] 读取当前 AGENTS、Skill、development workflow、verification review、Blueprint 05/06 和现有 Skill test 入口。
- [ ] 修改 Skill 主规则，直接加入内部注释和日志可观测性默认要求。
- [ ] 扩展 `development-workflows.md`，给出注释/日志适用条件、级别、内容与反模式。
- [ ] 扩展 `verification-review.md`，在代码质量 Review 检查注释与可观测性。
- [ ] 同步 Blueprint 05/06。
- [ ] 增加 Skill guidance unittest，保护规则消费链。
- [ ] 完成 Completion Audit、Review、Ready Check 和全部永久 CI。

# 验证

## 计划

- 目标测试：`python -m unittest discover .agents/skills/reliable-vibe-coding/tests -v`
- 文档/架构：主 CI `check_docs.py` 与现有仓库质量门禁。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`
- 相关回归：Change Completion Gate、主 CI 以及本 PR 自动触发的永久 Stage Workflow。

## 新鲜证据

- 尚未执行。

# 文档影响

- `docs/blueprint/05-日志安全部署与运维.md`
- `docs/blueprint/06-开发约束与分阶段实施.md`

# 交付

- Branch：`chore/skill-comments-observability`
- PR：待创建
- 发布：治理/文档变更；不涉及产品部署。
