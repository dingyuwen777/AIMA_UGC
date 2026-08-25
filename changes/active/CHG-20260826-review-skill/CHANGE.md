---
schema: rvc-change/v1
id: CHG-20260826-review-skill
title: 新增通用 Review Skill 与 Coding 强制路由
level: L2
status: in_progress
owner: aima
branch: feature/review-skill
created: 2026-08-26
updated: 2026-08-26
completion_gate: required
depends_on: []
affected_areas:
  - developer-tooling
  - testing-governance
  - review-governance
affected_paths:
  - .agents/skills/review/
  - .agents/skills/coding/SKILL.md
  - .agents/skills/coding/references/02_跨项目研发任务路由.md
  - .agents/skills/coding/agents/openai.yaml
  - .agents/skills/coding/tests/test_review_skill.py
  - docs/blueprint/06_开发约束与分阶段实施.md
  - changes/active/CHG-20260826-review-skill/CHANGE.md
contracts: []
data_changes: []
---

# 目标

新增一个跨项目、跨语言可复用的 `review` Skill。Review 不维护第二套编码规范，而是复用当前项目规则；同仓存在 `.agents/skills/coding/SKILL.md` 时，Coding 是研发规范与测试分层的唯一事实源，Review 只增加独立审查、Findings、测试充分性分析、主动验证和修复闭环。

同时把 Coding 与 Review 建立硬路由：显式 Code Review / Audit 在 Coding 完成事实恢复和四维路由后必须进入 Review；任何 Coding 实现任务在完成前 Review 阶段，只要仓库存在 Review Skill，也必须进入 Review。Review 发现需要修代码的问题时返回 Coding，修复取得新鲜验证后再次进入 Review。

# 成功标准

- [ ] `.agents/skills/review/SKILL.md` 可独立用于通用代码审查，支持 `review-only`、`review-and-test`、`review-and-fix`。
- [ ] Review 不复制 Coding 的编码、TDD、Git、兼容、安全、Contract、Migration 或测试分层规范；同仓 Coding 存在时必须读取并以其为唯一研发规范源。
- [ ] Review 从测试专家视角先从需求和风险推导应有证据，再检查现有测试；测试绿色不能自动等于覆盖充分。
- [ ] Web/Full-stack 项目在真实存在对应边界时可使用 Browser Mock Acceptance 广覆盖用户可见状态，并区分 Backend/API/Persistence、Contract、真实 Golden Path 与外部 Probe 的证据边界。
- [ ] Findings 有稳定严重度、位置、触发条件、影响、证据、测试缺口和建议修复方向；没有证据的问题不伪装成确定缺陷。
- [ ] Coding 显式 Review/Audit 硬路由到 Review；所有 Coding 任务进入完成前 Review 时也硬路由到 Review；Review 缺失时保留 Coding 原 Review 能力，Review 存在但无法读取时不得宣称 Review 完成。
- [ ] `review-and-fix` 只在已有修改授权时工作；生产代码修复必须返回 Coding 的完整流程，修复后执行 Review re-review。
- [ ] `.agents/skills/review/README.md` 说明定位、三种模式、与 Coding/Docs 的关系、测试专家方法、典型使用方式，不复制第二套详细规则。
- [ ] 自动化回归保护 Review 核心原则、Coding → Review 强制路由、Review → Coding 修复回路和 README 导航。
- [ ] 受影响的开发流程文档按 Docs targeted 模式同步，且不建立第二套 Skill 规则。

# 范围

- 新增 `.agents/skills/review/` 的主 Skill、README、agent metadata 和最少充分 references。
- 修改 Coding 主 Skill、任务路由 reference 与 agent metadata，建立 Review 双向硬路由。
- 新增 Coding Skill 回归测试，直接纳入现有 Change Completion Gate。
- targeted 更新 `docs/blueprint/06_开发约束与分阶段实施.md` 中 Review 的正式入口说明。

# 非目标

- 不复制或重写 Coding 的现有研发规范、Validation Matrix 语义、测试分层、Git、安全、兼容、Contract、Schema/Migration、时间、日志和注释规则。
- 不引入新的测试框架、浏览器框架、依赖或 CLI。
- 不要求所有项目机械执行 Browser、数据库、Full-stack 或 Provider 测试；只按项目真实边界和风险选择证据。
- 不修改产品代码、HTTP Contract、数据库、Migration、Runtime、部署或 CI workflow。
- 不把 Review 变成自动批准或自动合并机制。

# 必须保持不变

- Coding 现有规则语义、触发条件、失败处理和证据门禁保持不变；本次只增加 Review 协作层。
- Docs Skill 继续只负责文档工作流；Review 不接管 Docs 的文档审查规则。
- 项目上位 `AGENTS.md`、真实机器事实、用户授权和仓库本地规则继续高于通用 Skill。
- Review 默认只报告；未经授权不得通过 Review 自行修改、提交、推送、建 PR、合并或发布。

# 关键决策

- Skill 正式名称使用 `review`，目录 `.agents/skills/review/`。
- Coding 是开发规范编排入口；Review 是独立审查与测试充分性验证器，不成为第二套开发规范。
- “每次 Coding 都路由 Review”具体定义为：所有实现任务在完成前 Review 阶段调用 Review；显式 Review/Audit 请求在完成 Coding 的事实恢复/四维路由后立即调用 Review。
- Review 存在但无法读取时，不能退化后仍声称执行了 Review；Review 不存在时，Coding 继续使用其原有两阶段 Review 规则，保证通用 Coding 不被绑定到特定目录。
- Browser Mock 是条件式工具，不是所有项目固定必跑项；真实分层语义继续由 Coding references 在存在时提供。
- 测试专家职责是“从风险推导应有证据 → 评估已有覆盖 → 设计/执行最少充分验证”，不是“把所有场景做成真实端到端”。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增通用 Review Skill，复用现有 Coding 规范，避免两套规则 | user:current-request | not_satisfied | 待实现 |
| R2 | Review 必须包含测试专家视角，并支持 Browser Mock 验收用户可见行为 | user:current-request | not_satisfied | 待实现 |
| R3 | 每次 Coding 在 Review 阶段都必须正确路由到 Review，显式 Review/Audit 也必须路由 | user:current-request | not_satisfied | 待实现 |
| R4 | Review 要有效：能输出可执行 Findings、主动验证测试充分性并区分证据等级 | user:current-request | not_satisfied | 待实现 |
| R5 | 修改完成后按仓库流程推送并合并到 main | user:current-request | not_satisfied | 待 PR/CI/合并验证 |
| R6 | 在 review 目录增加 README 说明 | user:latest-clarification | not_satisfied | 待实现 `.agents/skills/review/README.md` |
| R7 | 不降低现有 Coding/Docs/CI/Change 门禁，不新增依赖 | AGENTS.md + coding/SKILL.md | not_satisfied | 待 diff 与 CI 证明 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | 新增 Skill 路由回归测试；先观察缺少 Review 时失败，再实现通过 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/Schema/序列化 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、队列、运行时依赖 |
| 用户 / Workflow Acceptance | required | 以 Skill 文本与自动化断言验证 Coding → Review、Review → Coding 修复回路 |
| 跨组件 Golden Path | not_applicable | 不涉及产品组件接线 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider |
| Build / Package / Runtime | not_applicable | 不修改生产构建和运行入口 |
| Docs / Governance / Other | required | Review README、Blueprint targeted 同步、Change Gate、PR CI 与 main 集成证据 |

# Completion Audit

- [ ] upstream_re_read
- [ ] change_coverage
- [ ] reverse_audit
- [ ] unresolved_cleared

# 两阶段 Review

待实现完成后执行 Review A1/A2 与代码质量 Review；由于本任务本身引入 Review Skill，最终复核同时按新 Review Skill 执行。
