# Collection 模块

Collection 负责“**什么时候采、采什么、通过哪个 Provider 采、一次采集运行到哪一步、外部请求到底发了几次、Raw/Candidate/Scope 如何追溯**”。

它不拥有最终 Content Current，也不把 TikHub JSON 直接写进 `contents`。

如果第一次读这个模块，先记住主链：

```text
Plan / API Run
→ Collection Run
→ Scope
→ Provider Request
→ Provider Attempt
→ Raw Artifact
→ Candidate
→ Operation / Mapper
→ Canonical
→ Relevance / Decision
→ ContentIngestionService
→ Content Owner
```

系统级设计：

- `docs/blueprint/02_采集系统与数据标准化.md`
- `docs/blueprint/08_采集策略与平台能力.md`
- `docs/appendix/05_Scheduler调度执行与停机恢复.md`
- `docs/appendix/02_TikHub五平台真实响应与字段映射.md`

---

## 1. Collection 拥有什么，不拥有什么

### Collection Owner 的事实

当前主要表：

```text
collection_plans
collection_plan_platforms
collection_plan_keyword_packs
collection_plan_decision_policies
collection_schedule_occurrences
collection_runs
collection_scopes
collection_content_actions
provider_requests
provider_request_attempts
collection_candidates
collection_candidate_ingestions
```

精确 Schema：

```text
modules/collection/tables.py
modules/collection/candidate_tables.py
modules/collection/corrective_tables.py
modules/collection/scheduler_schema.py
```

### Collection 不拥有

```text
contents / comments
→ content Owner

processing_import_batches
→ ingestion Owner

analysis_content_*
→ analysis Owner

jobs
→ platform/jobs Owner

artifacts
→ platform/storage Owner
```

Collection 可以在同一事务里协调这些 Owner 的公开 Repository/Service，但不能自己偷偷 UPDATE 别人的表。

---

## 2. 当前目录应该怎么读

### 2.1 Plan / Scheduler

```text
planning.py
→ Plan 领域模型、平台/词包配置和领域校验

scheduler.py
→ Cron 计算、latest_only、misfire 决策

scheduled_scopes.py
→ 从 Plan + Keyword Pack 展开实际 Scope

scheduler_schema.py
→ Scheduler 相关数据库补充约束注册
```

生产 Scheduler 装配不在本目录，而在：

```text
backend/src/aima_ugc/bootstrap/scheduler.py
```

PostgreSQL Plan / Occurrence Repository：

```text
backend/src/aima_ugc/adapters/persistence/postgres/collection_planning.py
```

### 2.2 Run / Scope

```text
execution.py
→ Collection Run / Scope 的领域记录和创建边界

collection_run_job.py
→ collection.run.v1 Job Payload / Handler

collection_run_executor.py
→ Run 的总体执行器、Scope 生命周期、Run 终态

execution_limits.py
→ Provider 执行上限的技术边界

run_snapshot.py
→ Run Snapshot 中稳定执行事实的结构
```

真正把 TikHub、Raw、Mapper、Ingestion 串起来：

```text
backend/src/aima_ugc/bootstrap/collection_scope.py
```

### 2.3 Provider Request / Attempt

```text
provider_persistence.py
→ Request / Attempt 领域 Port 和持久化边界

provider_dispatch.py
→ 一次 Attempt 的真实发送、Raw、失败收口

provider_recovery.py
→ takeover/recovery；已有完整 Raw 时避免再次发送

provider_routing.py
→ Provider Config / Registry / Capability 路由

providers/
→ Provider-neutral Protocol / Raw Service 等公共接口
```

TikHub 的具体 HTTP endpoint 不在 Collection Domain 里硬编码，而在：

```text
backend/src/aima_ugc/adapters/providers/tikhub/
```

### 2.4 Candidate / Decision

```text
candidates.py
candidate_tables.py
→ Raw 之后、Mapper 之前的 Candidate 来源账本

decision.py
corrective_tables.py
→ Detail / Comment / Refresh 等 Decision Pipeline 与持久 action/checkpoint
```

Candidate 的意义不是再造一份 Content，而是记录：

> 这次 Provider 响应里发现了什么来源项，以及这个来源项后来有没有成功进入 Canonical/Ingestion。

### 2.5 HTTP / Runtime Read Model

```text
http.py
→ Collection HTTP Port / 异常

strategy_http.py
→ Plan / Keyword Strategy HTTP Port

runtime_query.py
runtime_cursor.py
→ 采集运行中心的只读模型和 Cursor
```

生产 HTTP 实现：

```text
backend/src/aima_ugc/bootstrap/collection_http.py
backend/src/aima_ugc/bootstrap/collection_strategy_http.py
```

---

## 3. 一次正式 Collection Run 怎样执行

### 3.1 创建 Run

当前 API：

```text
POST /api/v1/collection-runs
```

入口：

```text
bootstrap/api.py
→ bootstrap/collection_http.py
```

Run 创建时会冻结当前需要的执行事实，例如：

- 目标平台；
- Provider Config；
- 一次性关键词或 Batch supplement 来源；
- Relevance Snapshot；
- Include Comments / Sub-comments；
- 技术执行限制。

随后创建：

```text
collection.run.v1 Job
+ collection_runs
+ collection_scopes
```

### 3.2 Worker 消费 Run

```text
bootstrap/worker.py
→ CollectionRunJobHandler
→ CollectionRunExecutor
→ TikHubCollectionScopeExecutor
```

`CollectionRunExecutor` 负责 Run/Scope 生命周期；`TikHubCollectionScopeExecutor` 负责真正的 Provider 执行、Raw、Candidate、Mapper、Ingestion。

### 3.3 0 Scope 为什么 fail closed

一个 Collection Run 如果没有任何可执行 Scope，不应该被记成“成功但什么都没做”。

当前 `CollectionRunExecutor` 对 0 Scope Run 关闭失败；相关回归测试位于：

```text
tests/unit/collection/
```

---

## 4. Provider Request 和 Attempt 为什么分开

### Request

代表逻辑业务请求，例如：

```text
对 xiaohongshu 搜索关键词“爱玛”第一页
```

### Attempt

代表一次真实发送尝试。

```text
Request #A
├─ Attempt 1
└─ Attempt 2（只有明确需要重发时才创建）
```

硬规则：

```text
一个 Attempt 最多一次真实网络发送
```

Transport 不允许偷偷自动重试同一个 Attempt。

这样才能准确回答：

- 实际发了几次；
- 哪次响应生成了 Raw；
- 哪次可能重复计费；
- 网络结果未知时是否可以安全重发。

---

## 5. Provider Recovery 怎么工作

最重要规则：

```text
完整且校验通过的 Raw 已经存在
→ 优先 replay
→ 不再次请求 Provider
```

代码：

```text
provider_recovery.py
provider_dispatch.py
```

网络失败要区分：

```text
not_sent
→ 可以证明没有发出去

unknown
→ 可能已经发出，结果未知
```

`unknown` 不能简单当作“没发过”立即重发，否则可能产生重复调用/重复计费。

当前不自动从 TikHub App API 切到 Web API，也不自动从 V2 切到 V1。API family 备用策略见：

```text
docs/appendix/03_TikHub多接口验证与备用策略.md
```

---

## 6. Raw 为什么必须先于 Mapper

主链要求：

```text
Provider Response
→ 先写不可变 Raw Artifact
→ 再 Extract / Candidate / Mapper
```

这样 Mapper 出 Bug 时可以：

```text
旧 Raw
→ 修 Mapper
→ replay
→ 不重新付费请求 TikHub
```

xiaohongshu 当前还有专门的 Raw Replay 实现：

```text
xiaohongshu_replay.py
```

Raw 不等于业务 Current。Raw 只保存“Provider 当时返回了什么”。

---

## 7. Candidate 为什么在 Mapper 前

Candidate 解决一个审计问题：

> Provider 响应里明明有一个来源项，但最后数据库为什么没有对应 Content？

如果直接：

```text
Raw → Mapper → Content
```

Mapper 失败或 Relevance 过滤后，很难知道来源项在哪里丢失。

所以当前：

```text
Raw
→ Candidate（来源项身份）
→ Mapper
→ Canonical
→ Decision / Relevance
→ Ingestion
→ Candidate Ingestion 结果
```

Candidate 不复制最终业务字段，也不代替 Content。

---

## 8. Decision Pipeline 做什么

Collection 不应该每次发现内容都无脑：

```text
抓 Detail
抓所有评论
抓所有二级回复
```

这会产生大量重复成本。

当前 Decision 相关代码：

```text
decision.py
collection_content_actions
```

它根据：

- 当前已有 Content；
- 指标变化；
- 评论覆盖；
- Detail/Comment Policy；
- 已完成 Action/Checkpoint；

决定后续是否需要：

```text
fetch_detail
fetch_comments
fetch_sub_comments
skip / refresh
```

具体平台能力和采集策略见 Blueprint 08。

---

## 9. Scheduler 当前怎样创建 Run

当前领域算法：

```text
scheduler.py
```

固定恢复策略：

```text
timezone = Asia/Shanghai
misfire_policy = latest_only
max_catch_up_runs = 0
```

Scheduler tick：

```text
扫描 due Plan
→ 每个 Plan 独立短事务
→ SELECT ... FOR UPDATE
→ 计算逻辑 slot
→ skipped old occurrences
→ enqueue latest occurrence
→ Job + scheduled Run + Scope
→ 推进 cursor
→ commit
```

Occurrence 唯一身份：

```text
(plan_id, schedule_version, scheduled_for)
```

详细代码和恢复案例：

```text
docs/appendix/05_Scheduler调度执行与停机恢复.md
```

---

## 10. 当前 HTTP 能力

Collection Runtime：

```text
GET  /api/v1/collection-capabilities
POST /api/v1/collection-runs
GET  /api/v1/collection-runs/{run_id}
GET  /api/v1/collection-runtime/runs
GET  /api/v1/collection-runtime/summary
```

Strategy：

```text
POST /api/v1/collection-plans
GET  /api/v1/collection-plans
GET  /api/v1/collection-plans/{plan_id}
PUT  /api/v1/collection-plans/{plan_id}/enabled

GET  /api/v1/keyword-packs
PUT  /api/v1/keyword-packs/{pack_id}/enabled
```

Search 参数的机器链是：

```text
ProviderPlatformCapabilityV1
→ CollectionCapabilityResponse.search
→ CollectionSearchConfig
→ Plan platform config / Run provider snapshot
```

`search_config.py` 负责从 Capability 提取合法值、生成手工 Discovery 默认值并执行统一校验。手工 Discovery 的默认意图是 `latest + 1d + all`，只应用平台真实支持的维度；新 Plan 要求所有受支持维度完整配置。历史 Plan 的空 `config={}` 仍按非完整兼容模式通过 Scheduler 校验，不能被补写成手工默认。

完整 Route 以：

```text
backend/src/aima_ugc/bootstrap/api.py
```

为准。

---

## 11. 采集运行中心不是一张万能表

前端 `/collection-runtime` 需要同时展示：

```text
Excel Import
TikHub Discovery Run
TikHub Batch Supplement Run
```

当前做法是 Query Read Model：

```text
PostgreSQL 不同 Owner 表
→ Query Adapter / UNION
→ CollectionRuntimeItemResponse
→ 前端
```

相关代码：

```text
runtime_query.py
runtime_cursor.py
backend/src/aima_ugc/adapters/persistence/postgres/collection_runtime_queries.py
```

不能因为页面想统一展示，就把 Import Batch 和 Collection Run 合并成一张业务表。

---

## 12. TikHub 具体实现去哪里看

### Operation

```text
backend/src/aima_ugc/adapters/providers/tikhub/operations/
```

回答：

- endpoint；
- method；
- 参数；
- 分页；
- item extractor。

### Mapper

```text
backend/src/aima_ugc/adapters/providers/tikhub/mappers/
```

回答：

- Provider JSON → Canonical；
- `observed_fields`；
- 评论 root/parent；
- 外部 ID 归一化。

### Capability

```text
backend/src/aima_ugc/adapters/providers/tikhub/capabilities.py
```

回答：某个平台当前正式支持哪些 Search/Detail/Comment/Reply 能力。

### Runtime / Transport / Pricing

```text
runtime.py
transport.py
pricing.py
pricing.toml
```

真实响应/Fixture：

```text
docs/appendix/02_TikHub五平台真实响应与字段映射.md
tests/fixtures/providers/tikhub/
```

---

## 13. 修改 Collection 时常见改法

### 换一个 TikHub endpoint

通常先改：

```text
adapters/providers/tikhub/operations/<platform>.py
```

如果响应结构变了，再改：

```text
mappers/<platform>.py
Fixture
Mapper/Operation Test
Capability / Pricing（按影响）
```

不要直接改 `collection_run_executor.py`。

### 改 Scheduler 策略

```text
scheduler.py
→ scheduler domain test
→ bootstrap/scheduler.py
→ collection_planning Repository
→ Schema/Migration（如约束变化）
→ Scheduler Appendix
```

### 改 Detail/Comment Decision

```text
decision.py
→ action/checkpoint persistence
→ collection_scope.py
→ Unit / Integration Test
```

### 改 Run/Scope 状态

```text
execution.py
collection_run_executor.py
tables.py
Postgres Run Repository
Migration（如果数据库约束变化）
```

---

## 14. 调试一条采集链怎么查

建议顺序：

```text
1. collection_runs
2. collection_scopes
3. provider_requests
4. provider_request_attempts
5. Raw Artifact
6. collection_candidates
7. collection_candidate_ingestions
8. contents / comments
```

SQL 示例：

```text
docs/appendix/01_PostgreSQL查询与调试实战.md
```

如果 Provider 返回字段不对：

```text
Raw Fixture
→ Operation extractor
→ Mapper
→ Canonical Contract
```

如果 Content 没入库但 Candidate 有：

```text
Candidate Ingestion
→ Relevance / Decision
→ Mapper error
→ Content Ingestion error
```

---

## 15. 测试入口

主要测试：

```text
tests/unit/collection/
tests/contracts/
tests/integration/
tests/fixtures/providers/tikhub/
```

修改不同能力时不要只跑一个“大而全”的测试：

```text
Scheduler 改动
→ scheduler unit + PostgreSQL scheduler integration

Provider shape 改动
→ fixture + operation/mapper contract tests

Run executor 改动
→ collection executor unit + Worker vertical slice
```

最终仍以 PR 最新 HEAD 的完整 CI 为准。
