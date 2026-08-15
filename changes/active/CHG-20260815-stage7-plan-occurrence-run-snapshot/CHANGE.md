---
schema: rvc-change/v1
id: CHG-20260815-stage7-plan-occurrence-run-snapshot
title: 建立 Stage 7 Plan、Occurrence 与 Run Snapshot 父事实
level: L3
status: in_progress
owner: dingyuwen777
branch: feature/stage7-plan-occurrence-run-snapshot
created: 2026-08-15
updated: 2026-08-15
depends_on: [CHG-20260815-stage7-provider-config-routing, CHG-20260815-stage7-keyword-packs]
affected_areas: [collection, system, database, jobs, testing, documentation]
affected_paths: [backend/src/aima_ugc/modules/collection/, backend/src/aima_ugc/adapters/persistence/postgres/, backend/src/aima_ugc/database_schema.py, migrations/versions/, tests/unit/collection/, tests/integration/collection/, docs/blueprint/03-数据库与文件存储.md, docs/blueprint/06-开发约束与分阶段实施.md, docs/blueprint/README.md, docs/collection/README.md, backend/src/aima_ugc/modules/collection/README.md, .github/workflows/]
contracts: []
data_changes: [collection_plans, collection_plan_platforms, collection_plan_keyword_packs, collection_schedule_occurrences, collection_runs.manual_plan_id, collection_runs.occurrence_id]
---

# 背景与现状

Stage 5B 已建立 `collection_runs/collection_scopes`，Stage 7 已建立 Provider Config 与 Keyword Pack，但当前 Run 仍只支持 `manual/api/backfill`，没有 Plan、Plan→Platform/Keyword Pack 关系、Schedule Occurrence 或 Scheduled Run 的数据库父事实。Blueprint 03 已冻结这些目标关系，同时 Blueprint 07 明确 Scheduler 的 misfire/catch-up 行为仍未批准。

# 目标

建立未来 Scheduler 和 Stage 8 Plan API 共用的最小数据库父事实：Plan、平台配置、词包关联、Occurrence，以及 Run 对 Plan/Occurrence 的不可歧义关联。当前 Change 只建立可约束数据模型和显式创建入口，不实现 Scheduler 行为。

# 成功标准

- `collection_plans`、`collection_plan_platforms`、`collection_plan_keyword_packs`、`collection_schedule_occurrences` 由 Collection Owner 管理并通过新 Alembic Revision 建立。
- Plan 首版时区只接受 `Asia/Shanghai`；`schedule_version >= 1`、`request_budget >= 0`、`max_catch_up_runs >= 0` 等稳定结构约束由数据库和 Domain 同时保护。
- Plan 平台关系必须引用稳定 `provider_config_id`，同一 Plan/Platform 唯一；平台配置使用 JSONB 保存经未来 Capability/API Contract 校验后的业务配置快照，不保存 Secret 或 Provider 私有分页状态。
- Plan→Keyword Pack 使用关联表，不把关系塞进 Plan JSON。
- Occurrence 唯一身份为 `(plan_id, schedule_version, scheduled_for)`；只允许 `enqueued/skipped` 可提交终态，并约束 `job_id/skip_reason` 一致性。
- `collection_runs` 新增可空 `manual_plan_id/occurrence_id`；`scheduled` Run 必须引用 Occurrence 且不得写 `manual_plan_id`；现有 `manual/api/backfill` 保持兼容并不得引用 Occurrence。
- Deferred 数据库约束在事务提交前验证：`enqueued` Occurrence 恰有一个反向 scheduled Run 且 Run/Occurrence `job_id` 一致；`skipped` Occurrence 没有 Run。
- Domain/Repository 能创建显式 Plan，以及原子创建 scheduled Job+Occurrence+Run/Scopes 所需父事实；不解析 Cron、不计算 misfire/catch-up。
- `0012 → head`、`base → head`、downgrade/upgrade、`alembic check` 和表 Owner/架构/Secret/Docs 门禁通过。
- PR 合并后 main 再次获得新鲜 CI 证据后才允许归档 Change。

# 范围

- Collection Plan/Platform/Keyword Pack/Occurrence/Run Snapshot 的 Domain、Table、Migration、Repository。
- Scheduled Run 数据一致性和现有 Run 创建兼容。
- Unit/PostgreSQL/Quality 测试与长期文档同步。

# 非目标

- 不实现 Scheduler 主循环、Cron 解析、`next_run_at/last_scheduled_at` 推进算法。
- 不批准或执行 `misfire_policy`、`max_catch_up_runs` 的具体运行语义；当前仅持久化调用方显式值，Scheduler 仍 No-Go。
- 不新增 Stage 8 HTTP API、前端页面或认证/授权能力。
- 不修改 TikHub Pricing、真实 Provider Probe、四平台 Mapper/Fixture。
- 不改写历史 Migration `0001`—`0012`。

# 必须保持不变

- PostgreSQL Job Runtime 是正式任务事实；一个 Run 继续只绑定一个 Job。
- Provider Config 只保存 `secret_ref`，Plan/Run Snapshot 不保存 API Key、Token、Cookie 等 Secret。
- 平台 Provider 选择使用稳定 `provider_config_id`；Provider 私有 cursor/page/search_id 等运行状态不进入 Plan 普通业务配置。
- Raw → Mapper → Canonical → Ingestion、表 Owner 与现有 Provider Budget 边界不改变。
- 当前 `manual/api/backfill` Run 调用保持兼容。

# Schema 取舍

采用“关系身份规范化 + 平台业务配置 JSONB 快照”：Plan/Platform、Plan/Keyword Pack 使用真实 FK 关联；平台变化较大的业务参数放在 `collection_plan_platforms.config` JSONB，并强制为 object。这样 Provider Config/Platform/Keyword Pack 等稳定身份可由数据库约束，而 Stage 8 未来的版本化 Pydantic Plan API/Capability 可以逐步冻结业务字段，不需要现在为尚未公开的五平台差异提前增加大量可空列。禁止用 JSONB 代替关系身份或保存 Secret/分页状态。

# Red → Green → Refactor 计划

[步骤 1：Red]
→ 修改范围：`tests/unit/collection/`、`tests/integration/collection/`、Stage 7 专项 workflow
→ 预期结果：Plan/Occurrence/Run Snapshot 测试因生产实现或新表不存在而失败。
→ 验证方式：分支 GitHub Actions 新鲜失败 Run，确认失败原因属于目标缺失。

[步骤 2：Green]
→ 修改范围：Collection Domain/Table/Postgres Repository、`database_schema.py`、`migrations/versions/20260815_0013_stage7_plan_occurrence_run_snapshot.py`
→ 预期结果：目标父事实、兼容 Run 创建和 Deferred 一致性约束成立。
→ 验证方式：专项 Unit/PostgreSQL；`0012→head`、`base→head`、round trip、`alembic check`。

[步骤 3：Refactor 与文档]
→ 修改范围：Collection README、Blueprint 03/06/README、Change
→ 预期结果：长期文档只描述当前真实能力，并明确 Scheduler 仍受决策门禁阻塞。
→ 验证方式：Ruff、mypy、Architecture、Table Ownership、Secret Scan、Docs、diff 两阶段 Review。

# 验证进度

- Red：GitHub Actions run `31887206516` 的 Stage 7 Plan Unit 在锁定环境安装成功后，因 `aima_ugc.modules.collection.planning` 尚不存在而以 1 error / exit code 2 失败；PostgreSQL Job 先成功升级到当时 head `20260815_0012` 且 `alembic check` 无漂移，再因 Planning Repository 尚不存在失败。该 Red 由目标生产能力缺失触发，不是环境或旧 Migration 故障。
- 首轮 Green：GitHub Actions run `31887495216` 的 Stage 7 Plan Unit 已通过；Stage 7 Plan PostgreSQL 已通过 8 个集成测试，并完成 `0012 → head`、`base → head`、downgrade/upgrade 与 `alembic check`。Quality 当轮只运行到 Ruff format，发现本 Change 文件格式问题后停止，因此不能把后续 mypy/Contract/Architecture/Table Ownership/Secret/Docs 记为已验证。
- Refactor：已修正 Ruff 指出的格式/类型注解，补充 Run/Occurrence 反向 Job 一致性、skipped Occurrence、Plan 平台 Secret 递归拒绝回归测试，并同步 Collection/Blueprint 当前状态说明。上述 Refactor 仍必须由本分支新的完整 CI 重新证明后才能进入 Review。

# 回滚与部署

- Migration 为追加式 `0013`；不改写历史 Revision。
- 回滚通过 `alembic downgrade 20260815_0012` 删除本 Change 新增父事实/列；生产若已有 Plan/Occurrence 数据，回滚前必须确认数据处置，不能静默丢数据。
- 不部署生产环境；数据库角色继续使用现有 Migration 权限。
