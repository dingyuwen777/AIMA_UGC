---
schema: coding-change/v1
id: CHG-20260924-160644-import-source-retention
title: 统一数据导入源 Artifact 七天生命周期
level: L2
status: ready_for_review
owner: yuwen.ding
branch: fix/595-import-source-retention
created: 2026-09-24T16:06:44+08:00
updated: 2026-09-24
completion_gate: required
depends_on: []
affected_areas:
  - platform-storage
  - ingestion
affected_paths:
  - backend/src/aima_ugc/platform/storage/
  - backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
  - backend/src/aima_ugc/adapters/persistence/postgres/historical_import.py
  - backend/src/aima_ugc/bootstrap/historical_import_http.py
  - tests/integration/database/test_artifact_retention_repository.py
  - tests/integration/ingestion/test_stage12_historical_campaign_worker.py
  - docs/blueprint/03_数据库与文件存储.md
  - docs/appendix/12_Artifact生命周期与保留策略.md
contracts: []
data_changes:
  - 只调整统一导入 Source Artifact 文件字节的 expires_at 与清理资格；不改变数据库 Schema、业务数据或 Canonical 内容
---

# 变更摘要

- **要解决的问题**：统一“导入数据”使用的 `data-import.source` / `historical-import.source` 没有继承既有 Excel Import Source 的 7 天文件字节生命周期，且 Campaign 允许终态后重试。
- **拟议修改**：让统一 Source Artifact 的 TTL 由 Campaign 当前生命周期驱动；终态写入 7 天截止时间，重试重新活动时撤销旧截止时间，并补齐本地上传 Source 的既有 1 天 orphan 清理。
- **预期结果**：源 Excel 在预检、导入和重试期间可稳定复用；Campaign 最终结束 7 天后自动释放 ArtifactStore 字节，而业务事实、来源账本和 Canonical Artifact 保留。

# 背景、现状与问题

## 当前现状

1. `IMPORT_SOURCE_RETENTION` 已固定为 7 天。
2. 旧 `file-import.raw` 会在 Import 终态后回填 `expires_at`。
3. 统一本地上传写 `data-import.source`，服务器目录快照写 `historical-import.source`。
4. 当前 retention deadline backfill 只匹配 `file-import.raw`。
5. `prepare_failed_retry()` 会复用同一个 Source Artifact，并把失败 Campaign 重新置为活动态。

## 问题与根因

统一导入新增 Source Artifact kind 时，没有把既有 Artifact retention 规则同步到新的 Campaign 生命周期。只把两个 kind 加进旧 Batch 终态查询也不充分：预检失败/取消可能没有普通 Import Batch，且失败 Campaign 可以重新进入重试活动态。

## 不修改的后果

统一导入源 Excel 字节可能长期留在 `.runtime/data/artifacts`；如果后续只增加一次性 TTL 而不处理重试重入，还可能在活动重试期间发生过期删除风险。

# 事实与证据

| 证据编号 | 已确认事实 | 来源 | 支撑的约束或决策 |
| --- | --- | --- | --- |
| E1 | Import Source 保留期为 7 天 | `platform/storage/retention.py` | 复用现有策略，不新增期限 |
| E2 | 统一 Source kind 为 `data-import.source` / `historical-import.source` | `historical_import_http.py` / `historical_import_worker.py` | 两种来源必须统一覆盖 |
| E3 | 当前 TTL 回填只匹配 `file-import.raw` | `artifact_metadata.py` | 已确认缺口 |
| E4 | 失败 Campaign 可重试并复用 Source Artifact | `historical_import.py::prepare_failed_retry` | TTL 必须支持活动态重入 |
| E5 | Artifact housekeeping 已有 1 天 orphan 与 `delete_pending → deleted` 安全状态机 | `artifact_metadata.py` / `artifact_cleanup.py` | 复用现有删除机制 |

## 推断与待确认

无。当前缺口、目标期限、重试路径和清理 Owner 均可由仓库及 Issue #595 确认。

# 目标、成功标准与非目标

## 目标

统一数据导入的原始 Excel Source Artifact 使用与现有 Import Source 一致、可重入且可验证的 7 天生命周期。

## 成功标准

- [x] `data-import.source` / `historical-import.source` 非终态不进入 7 天到期清理。
- [x] `succeeded / failed / partial_failed / cancelled` 终态使用当前 Campaign `finished_at + 7 days`。
- [x] retry-failed 重新活动时旧截止时间同步失效，再次终态后重新计算。
- [x] 未引用 `data-import.source` 复用现有 1 天 orphan 清理。
- [x] 旧 Import / Provider Raw / Export / Canonical 行为保持。
- [ ] required 独立 Review、正式 current-head CI、merge、main-fresh、Change archive 与 Issue closure 完成。

## 范围

- Artifact retention deadline reconciliation。
- cleanup eligibility / orphan 判定。
- Historical Campaign retry 与 Artifact TTL 的事务边界。
- 相关 PostgreSQL Integration、现有 Golden Path 回归和 targeted 文档。

## 非目标

- 不改变 Canonical Artifact retention。
- 不删除业务父事实、逐行账本、Artifact metadata 或来源关系。
- 不新增配置项、API、Schema、Migration、依赖、Scheduler 进程或文件管理能力。
- 不改变前端导入交互。

## 必须保持不变

- Campaign 活动期间 Source Artifact 必须可供预检、Worker 和 retry 使用。
- PostgreSQL 仍保存业务事实与 Artifact metadata；ArtifactStore 只保存大字节对象。
- 既有 `delete_pending → deleted`、CAS 删除认领与 Scheduler housekeeping 机制继续复用。

# 约束与意图决策

| 决策维度 | 当前决定 | 依据 | 影响 |
| --- | --- | --- | --- |
| 生命周期 Owner | 继续由 Platform Storage / Artifact metadata 负责 | E1/E5 | 不把 TTL 规则复制到 Worker |
| 终态时钟 | 使用 Campaign 当前 `finished_at` | Issue #595 / E4 | 覆盖无 Batch 的预检失败/取消与重试后的新终态 |
| 重试安全 | retry 事务内使旧 expiry 失效；cleanup 仍按当前状态重新判定 | E4/E5 | 防止旧 TTL 穿透活动重试 |
| Contract / Schema | 不变 | 当前实现 | 无 Migration / generated client |
| 删除范围 | 只删除 Source bytes | Issue #595 / Blueprint 03 | 业务事实和 Canonical 保留 |

# 修改方案与决策依据

采用现有 Artifact 生命周期机制做最小充分修复，不新增 Scheduler、配置或 Schema：

1. Platform Storage 继续作为 Artifact 生命周期唯一 Owner；新增统一 Source kind 集合，只用于生命周期判定。
2. `backfill_retention_deadlines()` 通过 Source Item → Campaign 关系判断当前状态：存在活动 Campaign 时清除 stale `expires_at`；全部终态时用最新 `finished_at + 7 days` 收敛截止时间。
3. cleanup 的最终 `delete_pending` CAS 同样重新检查是否存在活动 Campaign，避免“扫描后重试已启动”造成 stale candidate 误删。
4. `retry-failed` 与 Campaign 重入放在同一 PostgreSQL 事务中撤销旧 TTL；若 cleanup 已经先认领为 `delete_pending`，重试失败并整体回滚，不产生半激活状态。
5. `data-import.source` 加入与 `historical-import.source` 相同的未引用 orphan 判定；Canonical retention 不变。

不采用“终态时由 Worker 直接写一次 TTL”的方案，因为预检失败/上传取消不一定走普通 Import Batch，而且失败 Campaign 可再次重试，单次写入不能覆盖重入语义。

# 需求追溯

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 非终态统一 Source 不可被 7 天 TTL 清理 | #595 AC1 | satisfied | Red PR #597 Run 35974241664 证明旧行为失败；Green Run 35975130935 PostgreSQL Integration 通过；`artifact_metadata.py` 在 deadline reconcile 与删除认领两处检查活动 Campaign |
| R2 | 四种 Campaign 终态均从 `finished_at` 起保留 7 天 | #595 AC2 | satisfied | 两种 Source kind × 四类终态 PostgreSQL 回归通过；统一 deadline 使用 Campaign 当前 `finished_at + IMPORT_SOURCE_RETENTION` |
| R3 | retry-failed 使旧 expiry 失效，再终态重新计时 | #595 AC3 | satisfied | 真实 Historical Campaign retry Golden Path：失败终态先得到 expiry，retry HTTP 同事务清空，成功后按新 `finished_at + 7d` 重算；Green Run 35975130935 ingestion / Full-stack 通过 |
| R4 | 未引用 `data-import.source` 使用现有 1 天 orphan | #595 AC4 | satisfied | PostgreSQL orphan 回归覆盖 `data-import.source`，同时保留既有 `historical-import.source` / chunk / Canonical 行为 |
| R5 | 旧 Artifact/Canonical/业务事实兼容 | #595 AC5 | satisfied | Green Run 35975130935：CI Gate、PostgreSQL Integration、Real Full-stack、Runtime Acceptance、Developer Tooling Compatibility 均成功；无 Schema/Contract/依赖变化 |
| R6 | Review / CI / merge / main-fresh / archive / closure 完整交付 | #595 AC6 | explicitly_deferred | 属于实现 Ready 后的交付生命周期；独立 Standard Review 与正式 PR #596 current-head CI 后再 guarded merge，并在 merge 后完成 main-fresh / 自动归档 / Issue closure |

# 计划改动

1. **Red**：补 PostgreSQL retention 回归和现有 retry Golden Path 断言，证明当前 main 的缺口。
2. **Green**：在 Platform Artifact metadata 中统一计算 Campaign Source TTL，并在 Historical retry 事务中撤销旧 expiry；扩展 orphan kind。
3. **Docs targeted**：同步 Blueprint 03 和 Artifact 生命周期专题中的统一 Data Import Source 规则。
4. **验证与 Review**：目标 PostgreSQL Integration → 相关 Unit/Integration → quality gates → Standard Review。
5. **交付**：PR current-head CI → guarded merge → main-fresh → repository-native Change archive → #595 AC Evidence 回写与关闭 → 分支清理。

# 验证矩阵

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Artifact retention 回归已覆盖新 kind、四类终态、活动态和 orphan；Red/Green 证据来自 #597 |
| 接口 / Contract | not_applicable | 不改变 HTTP/Pydantic/OpenAPI/generated client；Green CI contract/generated drift 通过 |
| 集成 / Persistence / Runtime Dependency | required | Green Run 35975130935 在真实 PostgreSQL 18 上全部成功；分组结果含 53 / 103 / 141 / 73 / 63 / 2 passed |
| 用户 / Workflow Acceptance | required | 现有 Historical Campaign retry HTTP + Worker Golden Path 已验证旧 expiry 清空与新终态重新计时 |
| 跨组件 Golden Path | required | Green Run 35975130935 Real Full-stack Golden Path / Excel Browser Full-stack 成功 |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM/外部 API，不需要付费 Probe |
| Build / Package / Runtime | required | Green Run 35975130935 Wheel、Runtime Acceptance、Developer Tooling Compatibility 成功；正式 #596 current-head CI 待 Ready 后取得 |
| Docs / Governance / Other | required | Blueprint 03 与 Artifact 生命周期专题已 targeted 同步；Completion Audit 已完成；独立 Review、正式 CI、main-fresh 按交付阶段继续 |

# 风险、兼容性、迁移与回滚

- **主要风险**：终态和 retry 并发时旧 expiry 穿透活动态；通过事务内 expiry 失效和 cleanup 当前状态守卫覆盖。
- **兼容**：无公共 Contract、Schema、数据格式或依赖变化。
- **Migration**：不适用；只使用现有列与关系。
- **部署**：随普通应用版本发布；Scheduler 正常运行后旧统一 Source Artifact 会按当前 Campaign 状态补齐 TTL。
- **回滚**：代码回滚会停止新规则继续应用，但已经由 housekeeping 物理删除的超期 Source bytes 不可由代码回滚恢复；业务数据库事实不受删除影响。

# 完成审计

- [x] upstream_re_read：已重新读取 #595、Blueprint 03、Artifact 生命周期专题、最终 PR diff 与 Artifact/Campaign 生产调用链。
- [x] change_coverage：AC1-AC5 均有生产实现与直接回归；AC6 仅保留真实交付生命周期步骤，不把 CI Green 冒充 merge/main-fresh/archive/closure。
- [x] reverse_audit：从 cleanup 反查活动 Campaign 与 retry，从 retry 反查 `expires_at` / `delete_pending`；cleanup 先认领时 retry fail-closed，retry 先重入时 cleanup 当前事实重检拒绝删除。
- [x] unresolved_cleared：R1-R5 已 satisfied；R6 仅按生命周期 `explicitly_deferred`，没有 `not_satisfied`。

# Red / Green 证据

- Red：临时诊断 PR #597，commit `2353d519b6a8a777c0161fb962403bd9be2d9d8d`，CI Run `35974241664`。静态/Unit/API/架构门禁先通过，PostgreSQL Integration 因目标生命周期缺口得到 `11 failed / 92 passed`。
- Green：同一诊断 PR commit `21de7f9d55147e0b2fb1e19c0ef433833eda9d6a`，CI Run `35975130935`。CI Gate、PostgreSQL Integration、Real Full-stack、Runtime Acceptance、Developer Tooling Compatibility 均成功。
- Green PostgreSQL 分组输出：`53 / 103 / 141 / 73 / 63 / 2 passed`。
- 诊断 PR #597 已关闭且未合并；正式交付仅由 PR #596 承担。

# 文档、依赖、部署与发布影响

Docs Impact 为 targeted：同步 `docs/blueprint/03_数据库与文件存储.md` 与 `docs/appendix/12_Artifact生命周期与保留策略.md`，说明统一 Data Import Source 的 7 天期限、活动态/重试语义以及只删除 bytes 的边界。

依赖、Runtime、公共 Contract、Schema/Migration 均不变；无需新增配置。随普通应用版本发布即可，Scheduler 继续按现有 housekeeping 周期执行。已实际删除的超期 Source bytes 不可通过代码回滚恢复，但对应业务数据库事实、来源关系和 Canonical 不删除。

# 完成证据与状态

生产实现、回归、targeted 文档和 Completion Audit 已闭环，当前进入 `ready_for_review`。下一步执行独立 Standard Review 与 PR #596 最终 current-head required CI；只有两者均无阻断后才执行用户已授权的 guarded merge、main-fresh、repository-native Change archive 与 #595 closure。
