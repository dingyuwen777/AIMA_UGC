---
schema: rvc-change/v1
id: CHG-20260814-stage4-job-runtime
title: Stage 4 PostgreSQL Job Runtime
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage4-job-runtime
created: 2026-08-14
updated: 2026-08-14
depends_on: [CHG-20260813-stage3a-database-foundation, CHG-20260813-stage3b-canonical-v1]
affected_areas: [platform, jobs, database, migration, worker, ci, blueprint, testing]
affected_paths: [backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/adapters/persistence/postgres/jobs.py, backend/src/aima_ugc/database_schema.py, backend/src/aima_ugc/bootstrap/worker.py, migrations/versions/, tests/unit/jobs/, tests/integration/jobs/, .github/workflows/ci.yml, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/04-后端任务API与前端.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/测试与调试说明.md]
contracts: [JobPayloadRegistry]
data_changes: [jobs, job_attempt_events]
---

# 目标

建立 Stage 4 PostgreSQL Job Runtime，使长任务具备可恢复、可并发、可审计的持久化状态机：版本化 Payload Registry、内部幂等入队、原子 Claim/Lease takeover、Heartbeat、Fencing、重试、取消、Attempt Deadline、Platform Reaper 与 Worker 执行闭环。

# 可观察成功标准

- [ ] `jobs` 与 `job_attempt_events` 由第二条 Alembic Revision 建立，表 Owner 为 `platform`，约束与 Blueprint 一致。
- [ ] `job_type + internal_idempotency_key` 保证内部工作项幂等；同键但不同 Payload 关闭失败，不静默复用。
- [ ] Worker 只 Claim Registry 支持的 Job 类型；Payload 由对应版本的 Pydantic Model 校验，未知类型不被认领。
- [ ] Claim 使用单条 `UPDATE ... RETURNING` 原子认领 queued Job，或接管 Lease 过期但 Deadline 未到的 running Job。
- [ ] queued → running 才递增 `attempt`；Lease takeover 保持同一 Attempt/Deadline，只递增 `lease_takeover_count` 并更换 Token。
- [ ] Heartbeat 只延长 Lease 且不超过 `attempt_deadline_at`，不能延长 Deadline；取消、过期 Lease 或 Deadline 到达后续租失败。
- [ ] 成功、失败、重试、取消、进度和续租均以当前 `lease_token` Fencing；旧 Token 更新零行并按 `lease_lost` 处理。
- [ ] Reaper 与 Claim 职责分离：Deadline 到达时按重试次数重新排队或超时失败；running 取消且 Lease 过期、queued 取消均有界收敛。
- [ ] Claim、takeover、retry 与终态转换和 `job_attempt_events` 在同一事务完成；事件仅保存 Token SHA-256 指纹，不保存原 Token。
- [ ] Fake Handler 可通过正式 Worker 生产入口独立验证，不需要前端、Scheduler、Provider 或真实外部 HTTP。
- [ ] PostgreSQL 18 集成测试覆盖幂等、Claim/takeover、Deadline、Heartbeat、Fencing、重试、取消、Reaper 和多 Worker 竞争。
- [ ] 第二条 Revision 验证 `base → head`、`20260813_0001 → head`、downgrade/re-upgrade 和 `alembic check`。
- [ ] Stage 1/2/3A/3B 既有门禁继续通过，Stage 4 增加独立 PostgreSQL CI Job。
- [ ] 相关 Blueprint/测试说明同步当前实现，预算阶段边界冲突被修正且最终 Provider 多级预算 Schema 不改变。

# 范围

- Platform Job 表、模型和 PostgreSQL Repository；
- Job Payload Registry；
- Job Worker、Execution Context 和 Reaper；
- Worker bootstrap 装配；
- Stage 4 Unit/Integration Tests 与 CI；
- 第二条 Alembic Migration；
- 与本阶段直接相关的 Blueprint/测试说明同步。

# 非目标

- Scheduler、Collection Plan/Occurrence/Run；
- Provider Client、Operation、Raw、Mapper、Ingestion；
- `provider_requests` / `provider_request_attempts`；
- `provider_budget_accounts` / `provider_budget_reservations`；
- Content/Comment 业务表；
- 真实付费外部 HTTP；
- Job HTTP API、前端页面、登录、Retention、生产部署。

# 必须保持不变

- 根 Python 工程、Python/Node/uv/npm 与现有依赖锁定版本；
- PostgreSQL 18 + SQLAlchemy 2 + Alembic + psycopg 3 技术路线；
- Stage 1–3B 已有公共 Contract、Migration、Artifact/System 表与 API 行为；
- Provider → Raw → Mapper → Canonical → Ingestion → Owner Repository 边界；
- Router 不写 SQL、Mapper 不访问数据库/HTTP、一个表只有一个写 Owner；
- Secret 不进入代码、日志、Raw、Job Payload 或数据库明文。

# 方案比较与已确认决策

## A. Stage 4 提前建立 Collection/Content/Provider 表

不采用。虽然能立即满足 Provider 多级预算表外键，但会把 Stage 5–7 的业务 Schema、Provider 语义和单平台纵切提前塞入 Job Runtime，违反阶段范围并扩大 Migration 风险。

## B. Stage 4 先建立去掉后续外键的弱约束预算表

不采用。它会制造与已冻结 `provider_budget_accounts/provider_budget_reservations` 不一致的中间数据契约，后续必须二次迁移并接受暂时无法约束的数据。

## C. 修正阶段边界：Stage 4 完成纯 Job Runtime，Provider 多级预算留在 Stage 5（采用）

预算最终模型和业务规则不变。Stage 4 只交付能独立闭环的 `jobs/job_attempt_events` 与 Worker/Reaper/Registry；Stage 5 在 `provider_request_attempts`、Collection/Content 依赖进入范围后一起实现 Provider 多级预算 Ledger。Provider HTTP/Raw 崩溃矩阵同理在 Provider/纵切阶段补齐，Stage 4 只证明 Job 层 Claim/Lease/Fencing/终态恢复。

这是对阶段编排矛盾的最小修正，不改变产品目标、最终 Schema 或技术路线。

# 实施任务

1. Red：先提交 Registry/Job Runtime 行为测试并通过 PR CI 观察因实现缺失失败。
2. Green：建立 `jobs/job_attempt_events` Table、Migration 与 PostgreSQL Repository。
3. Green：实现 Registry、Worker Execution Context、状态结果和 Reaper。
4. 完成 Stage 4 PostgreSQL 集成测试与专用 CI，包括上一正式 Revision → head。
5. 同步 Worker bootstrap、数据库机器注册、Blueprint 与测试说明。
6. 执行两阶段 Review 和完整 CI；PR 合并后再次验证 main，成功后归档 Change 并清理本分支。

# 验证计划

- `uv lock --check`
- `uv run ruff format --check backend tests scripts`
- `uv run ruff check backend tests scripts`
- `uv run mypy backend/src`
- `uv run pytest tests/unit/jobs -q`
- `uv run pytest tests/integration/jobs -q`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/check_table_ownership.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`
- `uv run alembic upgrade 20260813_0001`
- `uv run alembic upgrade head`
- `uv run alembic current`
- `uv run alembic check`
- `uv run alembic downgrade 20260813_0001`
- `uv run alembic upgrade head`
- 仓库完整 PR CI；合并后 main CI。

当前宿主无法 clone GitHub，因此本轮命令执行证据以 GitHub Actions 隔离环境为准；不会把静态检查或历史结果冒充本轮本地验证。

# 兼容、Migration、部署与回滚

- 公共 HTTP/Canonical Contract：不改变。
- 新增数据库表：`jobs`、`job_attempt_events`；不回填历史业务数据。
- 依赖/锁文件：不改变。
- 部署：本阶段不部署生产；代码部署必须先执行 Alembic `20260814_0002`。
- 回滚：在没有后续 Revision/生产 Job 数据依赖时可 downgrade 到 `20260813_0001` 并回退本 PR；若已存在真实 Job 数据，回滚前必须先停 Worker 并评估数据丢失，不能直接删除生产表。

# Git / PR

- 基线 main：`d8cb5bf92d3cb62c0a969ca3e0d2abb2c5a83ca6`
- 分支：`feature/stage4-job-runtime`
- Red Commit：待创建
- PR：待创建
- CI：待执行
- 合并：未执行
- Change 归档：未执行
