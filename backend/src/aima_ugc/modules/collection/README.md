# Collection 模块

Collection 负责回答：**什么时候采、这次采什么、外部请求有没有真正执行、执行到哪一步、数据来自哪里。**

它不拥有最终帖子/评论 Current，也不把 TikHub 私有 JSON 直接写入业务表。

先看主链：

```text
Plan
→ Occurrence（定时场景）
→ Run
→ Scope
→ Provider Request
→ Provider Attempt
→ Raw Artifact
→ Candidate
→ Mapper
→ Canonical
→ Relevance
→ Content Ingestion / Owner
→ PostgreSQL
```

File Import 不是 Collection Run，具体见 `modules/ingestion` 和 `docs/appendix/数据入口与统一入库.md`。

## 1. Collection 拥有哪些事实

### Plan

长期采集计划：

- 什么时候执行；
- 哪些平台；
- 使用哪个 `provider_config_id`；
- 使用哪些关键词包；
- 详情/评论策略；
- Decision Policy。

Plan 不保存 Token、Cookie、Provider cursor 或某次请求状态。

### Occurrence

“某个 Plan 版本在某个逻辑时间点应该触发一次”。

唯一身份：

```text
(plan_id, schedule_version, scheduled_for)
```

### Run

一次完整业务运行。Run 绑定一个 PostgreSQL Job，并冻结当次执行需要的配置快照。

当前支持：

```text
scheduled
manual
api
backfill
```

Stage 8E 后 Run 还可以通过 `import_batch_id` 与一次业务批次关联，用于运行中心统一展示 Excel Import 和 TikHub Run。

### Scope

一个 Run 内最小可恢复执行单元，例如：

```text
xhs + keyword=爱玛 + discovery
```

Scope 保存 `pagination_state / progress / stats` 等 durable checkpoint。Worker 重试或 Lease takeover 时，已经终态的 Scope 不重复执行。

### Provider Request / Attempt

```text
Request
→ 一个逻辑外部请求

Attempt
→ 一次真实执行尝试
```

同一逻辑 Request 可以因为明确可重试失败创建新 Attempt，但同一 Attempt 最多发送一次。

### Candidate

Raw 里的一项内容/评论在 Mapper 前先建立 Candidate 来源账本。

这样 Mapper 即使失败，也能回答：

> 哪个 Run/Scope/Attempt/Raw 的哪一项没能进入 Canonical？

## 2. Scheduler 当前怎么工作

主要代码：

```text
modules/collection/scheduler.py
bootstrap/scheduler.py
entrypoints/scheduler_main.py
```

当前固定：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

Scheduler 只创建任务事实，不直接发 TikHub HTTP。

一次正常入队：

```text
扫描到 Plan 到期
→ PostgreSQL 行锁重读 Plan
→ 重新校验 Provider/关键词/Capability
→ 冻结 Run Snapshot
→ 创建 Job + Occurrence + Run
→ 推进 next_run_at
→ 同一短事务提交
```

停机恢复时，更早到期 slot 保存为 `skipped / misfire_superseded`，只执行最新一个到期 slot。

详细解释见：

[`../../../../../docs/appendix/Scheduler运行与恢复.md`](../../../../../docs/appendix/Scheduler运行与恢复.md)

## 3. Collection Job 怎么执行

正式 Job 类型：

```text
collection.run.v1
```

主要代码：

```text
execution.py
collection_run_job.py
collection_run_executor.py
bootstrap/collection_scope.py
bootstrap/worker.py
```

Job Payload 不复制 `run_id`、Plan、Secret 等可以通过受约束关系反查的事实。Handler 使用当前 `job_id` 反查正式 Run。

`CollectionRunExecutor`：

1. 验证当前 Job Fence；
2. 读取 Run/Scope；
3. 跳过已经终态的 Scope；
4. 执行待处理 Scope；
5. 持久化 checkpoint；
6. 汇总 Run/Job 进度和终态。

`collection.run.v1` 当前 `retry_on_timeout=false`。Attempt Deadline 到期后不自动重排整次 Collection Run，避免外部结果未知时隐式重复计费。

## 4. Provider Dispatch / Recovery

主要代码：

```text
provider_persistence.py
provider_dispatch.py
provider_recovery.py
```

核心原则：

```text
同一 Attempt 最多一次真实发送
→ 真正重发必须新 Attempt
```

当前自动可重试边界只覆盖明确允许的 Transport/HTTP 情况，例如部分 408/425/429/5xx 和 `not_sent/unknown` 恢复路径；其他 4xx 不无条件重试。

### Raw 已存在时

如果 Attempt 对应完整 Raw 已经保存：

```text
校验 metadata SHA-256 / bytes / gzip / Raw Envelope
→ replay
→ 禁止再次 Provider 请求
```

如果文件已原子落盘但 Artifact metadata 还停在 `pending`，Recovery 允许在专用路径重新校验后 CAS 确认 `stored`，再继续 link/replay。

文件缺失、损坏或来源不一致则保守收敛为 `unknown`，并记录安全 warning；日志不打印 Raw、请求参数或 Secret。

## 5. 正式 TikHub Scope 怎么走

`TikHubCollectionScopeExecutor` 复用五个平台生产 Operation：

```text
Search
→ Raw
→ Candidate
→ Mapper
→ Canonical
→ Relevance/Ingestion
→ Decision
→ 可选 Detail
→ 用最新 Canonical 重算评论决策
→ 可选 Comments/Sub-comments
→ Coverage
```

Search 首次 Decision 会保存 durable content action/checkpoint。Job retry/Lease takeover 恢复未完成 Detail/Comments，而不是因为 Current 已更新就重新计算后跳过原动作。

旧 Raw replay 使用 Raw Envelope 的真实 `observed_at`，不会拿“今天的恢复时间”回滚/污染 Current freshness。

## 6. 评论 Target 和 Coverage

评论 Target 只决定“还要不要请求下一页”。

例如目标 50 条、每页 20 条：第 3 页返回以后已经拿到 60 条，这 20 条全部 Mapper/Ingestion，再停止后续请求。

不能只保存前 10 条，因为整页已经付费返回。

内容级和 root thread 分别保存 Coverage，表达：

- fetched 数量；
- Provider reported 数量；
- complete/partial；
- stop reason。

数据库里有 50 条评论不等于“评论完整”。

## 7. Plan / Occurrence / Run 的数据库约束

当前长期重要约束：

### `collection_plans`

- `name` 唯一；
- `timezone=Asia/Shanghai`；
- `schedule_version >= 1`；
- `latest_only`；
- `max_catch_up_runs=0`；
- Scheduler 推进 `next_run_at / last_scheduled_at`。

### `collection_plan_platforms`

- 同一 Plan 同一平台只允许一条；
- 使用稳定 `provider_config_id`；
- `config` 是平台业务配置，不保存 Secret/Provider cursor。

### `collection_plan_keyword_packs`

Plan 与 Keyword Pack 使用真实关联表，不塞 JSON 字符串。

### `collection_schedule_occurrences`

- `(plan_id, schedule_version, scheduled_for)` 唯一；
- `enqueued` 必须有 Job；
- `skipped` 没有 Job，并有 `skip_reason`；
- `job_id` 唯一。

### `collection_runs`

- 一个 Run 一个 Job；
- `scheduled` 通过 `occurrence_id` 绑定调度身份；
- `manual/api/backfill` 保持人工/接口触发语义；
- `config_snapshot` 只是执行快照，不替代关系身份。

数据库 deferred constraint trigger 还会在事务提交前验证 Occurrence/Run/Job 跨表一致性。

精确列与约束仍以 `tables.py + migrations/versions/` 为准。

## 8. PostgreSQL Repository 写入口

主要入口：

```text
adapters/persistence/postgres/collection_planning.py
→ Plan / Platform / Keyword Pack / Occurrence / Scheduler cursor

adapters/persistence/postgres/collection.py
→ Run / Scope

adapters/persistence/postgres/collection_run_execution.py
→ Worker 下 Run/Scope 的 fenced start/checkpoint/finish

adapters/persistence/postgres/collection_provider_execution.py
→ Request/Attempt 恢复与 durable stats

adapters/persistence/postgres/collection_content.py
→ Collection 调 Content Owner 的 fenced Ingestion/Coverage 边界
```

Repository 不自行 `commit()`；事务由调用方 Unit of Work 持有。

Collection 不直接写 Content/Comment/Coverage 表。

## 9. Secret、Provider Config 和费用

- `provider_configs.secret_ref` 只保存 Secret 引用；
- Plan/Run/Scope/Raw/Job Payload 不保存 Secret；
- TikHub Bearer Secret 只发送到批准的 `https://api.tikhub.io` Origin；
- Plan `config` 不作为 Provider HTTP 私有参数仓库；
- Provider cursor/page/search_id 不写回 Plan。

Provider Request/Attempt 保存 Billing/Pricing/成本/`potential_duplicate_charge` 是为了执行审计。

当前没有：

```text
Budget Account
Reservation Ledger
请求次数预算
金额预算
发送前 Budget Guard
```

## 10. 当前已经实现到哪里

Collection 不能再写成“只有 Stage 1—7”。当前系统已经完成 Stage 8A—8F：

- Excel 正式 Import Batch；
- 全局 Relevance；
- 采集运行中心；
- 声音广场；
- 一次性 Discovery / Batch 补采；
- Keyword/Relevance/Plan 产品化；
- Analysis/Excel Export 等下游能力。

这些业务 API/页面已经存在。

当前仍未闭环：

- 企业正式认证授权；
- 完整离线生产 Release；
- 协调 Backup/Restore 写屏障；
- Stage 9 尚未正式实现的 Monitoring 业务。

不要把“Stage 8 已完成”和“认证/Release 也已完成”混为一件事。

## 11. 独立调试

### `tikhub_test`

默认可以只保存本地调试产物，不写业务数据库。

显式 `write_to_database=True` 后复用正式 manual Collection / Provider Dispatch / Raw / Candidate / Mapper / Ingestion；不会为了写库再发第二次 TikHub 请求。

### Raw Replay

`xhs_replay.py` 只回放已经保存的 XHS Raw，故意不持有 Provider Transport，因此不会重新产生外部请求。

所有 Probe/调试必须复用生产 Operation/Mapper，不复制 endpoint 和业务规则。

## 12. 测试重点

- Plan 校验与 fail-closed；
- `latest_only`、重复 tick、并发 Scheduler；
- Job retry/Lease takeover 后不重复已终态 Scope；
- Provider 同 Request + 新 Attempt；
- Raw Recovery 完整/损坏/pending 崩溃窗口；
- Candidate-before-Mapper；
- Detail 后评论重决策；
- 评论整页保留、Target 跨页、空页；
- Coverage 来源幂等；
- Fencing 防旧 Worker 写入；
- Migration old→head / downgrade-upgrade / `alembic check`。

真实付费 TikHub Probe 不进普通 CI。

## 13. 深入阅读

- 长期采集架构：[`../../../../../docs/blueprint/08-采集策略与平台能力.md`](../../../../../docs/blueprint/08-采集策略与平台能力.md)
- 数据标准化：[`../../../../../docs/blueprint/02-采集系统与数据标准化.md`](../../../../../docs/blueprint/02-采集系统与数据标准化.md)
- Scheduler：[`../../../../../docs/appendix/Scheduler运行与恢复.md`](../../../../../docs/appendix/Scheduler运行与恢复.md)
- TikHub：[`../../../../../docs/appendix/TikHub真实响应结构.md`](../../../../../docs/appendix/TikHub真实响应结构.md)
- 平台实现：[`../../../../../docs/collection/README.md`](../../../../../docs/collection/README.md)
- PostgreSQL：[`../../../../../docs/appendix/PostgreSQL调试与常用SQL.md`](../../../../../docs/appendix/PostgreSQL调试与常用SQL.md)
