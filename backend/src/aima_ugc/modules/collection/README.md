# Collection 模块

Collection 是采集业务 Owner。它负责把已经通过 Contract / Provider 边界确定的采集输入组织成可追踪的 Plan、Occurrence、Run、Scope、Provider Request / Attempt 和 Candidate 事实；它不拥有 HTTP Router、Provider 私有分页协议或 Canonical 业务表。Provider Billing/成本字段只作为执行审计事实，当前模块不实现预算账本。

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
3. `execution.py` / `collection_run_job.py` / `collection_run_executor.py`
   - `CollectionExecutionService`：创建 Run / Scope 父事实；
   - `manual` / `api` / `backfill` Run 可选择性绑定 `manual_plan_id`，但不得绑定 Occurrence；
   - `scheduled` Run 必须绑定唯一 `occurrence_id`，不得重复保存 `manual_plan_id`；
   - `collection.run.v1` Job Payload 只保存稳定 schema 身份，不复制 `run_id`、Plan 或 Secret；Handler 通过当前 `JobExecutionFence.job_id` 反查正式 Run；
   - `CollectionRunExecutor` 通过正式 Gateway 推进 Run/Scope，并把 Scope 交给注入的 `CollectionScopeExecutor`；
   - `collection.run.v1` 明确 `retry_on_timeout = false`：普通 Lease 仍可在同一 Attempt 内 takeover，但 Attempt Deadline 到期后不自动重排整个 Collection Run，避免在外部请求结果不确定时产生隐式重复请求/重复费用。
4. `provider_persistence.py` / `provider_dispatch.py` / `provider_recovery.py`
   - Provider Request / Attempt 的持久化、正式 Dispatch、失败归因与 Recovery；
   - Provider 私有 cursor / page / search_id 等状态只属于 Provider Request / Attempt / Scope，不进入 Plan 普通业务配置。
5. `candidates.py` / `candidate_tables.py` 与 Provider Mapper / Ingestion
   - Raw → Mapper → Candidate → Canonical / Ingestion 的现有纵向边界；
   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表。
6. `bootstrap/collection_scope.py` + `bootstrap/worker.py`
   - `TikHubCollectionScopeExecutor` 复用既有 TikHub Operation、Provider Dispatch、Raw、Mapper、Decision 和 fenced Ingestion 执行正式 Scope；
   - `create_collection_job_registry(...)` 用现有 Artifact/Raw/Provider/Collection 组件组装 `collection.run.v1`；
   - 默认 Secret 只通过 `secret_ref` 在 `AIMA_SECRET_DIR` 下解析；默认 TikHub Transport 每次发送后关闭其自持 HTTP Client，不遗留无人管理的连接生命周期；
   - 正式 `entrypoints/worker_main.py` 暴露同一 Registry 装配，不复制 JobWorker 循环。
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
- `adapters/persistence/postgres/collection_run_execution.py`
  - live Worker 的 Run/Scope 执行 Gateway；
  - 所有可见状态推进继续受 Job Fence 约束，不允许 Worker 绕过 Owner 直接写表。

`database_schema.py` 只注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。首版 Scheduler 策略通过 `0014` Migration 和 SQLAlchemy metadata 同时约束，预算回撤通过向前 Migration `20260817_0015` 完成，禁止改写历史 Revision。

## 4. Secret、Job 与配置边界

- Provider Secret 只通过 `provider_configs.secret_ref` 间接引用，不进入 Plan、Run、Scope、Raw、Job Payload 或日志明文；
- Plan 平台 `config` 是业务配置，不是 Provider HTTP 参数仓库；
- Provider 私有 cursor、page、search_id、签名或认证字段不进入 Plan；
- Scheduler 只创建任务事实，真实 Provider HTTP 仍必须经过 Provider Billing/Pricing、Dispatch 与 Raw 边界；
- Provider Billing、Pricing、成本快照和 `potential_duplicate_charge` 是执行/审计事实，不是请求次数或金额预算；当前不存在 Budget Account、Reservation Ledger 或发送预算门禁；
- `collection.run.v1` 的整个 Job Attempt 超时不自动重排；任何 Provider 重发都必须使用新 Attempt 并形成新的 Raw/计费审计事实，不能由 Job Runtime 隐式复制一次已经可能发送过的外部调用。

## 5. Stage 7 当前闭环状态

Scheduler → Occurrence → `collection.run.v1` Job → scheduled Run / Scope → 正式 Worker Registry / JobWorker → `CollectionRunJobHandler` → `CollectionRunExecutor` → `TikHubCollectionScopeExecutor` → Provider / Raw / Mapper / Canonical / Ingestion 的生产链已经在当前 Stage 7 分支通过 PostgreSQL/Fake Transport 纵切验证。

当前 Stage 7 剩余工作不再是补第二套 Worker 或 Provider 实现，而是：

- 保持五平台 Operation / Mapper / Capability、快手 App 评论主链、无自动 fallback 和预算回撤不漂移；
- 清理代码/文档质量门禁并完成需求符合性与代码质量/安全/兼容性 Review；
- 在最终 PR head 上取得新鲜完整 CI；
- 按仓库流程把 PR #55 正常合入 `main`，再验证合并后 `main`；
- 最后将当前 L3 Change 标记完成并按规则归档。

在这些收尾门禁全部完成前，可以说“Stage 7 live Worker 已闭环、Stage 7 正在收尾验收”，不能提前宣称整个 Stage 7 已完成。

## 6. 调试与测试原则

- 调试入口复用 `CollectionPlanningService` / `CollectionExecutionService` / 正式 Repository / Provider Operation，不另写第二套 SQL 或 Provider 实现；
- PostgreSQL 集成测试验证真实 FK、Unique、Check、行锁与 deferred constraint，而不是只验证 Mock；
- Scheduler 专项验证 new-plan 初始化、latest-only、重复 tick、并发 Scheduler 和 Migration round-trip；
- Worker 纵切使用 `FakeProviderTransport`，证明生产装配与数据库链路，不在普通 CI 产生付费 TikHub 请求；
- 新 Migration 至少验证上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- 真实付费 Provider Probe 默认不进入普通 CI，不能因为缺少真实网络调用而降低本模块数据库、领域和 Secret 门禁标准。
