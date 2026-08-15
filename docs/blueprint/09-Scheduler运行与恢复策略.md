# Scheduler 运行与恢复策略

> 状态：已批准设计；Stage 7 正在实现与验证  
> 首版时区：`Asia/Shanghai`  
> 批准日期：2026-08-15

本文冻结 AIMA_UGC 首版 Scheduler 的运行、停机恢复、并发和持久化语义。它补充 `04-后端任务API与前端.md` 中的 Scheduler 事务流程，以及 `07-技术决策与实施门禁.md`、`08-采集策略与平台能力.md` 中此前尚未批准的 misfire/catch-up 门禁。

如果本文与未更新的旧摘要冲突，以本文的已批准 Scheduler 决策和当前机器实现/测试为准；旧摘要应在后续文档同步中删除“misfire 尚未决定”的表述，而不是保留两套语义。

## 1. 已批准的停机恢复方案

首版固定：

```text
misfire_policy = latest_only
max_catch_up_runs = 0
```

当 Scheduler 停机后恢复，若同一个 Plan 已累计多个到期逻辑调度点：

1. 只把**最新一个**到期调度点创建为 `enqueued` Occurrence；
2. 更早的到期调度点逐个记录为 `skipped` Occurrence；
3. 跳过原因为稳定值：

```text
misfire_superseded
```

4. `max_catch_up_runs=0` 表示不再额外执行历史 Run；
5. `last_scheduled_at` 推进到本次已处理的最新逻辑调度点；
6. `next_run_at` 推进到严格位于当前 Scheduler 时间之后的下一个未来调度点。

例如 Plan 为本地时间：

```text
00:00 / 06:00 / 12:00 / 18:00
```

Scheduler 在 05:00 停机、17:00 恢复，则：

```text
06:00 → skipped / misfire_superseded
12:00 → enqueued
18:00 → next_run_at
```

不补跑 06:00 的历史采集 Run。

## 2. 为什么采用 latest-only

AIMA_UGC 是持续刷新型舆情监控系统，不是要求每一个调度批次都不可缺失的账务系统。恢复后的首要目标是尽快得到当前舆情状态，同时控制第三方 API 成本和恢复压力。

`latest_only` 的收益：

- 服务恢复后立即执行最近一个已错过周期，不额外等待下一个未来周期；
- 不会因长时间停机形成 TikHub 集中补跑和费用突增；
- 避免大量重叠搜索窗口重复请求；
- 历史漏数风险由搜索窗口重叠、backfill、去重和历史刷新机制负责补偿；
- Scheduler 状态清晰，所有被覆盖的历史 slot 仍有 `skipped` 审计事实。

以下方案首版不采用：

- `bounded_catch_up`：恢复时额外执行最近 N 个历史周期；
- `strict_skip`：错过的周期全部跳过并等待下一个未来周期。

后续如需改变策略，必须作为新的高风险 Change 处理，同时修改数据库约束、Domain、Scheduler、测试、Blueprint 和成本评估，不能只改前端参数。

## 3. 首版 Schedule Expression

首版 `schedule_expr` 使用**五字段数值 Cron**：

```text
minute hour day-of-month month day-of-week
```

首版解析器支持：

- `*`；
- 单个数字；
- 逗号列表；
- `a-b` 范围；
- `/n` 步长，例如 `*/6`、`1-23/2`。

不支持月份/星期英文名称、秒字段、年份字段或 Quartz 扩展。

示例：

```text
0 */6 * * *
```

表示按 Plan 的 `timezone` 每 6 小时整点触发。首版 Plan 时区仍固定 `Asia/Shanghai`；持久化的 `next_run_at`、`last_scheduled_at`、Occurrence `scheduled_for` 使用带时区时间并按 UTC 统一比较。

`day-of-month` 与 `day-of-week` 同时为限制条件时遵循常见 Cron OR 语义；其中任一字段为 `*` 时，另一个限制字段决定日期匹配。

## 4. 新 Plan 初始化

新建的定时 Plan 初始 `next_run_at` 可以为空。Scheduler 第一次扫描到它时：

1. 锁定并重读 Plan；
2. 从“当前时刻之后”计算第一个未来 Cron 时刻；
3. 只写入 `next_run_at`；
4. 不为 Plan 创建之前或 Scheduler 尚未初始化之前的时间点补造 Occurrence/Run。

这样避免把“新建 Plan”错误解释为“历史停机积压”。

## 5. Scheduler 事务边界

Scheduler 不执行 TikHub HTTP，也不建立第二套内存任务队列。正式任务事实仍是 PostgreSQL Job Runtime。

一次 tick：

```text
短事务预扫 schedulable Plan ID
→ 每个 Plan 单独开启短事务
→ SELECT Plan ... FOR UPDATE
→ 重读 enabled / schedule_version / schedule_expr / timezone
  / next_run_at / misfire_policy / max_catch_up_runs
→ 计算 latest-only 决策
→ 写更早的 skipped Occurrence
→ 通过 PostgresJobRepository 创建唯一 Job
→ 写最新 enqueued Occurrence
→ 通过 CollectionExecutionService 创建 scheduled Run
→ 推进 last_scheduled_at / next_run_at
→ commit
```

必须保持：

- Job 由 Job Owner Repository 写；
- Run 由 Collection Run Owner Repository 写；
- Plan/Occurrence 由 Collection Planning Repository 写；
- Scheduler 只负责跨 Owner 的同事务编排，不直接越权写别的 Owner 表；
- `enqueued` Occurrence、Job、scheduled Run 和 cursor 推进必须同事务提交；
- `skipped` Occurrence 不得关联 Job/Run。

## 6. 并发与幂等

同一个 Plan 可以被多个 Scheduler 实例预扫到，但只能在数据库行锁内作最终决定。

第一实例提交后，第二实例拿到 Plan 锁时必须重新读取最新 `next_run_at`。如果第一个实例已经推进到未来，第二个实例不得再次创建相同 Occurrence/Run/Job。

数据库继续以：

```text
(plan_id, schedule_version, scheduled_for)
```

作为 Occurrence 唯一身份。

Scheduler Job 的内部幂等键包含：

```text
plan_id + schedule_version + scheduled_for
```

事务提交前数据库 deferred constraint 继续保证：

- `enqueued` Occurrence 恰有一个 scheduled Run；
- Occurrence 与 Run 使用同一个 Job；
- `skipped` Occurrence 没有 Run。

若进程在事务提交前崩溃，整个事务回滚；下一次 tick 重新处理。若事务已提交，cursor 和唯一约束使重复 tick 不重复入队。

## 7. Plan 变更和禁用

预扫不是执行授权。Plan ID 进入预扫集合后，Scheduler 在 `FOR UPDATE` 内必须重新读取当前事实：

- 已禁用 → 不创建新的 Occurrence/Job/Run；
- `schedule_expr` 已取消 → 不创建新的定时任务；
- `schedule_version` 已变化 → 只按锁内读到的新版本事实计算，绝不能继续提交旧版本 Occurrence；
- 策略不再是 `latest_only` 或 `max_catch_up_runs != 0` → 首版 fail closed，不自行解释。

Stage 8 未来修改 Plan 时必须负责正确提升 `schedule_version` 和重置/调整 Scheduler cursor；在 Stage 8 Contract 冻结前，不在本阶段提前发明编辑 API 语义。

## 8. 成本和故障保护

`latest_only` 只是 Scheduler 第一层恢复限流，不能替代 Provider Budget Ledger。

真实 Provider HTTP 仍必须：

```text
Plan request_budget
→ global/run/run_comments/content_comments 预算
→ endpoint Pricing 已核验
→ Provider Request / Attempt
```

Pricing 未核验仍必须发送前 fail closed，不能因为 Scheduler 已经创建 Job 就绕过价格门禁。

如果一个 Plan 的历史积压逻辑 slot 数异常巨大，Scheduler 应 fail closed 并要求人工确认，而不是在一个事务中无限创建 skipped 行。

## 9. 日志与可观测性

Scheduler 的有用日志至少应能回答：

- 本次预扫多少 Plan；
- 初始化多少 Plan cursor；
- 入队多少最新 Occurrence；
- 因 `misfire_superseded` 跳过多少历史 slot；
- 哪个 Plan 因非法策略、非法 Cron 或异常 backlog fail closed；
- 一个 tick 是否完成。

日志不得包含 Provider Secret、Cookie、Authorization、完整第三方 Raw 或其他敏感数据。

## 10. Stage 7 验收

Scheduler Runtime 至少需要机器证明：

- Domain 拒绝非 `latest_only` 和 `max_catch_up_runs != 0`；
- PostgreSQL 同样拒绝不批准的策略；
- `0 */6 * * *` 在 `Asia/Shanghai` 的计算正确；
- 新 Plan 只初始化未来 cursor，不造历史 Run；
- 多个 due slot 恢复时更早 slot skipped、最新 slot enqueued；
- Job + Occurrence + scheduled Run + cursor 同事务一致；
- 同一时间重复 tick 不重复入队；
- 两个 Scheduler 并发处理同一 Plan 最终只有一个有效 Job/Run/Occurrence；
- Migration upgrade/downgrade、`alembic check` 和相关质量门禁通过。

在以上机器证据全部通过前，只能说“决策已批准、实现进行中”，不能把 Stage 7 Scheduler 标记完成。
