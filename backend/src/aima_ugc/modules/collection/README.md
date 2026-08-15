# Collection 模块

Collection 是采集业务 Owner。它负责把已经通过 Contract / Provider 边界确定的采集输入，组织成可追踪的 Plan、Run、Scope、Provider Request / Attempt、Candidate，以及预算账本事实；它不拥有 HTTP Router、Provider 私有分页协议或 Canonical 业务表。

## 1. 稳定边界

当前模块已经具备以下父事实与执行边界：

1. `planning.py`
   - `CollectionPlanDefinition`：Plan 的稳定创建输入；首版时区只允许 `Asia/Shanghai`；
   - `PlanPlatformDefinition`：以 `platform + provider_config_id` 固定 Provider 配置选择，`config` 只保存平台业务配置 object；
   - `CollectionPlanningService`：校验首版稳定约束、平台/关键词包关系唯一性，以及显式 Occurrence 输入；
   - 不解析 Cron，不推导 `misfire_policy` / catch-up 行为，也不推进 `next_run_at`。
2. `execution.py`
   - `CollectionExecutionService`：创建 Run / Scope 父事实；
   - `manual` / `api` / `backfill` Run 可以选择性绑定 `manual_plan_id`，但不得绑定 Occurrence；
   - `scheduled` Run 必须绑定唯一 `occurrence_id`，并不得重复保存 `manual_plan_id`。
3. `provider_persistence.py` / `provider_dispatch.py` / `provider_recovery.py`
   - Provider Request / Attempt 的持久化、正式 Dispatch、失败归因与 Recovery；
   - Provider 私有 cursor / page / search_id 等状态只属于 Provider Request / Attempt / Scope，不进入 Plan 普通业务配置。
4. `pipeline.py` / `candidate_tables.py`
   - Raw → Mapper → Candidate → Canonical / Ingestion 的正式纵向链路；
   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表。
5. `provider_budget.py`
   - Provider 调用前预算预留、成功/失败结算和 `unknown` 账务保守处理；
   - `unknown` 不自动退款。

## 2. Plan / Occurrence / Run Snapshot 父事实

Stage 7 已建立以下 Collection-owned 数据事实：

- `collection_plans`
  - 唯一 `name`；
  - 首版 `timezone = Asia/Shanghai`；
  - `schedule_version >= 1`；
  - `misfire_policy`、`max_catch_up_runs` 目前只持久化显式值，不解释运行语义；
  - `request_budget >= 0`；
  - `next_run_at` / `last_scheduled_at` 作为未来 Scheduler 可更新字段存在，但当前没有 Scheduler 写入逻辑。
- `collection_plan_platforms`
  - 一个 Plan 的同一平台只允许一条关系；
  - 通过稳定 `provider_config_id` 引用 `provider_configs`；
  - `config` 必须为 JSON object，并由领域入口拒绝 Secret 形态字段；不得保存 API Key、Token、Cookie 或 Provider 私有分页状态。
- `collection_plan_keyword_packs`
  - Plan 与 `keyword_packs` 使用真实关联表；不把关系塞入 JSON。
- `collection_schedule_occurrences`
  - `(plan_id, schedule_version, scheduled_for)` 唯一；
  - `enqueued` 必须有 `job_id`，`skipped` 必须无 Job 且有 `skip_reason`；
  - `job_id` 唯一。
- `collection_runs`
  - 一个 Run 仍只绑定一个 Job；
  - `scheduled` Run 必须通过 `occurrence_id` 关联 Plan / Schedule Version；
  - `manual` / `api` / `backfill` 保持兼容，并可选记录 `manual_plan_id`；
  - `config_snapshot` 继续作为运行时不可变配置快照，不替代 Plan/Occurrence 的关系身份。

数据库使用 deferred constraint trigger 在事务提交前检查跨表一致性：

- `enqueued` Occurrence 必须恰有一个反向 `scheduled` Run；
- Occurrence 与 Run 必须引用同一个 Job；
- `skipped` Occurrence 不允许存在 Run。

这样可以在同一事务中先创建 Job / Occurrence / Run，再在提交点统一验证，而不会因为插入顺序人为放松约束。

## 3. PostgreSQL 写入口

- `adapters/persistence/postgres/collection_planning.py`
  - `PostgresCollectionPlanningRepository` 是 Plan / PlanPlatform / PlanKeywordPack / Occurrence 的 Collection 写入口；
  - Repository 不自行 `commit()`，事务由调用方持有。
- `adapters/persistence/postgres/collection.py`
  - `PostgresCollectionRepository` 是 Run / Scope 的 Collection 写入口；
  - 保留既有 `manual/api/backfill` 调用兼容性，并支持新的 Plan / Occurrence 绑定。

`database_schema.py` 只负责注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。

## 4. Secret 与配置边界

- Provider Secret 只通过 `provider_configs.secret_ref` 间接引用，不进入 Plan、Run、Scope、Raw、Job Payload 或日志明文；
- Plan 平台 `config` 是业务配置，不是 Provider HTTP 参数仓库；
- Provider 私有 cursor、page、search_id、签名或认证字段不进入 Plan；
- `misfire_policy` 与 `max_catch_up_runs` 当前只是持久化字段，不能从数据库存在推断 Scheduler 策略已经批准。

## 5. 当前仍未实现的边界

当前 **没有正式 Scheduler Runtime**。以下能力仍需后续独立决策和实现：

- Cron / schedule expression 的正式解析与校验；
- `next_run_at` / `last_scheduled_at` 的推进算法；
- `misfire_policy` 的允许值与恢复语义；
- `max_catch_up_runs` 的实际追赶策略、停机成本与容量上界；
- Scheduler 主循环、抢占 / 并发协调、恢复测试。

因此：Plan/Occurrence/Run Snapshot 父事实已经存在，不等于 Scheduler 已经可运行。

## 6. 调试与测试原则

- 调试入口复用 `CollectionPlanningService` / `CollectionExecutionService` / 正式 Repository，不另写第二套 SQL；
- PostgreSQL 集成测试验证真实 FK、Unique、Check 与 deferred constraint，而不是只验证 Mock；
- 新 Migration 必须至少验证上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- 真实付费 Provider Probe 默认不进入普通 CI，不能因为缺少真实网络调用而降低本模块数据库和领域测试标准。
