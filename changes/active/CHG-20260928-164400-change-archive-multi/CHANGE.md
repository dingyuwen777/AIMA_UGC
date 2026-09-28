---
schema: coding-change/v1
id: CHG-20260928-164400-change-archive-multi
title: 支持单个已合并 PR 确定性归档多个 Active Change
level: L2
status: ready_for_review
owner: chatgpt
branch: fix/580-change-archive-multi
created: 2026-09-28
updated: 2026-09-28
completion_gate: required
depends_on:
  - CHG-20260917-180708-representative-selection-feishu-sync
  - CHG-20260923-115743-report-strategy-feishu-publication
affected_areas:
  - governance
  - ci
  - change-archive
affected_paths:
  - scripts/quality/archive_change_after_merge.py
  - .github/workflows/change-archive.yml
  - tests/unit/test_change_archive_automation.py
contracts:
  - repository-native Change Archive
data_changes: []
---

# 变更摘要

修复 PR #580 合并后的 repository-native Change Archive 失败：当前自动化把“一个 Implementation PR 只能包含一个 Active Change”写成硬限制，而 PR #580 合法地同时交付两个相互依赖的 gated Change，导致归档 run 36396828934 在产品/运行代码已经成功合并后无法完成 post-merge finalization。

本变更保持归档的 fail-closed 与 exact allowlist，不允许通用 changes/ 写入；只把单 Change 确定性归档扩展为同一 merged PR 中 N 个明确 Active Change 的批量确定性归档。

# Requirement Source / 已确认事实

- user:continue-pr580-delivery：用户要求 PR #580 修复完成后合并 main 并完成收尾。
- GitHub PR #580：已合并到 main，merge commit `07c0c7dc7e1bf4cc782e4822ccfaa54a455f6552`。
- Change Archive run `36396828934`：失败原因为“当前发现 2 个 Active Change”，不是配置、权限或产品代码失败。
- 当前 `.github/workflows/change-archive.yml` 已使用专用 App、当前 main、merged revision、changed-files allowlist 和串行 push；这些安全边界必须保持。

# 目标 / 成功标准

- AC1：归档脚本可从 merged PR changed files 确定性选择 0..N 个 Active Change。
- AC2：每个 Change 都必须来自该 merged revision，当前 main 内容必须与 merged revision 一致，且 status=ready_for_review。
- AC3：每个 Change 只允许 `active/<id>/CHANGE.md → archive/YYYY-MM/<id>/CHANGE.md`，正文不变，仅冻结 status/updated。
- AC4：Workflow staged diff exact allowlist 等于所有本次 changed item 的 source/target 集合；任何额外路径均失败。
- AC5：0 个 Change 继续安全 no-op；单 Change 现有行为保持兼容；重复 dispatch 对已经归档的同一 merged revision保持幂等。
- AC6：新增多 Change regression，并保留 active/archive 冲突、main 漂移、非 ready 状态、生命周期冻结等既有保护。
- AC7：修复 PR 合并后，使用 repository-native workflow_dispatch 重跑 PR #580，两个遗留 Active Change 均归档为 done。

# 非目标

- 不手工归档 PR #580 的两个 Change。
- 不降低 Change schema、ready_for_review、merged revision、main ancestor、exact diff allowlist 或专用 App 权限门禁。
- 不修改产品代码、Schema/Migration、Runtime、业务 Contract 或 Release/Deploy。

# 方案

1. 保留现有单 Change `archive_change()` 作为原子归档 helper。
2. 新增 `select_changes()` 与 batch result；CLI 针对所有 matched Active Change逐一读取 merged revision source 后调用原子 helper。
3. Workflow 从 JSON `items[]` 生成期望 source/target 路径集合，与 staged diff 做排序后的严格集合比较。
4. Commit message 使用批量 Change ID 摘要；仍只在 exact allowlist 验证后由专用 Archivist push main。
5. 用单 Change + 多 Change + 幂等 + 额外 diff 拒绝的测试证明行为。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 支持同一 merged PR 的多个 Active Change | run 36396828934 / AC1 | satisfied | `select_changes()` + `archive_changes()` batch 编排 |
| R2 | 保持 merged revision/current-main 身份绑定 | existing archive contract / AC2 | satisfied | 复用 `merged_source_at_revision` 与 `archive_change` |
| R3 | 保持生命周期最小冻结 | existing archive contract / AC3 | satisfied | 复用 `freeze_lifecycle` |
| R4 | 多 Change exact diff allowlist | run 36396828934 / AC4 | satisfied | Workflow 从 `items[]` 生成 expected paths，与 staged diff 严格比较 |
| R5 | 单 Change/no-op/幂等兼容 | existing tests / AC5 | satisfied | 既有测试保留；新增 multi select/archive/rerun regressions |
| R6 | 不降低既有安全门禁 | project governance / AC6 | satisfied | 单 Change helper 仍拒绝多 Change 误用；merged revision/current-main/status/lifecycle 门禁均复用 |
| R7 | PR #580 post-merge archive 完成 | user:continue-pr580-delivery / AC7 | explicitly_deferred | post-merge lifecycle：本修复进入 main 后由 repository-native workflow 对 #580 执行恢复归档 |

# 验证矩阵

| Layer | Required | Evidence |
| --- | --- | --- |
| Behavior / Unit | required | change archive automation 单/多 Change、幂等、拒绝路径 |
| Governance / Workflow | required | workflow structure + exact allowlist |
| CI | required | current-head CI/quality |
| Runtime / Product | not_applicable | 不改产品运行实现 |
| External Provider | not_applicable | 无外部 Provider |

# 完成审计

- [x] upstream_re_read：已重读 PR #580、失败 run 36396828934、当前 archive script/workflow 和 repository-native Archive Contract。
- [x] change_coverage：AC1—AC6 已映射到 batch script、workflow exact allowlist 与永久回归；AC7 明确属于 post-merge lifecycle。
- [x] reverse_audit：已反查 0 Change、单 Change、多 Change、重复 dispatch、非 ready、active/archive 冲突、merged revision/main 漂移和额外 staged path。
- [x] unresolved_cleared：当前实现范围无未解决 blocker；PR #580 实际归档仅依赖本修复先进入 main。

# 交付状态

- implementation: complete
- delivery: pr_ready
- validation: pending current-head CI
- main_fresh: not_applicable before merge
- change_archive: not_applicable before merge
- requirement_closure: incomplete
- cleanup: incomplete
- end_to_end: incomplete
