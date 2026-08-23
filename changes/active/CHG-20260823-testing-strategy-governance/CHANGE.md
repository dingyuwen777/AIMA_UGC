---
schema: rvc-change/v1
id: CHG-20260823-testing-strategy-governance
title: 固化 Browser Mock 与真实链路分层测试策略
level: L2
status: in_progress
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

- [ ] `AGENTS.md` 增加简洁的仓库级测试分层硬规则，并导航到详细测试策略。
- [ ] Reliable Vibe Coding 增加 `testing-strategy.md`，明确每层“证明什么 / 不能证明什么 / 何时使用 / 默认覆盖宽度”。
- [ ] Skill 的任务规划、实施和 Completion Audit 明确要求按任务边界建立 Validation Matrix，而不是把所有场景都塞进 Real Full-stack。
- [ ] `CHANGE.template.md` 增加 Validation Matrix，要求 L2/L3 明确 Browser Mock、Backend Integration、Contract、Real Full-stack、Real Provider Probe 的 required/not_applicable 及证据。
- [ ] Change 管理、Completion Gate 和 Verification Review 同步 Validation Matrix 语义，防止模板存在但 Review 不检查。
- [ ] Blueprint 06 把当前泛化 `E2E` 分层扩展为 AIMA 的正式长期测试策略，明确 Browser Mock 与 Real Full-stack 不是同一种证据。
- [ ] 保持现有真实 Stage 8F Full-stack、generated client、PostgreSQL Integration 和 Provider 有界 Probe 机制，不降低任何现有质量门禁。
- [ ] 不修改产品业务代码、HTTP Contract、Schema/Migration、依赖或运行时行为。

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
- 当前 Stage 8F Real Full-stack Acceptance 继续作为真实链路 Golden Path。
- 真实 TikHub/其他外部 Provider Probe 默认不进入普通 CI，继续受费用、稳定性和 Secret 边界约束。
- Completion Gate 的 Requirement Traceability / Ready Check 语义保持不变。

# 关键决策

用户明确确认采用分层方案并要求固化到仓库，使后续 Agent 每次开发能自动读取并实施。默认原则为：

```text
Browser Mock Acceptance → 用户可见行为和状态的最宽覆盖
Backend/API/PostgreSQL Integration → 服务器规则、事务、持久化、Worker
Contract → Pydantic/OpenAPI/generated client 一致性
Real Full-stack → 少量关键 Golden Path，只证明系统真实接通
Real Provider Probe → 极少、有界、必要时执行，不作为普通回归主力
```

测试数量不按固定配额机械分配；由行为边界和风险决定。用户可见状态复杂时优先扩 Browser Mock，而不是复制成大量昂贵 Full-stack 场景。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | Browser Mock 应作为用户可见行为/状态的广覆盖验收主力，但不能声称证明真实后端链路 | user:testing-strategy-confirmation | not_satisfied | 待固化 |
| R2 | Backend Integration、Contract、Real Full-stack、Real Provider Probe 必须各自有清晰证明边界和成本定位 | user:testing-strategy-confirmation | not_satisfied | 待固化 |
| R3 | 后续 Agent 应在每次相关任务中自行读取并实施该策略，不依赖用户重复提醒 | user:testing-strategy-confirmation | not_satisfied | 待固化 |
| R4 | L2/L3 Change 应通过 Validation Matrix 明确适用测试层与证据，Completion Audit/Review 必须检查 | user:testing-strategy-confirmation | not_satisfied | 待固化 |
| R5 | 新策略必须与当前 PostgreSQL Integration、generated client 和 Stage 8F Real Full-stack 事实兼容 | docs/blueprint/06-开发约束与分阶段实施.md | not_satisfied | 待核对并同步 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | not_applicable | 本 Change 只修改开发治理文档，不改变用户页面行为 |
| Backend/API/PostgreSQL Integration | not_applicable | 不修改后端业务行为、事务或持久化 |
| Contract / Generated Client | not_applicable | 不修改 HTTP Contract、OpenAPI 或 generated client |
| Real Full-stack Golden Path | not_applicable | 不修改真实业务链；通过现有永久 Workflow 回归确认门禁未降低 |
| Real Provider Probe | not_applicable | 不修改 Provider 能力/接口，不产生付费请求 |
| Docs / Governance Validation | required | 文档链接/规则一致性、Completion Gate、主 CI 与永久回归 |

# Completion Audit

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已按“入口规则 → Skill → 测试策略 → Change 模板 → Review/Completion Audit → Blueprint”反向检查规则消费链；不适用边界已有依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前 AGENTS、Skill、Completion Gate、Change 模板、Verification Review、Blueprint 06 和现有 Browser Mock/Real Full-stack 事实。
- [ ] 更新 AGENTS 与 Skill 导航/硬规则。
- [ ] 新增通用 `testing-strategy.md`。
- [ ] 更新 Change 模板、Change 管理、Completion Gate 和 Verification Review。
- [ ] 更新 Blueprint 06 长期测试分层。
- [ ] 执行文档/规则验证、Ready Check 与永久 CI。
- [ ] 完成 Completion Audit 与两阶段 Review。

# 验证

## 计划

- 文档/规则：主 CI 的 `check_docs.py`、Secret 扫描和仓库质量检查。
- Completion Gate：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`。
- 回归：最终 PR HEAD 所有被触发的永久 Workflow 必须成功；尤其保留 Stage 8F Full-stack Acceptance。
- TDD 例外：本任务只改变开发治理/文档和模板，不改变产品运行行为；不为纯文档治理编造业务 Red。

## 新鲜证据

- 尚未执行最终验证。

# 文档影响

- 更新 `AGENTS.md`、Reliable Vibe Coding references/模板和 Blueprint 06；不改变产品 Roadmap、业务 Blueprint、API/Schema 文档。

# 交付

- Branch：`chore/testing-strategy-governance`
- Commit：进行中
- PR：未创建
- 发布：不适用
