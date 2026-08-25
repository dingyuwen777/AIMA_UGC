---
schema: rvc-change/v1
id: CHG-20260826-review-skill
title: 新增通用 Review Skill 与 Coding 强制路由
level: L2
status: ready_for_review
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
  - changes/active/CHG-20260826-review-skill/CHANGE.md
contracts: []
data_changes: []
---

# 目标

新增一个跨项目、跨语言可复用的 `review` Skill。Review 不维护第二套编码规范，而是复用当前项目规则；同仓存在 `.agents/skills/coding/SKILL.md` 时，Coding 是研发流程规范与测试分层的唯一事实源，Review 只增加独立审查、Findings、测试充分性分析、主动验证和修复闭环。

同时把 Coding 与 Review 建立硬路由：显式 Code Review / Audit 在 Coding 完成事实恢复和四维路由后必须进入 Review；任何 Coding 实现任务在完成前 Review 阶段，只要仓库存在 Review Skill，也必须进入 Review。Review 发现需要修代码的问题时返回 Coding，修复取得新鲜验证后再次进入 Review。

# 成功标准

- [x] `.agents/skills/review/SKILL.md` 可独立用于通用代码审查，支持 `review-only`、`review-and-test`、`review-and-fix`。
- [x] Review 不复制 Coding 的编码、TDD、Git、兼容、安全、Contract、Migration 或测试分层规范；同仓 Coding 存在时必须读取并以其为唯一研发流程规范源。
- [x] Review 从测试专家视角先从需求和风险推导应有证据，再检查现有测试；测试绿色不能自动等于覆盖充分。
- [x] Web/Full-stack 项目在真实存在对应边界时可使用 Browser Mock Acceptance 广覆盖用户可见状态，并区分 Backend/API/Persistence、Contract、真实 Golden Path 与外部 Probe 的证据边界。
- [x] Findings 有稳定严重度、位置、触发条件、影响、证据、测试缺口和建议修复方向；没有证据的问题不伪装成确定缺陷。
- [x] Coding 显式 Review/Audit 硬路由到 Review；所有 Coding 实现任务进入完成前 Review 时也硬路由到 Review；Review 缺失时保留 Coding 原 Review 能力，Review 存在但无法读取时不得宣称 Review 完成。
- [x] `review-and-fix` 只在已有修改授权时工作；生产代码修复必须返回 Coding 的完整流程，修复后执行 Review re-review。
- [x] `.agents/skills/review/README.md` 说明定位、三种模式、与 Coding/Docs 的关系、测试专家方法、典型使用方式，不复制第二套详细规则。
- [x] 自动化回归保护 Review 核心原则、Coding → Review 强制路由、Review → Coding 修复回路和 README 导航。
- [x] Docs targeted 复核确认 `docs/blueprint/06_开发约束与分阶段实施.md` 现有 `AGENTS → Coding` 统一入口、Completion Audit / Review 和分层测试说明仍准确；具体 Review 路由由 Coding/Review Skill 与 `review/README.md` 承载，因此不复制第二套 Blueprint 规则。

# 范围

- 新增 `.agents/skills/review/` 的主 Skill、README、agent metadata 和最少充分 references。
- 修改 Coding 主 Skill、任务路由 reference 与 agent metadata，建立 Review 双向硬路由。
- 新增 Coding Skill 回归测试，直接纳入现有 Change Completion Gate。
- 对 `docs/blueprint/06_开发约束与分阶段实施.md` 执行 targeted 事实复核；现有说明无需修改。

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
- 仓库可以用规则文本、metadata 和 CI 回归验证路由规则存在且不会静默丢失，但无法从仓库内部证明任意外部宿主/模型必然服从指令；不得把这一能力边界虚构为绝对执行保证。
- Blueprint 06 保持上位流程说明，不复制 `.agents/skills/review/` 的具体路由规则；Review 使用说明由 `.agents/skills/review/README.md` 承担。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 新增通用 Review Skill，复用现有 Coding 规范，避免两套规则 | user:current-request | satisfied | `.agents/skills/review/SKILL.md`、3 个 references 与 agent metadata 已建立；Coding patch 只追加 Review 集成，未搬运既有规则 |
| R2 | Review 必须包含测试专家视角，并支持 Browser Mock 验收用户可见行为 | user:current-request | satisfied | `review/references/03_测试专家审查方法.md` 明确风险→证据方法，并条件式覆盖 Browser Mock / Backend / Contract / Full-stack / Provider 五层 |
| R3 | 每次 Coding 在 Review 阶段都必须正确路由到 Review，显式 Review/Audit 也必须路由 | user:current-request | satisfied | `coding/SKILL.md` 的 `Review Skill 强制路由` + `coding/references/02_跨项目研发任务路由.md` + `coding/agents/openai.yaml` 三处建立可达硬路由；回归测试保护两类入口 |
| R4 | Review 要有效：能输出可执行 Findings、主动验证测试充分性并区分证据等级 | user:current-request | satisfied | `review/references/01_审查执行流程.md`、`02_Findings与严重度.md`、`03_测试专家审查方法.md` 分别承担执行、Finding、测试充分性；Review 主 Skill 要求证据边界和主动验证 |
| R5 | 修改完成后按仓库流程推送并合并到 main | user:current-request | explicitly_deferred | `AGENTS.md` 的 Git/Review 门禁要求 Ready + 当前 HEAD CI 后才能合并；PR #240 已建立，main 合并属于本 Change Ready 后的同任务集成步骤，不是功能延期，完成合并后归档时改为 satisfied |
| R6 | 在 review 目录增加 README 说明 | user:latest-clarification | satisfied | `.agents/skills/review/README.md` 已说明定位、模式、路由、测试专家方法、Findings、典型用法和边界 |
| R7 | 不降低现有 Coding/Docs/CI/Change 门禁，不新增依赖 | AGENTS.md | satisfied | PR patch 显示 Coding 主 Skill 仅在文件末尾追加集成段；路由 reference 只调整 Code Review/Audit 段；未修改 manifest/lock/workflow/产品代码；既有规则保护测试保持成功 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Red HEAD `0ec7cf4c568b5ddf451d0c91a9b2de2ef8fd8d36`：Change Completion Gate `32873657217` 在 `Run Coding completion-gate tests` 失败；Green HEAD `987736b0b987d8eb0f864272b8ea9f9e40abef38`：run `32874908293` 的同一步 success，随后仅因 Change 尚未 Ready 在 Ready Check 失败 |
| 接口 / Contract | not_applicable | 不修改产品 API/ABI/Schema/序列化 Contract；Skill 文本路由由治理测试验证，不新建产品 Contract |
| 集成 / Persistence / Runtime Dependency | not_applicable | 不涉及数据库、队列、业务持久化或生产 Runtime 依赖 |
| 用户 / Workflow Acceptance | required | `test_review_skill.py` 覆盖显式 Review、所有实现完成前 Review、Review 缺失/不可读边界、Review → Coding → re-review 与 README 导航；Green run `32874908293` 中 Coding completion-gate tests success |
| 跨组件 Golden Path | not_applicable | 不修改产品组件接线；Skill 路由是声明式研发治理，不存在可由产品 Full-stack 额外证明的运行边界 |
| External Dependency / Provider Probe | not_applicable | 不涉及外部 Provider 或付费 API |
| Build / Package / Runtime | not_applicable | 不修改 manifest、lock、镜像、构建或运行入口；PR HEAD `987736b0` 的 Runtime Acceptance `32874905982` 与 Full-stack Acceptance `32874905984` success 作为无回归补充证据 |
| Docs / Governance / Other | required | PR #240 diff 已人工复核：Coding 主 Skill 只追加 Review 集成；Coding 路由 reference 只改变 Code Review/Audit 段；Docs targeted 复核 Blueprint 06 无需 diff；最终合并前必须以同步最新 main 后的新 HEAD CI 全绿为准 |

# Completion Audit

- [x] upstream_re_read：重新读取本轮“通用 Review、测试专家、Browser Mock、每次 Coding 路由、直接合入 main”要求及用户最新“README 必须位于 review 目录”的澄清；重新读取当前 AGENTS、Coding 04/10/11、测试分层和 Docs 规则。
- [x] change_coverage：独立重建的要求均映射到 R1—R7；README 路径已按最新澄清修正；未把 PR 描述或当前 Change 自身当需求全集。
- [x] reverse_audit：正向为 `AGENTS → Coding → Review`；显式 Review 与实现完成前 Review 均可达；反向为 `Review Finding → Coding fix → fresh evidence → Review re-review`；文档问题按需进入 Docs；Review 缺失时保留 Coding 既有 Review、存在但不可读时阻塞。
- [x] unresolved_cleared：R1—R4/R6/R7 已 satisfied；R5 按 AGENTS 强制集成顺序正式延期到 Ready + CI 后同任务执行，没有功能性 `not_satisfied`；所有 Validation `not_applicable` 均有事实依据。

# 两阶段 Review

## Review A1：上游要求 → Change

从用户当前要求重新建立完成定义，而不是读取 Change checkbox 反推：

1. Review 必须通用，可跨语言/项目；
2. Coding 是研发流程规范唯一事实源，避免双维护；
3. 每次代码实现完成前必须进入 Review，显式 Review/Audit 立即进入；
4. Review 必须像测试专家一样从风险推导证据，Browser Mock 可验收用户可见行为，但不得冒充真实后端/数据库/Provider；
5. Findings 必须有证据、触发条件、影响和测试缺口；
6. Review 能补测试、能在授权后驱动修复，但生产修复返回 Coding；
7. `review/README.md` 必须提供说明；
8. 不降低现有质量门禁，不新增不必要依赖；
9. 最终经过正常 PR/CI 合入 main。

R1—R7 已覆盖 1—9；第 9 项按仓库规定只能在 Ready 后完成集成，因此保留为正式 integration-stage deferred，不冒充已经合并。

## Review A2：Change → 实现 / 测试 / 文档

- Review 主 Skill、README、3 个 references、agent metadata 均已存在，职责分离明确；
- Coding 正文存在显式 Review 与任何实现完成前 Review 的硬路由；任务路由 reference 与 metadata 同步，且不依赖 metadata 作为唯一入口；
- Red/Green 已实际由 GitHub Actions 建立；Green 后 Ready Check 失败原因是 Change 状态尚未 Ready，不是 Skill 测试失败；
- PR patch 人工复核证明 Coding 主 Skill 原有正文没有被重写，只在末尾追加 Review 集成；路由 reference 仅修改 Review/Audit 段（另补 EOF newline）；
- Docs Impact = `targeted`：Blueprint 06 仍正确描述 `AGENTS → Coding` 和 Review/测试分层；具体 Review 路由若复制过去会形成第二套规则，所以不制造 Blueprint diff；Review 使用说明已由 `review/README.md` 提供。

## 第二阶段：代码/规则质量 Review

- 正确性：显式 Review、完成前 Review、缺失 fallback、不可读 blocking、fix/re-review 五条关键路径都明确；
- 测试质量：回归断言覆盖主 Skill、routing reference、metadata、反向修复和 README；测试关注可观察规则语义，不引入新测试框架；
- 兼容性：无产品 API/Schema/Migration/依赖/Runtime 变化；没有要求其他项目必须安装 Review，Coding 在 Review 不存在时保持原行为；
- 可维护性：Review 只维护审查方法，Coding 继续维护开发和分层测试事实，Docs 继续维护文档方法；
- 无关改动：PR changed files 仅 Skill/测试/Change，Blueprint targeted 复核后未修改；
- 剩余能力边界：仓库规则无法技术上强迫任意外部宿主/模型遵从 Skill；已通过 `AGENTS → Coding` 可达链、正文硬路由、metadata 辅助和 CI 回归最大化可验证约束，不虚构绝对保证；
- Findings：当前 Review 范围内无 BLOCKER/HIGH/MEDIUM；未发现需要返回 Coding 的实现缺陷。

# Git / 集成状态

- branch: `feature/review-skill`
- PR: `#240`（Draft，待 Ready Check 与最终 HEAD CI）
- base sync: 最新 `main` `eed6ebbb8348827998bba56f46c6e3cf83eacd13` 已通过双父 merge commit `ee673e27be40fdf5521b24bd2dfb10eca1f6c5d0` 合入 feature，compare 显示 feature `behind_by=0`
- Red evidence: `0ec7cf4c568b5ddf451d0c91a9b2de2ef8fd8d36` / Change Completion Gate `32873657217`
- Green skill-test evidence: `987736b0b987d8eb0f864272b8ea9f9e40abef38` / Change Completion Gate `32874908293` 的 Coding tests success
- Ready Check previous root cause: run `32875393808` 的 Skill tests 29/29 success，Ready Check 仅因 R7 Source 拼接两个路径而失败；本提交已按机器规则修正为单一真实来源 `AGENTS.md`
- main merge: 待本 Change Ready + 最新 HEAD 全量 CI 绿后执行
