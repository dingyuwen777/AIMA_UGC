---
schema: rvc-change/v1
id: CHG-20260823-stage-completion-gate
title: Stage 完成定义追溯与 Ready 门禁
level: L2
status: ready_for_review
owner: chatgpt
branch: chore/stage-completion-gate
created: 2026-08-23
updated: 2026-08-23
completion_gate: required
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
  - .agents/skills/reliable-vibe-coding/references/completion-gate.md
  - .agents/skills/reliable-vibe-coding/references/verification-review.md
  - .agents/skills/reliable-vibe-coding/assets/CHANGE.template.md
  - .agents/skills/reliable-vibe-coding/scripts/ready_check.py
  - .agents/skills/reliable-vibe-coding/tests/
  - .github/workflows/change-completion-gate.yml
contracts: []
data_changes: []
---

# 目标

把正式 Stage / 子 Stage / Roadmap 单元的“完成定义完整性”从依赖 Agent 记忆和用户复查，升级为仓库内可追溯、可复核、CI 可执行的强制门禁。Change 不能再作为自身需求全集；进入 `ready_for_review` 前必须重新读取上游正式事实源，逐条追溯到实现/验证，并执行独立 Completion Audit。

# 成功标准

- [x] 新建 L2/L3 Change 默认带机器可识别的 Completion Gate 标记、Requirement Traceability 和 Completion Audit。
- [x] Traceability 每条要求只能使用 `satisfied / explicitly_deferred / not_applicable / not_satisfied` 四种状态；进入 Ready 时不得存在 `not_satisfied`。
- [x] `explicitly_deferred` / `not_applicable` 必须有非占位依据；`satisfied` 必须有非占位证据。
- [x] Completion Audit 必须证明重新读取上游事实源、检查 Change 覆盖完整性、执行适用的反向能力审计并清零未满足项。
- [x] 历史 Change 和既有 `rvc-change/v1` 记录保持兼容，不因新门禁一次性失败。
- [x] 新增 RVC Ready Check 脚本，可在本地和 CI 检查声明启用 Completion Gate 的 Active/Archive Change。
- [x] CI 对 PR 强制检查本 PR 改动的 gated Change，对 `main` 强制检查全部 gated Active Change；Skill 自测试同时作为永久门禁。
- [x] `AGENTS.md`、Reliable Vibe Coding Skill、Change 管理和两阶段 Review 规则同步，明确“上游需求 → Change → 实现”的两层需求符合性复核。
- [x] 不修改产品 HTTP Contract、Schema、Migration、业务代码或依赖版本。

# 范围

- 开发治理规则、Change 模板、RVC Completion Gate 脚本及其测试、独立永久 CI Workflow。
- 仅校验流程完整性，不尝试让脚本理解全部业务语义。

# 非目标

- 不修改现有产品 Stage 的业务实现。
- 不回写全部历史归档 Change。
- 不替代人工/Agent 的语义需求审计。
- 不新增第三方依赖。

# 必须保持不变

- 现有 `rvc.py discover/status/new-change/conflicts` 行为保持兼容。
- 机制引入前没有 `completion_gate: required` 的历史/既有 Change 作为 legacy 保持兼容。
- L1 机械任务继续不强制创建 Change。
- 当前业务 CI、Contract、Migration、前端/后端验证门禁不得降低。
- 并行开发不因其他尚在进行中的 gated Change 被当前 PR 的 Ready Check 无关阻塞。

# 关键决策

用户明确选择方案 C：规则固化 + Completion Contract/Traceability + 独立 Completion Audit + 机器 Ready Check + CI 门禁。机器门禁只验证可机器判断的结构、状态、占位符和事实源路径；业务语义完整性仍由 Completion Audit 从上游正式事实源重新建立，不允许以当前 Change 自身作为需求全集。

为避免历史 Change 被新规则一次性打红，不升级 Change schema；仍使用 `rvc-change/v1`，新模板通过额外的 `completion_gate: required` 显式启用门禁。Ready Check 在调用严格 `rvc.py` parser 前先读取 marker，因此早期不满足当前 v1 parser 形态的历史归档也保持 legacy 兼容。

PR 模式使用 `--changed-since <base-sha>`：只强制当前 PR 新增/修改的 gated Active Change Ready，并额外拒绝本 PR 新增但故意遗漏 `completion_gate` 的 Active Change。`main` push 使用 `--require-active-ready`，确保集成后的新机制事实不会留下未 Ready 的 gated Active Change。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 正式 Stage/子 Stage/Roadmap 单元完成不能依赖用户继续发现遗漏；Agent 必须主动从上游完成定义逐项追溯 | user:scheme-c-confirmation | satisfied | `AGENTS.md` 正式单元完成定义追溯门禁；`SKILL.md` 第 6/10 步；新 Change 模板 Requirement Traceability |
| R2 | Change 不能作为自身需求全集；Review 必须先检查“上游要求 → Change”是否遗漏，再检查“Change → 实现” | user:scheme-c-confirmation | satisfied | `references/verification-review.md` Review A1/A2；`references/completion-gate.md` 两层 Review；自引用 Source 回归测试 |
| R3 | 方案 C 必须同时固化规则、Completion Audit、机器 Ready Check 和 CI 门禁，而不是只增强提示词 | user:scheme-c-confirmation | satisfied | `AGENTS.md` + Skill/References + `ready_check.py` + `change-completion-gate.yml`；Change Completion Gate #14 的 11 个自测试全部通过 |
| R4 | 新机制必须能在现有仓库长期落地，不能要求批量重写历史 Change，也不能让无关并行 Change 阻塞当前 PR | user:scheme-c-confirmation | satisfied | `ready_check.py` 先识别 marker 再严格解析；malformed legacy 回归通过；PR 使用 `--changed-since`，`main` 使用 `--require-active-ready` |
| R5 | 机器门禁不能假装证明自然语言业务语义完整，仍必须保留独立语义 Completion Audit | user:scheme-c-confirmation | satisfied | `references/completion-gate.md`、`verification-review.md` 和 `SKILL.md` 都明确脚本只验证结构/状态/Source/占位符/Audit checkbox，不替代语义 Review |

# Completion Audit

- [x] upstream_re_read：已重新读取用户对方案 C 的确认、当前 `AGENTS.md`、Reliable Vibe Coding Skill、Change 管理、Verification Review、Change 模板、RVC 脚本和 CI 入口，并独立重建本任务完成定义。
- [x] change_coverage：重新按“用户目标 → 规则固化 → Change 模板 → Ready Check → CI → Review”链路检查，本 Change 的 R1—R5 覆盖防漏项、双层 Review、机器门禁、兼容/并行和语义边界，没有把本 Change 自身作为 Requirement Source。
- [x] reverse_audit：本任务不涉及产品前后端；已按治理工具真实生产者/消费者反向审计 `CHANGE.template.md → 新 Change marker/sections → ready_check.py parser → PR changed-only gate / main all-active gate`，并用 legacy、marker omission、自引用、非法状态、占位 Evidence、未完成 Audit、归档状态等回归覆盖逆向失败路径。
- [x] unresolved_cleared：R1—R5 均为 `satisfied`；没有 `not_satisfied`、延期或不适用项，也没有依赖用户后续人工发现的剩余完成条件。

# TDD 与根因修复

## Red

首次永久 Workflow `Change Completion Gate #2`（run `32608507513`，job `97117464425`）中，8 个目标测试全部因正确原因失败：仓库当时没有 `ready_check.py`，Change 模板也没有 `completion_gate` / Traceability / Completion Audit。

## Green 过程中的真实回归

第一版脚本进入 CI 后，测试发现 `_normalise_relative_path()` 把 `Path` 当成 `str` 调用 `.replace()`；修复为显式 `str(value)`，没有降低断言。

随后真实仓库扫描发现 35 个早期归档 Change 不能通过当前严格 v1 parser。根因是门禁在判断 legacy 前已经严格解析历史文件。修复为：先以轻量 frontmatter marker 判断是否 gated，只对 `completion_gate: required` 的 Change 严格解析；并新增 malformed legacy 回归。

继续加强后新增“本 PR 新增 Active Change 缺少 marker 必须失败”测试，防止通过删除/漏写 `completion_gate` 绕过门禁。

## 当前 Green 证据

`Change Completion Gate #14`（run `32609005861`，job `97118758817`）：

```text
Ran 11 tests in 0.780s
OK
```

11 个测试覆盖：模板启用门禁、完整 Ready 通过、legacy 兼容、malformed legacy 兼容、新 Active Change 漏 marker 拒绝、`not_satisfied` 拒绝、Completion Audit 未完成拒绝、Source 文件缺失拒绝、Change 自引用拒绝、占位 Evidence 拒绝、归档未 `done` 拒绝。

该 HEAD 的 changed-PR Ready Check 只剩一个预期的自举失败：本 Change 当时尚未添加 `completion_gate: required`。本提交已完成 marker、Traceability、Audit 和 `ready_for_review` 状态，将由后续最新 HEAD Workflow 作为第一次完整自举通过证据。

# 任务

- [x] 调查当前 AGENTS、Skill、Change 模板、Review 规则、RVC 工具和 CI。
- [x] Red：建立 Completion Gate 自测试并确认当前实现因缺少门禁失败。
- [x] Green：实现机器 Ready Check、模板和规则同步。
- [x] 修复 Path 类型和 legacy 解析两个由 CI 实际发现的实现缺陷，并补回归。
- [x] 完成 Requirement Traceability 与 Completion Audit。
- [x] 建立永久 `Change Completion Gate` Workflow；最终 PR HEAD 仍以 GitHub Actions 新鲜结果作为合并门禁。

# 验证

## 计划

- 目标测试：`python -m unittest discover .agents/skills/reliable-vibe-coding/tests -v`
- PR Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --changed-since <PR base sha>`
- 集成后 Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`
- 静态/仓库质量：由主 `CI` 最新 PR HEAD 执行现有 Ruff、Secret、Docs、架构和完整项目门禁。
- 永久回归：最终 PR HEAD 的所有被触发永久 Workflow 必须 `success` 后才允许合并。

## 新鲜证据

- Red：Change Completion Gate #2 / run `32608507513` / job `97117464425`，8/8 目标测试失败，缺失文件/模板门禁为直接原因。
- Green 自测试：Change Completion Gate #14 / run `32609005861` / job `97118758817`，11/11 通过。
- 自举门禁：#14 在当前 Change 尚未启用 marker 时准确拒绝该新增 Active Change，证明 marker omission 不能绕过；本提交已补齐正式门禁，等待最新 HEAD 的永久 Workflow 验证。

# 文档影响

- `AGENTS.md` 固化仓库级正式单元完成定义追溯门禁。
- Reliable Vibe Coding Skill 及 `change-management.md`、`completion-gate.md`、`verification-review.md` 固化通用开发/Review 机制。
- `CHANGE.template.md` 让后续新 L2/L3 Change 默认进入门禁。
- 不修改 Blueprint：本次改变的是 Agent/Change/Review 开发治理，不改变产品架构、业务 Contract、数据模型或 Roadmap 阶段目标。

# 兼容、依赖、Migration、部署与回滚

- HTTP Contract / OpenAPI / generated client：无变化。
- PostgreSQL Schema / Alembic Migration：无变化。
- Python / Frontend 依赖与锁文件：无变化。
- 产品运行时与部署：无变化；新增 Workflow 只在 GitHub Actions 执行 stdlib Python 检查。
- 历史 Change：无 marker 的记录保持 legacy，不批量改写。
- 回滚：若本治理机制本身需要回滚，只需回退本 PR 的规则/模板/脚本/Workflow；不涉及业务数据迁移或恢复。

# 交付

- Branch：`chore/stage-completion-gate`
- PR：`#153 固化 Stage 完成定义追溯与 Ready 门禁`（Draft，最终门禁全绿后转 Ready）
- 发布：不适用
