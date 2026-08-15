# 采集能力说明

本文描述当前仓库已经落地的采集主链、Stage 7 运行事实以及仍受门禁约束的能力。长期设计以 `docs/blueprint/` 为准，机器事实以代码、Migration、Contract 与测试为准。

## 1. 当前稳定主链

采集主链保持：

`Plan / Run / Scope → Provider Request / Attempt → Raw Artifact → Mapper → Candidate → Canonical / Ingestion`

边界要求：

- Provider 负责外部 API 调用，不直接写业务表；
- Raw Artifact 先于 Mapper 保存；
- Mapper 只做纯映射，不访问数据库、不发 HTTP；
- Canonical 表由对应业务 Owner 写入；
- Provider 私有 cursor / page / search_id 等分页状态只留在 Provider Request / Attempt / Scope；
- Secret 不进入代码、日志、Raw、Job Payload、Plan 配置或数据库明文。

## 2. Run / Scope 与 Provider 执行

`CollectionExecutionService + PostgresCollectionRepository` 创建 Run / Scope 父事实，一个 Run 仍只绑定一个 Job。

当前 Run 触发方式：

- `manual`
- `api`
- `backfill`
- `scheduled`

其中：

- `manual/api/backfill` 保持既有兼容行为，并可选记录 `manual_plan_id`；
- `scheduled` 必须绑定唯一 `occurrence_id`，不得重复写 `manual_plan_id`；
- Run 的 `config_snapshot` 保存该次执行不可变配置快照，但 Plan / Schedule Version 的关系身份以数据库 FK 为准。

Provider Request / Attempt、Dispatch、Recovery 与预算账本继续复用现有 Stage 5D / Stage 7 生产实现。

## 3. Stage 7 Plan 与 Scheduler 事实

当前数据库已经存在：

- `collection_plans`
- `collection_plan_platforms`
- `collection_plan_keyword_packs`
- `collection_schedule_occurrences`
- `collection_runs.manual_plan_id`
- `collection_runs.occurrence_id`

### 3.1 Plan 与已批准恢复策略

首版 Plan 固定：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

领域层和数据库都拒绝与该策略冲突的 Plan。完整语义见 [Scheduler 运行与恢复策略](../blueprint/09-Scheduler运行与恢复策略.md)。

停机恢复若累计多个到期 slot：

- 最新一个创建 `enqueued` Occurrence；
- 更早的 slot 创建 `skipped` Occurrence；
- `skip_reason = misfire_superseded`；
- 不额外执行历史 Run；
- `last_scheduled_at` 推进到最新已处理 slot；
- `next_run_at` 推进到第一个未来 slot。

### 3.2 Plan → Platform

Plan 的平台配置通过 `collection_plan_platforms` 保存：

- 一个 Plan 的同一 `platform` 只能出现一次；
- Provider 选择通过稳定 `provider_config_id` 引用 `provider_configs`；
- `config` 只保存平台业务配置 JSON object；
- API Key、Token、Cookie、Password 等 Secret 形态字段由领域入口拒绝；
- Provider 私有分页状态不属于 Plan 配置。

### 3.3 Plan → Keyword Pack

Plan 与关键词包通过 `collection_plan_keyword_packs` 建立真实关联，不把词包 ID 列表塞入 Plan JSON。

### 3.4 Schedule Occurrence

Occurrence 唯一身份为：

`(plan_id, schedule_version, scheduled_for)`

状态只允许：

- `enqueued`：必须有唯一 `job_id`，不得有 `skip_reason`；
- `skipped`：不得有 Job，必须有非空 `skip_reason`。

数据库 deferred constraint 在事务提交前验证：

- `enqueued` Occurrence 恰好有一个反向 `scheduled` Run；
- Occurrence 与 Run 使用同一个 Job；
- `skipped` Occurrence 没有 Run。

### 3.5 Scheduler Runtime

Scheduler 已实现首版持久化 Runtime：

```text
预扫可调度 Plan ID
→ 每个 Plan 独立短事务
→ SELECT ... FOR UPDATE 重读当前 Plan
→ 解析五字段数值 Cron
→ 计算 latest-only 决策
→ 写 skipped Occurrence
→ 写 Job
→ 写 enqueued Occurrence
→ 写 scheduled Run
→ 推进 last_scheduled_at / next_run_at
→ commit
```

当前五字段 Cron 支持数字、`*`、列表、范围和步长，不支持秒字段、年份字段、月份/星期英文名称或 Quartz 扩展。

多 Scheduler 可以同时预扫同一 Plan，但最终决定在 PostgreSQL 行锁内完成；第二个 Scheduler 必须重读已推进后的 cursor，因此不能重复创建同一 Occurrence/Run/Job。

## 4. Stage 7 其他已经落地能力

当前还已经建立：

- Provider Config Registry / `secret_ref` 路由；
- Keyword / Keyword Pack 与数据库级并发串行化；
- XHS Unified Operation → Raw → Mapper → Canonical / Ingestion 纵向链路；
- Provider Budget Account / Reservation 账本；
- 请求级、全局、Run、Run Comment、Content Comment 预算维度与 `unknown` 保守结算；
- XHS 已存 Raw Replay Job Handler，用于把既有 Raw 重新走正式 Mapper / Ingestion，不重新发 Provider HTTP。

## 5. 当前仍未闭环的 Stage 7 能力

Stage 7 仍为进行中，当前不能因为 Scheduler 已能创建持久化 Job 就宣称自动采集完整闭环。主要剩余：

1. **正式 Collection Run Worker Handler**：Scheduler 当前能够原子创建 scheduled Job / Occurrence / Run，但生产 Worker 尚未注册可消费该 scheduled collection Job 的正式 Handler；必须复用现有 Run/Scope、Provider Routing、Pricing/Budget、Dispatch、Raw、Mapper、Ingestion 链路，不能注册空 Handler 或第二套采集实现；
2. **抖音、微博、B 站、快手真实兼容**：四平台仍缺当前目标 Operation 的合法取得、脱敏、非空真实 Fixture，以及基于该 Fixture 的 Mapper / Canonical Contract；没有这些证据不得编造字段或标记兼容；
3. **统一 Operation / Business Pipeline Probe**：真实 Probe 必须复用生产 Registry / Operation / Mapper / Decision Service；billable endpoint 在 endpoint 级 Pricing 未核验时发送前 fail closed；
4. **人工审阅导出与最终 Stage 7 集成证据**：真实付费 Probe 默认不进普通 CI，XLSX 只做人读视图，Raw/Canonical/Decision 仍是机器事实。

## 6. 测试与调试

- 调试复用生产 Service / Repository / Provider Operation，不实现第二套路径；
- Scheduler 专项必须验证 latest-only、并发去重、重复 tick 幂等、Plan 行锁重读、Migration drift 与 round-trip；
- 数据库变化必须验证 Alembic 上一正式 Revision → head、base → head、downgrade / upgrade 与 `alembic check`；
- Contract / Architecture / Table Ownership / Secret / Docs 门禁必须保持绿色；
- 真实付费 Provider Probe 默认不进入普通 CI，需要显式授权、可用网络以及 endpoint 级 Pricing 事实；
- 不能用 Fixture 测试冒充真实 TikHub 成功调用，也不能用旧版本 Provider 响应冒充当前 Operation 的兼容性证据。
