# Scheduler 运行与恢复策略：当前实现导航

本文保留 `09-Scheduler运行与恢复策略.md` 这个长期入口，但只描述**当前 Scheduler 已实现事实和修改导航**。

Stage 7 当时的完整设计、验收过程和“Stage 8 未来如何修改 Plan”等时间快照没有删除，原样保存在：

[`09-Scheduler设计与Stage7验收记录.md`](09-Scheduler设计与Stage7验收记录.md)

当前更详细、面向调试的实现说明：

[`../appendix/Scheduler调度执行与停机恢复.md`](../appendix/Scheduler调度执行与停机恢复.md)

---

## 1. Scheduler 当前负责什么

Scheduler 负责把**时间计划**变成**持久化执行事实**：

```text
Collection Plan
→ 到期逻辑 slot
→ Schedule Occurrence
→ Collection Run / Scope
→ collection.run.v1 Job
→ Worker 执行真实 Collection
```

Scheduler 不负责：

- 直接调用 TikHub；
- 解析 Provider JSON；
- 写 Content Current；
- 调用 LLM；
- 生成 Excel/Word。

真实代码：

```text
领域调度算法
→ backend/src/aima_ugc/modules/collection/scheduler.py

Plan / Platform 配置
→ backend/src/aima_ugc/modules/collection/planning.py

Scope 推导
→ backend/src/aima_ugc/modules/collection/scheduled_scopes.py

生产事务编排
→ backend/src/aima_ugc/bootstrap/scheduler.py

常驻入口
→ backend/src/aima_ugc/entrypoints/scheduler_main.py

PostgreSQL Plan / Occurrence
→ backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py

Run / Scope
→ backend/src/aima_ugc/adapters/persistence/postgres/collection_run_execution.py
```

---

## 2. 当前固定停机恢复策略

当前领域和数据库只允许：

```text
misfire_policy = latest_only
max_catch_up_runs = 0
```

含义：Scheduler 停机后如果已经错过多个调度点：

```text
更早的 due slot
→ skipped / misfire_superseded

最新的 due slot
→ enqueued

下一个未来 slot
→ next_run_at
```

例如：

```text
Plan: 00:00 / 06:00 / 12:00 / 18:00
05:00 停机
17:00 恢复

06:00 → skipped / misfire_superseded
12:00 → enqueued
18:00 → next_run_at
```

不会把所有历史周期集中补跑。

为什么这样做：舆情采集强调尽快恢复“当前视图”，历史漏数由重叠搜索窗口、backfill、稳定 ID 去重和后续观察补偿；停机恢复时集中重放所有周期会制造大量重复 Provider 请求。

---

## 3. Cron 当前语义

当前 `schedule_expr` 是五字段 Cron：

```text
minute hour day-of-month month day-of-week
```

当前实现支持：

- `*`；
- 数字；
- 逗号列表；
- 范围；
- `/n` 步长。

例如：

```text
0 */6 * * *
```

当前 Plan 时区固定为：

```text
Asia/Shanghai
```

持久化 `scheduled_for / next_run_at / last_scheduled_at` 使用带时区机器时间；人工日志再按北京时间格式展示。

Cron 的精确 Parser/边界以当前 `modules/collection/scheduler.py` 和测试为准，不从文档复制实现。

---

## 4. 新 Plan 为什么不补造历史 Run

新建 Plan 初始 `next_run_at` 可以为空。

Scheduler 第一次看到它时：

```text
FOR UPDATE 重读当前 Plan
→ 从当前时刻之后计算第一个未来 Cron slot
→ 只初始化 next_run_at
→ 不创建 Plan 建立之前的 Occurrence/Run
```

“新 Plan 第一次启动”与“已有 Plan 停机后恢复”是两个不同场景，不能共用一套 backlog 逻辑。

---

## 5. Scheduler 的事务边界

一次 tick 的核心流程：

```text
预扫 schedulable Plan ID
→ 每个 Plan 独立短事务
→ SELECT ... FOR UPDATE
→ 重读 enabled / schedule_version / schedule_expr / timezone
  / next_run_at / misfire_policy / max_catch_up_runs
→ 计算 latest_only 决策
→ 校验 Provider Config / Registry / Capability / Keyword Pack
→ 推导可执行 Scope
→ 冻结 Run Snapshot / execution limits
→ 计算 Job Deadline
→ 写 skipped Occurrence
→ 创建唯一 Job
→ 写 enqueued Occurrence
→ 创建 scheduled Run / Scope
→ 推进 last_scheduled_at / next_run_at
→ commit
```

跨 Owner 编排仍遵守：

```text
Plan/Occurrence
→ Collection Planning Owner

Run/Scope
→ Collection Run Owner

Job
→ Job Owner
```

Scheduler 负责同一事务中的编排，不通过直接 SQL 绕开 Owner。

---

## 6. 可执行性门禁与 Job Deadline

Scheduler 在创建 Run/Job 前会验证：

- Provider Config 存在、启用；
- Provider + Platform 已注册；
- Capability 接受当前业务配置；
- Keyword Pack/冻结关键词可用；
- 每个平台至少能得到一个可执行 Scope。

非法 Plan fail closed，只影响该 Plan，不应让整个 tick 退出。

`collection.run.v1` 的 Deadline 不是固定 300 秒，也不简单等于 Cron 周期。当前算法会综合：

```text
scheduled_for 到下一个逻辑 slot 的窗口
与
Scope 数 × 技术分页上限 × Provider timeout + 安全余量
```

取足够保护真实执行的下限。

这些 `execution_limits` 会进入 Run Snapshot 作为可审计执行事实。它们是技术上限，不是请求次数/金额 Budget。

---

## 7. 多 Scheduler 为什么不会重复入队

同一个 Plan 可以被多个 Scheduler 预扫到，但最终决策必须在数据库行锁内完成。

Occurrence 唯一身份：

```text
(plan_id, schedule_version, scheduled_for)
```

第一个实例提交后：

```text
next_run_at 已推进
+ 唯一约束已建立
```

第二个实例拿锁后必须重读最新 Plan，不得重复创建同一 Occurrence/Run/Job。

崩溃语义：

```text
事务提交前崩溃
→ 整个事务回滚
→ 下一个 tick 重新处理

事务提交后崩溃
→ Occurrence / Job / Run / cursor 已一起存在
→ 下个 tick 不重复入队
```

---

## 8. 当前 Plan 编辑已经不是“未来 Stage 8”

历史 Stage 7 文档曾写“Stage 8 未来修改 Plan 时再定义编辑 API”。该描述现在已经过期。

当前已经存在采集策略前端和 Plan HTTP 能力，相关当前事实请看：

```text
frontend/src/features/collection-strategy/
backend/src/aima_ugc/bootstrap/api.py
backend/src/aima_ugc/contracts/http.py
```

真正修改 Plan 字段/编辑语义时，仍必须保证：

```text
schedule_version 正确提升
→ Scheduler cursor 与新版本语义一致
→ 旧版本 Occurrence 不被新版本复用
→ API / generated Client / 前端 / 测试同步
```

精确当前 API 见 `docs/API接口说明.md`，不要从 Stage 7 验收记录判断当前页面是否存在。

---

## 9. Provider 费用与 Budget 的当前边界

当前系统保留 Provider Request/Attempt 的 Pricing/Billing/费用审计事实，但**没有**：

```text
Budget Account
Reservation Ledger
发送前金额 Budget Guard
```

这不是 Stage 7 遗漏，而是后续正式决策明确移除的能力。

未来如果重新需要预算硬限制，必须独立 L3 Change 重新设计 Contract、Schema、发送前并发门禁和 Migration。

---

## 10. 排障怎么判断是哪一层

### 到点没有任何 Job

```text
collection_plans
→ next_run_at / enabled / schedule_version
→ collection_schedule_occurrences
→ scheduler.log
→ bootstrap/scheduler.py
```

### Occurrence 有了，但 Job/Run 不一致

```text
Occurrence
→ Job
→ Collection Run
→ 同一事务/FK/唯一约束
```

### Job 已经创建，但 TikHub 没发送

这已经不是 Scheduler 问题：

```text
jobs
→ Worker Claim/Fence
→ Collection Run / Scope
→ Provider Request / Attempt
→ TikHub Transport
```

### 停机恢复后重复跑历史周期

检查：

```text
misfire_policy
max_catch_up_runs
scheduled_for
Occurrence 唯一身份
next_run_at
```

详细 SQL 和恢复例子见 Scheduler Appendix 和 PostgreSQL Appendix。

---

## 11. 修改 Scheduler 应该改哪些文件

| 需求 | 修改入口 |
| --- | --- |
| 改 Cron 解析 | `modules/collection/scheduler.py` + unit tests |
| 改 misfire 策略 | Scheduler Domain + Planning Contract/Table/Migration + Bootstrap + tests + 07/08/本页 |
| 改 Plan 编辑后 cursor 行为 | Planning Service/Repository + HTTP Contract + Scheduler tests |
| 改 Scope 推导 | `scheduled_scopes.py` + Capability/Plan 测试 |
| 改 Scheduler 跨 Owner 事务 | `bootstrap/scheduler.py` + PostgreSQL integration |
| 改 Occurrence/Run 唯一性 | Table/Migration/Repository + 并发测试 |
| 改 Job Deadline | Scheduler executor-limit 计算 + Job/Collection integration |

这种修改通常不是“改一行 Cron”那么简单；只要改变持久语义或数据库约束，至少按 L2/L3 Change 处理。

---

## 12. 当前验证入口

重点包括：

- Scheduler Domain unit；
- Planning/PostgreSQL integration；
- 多 Scheduler 并发；
- Occurrence/Run/Job 同事务；
- Worker 消费 `collection.run.v1`；
- Stage 7 Scheduler Runtime Workflow；
- Stage 1-7 Audit Correctness。

当前具体测试文件以仓库 `tests/` 和 CI workflow 为准，不在本文维护第二份易漂移清单。

---

## 13. 设计演进记录

Stage 7 的完整批准说明、验收列表、当时尚未进入 Stage 8 的边界原样保存在：

[`09-Scheduler设计与Stage7验收记录.md`](09-Scheduler设计与Stage7验收记录.md)

阅读它时：

```text
Scheduler 算法/事务/恢复原则
→ 大部分仍是当前设计

“Stage 8 未来...” / “不预定义 Stage 8...”
→ 只解释当时阶段边界
→ 当前实现以本页和代码为准
```

这样既不删掉设计理由和验收证据，也不会让阶段时间快照冒充今天的机器事实。
