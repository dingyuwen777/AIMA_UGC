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
   - `CollectionRunExecutor` 在 Lease takeover / Job retry 时跳过已经终态的 Scope，并从 Scope durable stats 复用已完成计数，不重新执行已完成业务副作用；
   - running Scope 的 `pagination_state / progress / stats` 通过 Fenced `checkpoint_scope()` 持久化；Scope 页进度不再直接改 Job progress，Job progress 只由 Run Executor 按 Scope 完成度推进；
   - 可重试 Provider 错误先保存 Scope checkpoint，再返回 `JobHandlerResult.retry()` 交给 PostgreSQL Job Runtime；普通 Scope 业务失败仍隔离在当前 Scope；
   - `collection.run.v1` 明确 `retry_on_timeout = false`：Attempt Deadline 到期后不自动重排整个 Collection Run，避免在外部结果不确定时产生隐式重复费用。
4. `provider_persistence.py` / `provider_dispatch.py` / `provider_recovery.py`
   - Provider Request / Attempt 的持久化、正式 Dispatch、失败归因与 Recovery；
   - Provider Request 是逻辑请求，同一 request fingerprint 在 Job retry / takeover 中复用；
   - 新的外部重发必须建立新的 Provider Attempt；429、408、425、5xx 以及 Transport `not_sent/unknown` 才进入当前自动 retry 边界，其他 4xx 不做无条件重试；
   - `dispatching` Attempt 在正式 Scope 开始时先经 `ProviderAttemptReconciler` 收敛：存在完整且 Contract/Hash 校验通过的确定性 Raw 时直接 finalize + replay，**禁止再次发送 Provider**；没有可用 Raw 的未知发送结果保留 `potential_duplicate_charge` 语义。
5. `candidates.py` / `candidate_tables.py` 与 Provider Mapper / Ingestion
   - Raw → Mapper → Candidate → Canonical / Ingestion 的统一纵向边界；
   - Mapper 不访问数据库、不发 HTTP；Provider 不直接写业务表；
   - Scope 请求/成功/失败计数和 Content/Comment 计数从 PostgreSQL Attempt/Candidate durable 事实恢复，不只依赖进程内计数。
6. `bootstrap/collection_scope.py` + `bootstrap/worker.py`
   - `TikHubCollectionScopeExecutor` 复用既有五平台 TikHub Operation、Provider Dispatch/Recovery、Raw、Mapper、Decision 和 fenced Ingestion 执行正式 Scope；
   - Search 决策为 `defer_until_detail` 时，Detail 摄取后必须使用最新 Canonical 再计算评论动作；只重算评论决策，不重复发 Detail；
   - 评论/二级回复的 target 是“是否继续请求下一页”的软目标：当前已经返回并付费的响应页全部 Mapper/Ingestion 后，才决定是否再请求下一页；
   - 每次评论抓取或明确不抓取形成 `comment_coverage_observations`，保存 complete/partial/not_requested/unavailable、Provider 报告总数、实际采集数、sample/sort/target/stop reason 和 Raw/Attempt 来源；
   - `create_collection_job_registry(...)` 用现有 Artifact/Raw/Provider/Collection 组件组装 `collection.run.v1`；
   - 默认 Secret 只通过 `secret_ref` 在 `AIMA_SECRET_DIR` 下解析；TikHub Transport 只允许批准的 `https://api.tikhub.io` Origin 接收 Bearer Secret。
7. `xhs_replay.py`
   - 只回放已经持久化的 XHS Raw；
   - 复用正式 Mapper / Ingestion；
   - 故意不持有 Provider Client / Transport，因此不会因回放再次产生外部 HTTP。

## 2. Plan / Occurrence / Run / Scheduler

当前 Collection-owned 数据事实：

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
  - 一个 Run 只绑定一个 Job；
  - `scheduled` Run 必须通过 `occurrence_id` 关联 Plan / Schedule Version；
  - `manual` / `api` / `backfill` 保持兼容，并可选记录 `manual_plan_id`；
  - `config_snapshot` 是运行时不可变配置快照，不替代 Plan/Occurrence 的关系身份。
- `collection_scopes`
  - 每个平台/来源的最小可恢复执行单元；
  - `pagination_state / progress / stats` 是 durable checkpoint，不把 Provider 私有 cursor 塞回 Plan；
  - 终态 Scope 在 Job takeover/retry 后不得重复执行。

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
  - start/checkpoint/finish 都先验证当前 Job Fence，不允许旧 Worker 在 Lease takeover 后继续写。
- `adapters/persistence/postgres/collection_provider_execution.py`
  - 同一逻辑 Provider Request 的 Attempt 恢复、可重发边界和 Scope durable 计数读取；
  - 成功且带完整 Raw 的 Request 直接复用；`dispatching` 必须先 Recovery；终态可重试失败才允许建立新的 Attempt。
- `adapters/persistence/postgres/collection_content.py`
  - Collection 到 Content Owner 的 Fenced Ingestion/Coverage 边界；
  - Collection 不直接写 Content/Comment/Coverage 表。

`database_schema.py` 只注册当前机器 Schema；正式结构变化必须通过 Alembic Revision 演进。首版 Scheduler 策略通过 `0014` 约束，预算回撤通过 `20260817_0015` 完成，评论 Coverage 可观测字段和来源幂等约束由向前 Revision `20260817_0016` 建立；禁止改写已发布历史 Revision。

## 4. Secret、Job、Provider 与配置边界

- Provider Secret 只通过 `provider_configs.secret_ref` 间接引用，不进入 Plan、Run、Scope、Raw、Job Payload 或日志明文；
- Plan 平台 `config` 是业务配置，不是 Provider HTTP 参数仓库；
- Provider 私有 cursor、page、search_id、签名或认证字段不进入 Plan；
- Scheduler 只创建任务事实，真实 Provider HTTP 必须经过 Provider Billing/Pricing、Dispatch 与 Raw 边界；
- Provider Billing、Pricing、成本快照和 `potential_duplicate_charge` 是执行/审计事实，不是请求次数或金额预算；当前不存在 Budget Account、Reservation Ledger 或发送预算门禁；
- 同一 Attempt 最多一次外部发送；重发只能新建 Attempt；完整 Raw 存在时必须 replay，不得为了 Job retry 再收费一次；
- 当前不自动做 Provider/App/Web fallback；各平台 Operation 的备用方案必须由独立决策/验证启用。

## 5. 当前阶段边界

Stage 1—7 已存在完整机器实现：Scheduler → Occurrence → `collection.run.v1` Job → Run/Scope → Worker → TikHub 五平台 Provider Operation → Raw → Mapper → Canonical → Candidate/Ingestion → Content Owner/PostgreSQL。

在进入 Stage 8 前，当前 L3 Corrective Change 重新验证并补齐 Stage 1—7 的恢复、并发、乱序 Current、评论整页/Coverage 与测试/文档一致性。**Stage 8 HTTP CRUD/业务页面/认证授权，以及 Release 阶段 Docker/离线发布/协调 Backup-Restore 仍未开始，不得把本次修复描述为这些能力已经实现。**

当前必须继续保持：

- 五平台 Operation / Mapper / Capability 的已验证边界；
- 快手 App comments/sub-comments 正式主链；
- 不建立自动 Provider/App/Web fallback；
- Provider Secret 只走 `secret_ref`，TikHub Bearer Secret 只发送到批准的 `https://api.tikhub.io` Origin；
- 当前不恢复请求/金额预算、Budget Account、Reservation Ledger 或 dormant Budget 接口。

## 6. 调试与测试原则

- 调试入口复用正式 `CollectionPlanningService` / `CollectionExecutionService` / Repository / Provider Operation，不另写第二套 SQL 或 Provider 实现；
- PostgreSQL 集成测试验证真实 FK、Unique、Check、行锁、并发 first-insert、Fencing、Raw Recovery 和 deferred constraint，而不是只验证 Mock；
- Scheduler 专项验证 new-plan 初始化、latest-only、重复 tick、并发 Scheduler 和 Migration round-trip；
- Worker 纵切使用 `FakeProviderTransport` 验证真实生产装配；普通 CI 不产生付费 TikHub 请求；
- Provider 可重试错误必须验证“同一逻辑 Request + 新 Attempt”，同时保留旧 Attempt/Raw/费用事实；
- Recovery 必须验证 `dispatching + 已完整 Raw + Lease takeover` 后正式 Scope 不再次发送 Provider；
- 评论测试必须覆盖 Detail 后重决策、整页保留、target 跨页、空页、reported_total=0、Coverage 来源幂等；
- 新 Migration 至少验证上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- 真实 Provider Probe 仅在 Fixture/Contract/一手文档不足以确认真实接口形态时人工显式运行，并设置请求/分页上限；不能把 Real Probe 当普通 CI，也不能把付费请求成功替代单元/集成测试。
