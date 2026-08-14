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
affected_paths: [backend/src/aima_ugc/platform/jobs/, backend/src/aima_ugc/adapters/persistence/postgres/jobs.py, backend/src/aima_ugc/database_schema.py, backend/src/aima_ugc/bootstrap/worker.py, backend/src/aima_ugc/entrypoints/worker_main.py, migrations/versions/, tests/unit/jobs/, tests/integration/jobs/, .github/workflows/stage4-job-runtime.yml, docs/blueprint/README.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/07-技术决策与实施门禁.md, docs/测试与调试说明.md]
contracts: [JobPayloadRegistry]
data_changes: [jobs, job_attempt_events]
---

# 目标

建立 Stage 4 PostgreSQL Job Runtime，使长任务具备可恢复、可并发、可审计的持久化状态机：版本化 Payload Registry、内部幂等入队、原子 Claim/Lease takeover、Heartbeat、Fencing、重试、取消、Attempt Deadline、Platform Reaper 与 Worker 执行闭环。

# 可观察成功标准

- [x] `jobs` 与 `job_attempt_events` 由第二条 Alembic Revision 建立，表 Owner 为 `platform`，约束与 Blueprint 一致。
- [x] `job_type + internal_idempotency_key` 保证内部工作项幂等；同键但不同 Payload 关闭失败，不静默复用。
- [x] Worker 只 Claim Registry 支持的 Job 类型；Payload 由对应版本的 Pydantic Model 校验，未知类型不被认领。
- [x] Claim 使用单条 `UPDATE ... RETURNING` 原子认领 queued Job，或接管 Lease 过期但 Deadline 未到的 running Job。
- [x] queued → running 才递增 `attempt`；Lease takeover 保持同一 Attempt/Deadline，只递增 `lease_takeover_count` 并更换 Token。
- [x] Heartbeat 只延长 Lease 且不超过 `attempt_deadline_at`，不能延长 Deadline；取消、过期 Lease 或 Deadline 到达后续租失败。
- [x] 成功、失败、重试、取消、进度和续租均以当前 `lease_token` Fencing；旧 Token 更新零行并按 `lease_lost` 处理。
- [x] Reaper 与 Claim 职责分离：Deadline 到达时按重试次数重新排队或超时失败；running 取消且 Lease 过期、queued 取消均有界收敛。
- [x] Claim、takeover、retry 与终态转换和 `job_attempt_events` 在同一事务完成；事件仅保存 Token SHA-256 指纹，不保存原 Token，并保留终态 Worker 身份。
- [x] Fake Handler 可通过正式 Worker 生产实现独立验证，不需要前端、Scheduler、Provider 或真实外部 HTTP。
- [x] PostgreSQL 18 集成测试覆盖幂等、Claim/takeover、Deadline、Heartbeat、Fencing、重试、取消、Reaper、终态审计和陈旧 Token。
- [ ] 第二条 Revision 在最终目标提交上同时验证 `base → head`、`20260813_0001 → head`、downgrade/re-upgrade 和 `alembic check`。
- [ ] Stage 1/2/3A/3B 既有门禁在最终目标提交继续通过，Stage 4 独立 PostgreSQL CI 最终全绿。
- [x] 相关 Blueprint/测试说明已准备同步当前实现；阶段编排修正为 Stage 4 Job Runtime、Stage 5 Provider Request/Attempt/Raw、Stage 6 Content/Ingestion、Stage 7 最终多级预算 Ledger + Scheduler，最终预算 Schema/费用语义不改变。
- [ ] PR 合并后 main 重新验证成功，Change 才允许 done/archive。

# 范围

- Platform Job 表、模型和 PostgreSQL Repository；
- Job Payload Registry；
- Job Worker、Execution Context 和 Reaper；
- Worker bootstrap/entrypoint 装配；
- Stage 4 Unit/Integration Tests 与独立 CI；
- 第二条 Alembic Migration；
- 与本阶段直接相关的 Blueprint/测试说明同步。

# 非目标

- Scheduler、Collection Plan/Occurrence/Run；
- Provider Client/Operation/Request/Attempt、Raw、Mapper、Ingestion；
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

# 阶段编排冲突与决策

冻结的最终预算模型包含以下父事实外键：

- `provider_budget_accounts.run_id → collection_runs`；
- `provider_budget_accounts.content_id → contents`；
- `provider_budget_reservations.provider_request_id → provider_requests`；
- `provider_budget_reservations.provider_request_attempt_id → provider_request_attempts`。

因此不能在 Stage 4 为满足旧文字门禁而提前建立最终预算表，也不能去掉外键制造临时弱约束 Schema。

采用最小一致边界：

1. Stage 4：只建立可独立闭环的 PostgreSQL Job Runtime；
2. Stage 5：建立 Provider Request/Attempt、Raw 与费用事实；
3. Stage 6：建立单平台 Content/Ingestion 父事实；
4. Stage 7：Collection/Run 父事实齐全后建立最终 `provider_budget_accounts/provider_budget_reservations`，并与 Scheduler/多平台预算并发一起验收。

最终预算 Schema、Provider 费用规则和业务语义保持不变；不提前实现后续业务表，不建立临时兼容层。

# TDD 与 Review 证据

## 初始 Red

第一次 Red 因测试 import 排序失败，未计为有效 Red。修正测试格式且仍未写生产实现后：

- 通用 CI `31761088235`：Ruff/mypy 先通过，`pytest tests/unit` 因 `ModuleNotFoundError: aima_ugc.platform.jobs` 收集失败，退出码 2；
- Stage 4 专项 `31761344098`：PostgreSQL 18.4 与锁定环境成功，`pytest tests/unit/jobs -q` 因同一缺失模块失败，退出码 2。

## Review 缺陷 Red → Green

需求/质量 Review 发现终态事件在清空 `jobs.lease_owner` 后丢失 Worker 身份。先新增回归测试：

- Stage 4 `31763328680`：原有行为通过，新 `test_terminal_event_preserves_worker_identity` 唯一失败，实际 `worker_id=None`；陈旧 Token 终态 Fencing 测试同时通过。

修复后 `cc227696231e8d5ecd2956f10c3e5d43038431c3` 的 Stage 4 专项已证明 3 个 Unit + 9 个 PostgreSQL Integration 通过，且 Token 仍只保存 SHA-256 指纹。

# 实施任务

1. [x] Red：建立 Registry/Job Runtime 行为测试并通过 GitHub Actions 观察正确 Red。
2. [x] Green：建立 `jobs/job_attempt_events` Table、Migration 与 PostgreSQL Repository。
3. [x] Green：实现 Registry、Worker Execution Context、自动 Heartbeat、状态结果和 Reaper。
4. [x] 建立 Stage 4 PostgreSQL 集成测试与专用 CI。
5. [x] 同步 Worker bootstrap/entrypoint、数据库机器注册和架构硬门禁。
6. [x] Review 发现终态 Worker 审计缺陷后完成独立 Red → Green 回归。
7. [ ] 在最终 PR 目标提交执行完整通用 CI + Stage 4 双 Migration 路径 CI。
8. [ ] PR Ready/Review/合并后重新验证 main，成功后归档 Change 并清理本分支。

# 验证计划

- `uv lock --check`
- `uv run ruff format --check backend tests scripts`
- `uv run ruff check backend tests scripts`
- `uv run mypy backend/src`
- `uv run pytest tests/unit/jobs -q`
- `uv run pytest tests/integration/jobs -q`
- `uv run pytest tests/unit -q`
- `uv run pytest tests/contracts -q`
- `uv run pytest tests/integration -q`
- `uv run pytest tests/api -q`
- `uv run python scripts/contracts/generate.py --check`
- `uv run python scripts/contracts/check_compatibility.py`
- `uv run python scripts/quality/check_architecture.py`
- `uv run python scripts/quality/check_table_ownership.py`
- `uv run python scripts/quality/scan_secrets.py`
- `uv run python scripts/quality/check_docs.py`
- Stage 4 CI：`base → head` 与 `20260813_0001 → head`、两条 downgrade/re-upgrade、`alembic check`
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
- 当前实现 HEAD：`cc227696231e8d5ecd2956f10c3e5d43038431c3`（文档/最终门禁提交待追加）
- PR：`#16` Draft，base=`main`
- 合并：未执行
- Change 归档：未执行
