---
schema: rvc-change/v1
id: CHG-20260824-artifact-retention-lifecycle
title: Artifact 保留策略与自动清理
level: L3
status: proposed
owner: openai
branch: feature/artifact-retention-lifecycle
created: 2026-08-24
updated: 2026-08-24
completion_gate: required
depends_on: []
affected_areas:
  - platform-storage
  - ingestion
  - collection
  - reporting
  - frontend
affected_paths:
  - backend/src/aima_ugc/platform/storage/
  - backend/src/aima_ugc/adapters/storage/local/
  - backend/src/aima_ugc/adapters/persistence/postgres/artifact_metadata.py
  - backend/src/aima_ugc/bootstrap/
  - backend/src/aima_ugc/entrypoints/scheduler_main.py
  - frontend/src/features/import-batches/
  - frontend/src/features/voice-plaza/
  - docs/
  - tests/
contracts: []
data_changes:
  - artifacts.expires_at 将按既定保留策略写入或补齐；到期后仅删除 Artifact 字节并保留业务父事实、来源关系和 Artifact 元数据。
---

# 目标

为服务器上的 Artifact 建立可执行的保留与清理生命周期，避免 Excel 上传文件、Excel 导出文件和 TikHub Provider Raw 无限占用磁盘；同时在现有前端入口明确显示用户可见文件的保留期限与过期行为。

# 成功标准

- [ ] TikHub `provider-raw` 从完成存储时起保留 30 天，到期后自动删除字节，元数据和 Provider/Content 来源关系继续保留。
- [ ] Excel `file-import.raw` 在 Import Batch 进入终态后保留 7 天；处理/重试期间不得提前删除。
- [ ] `content-export.xlsx` 从生成完成时起保留 7 天；到期后不能继续作为可下载文件使用，用户可重新创建导出。
- [ ] 写入成功但未建立业务引用的非 Provider-Raw 孤儿 Artifact 最多保留 1 天并可重试清理；Provider Raw 崩溃恢复证据不得被孤儿规则误删。
- [ ] 清理采用 `delete_pending -> deleted` 状态收敛；实体删除失败时不得伪造 `deleted`，后续可重试。
- [ ] Excel 导入前端明确显示“任务结束后保留 7 天”的规则，并在已知终态时显示对应到期时间/过期说明。
- [ ] Excel 导出记录显示下载有效期；过期后下载按钮不可用并提示重新导出。
- [ ] TikHub Provider Raw 作为后台审计/排障证据不新增普通业务前端入口。
- [ ] 现有业务数据库事实、Content/Analysis/Export 父事实、来源关系和公共启动方式保持兼容。

# 范围

- Artifact TTL 规则与到期判定。
- Local ArtifactStore 安全、幂等删除能力。
- PostgreSQL Artifact 元数据的过期补齐、清理候选查询与状态收敛。
- Scheduler 进程中的低频 Artifact housekeeping。
- Excel Import / Export 用户界面的保留期限提示和过期状态。
- 相关单元、PostgreSQL Integration、API/Frontend 测试与文档同步。

# 非目标

- 不删除 Content、Comment、Analysis、Import Batch、Export 父事实或来源关系。
- 不实现 S3/对象存储。
- 不改变 PostgreSQL + Artifact 协调 Backup/Restore 设计。
- 不新增独立“文件管理”页面。
- 不把 TikHub Raw 字节暴露给普通业务前端。
- 不改变 TikHub API、采集字段、计费或 Provider Operation。

# 必须保持不变

- PostgreSQL 仍是唯一业务事实库，ArtifactStore 只保存大字节对象。
- Provider Raw 的崩溃恢复和确定性 storage key 语义保持不变。
- Import Worker 在任务终态前始终可以从源 Artifact 重试。
- Excel Export 的冻结 Content Version 与现有 Excel Contract 不变。
- API / Worker / Scheduler / Migration 分进程边界不变，不新增基础设施依赖。
- 不升级 Python、Vue、PostgreSQL 或其他依赖。

# 关键决策

用户已确认保留策略：TikHub Provider Raw 30 天；Excel 上传源文件在 Import 终态后 7 天；Excel 导出文件生成后 7 天；非 Provider-Raw 的未引用孤儿 Artifact 1 天。

L3 方案比较：

1. **推荐并采用：现有 Artifact 状态机 + PostgreSQL 元数据 + Scheduler housekeeping。** 复用 `expires_at/delete_pending/deleted`，不新增服务；删除字节与状态提交分阶段，失败可重试。
2. API 请求时顺带清理：拒绝。会把磁盘维护耦合到用户请求，且没有请求时无法清理。
3. 独立 cron/sidecar：当前不采用。会新增部署分支和进程治理成本，现有 Scheduler 已提供低频后台执行边界。

兼容与迁移：不新增数据库列；已有 `artifacts.expires_at/deleted_at` 和删除状态足够。对历史 Artifact 由 housekeeping 幂等补齐保留截止时间，再按相同规则清理。部署只需要现有 Scheduler 正常运行；回滚代码不会恢复已经按用户批准策略删除的字节，因此回滚前应按生产备份策略评估不可逆数据删除。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | TikHub Provider Raw 仅保留 30 天 | user:2026-08-24-retention-decision | not_satisfied | 待实现与验证 |
| R2 | Excel 上传源文件终态后保留 7 天 | user:2026-08-24-retention-decision | not_satisfied | 待实现与验证 |
| R3 | Excel 导出文件生成后保留 7 天 | user:2026-08-24-retention-decision | not_satisfied | 待实现与验证 |
| R4 | 非 Provider-Raw 未引用孤儿 Artifact 1 天后清理且不误伤 Provider Raw Recovery | user:2026-08-24-retention-decision | not_satisfied | 待实现与验证 |
| R5 | 用户可见 Excel 文件保留/过期行为在现有前端入口展示 | user:2026-08-24-frontend-display | not_satisfied | 待实现与验证 |
| R6 | PostgreSQL 保存业务事实和 Artifact 元数据，文件字节由 ArtifactStore 管理 | docs/blueprint/03_数据库与文件存储.md | not_satisfied | 待实现与验证 |
| R7 | 不绕过现有 API/Worker/Scheduler/Owner/CI 边界 | AGENTS.md | not_satisfied | 待 Review/CI |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | Import 保留提示、Export 有效期/过期下载状态 |
| Backend/API/PostgreSQL Integration | required | TTL 补齐、到期候选、状态 CAS、真实 Local Store 删除、Import/Export/Raw 生命周期 |
| Contract / Generated Client | not_applicable | 本方案不新增公共 API 字段；前端从已有 `finished_at/completed_at` 按固定策略展示 |
| Real Full-stack Golden Path | required | 现有 Import/Export 页面与后端生命周期在 CI 可用边界内完成关键链验证 |
| Real Provider Probe | not_applicable | 不改变 TikHub endpoint、响应结构、Mapper 或 Provider 行为，不需要付费真实 Probe |
| Docs / Governance / Other | required | Appendix/Blueprint 导航与 Change 保留策略同步；Ready Check |

# Completion Audit

- [ ] upstream_re_read：已重新读取所有上游正式事实源，并从它们独立重建完成定义。
- [ ] change_coverage：已确认当前 Change 覆盖全部上游要求，没有把 Change 自身当作需求全集。
- [ ] reverse_audit：已执行适用的反向能力/边界审计，并复核 Validation Matrix；不适用项已有明确依据。
- [ ] unresolved_cleared：所有 `not_satisfied` 已清零；延期/不适用项均有正式依据。

# 任务

- [x] 调查当前实现和事实源
- [ ] 建立失败测试或说明测试例外
- [x] 建立并维护 Validation Matrix
- [ ] 完成最小实现
- [ ] 同步受影响文档
- [ ] 取得新鲜验证证据
- [ ] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 目标测试：Artifact policy/Local Store/cleanup；Import/Export retention；Frontend retention states。
- 相关测试：Provider Raw recovery、Import Worker、Data Export、Scheduler。
- 静态检查/构建：仓库现有 Python/Frontend lint、typecheck/build、OpenAPI 一致性与质量门禁。
- Ready Check：`python .agents/skills/reliable-vibe-coding/scripts/ready_check.py --root . --require-active-ready`

## 新鲜证据

- 尚未执行。当前会话没有仓库终端，Red/Green 与完整验证将以 GitHub Actions/CI 新鲜运行结果为证据。

# 文档影响

- 新增 Artifact 生命周期/保留策略专题说明，并更新现有 Blueprint/Appendix 导航或受影响说明。

# 交付

- Commit：进行中
- PR：待创建
- 发布：本轮不部署、不合并 main
