# Scheduler 调度执行与停机恢复

本文用于**理解和调试当前 Scheduler 真实实现**：Plan 到期后怎样变成 Occurrence / Run / Scope / Job，停机后为什么只补最新一个逻辑周期，多 Scheduler 为什么不会重复入队，以及修改调度语义时应该改哪些代码和测试。

长期边界：

- [`../blueprint/04_后端任务API与前端.md`](../blueprint/04_后端任务API与前端.md)
- [`../blueprint/07_技术决策与实施门禁.md`](../blueprint/07_技术决策与实施门禁.md)
- [`../blueprint/08_采集策略与平台能力.md`](../blueprint/08_采集策略与平台能力.md)

当前代码入口：

```text
领域算法
→ backend/src/aima_ugc/modules/collection/scheduler.py

Plan / Scope 领域
→ backend/src/aima_ugc/modules/collection/planning.py
→ backend/src/aima_ugc/modules/collection/scheduled_scopes.py

生产事务编排
→ backend/src/aima_ugc/bootstrap/scheduler.py

Scheduler 进程入口
→ backend/src/aima_ugc/entrypoints/scheduler_main.py

PostgreSQL Plan / Occurrence Repository
→ backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py

Run / Scope Repository
→ backend/src/aima_ugc/adapters/persistence/postgres/collection_run_execution.py

Job Runtime
→ backend/src/aima_ugc/platform/jobs/
```

---

## 1. Scheduler 到底负责什么

Scheduler 只负责：

```text
现在几点？
→ 哪些 Plan 到期？
→ 每个 Plan 这次应该产生哪个逻辑调度点？
→ 该调度点应该 skip 还是 enqueue？
→ 生成什么 Run / Scope / Job？
```

Scheduler **不**：

- 请求 TikHub；
- 解析 Provider JSON；
- 写 Content Current；
- 调用 LLM；
- 执行 Excel Export。

真正执行 Collection 的是 Worker：

```text
Scheduler
→ PostgreSQL Job
→ Worker
→ CollectionRunJobHandler
→ CollectionRunExecutor
→ TikHubCollectionScopeExecutor
```

所以排障时要先区分：

```text
“为什么没创建 Job？”
→ Scheduler 问题

“Job 创建了但 TikHub 没请求？”
→ Worker / Collection Scope / Provider 问题
```

---

## 2. 当前固定恢复策略

当前机器实现只允许：

```text
misfire_policy = latest_only
max_catch_up_runs = 0
```

这不是建议值，而是当前领域和数据库共同约束的行为。

当 Scheduler 停机后恢复，若同一个 Plan 已累计多个到期逻辑调度点：

1. 只把**最新一个**到期 slot 创建为 `enqueued` Occurrence；
2. 更早的到期 slot 逐个记录为 `skipped`；
3. skip 原因固定为：

```text
misfire_superseded
```

4. 不额外执行历史 Run；
5. `last_scheduled_at` 推进到本次处理的最新逻辑 slot；
6. `next_run_at` 推进到严格晚于当前时间的下一个 slot。

### 例子

Plan：

```text
0 */6 * * *
Asia/Shanghai
```

也就是：

```text
00:00
06:00
12:00
18:00
```

Scheduler 05:00 停机，17:00 恢复：

```text
06:00
→ skipped
→ misfire_superseded

12:00
→ enqueued
→ 创建 Job / Run / Scope

18:00
→ next_run_at
```

不会再补跑 06:00。

---

## 3. 为什么不是把所有错过周期都补一遍

AIMA_UGC 是持续刷新型舆情系统。很多搜索窗口本来就重叠；如果停机 24 小时后把 4 个历史周期全部集中补跑：

- 同一关键词会大量重复搜索；
- 同一内容重复 Detail/Comment 判断；
- Provider 请求瞬时放大；
- 恢复时更慢得到“当前状态”。

因此 `latest_only` 把 Scheduler 的恢复目标定为：

> 尽快恢复最新一轮正常采集，同时把被覆盖的历史调度点作为可审计 skipped 事实保留下来。

历史漏数由搜索窗口重叠、回补、数据库去重和后续刷新共同补偿，而不是让 Scheduler 无限 catch-up。

当前没有：

```text
bounded_catch_up
strict_skip 可配置策略
max_catch_up_runs > 0
```

如果未来改变恢复策略，至少会影响：

```text
modules/collection/scheduler.py
modules/collection/planning.py
数据库 Check Constraint / Migration
bootstrap/scheduler.py
Scheduler Test
本附录 / Blueprint 07
容量和 Provider 成本评估
```

不能只在前端增加一个下拉框。

---

## 4. 当前 Cron 支持什么

领域代码：

- [`backend/src/aima_ugc/modules/collection/scheduler.py`](../../backend/src/aima_ugc/modules/collection/scheduler.py)

关键函数：

```python
next_schedule_time(schedule_expr, timezone, after)
resolve_scheduler_plan(plan, now=...)
```

当前 `schedule_expr` 是**五字段数值 Cron**：

```text
minute hour day-of-month month day-of-week
```

支持：

- `*`
- 单个数字
- `1,2,3` 列表
- `1-5` 范围
- `*/6`、`1-23/2` 步长

不支持：

- 秒字段；
- 年字段；
- 月份/星期英文名称；
- Quartz 扩展。

当前 Plan 时区固定为：

```text
Asia/Shanghai
```

数据库中的：

```text
next_run_at
last_scheduled_at
scheduled_for
```

仍是带时区时间，并按 UTC 做机器比较。

### `day-of-month` / `day-of-week`

当前实现遵循常见 Cron OR 语义：当两者都不是 `*` 时，任一条件匹配即可；其中一个是 `*` 时由另一个决定日期。

精确实现看 `_date_matches()`，不要从通用 Cron 教程猜当前行为。

---

## 5. 新 Plan 为什么不会补造历史任务

一个新建 Plan 可以：

```text
next_run_at = NULL
```

Scheduler 第一次看到它时：

```text
锁 Plan
→ 计算“当前时间之后”的第一个未来 Cron 时刻
→ 只写 next_run_at
→ 不创建 Occurrence / Run / Job
```

原因：新 Plan 在创建之前不存在，不应把过去的 Cron slot 解释成“系统停机积压”。

当前 Plan HTTP 已实现：

```text
POST /api/v1/collection-plans
GET  /api/v1/collection-plans
GET  /api/v1/collection-plans/{plan_id}
PUT  /api/v1/collection-plans/{plan_id}/enabled
```

真实装配：

- [`backend/src/aima_ugc/bootstrap/collection_strategy_http.py`](../../backend/src/aima_ugc/bootstrap/collection_strategy_http.py)

所以旧文档中“Stage 8 未来才会定义 Plan API”一类表述已经过期。

---

## 6. 一次 Scheduler tick 的真实事务链

生产代码：

- [`backend/src/aima_ugc/bootstrap/scheduler.py`](../../backend/src/aima_ugc/bootstrap/scheduler.py)

当前流程：

```text
1. 短事务预扫 schedulable Plan ID
2. 每个 Plan 单独开短事务
3. SELECT Plan ... FOR UPDATE
4. 重读当前 Plan
   - enabled
   - schedule_version
   - schedule_expr
   - timezone
   - next_run_at
   - misfire_policy
   - max_catch_up_runs
5. resolve_scheduler_plan()
6. 校验 Provider Config / Capability / Keyword Pack
7. 展开实际可执行 Scope
8. 冻结 Run Snapshot
9. 计算 Job Deadline
10. 写旧 slot 的 skipped Occurrence
11. 创建 PostgreSQL Job
12. 写最新 enqueued Occurrence
13. 创建 scheduled Run / Scope
14. 推进 last_scheduled_at / next_run_at
15. commit
```

外部 HTTP 不在这个事务里发生。

### 为什么每个 Plan 一个事务

如果一个坏 Plan 的 Cron/Provider 配置有问题，不应拖住其他几十个合法 Plan。

当前行为是：

```text
Plan A 非法
→ A 失败并记录
→ 同一 tick 继续处理 B/C/D
```

不是整个 Scheduler 进程退出。

---

## 7. Scheduler 如何保证多实例不重复

两个 Scheduler 实例可能同时预扫到同一个 Plan。

真正的防重不是进程内锁，而是：

```text
SELECT Plan ... FOR UPDATE
+ Occurrence 数据库唯一约束
```

Occurrence 唯一身份：

```text
(plan_id, schedule_version, scheduled_for)
```

场景：

```text
Scheduler A 扫到 Plan
Scheduler B 也扫到 Plan

A 先拿 FOR UPDATE
→ 创建 Occurrence / Job / Run
→ 推进 next_run_at
→ commit

B 后拿到锁
→ 重新读取 next_run_at
→ 已经在未来
→ 不再创建同 slot
```

数据库还通过延迟约束保证：

```text
enqueued Occurrence
→ 恰好一个 scheduled Run
→ Occurrence.job_id == Run.job_id

skipped Occurrence
→ 没有 Run
→ 没有 Job
```

因此“先 SELECT 看有没有，再 INSERT”不是最终防重方案；唯一约束才是最终事实。

---

## 8. Plan 修改为什么有 `schedule_version`

Occurrence 身份中包含：

```text
schedule_version
```

原因：

```text
Plan 原来 6 小时一次
→ 修改成 12 小时一次
```

不能让新旧时间表产生的逻辑 slot 混成一个版本。

修改影响调度语义的字段时，需要：

- 提升 `schedule_version`；
- 正确重算/调整 `next_run_at`；
- Scheduler 锁内只按最新版本继续。

当前启停 HTTP 已实现；其他 Plan 字段修改能力是否公开，以当前 `bootstrap/api.py + contracts/http.py` 为准，不从本文预设不存在的编辑接口。

---

## 9. Scope 在 Scheduler 里什么时候生成

Scheduler 创建 scheduled Run 前会把当前 Plan 的：

```text
平台
Provider Config
Keyword Pack
启用关键词
Decision Policy
```

展开成具体 Scope，并冻结进 Run/Snapshot。

代码：

- [`backend/src/aima_ugc/modules/collection/scheduled_scopes.py`](../../backend/src/aima_ugc/modules/collection/scheduled_scopes.py)
- [`backend/src/aima_ugc/modules/collection/run_snapshot.py`](../../backend/src/aima_ugc/modules/collection/run_snapshot.py)

这样 Worker 真正运行时，不会重新读取一个已经被管理员改过的 Keyword Pack，然后执行出另一套任务。

如果一个 due Plan 最终没有任何可执行 Scope：

```text
Scheduler fail closed
```

即使其他入口构造出 0 Scope Run，`CollectionRunExecutor` 也会 fail closed，不把“什么都没做”记成成功。

---

## 10. Job Deadline 怎样估算

Scheduled Job 的 Deadline 不是固定 300 秒，也不简单等于 Cron 周期。

当前算法考虑：

```text
本次 scheduled_for → next logical slot 的时间

以及

scope_count
× 技术页数上限
× Provider 单请求 timeout
+ 安全余量
```

取足以覆盖当前可计算执行窗口的下限。

分页上限和 timeout 会冻结到 Run Snapshot 的 `execution_limits`，作为本次任务可审计的技术事实。

它不是：

- 请求次数 Budget；
- 金额 Budget；
- Token Budget。

当前系统没有 Scheduler 预算门禁。

---

## 11. Scheduler 与 Job Retry 是两层不同恢复

### Scheduler misfire

解决：

> “本来应该在 06:00 创建任务，但 Scheduler 当时没运行。”

结果：

```text
Occurrence skipped/enqueued
```

### Worker Retry / Takeover

解决：

> “Job 已经创建，但 Worker 执行时崩了/超时了。”

结果：

```text
Job Lease / Fencing / Retry / Reaper
```

两者不能混在一起。

不要因为 Worker 有 Retry，就让 Scheduler 不记录 misfire；也不要因为 Scheduler latest-only，就取消 Job 自己的可靠恢复。

---

## 12. 当前日志怎么排 Scheduler

当前重要事件主要回答：

```text
本 tick 扫了多少 Plan？
有没有初始化 cursor？
有没有 enqueue？
有没有 skip？
哪个 Plan 为什么被拒绝？
```

`scheduler.tick.completed` 关注：

```text
scanned
initialized
enqueued
skipped
failed
duration_ms
```

空 tick 不应该每 30 秒刷 INFO；真正有初始化/入队/skip 才值得 INFO，有失败提升 WARNING，并记录对应 `scheduler.plan.rejected` 安全错误信息。

日志配置和格式见：

- [`docs/blueprint/05_日志安全部署与运维.md`](../blueprint/05_日志安全部署与运维.md)

持久化 Scheduler 事实仍以 PostgreSQL 为准，日志不是第二套任务状态库。

---

## 13. SQL 排障顺序

如果“计划应该跑但没跑”，按这个顺序查：

```text
1. collection_plans
   → enabled / schedule_expr / schedule_version / next_run_at

2. collection_schedule_occurrences
   → 该逻辑时间有没有 enqueued / skipped

3. collection_runs
   → occurrence_id / job_id / status

4. collection_scopes
   → 是否生成可执行 Scope

5. jobs
   → queued / running / succeeded / failed

6. provider_requests / attempts
   → Worker 是否真的进入 Provider 阶段
```

SQL 示例：

[`01_PostgreSQL查询与调试实战.md`](01_PostgreSQL查询与调试实战.md)

### 常见判断

```text
没有 Occurrence
→ Scheduler 没处理到 / Plan 不到期 / Plan 被拒绝

有 skipped Occurrence
→ latest_only 正常覆盖历史 slot

有 enqueued Occurrence + Run + Job
→ Scheduler 已完成职责，继续查 Worker

Job queued 很久
→ Worker/claim 问题

Job running 但无 Provider Attempt
→ Collection Scope Executor / Capability / Secret 边界
```

---

## 14. 修改 Scheduler 应该改哪些文件

### 改 Cron 解析

```text
modules/collection/scheduler.py
→ Cron unit tests
→ 本附录
```

如果公共 Contract 允许新表达式，还要改 Plan Contract/Validation。

### 改 misfire 策略

这是高风险跨层变化：

```text
planning.py
scheduler.py
collection tables / constraints
Migration
bootstrap/scheduler.py
Scheduler unit/integration tests
Blueprint 07
本附录
```

### 改 Plan → Scope 规则

```text
scheduled_scopes.py
run_snapshot.py
Keyword/Provider Capability 相关代码
Scheduler integration tests
```

### 改 Job Deadline

```text
bootstrap/scheduler.py
execution_limits.py
相关 tests
```

不要用“延长 Heartbeat 就行”替代 Deadline 设计，因为 Heartbeat 不能无限续 Attempt Deadline。

---

## 15. 测试入口

主要测试按当前仓库实际分布在：

- [`tests/unit/collection/`](../../tests/unit/collection/)
- [`tests/integration/`](../../tests/integration/)
- [`.github/workflows/runtime.yml`](../../.github/workflows/runtime.yml)：当前 Runtime Acceptance；Scheduler 进程/Compose 运行边界由这一永久 Workflow 与相关测试共同覆盖，不再存在独立 `stage7-scheduler-runtime.yml`。

关键行为至少应覆盖：

- `0 */6 * * *` 在 `Asia/Shanghai` 计算正确；
- 非 `latest_only` 关闭失败；
- `max_catch_up_runs != 0` 关闭失败；
- 新 Plan 只初始化未来 cursor；
- 多个 due slot：旧的 skipped、最新的 enqueued；
- Occurrence + Job + Run + cursor 同事务；
- 同一时间重复 tick 不重复；
- 多 Scheduler 并发最终只产生一个逻辑任务；
- 单个坏 Plan 不阻断其他合法 Plan；
- 0 Scope Run 不能成功；
- Scheduler 创建的 `collection.run.v1` 能被正式 Worker Registry 消费。

最终交付仍以 PR 最新 HEAD 的新鲜 CI 为准。

---

## 16. 当前明确没有的 Scheduler 能力

当前不要写成已经支持：

```text
每个 Plan 自定义时区
bounded catch-up
max_catch_up_runs > 0
Quartz Cron
自动 Provider API family fallback
请求/金额 Budget Guard
```

未来如果实现，要用新的代码、Contract、Migration 和测试更新本文。
