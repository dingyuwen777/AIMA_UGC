---
schema: rvc-change/v1
id: CHG-20260814-stage4-job-runtime
title: Stage 4 PostgreSQL Job Runtime
level: L3
status: done
owner: dingyuwen777
branch: feature/stage4-job-runtime
created: 2026-08-14
updated: 2026-08-14
depends_on: [CHG-20260813-stage3a-database-foundation, CHG-20260813-stage3b-canonical-v1]
affected_areas: [platform, jobs, database, migration, worker, ci, blueprint, testing]
affected_paths: [backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/adapters/persistence/postgres/jobs.py, backend/src/aima_ugc/database_schema.py, backend/src/aima_ugc/bootstrap/worker.py, backend/src/aima_ugc/entrypoints/worker_main.py, migrations/versions/, tests/unit/jobs/, tests/integration/jobs/, .github/workflows/stage4-job-runtime.yml, docs/blueprint/README.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/测试与调试说明.md]
contracts: [JobPayloadRegistry]
data_changes: [jobs, job_attempt_events]
---

# 目标

建立 Stage 4 PostgreSQL Job Runtime，使长任务具备可恢复、可并发、可审计的持久化状态机：版本化 Payload Registry、内部幂等入队、原子 Claim/Lease takeover、Heartbeat、Fencing、重试、取消、Attempt Deadline、Platform Reaper 与 Worker 执行闭环。

# 完成范围

- `jobs` / `job_attempt_events` PostgreSQL 表、约束、索引和唯一 Platform 写 Owner；
- 第二条 Alembic Revision `20260814_0002`；
- `JobRegistry`、版本化 Pydantic Payload 校验和未知类型不认领；
- `PostgresJobRepository`：内部幂等入队、原子 Claim、Lease takeover、Heartbeat、Fencing、重试、取消、终态和事件账本；
- `JobWorker`、自动 Heartbeat、`JobReaper`、Fake Handler 正式执行闭环；
- Stage 4 Unit / PostgreSQL Integration / 独立 CI；
- Worker bootstrap/entrypoint、架构硬门禁、Blueprint 和测试说明同步。

# 非目标

- Scheduler、Collection Plan/Occurrence/Run；
- Provider Client/Operation/Request/Attempt、Raw、Mapper、Ingestion；
- `provider_budget_accounts` / `provider_budget_reservations`；
- Content/Comment 业务表；
- 真实付费外部 HTTP；
- Job HTTP API、前端页面、登录、Retention、生产部署。

# 成功标准结果

- [x] `jobs` 与 `job_attempt_events` 由第二条 Revision 建立，Owner=`platform`。
- [x] `job_type + internal_idempotency_key` 保证内部幂等；同键异 Payload 关闭失败。
- [x] Worker 只 Claim Registry 支持的类型，Payload 由注册的 Pydantic Model 按版本校验。
- [x] queued Claim 与 Deadline 前过期 Lease takeover 使用 PostgreSQL 原子认领；queued → running 才递增 Attempt。
- [x] Lease takeover 保持同一 Attempt/Deadline，只递增 `lease_takeover_count` 并更换 Token。
- [x] Heartbeat 不延长 Deadline；取消、过期 Lease、Deadline 到达或旧 Token 均不能续租。
- [x] 成功、失败、重试、取消、进度和续租由当前 `lease_token` Fencing。
- [x] Reaper 与 Claim 分工：普通过期 Lease 由 Claim 接管，Deadline/取消/次数耗尽由 Reaper 收敛。
- [x] Claim/takeover/retry/终态与 `job_attempt_events` 同事务；事件只保存 Token SHA-256 指纹并保留终态 Worker 身份。
- [x] Fake Handler 通过正式 Worker 实现独立验证，不需要 Scheduler/Provider/真实 HTTP。
- [x] PostgreSQL 18 测试覆盖幂等、Claim/takeover、Deadline、Heartbeat、Fencing、重试、取消、Reaper、终态审计和陈旧 Token。
- [x] 第二条 Revision 在最终 PR 和合并后 main 上验证 `base → head`、`20260813_0001 → head`、两种 downgrade/re-upgrade 与 `alembic check`。
- [x] Stage 1/2/3A/3B 既有门禁在最终 PR 和合并后 main 继续通过。
- [x] 相关 Blueprint/测试说明已同步阶段边界和当前实现。
- [x] PR #16 合并后 main 重新验证成功。

# 阶段编排决策

冻结的最终预算模型同时外键依赖：

- `provider_budget_accounts.run_id → collection_runs`；
- `provider_budget_accounts.content_id → contents`；
- `provider_budget_reservations.provider_request_id → provider_requests`；
- `provider_budget_reservations.provider_request_attempt_id → provider_request_attempts`。

因此没有为了旧 Stage 4 文字门禁提前建立后续业务表，也没有删除外键制造临时弱约束 Schema。最终阶段边界为：

1. Stage 4：PostgreSQL Job Runtime；
2. Stage 5：Provider Request/Attempt、Raw 与费用事实；
3. Stage 6：单平台 Content/Ingestion 父事实；
4. Stage 7：Collection/Run 父事实齐全后建立最终多级预算 Ledger，并与 Scheduler/多平台预算并发一起验收。

最终预算 Schema、Provider 费用规则和业务语义不变。

# TDD 与 Review 证据

## 初始 Red

第一次失败只来自测试 import 排序，不计为有效 Red。修正测试格式、仍未写生产实现后：

- CI `31761088235`：Ruff/mypy 先通过，`pytest tests/unit` 因 `ModuleNotFoundError: aima_ugc.platform.jobs` 失败，退出码 2；
- Stage 4 CI `31761344098`：PostgreSQL 18.4 和锁定环境成功，`pytest tests/unit/jobs -q` 因同一缺失模块失败，退出码 2。

## Review 缺陷 Red → Green

两阶段 Review 发现终态事件在清空 `jobs.lease_owner` 后丢失 Worker 身份：

- Stage 4 run `31763328680`：新回归测试 `test_terminal_event_preserves_worker_identity` 唯一失败，实际 `worker_id=None`；陈旧 Token 终态 Fencing 测试同时通过；
- 修复后用当前 Token 的 SHA-256 指纹关联既有 Claim/Takeover 事件恢复 Worker 身份，不保存原 Token；
- 后续 Stage 4 CI 3 个 Unit + 9 个 PostgreSQL Integration 全绿。

# 最终验证

实现 PR 最终目标提交：`cf7717eab3c3b36799057938ce8176efae1da949`。

PR 合并前：

- 通用 CI `31763979805`：success；
- Stage 4 Job Runtime `31763979835`：success。

PR #16 通过普通 Merge API 合并，merge commit：`5f9c4ab838e98f7a791fbfbd68ac047232099502`。

合并后 main：

- 通用 CI `31764203659`：completed / success；
- Stage 4 Job Runtime `31764203648`：completed / success；
- `uv run pytest tests/unit/jobs -q`：3 passed；
- `uv run pytest tests/integration/jobs -q`：9 passed；
- 空库 `base → head` 到 `20260814_0002` 成功，`alembic check` 无 drift；
- `head → base → head` 成功；
- `head → 20260813_0001 → head` 成功；
- 上一正式 Revision 保留 `artifacts/system_settings/audit_events`，Stage 4 两表正确移除后可重新升级。

当前宿主无法 clone GitHub，因此没有把远端状态冒充用户本地 `git status`，也没有声称运行过本地测试。所有执行证据来自 GitHub Actions。

# 兼容、Migration、部署与回滚

- 公共 HTTP/Canonical Contract：不改变；
- 新增数据库表：`jobs`、`job_attempt_events`，不回填历史业务数据；
- 依赖/锁文件：不改变；
- 本阶段未部署生产；未来部署此版本前必须执行 Alembic `20260814_0002`；
- 没有后续 Revision/真实 Job 数据依赖时可 downgrade 到 `20260813_0001` 并回退实现；已有真实 Job 数据时必须先停 Worker、评估数据丢失，不能直接删除生产表。

# Git / PR

- 基线 main：`d8cb5bf92d3cb62c0a969ca3e0d2abb2c5a83ca6`；
- 实现分支：`feature/stage4-job-runtime`；
- 实现 PR：#16；
- 实现最终 head：`cf7717eab3c3b36799057938ce8176efae1da949`；
- merge commit：`5f9c4ab838e98f7a791fbfbd68ac047232099502`；
- 合并后通用 CI：`31764203659` success；
- 合并后 Stage 4 CI：`31764203648` success；
- Change 状态：done，归档至 `changes/archive/2026-08/CHG-20260814-stage4-job-runtime/`；
- Change 收尾分支：`chore/archive-stage4-job-runtime-change`。
