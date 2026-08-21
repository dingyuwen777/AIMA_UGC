# Scheduler 运行与恢复

这篇文档只解决一个问题：**定时采集到了时间以后，系统怎么保证不重复创建任务；如果 Scheduler 停了一段时间，恢复后又怎么处理漏过的时刻。**

长期架构原则见 [`../blueprint/04-后端任务API与前端.md`](../blueprint/04-后端任务API与前端.md) 和 [`../blueprint/07-技术决策与实施门禁.md`](../blueprint/07-技术决策与实施门禁.md)。这里讲当前实现怎么工作。

## 1. 为什么 Scheduler 不直接抓数据

如果 Scheduler 自己调用 TikHub，那么“什么时候该执行”和“实际执行是否成功”会混在一个进程里，服务重启后很难恢复。

当前职责拆开：

```text
Scheduler
→ 只判断哪些 Plan 到期
→ 创建 Occurrence + Run + Job
→ Worker 认领 Job
→ Worker 真正调用 Provider
```

所以 Scheduler 停掉不会把正在运行的 Worker 任务一起丢掉，Worker 重启也不需要重新计算调度时间。

## 2. 四个最重要的对象

### Plan

长期计划，例如：

```text
每天 00:00 / 06:00 / 12:00 / 18:00
抓小红书和抖音
使用某个关键词包
```

当前首版时区固定 `Asia/Shanghai`。

### Occurrence

“某个 Plan 的某个版本，在某个逻辑时间点应该触发一次”。

唯一身份：

```text
(plan_id, schedule_version, scheduled_for)
```

这个数据库唯一约束是防重复的最后一道事实，不依赖进程内锁。

### Run

一次实际业务运行。Run 冻结当次执行需要的配置快照，后面再修改 Plan，不反向改变已经创建的 Run。

### Job

Worker 真正认领和执行的持久任务。Run 和 Job 一一绑定。

## 3. 正常到期时发生什么

简化流程：

```text
扫描到 Plan 到期
→ 行锁重读 Plan 当前状态
→ 再次校验 Plan / Provider / 关键词是否仍可执行
→ 计算本次 scheduled_for
→ 创建 Job
→ 创建 enqueued Occurrence
→ 创建 scheduled Run
→ 推进 Plan.next_run_at
→ 同一个 PostgreSQL 事务提交
```

为什么必须同一事务？

如果先推进 `next_run_at`，后创建 Job 时崩溃，会真的漏任务；如果先创建 Job，再推进游标时崩溃，又可能重复创建。放在一个事务里，要么一起成功，要么一起回滚。

## 4. 为什么当前使用 `latest_only`

假设一个计划每 6 小时跑一次：

```text
00:00
06:00
12:00
18:00
```

Scheduler 从 00:30 一直停到 13:00。

恢复时当前策略不是把 06:00、12:00 全部补跑，而是：

```text
06:00 → skipped / misfire_superseded
12:00 → enqueued
18:00 → next_run_at
```

也就是只执行“最近一个已经到期的时刻”。

原因是采集接口往往存在时间窗口重叠，如果停机后一次补很多历史采集，不一定能多拿到数据，反而可能快速放大 Provider 请求量和重复费用。

当前数据库约束：

```text
misfire_policy = latest_only
max_catch_up_runs = 0
```

如果未来业务真的要求“停机多久就补多少次”，那是调度语义变化，需要新的设计与测试，不能只改一个循环。

## 5. 多个 Scheduler 同时跑会怎样

正常部署不需要故意启动多个 Scheduler，但系统不能依赖“永远只有一个进程”才能正确。

关键保护有两层：

1. 处理 Plan 时使用 PostgreSQL 行锁重新读取；
2. `collection_schedule_occurrences` 对 `(plan_id, schedule_version, scheduled_for)` 有唯一约束。

即使两个进程同时看到同一个到期 Plan，最终也不允许提交两个相同 Occurrence。

## 6. Plan 在扫描后被修改怎么办

Scheduler 不能：

```text
先把所有 Plan 读进内存
→ 很久以后直接按旧值创建任务
```

真正创建任务前会在事务里重新读取并校验 Plan。这样可以处理：

- Plan 刚被禁用；
- `schedule_version` 已变化；
- Provider Config 被禁用；
- 关键词已经不可执行；
- Capability 不再允许当前 Operation。

不合法的单个 Plan 会记录 rejected/失败事实，不应拖垮其他 Plan 的调度。

## 7. Scheduler 和 Worker 的恢复不是一回事

Scheduler 恢复解决：

> “哪个逻辑调度时刻需要创建任务？”

Worker/Job Runtime 恢复解决：

> “已经创建的任务，Worker 中途挂了以后谁来接手？”

后者使用 Lease、Heartbeat、Deadline 和 Fencing Token。简单理解：

- Lease：这段时间任务归哪个 Worker；
- Heartbeat：Worker 还活着；
- Deadline：这次 Attempt 最晚什么时候必须收敛；
- Fencing Token：旧 Worker 失去 Lease 后，即使它晚回来，也不能继续写业务结果。

不要用 Scheduler 重建 Job 来解决 Worker 崩溃。

## 8. Provider 请求为什么还有自己的恢复规则

外部 HTTP 有一个特殊问题：

```text
请求可能已经发出
→ 对方可能已经处理/计费
→ 本机却在收到响应前崩溃
```

这种情况下不能简单把“没有本地成功结果”当成“肯定没发出去”。

当前原则：

- 已有完整、校验通过的 Raw：优先 replay，禁止再调用 Provider；
- 明确 `not_sent`：可以按规则重试；
- 发送结果不确定：标记 `unknown`，保留潜在重复计费事实；
- 一个 Attempt 内不隐藏自动网络重发；真正重发必须创建新 Attempt。

## 9. 日志怎么看

默认 INFO 不打印每 30 秒一次的空 tick。

有意义的 Scheduler 日志：

```text
初始化 cursor / 实际入队 / 产生 skip → INFO
存在 rejected Plan               → WARNING 汇总
单个非法 Plan                     → ERROR
没有任何动作的空 tick             → DEBUG
```

人工时间显示固定北京时间 `YYYY-MM-DD HH:mm:ss.SSS`；数据库里的调度时间仍是 `timestamptz`。

## 10. 数据库排障

最近 Occurrence：

```sql
SELECT
    plan_id,
    schedule_version,
    scheduled_for,
    status,
    skip_reason,
    job_id,
    created_at
FROM collection_schedule_occurrences
ORDER BY scheduled_for DESC
LIMIT 50;
```

Plan 当前游标：

```sql
SELECT
    id,
    name,
    enabled,
    schedule_expr,
    schedule_version,
    next_run_at,
    last_scheduled_at
FROM collection_plans
ORDER BY updated_at DESC;
```

更多 SQL 见 [`PostgreSQL调试与常用SQL.md`](PostgreSQL调试与常用SQL.md)。

## 11. 当前代码入口

| 想看什么 | 位置 |
| --- | --- |
| Cron / latest_only 计算 | `backend/src/aima_ugc/modules/collection/scheduler.py` |
| Scheduler 业务装配 | `backend/src/aima_ugc/bootstrap/scheduler.py` |
| 进程入口 | `backend/src/aima_ugc/entrypoints/scheduler_main.py` |
| Plan / Occurrence Repository | `backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py` |
| Collection 当前实现说明 | `backend/src/aima_ugc/modules/collection/README.md` |
| Job Runtime | `backend/src/aima_ugc/platform/jobs/` |
| 数据库约束 | `backend/src/aima_ugc/modules/collection/tables.py` + `migrations/versions/` |

## 12. 不要误解的几件事

- `skipped` 不一定是错误；`latest_only` 恢复时它是明确保存的业务结果。
- Scheduler 不直接发 TikHub 请求。
- Heartbeat 不能无限延长 Attempt Deadline。
- 当前没有“停机后无限补跑”的能力。
- 当前 Provider Billing/成本记录不等于 Budget；系统没有请求/金额预算门禁。
- Scheduler 的精确正确性依赖 PostgreSQL 约束和事务，不依赖单机内存状态。
