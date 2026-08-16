# Collection 模块

Collection 是采集业务 Owner。它负责把已经通过 Contract / Provider 边界确定的采集输入组织成可追踪的 Plan、Occurrence、Run、Scope、Provider Request / Attempt、Candidate 和预算账本事实；它不拥有 HTTP Router、Provider 私有分页协议或 Canonical 业务表。

## 1. 稳定边界

当前模块具备以下父事实与执行边界：

1. `planning.py`
   - `CollectionPlanDefinition`：Plan 的稳定创建输入；首版只允许 `Asia/Shanghai + latest_only + max_catch_up_runs=0`；
   - `PlanPlatformDefinition`：以 `platform + provider_config_id` 固定 Provider 配置选择，`config` 只保存平台业务配置 object；
   - `CollectionPlanningService`：校验首版策略、平台/关键词包关系唯一性，以及显式 Occurrence 输入。
2. `scheduler.py` + `bootstrap/scheduler.py`
   - 解析首版五字段数值 Cron；
   - 按 `latest_only` 计算停机恢复；
   - 对 Plan 使用 PostgreSQL 行锁重读当前状态；
   - 在一个短事务中编排 skipped Occurrence、Job、enqueued Occurrence、scheduled Run 与 cursor 推进；
   - 不直接执行 Provider HTTP，也不建立第二套内存任务队列。
3. `execution.py` / `collection_run_job.py`
   - `CollectionExecutionService`：创建 Run / Scope 父事实；
   - `manual` / `api` / `backfill` Run 可选择性绑定 `manual_plan_id`，但不得绑定 Occurrence；
   - `scheduled` Run 必须绑定唯一 `occurrence_id`，不得重复保存 `manual_plan_id`；
   - `collection.run.v1` Job Payload 只保存稳定 schema 身份，不复制 `run_id`、Plan 或 Secret；Handler 通过当前 `JobExecutionFence.job_id` 反查正式 Run；
   - `collection.run.v1` 明确 `retry_on_timeout = false`：普通 Lease 仍可在同一 Attempt 内 takeover，但 Attempt Deadline 到期后不自动重排整个 Collection Run，避免在外部付费请求结果不确定时产生隐式重复请求/重复费用。
4. `provider_persistence.py` / `provider_dispatch.py` / `provider_recovery.py`
   - Provider Request / Attempt 的持久化、正式 Dispatch、失败归因与 Recovery；
   - Provider 私有 cursor / page / search_id 等状态只属于 Provider Request / Attempt / Scope，不进入 Plan 普通业务配置。
5. `candidates.py` / `candidate_tables.py` 与 Provider Mapper / Ingestion
   - Raw → Mapper → Candidate → Canonical / Ingestion 的现有纵向边界；
   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表。
6. `provider_budget.py`
   - Provider 调用前预算预留、成功/失败结算和 `unknown` 账务保守处理；
   - `unknown` 不自动退款。
7. `xhs_replay.py`
   - 只回放已经持久化的 XHS Raw；
   - 复用正式 Mapper / Ingestion；
   - 故意不持有 Provider Client / Transport，因此不会因回放再次产生外部 HTTP。

## 2. Plan / Occurrence / Run / Scheduler

Stage 7 当前 Collection-owned 数据事实：

- `collection_plans`
  - 唯一 `name`；
  - 首版 `timezone = Asia/Shanghai`；
  - `schedule_version >= 1`；
  - 首版 `misfire_policy = latest_only`；
  - 首版 `max_catch_up_runs = 0`；
  - `request_budget >= 0`；
  - `next_run_at` / `last_scheduled_at` 由 Scheduler Runtime 推进。
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
  - `config_snapshot` 是运行时不可变配置快照，不替代 Plan/Occurrence 的关系身份。

数据库使用 deferred constraint trigger 在事务提交前检查跨表一致性：

- `enqueued` Occurrence 必须恰有一个反向 `scheduled` Run；
- Occurrence 与 Run 必须引用同一个 Job；
- `skipped` Occurrence 不允许存在 Run。

Scheduler 停机恢复固定为：

```text
更早的 due slot → skipped / misfire_superseded
最新 due slot → enqueued
未来首个 slot → next_run_at
```

不额外补跑历史 Run。完整设计见 `docs/blueprint/09-Scheduler运行与恢复策略.md`。

## 3. PostgreSQL 写入口

- `adapters/persistence/postgres/collection_planning.py`
  - Plan / PlanPlatform / PlanKeywordPack / Occurrence 的 Collection 写入口；
  - 提供 Scheduler 预扫、`FOR UPDATE` 重读与带 `schedule_version` 的 cursor 更新；
  - Repository 不自行 `commit()`，事务由调用方持有。
- `adapters/persistence/postgres/collection.py`
  - Run / Scope 的 Collection 写入口；
  - 保留 `manual/api/backfill` 兼容性并支持 Plan / Occurrence 绑定。

`database_schema.py` 只注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。首版 Scheduler 策略通过 `0014` Migration 和 SQLAlchemy metadata 同时约束，禁止只改一侧。

## 4. Secret、Job 与配置边界

- Provider Secret 只通过 `provider_configs.secret_ref` 间接引用，不进入 Plan、Run、Scope、Raw、Job Payload 或日志明文；
- Plan 平台 `config` 是业务配置，不是 Provider HTTP 参数仓库；
- Provider 私有 cursor、page、search_id、签名或认证字段不进入 Plan；
- Scheduler 只创建任务事实，真实 Provider HTTP 仍必须经过 Pricing、Budget、Dispatch 与 Raw 边界；
- `collection.run.v1` 的整个 Job Attempt 超时不自动重排；任何 Provider 重发都必须遵守“新 Attempt + 新预算预留 + 新 Raw 证据”边界，不能由 Job Runtime 隐式复制一次已经可能发送过的付费调用。

## 5. 当前仍未闭环的边界

Scheduler Runtime 已能计算、加锁并原子持久化调度事实，但 **Stage 7 自动采集还未闭环**：

- `collection.run.v1` 的稳定 Payload/Handler/Registry Contract 已存在，但生产 `bootstrap/worker.py` 还没有装配具体 `CollectionRunJobExecutor`，因此正式 Worker 仍不会 claim Scheduler 创建的 Collection Run Job；
- scheduled Run 的 Scope/关键词展开与正式 Provider Operation 执行还需要接回现有 Keyword Pack、Provider Routing、Pricing/Budget、Dispatch、Raw、Mapper、Decision、Ingestion 链；
- Collection-owned Run/Scope Repository 当前只有创建/读取能力，live Executor 仍需要通过正式 Owner 接口补齐运行状态推进，禁止在 Worker 中直接写表；
- 不允许用空 Handler、直接 SQL 或第二套 Provider 调用代码掩盖该断点；
- 统一真实 Probe 还必须继续保持 endpoint 级 Pricing 核验、安全 Secret 注入、显式请求数/费用上限和普通 CI 零付费请求。

因此当前可以说“Scheduler Runtime 与 `collection.run.v1` Job Contract 已实现并通过当前分支 CI”，不能说“Stage 7 自动采集已完成”。

## 6. 调试与测试原则

- 调试入口复用 `CollectionPlanningService` / `CollectionExecutionService` / 正式 Repository / Provider Operation，不另写第二套 SQL 或 Provider 实现；
- PostgreSQL 集成测试验证真实 FK、Unique、Check、行锁与 deferred constraint，而不是只验证 Mock；
- Scheduler 专项验证 new-plan 初始化、latest-only、重复 tick、并发 Scheduler 和 Migration round-trip；
- 新 Migration 至少验证上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- 真实付费 Provider Probe 默认不进入普通 CI，不能因为缺少真实网络调用而降低本模块数据库、领域和 Secret 门禁标准。
