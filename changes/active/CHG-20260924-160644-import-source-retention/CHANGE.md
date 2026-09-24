---
schema: coding-change/v1
id: CHG-20260924-160644-import-source-retention
title: 统一数据导入源 Artifact 七天生命周期
level: L2
status: proposed
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

- [ ] `data-import.source` / `historical-import.source` 非终态不进入 7 天到期清理。
- [ ] `succeeded / failed / partial_failed / cancelled` 终态使用当前 Campaign `finished_at + 7 days`。
- [ ] retry-failed 重新活动时旧截止时间同步失效，再次终态后重新计算。
- [ ] 未引用 `data-import.source` 复用现有 1 天 orphan 清理。
- [ ] 旧 Import / Provider Raw / Export / Canonical 行为保持。
- [ ] required 测试、Review、CI、main-fresh、Change archive 与 Issue closure 完成。

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

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | 非终态统一 Source 不可被 7 天 TTL 清理 | #595 AC1 | not_satisfied | Red integration 待取得 |
| R2 | 四种 Campaign 终态均从 `finished_at` 起保留 7 天 | #595 AC2 | not_satisfied | Red integration 待取得 |
| R3 | retry-failed 使旧 expiry 失效，再终态重新计时 | #595 AC3 | not_satisfied | Red Golden Path 待取得 |
| R4 | 未引用 `data-import.source` 使用现有 1 天 orphan | #595 AC4 | not_satisfied | Red integration 待取得 |
| R5 | 旧 Artifact/Canonical/业务事实兼容 | #595 AC5 | not_satisfied | 相关回归与 Review 待取得 |
| R6 | Review / CI / merge / main-fresh / archive / closure 完整交付 | #595 AC6 | not_satisfied | 交付阶段待取得 |

# 实施计划

1. **Red**：补 PostgreSQL retention 回归和现有 retry Golden Path 断言，证明当前 main 的缺口。
2. **Green**：在 Platform Artifact metadata 中统一计算 Campaign Source TTL，并在 Historical retry 事务中撤销旧 expiry；扩展 orphan kind。
3. **Docs targeted**：同步 Blueprint 03 和 Artifact 生命周期专题中的统一 Data Import Source 规则。
4. **验证与 Review**：目标 PostgreSQL Integration → 相关 Unit/Integration → quality gates → Standard Review。
5. **交付**：PR current-head CI → guarded merge → main-fresh → repository-native Change archive → #595 AC Evidence 回写与关闭 → 分支清理。

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| 行为 / Unit / Component | required | Retention policy / deadline reconciliation 的直接回归 |
| 接口 / Contract | not_applicable | 不改变 HTTP/Pydantic/OpenAPI/generated client |
| 集成 / Persistence / Runtime Dependency | required | 真实 PostgreSQL 下 terminal/active/orphan/CAS 与 retry expiry |
| 用户 / Workflow Acceptance | required | 现有 Historical Campaign retry HTTP + Worker Golden Path |
| 跨组件 Golden Path | required | Source Artifact → Campaign → Worker/retry → PostgreSQL retention |
| External Dependency / Provider Probe | not_applicable | 不改变 TikHub/LLM/外部 API |
| Build / Package / Runtime | required | PR CI 的 Python / deployable stack 等现有 required checks |
| Docs / Governance / Other | required | targeted docs、Completion Audit、Review、Change gate、main-fresh |

# 风险、兼容性与回滚

- **主要风险**：终态和 retry 并发时旧 expiry 穿透活动态；通过事务内 expiry 失效和 cleanup 当前状态守卫覆盖。
- **兼容**：无公共 Contract、Schema、数据格式或依赖变化。
- **Migration**：不适用；只使用现有列与关系。
- **部署**：随普通应用版本发布；Scheduler 正常运行后旧统一 Source Artifact 会按当前 Campaign 状态补齐 TTL。
- **回滚**：代码回滚会停止新规则继续应用，但已经由 housekeeping 物理删除的超期 Source bytes 不可由代码回滚恢复；业务数据库事实不受删除影响。

# Completion Audit

- [ ] upstream_re_read：Ready 前重读 #595、相关 Blueprint/Appendix 与最终机器事实。
- [ ] change_coverage：逐条映射 AC1-AC6，不以当前 Change 自证完整。
- [ ] reverse_audit：从 cleanup 反查 Campaign retry/活动态，从 retry 反查 Artifact delete_pending/expiry。
- [ ] unresolved_cleared：Ready 前 `not_satisfied` 清零或有正式延期依据。

# 当前状态

当前为 Red 阶段：先提交 Change 与失败回归，不包含生产修复。PR 在 Green、Docs、Completion、Review 和 required CI 完成前不得合并。
