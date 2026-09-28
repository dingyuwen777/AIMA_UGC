---
schema: coding-change/v1
id: CHG-20260928-172800-change-archive-rerun-compat
title: 兼容历史多 Change 归档 Run 的逐项重跑恢复
level: L2
status: done
owner: chatgpt
branch: fix/580-change-archive-rerun-compat
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on:
  - CHG-20260928-164400-change-archive-multi
affected_areas:
  - governance
  - ci
  - change-archive
affected_paths:
  - scripts/quality/archive_change_after_merge.py
  - tests/unit/test_change_archive_automation.py
contracts:
  - repository-native Change Archive rerun compatibility
data_changes: []
---

# 变更摘要

为已在旧版单 Change workflow 下失败的历史 Change Archive run 增加安全恢复兼容：GitHub rerun 会继续使用原事件时的旧 workflow YAML，因此即使 main 上脚本已经支持多 Change，旧 workflow 仍只接受一组 source/target。当前修复只在 `GITHUB_RUN_ATTEMPT > 1` 时逐个处理仍 active 的 Change，并向旧 workflow 输出兼容的顶层 `change_id/source/target`；正常首次运行继续批量归档。

# 背景、现状与问题

PR #580 的产品实现已经合并，后续 PR #648 已修复 repository-native Change Archive，使新 workflow 支持多 Change 并完成自身自动归档。

随后对 PR #580 原失败 run `36396828934` 执行 rerun：main 上的新脚本成功识别两个 Active Change 并生成 4 个合法 staged path，但 GitHub rerun 固定复用 #580 当时的旧 workflow YAML。旧 YAML 只读取顶层 `source/target` 并要求 staged diff 恰好 2 个路径，因此在 verify step 失败且未 push。

需要在不手工归档、不绕过专用 App 和 exact allowlist 的前提下，让历史失败 run 通过原 workflow 逐项恢复。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑约束 |
| --- | --- | --- | --- |
| E1 | PR #648 已合并且新 Change Archive run 36401947356 success | GitHub PR #648 | 新 workflow/批量机制有效 |
| E2 | PR #580 rerun attempt 2 的 archive script step success | run 36396828934 / attempt 2 | 新脚本能正确归档两个 Change |
| E3 | 同一 rerun 的 verify step 因旧 YAML 只接受 2 个 path 而失败 | job 108866828700 | 问题是历史 workflow 兼容，不是归档逻辑 |
| E4 | rerun checkout 的是 current main，因此脚本可使用 main 上修复后的实现 | job 108866828700 | 可通过脚本兼容恢复旧 run |
| E5 | 旧 workflow 只有在 `changed=true` 后才读取顶层 `change_id/source/target` 并 commit/push | PR #580 merge revision workflow | 单次恢复必须只产生一组路径 |

# 目标、成功标准与非目标

## 目标 / 成功标准

- [x] AC1：首次运行（attempt=1）保持当前 0..N Change 批量归档行为。
- [x] AC2：历史 rerun（attempt>1）且存在多个 changed-path Change 时，一次只选择一个仍 active 的 Change。
- [x] AC3：如果前一个 Change 已归档，下一次 rerun 自动选择下一个仍 active Change。
- [x] AC4：当一次实际只改变一个 Change 时，batch JSON 同时输出旧 workflow 需要的顶层 `change_id/source/target`。
- [x] AC5：所有 merged revision/current-main/status/lifecycle/exact allowlist/App 权限门禁保持不变。
- [ ] AC6：本修复进入 main 后连续重跑 PR #580 Change Archive，直到两个遗留 Change 均归档为 done。

## 非目标

- 不修改产品代码、业务 Contract、Schema/Migration、Runtime 或 Release。
- 不手工搬运 PR #580 Change。
- 不让正常新 workflow 退化为一次只归档一个 Change。
- 不绕过 GitHub App、main drift guard 或旧 workflow 自身 exact allowlist。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 兼容触发 | 仅 `GITHUB_RUN_ATTEMPT > 1` 进入逐项恢复 | E3、E4 | 正常首次运行不受影响 |
| 选择顺序 | changed paths 稳定顺序中第一个仍 active 的 Change | E5 | 每次 staged diff 恰好一组 source/target |
| 已归档项 | source 不存在时跳到下一个 active；全部归档则 changed=false | E2 | 重复 rerun 幂等 |
| JSON 兼容 | batch items[] 保留；仅恰好一个 changed item 时附顶层 legacy fields | E5 | 新旧 workflow 都可消费 |
| 安全门禁 | 原子 archive helper 不变 | E2 | 不降低身份/状态/生命周期校验 |

# 修改方案与决策依据

1. 在 `ArchiveBatchResult.as_dict()` 中，当且仅当一次只有一个 `changed=true` item 时补顶层 `change_id/source/target`。
2. 增加 `_github_run_attempt()`，严格解析 GitHub attempt，非 GitHub 环境默认 1。
3. 增加 `_selected_paths_for_run()`：首次运行返回全部 selected paths；rerun 多 Change 时返回第一个仍 active path；全部 archived 时保持幂等 no-op。
4. CLI 只对本次 selected run paths 读取 merged revision source 并执行现有 `archive_changes()`。
5. 新增 legacy top-level identity 与 rerun 逐项选择回归。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 首次运行仍批量归档 | user:continue-pr580-delivery / AC1 | satisfied | `_selected_paths_for_run(..., run_attempt=1)` 回归 |
| R2 | 历史 rerun 一次处理一个 active Change | user:continue-pr580-delivery / AC2 | satisfied | rerun selection helper + test |
| R3 | 后续 rerun 选择下一个 active Change | user:continue-pr580-delivery / AC3 | satisfied | source 删除后选择第二项回归 |
| R4 | 兼容旧 workflow 顶层 identity | user:continue-pr580-delivery / AC4 | satisfied | `ArchiveBatchResult.as_dict()` legacy fields test |
| R5 | 保持既有安全门禁 | user:continue-pr580-delivery / AC5 | satisfied | 复用现有 archive_change/archive_changes |
| R6 | PR #580 两个遗留 Change 最终归档 | user:continue-pr580-delivery / AC6 | explicitly_deferred | post-merge lifecycle；本修复进入 main 后连续 rerun #580 |

# 计划改动

| 文件 / 模块 | 修改 | 原因 |
| --- | --- | --- |
| `scripts/quality/archive_change_after_merge.py` | rerun attempt 兼容选择 + legacy JSON fields | 让旧 workflow 安全恢复 |
| `tests/unit/test_change_archive_automation.py` | 新增 rerun 兼容回归 | 固化恢复语义 |
| 本 Change | 追溯 #580 attempt 2 failure | 满足完成门禁 |

# 验证矩阵

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Behavior / Unit | required | 首次批量、rerun逐项、legacy JSON |
| Governance / Workflow | required | 原 workflow exact allowlist 兼容语义 |
| CI | required | current-head CI / Runtime |
| PostgreSQL / Full-stack | not_applicable | 无产品/DB 变化 |
| External Provider | not_applicable | 无 Provider |

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 正常新 workflow 被错误降级 | 只在 attempt>1 时逐项 | 首次运行回归 |
| 历史 rerun 重复执行 | 已归档 source 不存在则选择下一个；全归档 changed=false | 幂等 |
| 非法 attempt 环境 | fail closed | 严格正整数解析 |
| 数据/Schema/Migration | 不适用 | 无业务数据变更 |
| 回滚 | revert 本 PR | 已完成归档历史不回滚 |

# 文档、依赖、部署与发布影响

- 文档：仅当前 Change。
- 依赖：无新增/升级。
- Contract：仅归档脚本内部 JSON 向后兼容字段。
- Schema/Migration：不适用。
- Release/Deploy：不适用。

# 完成审计

- [x] upstream_re_read：已重读 #580 attempt 2 日志、当前 main archive script 与旧 workflow 行为。
- [x] change_coverage：AC1—AC5 均映射到 helper/JSON/test；AC6 属 post-merge lifecycle。
- [x] reverse_audit：已反查首次运行、首个 rerun、第二个 rerun、全部已归档和非法 attempt。
- [x] unresolved_cleared：当前实现范围无 blocker；最终 #580 archive 只依赖本修复先进入 main。

# 完成证据与状态

## 新鲜证据

- #580 Change Archive attempt 2：archive script step success；旧 workflow allowlist verify failure；未 push。
- 代码已增加 rerun 逐项恢复与 legacy JSON compatibility。
- 永久回归已覆盖一次只处理一个 active Change 和第二次选择下一个 active Change。
- current-head CI 待执行。

## 未验证内容与剩余风险

- 当前新 HEAD 的 CI 尚未执行。
- PR #580 两个 Active Change 尚未写入 main archive；必须等本修复合并后由 repository-native rerun 完成。

## 交付状态

- implementation: complete
- delivery: PR pending
- validation: incomplete
- main_fresh: not_applicable before merge
- change_archive: not_applicable before merge
- requirement_closure: R6 deferred to post-merge lifecycle
- cleanup: pending
- end_to_end: incomplete
