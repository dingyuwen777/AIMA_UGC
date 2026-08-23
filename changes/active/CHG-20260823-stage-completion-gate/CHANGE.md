---
schema: rvc-change/v1
id: CHG-20260823-stage-completion-gate
title: Stage 完成定义追溯与 Ready 门禁
level: L2
status: in_progress
owner: chatgpt
branch: chore/stage-completion-gate
created: 2026-08-23
updated: 2026-08-23
depends_on: []
affected_areas:
  - development-workflow
  - change-management
  - review
  - ci
affected_paths:
  - AGENTS.md
  - .agents/skills/reliable-vibe-coding/SKILL.md
  - .agents/skills/reliable-vibe-coding/references/change-management.md
  - .agents/skills/reliable-vibe-coding/references/verification-review.md
  - .agents/skills/reliable-vibe-coding/assets/CHANGE.template.md
  - .agents/skills/reliable-vibe-coding/scripts/ready_check.py
  - .agents/skills/reliable-vibe-coding/tests/
  - .github/workflows/ci.yml
contracts: []
data_changes: []
---

# 目标

把正式 Stage / 子 Stage / Roadmap 单元的“完成定义完整性”从依赖 Agent 记忆和用户复查，升级为仓库内可追溯、可复核、CI 可执行的强制门禁。Change 不能再作为自身需求全集；进入 `ready_for_review` 前必须重新读取上游正式事实源，逐条追溯到实现/验证，并执行独立 Completion Audit。

# 成功标准

- [ ] 新建 L2/L3 Change 默认带机器可识别的 Completion Gate 标记、Requirement Traceability 和 Completion Audit。
- [ ] Traceability 每条要求只能使用 `satisfied / explicitly_deferred / not_applicable / not_satisfied` 四种状态；进入 Ready 时不得存在 `not_satisfied`。
- [ ] `explicitly_deferred` / `not_applicable` 必须有非占位依据；`satisfied` 必须有非占位证据。
- [ ] Completion Audit 必须证明重新读取上游事实源、检查 Change 覆盖完整性、执行适用的反向能力审计并清零未满足项。
- [ ] 历史 Change 和当前未归档 `rvc-change/v1` 记录保持兼容，不因新门禁一次性失败。
- [ ] 新增 RVC Ready Check 脚本，可在本地和 CI 检查所有声明启用 Completion Gate 的 Active/Archive Change。
- [ ] CI 在最终可合并 HEAD 上强制执行 Skill 自测试和 Ready Check；未满足门禁时明确失败。
- [ ] `AGENTS.md`、Reliable Vibe Coding Skill、Change 管理和两阶段 Review 规则同步，明确“上游需求 → Change → 实现”的两层需求符合性复核。
- [ ] 不修改产品 HTTP Contract、Schema、Migration、业务代码或依赖版本。

# 范围

- 开发治理规则、Change 模板、RVC Completion Gate 脚本及其测试、主 CI。
- 仅校验流程完整性，不尝试让脚本理解全部业务语义。

# 非目标

- 不修改现有产品 Stage 的业务实现。
- 不回写全部历史归档 Change。
- 不替代人工/Agent 的语义需求审计。
- 不新增第三方依赖。

# 必须保持不变

- 现有 `rvc.py discover/status/new-change/conflicts` 行为保持兼容。
- 现有 `rvc-change/v1` 历史/Active Change 仍可被当前 RVC 工具读取。
- L1 机械任务继续不强制创建 Change。
- 当前业务 CI、Contract、Migration、前端/后端验证门禁不得降低。

# 关键决策

用户明确选择方案 C：规则固化 + Completion Contract/Traceability + 独立 Completion Audit + 机器 Ready Check + CI 门禁。机器门禁只验证可机器判断的结构、状态、占位符和事实源路径；业务语义完整性仍由 Completion Audit 从上游正式事实源重新建立，不允许以当前 Change 自身作为需求全集。

为避免历史 Change 和当前已合并但尚待归档的 L3 Change 被新规则一次性打红，新模板通过 `completion_gate: required` 显式启用新门禁；没有该标记的旧 Change 作为 legacy 保持兼容。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式 Stage 完成不能继续依赖用户发现遗漏；必须从上游完成定义逐项追溯 | user:current-request | not_satisfied | 待实现 |
| R2 | Change 不能作为自身需求全集；Review 必须检查上游要求是否被 Change 遗漏 | user:current-request | not_satisfied | 待实现 |
| R3 | 方案 C 要包含规则固化、Completion Audit、机器 Ready Check 和 CI 门禁 | user:current-request | not_satisfied | 待实现 |
| R4 | 新机制不得破坏当前业务 Change 与历史 Change | changes/active/CHG-20260822-provider-lookup-supplement-eligibility/CHANGE.md | not_satisfied | 待验证兼容 |

# Completion Audit

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前 AGENTS、Skill、Change 模板、Review 规则、RVC 工具和 CI。
- [ ] Red：建立 Completion Gate 自测试并确认当前实现因缺少门禁失败。
- [ ] Green：实现机器 Ready Check、模板和规则同步。
- [ ] 运行目标测试、质量检查和主 CI。
- [ ] 完成 Completion Audit 与两阶段 Review。

# 验证

## 计划

- 目标测试：Skill 内置 `unittest` 覆盖 legacy 兼容、完整 Ready 通过、未满足项/未勾选 Audit/占位符/失效事实源拒绝。
- 静态检查：Ruff 检查新增 Python；Ready Check 自检当前仓库。
- CI：主 `CI` 最新 PR HEAD 全绿，且 Ready Check 在 CI 内执行。

## 新鲜证据

- 尚未执行 Red/Green。

# 文档影响

- 更新 `AGENTS.md`、Skill、Change 管理、Verification Review；不修改 Blueprint，避免与当前待归档 L3 Change 的 `docs/blueprint/` 影响范围发生并行冲突。

# 交付

- Branch：`chore/stage-completion-gate`
- Commit：进行中
- PR：未创建
- 发布：不适用
