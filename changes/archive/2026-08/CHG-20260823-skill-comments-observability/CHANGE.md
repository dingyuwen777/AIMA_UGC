---
schema: rvc-change/v1
id: CHG-20260823-skill-comments-observability
title: 固化内部函数注释与关键日志开发规则
level: L2
status: done
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

- [x] `SKILL.md` 直接写明内部函数注释规则，不只覆盖 public/exported API。
- [x] 注释规则要求解释意图、约束、为什么、状态转换或副作用边界；简单自解释 helper 不强制写无意义注释，也不允许逐行翻译代码。
- [x] `SKILL.md` 直接写明重要功能的日志/可观测性规则：仓库已有日志能力且该功能对调试、异步运行、外部调用或后期排障有价值时，默认评估并补必要日志。
- [x] 日志规则要求复用仓库现有 logging/event 体系，选择正确级别和稳定事件名，记录已有业务/关联 ID 与阶段结果，避免 INFO 级逐条高频噪声。
- [x] 日志不得泄露 Secret、Token、密码、原始敏感 Payload/PII，不得用日志替代 PostgreSQL/业务事实，也不创建第二套 FileHandler/日志框架。
- [x] `development-workflows.md` 给出可执行的注释与日志设计细则；`verification-review.md` 在完成前 Review 检查两类要求。
- [x] AIMA Blueprint 05/06 与 Skill 新规则保持一致，不形成两套相互冲突的开发/日志规范。
- [x] 新增 Skill 自测试保护主规则、实施细则、Review 与 Blueprint 消费链；现有 Completion Gate、主 CI 与永久回归不回归。

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
| R1 | 后续 Skill 写代码时，内部函数也应有适量、有维护价值的注释 | user:internal-function-comments | satisfied | `SKILL.md` invariant 12 + plan/implementation bullets；`development-workflows.md#代码注释`；`verification-review.md` 代码质量复核；Final Ready HEAD guidance unittest 通过 |
| R2 | 重要且有调试/排障价值的功能，在仓库已有日志能力时应主动增加必要日志 | user:important-feature-logging | satisfied | `SKILL.md` invariant 13 + implementation bullet；`development-workflows.md#可观测性与日志`；Review 可观测性检查；Blueprint 05/06 同步；Final Ready HEAD guidance unittest 通过 |
| R3 | 新日志必须遵守现有日志级别、脱敏、安全和“不用日志替代业务事实”的边界 | docs/blueprint/05_日志安全部署与运维.md | satisfied | Skill/reference 明确 DEBUG/INFO/WARNING/ERROR、稳定 event/关联 ID、脱敏/Secret 禁止、日志不替代 DB/Health；Final Ready HEAD CI #2232 docs/secret gates 通过 |
| R4 | 开发治理规则应保持最小、精准，不机械制造注释、日志或新基础设施 | .agents/skills/coding/SKILL.md | satisfied | 简单自解释 helper 可不注释；无既有日志体系或无独立排障价值时不新造日志框架；禁止 INFO 逐条刷屏/重复异常；PR #162 仅治理文件，无产品批量改写 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本任务不改变用户界面或浏览器行为。 |
| Backend/API/PostgreSQL Integration | not_applicable | 本任务不改变产品后端、数据库或运行时行为。 |
| Contract / Generated Client | not_applicable | 不修改公共 Contract 或 generated client。 |
| Real Full-stack Golden Path | not_applicable | 不改变产品跨组件接线；Stage 8F #359 仅作为仓库级回归证据。 |
| Real Provider Probe | not_applicable | 不涉及外部 Provider 当前事实或付费调用。 |
| Docs / Governance / Other | required | Final Ready HEAD Completion Gate #78：3 个 guidance tests + 11 个 Ready tests 共 14/14 通过且 Ready Check success；CI #2232、Stage 8F #359、Stage 6 #229、Local Dev #55、Stage 7 Keyword #1841 / Plan #1839 / Provider #1954 / Scheduler #2181 全部 success。 |

# Completion Audit

- [x] upstream_re_read：Ready 前重新读取用户两条要求、AGENTS、当前 Skill、development/verification references 与 Blueprint 05/06，并独立重建完成定义。
- [x] change_coverage：确认“Skill 主规则 → 计划/实施细则 → Review → 自测试 → AIMA Blueprint”完整消费链覆盖两条上游要求，不依赖当前 Change 自证。
- [x] reverse_audit：从未来开发计划/实施入口反查可以读到内部注释与日志规则；从完成 Review 反查可以发现缺注释、缺关键观测、INFO 刷屏、重复异常和敏感日志；本任务无前后端反向审计边界。
- [x] unresolved_cleared：R1—R4 全部 satisfied；各测试层不适用依据明确；无 `not_satisfied` 或未解释延期。

# 两阶段 Review

## Review A1：上游要求 → 当前 Change

- 用户要求内部函数“也可以有些注释”，不是强制每个 helper 都写注释；当前规则按非显然语义/不变量/状态/副作用判断，保留简单 helper 例外。
- 用户要求重要功能在已有日志能力时增加有助调试与排障的消息；当前规则覆盖生命周期、异步、外部 I/O、Retry/部分失败/终态，并要求按排障价值选择。
- Blueprint 05 的既有安全/级别/持久事实边界必须继续成立，因此新规则没有降低脱敏，也没有把日志当业务事实。

结论：未发现上游要求遗漏或被机械扩大。

## Review A2：当前 Change → 实现 / 测试 / 文档

- Skill 主文直接暴露两条不变量，并在计划和实施阶段再次消费。
- Development reference 提供可执行判断与反模式；Verification reference 在交付前复核。
- Blueprint 05/06 将 AIMA 当前日志事实和开发约束与 Skill 对齐。
- 新 guidance unittest 防止核心规则/消费链被静默删除；现有 11 个 Ready tests 同时保持通过。
- 最终 diff 不含临时迁移脚本或临时 Workflow，也没有产品代码、Contract、Schema、Migration、依赖变化。

结论：未发现 Change 要求缺实现、缺测试或缺文档；未发现无关产品改动。

# 任务

- [x] 读取当前 AGENTS、Skill、development workflow、verification review、Blueprint 05/06 和现有 Skill test 入口。
- [x] 修改 Skill 主规则，直接加入内部注释和日志可观测性默认要求。
- [x] 扩展 `development-workflows.md`，给出注释/日志适用条件、级别、内容与反模式。
- [x] 扩展 `verification-review.md`，在代码质量 Review 检查注释与可观测性。
- [x] 同步 Blueprint 05/06。
- [x] 增加 Skill guidance unittest，保护规则消费链。
- [x] 完成 Completion Audit 与两阶段语义 Review。
- [x] Final Ready HEAD Completion Gate 与永久 CI 全绿；PR #162 转 Ready 并正常合并。

# 验证

## Final Ready HEAD `1841df954dc2b37c9ad47e6cde4517e692774872`

- Change Completion Gate #78：success；新增 3 个 guidance tests + 11 个 Ready tests 共 14/14 通过，Changed-PR Ready Check success。
- CI #2232：success；Stage 1/2/3A/Windows 全部通过，包含 Ruff、mypy、unit/contract/API、architecture/table ownership/secret scan/docs、Wheel、Frontend lint/typecheck/unit/build/Playwright。
- Stage 8F #359：success。
- Stage 6 #229：success。
- Local Dev Bootstrap #55：success。
- Stage 7 Keyword #1841、Plan #1839、Provider Config #1954、Scheduler #2181：全部 success。

## 合并

- PR：#162 `固化内部函数注释与关键日志开发规则`
- Final Ready HEAD：`1841df954dc2b37c9ad47e6cde4517e692774872`
- Merge commit：`0defa2c71b55c41627f32af2415daa9b57c53fcd`
- 合并方式：正常 PR merge；未绕过 Completion Gate、CI 或 Review 流程。

# 文档影响

- `docs/blueprint/05-日志安全部署与运维.md`：增加功能开发时选择日志观测点、噪声控制和安全边界。
- `docs/blueprint/06-开发约束与分阶段实施.md`：把内部注释与关键日志纳入实现质量和完成前 Review。

# 交付

- Branch：`chore/skill-comments-observability`
- PR：#162，已合并。
- Merge commit：`0defa2c71b55c41627f32af2415daa9b57c53fcd`。
- Change：归档于 `changes/archive/2026-08/CHG-20260823-skill-comments-observability/CHANGE.md`。
- 发布：治理/文档变更；不涉及产品部署、Contract、Schema、Migration 或依赖。
