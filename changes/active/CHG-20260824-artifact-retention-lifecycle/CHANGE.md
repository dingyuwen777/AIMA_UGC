---
schema: rvc-change/v1
id: CHG-20260824-artifact-retention-lifecycle
title: Artifact 保留策略与自动清理
level: L3
status: ready_for_review
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

- [x] TikHub `provider-raw` 从 Artifact 创建时起保留 30 天，到期后自动删除字节，元数据和 Provider/Content 来源关系继续保留。
- [x] Excel `file-import.raw` 在 Import Batch 进入终态后保留 7 天；处理/重试期间不得提前删除。
- [x] `content-export.xlsx` 从生成完成时起保留 7 天；到期后不能继续作为可下载文件使用，用户可重新创建导出。
- [x] 当前可由业务父事实明确判定未引用的 Excel Import/Export 孤儿 Artifact 最多保留 1 天并可重试清理；Provider Raw 崩溃恢复证据不得被孤儿规则误删。
- [x] 清理采用 `delete_pending -> deleted` 状态收敛；实体删除失败时不得伪造 `deleted`，后续可重试。
- [x] Excel 导入前端明确显示“任务结束后保留 7 天”的规则，并在已知终态时显示对应到期时间/过期说明。
- [x] Excel 导出记录显示下载有效期；过期后下载按钮不可用并提示重新导出。
- [x] TikHub Provider Raw 作为后台审计/排障证据不新增普通业务前端入口。
- [x] 现有业务数据库事实、Content/Analysis/Export 父事实、来源关系和公共启动方式保持兼容。

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
- 不把未来未知 Artifact kind 在没有可验证父事实引用关系时机械套用 1 天孤儿删除。

# 必须保持不变

- PostgreSQL 仍是唯一业务事实库，ArtifactStore 只保存大字节对象。
- Provider Raw 的崩溃恢复和确定性 storage key 语义保持不变。
- Import Worker 在任务终态前始终可以从源 Artifact 重试。
- Excel Export 的冻结 Content Version 与现有 Excel Contract 不变。
- API / Worker / Scheduler / Migration 分进程边界不变，不新增基础设施依赖。
- 不升级 Python、Vue、PostgreSQL 或其他依赖。

# 关键决策

用户已确认保留策略：TikHub Provider Raw 30 天；Excel 上传源文件在 Import 终态后 7 天；Excel 导出文件生成后 7 天；孤儿字节按推荐采用短期清理。当前机器事实只有 Excel Import/Export 能通过既有父事实表安全证明“未建立业务引用”，因此 1 天孤儿规则只覆盖这两种 Excel kind；Provider Raw 明确排除，未来其他 Artifact kind 必须先建立可验证引用边界，不能仅凭 `stored` 状态推断为孤儿。

L3 方案比较：

1. **推荐并采用：现有 Artifact 状态机 + PostgreSQL 元数据 + Scheduler housekeeping。** 复用 `expires_at/delete_pending/deleted`，不新增服务；删除字节与状态提交分阶段，失败可重试。
2. API 请求时顺带清理：拒绝。会把磁盘维护耦合到用户请求，且没有请求时无法清理。
3. 独立 cron/sidecar：当前不采用。会新增部署分支和进程治理成本，现有 Scheduler 已提供低频后台执行边界。

兼容与迁移：不新增数据库列；已有 `artifacts.expires_at/deleted_at` 和删除状态足够。对历史 Artifact 由 housekeeping 幂等补齐保留截止时间，再按相同规则清理。部署只需要现有 Scheduler 正常运行；回滚代码不会恢复已经按用户批准策略删除的字节，因此回滚前应按生产备份策略评估不可逆数据删除。

并发删除边界：候选扫描只负责发现，不构成删除授权。真正执行 `stored/linked -> delete_pending` 时，PostgreSQL CAS 会重新检查当前 Artifact 是否仍已到期或仍属于无引用 Excel 孤儿；如果扫描后业务事务已经建立正式引用，本轮认领失败并放弃删除，避免 stale candidate 导致数据丢失。

# Requirement Traceability

| ID | Requirement | Source | Status | Evidence |
| --- | --- | --- | --- | --- |
| R1 | TikHub Provider Raw 保留 30 天 | user:2026-08-24-retention-decision | satisfied | `platform/storage/retention.py`、ArtifactService、Provider Raw 专项测试与 `docs/appendix/12_Artifact生命周期与保留策略.md` |
| R2 | Excel 上传源文件在 Import 终态后保留 7 天，运行/重试期间不提前删除 | user:2026-08-24-retention-decision | satisfied | `artifact_metadata.py` 终态回填含 cancelled Job fallback；真实 PostgreSQL Integration 与 Import Worker 回归覆盖 |
| R3 | Excel 导出文件完成后保留 7 天，过期后不能下载 | user:2026-08-24-retention-decision | satisfied | `reporting_http.py` 下载过期守卫、`completed_at + 7d` 回填、后端/API/Frontend 回归覆盖 |
| R4 | 可安全判定未引用的孤儿字节 1 天后清理，且不误伤 Provider Raw Recovery | user:2026-08-24-retention-decision | satisfied | 当前仅 Excel Import/Export 进入 1 天孤儿判定；Provider Raw 明确排除；真实 PostgreSQL Integration 覆盖扫描后建立引用时 CAS 拒绝删除 |
| R5 | 用户可见 Excel 文件保留/过期行为在现有前端入口展示 | user:2026-08-24-frontend-display | satisfied | `ImportBatchDetailDrawer.vue`、`DataExportDialog.vue`、`artifactRetention.ts`；Browser Mock 与 Real Full-stack 覆盖 |
| R6 | PostgreSQL 保存业务事实和 Artifact 元数据，文件字节由 ArtifactStore 管理 | docs/blueprint/03_数据库与文件存储.md | satisfied | 清理只更新 Artifact 生命周期字段并调用 Store.delete；Content/Import/Export/Provider 父事实不删除；Platform/Database Integration 覆盖 |
| R7 | 不绕过现有 API/Worker/Scheduler/Owner/CI 边界并保护最新 main | AGENTS.md | satisfied | Scheduler housekeeping 复用现有进程；无新依赖/Migration/公共 API；最新 main 已正常合入 feature；CI、Audit、Scheduler、Completion Gate 均已成功验证 |

# Validation Matrix

| Layer | Required | Scope / Evidence |
| --- | --- | --- |
| Browser Mock Acceptance | required | `frontend/e2e/artifact-retention.spec.ts` 覆盖 Import 终态时间 fallback、Export 7 天提示/有效期/下载资格；Frontend checks 已通过 |
| Backend/API/PostgreSQL Integration | required | 真实 PostgreSQL Integration 覆盖 TTL 回填、真实 Local Store 删除、Provider Raw 排除、取消任务与 stale candidate 并发回归；总 CI 已通过 |
| Contract / Generated Client | not_applicable | 本次未新增/修改公共 HTTP 字段，前端只读取已有 `finished_at/job.finished_at/completed_at`；OpenAPI/generated client drift/compatibility 检查通过 |
| Real Full-stack Golden Path | required | Stage 8F Full-stack Acceptance 已通过，真实 Frontend/API/Worker/PostgreSQL Excel Golden Path 接通 |
| Real Provider Probe | not_applicable | 本次不改变 TikHub endpoint、参数、响应、Mapper 或计费事实；无需付费真实 Probe，Provider Raw 专项回归已覆盖本次边界 |
| Docs / Governance / Other | required | `docs/appendix/12_Artifact生命周期与保留策略.md` 已同步；docs/architecture/secret gates、Audit、Change Completion Gate、Deployable Stack 已通过 |

# Completion Audit

- [x] upstream_re_read：已重新读取用户本轮保留决定、`AGENTS.md`、reliable-vibe-coding、Blueprint 03/04/05/06/07 与当前机器事实，独立重建完成定义。
- [x] change_coverage：已比较上游要求与当前 Change，并修正 Provider Raw 起点措辞、把 1 天孤儿规则收敛到当前可安全证明未引用的 Excel Import/Export Artifact；没有把 Change 自身当作需求全集。
- [x] reverse_audit：已从后端生命周期反查现有 Import/Export 前端入口，并从前端下载/状态反查后端真实守卫；Validation Matrix 各层证据与实际运行边界一致，TikHub Raw 无普通业务前端入口符合批准范围。
- [x] unresolved_cleared：R1-R7 均已有实现与当前验证证据；没有 `not_satisfied`，不适用层已有事实依据。

# 任务

- [x] 调查当前实现和事实源
- [x] 建立失败测试或说明测试例外
- [x] 建立并维护 Validation Matrix
- [x] 完成最小实现
- [x] 同步受影响文档
- [x] 取得新鲜验证证据
- [x] 完成 Requirement Traceability 与 Completion Audit

# 验证

## 计划

- 目标测试：Artifact policy/Local Store/cleanup；Import/Export retention；Frontend retention states。
- 相关测试：Provider Raw recovery、Import Worker、Data Export、Scheduler。
- 静态检查/构建：仓库现有 Python/Frontend lint、typecheck/build、OpenAPI 一致性与质量门禁。
- Ready Check：PR 由 Change Completion Gate 使用 changed-since 语义执行机器检查。

## 新鲜证据

- Red：提交 `e4ae8eb` 的真实 PostgreSQL Integration 为 `2 failed, 16 passed`；两处均因生产 Repository 尚不支持带 `now/orphan_before` 的原子删除认领，证明并发保护测试先于实现失败。
- Green：产品代码和长期文档完成后，最新完整 PR 流水线已经验证总 CI、真实 PostgreSQL、Frontend、Provider Raw、Scheduler、Real Full-stack、Audit、Change Completion Gate、Windows Compose 与 Deployable Stack 均成功；最终合并仍要求 GitHub 对最终 HEAD 再次给出相同门禁结果。

# 文档影响

- 新增并维护 `docs/appendix/12_Artifact生命周期与保留策略.md`，明确 30/7/7/1 天策略、只删除文件字节、Provider Raw Recovery 例外、历史回填、Scheduler housekeeping、删除认领并发 CAS 与前端可见行为。
- Blueprint 既有“PostgreSQL 保存事实、ArtifactStore 保存字节”边界保持不变，无需修改核心架构决策。

# 交付

- Commit：产品实现与长期文档已完成；本文件只保存稳定验收事实，不维护会因后续台账提交而变化的“最终 HEAD”字符串。
- PR：#187；转 Ready 和合并前必须确认最终 HEAD 的 Change Gate/CI，并重新检查最新 main/merge diff。
- 发布：未部署；本 Change 不改变依赖、Migration 或启动命令，已删除字节不可由代码回滚恢复。