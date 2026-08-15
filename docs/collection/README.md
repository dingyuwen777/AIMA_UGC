# 采集能力说明

本文描述当前仓库已经落地的采集主链、Stage 7 父事实以及仍受门禁约束的能力。长期设计以 `docs/blueprint/` 为准，机器事实以代码、Migration、Contract 与测试为准。

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
- Run 的 `config_snapshot` 继续保存该次执行不可变配置快照，但 Plan / Schedule Version 的关系身份以数据库 FK 为准。

Provider Request / Attempt、Dispatch、Recovery 与预算账本继续复用现有 Stage 5D / Stage 7 生产实现。

## 3. Stage 7 已建立的 Plan 父事实

当前数据库已经存在：

- `collection_plans`
- `collection_plan_platforms`
- `collection_plan_keyword_packs`
- `collection_schedule_occurrences`
- `collection_runs.manual_plan_id`
- `collection_runs.occurrence_id`

### 3.1 Plan

首版 Plan 时区只允许 `Asia/Shanghai`。`schedule_version` 从 1 开始，`request_budget`、`max_catch_up_runs` 不能为负数。

`misfire_policy` 与 `max_catch_up_runs` 当前只是调用方显式提供并持久化的字段；仓库尚未批准 Scheduler 如何解释它们，因此不能从这些字段已经存在推断 Scheduler 已完成。

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

数据库 deferred constraint 在事务提交前继续验证：

- `enqueued` Occurrence 恰好有一个反向 `scheduled` Run；
- Occurrence 与 Run 使用同一个 Job；
- `skipped` Occurrence 没有 Run。

因此 Job、Occurrence、Run 可以在一个事务内按合理顺序建立，但不能在提交后留下半套父事实。

## 4. Stage 7 其他已经落地能力

除 Plan 父事实外，Stage 7 当前还已经建立：

- Provider Config Registry / `secret_ref` 路由；
- Keyword / Keyword Pack 与数据库级并发串行化；
- XHS Unified Operation → Raw → Mapper → Canonical / Ingestion 纵向链路；
- Provider Budget Account / Reservation 账本；
- 请求级、全局、Run、Run Comment、Content Comment 预算维度与 `unknown` 保守结算。

## 5. 当前仍未闭环的 Stage 7 能力

Stage 7 仍为进行中，主要剩余：

1. 抖音、微博、B 站、快手四平台合法脱敏真实 Fixture、Mapper / Ingestion 纵切，以及对应 billable endpoint 定价从 `pending` 升级为经正式 Probe 验证；
2. Unified Operation 真实 Provider Probe 与业务 Pipeline Probe / Export；
3. Scheduler Runtime。

Scheduler Runtime 仍受以下决策门禁约束：

- `misfire_policy` 的允许值与精确语义；
- `max_catch_up_runs` 的追赶上限和停止条件；
- 停机恢复产生的请求成本与容量上界。

在这些事实被批准前，可以继续完善不依赖该语义的父事实和 Provider 纵切，但不得自行猜 Scheduler 默认策略。

## 6. 测试与调试

- 调试复用生产 Service / Repository / Provider Client，不实现第二套路径；
- 数据库变化必须验证 Alembic 上一正式 Revision → head、base → head、downgrade / upgrade 与 drift；
- Contract / Architecture / Table Ownership / Secret / Docs 门禁必须保持绿色；
- 真实付费 Provider Probe 默认不进入普通 CI，需要显式授权和可用网络环境；
- 不能用 Fixture 测试冒充真实 TikHub 成功调用。
