---
schema: coding-change/v1
id: CHG-20260928-164400-change-archive-multi
title: 支持单个已合并 PR 确定性归档多个 Active Change
level: L2
status: done
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

修复 PR #580 合并后的 repository-native Change Archive 失败：当前自动化把“一个 Implementation PR 只能包含一个 Active Change”写成硬限制，而 PR #580 合法地同时交付两个相互依赖的 gated Change，导致归档 run `36396828934` 在产品/运行代码已经成功合并后无法完成 post-merge finalization。

本变更保持归档的 fail-closed、merged revision 绑定和 exact allowlist，只把单 Change 确定性归档扩展为同一 merged PR 中 0..N 个明确 Active Change 的批量确定性归档。

# 背景、现状与问题

PR #580 已于 2026-09-28 合并到 `main`，merge commit 为 `07c0c7dc7e1bf4cc782e4822ccfaa54a455f6552`。其 merge revision 的产品 CI、Runtime Acceptance 和 Developer Tooling 均已通过；但 repository-native Change Archive run `36396828934` 在归档阶段失败。

失败日志明确显示，专用 Archive App token、current main checkout、merged PR facts 都成功，真正失败点是归档脚本发现两个 Active Change 后主动报错：

`一个 Implementation PR 只能由归档自动化确定性处理一个 Active Change`

这说明问题不在权限、网络、产品实现或 Change 本身，而在 archive automation 把“单 Change”实现细节错误提升成了跨项目流程不变量。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 / 定位 | 支撑约束 |
| --- | --- | --- | --- |
| E1 | PR #580 已合并且 main 当前等于 merge commit `07c0c7dc` | GitHub PR #580 + main compare | 不回滚已完成产品交付 |
| E2 | merge commit 的 push CI、Runtime Acceptance、Developer Tooling 均 success | runs `36396830760`、`36396830351`、`36396830303` | 产品 main-fresh 已成立 |
| E3 | Change Archive run 的 App 配置、token、checkout、PR facts 都成功 | run `36396828934` / job `108845104470` | 不是权限或基础设施凭据问题 |
| E4 | 归档失败唯一直接原因是同一 PR 出现 2 个 Active Change | run `36396828934` 日志 | 需要支持多 Change batch |
| E5 | 当前单 Change helper 已校验 merged revision ancestor、current main 内容、schema/id/status、生命周期最小冻结 | `archive_change_after_merge.py` | 批量层应复用，不复制/弱化 |
| E6 | Workflow 已使用专用 App、串行 concurrency、current main checkout、exact staged diff allowlist | `.github/workflows/change-archive.yml` | 多 Change 仍必须 fail closed |

# 目标、成功标准与非目标

## 目标 / 成功标准

- [x] AC1：归档脚本可从 merged PR changed files 确定性选择 0..N 个 Active Change。
- [x] AC2：每个 Change 都必须来自该 merged revision，当前 main 内容必须与 merged revision 一致，且 status=`ready_for_review`。
- [x] AC3：每个 Change 只允许 `active/<id>/CHANGE.md → archive/YYYY-MM/<id>/CHANGE.md`，正文不变，仅冻结 `status/updated`。
- [x] AC4：Workflow staged diff exact allowlist 等于所有本次 changed item 的 source/target 集合；任何额外路径均失败。
- [x] AC5：0 个 Change 继续安全 no-op；单 Change 现有行为保持兼容；重复 dispatch 对已经归档的同一 merged revision 保持幂等。
- [x] AC6：新增多 Change regression，并保留 active/archive 冲突、main 漂移、非 ready 状态、生命周期冻结等既有保护。
- [ ] AC7：本修复合并后，由 repository-native 流程恢复归档 PR #580 的两个遗留 Active Change。

## 非目标

- 不手工移动或改写 PR #580 的两个 Change 来冒充自动归档成功。
- 不降低 Change schema、`ready_for_review`、merged revision、main ancestor、exact diff allowlist 或专用 App 权限门禁。
- 不修改产品代码、Schema/Migration、Runtime、业务 Contract、Release 或 Deploy。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 批量边界 | 只对 merged PR changed files 明确出现的 Active Change 建 batch | E4、E5 | 不扫描/猜测其他 Active Change |
| 单 Change 原子门禁 | 保留 `archive_change()` 作为单 Change 安全 Owner | E5 | batch 不复制 schema/status/lifecycle 校验 |
| merged revision 身份 | 每个 source 都独立从 merged revision 读取，并要求 current main 内容一致 | E5 | 后续 main 改写会 fail closed |
| Workflow allowlist | expected paths 从实际 changed items 的 source/target 生成并与 staged diff 严格集合比较 | E6 | N 个 Change 只允许 2N 个精确路径 |
| 权限 | 继续只由 change-archive-main Environment 的专用 App push main | E3、E6 | 不新增通用 contents:write |
| 恢复 #580 | 修复进入 main 后再由 repository-native 自动化处理 | Agent_Skills Archive Contract | Agent 不手工接管 archive commit |

# 修改方案与决策依据

## 最小充分方案

1. 保留现有 `select_change()` / `archive_change()` 单 Change helper 兼容边界。
2. 新增 `select_changes()`，只解析 merged PR changed paths 中符合 `changes/active/<id>/CHANGE.md` 的路径，按路径稳定排序。
3. 新增 `ArchiveBatchResult` / `archive_changes()`，对每个 selected Change 分别读取对应 merged revision source，并复用 `archive_change()`。
4. CLI 输出 `items[]`，每项保留 `changed/change_id/source/target/reason`。
5. Workflow 从所有 `changed=true` items 生成 expected source/target 文件，与 staged diff 排序后做 exact diff；expected path 数必须为大于等于 2 的偶数。
6. Commit message 使用批量 Change ID 摘要，其余 current-main drift 和专用 App push 门禁保持不变。
7. 新增多 Change selection、批量归档、批量幂等和单 helper 防误用回归。

## 备选方案与取舍

不采用“只归档两个 Change 中的一个”：会让另一个 Change 永久遗留 active，且无法解释同一 Implementation PR 的完成事实。

不采用“人工直接把两个 Change 移到 archive”：会绕过 repository-native Archivist、merged revision 绑定和 exact allowlist，掩盖基础设施缺陷。

不采用“把一个 PR 多 Change 永久禁止”：PR #580 已证明依赖 Change 可以合法共同构成一个完整交付；机械禁止不能解决真实使用路径。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 支持同一 merged PR 的多个 Active Change | user:continue-pr580-delivery / AC1 | satisfied | `select_changes()` + `archive_changes()` |
| R2 | 保持 merged revision/current-main 身份绑定 | user:continue-pr580-delivery / AC2 | satisfied | 逐 Change 复用 `merged_source_at_revision()` + `archive_change()` |
| R3 | 保持生命周期最小冻结 | user:continue-pr580-delivery / AC3 | satisfied | 继续复用 `freeze_lifecycle()` / `_verify_lifecycle_only()` |
| R4 | 多 Change exact staged diff allowlist | user:continue-pr580-delivery / AC4 | satisfied | Workflow `items[] → expected.txt → diff -u actual.txt` |
| R5 | 0/1/N Change 与 rerun 幂等兼容 | user:continue-pr580-delivery / AC5 | satisfied | 既有单 Change tests + 新增 batch tests |
| R6 | 不降低权限、schema、status、drift 等安全门禁 | user:continue-pr580-delivery / AC6 | satisfied | 原 helper 与 Workflow security boundary 保留 |
| R7 | PR #580 两个遗留 Active Change 真正归档 | user:continue-pr580-delivery / AC7 | explicitly_deferred | post-merge lifecycle；依赖本修复先进入 main 后由 repository-native automation 恢复 |

# 计划改动

| 文件 / 模块 | 修改 | 原因 |
| --- | --- | --- |
| `scripts/quality/archive_change_after_merge.py` | 新增 batch select/result/orchestration，CLI 输出 items | 支持 0..N Change |
| `.github/workflows/change-archive.yml` | 动态 exact allowlist 与批量 commit 摘要 | 保持 Workflow fail closed |
| `tests/unit/test_change_archive_automation.py` | 新增多 Change 与幂等回归 | 固化根因 |
| 本 Change | 追溯 run #36396828934 与 post-merge 恢复要求 | 满足治理门禁 |

# 验证矩阵

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Behavior / Unit | required | 单/多 Change selection、archive、rerun、错误边界 |
| Governance / Workflow | required | workflow trigger、专用 App、exact allowlist、main drift guard |
| Repository Quality / CI | required | current-head Requirement/quality/unit gates |
| PostgreSQL / Full-stack | not_applicable | 不改变 DB、产品调用链或用户业务 workflow |
| Runtime / Package | not_applicable | 只改 repository-native governance automation |
| External Provider | not_applicable | 无 Provider |

## 验证计划

- 运行 `tests/unit/test_change_archive_automation.py`、same-day/timezone 归档测试。
- 运行 Change Completion / PR Requirement Source / workflow structure 等仓库质量门禁。
- current-head CI 必须 green；不得通过跳过/降低测试让 CI 通过。
- merge 后确认本修复 Change 被 repository-native automation 自动归档。
- 随后恢复执行 PR #580 的 Change Archive，并确认两个原 Change 均进入 `changes/archive/2026-09/.../CHANGE.md` 且 `status: done`。

# 风险、兼容性、迁移与回滚

| 项目 | 结论 | 处理 |
| --- | --- | --- |
| 部分批次在本地工作树已移动、后续项失败 | Workflow 在任何脚本错误时不会进入 commit/push | runner 丢弃工作树；main 无部分归档 |
| allowlist 过宽 | 不允许目录级通配提交 | expected 精确来自 changed items 的 source/target |
| 单 Change 兼容 | 保留原 helper | 既有测试继续覆盖 |
| 重复 dispatch | 每个 item 独立验证 already_archived 与 merged source 一致 | 不一致即 fail closed |
| main 并发漂移 | 保留 ARCHIVE_PARENT/CURRENT_MAIN 比较 | 漂移停止 push，要求重跑 |
| Migration / 数据 | 不适用 | 无 Schema/数据变更 |
| 回滚 | revert 本 PR | 不影响已经归档的历史 Change；后续按真实 main 状态处理 |

# 文档、依赖、部署与发布影响

- 文档：仅当前 Change；不新增长期产品文档。
- 依赖：无新增/升级。
- Contract：仅 repository-native Change Archive JSON/workflow 内部契约扩展为 batch `items[]`。
- Schema/Migration：不适用。
- Release/Deploy：不适用。
- 生产数据：不触碰。

# 完成审计

- [x] upstream_re_read：已重读 PR #580、失败 run `36396828934`、当前 archive script/workflow 和 Agent_Skills repository-native Archive Contract。
- [x] change_coverage：AC1—AC6 均映射到 batch script、workflow exact allowlist 与永久回归；AC7 明确是 post-merge lifecycle。
- [x] reverse_audit：已反查 0 Change、单 Change、多 Change、重复 dispatch、非 ready、active/archive 冲突、merged revision/main 漂移和额外 staged path。
- [x] unresolved_cleared：当前实现范围无 unresolved blocker；PR #580 实际归档只依赖本修复先进入 main。

# 完成证据与状态

## 新鲜证据

- Failure evidence：Change Archive run `36396828934` / job `108845104470` 明确因 2 个 Active Change 失败。
- Static implementation review：batch 只编排 merged PR 明确 source，单 Change安全 helper 未被绕过。
- Runtime Acceptance run `36399784340` 已在初版 HEAD 成功；初版 CI 的失败仅来自 Change 文档 canonical headings，不来自实现测试。
- 本轮 canonical Change 结构修复后需以新 HEAD CI 作为最终证据。

## 未验证内容与剩余风险

- 当前新 HEAD 的正式 CI 尚待运行。
- PR #580 的两个原 Change 尚未归档；按 repository-native contract 不能在本修复合并前手工接管。
- 当前宿主 GitHub connector 未暴露 workflow_dispatch action；本修复进入 main 后优先使用 repository-native可用触发路径恢复 #580 archive，若宿主仍无法触发则如实报告该单一收尾权限/能力边界。

## 交付状态

- implementation: complete
- delivery: PR #648 open / current-head CI pending
- validation: incomplete
- main_fresh: not_applicable before merge
- change_archive: not_applicable before merge
- requirement_closure: R7 explicitly deferred to post-merge lifecycle
- cleanup: pending
- end_to_end: incomplete
