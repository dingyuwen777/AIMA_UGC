---
schema: rvc-change/v1
id: CHG-20260823-testing-strategy-governance
title: 固化 Browser Mock 与真实链路分层测试策略
level: L2
status: done
owner: chatgpt
branch: chore/testing-strategy-governance
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
depends_on: []
affected_areas:
  - development-workflow
  - testing
  - review
  - documentation
affected_paths:
  - AGENTS.md
  - .agents/skills/reliable-vibe-coding/SKILL.md
  - .agents/skills/reliable-vibe-coding/references/testing-strategy.md
  - .agents/skills/reliable-vibe-coding/references/change-management.md
  - .agents/skills/reliable-vibe-coding/references/completion-gate.md
  - .agents/skills/reliable-vibe-coding/references/verification-review.md
  - .agents/skills/reliable-vibe-coding/assets/CHANGE.template.md
  - docs/blueprint/06-开发约束与分阶段实施.md
contracts: []
data_changes: []
---

# 目标

把已经确认的测试分层原则固化成仓库长期开发规则：Browser Mock Acceptance 负责广覆盖用户可见行为；Backend/API/PostgreSQL Integration 负责服务器业务规则和持久化；Contract 保证 Pydantic/OpenAPI/generated client 一致；Real Full-stack 只保留少量关键 Golden Path 证明真实链路接通；Real Provider Probe 仅在必要时有界执行。后续 Agent 在涉及用户可见、前后端、异步、Provider 或正式 Stage 的任务中应主动读取并据此制定验证计划，不依赖用户重复提醒。

# 成功标准

- [x] `AGENTS.md` 增加仓库级测试分层硬规则，并导航到详细测试策略。
- [x] Reliable Vibe Coding 增加 `testing-strategy.md`，明确每层“证明什么 / 不能证明什么 / 何时使用 / 默认覆盖宽度”。
- [x] Skill 的任务规划、实施和 Completion Audit 要求按任务边界建立 Validation Matrix，而不是把所有场景都塞进 Real Full-stack。
- [x] `CHANGE.template.md` 增加 Validation Matrix，要求 L2/L3 明确 Browser Mock、Backend Integration、Contract、Real Full-stack、Real Provider Probe 的 `required/not_applicable` 及证据。
- [x] Change 管理、Completion Gate 和 Verification Review 同步 Validation Matrix 语义。
- [x] Blueprint 06 把泛化 `E2E` 分层扩展为 AIMA 的正式长期测试策略，明确 Browser Mock 与 Real Full-stack 不是同一种证据。
- [x] 保持现有 Stage 8F Full-stack、generated client、PostgreSQL Integration 和 Provider 有界 Probe 机制，不降低现有质量门禁。
- [x] 不修改产品业务代码、HTTP Contract、Schema/Migration、依赖或运行时行为。
- [x] 实现 PR #155 最终 HEAD 的 8 个永久 Workflow 全部成功并正常合并到 `main`。

# 范围

- 开发治理、测试策略、Review/Completion Audit 规则和 Change 模板。
- 只固化测试职责与选择机制，不重写现有业务测试用例。

# 非目标

- 不把所有用户行为改造成真实 Full-stack 测试。
- 不要求所有任务机械执行全部五层；不适用层必须说明依据。
- 不让 Browser Mock 冒充真实后端、数据库、Worker 或 Provider 端到端证明。
- 不新增测试框架、第三方依赖或新的产品运行组件。

# 必须保持不变

- Pydantic → OpenAPI → Orval generated client 是前后端 Contract 唯一生成链。
- 真正数据库行为继续使用 PostgreSQL Integration，不用 SQLite 替代。
- Stage 8F Real Full-stack Acceptance 继续作为真实链路 Golden Path。
- 真实 TikHub/其他外部 Provider Probe 默认不进入普通 CI，继续受费用、稳定性和 Secret 边界约束。
- Completion Gate 的 Requirement Traceability / Ready Check 语义保持不变。

# 关键决策

用户明确确认采用分层方案并要求固化到仓库，使后续 Agent 每次开发能自动读取并实施。默认原则：

```text
Browser Mock Acceptance → 用户可见行为和状态的最宽覆盖
Backend/API/PostgreSQL Integration → 服务器规则、事务、持久化、Worker
Contract → Pydantic/OpenAPI/generated client 一致性
Real Full-stack → 少量关键 Golden Path，只证明系统真实接通
Real Provider Probe → 极少、有界、必要时执行，不作为普通回归主力
```

测试数量不按固定配额机械分配；由行为边界和风险决定。用户可见状态复杂时优先扩 Browser Mock，而不是复制成大量昂贵 Full-stack 场景。

Validation Matrix 是“风险 → 证据”的语义计划，不要求 `ready_check.py` 判断测试是否充分；机器门禁继续只做结构、状态、Source、占位符和 Audit checkbox 检查，具体测试层选择由 Agent/Reviewer 在 Completion Audit 和 Review 中复核。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Browser Mock 应作为用户可见行为/状态的广覆盖验收主力，但不能声称证明真实后端链路 | user:testing-strategy-confirmation | satisfied | `testing-strategy.md` §1、`AGENTS.md` §12、Blueprint 06 §11.6 均明确 Browser Mock 证明范围与不能证明的下游边界 |
| R2 | Backend Integration、Contract、Real Full-stack、Real Provider Probe 必须各自有清晰证明边界和成本定位 | user:testing-strategy-confirmation | satisfied | `testing-strategy.md` §2—5；Blueprint 06 §11.2—11.8；Verification Review 证据表区分各层证据等级 |
| R3 | 后续 Agent 应在每次相关任务中自行读取并实施该策略，不依赖用户重复提醒 | user:testing-strategy-confirmation | satisfied | `AGENTS.md` 导航与 §12；`SKILL.md` 不变量 #11、按需读取、步骤 6—10 均要求相关任务读取 `testing-strategy.md` 并维护 Validation Matrix |
| R4 | L2/L3 Change 应通过 Validation Matrix 明确适用测试层与证据，Completion Audit/Review 必须检查 | user:testing-strategy-confirmation | satisfied | `CHANGE.template.md` 新增 Validation Matrix；`change-management.md`、`completion-gate.md`、`verification-review.md` 均把矩阵纳入 Ready/Review/归档语义 |
| R5 | 新策略必须与当前 PostgreSQL Integration、generated client 和 Stage 8F Real Full-stack 事实兼容 | docs/blueprint/06_开发约束与分阶段实施.md | satisfied | 实现 PR #155 最终 HEAD `ea1814e8e1162f77e0a0561382e3e9c9aafa210f` 的 CI #2174、Stage 8F #301、Stage 6 #172、Stage 7 四个专项和 Completion Gate #20 全部成功 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 只修改开发治理文档，不改变用户页面行为；现有 Browser Mock 仅作为策略事实示例 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务行为、事务或持久化；最终主 CI/Stage 6/Stage 7 回归成功确认既有门禁未受影响 |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract、OpenAPI 或 generated client；最终主 CI #2174 的 generated contracts/client 漂移检查成功 |
| Real Full-stack Golden Path | not_applicable | 不修改真实业务链；Stage 8F Full-stack #301 成功作为既有 Golden Path 兼容回归，而非本 Change 新业务行为证据 |
| Real Provider Probe | not_applicable | 不修改 Provider endpoint、字段、分页、Capability 或费用事实；没有产生真实付费请求 |
| Docs / Governance / Other | required | `AGENTS.md` → Skill → `testing-strategy.md` → Change 模板 → Completion/Review → Blueprint 06 规则链；Completion Gate #20 与主 CI #2174 成功 |

# Completion Audit

- [x] upstream_re_read：重新读取用户确认、`AGENTS.md`、Reliable Vibe Coding Skill/Change/Completion/Review、Change 模板、Blueprint 06，以及现有 Browser Mock 和 Stage 8F Full-stack 事实，独立重建完成定义。
- [x] change_coverage：按“自动入口 → 详细策略 → Change 计划 → Completion/Review → AIMA 长期 Blueprint”核对 R1—R5，没有把当前 Change 当需求全集，也没有遗漏证据边界。
- [x] reverse_audit：从消费者反向确认 `AGENTS.md` 首读、Skill 自动导航、Change 模板建立 Validation Matrix、Completion/Verification 消费矩阵、Blueprint 06 保存长期事实；不设固定测试数量，不机械强制五层，不允许 Mock 冒充真实链。
- [x] unresolved_cleared：R1—R5 均 `satisfied`；无 `not_satisfied`、未批准延期或无依据不适用。

# 两阶段 Review

## Review A1：上游要求 → Change

从用户确认目标独立检查：需要固化测试分工、保证后续 Agent 自动读取、把分层落到 Change/Completion Review，而不是只写普通说明文档。R1—R5 完整覆盖，没有 requirement omission。

## Review A2：Change → 实现 / 测试 / 文档

- `AGENTS.md`：必读入口和测试硬规则已加入；
- `SKILL.md`：按需读取、计划、实施、Completion Audit、交付均消费分层策略；
- `testing-strategy.md`：定义每层证明范围、不能证明范围、默认覆盖宽度、Validation Matrix 和反模式；
- `CHANGE.template.md`：新 L2/L3 Change 默认建立矩阵；
- Change/Completion/Verification references：Ready、Review、归档都复核矩阵；
- Blueprint 06：AIMA 长期测试架构已从泛化 E2E 拆成 Browser Mock 与 Real Full-stack 等明确层次；
- 实现 PR #155 只涉及治理/文档，不含产品业务代码、Contract、Migration、依赖或 CI Workflow。

## 代码/治理质量 Review

未发现严重或重要问题。策略避免两种过度：不要求所有状态跑昂贵 Full-stack，也不允许 Browser Mock 单独证明后端/DB/Worker/Provider；真实 Provider Probe 保留费用、稳定性和 Secret 边界。没有新增第三方依赖或运行时机制。

# 任务

- [x] 调查当前 AGENTS、Skill、Completion Gate、Change 模板、Verification Review、Blueprint 06 和现有 Browser Mock/Real Full-stack 事实。
- [x] 更新 AGENTS 与 Skill 导航/硬规则。
- [x] 新增通用 `testing-strategy.md`。
- [x] 更新 Change 模板、Change 管理、Completion Gate 和 Verification Review。
- [x] 更新 Blueprint 06 长期测试分层。
- [x] 完成 Requirement Traceability、Validation Matrix、Completion Audit 与两阶段 Review。
- [x] 最终 PR HEAD 的全部永久 CI 成功、无 Review/评论问题并正常合并。

# 验证

## 新鲜证据

实现 PR #155 最终 HEAD：`ea1814e8e1162f77e0a0561382e3e9c9aafa210f`。

8 个被触发永久 Workflow 全部 `success`：

- Change Completion Gate #20；
- CI #2174；
- Stage 6 Xiaohongshu Vertical Slice #172；
- Stage 7 Keyword Packs #1784；
- Stage 7 Provider Config Routing #1897；
- Stage 7 Plan Occurrence Run Snapshot #1782；
- Stage 7 Scheduler Runtime #2124；
- Stage 8F Full-stack Acceptance #301。

首轮 Draft HEAD 的 Change Completion Gate #19 中 11/11 RVC 自测试通过，唯一失败是 Change 当时仍为 `in_progress`；切到 `ready_for_review` 后最终 #20 成功。

实现 PR #155 无 Review、inline thread 或普通评论问题，merge commit：`20c183eab5cb0be81437a6ece90a4e43a64f4f9b`。

# 文档影响

- `AGENTS.md`：测试分层导航、硬规则和交付矩阵要求；
- Reliable Vibe Coding：新增通用 `testing-strategy.md`，并由 Skill/Change/Completion/Review/模板自动消费；
- Blueprint 06：固化 AIMA 长期测试架构和当前 Browser Mock/Stage 8F Full-stack 实例；
- 未改变产品 Roadmap、业务 Blueprint、API/Schema 文档或运行时代码事实。

# 兼容、依赖、Migration、部署与回滚

- HTTP Contract / OpenAPI / generated client：无变化；
- PostgreSQL Schema / Alembic Migration：无变化；
- Python / Frontend 依赖与锁文件：无变化；
- 产品运行时/部署：无变化；
- 现有 Browser Mock、PostgreSQL Integration、Stage 8F Full-stack 和 Provider Probe 行为：不修改，只明确长期职责；
- 回滚：回退 PR #155 的治理/文档/模板文件即可，不涉及业务数据恢复。

# 交付

- 实现 Branch：`chore/testing-strategy-governance`
- 实现 PR：`#155 固化 Browser Mock 与真实链路分层测试策略`
- 实现 HEAD：`ea1814e8e1162f77e0a0561382e3e9c9aafa210f`
- 实现 Merge Commit：`20c183eab5cb0be81437a6ece90a4e43a64f4f9b`
- 归档 Branch：`chore/archive-testing-strategy-governance`
- 发布：不适用
